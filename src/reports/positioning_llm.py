"""Tier 2 LLM enrichment for defensive positioning (E-228-07).

Mirrors :mod:`src.reports.llm_analysis` exactly per epic TN-1: the
deterministic engine decides, the LLM only narrates. The Tier 2 layer
takes a finished :class:`BatterPositioningResult` from Tier 1
(:mod:`src.reports.positioning`) and writes ONLY a one-line rationale
sentence. It never sees raw x/y, never reads ``spray_charts``, and any
LLM opinion on the positioning decision is discarded.

The call sheet must remain fully usable with the LLM layer disabled --
this module returns ``None`` on every error and config-absent path.

Public API::

    from src.reports.positioning_llm import enrich_positioning

    rationale: str | None = enrich_positioning(per_batter_result)
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import TYPE_CHECKING

from src.llm.openrouter import LLMError, is_llm_available, query_openrouter

if TYPE_CHECKING:
    from src.reports.positioning import BatterPositioningResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation thresholds (E-228-07 AC-1 observable contract)
# ---------------------------------------------------------------------------

_MIN_WORDS: int = 10
"""AC-1 (a) lower length bound -- a too-short rationale is treated as a parse
failure and routes to WARNING-and-skip (AC-2a contract)."""

_MAX_WORDS: int = 50
"""AC-1 (a) upper length bound -- a too-long rationale is truncated at the
first in-band sentence boundary."""

_MAX_SENTENCES: int = 2
"""AC-1 (a) sentence-count cap. Truncation prefers full sentences."""


# Zone keywords -- AC-1 (b) structural citation. The render layer's
# vocabulary (POSITIONING_CALL_WORDS) lives in renderer.py; this list
# stays narrowly focused on the citation-evidence terms the prompt can
# emit.
_ZONE_KEYWORDS: frozenset[str] = frozenset({
    "left", "center", "right",
    # Also accept common analyst variants the prompt may surface.
    "lf", "cf", "rf",
})

# Contact-type keywords -- AC-1 (b).
_CONTACT_TYPE_KEYWORDS: frozenset[str] = frozenset({
    "ground ball", "ground-ball", "grounder", "grounders",
    "line drive", "line-drive", "liner", "liners",
    "fly ball", "fly-ball", "flyball",
    "popup", "pop-up", "pop fly",
    "gb", "ld", "fb",
})

# Adjacency lattice ordering of LEFT/RIGHT direction. AC-1 (c) decision
# discipline: if the row is a LEFT* call_state, the rationale must not
# contain "shade right" / "to right" direction-flip phrases (and vice
# versa). Two patterns each side: bare "right"/"left" alone is too broad
# (the citation list accepts "center", which can appear next to a
# direction term), so we look for direction-action phrases.
_LEFT_CONTRADICTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bshade\s+right\b", re.IGNORECASE),
    re.compile(r"\bpulls?\s+right\b", re.IGNORECASE),
    re.compile(r"\bto\s+right\s+field\b", re.IGNORECASE),
)
_RIGHT_CONTRADICTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bshade\s+left\b", re.IGNORECASE),
    re.compile(r"\bpulls?\s+left\b", re.IGNORECASE),
    re.compile(r"\bto\s+left\s+field\b", re.IGNORECASE),
)
_TRUE_CONTRADICTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bshade\s+(?:left|right)\b", re.IGNORECASE),
)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a high school baseball coaching analyst. You analyze ONE batter's \
spray-chart tendencies and produce one short coach-facing rationale that \
explains WHY the deterministic positioning call makes sense for this batter.

You will be given:
1. The deterministic positioning call (already decided -- do not change it).
2. The batter's per-zone batted-ball aggregation (counts per field zone \
and contact type, plus BIP and HR totals).

Respond ONLY with a JSON object (no markdown, no code fences) of the form:
{
  "rationale": "1-2 sentences, 10-50 words. Coach-facing prose explaining \
why the call fits this batter's tendency."
}

Hard rules for the rationale:
- 1-2 sentences. 10-50 words inclusive.
- Reference the data: name a field zone ("left"/"center"/"right") or a \
contact type ("ground ball"/"line drive"/"fly ball") or a specific count \
from the aggregates (BIP total, HR total, or a per-zone count).
- Do NOT contradict the deterministic call. If the call is SHADE LEFT, \
do not say "shade right" or describe pulling to right field. If the call \
is STRAIGHT UP, do not say "shade left" or "shade right".
- No jargon the coach cannot use immediately. No baseball-statistics \
abbreviations like "wOBA" or "ISO". Plain English.
- Do not state the call (the render layer already shows it). Explain the \
tendency.
"""


def _build_user_prompt(result: "BatterPositioningResult") -> str:
    """Build the user prompt with the finished Tier 1 call and aggregation.

    The LLM is fed:
    * the batter's team-state call (full word) and per-position call set;
    * the per-zone aggregation (BIP totals per direction zone and contact
      type), plus ``bip_count`` and ``hr_count``.

    The LLM never sees raw x/y, never sees ``spray_charts`` -- per AC-3.
    """
    from src.reports.renderer import POSITIONING_CALL_WORDS

    # Per-batter context (denormalized across the 6 rows -- pull from row 0).
    first_row = result.per_position_rows[0]
    bip_count = first_row.bip_count
    hr_count = first_row.hr_count
    team_state_word = POSITIONING_CALL_WORDS.get(
        result.team_state_call, result.team_state_call,
    )

    parts: list[str] = []
    parts.append("# Defensive Positioning Rationale Request")
    parts.append("")
    parts.append("## Deterministic positioning call (already decided)")
    parts.append(f"Team-state call: {team_state_word}")
    # Per-position calls -- show the per-position call state to ground the
    # LLM in which positions the engine flagged.
    per_position_lines: list[str] = []
    for row in result.per_position_rows:
        if row.call_state == "TRUE":
            continue
        call_word = POSITIONING_CALL_WORDS.get(row.call_state, row.call_state)
        per_position_lines.append(f"  {row.position}: {call_word}")
    if per_position_lines:
        parts.append("Per-position flagged calls:")
        parts.extend(per_position_lines)
    parts.append("")
    parts.append("## Batter aggregation")
    parts.append(f"Total BIP: {bip_count}")
    parts.append(f"Total HR: {hr_count}")
    parts.append("")
    parts.append("### BIP per field zone")
    zone_totals = result.zone_aggregation.zone_totals
    parts.append(
        f"  left:   {zone_totals.get('left', 0)}"
    )
    parts.append(
        f"  center: {zone_totals.get('center', 0)}"
    )
    parts.append(
        f"  right:  {zone_totals.get('right', 0)}"
    )
    parts.append("")
    parts.append("### BIP per contact type")
    ct_totals = result.zone_aggregation.contact_type_totals
    parts.append(
        f"  ground ball: {ct_totals.get('gb', 0)}"
    )
    parts.append(
        f"  line drive:  {ct_totals.get('ld', 0)}"
    )
    parts.append(
        f"  fly ball:    {ct_totals.get('fb', 0)}"
    )
    parts.append(
        f"  popup:       {ct_totals.get('pu', 0)}"
    )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Response validation (AC-1 observable contract)
# ---------------------------------------------------------------------------


def _count_words(text: str) -> int:
    """Word count -- whitespace tokenization, matches the prompt-side rule."""
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def _split_sentences(text: str) -> list[str]:
    """Split on sentence-ending punctuation. Cheap heuristic, sufficient
    for the 1-2-sentence cap."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _truncate_to_in_band_sentence(text: str) -> str | None:
    """If ``text`` is too long, return the longest prefix of full sentences
    whose word count fits in [_MIN_WORDS, _MAX_WORDS]. Return None when no
    such prefix exists (the caller treats this as discard-and-skip)."""
    sentences = _split_sentences(text)
    if not sentences:
        return None
    # Try 1-sentence prefix; if it fits AND is at least _MIN_WORDS, take it.
    # Otherwise try 2-sentence prefix.
    for n in range(1, min(len(sentences), _MAX_SENTENCES) + 1):
        candidate = " ".join(sentences[:n])
        words = _count_words(candidate)
        if _MIN_WORDS <= words <= _MAX_WORDS:
            return candidate
    return None


def _has_structural_citation(
    text: str,
    result: "BatterPositioningResult",
) -> bool:
    """AC-1 (b): the rationale must contain at least one concrete reference
    drawn from the Tier 1 input (zone, contact-type, or a numeric count)."""
    lowered = text.lower()
    # Zone keywords.
    for kw in _ZONE_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", lowered):
            return True
    # Contact-type keywords.
    for kw in _CONTACT_TYPE_KEYWORDS:
        if kw in lowered:
            return True
    # Numeric figures from the aggregates: bip_count, hr_count, any per-zone
    # or per-contact count.
    first_row = result.per_position_rows[0]
    candidate_numbers = {first_row.bip_count, first_row.hr_count}
    for v in result.zone_aggregation.zone_totals.values():
        candidate_numbers.add(v)
    for v in result.zone_aggregation.contact_type_totals.values():
        candidate_numbers.add(v)
    # Drop 0 as a citation -- 0-counts are noise, not signal.
    candidate_numbers.discard(0)
    for n in candidate_numbers:
        if re.search(rf"\b{n}\b", lowered):
            return True
    return False


def _has_decision_contradiction(
    text: str,
    team_state_call: str,
) -> bool:
    """AC-1 (c): direction-action phrases contradicting the row's
    ``team_state_call`` make the rationale invalid."""
    if team_state_call.startswith("LEFT"):
        return any(p.search(text) for p in _LEFT_CONTRADICTION_PATTERNS)
    if team_state_call.startswith("RIGHT"):
        return any(p.search(text) for p in _RIGHT_CONTRADICTION_PATTERNS)
    if team_state_call == "TRUE":
        return any(p.search(text) for p in _TRUE_CONTRADICTION_PATTERNS)
    # MIXED has no single direction expectation -- no contradiction check.
    return False


def _validate_rationale(
    raw: str,
    result: "BatterPositioningResult",
) -> str | None:
    """Apply the AC-1 (a/b/c) observable contract. Return the
    (possibly truncated) rationale, or ``None`` when validation fails.

    Failure paths log at WARNING (per AC-2a treatment of malformed
    output) so the operator can see why the rationale was skipped.
    """
    text = raw.strip()
    if not text:
        logger.warning("Positioning rationale empty -- skipping.")
        return None

    # AC-1 (a): length gate.
    words = _count_words(text)
    if words < _MIN_WORDS:
        logger.warning(
            "Positioning rationale too short (%d words; min %d) -- skipping. "
            "team_state_call=%s",
            words, _MIN_WORDS, result.team_state_call,
        )
        return None
    if words > _MAX_WORDS:
        # Try to truncate at a sentence boundary.
        truncated = _truncate_to_in_band_sentence(text)
        if truncated is None:
            logger.warning(
                "Positioning rationale too long (%d words; max %d) and no "
                "in-band sentence prefix -- skipping. team_state_call=%s",
                words, _MAX_WORDS, result.team_state_call,
            )
            return None
        text = truncated
    else:
        # Also enforce the sentence cap on in-band output.
        sentences = _split_sentences(text)
        if len(sentences) > _MAX_SENTENCES:
            truncated = _truncate_to_in_band_sentence(text)
            if truncated is None:
                logger.warning(
                    "Positioning rationale exceeds %d sentences with no "
                    "in-band prefix -- skipping. team_state_call=%s",
                    _MAX_SENTENCES, result.team_state_call,
                )
                return None
            text = truncated

    # AC-1 (c): decision discipline -- check BEFORE returning truncated text.
    if _has_decision_contradiction(text, result.team_state_call):
        logger.warning(
            "Positioning rationale contradicts call_state %s -- skipping. "
            "rationale=%r",
            result.team_state_call, text,
        )
        return None

    # AC-1 (b): structural citation.
    if not _has_structural_citation(text, result):
        logger.warning(
            "Positioning rationale lacks structural citation (no zone, "
            "contact-type, or aggregate count) -- skipping. team_state_call=%s",
            result.team_state_call,
        )
        return None

    return text


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def enrich_positioning(
    result: "BatterPositioningResult",
) -> str | None:
    """Tier 2 LLM-written rationale for a per-batter positioning result.

    Mirrors :func:`src.reports.llm_analysis.enrich_prediction`:

    * If :func:`src.llm.openrouter.is_llm_available` returns ``False``,
      return ``None`` with an **INFO** log (AC-2). Expected config state,
      not an error.
    * If the LLM call raises :class:`src.llm.openrouter.LLMError` (or any
      other exception) mid-request, return ``None`` with a **WARNING** log
      (AC-2a). Non-fatal -- the call sheet must remain fully usable.
    * The Tier 2 layer never sees raw x/y, never reads ``spray_charts``,
      and discards any LLM opinion on the positioning decision (AC-3).

    Args:
        result: The :class:`BatterPositioningResult` for one batter from
            :func:`src.reports.positioning.compute_positioning`.

    Returns:
        The validated rationale string (1-2 sentences, 10-50 words,
        cites concrete Tier 1 input, does not contradict the call) when
        the call succeeds and the response passes AC-1; otherwise
        ``None``.
    """
    if not is_llm_available():
        logger.info(
            "Tier 2 LLM unavailable (OPENROUTER_API_KEY not set) -- "
            "positioning rationale skipped for player_id=%s.",
            result.player_id,
        )
        return None

    # MIXED batters get a rationale too (they still need explanation), but
    # TRUE batters do not need one -- the dot grid carries the message.
    # The render layer simply ignores a None rationale.
    if result.team_state_call == "TRUE":
        return None

    model = os.environ.get(
        "OPENROUTER_MODEL", "anthropic/claude-haiku-4-5-20251001",
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(result)},
    ]

    try:
        response = query_openrouter(
            messages, model=model, max_tokens=200, temperature=0.3,
        )
    except LLMError as exc:
        logger.warning(
            "Tier 2 LLM call failed for player_id=%s: %s. Continuing without rationale.",
            result.player_id, exc, exc_info=True,
        )
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Tier 2 LLM unexpected error for player_id=%s: %s. "
            "Continuing without rationale.",
            result.player_id, exc, exc_info=True,
        )
        return None

    # Parse the response. Any parse failure routes to WARNING-and-skip
    # (AC-2a) -- the LLM was reachable but returned something unusable.
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning(
            "Tier 2 LLM response structure unexpected for player_id=%s: %s. "
            "Skipping rationale.",
            result.player_id, exc,
        )
        return None

    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning(
            "Tier 2 LLM response is not valid JSON for player_id=%s: %s. "
            "Skipping rationale.",
            result.player_id, exc,
        )
        return None

    raw = parsed.get("rationale") if isinstance(parsed, dict) else None
    if not isinstance(raw, str):
        logger.warning(
            "Tier 2 LLM response missing/non-string 'rationale' for "
            "player_id=%s. Skipping.",
            result.player_id,
        )
        return None

    # Any LLM opinion on the decision itself is discarded -- AC-3, mirrors
    # `enrich_prediction`'s confidence_adjustment discard. The response
    # schema does not even expose a decision-adjustment field; any extra
    # fields parsed are simply not read.

    return _validate_rationale(raw, result)
