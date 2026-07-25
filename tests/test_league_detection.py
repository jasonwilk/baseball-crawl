"""Tests for league/level detection function.

Tests ``detect_league_level()`` and supporting helpers in
``src/reports/starter_prediction.py``.
"""

from __future__ import annotations

import datetime
import logging

from src.api.db import build_pitcher_profiles
from src.reports.starter_prediction import (
    NSAA_SUBVARSITY,
    compute_starter_prediction,
    detect_league_level,
    get_rules_for_league,
    get_subvarsity_rules,
)


# ── Priority 1: DB fields (tracked teams) ─────────────────────────────


class TestDBFieldDetection:
    """AC-1 through AC-5: program_type + classification from DB."""

    def test_hs_varsity(self) -> None:
        """AC-1: hs + varsity → nsaa_varsity."""
        assert detect_league_level(
            program_type="hs", classification="varsity",
        ) == "nsaa_varsity"

    def test_hs_jv(self) -> None:
        """AC-2: hs + jv → nsaa_subvarsity."""
        assert detect_league_level(
            program_type="hs", classification="jv",
        ) == "nsaa_subvarsity"

    def test_hs_freshman(self) -> None:
        """AC-2: hs + freshman → nsaa_subvarsity."""
        assert detect_league_level(
            program_type="hs", classification="freshman",
        ) == "nsaa_subvarsity"

    def test_hs_reserve(self) -> None:
        """AC-2: hs + reserve → nsaa_subvarsity."""
        assert detect_league_level(
            program_type="hs", classification="reserve",
        ) == "nsaa_subvarsity"

    def test_hs_null_classification(self) -> None:
        """AC-3: hs + NULL classification → nsaa_varsity (default)."""
        assert detect_league_level(
            program_type="hs", classification=None,
        ) == "nsaa_varsity"

    def test_legion(self) -> None:
        """AC-4: legion program_type → legion."""
        assert detect_league_level(program_type="legion") == "legion"

    def test_usssa(self) -> None:
        """AC-5: usssa program_type → usssa."""
        assert detect_league_level(program_type="usssa") == "usssa"

    def test_db_fields_take_priority_over_ngb(self) -> None:
        """DB fields short-circuit NGB parsing."""
        assert detect_league_level(
            program_type="hs",
            classification="varsity",
            ngb='["usssa"]',
            team_name="Some USSSA Team 14U",
        ) == "nsaa_varsity"


# ── Priority 2: NGB + age_group (GC public API) ───────────────────────


class TestNGBDetection:
    """AC-6 through AC-8, AC-10: ngb-based detection."""

    def test_ngb_american_legion(self) -> None:
        """AC-6: ngb=american_legion → legion."""
        assert detect_league_level(
            ngb='["american_legion"]',
        ) == "legion"

    def test_ngb_usssa(self) -> None:
        """AC-7: ngb=usssa → usssa."""
        assert detect_league_level(ngb='["usssa"]') == "usssa"

    def test_ngb_nsaa_with_jv_name(self) -> None:
        """AC-8: ngb=nsaa + team name JV → nsaa_subvarsity."""
        assert detect_league_level(
            ngb='["nsaa"]', team_name="Lincoln JV",
        ) == "nsaa_subvarsity"

    def test_ngb_nfhs_with_varsity_name(self) -> None:
        """ngb=nfhs (NSAA-like) + varsity name → nsaa_varsity."""
        assert detect_league_level(
            ngb='["nfhs"]', team_name="Lincoln Varsity",
        ) == "nsaa_varsity"

    def test_ngb_nsaa_no_name(self) -> None:
        """ngb=nsaa with no team name → nsaa_varsity (default)."""
        assert detect_league_level(ngb='["nsaa"]') == "nsaa_varsity"

    def test_ngb_perfect_game(self) -> None:
        """ngb=perfect_game → perfect_game."""
        assert detect_league_level(ngb='["perfect_game"]') == "perfect_game"

    def test_ngb_multi_value_priority(self) -> None:
        """Multi-value ngb: first match in priority order wins."""
        # nsaa has higher priority than usssa
        assert detect_league_level(
            ngb='["usssa", "nsaa"]',
        ) == "nsaa_varsity"

    def test_ngb_multi_usssa_perfect_game(self) -> None:
        """Multi-value ngb: usssa beats perfect_game."""
        assert detect_league_level(
            ngb='["usssa", "perfect_game"]',
        ) == "usssa"

    def test_ngb_unrecognized(self) -> None:
        """Unrecognized ngb value → unknown."""
        assert detect_league_level(ngb='["some_new_org"]') == "unknown"

    def test_ngb_pre_parsed_list(self) -> None:
        """Accept pre-parsed list (not just JSON string)."""
        assert detect_league_level(ngb=["usssa"]) == "usssa"

    def test_ngb_empty_list_string(self) -> None:
        """Empty ngb JSON list falls through to age_group/name."""
        assert detect_league_level(ngb="[]") == "unknown"

    def test_ngb_empty_list(self) -> None:
        """Empty pre-parsed list falls through."""
        assert detect_league_level(ngb=[]) == "unknown"


class TestAgeGroupDetection:
    """AC-10: age_group-based detection when ngb is empty."""

    def test_age_group_14u(self) -> None:
        """AC-10: age_group with U suffix → youth_travel."""
        assert detect_league_level(
            ngb="[]", age_group="14U",
        ) == "youth_travel"

    def test_age_group_12u(self) -> None:
        """age_group 12U → youth_travel."""
        assert detect_league_level(
            age_group="12U",
        ) == "youth_travel"

    def test_age_group_high_school_falls_through(self) -> None:
        """age_group 'High School' falls through to name keywords."""
        assert detect_league_level(
            ngb="[]", age_group="High School", team_name="Lincoln JV",
        ) == "nsaa_subvarsity"

    def test_age_group_between_range_is_youth_travel(self) -> None:
        """IDEA-126: GameChanger's free-text range form ("Between 13 - 18")
        resolves to youth_travel (the labeled PITCH_SMART_15_18 estimate),
        not unknown/fall-through. age_group takes priority over the name
        keyword, mirroring the existing \\d+U handling (so even a
        legion-looking name yields youth_travel when the age range is present).
        """
        assert detect_league_level(
            ngb="[]", age_group="Between 13 - 18", team_name="Post 143",
        ) == "youth_travel"

    def test_age_group_range_no_spaces_is_youth_travel(self) -> None:
        """IDEA-126: the range form without surrounding spaces ("13-18") also
        resolves to youth_travel."""
        assert detect_league_level(
            ngb="[]", age_group="13-18",
        ) == "youth_travel"

    def test_age_group_high_school_still_falls_through_with_range_fix(self) -> None:
        """Regression: a non-range HS age_group ("High School", no digits/range)
        still falls through to name keywords after the range-form fix."""
        assert detect_league_level(
            ngb="[]", age_group="High School", team_name="Lincoln Varsity",
        ) == "nsaa_varsity"


# ── Priority 3: Team name keywords ────────────────────────────────────


class TestNameKeywordDetection:
    """AC-9, AC-11: name keyword-based detection."""

    def test_jv_in_name(self) -> None:
        """AC-9: team name contains JV → nsaa_subvarsity."""
        assert detect_league_level(team_name="Lincoln JV") == "nsaa_subvarsity"

    def test_junior_varsity_in_name(self) -> None:
        """Junior Varsity → nsaa_subvarsity."""
        assert detect_league_level(
            team_name="Lincoln Junior Varsity",
        ) == "nsaa_subvarsity"

    def test_varsity_in_name(self) -> None:
        """Varsity → nsaa_varsity."""
        assert detect_league_level(
            team_name="Lincoln Varsity",
        ) == "nsaa_varsity"

    def test_freshman_in_name(self) -> None:
        """Freshman → nsaa_subvarsity."""
        assert detect_league_level(
            team_name="Lincoln Freshman",
        ) == "nsaa_subvarsity"

    def test_frosh_in_name(self) -> None:
        """Frosh → nsaa_subvarsity."""
        assert detect_league_level(
            team_name="Lincoln Frosh",
        ) == "nsaa_subvarsity"

    def test_reserve_in_name(self) -> None:
        """Reserve → nsaa_subvarsity."""
        assert detect_league_level(
            team_name="Lincoln Reserve",
        ) == "nsaa_subvarsity"

    def test_sophomore_in_name(self) -> None:
        """Sophomore → nsaa_subvarsity."""
        assert detect_league_level(
            team_name="Lincoln Sophomore",
        ) == "nsaa_subvarsity"

    def test_legion_in_name(self) -> None:
        """AC-11: Legion → legion."""
        assert detect_league_level(
            team_name="Lincoln Legion",
        ) == "legion"

    def test_american_legion_in_name(self) -> None:
        """American Legion → legion."""
        assert detect_league_level(
            team_name="Lincoln American Legion Seniors",
        ) == "legion"

    def test_post_number_in_name(self) -> None:
        """AC-11: Post + number → legion."""
        assert detect_league_level(
            team_name="Post 143 Juniors",
        ) == "legion"

    def test_seniors_in_name(self) -> None:
        """Seniors → legion."""
        assert detect_league_level(
            team_name="Waverly Seniors",
        ) == "legion"

    def test_juniors_in_name(self) -> None:
        """Juniors → legion."""
        assert detect_league_level(
            team_name="Waverly Juniors",
        ) == "legion"

    def test_age_pattern_in_name(self) -> None:
        """14U in name → youth_travel."""
        assert detect_league_level(
            team_name="Lincoln 14U Travel",
        ) == "youth_travel"

    def test_14u_juniors_is_youth_travel(self) -> None:
        """'14U Juniors' → youth_travel (age pattern beats standalone juniors)."""
        assert detect_league_level(
            team_name="14U Juniors",
        ) == "youth_travel"

    def test_seniors_14u_is_youth_travel(self) -> None:
        """'Seniors 14U' → youth_travel (age pattern beats standalone seniors)."""
        assert detect_league_level(
            team_name="Seniors 14U",
        ) == "youth_travel"

    def test_case_insensitive(self) -> None:
        """Keywords are case-insensitive."""
        assert detect_league_level(team_name="lincoln jv") == "nsaa_subvarsity"
        assert detect_league_level(team_name="LINCOLN VARSITY") == "nsaa_varsity"
        assert detect_league_level(team_name="post 99") == "legion"


# ── Priority 4: Unknown fallback ──────────────────────────────────────


class TestUnknownFallback:
    """AC-12: no signals → unknown."""

    def test_no_signals(self) -> None:
        """AC-12: No arguments → unknown."""
        assert detect_league_level() == "unknown"

    def test_empty_strings(self) -> None:
        """All empty strings → unknown."""
        assert detect_league_level(
            program_type="", classification="", ngb="", team_name="",
        ) == "unknown"

    def test_none_values(self) -> None:
        """All None values → unknown."""
        assert detect_league_level(
            program_type=None, classification=None,
            ngb=None, age_group=None, team_name=None,
        ) == "unknown"

    def test_team_name_no_keywords(self) -> None:
        """Team name without recognized keywords → unknown."""
        assert detect_league_level(
            team_name="Springfield Eagles",
        ) == "unknown"


# ── Rule set dispatch ──────────────────────────────────────────────────


class TestGetRulesForLeague:
    """Test get_rules_for_league() dispatch."""

    def test_nsaa_varsity_pre_april(self) -> None:
        import datetime
        rules = get_rules_for_league("nsaa_varsity", datetime.date(2026, 3, 15))
        assert rules is not None
        assert rules.max_pitches == 90

    def test_nsaa_varsity_post_april(self) -> None:
        import datetime
        rules = get_rules_for_league("nsaa_varsity", datetime.date(2026, 4, 15))
        assert rules is not None
        assert rules.max_pitches == 110

    def test_nsaa_subvarsity(self) -> None:
        import datetime
        rules = get_rules_for_league("nsaa_subvarsity", datetime.date(2026, 4, 15))
        assert rules is not None
        assert rules.max_pitches == 90  # year-round 90

    def test_legion(self) -> None:
        import datetime
        rules = get_rules_for_league("legion", datetime.date(2026, 4, 15))
        assert rules is not None
        assert rules.max_pitches == 105

    def test_unsupported_returns_none(self) -> None:
        import datetime
        ref = datetime.date(2026, 4, 15)
        assert get_rules_for_league("usssa", ref) is None
        assert get_rules_for_league("perfect_game", ref) is None
        assert get_rules_for_league("unknown", ref) is None

    def test_youth_travel_returns_pitch_smart(self) -> None:
        """E-243-02: youth_travel falls back to the Pitch Smart 15-18 curve."""
        import datetime

        from src.reports.starter_prediction import PITCH_SMART_15_18
        ref = datetime.date(2026, 4, 15)
        rules = get_rules_for_league("youth_travel", ref)
        assert rules is PITCH_SMART_15_18
        assert rules.max_pitches == 105

    def test_range_age_group_end_to_end_reaches_pitch_smart(self) -> None:
        """IDEA-126 (AC-1): a no-NGB team with the free-text range age_group
        resolves through detect_league_level -> youth_travel ->
        PITCH_SMART_15_18, so the labeled-estimate rules are applied instead of
        the projection being suppressed."""
        import datetime

        from src.reports.starter_prediction import PITCH_SMART_15_18

        level = detect_league_level(ngb="[]", age_group="Between 13 - 18")
        assert level == "youth_travel"
        rules = get_rules_for_league(level, datetime.date(2026, 4, 15))
        assert rules is PITCH_SMART_15_18

    def test_pitch_smart_is_distinct_constant_from_legion(self) -> None:
        """TN-4: distinct constant so a Legion-only change can't move it."""
        from src.reports.starter_prediction import LEGION, PITCH_SMART_15_18
        assert PITCH_SMART_15_18 is not LEGION
        # Same tiers today, but separately defined.
        assert PITCH_SMART_15_18.rest_tiers == LEGION.rest_tiers


class TestSubvarsityRules:
    """Test NSAA subvarsity rule set constants."""

    def test_subvarsity_90_pitch_max(self) -> None:
        assert NSAA_SUBVARSITY.max_pitches == 90

    def test_subvarsity_rest_tiers_stricter_than_pre_april_by_one_day(self) -> None:
        """E-272-01 (AC-1/AC-3): Sub-Varsity shares NSAA Varsity's pre-April
        90-pitch breakpoints but requires exactly one MORE rest day at every
        tier (1/2/3/4 vs 0/1/2/3), per the NSAA 2022 Pitch Count Regulations.

        Replaces ``test_subvarsity_same_rest_tiers_as_pre_april``, which
        asserted equality and so encoded the under-resting bug.
        """
        from src.reports.starter_prediction import NSAA_PRE_APRIL

        assert NSAA_SUBVARSITY.rest_tiers != NSAA_PRE_APRIL.rest_tiers
        assert len(NSAA_SUBVARSITY.rest_tiers) == len(NSAA_PRE_APRIL.rest_tiers)
        for sub_tier, var_tier in zip(
            NSAA_SUBVARSITY.rest_tiers, NSAA_PRE_APRIL.rest_tiers
        ):
            # Same breakpoints ...
            assert sub_tier.min_pitches == var_tier.min_pitches
            assert sub_tier.max_pitches == var_tier.max_pitches
            # ... one more rest day.
            assert sub_tier.rest_days == var_tier.rest_days + 1

    def test_subvarsity_rest_tiers_exact_curve(self) -> None:
        """AC-1: pin the authoritative Sub-Varsity curve literally, so a
        Varsity-side change cannot drag Sub-Varsity along via the
        relative-comparison test above."""
        assert [
            (t.min_pitches, t.max_pitches, t.rest_days)
            for t in NSAA_SUBVARSITY.rest_tiers
        ] == [(1, 30, 1), (31, 50, 2), (51, 70, 3), (71, 90, 4)]

    def test_subvarsity_year_round(self) -> None:
        """Subvarsity rules don't change with date."""
        import datetime
        rules_march = get_subvarsity_rules(datetime.date(2026, 3, 15))
        rules_may = get_subvarsity_rules(datetime.date(2026, 5, 15))
        assert rules_march == rules_may
        assert rules_march.max_pitches == 90

    def test_subvarsity_arm_needs_one_more_rest_day_than_varsity(self) -> None:
        """E-272-01 (AC-2): behavioral -- for the same pitch load, a
        sub-varsity arm is STILL excluded on the day a varsity arm becomes
        available, and becomes available exactly one day later.  Runs through
        ``_is_excluded`` (the real eligibility gate), not just the constants,
        so the correction is proven where it changes report output.
        """
        from src.reports.starter_prediction import NSAA_PRE_APRIL, _is_excluded

        reference_date = datetime.date(2026, 4, 15)

        for var_tier in NSAA_PRE_APRIL.rest_tiers:
            pitches = var_tier.max_pitches  # top of the tier
            var_rest = var_tier.rest_days
            label = f"{pitches}p"

            def _profile(days_rest: int) -> dict:
                last = reference_date - datetime.timedelta(days=days_rest)
                return {
                    "appearances": [
                        {"game_date": last.isoformat(), "pitches": pitches}
                    ]
                }

            # Rested exactly as long as Varsity requires: varsity available,
            # sub-varsity is not.
            profile = _profile(var_rest)
            var_excluded, _ = _is_excluded(profile, reference_date, NSAA_PRE_APRIL)
            sub_excluded, sub_reason = _is_excluded(
                profile, reference_date, NSAA_SUBVARSITY
            )
            assert var_excluded is False, f"{label}/{var_rest}d varsity"
            assert sub_excluded is True, f"{label}/{var_rest}d subvarsity"
            assert sub_reason is not None
            assert f"needs {var_rest + 1}" in sub_reason

            # One more day of rest: sub-varsity is now available too.
            assert _is_excluded(
                _profile(var_rest + 1), reference_date, NSAA_SUBVARSITY
            ) == (False, None), f"{label}/{var_rest + 1}d subvarsity"


# ── AC-13: Warning Output Contract end-to-end ─────────────────────────


def _make_appearance(
    player_id: str,
    game_id: str,
    game_date: str,
    *,
    ip_outs: int = 0,
    pitches: int | None = None,
    so: int = 0,
    bb: int = 0,
    appearance_order: int | None = None,
) -> dict:
    """Minimal appearance row for Warning Output Contract tests."""
    return {
        "player_id": player_id,
        "first_name": player_id.title(),
        "last_name": "Player",
        "jersey_number": None,
        "game_id": game_id,
        "game_date": game_date,
        "start_time": None,
        "ip_outs": ip_outs,
        "pitches": pitches,
        "so": so,
        "bb": bb,
        "h": 3,
        "r": 1,
        "er": 1,
        "bf": 18,
        "decision": None,
        "appearance_order": appearance_order,
        "rest_days": None,
        "team_game_number": 1,
    }


def _build_history_for_warning_test() -> list[dict]:
    """Build a 5-game pitching history with one starter and one reliever."""
    history = []
    dates = [
        "2026-03-10", "2026-03-13", "2026-03-16",
        "2026-03-19", "2026-03-22",
    ]
    for i, d in enumerate(dates):
        gid = f"g{i + 1:02d}"
        history.append(_make_appearance(
            "ace", gid, d, ip_outs=18, pitches=75, so=6,
            appearance_order=1,
        ))
        history.append(_make_appearance(
            "reliever", gid, d, ip_outs=3, pitches=15, so=1,
            appearance_order=2,
        ))
    return history


class TestWarningOutputContract:
    """AC-13: unsupported leagues produce the full Warning Output Contract."""

    def test_usssa_warning_output(self) -> None:
        """USSSA league → suppress with league-specific warning."""
        history = _build_history_for_warning_test()
        profiles = build_pitcher_profiles(history)
        pred = compute_starter_prediction(
            profiles, history,
            reference_date=datetime.date(2026, 4, 1),
            league="usssa",
        )
        assert pred.confidence == "suppress"
        assert pred.data_note is not None
        assert "USSSA" in pred.data_note
        assert pred.predicted_starter is None
        assert pred.alternative is None
        assert pred.top_candidates == []
        assert pred.bullpen_order == []
        # rest_table still populated with raw workload data
        assert len(pred.rest_table) > 0

    def test_unknown_warning_output(self) -> None:
        """Unknown league → suppress with detection-failure message."""
        history = _build_history_for_warning_test()
        profiles = build_pitcher_profiles(history)
        pred = compute_starter_prediction(
            profiles, history,
            reference_date=datetime.date(2026, 4, 1),
            league="unknown",
        )
        assert pred.confidence == "suppress"
        assert pred.data_note is not None
        assert "not detected" in pred.data_note.lower()
        assert pred.predicted_starter is None
        assert pred.alternative is None
        assert pred.top_candidates == []
        assert pred.bullpen_order == []
        assert len(pred.rest_table) > 0

    def test_legion_applies_rules(self) -> None:
        """Legion is now supported (E-218-02) → normal prediction, no warning."""
        history = _build_history_for_warning_test()
        profiles = build_pitcher_profiles(history)
        pred = compute_starter_prediction(
            profiles, history,
            reference_date=datetime.date(2026, 4, 1),
            league="legion",
        )
        # Legion is supported -- should NOT show "not yet supported" warning
        if pred.data_note:
            assert "not yet supported" not in pred.data_note
            assert "not detected" not in pred.data_note
        # Should produce candidates (5 games with one starter)
        assert len(pred.top_candidates) > 0

    def test_supported_league_does_not_suppress(self) -> None:
        """nsaa_varsity with enough games → normal prediction (not suppressed by league)."""
        history = _build_history_for_warning_test()
        profiles = build_pitcher_profiles(history)
        pred = compute_starter_prediction(
            profiles, history,
            reference_date=datetime.date(2026, 4, 1),
            league="nsaa_varsity",
        )
        # Should NOT be suppressed due to league (may be suppress for
        # other reasons like < 4 games, but league is supported)
        if pred.data_note:
            assert "not yet supported" not in pred.data_note
            assert "not detected" not in pred.data_note


# ── E-243-02: youth/travel labeled-estimate fallback ──────────────────


class TestYouthTravelFallback:
    """youth_travel falls back to the Pitch Smart estimate instead of a blank card."""

    def test_youth_travel_produces_ranked_prediction(self) -> None:
        """AC-1: youth_travel with >=4 games -> ranked prediction, not suppress."""
        history = _build_history_for_warning_test()
        profiles = build_pitcher_profiles(history)
        pred = compute_starter_prediction(
            profiles, history,
            reference_date=datetime.date(2026, 4, 1),
            league="youth_travel",
        )
        assert pred.confidence != "suppress"
        assert len(pred.top_candidates) > 0
        # Not the no-rules warning card.
        if pred.data_note:
            assert "not yet supported" not in pred.data_note
            assert "not detected" not in pred.data_note

    def test_youth_travel_flagged_as_estimate(self) -> None:
        """AC-2: youth_travel fallback sets is_estimate True."""
        history = _build_history_for_warning_test()
        profiles = build_pitcher_profiles(history)
        pred = compute_starter_prediction(
            profiles, history,
            reference_date=datetime.date(2026, 4, 1),
            league="youth_travel",
        )
        assert pred.is_estimate is True

    def test_youth_travel_under_4_games_still_suppresses(self) -> None:
        """AC-7: the min-games gate is independent of the league gate."""
        # Only 3 games -> below _MIN_GAMES_FOR_ROTATION.
        history = []
        for i, d in enumerate(["2026-03-10", "2026-03-13", "2026-03-16"]):
            gid = f"g{i + 1:02d}"
            history.append(_make_appearance(
                "ace", gid, d, ip_outs=18, pitches=75, so=6,
                appearance_order=1,
            ))
            history.append(_make_appearance(
                "reliever", gid, d, ip_outs=3, pitches=15, so=1,
                appearance_order=2,
            ))
        profiles = build_pitcher_profiles(history)
        pred = compute_starter_prediction(
            profiles, history,
            reference_date=datetime.date(2026, 3, 16),
            league="youth_travel",
        )
        assert pred.confidence == "suppress"
        assert pred.predicted_starter is None


# ══ E-272-02: season x level -> league classification (+ NRBL) ═════════


class TestMappedAgeBrackets:
    """AC-2: single \\d+U brackets map to a league family (empty-ngb path)."""

    def test_18u_is_legion(self) -> None:
        assert detect_league_level(ngb="[]", age_group="18U") == "legion"

    def test_17u_is_legion(self) -> None:
        assert detect_league_level(ngb="[]", age_group="17U") == "legion"

    def test_16u_is_nrbl(self) -> None:
        assert detect_league_level(ngb="[]", age_group="16U") == "nrbl"

    def test_15u_is_nrbl(self) -> None:
        assert detect_league_level(ngb="[]", age_group="15U") == "nrbl"

    def test_14u_stays_youth_travel(self) -> None:
        """AC-2: the unmapped bracket boundary is unchanged."""
        assert detect_league_level(ngb="[]", age_group="14U") == "youth_travel"

    def test_19u_is_legion(self) -> None:
        """TN-2: 17U and ABOVE is legion, so an unseen 19U resolves too."""
        assert detect_league_level(ngb="[]", age_group="19U") == "legion"

    def test_bracket_in_team_name_maps_too(self) -> None:
        """TN-2: age_group and team_name share one bracket ladder."""
        assert detect_league_level(
            ngb="[]", team_name="Norfolk Motor Company 18U",
        ) == "legion"
        assert detect_league_level(
            ngb="[]", team_name="Columbus 16U Blues",
        ) == "nrbl"

    def test_bracket_is_case_insensitive(self) -> None:
        assert detect_league_level(ngb="[]", age_group="18u") == "legion"

    def test_mapped_bracket_beats_subvarsity_keyword(self) -> None:
        """TN-2 4a: the bracket runs ahead of ALL level words, so "16U Reserve"
        is nrbl via the bracket -- NOT nsaa_subvarsity via "Reserve"."""
        assert detect_league_level(
            ngb="[]", team_name="Lincoln 16U Reserve",
        ) == "nrbl"

    def test_mapped_bracket_beats_legion_keyword(self) -> None:
        """A 15U team named "Juniors" is NRBL-age, not Legion-age."""
        assert detect_league_level(
            ngb="[]", team_name="Waverly 15U Juniors",
        ) == "nrbl"

    def test_unmapped_bracket_beats_nsaa_level_word(self) -> None:
        """TN-2 4b: the UNMAPPED half of the ladder outranks NSAA level words
        too, so a 14U bracket in the NAME wins over "Reserve" / "Varsity" /
        "Freshman" / "JV".

        SCOPE: this is the bracket-in-TEAM-NAME path only.  With
        ``age_group="14U"`` the old code already short-circuited to
        youth_travel before reaching any name keyword, so nothing changed there
        (pinned by ``test_unmapped_bracket_in_age_group_is_unchanged``).

        This is the combination whose outcome CHANGED, and the only one that
        changed in the LESS-strict direction: the old ``_NAME_KEYWORDS`` table
        ordered reserve/varsity ahead of the flat ``\\d+U`` entry, so
        "Lincoln 14U Reserve" returned nsaa_subvarsity (90 max, 1/2/3/4) and
        "Lincoln 14U Varsity" returned nsaa_varsity; both now take the labeled
        Pitch Smart estimate (105 max, 0/1/2/3/4).  Pinned rather than left
        emergent so a maintainer who finds it surprising meets the reasoning
        before deciding it is a bug: a team branded "14U" is a youth-travel org,
        whereas NSAA sub-varsity/varsity are Nebraska HS tiers and HS teams do
        not brand by age bracket.
        """
        for name in (
            "Lincoln 14U Reserve",
            "Lincoln 14U Varsity",
            "Lincoln 14U Freshman",
            "Lincoln 14U JV",
        ):
            assert detect_league_level(
                ngb="[]", team_name=name,
            ) == "youth_travel", name

    def test_unmapped_bracket_in_age_group_is_unchanged(self) -> None:
        """Scope guard for the test above: the age_group path did NOT change --
        a 14U age_group already outranked every name keyword."""
        for name in ("Lincoln Reserve", "Lincoln Varsity"):
            assert detect_league_level(
                ngb="[]", age_group="14U", team_name=name,
            ) == "youth_travel", name

    def test_unmapped_bracket_nsaa_word_is_labeled_an_estimate(self) -> None:
        """The less-strict landing spot is not presented as a binding rule: the
        youth_travel path sets is_estimate, so the report banners it."""
        history = _build_history_for_warning_test()
        profiles = build_pitcher_profiles(history)
        pred = compute_starter_prediction(
            profiles, history,
            reference_date=datetime.date(2026, 4, 15),
            league=detect_league_level(ngb="[]", team_name="Lincoln 14U Reserve"),
        )
        assert pred.is_estimate is True

    def test_range_form_is_not_a_mapped_bracket(self) -> None:
        """TN-2: the U suffix is load-bearing -- a bare-integer match would grab
        the 18 out of "Between 13 - 18" and wrongly return legion."""
        assert detect_league_level(
            ngb="[]", age_group="Between 13 - 18",
        ) == "youth_travel"
        assert detect_league_level(ngb="[]", age_group="13-18") == "youth_travel"


class TestLegion18UBugFixed:
    """AC-1: the live bug -- a scouted 18U Legion opponent rendered the youth
    Pitch Smart estimate instead of the binding Legion rules."""

    def test_18u_legion_opponent_resolves_legion(self) -> None:
        """Empty ngb, no DB fields, Legion/Seniors name + 18U bracket."""
        assert detect_league_level(
            ngb="[]",
            age_group="18U",
            team_name="Norfolk Motor Company Seniors 18U",
        ) == "legion"

    def test_18u_legion_opponent_gets_binding_legion_rules(self) -> None:
        """AC-1: the resolved league selects the LEGION table (max 105), not the
        Pitch Smart estimate."""
        from src.reports.starter_prediction import LEGION, PITCH_SMART_15_18

        level = detect_league_level(
            ngb="[]",
            age_group="18U",
            team_name="Norfolk Motor Company Seniors 18U",
        )
        rules = get_rules_for_league(level, datetime.date(2026, 7, 18))
        assert rules is LEGION
        assert rules is not PITCH_SMART_15_18

    def test_18u_legion_opponent_is_not_flagged_an_estimate(self) -> None:
        """AC-1: end-to-end, the youth estimate banner is driven by
        ``is_estimate``; a Legion-resolved 18U opponent must not set it."""
        history = _build_history_for_warning_test()
        profiles = build_pitcher_profiles(history)
        level = detect_league_level(
            ngb="[]",
            age_group="18U",
            team_name="Norfolk Motor Company Seniors 18U",
        )
        pred = compute_starter_prediction(
            profiles, history,
            reference_date=datetime.date(2026, 7, 18),
            league=level,
        )
        assert pred.is_estimate is False
        assert pred.confidence != "suppress"


class TestSeasonLevelWordMatrix:
    """AC-3: season picks the league FAMILY across every level word."""

    # ── Summer ────────────────────────────────────────────────────────
    def test_summer_varsity_is_legion(self) -> None:
        assert detect_league_level(
            ngb="[]", team_name="Lincoln Varsity", season="summer",
        ) == "legion"

    def test_summer_jv_is_nrbl(self) -> None:
        assert detect_league_level(
            ngb="[]", team_name="Lincoln JV", season="summer",
        ) == "nrbl"

    def test_summer_reserve_is_nrbl(self) -> None:
        assert detect_league_level(
            ngb="[]", team_name="Lincoln Reserve", season="summer",
        ) == "nrbl"

    def test_summer_freshman_is_nrbl(self) -> None:
        assert detect_league_level(
            ngb="[]", team_name="Lincoln Freshman", season="summer",
        ) == "nrbl"

    def test_summer_sophomore_is_nrbl(self) -> None:
        assert detect_league_level(
            ngb="[]", team_name="Lincoln Sophomore", season="summer",
        ) == "nrbl"

    def test_summer_junior_varsity_is_nrbl_not_legion(self) -> None:
        """"Junior Varsity" must stay sub-varsity (nrbl in summer) rather than
        matching bare "Varsity" (legion in summer)."""
        assert detect_league_level(
            ngb="[]", team_name="Lincoln Junior Varsity", season="summer",
        ) == "nrbl"

    # ── Spring ────────────────────────────────────────────────────────
    def test_spring_varsity_is_nsaa_varsity(self) -> None:
        assert detect_league_level(
            ngb="[]", team_name="Lincoln Varsity", season="spring",
        ) == "nsaa_varsity"

    def test_spring_jv_is_nsaa_subvarsity(self) -> None:
        assert detect_league_level(
            ngb="[]", team_name="Lincoln JV", season="spring",
        ) == "nsaa_subvarsity"

    def test_spring_freshman_is_nsaa_subvarsity(self) -> None:
        assert detect_league_level(
            ngb="[]", team_name="Lincoln Freshman", season="spring",
        ) == "nsaa_subvarsity"

    # ── Season absent → NSAA spring default ───────────────────────────
    def test_season_absent_varsity_defaults_nsaa_varsity(self) -> None:
        assert detect_league_level(
            ngb="[]", team_name="Lincoln Varsity",
        ) == "nsaa_varsity"

    def test_season_absent_jv_defaults_nsaa_subvarsity(self) -> None:
        assert detect_league_level(
            ngb="[]", team_name="Lincoln JV",
        ) == "nsaa_subvarsity"

    # ── Legion words are season-independent ───────────────────────────
    def test_legion_words_ignore_season(self) -> None:
        """TN-2 4c: Legion/Post/Seniors/Juniors resolve legion in any season."""
        for season in ("summer", "spring", None):
            for name in (
                "Lincoln Legion",
                "Lincoln American Legion",
                "Post 143",
                "Waverly Seniors",
                "Waverly Juniors",
            ):
                assert detect_league_level(
                    ngb="[]", team_name=name, season=season,
                ) == "legion", f"{name!r} / season={season!r}"

    def test_reserves_plural_is_a_level_word(self) -> None:
        """TN-2 4c lists "Reserves" alongside "Reserve"."""
        assert detect_league_level(
            ngb="[]", team_name="Lincoln Reserves", season="summer",
        ) == "nrbl"
        assert detect_league_level(
            ngb="[]", team_name="Lincoln Reserves",
        ) == "nsaa_subvarsity"


class TestSeasonDiscriminator:
    """AC-3 (multi-scope anchor): the SAME team name resolves to a different
    league in each season.  A single-season fixture would hide the whole season
    axis, so this asserts all three scopes side by side."""

    def test_reserve_resolves_by_season(self) -> None:
        name = "Anytown Reserve"
        assert detect_league_level(
            ngb="[]", team_name=name, season="summer",
        ) == "nrbl"
        assert detect_league_level(
            ngb="[]", team_name=name, season="spring",
        ) == "nsaa_subvarsity"
        assert detect_league_level(ngb="[]", team_name=name) == "nsaa_subvarsity"

    def test_reserve_selects_a_different_rule_table_by_season(self) -> None:
        """The season axis reaches the rest TABLE, not just the league id."""
        from src.reports.starter_prediction import NRBL

        ref = datetime.date(2026, 6, 15)
        summer = get_rules_for_league(
            detect_league_level(
                ngb="[]", team_name="Anytown Reserve", season="summer",
            ), ref,
        )
        spring = get_rules_for_league(
            detect_league_level(
                ngb="[]", team_name="Anytown Reserve", season="spring",
            ), ref,
        )
        assert summer is NRBL
        assert spring is NSAA_SUBVARSITY
        assert summer.max_pitches == 105
        assert spring.max_pitches == 90

    def test_spring_subvarsity_selects_the_corrected_e272_01_curve(self) -> None:
        """E-272-01 linkage: the spring sub-varsity path must land on the
        CORRECTED 1/2/3/4 table, not the pre-E-272-01 0/1/2/3 curve."""
        rules = get_rules_for_league(
            detect_league_level(
                ngb="[]", team_name="Anytown Reserve", season="spring",
            ),
            datetime.date(2026, 4, 15),
        )
        assert rules is NSAA_SUBVARSITY
        assert [
            (t.min_pitches, t.max_pitches, t.rest_days) for t in rules.rest_tiers
        ] == [(1, 30, 1), (31, 50, 2), (51, 70, 3), (71, 90, 4)]


class TestSeasonNormalization:
    """AC-3 / TN-4: season matching is case-insensitive; anything that is not
    "summer" takes the NSAA default (conservative on the sub-varsity branch
    exercised here -- see `_SUMMER_SEASON`, it is not a blanket safety margin)."""

    def test_summer_is_case_insensitive(self) -> None:
        for token in ("summer", "Summer", "SUMMER", "  summer  "):
            assert detect_league_level(
                ngb="[]", team_name="Lincoln Reserve", season=token,
            ) == "nrbl", f"season={token!r}"

    def test_unrecognized_season_takes_the_nsaa_default(self) -> None:
        """TN-4: an unknown token must not be guessed into the summer family.
        For the SUB-VARSITY branch this fixture drives, that is the safe
        direction -- NSAA_SUBVARSITY (90) demands at least NRBL's rest at every
        pitch count, so the sub-varsity default over-rests rather than
        under-rests.  This does NOT generalize to the varsity branch; see the
        `_SUMMER_SEASON` comment for the bands where NSAA Varsity under-rests."""
        for token in ("fall", "winter", "offseason", "", "   "):
            assert detect_league_level(
                ngb="[]", team_name="Lincoln Reserve", season=token,
            ) == "nsaa_subvarsity", f"season={token!r}"


class TestRecognizedNgbWinsOverBracket:
    """AC-4: a recognized ngb outranks the age bracket and the season."""

    def test_usssa_ngb_beats_15u_bracket(self) -> None:
        """A genuine USSSA 15U team is usssa (suppress), NOT nrbl."""
        assert detect_league_level(
            ngb='["usssa"]', age_group="15U",
        ) == "usssa"

    def test_usssa_ngb_beats_18u_bracket(self) -> None:
        assert detect_league_level(
            ngb='["usssa"]', age_group="18U", team_name="Lincoln 18U",
        ) == "usssa"

    def test_legion_ngb_beats_14u_bracket(self) -> None:
        """The precedence holds in the other direction too."""
        assert detect_league_level(
            ngb='["american_legion"]', age_group="14U",
        ) == "legion"

    def test_nsaa_ngb_beats_bracket_and_stays_season_blind(self) -> None:
        """TN-2: the step-2 nsaa name disambiguation stays season-BLIND."""
        assert detect_league_level(
            ngb='["nsaa"]', age_group="16U", team_name="Lincoln Reserve",
            season="summer",
        ) == "nsaa_subvarsity"


class TestNrblRules:
    """AC-5: NRBL engine wiring."""

    def test_get_rules_for_nrbl(self) -> None:
        from src.reports.starter_prediction import NRBL

        rules = get_rules_for_league("nrbl", datetime.date(2026, 6, 15))
        assert rules is NRBL
        assert rules.max_pitches == 105

    def test_nrbl_is_distinct_constant_from_legion(self) -> None:
        """TN-3: same tiers today, separately defined -- mirrors
        test_pitch_smart_is_distinct_constant_from_legion."""
        from src.reports.starter_prediction import LEGION, NRBL

        assert NRBL is not LEGION
        assert NRBL.rest_tiers == LEGION.rest_tiers
        assert NRBL.max_pitches == LEGION.max_pitches
        # Equal VALUES but no shared structure: the tiers are separate literals,
        # so editing LEGION's table cannot reach NRBL's.
        assert NRBL.rest_tiers is not LEGION.rest_tiers

    def test_nrbl_year_round_no_date_split(self) -> None:
        """TN-10: summer leagues are flat year-round, no April phase split."""
        assert get_rules_for_league(
            "nrbl", datetime.date(2026, 3, 15),
        ) is get_rules_for_league("nrbl", datetime.date(2026, 7, 15))

    def test_nrbl_renders_binding_not_an_estimate(self) -> None:
        """AC-5: NRBL is a real rule unit -- no estimate banner, no suppress."""
        history = _build_history_for_warning_test()
        profiles = build_pitcher_profiles(history)
        pred = compute_starter_prediction(
            profiles, history,
            reference_date=datetime.date(2026, 6, 15),
            league="nrbl",
        )
        assert pred.is_estimate is False
        assert pred.confidence != "suppress"
        assert pred.suppress_reason is None
        if pred.data_note:
            assert "not yet supported" not in pred.data_note
            assert "not detected" not in pred.data_note


class TestBracketSeasonDisagreementLog:
    """AC-7: a mapped bracket that contradicts the season logs a data-quality
    WARNING.  Observability only -- the bracket still wins the gate."""

    def test_disagreement_logs_warning(self, caplog) -> None:
        with caplog.at_level(
            logging.WARNING, logger="src.reports.starter_prediction",
        ):
            level = detect_league_level(
                ngb="[]", age_group="18U", season="spring",
            )
        assert level == "legion"  # bracket still wins
        messages = [r.getMessage() for r in caplog.records]
        assert any("age bracket resolved legion" in m for m in messages), messages
        # The conflicting season is named so the line is actionable.
        assert any("'spring'" in m for m in messages), messages

    def test_nrbl_bracket_disagreement_logs_warning(self, caplog) -> None:
        with caplog.at_level(
            logging.WARNING, logger="src.reports.starter_prediction",
        ):
            level = detect_league_level(
                ngb="[]", age_group="16U", season="spring",
            )
        assert level == "nrbl"
        assert any("nrbl" in r.getMessage() for r in caplog.records)

    def test_absent_season_is_not_a_disagreement(self, caplog) -> None:
        """TN-2: an ABSENT season is explicitly not a disagreement."""
        with caplog.at_level(
            logging.WARNING, logger="src.reports.starter_prediction",
        ):
            assert detect_league_level(ngb="[]", age_group="18U") == "legion"
        assert caplog.records == []

    def test_agreeing_season_is_silent(self, caplog) -> None:
        with caplog.at_level(
            logging.WARNING, logger="src.reports.starter_prediction",
        ):
            assert detect_league_level(
                ngb="[]", age_group="18U", season="summer",
            ) == "legion"
        assert caplog.records == []

    def test_unrecognized_season_is_silent(self, caplog) -> None:
        """We cannot substantiate a conflict with a token we do not know."""
        with caplog.at_level(
            logging.WARNING, logger="src.reports.starter_prediction",
        ):
            assert detect_league_level(
                ngb="[]", age_group="18U", season="banana",
            ) == "legion"
        assert caplog.records == []

    def test_unmapped_bracket_is_not_a_disagreement(self, caplog) -> None:
        """14U is not a mapped (summer-family) bracket, so there is nothing to
        disagree with."""
        with caplog.at_level(
            logging.WARNING, logger="src.reports.starter_prediction",
        ):
            assert detect_league_level(
                ngb="[]", age_group="14U", season="spring",
            ) == "youth_travel"
        assert caplog.records == []
