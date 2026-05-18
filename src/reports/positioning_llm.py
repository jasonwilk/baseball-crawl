"""Tier 2 LLM input contract for E-229 defensive positioning.

Per epic TN-2 (single-source provenance): the deterministic engine
(:mod:`src.reports.positioning`) decides; this module narrates. The
Tier 2 layer takes one flagged batter's per-position row plus the
matching team-aggregate row and emits a one-line rationale that
references the zone vocabulary (A-H) or the underlying deviation
signs.

**No DB persistence** (per Phase 3 iteration 1 CR B1 lock):
rationales are render-time in-memory only. There is no ``rationale``
column on ``batter_positioning``; this module issues no
``INSERT``/``UPDATE`` against ``batter_positioning`` or
``team_position_aggregate``. The bundle assembler (E-229-08) calls
:func:`generate_rationale` per flagged batter at render time and
threads the result directly into the template context.

Public API::

    from src.reports.positioning_llm import generate_rationale

    rationale: str | None = generate_rationale(
        batter_row, aggregate_row, batter_metadata,
    )

The bundle and call sheet must remain fully usable with the LLM
layer disabled -- this module returns ``None`` on every error,
config-absent, and validation-failure path.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

from src.llm.openrouter import LLMError, is_llm_available, query_openrouter
from src.reports.positioning import PerPositionRow, TeamAggregateRow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation thresholds (AC-2 observable contract)
# ---------------------------------------------------------------------------

_MIN_WORDS: int = 10
_MAX_WORDS: int = 50
_MAX_SENTENCES: int = 2


# ---------------------------------------------------------------------------
# Zone vocabulary (epic TN-3 sign-rule table)
#
# Each zone letter encodes the SIGN of (direction_deviation,
# depth_deviation). The vertical band (D, E) has no left/right
# component; the horizontal band (B, G) has no in/deep component.
#
# left_sign  = -1 for A/B/C (left), 0 for D/E (vertical), +1 for F/G/H
# in_sign    = -1 for A/D/F (in), 0 for B/G (horizontal), +1 for C/E/H
# ---------------------------------------------------------------------------

_ZONE_HORIZONTAL_SIGN: dict[str, int] = {
    "A": -1, "B": -1, "C": -1,  # left
    "D":  0, "E":  0,            # vertical (no horizontal lean)
    "F":  1, "G":  1, "H":  1,  # right
}
_ZONE_VERTICAL_SIGN: dict[str, int] = {
    "A": -1, "D": -1, "F": -1,  # in
    "B":  0, "G":  0,            # horizontal (no vertical lean)
    "C":  1, "E":  1, "H":  1,  # deep
}


# ---------------------------------------------------------------------------
# Structural-citation vocabulary (AC-2 b)
# ---------------------------------------------------------------------------

# Zone keywords -- any letter A-H, OR the long-form zone names ("in-left",
# "deep", etc.). Case-insensitive. The regex matches "Zone B" / "zone b"
# as a phrase and also accepts the long-form vocabulary that the
# COMPASS_LEGEND_LONG legend exposes ("in-left", "deep-right", etc.).
_ZONE_LETTER_PATTERN: re.Pattern[str] = re.compile(
    r"\bzone\s+[A-H]\b", re.IGNORECASE,
)
_ZONE_LONGFORM_KEYWORDS: frozenset[str] = frozenset({
    "in-left", "left", "deep-left",
    "in", "deep",
    "in-right", "right", "deep-right",
})

# Contact-type / pitching-context keywords. Kept narrow -- the engine
# input does not carry contact type, but the LLM may still reference
# coaching-vocabulary phrases like "ground ball" if the operator wants
# them in the prompt template.
_CONTACT_TYPE_KEYWORDS: frozenset[str] = frozenset({
    "ground ball", "ground-ball", "grounder", "grounders",
    "line drive", "line-drive", "liner", "liners",
    "fly ball", "fly-ball", "flyball",
    "popup", "pop-up", "pop fly",
})


# ---------------------------------------------------------------------------
# Decision-discipline patterns (AC-2 c)
#
# When the batter's zone_id is in the LEFT half (A/B/C) -- or when the
# raw direction_deviation sign is negative -- the rationale must not
# tell the coach to shade in the OPPOSITE direction. Symmetric for
# right-half zones (F/G/H).
#
# Two patterns each side: bare "right"/"left" alone is too broad (the
# citation list accepts "left" as a zone keyword and many coaching
# phrases use the word in neutral senses, e.g. "left field" appears in
# nearly every rationale). We look for direction-ACTION phrases.
# ---------------------------------------------------------------------------

_SHADE_RIGHT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bshade\s+right\b", re.IGNORECASE),
    re.compile(r"\bshift\s+right\b", re.IGNORECASE),
    re.compile(r"\bcheat\s+right\b", re.IGNORECASE),
    re.compile(r"\bto\s+right\s+field\b", re.IGNORECASE),
    re.compile(r"\bpulls?\s+right\b", re.IGNORECASE),
    re.compile(r"\bplay\s+(?:him\s+)?(?:to\s+the\s+)?right\b", re.IGNORECASE),
)
_SHADE_LEFT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bshade\s+left\b", re.IGNORECASE),
    re.compile(r"\bshift\s+left\b", re.IGNORECASE),
    re.compile(r"\bcheat\s+left\b", re.IGNORECASE),
    re.compile(r"\bto\s+left\s+field\b", re.IGNORECASE),
    re.compile(r"\bpulls?\s+left\b", re.IGNORECASE),
    re.compile(r"\bplay\s+(?:him\s+)?(?:to\s+the\s+)?left\b", re.IGNORECASE),
)
_SHADE_IN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bplay\s+(?:him\s+)?(?:in|shallow)\b", re.IGNORECASE),
    re.compile(r"\bshade\s+in\b", re.IGNORECASE),
    re.compile(r"\bcheat\s+in\b", re.IGNORECASE),
)
_SHADE_DEEP_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bplay\s+(?:him\s+)?(?:deep|back)\b", re.IGNORECASE),
    re.compile(r"\bshade\s+(?:deep|back)\b", re.IGNORECASE),
    re.compile(r"\bcheat\s+(?:deep|back)\b", re.IGNORECASE),
)


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a high school baseball coaching analyst. You analyze ONE batter's \
team-aggregate spray-chart tendencies and produce one short coach-facing \
rationale that explains WHY the deterministic positioning call makes sense \
for this batter at this position.

You will be given:
1. The deterministic positioning call for this batter at one position \
(already decided -- do not change it). It includes the zone letter (A-H) \
plus the underlying directional and depth deviation values relative to \
the team default for the position.
2. The team-aggregate context (per-position default location and BIP volume).

Respond ONLY with a JSON object (no markdown, no code fences) of the form:
{
  "rationale": "1-2 sentences, 10-50 words. Coach-facing prose explaining \
why this zone fits this batter's tendency."
}

Hard rules for the rationale:
- 1-2 sentences. 10-50 words inclusive.
- Reference the data: name the zone (e.g. "Zone B" or "in-left") OR a \
numeric figure from the input (BIP count, direction deviation, depth deviation).
- Do NOT contradict the deterministic call. If the zone is on the LEFT \
side (A/B/C), do not say "shade right" or "to right field." If the zone \
is deep (C/E/H), do not say "play him in." Symmetric for opposite signs.
- No baseball-statistics abbreviations like "wOBA" or "ISO". Plain English.
- Do not restate the zone name (the matrix already shows it). Explain \
the tendency.
"""


def _assemble_llm_input(
    batter_row: PerPositionRow,
    aggregate_row: TeamAggregateRow,
    batter_metadata: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the LLM input dict (AC-1 contract).

    Carries jersey, name, position, the per-position positioning row's
    zone_id + deviation values + BIP count + thin flag, plus the
    team-aggregate context for the same position. Opponent name and
    coverage cue come from ``batter_metadata`` (the bundle assembler
    threads them in once per render pass).

    The output dict is the locked contract per AC-1. Keys: jersey,
    name, position, zone_id, direction_deviation, depth_deviation,
    bip_count, is_thin, team_star_x, team_star_y, team_bip_count,
    team_is_low_confidence, opponent_name, coverage_cue.
    """
    if batter_row.position != aggregate_row.position:
        raise ValueError(
            "Position mismatch between batter_row "
            f"({batter_row.position}) and aggregate_row "
            f"({aggregate_row.position}). Caller must pass the "
            "team-aggregate row for the same position."
        )

    jersey = batter_metadata.get("jersey_number")
    first = batter_metadata.get("first_name") or ""
    last = batter_metadata.get("last_name") or ""
    name = (first + " " + last).strip() or batter_metadata.get("display_name") or ""

    return {
        "jersey": jersey,
        "name": name,
        "position": batter_row.position,
        "zone_id": batter_row.zone_id,
        "direction_deviation": batter_row.direction_deviation,
        "depth_deviation": batter_row.depth_deviation,
        "bip_count": batter_row.bip_count,
        "is_thin": batter_row.is_thin,
        "team_star_x": aggregate_row.star_x,
        "team_star_y": aggregate_row.star_y,
        "team_bip_count": aggregate_row.bip_count,
        "team_is_low_confidence": aggregate_row.is_low_confidence,
        "opponent_name": batter_metadata.get("opponent_name", ""),
        "coverage_cue": batter_metadata.get("coverage_cue", ""),
    }


def _build_user_prompt(llm_input: dict[str, Any]) -> str:
    """Render the user-prompt body from the assembled input contract."""
    parts: list[str] = []
    parts.append("# Defensive Positioning Rationale Request")
    parts.append("")
    parts.append(f"Opponent: {llm_input['opponent_name']}")
    parts.append(f"Coverage: {llm_input['coverage_cue']}")
    parts.append("")
    parts.append("## Batter")
    jersey = llm_input["jersey"]
    parts.append(f"  Jersey: #{jersey}" if jersey else "  Jersey: (none)")
    parts.append(f"  Name:   {llm_input['name']}")
    parts.append(f"  Position context: {llm_input['position']}")
    parts.append(f"  BIP this season: {llm_input['bip_count']}")
    parts.append(f"  Thin sample: {'yes' if llm_input['is_thin'] else 'no'}")
    parts.append("")
    parts.append("## Deterministic call (already decided)")
    zone = llm_input["zone_id"]
    parts.append(f"  Zone: {zone if zone else '(team default; no outlier)'}")
    parts.append(f"  direction_deviation: {llm_input['direction_deviation']}")
    parts.append(f"  depth_deviation: {llm_input['depth_deviation']}")
    parts.append("")
    parts.append("## Team-aggregate context")
    parts.append(f"  Position: {llm_input['position']}")
    parts.append(
        f"  Star location (SVG-space): "
        f"({llm_input['team_star_x']:.1f}, {llm_input['team_star_y']:.1f})"
    )
    parts.append(f"  Team BIP volume: {llm_input['team_bip_count']}")
    parts.append(
        f"  Low confidence team coverage: "
        f"{'yes' if llm_input['team_is_low_confidence'] else 'no'}"
    )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Response validation (AC-2 / AC-4)
# ---------------------------------------------------------------------------


def _count_words(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _truncate_to_in_band_sentence(text: str) -> str | None:
    """Longest prefix of full sentences with word count in [_MIN_WORDS,
    _MAX_WORDS]; None if no such prefix exists."""
    sentences = _split_sentences(text)
    if not sentences:
        return None
    for n in range(1, min(len(sentences), _MAX_SENTENCES) + 1):
        candidate = " ".join(sentences[:n])
        words = _count_words(candidate)
        if _MIN_WORDS <= words <= _MAX_WORDS:
            return candidate
    return None


def _has_structural_citation(
    text: str,
    batter_row: PerPositionRow,
) -> bool:
    """AC-2 (b): the rationale must contain at least one concrete
    reference drawn from the engine input -- a zone keyword (letter
    or long-form name) OR a numeric figure from the row."""
    lowered = text.lower()
    if _ZONE_LETTER_PATTERN.search(text):
        return True
    for kw in _ZONE_LONGFORM_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", lowered):
            return True
    for kw in _CONTACT_TYPE_KEYWORDS:
        if kw in lowered:
            return True
    candidate_numbers = {
        batter_row.bip_count,
        batter_row.hr_count,
        abs(batter_row.direction_deviation),
        abs(batter_row.depth_deviation),
    }
    candidate_numbers.discard(0)
    for n in candidate_numbers:
        if re.search(rf"\b{n}\b", lowered):
            return True
    return False


def _has_decision_contradiction(
    text: str,
    batter_row: PerPositionRow,
) -> bool:
    """AC-2 (c): direction-action phrases contradicting the row's spatial
    assignment make the rationale invalid.

    The spatial assignment is derived from the row's zone_id (if set)
    or from the sign of its deviation values otherwise.
    """
    if batter_row.zone_id is not None:
        h_sign = _ZONE_HORIZONTAL_SIGN.get(batter_row.zone_id, 0)
        v_sign = _ZONE_VERTICAL_SIGN.get(batter_row.zone_id, 0)
    else:
        h_sign = _sign(batter_row.direction_deviation)
        v_sign = _sign(batter_row.depth_deviation)

    if h_sign < 0:  # batter pulls/lines left -> "shade right" contradicts
        if any(p.search(text) for p in _SHADE_RIGHT_PATTERNS):
            return True
    if h_sign > 0:  # batter pulls/lines right -> "shade left" contradicts
        if any(p.search(text) for p in _SHADE_LEFT_PATTERNS):
            return True
    if v_sign < 0:  # batter lines in (shallow) -> "play deep" contradicts
        if any(p.search(text) for p in _SHADE_DEEP_PATTERNS):
            return True
    if v_sign > 0:  # batter lines deep -> "play in" contradicts
        if any(p.search(text) for p in _SHADE_IN_PATTERNS):
            return True
    return False


def _sign(n: int) -> int:
    if n < 0:
        return -1
    if n > 0:
        return 1
    return 0


def _validate_response(
    raw: str,
    batter_row: PerPositionRow,
) -> str | None:
    """Apply the AC-2 (a/b/c) observable contract. Return the (possibly
    truncated) rationale, or ``None`` when validation fails.

    Failure paths log at WARNING per AC-4 so the operator can audit
    rationale drops during the calibration pass.
    """
    text = raw.strip()
    if not text:
        logger.warning("Positioning rationale empty -- dropping.")
        return None

    # AC-2 (a): length gate.
    words = _count_words(text)
    if words < _MIN_WORDS:
        logger.warning(
            "Positioning rationale too short (%d words; min %d) -- dropping. "
            "zone_id=%s",
            words, _MIN_WORDS, batter_row.zone_id,
        )
        return None
    if words > _MAX_WORDS:
        truncated = _truncate_to_in_band_sentence(text)
        if truncated is None:
            logger.warning(
                "Positioning rationale too long (%d words; max %d) and no "
                "in-band sentence prefix -- dropping. zone_id=%s",
                words, _MAX_WORDS, batter_row.zone_id,
            )
            return None
        text = truncated
    else:
        sentences = _split_sentences(text)
        if len(sentences) > _MAX_SENTENCES:
            truncated = _truncate_to_in_band_sentence(text)
            if truncated is None:
                logger.warning(
                    "Positioning rationale exceeds %d sentences with no "
                    "in-band prefix -- dropping. zone_id=%s",
                    _MAX_SENTENCES, batter_row.zone_id,
                )
                return None
            text = truncated

    # AC-2 (c): decision discipline -- check the (possibly truncated) text.
    if _has_decision_contradiction(text, batter_row):
        logger.warning(
            "Positioning rationale contradicts zone_id=%s "
            "(direction_dev=%d, depth_dev=%d) -- dropping. rationale=%r",
            batter_row.zone_id,
            batter_row.direction_deviation,
            batter_row.depth_deviation,
            text,
        )
        return None

    # AC-2 (b): structural citation.
    if not _has_structural_citation(text, batter_row):
        logger.warning(
            "Positioning rationale lacks structural citation (no zone, "
            "contact-type, or numeric figure) -- dropping. zone_id=%s",
            batter_row.zone_id,
        )
        return None

    return text


# ---------------------------------------------------------------------------
# Public entry point (AC-5)
# ---------------------------------------------------------------------------


def generate_rationale(
    batter_row: PerPositionRow,
    aggregate_row: TeamAggregateRow,
    batter_metadata: dict[str, Any],
) -> Optional[str]:
    """Top-level entry: per-batter rationale or ``None`` on any failure.

    Per AC-3 (non-fatal contract preserved from E-228 CX-4):

    * :func:`is_llm_available` returns False -> Tier 2 skipped silently
      with **INFO** log. Expected config state, not an error.
    * The LLM call raises any exception -> caught with **WARNING** log;
      bundle still renders without this batter's rationale line.

    Per AC-4: a response that fails the three-part output contract
    (length / citation / decision discipline) is logged at WARNING and
    the rationale is dropped (return None). **No DB persistence.**
    The bundle assembler (E-229-08) iterates flagged batters, calls
    this function per batter, and threads the result directly into
    the template context.

    Args:
        batter_row: The :class:`PerPositionRow` for this batter at the
            position being rationalized.
        aggregate_row: The :class:`TeamAggregateRow` for the same
            position. Must match ``batter_row.position``.
        batter_metadata: Dict with ``jersey_number``, ``first_name``,
            ``last_name``, ``opponent_name``, ``coverage_cue``.

    Returns:
        The validated rationale string on success; ``None`` on any
        failure mode (LLM unavailable, exception, validation rejection).
    """
    if not is_llm_available():
        logger.info(
            "Tier 2 LLM unavailable (OPENROUTER_API_KEY not set) -- "
            "positioning rationale skipped for jersey=%s position=%s.",
            batter_metadata.get("jersey_number"),
            batter_row.position,
        )
        return None

    try:
        llm_input = _assemble_llm_input(batter_row, aggregate_row, batter_metadata)
    except ValueError as exc:
        logger.warning(
            "Tier 2 LLM input assembly failed: %s. Dropping rationale.", exc,
        )
        return None

    model = os.environ.get(
        "OPENROUTER_MODEL", "anthropic/claude-haiku-4-5-20251001",
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(llm_input)},
    ]

    try:
        response = query_openrouter(
            messages, model=model, max_tokens=200, temperature=0.3,
        )
    except LLMError as exc:
        logger.warning(
            "Tier 2 LLM call failed for jersey=%s position=%s: %s. "
            "Continuing without rationale.",
            batter_metadata.get("jersey_number"),
            batter_row.position,
            exc,
            exc_info=True,
        )
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Tier 2 LLM unexpected error for jersey=%s position=%s: %s. "
            "Continuing without rationale.",
            batter_metadata.get("jersey_number"),
            batter_row.position,
            exc,
            exc_info=True,
        )
        return None

    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning(
            "Tier 2 LLM response structure unexpected for jersey=%s "
            "position=%s: %s. Dropping rationale.",
            batter_metadata.get("jersey_number"),
            batter_row.position,
            exc,
        )
        return None

    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning(
            "Tier 2 LLM response is not valid JSON for jersey=%s "
            "position=%s: %s. Dropping rationale.",
            batter_metadata.get("jersey_number"),
            batter_row.position,
            exc,
        )
        return None

    raw = parsed.get("rationale") if isinstance(parsed, dict) else None
    if not isinstance(raw, str):
        logger.warning(
            "Tier 2 LLM response missing/non-string 'rationale' for "
            "jersey=%s position=%s. Dropping.",
            batter_metadata.get("jersey_number"),
            batter_row.position,
        )
        return None

    return _validate_response(raw, batter_row)


# ---------------------------------------------------------------------------
# Deprecated v1 shim -- removed by E-229-10 (pipeline wiring)
# ---------------------------------------------------------------------------


def enrich_positioning(*_args: Any, **_kwargs: Any) -> None:
    """Deprecated v1 entry point retained for collection-time compatibility.

    The v1 contract (categorical ``call_state`` / ``team_state_call`` /
    direction / depth shades) is retired by E-229-02. The v2 entry
    point is :func:`generate_rationale`. The v1 call site in
    :mod:`src.reports.generator` will be excised by E-229-10 (pipeline
    wiring); until then this shim returns ``None`` unconditionally so
    the bundle continues to render without a rationale line.
    """
    logger.info(
        "Tier 2 LLM v1 entry point invoked (deprecated; E-229-10 will "
        "remove the call site). Returning None so the bundle still renders."
    )
    return None
