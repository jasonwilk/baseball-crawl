"""Shared pytest configuration and fixtures."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

# Force plain (uncolored, unwrapped) CLI output for the whole test session.
#
# CI environments (e.g. GitHub Actions) force color on, so typer/click/rich
# inject ANSI escape codes -- and rich line-wraps to the terminal width -- into
# ``--help`` and command output, breaking the plain-substring assertions the CLI
# tests make against ``result.output``. ``NO_COLOR`` takes precedence over
# ``FORCE_COLOR`` in both rich and click.
#
# This MUST run at conftest import time (before any test module imports the CLI):
# the command modules build module-global ``rich.Console()`` instances at import,
# and rich freezes each Console's ``no_color`` decision in ``__init__`` from the
# environment then. An autouse fixture alone runs too late to affect those cached
# globals -- hence the import-time environment mutation here, with the fixture
# below as per-test belt-and-suspenders. conftest is imported before test modules,
# so setting these here guarantees the globals are constructed plain.
os.environ["NO_COLOR"] = "1"
os.environ.pop("FORCE_COLOR", None)
os.environ["COLUMNS"] = "200"

_MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
_SCHEMA_PATH = _MIGRATIONS_DIR / "001_initial_schema.sql"


@pytest.fixture(autouse=True)
def _force_plain_cli_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-assert plain CLI output before every test (see module-level note).

    The import-time env mutation above fixes the module-global Consoles; this
    fixture re-asserts the same environment per test so a test that mutates these
    vars cannot leak color into a later one. ``NO_COLOR`` wins over ``FORCE_COLOR``
    in rich and click; the wide ``COLUMNS`` keeps rich from wrapping a multi-word
    substring across lines. monkeypatch auto-reverts after each test.
    """
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.setenv("COLUMNS", "200")


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
