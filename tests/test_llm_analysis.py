"""Tests for the LLM analysis module in src/reports/llm_analysis.py."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from src.llm.openrouter import LLMError
from src.reports.llm_analysis import (
    _SYSTEM_PROMPT_TEMPLATE,
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
                "days_rest": 5,
                "last_outing_pitches": 85,
                "rest_eligibility": "available",
                "rest_estimate": False,
                "preferred_rest": None,
                "start_share_pct": 27,
                "total_team_games": 30,
                "throws": None,
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
    "model": "anthropic/claude-haiku-4-5-20251001",
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


def _response_with_content(content: str, *, model: str = "test/model") -> dict:
    """Build an OpenRouter-shaped response wrapping raw ``content``."""
    return {
        "model": model,
        "choices": [{"message": {"content": content}}],
    }


# ── Prompt construction tests (AC-10) ──────────────────────────────────


class TestSystemPrompt:
    """AC-1 / AC-2: validated Variant A system prompt, no no-predict guideline."""

    def test_no_manufacture_guideline(self):
        # AC-1: the removed "Do not manufacture a prediction" guideline is gone.
        assert "manufacture" not in _SYSTEM_PROMPT_TEMPLATE
        assert "Do not manufacture" not in _SYSTEM_PROMPT_TEMPLATE
        assert "LOW/COMMITTEE" not in _SYSTEM_PROMPT_TEMPLATE

    def test_variant_a_lead_and_structure(self):
        # AC-2: leads with the named most-likely arm + concrete rest reason.
        assert "bench briefing" in _SYSTEM_PROMPT_TEMPLATE
        assert "single most-likely arm by name" in _SYSTEM_PROMPT_TEMPLATE
        assert "Always name a specific pitcher in your first sentence." in (
            _SYSTEM_PROMPT_TEMPLATE
        )

    def test_retains_json_envelope(self):
        # The response contract (JSON envelope) is retained for the parser.
        assert '"narrative"' in _SYSTEM_PROMPT_TEMPLATE
        assert "JSON object" in _SYSTEM_PROMPT_TEMPLATE


class TestPromptConstruction:
    """AC-2: the Variant A ranked-arms data block."""

    def test_ranked_arms_block_header(self):
        pred = _make_prediction()
        prompt = _build_user_prompt(pred, _SAMPLE_HISTORY)
        assert "MOST LIKELY ARMS TODAY:" in prompt
        assert "Ace Smith" in prompt

    def test_arm_line_has_rest_eligibility_and_starts(self):
        pred = _make_prediction()
        prompt = _build_user_prompt(pred, _SAMPLE_HISTORY)
        # "1. Ace Smith (#22) — 5 days rest, fully rested (only eligible arm
        #  today) | 85 pitches 5 days ago | 8 of 30 starts this season"
        assert "1. Ace Smith (#22)" in prompt
        assert "5 days rest" in prompt
        assert "fully rested" in prompt
        assert "85 pitches" in prompt
        assert "8 of 30 starts this season" in prompt

    def test_single_candidate_marked_only_eligible(self):
        pred = _make_prediction()
        prompt = _build_user_prompt(pred, _SAMPLE_HISTORY)
        assert "(only eligible arm today)" in prompt

    def test_discounted_label(self):
        pred = _make_prediction(
            top_candidates=[
                {
                    "player_id": "p1", "name": "Ace Smith", "jersey_number": "22",
                    "likelihood": 0.85, "reasoning": "x", "games_started": 8,
                    "recent_starts": [], "days_rest": 2,
                    "last_outing_pitches": 70, "rest_eligibility": "discounted",
                    "rest_estimate": False, "preferred_rest": 4,
                    "start_share_pct": 27, "total_team_games": 30, "throws": None,
                },
                {
                    "player_id": "p2", "name": "Bravo Lee", "jersey_number": "15",
                    "likelihood": 0.4, "reasoning": "y", "games_started": 6,
                    "recent_starts": [], "days_rest": 6,
                    "last_outing_pitches": 60, "rest_eligibility": "available",
                    "rest_estimate": False, "preferred_rest": None,
                    "start_share_pct": 20, "total_team_games": 30, "throws": None,
                },
            ],
        )
        prompt = _build_user_prompt(pred, _SAMPLE_HISTORY)
        assert "eligible but on short rest" in prompt
        # 2+ candidates -> no "only eligible arm" tag.
        assert "only eligible arm today" not in prompt

    def test_unavailable_block(self):
        pred = _make_prediction(
            unavailable_arms=[
                {"name": "Carl Diaz", "reason": "0d rest -- needs 2"},
            ],
        )
        prompt = _build_user_prompt(pred, _SAMPLE_HISTORY)
        assert "UNAVAILABLE TODAY:" in prompt
        assert "- Carl Diaz: 0d rest -- needs 2" in prompt

    def test_opponent_header_and_closing(self):
        pred = _make_prediction()
        prompt = _build_user_prompt(pred, _SAMPLE_HISTORY, team_name="Gretna 216")
        assert "OPPONENT: Gretna 216" in prompt
        assert "Write a 2-4 sentence briefing for the coach now." in prompt

    def test_retains_integer_ip_outs_game_log(self):
        # AC-8 guard: the integer "IP Outs" recent-game-log column is preserved.
        pred = _make_prediction()
        table = _format_pitcher_table(pred)
        assert "IP Outs" in table
        assert "2026-03-28" in table

    def test_no_decimal_ip_field(self):
        # AC-8 guard: no decimal IP field (e.g. "6.0 IP") in the data block.
        pred = _make_prediction()
        table = _format_pitcher_table(pred)
        assert " IP)" not in table
        assert "6.0 IP" not in table


class TestEstimateAndNoJargon:
    """AC-3 / AC-6(a): estimate consequence framing + no brand-emit directive."""

    def test_estimate_consequence_framing_reaches_prompt(self):
        pred = _make_prediction(is_estimate=True)
        prompt = _build_user_prompt(pred, _SAMPLE_HISTORY)
        assert "league pitch rules are not on file" in prompt
        assert "treat borderline calls as approximate" in prompt

    def test_estimate_framing_is_jargon_free(self):
        pred = _make_prediction(is_estimate=True)
        prompt = _build_user_prompt(pred, _SAMPLE_HISTORY)
        for brand in ("Pitch Smart", "USA Baseball", "soft prior"):
            assert brand not in prompt

    def test_no_estimate_note_when_not_estimate(self):
        pred = _make_prediction(is_estimate=False)
        prompt = _build_user_prompt(pred, _SAMPLE_HISTORY)
        assert "not on file" not in prompt

    def test_system_prompt_forbids_brands_not_a_directive(self):
        # AC-6(a): brand terms appear ONLY inside the prohibition line, never as
        # an instruction to emit them in the output.
        assert "Never use these words or phrases" in _SYSTEM_PROMPT_TEMPLATE
        assert '"Pitch Smart," "Legion,"' in _SYSTEM_PROMPT_TEMPLATE


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
        """confidence_adjustment is requested but intentionally not stored."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.return_value = _VALID_LLM_RESPONSE
            result = enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)

        assert not hasattr(result, "confidence_adjustment")

    def test_records_accepted_but_not_rendered(self, monkeypatch):
        """E-243-04 AC-5: Variant A drops the records section; the params are
        still accepted for call-site compatibility but no longer rendered."""
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
        assert "15-3" not in user_msg
        assert "10-8" not in user_msg

    def test_model_used_from_response_not_env_or_constant(self, monkeypatch):
        """model_used derives from response['model'], not env or the constant (AC-5, F-A)."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        # Env set to a DIFFERENT model than the response reports.
        monkeypatch.setenv("OPENROUTER_MODEL", "google/gemini-flash")

        response = _response_with_content(
            json.dumps({"narrative": "Analysis text."}),
            model="anthropic/claude-sonnet-4-5",
        )
        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.return_value = response
            result = enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)

        # Comes from the response body, NOT the env var, NOT the default constant.
        assert result.model_used == "anthropic/claude-sonnet-4-5"
        assert result.model_used != "google/gemini-flash"

    def test_model_used_safe_fallback_when_absent(self, monkeypatch):
        """A response lacking 'model' yields a safe fallback, not a crash (F-A)."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        response = {"choices": [{"message": {"content": json.dumps({"narrative": "Text."})}}]}
        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.return_value = response
            result = enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)

        assert result.model_used == "unknown"

    def test_no_model_kwarg_passed_to_query_openrouter(self, monkeypatch):
        """Single-source default: enrich_prediction does not override the model (AC-5, TN-5)."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        captured_kwargs = {}

        def mock_qr(messages, **kwargs):
            captured_kwargs.update(kwargs)
            return _VALID_LLM_RESPONSE

        with patch("src.reports.llm_analysis.query_openrouter", side_effect=mock_qr):
            enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)

        # query_openrouter owns model + max_tokens defaults; call site overrides neither.
        assert "model" not in captured_kwargs
        assert "max_tokens" not in captured_kwargs


# ── Malformed response tests (AC-8, AC-10) ─────────────────────────────


class TestMalformedResponses:

    def test_not_json_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        response = {
            "choices": [{"message": {"content": "This is not JSON"}}],
        }
        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.return_value = response
            with pytest.raises(LLMError):
                enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)

    def test_empty_narrative_raises(self, monkeypatch):
        """An empty narrative triggers Tier-1 fallback per F-G (deliberate tightening)."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        response = _response_with_content(json.dumps({"narrative": "   "}))
        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.return_value = response
            with pytest.raises(LLMError, match="empty"):
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


# ── Defensive parse + retry tests (E-233-02: AC-2, AC-3, AC-4, AC-7, AC-8) ──


class TestDefensiveParseAndRetry:

    def test_fenced_response_succeeds(self, monkeypatch):
        """A ```json-fenced response (previously dropped Tier-2) now parses (AC-4)."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        fenced = "```json\n" + json.dumps({
            "narrative": "Ace Smith starts; bullpen rested.",
            "bullpen_sequence": "Jones then Lee.",
        }) + "\n```"
        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.return_value = _response_with_content(fenced)
            result = enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)

        assert isinstance(result, EnrichedPrediction)
        assert result.narrative == "Ace Smith starts; bullpen rested."
        assert result.bullpen_sequence == "Jones then Lee."
        # No retry needed: single call.
        assert mock_qr.call_count == 1

    def test_prose_wrapped_response_succeeds(self, monkeypatch):
        """Leading prose around the JSON still parses (AC-4)."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        content = "Here is the analysis:\n" + json.dumps({"narrative": "Solid start."})
        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.return_value = _response_with_content(content)
            result = enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)

        assert result.narrative == "Solid start."
        assert mock_qr.call_count == 1

    def test_retry_recovers_after_unparseable_first(self, monkeypatch):
        """First response unparseable → one retry → parseable → success (AC-2)."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        good = _response_with_content(json.dumps({"narrative": "Recovered on retry."}))
        responses = [
            _response_with_content("totally not json"),
            good,
        ]
        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.side_effect = responses
            result = enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)

        assert result.narrative == "Recovered on retry."
        assert mock_qr.call_count == 2

    def test_both_calls_temperature_zero_and_identical_kwargs(self, monkeypatch):
        """E-243-04 AC-7c: initial call is now 0.0 (retry already 0.0)."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        calls: list[dict] = []

        def mock_qr(messages, **kwargs):
            calls.append({"messages": messages, **kwargs})
            if len(calls) == 1:
                return _response_with_content("not json")
            return _response_with_content(json.dumps({"narrative": "ok"}))

        with patch("src.reports.llm_analysis.query_openrouter", side_effect=mock_qr):
            enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)

        assert len(calls) == 2
        # Both the initial call and the retry use temperature 0.0.
        assert calls[0]["temperature"] == 0.0
        assert calls[1]["temperature"] == 0.0
        # Every kwarg other than temperature is identical across both calls.
        first = {k: v for k, v in calls[0].items() if k != "temperature"}
        second = {k: v for k, v in calls[1].items() if k != "temperature"}
        assert first == second

    def test_retry_exhaustion_raises_llmerror(self, monkeypatch):
        """Both attempts unparseable → LLMError after exactly one retry (AC-3, TN-2)."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.return_value = _response_with_content("never valid json")
            with pytest.raises(LLMError):
                enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)
            # Exactly one retry: two calls total, no retry storm.
            assert mock_qr.call_count == 2

    def test_no_retry_on_http_error(self, monkeypatch):
        """HTTP/transport errors raise immediately with no retry (AC-2)."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.side_effect = LLMError("OpenRouter request timed out")
            with pytest.raises(LLMError, match="timed out"):
                enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)
            # Single call: the initial _invoke raised before the parse step.
            assert mock_qr.call_count == 1

    def test_no_retry_on_malformed_envelope(self, monkeypatch):
        """A malformed envelope raises LLMError after EXACTLY ONE call, no retry (P2)."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        with patch("src.reports.llm_analysis.query_openrouter") as mock_qr:
            mock_qr.return_value = {"choices": []}  # can't pull content out
            with pytest.raises(LLMError, match="Unexpected response structure"):
                enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)
            # Envelope errors are not parse failures: no retry.
            assert mock_qr.call_count == 1

    def test_response_format_json_object_on_both_calls(self, monkeypatch):
        """response_format={'type':'json_object'} rides initial call AND retry (AC-3, F-C)."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        calls: list[dict] = []

        def mock_qr(messages, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return _response_with_content("not json")  # force the retry
            return _response_with_content(json.dumps({"narrative": "ok"}))

        with patch("src.reports.llm_analysis.query_openrouter", side_effect=mock_qr):
            enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)

        assert len(calls) == 2
        assert calls[0]["response_format"] == {"type": "json_object"}
        assert calls[1]["response_format"] == {"type": "json_object"}

    def test_parser_remains_baseline_with_response_format(self, monkeypatch):
        """Even when response_format is requested, a fenced response still parses (AC-5)."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        fenced = "```json\n" + json.dumps({"narrative": "Parser still runs."}) + "\n```"
        captured: list[dict] = []

        def mock_qr(messages, **kwargs):
            captured.append(kwargs)
            return _response_with_content(fenced)

        with patch("src.reports.llm_analysis.query_openrouter", side_effect=mock_qr):
            result = enrich_prediction(_make_prediction(), _SAMPLE_HISTORY)

        # response_format was requested, yet the TN-1 parser still recovered the JSON.
        assert captured[0]["response_format"] == {"type": "json_object"}
        assert result.narrative == "Parser still runs."
