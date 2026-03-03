#!/usr/bin/env python3
"""Drop and recreate the development database, then load seed data.

Deletes the database file at DATABASE_PATH, runs apply_migrations.py to create
a fresh schema, then loads data/seeds/seed_dev.sql.

Usage::

    python scripts/reset_dev_db.py [--db-path PATH]

Options:
    --db-path PATH   Override DATABASE_PATH env var (absolute or relative path).
    --force          Required when APP_ENV=production to prevent accidental resets.

Environment variables (loaded from .env if present):
    DATABASE_PATH   Path to the SQLite file.  Defaults to ``./data/app.db``.
    APP_ENV         Runtime environment.  If ``production``, --force is required.
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup -- allow running from project root without install
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [reset_dev_db] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_DB_PATH = _PROJECT_ROOT / "data" / "app.db"
_SEED_FILE = _PROJECT_ROOT / "data" / "seeds" / "seed_dev.sql"

# Load .env if python-dotenv is available.
try:
    from dotenv import load_dotenv

    _env_file = _PROJECT_ROOT / ".env"
    if _env_file.exists():
        load_dotenv(_env_file)
except ImportError:
    pass  # dotenv is optional; env vars may be injected directly (Docker)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def get_db_path(override: str | None = None) -> Path:
    """Return the resolved path to the SQLite database file.

    Checks the CLI override first, then DATABASE_PATH from the environment,
    then falls back to the default path.

    Args:
        override: Optional path string from the --db-path CLI argument.

    Returns:
        Resolved absolute Path to the database file.
    """
    if override is not None:
        return Path(override).resolve()
    raw = os.environ.get("DATABASE_PATH", str(_DEFAULT_DB_PATH))
    return Path(raw).resolve()


def check_production_guard(force: bool) -> None:
    """Raise SystemExit if running in production without --force.

    Protects against accidental resets in production environments.

    Args:
        force: True if the --force flag was passed on the CLI.

    Raises:
        SystemExit: If APP_ENV is 'production' and force is False.
    """
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
        # If -wal/-shm don't exist, that's fine -- skip silently.


def run_migrations(db_path: Path) -> int:
    """Apply all pending migrations to a fresh database.

    Delegates to migrations.apply_migrations.run_migrations so we do not
    duplicate migration logic.

    Args:
        db_path: Path to the SQLite file to create and migrate.

    Returns:
        Number of tables created (excluding the _migrations tracking table).

    Raises:
        Exception: Re-raises any error from the migration runner.
    """
    from migrations.apply_migrations import run_migrations as _run_migrations

    _run_migrations(db_path=db_path)

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


def reset_database(db_path: Path | None = None, force: bool = False) -> tuple[int, int]:
    """Orchestrate a full database reset: delete, migrate, seed.

    This is the public entry point for programmatic use (e.g., from tests).

    Args:
        db_path: Path to the database file.  Uses get_db_path() if None.
        force: If True, bypasses the production guard.

    Returns:
        Tuple of (tables_created, rows_inserted).

    Raises:
        SystemExit: If APP_ENV=production and force is False.
        FileNotFoundError: If the seed file is missing.
    """
    if db_path is None:
        db_path = get_db_path()

    check_production_guard(force=force)

    logger.info("Resetting database at: %s", db_path)

    delete_database(db_path)
    table_count = run_migrations(db_path)
    row_count = load_seed(db_path, seed_file=_SEED_FILE)

    return table_count, row_count


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed namespace with db_path and force attributes.
    """
    parser = argparse.ArgumentParser(
        description="Drop and recreate the development database with seed data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/reset_dev_db.py\n"
            "  python scripts/reset_dev_db.py --db-path /tmp/test.db\n"
            "  APP_ENV=production python scripts/reset_dev_db.py --force\n"
        ),
    )
    parser.add_argument(
        "--db-path",
        metavar="PATH",
        default=None,
        help="Override DATABASE_PATH env var. Accepts absolute or relative paths.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Required when APP_ENV=production to confirm intentional reset.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    db_path = get_db_path(override=args.db_path)

    try:
        tables, rows = reset_database(db_path=db_path, force=args.force)
    except FileNotFoundError as exc:
        logger.error("Seed file error: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.error("Reset failed: %s", exc)
        sys.exit(1)

    print(f"Database reset. {tables} tables created. {rows} rows inserted.")
