"""Shared pytest configuration and fixtures."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
_SCHEMA_PATH = _MIGRATIONS_DIR / "001_initial_schema.sql"


def load_real_schema(conn: sqlite3.Connection) -> None:
    """Load the production schema into ``conn`` with FK enforcement enabled.

    Applies every numbered migration (``[0-9][0-9][0-9]_*.sql``) in sorted
    order so the test schema mirrors what ``apply_migrations.py`` produces in
    production -- e.g. migration 002 (``report_generation_runs``) is included
    alongside the initial schema. The glob pattern matches the production
    runner's so test and prod migration discovery stay in parity (a future
    non-numbered ``.sql`` file would be skipped by both). Migrations are
    idempotent ``CREATE ... IF NOT EXISTS``, so concatenating them is safe.

    SQLite's ``executescript`` implicitly commits and resets connection state,
    so setting ``PRAGMA foreign_keys=ON`` on the connection beforehand has no
    effect on the script it runs. The pragma must be prepended to the SQL
    string so that FK enforcement is active for every CREATE/INSERT in the
    migrations. See ``.claude/rules/migrations.md`` ("executescript() and
    PRAGMAs") for the full rationale.
    """
    sql_files = sorted(_MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    combined = "\n".join(path.read_text() for path in sql_files)
    conn.executescript("PRAGMA foreign_keys=ON;\n" + combined)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests that run git commands in temp repos (deselect with '-m \"not integration\"')",
    )
