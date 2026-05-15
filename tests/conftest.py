"""Shared pytest configuration and fixtures."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
_SCHEMA_PATH = _MIGRATIONS_DIR / "001_initial_schema.sql"
# E-228-01: batter_positioning table for the Tier 1 positioning engine.
# Listed in apply order; load_real_schema applies each migration after 001.
_POST_BASE_MIGRATIONS: tuple[Path, ...] = (
    _MIGRATIONS_DIR / "002_batter_positioning.sql",
)


def load_real_schema(conn: sqlite3.Connection) -> None:
    """Load the production schema into ``conn`` with FK enforcement enabled.

    Applies ``001_initial_schema.sql`` (the consolidated base) followed by
    every post-base migration in order. Mirrors the production schema so
    test fixtures see the same tables the running app sees.

    SQLite's ``executescript`` implicitly commits and resets connection state,
    so setting ``PRAGMA foreign_keys=ON`` on the connection beforehand has no
    effect on the script it runs. The pragma must be prepended to the SQL
    string so that FK enforcement is active for every CREATE/INSERT in the
    migration. See ``.claude/rules/migrations.md`` ("executescript() and
    PRAGMAs") for the full rationale.
    """
    sql = _SCHEMA_PATH.read_text()
    conn.executescript("PRAGMA foreign_keys=ON;\n" + sql)
    for path in _POST_BASE_MIGRATIONS:
        conn.executescript("PRAGMA foreign_keys=ON;\n" + path.read_text())


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests that run git commands in temp repos (deselect with '-m \"not integration\"')",
    )
