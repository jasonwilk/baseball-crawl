"""Database reset logic.

Provides ``reset_database()`` and helpers for dropping and recreating the
SQLite database from migrations and seed data.  Used by the ``bb db reset``
command.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

from migrations.apply_migrations import run_migrations

logger = logging.getLogger(__name__)

# Repo root: src/db/reset.py is 3 levels deep, so .parents[2] is the repo root.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DB_PATH = _PROJECT_ROOT / "data" / "app.db"
_SEED_FILE = _PROJECT_ROOT / "data" / "seeds" / "seed_dev.sql"


def get_db_path(override: str | Path | None = None) -> Path:
    """Return the resolved path to the SQLite database file.

    Checks the caller-supplied override first, then DATABASE_PATH from the
    environment, then falls back to the default path.

    Args:
        override: Optional path override from the caller (string or Path).

    Returns:
        Resolved absolute Path to the database file.
    """
    if override is not None:
        return Path(override).resolve()
    env_db = os.environ.get("DATABASE_PATH")
    if env_db is not None:
        env_path = Path(env_db)
        return env_path if env_path.is_absolute() else _PROJECT_ROOT / env_path
    return _DEFAULT_DB_PATH


def check_production_guard(force: bool) -> None:
    """Raise SystemExit if running in production without --force.

    Protects against accidental resets in production environments.

    Args:
        force: True if the --force flag was passed on the CLI.

    Raises:
        SystemExit: If APP_ENV is 'production' and force is False.
    """
    import sys

    app_env = os.environ.get("APP_ENV", "development").lower()
    if app_env == "production" and not force:
        logger.error(
            "APP_ENV=production detected. Pass --force to confirm reset. "
            "This is a destructive operation."
        )
        sys.exit(1)
    if app_env == "production" and force:
        logger.warning("Resetting PRODUCTION database (--force supplied). Proceeding.")


def delete_database(db_path: Path) -> None:
    """Delete the database file and any WAL/SHM sidecar files.

    Args:
        db_path: Path to the SQLite database file to remove.
    """
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(db_path) + suffix)
        if candidate.exists():
            candidate.unlink()
            logger.info("Deleted: %s", candidate)


def _run_migrations_and_count(db_path: Path) -> int:
    """Apply all pending migrations and return the number of tables created.

    Args:
        db_path: Path to the SQLite file to create and migrate.

    Returns:
        Number of tables created (excluding the _migrations tracking table).
    """
    run_migrations(db_path=db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type='table' AND name != '_migrations';"
        )
        table_count: int = cursor.fetchone()[0]
    finally:
        conn.close()

    return table_count


def load_seed(db_path: Path, seed_file: Path) -> int:
    """Execute the seed SQL file and return the total rows inserted.

    Args:
        db_path: Path to the already-migrated SQLite database.
        seed_file: Path to the SQL seed file.

    Returns:
        Total rows inserted across all seeded tables.

    Raises:
        FileNotFoundError: If the seed file does not exist.
        sqlite3.Error: If any SQL statement fails.
    """
    if not seed_file.exists():
        raise FileNotFoundError(f"Seed file not found: {seed_file}")

    sql = seed_file.read_text(encoding="utf-8")
    logger.info("Loading seed data from %s", seed_file)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.executescript(sql)
        conn.commit()

        # Count total rows across all user tables (excluding _migrations).
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name != '_migrations';"
        )
        table_names = [row[0] for row in cursor.fetchall()]

        total_rows = 0
        for table in table_names:
            count: int = conn.execute(
                f"SELECT COUNT(*) FROM {table};"  # noqa: S608  -- table names from schema, not user input
            ).fetchone()[0]
            total_rows += count
            logger.info("  %s: %d rows", table, count)
    except sqlite3.Error:
        conn.rollback()
        logger.exception("Failed to load seed data.")
        raise
    finally:
        conn.close()

    return total_rows


def reset_database(
    db_path: Path | None = None,
    force: bool = False,
    _skip_guard: bool = False,
) -> tuple[int, int]:
    """Orchestrate a full database reset: delete, migrate, seed.

    This is the public entry point for programmatic use (e.g., from the CLI).
    The production guard runs internally unless ``_skip_guard=True`` is passed.
    Direct callers (e.g., scripts) should leave ``_skip_guard`` at its default
    so the guard still protects them.  The CLI passes ``_skip_guard=True`` after
    calling ``check_production_guard()`` directly for correct sequencing (guard
    before confirmation prompt).

    Args:
        db_path: Path to the database file.  Uses ``get_db_path()`` if None.
        force: If True, bypasses the production guard (only used when
            ``_skip_guard`` is False).
        _skip_guard: Internal flag.  When True, the internal
            ``check_production_guard()`` call is skipped.  Default False.

    Returns:
        Tuple of (tables_created, rows_inserted).

    Raises:
        SystemExit: If APP_ENV=production, force is False, and _skip_guard is False.
        FileNotFoundError: If the seed file is missing.
    """
    if db_path is None:
        db_path = get_db_path()

    if not _skip_guard:
        check_production_guard(force=force)

    logger.info("Resetting database at: %s", db_path)

    delete_database(db_path)
    table_count = _run_migrations_and_count(db_path)
    row_count = load_seed(db_path, seed_file=_SEED_FILE)

    return table_count, row_count
