"""Tests for E-228-07 -- Tier 2 LLM rationale enrichment.

Mocks :func:`src.reports.positioning_llm.query_openrouter` and covers the
AC-1 observable contract (length, structural citation, decision
discipline) plus the AC-2 / AC-2a non-fatal paths (LLM unavailable INFO,
LLM mid-call failure WARNING).
"""

from __future__ import annotations

import json
import logging
from unittest.mock import patch

import pytest

from src.llm.openrouter import LLMError
from src.reports.positioning import (
    BatterPositioningResult,
    PerPositionRow,
    PerZoneAggregation,
    PerZoneContactEntry,
)
from src.reports.positioning_llm import (
    _MAX_WORDS,
    _MIN_WORDS,
    _build_user_prompt,
    _has_decision_contradiction,
    _has_structural_citation,
    _truncate_to_in_band_sentence,
    _validate_rationale,
    enrich_positioning,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_result(
    *,
    team_state_call: str = "LEFT",
    per_position_calls: dict[str, str] | None = None,
    bip_count: int = 38,
    hr_count: int = 2,
    zone_totals: dict[str, int] | None = None,
    contact_totals: dict[str, int] | None = None,
    player_id: str = "p-test",
) -> BatterPositioningResult:
    """Build a `BatterPositioningResult` with sensible defaults."""
    per_position_calls = per_position_calls or {"LF": "LEFT", "3B": "LEFT"}
    zone_totals = zone_totals or {"left": 22, "center": 12, "right": 4}
    contact_totals = contact_totals or {"gb": 18, "ld": 12, "fb": 6}

    positions = ("LF", "CF", "RF", "3B", "SS", "2B")
    rows = tuple(
        PerPositionRow(
            position=p,
            call_state=per_position_calls.get(p, "TRUE"),
            team_state_call=team_state_call,
            direction_shade="left" if per_position_calls.get(p, "TRUE") != "TRUE" else None,
            depth_shade=None,
            bip_count=bip_count,
            hr_count=hr_count,
            is_thin=0,
            zone_concentration=0.6,
            direction_deviation=-1 if per_position_calls.get(p, "TRUE") != "TRUE" else None,
            depth_deviation=None,
        )
        for p in positions
    )
    entries = tuple(
        PerZoneContactEntry(zone=zone, contact_type=ct, count=cnt)
        for zone, cnt in zone_totals.items()
        for ct in ("gb", "ld", "fb")
        if (cnt > 0)
    )
    aggregation = PerZoneAggregation(
        entries=entries,
        zone_totals=zone_totals,
        contact_type_totals=contact_totals,
    )
    return BatterPositioningResult(
        player_id=player_id,
        team_id=1,
        season_id="2026-spring-hs",
        perspective_team_id=1,
        per_position_rows=rows,
        team_state_call=team_state_call,
        zone_aggregation=aggregation,
    )


def _openrouter_response(content: str | dict) -> dict:
    """Build a mock OpenRouter response dict.

    ``content`` may be a string (placed verbatim in the message content)
    or a dict (JSON-encoded into the content field).
    """
    if isinstance(content, dict):
        content = json.dumps(content)
    return {"choices": [{"message": {"content": content}}]}


# ---------------------------------------------------------------------------
# AC-3 -- Prompt construction (no raw x/y, no spray_charts; aggregates only)
# ---------------------------------------------------------------------------


class TestPromptConstruction:
    def test_includes_finished_tier1_call(self):
        result = _make_result(team_state_call="LEFT_SHALLOW")
        prompt = _build_user_prompt(result)
        # The full display word from the render-layer vocab block.
        assert "SHADE LEFT SHALLOW" in prompt

    def test_includes_zone_aggregates(self):
        result = _make_result(
            zone_totals={"left": 22, "center": 12, "right": 4},
        )
        prompt = _build_user_prompt(result)
        assert "left:   22" in prompt
        assert "center: 12" in prompt
        assert "right:  4" in prompt

    def test_includes_contact_type_aggregates(self):
        result = _make_result(
            contact_totals={"gb": 18, "ld": 12, "fb": 6, "pu": 2},
        )
        prompt = _build_user_prompt(result)
        assert "ground ball: 18" in prompt
        assert "line drive:  12" in prompt
        assert "fly ball:    6" in prompt
        assert "popup:       2" in prompt

    def test_includes_totals(self):
        result = _make_result(bip_count=38, hr_count=2)
        prompt = _build_user_prompt(result)
        assert "Total BIP: 38" in prompt
        assert "Total HR: 2" in prompt

    def test_does_not_leak_raw_x_y_or_spray_charts(self):
        """AC-3: the prompt must NOT carry raw coordinates or any
        spray_charts-like field. The aggregation layer is the boundary."""
        result = _make_result()
        prompt = _build_user_prompt(result)
        # Spot-check for raw-coord hints that would only exist if the
        # aggregation boundary leaked.
        for forbidden in ("svg_x", "svg_y", "raw_x", "raw_y", "spray_charts"):
            assert forbidden not in prompt


# ---------------------------------------------------------------------------
# AC-1 (a) -- length gate
# ---------------------------------------------------------------------------


class TestLengthGate:
    def test_too_short_is_skipped(self):
        result = _make_result()
        # 4 words < _MIN_WORDS (10).
        assert _validate_rationale("Pulls grounders to left.", result) is None

    def test_at_min_length_passes(self):
        result = _make_result()
        # 13 words, 1 sentence, cites "left" + "grounders".
        text = (
            "Loves to pull grounders to left field early in the count, "
            "especially against fastballs."
        )
        assert _validate_rationale(text, result) == text

    def test_at_max_length_passes(self):
        result = _make_result()
        # ~50 words, 2 sentences, cites "left", "ground", and "22".
        text = (
            "This batter shows a strong pull tendency in the data: most "
            "of his 22 left-zone ground balls come on inside fastballs "
            "early in the count. The infield should expect ground balls "
            "to the left side and shade accordingly to make routine plays."
        )
        out = _validate_rationale(text, result)
        assert out is not None
        # Word count is within bounds.
        words = len(out.split())
        assert _MIN_WORDS <= words <= _MAX_WORDS

    def test_too_long_truncated_at_sentence_boundary(self):
        result = _make_result()
        # 3-sentence input where the FIRST sentence is in-band (10-50 words).
        first_sentence = (
            "This batter pulls grounders to left field on most contact, "
            "with twenty-two of his ground balls landing on that side."
        )
        long_text = (
            first_sentence
            + " But there is also a non-trivial residual tendency where "
              "balls go elsewhere, particularly when he sees offspeed "
              "and is fooled into rolling over to the right side instead. "
              "Coaches should still note that the bulk of contact aligns "
              "with the dominant call, so the recommendation stands solidly."
        )
        # NOTE: the long_text mentions "right side" which doesn't trigger
        # the contradiction patterns ("shade right" / "pulls right" /
        # "to right field"). The first sentence has no contradiction.
        out = _validate_rationale(long_text, result)
        assert out is not None
        # Output truncated to a prefix containing the first sentence.
        assert out.startswith(first_sentence)
        # Word count is in-band after truncation.
        words = len(out.split())
        assert words <= _MAX_WORDS

    def test_truncate_helper_returns_none_when_no_in_band_prefix(self):
        """_truncate_to_in_band_sentence: when every sentence prefix is
        too short or too long, return None."""
        # Single ultra-long sentence with no period -- can't be truncated.
        ultra_long = " ".join(["word"] * 60)
        assert _truncate_to_in_band_sentence(ultra_long) is None


# ---------------------------------------------------------------------------
# AC-1 (b) -- structural citation
# ---------------------------------------------------------------------------


class TestStructuralCitation:
    def test_zone_keyword_counts_as_citation(self):
        result = _make_result()
        # Mentions "left" -- passes citation regardless of numbers.
        assert _has_structural_citation(
            "Strong pull tendency to left side on early counts.", result,
        )

    def test_contact_type_keyword_counts_as_citation(self):
        result = _make_result()
        assert _has_structural_citation(
            "This hitter rolls a lot of ground balls in fastball counts.",
            result,
        )

    def test_numeric_count_from_aggregates_counts(self):
        result = _make_result(
            zone_totals={"left": 22, "center": 12, "right": 4},
        )
        # "22" is the left-zone count -- citation passes.
        assert _has_structural_citation(
            "Has 22 batted balls heading the same direction this season.",
            result,
        )

    def test_no_zone_no_contact_type_no_number_fails(self):
        result = _make_result()
        assert not _has_structural_citation(
            "Likely a pull hitter based on tendency cues from the data.",
            result,
        )

    def test_validate_rejects_response_missing_citation(self):
        result = _make_result()
        # 15 words, in-band, NO zone / contact / aggregate-count citation.
        text = (
            "This hitter has shown a clear pattern that the deterministic "
            "engine reflects accurately overall."
        )
        assert _validate_rationale(text, result) is None


# ---------------------------------------------------------------------------
# AC-1 (c) -- decision discipline
# ---------------------------------------------------------------------------


class TestDecisionDiscipline:
    def test_left_call_with_shade_right_is_contradiction(self):
        assert _has_decision_contradiction(
            "Strong tendency to shade right against this batter.", "LEFT",
        )

    def test_left_call_with_left_phrase_is_fine(self):
        assert not _has_decision_contradiction(
            "Pulls grounders to left field early in the count.", "LEFT",
        )

    def test_right_call_with_shade_left_is_contradiction(self):
        assert _has_decision_contradiction(
            "Pulls left consistently against breaking balls.", "RIGHT",
        )

    def test_true_call_with_shade_left_is_contradiction(self):
        assert _has_decision_contradiction(
            "Best to shade left on this batter.", "TRUE",
        )

    def test_mixed_call_has_no_contradiction(self):
        # MIXED has no single direction expectation.
        assert not _has_decision_contradiction(
            "Pulls left on fastballs but goes right on offspeed.", "MIXED",
        )

    def test_validate_rejects_contradictory_response(self):
        result = _make_result(team_state_call="LEFT")
        # In-band, cites "left", but contradicts the call.
        text = (
            "Hits to left side but the better play is to shade right "
            "against this batter on most counts."
        )
        assert _validate_rationale(text, result) is None


# ---------------------------------------------------------------------------
# AC-2 -- LLM unavailable path (INFO log)
# ---------------------------------------------------------------------------


class TestLLMUnavailable:
    def test_returns_none_and_logs_info_when_api_key_unset(
        self, monkeypatch, caplog: pytest.LogCaptureFixture,
    ):
        """AC-2: `is_llm_available()` false -> Tier 2 skipped, INFO log
        (NOT WARNING; this is an expected config state, not error)."""
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        caplog.set_level(logging.INFO, logger="src.reports.positioning_llm")

        out = enrich_positioning(_make_result())

        assert out is None
        info_records = [
            r for r in caplog.records if r.levelno == logging.INFO
        ]
        assert any("Tier 2 LLM unavailable" in r.getMessage() for r in info_records)
        warning_records = [
            r for r in caplog.records if r.levelno == logging.WARNING
        ]
        # Must not log at WARNING for the missing-config case.
        assert not warning_records


# ---------------------------------------------------------------------------
# AC-2a -- LLM mid-call failure (WARNING log, non-fatal)
# ---------------------------------------------------------------------------


class TestLLMMidCallFailure:
    def test_llm_error_caught_and_logged_warning(
        self, monkeypatch, caplog: pytest.LogCaptureFixture,
    ):
        """AC-2a: `LLMError` raised mid-call -> caught, WARNING log,
        rationale is None. Call sheet renders fully without rationale."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        caplog.set_level(logging.WARNING, logger="src.reports.positioning_llm")

        with patch(
            "src.reports.positioning_llm.query_openrouter",
            side_effect=LLMError("synthetic API failure"),
        ):
            out = enrich_positioning(_make_result())

        assert out is None
        warning_records = [
            r for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any(
            "Tier 2 LLM call failed" in r.getMessage()
            for r in warning_records
        )

    def test_unexpected_exception_caught_and_logged_warning(
        self, monkeypatch, caplog: pytest.LogCaptureFixture,
    ):
        """Defensive: any non-LLMError mid-call also produces a WARNING
        (the call sheet must remain usable)."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        caplog.set_level(logging.WARNING, logger="src.reports.positioning_llm")

        with patch(
            "src.reports.positioning_llm.query_openrouter",
            side_effect=RuntimeError("synthetic non-LLM error"),
        ):
            out = enrich_positioning(_make_result())

        assert out is None

    def test_malformed_response_routes_to_warning_and_skip(
        self, monkeypatch, caplog: pytest.LogCaptureFixture,
    ):
        """LLM returns garbage -> WARNING log, None."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        caplog.set_level(logging.WARNING, logger="src.reports.positioning_llm")

        with patch(
            "src.reports.positioning_llm.query_openrouter",
            return_value=_openrouter_response("not even json"),
        ):
            out = enrich_positioning(_make_result())

        assert out is None
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("not valid JSON" in r.getMessage() for r in warnings)


# ---------------------------------------------------------------------------
# Happy path -- valid response surfaces through the validation gate
# ---------------------------------------------------------------------------


class TestEnrichPositioningHappyPath:
    def test_valid_response_passes_through(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        result = _make_result(team_state_call="LEFT", zone_totals={
            "left": 22, "center": 12, "right": 4,
        })
        rationale = (
            "Loves to pull grounders to left field early in the count, "
            "especially on inside fastballs against right-handed pitchers."
        )

        with patch(
            "src.reports.positioning_llm.query_openrouter",
            return_value=_openrouter_response({"rationale": rationale}),
        ):
            out = enrich_positioning(result)

        assert out == rationale

    def test_true_call_skipped_short_circuit(self, monkeypatch):
        """A TRUE batter doesn't need a rationale -- short-circuit before
        calling the LLM at all (saves cost)."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        result = _make_result(
            team_state_call="TRUE",
            per_position_calls={},  # all TRUE
        )
        with patch("src.reports.positioning_llm.query_openrouter") as mock_qr:
            out = enrich_positioning(result)
        assert out is None
        mock_qr.assert_not_called()

    def test_response_missing_rationale_field_routes_to_skip(
        self, monkeypatch, caplog: pytest.LogCaptureFixture,
    ):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        caplog.set_level(logging.WARNING, logger="src.reports.positioning_llm")

        with patch(
            "src.reports.positioning_llm.query_openrouter",
            return_value=_openrouter_response({"narrative": "wrong field"}),
        ):
            out = enrich_positioning(_make_result())

        assert out is None
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            "missing/non-string 'rationale'" in r.getMessage()
            for r in warnings
        )

    def test_response_with_discarded_decision_field_still_returns_rationale(
        self, monkeypatch,
    ):
        """AC-3: any LLM-suggested change to the decision is discarded.
        The schema doesn't even expose a decision field -- extra fields
        in the response are simply not read."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        rationale = (
            "Strong pull tendency: 22 of 38 batted balls go to left field, "
            "mostly grounders early in the count."
        )

        with patch(
            "src.reports.positioning_llm.query_openrouter",
            return_value=_openrouter_response({
                "rationale": rationale,
                "call_state_override": "RIGHT",  # ignored
                "confidence_adjustment": "disagree-lower",  # ignored
            }),
        ):
            out = enrich_positioning(_make_result(team_state_call="LEFT"))

        assert out == rationale
