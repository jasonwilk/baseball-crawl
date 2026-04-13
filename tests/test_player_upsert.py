"""Unit tests for src.db.players.ensure_player_row().

Tests all 6 name-transition cases per AC-8, plus new-player insertion.
"""

from __future__ import annotations

import sqlite3

import pytest

from src.db.players import ensure_player_row
from tests.conftest import load_real_schema


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory SQLite database with the production schema (FK enforcement on)."""
    conn = sqlite3.connect(":memory:")
    load_real_schema(conn)
    return conn


def _get_player(db: sqlite3.Connection, player_id: str) -> tuple[str, str]:
    """Return (first_name, last_name) for a player_id."""
    row = db.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?",
        (player_id,),
    ).fetchone()
    assert row is not None, f"Player {player_id} not found"
    return row[0], row[1]


class TestNewPlayerInsertion:
    """AC-1: ensure_player_row creates a new row when none exists."""

    def test_insert_new_player(self, db: sqlite3.Connection) -> None:
        ensure_player_row(db, "p1", "Oliver", "Smith")
        first, last = _get_player(db, "p1")
        assert first == "Oliver"
        assert last == "Smith"

    def test_insert_stub_player(self, db: sqlite3.Connection) -> None:
        ensure_player_row(db, "p1", "Unknown", "Unknown")
        first, last = _get_player(db, "p1")
        assert first == "Unknown"
        assert last == "Unknown"


class TestUnknownToShort:
    """AC-8 case: Unknown -> short name (upgrade)."""

    def test_unknown_to_initial_first_name(self, db: sqlite3.Connection) -> None:
        ensure_player_row(db, "p1", "Unknown", "Unknown")
        ensure_player_row(db, "p1", "O", "S")
        first, last = _get_player(db, "p1")
        assert first == "O"
        assert last == "S"


class TestUnknownToFull:
    """AC-8 case: Unknown -> full name (upgrade)."""

    def test_unknown_to_full_name(self, db: sqlite3.Connection) -> None:
        ensure_player_row(db, "p1", "Unknown", "Unknown")
        ensure_player_row(db, "p1", "Oliver", "Smith")
        first, last = _get_player(db, "p1")
        assert first == "Oliver"
        assert last == "Smith"


class TestShortToFull:
    """AC-3 / AC-8 case: short -> full name (upgrade)."""

    def test_initial_to_full_first_name(self, db: sqlite3.Connection) -> None:
        ensure_player_row(db, "p1", "O", "S")
        ensure_player_row(db, "p1", "Oliver", "Smith")
        first, last = _get_player(db, "p1")
        assert first == "Oliver"
        assert last == "Smith"


class TestFullToShortNoOp:
    """AC-2 / AC-8 case: full -> short name (no-op, preserved)."""

    def test_full_to_initial_preserves_first_name(self, db: sqlite3.Connection) -> None:
        ensure_player_row(db, "p1", "Oliver", "Smith")
        ensure_player_row(db, "p1", "O", "S")
        first, last = _get_player(db, "p1")
        assert first == "Oliver"
        assert last == "Smith"


class TestSameToSameNoOp:
    """AC-8 case: same -> same (no-op)."""

    def test_same_name_no_change(self, db: sqlite3.Connection) -> None:
        ensure_player_row(db, "p1", "Oliver", "Smith")
        ensure_player_row(db, "p1", "Oliver", "Smith")
        first, last = _get_player(db, "p1")
        assert first == "Oliver"
        assert last == "Smith"


class TestFullToUnknownNoOp:
    """AC-8 case: full -> Unknown (no-op)."""

    def test_full_to_unknown_preserves_name(self, db: sqlite3.Connection) -> None:
        ensure_player_row(db, "p1", "Oliver", "Smith")
        ensure_player_row(db, "p1", "Unknown", "Unknown")
        first, last = _get_player(db, "p1")
        assert first == "Oliver"
        assert last == "Smith"


class TestIndependentNameComponents:
    """AC-5: first_name and last_name are evaluated independently."""

    def test_upgrade_first_keep_last(self, db: sqlite3.Connection) -> None:
        ensure_player_row(db, "p1", "O", "Smith")
        ensure_player_row(db, "p1", "Oliver", "S")
        first, last = _get_player(db, "p1")
        assert first == "Oliver"
        assert last == "Smith"

    def test_upgrade_last_keep_first(self, db: sqlite3.Connection) -> None:
        ensure_player_row(db, "p1", "Oliver", "S")
        ensure_player_row(db, "p1", "O", "Smith")
        first, last = _get_player(db, "p1")
        assert first == "Oliver"
        assert last == "Smith"

    def test_unknown_first_real_last(self, db: sqlite3.Connection) -> None:
        ensure_player_row(db, "p1", "Unknown", "Smith")
        first, last = _get_player(db, "p1")
        assert first == "Unknown"
        assert last == "Smith"
        ensure_player_row(db, "p1", "Oliver", "Unknown")
        first, last = _get_player(db, "p1")
        assert first == "Oliver"
        assert last == "Smith"


class TestStubOnlyLoadersNoop:
    """Stub-only loaders pass Unknown/Unknown -- should not overwrite real names."""

    def test_stub_call_after_real_name_is_noop(self, db: sqlite3.Connection) -> None:
        ensure_player_row(db, "p1", "Oliver", "Smith")
        # Simulates what plays_loader, spray_chart_loader etc. do:
        ensure_player_row(db, "p1", "Unknown", "Unknown")
        first, last = _get_player(db, "p1")
        assert first == "Oliver"
        assert last == "Smith"
