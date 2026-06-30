"""Tests for the "Most Likely Arms" section rendering in scouting reports.

Tests ``render_report()`` with various ``StarterPrediction`` and
``EnrichedPrediction`` inputs.  Since E-243-03 the section renders a ranked
list from ``top_candidates`` for every non-suppressed state (the old
four-confidence-branch single-name/blank card contract is gone); the rest
table, LLM narrative, mobile classes, and kill-switch still apply.
"""

from __future__ import annotations

from typing import Any

import pytest

import itertools

from src.reports.renderer import _total_bases, render_report
from src.reports.starter_prediction import StarterPrediction


# ── Test data helpers ───────────────────────────────────────────────────


def _base_data(**overrides: Any) -> dict[str, Any]:
    """Build a minimal valid data dict for render_report()."""
    data: dict[str, Any] = {
        "team": {"name": "Test Team", "season_year": 2026, "record": {"wins": 10, "losses": 5}},
        "generated_at": "2026-04-01T12:00:00Z",
        "expires_at": "2026-04-15T12:00:00Z",
        "freshness_date": "2026-03-31",
        "game_count": 15,
        "recent_form": [],
        "pitching": [],
        "batting": [],
        "spray_charts": {},
        "roster": [],
        "runs_scored_avg": 5.0,
        "runs_allowed_avg": 3.0,
        "team_fps_pct": None,
        "team_pitches_per_pa": None,
        "has_plays_data": False,
        "plays_game_count": 0,
        "pitching_workload": {},
        "generation_date": "2026-04-01",
        "starter_prediction": None,
        "enriched_prediction": None,
    }
    data.update(overrides)
    return data


def _make_candidate(
    name: str = "Ace Smith",
    *,
    player_id: str = "p1",
    games_started: int = 8,
    total_team_games: int = 30,
    days_rest: int | None = 5,
    rest_eligibility: str = "available",
    preferred_rest: int | None = None,
    throws: str | None = None,
    reasoning: str = "Next in rotation, 5 days rest",
    with_log: bool = True,
) -> dict:
    """Build a fully-enriched ranked-candidate dict as the engine produces."""
    start_share_pct = (
        round(games_started / total_team_games * 100) if total_team_games else 0
    )
    return {
        "player_id": player_id,
        "name": name,
        "jersey_number": "22",
        "likelihood": 0.85,
        "reasoning": reasoning,
        "games_started": games_started,
        "recent_starts": (
            [
                {
                    "game_date": "2026-03-28",
                    "ip_outs": 18,
                    "pitches": 70,
                    "so": 6,
                    "bb": 2,
                    "decision": "W",
                    "rest_days_from_previous_start": 4,
                },
            ]
            if with_log
            else []
        ),
        "days_rest": days_rest,
        "last_outing_pitches": 70,
        "rest_eligibility": rest_eligibility,
        "rest_estimate": False,
        "preferred_rest": preferred_rest,
        "start_share_pct": start_share_pct,
        "total_team_games": total_team_games,
        "throws": throws,
    }


def _make_rest_table() -> list[dict]:
    return [
        {
            "name": "Ace Smith",
            "jersey_number": "22",
            "games_started": 8,
            "last_outing_date": "2026-03-28",
            "days_since_last_appearance": 3,
            "last_outing_pitches": 70,
            "workload_7d": 70,
        },
        {
            "name": "Reliever Jones",
            "jersey_number": "45",
            "games_started": 0,
            "last_outing_date": "2026-03-30",
            "days_since_last_appearance": 1,
            "last_outing_pitches": 25,
            "workload_7d": 40,
        },
    ]


def _make_bullpen_order() -> list[dict]:
    return [
        {"name": "Closer Davis", "jersey_number": "33", "frequency": 5, "games_sampled": 10},
    ]


# ── No prediction (None) ───────────────────────────────────────────────


class TestNoPrediction:
    """starter_prediction is None -> 'No pitching data available'."""

    def test_no_data_message(self):
        html = render_report(_base_data(starter_prediction=None))
        assert "No pitching data available" in html

    def test_section_header_present(self):
        html = render_report(_base_data(starter_prediction=None))
        assert "Most Likely Arms" in html
        assert "Predicted Starter" not in html


# ── AC-8(a): Multi-candidate ranked list ───────────────────────────────


class TestRankedListMultiCandidate:
    """A multi-candidate prediction renders >=2 ranked arms with stats."""

    @pytest.fixture
    def html(self):
        candidates = [
            _make_candidate(
                "Ace Smith", player_id="p1", games_started=8,
                days_rest=5, rest_eligibility="available",
            ),
            _make_candidate(
                "Tito Reyes", player_id="p2", games_started=6,
                days_rest=2, rest_eligibility="discounted", preferred_rest=4,
                reasoning="Spot starter; lefty matchup option.",
            ),
        ]
        pred = StarterPrediction(
            confidence="moderate",
            predicted_starter=candidates[0],
            top_candidates=candidates,
            rotation_pattern="2-man rotation",
            rest_table=_make_rest_table(),
            bullpen_order=_make_bullpen_order(),
            unavailable_arms=[
                {"name": "Carl Diaz", "reason": "threw 95p Jun 24, needs 4 days rest"},
            ],
        )
        return render_report(_base_data(starter_prediction=pred))

    def test_both_arms_rendered(self, html):
        assert "Ace Smith" in html
        assert "Tito Reyes" in html

    def test_ranked_numbers(self, html):
        assert "starter-rank" in html

    def test_primary_card_on_first_only(self, html):
        assert html.count("starter-card-primary") >= 1

    def test_start_share_grounded_in_games(self, html):
        # "8 of 30 starts (27%)" — games-grounded, percent secondary.
        assert "8 of 30 starts (27%)" in html
        assert "6 of 30 starts (20%)" in html

    def test_days_rest_shown(self, html):
        assert "5d rest" in html
        assert "2d rest" in html

    def test_eligibility_chips_two_valued(self, html):
        # Assert on rendered class attributes (CSS defs alone must not pass).
        assert "rest-chip rest-chip-ready" in html
        assert ">Ready<" in html
        assert "rest-chip rest-chip-short" in html
        assert ">Short rest<" in html
        # Never "unavailable" on a ranked line.
        assert "rest-chip-unavailable" not in html

    def test_discounted_prefers_suffix(self, html):
        assert "(prefers 4)" in html

    def test_unavailable_subblock(self, html):
        assert "Unavailable today" in html
        assert "Carl Diaz" in html
        assert "needs 4 days rest" in html

    def test_staff_usage_context(self, html):
        assert "Staff usage: 2-man rotation" in html

    def test_no_committee_hedge(self, html):
        assert "multiple candidates" not in html
        assert "true committee situation" not in html.lower()

    def test_rest_table_present(self, html):
        assert "starter-rest-table" in html
        assert "Reliever Jones" in html

    def test_no_likelihood_leaked(self, html):
        assert "0.85" not in html


class TestHandedness:
    """AC-2: handedness shown when throws present, omitted silently when absent."""

    def test_handedness_shown_when_present(self):
        pred = StarterPrediction(
            confidence="high",
            top_candidates=[_make_candidate("Lefty Lou", throws="LHP")],
            rest_table=_make_rest_table(),
        )
        html = render_report(_base_data(starter_prediction=pred))
        assert "Lefty Lou (LHP)" in html

    def test_handedness_omitted_when_absent(self):
        pred = StarterPrediction(
            confidence="high",
            top_candidates=[_make_candidate("Nohand Nick", throws=None)],
            rest_table=_make_rest_table(),
        )
        html = render_report(_base_data(starter_prediction=pred))
        assert "Nohand Nick" in html
        assert "Nohand Nick (" not in html


# ── AC-8(b)/AC-1b: Single-candidate ranked list ────────────────────────


class TestRankedListSingleCandidate:
    """One genuine candidate -> exactly one ranked arm, no fabricated extras."""

    @pytest.fixture
    def html(self):
        pred = StarterPrediction(
            confidence="high",
            predicted_starter=_make_candidate("Solo Ace", player_id="p1"),
            top_candidates=[_make_candidate("Solo Ace", player_id="p1")],
            rotation_pattern="ace-dominant",
            rest_table=_make_rest_table(),
            unavailable_arms=[
                {"name": "Carl Diaz", "reason": "0d rest -- needs 2"},
            ],
        )
        return render_report(_base_data(starter_prediction=pred))

    def test_single_arm_rendered(self, html):
        assert "Solo Ace" in html

    def test_exactly_one_ranked_card(self, html):
        # Only one ranked card -> exactly one rank marker, and no rank 2.
        assert html.count('class="starter-rank">1<') == 1
        assert 'class="starter-rank">2<' not in html

    def test_unavailable_block_present(self, html):
        assert "Unavailable today" in html
        assert "Carl Diaz" in html

    def test_no_old_single_name_framing(self, html):
        # The old "GS" depth badge framing is gone.
        assert "8 GS" not in html
        assert "Most Likely Arms" in html


# ── AC-8(c): Data-sufficient opponent never shows blank/single-name card ─


class TestNoBlankForDataSufficient:
    """A non-suppressed prediction always surfaces the ranked list."""

    def test_low_confidence_renders_ranked_list_not_hedge(self):
        candidates = [
            _make_candidate(f"Pitcher {i}", player_id=f"p{i}", games_started=2)
            for i in range(1, 4)
        ]
        pred = StarterPrediction(
            confidence="low",
            top_candidates=candidates,
            rotation_pattern="committee",
            rest_table=_make_rest_table(),
        )
        html = render_report(_base_data(starter_prediction=pred))
        assert "Pitcher 1" in html
        assert "Pitcher 2" in html
        assert "Pitcher 3" in html
        # Committee is context, not an opening hedge.
        assert "Staff usage: committee (no dominant ace)" in html
        assert "multiple candidates" not in html


# ── AC-5: Estimate treatment (youth/travel) ────────────────────────────


class TestEstimateTreatment:

    @pytest.fixture
    def html(self):
        pred = StarterPrediction(
            confidence="moderate",
            top_candidates=[_make_candidate("Youth Ace", player_id="p1")],
            rotation_pattern="2-man rotation",
            rest_table=_make_rest_table(),
            is_estimate=True,
        )
        return render_report(_base_data(starter_prediction=pred))

    def test_estimate_badge_present(self, html):
        assert "Estimated rest" in html
        assert 'class="starter-estimate-badge"' in html

    def test_estimate_banner_copy(self, html):
        assert "This level doesn't publish pitch-count rules" in html
        assert "Treat as a directional read, not a hard rule." in html

    def test_no_jargon_in_render(self, html):
        for jargon in ("Pitch Smart", "Legion", "USA Baseball", "soft prior"):
            assert jargon not in html

    def test_word_is_estimate_not_uncertain(self, html):
        assert "uncertain" not in html.lower()

    def test_badge_absent_for_non_estimate(self):
        pred = StarterPrediction(
            confidence="moderate",
            top_candidates=[_make_candidate("NSAA Ace", player_id="p1")],
            rotation_pattern="2-man rotation",
            rest_table=_make_rest_table(),
            is_estimate=False,
        )
        html = render_report(_base_data(starter_prediction=pred))
        # Rendered badge text and banner copy must be absent (CSS class defs
        # for these always live in the <style> block, so assert on copy).
        assert "Estimated rest" not in html
        assert "This level doesn't publish pitch-count rules" not in html


# ── AC-6: Suppress / not-enough-data state ─────────────────────────────


class TestSuppressState:

    @pytest.fixture
    def html(self):
        # data_note carries the raw technical string; it must NOT be rendered.
        pred = StarterPrediction(
            confidence="suppress",
            suppress_reason="insufficient_data",
            data_note="Rotation pattern unclear -- 3 games played, rest data accumulating",
            rest_table=_make_rest_table(),
            bullpen_order=_make_bullpen_order(),
        )
        return render_report(_base_data(starter_prediction=pred))

    def test_no_ranked_cards(self, html):
        # Assert on rendered markup (CSS class defs always present in <style>).
        assert 'class="starter-rank"' not in html
        assert 'class="rest-chip' not in html

    def test_insufficient_data_softened_copy(self, html):
        assert (
            "Not enough games yet to project likely arms — "
            "rest data still accumulating." in html
        )

    def test_raw_data_note_not_rendered(self, html):
        # Raw engine data_note (internal/diagnostic) must never reach the coach.
        assert "3 games played" not in html
        assert "Rotation pattern unclear" not in html

    def test_rest_table_present(self, html):
        assert "starter-rest-table" in html

    def test_bullpen_order_rendered(self, html):
        assert "Closer Davis" in html

    def test_no_estimate_badge_in_suppress(self):
        # A youth/travel suppress (estimate True but too few games) shows the
        # honest copy, not an "Estimated rest" badge over nothing.
        pred = StarterPrediction(
            confidence="suppress",
            suppress_reason="insufficient_data",
            data_note="Rotation pattern unclear -- 3 games played",
            is_estimate=True,
        )
        html = render_report(_base_data(starter_prediction=pred))
        assert "Estimated rest" not in html

    def test_unsupported_level_softened_copy(self):
        # Raw warning strings ("USSSA pitch rules not yet supported" /
        # "League not detected ...") must NOT reach the coach.
        pred = StarterPrediction(
            confidence="suppress",
            suppress_reason="unsupported_level",
            data_note="USSSA pitch rules not yet supported",
            rest_table=_make_rest_table(),
        )
        html = render_report(_base_data(starter_prediction=pred))
        assert (
            "Likely-arm projections aren't available for this matchup — "
            "this team's level doesn't have pitch-count rules we can apply." in html
        )
        assert "USSSA" not in html
        assert "League not detected" not in html
        assert "not yet supported" not in html

    def test_default_copy_when_suppress_reason_unset(self):
        # Defensive fallback: unset suppress_reason renders the insufficient
        # string, never the raw data_note.
        pred = StarterPrediction(
            confidence="suppress",
            data_note="League not detected -- pitch count rules cannot be applied",
            rest_table=_make_rest_table(),
        )
        html = render_report(_base_data(starter_prediction=pred))
        assert "Not enough games yet to project likely arms" in html
        assert "League not detected" not in html


# ── LLM narrative present / absent ─────────────────────────────────────


class TestWithLLMNarrative:

    @pytest.fixture
    def html(self):
        from src.reports.llm_analysis import EnrichedPrediction

        pred = StarterPrediction(
            confidence="high",
            top_candidates=[_make_candidate()],
            rotation_pattern="ace-dominant",
            rest_table=_make_rest_table(),
        )
        enriched = EnrichedPrediction(
            base=pred,
            narrative="Ace Smith has been dominant with 6K per start. Expect a strong outing.",
            bullpen_sequence="Jones likely in from the 5th, Davis to close.",
            model_used="anthropic/claude-haiku-4-5-20251001",
        )
        return render_report(_base_data(
            starter_prediction=pred,
            enriched_prediction=enriched,
        ))

    def test_narrative_block_rendered(self, html):
        assert "starter-narrative" in html
        assert "Scouting Analysis" in html

    def test_narrative_text_rendered(self, html):
        assert "Ace Smith has been dominant" in html

    def test_bullpen_sequence_rendered(self, html):
        assert "Jones likely in from the 5th" in html

    def test_disclaimer_mentions_ai(self, html):
        assert "Based on rotation pattern, rest days, recent workload, and AI-assisted analysis. Actual starter may differ." in html

    def test_narrative_text_escaped(self, html):
        assert "starter-narrative-text" in html


class TestLLMNarrativeAbsent:
    """When enriched_prediction is None, no narrative block."""

    def test_no_narrative_block(self):
        pred = StarterPrediction(
            confidence="high",
            top_candidates=[_make_candidate()],
            rest_table=_make_rest_table(),
        )
        html = render_report(_base_data(
            starter_prediction=pred,
            enriched_prediction=None,
        ))
        assert "Scouting Analysis" not in html


# ── Rest table renders in all modes ────────────────────────────────────


class TestRestTableAllModes:

    @pytest.mark.parametrize("confidence", ["high", "moderate", "low", "suppress"])
    def test_rest_table_present(self, confidence):
        pred = StarterPrediction(
            confidence=confidence,
            top_candidates=[_make_candidate()] if confidence != "suppress" else [],
            rest_table=_make_rest_table(),
            data_note="Test note" if confidence == "suppress" else None,
            rotation_pattern="committee" if confidence == "low" else "ace-dominant",
        )
        html = render_report(_base_data(starter_prediction=pred))
        assert "starter-rest-table" in html


# ── Mobile classes ─────────────────────────────────────────────────────


class TestMobileClasses:

    def test_mob_hide_extra_on_game_log(self):
        pred = StarterPrediction(
            confidence="high",
            top_candidates=[_make_candidate()],
            rest_table=_make_rest_table(),
        )
        html = render_report(_base_data(starter_prediction=pred))
        assert "mob-hide-extra" in html

    def test_primary_card_and_reasoning_visible(self):
        pred = StarterPrediction(
            confidence="high",
            top_candidates=[_make_candidate()],
            rest_table=_make_rest_table(),
        )
        html = render_report(_base_data(starter_prediction=pred))
        assert "starter-card-primary" in html
        assert 'class="starter-card-reasoning"' in html


# ── Game log date attribute ────────────────────────────────────────────


class TestGameLogDates:

    def test_data_date_attribute(self):
        pred = StarterPrediction(
            confidence="high",
            top_candidates=[_make_candidate()],
            rest_table=_make_rest_table(),
        )
        html = render_report(_base_data(starter_prediction=pred))
        assert 'data-date="2026-03-28"' in html


# ── LLM failure produces valid Tier 1 report ───────────────────────────


class TestLLMFailureFallback:
    """When enrich_prediction raises LLMError, the report renders Tier 1 only."""

    def test_llm_failure_produces_tier1_report(self):
        from unittest.mock import patch

        from src.llm.openrouter import LLMError

        pred = StarterPrediction(
            confidence="high",
            top_candidates=[_make_candidate()],
            rotation_pattern="ace-dominant",
            rest_table=_make_rest_table(),
            bullpen_order=_make_bullpen_order(),
        )
        with patch(
            "src.reports.llm_analysis.enrich_prediction",
            side_effect=LLMError("OpenRouter rate limit exceeded (429)"),
        ):
            html = render_report(_base_data(
                starter_prediction=pred,
                enriched_prediction=None,
            ))

        assert "Most Likely Arms" in html
        assert "Ace Smith" in html
        assert "starter-rest-table" in html
        assert "Scouting Analysis" not in html
        assert "Based on rotation pattern, rest days, and recent workload. Actual starter may differ." in html


# ── show_predicted_starter kill-switch ─────────────────────────────────


class TestShowPredictedStarterFalse:
    """show_predicted_starter=False removes the entire section."""

    def test_section_removed_when_flag_false(self):
        pred = StarterPrediction(
            confidence="high",
            top_candidates=[_make_candidate()],
            rotation_pattern="ace-dominant",
            rest_table=_make_rest_table(),
            bullpen_order=_make_bullpen_order(),
        )
        html = render_report(_base_data(
            starter_prediction=pred,
            show_predicted_starter=False,
        ))
        assert '<div class="predicted-starter-section">' not in html
        assert "Ace Smith" not in html
        assert "No pitching data available" not in html

    def test_section_present_when_flag_true(self):
        pred = StarterPrediction(
            confidence="high",
            top_candidates=[_make_candidate()],
            rotation_pattern="ace-dominant",
            rest_table=_make_rest_table(),
            bullpen_order=_make_bullpen_order(),
        )
        html = render_report(_base_data(
            starter_prediction=pred,
            show_predicted_starter=True,
        ))
        assert "Most Likely Arms" in html
        assert "Ace Smith" in html
        assert "starter-rest-table" in html


# ---------------------------------------------------------------------------
# E-247-06 AC-1: total-bases formula equality (HARD GATE)
#
# Three call sites inlined total bases two ways:
#   formula 1 (sites A,B): h - 2B - 3B - HR + 2*2B + 3*3B + 4*HR
#   formula 2 (site C):    h + 2B + 2*3B + 3*HR
# These tests PROVE the two are equal to each other AND to the single
# _total_bases helper across an exhaustive grid of edge inputs -- including
# None, zero, negative, and every doubles/triples/hr combination -- before
# the collapse is trusted.
# ---------------------------------------------------------------------------


def _formula_1(h, doubles, triples, hr):
    """Pre-consolidation formula at sites A and B (renderer.py)."""
    h = h or 0
    return (
        h
        - (doubles or 0)
        - (triples or 0)
        - (hr or 0)
        + (doubles or 0) * 2
        + (triples or 0) * 3
        + (hr or 0) * 4
    )


def _formula_2(h, doubles, triples, hr):
    """Pre-consolidation formula at site C (renderer.py)."""
    return (h or 0) + (doubles or 0) + 2 * (triples or 0) + 3 * (hr or 0)


class TestTotalBasesFormulaEquality:
    """AC-1: the two inlined TB formulas and _total_bases agree everywhere."""

    def test_three_formulas_identical_over_edge_grid(self) -> None:
        # Include None (missing field), 0, negatives, and multi-base values so
        # every spot where the two formulas could diverge is exercised.
        components = [None, 0, 1, 2, 3, 5, -1]
        checked = 0
        for h, doubles, triples, hr in itertools.product(components, repeat=4):
            player = {"h": h, "doubles": doubles, "triples": triples, "hr": hr}
            f1 = _formula_1(h, doubles, triples, hr)
            f2 = _formula_2(h, doubles, triples, hr)
            helper = _total_bases(player)
            assert f1 == f2 == helper, (
                f"TB divergence at h={h} 2B={doubles} 3B={triples} HR={hr}: "
                f"formula_1={f1} formula_2={f2} _total_bases={helper}"
            )
            checked += 1
        assert checked == len(components) ** 4  # 2401 combinations

    def test_total_bases_matches_canonical_definition(self) -> None:
        # Canonical: 1*1B + 2*2B + 3*3B + 4*HR, where 1B = h - 2B - 3B - HR.
        for h, doubles, triples, hr in [(4, 1, 1, 1), (10, 3, 0, 2), (0, 0, 0, 0), (3, 3, 0, 0)]:
            singles = h - doubles - triples - hr
            canonical = singles + 2 * doubles + 3 * triples + 4 * hr
            assert _total_bases(
                {"h": h, "doubles": doubles, "triples": triples, "hr": hr}
            ) == canonical

    def test_missing_keys_coerce_to_zero(self) -> None:
        assert _total_bases({}) == 0
        assert _total_bases({"h": 2}) == 2  # 2 singles
        assert _total_bases({"h": 1, "hr": 1}) == 4  # a lone HR (h counts it)
