"""Database backup logic.

Provides ``backup_database()`` for creating timestamped copies of the SQLite
database file.  Used by the ``bb db backup`` command.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.db.paths import resolve_db_path

logger = logging.getLogger(__name__)

# Repo root: src/db/backup.py is 3 levels deep, so .parents[2] is the repo root.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BACKUPS_DIR = _PROJECT_ROOT / "data" / "backups"


def backup_database(db_path: Path | None = None) -> Path:
    """Copy the database file to a timestamped backup using the SQLite backup API.

    Uses ``sqlite3.Connection.backup()`` instead of a raw file copy so that
    WAL-mode sidecar files (.wal, .shm) are included in the checkpoint and the
    backup is always a consistent, self-contained database file.

    Args:
        db_path: Path to the database file.  Uses ``resolve_db_path()`` if None.

    Returns:
        Path to the newly created backup file.

    Raises:
        FileNotFoundError: If the database file does not exist.
    """
    if db_path is None:
        db_path = resolve_db_path()

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    _BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    backup_name = f"app-{timestamp}.db"
    backup_path = _BACKUPS_DIR / backup_name

    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(backup_path)
    try:
        src.backup(dst)
        logger.info("Backup saved to %s", backup_path)
    finally:
        dst.close()
        src.close()

    return backup_path
