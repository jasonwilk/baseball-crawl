"""Database connection helpers for the FastAPI application.

Provides a simple synchronous SQLite connection factory and a health-check
function.  All database calls are run via ``run_in_threadpool`` in async
route handlers to avoid blocking the event loop (see routes/health.py).

Configuration:
    DATABASE_PATH   Environment variable specifying the path to the SQLite
                    file.  Defaults to ``./data/app.db``.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = "./data/app.db"


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
    team_id: str = "lsb-varsity-2026",
    season_id: str = "2026-spring-hs",
) -> list[dict[str, Any]]:
    """Return season batting stats for all players on a team.

    Joins ``player_season_batting`` with ``players`` and ``team_rosters`` to
    return each player's display name, jersey number, and full batting stats.
    Results are sorted by AVG descending; players with no AB appear at bottom.

    Args:
        team_id:   The team identifier to query.  Defaults to LSB Varsity 2026.
        season_id: The season slug (e.g. ``"2026-spring-hs"``).  Defaults to
                   ``"2026-spring-hs"``.

    Returns:
        List of dicts with keys: player_id, name, jersey_number, games, ab, h,
        doubles, triples, hr, rbi, bb, so, sb.
        Returns an empty list if the database is not accessible or the team
        has no season batting rows.
    """
    query = """
        SELECT
            p.player_id,
            p.first_name || ' ' || p.last_name AS name,
            tr.jersey_number,
            COALESCE(psb.games, 0)   AS games,
            COALESCE(psb.ab, 0)      AS ab,
            COALESCE(psb.h, 0)       AS h,
            COALESCE(psb.doubles, 0) AS doubles,
            COALESCE(psb.triples, 0) AS triples,
            COALESCE(psb.hr, 0)      AS hr,
            COALESCE(psb.rbi, 0)     AS rbi,
            COALESCE(psb.bb, 0)      AS bb,
            COALESCE(psb.so, 0)      AS so,
            COALESCE(psb.sb, 0)      AS sb
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
            cursor = conn.execute(query, (team_id, season_id))
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error:
        logger.exception("Failed to fetch team batting stats")
        return []


def get_teams_by_ids(team_ids: list[str]) -> list[dict[str, Any]]:
    """Return team display names for the given list of team_ids.

    Args:
        team_ids: List of team_id strings to look up.

    Returns:
        List of dicts with keys: team_id, name.
        Returns an empty list if team_ids is empty or on DB error.
    """
    if not team_ids:
        return []
    placeholders = ",".join("?" for _ in team_ids)
    query = f"SELECT team_id, name FROM teams WHERE team_id IN ({placeholders})"
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
    team_id: str = "lsb-varsity-2026",
    season_id: str = "2026-spring-hs",
) -> list[dict[str, Any]]:
    """Return season pitching stats for all pitchers on a team.

    Joins ``player_season_pitching`` with ``players`` and ``team_rosters`` to
    return each pitcher's display name, jersey number, and aggregate pitching
    stats.  Results are sorted by ERA ascending (pitchers with 0 ip_outs appear
    at the bottom).

    Args:
        team_id:   The team identifier to query.  Defaults to LSB Varsity 2026.
        season_id: The season slug (e.g. ``"2026-spring-hs"``).  Defaults to
                   ``"2026-spring-hs"``.

    Returns:
        List of dicts with keys: player_id, name, jersey_number, games,
        ip_outs, h, er, bb, so, hr.
        Returns an empty list if the database is not accessible or the team
        has no season pitching rows.
    """
    query = """
        SELECT
            p.player_id,
            p.first_name || ' ' || p.last_name AS name,
            tr.jersey_number,
            COALESCE(psp.games, 0)   AS games,
            COALESCE(psp.ip_outs, 0) AS ip_outs,
            COALESCE(psp.h, 0)       AS h,
            COALESCE(psp.er, 0)      AS er,
            COALESCE(psp.bb, 0)      AS bb,
            COALESCE(psp.so, 0)      AS so,
            COALESCE(psp.hr, 0)      AS hr
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
            cursor = conn.execute(query, (team_id, season_id))
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error:
        logger.exception("Failed to fetch team pitching stats")
        return []


def get_team_games(
    team_id: str,
    season_id: str,
) -> list[dict[str, Any]]:
    """Return the game list for a team in a season, sorted by date descending.

    Joins ``games`` with ``teams`` (twice, via a CASE expression) to resolve the
    opponent name and determine home/away context.

    Args:
        team_id:   The team_id to query (home or away).
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
        LEFT JOIN teams opp_away ON opp_away.team_id = g.away_team_id
        LEFT JOIN teams opp_home ON opp_home.team_id = g.home_team_id
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


def get_game_box_score(game_id: str) -> dict[str, Any]:
    """Return the full box score for a game: batting and pitching lines for both teams.

    Queries ``player_game_batting`` and ``player_game_pitching`` joined with
    ``players`` and ``teams``, returning per-player lines grouped by team.

    Also returns top-level game metadata (game_date, home_team_id, away_team_id,
    home_score, away_score).

    Args:
        game_id: The game identifier.

    Returns:
        Dict with keys:
            - ``game``: dict with game_id, game_date, home_team_id, away_team_id,
              home_score, away_score, home_team_name, away_team_name
            - ``teams``: list of two dicts, each with:
                - team_id, team_name
                - batting_lines: list of player batting dicts
                - pitching_lines: list of player pitching dicts
        Returns ``{}`` on DB error or missing game.
    """
    game_query = """
        SELECT
            g.game_id,
            g.game_date,
            g.home_team_id,
            g.away_team_id,
            g.home_score,
            g.away_score,
            th.name AS home_team_name,
            ta.name AS away_team_name
        FROM games g
        LEFT JOIN teams th ON th.team_id = g.home_team_id
        LEFT JOIN teams ta ON ta.team_id = g.away_team_id
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
            COALESCE(pgb.sb, 0)      AS sb
        FROM player_game_batting pgb
        JOIN players p ON p.player_id = pgb.player_id
        WHERE pgb.game_id = ?
        ORDER BY pgb.team_id, p.last_name
    """
    pitching_query = """
        SELECT
            pgp.player_id,
            p.first_name || ' ' || p.last_name AS name,
            pgp.team_id,
            COALESCE(pgp.ip_outs, 0) AS ip_outs,
            COALESCE(pgp.h, 0)       AS h,
            COALESCE(pgp.er, 0)      AS er,
            COALESCE(pgp.bb, 0)      AS bb,
            COALESCE(pgp.so, 0)      AS so,
            COALESCE(pgp.hr, 0)      AS hr
        FROM player_game_pitching pgp
        JOIN players p ON p.player_id = pgp.player_id
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
            batting_rows = [dict(r) for r in conn.execute(batting_query, (game_id,)).fetchall()]
            pitching_rows = [dict(r) for r in conn.execute(pitching_query, (game_id,)).fetchall()]
    except sqlite3.Error:
        logger.exception("Failed to fetch game box score")
        return {}

    # Group batting and pitching lines by team_id
    batting_by_team: dict[str, list[dict[str, Any]]] = {}
    for row in batting_rows:
        batting_by_team.setdefault(row["team_id"], []).append(row)

    pitching_by_team: dict[str, list[dict[str, Any]]] = {}
    for row in pitching_rows:
        pitching_by_team.setdefault(row["team_id"], []).append(row)

    home_id = game["home_team_id"]
    away_id = game["away_team_id"]
    team_ids = [home_id, away_id]

    teams_data = []
    for tid in team_ids:
        team_name = game["home_team_name"] if tid == home_id else game["away_team_name"]
        teams_data.append(
            {
                "team_id": tid,
                "team_name": team_name or tid,
                "batting_lines": batting_by_team.get(tid, []),
                "pitching_lines": pitching_by_team.get(tid, []),
            }
        )

    return {"game": game, "teams": teams_data}


def get_team_opponents(
    team_id: str,
    season_id: str,
) -> list[dict[str, Any]]:
    """Return all opponents the given team has faced or will face in a season.

    Groups games by opponent and computes: game count, W-L record against the
    opponent, and either the next scheduled game date (if one exists in the
    future) or the most recent completed game date.

    Args:
        team_id:   The team_id to query (home or away side).
        season_id: The season slug (e.g. ``"2026-spring-hs"``).

    Returns:
        List of dicts with keys: opponent_team_id, opponent_name, games_played,
        wins, losses, next_game_date (ISO date str or None), last_game_date
        (ISO date str or None).
        Returns an empty list on DB error.
    """
    query = """
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
        LEFT JOIN teams opp_away ON opp_away.team_id = g.away_team_id
        LEFT JOIN teams opp_home ON opp_home.team_id = g.home_team_id
        WHERE g.season_id = :season_id
          AND (g.home_team_id = :team_id OR g.away_team_id = :team_id)
        GROUP BY opponent_team_id, opponent_name
        ORDER BY opponent_name ASC
    """
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, {"team_id": team_id, "season_id": season_id})
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error:
        logger.exception("Failed to fetch team opponents")
        return []


def get_opponent_scouting_report(
    opponent_team_id: str,
    season_id: str,
) -> dict[str, Any]:
    """Return batting and pitching stats for an opponent team in a season.

    Queries ``player_season_batting`` and ``player_season_pitching`` for the
    given team_id and season_id.  Results are sorted by AVG desc (batting) and
    ERA asc (pitching).

    Also returns the opponent team name from the ``teams`` table, and the
    opponent's season record (wins/losses from ``games``).

    Args:
        opponent_team_id: The opponent's team_id.
        season_id:        The season slug (e.g. ``"2026-spring-hs"``).

    Returns:
        Dict with keys:
            - ``team_name``: display name or opponent_team_id fallback
            - ``record``: dict with wins/losses (int), or None if no games
            - ``batting``: list of dicts (player_id, name, games, ab, h,
              doubles, triples, hr, rbi, bb, so, sb)
            - ``pitching``: list of dicts (player_id, name, games, ip_outs,
              h, er, bb, so, pitches)
        Returns an empty dict on DB error.
    """
    team_query = "SELECT name FROM teams WHERE team_id = ?"
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
            COALESCE(psb.games, 0)   AS games,
            COALESCE(psb.ab, 0)      AS ab,
            COALESCE(psb.h, 0)       AS h,
            COALESCE(psb.doubles, 0) AS doubles,
            COALESCE(psb.triples, 0) AS triples,
            COALESCE(psb.hr, 0)      AS hr,
            COALESCE(psb.rbi, 0)     AS rbi,
            COALESCE(psb.bb, 0)      AS bb,
            COALESCE(psb.so, 0)      AS so,
            COALESCE(psb.sb, 0)      AS sb
        FROM player_season_batting psb
        JOIN players p ON p.player_id = psb.player_id
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
            COALESCE(psp.games, 0)   AS games,
            COALESCE(psp.ip_outs, 0) AS ip_outs,
            COALESCE(psp.h, 0)       AS h,
            COALESCE(psp.er, 0)      AS er,
            COALESCE(psp.bb, 0)      AS bb,
            COALESCE(psp.so, 0)      AS so,
            COALESCE(psp.pitches, 0) AS pitches
        FROM player_season_pitching psp
        JOIN players p ON p.player_id = psp.player_id
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
            team_name = dict(team_row)["name"] if team_row else opponent_team_id
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
    team_id: str,
    opponent_team_id: str,
    season_id: str,
) -> dict[str, Any] | None:
    """Return the most recent completed game between two teams in a season.

    Looks for the latest game where one side is ``team_id`` and the other is
    ``opponent_team_id``, with ``status = 'completed'`` and scores recorded.

    Args:
        team_id:          The user's active team_id.
        opponent_team_id: The opponent's team_id.
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
            COALESCE(psb.games, 0)   AS games,
            COALESCE(psb.ab, 0)      AS ab,
            COALESCE(psb.h, 0)       AS h,
            COALESCE(psb.doubles, 0) AS doubles,
            COALESCE(psb.triples, 0) AS triples,
            COALESCE(psb.hr, 0)      AS hr,
            COALESCE(psb.rbi, 0)     AS rbi,
            COALESCE(psb.bb, 0)      AS bb,
            COALESCE(psb.so, 0)      AS so,
            COALESCE(psb.sb, 0)      AS sb
        FROM player_season_batting psb
        JOIN seasons s ON s.season_id = psb.season_id
        JOIN teams t ON t.team_id = psb.team_id
        WHERE psb.player_id = ?
        ORDER BY psb.season_id DESC
    """
    pitching_query = """
        SELECT
            psp.season_id,
            s.name        AS season_name,
            psp.team_id,
            t.name        AS team_name,
            COALESCE(psp.games, 0)   AS games,
            COALESCE(psp.ip_outs, 0) AS ip_outs,
            COALESCE(psp.h, 0)       AS h,
            COALESCE(psp.er, 0)      AS er,
            COALESCE(psp.bb, 0)      AS bb,
            COALESCE(psp.so, 0)      AS so,
            COALESCE(psp.hr, 0)      AS hr
        FROM player_season_pitching psp
        JOIN seasons s ON s.season_id = psp.season_id
        JOIN teams t ON t.team_id = psp.team_id
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
        LEFT JOIN teams opp_away ON opp_away.team_id = g.away_team_id
        LEFT JOIN teams opp_home ON opp_home.team_id = g.home_team_id
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
        LEFT JOIN teams opp_away ON opp_away.team_id = g.away_team_id
        LEFT JOIN teams opp_home ON opp_home.team_id = g.home_team_id
        WHERE pgp.player_id = ?
    """
    # Deduplicate by game_id (prefer batting row when both exist), then sort and limit.
    # We do this in Python after fetching both UNION arms to avoid complex SQLite window functions.
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

    # Deduplicate recent games: one row per game_id, batting preferred over pitching
    games_by_id: dict[str, dict[str, Any]] = {}
    for row in raw_games:
        gid = row["game_id"]
        if gid not in games_by_id or row["appearance_type"] == "batting":
            games_by_id[gid] = row
    recent_games = sorted(games_by_id.values(), key=lambda r: r["game_date"], reverse=True)[:5]

    player["jersey_number"] = jersey_number

    return {
        "player": player,
        "batting_seasons": batting_rows,
        "pitching_seasons": pitching_rows,
        "recent_games": recent_games,
    }


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
