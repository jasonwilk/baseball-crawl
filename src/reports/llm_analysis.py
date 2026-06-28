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
from src.reports.starter_prediction import StarterPrediction

logger = logging.getLogger(__name__)


@dataclass
class EnrichedPrediction:
    """Tier 2 enrichment wrapping the Tier 1 ``StarterPrediction``."""

    base: StarterPrediction
    narrative: str
    bullpen_sequence: str | None
    model_used: str


# ── Prompt construction ─────────────────────────────────────────────────

# REQUIRED POST-MERGE MANUAL STEP (E-243-04 AC-6b): live-model output is not
# deterministically unit-testable.  After merge, generate a sample youth/travel
# report (is_estimate=True) with OPENROUTER_API_KEY set and confirm the rendered
# narrative contains NONE of: "Pitch Smart", "Legion", "USA Baseball",
# "soft prior".  The deterministic prompt-construction surface is covered by the
# unit tests in tests/test_llm_analysis.py (TestEstimateAndNoJargon).
#
# Validated "Variant A" bench-briefing prompt (E-243-04 / bake-off winner;
# google/gemini-2.5-flash-lite scored 16/16).  Source of truth, reproduced
# verbatim from epics/E-243-probable-starter-usefulness/E-243-04-narration-
# prompt.md.  The JSON OUTPUT block below is the unchanged response contract
# (the deterministic parser + response_format hardening require a JSON
# envelope); the narration substance above it is Variant A as-validated.
# This string has no .format() placeholders -- the literal JSON braces are
# intentional and must not be doubled.
_SYSTEM_PROMPT_TEMPLATE = """\
You are a baseball scout writing a brief bench briefing for a high school coach preparing for today's game. The ranked pitching data has already been computed for you — your job is to narrate it in 2-4 sentences of plain English prose.

STRUCTURE (follow this order):
1. Lead with the single most-likely arm by name and the concrete reason — how many days of rest they have, or how many pitches they threw and when. One name. One reason. First sentence.
2. Mention the next 1-2 likely arms if they appear in the data, with their rest situation.
3. Name anyone who is unavailable today and state why in plain English (e.g., "threw 72 pitches four days ago and needs one more day").
4. If the data is flagged as a pitch-count estimate, say so plainly in one phrase (e.g., "rest eligibility is estimated — their league rules aren't on file").

HARD RULES:
— Always name a specific pitcher in your first sentence. Never open with uncertainty, ambiguity, or a description of the situation.
— The ranked order in the data is correct. Do not reorder, reverse, or qualify the ranking. Do not present the #2 arm as more likely than #1.
— 2-4 sentences total. No bullet lists. Flowing prose only.
— Never use these words or phrases: "committee situation," "committee," "Pitch Smart," "Legion," "WHIP," "FIP," or any phrase that amounts to refusing to name a likely starter.
— "Days of rest" and "threw X pitches N days ago" are fine. Rule-set names and advanced stats are not.
— A discounted arm (eligible but on short rest) is still a real candidate — mention it, but as secondary to a fully-rested arm.

Respond ONLY with a JSON object (no markdown, no code fences):
{"narrative": "<your 2-4 sentence briefing as a single prose string>", "bullpen_sequence": null}
"""


def _availability_label(eligibility: str | None, *, only_eligible: bool) -> str:
    """Translate the two-valued rest eligibility into the validated phrasing."""
    if eligibility == "available":
        label = "fully rested"
    else:
        label = "eligible but on short rest"
    if only_eligible:
        label += " (only eligible arm today)"
    return label


def _pitch_display(candidate: dict) -> str:
    """Render a ranked arm's most-recent pitch load, with no decimal IP (AC-8).

    Real pitch count -> ``"{N} pitches"``.  Null/IP-proxy case (E-243-01 M1) ->
    a non-numeric estimate phrase, since the engine output carries no innings
    field to derive a count and AC-8 forbids introducing one.
    """
    pitches = candidate.get("last_outing_pitches")
    if pitches is not None:
        return f"{pitches} pitches"
    return "an estimated recent workload (pitch count not on file)"


def _format_pitcher_table(prediction: StarterPrediction) -> str:
    """Format the ranked-arms data block (validated Variant A shape).

    Surfaces pitch count only -- no decimal IP field (AC-8).  Consumes the
    enriched candidate fields from E-243-03 (days_rest, rest_eligibility,
    games_started, total_team_games) and the additive unavailable_arms output.
    """
    lines: list[str] = []

    candidates = prediction.top_candidates
    only_eligible = len(candidates) == 1
    lines.append("MOST LIKELY ARMS TODAY:")
    for i, c in enumerate(candidates, start=1):
        jersey = c.get("jersey_number") or "?"
        days_rest = c.get("days_rest")
        rest_str = (
            f"{days_rest} days rest" if days_rest is not None else "rest unknown"
        )
        label = _availability_label(
            c.get("rest_eligibility"),
            only_eligible=only_eligible and i == 1,
        )
        # days_since equals days_rest for the ranked line (verbatim spec).
        days_since_str = (
            f"{days_rest} days ago" if days_rest is not None else "recently"
        )
        gs = c.get("games_started")
        tg = c.get("total_team_games")
        if gs is not None and tg:
            starts_str = f"{gs} of {tg} starts this season"
        else:
            starts_str = f"{gs} starts this season"
        lines.append(
            f"{i}. {c['name']} (#{jersey}) — {rest_str}, {label} | "
            f"{_pitch_display(c)} {days_since_str} | {starts_str}"
        )

    if prediction.unavailable_arms:
        lines.append("")
        lines.append("UNAVAILABLE TODAY:")
        for arm in prediction.unavailable_arms:
            lines.append(f"- {arm['name']}: {arm['reason']}")

    # Preserve the top arm's recent game log with its INTEGER "IP Outs" column
    # (AC-8 guard: do not strip it, do not add a decimal IP field).
    if prediction.predicted_starter and prediction.predicted_starter.get("recent_starts"):
        starter = prediction.predicted_starter
        lines.append("")
        lines.append(f"## Most Recent Game Log — {starter['name']}")
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
    team_name: str | None = None,
    team_record: str | None = None,
    opponent_record: str | None = None,
) -> str:
    """Build the Variant A user/data block.

    ``team_record``/``opponent_record`` are accepted for call-site
    compatibility but intentionally unused: the validated Variant A block drops
    the records section (the "elevate the ace for big games" guideline is gone).
    The estimate NOTE is emitted from ``prediction.is_estimate`` (E-243-02), in
    jargon-free consequence framing (no brand/rule-set names reach the prose).
    """
    parts: list[str] = []

    parts.append(f"OPPONENT: {team_name}" if team_name else "OPPONENT: this opponent")
    parts.append("")
    parts.append(_format_pitcher_table(prediction))

    if prediction.is_estimate:
        parts.append("")
        parts.append(
            "NOTE: This opponent's league pitch rules are not on file. The rest "
            "eligibility above is a standard pitch-count estimate — the actual "
            "rules may differ, so treat borderline calls as approximate."
        )

    parts.append("")
    parts.append("Write a 2-4 sentence briefing for the coach now.")

    return "\n".join(parts)


# ── Main enrichment function ────────────────────────────────────────────


def enrich_prediction(
    prediction: StarterPrediction,
    pitching_history: list[dict],
    *,
    team_name: str | None = None,
    team_record: str | None = None,
    opponent_record: str | None = None,
    reference_date: datetime.date | None = None,
) -> EnrichedPrediction:
    """Enrich a Tier 1 prediction with LLM-generated narrative.

    Args:
        prediction: The deterministic ``StarterPrediction`` from Tier 1.
        pitching_history: Raw pitching history rows from
            ``get_pitching_history()``.
        team_name: Opponent team name for the data-block header (optional).
        team_record: W-L record of the scouted team.  Accepted for call-site
            compatibility; the validated Variant A prompt does not use records.
        opponent_record: W-L record of our team.  Same compatibility note.
        reference_date: Accepted for call-site compatibility; the Variant A
            prompt is self-contained and no longer injects an NSAA rest table.

    Returns:
        ``EnrichedPrediction`` wrapping the base prediction with narrative.

    Raises:
        LLMError: On API failures or malformed responses.
    """
    system_prompt = _SYSTEM_PROMPT_TEMPLATE

    user_prompt = _build_user_prompt(
        prediction, pitching_history,
        team_name=team_name,
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
    # Temperature 0.0 for deterministic narration (E-243-04 AC-7c); the retry
    # is already 0.0.  Temperature is NOT env-controlled.
    response = _invoke(0.0)
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
