"""Canonical SQLite database-path resolution.

Single source of truth for the ``override -> DATABASE_PATH -> default`` cascade
shared by the CLI commands (``bb data``, ``bb report``), the backup/reset
utilities, and the FastAPI application.  Kept dependency-light (only ``os`` and
``pathlib``) so every layer can import it without pulling in heavier modules.
"""

from __future__ import annotations

import os
from pathlib import Path

# Repo root: src/db/paths.py is 3 levels deep, so .parents[2] is the repo root.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DB_PATH = _PROJECT_ROOT / "data" / "app.db"


def resolve_db_path(override: str | Path | None = None) -> Path:
    """Return the resolved path to the SQLite database file.

    Precedence (highest to lowest):

    1. An explicit ``override`` supplied by the caller (resolved to absolute).
    2. The ``DATABASE_PATH`` environment variable.  A relative value is
       resolved against the repo root; an absolute value is used as-is.
    3. The default path, ``<repo_root>/data/app.db``.

    Args:
        override: Optional path override from the caller (string or Path).

    Returns:
        Path to the database file (absolute).
    """
    if override is not None:
        return Path(override).resolve()
    env_db = os.environ.get("DATABASE_PATH")
    if env_db is not None:
        env_path = Path(env_db)
        return env_path if env_path.is_absolute() else _PROJECT_ROOT / env_path
    return _DEFAULT_DB_PATH
