#!/usr/bin/env python3
"""Create a timestamped backup of the SQLite database.

Copies the database file to ``data/backups/app-<timestamp>.db``. Creates the
backups directory if it does not exist.

Usage::

    python scripts/backup_db.py [--db-path PATH]

Options:
    --db-path PATH   Override DATABASE_PATH env var (absolute or relative path).

Environment variables (loaded from .env if present):
    DATABASE_PATH   Path to the SQLite file.  Defaults to ``./data/app.db``.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
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
    format="%(asctime)s %(levelname)s [backup_db] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BACKUPS_DIR = _PROJECT_ROOT / "data" / "backups"

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


def _get_db_path(override: str | None = None) -> Path:
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
    default = _PROJECT_ROOT / "data" / "app.db"
    raw = os.environ.get("DATABASE_PATH", str(default))
    return Path(raw).resolve()


def backup_database(db_path: Path | None = None) -> Path:
    """Copy the database file to a timestamped backup.

    Args:
        db_path: Path to the database file.  Uses _get_db_path() if None.

    Returns:
        Path to the newly created backup file.

    Raises:
        FileNotFoundError: If the database file does not exist.
    """
    if db_path is None:
        db_path = _get_db_path()

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    _BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    backup_name = f"app-{timestamp}.db"
    backup_path = _BACKUPS_DIR / backup_name

    shutil.copy2(db_path, backup_path)
    logger.info("Backup saved to %s", backup_path)

    return backup_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed namespace with db_path attribute.
    """
    parser = argparse.ArgumentParser(
        description="Create a timestamped backup of the SQLite database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/backup_db.py\n"
            "  python scripts/backup_db.py --db-path /tmp/custom.db\n"
        ),
    )
    parser.add_argument(
        "--db-path",
        metavar="PATH",
        default=None,
        help="Override DATABASE_PATH env var. Accepts absolute or relative paths.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    resolved_path = _get_db_path(override=args.db_path)

    try:
        result = backup_database(db_path=resolved_path)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    print(f"Backup saved to {result}")
