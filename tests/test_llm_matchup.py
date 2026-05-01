"""Tests for the LLM matchup wrapper in src/reports/llm_matchup.py.

Mirrors the test pattern in tests/test_llm_analysis.py.  All tests mock
``query_openrouter`` -- NEVER hits the real OpenRouter API (AC-T9).
"""

from __future__ import annotations

import datetime
import json
from unittest.mock import patch

import pytest

from src.llm.openrouter import LLMError
from src.reports.llm_matchup import (
    EnrichedMatchup,
    HitterCue,
    _build_user_prompt,
    _SYSTEM_PROMPT,
    enrich_matchup,
)
from src.reports.matchup import (
    DataNote,
    EligiblePitcher,
    LossRecipe,
    LossRecipeBucket,
    MatchupAnalysis,
    MatchupInputs,
    PullTendencyNote,
    ThreatHitter,
)


# ── Fixtures ────────────────────────────────────────────────────────────


def _make_threat(player_id: str, name: str, **overrides) -> ThreatHitter:
    defaults = {
        "player_id": player_id,
        "name": name,
        "jersey_number": "12",
        "pa": 35,
        "obp": 0.420,
        "slg": 0.510,
        "ops": 0.930,
        "bb_pct": 0.10,
        "k_pct": 0.18,
        "fps_swing_rate": 0.45,
        "chase_rate": 0.28,
        "swing_rate_by_count": {"0-0": 0.42, "1-1": 0.55},
        "cue_kind": "default",
        "supporting_stats": [f"{name} 35 PA", "45% first-pitch swing"],
    }
    defaults.update(overrides)
    return ThreatHitter(**defaults)


def _make_pitcher(player_id: str, name: str) -> EligiblePitcher:
    return EligiblePitcher(
        player_id=player_id,
        name=name,
        jersey_number="22",
        last_outing_date="2026-04-25",
        days_rest=5,
        last_outing_pitches=85,
        workload_7d=85,
    )


def _make_inputs(
    *,
    top_hitter_ids: list[tuple[str, str]] | None = None,
) -> MatchupInputs:
    """Build a MatchupInputs bundle with a configurable opponent_top_hitters list."""
    if top_hitter_ids is None:
        top_hitter_ids = [
            ("p-h1", "Adam Apple"),
            ("p-h2", "Bobby Banana"),
            ("p-h3", "Carlos Cherry"),
        ]
    top_hitters: list[dict] = []
    for pid, name in top_hitter_ids:
        top_hitters.append({
            "player_id": pid,
            "name": name,
            "jersey_number": "11",
            "pa": 35,
            "obp": 0.420,
            "slg": 0.510,
            "ops": 0.930,
            "bb": 4,
            "so": 6,
            "fps_seen": 30,
            "fps_swing_count": 14,
            "two_strike_pa": 12,
            "full_count_pa": 4,
            "chase_rate": 0.28,
            "swing_rate_by_count": {"0-0": 0.45, "1-1": 0.55},
        })
    return MatchupInputs(
        opponent_team={"id": 1, "name": "Test Tigers", "public_id": "test-tigers"},
        opponent_top_hitters=top_hitters,
        opponent_pitching=[],
        opponent_losses=[],
        # Real keys produced by ``get_sb_tendency`` in src/api/db.py --
        # see the AC-T3 prompt-construction test which asserts every value
        # appears in the rendered prompt (locks the grounding contract).
        opponent_sb_profile={
            "sb_attempts": 12,
            "sb_successes": 9,
            "sb_success_rate": 0.75,
            "catcher_cs_against_attempts": 7,
            "catcher_cs_against_count": 3,
            "catcher_cs_against_rate": 0.4286,
        },
        # Real keys produced by ``get_first_inning_pattern`` in src/api/db.py.
        opponent_first_inning_pattern={
            "games_played": 10,
            "games_with_first_inning_runs_scored": 4,
            "games_with_first_inning_runs_allowed": 3,
            "first_inning_scored_rate": 0.40,
            "first_inning_allowed_rate": 0.30,
        },
        opponent_roster_spray=[],
        lsb_team=None,
        lsb_pitching=None,
        reference_date=datetime.date(2026, 4, 30),
        season_id="2026",
    )


def _make_analysis(
    *,
    confidence: str = "moderate",
    threat_player_ids: list[tuple[str, str]] | None = None,
) -> MatchupAnalysis:
    if threat_player_ids is None:
        threat_player_ids = [
            ("p-h1", "Adam Apple"),
            ("p-h2", "Bobby Banana"),
            ("p-h3", "Carlos Cherry"),
        ]
    threats = [_make_threat(pid, name) for pid, name in threat_player_ids]
    recipe = LossRecipe(
        starter_shelled_early=LossRecipeBucket(
            count=2,
            grounding=[
                ("2026-04-10", 3, 9, "Joe Pitcher", "starter 1.2 IP, 5 ER"),
            ],
        ),
        bullpen_couldnt_hold=LossRecipeBucket(count=1, grounding=[]),
        close_game_lost_late=LossRecipeBucket(count=0, grounding=[]),
        uncategorized_count=1,
        total_losses=4,
    )
    return MatchupAnalysis(
        confidence=confidence,
        threat_list=threats,
        pull_tendency_notes=[
            PullTendencyNote(
                player_id="p-h1", name="Adam Apple",
                jersey_number="11", pull_pct=0.62, bip_count=18,
            ),
        ],
        sb_profile_summary={
            "sb_attempts": 12,
            "summary": "engine-sb-summary-marker",
        },
        first_inning_summary={
            "games_played": 10,
            "summary": "engine-fi-summary-marker",
        },
        loss_recipe_buckets=recipe,
        eligible_opposing_pitchers=[
            _make_pitcher("p-p1", "Pitcher One"),
            _make_pitcher("p-p2", "Pitcher Two"),
        ],
        eligible_lsb_pitchers=None,
        data_notes=[DataNote(message="Thin sample", subsection="loss_recipe")],
    )


def _wrap_response(payload: dict) -> dict:
    """Wrap a JSON payload into an OpenRouter-style chat response."""
    return {
        "choices": [
            {"message": {"content": json.dumps(payload)}},
        ],
    }


_VALID_PAYLOAD = {
    "game_plan_intro": "Disrupt their top of the order early and force \
their bullpen into late innings (4 losses include 1 bullpen-couldn't-hold).",
    "hitter_cues": [
        {
            "player_id": "p-h1",
            "cue": "Pitch around Adam Apple (10% BB, .510 SLG); \
he punishes mistakes.",
        },
        {
            "player_id": "p-h2",
            "cue": "Attack Bobby Banana early (45% first-pitch swing).",
        },
        {
            "player_id": "p-h3",
            "cue": "Expand the zone with two strikes against Carlos Cherry \
(18% K).",
        },
    ],
    "sb_profile_prose": "Hold runners; they attempt aggressively (12 SB \
attempts, 75% success).",
    "first_inning_prose": "Expect early pressure -- they score first 40% \
of games.",
    "loss_recipe_prose": "Their losses cluster in starter-shelled-early \
(2 of 4); attack the starter early.",
}


# ── AC-T1: Golden path ──────────────────────────────────────────────────


class TestGoldenPath:

    def test_enriches_with_valid_response(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
        monkeypatch.delenv("FEATURE_MATCHUP_STRICT", raising=False)

        analysis = _make_analysis()
        inputs = _make_inputs()

        with patch(
            "src.reports.llm_matchup.query_openrouter",
            return_value=_wrap_response(_VALID_PAYLOAD),
        ) as mock_qr:
            result = enrich_matchup(analysis, inputs)

        assert mock_qr.call_count == 1
        assert isinstance(result, EnrichedMatchup)
        assert result.analysis is analysis
        assert result.game_plan_intro == _VALID_PAYLOAD["game_plan_intro"]
        assert result.sb_profile_prose == _VALID_PAYLOAD["sb_profile_prose"]
        assert result.first_inning_prose == _VALID_PAYLOAD["first_inning_prose"]
        assert result.loss_recipe_prose == _VALID_PAYLOAD["loss_recipe_prose"]
        assert len(result.hitter_cues) == 3
        assert all(isinstance(c, HitterCue) for c in result.hitter_cues)
        assert [c.player_id for c in result.hitter_cues] == [
            "p-h1", "p-h2", "p-h3",
        ]
        assert result.model_used == "anthropic/claude-haiku-4-5-20251001"


# ── AC-T2: Suppress short-circuit ──────────────────────────────────────


class TestSuppressShortCircuit:

    def test_does_not_call_openrouter_on_suppress(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        analysis = _make_analysis(confidence="suppress")
        inputs = _make_inputs()

        with patch("src.reports.llm_matchup.query_openrouter") as mock_qr:
            result = enrich_matchup(analysis, inputs)

        assert mock_qr.call_count == 0
        assert isinstance(result, EnrichedMatchup)
        assert result.analysis is analysis
        assert result.game_plan_intro == ""
        assert result.hitter_cues == []
        assert result.sb_profile_prose == ""
        assert result.first_inning_prose == ""
        assert result.loss_recipe_prose == ""


# ── AC-T3: Prompt construction snapshot ────────────────────────────────


class TestPromptConstruction:

    def test_player_names_appear_in_user_prompt(self):
        inputs = _make_inputs(top_hitter_ids=[
            ("p-h1", "Adam Apple"),
            ("p-h2", "Bobby Banana"),
            ("p-h3", "Carlos Cherry"),
        ])
        analysis = _make_analysis(threat_player_ids=[
            ("p-h1", "Adam Apple"),
            ("p-h2", "Bobby Banana"),
            ("p-h3", "Carlos Cherry"),
        ])
        prompt = _build_user_prompt(analysis, inputs)
        for name in ("Adam Apple", "Bobby Banana", "Carlos Cherry"):
            assert name in prompt, f"{name!r} missing from user prompt"
        # Player IDs must also appear so the LLM can copy them.
        for pid in ("p-h1", "p-h2", "p-h3"):
            assert pid in prompt, f"{pid!r} missing from user prompt"
        # Engine confidence + opponent header.
        assert "Test Tigers" in prompt
        assert "Engine confidence: moderate" in prompt
        # Pull-tendency table header rendered (deterministic, for context).
        assert "Pull-Tendency Notes" in prompt
        # SB and first-inning grounding present.
        assert "Stolen-Base Profile" in prompt
        assert "First-Inning Pattern" in prompt
        # AC-4: engine deterministic summaries rendered separately from
        # raw inputs.  Both raw-input and engine-summary sub-headers must
        # appear, and the engine-summary marker fields must be visible so
        # the LLM cannot contradict the engine's deterministic core.
        assert "Raw input" in prompt
        assert "Engine summary" in prompt
        assert "engine-sb-summary-marker" in prompt
        assert "engine-fi-summary-marker" in prompt
        # Lock the grounding-table contract: every value from the SB and
        # first-inning raw input dicts must appear in the prompt.  These
        # assertions FAIL if the helper enumerates wrong keys (e.g., if
        # someone re-introduces "summary" or drops a real field from
        # ``get_sb_tendency`` / ``get_first_inning_pattern``).
        assert "sb_attempts: 12" in prompt
        assert "sb_successes: 9" in prompt
        assert "sb_success_rate: 0.75" in prompt
        assert "catcher_cs_against_attempts: 7" in prompt
        assert "catcher_cs_against_count: 3" in prompt
        assert "catcher_cs_against_rate: 0.4286" in prompt
        assert "games_played: 10" in prompt
        assert "games_with_first_inning_runs_scored: 4" in prompt
        assert "games_with_first_inning_runs_allowed: 3" in prompt
        assert "first_inning_scored_rate: 0.4" in prompt
        assert "first_inning_allowed_rate: 0.3" in prompt
        # Loss recipe block + bucket header.
        assert "Loss Recipe" in prompt
        assert "Starter shelled early" in prompt
        # Eligible opposing pitchers.
        assert "Eligible Opposing Pitchers" in prompt
        assert "Pitcher One" in prompt


# ── AC-T4: System prompt rules verbatim ────────────────────────────────


class TestSystemPromptRules:

    def test_contains_required_substrings(self):
        # These three substrings are the prompt's load-bearing anti-drift
        # anchors -- changes to the system prompt must keep them.
        assert "Do NOT invent statistics, names, or game results" in _SYSTEM_PROMPT
        assert "embed an inline parenthetical" in _SYSTEM_PROMPT
        assert "Lead with the recommendation" in _SYSTEM_PROMPT


# ── AC-T5: JSON parsing error paths ────────────────────────────────────


class TestJSONParsing:

    def test_not_json_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        response = {"choices": [{"message": {"content": "not JSON {"}}]}
        with patch("src.reports.llm_matchup.query_openrouter", return_value=response):
            with pytest.raises(LLMError, match="not valid JSON"):
                enrich_matchup(_make_analysis(), _make_inputs())

    def test_missing_required_field_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        bad = {k: v for k, v in _VALID_PAYLOAD.items() if k != "game_plan_intro"}
        with patch(
            "src.reports.llm_matchup.query_openrouter",
            return_value=_wrap_response(bad),
        ):
            with pytest.raises(LLMError, match="missing required.*game_plan_intro"):
                enrich_matchup(_make_analysis(), _make_inputs())

    def test_missing_hitter_cues_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        bad = {k: v for k, v in _VALID_PAYLOAD.items() if k != "hitter_cues"}
        with patch(
            "src.reports.llm_matchup.query_openrouter",
            return_value=_wrap_response(bad),
        ):
            with pytest.raises(LLMError, match="hitter_cues"):
                enrich_matchup(_make_analysis(), _make_inputs())

    def test_wrong_type_for_hitter_cues_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        bad = dict(_VALID_PAYLOAD)
        bad["hitter_cues"] = "this should be a list"
        with patch(
            "src.reports.llm_matchup.query_openrouter",
            return_value=_wrap_response(bad),
        ):
            with pytest.raises(LLMError, match="hitter_cues.*not a list"):
                enrich_matchup(_make_analysis(), _make_inputs())

    def test_wrong_type_for_string_field_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        bad = dict(_VALID_PAYLOAD)
        bad["sb_profile_prose"] = 42
        with patch(
            "src.reports.llm_matchup.query_openrouter",
            return_value=_wrap_response(bad),
        ):
            with pytest.raises(LLMError, match="sb_profile_prose.*not a string"):
                enrich_matchup(_make_analysis(), _make_inputs())

    def test_unexpected_response_structure_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        with patch(
            "src.reports.llm_matchup.query_openrouter",
            return_value={"error": "broken"},
        ):
            with pytest.raises(LLMError, match="Unexpected response structure"):
                enrich_matchup(_make_analysis(), _make_inputs())

    def test_hitter_cue_entry_missing_player_id_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        bad = dict(_VALID_PAYLOAD)
        bad["hitter_cues"] = [
            {"cue": "Missing player_id"},
        ]
        with patch(
            "src.reports.llm_matchup.query_openrouter",
            return_value=_wrap_response(bad),
        ):
            with pytest.raises(LLMError, match="missing/invalid 'player_id'"):
                enrich_matchup(_make_analysis(), _make_inputs())


# ── AC-T6: Hallucination guardrail -- strict mode ─────────────────────


class TestStrictMode:

    def test_strict_mode_raises_on_unknown_player_id(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        monkeypatch.setenv("FEATURE_MATCHUP_STRICT", "1")

        bad = dict(_VALID_PAYLOAD)
        bad["hitter_cues"] = [
            {"player_id": "p-h1", "cue": "Real player."},
            {"player_id": "p-fake", "cue": "Hallucinated player."},
            {"player_id": "p-h3", "cue": "Real player."},
        ]
        with patch(
            "src.reports.llm_matchup.query_openrouter",
            return_value=_wrap_response(bad),
        ):
            with pytest.raises(LLMError, match="Hallucinated.*p-fake"):
                enrich_matchup(_make_analysis(), _make_inputs())


# ── AC-T7: Hallucination guardrail -- graceful mode ────────────────────


class TestGracefulMode:

    def test_graceful_mode_filters_offender_preserves_rest(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        monkeypatch.delenv("FEATURE_MATCHUP_STRICT", raising=False)

        bad = dict(_VALID_PAYLOAD)
        bad["hitter_cues"] = [
            {"player_id": "p-h1", "cue": "Cue 1."},
            {"player_id": "p-fake", "cue": "Hallucinated."},
            {"player_id": "p-h2", "cue": "Cue 2."},
            {"player_id": "p-h3", "cue": "Cue 3."},
        ]
        with patch(
            "src.reports.llm_matchup.query_openrouter",
            return_value=_wrap_response(bad),
        ):
            result = enrich_matchup(_make_analysis(), _make_inputs())

        # Offender filtered; the other three preserved in order.
        assert len(result.hitter_cues) == 3
        assert [c.player_id for c in result.hitter_cues] == [
            "p-h1", "p-h2", "p-h3",
        ]
        # Other prose fields preserved.
        assert result.game_plan_intro == _VALID_PAYLOAD["game_plan_intro"]
        assert result.sb_profile_prose == _VALID_PAYLOAD["sb_profile_prose"]


# ── AC-T8: OpenRouter parameters pinned ────────────────────────────────


class TestOpenRouterParams:

    def test_params_pinned(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

        captured: dict = {}

        def fake_qr(messages, **kwargs):
            captured["messages"] = messages
            captured.update(kwargs)
            return _wrap_response(_VALID_PAYLOAD)

        with patch(
            "src.reports.llm_matchup.query_openrouter",
            side_effect=fake_qr,
        ):
            enrich_matchup(_make_analysis(), _make_inputs())

        assert captured["max_tokens"] == 1500
        assert captured["temperature"] == 0.3
        assert captured["model"] == "anthropic/claude-haiku-4-5-20251001"
        # Two messages: system + user.
        assert len(captured["messages"]) == 2
        assert captured["messages"][0]["role"] == "system"
        assert captured["messages"][1]["role"] == "user"

    def test_model_from_env_override(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        monkeypatch.setenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
        # Explicit env hygiene: ensure FEATURE_MATCHUP_STRICT is not set
        # by a prior test in a different order.
        monkeypatch.delenv("FEATURE_MATCHUP_STRICT", raising=False)

        captured: dict = {}

        def fake_qr(messages, **kwargs):
            captured.update(kwargs)
            return _wrap_response(_VALID_PAYLOAD)

        with patch(
            "src.reports.llm_matchup.query_openrouter",
            side_effect=fake_qr,
        ):
            result = enrich_matchup(_make_analysis(), _make_inputs())

        assert captured["model"] == "google/gemini-2.5-flash"
        assert result.model_used == "google/gemini-2.5-flash"


# ── AC-T9: Mocked client throughout (asserted by structural test) ──────


class TestMockedClientOnly:

    def test_no_real_api_calls_in_test_module(self, monkeypatch):
        """Sanity check the mock-only contract per AC-T9.

        If the wrapper ever bypasses the patched ``query_openrouter`` and
        reaches the real OpenRouter HTTP path, the missing API key will
        surface as an LLMError -- this test sets a placeholder key, then
        verifies that a normal enrich_matchup call goes through the
        patched mock and does NOT raise (proving the patch is the only
        path to the network).
        """
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-fake")

        with patch(
            "src.reports.llm_matchup.query_openrouter",
            return_value=_wrap_response(_VALID_PAYLOAD),
        ) as mock_qr:
            enrich_matchup(_make_analysis(), _make_inputs())
        # Mock was called exactly once -- nothing reached the real client.
        assert mock_qr.call_count == 1


# ── AC-1: client= injection contract ───────────────────────────────────


class TestClientInjection:
    """Lock the contract for callers passing ``client=`` per AC-1.

    The injected callable MUST be callable with the same kwargs the
    wrapper uses when calling ``query_openrouter`` (``model``,
    ``max_tokens``, ``temperature``) plus the positional ``messages``.
    This test does NOT patch ``query_openrouter`` -- it proves that when
    ``client=`` is supplied, the injected callable is used in its place.
    """

    def test_client_injection_uses_injected_callable(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
        monkeypatch.delenv("FEATURE_MATCHUP_STRICT", raising=False)

        captured: dict = {}

        def fake_client(messages, *, model, max_tokens, temperature):
            # Mirrors query_openrouter's signature: positional messages
            # + keyword-only model/max_tokens/temperature.
            captured["messages"] = messages
            captured["model"] = model
            captured["max_tokens"] = max_tokens
            captured["temperature"] = temperature
            return _wrap_response(_VALID_PAYLOAD)

        analysis = _make_analysis()
        inputs = _make_inputs()

        # NOTE: query_openrouter is intentionally NOT patched here.  If
        # the wrapper ignored client= and reached the real query_openrouter,
        # the call would attempt to perform a real HTTP request and fail.
        result = enrich_matchup(analysis, inputs, client=fake_client)

        # Injected client was invoked with the pinned kwargs.
        assert captured["max_tokens"] == 1500
        assert captured["temperature"] == 0.3
        assert captured["model"] == "anthropic/claude-haiku-4-5-20251001"
        assert len(captured["messages"]) == 2
        assert captured["messages"][0]["role"] == "system"
        assert captured["messages"][1]["role"] == "user"

        # Result was correctly parsed from the injected client's response.
        assert isinstance(result, EnrichedMatchup)
        assert result.game_plan_intro == _VALID_PAYLOAD["game_plan_intro"]
        assert len(result.hitter_cues) == 3
        assert [c.player_id for c in result.hitter_cues] == [
            "p-h1", "p-h2", "p-h3",
        ]
        assert result.model_used == "anthropic/claude-haiku-4-5-20251001"
