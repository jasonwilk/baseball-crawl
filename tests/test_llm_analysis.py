"""Tests for the LLM analysis module in src/reports/llm_analysis.py."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from src.llm.openrouter import LLMError
from src.reports.llm_analysis import (
    EnrichedPrediction,
    _build_user_prompt,
    _format_pitcher_table,
    enrich_prediction,
)
from src.reports.starter_prediction import StarterPrediction


# ── Fixtures ────────────────────────────────────────────────────────────


def _make_prediction(**kwargs) -> StarterPrediction:
    """Build a StarterPrediction with sensible defaults."""
    defaults = {
        "confidence": "high",
        "predicted_starter": {
            "player_id": "p1",
            "name": "Ace Smith",
            "jersey_number": "22",
            "likelihood": 0.85,
            "reasoning": "Next in rotation, 5 days rest",
            "games_started": 8,
            "recent_starts": [
                {
                    "game_date": "2026-03-28",
                    "ip_outs": 18,
                    "pitches": 85,
                    "so": 6,
                    "bb": 2,
                    "decision": "W",
                    "rest_days_from_previous_start": 4,
                },
            ],
        },
        "rotation_pattern": "ace-dominant",
        "top_candidates": [
            {
                "player_id": "p1",
                "name": "Ace Smith",
                "jersey_number": "22",
                "likelihood": 0.85,
                "reasoning": "Next in rotation",
                "games_started": 8,
                "recent_starts": [],
            },
        ],
        "rest_table": [
            {
                "name": "Ace Smith",
                "jersey_number": "22",
                "games_started": 8,
                "last_outing_date": "2026-03-28",
                "days_since_last_appearance": 3,
                "last_outing_pitches": 85,
                "workload_7d": 85,
            },
        ],
        "bullpen_order": [
            {
                "name": "Closer Jones",
                "jersey_number": "45",
                "frequency": 5,
                "games_sampled": 10,
            },
        ],
        "data_note": None,
    }
    defaults.update(kwargs)
    return StarterPrediction(**defaults)


_SAMPLE_HISTORY = [
    {
        "player_id": "p1",
        "first_name": "Ace",
        "last_name": "Smith",
        "jersey_number": "22",
        "game_id": "g01",
        "game_date": "2026-03-28",
        "start_time": "16:00",
        "ip_outs": 18,
        "pitches": 85,
        "so": 6,
        "bb": 2,
        "h": 4,
        "r": 2,
        "er": 1,
        "bf": 22,
        "decision": "W",
        "appearance_order": 1,
        "rest_days": None,
        "team_game_number": 1,
    },
]

_VALID_LLM_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": json.dumps({
                    "narrative": "Ace Smith is the clear starter. Strong recent form.",
                    "bullpen_sequence": "Expect Jones in relief from the 5th inning.",
                    "confidence_adjustment": "agree",
                }),
            },
        },
    ],
}


# ── Prompt construction tests (AC-10) ──────────────────────────────────


class TestPromptConstruction:
    """Verify prompt includes required data."""

    def test_includes_pitcher_data(self):
        pred = _make_prediction()
        prompt = _build_user_prompt(pred, _SAMPLE_HISTORY)
        assert "Ace Smith" in prompt
        assert "ace-dominant" in prompt

    def test_includes_tier1_prediction(self):
        pred = _make_prediction()
        prompt = _build_user_prompt(pred, _SAMPLE_HISTORY)
        assert "Confidence: high" in prompt
        assert "Predicted starter: Ace Smith" in prompt

    def test_includes_team_records(self):
        pred = _make_prediction()
        prompt = _build_user_prompt(
            pred, _SAMPLE_HISTORY,
            team_record="15-3", opponent_record="12-6",
        )
        assert "15-3" in prompt
        assert "12-6" in prompt
        assert "Scouted team:" in prompt
        assert "Our team:" in prompt

    def test_records_omitted_when_none(self):
        pred = _make_prediction()
        prompt = _build_user_prompt(pred, _SAMPLE_HISTORY)
        assert "Records" not in prompt

    def test_includes_game_count(self):
        pred = _make_prediction()
        prompt = _build_user_prompt(pred, _SAMPLE_HISTORY)
        assert "Total completed games in season: 1" in prompt

    def test_includes_alternative_when_present(self):
        pred = _make_prediction(
            confidence="moderate",
            alternative={
                "player_id": "p2",
                "name": "Bravo Lee",
                "jersey_number": "15",
                "likelihood": 0.4,
                "reasoning": "Higher K/9",
                "games_started": 4,
                "recent_starts": [],
            },
        )
        prompt = _build_user_prompt(pred, _SAMPLE_HISTORY)
        assert "Alternative: Bravo Lee" in prompt

    def test_includes_data_note_when_present(self):
        pred = _make_prediction(
            data_note="Compressed schedule detected -- rotation predictions less reliable.",
        )
        prompt = _build_user_prompt(pred, _SAMPLE_HISTORY)
        assert "Compressed schedule" in prompt

    def test_includes_rest_table(self):
        pred = _make_prediction()
        table = _format_pitcher_table(pred)
        assert "Rest & Availability Table" in table
        assert "Ace Smith" in table

    def test_includes_bullpen_order(self):
        pred = _make_prediction()
        table = _format_pitcher_table(pred)
        assert "Bullpen Order" in table
        assert "Closer Jones" in table

    def test_includes_recent_game_log(self):
        pred = _make_prediction()
        table = _format_pitcher_table(pred)
        assert "Recent Game Log" in table
        assert "2026-03-28" in table


# ── Response parsing tests (AC-10) ─────────────────────────────────────


class TestResponseParsing:

    def test_extracts_narrative(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.return_value = _VALID_LLM_RESPONSE
            result = enrich_prediction(
                _make_prediction(), _SAMPLE_HISTORY,
            )

        assert isinstance(result, EnrichedPrediction)
        assert result.narrative == "Ace Smith is the clear starter. Strong recent form."
        assert result.bullpen_sequence == "Expect Jones in relief from the 5th inning."
        assert result.model_used == "anthropic/claude-haiku-4-5-20251001"

    def test_base_prediction_preserved(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.return_value = _VALID_LLM_RESPONSE
            pred = _make_prediction()
            result = enrich_prediction(pred, _SAMPLE_HISTORY)

        assert result.base is pred

    def test_bullpen_sequence_nullable(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "narrative": "Analysis text.",
                        "bullpen_sequence": None,
                        "confidence_adjustment": "agree",
                    }),
                },
            }],
        }
        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.return_value = response
            result = enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)

        assert result.bullpen_sequence is None

    def test_confidence_adjustment_discarded(self, monkeypatch):
        """confidence_adjustment is requested but not stored per AC-6."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.return_value = _VALID_LLM_RESPONSE
            result = enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)

        assert not hasattr(result, "confidence_adjustment")

    def test_records_passed_to_prompt(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        captured_messages = []

        def mock_qr(messages, **kwargs):
            captured_messages.extend(messages)
            return _VALID_LLM_RESPONSE

        with patch("src.reports.llm_analysis.query_openrouter", side_effect=mock_qr):
            enrich_prediction(
                _make_prediction(), _SAMPLE_HISTORY,
                team_record="15-3", opponent_record="10-8",
            )

        user_msg = captured_messages[1]["content"]
        assert "15-3" in user_msg
        assert "10-8" in user_msg

    def test_model_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        monkeypatch.setenv("OPENROUTER_MODEL", "google/gemini-flash")

        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.return_value = _VALID_LLM_RESPONSE
            result = enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)

        assert result.model_used == "google/gemini-flash"


# ── Malformed response tests (AC-8, AC-10) ─────────────────────────────


class TestMalformedResponses:

    def test_not_json_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        response = {
            "choices": [{"message": {"content": "This is not JSON"}}],
        }
        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.return_value = response
            with pytest.raises(LLMError, match="not valid JSON"):
                enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)

    def test_missing_narrative_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        response = {
            "choices": [{
                "message": {
                    "content": json.dumps({"bullpen_sequence": "text"}),
                },
            }],
        }
        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.return_value = response
            with pytest.raises(LLMError, match="missing required.*narrative"):
                enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)

    def test_narrative_not_string_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        response = {
            "choices": [{
                "message": {
                    "content": json.dumps({"narrative": 42}),
                },
            }],
        }
        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.return_value = response
            with pytest.raises(LLMError, match="narrative.*not a string"):
                enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)

    def test_missing_choices_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.return_value = {"error": "something"}
            with pytest.raises(LLMError, match="Unexpected response structure"):
                enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)

    def test_empty_choices_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.return_value = {"choices": []}
            with pytest.raises(LLMError, match="Unexpected response structure"):
                enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)

    def test_api_error_propagates(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.side_effect = LLMError("OpenRouter rate limit exceeded (429)")
            with pytest.raises(LLMError, match="429"):
                enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)
