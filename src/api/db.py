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
    season: str = "2026",
) -> list[dict[str, Any]]:
    """Return season batting stats for all players on a team.

    Joins ``player_season_batting`` with ``players`` to return each player's
    display name alongside their aggregate batting stats.  Results are ordered
    by player last name.

    Args:
        team_id: The team identifier to query.  Defaults to LSB Varsity 2026.
        season:  The season year string.  Defaults to ``"2026"``.

    Returns:
        List of dicts with keys: name, ab, h, bb, so.
        Returns an empty list if the database is not accessible or the team
        has no season batting rows.
    """
    query = """
        SELECT
            p.first_name || ' ' || p.last_name AS name,
            psb.ab,
            psb.h,
            psb.bb,
            psb.so
        FROM player_season_batting psb
        JOIN players p ON p.player_id = psb.player_id
        WHERE psb.team_id = ? AND psb.season = ?
        ORDER BY p.last_name
    """
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, (team_id, season))
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error:
        logger.exception("Failed to fetch team batting stats")
        return []


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
