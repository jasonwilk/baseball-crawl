"""Coach prep page renderer (E-229-06).

Produces a single letter-landscape page showing all 6 position stars +
all outlier batter pills (across all positions) overlaid on one
full-field SVG, with a faint spray-density background and a complete
jersey x position lookup sidebar. The prep page is a coach-facing
pre-game artifact -- distinct from the in-game call sheet (E-229-07)
and the per-position pocket cards (E-229-05).

Public API::

    from src.reports.positioning_prep import render_prep_page_context

    ctx: dict = render_prep_page_context(
        conn, public_id="opp-bears",
        season_id="2026-spring-hs",
        opponent_name="Opp Bears", through_date="Apr 12", game_count=8,
        rationales={"player-7": "..."},
    )

The function returns a Jinja-template context dict; the template
``src/api/templates/reports/positioning_prep.html`` consumes it.

This module reuses several helpers from ``src/reports/positioning_card.py``
(field-SVG primitives, pill projection, collision-jitter logic) per the
E-229-06 story's "May import shared helpers" guidance.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from src.reports.positioning import BASE_POSITIONS, COVERED_POSITIONS
from src.reports.positioning_card import (
    COMPASS_LEGEND_LONG,
    _CARD_VIEWBOX_H,
    _CARD_VIEWBOX_W,
    _PILL_CHAR_WIDTH,
    _PILL_CORNER_RADIUS,
    _PILL_HEIGHT,
    _PILL_MIN_WIDTH,
    _PILL_STROKE_WIDTH,
    _PILL_TEXT_FONT_SIZE_PT,
    _PILL_TEXT_PADDING_X,
    _engine_to_card_xy,
    _jersey_collision_key,
    _jersey_sort_key,
    _pill_anchor_xy,
    _query_density_points,
    _query_team_id_from_public_id,
    _resolve_pill_collisions,
    _svg_density_background,
    _svg_field_outline,
    _svg_star,
    _truncate_last_name,
    _xml_escape,
    format_coverage_cue,
)

# ---------------------------------------------------------------------------
# Prep-page-specific constants
# ---------------------------------------------------------------------------

# Pill text uses the prep-page format `{jersey}-{position}` (no `#`,
# hyphen separator) per artifact §E "Intentional surface-specific
# exceptions" + UXD M-2 lock.
#
# NULL-jersey fallback for prep page is `{initial}-{position}` (e.g.
# "W-RF" for Wilkinson at RF) per artifact §E exception table -- the
# parenthetical `(L. init)` form would read as a "special pill" on the
# dense overlay; the position-suffix structure disambiguates against
# zone-letter syntax.


# ---------------------------------------------------------------------------
# Pill text + position-suffix format (artifact §E exception table)
# ---------------------------------------------------------------------------


def _prep_pill_text(batter: dict[str, Any], position: str) -> str:
    """Build the prep-page pill text per artifact §E exception table.

    Populated jersey: ``{jersey}-{position}`` (e.g. ``7-LF``).
    NULL-jersey: ``{initial}-{position}`` (e.g. ``W-RF``).
    """
    jersey = batter.get("jersey_number")
    last = batter.get("last_name") or ""
    if jersey:
        return f"{jersey}-{position}"
    initial = last[:1].upper() if last else "?"
    return f"{initial}-{position}"


def _prep_pill_width(text: str) -> float:
    """Width budget for a prep-page pill. Prep pills are typically
    shorter (`7-LF` ~4 chars) than per-card (`#7 RAMIR` ~7 chars), so
    the heuristic produces narrower rects. Uses the same per-char
    width and padding as positioning_card to keep visual parity.
    """
    return max(
        _PILL_MIN_WIDTH,
        len(text) * _PILL_CHAR_WIDTH + 2 * _PILL_TEXT_PADDING_X,
    )


# ---------------------------------------------------------------------------
# Queries (perspective-scoped per epic TN-7)
# ---------------------------------------------------------------------------


def _query_all_aggregates(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
) -> dict[str, dict[str, Any]]:
    """Return the 6 team_position_aggregate rows for an opponent.

    Standalone perspective preferred (`perspective_team_id = team_id`);
    falls back to any perspective. Returns a dict keyed on position
    with the chosen `perspective_team_id` included on every row so the
    caller can verify perspective consistency.
    """
    rows = conn.execute(
        """
        SELECT position, star_x, star_y, bip_count, is_low_confidence,
               perspective_team_id
        FROM team_position_aggregate
        WHERE team_id = ? AND season_id = ?
        ORDER BY position,
                 CASE WHEN perspective_team_id = ? THEN 0 ELSE 1 END
        """,
        (team_id, season_id, team_id),
    ).fetchall()
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, sqlite3.Row):
            r = dict(row)
        else:
            r = {
                "position": row[0], "star_x": row[1], "star_y": row[2],
                "bip_count": row[3], "is_low_confidence": row[4],
                "perspective_team_id": row[5],
            }
        # First row per position (ORDER BY position, perspective-preferred)
        # wins; ignore subsequent rows for the same position.
        if r["position"] not in out:
            out[r["position"]] = r
    return out


def _query_all_outliers(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    perspective_team_id: int,
) -> list[dict[str, Any]]:
    """All outlier batter rows across all 6 positions per epic TN-5.

    Returns rows with ``zone_id IS NOT NULL AND is_thin = 0`` joined to
    ``players`` and ``team_rosters``. Scoped to a single
    ``perspective_team_id`` per the TN-7 perspective-provenance
    invariant.
    """
    rows = conn.execute(
        """
        SELECT
            bp.player_id,
            bp.position,
            bp.direction_deviation,
            bp.depth_deviation,
            bp.zone_id,
            bp.is_thin,
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
          AND bp.perspective_team_id = ?
          AND bp.zone_id IS NOT NULL
          AND bp.is_thin = 0
        """,
        (team_id, season_id, perspective_team_id),
    ).fetchall()
    if rows and isinstance(rows[0], sqlite3.Row):
        return [dict(r) for r in rows]
    return [
        {
            "player_id": r[0], "position": r[1],
            "direction_deviation": r[2], "depth_deviation": r[3],
            "zone_id": r[4], "is_thin": r[5],
            "jersey_number": r[6],
            "first_name": r[7], "last_name": r[8],
        }
        for r in rows
    ]


def _query_all_batters_for_sidebar(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    perspective_team_id: int,
) -> list[dict[str, Any]]:
    """Distinct batters (any position, any zone_id, any is_thin) for
    the sidebar lookup. The sidebar shows EVERY batter (one row each)
    with a column per position; cells are zone-letters or `·`.

    Returns one dict per distinct ``(player_id)`` with their roster
    name + jersey number. Per-position zone cells are filled in by
    :func:`_build_sidebar_rows`.
    """
    rows = conn.execute(
        """
        SELECT DISTINCT
            bp.player_id,
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
          AND bp.perspective_team_id = ?
        """,
        (team_id, season_id, perspective_team_id),
    ).fetchall()
    if rows and isinstance(rows[0], sqlite3.Row):
        return [dict(r) for r in rows]
    return [
        {
            "player_id": r[0],
            "jersey_number": r[1],
            "first_name": r[2],
            "last_name": r[3],
        }
        for r in rows
    ]


def _query_zone_grid(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    perspective_team_id: int,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Build a ``(player_id, position) -> {zone_id, is_thin}`` lookup
    for the sidebar's per-position cells.

    Used by :func:`_build_sidebar_rows` to fill in each batter's
    LF/CF/RF/3B/SS/2B cells. Rows with ``zone_id IS NULL`` or
    ``is_thin = 1`` render as the team-default ``·`` glyph.
    """
    rows = conn.execute(
        """
        SELECT player_id, position, zone_id, is_thin
        FROM batter_positioning
        WHERE team_id = ? AND season_id = ?
          AND perspective_team_id = ?
        """,
        (team_id, season_id, perspective_team_id),
    ).fetchall()
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, sqlite3.Row):
            r = dict(row)
        else:
            r = {
                "player_id": row[0], "position": row[1],
                "zone_id": row[2], "is_thin": row[3],
            }
        out[(r["player_id"], r["position"])] = r
    return out


# ---------------------------------------------------------------------------
# SVG fragment builders (prep-page-specific)
# ---------------------------------------------------------------------------


def _svg_position_label(star_x: float, star_y: float, position: str) -> str:
    """Small position label adjacent to each star.

    Per AC-1 + the prep-page's whole-field overlay design: each star
    needs a position tag so the coach can identify which position's
    aggregate landed where (otherwise 6 stars look identical).
    """
    return (
        f'<text x="{star_x + 8:.2f}" y="{star_y - 8:.2f}" '
        'font-size="7pt" font-weight="bold" fill="#4d4d4d" '
        'font-family="Arial, Helvetica, sans-serif">'
        f'{position}</text>'
    )


def _svg_prep_outlier_pills(
    aggregates_by_position: dict[str, dict[str, Any]],
    outliers: list[dict[str, Any]],
) -> str:
    """Render the prep page's outlier pills (all positions on one canvas).

    Each outlier batter row produces ONE pill at its (position-specific
    star + per-position deviation) projection. The same batter at two
    positions produces two pills, both labeled with the per-pill
    position suffix (e.g., ``7-LF`` and ``7-CF``).

    Collision-resolution per epic TN-10: pills landing within ε of one
    another (across positions or within) get deterministic radial
    jitter keyed on jersey number ascending, with position-tag
    ordering as the secondary key (per AC-8).
    """
    if not outliers:
        return ""

    # Project each outlier to its card-space pill anchor.
    # Star coords are stored in engine space; rescale to card space
    # via _engine_to_card_xy, then apply the pill projection
    # `pill_x = star_x + dir_dev * scale_x; pill_y = star_y - depth_dev * scale_y`.
    anchors: list[tuple[float, float, int]] = []
    for outlier in outliers:
        position = outlier["position"]
        agg = aggregates_by_position.get(position)
        if agg is None:
            # No aggregate for this position -- shouldn't happen if the
            # engine ran, but defensively skip the pill.
            continue
        star_x_card, star_y_card = _engine_to_card_xy(
            agg["star_x"], agg["star_y"],
        )
        ax, ay = _pill_anchor_xy(
            star_x_card, star_y_card,
            outlier["direction_deviation"],
            outlier["depth_deviation"],
        )
        # Primary sort key = jersey ascending (collision-resolution
        # ordering per AC-8). Secondary key (position tag ordering) is
        # implicit in the COVERED_POSITIONS order; we encode it as a
        # tiebreaker into the integer collision-sort key by adding the
        # position index.
        jk = _jersey_sort_key(outlier.get("jersey_number"))
        position_index = COVERED_POSITIONS.index(position)
        # Pack jersey_collision_key (range 0..2_000_000) and position
        # index (0..5) into a single int.
        sort_key = _jersey_collision_key(jk) * 10 + position_index
        anchors.append((ax, ay, sort_key))

    if not anchors:
        return ""

    placed = _resolve_pill_collisions(anchors)

    # Emit pills in input order (preserved by _resolve_pill_collisions).
    pieces: list[str] = [
        '<g font-family="Arial, Helvetica, sans-serif" '
        f'font-weight="bold" font-size="{_PILL_TEXT_FONT_SIZE_PT}">'
    ]
    placed_iter = iter(placed)
    for outlier in outliers:
        position = outlier["position"]
        if position not in aggregates_by_position:
            continue
        px, py, _ = next(placed_iter)
        text = _prep_pill_text(outlier, position)
        w = _prep_pill_width(text)
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


def _svg_zero_coverage_message_prep() -> str:
    """Centered dominant message for the zero-coverage state (AC-7)."""
    return (
        f'<text x="{_CARD_VIEWBOX_W / 2}" y="150" '
        'font-size="12pt" font-weight="bold" fill="#000" '
        'text-anchor="middle" '
        'font-family="Arial, Helvetica, sans-serif">'
        'Not enough spray data</text>'
        f'<text x="{_CARD_VIEWBOX_W / 2}" y="170" '
        'font-size="10pt" fill="#4d4d4d" text-anchor="middle" '
        'font-family="Arial, Helvetica, sans-serif">'
        '— play your standard alignment</text>'
    )


def _build_prep_svg(
    aggregates_by_position: dict[str, dict[str, Any]],
    outliers: list[dict[str, Any]],
    density_points: list[tuple[float, float]],
    show_density: bool,
) -> str:
    """Assemble the full prep-page SVG.

    Z-order (matches per-card stack per artifact §B):
      1. field outline
      2. density bg (when show_density)
      3. position-labeled stars (one per covered position)
      4. outlier pills

    The textbook reference dot and compass letter ring are NOT
    rendered on the prep page -- the prep page is an analysis canvas
    showing the team-aggregate stars and individual outliers; the
    textbook dot and compass language carry through on the per-card
    pocket cards (E-229-05).
    """
    parts: list[str] = [_svg_field_outline()]
    if show_density:
        parts.append(_svg_density_background(density_points))

    # Stars + small position labels.
    for position in COVERED_POSITIONS:
        agg = aggregates_by_position.get(position)
        if agg is None:
            continue
        star_x_card, star_y_card = _engine_to_card_xy(
            agg["star_x"], agg["star_y"],
        )
        is_thin = bool(agg["is_low_confidence"])
        parts.append(_svg_star(
            star_x_card, star_y_card,
            agg["bip_count"], is_thin,
        ))
        parts.append(_svg_position_label(star_x_card, star_y_card, position))

    parts.append(_svg_prep_outlier_pills(aggregates_by_position, outliers))

    return (
        f'<svg viewBox="0 0 {_CARD_VIEWBOX_W} {_CARD_VIEWBOX_H}" '
        'preserveAspectRatio="xMidYMid meet" '
        'xmlns="http://www.w3.org/2000/svg" '
        'font-family="Arial, Helvetica, sans-serif">'
        + "".join(parts)
        + '</svg>'
    )


# ---------------------------------------------------------------------------
# Sidebar rows (alphabetical-by-last-name within two partitions)
# ---------------------------------------------------------------------------


def _build_sidebar_rows(
    all_batters: list[dict[str, Any]],
    zone_grid: dict[tuple[str, str], dict[str, Any]],
    rationales: dict[str, str] | None,
) -> list[dict[str, Any]]:
    """Construct the prep-page sidebar lookup rows.

    Per AC-4: two-partition alphabetical-by-last-name sort.
      Partition 1 (flagged): batters with at least one non-`·` cell
        (zone_id IS NOT NULL AND is_thin = 0 at some position).
      Partition 2 (default): all-`·` batters.

    Each row carries:
      * player_id, jersey_number, last_name, first_name
      * cells: list of 6 dicts {position, zone_letter} where
        zone_letter is the A-H letter or '·' for team-default
      * is_flagged: True if at least one cell has a zone letter
      * rationale: optional string from the rationales dict
        (E-229-08 bundle assembler supplies; collapsed slot when None)
      * is_partition_divider: False (the divider is a synthetic
        element inserted by the template once the partitions are
        identified; see ``partition_divider_index`` on the context dict)
    """
    rationales = rationales or {}
    rows: list[dict[str, Any]] = []
    for batter in all_batters:
        cells: list[dict[str, Any]] = []
        is_flagged = False
        for position in COVERED_POSITIONS:
            entry = zone_grid.get((batter["player_id"], position))
            if entry is None or entry["zone_id"] is None or entry["is_thin"]:
                cells.append({"position": position, "zone_letter": "·"})
            else:
                cells.append({
                    "position": position,
                    "zone_letter": entry["zone_id"],
                })
                is_flagged = True
        last = (batter.get("last_name") or "").upper()
        rows.append({
            "player_id": batter["player_id"],
            "jersey_number": batter.get("jersey_number"),
            "first_name": batter.get("first_name"),
            "last_name": last,
            "cells": cells,
            "is_flagged": is_flagged,
            "rationale": rationales.get(batter["player_id"]),
        })

    # Partition + sort.
    flagged = sorted(
        (r for r in rows if r["is_flagged"]),
        key=lambda r: (r["last_name"], _jersey_sort_key(r["jersey_number"])),
    )
    default = sorted(
        (r for r in rows if not r["is_flagged"]),
        key=lambda r: (r["last_name"], _jersey_sort_key(r["jersey_number"])),
    )
    return flagged + default


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render_prep_page_context(
    conn: sqlite3.Connection,
    public_id: str,
    season_id: str,
    *,
    opponent_name: str = "",
    through_date: str = "",
    game_count: int = 0,
    rationales: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the template context dict for the prep page.

    The returned dict is consumed by
    ``src/api/templates/reports/positioning_prep.html``.

    Args:
        conn: open sqlite3 connection with v2 schema applied.
        public_id: opponent's GameChanger public_id slug.
        season_id: season slug (e.g. ``"2026-spring-hs"``).
        opponent_name: opponent display name for the header.
        through_date: pre-formatted "Mon Day" for the coverage cue
            (E-229-08 supplies this at bundle-generation time).
        game_count: game count at bundle-generation time.
        rationales: optional ``{player_id: rationale_str}`` from Tier 2
            LLM enrichment (E-229-08 + E-229-09).

    Returns:
        A dict with these top-level keys:
          * ``state``: one of ``"full"``, ``"no_outliers"``,
            ``"zero_coverage"``. The template branches on this.
          * ``svg``: complete ``<svg>...</svg>`` string for the
            full-field overlay. Empty string in the
            ``zero_coverage`` state where the template renders a
            message instead.
          * ``zero_coverage_svg``: full-field SVG containing the
            "Not enough spray data" message (rendered in place of the
            normal field+sidebar when the team has <15 BIPs).
          * ``header``: dict with ``opponent_name`` and ``coverage_cue``
            (already-formatted via :func:`format_coverage_cue`).
          * ``sidebar_rows``: list of sidebar row dicts; empty list in
            zero-coverage and no-outliers states.
          * ``partition_divider_index``: index into ``sidebar_rows``
            where the flagged/default partition boundary sits. ``None``
            if there's no divider (all rows in one partition or no
            rows at all).
          * ``no_outliers_banner``: present (string) only when
            ``state == "no_outliers"``.
          * ``compass_legend``: the locked-constants ``COMPASS_LEGEND_LONG``
            (artifact §F + AC-2's cross-artifact typography parity).
    """
    rationales = rationales or {}

    team_id = _query_team_id_from_public_id(conn, public_id)
    if team_id is None:
        raise ValueError(f"No team found for public_id={public_id!r}")

    aggregates = _query_all_aggregates(conn, team_id, season_id)

    # Header is built once for every state.
    header = {
        "opponent_name": opponent_name,
        "coverage_cue": (
            format_coverage_cue(through_date, game_count)
            if through_date and game_count > 0 else ""
        ),
    }

    # Zero-coverage: per AC-7 -- when team has 0-14 BIPs (any
    # aggregate row's bip_count < 15, OR no rows at all), render the
    # dominant message in place of the field+sidebar.
    if not aggregates or all(
        a["bip_count"] < 15 for a in aggregates.values()
    ):
        return {
            "state": "zero_coverage",
            "svg": "",
            "zero_coverage_svg": (
                f'<svg viewBox="0 0 {_CARD_VIEWBOX_W} {_CARD_VIEWBOX_H}" '
                'preserveAspectRatio="xMidYMid meet" '
                'xmlns="http://www.w3.org/2000/svg">'
                + _svg_zero_coverage_message_prep()
                + '</svg>'
            ),
            "header": header,
            "sidebar_rows": [],
            "partition_divider_index": None,
            "no_outliers_banner": None,
            "compass_legend": COMPASS_LEGEND_LONG,
        }

    # Both no-outliers and full states need a consistent perspective.
    # Use the perspective the first aggregate row resolved to (every
    # row in `aggregates` has the same perspective due to ORDER BY).
    perspective_team_id = next(iter(aggregates.values()))["perspective_team_id"]
    # Engine writes all 6 positions atomically per perspective (epic
    # TN-6 atomicity invariant). Verify so a pathological partial-reseed
    # scenario where different positions resolve to different
    # perspectives fails loudly here rather than silently dropping the
    # other positions' data from the downstream perspective-scoped
    # queries.
    assert all(
        a["perspective_team_id"] == perspective_team_id
        for a in aggregates.values()
    ), (
        "team_position_aggregate rows span multiple perspectives — "
        "engine atomicity invariant (epic TN-6) violated"
    )

    outliers = _query_all_outliers(
        conn, team_id, season_id, perspective_team_id,
    )

    # Density-bg gate: per AC-3, hidden when is_low_confidence = 1 for
    # ALL 6 rows. Show when ANY row has is_low_confidence = 0.
    show_density = any(
        not a["is_low_confidence"] for a in aggregates.values()
    )
    density_points: list[tuple[float, float]] = []
    if show_density:
        density_points = _query_density_points(
            conn, team_id, season_id, perspective_team_id,
        )

    # Build the sidebar regardless of outlier count.
    all_batters = _query_all_batters_for_sidebar(
        conn, team_id, season_id, perspective_team_id,
    )
    zone_grid = _query_zone_grid(
        conn, team_id, season_id, perspective_team_id,
    )
    sidebar_rows = _build_sidebar_rows(all_batters, zone_grid, rationales)
    flagged_count = sum(1 for r in sidebar_rows if r["is_flagged"])
    if 0 < flagged_count < len(sidebar_rows):
        partition_divider_index = flagged_count
    else:
        partition_divider_index = None

    # No-outliers state (AC-7a): ≥15 BIPs but zero non-thin non-NULL
    # zone batters. Field + stars + density render normally; pills
    # don't render; sidebar shows the banner.
    if not outliers:
        return {
            "state": "no_outliers",
            "svg": _build_prep_svg(
                aggregates, [], density_points, show_density,
            ),
            "zero_coverage_svg": "",
            "header": header,
            "sidebar_rows": sidebar_rows,
            "partition_divider_index": partition_divider_index,
            "no_outliers_banner": (
                "No outlier batters this opponent. "
                "Play team default at all positions."
            ),
            "compass_legend": COMPASS_LEGEND_LONG,
        }

    # Full state.
    return {
        "state": "full",
        "svg": _build_prep_svg(
            aggregates, outliers, density_points, show_density,
        ),
        "zero_coverage_svg": "",
        "header": header,
        "sidebar_rows": sidebar_rows,
        "partition_divider_index": partition_divider_index,
        "no_outliers_banner": None,
        "compass_legend": COMPASS_LEGEND_LONG,
    }
