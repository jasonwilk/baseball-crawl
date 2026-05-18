"""E-229-08: Defensive positioning bundle assembler.

Renders a single 4-page mixed-orientation HTML bundle for one opponent:

* **Page 1**: Coach in-game call sheet (letter landscape) — via
  :func:`src.reports.positioning_call_sheet.render_call_sheet_context`
* **Page 2**: Coach pre-game prep page (letter landscape) — via
  :func:`src.reports.positioning_prep.render_prep_page_context`
* **Page 3**: 4-up player cards portrait — LF / CF / RF / 3B — via the
  per-position SVGs from
  :func:`src.reports.positioning_card.render_field_svg` plus the
  E-229-05 cards template context built locally
* **Page 4**: 4-up player cards portrait — SS / 2B / compass-key /
  opponent-context-card (slot fill per E-229-05 AC-9 + UXD I-2)

All four pages cite the same coverage cue computed once at
bundle-generation time and threaded into each page's template
context. Per AC-4a the cue is captured AT the moment the bundle is
rendered — the rendered HTML carries the value directly, so re-viewing
the same artifact shows the same cue (no live-data recomputation).

Tier 2 LLM render-time threading (AC-7 / AC-8): for each flagged batter
(``zone_id IS NOT NULL AND is_thin = 0``), the assembler calls
:func:`src.reports.positioning_llm.generate_rationale` and threads the
returned ``Optional[str]`` into the template context. NO INSERT or
UPDATE statements are issued against ``batter_positioning`` or
``team_position_aggregate`` from this module — rationales live only in
the rendered HTML.
"""

from __future__ import annotations

import datetime
import logging
import sqlite3
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from src.llm.openrouter import is_llm_available
from src.reports.positioning import (
    COVERED_POSITIONS,
    PerPositionRow,
    TeamAggregateRow,
)
from src.reports.positioning_call_sheet import render_call_sheet_context
from src.reports.positioning_card import (
    COMPASS_LEGEND_LONG,
    _query_team_aggregate,
    _query_team_id_from_public_id,
    render_compass_key_svg,
    render_field_svg,
)
from src.reports.positioning_llm import generate_rationale
from src.reports.positioning_prep import render_prep_page_context

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "api" / "templates"
_TEMPLATE_NAME = "reports/positioning_bundle.html"

# Slot fill for page 4 (per E-229-05 AC-9 + epic TN-12 lock — was
# `blank | blank` in the prior draft).
_PAGE_4_SLOT_3 = "compass-key"
_PAGE_4_SLOT_4 = "opponent-context-card"


def _build_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )


# ---------------------------------------------------------------------------
# LLM rationale threading (AC-7)
# ---------------------------------------------------------------------------


def _query_flagged_batters_with_aggregate(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
) -> list[dict[str, Any]]:
    """Flagged (outlier) batter rows joined with their per-position team
    aggregate.

    Returns one dict per ``(player_id, position)`` pair where
    ``zone_id IS NOT NULL AND is_thin = 0``. Each dict carries the
    batter's per-position row fields, the team-aggregate fields for
    the same position, and player+roster identity. Used to build the
    LLM-input contract per E-229-09 AC-1.

    Perspective-provenance (epic TN-7): the join scopes to the
    standalone-preferred perspective (``perspective_team_id =
    team_id``) when available, with fallback to any perspective.
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
            bp.bip_count       AS batter_bip_count,
            bp.hr_count,
            bp.perspective_team_id,
            tpa.star_x,
            tpa.star_y,
            tpa.bip_count      AS team_bip_count,
            tpa.is_low_confidence,
            p.first_name,
            p.last_name,
            tr.jersey_number
        FROM batter_positioning bp
        JOIN players p USING (player_id)
        LEFT JOIN team_rosters tr
            ON  tr.player_id = bp.player_id
            AND tr.team_id   = bp.team_id
            AND tr.season_id = bp.season_id
        JOIN team_position_aggregate tpa
            ON  tpa.team_id              = bp.team_id
            AND tpa.season_id            = bp.season_id
            AND tpa.perspective_team_id  = bp.perspective_team_id
            AND tpa.position             = bp.position
        WHERE bp.team_id = ?
          AND bp.season_id = ?
          AND bp.zone_id IS NOT NULL
          AND bp.is_thin = 0
        ORDER BY
          CASE WHEN bp.perspective_team_id = ? THEN 0 ELSE 1 END,
          bp.player_id, bp.position
        """,
        (team_id, season_id, team_id),
    ).fetchall()
    return [dict(r) for r in rows]


def _build_rationales(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    *,
    opponent_name: str,
    coverage_cue: str,
) -> dict[str, str]:
    """Generate rationales for all flagged batters at render time.

    Returns a dict ``{player_id: rationale_str}``. Per AC-7: when the
    LLM is unavailable the function returns an empty dict (no calls
    made; INFO log already emitted by :func:`generate_rationale`). Per
    AC-3 + AC-7 non-fatal contract: per-batter try/except so one
    batter's failure doesn't take out the rest of the lineup.

    Per AC-8 the function issues ZERO INSERT/UPDATE — the dict lives
    only in render-pass memory.

    Each flagged batter may have multiple flagged positions; we
    rationalize against the FIRST flagged position the query returns
    (jersey-ascending tiebreak via ORDER BY). One rationale per
    player_id is what the call-sheet NOTE column and the prep-page
    sidebar both expect.
    """
    if not is_llm_available():
        logger.info(
            "Tier 2 LLM unavailable for bundle assembly (team_id=%d, "
            "season_id=%s) -- bundle renders without rationales.",
            team_id, season_id,
        )
        return {}

    rationales: dict[str, str] = {}
    seen_players: set[str] = set()
    rows = _query_flagged_batters_with_aggregate(conn, team_id, season_id)
    for row in rows:
        player_id = row["player_id"]
        if player_id in seen_players:
            continue
        seen_players.add(player_id)

        batter_row = PerPositionRow(
            position=row["position"],
            direction_deviation=row["direction_deviation"],
            depth_deviation=row["depth_deviation"],
            zone_id=row["zone_id"],
            is_thin=row["is_thin"],
            bip_count=row["batter_bip_count"],
            hr_count=row["hr_count"] or 0,
        )
        aggregate_row = TeamAggregateRow(
            position=row["position"],
            star_x=row["star_x"],
            star_y=row["star_y"],
            bip_count=row["team_bip_count"],
            is_low_confidence=row["is_low_confidence"],
        )
        metadata = {
            "jersey_number": row["jersey_number"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "opponent_name": opponent_name,
            "coverage_cue": coverage_cue,
        }
        try:
            rationale = generate_rationale(batter_row, aggregate_row, metadata)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Tier 2 LLM rationale generation failed for player_id=%s "
                "(non-fatal); bundle renders without rationale for this batter.",
                player_id, exc_info=True,
            )
            continue
        if rationale:
            rationales[player_id] = rationale
    return rationales


# ---------------------------------------------------------------------------
# Per-position card-page context (E-229-05 cards template)
# ---------------------------------------------------------------------------


def _choose_perspective_team_id(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
) -> int | None:
    """Pick the canonical perspective for an opponent's positioning data.

    Mirrors the prefer-then-fallback shape used in
    :func:`src.reports.positioning_card._query_team_aggregate`,
    :func:`src.reports.positioning_call_sheet._query_any_aggregate_row`,
    and :func:`src.reports.positioning_prep._query_all_aggregates`:

    1. Prefer the standalone perspective (``perspective_team_id =
       team_id``).
    2. Fall back to any other perspective when standalone is absent
       (e.g., opponents scouted only from the member team's
       perspective).

    Per epic TN-7 the chosen perspective MUST be threaded into all
    downstream queries scoped to the same render pass so no rendered
    artifact mixes data from different perspectives. F3 (codex P2)
    triage: the prior hard-filter on ``perspective_team_id = team_id``
    in :func:`_query_cards_positioning_rows` left the cards section
    empty for opponents with only non-standalone perspectives (call
    sheet + prep page already used the prefer-then-fallback pattern;
    cards was the asymmetric outlier).

    Returns ``None`` when no aggregate rows exist for the opponent at
    all (zero-coverage case).
    """
    row = conn.execute(
        """
        SELECT perspective_team_id
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
        return row["perspective_team_id"]
    return row[0]


def _query_cards_positioning_rows(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
) -> list[dict[str, Any]]:
    """Query the v2 batter_positioning rows shape the cards template
    context builder expects.

    Mirrors :func:`src.reports.generator._query_batter_positioning` but
    is duplicated here so the bundle module does not import from the
    generator (avoids the circular-import path through the larger
    scouting-report machinery).

    F3 (codex P2 pre-closure triage): uses
    :func:`_choose_perspective_team_id` for the prefer-then-fallback
    perspective derivation, matching the sibling render-helper shape
    in card/call-sheet/prep modules. The prior implementation hard-
    filtered on ``perspective_team_id = team_id`` and left the cards
    section empty for opponents with only non-standalone perspectives.
    """
    perspective_team_id = _choose_perspective_team_id(
        conn, team_id, season_id,
    )
    if perspective_team_id is None:
        return []
    rows = conn.execute(
        """
        SELECT
            bp.player_id,
            bp.position,
            bp.direction_deviation,
            bp.depth_deviation,
            bp.zone_id,
            bp.bip_count,
            bp.hr_count,
            bp.is_thin,
            p.first_name,
            p.last_name,
            tr.jersey_number
        FROM batter_positioning bp
        JOIN players p ON p.player_id = bp.player_id
        LEFT JOIN team_rosters tr
            ON  tr.player_id = bp.player_id
            AND tr.team_id   = bp.team_id
            AND tr.season_id = bp.season_id
        WHERE bp.team_id = ?
          AND bp.season_id = ?
          AND bp.perspective_team_id = ?
        ORDER BY bp.player_id, bp.position
        """,
        (team_id, season_id, perspective_team_id),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# F2 (codex P1 pre-closure triage): page-4 slot-3 + slot-4 content
# ---------------------------------------------------------------------------


_TIER_COPY: dict[str, str] = {
    "Full": (
        "outlier markers and density background render on all 6 "
        "position cards."
    ),
    "Thin": (
        "outlier markers render with thin-tier indicators; no density "
        "background."
    ),
    "Zero": (
        "not enough spray data; cards show 'play standard alignment'."
    ),
}


def _season_label(season_id: str) -> str:
    """Render a coach-facing label for a season slug.

    Best-effort conversion: ``"2026-spring-hs"`` -> ``"2026 Spring HS"``.
    Falls back to the raw slug on unfamiliar shapes.
    """
    if not season_id:
        return ""
    parts = season_id.split("-")
    if len(parts) < 2:
        return season_id
    year = parts[0]
    rest = " ".join(p.capitalize() if len(p) > 2 else p.upper() for p in parts[1:])
    return f"{year} {rest}"


def _coverage_tier(bip_count: int, is_low_confidence: int) -> str:
    """Tier-classify a team aggregate row per epic TN-4.

    Returns one of ``"Full"``, ``"Thin"``, ``"Zero"``. Branching mirrors
    the rule sketched in the F2 spec:
      * ``bip_count >= 50`` AND ``is_low_confidence = 0`` -> Full
      * ``15 <= bip_count < 50`` (or low_confidence with >= 15) -> Thin
      * ``bip_count < 15`` -> Zero
    """
    if bip_count >= 50 and not is_low_confidence:
        return "Full"
    if bip_count >= 15:
        return "Thin"
    return "Zero"


def _query_next_game_date(
    conn: sqlite3.Connection,
    opponent_team_id: int,
    our_team_id: int,
    today: str,
) -> str | None:
    """Earliest upcoming game date between the opponent and our team.

    Returns the ISO date string (``YYYY-MM-DD``) of the first scheduled
    game after ``today``, or ``None`` if no such game exists. Used for
    the opponent-context-card "vs. {our_team_name} {next_game_date}"
    suffix; degrades gracefully when there is no upcoming game.
    """
    row = conn.execute(
        """
        SELECT game_date
        FROM games
        WHERE (
            (home_team_id = ? AND away_team_id = ?)
            OR (home_team_id = ? AND away_team_id = ?)
        )
          AND game_date > ?
        ORDER BY game_date ASC
        LIMIT 1
        """,
        (opponent_team_id, our_team_id, our_team_id, opponent_team_id, today),
    ).fetchone()
    if row is None:
        return None
    return row[0] if not isinstance(row, sqlite3.Row) else row["game_date"]


def _query_team_record(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
) -> str:
    """Return the opponent's record formatted as ``"W-L"`` (or ``"—"``
    when there are no completed games)."""
    row = conn.execute(
        """
        SELECT
            SUM(CASE
                WHEN home_team_id = :tid AND home_score > away_score THEN 1
                WHEN away_team_id = :tid AND away_score > home_score THEN 1
                ELSE 0
            END) AS wins,
            SUM(CASE
                WHEN home_team_id = :tid AND home_score < away_score THEN 1
                WHEN away_team_id = :tid AND away_score < home_score THEN 1
                ELSE 0
            END) AS losses
        FROM games
        WHERE season_id = :season_id
          AND (home_team_id = :tid OR away_team_id = :tid)
          AND home_score IS NOT NULL AND away_score IS NOT NULL
        """,
        {"tid": team_id, "season_id": season_id},
    ).fetchone()
    if row is None or row[0] is None:
        return "—"
    return f"{int(row[0])}–{int(row[1])}"


def _query_runs_per_game(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
) -> tuple[str, str]:
    """Return formatted runs-scored and runs-allowed per game as a
    pair of strings (each rounded to one decimal, or ``"—"`` when
    there are no completed games).
    """
    row = conn.execute(
        """
        SELECT
            AVG(CASE WHEN home_team_id = :tid THEN home_score
                     ELSE away_score END) AS avg_scored,
            AVG(CASE WHEN home_team_id = :tid THEN away_score
                     ELSE home_score END) AS avg_allowed
        FROM games
        WHERE season_id = :season_id
          AND (home_team_id = :tid OR away_team_id = :tid)
          AND home_score IS NOT NULL AND away_score IS NOT NULL
        """,
        {"tid": team_id, "season_id": season_id},
    ).fetchone()
    if row is None or row[0] is None:
        return "—", "—"
    return f"{row[0]:.1f}", f"{row[1]:.1f}"


def _query_team_bip_count(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    perspective_team_id: int,
) -> int:
    """Return the opponent's team-aggregate BIP count (any position
    carries the same value per ``_compute_team_aggregate``).

    Falls back to 0 when no aggregate rows exist.
    """
    row = conn.execute(
        """
        SELECT bip_count FROM team_position_aggregate
        WHERE team_id = ? AND season_id = ? AND perspective_team_id = ?
        ORDER BY position
        LIMIT 1
        """,
        (team_id, season_id, perspective_team_id),
    ).fetchone()
    if row is None:
        return 0
    return int(row[0]) if not isinstance(row, sqlite3.Row) else int(row["bip_count"])


def _query_team_low_confidence(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    perspective_team_id: int,
) -> int:
    """Returns the opponent's ``is_low_confidence`` flag (any position;
    the engine writes the same value across all 6 rows). Returns 0
    when no aggregate rows exist."""
    row = conn.execute(
        """
        SELECT is_low_confidence FROM team_position_aggregate
        WHERE team_id = ? AND season_id = ? AND perspective_team_id = ?
        ORDER BY position
        LIMIT 1
        """,
        (team_id, season_id, perspective_team_id),
    ).fetchone()
    if row is None:
        return 0
    return int(row[0]) if not isinstance(row, sqlite3.Row) else int(row["is_low_confidence"])


def _query_team_name(
    conn: sqlite3.Connection,
    team_id: int,
) -> str:
    """Return ``teams.name`` for a given team_id, or an empty string
    when the row is missing."""
    row = conn.execute(
        "SELECT name FROM teams WHERE id = ?", (team_id,),
    ).fetchone()
    if row is None:
        return ""
    return row[0] if not isinstance(row, sqlite3.Row) else row["name"]


def _build_opponent_context(
    conn: sqlite3.Connection,
    *,
    team_id: int,
    season_id: str,
    perspective_team_id: int,
    game_count: int,
    today: str | None = None,
) -> dict[str, Any]:
    """Build the page-4 slot-3 + slot-4 context payload.

    Returns a dict with the four template-context keys the renderer
    forwards to the cards template:
      * ``compass_key_svg`` -- reference card SVG (F2a)
      * ``opponent_context_coverage_line`` -- season label + game
        count + "vs. {our_team} {next_game}" suffix
      * ``opponent_context_stats`` -- 4-row label/value list
        (Record / Runs per game / Runs allowed per game / Team BIPs)
      * ``opponent_context_tier_line`` -- "Coverage tier: {tier} —
        {tier-copy}" per the locked tier descriptions

    Args:
        conn: Open sqlite3 connection with v2 schema applied.
        team_id: The opponent team's integer PK.
        season_id: Season slug (e.g. ``"2026-spring-hs"``).
        perspective_team_id: The chosen perspective for THIS render
            pass (per F3 prefer-then-fallback); used to look up the
            opponent's BIP count + low-confidence flag from
            ``team_position_aggregate``.
        game_count: Game count at bundle-generation time (caller-
            supplied; matches the coverage-cue snapshot).
        today: ISO date string (``YYYY-MM-DD``) for the "no upcoming
            game" comparison. Defaults to UTC today. Tests inject a
            fixed value for determinism.
    """
    if today is None:
        today = datetime.date.today().isoformat()

    # Slot 3: compass key SVG (opponent-independent reference card).
    compass_key_svg = render_compass_key_svg()

    # Slot 4: coverage line.
    season_label = _season_label(season_id)
    our_team_name = _query_team_name(conn, perspective_team_id)
    next_game = _query_next_game_date(
        conn,
        opponent_team_id=team_id,
        our_team_id=perspective_team_id,
        today=today,
    )
    parts: list[str] = []
    if season_label:
        parts.append(season_label)
    games_word = "game" if game_count == 1 else "games"
    parts.append(f"{game_count} {games_word}")
    if our_team_name:
        if next_game:
            parts.append(f"vs. {our_team_name} {next_game}")
        else:
            # Graceful degradation: omit trailing date.
            parts.append(f"vs. {our_team_name}")
    coverage_line = " · ".join(parts)

    # Slot 4: stats list (4 rows in fixed order).
    record = _query_team_record(conn, team_id, season_id)
    rs_pg, ra_pg = _query_runs_per_game(conn, team_id, season_id)
    team_bip = _query_team_bip_count(
        conn, team_id, season_id, perspective_team_id,
    )
    bip_value = str(team_bip) if team_bip > 0 else "—"
    stats = [
        {"label": "Record",                "value": record},
        {"label": "Runs / game",           "value": rs_pg},
        {"label": "Runs allowed / game",   "value": ra_pg},
        {"label": "Team BIPs",             "value": bip_value},
    ]

    # Slot 4: tier line.
    low_conf = _query_team_low_confidence(
        conn, team_id, season_id, perspective_team_id,
    )
    tier = _coverage_tier(team_bip, low_conf)
    tier_line = f"Coverage tier: {tier} — {_TIER_COPY[tier]}"

    return {
        "compass_key_svg": compass_key_svg,
        "opponent_context_coverage_line": coverage_line,
        "opponent_context_stats": stats,
        "opponent_context_tier_line": tier_line,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def generate_positioning_bundle(
    conn: sqlite3.Connection,
    public_id: str,
    season_id: str,
    *,
    opponent_name: str = "",
    through_date: str = "",
    game_count: int = 0,
) -> str:
    """Render the 4-page positioning bundle HTML for one opponent.

    AC-1: returns a complete HTML document containing four sections in
    order — call sheet (landscape), prep page (landscape), cards page
    1 (portrait LF/CF/RF/3B), cards page 2 (portrait
    SS/2B/compass-key/opponent-context-card).

    AC-4a: the coverage-cue inputs (``through_date``, ``game_count``)
    are captured at this call site by the caller. The returned HTML
    embeds the cue verbatim — re-rendering the bundle from disk shows
    the same cue (no live-data recomputation).

    AC-5: zero-coverage degradation handled by the per-section render
    helpers — the bundle always returns 4 pages, even when each page
    is in its zero-coverage state.

    AC-7: the LLM rationale step iterates flagged batters and threads
    the result into the call-sheet + prep-page contexts. LLM
    unavailable / failure leaves an empty dict; the bundle still
    renders.

    AC-8: this function issues ZERO INSERT/UPDATE statements against
    ``batter_positioning`` or ``team_position_aggregate``. Rationales
    live only in the rendered HTML.

    Args:
        conn: Open sqlite3 connection with v2 schema applied.
        public_id: Opponent's GameChanger public_id slug.
        season_id: Season slug (e.g. ``"2026-spring-hs"``).
        opponent_name: Opponent display name for page headers.
        through_date: Pre-formatted "Mon Day" string for coverage cue.
        game_count: Game count at bundle-generation time.

    Returns:
        Complete HTML document string ready to write to
        ``data/reports/{slug}/index.html``.

    Raises:
        ValueError: if no team is found for ``public_id``.
    """
    # Production callers open the connection via
    # ``src.api.db.get_connection()``, which does NOT set a row_factory
    # -- rows come back as plain tuples. This module and its siblings
    # (``positioning_card``, ``positioning_prep``) call ``dict(r)`` on
    # query results, which requires ``sqlite3.Row``. Tests already set
    # ``conn.row_factory = sqlite3.Row`` via fixtures; production did
    # not, which raised ``ValueError: dictionary update sequence element
    # #0 has length N; 2 is required`` during bundle render. Setting
    # row_factory here propagates to all sibling render helpers because
    # they share the same ``conn`` -- the bundle is their sole entry
    # point. Scope is intentionally local to avoid the wider blast
    # radius of changing ``get_connection()`` (other callers index by
    # position, e.g., ``row[0]``).
    conn.row_factory = sqlite3.Row

    # Resolve team_id once at the top so we can fail fast on bad
    # public_id and share the resolution with the LLM-rationale query.
    team_id = _query_team_id_from_public_id(conn, public_id)
    if team_id is None:
        raise ValueError(f"No team found for public_id={public_id!r}")

    # Coverage-cue snapshot (AC-4a): captured once here from the
    # caller-supplied inputs. Threaded identically into all four pages.
    coverage_cue = ""
    if through_date and game_count > 0:
        from src.reports.positioning_card import format_coverage_cue
        coverage_cue = format_coverage_cue(through_date, game_count)

    # ------------------------------------------------------------------
    # Tier 2 LLM rationales (AC-7) — render-time only, no DB persistence
    # ------------------------------------------------------------------
    rationales = _build_rationales(
        conn, team_id, season_id,
        opponent_name=opponent_name,
        coverage_cue=coverage_cue,
    )

    # ------------------------------------------------------------------
    # Page 1: call sheet
    # ------------------------------------------------------------------
    call_sheet_ctx = render_call_sheet_context(
        conn, public_id, season_id,
        opponent_name=opponent_name,
        through_date=through_date,
        game_count=game_count,
        rationales=rationales,
    )

    # ------------------------------------------------------------------
    # Page 2: prep page
    # ------------------------------------------------------------------
    prep_ctx = render_prep_page_context(
        conn, public_id, season_id,
        opponent_name=opponent_name,
        through_date=through_date,
        game_count=game_count,
        rationales=rationales,
    )

    # ------------------------------------------------------------------
    # Pages 3-4: cards (per-position SVGs + cards-template context)
    # ------------------------------------------------------------------
    per_card_svgs: dict[str, str] = {}
    for position in COVERED_POSITIONS:
        try:
            per_card_svgs[position] = render_field_svg(
                conn, public_id, position, season_id,
                opponent_name=opponent_name,
                through_date=through_date,
                game_count=game_count,
            )
        except Exception:  # noqa: BLE001
            # Per-card failure is non-fatal: the card slot renders
            # empty; the rest of the bundle still ships.
            logger.warning(
                "Card SVG render failed for position=%s (non-fatal); "
                "bundle continues with empty card slot.",
                position, exc_info=True,
            )
            per_card_svgs[position] = ""

    # Use renderer.py's existing v2 context-builder for the cards
    # template; it owns the row->card bucketing + sidebar truncation
    # rules already exercised by E-229-05 tests.
    from src.reports.renderer import _build_positioning_context
    positioning_rows = _query_cards_positioning_rows(
        conn, team_id, season_id,
    )

    # F2 (codex P1 pre-closure triage): page-4 slot-3 (compass key) +
    # slot-4 (opponent context) per E-229-05 AC-9 + epic TN-12 slot-fill
    # lock. Derive the chosen perspective once via the same prefer-then-
    # fallback helper that drives the cards-row query (F3 alignment), so
    # the opponent-context stats scope to the same perspective shown in
    # the cards above. When no perspective is available (zero-coverage),
    # we skip the F2 payload and the slots fall back to their empty
    # template defaults.
    f2_context: dict[str, Any] = {}
    chosen_perspective = _choose_perspective_team_id(
        conn, team_id, season_id,
    )
    if chosen_perspective is not None:
        try:
            f2_context = _build_opponent_context(
                conn,
                team_id=team_id,
                season_id=season_id,
                perspective_team_id=chosen_perspective,
                game_count=game_count,
            )
        except Exception:  # noqa: BLE001
            # Non-fatal: F2 payload is a render enhancement, not a
            # bundle-blocker. The slots render their template defaults
            # (empty compass-key slot + bare opponent-context header).
            logger.warning(
                "F2 opponent-context payload failed for team_id=%d "
                "(non-fatal); page 4 slots 3-4 render bare defaults.",
                team_id, exc_info=True,
            )

    cards_ctx = _build_positioning_context(
        positioning_rows,
        positioning_rationales=rationales,
        per_card_svgs=per_card_svgs,
        opponent_name=opponent_name,
        coverage_cue=coverage_cue,
        compass_key_svg=f2_context.get("compass_key_svg", ""),
        opponent_context_coverage_line=f2_context.get(
            "opponent_context_coverage_line", "",
        ),
        opponent_context_stats=f2_context.get("opponent_context_stats", []),
        opponent_context_tier_line=f2_context.get(
            "opponent_context_tier_line", "",
        ),
    )

    # ------------------------------------------------------------------
    # Bundle assembly
    # ------------------------------------------------------------------
    env = _build_jinja_env()
    template = env.get_template(_TEMPLATE_NAME)
    return template.render(
        call_sheet=call_sheet_ctx,
        positioning_prep=prep_ctx,
        positioning=cards_ctx,
        opponent_name=opponent_name,
        coverage_cue=coverage_cue,
        compass_legend_long=COMPASS_LEGEND_LONG,
        page_4_slot_3=_PAGE_4_SLOT_3,
        page_4_slot_4=_PAGE_4_SLOT_4,
    )
