"""Shared pytest configuration and fixtures."""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

import click.testing
import pytest
import typer.testing

# --- Global ANSI strip on the CliRunner Result (env-independent) --------------
#
# CI runners (e.g. GitHub Actions) enable color for typer's ``--help`` formatter
# via a path that env vars like ``NO_COLOR`` override locally but NOT in CI, so
# ANSI SGR codes (``\x1b[1m`` bold, ``\x1b[3Xm`` colors) leak into the captured
# output and break the plain-substring assertions the CLI tests make against
# ``result.output``. The only env-INDEPENDENT fix is to strip ANSI from the
# captured output itself -- it cannot be defeated by however the runner forces
# color, because it post-processes what CliRunner already captured.
#
# We patch the ``Result`` text getters at conftest import time so EVERY
# ``runner.invoke(...)`` result is plain, for all present and future CLI tests.
# ``typer.testing.CliRunner`` returns its OWN ``typer.testing.Result`` (a
# standalone class, not a subclass of click's), so patching click's Result alone
# does not reach it -- both classes are patched. In click >= 8.2 (installed:
# 8.4.2) and typer 0.26.8, ``.output`` is its own getter over ``output_bytes``
# -- NOT a proxy for ``.stdout`` -- so ``output`` / ``stdout`` / ``stderr`` are
# each wrapped independently.
_ANSI_SGR = re.compile(r"\x1b\[[0-9;]*m")


def _ansi_stripping_property(result_cls: type, name: str) -> property:
    """Return a property that strips ANSI SGR codes from ``result_cls.<name>``."""
    original = getattr(result_cls, name).fget

    def getter(self: object) -> str:
        return _ANSI_SGR.sub("", original(self))

    return property(getter)


for _result_cls in (click.testing.Result, typer.testing.Result):
    for _attr in ("output", "stdout", "stderr"):
        setattr(_result_cls, _attr, _ansi_stripping_property(_result_cls, _attr))

# A wide COLUMNS keeps click/rich from line-wrapping a multi-word substring
# across lines (the strip removes color, not layout). Set at import time and
# re-asserted per test below. NO_COLOR/FORCE_COLOR are intentionally NOT set:
# the global strip is env-independent, and leaving color forcing untouched lets
# the FORCE_COLOR=1 suite run genuinely exercise the strip rather than mask it.
os.environ["COLUMNS"] = "200"

_MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
_SCHEMA_PATH = _MIGRATIONS_DIR / "001_initial_schema.sql"


@pytest.fixture(autouse=True)
def _force_plain_cli_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep CLI help/command output unwrapped before every test.

    The import-time ``Result`` patch above removes ANSI color regardless of the
    runner environment; this fixture re-asserts the wide ``COLUMNS`` per test so a
    test that mutates it cannot let click/rich wrap a multi-word substring across
    lines in a later one. monkeypatch auto-reverts after each test.
    """
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
