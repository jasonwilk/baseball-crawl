"""Tests for league/level detection function.

Tests ``detect_league_level()`` and supporting helpers in
``src/reports/starter_prediction.py``.
"""

from __future__ import annotations

import datetime

import pytest

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

    def test_age_group_between_13_18_falls_through(self) -> None:
        """Ambiguous age_group falls through to name keywords."""
        assert detect_league_level(
            ngb="[]", age_group="Between 13 - 18", team_name="Post 143",
        ) == "legion"


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
        assert get_rules_for_league("youth_travel", ref) is None
        assert get_rules_for_league("unknown", ref) is None


class TestSubvarsityRules:
    """Test NSAA subvarsity rule set constants."""

    def test_subvarsity_90_pitch_max(self) -> None:
        assert NSAA_SUBVARSITY.max_pitches == 90

    def test_subvarsity_same_rest_tiers_as_pre_april(self) -> None:
        """Subvarsity rest tiers match NSAA pre-April (same 90-pitch structure)."""
        from src.reports.starter_prediction import NSAA_PRE_APRIL
        assert NSAA_SUBVARSITY.rest_tiers == NSAA_PRE_APRIL.rest_tiers

    def test_subvarsity_year_round(self) -> None:
        """Subvarsity rules don't change with date."""
        import datetime
        rules_march = get_subvarsity_rules(datetime.date(2026, 3, 15))
        rules_may = get_subvarsity_rules(datetime.date(2026, 5, 15))
        assert rules_march == rules_may
        assert rules_march.max_pitches == 90


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
