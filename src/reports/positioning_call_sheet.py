"""Coach call sheet renderer (E-229-07).

Produces a single letter-landscape page with a compact matrix:
  * rows = batters, sorted ALPHABETICALLY by name (per coach BC-1 +
    DE B-5 -- no batting_order conditional; team_rosters has no
    batting_order column and player_game_batting.batting_order is
    unpopulated schema. Future work: IDEA-077 boxscore backfill).
  * columns = jersey, name, LF, CF, RF, 3B, SS, 2B, NOTE.

Cells carry a single zone letter (A-H) for outlier batters or a
center-dot (U+00B7 ·) for team-default batters. The NOTE column
displays Tier 2 LLM rationale text when supplied; blank otherwise.

The call sheet is distinct from the prep page (E-229-06) and the
player cards (E-229-05). It is the coach's in-game artifact: scan by
row, yell the two-part call ("#7 - LF Zone B, RF Zone G").

NO flagged-first grouping (per coach BC-1: lineup-card-pairing
constraint forces strict alphabetical ordering on the call sheet).
Flagged-first lives on the prep page.

Public API::

    from src.reports.positioning_call_sheet import render_call_sheet_context

    ctx: dict = render_call_sheet_context(
        conn, public_id="opp-bears",
        season_id="2026-spring-hs",
        opponent_name="Opp Bears", through_date="Apr 12", game_count=8,
        rationales={"player-7": "..."},
    )

The function returns a Jinja-template context dict; the template
``src/api/templates/reports/positioning_call_sheet.html`` consumes it.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from src.reports.positioning import COVERED_POSITIONS
from src.reports.positioning_card import (
    COMPASS_LEGEND_LONG,
    _query_team_id_from_public_id,
    format_coverage_cue,
)

# Center-dot glyph used in matrix cells for team-default (non-outlier)
# entries per AC-2 + epic TN-3. U+00B7 MIDDLE DOT.
_DEFAULT_CELL = "·"


# ---------------------------------------------------------------------------
# Queries (perspective-scoped per epic TN-7)
# ---------------------------------------------------------------------------


def _query_any_aggregate_row(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
) -> dict[str, Any] | None:
    """Pull any one team_position_aggregate row to determine confidence
    tier + the chosen perspective.

    Used for the zero-coverage check (AC-8) and to derive the
    `perspective_team_id` that filters the matrix query (epic TN-7
    perspective-provenance invariant). The standalone perspective
    (`perspective_team_id = team_id`) is preferred; falls back to any
    perspective.
    """
    row = conn.execute(
        """
        SELECT bip_count, is_low_confidence, perspective_team_id
        FROM team_position_aggregate
        WHERE team_id = ? AND season_id = ?
        ORDER BY CASE WHEN perspective_team_id = ? THEN 0 ELSE 1 END,
                 position
        LIMIT 1
        """,
        (team_id, season_id, team_id),
    ).fetchone()
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return dict(row)
    return {
        "bip_count": row[0],
        "is_low_confidence": row[1],
        "perspective_team_id": row[2],
    }


def _query_max_bip_count(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    perspective_team_id: int,
) -> int:
    """Max bip_count across the 6 team_position_aggregate rows.

    Used to detect the zero-coverage state (max < 15). The aggregate
    table denormalizes bip_count to the opponent total per row, so any
    one row suffices; max is defensive in case of partial-reseed edge
    cases.
    """
    row = conn.execute(
        """
        SELECT MAX(bip_count) FROM team_position_aggregate
        WHERE team_id = ? AND season_id = ? AND perspective_team_id = ?
        """,
        (team_id, season_id, perspective_team_id),
    ).fetchone()
    if row is None or row[0] is None:
        return 0
    return int(row[0])


def _query_matrix_rows(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    perspective_team_id: int,
) -> list[dict[str, Any]]:
    """Pivot batter_positioning into one row per batter for the matrix.

    Returns a list of dicts with:
      * ``player_id``
      * ``jersey_number`` (TEXT or NULL via LEFT JOIN team_rosters)
      * ``first_name``, ``last_name``
      * one key per covered position: ``cell_LF``, ``cell_CF``, ..., ``cell_2B``
        — each set to either a zone letter (A-H) or the center-dot glyph.

    The matrix scopes to a single ``perspective_team_id`` per the TN-7
    perspective-provenance invariant -- the caller threads the
    perspective chosen by :func:`_query_any_aggregate_row` so the
    matrix stays internally consistent with the aggregate stars used
    for zero-coverage / no-outliers state inference.
    """
    rows = conn.execute(
        """
        SELECT
            bp.player_id,
            bp.position,
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
        """,
        (team_id, season_id, perspective_team_id),
    ).fetchall()

    by_player: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if isinstance(raw, sqlite3.Row):
            r = dict(raw)
        else:
            r = {
                "player_id": raw[0], "position": raw[1],
                "zone_id": raw[2], "is_thin": raw[3],
                "jersey_number": raw[4],
                "first_name": raw[5], "last_name": raw[6],
            }
        pid = r["player_id"]
        if pid not in by_player:
            by_player[pid] = {
                "player_id": pid,
                "jersey_number": r["jersey_number"],
                "first_name": r["first_name"],
                "last_name": r["last_name"],
                **{f"cell_{p}": _DEFAULT_CELL for p in COVERED_POSITIONS},
                "is_flagged": False,
            }
        position = r["position"]
        # Outlier cell: zone_id present + not thin. Otherwise team-default.
        if r["zone_id"] is not None and not (r["is_thin"] or 0):
            by_player[pid][f"cell_{position}"] = r["zone_id"]
            by_player[pid]["is_flagged"] = True
    return list(by_player.values())


# ---------------------------------------------------------------------------
# Sort + matrix shaping
# ---------------------------------------------------------------------------
#
# Sort policy (per AC-3 + AC-4 + coach BC-1 + DE B-5):
#
#   * Strict alphabetical-by-name.
#   * NO flagged-first partition (lineup-card-pairing logic).
#   * NO batting_order conditional.
#
# Future work for batting-order-driven sort lives in IDEA-077 "Season-modal
# batting order from boxscore backfill"; per DE that becomes its own
# epic if promoted, NOT absorbed into E-229.


def _sort_alphabetical(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strict alphabetical-by-last-name sort. No partitioning.

    Secondary key (jersey) keeps same-last-name batters in a stable
    order; if both jerseys are NULL or non-numeric, last name is the
    sole determinant.
    """
    def _key(row: dict[str, Any]) -> tuple[str, str, str]:
        last = (row.get("last_name") or "").lower()
        first = (row.get("first_name") or "").lower()
        jersey = row.get("jersey_number") or ""
        return (last, first, str(jersey))

    return sorted(rows, key=_key)


def _display_name(row: dict[str, Any]) -> str:
    """Render the NAME column.

    Format: "LAST, First" with last-name uppercased per artifact §E
    typography parity. If last_name is missing, fall back to first
    name or jersey-only display.
    """
    last = (row.get("last_name") or "").upper().strip()
    first = (row.get("first_name") or "").strip()
    if last and first:
        return f"{last}, {first}"
    if last:
        return last
    if first:
        return first
    jersey = row.get("jersey_number")
    if jersey:
        return f"#{jersey}"
    return "(unresolved)"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render_call_sheet_context(
    conn: sqlite3.Connection,
    public_id: str,
    season_id: str,
    *,
    opponent_name: str = "",
    through_date: str = "",
    game_count: int = 0,
    rationales: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the template context dict for the call sheet.

    The returned dict is consumed by
    ``src/api/templates/reports/positioning_call_sheet.html``.

    Args:
        conn: open sqlite3 connection with v2 schema applied.
        public_id: opponent's GameChanger public_id slug.
        season_id: season slug (e.g. ``"2026-spring-hs"``).
        opponent_name: opponent display name for the header.
        through_date: pre-formatted "Mon Day" for the coverage cue
            (E-229-08 supplies this at bundle-generation time).
        game_count: game count at bundle-generation time.
        rationales: optional ``{player_id: rationale_str}`` from
            Tier 2 LLM enrichment (E-229-08 + E-229-09).

    Returns:
        A dict with these top-level keys:
          * ``state``: one of ``"full"``, ``"no_outliers"``,
            ``"zero_coverage"``. The template branches on this.
          * ``header``: dict with ``opponent_name`` and ``coverage_cue``.
          * ``rows``: list of matrix-row dicts (one per batter), in
            alphabetical-by-name order. Empty in the zero-coverage state.
          * ``positions``: tuple of position column keys (LF, CF, RF,
            3B, SS, 2B) — used by the template for the matrix.
          * ``no_outliers_banner``: string when ``state == "no_outliers"``,
            otherwise None.
          * ``compass_legend``: locked ``COMPASS_LEGEND_LONG`` from
            artifact §F.
          * ``rationales``: passed-through dict so the template can
            look up per-row NOTE cell content.

    Raises:
        ValueError: if no team is found for ``public_id``.
    """
    rationales = rationales or {}

    team_id = _query_team_id_from_public_id(conn, public_id)
    if team_id is None:
        raise ValueError(f"No team found for public_id={public_id!r}")

    header = {
        "opponent_name": opponent_name,
        "coverage_cue": (
            format_coverage_cue(through_date, game_count)
            if through_date and game_count > 0 else ""
        ),
    }

    seed = _query_any_aggregate_row(conn, team_id, season_id)
    # Zero-coverage gate (AC-8): no aggregate rows at all, OR all rows
    # below the 15-BIP threshold. The seed query returns the row with
    # the standalone-preferred perspective; we cross-check the max bip
    # in case different positions show different counts (partial
    # reseed edge case).
    if seed is None:
        return _zero_coverage_context(header)

    perspective_team_id = seed["perspective_team_id"]
    max_bip = _query_max_bip_count(
        conn, team_id, season_id, perspective_team_id,
    )
    if max_bip < 15:
        return _zero_coverage_context(header)

    matrix_rows = _query_matrix_rows(
        conn, team_id, season_id, perspective_team_id,
    )

    # Attach display fields each row needs at render time.
    for row in matrix_rows:
        row["display_name"] = _display_name(row)
        row["rationale"] = rationales.get(row["player_id"])

    # Strict alphabetical sort (no flagged-first per coach BC-1).
    sorted_rows = _sort_alphabetical(matrix_rows)

    # State branching: full vs no_outliers per AC-8a.
    has_any_outlier = any(r["is_flagged"] for r in sorted_rows)
    if not has_any_outlier:
        return {
            "state": "no_outliers",
            "header": header,
            "rows": sorted_rows,
            "positions": COVERED_POSITIONS,
            "no_outliers_banner": (
                "No outlier batters this opponent. "
                "Play team default at all positions."
            ),
            "compass_legend": COMPASS_LEGEND_LONG,
            "rationales": rationales,
        }

    return {
        "state": "full",
        "header": header,
        "rows": sorted_rows,
        "positions": COVERED_POSITIONS,
        "no_outliers_banner": None,
        "compass_legend": COMPASS_LEGEND_LONG,
        "rationales": rationales,
    }


def _zero_coverage_context(header: dict[str, str]) -> dict[str, Any]:
    """Build the zero-coverage state context (AC-8).

    Header + dominant message replace the matrix. No legend, no rows,
    no NOTE column.
    """
    return {
        "state": "zero_coverage",
        "header": header,
        "rows": [],
        "positions": COVERED_POSITIONS,
        "no_outliers_banner": None,
        "compass_legend": COMPASS_LEGEND_LONG,
        "rationales": {},
        "zero_coverage_message": (
            "Not enough spray data — play your standard alignment"
        ),
    }
