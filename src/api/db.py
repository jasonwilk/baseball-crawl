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
from pathlib import Path

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
        with get_connection() as conn:
            conn.execute("SELECT 1 FROM _migrations LIMIT 1;")
        return True
    except Exception:
        logger.exception("Database health check failed")
        return False
