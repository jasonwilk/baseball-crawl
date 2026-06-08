"""LLM-enriched starter analysis (Tier 2).

Builds a prompt from structured pitching data and the Tier 1 deterministic
prediction, calls OpenRouter, and parses the response into an
``EnrichedPrediction`` dataclass.  Enrichment is optional -- callers detect
availability via ``is_llm_available()`` and handle ``LLMError`` as non-fatal.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Any

from src.llm.json_extract import extract_json_object
from src.llm.openrouter import LLMError, query_openrouter
from src.reports.starter_prediction import (
    StarterPrediction,
    format_nsaa_rest_table,
    get_nsaa_rules,
)

logger = logging.getLogger(__name__)


@dataclass
class EnrichedPrediction:
    """Tier 2 enrichment wrapping the Tier 1 ``StarterPrediction``."""

    base: StarterPrediction
    narrative: str
    bullpen_sequence: str | None
    model_used: str


# ── Prompt construction ─────────────────────────────────────────────────

_SYSTEM_PROMPT_TEMPLATE = """\
You are a high school baseball coaching analyst. You analyze pitching \
rotation data and produce concise, actionable scouting intelligence for \
coaches preparing for their next game.

{nsaa_rest_table}

Your analysis should be practical and bench-ready. Coaches want to know:
1. Who is most likely to start and why
2. What bullpen sequence to expect
3. Any workload or rest concerns
4. Any NSAA pitch count compliance issues (unavailable arms, approaching limits)

Respond ONLY with a JSON object (no markdown, no code fences) containing:
{{
  "narrative": "2-4 sentence analysis of the predicted starter and key factors",
  "bullpen_sequence": "Expected bullpen sequence after the starter (1-2 sentences, or null if insufficient data)",
  "confidence_adjustment": "agree" or "disagree-higher" or "disagree-lower" (your assessment vs the deterministic prediction)
}}

Guidelines:
- Use plain English a coach understands. No jargon like "WHIP" unless the data includes it.
- At HIGH confidence: confirm the prediction, note any workload concerns.
- At MODERATE confidence: explain the alternative scenario clearly.
- At LOW/COMMITTEE confidence: explain the ambiguity honestly. Do not manufacture a prediction.
- If W-L records suggest a meaningful matchup (e.g., strong team vs weak), note that coaches sometimes elevate their top arm for big games (~25-30% of HS games), but do not overstate this -- record alone cannot predict deployment decisions.
- If compressed schedule is noted, mention that rotation predictions are less reliable in tournament play.
- If any bullpen pitcher is marked unavailable, note the reason and suggest skipping them in the sequence.
"""


def _format_pitcher_table(prediction: StarterPrediction) -> str:
    """Format pitcher candidates and rest table as structured text."""
    lines: list[str] = []

    if prediction.top_candidates:
        lines.append("## Top Starter Candidates")
        lines.append(
            f"{'Name':<20} {'GS':>3} {'Likelihood':>10} {'Reasoning'}"
        )
        lines.append("-" * 70)
        for c in prediction.top_candidates:
            lines.append(
                f"{c['name']:<20} {c['games_started']:>3} "
                f"{c['likelihood']:>10.1%} {c['reasoning']}"
            )

    if prediction.rest_table:
        lines.append("")
        lines.append("## Rest & Availability Table")
        lines.append(
            f"{'Name':<20} {'GS':>3} {'Last Outing':>12} "
            f"{'Days Rest':>9} {'Last Pitches':>12} {'7d Workload':>11}"
        )
        lines.append("-" * 80)
        for r in prediction.rest_table:
            last_date = r.get("last_outing_date") or "?"
            days = r.get("days_since_last_appearance")
            days_str = str(days) if days is not None else "?"
            pitches = r.get("last_outing_pitches")
            pitches_str = str(pitches) if pitches is not None else "?"
            wl = r.get("workload_7d")
            wl_str = str(wl) if wl is not None else "?"
            lines.append(
                f"{r['name']:<20} {r['games_started']:>3} "
                f"{last_date:>12} {days_str:>9} "
                f"{pitches_str:>12} {wl_str:>11}"
            )

    if prediction.bullpen_order:
        lines.append("")
        lines.append("## Bullpen Order (by first-relief frequency)")
        lines.append(
            f"{'Name':<20} {'Freq':>4} {'Games Sampled':>13} {'Status':<30}"
        )
        lines.append("-" * 70)
        for b in prediction.bullpen_order:
            status = "available"
            if not b.get("available", True):
                reason = b.get("unavailability_reason") or "unavailable"
                status = f"(unavailable: {reason})"
            lines.append(
                f"{b['name']:<20} {b['frequency']:>4} "
                f"{b['games_sampled']:>13} {status}"
            )

    if prediction.predicted_starter and prediction.predicted_starter.get("recent_starts"):
        lines.append("")
        lines.append("## Predicted Starter Recent Game Log")
        starter = prediction.predicted_starter
        lines.append(f"Name: {starter['name']}")
        lines.append(
            f"{'Date':<12} {'IP Outs':>7} {'Pitches':>7} "
            f"{'K':>3} {'BB':>3} {'Dec':>3} {'Rest':>4}"
        )
        lines.append("-" * 50)
        for g in starter["recent_starts"]:
            ip = g.get("ip_outs") or 0
            p = g.get("pitches")
            p_str = str(p) if p is not None else "?"
            dec = g.get("decision") or "-"
            rest = g.get("rest_days_from_previous_start")
            rest_str = str(rest) if rest is not None else "-"
            lines.append(
                f"{g['game_date']:<12} {ip:>7} {p_str:>7} "
                f"{g.get('so', 0):>3} {g.get('bb', 0):>3} "
                f"{dec:>3} {rest_str:>4}"
            )

    return "\n".join(lines)


def _build_user_prompt(
    prediction: StarterPrediction,
    pitching_history: list[dict],
    *,
    team_record: str | None = None,
    opponent_record: str | None = None,
) -> str:
    """Build the user prompt with structured data and Tier 1 results."""
    parts: list[str] = []

    # Context
    parts.append("# Pitching Rotation Analysis Request")
    parts.append("")

    if team_record or opponent_record:
        parts.append("## Records")
        if team_record:
            parts.append(f"Scouted team: {team_record}")
        if opponent_record:
            parts.append(f"Our team: {opponent_record}")
        parts.append("")

    # Tier 1 summary
    parts.append("## Deterministic Prediction (Tier 1)")
    parts.append(f"Confidence: {prediction.confidence}")
    parts.append(f"Rotation pattern: {prediction.rotation_pattern}")
    if prediction.predicted_starter:
        parts.append(
            f"Predicted starter: {prediction.predicted_starter['name']} "
            f"(#{prediction.predicted_starter.get('jersey_number') or '?'})"
        )
    if prediction.alternative:
        parts.append(
            f"Alternative: {prediction.alternative['name']} "
            f"(#{prediction.alternative.get('jersey_number') or '?'})"
        )
    if prediction.data_note:
        parts.append(f"Note: {prediction.data_note}")
    parts.append("")

    # Structured data
    parts.append(_format_pitcher_table(prediction))

    # Game count context
    game_ids = set(r["game_id"] for r in pitching_history)
    parts.append(f"\nTotal completed games in season: {len(game_ids)}")

    return "\n".join(parts)


# ── Main enrichment function ────────────────────────────────────────────


def enrich_prediction(
    prediction: StarterPrediction,
    pitching_history: list[dict],
    *,
    team_record: str | None = None,
    opponent_record: str | None = None,
    reference_date: datetime.date | None = None,
) -> EnrichedPrediction:
    """Enrich a Tier 1 prediction with LLM-generated narrative.

    Args:
        prediction: The deterministic ``StarterPrediction`` from Tier 1.
        pitching_history: Raw pitching history rows from
            ``get_pitching_history()``.
        team_record: W-L record of the scouted team (e.g., ``"15-3"``).
        opponent_record: W-L record of our team (e.g., ``"12-6"``).
        reference_date: Anchor date for NSAA rule selection (defaults to
            today if not provided).

    Returns:
        ``EnrichedPrediction`` wrapping the base prediction with narrative.

    Raises:
        LLMError: On API failures or malformed responses.
    """
    if reference_date is None:
        reference_date = datetime.date.today()

    rules = get_nsaa_rules(reference_date)
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        nsaa_rest_table=format_nsaa_rest_table(rules),
    )

    user_prompt = _build_user_prompt(
        prediction, pitching_history,
        team_record=team_record, opponent_record=opponent_record,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    def _invoke(temperature: float) -> dict[str, Any]:
        """Single OpenRouter invocation point for the initial call and retry.

        Both the initial call and the TN-3 retry route through here so they
        share identical kwargs, varying only ``temperature``.  The
        ``response_format={"type": "json_object"}`` constraint (TN-7) is
        applied here so it rides every invocation, including the retry (F-C).
        It is additive/model-dependent -- never assumed sufficient -- so the
        E-233-01 parser and the TN-3 retry remain the model-agnostic baseline;
        the system prompt's JSON instruction is also retained (json_object
        guarantees valid JSON, not the prompt's intended shape).  No ``model``
        kwarg is passed: ``query_openrouter`` owns default-model resolution
        (TN-5), and ``max_tokens`` is left at its 1024 default (F-H).
        """
        return query_openrouter(
            messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )

    def _content_of(resp: dict[str, Any]) -> str:
        """Pull the message ``content`` string out of an OpenRouter envelope.

        Raises ``LLMError`` on a malformed envelope.  This is NOT a JSON parse
        failure, so -- like a transport error -- it must NOT trigger the TN-3
        retry; only ``extract_json_object`` failures are retried.
        """
        try:
            return resp["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected response structure: {exc}") from exc

    # Initial call, then exactly one retry scoped to JSON *extraction* failure
    # (TN-3).  HTTP/transport errors (from ``_invoke``) and malformed-envelope
    # errors (from ``_content_of``) propagate WITHOUT a retry -- only
    # ``extract_json_object`` failures are retried.
    response = _invoke(0.3)
    content = _content_of(response)
    try:
        parsed = extract_json_object(content)
    except LLMError:
        response = _invoke(0.0)
        content = _content_of(response)
        parsed = extract_json_object(content)  # re-raises if still unparseable

    # Domain validation stays here (out of src/llm extraction scope).
    if "narrative" not in parsed:
        raise LLMError(
            "LLM response missing required 'narrative' field"
        )
    narrative = parsed["narrative"]
    if not isinstance(narrative, str):
        raise LLMError("LLM 'narrative' field is not a string")
    if not narrative.strip():
        raise LLMError("LLM 'narrative' field is empty")

    bullpen_sequence = parsed.get("bullpen_sequence")
    if bullpen_sequence is not None and not isinstance(bullpen_sequence, str):
        bullpen_sequence = str(bullpen_sequence)

    # confidence_adjustment is intentionally discarded

    # model_used reflects the model the API actually used (F-A): read from the
    # response body, not env or the shared constant.  Safe fallback if absent.
    model_used = "unknown"
    if isinstance(response, dict):
        model_value = response.get("model")
        if isinstance(model_value, str) and model_value:
            model_used = model_value

    return EnrichedPrediction(
        base=prediction,
        narrative=narrative,
        bullpen_sequence=bullpen_sequence,
        model_used=model_used,
    )
