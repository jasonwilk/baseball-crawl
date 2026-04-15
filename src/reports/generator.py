"""Report generation pipeline for standalone scouting reports.

Orchestrates the full lifecycle: URL parsing, team creation, scouting crawl/load,
stats query, HTML rendering, and file storage. Each generation creates a new
``reports`` row with a unique slug.

Public API::

    from src.reports.generator import generate_report

    result = generate_report("https://web.gc.com/teams/abc123/some-team")
    if result.success:
        print(result.slug, result.url)
    else:
        print(result.error_message)
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from src.api.db import (
    build_pitcher_profiles,
    get_connection,
    get_pitching_history,
    get_pitching_workload,
)
from src.db.teams import ensure_team_row
from src.gamechanger.client import CredentialExpiredError, GameChangerClient
from src.gamechanger.crawlers.scouting import ScoutingCrawler
from src.gamechanger.crawlers.scouting_spray import ScoutingSprayChartCrawler
from src.gamechanger.loaders import derive_season_id_for_team
from src.gamechanger.loaders.plays_loader import PlaysLoader
from src.gamechanger.loaders.scouting_loader import ScoutingLoader
from src.gamechanger.loaders.scouting_spray_loader import ScoutingSprayChartLoader
from src.gamechanger.types import TeamRef
from src.gamechanger.url_parser import parse_team_url
from src.reconciliation.engine import reconcile_game
from src.reports.renderer import render_report

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPORTS_DIR = _REPO_ROOT / "data" / "reports"
_EXPIRY_DAYS = 14
_APP_URL_DEFAULT = "http://localhost:8001"
_SEARCH_CONTENT_TYPE = "application/vnd.gc.com.post_search+json; version=0.0.0"
_PLAYS_ACCEPT = "application/vnd.gc.com.event_plays+json; version=0.0.0"


@dataclass
class GenerationResult:
    """Result of a report generation attempt."""

    success: bool
    slug: str | None = None
    title: str | None = None
    url: str | None = None
    error_message: str | None = None


def _get_base_url() -> str:
    """Return the base URL for public report links."""
    return os.environ.get("APP_URL", _APP_URL_DEFAULT).rstrip("/")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _create_report_row(
    conn: sqlite3.Connection,
    slug: str,
    team_id: int,
    title: str,
    generated_at: str,
    expires_at: str,
) -> int:
    """Insert a new reports row with status='generating'. Returns the row id."""
    cursor = conn.execute(
        """
        INSERT INTO reports (slug, team_id, title, status, generated_at, expires_at)
        VALUES (?, ?, ?, 'generating', ?, ?)
        """,
        (slug, team_id, title, generated_at, expires_at),
    )
    conn.commit()
    return cursor.lastrowid


def _update_report_ready(
    conn: sqlite3.Connection, report_id: int, report_path: str
) -> None:
    conn.execute(
        "UPDATE reports SET status = 'ready', report_path = ? WHERE id = ?",
        (report_path, report_id),
    )
    conn.commit()


def _update_report_failed(
    conn: sqlite3.Connection, report_id: int, error_message: str
) -> None:
    conn.execute(
        "UPDATE reports SET status = 'failed', error_message = ? WHERE id = ?",
        (error_message, report_id),
    )
    conn.commit()


def _query_team_info(conn: sqlite3.Connection, team_id: int) -> dict:
    """Query team name, season_year from the teams table."""
    row = conn.execute(
        "SELECT name, season_year FROM teams WHERE id = ?", (team_id,)
    ).fetchone()
    if row:
        return {"name": row[0], "season_year": row[1]}
    return {"name": f"Team {team_id}", "season_year": None}


def _query_record(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> dict | None:
    """Query win/loss record from the games table."""
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
    if row and (row[0] is not None or row[1] is not None):
        return {"wins": row[0] or 0, "losses": row[1] or 0}
    return None


def _query_batting(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> list[dict]:
    """Query season batting stats."""
    rows = conn.execute(
        """
        SELECT
            p.player_id,
            p.first_name || ' ' || p.last_name AS name,
            COALESCE(psb.gp, 0) AS games,
            COALESCE(psb.ab, 0) AS ab,
            COALESCE(psb.h, 0) AS h,
            COALESCE(psb.doubles, 0) AS doubles,
            COALESCE(psb.triples, 0) AS triples,
            COALESCE(psb.hr, 0) AS hr,
            COALESCE(psb.rbi, 0) AS rbi,
            COALESCE(psb.bb, 0) AS bb,
            COALESCE(psb.so, 0) AS so,
            COALESCE(psb.sb, 0) AS sb,
            COALESCE(psb.cs, 0) AS cs,
            COALESCE(psb.hbp, 0) AS hbp,
            COALESCE(psb.shf, 0) AS shf,
            tr.jersey_number
        FROM player_season_batting psb
        JOIN players p ON p.player_id = psb.player_id
        LEFT JOIN team_rosters tr
            ON tr.player_id = psb.player_id
            AND tr.team_id = psb.team_id
            AND tr.season_id = psb.season_id
        WHERE psb.team_id = ? AND psb.season_id = ?
        ORDER BY
            (COALESCE(psb.ab, 0) + COALESCE(psb.bb, 0)
             + COALESCE(psb.hbp, 0) + COALESCE(psb.shf, 0)) DESC,
            p.last_name ASC
        """,
        (team_id, season_id),
    ).fetchall()
    result = [dict(r) for r in rows]
    _apply_name_cascade(result)
    return result


def _query_pitching(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> list[dict]:
    """Query season pitching stats and compute rate fields."""
    rows = conn.execute(
        """
        SELECT
            p.player_id,
            p.first_name || ' ' || p.last_name AS name,
            COALESCE(psp.gp_pitcher, 0) AS games,
            COALESCE(psp.ip_outs, 0) AS ip_outs,
            COALESCE(psp.h, 0) AS h,
            COALESCE(psp.er, 0) AS er,
            COALESCE(psp.bb, 0) AS bb,
            COALESCE(psp.so, 0) AS so,
            COALESCE(psp.pitches, 0) AS pitches,
            COALESCE(psp.total_strikes, 0) AS total_strikes,
            p.throws,
            tr.jersey_number,
            psp.gs
        FROM player_season_pitching psp
        JOIN players p ON p.player_id = psp.player_id
        LEFT JOIN team_rosters tr
            ON tr.player_id = psp.player_id
            AND tr.team_id = psp.team_id
            AND tr.season_id = psp.season_id
        WHERE psp.team_id = ? AND psp.season_id = ?
        ORDER BY
            COALESCE(psp.ip_outs, 0) DESC,
            p.last_name ASC
        """,
        (team_id, season_id),
    ).fetchall()
    result = [dict(r) for r in rows]
    _apply_name_cascade(result)
    _compute_pitching_rates(result)
    return result


def _compute_pitching_rates(pitchers: list[dict]) -> None:
    """Add computed rate stats to pitcher dicts (mutates in place)."""
    for row in pitchers:
        ip_outs = row.get("ip_outs") or 0
        er = row.get("er") or 0
        so = row.get("so") or 0
        bb = row.get("bb") or 0
        h = row.get("h") or 0
        pitches = row.get("pitches") or 0
        total_strikes = row.get("total_strikes") or 0
        if ip_outs == 0:
            row["era"] = "-"
            row["k9"] = "-"
            row["whip"] = "-"
        else:
            row["era"] = f"{(er * 27) / ip_outs:.2f}"
            row["k9"] = f"{(so * 27) / ip_outs:.1f}"
            row["whip"] = f"{(bb + h) * 3 / ip_outs:.2f}"
        row["strike_pct"] = (
            f"{(total_strikes / pitches) * 100:.1f}%" if pitches > 0 else "-"
        )


def _apply_name_cascade(rows: list[dict]) -> None:
    """Apply the fallback display name cascade for Unknown players."""
    for row in rows:
        if row.get("name") == "Unknown Unknown":
            jersey = row.get("jersey_number")
            row["name"] = f"Player #{jersey}" if jersey else "Unknown Player"


def _query_recent_games(
    conn: sqlite3.Connection, team_id: int, season_id: str, limit: int = 5
) -> list[dict]:
    """Query the most recent completed games for recent form display.

    Joins the teams table to resolve opponent names.
    """
    rows = conn.execute(
        """
        SELECT
            g.game_date,
            g.home_team_id,
            g.away_team_id,
            g.home_score,
            g.away_score,
            t_home.name AS home_name,
            t_away.name AS away_name
        FROM games g
        LEFT JOIN teams t_home ON t_home.id = g.home_team_id
        LEFT JOIN teams t_away ON t_away.id = g.away_team_id
        WHERE g.season_id = ?
          AND (g.home_team_id = ? OR g.away_team_id = ?)
          AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL
        ORDER BY g.game_date DESC, g.start_time DESC NULLS LAST
        LIMIT ?
        """,
        (season_id, team_id, team_id, limit),
    ).fetchall()
    results = []
    for row in rows:
        home_id = row[1]
        home_score = row[3]
        away_score = row[4]
        home_name = row[5]
        away_name = row[6]
        is_home = home_id == team_id
        our_score = home_score if is_home else away_score
        their_score = away_score if is_home else home_score
        opponent_name = (away_name if is_home else home_name) or "Unknown"
        if our_score > their_score:
            result = "W"
        elif our_score < their_score:
            result = "L"
        else:
            result = "T"
        results.append({
            "result": result,
            "our_score": our_score,
            "their_score": their_score,
            "opponent_name": opponent_name,
            "is_home": is_home,
        })
    return results


def _query_runs_avg(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> tuple[float | None, float | None]:
    """Return (avg_runs_scored, avg_runs_allowed) per game for the team/season."""
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
    if row and row[0] is not None:
        return row[0], row[1]
    return None, None


def _query_freshness(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> tuple[str | None, int]:
    """Return (most_recent_game_date, game_count) for the team/season."""
    row = conn.execute(
        """
        SELECT MAX(game_date) AS latest, COUNT(*) AS cnt
        FROM games
        WHERE season_id = ?
          AND (home_team_id = ? OR away_team_id = ?)
          AND home_score IS NOT NULL AND away_score IS NOT NULL
        """,
        (season_id, team_id, team_id),
    ).fetchone()
    if row and row[1] > 0:
        return row[0], row[1]
    return None, 0


def _query_roster(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> list[dict]:
    """Query roster with jersey numbers and positions."""
    rows = conn.execute(
        """
        SELECT
            p.first_name || ' ' || p.last_name AS name,
            tr.jersey_number,
            tr.position
        FROM team_rosters tr
        JOIN players p ON p.player_id = tr.player_id
        WHERE tr.team_id = ? AND tr.season_id = ?
        ORDER BY
            CASE WHEN tr.jersey_number IS NOT NULL
                 THEN CAST(tr.jersey_number AS INTEGER) ELSE 9999 END ASC,
            p.last_name ASC
        """,
        (team_id, season_id),
    ).fetchall()
    return [dict(r) for r in rows]


def _query_spray_charts(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> dict[str, list[dict]]:
    """Query spray chart events grouped by player_id."""
    rows = conn.execute(
        """
        SELECT player_id, x, y, play_result, play_type
        FROM spray_charts
        WHERE team_id = ? AND chart_type = 'offensive' AND season_id = ?
          AND perspective_team_id = ?
        """,
        (team_id, season_id, team_id),
    ).fetchall()
    result: dict[str, list[dict]] = {}
    for row in rows:
        r = dict(row)
        pid = r.pop("player_id")
        result.setdefault(pid, []).append(r)
    return result


_SEARCH_PAGE_SIZE = 25
_SEARCH_MAX_PAGES = 5


def _resolve_gc_uuid(
    client: GameChangerClient,
    team_name: str,
    public_id: str,
) -> str | None:
    """Resolve a team's gc_uuid via POST /search + public_id filtering.

    Searches for the team by name and filters results for an exact
    ``public_id`` match.  Paginates through up to 5 pages (125 results)
    using the ``start_at_page`` parameter.  Returns immediately when a
    match is found, or short-circuits when a page returns fewer than 25
    hits (indicating no more pages).

    ``CredentialExpiredError`` propagates.  All other exceptions are
    caught and logged as warnings (resolution failure is non-fatal).
    """
    try:
        for page in range(_SEARCH_MAX_PAGES):
            result = client.post_json(
                "/search",
                body={"name": team_name},
                params={"start_at_page": page, "search_source": "search"},
                content_type=_SEARCH_CONTENT_TYPE,
            )
            hits = result.get("hits", []) if isinstance(result, dict) else []
            for hit in hits:
                r = hit.get("result", {})
                if r.get("public_id") == public_id:
                    gc_uuid = r.get("id")
                    if gc_uuid:
                        logger.info(
                            "Resolved gc_uuid=%s for public_id=%s via search "
                            "(page %d).",
                            gc_uuid,
                            public_id,
                            page,
                        )
                        return gc_uuid
            # Short-circuit: partial page means no more results
            if len(hits) < _SEARCH_PAGE_SIZE:
                break
        logger.info(
            "POST /search returned no hit matching public_id=%s; "
            "spray charts unavailable.",
            public_id,
        )
        return None
    except CredentialExpiredError:
        raise
    except Exception:  # noqa: BLE001
        logger.warning(
            "gc_uuid resolution via search failed for public_id=%s; "
            "continuing without spray charts.",
            public_id,
            exc_info=True,
        )
        return None


def _crawl_and_load_spray(
    client: GameChangerClient,
    public_id: str,
    season_id: str,
    gc_uuid: str | None = None,
    games_data: list | None = None,
) -> None:
    """Crawl and load spray chart data in-memory (E-220-06).

    ``CredentialExpiredError`` propagates to the caller. All other exceptions
    are caught and logged as warnings -- spray failure is non-fatal.

    Args:
        client: Authenticated ``GameChangerClient``.
        public_id: The scouted team's ``public_id`` slug.
        season_id: Season slug (e.g., ``"2026-spring-hs"``).
        gc_uuid: When provided, passed to the crawler to bypass DB lookup.
        games_data: In-memory games list from the scouting crawl result.
    """
    try:
        with closing(get_connection()) as conn:
            spray_crawler = ScoutingSprayChartCrawler(client, conn)
            spray_result = spray_crawler.crawl_team(
                public_id, season_id=season_id, gc_uuid=gc_uuid,
                games_data=games_data,
            )

        if spray_result.errors and spray_result.games_crawled == 0:
            logger.warning("Spray crawl failed for public_id=%s; no data.", public_id)
            return

        with closing(get_connection()) as conn:
            spray_loader = ScoutingSprayChartLoader(conn)
            spray_loader.load_from_data(
                spray_result.spray_data, public_id=public_id,
            )
    except CredentialExpiredError:
        raise
    except Exception:  # noqa: BLE001
        logger.warning(
            "Spray chart crawl/load failed for public_id=%s; "
            "continuing without spray charts.",
            public_id,
            exc_info=True,
        )


def _crawl_and_load_plays(
    client: GameChangerClient,
    public_id: str,
    team_id: int,
    season_id: str,
    game_ids: list[str] | None = None,
) -> list[str]:
    """Crawl, load, and reconcile plays data in-memory (E-220-06).

    Game IDs come from crawl result boxscores (in-memory), not disk globs.
    Plays are fetched in-memory and written to temp files for PlaysLoader.

    Args:
        client: Authenticated ``GameChangerClient``.
        public_id: The scouted team's ``public_id`` slug.
        team_id: The team's DB integer PK.
        season_id: Canonical DB season_id for query scoping.
        game_ids: List of game IDs from the crawl result boxscores.

    Returns:
        List of game_id strings that were processed.
    """
    import tempfile

    if not game_ids:
        logger.info("No game IDs for plays stage for public_id=%s; skipping.", public_id)
        return []

    try:
        # Crawl: fetch plays for each game in-memory (per-game error isolation)
        plays_data: dict[str, dict] = {}
        for game_id in game_ids:
            # Check DB idempotency (perspective-aware)
            with closing(get_connection()) as conn:
                existing = conn.execute(
                    "SELECT 1 FROM plays WHERE game_id = ? AND perspective_team_id = ? LIMIT 1",
                    (game_id, team_id),
                ).fetchone()
            if existing is not None:
                logger.debug("Plays already loaded for game %s perspective %d; skipping.", game_id, team_id)
                plays_data[game_id] = {}  # mark as processed for reconcile
                continue

            try:
                raw = client.get(
                    f"/game-stream-processing/{game_id}/plays",
                    accept=_PLAYS_ACCEPT,
                )
                plays_data[game_id] = raw if isinstance(raw, dict) else {}
                logger.debug("Fetched plays for game %s.", game_id)
            except CredentialExpiredError:
                raise
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Failed to fetch plays for game %s; skipping.",
                    game_id,
                    exc_info=True,
                )

        if not plays_data:
            logger.info("No plays data fetched for team_id=%d.", team_id)
            return []

        # Load: write each game's plays to a temp dir, then use PlaysLoader
        with closing(get_connection()) as conn:
            row = conn.execute(
                "SELECT gc_uuid, public_id FROM teams WHERE id = ?", (team_id,)
            ).fetchone()
            gc_uuid = row[0] if row else None
            team_public_id = row[1] if row else public_id

        team_ref = TeamRef(id=team_id, gc_uuid=gc_uuid, public_id=team_public_id)

        with tempfile.TemporaryDirectory() as tmp_dir:
            plays_dir = Path(tmp_dir) / "plays"
            plays_dir.mkdir()
            for gid, data in plays_data.items():
                if data:  # only write non-empty (skip already-loaded)
                    (plays_dir / f"{gid}.json").write_text(
                        json.dumps(data), encoding="utf-8"
                    )

            with closing(get_connection()) as conn:
                loader = PlaysLoader(conn, owned_team_ref=team_ref)
                load_result = loader.load_all(Path(tmp_dir))

        logger.info(
            "Plays load for team_id=%d: loaded=%d skipped=%d errors=%d",
            team_id, load_result.loaded, load_result.skipped, load_result.errors,
        )

        # Reconcile: correct pitcher attribution for each game.  E-220 round
        # 6 cluster 4: pass perspective_team_id=team_id so reconcile targets
        # the report's team perspective.  Otherwise cross-perspective games
        # where team_id != home_team_id would reconcile the wrong rows.
        for game_id in game_ids:
            try:
                with closing(get_connection()) as conn:
                    has_plays = conn.execute(
                        "SELECT 1 FROM plays WHERE game_id = ? AND perspective_team_id = ? LIMIT 1",
                        (game_id, team_id),
                    ).fetchone()
                    if has_plays:
                        reconcile_game(
                            conn, game_id, dry_run=False,
                            perspective_team_id=team_id,
                        )
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Reconciliation failed for game %s; plays data still usable.",
                    game_id,
                    exc_info=True,
                )

        return game_ids

    except CredentialExpiredError:
        raise
    except Exception:  # noqa: BLE001
        logger.warning(
            "Plays crawl/load/reconcile failed for public_id=%s; "
            "continuing without plays data.",
            public_id,
            exc_info=True,
        )
        return []


def _query_plays_pitching_stats(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    game_ids: list[str] | None = None,
) -> dict[str, dict]:
    """Aggregate plays-derived pitching stats grouped by pitcher_id.

    When ``game_ids`` is provided, scopes to exactly those games (E-211:
    prevents cross-pipeline game leakage).  Falls back to team_id scope.

    Returns dict keyed by player_id with ``fps_pct`` and ``pitches_per_bf``.
    """
    if game_ids is not None:
        if not game_ids:
            return {}
        placeholders = ",".join("?" for _ in game_ids)
        rows = conn.execute(
            f"""
            SELECT
                p.pitcher_id,
                SUM(p.is_first_pitch_strike) AS fps_sum,
                COUNT(*) AS fps_denom,
                SUM(p.pitch_count) AS total_pitches,
                COUNT(*) AS total_bf
            FROM plays p
            WHERE p.game_id IN ({placeholders})
              AND p.perspective_team_id = ?
              AND p.pitcher_id IS NOT NULL
            GROUP BY p.pitcher_id
            """,
            [*game_ids, team_id],
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT
                p.pitcher_id,
                SUM(p.is_first_pitch_strike) AS fps_sum,
                COUNT(*) AS fps_denom,
                SUM(p.pitch_count) AS total_pitches,
                COUNT(*) AS total_bf
            FROM plays p
            JOIN games g ON g.game_id = p.game_id
            WHERE g.season_id = ?
              AND (g.home_team_id = ? OR g.away_team_id = ?)
              AND p.perspective_team_id = ?
              AND p.pitcher_id IS NOT NULL
            GROUP BY p.pitcher_id
            """,
            (season_id, team_id, team_id, team_id),
        ).fetchall()

    result: dict[str, dict] = {}
    for row in rows:
        pitcher_id = row[0]
        fps_sum, fps_denom = row[1], row[2]
        total_pitches, total_bf = row[3], row[4]
        fps_pct = (fps_sum / fps_denom) if fps_denom and fps_denom > 0 else None
        pitches_per_bf = (total_pitches / total_bf) if total_bf and total_bf > 0 else None
        result[pitcher_id] = {
            "fps_pct": fps_pct,
            "pitches_per_bf": pitches_per_bf,
        }
    return result


def _query_plays_batting_stats(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    game_ids: list[str] | None = None,
) -> dict[str, dict]:
    """Aggregate plays-derived batting stats grouped by batter_id.

    When ``game_ids`` is provided, scopes to exactly those games (E-211).
    Falls back to season_id + batting_team_id scope.

    Returns dict keyed by player_id with ``qab_pct`` and ``pitches_per_pa``.
    """
    if game_ids is not None:
        if not game_ids:
            return {}
        placeholders = ",".join("?" for _ in game_ids)
        rows = conn.execute(
            f"""
            SELECT
                p.batter_id,
                SUM(p.is_qab) AS qab_sum,
                SUM(p.pitch_count) AS total_pitches,
                COUNT(*) AS total_pa
            FROM plays p
            WHERE p.game_id IN ({placeholders})
              AND p.batting_team_id = ?
              AND p.perspective_team_id = ?
            GROUP BY p.batter_id
            """,
            [*game_ids, team_id, team_id],
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT
                p.batter_id,
                SUM(p.is_qab) AS qab_sum,
                SUM(p.pitch_count) AS total_pitches,
                COUNT(*) AS total_pa
            FROM plays p
            JOIN games g ON g.game_id = p.game_id
            WHERE g.season_id = ?
              AND p.batting_team_id = ?
              AND p.perspective_team_id = ?
            GROUP BY p.batter_id
            """,
            (season_id, team_id, team_id),
        ).fetchall()

    result: dict[str, dict] = {}
    for row in rows:
        batter_id = row[0]
        qab_sum, total_pitches, total_pa = row[1], row[2], row[3]
        qab_pct = (qab_sum / total_pa) if total_pa and total_pa > 0 else None
        pitches_per_pa = (total_pitches / total_pa) if total_pa and total_pa > 0 else None
        result[batter_id] = {
            "qab_pct": qab_pct,
            "pitches_per_pa": pitches_per_pa,
        }
    return result


def _query_plays_team_stats(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    game_ids: list[str] | None = None,
) -> dict:
    """Compute team-level plays aggregates and metadata.

    When ``game_ids`` is provided, scopes to exactly those games (E-211).
    Falls back to team_id scope.

    Returns dict with ``team_fps_pct``, ``team_pitches_per_pa``,
    ``has_plays_data``, and ``plays_game_count``.
    """
    # Check how many games have plays data
    if game_ids is not None:
        if not game_ids:
            return {
                "team_fps_pct": None,
                "team_pitches_per_pa": None,
                "has_plays_data": False,
                "plays_game_count": 0,
            }
        placeholders = ",".join("?" for _ in game_ids)
        row = conn.execute(
            f"""
            SELECT COUNT(DISTINCT p.game_id)
            FROM plays p
            WHERE p.game_id IN ({placeholders})
              AND p.perspective_team_id = ?
            """,
            [*game_ids, team_id],
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT p.game_id)
            FROM plays p
            JOIN games g ON g.game_id = p.game_id
            WHERE g.season_id = ?
              AND (g.home_team_id = ? OR g.away_team_id = ?)
              AND p.perspective_team_id = ?
            """,
            (season_id, team_id, team_id, team_id),
        ).fetchone()
    plays_game_count = row[0] if row else 0
    has_plays_data = plays_game_count > 0

    if not has_plays_data:
        return {
            "team_fps_pct": None,
            "team_pitches_per_pa": None,
            "has_plays_data": False,
            "plays_game_count": 0,
        }

    # Team FPS%: pitchers for this team (matched via roster)
    if game_ids is not None:
        fps_row = conn.execute(
            f"""
            SELECT
                SUM(p.is_first_pitch_strike),
                COUNT(*)
            FROM plays p
            JOIN team_rosters tr ON tr.player_id = p.pitcher_id
                AND tr.team_id = ?
                AND tr.season_id = ?
            WHERE p.game_id IN ({placeholders})
              AND p.perspective_team_id = ?
              AND p.pitcher_id IS NOT NULL
            """,
            [team_id, season_id, *game_ids, team_id],
        ).fetchone()
    else:
        fps_row = conn.execute(
            """
            SELECT
                SUM(p.is_first_pitch_strike),
                COUNT(*)
            FROM plays p
            JOIN games g ON g.game_id = p.game_id
            JOIN team_rosters tr ON tr.player_id = p.pitcher_id
                AND tr.team_id = ?
                AND tr.season_id = ?
            WHERE g.season_id = ?
              AND (g.home_team_id = ? OR g.away_team_id = ?)
              AND p.perspective_team_id = ?
              AND p.pitcher_id IS NOT NULL
            """,
            (team_id, season_id, season_id, team_id, team_id, team_id),
        ).fetchone()
    fps_sum = fps_row[0] if fps_row and fps_row[0] else 0
    fps_denom = fps_row[1] if fps_row and fps_row[1] else 0
    team_fps_pct = (fps_sum / fps_denom) if fps_denom > 0 else None

    # Team pitches per PA (batting side)
    if game_ids is not None:
        ppa_row = conn.execute(
            f"""
            SELECT SUM(p.pitch_count), COUNT(*)
            FROM plays p
            WHERE p.game_id IN ({placeholders})
              AND p.batting_team_id = ?
              AND p.perspective_team_id = ?
            """,
            [*game_ids, team_id, team_id],
        ).fetchone()
    else:
        ppa_row = conn.execute(
            """
            SELECT SUM(p.pitch_count), COUNT(*)
            FROM plays p
            JOIN games g ON g.game_id = p.game_id
            WHERE g.season_id = ?
              AND p.batting_team_id = ?
              AND p.perspective_team_id = ?
            """,
            (season_id, team_id, team_id),
        ).fetchone()
    total_pitches = ppa_row[0] if ppa_row and ppa_row[0] else 0
    total_pa = ppa_row[1] if ppa_row and ppa_row[1] else 0
    team_pitches_per_pa = (total_pitches / total_pa) if total_pa > 0 else None

    return {
        "team_fps_pct": team_fps_pct,
        "team_pitches_per_pa": team_pitches_per_pa,
        "has_plays_data": has_plays_data,
        "plays_game_count": plays_game_count,
    }


def generate_report(gc_url: str) -> GenerationResult:
    """Generate a standalone scouting report for a GameChanger team.

    Executes the full pipeline per TN-3: parse URL, ensure team row, create
    reports row, run scouting crawl/load, query stats, render HTML, save file.

    Args:
        gc_url: A GameChanger team URL, bare public_id, or bare UUID.

    Returns:
        A :class:`GenerationResult` with success/failure details.
    """
    # Step 1: Parse URL
    try:
        parsed = parse_team_url(gc_url)
    except ValueError as exc:
        return GenerationResult(success=False, error_message=str(exc))

    if parsed.is_uuid:
        return GenerationResult(
            success=False,
            error_message="UUID-based URLs are not supported for report generation. "
            "Please use a public team URL (with a public_id slug).",
        )

    public_id = parsed.value

    # Step 1b: Fetch team name + season year from public API (no auth needed)
    team_name_from_api: str | None = None
    season_year_from_api: int | None = None
    ngb_from_api: str | None = None
    age_group_from_api: str | None = None
    try:
        from src.http.session import create_session

        session = create_session()
        resp = session.get(
            f"https://api.team-manager.gc.com/public/teams/{public_id}",
            timeout=15,
        )
        if resp.status_code == 200:
            pub_data = resp.json()
            team_name_from_api = pub_data.get("name")
            ts = pub_data.get("team_season") or {}
            season_year_from_api = ts.get("year")
            ngb_from_api = pub_data.get("ngb")
            age_group_from_api = pub_data.get("age_group")
        session.close()
    except Exception:  # noqa: BLE001
        logger.warning("Could not fetch public team info for %s", public_id)

    # Step 2: Ensure team row
    with closing(get_connection()) as conn:
        team_id = ensure_team_row(
            conn,
            public_id=public_id,
            name=team_name_from_api,
            season_year=season_year_from_api,
            source="report_generator",
        )
        # ensure_team_row doesn't overwrite existing names (conservative backfill).
        # Force-update name/season_year from the public API when available, since
        # earlier failed attempts may have left the row with placeholder values.
        if team_name_from_api:
            conn.execute(
                "UPDATE teams SET name = ?, season_year = COALESCE(?, season_year) "
                "WHERE id = ?",
                (team_name_from_api, season_year_from_api, team_id),
            )
            # Backfill public_id when ensure_team_row matched by name+season_year
            # (step 3) and left public_id NULL. Safe: AND public_id IS NULL guard
            # prevents overwriting a value set through a more authoritative path.
            try:
                result = conn.execute(
                    "UPDATE teams SET public_id = ? WHERE id = ? AND public_id IS NULL",
                    (public_id, team_id),
                )
                if result.rowcount > 0:
                    logger.info("Backfilled public_id=%s on team_id=%d", public_id, team_id)
            except sqlite3.IntegrityError:
                logger.warning(
                    "Could not backfill public_id=%s on team_id=%d — "
                    "another team already has this public_id",
                    public_id, team_id,
                )
        conn.commit()

    # Step 3: Create reports row (placeholder title — updated after crawl)
    slug = secrets.token_urlsafe(12)
    generated_at = _utcnow_iso()
    expires_dt = datetime.now(timezone.utc) + timedelta(days=_EXPIRY_DAYS)
    expires_at = expires_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    with closing(get_connection()) as conn:
        initial_title = f"Scouting Report — {team_name_from_api or public_id}"
        report_id = _create_report_row(
            conn, slug, team_id, initial_title,
            generated_at, expires_at,
        )

    # Snapshot team IDs before scouting load (for orphan cleanup)
    with closing(get_connection()) as conn:
        pre_team_ids = _snapshot_team_ids(conn)

    # Step 4: Run scouting pipeline synchronously (in-memory -- E-220-06)
    try:
        client = GameChangerClient()
        with closing(get_connection()) as conn:
            crawler = ScoutingCrawler(client, conn)
            crawl_result = crawler.scout_team(public_id)

        if crawl_result.errors > 0 and crawl_result.games_crawled == 0:
            _fail_report(report_id, "Scouting crawl failed — no data retrieved.")
            return GenerationResult(
                success=False, slug=slug, error_message="Scouting crawl failed."
            )

        # Derive the canonical DB season_id from team metadata.
        with closing(get_connection()) as conn:
            season_id, _ = derive_season_id_for_team(conn, team_id)

        # Run the loader with in-memory crawl result.
        with closing(get_connection()) as conn:
            loader = ScoutingLoader(conn)
            load_result = loader.load_team(crawl_result)

        if load_result.loaded == 0 and load_result.errors > 0:
            _fail_report(report_id, "Scouting load failed — no data loaded.")
            return GenerationResult(
                success=False, slug=slug, error_message="Scouting load failed."
            )

        # Re-read team_info AFTER crawl/load so name is populated from schedule
        with closing(get_connection()) as conn:
            team_info = _query_team_info(conn, team_id)

        title = f"Scouting Report — {team_info['name']}"

        # Update the placeholder title with the real team name
        with closing(get_connection()) as conn:
            conn.execute(
                "UPDATE reports SET title = ? WHERE id = ?", (title, report_id)
            )
            conn.commit()

        # Step 4b: Resolve gc_uuid for spray chart access.
        # Tracked teams always search-resolve (stored gc_uuid may be
        # contaminated by opponent-perspective boxscore keys -- see E-211).
        # Member teams use stored gc_uuid (from authenticated API).
        resolved_gc_uuid: str | None = None
        with closing(get_connection()) as conn:
            row = conn.execute(
                "SELECT gc_uuid, membership_type FROM teams WHERE id = ?",
                (team_id,),
            ).fetchone()
            existing_gc_uuid = row[0] if row else None
            membership_type = row[1] if row else "tracked"

        if membership_type == "member" and existing_gc_uuid:
            resolved_gc_uuid = existing_gc_uuid
        elif team_info.get("name"):
            resolved_gc_uuid = _resolve_gc_uuid(client, team_info["name"], public_id)
            if resolved_gc_uuid:
                with closing(get_connection()) as conn:
                    conn.execute(
                        "UPDATE teams SET gc_uuid = ? WHERE id = ? "
                        "AND membership_type = 'tracked'",
                        (resolved_gc_uuid, team_id),
                    )
                    conn.commit()

        # Step 4c: Spray chart crawl/load (in-memory -- E-220-06)
        _crawl_and_load_spray(
            client, public_id, season_id,
            gc_uuid=resolved_gc_uuid,
            games_data=crawl_result.games,
        )

        # Step 4d: Plays crawl/load/reconcile (in-memory -- E-220-06).
        # Game IDs from crawl result boxscores, not disk globs.
        plays_game_ids: list[str] = []
        try:
            plays_game_ids = _crawl_and_load_plays(
                client, public_id, team_id, season_id,
                game_ids=sorted(crawl_result.boxscores.keys()),
            )
        except CredentialExpiredError:
            logger.warning(
                "Auth expired during plays stage for public_id=%s; "
                "continuing without plays data.",
                public_id,
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Plays stage failed for public_id=%s; continuing without plays data.",
                public_id,
                exc_info=True,
            )

    except CredentialExpiredError:
        msg = "Authentication credentials expired — refresh with `bb creds setup web`"
        _fail_report(report_id, msg)
        return GenerationResult(success=False, slug=slug, error_message=msg)
    except Exception as exc:  # noqa: BLE001
        msg = f"Pipeline error: {exc}"
        logger.exception("Report generation pipeline failed")
        _fail_report(report_id, msg)
        return GenerationResult(success=False, slug=slug, error_message=msg)

    # Compute orphan team IDs created during the scouting load
    with closing(get_connection()) as conn:
        post_team_ids = _snapshot_team_ids(conn)
    orphan_ids = post_team_ids - pre_team_ids - {team_id}

    # Step 5: Query stats, render, save, and mark ready — all in one
    # failure-handling block so the report never gets stuck in 'generating'.
    try:
        # Query BEFORE cleanup -- game-dependent queries need game rows
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            batting = _query_batting(conn, team_id, season_id)
            pitching = _query_pitching(conn, team_id, season_id)
            roster = _query_roster(conn, team_id, season_id)
            record = _query_record(conn, team_id, season_id)
            recent_form = _query_recent_games(conn, team_id, season_id)
            freshness_date, game_count = _query_freshness(conn, team_id, season_id)
            spray_charts = _query_spray_charts(conn, team_id, season_id)
            runs_scored_avg, runs_allowed_avg = _query_runs_avg(
                conn, team_id, season_id
            )

            # Pitching workload (uses generation date as reference)
            generation_date = generated_at[:10]
            pitching_workload = get_pitching_workload(
                team_id, season_id, generation_date, db=conn,
            )

            # Predicted starter (Tier 1)
            starter_prediction = None
            enriched_prediction = None
            from src.reports.starter_prediction import (
                is_predicted_starter_enabled,
            )
            show_predicted_starter = is_predicted_starter_enabled()
            if show_predicted_starter:
                pitching_history_rows = get_pitching_history(
                    team_id, season_id, db=conn,
                )
                if pitching_history_rows:
                    from src.reports.starter_prediction import (
                        compute_starter_prediction,
                        detect_league_level,
                    )

                    league = detect_league_level(
                        ngb=ngb_from_api,
                        age_group=age_group_from_api,
                        team_name=team_name_from_api,
                    )

                    pitcher_profiles = build_pitcher_profiles(
                        pitching_history_rows,
                    )
                    starter_prediction = compute_starter_prediction(
                        pitcher_profiles, pitching_history_rows,
                        reference_date=date.fromisoformat(generated_at[:10]),
                        workload=pitching_workload,
                        league=league,
                    )

                    # Tier 2: LLM enrichment (optional, non-fatal)
                    from src.llm.openrouter import is_llm_available

                    if is_llm_available():
                        try:
                            from src.reports.llm_analysis import enrich_prediction

                            team_record_str = None
                            if record:
                                team_record_str = (
                                    f"{record['wins']}-{record['losses']}"
                                )
                            enriched_prediction = enrich_prediction(
                                starter_prediction,
                                pitching_history_rows,
                                team_record=team_record_str,
                                reference_date=date.fromisoformat(
                                    generated_at[:10],
                                ),
                            )
                        except Exception:  # noqa: BLE001
                            logger.warning(
                                "LLM enrichment failed for public_id=%s; "
                                "continuing with Tier 1 only.",
                                public_id,
                                exc_info=True,
                            )

            # Plays-derived stats
            plays_pitching = _query_plays_pitching_stats(
                conn, team_id, season_id, game_ids=plays_game_ids,
            )
            plays_batting = _query_plays_batting_stats(
                conn, team_id, season_id, game_ids=plays_game_ids,
            )
            plays_team = _query_plays_team_stats(
                conn, team_id, season_id, game_ids=plays_game_ids,
            )

        # Build roster set for pitcher matching (pitching query returns all
        # pitchers in games involving this team; filter to team's own roster)
        with closing(get_connection()) as conn:
            roster_pids = {
                row[0] for row in conn.execute(
                    "SELECT player_id FROM team_rosters WHERE team_id = ? AND season_id = ?",
                    (team_id, season_id),
                ).fetchall()
            }
        for p in pitching:
            pid = p.get("player_id")
            if pid and pid in plays_pitching and pid in roster_pids:
                p["fps_pct"] = plays_pitching[pid]["fps_pct"]
                p["pitches_per_bf"] = plays_pitching[pid]["pitches_per_bf"]
            else:
                p["fps_pct"] = None
                p["pitches_per_bf"] = None

        # Merge plays stats into batter dicts
        for b in batting:
            pid = b.get("player_id")
            if pid and pid in plays_batting:
                b["qab_pct"] = plays_batting[pid]["qab_pct"]
                b["pitches_per_pa"] = plays_batting[pid]["pitches_per_pa"]
            else:
                b["qab_pct"] = None
                b["pitches_per_pa"] = None

        # Orphan cleanup -- after queries, before render (non-fatal)
        if orphan_ids:
            try:
                with closing(get_connection()) as conn:
                    cleanup_orphan_teams(conn, orphan_ids)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Orphan cleanup failed for %d team(s); report continues.",
                    len(orphan_ids),
                    exc_info=True,
                )

        # Render HTML
        team_info["record"] = record
        data = {
            "team": team_info,
            "generated_at": generated_at,
            "expires_at": expires_at,
            "freshness_date": freshness_date,
            "game_count": game_count,
            "recent_form": recent_form,
            "pitching": pitching,
            "batting": batting,
            "spray_charts": spray_charts,
            "roster": roster,
            "runs_scored_avg": runs_scored_avg,
            "runs_allowed_avg": runs_allowed_avg,
            "team_fps_pct": plays_team["team_fps_pct"],
            "team_pitches_per_pa": plays_team["team_pitches_per_pa"],
            "has_plays_data": plays_team["has_plays_data"],
            "plays_game_count": plays_team["plays_game_count"],
            "pitching_workload": pitching_workload,
            "generation_date": generation_date,
            "starter_prediction": starter_prediction,
            "enriched_prediction": enriched_prediction,
            "show_predicted_starter": show_predicted_starter,
        }
        html = render_report(data)

        # Save HTML to disk
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = f"reports/{slug}.html"
        file_path = _REPO_ROOT / "data" / report_path
        file_path.write_text(html, encoding="utf-8")

        # Update reports row to 'ready'
        with closing(get_connection()) as conn:
            _update_report_ready(conn, report_id, report_path)

    except Exception as exc:  # noqa: BLE001
        msg = f"Post-pipeline error: {exc}"
        logger.exception("Failed to query/render/save report")
        _fail_report(report_id, msg)
        return GenerationResult(success=False, slug=slug, error_message=msg)

    url = f"{_get_base_url()}/reports/{slug}"
    logger.info("Report generated: slug=%s team=%s url=%s", slug, team_info["name"], url)

    return GenerationResult(
        success=True,
        slug=slug,
        title=title,
        url=url,
    )


def _snapshot_team_ids(conn: sqlite3.Connection) -> set[int]:
    """Return all current team IDs as a set."""
    return {row[0] for row in conn.execute("SELECT id FROM teams")}


def _delete_game_scoped_data_for_perspectives(
    conn: sqlite3.Connection,
    game_ids: list[str],
    perspective_team_ids: list[int],
) -> None:
    """Delete game-scoped rows owned by the given perspectives only.

    E-220 round 6 cluster 2: scoped replacement for the prior
    ``_delete_game_scoped_data()``.  Preserves rows belonging to OTHER
    perspectives of the same games.  The ``games`` row itself is only
    deleted when no other perspective remains in ``game_perspectives``;
    otherwise the games row is preserved so the other perspective's data
    still has a valid FK target.

    FK-safe order: play_events -> plays -> reconciliation_discrepancies ->
    player_game_batting -> player_game_pitching -> spray_charts ->
    game_perspectives -> games.

    Args:
        conn: Open SQLite connection.
        game_ids: The games whose dependent rows should be considered.
        perspective_team_ids: Delete only rows tagged with these
            perspectives.  Rows belonging to other perspectives are
            preserved.

    Note: ``reconciliation_discrepancies`` uses ``perspective_team_id``
    directly for perspective-scoped deletion (E-220 round 7 P1-2).
    """
    if not game_ids or not perspective_team_ids:
        return
    gp = ",".join("?" for _ in game_ids)
    pp = ",".join("?" for _ in perspective_team_ids)
    params = list(game_ids) + list(perspective_team_ids)

    # play_events inherits perspective via parent plays (FK to plays.id)
    conn.execute(
        f"DELETE FROM play_events WHERE play_id IN ("
        f"  SELECT id FROM plays "
        f"  WHERE game_id IN ({gp}) AND perspective_team_id IN ({pp})"
        f")",
        params,
    )
    conn.execute(
        f"DELETE FROM plays "
        f"WHERE game_id IN ({gp}) AND perspective_team_id IN ({pp})",
        params,
    )
    # reconciliation_discrepancies: scope by perspective_team_id so
    # cross-perspective game-level rows for the opposite participant are
    # not incorrectly preserved (E-220 round 7 P1-2 bonus bugfix).
    conn.execute(
        f"DELETE FROM reconciliation_discrepancies "
        f"WHERE game_id IN ({gp}) AND perspective_team_id IN ({pp})",
        params,
    )
    conn.execute(
        f"DELETE FROM player_game_batting "
        f"WHERE game_id IN ({gp}) AND perspective_team_id IN ({pp})",
        params,
    )
    conn.execute(
        f"DELETE FROM player_game_pitching "
        f"WHERE game_id IN ({gp}) AND perspective_team_id IN ({pp})",
        params,
    )
    conn.execute(
        f"DELETE FROM spray_charts "
        f"WHERE game_id IN ({gp}) AND perspective_team_id IN ({pp})",
        params,
    )
    conn.execute(
        f"DELETE FROM game_perspectives "
        f"WHERE game_id IN ({gp}) AND perspective_team_id IN ({pp})",
        params,
    )
    # Only delete the games row if no other perspective remains for that game.
    conn.execute(
        f"DELETE FROM games "
        f"WHERE game_id IN ({gp}) "
        f"  AND NOT EXISTS ("
        f"    SELECT 1 FROM game_perspectives gp2 "
        f"    WHERE gp2.game_id = games.game_id"
        f"  )",
        list(game_ids),
    )


def _delete_team_anchor_and_orphan_data(
    conn: sqlite3.Connection, team_id: int
) -> None:
    """Delete game-level stat rows anchored to or perspectived by the given team.

    Two passes, both unbounded by the participant-games set:

      1. Perspective pass: rows where ``perspective_team_id = team_id`` in any
         game.  Mirrors the Phase 1b cleanup from the pre-refactor admin cascade
         (``src/api/routes/admin.py``).  Necessary because
         ``_delete_game_scoped_data_for_perspectives`` scopes its DELETEs to a
         participant-games set, so cross-perspective scouting rows the team
         produced about games it did not play in are missed.

      2. Anchor pass: rows where ``team_id = team_id`` (and ``batting_team_id``
         for ``plays``) in any game, regardless of which perspective owns them.
         Necessary because ``team_id INTEGER NOT NULL REFERENCES teams(id)``
         has no ``ON DELETE`` clause anywhere in the schema.  SQLite's default
         is NO ACTION (RESTRICT on immediate), so deleting a team without first
         removing its anchor rows raises ``IntegrityError`` at the
         ``DELETE FROM teams`` step.

    Pass order (perspective first, anchor second) matches the historical
    admin.py Phase 1b / Phase 3 ordering and keeps the two WHERE-clause
    families grepable.  Correctness does not depend on the order -- both
    passes are idempotent DELETEs on overlapping tables with different
    filters.  Within the anchor pass, ``play_events`` MUST be deleted before
    its parent ``plays`` rows to respect the ``play_events.play_id -> plays.id``
    FK.
    """
    # --- Pass 1: perspective_team_id = T (any game) --------------------------
    conn.execute(
        "DELETE FROM play_events WHERE play_id IN ("
        "  SELECT id FROM plays WHERE perspective_team_id = ?"
        ")",
        (team_id,),
    )
    conn.execute(
        "DELETE FROM plays WHERE perspective_team_id = ?", (team_id,)
    )
    conn.execute(
        "DELETE FROM player_game_batting WHERE perspective_team_id = ?",
        (team_id,),
    )
    conn.execute(
        "DELETE FROM player_game_pitching WHERE perspective_team_id = ?",
        (team_id,),
    )
    conn.execute(
        "DELETE FROM spray_charts WHERE perspective_team_id = ?",
        (team_id,),
    )
    conn.execute(
        "DELETE FROM reconciliation_discrepancies WHERE perspective_team_id = ?",
        (team_id,),
    )
    conn.execute(
        "DELETE FROM game_perspectives WHERE perspective_team_id = ?",
        (team_id,),
    )

    # --- Pass 2: team_id / batting_team_id = T (any game, any perspective) ---
    # plays.batting_team_id and plays.perspective_team_id are independent FKs;
    # the perspective pass already handled perspective_team_id = T, so we
    # target batting_team_id = T here.  play_events must precede plays.
    conn.execute(
        "DELETE FROM play_events WHERE play_id IN ("
        "  SELECT id FROM plays WHERE batting_team_id = ?"
        ")",
        (team_id,),
    )
    conn.execute(
        "DELETE FROM plays WHERE batting_team_id = ?", (team_id,)
    )
    conn.execute(
        "DELETE FROM player_game_batting WHERE team_id = ?", (team_id,)
    )
    conn.execute(
        "DELETE FROM player_game_pitching WHERE team_id = ?", (team_id,)
    )
    conn.execute(
        "DELETE FROM spray_charts WHERE team_id = ?", (team_id,)
    )
    conn.execute(
        "DELETE FROM reconciliation_discrepancies WHERE team_id = ?", (team_id,)
    )


def _delete_team_scoped_data(
    conn: sqlite3.Connection, team_ids: list[int], *, delete_team_rows: bool = True
) -> None:
    """Delete team-scoped dependent rows for the given team IDs.

    FK-safe order per TN-6 Phase 2.  Optionally deletes the team rows
    themselves (set ``delete_team_rows=False`` to skip when game FKs
    still reference the team).
    """
    if not team_ids:
        return
    placeholders = ",".join("?" for _ in team_ids)
    conn.execute(f"DELETE FROM team_rosters WHERE team_id IN ({placeholders})", team_ids)
    conn.execute(f"DELETE FROM player_season_batting WHERE team_id IN ({placeholders})", team_ids)
    conn.execute(f"DELETE FROM player_season_pitching WHERE team_id IN ({placeholders})", team_ids)
    conn.execute(f"DELETE FROM scouting_runs WHERE team_id IN ({placeholders})", team_ids)
    conn.execute(f"DELETE FROM crawl_jobs WHERE team_id IN ({placeholders})", team_ids)
    conn.execute(f"DELETE FROM coaching_assignments WHERE team_id IN ({placeholders})", team_ids)
    conn.execute(f"DELETE FROM user_team_access WHERE team_id IN ({placeholders})", team_ids)
    conn.execute(
        f"DELETE FROM team_opponents WHERE our_team_id IN ({placeholders}) "
        f"OR opponent_team_id IN ({placeholders})",
        team_ids + team_ids,
    )
    conn.execute(
        f"DELETE FROM opponent_links WHERE our_team_id IN ({placeholders})",
        team_ids,
    )
    conn.execute(
        f"UPDATE opponent_links SET resolved_team_id = NULL, resolution_method = NULL, "
        f"resolved_at = NULL WHERE resolved_team_id IN ({placeholders})",
        team_ids,
    )
    if delete_team_rows:
        conn.execute(f"DELETE FROM teams WHERE id IN ({placeholders})", team_ids)


def cascade_delete_team(conn: sqlite3.Connection, team_id: int) -> None:
    """Cascade-delete a single team and its dependent data.

    Used by the report-deletion path where the team is confirmed eligible
    for cleanup (all guard conditions passed).  Deletes only rows owned
    by this team's perspective; cross-perspective rows belonging to other
    teams are preserved, as are games rows when another perspective
    remains.  The team-scoped tables (rosters, season aggregates,
    scouting_runs, etc.) are deleted unconditionally since they are keyed
    on team_id alone.

    FK-safe team-row deletion (round 7 P1-1): after data cleanup, the
    ``teams`` row itself is only deleted when no ``games`` row still
    FK-references the team.  A survivor occurs when another stub
    perspective loaded the same game and its ``game_perspectives`` row
    kept the ``games`` row alive.  In that case, the team-scoped data
    is still cleaned, but the ``teams`` row is retained to preserve the
    cross-perspective ``games`` FK target.  This mirrors the pattern
    ``cleanup_orphan_teams`` uses.
    """
    game_rows = conn.execute(
        "SELECT game_id FROM games WHERE home_team_id = ? OR away_team_id = ?",
        (team_id, team_id),
    ).fetchall()
    # Unbounded cleanup MUST run before _delete_game_scoped_data_for_perspectives,
    # because the latter attempts to delete the games row inside its last DELETE
    # and will FK-violate if anchor rows (team_id = T, any perspective) still
    # reference the game.  The anchor pass clears those; the perspective-scoped
    # helper then cleans remaining perspective-scoped rows and deletes the game
    # row under the NOT EXISTS guard.
    _delete_team_anchor_and_orphan_data(conn, team_id)
    _delete_game_scoped_data_for_perspectives(
        conn, [r[0] for r in game_rows], [team_id],
    )
    _delete_team_scoped_data(conn, [team_id], delete_team_rows=False)

    # Only delete the teams row if no games row still FK-references it.
    game_still_references_team = conn.execute(
        "SELECT 1 FROM games WHERE home_team_id = ? OR away_team_id = ? LIMIT 1",
        (team_id, team_id),
    ).fetchone() is not None

    if game_still_references_team:
        conn.commit()
        logger.info(
            "Cascade-deleted data for team_id=%d; teams row retained "
            "(cross-perspective games still reference it).",
            team_id,
        )
        return

    conn.execute("DELETE FROM teams WHERE id = ?", (team_id,))
    conn.commit()
    logger.info("Cascade-deleted team_id=%d and all dependent data.", team_id)


def cleanup_orphan_teams(
    conn: sqlite3.Connection, orphan_ids: set[int]
) -> int:
    """Delete orphan teams and their dependent rows in FK-safe order.

    Used during report generation to clean up auto-created opponent stubs.
    Only deletes games where BOTH participants are orphans — shared games
    between an orphan and a non-orphan (e.g., the report team) are
    preserved.  Orphan teams that still have game FK references after
    Phase 1 are retained (team-scoped data is still cleaned).
    """
    if not orphan_ids:
        return 0

    placeholders = ",".join("?" for _ in orphan_ids)
    id_list = list(orphan_ids)

    # Phase 1: delete games where BOTH participants are orphans.  Scope to
    # orphan perspectives only -- non-orphan perspective rows for the same
    # games (e.g., the report team's perspective) are preserved.
    game_rows = conn.execute(
        f"SELECT game_id FROM games WHERE home_team_id IN ({placeholders}) "
        f"AND away_team_id IN ({placeholders})",
        id_list + id_list,
    ).fetchall()
    _delete_game_scoped_data_for_perspectives(
        conn, [r[0] for r in game_rows], id_list,
    )

    # Determine which orphans still have remaining game FK references
    remaining_rows = conn.execute(
        f"SELECT DISTINCT home_team_id FROM games WHERE home_team_id IN ({placeholders}) "
        f"UNION "
        f"SELECT DISTINCT away_team_id FROM games WHERE away_team_id IN ({placeholders})",
        id_list + id_list,
    ).fetchall()
    undeletable_ids = {r[0] for r in remaining_rows}
    deletable_ids = orphan_ids - undeletable_ids

    # Phase 2: clean team-scoped data for all orphans
    _delete_team_scoped_data(
        conn, id_list, delete_team_rows=False,
    )
    # Only delete team rows that have no remaining game references
    if deletable_ids:
        dp = ",".join("?" for _ in deletable_ids)
        conn.execute(f"DELETE FROM teams WHERE id IN ({dp})", list(deletable_ids))
    conn.commit()

    count = len(deletable_ids)
    if undeletable_ids:
        logger.info(
            "Cleaned up %d orphan team(s); %d retained (shared games).",
            count, len(undeletable_ids),
        )
    else:
        logger.info("Cleaned up %d orphan team(s) from report generation.", count)
    return count


def is_team_eligible_for_cleanup(
    conn: sqlite3.Connection, team_id: int, exclude_report_id: int
) -> bool:
    """Check whether a team is eligible for cascade-delete after report removal.

    Guard conditions (all must pass):
    1. ``is_active = 0``
    2. No rows in ``team_opponents`` reference this team_id (either direction)
    3. No other ``reports`` rows reference this team_id
    4. No games involving this team also involve a tracked team (one that
       appears in ``team_opponents``)

    Args:
        conn: Open SQLite connection.
        team_id: The team to check.
        exclude_report_id: The report being deleted (excluded from the
            multi-report check).
    """
    # Guard 1: is_active
    row = conn.execute(
        "SELECT is_active FROM teams WHERE id = ?", (team_id,)
    ).fetchone()
    if row is None:
        return False
    if row[0] != 0:
        return False

    # Guard 2: team_opponents (either direction)
    row = conn.execute(
        "SELECT 1 FROM team_opponents "
        "WHERE our_team_id = ? OR opponent_team_id = ? LIMIT 1",
        (team_id, team_id),
    ).fetchone()
    if row is not None:
        return False

    # Guard 3: other reports
    row = conn.execute(
        "SELECT 1 FROM reports WHERE team_id = ? AND id != ? LIMIT 1",
        (team_id, exclude_report_id),
    ).fetchone()
    if row is not None:
        return False

    # Guard 4: shared games with tracked teams
    row = conn.execute(
        """
        SELECT 1 FROM games g
        WHERE (g.home_team_id = :tid OR g.away_team_id = :tid)
          AND EXISTS (
              SELECT 1 FROM team_opponents to2
              WHERE to2.our_team_id IN (g.home_team_id, g.away_team_id)
                 OR to2.opponent_team_id IN (g.home_team_id, g.away_team_id)
          )
        LIMIT 1
        """,
        {"tid": team_id},
    ).fetchone()
    if row is not None:
        return False

    return True


def _fail_report(report_id: int, error_message: str) -> None:
    """Mark a report as failed."""
    try:
        with closing(get_connection()) as conn:
            _update_report_failed(conn, report_id, error_message)
    except sqlite3.Error:
        logger.exception("Failed to update report status to 'failed'")


def list_reports() -> list[dict]:
    """Return all reports sorted by generated_at descending.

    Returns:
        List of report dicts with keys: slug, title, status, generated_at,
        expires_at, url, is_expired.
    """
    base_url = _get_base_url()
    now = _utcnow_iso()
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT slug, title, status, generated_at, expires_at "
                "FROM reports ORDER BY generated_at DESC"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("Failed to list reports")
        return []

    result = []
    for row in rows:
        r = dict(row)
        r["url"] = f"{base_url}/reports/{r['slug']}"
        r["is_expired"] = r["expires_at"] < now
        result.append(r)
    return result
