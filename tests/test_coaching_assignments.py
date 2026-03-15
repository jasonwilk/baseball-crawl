# synthetic-test-data
"""Tests for coaching_assignments table (E-100-01 schema rewrite).

Verifies that coaching_assignments works under the new E-100 schema where:
- teams uses INTEGER PRIMARY KEY AUTOINCREMENT (no team_id TEXT column)
- users has id INTEGER PK (no user_id alias, no display_name, no is_admin)
- coaching_assignments has no season_id column
- UNIQUE constraint is (user_id, team_id) — one role per user per team

Tests use a temporary SQLite database via run_migrations().
No Docker required.

Run with:
    pytest tests/test_coaching_assignments.py -v
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from migrations.apply_migrations import run_migrations  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fresh_db(tmp_path: Path) -> Path:
    """Return a path to a fresh migrated database.

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Path object pointing to the database file after run_migrations().
    """
    db_path = tmp_path / "test_coaching.db"
    run_migrations(db_path=db_path)
    return db_path


@pytest.fixture()
def db(fresh_db: Path) -> sqlite3.Connection:
    """Return an open connection with FK enforcement to the migrated database.

    Yields:
        Open sqlite3.Connection with foreign_keys=ON.
    """
    conn = sqlite3.connect(str(fresh_db))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture()
def seeded_db(db: sqlite3.Connection) -> sqlite3.Connection:
    """Return a db connection pre-seeded with one user and one team.

    teams.id is INTEGER AUTOINCREMENT; we capture it via lastrowid.
    users.id is INTEGER AUTOINCREMENT; inserted rows get auto-IDs.
    No display_name column. No season_id in coaching_assignments.

    Yields:
        Open sqlite3.Connection with seed rows inserted.
    """
    db.execute(
        "INSERT INTO users (email) VALUES (?)",
        ("coach@example.test",),
    )
    db.execute(
        "INSERT INTO teams (name, membership_type, classification) VALUES (?, ?, ?)",
        ("LSB Varsity", "member", "varsity"),
    )
    db.commit()
    yield db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _table_names(conn: sqlite3.Connection) -> set[str]:
    """Return the set of user-defined table names in the connection."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    )
    return {row[0] for row in cursor.fetchall()}


def _get_team_id(conn: sqlite3.Connection, name: str) -> int:
    """Return the INTEGER id for a team by name."""
    row = conn.execute("SELECT id FROM teams WHERE name = ?", (name,)).fetchone()
    assert row is not None, f"Team '{name}' not found"
    return row[0]


def _get_user_id(conn: sqlite3.Connection, email: str) -> int:
    """Return the INTEGER id for a user by email."""
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    assert row is not None, f"User '{email}' not found"
    return row[0]


# ---------------------------------------------------------------------------
# All tables exist after applying migrations
# ---------------------------------------------------------------------------


def test_all_expected_tables_exist(db: sqlite3.Connection) -> None:
    """All schema tables are present after applying migrations."""
    tables = _table_names(db)

    # Core data tables
    assert "seasons" in tables
    assert "players" in tables
    assert "teams" in tables
    assert "team_rosters" in tables
    assert "games" in tables
    assert "player_game_batting" in tables
    assert "player_game_pitching" in tables
    assert "player_season_batting" in tables
    assert "player_season_pitching" in tables

    # Auth tables
    assert "users" in tables
    assert "user_team_access" in tables
    assert "magic_link_tokens" in tables
    assert "passkey_credentials" in tables
    assert "sessions" in tables
    assert "coaching_assignments" in tables


# ---------------------------------------------------------------------------
# FK enforcement -- bad user_id
# ---------------------------------------------------------------------------


def test_fk_enforcement_bad_user_id_fails(seeded_db: sqlite3.Connection) -> None:
    """Inserting a coaching_assignments row with a non-existent user_id raises IntegrityError."""
    team_id = _get_team_id(seeded_db, "LSB Varsity")
    with pytest.raises(sqlite3.IntegrityError):
        seeded_db.execute(
            "INSERT INTO coaching_assignments (user_id, team_id, role) VALUES (?, ?, ?)",
            (9999, team_id, "head_coach"),
        )
        seeded_db.commit()


# ---------------------------------------------------------------------------
# FK enforcement -- bad team_id
# ---------------------------------------------------------------------------


def test_fk_enforcement_bad_team_id_fails(seeded_db: sqlite3.Connection) -> None:
    """Inserting a coaching_assignments row with a non-existent team_id raises IntegrityError."""
    user_id = _get_user_id(seeded_db, "coach@example.test")
    with pytest.raises(sqlite3.IntegrityError):
        seeded_db.execute(
            "INSERT INTO coaching_assignments (user_id, team_id, role) VALUES (?, ?, ?)",
            (user_id, 99999, "head_coach"),
        )
        seeded_db.commit()


# ---------------------------------------------------------------------------
# UNIQUE constraint: duplicate (user_id, team_id) fails
# ---------------------------------------------------------------------------


def test_unique_constraint_duplicate_assignment_fails(seeded_db: sqlite3.Connection) -> None:
    """Inserting two rows with the same (user_id, team_id) raises IntegrityError."""
    user_id = _get_user_id(seeded_db, "coach@example.test")
    team_id = _get_team_id(seeded_db, "LSB Varsity")

    seeded_db.execute(
        "INSERT INTO coaching_assignments (user_id, team_id, role) VALUES (?, ?, ?)",
        (user_id, team_id, "head_coach"),
    )
    seeded_db.commit()

    with pytest.raises(sqlite3.IntegrityError):
        seeded_db.execute(
            "INSERT INTO coaching_assignments (user_id, team_id, role) VALUES (?, ?, ?)",
            (user_id, team_id, "assistant"),
        )
        seeded_db.commit()


# ---------------------------------------------------------------------------
# Multi-role scenario: same coach, different teams
# ---------------------------------------------------------------------------


def test_multi_role_same_coach_different_teams_succeeds(seeded_db: sqlite3.Connection) -> None:
    """A coach can hold different roles on different teams."""
    user_id = _get_user_id(seeded_db, "coach@example.test")
    varsity_id = _get_team_id(seeded_db, "LSB Varsity")

    # Add a second team
    seeded_db.execute(
        "INSERT INTO teams (name, membership_type, classification) VALUES (?, ?, ?)",
        ("LSB JV", "member", "jv"),
    )
    seeded_db.commit()
    jv_id = _get_team_id(seeded_db, "LSB JV")

    # Assign head_coach on Varsity
    seeded_db.execute(
        "INSERT INTO coaching_assignments (user_id, team_id, role) VALUES (?, ?, ?)",
        (user_id, varsity_id, "head_coach"),
    )
    # Assign volunteer on JV -- same coach, different team
    seeded_db.execute(
        "INSERT INTO coaching_assignments (user_id, team_id, role) VALUES (?, ?, ?)",
        (user_id, jv_id, "volunteer"),
    )
    seeded_db.commit()

    cursor = seeded_db.execute(
        "SELECT team_id, role FROM coaching_assignments WHERE user_id = ? ORDER BY team_id;",
        (user_id,),
    )
    rows = cursor.fetchall()

    assert len(rows) == 2
    roles_by_team = {row[0]: row[1] for row in rows}
    assert roles_by_team[varsity_id] == "head_coach"
    assert roles_by_team[jv_id] == "volunteer"


# ---------------------------------------------------------------------------
# role column accepts expected values
# ---------------------------------------------------------------------------


def test_role_column_accepts_head_coach(seeded_db: sqlite3.Connection) -> None:
    """role column accepts 'head_coach'."""
    user_id = _get_user_id(seeded_db, "coach@example.test")
    team_id = _get_team_id(seeded_db, "LSB Varsity")
    seeded_db.execute(
        "INSERT INTO coaching_assignments (user_id, team_id, role) VALUES (?, ?, ?)",
        (user_id, team_id, "head_coach"),
    )
    seeded_db.commit()
    cursor = seeded_db.execute(
        "SELECT role FROM coaching_assignments WHERE user_id = ?", (user_id,)
    )
    assert cursor.fetchone()[0] == "head_coach"


def test_role_column_defaults_to_assistant(seeded_db: sqlite3.Connection) -> None:
    """role column defaults to 'assistant' when not specified."""
    user_id = _get_user_id(seeded_db, "coach@example.test")
    team_id = _get_team_id(seeded_db, "LSB Varsity")
    seeded_db.execute(
        "INSERT INTO coaching_assignments (user_id, team_id) VALUES (?, ?)",
        (user_id, team_id),
    )
    seeded_db.commit()
    cursor = seeded_db.execute(
        "SELECT role FROM coaching_assignments WHERE user_id = ?", (user_id,)
    )
    assert cursor.fetchone()[0] == "assistant"


def test_role_column_accepts_volunteer(seeded_db: sqlite3.Connection) -> None:
    """role column accepts 'volunteer'."""
    user_id = _get_user_id(seeded_db, "coach@example.test")
    team_id = _get_team_id(seeded_db, "LSB Varsity")
    seeded_db.execute(
        "INSERT INTO coaching_assignments (user_id, team_id, role) VALUES (?, ?, ?)",
        (user_id, team_id, "volunteer"),
    )
    seeded_db.commit()
    cursor = seeded_db.execute(
        "SELECT role FROM coaching_assignments WHERE user_id = ?", (user_id,)
    )
    assert cursor.fetchone()[0] == "volunteer"


# ---------------------------------------------------------------------------
# Indexes exist
# ---------------------------------------------------------------------------


def _index_names(conn: sqlite3.Connection) -> set[str]:
    """Return the set of index names in the connection."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%';"
    )
    return {row[0] for row in cursor.fetchall()}


def test_index_on_user_id_exists(db: sqlite3.Connection) -> None:
    """Index idx_coaching_assignments_user exists on coaching_assignments(user_id)."""
    assert "idx_coaching_assignments_user" in _index_names(db)


def test_index_on_team_id_exists(db: sqlite3.Connection) -> None:
    """Index idx_coaching_assignments_team exists on coaching_assignments(team_id)."""
    assert "idx_coaching_assignments_team" in _index_names(db)
