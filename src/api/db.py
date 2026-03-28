"""Database connection helpers for the FastAPI application.

Provides a simple synchronous SQLite connection factory and a health-check
function.  All database calls are run via ``run_in_threadpool`` in async
route handlers to avoid blocking the event loop (see routes/health.py).

Configuration:
    DATABASE_PATH   Environment variable specifying the path to the SQLite
                    file.  Defaults to ``<repo_root>/data/app.db``.
"""

from __future__ import annotations

import datetime
import logging
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "app.db"


def get_db_path() -> Path:
    """Return the resolved path to the SQLite database file.

    Reads DATABASE_PATH from the environment, falling back to the default.

    Returns:
        Resolved Path to the database file.
    """
    raw = os.environ.get("DATABASE_PATH", _DEFAULT_DB_PATH)
    return Path(raw).resolve()


def get_connection() -> sqlite3.Connection:
    """Open and return a new SQLite connection with recommended pragmas.

    Callers are responsible for closing the connection (use as a context
    manager or call ``conn.close()`` explicitly).

    Returns:
        Open sqlite3.Connection with WAL mode and foreign keys enabled.

    Raises:
        sqlite3.Error: If the database file cannot be opened.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def get_team_batting_stats(
    team_id: int,
    season_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return season batting stats for all players on a team.

    Joins ``player_season_batting`` with ``players`` and ``team_rosters`` to
    return each player's display name, jersey number, and full batting stats.
    Results are sorted by AVG descending; players with no AB appear at bottom.

    Args:
        team_id:   The INTEGER team id to query.
        season_id: The season slug (e.g. ``"2026-spring-hs"``).  Defaults to
                   the most recent season in the ``seasons`` table.

    Returns:
        List of dicts with keys: player_id, name, jersey_number, games, ab, h,
        doubles, triples, hr, rbi, bb, so, sb.
        Returns an empty list if the database is not accessible, no seasons
        exist, or the team has no season batting rows.
    """
    query = """
        SELECT
            p.player_id,
            p.first_name || ' ' || p.last_name AS name,
            tr.jersey_number,
            COALESCE(psb.gp, 0)      AS games,
            COALESCE(psb.ab, 0)      AS ab,
            COALESCE(psb.h, 0)       AS h,
            COALESCE(psb.doubles, 0) AS doubles,
            COALESCE(psb.triples, 0) AS triples,
            COALESCE(psb.hr, 0)      AS hr,
            COALESCE(psb.rbi, 0)     AS rbi,
            COALESCE(psb.bb, 0)      AS bb,
            COALESCE(psb.so, 0)      AS so,
            COALESCE(psb.sb, 0)      AS sb,
            COALESCE(psb.hbp, 0)     AS hbp,
            COALESCE(psb.shf, 0)     AS shf
        FROM player_season_batting psb
        JOIN players p ON p.player_id = psb.player_id
        LEFT JOIN team_rosters tr
            ON tr.player_id = psb.player_id
            AND tr.team_id = psb.team_id
            AND tr.season_id = psb.season_id
        WHERE psb.team_id = ? AND psb.season_id = ?
        ORDER BY
            CASE WHEN COALESCE(psb.ab, 0) = 0 THEN 1 ELSE 0 END ASC,
            CAST(COALESCE(psb.h, 0) AS REAL) / NULLIF(psb.ab, 0) DESC NULLS LAST,
            p.last_name ASC
    """
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            if season_id is None:
                row = conn.execute(
                    "SELECT season_id FROM seasons ORDER BY season_id DESC LIMIT 1"
                ).fetchone()
                if row is None:
                    return []
                season_id = row["season_id"]
            cursor = conn.execute(query, (team_id, season_id))
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error:
        logger.exception("Failed to fetch team batting stats")
        return []


def get_teams_by_ids(team_ids: list[int]) -> list[dict[str, Any]]:
    """Return team display names for the given list of INTEGER team ids.

    Args:
        team_ids: List of INTEGER team ids to look up.

    Returns:
        List of dicts with keys: id, name.
        Returns an empty list if team_ids is empty or on DB error.
    """
    if not team_ids:
        return []
    placeholders = ",".join("?" for _ in team_ids)
    query = f"SELECT id, name FROM teams WHERE id IN ({placeholders})"
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, team_ids)
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error:
        logger.exception("Failed to fetch teams by ids")
        return []


def get_team_pitching_stats(
    team_id: int,
    season_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return season pitching stats for all pitchers on a team.

    Joins ``player_season_pitching`` with ``players`` and ``team_rosters`` to
    return each pitcher's display name, jersey number, and aggregate pitching
    stats.  Results are sorted by ERA ascending (pitchers with 0 ip_outs appear
    at the bottom).

    Args:
        team_id:   The INTEGER team id to query.
        season_id: The season slug (e.g. ``"2026-spring-hs"``).  Defaults to
                   the most recent season in the ``seasons`` table.

    Returns:
        List of dicts with keys: player_id, name, jersey_number, games,
        ip_outs, h, er, bb, so, hr.
        Returns an empty list if the database is not accessible, no seasons
        exist, or the team has no season pitching rows.
    """
    query = """
        SELECT
            p.player_id,
            p.first_name || ' ' || p.last_name AS name,
            tr.jersey_number,
            COALESCE(psp.gp_pitcher, 0) AS games,
            COALESCE(psp.ip_outs, 0) AS ip_outs,
            COALESCE(psp.h, 0)             AS h,
            COALESCE(psp.er, 0)            AS er,
            COALESCE(psp.bb, 0)            AS bb,
            COALESCE(psp.so, 0)            AS so,
            COALESCE(psp.hr, 0)            AS hr,
            COALESCE(psp.pitches, 0)       AS pitches,
            COALESCE(psp.total_strikes, 0) AS total_strikes
        FROM player_season_pitching psp
        JOIN players p ON p.player_id = psp.player_id
        LEFT JOIN team_rosters tr
            ON tr.player_id = psp.player_id
            AND tr.team_id = psp.team_id
            AND tr.season_id = psp.season_id
        WHERE psp.team_id = ? AND psp.season_id = ?
        ORDER BY
            CASE WHEN COALESCE(psp.ip_outs, 0) = 0 THEN 1 ELSE 0 END ASC,
            CAST(COALESCE(psp.er, 0) AS REAL) * 27 / NULLIF(psp.ip_outs, 0) ASC NULLS LAST,
            p.last_name ASC
    """
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            if season_id is None:
                row = conn.execute(
                    "SELECT season_id FROM seasons ORDER BY season_id DESC LIMIT 1"
                ).fetchone()
                if row is None:
                    return []
                season_id = row["season_id"]
            cursor = conn.execute(query, (team_id, season_id))
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error:
        logger.exception("Failed to fetch team pitching stats")
        return []


def get_team_games(
    team_id: int,
    season_id: str,
) -> list[dict[str, Any]]:
    """Return the game list for a team in a season, sorted by date descending.

    Joins ``games`` with ``teams`` (twice, via a CASE expression) to resolve the
    opponent name and determine home/away context.

    Args:
        team_id:   The INTEGER team id to query (home or away).
        season_id: The season slug (e.g. ``"2026-spring-hs"``).

    Returns:
        List of dicts with keys: game_id, game_date, home_team_id, away_team_id,
        home_score, away_score, is_home (1 or 0), opponent_team_id, opponent_name.
        Returns an empty list on DB error.
    """
    query = """
        SELECT
            g.game_id,
            g.game_date,
            g.home_team_id,
            g.away_team_id,
            g.home_score,
            g.away_score,
            CASE WHEN g.home_team_id = :team_id THEN 1 ELSE 0 END AS is_home,
            CASE WHEN g.home_team_id = :team_id
                 THEN g.away_team_id
                 ELSE g.home_team_id
            END AS opponent_team_id,
            CASE WHEN g.home_team_id = :team_id
                 THEN opp_away.name
                 ELSE opp_home.name
            END AS opponent_name
        FROM games g
        LEFT JOIN teams opp_away ON opp_away.id = g.away_team_id
        LEFT JOIN teams opp_home ON opp_home.id = g.home_team_id
        WHERE g.season_id = :season_id
          AND (g.home_team_id = :team_id OR g.away_team_id = :team_id)
        ORDER BY g.game_date DESC
    """
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, {"team_id": team_id, "season_id": season_id})
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error:
        logger.exception("Failed to fetch team games")
        return []


def get_schedule_games(
    team_id: int,
    season_id: str,
) -> list[dict[str, Any]]:
    """Return all games for a team in a season sorted by date ascending.

    Extends ``get_team_games`` with game status, scouting status (has_stats),
    and opponent win/loss record.  Intended for the schedule landing page.

    Args:
        team_id:   The INTEGER team id (home or away).
        season_id: The season slug (e.g. ``"2026-spring-hs"``).

    Returns:
        List of dicts with keys: game_id, game_date, status,
        home_score, away_score, is_home (1 or 0), opponent_team_id,
        opponent_name, has_stats (1 or 0), opponent_wins, opponent_losses.
        Returns an empty list on DB error.
    """
    query = """
        WITH opp_has_stats AS (
            SELECT DISTINCT team_id FROM player_season_batting WHERE season_id = :season_id
            UNION
            SELECT DISTINCT team_id FROM player_season_pitching WHERE season_id = :season_id
        ),
        opp_game_results AS (
            SELECT home_team_id AS team_id,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END AS is_win,
                   CASE WHEN away_score > home_score THEN 1 ELSE 0 END AS is_loss
            FROM games
            WHERE season_id = :season_id
              AND home_score IS NOT NULL AND away_score IS NOT NULL
              AND status = 'completed'
            UNION ALL
            SELECT away_team_id AS team_id,
                   CASE WHEN away_score > home_score THEN 1 ELSE 0 END AS is_win,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END AS is_loss
            FROM games
            WHERE season_id = :season_id
              AND home_score IS NOT NULL AND away_score IS NOT NULL
              AND status = 'completed'
        ),
        opp_records AS (
            SELECT team_id,
                   SUM(is_win) AS wins,
                   SUM(is_loss) AS losses
            FROM opp_game_results
            GROUP BY team_id
        )
        SELECT
            g.game_id,
            g.game_date,
            g.status,
            g.home_score,
            g.away_score,
            CASE WHEN g.home_team_id = :team_id THEN 1 ELSE 0 END AS is_home,
            CASE WHEN g.home_team_id = :team_id
                 THEN g.away_team_id
                 ELSE g.home_team_id
            END AS opponent_team_id,
            CASE WHEN g.home_team_id = :team_id
                 THEN opp_away.name
                 ELSE opp_home.name
            END AS opponent_name,
            CASE WHEN ohs.team_id IS NOT NULL THEN 1 ELSE 0 END AS has_stats,
            COALESCE(opp_rec.wins, 0) AS opponent_wins,
            COALESCE(opp_rec.losses, 0) AS opponent_losses
        FROM games g
        LEFT JOIN teams opp_away ON opp_away.id = g.away_team_id
        LEFT JOIN teams opp_home ON opp_home.id = g.home_team_id
        LEFT JOIN opp_has_stats ohs ON ohs.team_id = (
            CASE WHEN g.home_team_id = :team_id THEN g.away_team_id ELSE g.home_team_id END
        )
        LEFT JOIN opp_records opp_rec ON opp_rec.team_id = (
            CASE WHEN g.home_team_id = :team_id THEN g.away_team_id ELSE g.home_team_id END
        )
        WHERE g.season_id = :season_id
          AND (g.home_team_id = :team_id OR g.away_team_id = :team_id)
        ORDER BY g.game_date ASC
    """
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, {"team_id": team_id, "season_id": season_id})
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error:
        logger.exception("Failed to fetch schedule games")
        return []


def _apply_name_cascade(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply the fallback display name cascade to player rows.

    Transforms ``name`` from ``'Unknown Unknown'`` to ``'Player #NN'`` (when
    ``jersey_number`` is available) or ``'Unknown Player'`` (no jersey number).
    Sets ``name_unresolved = True`` on affected rows for template styling.

    Rows with real names are returned unchanged (``name_unresolved = False``).
    """
    for row in rows:
        if row.get("name") == "Unknown Unknown":
            jersey = row.get("jersey_number")
            if jersey:
                row["name"] = f"Player #{jersey}"
            else:
                row["name"] = "Unknown Player"
            row["name_unresolved"] = True
        else:
            row["name_unresolved"] = False
    return rows


def get_game_box_score(game_id: str) -> dict[str, Any]:
    """Return the full box score for a game: batting and pitching lines for both teams.

    Queries ``player_game_batting`` and ``player_game_pitching`` joined with
    ``players`` and ``teams``, returning per-player lines grouped by team.

    Also returns top-level game metadata (game_date, home_team_id, away_team_id,
    home_score, away_score).  The ``home_team_id`` and ``away_team_id`` values
    are INTEGER references to ``teams.id``.

    Args:
        game_id: The game identifier.

    Returns:
        Dict with keys:
            - ``game``: dict with game_id, game_date, home_team_id (int),
              away_team_id (int), home_score, away_score, home_team_name,
              away_team_name
            - ``teams``: list of two dicts, each with:
                - id (int), team_name
                - batting_lines: list of player batting dicts
                - pitching_lines: list of player pitching dicts
        Returns ``{}`` on DB error or missing game.
    """
    game_query = """
        SELECT
            g.game_id,
            g.game_date,
            g.season_id,
            g.home_team_id,
            g.away_team_id,
            g.home_score,
            g.away_score,
            th.name AS home_team_name,
            ta.name AS away_team_name
        FROM games g
        LEFT JOIN teams th ON th.id = g.home_team_id
        LEFT JOIN teams ta ON ta.id = g.away_team_id
        WHERE g.game_id = ?
    """
    batting_query = """
        SELECT
            pgb.player_id,
            p.first_name || ' ' || p.last_name AS name,
            pgb.team_id,
            COALESCE(pgb.ab, 0)      AS ab,
            COALESCE(pgb.h, 0)       AS h,
            COALESCE(pgb.doubles, 0) AS doubles,
            COALESCE(pgb.triples, 0) AS triples,
            COALESCE(pgb.hr, 0)      AS hr,
            COALESCE(pgb.rbi, 0)     AS rbi,
            COALESCE(pgb.bb, 0)      AS bb,
            COALESCE(pgb.so, 0)      AS so,
            COALESCE(pgb.sb, 0)      AS sb,
            tr.jersey_number
        FROM player_game_batting pgb
        JOIN players p ON p.player_id = pgb.player_id
        LEFT JOIN team_rosters tr
            ON tr.player_id = pgb.player_id
            AND tr.team_id = pgb.team_id
            AND tr.season_id = ?
        WHERE pgb.game_id = ?
        ORDER BY pgb.team_id, p.last_name
    """
    pitching_query = """
        SELECT
            pgp.player_id,
            p.first_name || ' ' || p.last_name AS name,
            pgp.team_id,
            COALESCE(pgp.ip_outs, 0)       AS ip_outs,
            COALESCE(pgp.h, 0)             AS h,
            COALESCE(pgp.er, 0)            AS er,
            COALESCE(pgp.bb, 0)            AS bb,
            COALESCE(pgp.so, 0)            AS so,
            COALESCE(pgp.pitches, 0)       AS pitches,
            COALESCE(pgp.total_strikes, 0) AS total_strikes,
            tr.jersey_number
        FROM player_game_pitching pgp
        JOIN players p ON p.player_id = pgp.player_id
        LEFT JOIN team_rosters tr
            ON tr.player_id = pgp.player_id
            AND tr.team_id = pgp.team_id
            AND tr.season_id = ?
        WHERE pgp.game_id = ?
        ORDER BY pgp.team_id, p.last_name
    """
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            game_row = conn.execute(game_query, (game_id,)).fetchone()
            if game_row is None:
                return {}
            game = dict(game_row)
            season_id = game["season_id"]
            batting_rows = [
                dict(r)
                for r in conn.execute(batting_query, (season_id, game_id)).fetchall()
            ]
            pitching_rows = [
                dict(r)
                for r in conn.execute(pitching_query, (season_id, game_id)).fetchall()
            ]
    except sqlite3.Error:
        logger.exception("Failed to fetch game box score")
        return {}

    _apply_name_cascade(batting_rows)
    _apply_name_cascade(pitching_rows)

    # Group batting and pitching lines by team_id (INTEGER)
    batting_by_team: dict[int, list[dict[str, Any]]] = {}
    for row in batting_rows:
        batting_by_team.setdefault(row["team_id"], []).append(row)

    pitching_by_team: dict[int, list[dict[str, Any]]] = {}
    for row in pitching_rows:
        pitching_by_team.setdefault(row["team_id"], []).append(row)

    home_id: int = game["home_team_id"]
    away_id: int = game["away_team_id"]
    team_ids = [home_id, away_id]

    teams_data = []
    for tid in team_ids:
        team_name = game["home_team_name"] if tid == home_id else game["away_team_name"]
        teams_data.append(
            {
                "id": tid,
                "team_name": team_name or str(tid),
                "batting_lines": batting_by_team.get(tid, []),
                "pitching_lines": pitching_by_team.get(tid, []),
            }
        )

    return {"game": game, "teams": teams_data}


def get_team_opponents(
    team_id: int,
    season_id: str,
) -> list[dict[str, Any]]:
    """Return all opponents the given team has faced, will face, or is linked to in a season.

    Primary source: ``games`` table (grouped by opponent, with W-L record and dates).
    Fallback source: ``team_opponents`` junction table for opponents with no game rows yet.
    The two sources are merged in Python; games-based rows always take precedence.

    For opponents from ``team_opponents`` with no game data, ``games_played``,
    ``wins``, and ``losses`` are 0 and date columns are None.  The template
    renders ``games_played == 0`` as ``--`` per TN-3.

    The ``first_seen_year`` filter uses the first 4 characters of ``season_id``
    to bridge the INTEGER/TEXT impedance mismatch (e.g. ``"2026-spring-hs"`` → 2026).

    Args:
        team_id:   The INTEGER team id to query (home or away side).
        season_id: The season slug (e.g. ``"2026-spring-hs"``).

    Returns:
        List of dicts with keys: opponent_team_id, opponent_name, games_played,
        wins, losses, next_game_date (ISO date str or None), last_game_date
        (ISO date str or None).  Sorted by opponent_name ASC.
        Returns an empty list on DB error.
    """
    games_query = """
        SELECT
            CASE WHEN g.home_team_id = :team_id
                 THEN g.away_team_id
                 ELSE g.home_team_id
            END AS opponent_team_id,
            CASE WHEN g.home_team_id = :team_id
                 THEN opp_away.name
                 ELSE opp_home.name
            END AS opponent_name,
            COUNT(*) AS games_played,
            SUM(CASE
                WHEN g.home_score IS NOT NULL AND g.away_score IS NOT NULL
                 AND g.home_team_id = :team_id AND g.home_score > g.away_score THEN 1
                WHEN g.home_score IS NOT NULL AND g.away_score IS NOT NULL
                 AND g.away_team_id = :team_id AND g.away_score > g.home_score THEN 1
                ELSE 0
            END) AS wins,
            SUM(CASE
                WHEN g.home_score IS NOT NULL AND g.away_score IS NOT NULL
                 AND g.home_team_id = :team_id AND g.home_score < g.away_score THEN 1
                WHEN g.home_score IS NOT NULL AND g.away_score IS NOT NULL
                 AND g.away_team_id = :team_id AND g.away_score < g.home_score THEN 1
                ELSE 0
            END) AS losses,
            MIN(CASE WHEN g.game_date >= date('now') AND g.status != 'completed'
                     THEN g.game_date END) AS next_game_date,
            MAX(CASE WHEN g.status = 'completed' THEN g.game_date END) AS last_game_date
        FROM games g
        LEFT JOIN teams opp_away ON opp_away.id = g.away_team_id
        LEFT JOIN teams opp_home ON opp_home.id = g.home_team_id
        WHERE g.season_id = :season_id
          AND (g.home_team_id = :team_id OR g.away_team_id = :team_id)
        GROUP BY opponent_team_id, opponent_name
        ORDER BY opponent_name ASC
    """
    junction_query = """
        SELECT
            to_.opponent_team_id,
            t.name AS opponent_name,
            0 AS games_played,
            0 AS wins,
            0 AS losses,
            NULL AS next_game_date,
            NULL AS last_game_date
        FROM team_opponents to_
        JOIN teams t ON t.id = to_.opponent_team_id
        WHERE to_.our_team_id = :team_id
          AND to_.first_seen_year = CAST(substr(:season_id, 1, 4) AS INTEGER)
        ORDER BY t.name ASC
    """
    params = {"team_id": team_id, "season_id": season_id}
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            games_rows = [dict(r) for r in conn.execute(games_query, params).fetchall()]
            junction_rows = [dict(r) for r in conn.execute(junction_query, params).fetchall()]

        # Build result from games rows; supplement with junction rows not already present.
        seen_ids = {r["opponent_team_id"] for r in games_rows}
        fallback_rows = [r for r in junction_rows if r["opponent_team_id"] not in seen_ids]
        combined = games_rows + fallback_rows
        combined.sort(key=lambda r: (r["opponent_name"] or "").lower())
        return combined
    except sqlite3.Error:
        logger.exception("Failed to fetch team opponents")
        return []


def get_opponent_scouting_report(
    opponent_team_id: int,
    season_id: str,
) -> dict[str, Any]:
    """Return batting and pitching stats for an opponent team in a season.

    Queries ``player_season_batting`` and ``player_season_pitching`` for the
    given team id and season_id.  Results are sorted by AVG desc (batting) and
    ERA asc (pitching).

    Also returns the opponent team name from the ``teams`` table, and the
    opponent's season record (wins/losses from ``games``).

    Args:
        opponent_team_id: The opponent's INTEGER team id.
        season_id:        The season slug (e.g. ``"2026-spring-hs"``).

    Returns:
        Dict with keys:
            - ``team_name``: display name or str(opponent_team_id) fallback
            - ``record``: dict with wins/losses (int), or None if no games
            - ``batting``: list of dicts (player_id, name, games, ab, h,
              doubles, triples, hr, rbi, bb, so, sb)
            - ``pitching``: list of dicts (player_id, name, games, ip_outs,
              h, er, bb, so, pitches)
        Returns an empty dict on DB error.
    """
    team_query = "SELECT name FROM teams WHERE id = ?"
    record_query = """
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
    """
    batting_query = """
        SELECT
            p.player_id,
            p.first_name || ' ' || p.last_name AS name,
            COALESCE(psb.gp, 0)      AS games,
            COALESCE(psb.ab, 0)      AS ab,
            COALESCE(psb.h, 0)       AS h,
            COALESCE(psb.doubles, 0) AS doubles,
            COALESCE(psb.triples, 0) AS triples,
            COALESCE(psb.hr, 0)      AS hr,
            COALESCE(psb.rbi, 0)     AS rbi,
            COALESCE(psb.bb, 0)      AS bb,
            COALESCE(psb.so, 0)      AS so,
            COALESCE(psb.sb, 0)      AS sb,
            COALESCE(psb.hbp, 0)     AS hbp,
            COALESCE(psb.shf, 0)     AS shf,
            COALESCE(psb.tb, 0)      AS tb,
            tr.jersey_number
        FROM player_season_batting psb
        JOIN players p ON p.player_id = psb.player_id
        LEFT JOIN team_rosters tr
            ON tr.player_id = psb.player_id
            AND tr.team_id = psb.team_id
            AND tr.season_id = psb.season_id
        WHERE psb.team_id = ? AND psb.season_id = ?
        ORDER BY
            CASE WHEN COALESCE(psb.ab, 0) = 0 THEN 1 ELSE 0 END ASC,
            CAST(COALESCE(psb.h, 0) AS REAL) / NULLIF(psb.ab, 0) DESC NULLS LAST,
            p.last_name ASC
    """
    pitching_query = """
        SELECT
            p.player_id,
            p.first_name || ' ' || p.last_name AS name,
            COALESCE(psp.gp_pitcher, 0)    AS games,
            COALESCE(psp.ip_outs, 0)       AS ip_outs,
            COALESCE(psp.h, 0)             AS h,
            COALESCE(psp.er, 0)            AS er,
            COALESCE(psp.bb, 0)            AS bb,
            COALESCE(psp.so, 0)            AS so,
            COALESCE(psp.pitches, 0)       AS pitches,
            COALESCE(psp.total_strikes, 0) AS total_strikes,
            p.throws,
            tr.jersey_number
        FROM player_season_pitching psp
        JOIN players p ON p.player_id = psp.player_id
        LEFT JOIN team_rosters tr
            ON tr.player_id = psp.player_id
            AND tr.team_id = psp.team_id
            AND tr.season_id = psp.season_id
        WHERE psp.team_id = ? AND psp.season_id = ?
        ORDER BY
            CASE WHEN COALESCE(psp.ip_outs, 0) = 0 THEN 1 ELSE 0 END ASC,
            CAST(COALESCE(psp.er, 0) AS REAL) * 27 / NULLIF(psp.ip_outs, 0) ASC NULLS LAST,
            p.last_name ASC
    """
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            team_row = conn.execute(team_query, (opponent_team_id,)).fetchone()
            team_name = dict(team_row)["name"] if team_row else str(opponent_team_id)
            record_row = conn.execute(
                record_query, {"tid": opponent_team_id, "season_id": season_id}
            ).fetchone()
            record: dict[str, int] | None = None
            if record_row:
                r = dict(record_row)
                record = {"wins": r["wins"] or 0, "losses": r["losses"] or 0}
            batting_rows = [
                dict(r)
                for r in conn.execute(batting_query, (opponent_team_id, season_id)).fetchall()
            ]
            pitching_rows = [
                dict(r)
                for r in conn.execute(pitching_query, (opponent_team_id, season_id)).fetchall()
            ]
        _apply_name_cascade(batting_rows)
        _apply_name_cascade(pitching_rows)
        return {
            "team_name": team_name,
            "record": record,
            "batting": batting_rows,
            "pitching": pitching_rows,
        }
    except sqlite3.Error:
        logger.exception("Failed to fetch opponent scouting report")
        return {}


def get_last_meeting(
    team_id: int,
    opponent_team_id: int,
    season_id: str,
) -> dict[str, Any] | None:
    """Return the most recent completed game between two teams in a season.

    Looks for the latest game where one side is ``team_id`` and the other is
    ``opponent_team_id``, with ``status = 'completed'`` and scores recorded.

    Args:
        team_id:          The user's active INTEGER team id.
        opponent_team_id: The opponent's INTEGER team id.
        season_id:        The season slug (e.g. ``"2026-spring-hs"``).

    Returns:
        Dict with keys: game_id, game_date, home_score, away_score, is_home
        (1 if team_id is home), or None if no completed game exists.
    """
    query = """
        SELECT
            g.game_id,
            g.game_date,
            g.home_score,
            g.away_score,
            CASE WHEN g.home_team_id = :team_id THEN 1 ELSE 0 END AS is_home
        FROM games g
        WHERE g.season_id = :season_id
          AND g.status = 'completed'
          AND g.home_score IS NOT NULL
          AND g.away_score IS NOT NULL
          AND (
              (g.home_team_id = :team_id AND g.away_team_id = :opp_id)
              OR
              (g.away_team_id = :team_id AND g.home_team_id = :opp_id)
          )
        ORDER BY g.game_date DESC
        LIMIT 1
    """
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                query,
                {"team_id": team_id, "opp_id": opponent_team_id, "season_id": season_id},
            ).fetchone()
        return dict(row) if row else None
    except sqlite3.Error:
        logger.exception("Failed to fetch last meeting")
        return None


def get_player_profile(player_id: str) -> dict[str, Any]:
    """Return full career profile for a player: info, batting seasons, pitching seasons, recent games.

    Four queries:
        (a) player info from ``players``
        (b) batting seasons from ``player_season_batting`` joined with ``seasons`` and ``teams``
        (c) pitching seasons from ``player_season_pitching`` joined with ``seasons`` and ``teams``
        (d) last 5 distinct games from ``player_game_batting`` and ``player_game_pitching``

    Args:
        player_id: The player's UUID.

    Returns:
        Dict with keys:
            - ``player``: dict with player_id, first_name, last_name
            - ``batting_seasons``: list of dicts sorted by season_id desc
            - ``pitching_seasons``: list of dicts sorted by season_id desc
            - ``recent_games``: list of up to 5 dicts sorted by game_date desc
        Returns ``{}`` if the player_id does not exist.
        Returns ``{}`` on DB error.
    """
    player_query = """
        SELECT player_id, first_name, last_name
        FROM players
        WHERE player_id = ?
    """
    batting_query = """
        SELECT
            psb.season_id,
            s.name        AS season_name,
            psb.team_id,
            t.name        AS team_name,
            COALESCE(psb.gp, 0)      AS games,
            COALESCE(psb.ab, 0)      AS ab,
            COALESCE(psb.h, 0)       AS h,
            COALESCE(psb.doubles, 0) AS doubles,
            COALESCE(psb.triples, 0) AS triples,
            COALESCE(psb.hr, 0)      AS hr,
            COALESCE(psb.rbi, 0)     AS rbi,
            COALESCE(psb.bb, 0)      AS bb,
            COALESCE(psb.so, 0)      AS so,
            COALESCE(psb.sb, 0)      AS sb,
            COALESCE(psb.hbp, 0)     AS hbp,
            COALESCE(psb.shf, 0)     AS shf
        FROM player_season_batting psb
        JOIN seasons s ON s.season_id = psb.season_id
        JOIN teams t ON t.id = psb.team_id
        WHERE psb.player_id = ?
        ORDER BY psb.season_id DESC
    """
    pitching_query = """
        SELECT
            psp.season_id,
            s.name        AS season_name,
            psp.team_id,
            t.name        AS team_name,
            COALESCE(psp.gp_pitcher, 0)    AS games,
            COALESCE(psp.ip_outs, 0)       AS ip_outs,
            COALESCE(psp.h, 0)             AS h,
            COALESCE(psp.er, 0)            AS er,
            COALESCE(psp.bb, 0)            AS bb,
            COALESCE(psp.so, 0)            AS so,
            COALESCE(psp.hr, 0)            AS hr,
            COALESCE(psp.pitches, 0)       AS pitches,
            COALESCE(psp.total_strikes, 0) AS total_strikes
        FROM player_season_pitching psp
        JOIN seasons s ON s.season_id = psp.season_id
        JOIN teams t ON t.id = psp.team_id
        WHERE psp.player_id = ?
        ORDER BY psp.season_id DESC
    """
    # Two-way player edge case: player may appear in both batting and pitching for the same game.
    # UNION the two sources and deduplicate by game_id before taking the last 5.
    recent_games_query = """
        SELECT
            g.game_id,
            g.game_date,
            CASE WHEN g.home_team_id = pgb.team_id
                 THEN opp_away.name
                 ELSE opp_home.name
            END AS opponent_name,
            pgb.ab,
            pgb.h,
            COALESCE(pgb.hr, 0) AS hr,
            COALESCE(pgb.rbi, 0) AS rbi,
            NULL AS ip_outs,
            NULL AS er,
            NULL AS so_pitched,
            'batting' AS appearance_type
        FROM player_game_batting pgb
        JOIN games g ON g.game_id = pgb.game_id
        LEFT JOIN teams opp_away ON opp_away.id = g.away_team_id
        LEFT JOIN teams opp_home ON opp_home.id = g.home_team_id
        WHERE pgb.player_id = ?

        UNION

        SELECT
            g.game_id,
            g.game_date,
            CASE WHEN g.home_team_id = pgp.team_id
                 THEN opp_away.name
                 ELSE opp_home.name
            END AS opponent_name,
            NULL AS ab,
            NULL AS h,
            NULL AS hr,
            NULL AS rbi,
            pgp.ip_outs,
            pgp.er,
            pgp.so AS so_pitched,
            'pitching' AS appearance_type
        FROM player_game_pitching pgp
        JOIN games g ON g.game_id = pgp.game_id
        LEFT JOIN teams opp_away ON opp_away.id = g.away_team_id
        LEFT JOIN teams opp_home ON opp_home.id = g.home_team_id
        WHERE pgp.player_id = ?
    """
    # All rows from both UNION arms are fetched in Python; we then take the 5 most recent
    # distinct games and return all rows for those games (including both batting and pitching
    # rows for two-way players who bat and pitch in the same game).
    jersey_query = """
        SELECT tr.jersey_number
        FROM team_rosters tr
        WHERE tr.player_id = ?
        ORDER BY tr.season_id DESC
        LIMIT 1
    """
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            player_row = conn.execute(player_query, (player_id,)).fetchone()
            if player_row is None:
                return {}
            player = dict(player_row)

            batting_rows = [dict(r) for r in conn.execute(batting_query, (player_id,)).fetchall()]
            pitching_rows = [dict(r) for r in conn.execute(pitching_query, (player_id,)).fetchall()]

            raw_games = [
                dict(r)
                for r in conn.execute(recent_games_query, (player_id, player_id)).fetchall()
            ]

            jersey_row = conn.execute(jersey_query, (player_id,)).fetchone()
            jersey_number = dict(jersey_row)["jersey_number"] if jersey_row else None

    except sqlite3.Error:
        logger.exception("Failed to fetch player profile")
        return {}

    # Return both batting and pitching rows for two-way games (a player who bats
    # and pitches in the same game has two rows -- both are needed for the full picture).
    # Identify the 5 most recent distinct games by date, then return all rows for those games.
    game_dates: dict[str, str] = {row["game_id"]: row["game_date"] for row in raw_games}
    top_game_ids = {
        gid
        for gid, _ in sorted(game_dates.items(), key=lambda x: x[1], reverse=True)[:5]
    }
    recent_games = sorted(
        [row for row in raw_games if row["game_id"] in top_game_ids],
        key=lambda r: r["game_date"],
        reverse=True,
    )

    player["jersey_number"] = jersey_number

    return {
        "player": player,
        "batting_seasons": batting_rows,
        "pitching_seasons": pitching_rows,
        "recent_games": recent_games,
    }


def bulk_create_opponents(names: list[str]) -> int:
    """Insert discovered opponent placeholder rows for names not already in the DB.

    Skips any name that already exists in the ``teams`` table (case-insensitive
    match on the ``name`` column).  New rows are inserted with:
    - ``membership_type = 'tracked'``
    - ``is_active = 0``
    - ``source = 'discovered'``
    - INTEGER PK auto-assigned by SQLite AUTOINCREMENT

    Uses ``INSERT OR IGNORE`` as a secondary safety net for any race conditions.

    Args:
        names: List of opponent display names to insert.

    Returns:
        Count of newly inserted rows.
    """
    inserted = 0
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            # Fetch existing names once, lowercase, for fast O(1) lookups
            existing_rows = conn.execute("SELECT LOWER(name) AS lname FROM teams").fetchall()
            existing_lower: set[str] = {row["lname"] for row in existing_rows}

            for name in names:
                if name.lower() in existing_lower:
                    continue
                result = conn.execute(
                    """
                    INSERT OR IGNORE INTO teams
                        (name, membership_type, is_active, source)
                    VALUES (?, 'tracked', 0, 'discovered')
                    """,
                    (name,),
                )
                existing_lower.add(name.lower())
                if result.rowcount:
                    inserted += 1

            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to bulk-create opponent placeholders")
    return inserted


_OPPONENT_LINKS_BASE_SQL = """
    SELECT
        ol.id,
        ol.our_team_id,
        t.name AS our_team_name,
        ol.opponent_name,
        ol.resolved_team_id,
        ol.public_id,
        ol.resolution_method,
        ol.resolved_at,
        ol.is_hidden
    FROM opponent_links ol
    JOIN teams t ON t.id = ol.our_team_id
    WHERE {where}
    ORDER BY t.name, ol.opponent_name
"""


def _opponent_links_where(
    our_team_id: int | None, status_filter: str | None
) -> tuple[str, list[Any]]:
    """Build WHERE clause and params for opponent_links queries."""
    if status_filter == "hidden":
        conditions: list[str] = ["ol.is_hidden = 1"]
    else:
        conditions = ["ol.is_hidden = 0"]
    params: list[Any] = []
    if our_team_id is not None:
        conditions.append("ol.our_team_id = ?")
        params.append(our_team_id)
    if status_filter == "full":
        conditions.append("ol.public_id IS NOT NULL")
    elif status_filter == "scoresheet":
        conditions.append("ol.public_id IS NULL")
    elif status_filter == "unresolved":
        conditions.append("ol.resolved_team_id IS NULL")
    return " AND ".join(conditions), params


def get_opponent_links(
    our_team_id: int | None = None,
    status_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Return opponent_links rows with optional team id and resolution-state filter.

    Args:
        our_team_id: INTEGER team id to scope to a specific owned team.
            None returns all teams.
        status_filter: ``'full'`` for resolved, ``'scoresheet'`` for unlinked, None for all.

    Returns:
        List of dicts with keys: id, our_team_id, our_team_name, opponent_name,
        resolved_team_id, public_id, resolution_method, resolved_at, is_hidden.
    """
    where, params = _opponent_links_where(our_team_id, status_filter)
    query = _OPPONENT_LINKS_BASE_SQL.format(where=where)
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error:
        logger.exception("Failed to fetch opponent links")
        return []


def get_opponent_link_counts(our_team_id: int | None = None) -> dict[str, int]:
    """Return opponent link counts by resolution state.

    Args:
        our_team_id: INTEGER team id to scope to a specific team, or None for all teams.

    Returns:
        Dict with keys: total, full_stats, scoresheet_only, unresolved, hidden.
    """
    team_cond = ""
    params: list[Any] = []
    if our_team_id is not None:
        team_cond = "AND our_team_id = ?"
        params.append(our_team_id)
    query = f"""
        SELECT
            SUM(CASE WHEN is_hidden = 0 THEN 1 ELSE 0 END) AS total,
            SUM(CASE WHEN is_hidden = 0 AND public_id IS NOT NULL THEN 1 ELSE 0 END) AS full_stats,
            SUM(CASE WHEN is_hidden = 0 AND public_id IS NULL THEN 1 ELSE 0 END) AS scoresheet_only,
            SUM(CASE WHEN is_hidden = 0 AND resolved_team_id IS NULL THEN 1 ELSE 0 END) AS unresolved,
            SUM(CASE WHEN is_hidden = 1 THEN 1 ELSE 0 END) AS hidden
        FROM opponent_links
        WHERE 1=1 {team_cond}
    """
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(query, params).fetchone()
        if row:
            r = dict(row)
            return {
                "total": r["total"] or 0,
                "full_stats": r["full_stats"] or 0,
                "scoresheet_only": r["scoresheet_only"] or 0,
                "unresolved": r["unresolved"] or 0,
                "hidden": r["hidden"] or 0,
            }
    except sqlite3.Error:
        logger.exception("Failed to count opponent links")
    return {"total": 0, "full_stats": 0, "scoresheet_only": 0, "unresolved": 0, "hidden": 0}


def get_opponent_link_by_id(link_id: int) -> dict[str, Any] | None:
    """Fetch a single opponent_links row by id.

    Args:
        link_id: The opponent_links primary key.

    Returns:
        Dict with link data, or None if not found.
    """
    query = """
        SELECT
            ol.id,
            ol.our_team_id,
            t.name AS our_team_name,
            ol.opponent_name,
            ol.resolved_team_id,
            ol.public_id,
            ol.resolution_method,
            ol.resolved_at,
            ol.is_hidden
        FROM opponent_links ol
        JOIN teams t ON t.id = ol.our_team_id
        WHERE ol.id = ?
    """
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(query, (link_id,)).fetchone()
        return dict(row) if row else None
    except sqlite3.Error:
        logger.exception("Failed to fetch opponent link %s", link_id)
        return None


def is_member_team_public_id(public_id: str) -> bool:
    """Return True if the public_id belongs to a member (LSB) team.

    Args:
        public_id: The public_id slug to check.

    Returns:
        True if a member team has this public_id.
    """
    try:
        with closing(get_connection()) as conn:
            row = conn.execute(
                "SELECT 1 FROM teams WHERE public_id = ? AND membership_type = 'member'",
                (public_id,),
            ).fetchone()
        return row is not None
    except sqlite3.Error:
        logger.exception("Failed to check member team public_id %s", public_id)
        return False


def get_duplicate_opponent_name(
    public_id: str,
    our_team_id: int,
    exclude_id: int | None = None,
) -> str | None:
    """Return the opponent_name of an existing row that already uses this public_id.

    The check is scoped to ``our_team_id`` so that different teams sharing the
    same opponent ``public_id`` do not produce spurious duplicate warnings.

    Args:
        public_id: The public_id slug to check.
        our_team_id: The owning INTEGER team id -- only rows for this team are checked.
        exclude_id: opponent_links.id to exclude (for updates).

    Returns:
        The opponent_name string if a duplicate exists within the same team, else None.
    """
    try:
        with closing(get_connection()) as conn:
            if exclude_id is not None:
                row = conn.execute(
                    "SELECT opponent_name FROM opponent_links"
                    " WHERE public_id = ? AND our_team_id = ? AND id != ?",
                    (public_id, our_team_id, exclude_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT opponent_name FROM opponent_links"
                    " WHERE public_id = ? AND our_team_id = ?",
                    (public_id, our_team_id),
                ).fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        logger.exception("Failed to fetch duplicate opponent name for %s", public_id)
        return None


def _find_tracked_stub(
    conn: sqlite3.Connection,
    our_team_id: int,
    opponent_name: str,
) -> int | None:
    """Find the INTEGER PK of a tracked team stub for the given opponent.

    Two-tier lookup:
    (a) Primary: team_opponents join to teams where our_team_id matches,
        teams.name = opponent_name, teams.membership_type = 'tracked'.
    (b) Fallback: direct teams match on name + membership_type = 'tracked'.

    Tie-break: prefer rows with public_id IS NULL; if multiple null-slug stubs,
    prefer highest id.  If no null-slug candidates and multiple non-null stubs,
    return None (graceful degradation).

    Args:
        conn: An open SQLite connection.
        our_team_id: The member team's INTEGER PK.
        opponent_name: The opponent name to match.

    Returns:
        The stub team's INTEGER PK, or None if not found.
    """
    rows = conn.execute(
        """
        SELECT t.id, t.public_id
        FROM teams t
        JOIN team_opponents toop ON toop.opponent_team_id = t.id
        WHERE toop.our_team_id = ?
          AND t.name = ?
          AND t.membership_type = 'tracked'
        """,
        (our_team_id, opponent_name),
    ).fetchall()

    if not rows:
        rows = conn.execute(
            """
            SELECT id, public_id
            FROM teams
            WHERE name = ?
              AND membership_type = 'tracked'
            """,
            (opponent_name,),
        ).fetchall()

    if not rows:
        return None

    null_rows = [r[0] for r in rows if r[1] is None]
    if null_rows:
        return max(null_rows)
    if len(rows) == 1:
        return rows[0][0]
    return None


def save_manual_opponent_link(
    link_id: int,
    public_id: str,
    our_team_id: int,
    opponent_name: str,
) -> dict[str, Any]:
    """Set public_id and resolution_method='manual' on an opponent_links row.

    Also finds the existing tracked team stub (via team_opponents or direct name
    match) and sets teams.public_id and opponent_links.resolved_team_id.

    If the stub has no public_id (None) and the target public_id is already owned
    by another teams row, the stub is left unchanged and resolved_team_id is set to
    the existing team's id (merge path).  The return value signals this to the caller.

    If the stub already has a non-NULL public_id that differs from the new slug:
    - If the new slug is not owned by another teams row, overwrites with a WARNING.
    - If the new slug is already owned by another teams row, merges like the None
      branch: skips the overwrite, sets resolved_team_id to the existing team, and
      returns merged=True.
    In all cases where a stub is found, resolved_team_id is set.

    Args:
        link_id: The opponent_links primary key.
        public_id: The GameChanger public_id slug.
        our_team_id: The member team's INTEGER PK.
        opponent_name: The opponent name (used for stub team lookup).

    Returns:
        A dict with keys:
        - ``merged`` (bool): True when resolved_team_id was pointed to an existing
          team that already owned the public_id (instead of the stub).
        - ``merged_team_name`` (str | None): Name of the existing team when merged,
          else None.
    """
    result: dict[str, Any] = {"merged": False, "merged_team_name": None}
    try:
        with closing(get_connection()) as conn:
            conn.execute(
                """
                UPDATE opponent_links
                SET public_id          = ?,
                    resolution_method  = 'manual',
                    resolved_team_id   = NULL,
                    resolved_at        = datetime('now')
                WHERE id = ?
                """,
                (public_id, link_id),
            )

            stub_id = _find_tracked_stub(conn, our_team_id, opponent_name)

            if stub_id is not None:
                existing_row = conn.execute(
                    "SELECT public_id FROM teams WHERE id = ?", (stub_id,)
                ).fetchone()
                existing_public_id = existing_row[0] if existing_row else None

                resolved_id = stub_id

                if existing_public_id is None:
                    collision = conn.execute(
                        "SELECT id, name FROM teams WHERE public_id = ? AND id != ?",
                        (public_id, stub_id),
                    ).fetchone()
                    if collision:
                        logger.warning(
                            "Slug %r already owned by teams.id=%d (%r) — merging link %d "
                            "to existing team (stub team %d left unchanged)",
                            public_id, collision[0], collision[1], link_id, stub_id,
                        )
                        resolved_id = collision[0]
                        result = {"merged": True, "merged_team_name": collision[1]}
                    else:
                        conn.execute(
                            "UPDATE teams SET public_id = ? WHERE id = ?",
                            (public_id, stub_id),
                        )
                elif existing_public_id != public_id:
                    collision = conn.execute(
                        "SELECT id, name FROM teams WHERE public_id = ? AND id != ?",
                        (public_id, stub_id),
                    ).fetchone()
                    if collision:
                        logger.warning(
                            "Slug %r already owned by teams.id=%d (%r) — merging link %d "
                            "to existing team (stub team %d left unchanged)",
                            public_id, collision[0], collision[1], link_id, stub_id,
                        )
                        resolved_id = collision[0]
                        result = {"merged": True, "merged_team_name": collision[1]}
                    else:
                        logger.warning(
                            "Overwriting existing public_id=%r with %r on stub team %d "
                            "(opponent link %d)",
                            existing_public_id, public_id, stub_id, link_id,
                        )
                        conn.execute(
                            "UPDATE teams SET public_id = ? WHERE id = ?",
                            (public_id, stub_id),
                        )

                conn.execute(
                    "UPDATE opponent_links SET resolved_team_id = ? WHERE id = ?",
                    (resolved_id, link_id),
                )

            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to save manual opponent link %s -> %s", link_id, public_id)
        raise

    return result


def get_team_name_by_public_id(public_id: str) -> str | None:
    """Return the name of any team row that owns the given public_id.

    Used by the confirm page to warn when a public_id is already claimed by an
    existing teams row (a different check from the opponent_links duplicate warning).

    Args:
        public_id: The GameChanger public_id slug to look up.

    Returns:
        The team name if a row exists, else None.
    """
    try:
        with closing(get_connection()) as conn:
            row = conn.execute(
                "SELECT name FROM teams WHERE public_id = ?", (public_id,)
            ).fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        logger.exception("Failed to look up team name for public_id %s", public_id)
        return None


def disconnect_opponent_link(link_id: int) -> bool:
    """Remove a manual link from an opponent_links row.

    Only removes links where resolution_method='manual'.  Returns False if the
    link is auto-resolved (which would be re-created by the resolver) or if the
    row does not exist.

    When the link has a resolved_team_id, also clears teams.public_id on the
    stub team — unless other opponent_links rows reference the same
    resolved_team_id (shared-reference guard).

    Args:
        link_id: The opponent_links primary key.

    Returns:
        True if successfully disconnected, False if not a manual link or not found.
    """
    try:
        with closing(get_connection()) as conn:
            row = conn.execute(
                "SELECT resolution_method, resolved_team_id, our_team_id, opponent_name"
                " FROM opponent_links WHERE id = ?",
                (link_id,),
            ).fetchone()
            if row is None:
                return False
            resolution_method, resolved_team_id, our_team_id, opponent_name = row
            if resolution_method != "manual":
                return False
            conn.execute(
                """
                UPDATE opponent_links
                SET public_id         = NULL,
                    resolution_method = NULL,
                    resolved_team_id  = NULL,
                    resolved_at       = NULL
                WHERE id = ?
                """,
                (link_id,),
            )
            if resolved_team_id is not None:
                # Guard: do not clear public_id when the link was resolved via
                # the merge path (collision found in the None-branch of
                # save_manual_opponent_link).  In that path, resolved_team_id
                # points to a pre-existing team whose public_id was NOT set by
                # this link.  Detect merge by re-running the stub lookup: if
                # the current stub (public_id-NULL tracked team) differs from
                # resolved_team_id, this was a merge and we must skip the clear.
                stub_id = _find_tracked_stub(conn, our_team_id, opponent_name)
                is_merge = stub_id is not None and stub_id != resolved_team_id
                if not is_merge:
                    other = conn.execute(
                        "SELECT 1 FROM opponent_links WHERE resolved_team_id = ? AND id != ?",
                        (resolved_team_id, link_id),
                    ).fetchone()
                    if other is None:
                        conn.execute(
                            "UPDATE teams SET public_id = NULL WHERE id = ?",
                            (resolved_team_id,),
                        )
            conn.commit()
        return True
    except sqlite3.Error:
        logger.exception("Failed to disconnect opponent link %s", link_id)
        return False


def count_all_opponent_links() -> int:
    """Return total non-hidden opponent_links row count across all teams.

    Returns:
        Integer count.
    """
    try:
        with closing(get_connection()) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM opponent_links WHERE is_hidden = 0"
            ).fetchone()
        return row[0] if row else 0
    except sqlite3.Error:
        logger.exception("Failed to count all opponent links")
        return 0


def get_opponent_link_count_for_team(our_team_id: int) -> int:
    """Return the non-hidden opponent_links count for a specific owned team.

    Args:
        our_team_id: The INTEGER team id to count for.

    Returns:
        Integer count.
    """
    try:
        with closing(get_connection()) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM opponent_links WHERE our_team_id = ? AND is_hidden = 0",
                (our_team_id,),
            ).fetchone()
        return row[0] if row else 0
    except sqlite3.Error:
        logger.exception("Failed to count opponent links for team %d", our_team_id)
        return 0


def get_team_year_map(team_ids: list[int]) -> dict[int, int]:
    """Return a mapping of team_id → year for the given team IDs.

    Reads ``teams.season_year`` directly.  Teams whose ``season_year`` is
    NULL fall back to the current calendar year so they remain visible in
    the dashboard year selector and team pill list.

    Only team IDs that exist in the ``teams`` table are included in the
    result.  Stale IDs (e.g. from permission lists referencing deleted
    teams) are silently omitted -- callers should not assume every input
    ID appears in the output.

    Args:
        team_ids: List of INTEGER team ids to look up.

    Returns:
        Dict mapping ``team_id → year`` for every id in ``team_ids``
        that exists in the ``teams`` table.  Teams with an explicit
        ``season_year`` use that value; teams with NULL map to the
        current calendar year.  Empty dict if ``team_ids`` is empty or
        on DB error.
    """
    if not team_ids:
        return {}
    placeholders = ",".join("?" for _ in team_ids)
    query = f"SELECT id, season_year FROM teams WHERE id IN ({placeholders})"
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, list(team_ids)).fetchall()
        current_year = datetime.date.today().year
        return {
            row["id"]: row["season_year"] if row["season_year"] is not None else current_year
            for row in rows
        }
    except sqlite3.Error:
        logger.exception("Failed to fetch team year map")
        return {}


def get_teams_with_stat_data(team_ids: list[int]) -> set[int]:
    """Return the subset of team ids that have actual rows in the stat tables.

    Queries ``player_season_batting`` and ``player_season_pitching`` for the
    given team ids and returns only those with at least one row.  This is the
    authoritative ``has_stat_data`` signal -- after the year-map fallback,
    every team appears in ``get_team_year_map``, so callers must use this
    function to distinguish teams with real data from fallback teams.

    Args:
        team_ids: List of INTEGER team ids to check.

    Returns:
        Set of INTEGER team ids that have at least one stat row.  Empty set
        if ``team_ids`` is empty or on DB error.
    """
    if not team_ids:
        return set()
    placeholders = ",".join("?" for _ in team_ids)
    query = f"""
        SELECT DISTINCT team_id
        FROM (
            SELECT team_id FROM player_season_batting WHERE team_id IN ({placeholders})
            UNION
            SELECT team_id FROM player_season_pitching WHERE team_id IN ({placeholders})
        )
    """
    params = list(team_ids) + list(team_ids)
    try:
        with closing(get_connection()) as conn:
            rows = conn.execute(query, params).fetchall()
        return {row[0] for row in rows}
    except sqlite3.Error:
        logger.exception("Failed to fetch teams with stat data")
        return set()


def get_available_seasons(team_id: int) -> list[dict[str, Any]]:
    """Return the distinct seasons for which a team has batting or pitching data.

    Queries ``player_season_batting`` and ``player_season_pitching`` for the
    given team id, deduplicates via UNION, and returns results ordered
    most-recent first (lexicographic DESC on the ``YYYY-type[-class]`` format).

    Args:
        team_id: The INTEGER team id.

    Returns:
        List of dicts with key ``season_id``, ordered most-recent first.
        Returns an empty list if no data exists or on DB error.
    """
    query = """
        SELECT DISTINCT season_id FROM player_season_batting WHERE team_id = ?
        UNION
        SELECT DISTINCT season_id FROM player_season_pitching WHERE team_id = ?
        ORDER BY season_id DESC
    """
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, (team_id, team_id)).fetchall()
        return [{"season_id": row["season_id"]} for row in rows]
    except sqlite3.Error:
        logger.exception("Failed to fetch available seasons for team %d", team_id)
        return []


def get_opponent_scouting_status(
    opponent_team_id: int,
    our_team_id: int | None,
    season_id: str,
) -> dict[str, Any]:
    """Determine the scouting status of an opponent team.

    Three mutually exclusive states:
    - ``'full_stats'``: at least one row in ``player_season_batting`` or
      ``player_season_pitching`` for this team_id + season_id.
    - ``'linked_unscouted'``: opponent has a resolved ``opponent_links`` row
      for ``our_team_id`` (``resolved_team_id IS NOT NULL``), or the opponent's
      ``teams.public_id IS NOT NULL`` -- but no stat rows.
    - ``'unlinked'``: no resolved link and no public_id and no stat rows.

    Args:
        opponent_team_id: The opponent's INTEGER team id.
        our_team_id:      The active member team's INTEGER id; used to scope
                          the ``opponent_links`` lookup.  May be None.
        season_id:        The season slug (e.g. ``"2026-spring-hs"``).

    Returns:
        Dict with keys:
            - ``status``: ``'full_stats'`` | ``'linked_unscouted'`` | ``'unlinked'``
            - ``link_id``: ``opponent_links.id`` (int) if any ``opponent_links``
              row exists for ``our_team_id`` -- either a resolved row
              (``resolved_team_id = opponent_team_id``) or an unresolved row
              matched by opponent name (``resolved_team_id IS NULL``).  ``None``
              when no row exists.  Used by the caller to construct the admin
              shortcut URL (``/admin/opponents/{link_id}/connect``).
    """
    try:
        with closing(get_connection()) as conn:
            # 1. Check if stat rows exist for this opponent + season.
            stats_row = conn.execute(
                """
                SELECT 1 FROM (
                    SELECT 1 FROM player_season_batting
                     WHERE team_id = ? AND season_id = ?
                    UNION ALL
                    SELECT 1 FROM player_season_pitching
                     WHERE team_id = ? AND season_id = ?
                ) LIMIT 1
                """,
                (opponent_team_id, season_id, opponent_team_id, season_id),
            ).fetchone()
            has_stats = stats_row is not None

            # 2. Look for opponent_links rows scoped to our_team_id.
            #
            #    resolved_link_id: a row where resolved_team_id = opponent_team_id.
            #      Used for both state detection (linked_unscouted) and the admin URL.
            #
            #    unresolved_link_id: a row where resolved_team_id IS NULL, matched by
            #      team name.  OpponentSeeder creates rows before OpponentResolver runs,
            #      so this provides the link_id for the admin shortcut even when the
            #      opponent hasn't been resolved yet.  Does NOT count as "linked" for
            #      state purposes -- only a resolved row or non-null public_id does.
            resolved_link_id: int | None = None
            unresolved_link_id: int | None = None
            if our_team_id is not None:
                link_row = conn.execute(
                    """
                    SELECT id FROM opponent_links
                    WHERE resolved_team_id = ? AND our_team_id = ?
                    LIMIT 1
                    """,
                    (opponent_team_id, our_team_id),
                ).fetchone()
                if link_row:
                    resolved_link_id = link_row[0]
                else:
                    # Fallback: unresolved row whose opponent_name matches the team name.
                    unresolved_row = conn.execute(
                        """
                        SELECT ol.id FROM opponent_links ol
                        JOIN teams t ON t.name = ol.opponent_name
                        WHERE ol.our_team_id = ? AND t.id = ?
                          AND ol.resolved_team_id IS NULL
                        LIMIT 1
                        """,
                        (our_team_id, opponent_team_id),
                    ).fetchone()
                    if unresolved_row:
                        unresolved_link_id = unresolved_row[0]

            # link_id for the admin URL: prefer resolved, fall back to unresolved.
            link_id: int | None = resolved_link_id if resolved_link_id is not None else unresolved_link_id

            if has_stats:
                return {"status": "full_stats", "link_id": link_id}

            # 3. State is linked_unscouted if there is a RESOLVED link or a non-null
            #    public_id.  An unresolved link does not count as linked.
            is_linked = resolved_link_id is not None
            if not is_linked:
                team_row = conn.execute(
                    "SELECT public_id FROM teams WHERE id = ?",
                    (opponent_team_id,),
                ).fetchone()
                if team_row and team_row[0]:
                    is_linked = True

            status = "linked_unscouted" if is_linked else "unlinked"
            return {"status": status, "link_id": link_id}

    except sqlite3.Error:
        logger.exception(
            "Failed to get opponent scouting status for team %d", opponent_team_id
        )
        return {"status": "unlinked", "link_id": None}


def get_team_spray_bip_count(team_id: int, season_id: str) -> int:
    """Return the count of offensive BIP events for a team in a season.

    Args:
        team_id:   The INTEGER team id.
        season_id: Season slug to filter events.

    Returns:
        Integer count of ``chart_type = 'offensive'`` rows, or 0 on error.
    """
    try:
        with closing(get_connection()) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM spray_charts "
                "WHERE team_id = ? AND chart_type = 'offensive' AND season_id = ?",
                (team_id, season_id),
            ).fetchone()
        return row[0] if row else 0
    except sqlite3.Error:
        logger.exception(
            "Failed to fetch spray BIP count for team_id=%s season_id=%s",
            team_id,
            season_id,
        )
        return 0


def get_player_spray_bip_counts(
    player_ids: list[str],
    season_id: str,
) -> dict[str, int]:
    """Return a mapping of player_id → offensive BIP count for a season.

    Runs a single query covering all requested player IDs.  Players with no
    spray data are absent from the returned dict (callers should use
    ``dict.get(player_id, 0)``).

    Args:
        player_ids: List of GC player UUIDs to look up.
        season_id:  Season slug to filter events.

    Returns:
        Dict mapping ``player_id`` → count.  Returns ``{}`` on error or when
        ``player_ids`` is empty.
    """
    if not player_ids:
        return {}
    placeholders = ",".join("?" for _ in player_ids)
    query = (
        f"SELECT player_id, COUNT(*) AS bip_count FROM spray_charts "
        f"WHERE player_id IN ({placeholders}) "
        f"AND chart_type = 'offensive' AND season_id = ? "
        f"GROUP BY player_id"
    )
    try:
        with closing(get_connection()) as conn:
            rows = conn.execute(query, [*player_ids, season_id]).fetchall()
        return {row[0]: row[1] for row in rows}
    except sqlite3.Error:
        logger.exception(
            "Failed to fetch spray BIP counts for %d players season_id=%s",
            len(player_ids),
            season_id,
        )
        return {}


def get_player_spray_bip_count(player_id: str, season_id: str) -> int:
    """Return the count of offensive BIP events for a player in a season.

    Args:
        player_id: The player's UUID.
        season_id: Season slug to filter events.

    Returns:
        Integer count of ``chart_type = 'offensive'`` rows, or 0 on error.
    """
    try:
        with closing(get_connection()) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM spray_charts "
                "WHERE player_id = ? AND chart_type = 'offensive' AND season_id = ?",
                (player_id, season_id),
            ).fetchone()
        return row[0] if row else 0
    except sqlite3.Error:
        logger.exception(
            "Failed to fetch spray BIP count for player_id=%s season_id=%s",
            player_id,
            season_id,
        )
        return 0


def get_player_spray_events(
    player_id: str,
    season_id: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Return offensive BIP events and display title for a player's spray chart.

    When ``season_id`` is omitted, uses the most recent season that has
    spray chart data for this player.

    Args:
        player_id: The player's UUID.
        season_id: Season slug to filter events.  When ``None``, uses the most
                   recent season with spray data for this player.

    Returns:
        Tuple of ``(events, title)`` where:
        - ``events``: list of dicts with ``x``, ``y``, ``play_result``
        - ``title``: ``"{first_name} {last_name}"`` or ``None`` if not found
        Returns ``([], None)`` on DB error or when no spray data exists.
    """
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row

            if season_id is None:
                season_row = conn.execute(
                    "SELECT season_id FROM spray_charts "
                    "WHERE player_id = ? AND chart_type = 'offensive' "
                    "ORDER BY season_id DESC LIMIT 1",
                    (player_id,),
                ).fetchone()
                if season_row is None:
                    return [], None
                season_id = season_row["season_id"]

            player_row = conn.execute(
                "SELECT first_name, last_name FROM players WHERE player_id = ?",
                (player_id,),
            ).fetchone()
            title = (
                f"{player_row['first_name']} {player_row['last_name']}"
                if player_row else None
            )

            rows = conn.execute(
                "SELECT x, y, play_result, play_type FROM spray_charts "
                "WHERE player_id = ? AND chart_type = 'offensive' AND season_id = ?",
                (player_id, season_id),
            ).fetchall()

        return [dict(row) for row in rows], title
    except sqlite3.Error:
        logger.exception("Failed to fetch player spray events for player_id=%s", player_id)
        return [], None


def get_team_spray_events(
    team_id: int,
    season_id: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Return offensive BIP events and display title for a team's spray chart.

    When ``season_id`` is omitted, uses the most recent season that has
    spray chart data for this team.

    Args:
        team_id: The INTEGER team id.
        season_id: Season slug to filter events.  When ``None``, uses the most
                   recent season with spray data for this team.

    Returns:
        Tuple of ``(events, title)`` where:
        - ``events``: list of dicts with ``x``, ``y``, ``play_result``
        - ``title``: team name or ``None`` if team not found
        Returns ``([], None)`` on DB error or when no spray data exists.
    """
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row

            if season_id is None:
                season_row = conn.execute(
                    "SELECT season_id FROM spray_charts "
                    "WHERE team_id = ? AND chart_type = 'offensive' "
                    "ORDER BY season_id DESC LIMIT 1",
                    (team_id,),
                ).fetchone()
                if season_row is None:
                    return [], None
                season_id = season_row["season_id"]

            team_row = conn.execute(
                "SELECT name FROM teams WHERE id = ?",
                (team_id,),
            ).fetchone()
            title = team_row["name"] if team_row else None

            rows = conn.execute(
                "SELECT x, y, play_result, play_type FROM spray_charts "
                "WHERE team_id = ? AND chart_type = 'offensive' AND season_id = ?",
                (team_id, season_id),
            ).fetchall()

        return [dict(row) for row in rows], title
    except sqlite3.Error:
        logger.exception("Failed to fetch team spray events for team_id=%s", team_id)
        return [], None


def check_connection() -> bool:
    """Verify that the database is accessible and the schema is initialized.

    Executes a trivial query against the ``_migrations`` table (created by
    ``apply_migrations.py``).  Returns True if the query succeeds, False if
    the database is not reachable or the migrations table does not exist.

    This function is designed to be called via ``run_in_threadpool`` from an
    async route handler.

    Returns:
        True if the database is accessible and initialized; False otherwise.
    """
    try:
        with closing(get_connection()) as conn:
            conn.execute("SELECT 1 FROM _migrations LIMIT 1;")
        return True
    except sqlite3.Error:
        logger.exception("Database health check failed")
        return False
