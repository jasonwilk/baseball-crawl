"""LLM-enriched matchup analysis (Tier 2).

Builds a prompt from a deterministic ``MatchupAnalysis`` (engine output) plus
the underlying ``MatchupInputs`` grounding tables, calls OpenRouter, and parses
the response into an :class:`EnrichedMatchup` dataclass.

This module mirrors :mod:`src.reports.llm_analysis` exactly:

- The system prompt is a module-level template constant that instructs the
  model to lead with a recommendation, embed inline parenthetical citations
  for every prescriptive claim, and never invent statistics, names, or
  results not present in the structured grounding tables.
- The user prompt renders the inputs as ASCII tables (top-3 hitters,
  pull-tendency rows, stolen-base profile, first-inning pattern, 3-bucket
  loss recipe, eligible opposing pitchers, eligible LSB pitchers when
  present) plus the engine's deterministic signals (cue_kind per hitter,
  bucket counts, summaries) so the narrative cannot contradict the
  deterministic core.
- The OpenRouter call uses ``model = os.environ.get("OPENROUTER_MODEL",
  "anthropic/claude-haiku-4-5-20251001")``, ``max_tokens=1500``,
  ``temperature=0.3``, single-pass JSON.
- Failure modes (timeout, network error, malformed JSON, missing or
  wrong-typed required fields) raise :class:`~src.llm.openrouter.LLMError`.

Hallucination guardrail: every ``hitter_cues[i].player_id`` returned by the
LLM must round-trip to one of ``inputs.opponent_top_hitters[*].player_id``.
When ``FEATURE_MATCHUP_STRICT=1`` is set, an offender raises ``LLMError``;
when unset, the offender is filtered while the rest of the response is
preserved.

Pull-tendency notes are NOT in the LLM output schema -- they are deterministic
engine output (per E-228-12 AC-7) formatted by the renderer (E-228-14)
directly from raw ``PullTendencyNote`` fields.

The wrapper does NOT re-check ``FEATURE_MATCHUP_ANALYSIS`` -- the caller (the
report generator in E-228-14) gates on :func:`src.reports.matchup.is_matchup_enabled`
before invoking ``enrich_matchup``.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from src.llm.openrouter import LLMError, query_openrouter
from src.reports.matchup import (
    EligiblePitcher,
    MatchupAnalysis,
    MatchupInputs,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------


@dataclass
class HitterCue:
    """A single LLM-authored coaching cue for one top-3 hitter.

    ``player_id`` is the round-trip identifier the wrapper validates
    against ``inputs.opponent_top_hitters[*].player_id``.  ``cue`` is the
    LLM-authored prose (1-2 sentences, with inline parenthetical citations
    embedded by the LLM).
    """

    player_id: str
    cue: str


@dataclass
class EnrichedMatchup:
    """Tier 2 enrichment wrapping the Tier 1 :class:`MatchupAnalysis`.

    Composition (not inheritance) -- mirrors :class:`EnrichedPrediction`
    in :mod:`src.reports.llm_analysis`.  ``analysis`` is the original
    deterministic ``MatchupAnalysis``; the LLM-authored prose fields are
    appended.  Pull-tendency notes are NOT here -- they live on the
    underlying ``analysis.pull_tendency_notes`` and are formatted
    directly by the renderer.
    """

    analysis: MatchupAnalysis
    game_plan_intro: str
    hitter_cues: list[HitterCue] = field(default_factory=list)
    sb_profile_prose: str = ""
    first_inning_prose: str = ""
    loss_recipe_prose: str = ""
    model_used: str = ""


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = """\
You are a high school baseball coaching analyst producing matchup-strategy \
intelligence. Lead with the recommendation, support with evidence in \
parenthetical. Direct, decisive, conclusion-first.

For every prescriptive claim about a hitter or a pitcher, embed an inline \
parenthetical citing the supporting data point (e.g., "attack early in the \
count (62% first-pitch swing, 4% BB)").

Do NOT invent statistics, names, or game results not present in the \
structured data above. Use only the player names, IDs, and counts shown in \
the grounding tables. If a tendency is unsupported by the data, say so or \
omit it.

Respond ONLY with a JSON object (no markdown, no code fences) containing:
{
  "game_plan_intro": "1-2 sentences setting the table for the matchup",
  "hitter_cues": [
    {"player_id": "<one of the top-3 player_ids>", "cue": "1-2 sentences \
with inline parenthetical citation(s)"}
  ],
  "sb_profile_prose": "1-2 sentences on stolen-base risk, with inline citation",
  "first_inning_prose": "1-2 sentences on first-inning tendencies, with \
inline citation",
  "loss_recipe_prose": "2-3 sentences summarizing what the bucket pattern \
reveals, with inline citations"
}

Constraints:
- Output exactly one ``hitter_cues`` entry per top-3 hitter, in the same \
order they appear in the grounding table.
- ``player_id`` MUST exactly match one of the IDs in the top-3 hitters \
table.  Names alone are insufficient.
- Pull-tendency notes are deterministic and rendered separately -- do NOT \
include any pull-tendency prose in this JSON payload.
"""


def _format_hitter_table(inputs: MatchupInputs, analysis: MatchupAnalysis) -> str:
    """Render the top-3 hitters as an ASCII table with cue_kind annotations."""
    lines: list[str] = []
    lines.append("## Top-3 Opposing Hitters (engine ranked by OPS)")
    if not analysis.threat_list:
        lines.append("(none qualified -- insufficient PA across opposing roster)")
        return "\n".join(lines)
    lines.append(
        f"{'PlayerID':<14} {'Name':<22} {'#':>3} {'PA':>4} {'OBP':>5} "
        f"{'SLG':>5} {'BB%':>5} {'K%':>5} {'FPS%':>5} {'Chase%':>6} "
        f"{'CueKind':<14}"
    )
    lines.append("-" * 110)
    for t in analysis.threat_list:
        jersey = t.jersey_number or "?"
        lines.append(
            f"{t.player_id:<14} {t.name:<22} {jersey:>3} {t.pa:>4} "
            f"{t.obp:>5.3f} {t.slg:>5.3f} "
            f"{t.bb_pct * 100:>4.1f}% {t.k_pct * 100:>4.1f}% "
            f"{t.fps_swing_rate * 100:>4.1f}% {t.chase_rate * 100:>5.1f}% "
            f"{t.cue_kind:<14}"
        )
    # Per-hitter swing-rate-by-count breakdown.
    for t in analysis.threat_list:
        if t.swing_rate_by_count:
            lines.append(
                f"  {t.name} swing-rate by count: "
                + ", ".join(
                    f"{k}={v * 100:.0f}%"
                    for k, v in sorted(t.swing_rate_by_count.items())
                )
            )
    # Supporting stats summaries (engine-emitted).
    for t in analysis.threat_list:
        if t.supporting_stats:
            lines.append(f"  {t.name} supporting: {', '.join(t.supporting_stats)}")
    return "\n".join(lines)


def _format_pull_tendency_table(analysis: MatchupAnalysis) -> str:
    """Render pull-tendency rows for grounding (LLM does NOT prose these)."""
    lines: list[str] = []
    lines.append("## Pull-Tendency Notes (deterministic; for context only)")
    if not analysis.pull_tendency_notes:
        lines.append("(none qualified -- threshold pull_pct >= 55% on >= 10 BIP)")
        return "\n".join(lines)
    lines.append(f"{'Name':<22} {'#':>3} {'Pull%':>6} {'BIP':>4}")
    lines.append("-" * 40)
    for n in analysis.pull_tendency_notes:
        jersey = n.jersey_number or "?"
        lines.append(
            f"{n.name:<22} {jersey:>3} {n.pull_pct * 100:>5.1f}% {n.bip_count:>4}"
        )
    lines.append(
        "(Renderer will format the prose; do not include pull-tendency prose "
        "in your JSON output.)"
    )
    return "\n".join(lines)


def _format_sb_profile(inputs: MatchupInputs, analysis: MatchupAnalysis) -> str:
    """Render the stolen-base profile as raw inputs + engine summary.

    Two distinct sub-blocks per AC-4: the raw input dict from
    ``inputs.opponent_sb_profile`` (grounding) and the engine's
    deterministic ``analysis.sb_profile_summary`` (post-engine fact the
    LLM must respect, not contradict).
    """
    lines: list[str] = []
    lines.append("## Stolen-Base Profile (opponent perspective)")
    sb = inputs.opponent_sb_profile or {}
    lines.append("### Raw input")
    if not sb:
        lines.append("(no SB data on file)")
    else:
        # Mirrors the keys produced by ``get_sb_tendency`` in src/api/db.py.
        for key in (
            "sb_attempts",
            "sb_successes",
            "sb_success_rate",
            "catcher_cs_against_attempts",
            "catcher_cs_against_count",
            "catcher_cs_against_rate",
        ):
            if key in sb and sb[key] is not None:
                lines.append(f"{key}: {sb[key]}")
    lines.append("### Engine summary (deterministic; do not contradict)")
    sb_sum = analysis.sb_profile_summary or {}
    if not sb_sum:
        lines.append("(engine produced no summary)")
    else:
        for key, value in sorted(sb_sum.items()):
            if value is None:
                continue
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _format_first_inning(inputs: MatchupInputs, analysis: MatchupAnalysis) -> str:
    """Render the first-inning pattern as raw inputs + engine summary.

    Two distinct sub-blocks per AC-4: the raw input dict from
    ``inputs.opponent_first_inning_pattern`` (grounding) and the engine's
    deterministic ``analysis.first_inning_summary`` (post-engine fact the
    LLM must respect, not contradict).
    """
    lines: list[str] = []
    lines.append("## First-Inning Pattern (opponent perspective)")
    fi = inputs.opponent_first_inning_pattern or {}
    lines.append("### Raw input")
    if not fi:
        lines.append("(no first-inning data on file)")
    else:
        # Mirrors the keys produced by ``get_first_inning_pattern`` in
        # src/api/db.py.
        for key in (
            "games_played",
            "games_with_first_inning_runs_scored",
            "games_with_first_inning_runs_allowed",
            "first_inning_scored_rate",
            "first_inning_allowed_rate",
        ):
            if key in fi and fi[key] is not None:
                lines.append(f"{key}: {fi[key]}")
    lines.append("### Engine summary (deterministic; do not contradict)")
    fi_sum = analysis.first_inning_summary or {}
    if not fi_sum:
        lines.append("(engine produced no summary)")
    else:
        for key, value in sorted(fi_sum.items()):
            if value is None:
                continue
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _format_loss_recipe(analysis: MatchupAnalysis) -> str:
    """Render the 3-bucket loss recipe with grounding tuples."""
    lines: list[str] = []
    recipe = analysis.loss_recipe_buckets
    lines.append("## Loss Recipe (3 buckets + uncategorized)")
    lines.append(f"Total losses: {recipe.total_losses}")
    lines.append(f"Uncategorized: {recipe.uncategorized_count}")

    def _emit_bucket(label: str, bucket) -> None:
        lines.append(f"### {label}: {bucket.count} loss(es)")
        if not bucket.grounding:
            return
        lines.append(
            f"  {'Date':<12} {'OppScore':>8} {'OurScore':>8} "
            f"{'Starter':<22} {'KeyStat':<30}"
        )
        for g in bucket.grounding:
            date, opp_score, our_score, starter, key_stat = g
            lines.append(
                f"  {date or '?':<12} "
                f"{(opp_score if opp_score is not None else '?'):>8} "
                f"{(our_score if our_score is not None else '?'):>8} "
                f"{(starter or '?'):<22} {(key_stat or '?'):<30}"
            )

    _emit_bucket("Starter shelled early", recipe.starter_shelled_early)
    _emit_bucket("Bullpen couldn't hold", recipe.bullpen_couldnt_hold)
    _emit_bucket("Close game lost late", recipe.close_game_lost_late)
    return "\n".join(lines)


def _format_pitcher_block(label: str, pitchers: list[EligiblePitcher] | None) -> str:
    """Render an eligible-pitcher list for either side."""
    lines: list[str] = []
    lines.append(f"## {label}")
    if not pitchers:
        lines.append("(none eligible)")
        return "\n".join(lines)
    lines.append(
        f"{'PlayerID':<14} {'Name':<22} {'#':>3} {'LastOut':>10} "
        f"{'Rest':>5} {'LastP':>6} {'7dPit':>6}"
    )
    lines.append("-" * 75)
    for p in pitchers:
        jersey = p.jersey_number or "?"
        last = p.last_outing_date or "?"
        rest = p.days_rest if p.days_rest is not None else "?"
        last_p = p.last_outing_pitches if p.last_outing_pitches is not None else "?"
        wl = p.workload_7d if p.workload_7d is not None else "?"
        lines.append(
            f"{p.player_id:<14} {p.name:<22} {jersey:>3} {last:>10} "
            f"{str(rest):>5} {str(last_p):>6} {str(wl):>6}"
        )
    return "\n".join(lines)


def _build_user_prompt(
    analysis: MatchupAnalysis,
    inputs: MatchupInputs,
) -> str:
    """Build the user prompt from the engine output + grounding inputs."""
    parts: list[str] = []
    parts.append("# Matchup Strategy Request")
    parts.append("")

    opp_name = (inputs.opponent_team or {}).get("name", "Unknown Team")
    parts.append(f"Opponent: {opp_name}")
    parts.append(f"Reference date: {inputs.reference_date.isoformat()}")
    parts.append(f"Season: {inputs.season_id}")
    parts.append(f"Engine confidence: {analysis.confidence}")
    parts.append("")

    parts.append(_format_hitter_table(inputs, analysis))
    parts.append("")
    parts.append(_format_pull_tendency_table(analysis))
    parts.append("")
    parts.append(_format_sb_profile(inputs, analysis))
    parts.append("")
    parts.append(_format_first_inning(inputs, analysis))
    parts.append("")
    parts.append(_format_loss_recipe(analysis))
    parts.append("")
    parts.append(_format_pitcher_block(
        "Eligible Opposing Pitchers", analysis.eligible_opposing_pitchers,
    ))
    parts.append("")
    if analysis.eligible_lsb_pitchers is not None:
        parts.append(_format_pitcher_block(
            "Eligible LSB Pitchers", analysis.eligible_lsb_pitchers,
        ))
        parts.append("")

    if analysis.data_notes:
        parts.append("## Data Thinness Notes (engine-emitted)")
        for n in analysis.data_notes:
            parts.append(f"- [{n.subsection}] {n.message}")
        parts.append("")

    parts.append("Produce the JSON payload now.")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Helpers: parsing + guardrail
# ---------------------------------------------------------------------------


def _is_strict_mode() -> bool:
    """Return True when ``FEATURE_MATCHUP_STRICT=1`` (or truthy)."""
    return os.environ.get("FEATURE_MATCHUP_STRICT", "").lower() in (
        "1", "true", "yes",
    )


def _validate_payload(parsed: Any) -> dict[str, Any]:
    """Validate the LLM JSON payload's required fields and types.

    Raises:
        LLMError: If a required field is missing or has the wrong type.
    """
    if not isinstance(parsed, dict):
        raise LLMError("LLM response is not a JSON object")

    required_string_fields = (
        "game_plan_intro",
        "sb_profile_prose",
        "first_inning_prose",
        "loss_recipe_prose",
    )
    for fname in required_string_fields:
        if fname not in parsed:
            raise LLMError(f"LLM response missing required '{fname}' field")
        if not isinstance(parsed[fname], str):
            raise LLMError(f"LLM '{fname}' field is not a string")

    if "hitter_cues" not in parsed:
        raise LLMError("LLM response missing required 'hitter_cues' field")
    if not isinstance(parsed["hitter_cues"], list):
        raise LLMError("LLM 'hitter_cues' field is not a list")
    for i, entry in enumerate(parsed["hitter_cues"]):
        if not isinstance(entry, dict):
            raise LLMError(f"hitter_cues[{i}] is not an object")
        if "player_id" not in entry or not isinstance(entry["player_id"], str):
            raise LLMError(f"hitter_cues[{i}] missing/invalid 'player_id'")
        if "cue" not in entry or not isinstance(entry["cue"], str):
            raise LLMError(f"hitter_cues[{i}] missing/invalid 'cue'")
    return parsed


def _apply_hallucination_guardrail(
    cues: list[dict[str, Any]],
    inputs: MatchupInputs,
) -> list[HitterCue]:
    """Round-trip ``player_id`` against the inputs.

    Strict mode (``FEATURE_MATCHUP_STRICT=1``) raises on any offender.
    Graceful mode filters offenders and preserves the rest.
    """
    valid_ids = {
        str(h.get("player_id"))
        for h in inputs.opponent_top_hitters
        if h.get("player_id")
    }
    strict = _is_strict_mode()
    accepted: list[HitterCue] = []
    for entry in cues:
        pid = entry["player_id"]
        if pid not in valid_ids:
            if strict:
                raise LLMError(
                    f"Hallucinated hitter_cues player_id={pid!r} not in "
                    f"inputs.opponent_top_hitters (strict mode)"
                )
            logger.warning(
                "Filtering hallucinated hitter_cues entry: player_id=%r not "
                "in opponent_top_hitters",
                pid,
            )
            continue
        accepted.append(HitterCue(player_id=pid, cue=entry["cue"]))
    return accepted


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def enrich_matchup(
    analysis: MatchupAnalysis,
    inputs: MatchupInputs,
    *,
    client: Any = None,
) -> EnrichedMatchup:
    """Enrich a deterministic ``MatchupAnalysis`` with LLM-authored prose.

    Wrapper signature ``(analysis, inputs)`` -- both are needed: ``inputs``
    supplies the grounding tables for the prompt; ``analysis`` supplies the
    deterministic structure (cue kinds, bucket counts, summaries) the LLM
    must respect.

    Args:
        analysis: The Tier 1 ``MatchupAnalysis`` from
            :func:`src.reports.matchup.compute_matchup`.
        inputs: The ``MatchupInputs`` bundle that produced ``analysis``,
            used to render the prompt's grounding ASCII tables.
        client: Optional override for ``query_openrouter``.  When ``None``,
            the module-level :func:`src.llm.openrouter.query_openrouter`
            is used.  Tests inject a callable here OR (preferred) patch
            ``src.reports.llm_matchup.query_openrouter``.

    Returns:
        An :class:`EnrichedMatchup` carrying the original ``analysis``
        plus the LLM-authored narrative fields (``game_plan_intro``,
        ``hitter_cues`` per top-3 hitter, ``sb_profile_prose``,
        ``first_inning_prose``, ``loss_recipe_prose``).

    Behavior:
        - **Suppress short-circuit** -- when ``analysis.confidence ==
          "suppress"``, OpenRouter is NOT called and the function returns
          an :class:`EnrichedMatchup` with empty narrative fields.  The
          caller (renderer) hides the section in this case.
        - **Hallucination guardrail** -- every returned
          ``hitter_cues[i].player_id`` is validated against
          ``inputs.opponent_top_hitters[*].player_id``.  When
          ``FEATURE_MATCHUP_STRICT=1`` is set, any offender raises
          :class:`LLMError`.  When unset (default), the offender is
          filtered while the rest of the response is preserved.
        - **Feature flag** -- this wrapper does NOT re-check
          ``FEATURE_MATCHUP_ANALYSIS``; the caller (the report generator)
          gates on :func:`src.reports.matchup.is_matchup_enabled` before
          invoking ``enrich_matchup``.

    Raises:
        LLMError: On OpenRouter failures (timeout, network error, HTTP
            error), malformed JSON, missing or wrong-typed required
            fields, or -- in strict mode -- a hallucinated ``player_id``
            that doesn't round-trip against ``inputs.opponent_top_hitters``.

    See ``epics/E-228-matchup-strategy-report/E-228-13.md`` for the full AC
    list and ``src/reports/llm_analysis.py`` for the architectural mirror.
    """
    model = os.environ.get(
        "OPENROUTER_MODEL", "anthropic/claude-haiku-4-5-20251001",
    )

    # AC-2: suppress short-circuit -- return empty narrative without an
    # OpenRouter call.
    if analysis.confidence == "suppress":
        return EnrichedMatchup(
            analysis=analysis,
            game_plan_intro="",
            hitter_cues=[],
            sb_profile_prose="",
            first_inning_prose="",
            loss_recipe_prose="",
            model_used=model,
        )

    user_prompt = _build_user_prompt(analysis, inputs)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    qr = client if client is not None else query_openrouter
    response = qr(messages, model=model, max_tokens=1500, temperature=0.3)

    # Extract content from OpenRouter response.
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Unexpected response structure: {exc}") from exc

    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise LLMError(f"LLM response is not valid JSON: {exc}") from exc

    payload = _validate_payload(parsed)
    cues = _apply_hallucination_guardrail(payload["hitter_cues"], inputs)

    return EnrichedMatchup(
        analysis=analysis,
        game_plan_intro=payload["game_plan_intro"],
        hitter_cues=cues,
        sb_profile_prose=payload["sb_profile_prose"],
        first_inning_prose=payload["first_inning_prose"],
        loss_recipe_prose=payload["loss_recipe_prose"],
        model_used=model,
    )
