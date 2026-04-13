"""Shared pytest configuration and fixtures."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "migrations" / "001_initial_schema.sql"


def load_real_schema(conn: sqlite3.Connection) -> None:
    """Load the production schema into ``conn`` with FK enforcement enabled.

    SQLite's ``executescript`` implicitly commits and resets connection state,
    so setting ``PRAGMA foreign_keys=ON`` on the connection beforehand has no
    effect on the script it runs. The pragma must be prepended to the SQL
    string so that FK enforcement is active for every CREATE/INSERT in the
    migration. See ``.claude/rules/migrations.md`` ("executescript() and
    PRAGMAs") for the full rationale.
    """
    sql = _SCHEMA_PATH.read_text()
    conn.executescript("PRAGMA foreign_keys=ON;\n" + sql)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests that run git commands in temp repos (deselect with '-m \"not integration\"')",
    )
