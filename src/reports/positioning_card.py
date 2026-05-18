"""Per-position card field SVG generator (E-229-03).

Produces a single field diagram for one (opponent, fielder position):
the team-aggregate star, a whisper-quiet textbook reference dot, the
full 8-zone compass letter ring at fixed angular offsets around the
star, and a faint spray-density background. Three confidence states
(zero-coverage / thin-data / full) are supported per epic TN-4.

Outlier batter pills are NOT in this story (E-229-04 layers them on
top of this SVG). The render layer that wraps this SVG inside the
4.25" x 5.5" quarter-letter card template is E-229-05.

Public API::

    from src.reports.positioning_card import render_field_svg

    svg: str = render_field_svg(conn, public_id="opp-bears", position="LF")

All numeric constants (viewBox dimensions, element sizes, ring radius,
scale factors, opacities, typography) are consumed from the locked
artifact at ``.project/research/E-229-locked-layout-constants.md``
section B per the citation pattern in epic TN-16 and AC-1 of this story.
This module does NOT inline values that would conflict with the
artifact; values appear in code only because they have to (constants
in source), and any change goes to the artifact first.
"""

from __future__ import annotations

import math
import sqlite3
from typing import Any

from src.reports.positioning import BASE_POSITIONS, COVERED_POSITIONS

# ---------------------------------------------------------------------------
# Module-level legend constants (per UXD M-1, artifact §F)
# ---------------------------------------------------------------------------

COMPASS_LEGEND_SHORT: str = "★ default · ○ textbook · A-H outliers"
"""Per-card legend wording. Locked per E-229-2b coach AC-12 Option 1 +
epic TN-3 amendment (LOCKED v1, artifact §F)."""

COMPASS_LEGEND_LONG: str = (
    "A in-left · B left · C deep-left · D in · E deep "
    "· F in-right · G right · H deep-right · · = team default"
)
"""Call sheet + prep page legend wording (artifact §F)."""


def format_coverage_cue(through_date: str, game_count: int) -> str:
    """Render the locked coverage-cue format string.

    Per artifact §F + epic TN-16. Produces ``Through {Mon Day} ({N} games)``
    where ``{Mon Day}`` is the abbreviated month-day (e.g. ``Apr 12``).
    Both inputs are captured at bundle-generation time (per coach IM-2 +
    user lock); this helper performs only format-string assembly.

    Args:
        through_date: Pre-formatted "Mon Day" string (e.g. "Apr 12").
            The bundle assembler (E-229-08) owns the date-formatting
            step using the freshness-date snapshot.
        game_count: Game count at bundle-generation time.

    Returns:
        Formatted coverage-cue string, ready to render in 9pt Arial regular.
    """
    suffix = "game" if game_count == 1 else "games"
    return f"Through {through_date} ({game_count} {suffix})"


# ---------------------------------------------------------------------------
# Coordinate-space rescaling (artifact §B, v1.2 anchor-based)
# ---------------------------------------------------------------------------
#
# The engine writes team_position_aggregate.(star_x, star_y) in
# spray.py's 320 x 480 SVG-space convention (y=0 at deep CF; see
# src/charts/spray.py:47 and epic TN-15). The card's field SVG viewBox
# is 200 x 320 (artifact §B aspect 0.625), but the field outline does
# NOT fill the viewBox edge-to-edge -- the top 80 viewBox-y units are
# header space and the bottom 15 are legend space; the field itself
# occupies the inner rectangle (10, 80) -- (190, 305).

_CARD_VIEWBOX_W = 200
_CARD_VIEWBOX_H = 320

# Engine landmark constants (320 x 480 GC canonical).
_ENGINE_W = 320.0
_ENGINE_HOME_Y = 295.0

# Card landmark constants (viewBox 200 x 320 inner field rectangle).
_CARD_LEFT_X = 10.0
_CARD_FENCE_Y = 80.0
_CARD_HOME_Y = 305.0
_CARD_FIELD_W = 180.0  # x range from foul to foul
_CARD_FIELD_H = _CARD_HOME_Y - _CARD_FENCE_Y  # 225 px vertical extent


def _engine_to_card_xy(engine_x: float, engine_y: float) -> tuple[float, float]:
    """Map engine 320 x 480 GC coords to card 200 x 320 viewBox coords.

    Anchors engine field corners to the prototype's actual field corners:
      * engine (0, 0)       -> card (10, 80)    (LF foul / deep CF top)
      * engine (320, 295)   -> card (190, 305)  (RF home plate)

    The top 80 card-y units are header space; the bottom 15 are legend;
    the field is the inner rectangle (10, 80) -- (190, 305). Anchoring
    at the field corners (not the viewBox edges) is what makes engine
    landmarks land at the corresponding visual landmarks on the card.

    NOTE: spec v1.1 §B had a pure-scalar formula (x_engine * 0.625,
    y_engine * 0.6667) that was geometrically wrong -- it ignored the
    field-outline offset from the viewBox edges, landing engine y=0 at
    card y=0 (above the fence arc) and engine home plate at card y~=197
    (mid-card, far above the actual home plate at card y=305). Spec
    v1.2 ratifies this anchor-based mapping as the canonical contract.

    Applied to every coordinate sourced from the engine:
      * ``team_position_aggregate.(star_x, star_y)``
      * ``spray_charts.(x, y)`` for the density background
      * ``BASE_POSITIONS[position]`` (engine-module constants) -- per the
        §B textbook-dot caveat (rescale rather than declaring
        card-native textbook positions)

    Coordinates that are NOT engine-sourced (compass-letter offsets,
    pill offsets, field-outline primitives) are viewBox-native already
    and do NOT route through this helper.

    Sign-rule preservation: positive-only affine; the TN-15
    y=0-at-deep-CF convention carries through unchanged.
    """
    card_x = _CARD_LEFT_X + (engine_x / _ENGINE_W) * _CARD_FIELD_W
    card_y = _CARD_FENCE_Y + (engine_y / _ENGINE_HOME_Y) * _CARD_FIELD_H
    return card_x, card_y


# ---------------------------------------------------------------------------
# Locked numeric constants (artifact §B — must match)
# ---------------------------------------------------------------------------

# Star + textbook dot + compass disc dimensions in card viewBox space.
_STAR_RADIUS = 8.0  # ~16px wide star (artifact: ~16 px wide in viewBox)
_TEXTBOOK_DOT_RADIUS = 3.5
_COMPASS_DISC_RADIUS = 6.5
_DENSITY_DOT_RADIUS = 1.8

# Compass ring asymmetric radii (artifact §B "Compass ring placement"
# practical values when star is mid-field). The asymmetric values honor
# the field's taller-than-wide aspect (viewBox 200 x 320). Used as the
# baseline R_x / R_y; edge-clamping shrinks them if needed.
_COMPASS_RX = 36.0
_COMPASS_RY = 50.0

# Compass letter typography (artifact §B + §E + §C).
_COMPASS_FONT_SIZE_PT = "10pt"
_PILL_TEXT_FONT_SIZE_PT = "9pt"
_BIP_CAPTION_FONT_SIZE_PT = "7pt"

# Compass disc fill alpha (artifact §B "0.18 in disc, disc fill rgba(0,0,0,0.20)").
_COMPASS_DISC_FILL = "rgba(0,0,0,0.20)"

# Density background opacity (artifact §B "12%").
_DENSITY_BG_OPACITY = 0.12

# Textbook dot opacity (artifact §B "100% black ink at 45% opacity").
_TEXTBOOK_DOT_OPACITY = 0.45

# Empty-zone placeholder opacity (artifact §B "both letter and disc at 30%").
_EMPTY_ZONE_OPACITY = 0.30

# Thin-tier dashed ring around star (artifact §B "stroke 0.6 px, dash 2 1.5,
# opacity 0.85, radius 10 px in viewBox").
_THIN_TIER_RING_RADIUS = 10.0

# BIP caption placement (artifact §B "placed 18 px below star center").
_BIP_CAPTION_OFFSET_Y = 18.0

# Pill projection scale (artifact §B "Projection formulas" / "Pill
# projection scale"). Pixels per ordinal-bucket unit in viewBox space.
_PILL_SCALE_X = 18.0
_PILL_SCALE_Y = 22.0

# Pill dimensions (artifact §B "Outlier pill — shape").
_PILL_HEIGHT = 14.0          # viewBox px, ~0.20 in printed
_PILL_CORNER_RADIUS = 2.0
_PILL_STROKE_WIDTH = 0.5
# Auto-width is approximated from text length; the pill rect is sized
# per-character so 9pt Arial bold text fits. Each character is treated
# as ~4.5 viewBox-px wide (calibrated empirically against the
# prototype's pill widths, e.g. `#7 RAMIR` at 7 chars sits at width ~38).
_PILL_CHAR_WIDTH = 4.5
_PILL_TEXT_PADDING_X = 4.0   # px each side
_PILL_MIN_WIDTH = 18.0       # floor for very short labels

# Last-name truncation (artifact §B "5-6 chars depending on width budget").
_PILL_LAST_NAME_MAX_CHARS = 6

# Collision-resolution geometry (epic TN-10 + DE recommendation).
# Two pills whose projected centers fall within `_PILL_COLLISION_EPSILON`
# are considered collided. Deterministic radial jitter places the
# colliding pills around the centroid at `_PILL_JITTER_RADIUS`
# with stable angular order keyed on jersey number (ascending).
_PILL_COLLISION_EPSILON = 18.0   # ~ pill width; tighter than 1.5x to avoid over-jittering
_PILL_JITTER_RADIUS = 12.0       # viewBox px; large enough to break overlap, small enough to stay visually associated
_PILL_JITTER_ANGLE_STEP_DEG = 60.0

# Confidence-tier boundary (engine constant; mirrored for callers).
_LOW_CONFIDENCE_THRESHOLD = 50  # mirrors src/reports/positioning.LOW_CONFIDENCE_THRESHOLD


# ---------------------------------------------------------------------------
# Zone-letter sign table (mirrors src/reports/positioning._ZONE_SIGN_TABLE)
# ---------------------------------------------------------------------------
# Per epic TN-3: zone letter -> (sign(direction), sign(depth)).
# direction: negative = left (toward LF), positive = right (toward RF)
# depth:     negative = in (toward home),  positive = deep (toward CF wall)

_ZONE_SIGNS: dict[str, tuple[int, int]] = {
    "A": (-1, -1),  # in + left
    "B": (-1,  0),  # left
    "C": (-1,  1),  # deep + left
    "D": ( 0, -1),  # in
    "E": ( 0,  1),  # deep
    "F": ( 1, -1),  # in + right
    "G": ( 1,  0),  # right
    "H": ( 1,  1),  # deep + right
}


# ---------------------------------------------------------------------------
# Field geometry (200 x 320 card viewBox; per E-229-2b prototype)
# ---------------------------------------------------------------------------
# Reproduced from the prototype HTML at .project/research/E-229-2b-quarter-letter-prototype.html
# Outfield arc apex at deep CF (100, 80), foul corners at (10, 80) and (190, 80),
# home plate at (100, 305), infield arc spanning ~(55,245) to (145,245).

# Field-outline primitives in card viewBox space (NOT engine space).
# The field outline is a static decorative element drawn from the
# prototype HTML; it is NOT regenerated from engine output. The
# `_CARD_FENCE_Y` / `_CARD_HOME_Y` constants used by `_clamp_to_field`
# are declared above in the Coordinate-space rescaling section.
_FIELD_OUTLINE_PATH = (
    # Outfield fence arc (outer edge of the field).
    'M 10 80 Q 100 -10 190 80 L 190 90 Q 100 0 10 90 Z'
)
_FOUL_LINE_LEFT = (10.0, 80.0)
_FOUL_LINE_RIGHT = (190.0, 80.0)
_HOME_PLATE_CARD = (100.0, _CARD_HOME_Y)
_INFIELD_ARC_PATH = "M 55 245 Q 100 200 145 245"
_BASES_CARD: tuple[tuple[float, float], ...] = (
    (97.0, 302.0),   # home
    (127.0, 272.0),  # 1B
    (97.0, 242.0),   # 2B
    (67.0, 272.0),   # 3B
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clamp_to_field(
    cx: float, cy: float, disc_radius: float,
) -> tuple[float, float]:
    """Edge-clamp a compass-letter position to stay inside the field outline.

    Per artifact §B "edge-clamping rule": if `letter_position + disc_radius
    > field_edge`, slide letter inward along the radial vector until clear.

    The field outline in card viewBox space is bounded by:
      * left foul line:  segment from (100, 305) to (10, 80)
      * right foul line: segment from (100, 305) to (190, 80)
      * back fence arc:  arc from (10, 80) over (100, ~0) to (190, 80)

    For simplicity (and to match the prototype's behavior) we approximate
    the field as a triangle bounded by the two foul lines and a horizontal
    line at y = `_CARD_FENCE_Y` (the deep CF fence). This is a slight
    underestimate of the actual field area (the OF arc bows above the
    fence line) but the foul lines are the most restrictive constraints
    for compass letters projecting outward from a star near the center
    of the field.
    """
    # Constrain to the deep-CF fence (y >= _CARD_FENCE_Y + disc_radius).
    if cy < _CARD_FENCE_Y + disc_radius:
        cy = _CARD_FENCE_Y + disc_radius

    # Constrain to the left foul line. The left foul line runs from
    # home (100, 305) to LF corner (10, 80). Its equation:
    #   slope = (80 - 305) / (10 - 100) = 2.5
    #   y - 305 = 2.5 * (x - 100)  =>  x_min(y) = 100 - (305 - y) / 2.5
    # Center must satisfy cx >= x_min(cy) + disc_radius.
    x_min = 100.0 - (_CARD_HOME_Y - cy) / 2.5
    if cx < x_min + disc_radius:
        cx = x_min + disc_radius

    # Right foul line: slope = (80 - 305) / (190 - 100) = -2.5
    # Center must satisfy cx <= x_max(cy) - disc_radius.
    x_max = 100.0 + (_CARD_HOME_Y - cy) / 2.5
    if cx > x_max - disc_radius:
        cx = x_max - disc_radius

    return cx, cy


def _compass_letter_positions(
    star_x: float, star_y: float,
) -> dict[str, tuple[float, float]]:
    """Compute the 8 compass-letter positions (A..H) around the star.

    Per epic TN-3 sign-rule table + epic TN-15 SVG coord convention. The
    `-` on depth_dev_for_zone is the canonical y-axis convention
    adjustment (y=0 at deep CF, so `deep` = negative y_offset).

    The compass ring is asymmetric (`_COMPASS_RX` x `_COMPASS_RY`) to honor
    the card's portrait aspect. Each letter is edge-clamped to the field
    outline so it never renders outside the field.
    """
    positions: dict[str, tuple[float, float]] = {}
    for letter, (sign_x, sign_y) in _ZONE_SIGNS.items():
        # SVG offset per artifact §B projection formula.
        # letter_x = star_x + sign(direction) * scale_x * R_units
        # letter_y = star_y + (-sign(depth))  * scale_y * R_units
        # Where (scale_x * R_units, scale_y * R_units) = (_COMPASS_RX, _COMPASS_RY).
        cx = star_x + sign_x * _COMPASS_RX
        cy = star_y - sign_y * _COMPASS_RY
        positions[letter] = _clamp_to_field(cx, cy, _COMPASS_DISC_RADIUS)
    return positions


def _star_polygon_points() -> str:
    """The 10-point star polygon points (centered at origin).

    Reproduced from the prototype HTML (line 490).
    """
    return (
        "0,-8 2.4,-2.6 8,-2.6 3.6,1.2 5.4,7 0,3.4 "
        "-5.4,7 -3.6,1.2 -8,-2.6 -2.4,-2.6"
    )


def _xml_escape(text: str) -> str:
    """Escape a small set of characters for inclusion in XML text content.

    Card content is mostly known-safe (position abbreviations, integer
    counts, dates), but opponent names come from external sources and
    might carry `&`, `<`, `>`, `'`, or `"`. We escape conservatively.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


# ---------------------------------------------------------------------------
# Query helpers (epic TN-7 JOIN patterns)
# ---------------------------------------------------------------------------


def _query_team_id_from_public_id(
    conn: sqlite3.Connection, public_id: str,
) -> int | None:
    row = conn.execute(
        "SELECT id FROM teams WHERE public_id = ?", (public_id,),
    ).fetchone()
    if row is None:
        return None
    return row[0] if not isinstance(row, sqlite3.Row) else row["id"]


def _query_team_aggregate(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    position: str,
) -> dict[str, Any] | None:
    """Query the team_position_aggregate row for one (opponent, season, position).

    Returns the row from the perspective that matches ``team_id`` (the
    standalone convention used elsewhere in the codebase). When multiple
    perspectives exist, the standalone perspective (perspective_team_id
    = team_id) is preferred; if absent, the first perspective row is
    returned. The chosen ``perspective_team_id`` is included in the
    returned dict so callers can thread it through to the populated-zone
    and density-bg queries (epic TN-7 perspective-provenance invariant).
    Returns None if no row exists.
    """
    row = conn.execute(
        """
        SELECT position, star_x, star_y, bip_count, is_low_confidence,
               perspective_team_id
        FROM team_position_aggregate
        WHERE team_id = ? AND season_id = ? AND position = ?
        ORDER BY CASE WHEN perspective_team_id = ? THEN 0 ELSE 1 END
        LIMIT 1
        """,
        (team_id, season_id, position, team_id),
    ).fetchone()
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return dict(row)
    return {
        "position": row[0], "star_x": row[1], "star_y": row[2],
        "bip_count": row[3], "is_low_confidence": row[4],
        "perspective_team_id": row[5],
    }


def _query_populated_zones(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    position: str,
    perspective_team_id: int,
) -> set[str]:
    """Return the set of zone letters with at least one non-thin outlier batter.

    Per epic TN-5: a populated zone has `zone_id IS NOT NULL AND
    is_thin = 0` for at least one batter at this position. Scoped to a
    single ``perspective_team_id`` per the TN-7 perspective-provenance
    invariant -- the caller threads the perspective chosen by
    :func:`_query_team_aggregate` so the populated-zone coloring stays
    internally consistent with the star.
    """
    rows = conn.execute(
        """
        SELECT DISTINCT zone_id FROM batter_positioning
        WHERE team_id = ? AND season_id = ? AND position = ?
          AND perspective_team_id = ?
          AND zone_id IS NOT NULL AND is_thin = 0
        """,
        (team_id, season_id, position, perspective_team_id),
    ).fetchall()
    if rows and isinstance(rows[0], sqlite3.Row):
        return {r["zone_id"] for r in rows}
    return {r[0] for r in rows}


def _query_density_points(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    perspective_team_id: int,
) -> list[tuple[float, float]]:
    """Spray-density background points per epic TN-7.

    Same (x, y) pool fuels every position's card. Scoped to a single
    ``perspective_team_id`` per the TN-7 perspective-provenance
    invariant -- the caller threads the perspective chosen by
    :func:`_query_team_aggregate` so the density background stays
    internally consistent with the star.
    """
    rows = conn.execute(
        """
        SELECT x, y FROM spray_charts
        WHERE team_id = ? AND season_id = ? AND perspective_team_id = ?
          AND chart_type = 'offensive' AND x IS NOT NULL AND y IS NOT NULL
        """,
        (team_id, season_id, perspective_team_id),
    ).fetchall()
    return [(r[0], r[1]) if not isinstance(r, sqlite3.Row) else (r["x"], r["y"])
            for r in rows]


def _query_outlier_batters(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    position: str,
    perspective_team_id: int,
) -> list[dict[str, Any]]:
    """Outlier batters for one (opponent, position) card per epic TN-5.

    Returns one row per non-thin batter with a non-NULL ``zone_id`` at
    this position, joined with ``team_rosters`` for the jersey number
    and ``players`` for the last-name fallback (epic TN-7 JOIN pattern).

    Each returned dict carries:
      * ``player_id``
      * ``direction_deviation`` / ``depth_deviation`` (signed ordinals)
      * ``zone_id`` (A-H)
      * ``jersey_number`` (TEXT or NULL)
      * ``first_name`` / ``last_name``

    Sort order: jersey ascending (NULL last). Sorting in Python keeps
    the SQL portable; for the small N (typically <= 15 outliers per
    card) the cost is negligible.
    """
    rows = conn.execute(
        """
        SELECT
            bp.player_id,
            bp.direction_deviation,
            bp.depth_deviation,
            bp.zone_id,
            tr.jersey_number,
            p.first_name,
            p.last_name
        FROM batter_positioning bp
        JOIN players p USING (player_id)
        LEFT JOIN team_rosters tr
            ON  tr.player_id = bp.player_id
            AND tr.team_id   = bp.team_id
            AND tr.season_id = bp.season_id
        WHERE bp.team_id = ?
          AND bp.season_id = ?
          AND bp.position = ?
          AND bp.perspective_team_id = ?
          AND bp.zone_id IS NOT NULL
          AND bp.is_thin = 0
        """,
        (team_id, season_id, position, perspective_team_id),
    ).fetchall()
    if rows and isinstance(rows[0], sqlite3.Row):
        return sorted(
            (dict(r) for r in rows),
            key=lambda d: _jersey_sort_key(d["jersey_number"]),
        )
    return sorted(
        (
            {
                "player_id": r[0],
                "direction_deviation": r[1],
                "depth_deviation": r[2],
                "zone_id": r[3],
                "jersey_number": r[4],
                "first_name": r[5],
                "last_name": r[6],
            }
            for r in rows
        ),
        key=lambda d: _jersey_sort_key(d["jersey_number"]),
    )


def _jersey_sort_key(jersey: str | None) -> tuple[int, int, str]:
    """Sort key: NULL jerseys last; numeric jerseys ascend by number; non-
    numeric jerseys sort last by string. Mirrors the precedent in
    ``src/reports/renderer.py::_jersey_sort_key``.
    """
    if jersey is None or jersey == "":
        return (2, 0, "")
    try:
        return (0, int(jersey), jersey)
    except ValueError:
        return (1, 0, jersey)


# ---------------------------------------------------------------------------
# SVG fragment builders
# ---------------------------------------------------------------------------


def _svg_field_outline() -> str:
    """Static field-shape primitives (outfield arc, foul lines, IF arc, bases)."""
    return (
        f'<path d="{_FIELD_OUTLINE_PATH}" fill="none" stroke="#000" '
        'stroke-width="0.8"/>'
        f'<line x1="{_HOME_PLATE_CARD[0]}" y1="{_HOME_PLATE_CARD[1]}" '
        f'x2="{_FOUL_LINE_LEFT[0]}" y2="{_FOUL_LINE_LEFT[1]}" '
        'stroke="#000" stroke-width="0.8"/>'
        f'<line x1="{_HOME_PLATE_CARD[0]}" y1="{_HOME_PLATE_CARD[1]}" '
        f'x2="{_FOUL_LINE_RIGHT[0]}" y2="{_FOUL_LINE_RIGHT[1]}" '
        'stroke="#000" stroke-width="0.8"/>'
        f'<path d="{_INFIELD_ARC_PATH}" fill="none" stroke="#000" '
        'stroke-width="0.5"/>'
        + "".join(
            f'<rect x="{bx}" y="{by}" width="6" height="6" '
            'fill="#fff" stroke="#000" stroke-width="0.5"/>'
            for bx, by in _BASES_CARD
        )
    )


def _svg_density_background(
    density_points: list[tuple[float, float]],
) -> str:
    """Faint density-background dots (rendered behind everything else)."""
    if not density_points:
        return ""
    dots = "".join(
        f'<circle cx="{_engine_to_card_xy(x, y)[0]:.2f}" '
        f'cy="{_engine_to_card_xy(x, y)[1]:.2f}" '
        f'r="{_DENSITY_DOT_RADIUS}"/>'
        for (x, y) in density_points
    )
    return f'<g fill="#000" opacity="{_DENSITY_BG_OPACITY}">{dots}</g>'


def _svg_textbook_dot(position: str) -> str:
    base_engine_x, base_engine_y = BASE_POSITIONS[position]
    cx, cy = _engine_to_card_xy(base_engine_x, base_engine_y)
    return (
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{_TEXTBOOK_DOT_RADIUS}" '
        f'fill="none" stroke="#000" stroke-width="0.6" '
        f'opacity="{_TEXTBOOK_DOT_OPACITY}"/>'
    )


def _svg_star(
    star_x_card: float, star_y_card: float,
    bip_count: int, is_thin: bool,
) -> str:
    """Render the team-aggregate star.

    Full tier: solid star + "(N BIP)" caption.
    Thin tier: solid star + dashed ring + "(~N BIP)" caption.
    """
    caption = f"(~{bip_count} BIP)" if is_thin else f"({bip_count} BIP)"
    thin_ring = ""
    if is_thin:
        thin_ring = (
            f'<circle cx="0" cy="0" r="{_THIN_TIER_RING_RADIUS}" '
            'fill="none" stroke="#000" stroke-width="0.6" '
            'stroke-dasharray="2 1.5" opacity="0.85"/>'
        )
    return (
        f'<g transform="translate({star_x_card:.2f}, {star_y_card:.2f})">'
        f'<polygon points="{_star_polygon_points()}" fill="#000" '
        f'stroke="none"/>'
        f'{thin_ring}'
        f'<text x="0" y="{_BIP_CAPTION_OFFSET_Y}" '
        f'font-size="{_BIP_CAPTION_FONT_SIZE_PT}" text-anchor="middle" '
        f'fill="#000">{caption}</text>'
        f'</g>'
    )


def _svg_compass_ring(
    star_x_card: float, star_y_card: float,
    populated_zones: set[str],
) -> str:
    """All 8 compass letters; populated full opacity, empty 30% per AC-4."""
    positions = _compass_letter_positions(star_x_card, star_y_card)
    parts: list[str] = [
        '<g font-size="' + _COMPASS_FONT_SIZE_PT + '" font-weight="bold" '
        'text-anchor="middle" dominant-baseline="central" '
        'font-family="Arial, Helvetica, sans-serif">'
    ]
    for letter in ("A", "B", "C", "D", "E", "F", "G", "H"):
        cx, cy = positions[letter]
        if letter in populated_zones:
            opacity = ""
        else:
            opacity = f' opacity="{_EMPTY_ZONE_OPACITY}"'
        parts.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" '
            f'r="{_COMPASS_DISC_RADIUS}" fill="{_COMPASS_DISC_FILL}" '
            f'stroke="none"{opacity}/>'
        )
        parts.append(
            f'<text x="{cx:.2f}" y="{cy:.2f}" fill="#000"{opacity}>'
            f'{letter}</text>'
        )
    parts.append("</g>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Outlier-pill rendering (E-229-04)
# ---------------------------------------------------------------------------


def _truncate_last_name(last_name: str | None) -> str:
    """Truncate to artifact §B's last-name budget (5-6 chars).

    Per ``_PILL_LAST_NAME_MAX_CHARS``: e.g., "RAMIREZ" -> "RAMIR" (or
    "RAMIRE" depending on slice width). We use the upper bound (6).
    """
    if not last_name:
        return ""
    return last_name[:_PILL_LAST_NAME_MAX_CHARS].upper()


def _pill_text(batter: dict[str, Any]) -> str:
    """Build the pill's label per artifact §B.

    Populated jersey: ``#<jersey> <truncated-last-name>`` (e.g.,
    ``#7 RAMIR``).

    NULL-jersey fallback per artifact §B "Outlier pill — NULL-jersey
    fallback": ``(L. init)`` where L is the first letter of the last
    name. No ``#`` prefix.
    """
    jersey = batter.get("jersey_number")
    last = batter.get("last_name") or ""
    if jersey:
        return f"#{jersey} {_truncate_last_name(last)}"
    # NULL-jersey fallback.
    initial = last[:1].upper() if last else "?"
    return f"({initial}. init)"


def _pill_width(text: str) -> float:
    """Approximate pill width for a given text label.

    Calibrated against the prototype's `#7 RAMIR` (7 chars) at width 38.
    Rough heuristic: characters * _PILL_CHAR_WIDTH + 2 * padding;
    clamped to `_PILL_MIN_WIDTH`.
    """
    return max(
        _PILL_MIN_WIDTH,
        len(text) * _PILL_CHAR_WIDTH + 2 * _PILL_TEXT_PADDING_X,
    )


def _pill_anchor_xy(
    star_x_card: float, star_y_card: float,
    direction_dev: int, depth_dev: int,
) -> tuple[float, float]:
    """Project a batter's signed deviations to a pill anchor in card space.

    Per epic TN-15 + artifact §B "Projection formulas":
      ``pill_x = star_x + direction_dev * scale_x``
      ``pill_y = star_y + (-depth_dev) * scale_y``

    The y-axis negation is the canonical convention adjustment (y=0 at
    deep CF; depth-positive "deep" projects upward / smaller y).
    """
    return (
        star_x_card + direction_dev * _PILL_SCALE_X,
        star_y_card - depth_dev * _PILL_SCALE_Y,
    )


def _resolve_pill_collisions(
    anchors: list[tuple[float, float, int]],
) -> list[tuple[float, float, int]]:
    """Apply deterministic radial jitter to pills that land within ε.

    Input: list of ``(anchor_x, anchor_y, sort_key)`` triples; the
    ``sort_key`` is the pill's jersey-sort tuple (so a stable angular
    order is keyed on jersey number per AC-4).

    Algorithm (epic TN-10 + DE recommendation):
      1. Build collision groups by union-find: two pills whose anchors
         lie within ``_PILL_COLLISION_EPSILON`` join the same group.
      2. For each group with > 1 pill:
         - Sort group members by ``sort_key`` (ascending).
         - Place pill 0 at the group centroid.
         - Place pill k (k >= 1) at the centroid + a radial offset of
           ``_PILL_JITTER_RADIUS`` at angle ``(k-1) *
           _PILL_JITTER_ANGLE_STEP_DEG`` degrees, measured clockwise
           from the SVG "topmost" direction (straight up = angle 0;
           in card SVG that's negative y delta).
      3. Singleton groups are unchanged.

    Returns: list of ``(jittered_x, jittered_y, sort_key)`` triples in
    the SAME order as the input list (so callers can zip with their
    batter list).
    """
    n = len(anchors)
    if n <= 1:
        return list(anchors)

    # Union-find over collision pairs.
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    for i in range(n):
        for j in range(i + 1, n):
            dx = anchors[i][0] - anchors[j][0]
            dy = anchors[i][1] - anchors[j][1]
            if dx * dx + dy * dy < _PILL_COLLISION_EPSILON ** 2:
                union(i, j)

    # Group indices by root.
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    out: list[tuple[float, float, int] | None] = [None] * n
    for members in groups.values():
        if len(members) == 1:
            out[members[0]] = anchors[members[0]]
            continue
        # Centroid of the group (mean of original anchors).
        cx = sum(anchors[m][0] for m in members) / len(members)
        cy = sum(anchors[m][1] for m in members) / len(members)
        # Stable angular order keyed on the sort_key (ascending).
        ordered = sorted(members, key=lambda m: anchors[m][2])
        # Pill 0 stays at the centroid; remaining rotate clockwise from
        # straight-up (angle 0 = -y direction) at 60° steps.
        for k, m in enumerate(ordered):
            if k == 0:
                out[m] = (cx, cy, anchors[m][2])
            else:
                angle_deg = (k - 1) * _PILL_JITTER_ANGLE_STEP_DEG
                angle_rad = math.radians(angle_deg)
                # SVG y is inverted from math convention; "straight up"
                # is negative y delta. Angle 0 = up; angle 90 (CW) =
                # right; 180 = down; 270 = left.
                ox = _PILL_JITTER_RADIUS * math.sin(angle_rad)
                oy = -_PILL_JITTER_RADIUS * math.cos(angle_rad)
                out[m] = (cx + ox, cy + oy, anchors[m][2])

    # All slots filled.
    return [t for t in out if t is not None]


def _svg_outlier_pills(
    star_x_card: float, star_y_card: float,
    outliers: list[dict[str, Any]],
) -> str:
    """Render the outlier-pill layer for a card.

    Steps:
      1. Project each batter's (direction_deviation, depth_deviation)
         to a card-space anchor via :func:`_pill_anchor_xy`.
      2. Resolve collisions via deterministic radial jitter.
      3. Emit one ``<g>`` group containing a ``<rect>`` + ``<text>``
         per pill.

    Per AC-5 z-order: pills layer on top of every other body element
    (the caller appends this fragment last in the body_parts list).
    """
    if not outliers:
        return ""

    # Precompute (anchor_x, anchor_y, sort_key) per batter.
    anchors: list[tuple[float, float, int]] = []
    sort_keys: list[tuple[int, int, str]] = []
    for batter in outliers:
        ax, ay = _pill_anchor_xy(
            star_x_card, star_y_card,
            batter["direction_deviation"], batter["depth_deviation"],
        )
        # Use a single integer key for collision sort_key (the jersey
        # number if numeric; else a synthetic large number so non-
        # numeric / NULL sort last consistently with the SQL order).
        jk = _jersey_sort_key(batter.get("jersey_number"))
        sort_keys.append(jk)
        anchors.append((ax, ay, _jersey_collision_key(jk)))

    placed = _resolve_pill_collisions(anchors)

    pieces: list[str] = [
        '<g font-family="Arial, Helvetica, sans-serif" '
        f'font-weight="bold" font-size="{_PILL_TEXT_FONT_SIZE_PT}">'
    ]
    for batter, (px, py, _key) in zip(outliers, placed):
        text = _pill_text(batter)
        w = _pill_width(text)
        half_w = w / 2.0
        half_h = _PILL_HEIGHT / 2.0
        pieces.append(
            f'<g transform="translate({px:.2f}, {py:.2f})">'
            f'<rect x="{-half_w:.2f}" y="{-half_h:.2f}" '
            f'width="{w:.2f}" height="{_PILL_HEIGHT}" '
            f'rx="{_PILL_CORNER_RADIUS}" ry="{_PILL_CORNER_RADIUS}" '
            f'fill="#fff" stroke="#000" '
            f'stroke-width="{_PILL_STROKE_WIDTH}"/>'
            f'<text x="0" y="0" text-anchor="middle" '
            f'dominant-baseline="central" fill="#000">'
            f'{_xml_escape(text)}</text>'
            f'</g>'
        )
    pieces.append('</g>')
    return "".join(pieces)


def _jersey_collision_key(sort_key: tuple[int, int, str]) -> int:
    """Project a jersey-sort-key tuple to a single int for radial-order
    sorting inside ``_resolve_pill_collisions``.

    Numeric jerseys sort by number; non-numeric and NULL sort after,
    with stable but jersey-independent ordering. We pack the tuple's
    ranks into a single int so the collision resolver can ``sort()``
    by a single key. Within numeric jerseys, the actual jersey number
    drives the radial rotation order.
    """
    bucket, value, _str = sort_key
    return bucket * 1_000_000 + value


def _svg_no_outliers_note() -> str:
    """One-line note under the field when zero zones are populated.

    Per AC-8. Centered horizontally, placed below the infield arc.
    """
    return (
        f'<text x="{_CARD_VIEWBOX_W / 2}" y="290" '
        'font-size="8pt" font-style="italic" fill="#4d4d4d" '
        'text-anchor="middle" '
        'font-family="Arial, Helvetica, sans-serif">'
        'No outliers this opponent</text>'
    )


def _svg_zero_coverage_message() -> str:
    """Centered dominant message for the zero-coverage state (AC-9)."""
    return (
        f'<text x="{_CARD_VIEWBOX_W / 2}" y="170" '
        'font-size="10pt" font-weight="bold" fill="#000" '
        'text-anchor="middle" '
        'font-family="Arial, Helvetica, sans-serif">'
        'Not enough spray data</text>'
        f'<text x="{_CARD_VIEWBOX_W / 2}" y="190" '
        'font-size="9pt" fill="#4d4d4d" text-anchor="middle" '
        'font-family="Arial, Helvetica, sans-serif">'
        '— play your standard alignment</text>'
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render_field_svg(
    conn: sqlite3.Connection,
    public_id: str,
    position: str,
    season_id: str,
    *,
    opponent_name: str = "",
    through_date: str = "",
    game_count: int = 0,
) -> str:
    """Render the field SVG for one (opponent, position) card.

    Args:
        conn: Open sqlite3 connection with v2 schema applied.
        public_id: Opponent's GameChanger public_id slug.
        position: One of LF/CF/RF/3B/SS/2B (per epic TN-3).
        season_id: Season slug (e.g. "2026-spring-hs").
        opponent_name: Opponent display name (rendered in card header).
        through_date: Pre-formatted "Mon Day" string for coverage cue
            (the bundle assembler in E-229-08 supplies this).
        game_count: Game count at bundle-generation time.

    Returns:
        A string containing a complete ``<svg>...</svg>`` element with
        the card's header (opponent name, position, coverage cue),
        field SVG body, and bottom legend. Suitable for inclusion in
        the card template (E-229-05) or the prep page (E-229-06).

    The function selects the three-state confidence rendering based on
    the opponent's ``team_position_aggregate`` row:
      * No row OR ``bip_count < 15`` -> zero-coverage state
      * ``is_low_confidence = 1`` -> thin-data state
      * else -> full state
    """
    if position not in COVERED_POSITIONS:
        raise ValueError(
            f"position must be one of {COVERED_POSITIONS!r}, got {position!r}"
        )

    team_id = _query_team_id_from_public_id(conn, public_id)
    if team_id is None:
        raise ValueError(f"No team found for public_id={public_id!r}")

    aggregate = _query_team_aggregate(conn, team_id, season_id, position)

    # Confidence-tier branching (epic TN-4):
    #   No row OR bip_count < 15 -> zero coverage
    #   is_low_confidence == 1   -> thin data
    #   else                     -> full
    if aggregate is None or aggregate["bip_count"] < 15:
        confidence_tier = "zero"
    elif aggregate["is_low_confidence"]:
        confidence_tier = "thin"
    else:
        confidence_tier = "full"

    # Header + legend are rendered for all three tiers.
    header_svg = _build_header(
        opponent_name, position, through_date, game_count,
    )
    legend_svg = _build_legend()

    if confidence_tier == "zero":
        body_svg = (
            _svg_field_outline()
            + _svg_zero_coverage_message()
        )
    else:
        star_x_card, star_y_card = _engine_to_card_xy(
            aggregate["star_x"], aggregate["star_y"],
        )
        bip_count = aggregate["bip_count"]
        # By here, bip_count >= 15 (zero-coverage branch returned above);
        # is_low_confidence == 1 ⇒ thin tier; is_low_confidence == 0 ⇒
        # full tier. The star renderer uses the same boolean as its
        # dashed-ring/thin-caption switch.
        is_thin = bool(aggregate["is_low_confidence"])

        # Perspective-provenance (epic TN-7): the populated-zone
        # coloring and density-bg dots MUST scope to the same
        # perspective the star came from, otherwise cross-perspective
        # rows could leak into the visual layer while the star stays
        # standalone. _query_team_aggregate returned the chosen
        # perspective; thread it through.
        perspective_team_id = aggregate["perspective_team_id"]

        density_svg = ""
        if confidence_tier == "full":
            density_points = _query_density_points(
                conn, team_id, season_id, perspective_team_id,
            )
            density_svg = _svg_density_background(density_points)

        populated_zones = _query_populated_zones(
            conn, team_id, season_id, position, perspective_team_id,
        )

        outliers = _query_outlier_batters(
            conn, team_id, season_id, position, perspective_team_id,
        )

        # Z-order (artifact §B "Z-order stack", back to front):
        #   1. field outline
        #   2. density bg dots
        #   3. textbook dot
        #   4-5. compass letters (discs + text)
        #   6. star (+ thin ring + caption)
        #   7. outlier pills -- drawn LAST so they sit on top of every
        #      decorative layer (AC-5).
        body_parts = [
            _svg_field_outline(),
            density_svg,
            _svg_textbook_dot(position),
            _svg_compass_ring(star_x_card, star_y_card, populated_zones),
            _svg_star(star_x_card, star_y_card, bip_count, is_thin),
            _svg_outlier_pills(star_x_card, star_y_card, outliers),
        ]
        if not outliers:
            body_parts.append(_svg_no_outliers_note())
        body_svg = "".join(body_parts)

    return (
        f'<svg viewBox="0 0 {_CARD_VIEWBOX_W} {_CARD_VIEWBOX_H}" '
        'preserveAspectRatio="xMidYMid meet" '
        'xmlns="http://www.w3.org/2000/svg" '
        'font-family="Arial, Helvetica, sans-serif">'
        f'{header_svg}'
        f'{body_svg}'
        f'{legend_svg}'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Header + legend (rendered inside the SVG for E-229-03; E-229-05's
# template later wraps the SVG and may move these to HTML/CSS instead).
# ---------------------------------------------------------------------------

_HEADER_Y_OPPONENT = 18
_HEADER_Y_POSITION = 42
_HEADER_DIVIDER_Y = 55
_LEGEND_Y = 315


def _position_full_name(position: str) -> str:
    return {
        "LF": "LEFT FIELD",
        "CF": "CENTER FIELD",
        "RF": "RIGHT FIELD",
        "3B": "THIRD BASE",
        "SS": "SHORTSTOP",
        "2B": "SECOND BASE",
    }.get(position, position)


def _build_header(
    opponent_name: str,
    position: str,
    through_date: str,
    game_count: int,
) -> str:
    """Header zone (artifact §C: opponent name + position + coverage cue)."""
    coverage_cue = ""
    if through_date and game_count > 0:
        coverage_cue = format_coverage_cue(through_date, game_count)

    parts = [
        '<g font-family="Arial, Helvetica, sans-serif">',
        f'<text x="6" y="{_HEADER_Y_OPPONENT}" font-size="11pt" '
        f'font-weight="bold" fill="#000">{_xml_escape(opponent_name)}</text>',
        f'<text x="{_CARD_VIEWBOX_W - 6}" y="{_HEADER_Y_OPPONENT}" '
        f'font-size="9pt" fill="#4d4d4d" text-anchor="end">'
        f'{_xml_escape(coverage_cue)}</text>',
        f'<text x="6" y="{_HEADER_Y_POSITION}" font-size="10pt" '
        f'font-weight="bold" fill="#000" letter-spacing="0.04em">'
        f'{_position_full_name(position)}</text>',
        f'<line x1="6" y1="{_HEADER_DIVIDER_Y}" '
        f'x2="{_CARD_VIEWBOX_W - 6}" y2="{_HEADER_DIVIDER_Y}" '
        'stroke="#b3b3b3" stroke-width="0.5"/>',
        '</g>',
    ]
    return "".join(parts)


def _build_legend() -> str:
    """Legend zone (artifact §C: COMPASS_LEGEND_SHORT at 7pt 70% grey)."""
    return (
        f'<line x1="6" y1="{_LEGEND_Y - 8}" '
        f'x2="{_CARD_VIEWBOX_W - 6}" y2="{_LEGEND_Y - 8}" '
        'stroke="#b3b3b3" stroke-width="0.5"/>'
        f'<text x="{_CARD_VIEWBOX_W / 2}" y="{_LEGEND_Y}" '
        f'font-size="7pt" fill="#4d4d4d" text-anchor="middle" '
        f'font-family="Arial, Helvetica, sans-serif">'
        f'{COMPASS_LEGEND_SHORT}</text>'
    )


# ---------------------------------------------------------------------------
# F2a (codex P1 pre-closure triage): compass-key reference card
# ---------------------------------------------------------------------------
#
# The page-4 slot-3 "compass key" is opponent-independent reference
# content: the same 8 zone letters at the same positions on the same
# field outline, with the team-default star centered (so the labels
# are illustrative -- the actual on-card star moves but the labels do
# not). UXD provided exact coordinates lifted from the
# E-229-2b prototype: star at (100, 170); 8 compass discs at full
# 20%-grey opacity; 11pt bold letters; axis annotations DEEP / IN /
# LEFT / RIGHT at the four edges.


def render_compass_key_svg() -> str:
    """Render the page-4 slot-3 "compass key" reference card SVG.

    Returns a complete ``<svg>...</svg>`` element with viewBox
    ``0 0 200 320``, the standard field outline, a centered star at
    ``(100, 170)``, all 8 compass discs A–H at full opacity (no fading
    for unused zones since this is a reference card), and the four
    axis annotations (DEEP / IN / LEFT / RIGHT).

    Opponent-independent — no DB, no per-position context. The bundle
    assembler renders this once per bundle and threads it into the
    cards-template context as ``compass_key_svg``.
    """
    # Star centered for the key (artifact §D + prototype lines 1144-1146).
    star = (
        '<g transform="translate(100, 170)">'
        '<polygon points="0,-8 2.4,-2.6 8,-2.6 3.6,1.2 5.4,7 0,3.4 '
        '-5.4,7 -3.6,1.2 -8,-2.6 -2.4,-2.6" fill="#000"/>'
        '</g>'
    )

    # All 8 compass discs at full opacity (reference card -- no fading).
    # Coordinates lifted from prototype lines 1150-1157.
    disc_radius = 7.5
    zones = (
        ("A",  46, 220),
        ("B",  46, 170),
        ("C",  46, 120),
        ("D", 100, 220),
        ("E", 100, 120),
        ("F", 154, 220),
        ("G", 154, 170),
        ("H", 154, 120),
    )
    disc_parts = ['<g font-size="11" font-weight="bold" '
                  'text-anchor="middle" dominant-baseline="central">']
    for letter, cx, cy in zones:
        disc_parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{disc_radius}" '
            'fill="rgba(0,0,0,0.20)"/>'
            f'<text x="{cx}" y="{cy}" fill="#000">{letter}</text>'
        )
    disc_parts.append('</g>')
    discs = "".join(disc_parts)

    # Axis annotations -- DEEP / IN / LEFT / RIGHT at the four edges.
    # Prototype lines 1161-1166.
    axes = (
        '<g font-size="9" fill="#000" text-anchor="middle" '
        'font-family="Arial, Helvetica, sans-serif">'
        '<text x="100" y="50">DEEP</text>'
        '<text x="100" y="295">IN</text>'
        '<text x="18" y="50" transform="rotate(-90 18 50)">LEFT</text>'
        '<text x="182" y="50" transform="rotate(90 182 50)">RIGHT</text>'
        '</g>'
    )

    return (
        f'<svg viewBox="0 0 {_CARD_VIEWBOX_W} {_CARD_VIEWBOX_H}" '
        'preserveAspectRatio="xMidYMid meet" '
        'xmlns="http://www.w3.org/2000/svg" '
        'font-family="Arial, Helvetica, sans-serif">'
        + _svg_field_outline()
        + star
        + discs
        + axes
        + '</svg>'
    )
