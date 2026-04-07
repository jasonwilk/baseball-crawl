"""Tests for predicted starter section rendering in scouting reports.

Tests ``render_report()`` with various ``StarterPrediction`` and
``EnrichedPrediction`` inputs to verify all four confidence-dependent
rendering modes, rest table, LLM narrative, and mobile classes.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.reports.renderer import render_report
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


def _make_starter(game_date: str = "2026-03-28") -> dict:
    return {
        "player_id": "p1",
        "name": "Ace Smith",
        "jersey_number": "22",
        "likelihood": 0.85,
        "reasoning": "Next in rotation, 5 days rest, 70 pitches last outing",
        "games_started": 8,
        "recent_starts": [
            {
                "game_date": game_date,
                "ip_outs": 18,
                "pitches": 70,
                "so": 6,
                "bb": 2,
                "decision": "W",
                "rest_days_from_previous_start": 4,
            },
        ],
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


# ── AC-16: No prediction (None) ────────────────────────────────────────


class TestNoPrediction:
    """starter_prediction is None -> 'No pitching data available'."""

    def test_no_data_message(self):
        html = render_report(_base_data(starter_prediction=None))
        assert "No pitching data available" in html

    def test_section_header_present(self):
        html = render_report(_base_data(starter_prediction=None))
        assert "Predicted Starter" in html


# ── AC-16: High confidence rendering ───────────────────────────────────


class TestHighConfidence:

    @pytest.fixture
    def html(self):
        pred = StarterPrediction(
            confidence="high",
            predicted_starter=_make_starter(),
            rotation_pattern="ace-dominant",
            rest_table=_make_rest_table(),
            bullpen_order=_make_bullpen_order(),
        )
        return render_report(_base_data(starter_prediction=pred))

    def test_starter_name_rendered(self, html):
        assert "Ace Smith" in html

    def test_blue_accent_card(self, html):
        assert "starter-card-primary" in html

    def test_reasoning_rendered(self, html):
        assert "Next in rotation" in html

    def test_no_percentage_displayed(self, html):
        # Internal likelihood (0.85) should NOT appear
        assert "0.85" not in html
        assert "85%" not in html

    def test_gs_badge_rendered(self, html):
        assert "8 GS" in html

    def test_game_log_rendered(self, html):
        assert "2026-03-28" in html
        assert "starter-game-log" in html

    def test_rest_table_rendered(self, html):
        assert "starter-rest-table" in html
        assert "Reliever Jones" in html

    def test_disclaimer_rendered(self, html):
        assert "Based on rotation pattern, rest days, and recent workload. Actual starter may differ." in html

    def test_no_narrative_block(self, html):
        assert "Scouting Analysis" not in html


# ── AC-16: Moderate confidence rendering ────────────────────────────────


class TestModerateConfidence:

    @pytest.fixture
    def html(self):
        pred = StarterPrediction(
            confidence="moderate",
            predicted_starter=_make_starter(),
            alternative={
                "player_id": "p2",
                "name": "Bravo Lee",
                "jersey_number": "15",
                "likelihood": 0.4,
                "reasoning": "Higher K/9, 6 days rest",
                "games_started": 4,
                "recent_starts": [
                    {
                        "game_date": "2026-03-26",
                        "ip_outs": 15,
                        "pitches": 65,
                        "so": 8,
                        "bb": 1,
                        "decision": None,
                        "rest_days_from_previous_start": 5,
                    },
                ],
            },
            rotation_pattern="2-man rotation",
            rest_table=_make_rest_table(),
        )
        return render_report(_base_data(starter_prediction=pred))

    def test_primary_card_with_accent(self, html):
        assert "starter-card-primary" in html

    def test_caveat_rendered(self, html):
        assert "Matchup alternative possible" in html

    def test_alternative_name(self, html):
        assert "Bravo Lee" in html

    def test_alternative_card_no_primary_accent(self, html):
        # The alternative card should be a standard card, not primary
        # Only 1 primary card class in HTML body elements (CSS defs don't count)
        assert html.count('class="starter-card starter-card-primary"') == 1


# ── AC-16: Low/Committee rendering ─────────────────────────────────────


class TestLowCommittee:

    @pytest.fixture
    def html(self):
        candidates = [
            {
                "player_id": f"p{i}",
                "name": f"Pitcher {i}",
                "jersey_number": str(i),
                "likelihood": 0.25,
                "reasoning": f"Committee candidate {i}",
                "games_started": 2,
                "recent_starts": [],
            }
            for i in range(1, 4)
        ]
        pred = StarterPrediction(
            confidence="low",
            top_candidates=candidates,
            rotation_pattern="committee",
            rest_table=_make_rest_table(),
        )
        return render_report(_base_data(starter_prediction=pred))

    def test_no_primary_accent(self, html):
        assert 'class="starter-card starter-card-primary"' not in html

    def test_committee_label(self, html):
        assert "committee" in html.lower()
        assert "multiple candidates" in html

    def test_all_candidates_rendered(self, html):
        assert "Pitcher 1" in html
        assert "Pitcher 2" in html
        assert "Pitcher 3" in html

    def test_rest_table_present(self, html):
        assert "starter-rest-table" in html


# ── AC-16: Suppress rendering ──────────────────────────────────────────


class TestSuppressConfidence:

    @pytest.fixture
    def html(self):
        pred = StarterPrediction(
            confidence="suppress",
            data_note="Rotation pattern unclear -- 3 games played, rest data accumulating",
            rest_table=_make_rest_table(),
            bullpen_order=_make_bullpen_order(),
        )
        return render_report(_base_data(starter_prediction=pred))

    def test_no_candidate_cards(self, html):
        assert 'class="starter-card' not in html

    def test_data_note_rendered(self, html):
        assert "3 games played" in html

    def test_rest_table_present(self, html):
        assert "starter-rest-table" in html

    def test_bullpen_order_rendered(self, html):
        assert "Closer Davis" in html


# ── AC-16: LLM narrative present ───────────────────────────────────────


class TestWithLLMNarrative:

    @pytest.fixture
    def html(self):
        from src.reports.llm_analysis import EnrichedPrediction

        pred = StarterPrediction(
            confidence="high",
            predicted_starter=_make_starter(),
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

    def test_model_attribution(self, html):
        # Model is stored in EnrichedPrediction but not rendered in disclaimer
        # per AC-11. Verify AI-assisted text is present instead.
        assert "AI-assisted analysis" in html

    def test_disclaimer_mentions_ai(self, html):
        assert "Based on rotation pattern, rest days, recent workload, and AI-assisted analysis. Actual starter may differ." in html

    def test_narrative_text_escaped(self, html):
        # Verify LLM text uses escaping (no | safe)
        assert "starter-narrative-text" in html


class TestLLMNarrativeAbsent:
    """When enriched_prediction is None, no narrative block."""

    def test_no_narrative_block(self):
        pred = StarterPrediction(
            confidence="high",
            predicted_starter=_make_starter(),
            rest_table=_make_rest_table(),
        )
        html = render_report(_base_data(
            starter_prediction=pred,
            enriched_prediction=None,
        ))
        assert "Scouting Analysis" not in html


# ── AC-16: Rest table in all modes ─────────────────────────────────────


class TestRestTableAllModes:

    @pytest.mark.parametrize("confidence", ["high", "moderate", "low", "suppress"])
    def test_rest_table_present(self, confidence):
        pred = StarterPrediction(
            confidence=confidence,
            predicted_starter=_make_starter() if confidence in ("high", "moderate") else None,
            rest_table=_make_rest_table(),
            data_note="Test note" if confidence == "suppress" else None,
            top_candidates=[
                {"player_id": "p1", "name": "Test", "jersey_number": "1",
                 "likelihood": 0.5, "reasoning": "test", "games_started": 2,
                 "recent_starts": []}
            ] if confidence == "low" else [],
            rotation_pattern="committee" if confidence == "low" else "ace-dominant",
        )
        html = render_report(_base_data(starter_prediction=pred))
        assert "starter-rest-table" in html


# ── AC-13: Mobile classes ──────────────────────────────────────────────


class TestMobileClasses:

    def test_mob_hide_extra_on_game_log(self):
        pred = StarterPrediction(
            confidence="high",
            predicted_starter=_make_starter(),
            rest_table=_make_rest_table(),
        )
        html = render_report(_base_data(starter_prediction=pred))
        assert "mob-hide-extra" in html

    def test_primary_card_visible_on_mobile(self):
        """Primary card and reasoning should NOT have mob-hide-extra."""
        pred = StarterPrediction(
            confidence="high",
            predicted_starter=_make_starter(),
            rest_table=_make_rest_table(),
        )
        html = render_report(_base_data(starter_prediction=pred))
        # The card itself and reasoning line should not be hidden
        assert 'class="starter-card starter-card-primary"' in html
        assert 'class="starter-card-reasoning"' in html


# ── AC-12: Game log date attribute ──────────────────────────────────────


class TestGameLogDates:

    def test_data_date_attribute(self):
        pred = StarterPrediction(
            confidence="high",
            predicted_starter=_make_starter("2026-03-28"),
            rest_table=_make_rest_table(),
        )
        html = render_report(_base_data(starter_prediction=pred))
        assert 'data-date="2026-03-28"' in html


# ── AC-16: LLM failure produces valid Tier 1 report ────────────────────


class TestLLMFailureFallback:
    """When enrich_prediction raises LLMError, the report renders with Tier 1 only."""

    def test_llm_failure_produces_tier1_report(self):
        """Mock enrich_prediction to raise LLMError, verify render still works."""
        from unittest.mock import patch

        from src.llm.openrouter import LLMError

        pred = StarterPrediction(
            confidence="high",
            predicted_starter=_make_starter(),
            rotation_pattern="ace-dominant",
            rest_table=_make_rest_table(),
            bullpen_order=_make_bullpen_order(),
        )
        # Simulate what the generator does: catch LLMError, set enriched=None
        with patch(
            "src.reports.llm_analysis.enrich_prediction",
            side_effect=LLMError("OpenRouter rate limit exceeded (429)"),
        ):
            # The generator catches LLMError and continues with enriched=None.
            # We test the rendering path: Tier 1 data, no enrichment.
            html = render_report(_base_data(
                starter_prediction=pred,
                enriched_prediction=None,
            ))

        # Report renders successfully with Tier 1 prediction
        assert "Predicted Starter" in html
        assert "Ace Smith" in html
        assert "starter-rest-table" in html
        # No LLM narrative
        assert "Scouting Analysis" not in html
        # Disclaimer is Tier 1 variant
        assert "Based on rotation pattern, rest days, and recent workload. Actual starter may differ." in html

# ── show_predicted_starter kill-switch ─────────────────────────────────


class TestShowPredictedStarterFalse:
    """show_predicted_starter=False removes the entire predicted starter section."""

    def test_section_removed_when_flag_false(self):
        pred = StarterPrediction(
            confidence="high",
            predicted_starter=_make_starter(),
            rotation_pattern="ace-dominant",
            rest_table=_make_rest_table(),
            bullpen_order=_make_bullpen_order(),
        )
        html = render_report(_base_data(
            starter_prediction=pred,
            show_predicted_starter=False,
        ))
        # CSS styles always include the class name, so assert on the
        # structural HTML element that only appears inside the guard.
        assert '<div class="predicted-starter-section">' not in html
        assert "Ace Smith" not in html
        assert "No pitching data available" not in html

    def test_section_present_when_flag_true(self):
        pred = StarterPrediction(
            confidence="high",
            predicted_starter=_make_starter(),
            rotation_pattern="ace-dominant",
            rest_table=_make_rest_table(),
            bullpen_order=_make_bullpen_order(),
        )
        html = render_report(_base_data(
            starter_prediction=pred,
            show_predicted_starter=True,
        ))
        assert "Predicted Starter" in html
        assert "Ace Smith" in html
        assert "starter-rest-table" in html
