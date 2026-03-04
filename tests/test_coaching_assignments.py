"""Tests for migrations/004_coaching_assignments.sql (E-003-02).  # synthetic-test-data

Applies migrations 001 + 003 + 004 to an in-memory SQLite database and verifies:
- All tables from all three migrations exist after applying in sequence
- FK enforcement: bad user_id, bad team_id, and bad season_id all fail with FKs ON
- UNIQUE constraint: duplicate (user_id, team_id, season_id) fails
- Multi-role scenario: same coach on different teams in the same season succeeds

Tests use an in-memory SQLite database; no file I/O required, no network calls.

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
_MIGRATION_001 = _PROJECT_ROOT / "migrations" / "001_initial_schema.sql"
_MIGRATION_003 = _PROJECT_ROOT / "migrations" / "003_auth.sql"
_MIGRATION_004 = _PROJECT_ROOT / "migrations" / "004_coaching_assignments.sql"

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with migrations 001, 003, 004 applied.

    Enables foreign key enforcement and WAL mode, then applies all three
    migrations in order.

    Yields:
        Open sqlite3.Connection with all three migrations applied and FKs enabled.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()

    for migration_file in (_MIGRATION_001, _MIGRATION_003, _MIGRATION_004):
        sql = migration_file.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.commit()

    yield conn
    conn.close()


@pytest.fixture()
def seeded_db(db: sqlite3.Connection) -> sqlite3.Connection:
    """Return a db connection pre-seeded with one user, one team, and one season.

    The seed data lets FK tests insert coaching_assignments rows without
    repeating setup in each test.

    Yields:
        Open sqlite3.Connection with seed rows inserted.
    """
    db.execute(
        "INSERT INTO users (user_id, email, display_name) VALUES (?, ?, ?)",
        (1, "coach@example.test", "Coach Smith"),
    )
    db.execute(
        "INSERT INTO teams (team_id, name, level, is_owned) VALUES ('team-varsity', 'LSB Varsity', 'varsity', 1);"
    )
    db.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) VALUES ('2026-spring-hs', 'Spring 2026 High School', 'spring-hs', 2026);"
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


# ---------------------------------------------------------------------------
# AC-4: Migration applies cleanly -- all tables exist
# ---------------------------------------------------------------------------


def test_all_tables_exist_after_applying_migrations(db: sqlite3.Connection) -> None:
    """All tables from migrations 001, 003, and 004 are present after applying in sequence."""
    tables = _table_names(db)

    # Tables from 001_initial_schema.sql
    assert "seasons" in tables
    assert "players" in tables
    assert "teams" in tables
    assert "team_rosters" in tables
    assert "games" in tables
    assert "player_game_batting" in tables
    assert "player_game_pitching" in tables
    assert "player_season_batting" in tables
    assert "player_season_pitching" in tables

    # Tables from 003_auth.sql
    assert "users" in tables
    assert "user_team_access" in tables
    assert "magic_link_tokens" in tables
    assert "passkey_credentials" in tables
    assert "sessions" in tables

    # Table from 004_coaching_assignments.sql
    assert "coaching_assignments" in tables


# ---------------------------------------------------------------------------
# AC-5: FK enforcement -- bad user_id
# ---------------------------------------------------------------------------


def test_fk_enforcement_bad_user_id_fails(seeded_db: sqlite3.Connection) -> None:
    """Inserting a coaching_assignments row with a non-existent user_id raises IntegrityError."""
    with pytest.raises(sqlite3.IntegrityError):
        seeded_db.execute(
            """
            INSERT INTO coaching_assignments (user_id, team_id, season_id, role)
            VALUES (9999, 'team-varsity', '2026-spring-hs', 'head_coach');
            """
        )


# ---------------------------------------------------------------------------
# FK enforcement -- bad team_id
# ---------------------------------------------------------------------------


def test_fk_enforcement_bad_team_id_fails(seeded_db: sqlite3.Connection) -> None:
    """Inserting a coaching_assignments row with a non-existent team_id raises IntegrityError."""
    with pytest.raises(sqlite3.IntegrityError):
        seeded_db.execute(
            """
            INSERT INTO coaching_assignments (user_id, team_id, season_id, role)
            VALUES (1, 'no-such-team', '2026-spring-hs', 'head_coach');
            """
        )


# ---------------------------------------------------------------------------
# AC-6: FK enforcement -- bad season_id
# ---------------------------------------------------------------------------


def test_fk_enforcement_bad_season_id_fails(seeded_db: sqlite3.Connection) -> None:
    """Inserting a coaching_assignments row with a non-existent season_id raises IntegrityError."""
    with pytest.raises(sqlite3.IntegrityError):
        seeded_db.execute(
            """
            INSERT INTO coaching_assignments (user_id, team_id, season_id, role)
            VALUES (1, 'team-varsity', 'no-such-season', 'head_coach');
            """
        )


# ---------------------------------------------------------------------------
# AC-7: UNIQUE constraint
# ---------------------------------------------------------------------------


def test_unique_constraint_duplicate_assignment_fails(seeded_db: sqlite3.Connection) -> None:
    """Inserting two rows with the same (user_id, team_id, season_id) raises IntegrityError."""
    seeded_db.execute(
        """
        INSERT INTO coaching_assignments (user_id, team_id, season_id, role)
        VALUES (1, 'team-varsity', '2026-spring-hs', 'head_coach');
        """
    )
    seeded_db.commit()

    with pytest.raises(sqlite3.IntegrityError):
        seeded_db.execute(
            """
            INSERT INTO coaching_assignments (user_id, team_id, season_id, role)
            VALUES (1, 'team-varsity', '2026-spring-hs', 'assistant');
            """
        )


# ---------------------------------------------------------------------------
# AC-8: Multi-role scenario -- same coach, different teams, same season
# ---------------------------------------------------------------------------


def test_multi_role_same_coach_different_teams_succeeds(seeded_db: sqlite3.Connection) -> None:
    """A coach can hold different roles on different teams in the same season."""
    # Add a second team
    seeded_db.execute(
        "INSERT INTO teams (team_id, name, level, is_owned) VALUES ('team-jv', 'LSB JV', 'jv', 1);"
    )
    seeded_db.commit()

    # Assign head_coach on Varsity
    seeded_db.execute(
        """
        INSERT INTO coaching_assignments (user_id, team_id, season_id, role)
        VALUES (1, 'team-varsity', '2026-spring-hs', 'head_coach');
        """
    )
    # Assign volunteer on JV -- same coach, same season, different team
    seeded_db.execute(
        """
        INSERT INTO coaching_assignments (user_id, team_id, season_id, role)
        VALUES (1, 'team-jv', '2026-spring-hs', 'volunteer');
        """
    )
    seeded_db.commit()

    cursor = seeded_db.execute(
        "SELECT team_id, role FROM coaching_assignments WHERE user_id = 1 ORDER BY team_id;"
    )
    rows = cursor.fetchall()

    assert len(rows) == 2
    assert ("team-jv", "volunteer") in rows
    assert ("team-varsity", "head_coach") in rows


# ---------------------------------------------------------------------------
# AC-10: role column accepts expected values
# ---------------------------------------------------------------------------


def test_role_column_accepts_head_coach(seeded_db: sqlite3.Connection) -> None:
    """role column accepts 'head_coach'."""
    seeded_db.execute(
        """
        INSERT INTO coaching_assignments (user_id, team_id, season_id, role)
        VALUES (1, 'team-varsity', '2026-spring-hs', 'head_coach');
        """
    )
    seeded_db.commit()

    cursor = seeded_db.execute(
        "SELECT role FROM coaching_assignments WHERE user_id = 1;"
    )
    assert cursor.fetchone()[0] == "head_coach"


def test_role_column_accepts_assistant(seeded_db: sqlite3.Connection) -> None:
    """role column accepts 'assistant' (the default)."""
    seeded_db.execute(
        """
        INSERT INTO coaching_assignments (user_id, team_id, season_id)
        VALUES (1, 'team-varsity', '2026-spring-hs');
        """
    )
    seeded_db.commit()

    cursor = seeded_db.execute(
        "SELECT role FROM coaching_assignments WHERE user_id = 1;"
    )
    assert cursor.fetchone()[0] == "assistant"


def test_role_column_accepts_volunteer(seeded_db: sqlite3.Connection) -> None:
    """role column accepts 'volunteer'."""
    seeded_db.execute(
        """
        INSERT INTO coaching_assignments (user_id, team_id, season_id, role)
        VALUES (1, 'team-varsity', '2026-spring-hs', 'volunteer');
        """
    )
    seeded_db.commit()

    cursor = seeded_db.execute(
        "SELECT role FROM coaching_assignments WHERE user_id = 1;"
    )
    assert cursor.fetchone()[0] == "volunteer"


# ---------------------------------------------------------------------------
# AC-2 / AC-3: Indexes exist
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


def test_index_on_team_season_exists(db: sqlite3.Connection) -> None:
    """Index idx_coaching_assignments_team_season exists on coaching_assignments(team_id, season_id)."""
    assert "idx_coaching_assignments_team_season" in _index_names(db)
