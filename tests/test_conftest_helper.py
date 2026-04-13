"""Tests for the ``load_real_schema`` helper in ``tests/conftest.py``."""

from __future__ import annotations

import sqlite3

import pytest

from tests.conftest import load_real_schema


def test_load_real_schema_creates_production_tables():
    """AC-1: helper loads every table from 001_initial_schema.sql."""
    conn = sqlite3.connect(":memory:")
    load_real_schema(conn)

    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = {row[0] for row in rows}

    # Spot-check core tables from the production schema. If any of these are
    # missing, the helper did not load the real migration.
    for expected in ("teams", "players", "games", "seasons", "programs"):
        assert expected in table_names, f"expected table {expected!r} missing from schema"


def test_load_real_schema_enforces_foreign_keys():
    """AC-2: FK violations raise IntegrityError, confirming PRAGMA took effect."""
    conn = sqlite3.connect(":memory:")
    load_real_schema(conn)

    # teams.program_id REFERENCES programs(program_id). Inserting a team that
    # points at a nonexistent program must raise IntegrityError when FK
    # enforcement is active.
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        conn.execute(
            "INSERT INTO teams (name, program_id, membership_type) VALUES (?, ?, ?)",
            ("Nonexistent FK Target", "program-does-not-exist", "tracked"),
        )
