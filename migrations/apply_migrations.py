#!/usr/bin/env python3
"""Apply numbered SQL migration files to the SQLite database.

Migration files live in the same directory as this script and follow the
naming convention ``NNN_description.sql`` (e.g., ``001_initial_schema.sql``).
They are applied in ascending numeric order.

Applied migrations are tracked in a ``_migrations`` table inside the database
itself.  Running this script multiple times is idempotent: each migration is
applied exactly once.

Usage::

    python migrations/apply_migrations.py

Environment variables (loaded from .env if present):

    DATABASE_PATH   Path to the SQLite file.  Defaults to ``./data/app.db``.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIGRATIONS_DIR = Path(__file__).resolve().parent

# Repo root: migrations/apply_migrations.py is 1 level deep, so .parents[1] is the repo root.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Load DATABASE_PATH from .env only when run as a script (not on import).
# Guarding here prevents load_dotenv() from polluting os.environ in the test
# session when test modules import run_migrations at the module level.
def _load_dotenv_if_cli() -> None:
    """Load .env only when this module is invoked directly or via CLI."""
    try:
        from dotenv import load_dotenv

        _env_file = _MIGRATIONS_DIR.parent / ".env"
        if _env_file.exists():
            load_dotenv(_env_file)
    except ImportError:
        pass  # dotenv is optional; env vars may be injected directly (Docker)

_DEFAULT_DB_PATH = _PROJECT_ROOT / "data" / "app.db"

# ---------------------------------------------------------------------------
# Migrations tracking table DDL
# ---------------------------------------------------------------------------

_CREATE_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS _migrations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT    NOT NULL UNIQUE,
    applied_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def get_db_path() -> Path:
    """Return the resolved path to the SQLite database file.

    Reads DATABASE_PATH from the environment, falling back to the default.
    Relative paths are resolved against the repo root, not the current working
    directory.
    """
    env_db = os.environ.get("DATABASE_PATH")
    if env_db is not None:
        env_path = Path(env_db)
        return env_path if env_path.is_absolute() else _PROJECT_ROOT / env_path
    return _DEFAULT_DB_PATH


def collect_migration_files() -> list[Path]:
    """Return all ``NNN_*.sql`` files in the migrations directory, sorted.

    Returns:
        Sorted list of Path objects for each migration file.
    """
    files = sorted(_MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    return files


def get_applied_migrations(conn: sqlite3.Connection) -> set[str]:
    """Return the set of filenames already recorded in ``_migrations``.

    Args:
        conn: Open SQLite connection with _migrations table present.

    Returns:
        Set of filename strings (e.g., ``{'001_initial_schema.sql'}``).
    """
    cursor = conn.execute("SELECT filename FROM _migrations;")
    return {row[0] for row in cursor.fetchall()}


def apply_migration(conn: sqlite3.Connection, migration_file: Path) -> None:
    """Apply a single migration file and record it in ``_migrations``.

    Executes the file's SQL in a transaction.  On success, inserts a row into
    ``_migrations``.  On failure, rolls back and re-raises.

    Args:
        conn: Open SQLite connection.
        migration_file: Path to the ``.sql`` file to apply.

    Raises:
        sqlite3.Error: If the SQL execution fails.
    """
    sql = migration_file.read_text(encoding="utf-8")
    logger.info("Applying migration: %s", migration_file.name)
    try:
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO _migrations (filename) VALUES (?);",
            (migration_file.name,),
        )
        conn.commit()
        logger.info("Migration applied: %s", migration_file.name)
    except sqlite3.Error:
        conn.rollback()
        logger.error("Migration failed: %s", migration_file.name)
        raise


def run_migrations(db_path: Path | None = None) -> None:
    """Apply all pending migrations to the database at ``db_path``.

    Creates the database file and its parent directory if they do not exist.
    Enables WAL mode before running any migrations.  Idempotent.

    Args:
        db_path: Path to the SQLite file.  Defaults to ``get_db_path()``.
    """
    if db_path is None:
        db_path = get_db_path()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Database path: %s", db_path)

    conn = sqlite3.connect(db_path)
    try:
        # Enable WAL mode for better read concurrency.
        # This is a one-time operation per database file; safe to run every time.
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.commit()

        # Ensure the migrations tracking table exists.
        conn.executescript(_CREATE_MIGRATIONS_TABLE)
        conn.commit()

        applied = get_applied_migrations(conn)
        migration_files = collect_migration_files()

        pending = [f for f in migration_files if f.name not in applied]

        if not pending:
            logger.info("No pending migrations. Database is up to date.")
            return

        logger.info("%d pending migration(s) to apply.", len(pending))
        for migration_file in pending:
            apply_migration(conn, migration_file)

        logger.info("All migrations applied successfully.")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _load_dotenv_if_cli()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [migrations] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    try:
        run_migrations()
    except Exception as exc:
        logger.error("Migration run failed: %s", exc)
        sys.exit(1)
