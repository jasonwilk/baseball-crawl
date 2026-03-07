"""Database backup logic.

Provides ``backup_database()`` for creating timestamped copies of the SQLite
database file.  Used by the ``bb db backup`` command.
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Repo root: src/db/backup.py is 3 levels deep, so .parents[2] is the repo root.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BACKUPS_DIR = _PROJECT_ROOT / "data" / "backups"


def _get_db_path(override: Path | None = None) -> Path:
    """Return the resolved path to the SQLite database file.

    Checks the caller-supplied override first, then DATABASE_PATH from the
    environment, then falls back to the default path.

    Args:
        override: Optional Path override from the caller.

    Returns:
        Resolved absolute Path to the database file.
    """
    if override is not None:
        return override.resolve() if not override.is_absolute() else override
    default = _PROJECT_ROOT / "data" / "app.db"
    env_db = os.environ.get("DATABASE_PATH")
    if env_db is not None:
        env_path = Path(env_db)
        return env_path if env_path.is_absolute() else _PROJECT_ROOT / env_path
    return default


def backup_database(db_path: Path | None = None) -> Path:
    """Copy the database file to a timestamped backup.

    Args:
        db_path: Path to the database file.  Uses ``_get_db_path()`` if None.

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
