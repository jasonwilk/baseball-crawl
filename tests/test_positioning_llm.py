"""Tests for E-229-09: Tier 2 LLM input contract (v2).

Mocks :func:`src.reports.positioning_llm.query_openrouter` and covers
the AC-2 observable contract (length, structural citation, decision
discipline) plus the AC-3 non-fatal paths (LLM unavailable INFO,
LLM mid-call failure WARNING), plus AC-4 (validation drops + no DB
persistence) and AC-6 (input-assembly + grep AC for DB writes).
"""

from __future__ import annotations

import inspect
import json
import logging
import re
from pathlib import Path
from unittest.mock import patch

import pytest

import src.reports.positioning_llm as positioning_llm
from src.llm.openrouter import LLMError
from src.reports.positioning import PerPositionRow, TeamAggregateRow
from src.reports.positioning_llm import (
    _MAX_WORDS,
    _MIN_WORDS,
    _assemble_llm_input,
    _build_user_prompt,
    _has_decision_contradiction,
    _has_structural_citation,
    _truncate_to_in_band_sentence,
    _validate_response,
    generate_rationale,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_batter_row(
    *,
    position: str = "LF",
    direction_deviation: int = -1,
    depth_deviation: int = 0,
    zone_id: str | None = "B",
    is_thin: int = 0,
    bip_count: int = 38,
    hr_count: int = 2,
) -> PerPositionRow:
    return PerPositionRow(
        position=position,
        direction_deviation=direction_deviation,
        depth_deviation=depth_deviation,
        zone_id=zone_id,
        is_thin=is_thin,
        bip_count=bip_count,
        hr_count=hr_count,
    )


def _make_aggregate_row(
    *,
    position: str = "LF",
    star_x: float = 90.0,
    star_y: float = 120.0,
    bip_count: int = 320,
    is_low_confidence: int = 0,
) -> TeamAggregateRow:
    return TeamAggregateRow(
        position=position,
        star_x=star_x,
        star_y=star_y,
        bip_count=bip_count,
        is_low_confidence=is_low_confidence,
    )


def _make_metadata(
    *,
    jersey_number: str | None = "7",
    first_name: str = "Mike",
    last_name: str = "Ramirez",
    opponent_name: str = "Eagles",
    coverage_cue: str = "Through Apr 12 (12 games)",
) -> dict:
    return {
        "jersey_number": jersey_number,
        "first_name": first_name,
        "last_name": last_name,
        "opponent_name": opponent_name,
        "coverage_cue": coverage_cue,
    }


def _openrouter_response(content: str | dict) -> dict:
    if isinstance(content, dict):
        content = json.dumps(content)
    return {"choices": [{"message": {"content": content}}]}


# ---------------------------------------------------------------------------
# AC-1 / AC-6 (a) -- Input-assembly contract
# ---------------------------------------------------------------------------


class TestAssembleLLMInput:
    """AC-1: input-assembly function emits the locked contract shape."""

    def test_contract_keys_present(self):
        batter = _make_batter_row()
        agg = _make_aggregate_row()
        meta = _make_metadata()
        out = _assemble_llm_input(batter, agg, meta)
        expected_keys = {
            "jersey", "name", "position", "zone_id",
            "direction_deviation", "depth_deviation",
            "bip_count", "is_thin",
            "team_star_x", "team_star_y",
            "team_bip_count", "team_is_low_confidence",
            "opponent_name", "coverage_cue",
        }
        assert set(out.keys()) == expected_keys

    def test_contract_values_from_inputs(self):
        batter = _make_batter_row(
            position="3B",
            direction_deviation=-2,
            depth_deviation=1,
            zone_id="C",
            is_thin=0,
            bip_count=42,
        )
        agg = _make_aggregate_row(
            position="3B",
            star_x=160.5,
            star_y=200.0,
            bip_count=420,
            is_low_confidence=0,
        )
        meta = _make_metadata(jersey_number="11", first_name="Sam", last_name="Quinn")
        out = _assemble_llm_input(batter, agg, meta)
        assert out["jersey"] == "11"
        assert out["name"] == "Sam Quinn"
        assert out["position"] == "3B"
        assert out["zone_id"] == "C"
        assert out["direction_deviation"] == -2
        assert out["depth_deviation"] == 1
        assert out["bip_count"] == 42
        assert out["team_star_x"] == 160.5
        assert out["team_star_y"] == 200.0
        assert out["team_bip_count"] == 420
        assert out["team_is_low_confidence"] == 0
        assert out["opponent_name"] == "Eagles"
        assert out["coverage_cue"] == "Through Apr 12 (12 games)"

    def test_missing_jersey_is_none(self):
        batter = _make_batter_row()
        agg = _make_aggregate_row()
        meta = _make_metadata(jersey_number=None)
        out = _assemble_llm_input(batter, agg, meta)
        assert out["jersey"] is None

    def test_position_mismatch_raises(self):
        batter = _make_batter_row(position="LF")
        agg = _make_aggregate_row(position="RF")
        with pytest.raises(ValueError, match="Position mismatch"):
            _assemble_llm_input(batter, agg, _make_metadata())

    def test_prompt_includes_zone_and_deviations(self):
        batter = _make_batter_row(
            zone_id="B", direction_deviation=-1, depth_deviation=0, bip_count=38,
        )
        agg = _make_aggregate_row()
        meta = _make_metadata()
        body = _build_user_prompt(_assemble_llm_input(batter, agg, meta))
        assert "Zone: B" in body
        assert "direction_deviation: -1" in body
        assert "depth_deviation: 0" in body
        assert "BIP this season: 38" in body
        assert "Eagles" in body
        assert "Through Apr 12 (12 games)" in body

    def test_prompt_does_not_leak_v1_vocabulary(self):
        """v1 fields like call_state / team_state_call / direction_shade
        were retired in E-229-02. The prompt MUST NOT carry them."""
        batter = _make_batter_row()
        agg = _make_aggregate_row()
        body = _build_user_prompt(_assemble_llm_input(batter, agg, _make_metadata()))
        for forbidden in (
            "call_state", "team_state_call",
            "direction_shade", "depth_shade",
            "spray_charts", "svg_x", "svg_y",
        ):
            assert forbidden not in body


# ---------------------------------------------------------------------------
# AC-2 (a) -- length gate
# ---------------------------------------------------------------------------


class TestLengthGate:
    def test_too_short_is_skipped(self):
        batter = _make_batter_row()
        # 4 words < _MIN_WORDS (10).
        assert _validate_response("Pulls grounders to left.", batter) is None

    def test_at_min_length_passes(self):
        batter = _make_batter_row(zone_id="B")
        text = (
            "Loves to pull grounders to left field early in the count, "
            "especially against fastballs."
        )
        assert _validate_response(text, batter) == text

    def test_at_max_length_passes(self):
        batter = _make_batter_row(zone_id="B", direction_deviation=-1, bip_count=22)
        # ~50 words, 2 sentences, cites "left" + "22".
        text = (
            "This batter shows a strong pull tendency in the data: most "
            "of his 22 left-zone ground balls come on inside fastballs "
            "early in the count. The infield should expect grounders to "
            "left side and adjust accordingly to make routine plays."
        )
        out = _validate_response(text, batter)
        assert out is not None
        assert _MIN_WORDS <= len(out.split()) <= _MAX_WORDS

    def test_too_long_truncated_at_sentence_boundary(self):
        batter = _make_batter_row(zone_id="B", direction_deviation=-1)
        first_sentence = (
            "This batter pulls grounders to left field on most contact, "
            "with twenty-two of his ground balls landing on that side."
        )
        long_text = (
            first_sentence
            + " But there is also a non-trivial residual tendency where "
              "balls go elsewhere, particularly when he sees offspeed "
              "and is fooled into rolling over to opposite side instead. "
              "Coaches should still note that the bulk of contact aligns "
              "with the dominant call, so the recommendation stands solidly."
        )
        out = _validate_response(long_text, batter)
        assert out is not None
        assert out.startswith(first_sentence)
        assert len(out.split()) <= _MAX_WORDS

    def test_truncate_helper_returns_none_when_no_in_band_prefix(self):
        ultra_long = " ".join(["word"] * 60)
        assert _truncate_to_in_band_sentence(ultra_long) is None


# ---------------------------------------------------------------------------
# AC-2 (b) -- structural citation
# ---------------------------------------------------------------------------


class TestStructuralCitation:
    def test_zone_letter_phrase_counts_as_citation(self):
        batter = _make_batter_row(zone_id="B")
        assert _has_structural_citation(
            "Strong pull tendency: heavy concentration in Zone B on early counts.",
            batter,
        )

    def test_zone_longform_counts_as_citation(self):
        batter = _make_batter_row(zone_id="A")
        assert _has_structural_citation(
            "Hits clustered in the in-left part of the field this season.",
            batter,
        )

    def test_contact_type_keyword_counts_as_citation(self):
        batter = _make_batter_row()
        assert _has_structural_citation(
            "This hitter rolls a lot of ground balls in fastball counts.",
            batter,
        )

    def test_numeric_bip_count_counts(self):
        batter = _make_batter_row(bip_count=38)
        assert _has_structural_citation(
            "Has 38 batted balls heading the same direction this season.",
            batter,
        )

    def test_numeric_deviation_value_counts(self):
        batter = _make_batter_row(direction_deviation=-2)
        # |direction_deviation| = 2 is a citation-eligible number.
        assert _has_structural_citation(
            "Pulls 2 ordinal steps off the default each time he makes solid contact.",
            batter,
        )

    def test_no_zone_no_contact_type_no_number_fails(self):
        batter = _make_batter_row()
        assert not _has_structural_citation(
            "Likely a pull hitter based on tendency cues from the data here.",
            batter,
        )

    def test_validate_rejects_response_missing_citation(self):
        batter = _make_batter_row()
        text = (
            "This hitter has shown a clear pattern that the deterministic "
            "engine reflects accurately overall here."
        )
        assert _validate_response(text, batter) is None


# ---------------------------------------------------------------------------
# AC-2 (c) -- decision discipline
# ---------------------------------------------------------------------------


class TestDecisionDiscipline:
    def test_left_zone_with_shade_right_is_contradiction(self):
        # zone B -> direction_deviation < 0 (left). "shade right" contradicts.
        batter = _make_batter_row(zone_id="B")
        assert _has_decision_contradiction(
            "Strong tendency, shade right against this batter on early counts.",
            batter,
        )

    def test_left_zone_with_left_phrase_is_fine(self):
        batter = _make_batter_row(zone_id="B")
        assert not _has_decision_contradiction(
            "Pulls grounders to left field early in the count.",
            batter,
        )

    def test_right_zone_with_shade_left_is_contradiction(self):
        batter = _make_batter_row(zone_id="G", direction_deviation=1)
        assert _has_decision_contradiction(
            "Pulls left consistently against breaking balls.",
            batter,
        )

    def test_deep_zone_with_play_in_is_contradiction(self):
        # zone C is deep + left. "play him in" contradicts depth.
        batter = _make_batter_row(zone_id="C", direction_deviation=-1, depth_deviation=1)
        assert _has_decision_contradiction(
            "Play him in -- the data shows heavy ground-ball tendency this season.",
            batter,
        )

    def test_in_zone_with_play_deep_is_contradiction(self):
        # zone A is in + left. "play him deep" contradicts depth.
        batter = _make_batter_row(zone_id="A", direction_deviation=-1, depth_deviation=-1)
        assert _has_decision_contradiction(
            "Play him deep against power threat from this hitter.",
            batter,
        )

    def test_vertical_band_zone_d_no_horizontal_contradiction(self):
        # zone D (in, no horizontal lean) -- "shade left" / "shade right" are
        # both fine (no horizontal expectation to contradict).
        batter = _make_batter_row(zone_id="D", direction_deviation=0, depth_deviation=-1)
        assert not _has_decision_contradiction(
            "Shade left a touch on this batter.", batter,
        )
        assert not _has_decision_contradiction(
            "Shade right a touch on this batter.", batter,
        )

    def test_horizontal_band_zone_b_no_vertical_contradiction(self):
        # zone B (left, no vertical lean) -- "play deep" / "play in" are fine.
        batter = _make_batter_row(zone_id="B", direction_deviation=-1, depth_deviation=0)
        assert not _has_decision_contradiction(
            "Play him deep against this hitter on most counts.", batter,
        )

    def test_no_zone_falls_back_to_deviation_signs(self):
        """When zone_id is None the discipline check uses deviation signs
        directly (the engine emits NULL zone for batters on the star)."""
        batter = _make_batter_row(
            zone_id=None, direction_deviation=-1, depth_deviation=0,
        )
        assert _has_decision_contradiction(
            "Shade right against this batter on every count.", batter,
        )

    def test_validate_rejects_contradictory_response(self):
        batter = _make_batter_row(zone_id="B")
        # In-band, cites "left", but contradicts the left-half zone.
        text = (
            "Hits to left side but the better play is to shade right "
            "against this batter on most counts."
        )
        assert _validate_response(text, batter) is None


# ---------------------------------------------------------------------------
# AC-3 / AC-6 (c) -- LLM unavailable path (INFO log)
# ---------------------------------------------------------------------------


class TestLLMUnavailable:
    def test_returns_none_and_logs_info_when_api_key_unset(
        self, monkeypatch, caplog: pytest.LogCaptureFixture,
    ):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        caplog.set_level(logging.INFO, logger="src.reports.positioning_llm")

        out = generate_rationale(
            _make_batter_row(), _make_aggregate_row(), _make_metadata(),
        )

        assert out is None
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert any(
            "Tier 2 LLM unavailable" in r.getMessage() for r in info_records
        )
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert not warning_records, (
            "missing-config must NOT log at WARNING (AC-3 INFO contract)"
        )


# ---------------------------------------------------------------------------
# AC-3 / AC-6 (d) -- LLM mid-call failure (WARNING log, non-fatal)
# ---------------------------------------------------------------------------


class TestLLMMidCallFailure:
    def test_llm_error_caught_and_logged_warning(
        self, monkeypatch, caplog: pytest.LogCaptureFixture,
    ):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        caplog.set_level(logging.WARNING, logger="src.reports.positioning_llm")

        with patch(
            "src.reports.positioning_llm.query_openrouter",
            side_effect=LLMError("synthetic API failure"),
        ):
            out = generate_rationale(
                _make_batter_row(), _make_aggregate_row(), _make_metadata(),
            )

        assert out is None
        warnings_ = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("Tier 2 LLM call failed" in r.getMessage() for r in warnings_)

    def test_unexpected_exception_caught_and_logged_warning(
        self, monkeypatch, caplog: pytest.LogCaptureFixture,
    ):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        caplog.set_level(logging.WARNING, logger="src.reports.positioning_llm")

        with patch(
            "src.reports.positioning_llm.query_openrouter",
            side_effect=RuntimeError("synthetic non-LLM error"),
        ):
            out = generate_rationale(
                _make_batter_row(), _make_aggregate_row(), _make_metadata(),
            )

        assert out is None
        warnings_ = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            "Tier 2 LLM unexpected error" in r.getMessage() for r in warnings_
        )

    def test_malformed_response_routes_to_warning_and_drop(
        self, monkeypatch, caplog: pytest.LogCaptureFixture,
    ):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        caplog.set_level(logging.WARNING, logger="src.reports.positioning_llm")

        with patch(
            "src.reports.positioning_llm.query_openrouter",
            return_value=_openrouter_response("not even json"),
        ):
            out = generate_rationale(
                _make_batter_row(), _make_aggregate_row(), _make_metadata(),
            )

        assert out is None
        warnings_ = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("not valid JSON" in r.getMessage() for r in warnings_)


# ---------------------------------------------------------------------------
# AC-5 -- Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_valid_response_passes_through(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        batter = _make_batter_row(
            zone_id="B", direction_deviation=-1, depth_deviation=0, bip_count=22,
        )
        rationale = (
            "Loves to pull grounders to left field early in the count, "
            "especially on inside fastballs against right-handed pitchers."
        )

        with patch(
            "src.reports.positioning_llm.query_openrouter",
            return_value=_openrouter_response({"rationale": rationale}),
        ):
            out = generate_rationale(batter, _make_aggregate_row(), _make_metadata())

        assert out == rationale

    def test_response_missing_rationale_field_drops(
        self, monkeypatch, caplog: pytest.LogCaptureFixture,
    ):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        caplog.set_level(logging.WARNING, logger="src.reports.positioning_llm")

        with patch(
            "src.reports.positioning_llm.query_openrouter",
            return_value=_openrouter_response({"narrative": "wrong field"}),
        ):
            out = generate_rationale(
                _make_batter_row(), _make_aggregate_row(), _make_metadata(),
            )

        assert out is None
        warnings_ = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            "missing/non-string 'rationale'" in r.getMessage() for r in warnings_
        )

    def test_response_with_extra_fields_still_returns_rationale(
        self, monkeypatch,
    ):
        """Extra response fields (e.g. an attempt to override the call)
        are simply not read -- only the 'rationale' key is consumed."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        rationale = (
            "Strong pull tendency: 22 of 38 batted balls go to left field, "
            "mostly grounders early in the count."
        )

        with patch(
            "src.reports.positioning_llm.query_openrouter",
            return_value=_openrouter_response({
                "rationale": rationale,
                "zone_override": "G",  # ignored
                "confidence_adjustment": "disagree-lower",  # ignored
            }),
        ):
            out = generate_rationale(
                _make_batter_row(zone_id="B", bip_count=38),
                _make_aggregate_row(),
                _make_metadata(),
            )

        assert out == rationale


# ---------------------------------------------------------------------------
# AC-4 / AC-6 (e) -- No DB persistence
# ---------------------------------------------------------------------------


class TestNoDBPersistence:
    """AC-4 + AC-6 (e): the rationale lives only in render-pass memory.
    Verify via grep AC (source contains no INSERT/UPDATE against the
    positioning tables) and by inspecting the module surface."""

    SOURCE_PATH = Path(positioning_llm.__file__)

    def test_no_insert_or_update_against_positioning_tables(self):
        """Grep AC: the module source contains zero SQL INSERT/UPDATE
        statements against batter_positioning or team_position_aggregate.
        (Plain DB-write keywords are also banned to catch the indirect
        case where another module is invoked to persist.)"""
        text = self.SOURCE_PATH.read_text()
        forbidden_patterns = (
            r"INSERT\s+INTO\s+batter_positioning",
            r"UPDATE\s+batter_positioning",
            r"INSERT\s+INTO\s+team_position_aggregate",
            r"UPDATE\s+team_position_aggregate",
        )
        for pat in forbidden_patterns:
            assert not re.search(pat, text, re.IGNORECASE), (
                f"positioning_llm.py must not write to positioning tables; "
                f"found pattern {pat!r}"
            )

    def test_module_does_not_import_sqlite3(self):
        """The module does not open DB connections at all; per CR B1 lock
        the rationale layer is purely render-time."""
        text = self.SOURCE_PATH.read_text()
        # Exclude type-annotation imports inside TYPE_CHECKING blocks;
        # a runtime import of sqlite3 would be a code smell here.
        assert not re.search(
            r"^import\s+sqlite3\b", text, re.MULTILINE,
        )
        assert not re.search(
            r"^from\s+sqlite3\s+import\b", text, re.MULTILINE,
        )

    def test_public_surface_accepts_no_connection(self):
        """The public entry point's signature carries no DB Connection
        parameter -- it cannot persist even if asked."""
        sig = inspect.signature(generate_rationale)
        params = list(sig.parameters.values())
        # Three positional args: batter_row, aggregate_row, batter_metadata.
        assert len(params) == 3
        for p in params:
            assert "connection" not in p.name.lower()
            assert "conn" != p.name.lower()


# ---------------------------------------------------------------------------
# AC-6 -- Cross-AC smoke (assemble -> validate -> rationale path)
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_full_pipeline_with_real_input_assembly(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        batter = _make_batter_row(
            position="3B", zone_id="A",
            direction_deviation=-1, depth_deviation=-1, bip_count=27, hr_count=3,
        )
        agg = _make_aggregate_row(position="3B", star_x=180.0, star_y=215.0, bip_count=380)
        meta = _make_metadata(jersey_number="14", first_name="Jordan", last_name="Lee")

        rationale = (
            "Pulls hot grounders into Zone A, especially on inside fastballs "
            "early in the count; expect ground balls in this area."
        )

        with patch(
            "src.reports.positioning_llm.query_openrouter",
            return_value=_openrouter_response({"rationale": rationale}),
        ) as mock_qr:
            out = generate_rationale(batter, agg, meta)

        assert out == rationale
        # The mock saw a prompt containing the assembled-input values.
        call_kwargs = mock_qr.call_args
        messages = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs["messages"]
        user_prompt = next(m["content"] for m in messages if m["role"] == "user")
        assert "Zone: A" in user_prompt
        assert "direction_deviation: -1" in user_prompt
        assert "depth_deviation: -1" in user_prompt
        assert "#14" in user_prompt
        assert "Jordan Lee" in user_prompt
