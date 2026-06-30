"""Database reset logic.

Provides ``reset_database()`` and helpers for dropping and recreating the
SQLite database from migrations.  Used by the ``bb db reset`` command.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

from migrations.apply_migrations import run_migrations
from src.db.paths import resolve_db_path

logger = logging.getLogger(__name__)


def get_db_path(override: str | Path | None = None) -> Path:
    """Return the resolved path to the SQLite database file.

    Thin wrapper around the canonical :func:`src.db.paths.resolve_db_path`
    (override -> DATABASE_PATH -> default).  Retained for callers that import
    ``get_db_path`` from this module.

    Args:
        override: Optional path override from the caller (string or Path).

    Returns:
        Resolved absolute Path to the database file.
    """
    return resolve_db_path(override)


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


def reset_database(
    db_path: Path | None = None,
    force: bool = False,
    _skip_guard: bool = False,
) -> tuple[int, int]:
    """Orchestrate a full database reset: delete, migrate.

    Produces a database containing only the migrated schema (and any rows the
    migrations themselves insert, e.g. the ``programs`` bootstrap row).  No
    demo/seed data is loaded.

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
        Tuple of (tables_created, 0).  The second element is always 0: no seed
        rows are loaded.  It is retained for backward compatibility with the
        2-tuple return shape.

    Raises:
        SystemExit: If APP_ENV=production, force is False, and _skip_guard is False.
    """
    if db_path is None:
        db_path = get_db_path()

    if not _skip_guard:
        check_production_guard(force=force)

    logger.info("Resetting database at: %s", db_path)

    delete_database(db_path)
    table_count = _run_migrations_and_count(db_path)

    return table_count, 0
