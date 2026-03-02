#!/usr/bin/env python3
"""Load development seed data into the local SQLite database.

Reads ``data/seeds/seed_dev.sql`` and executes it against the database
specified by the ``DATABASE_PATH`` environment variable (or the default
``./data/app.db``).

The SQL file uses ``INSERT OR IGNORE`` so this script is idempotent: running
it multiple times does not create duplicate rows.

Usage::

    python scripts/seed_dev.py

Prerequisites:
    - Run ``python migrations/apply_migrations.py`` first to initialize the schema.
    - The database file must exist at DATABASE_PATH.
"""

from __future__ import annotations

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
    format="%(asctime)s %(levelname)s [seed_dev] %(message)s",
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
    pass


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def get_db_path() -> Path:
    """Return the resolved path to the SQLite database file.

    Reads DATABASE_PATH from the environment, falling back to the default.

    Returns:
        Resolved Path to the database file.
    """
    raw = os.environ.get("DATABASE_PATH", str(_DEFAULT_DB_PATH))
    return Path(raw).resolve()


def load_seed(db_path: Path, seed_file: Path) -> None:
    """Execute the seed SQL file against the database.

    Args:
        db_path: Path to the SQLite database file.
        seed_file: Path to the SQL seed file to execute.

    Raises:
        FileNotFoundError: If the seed file does not exist.
        sqlite3.Error: If any SQL statement fails.
    """
    if not seed_file.exists():
        raise FileNotFoundError(f"Seed file not found: {seed_file}")

    if not db_path.exists():
        logger.error(
            "Database not found: %s -- run apply_migrations.py first.", db_path
        )
        sys.exit(1)

    sql = seed_file.read_text(encoding="utf-8")
    logger.info("Loading seed data from %s into %s", seed_file, db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.executescript(sql)
        conn.commit()
        logger.info("Seed data loaded successfully.")
    except sqlite3.Error:
        conn.rollback()
        logger.exception("Failed to load seed data.")
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    db_path = get_db_path()
    try:
        load_seed(db_path=db_path, seed_file=_SEED_FILE)
    except Exception as exc:
        logger.error("Seed failed: %s", exc)
        sys.exit(1)
