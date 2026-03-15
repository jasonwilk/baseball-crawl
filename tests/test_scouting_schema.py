"""Tests for migrations 007 (scouting_runs) and 008 (teams.gc_uuid) (E-097-02).

Verifies:
- Migration 007 applies cleanly to a fresh database.
- scouting_runs table has all required columns (including first_fetched, last_checked).
- Index on (team_id, season_id) exists.
- UNIQUE(team_id, season_id, run_type) constraint is enforced.
- ON CONFLICT DO UPDATE updates last_checked without overwriting first_fetched.
- status CHECK constraint rejects invalid values.
- Migration 008 applies cleanly (both on fresh DB and after 007).
- gc_uuid column is nullable.
- Partial unique index prevents duplicate non-null gc_uuid values.

Tests use a temporary SQLite database; no Docker required.

Run with:
    pytest tests/test_scouting_schema.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Generator

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
    """Return a path to a non-existent database in a temporary directory.

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Path object pointing to the future database file.
    """
    return tmp_path / "test_app.db"


@pytest.fixture()
def migrated_db(fresh_db: Path) -> Generator[sqlite3.Connection, None, None]:
    """Apply all migrations and yield an open connection with FK enforcement.

    Args:
        fresh_db: Path to the (not yet created) database file.

    Yields:
        Open sqlite3.Connection with foreign_keys=ON.
    """
    run_migrations(db_path=fresh_db)
    conn = sqlite3.connect(str(fresh_db))
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_team(conn: sqlite3.Connection, team_id: str, name: str) -> int:
    """Insert a minimal team row and return its INTEGER id.

    The team_id parameter is unused (teams now use INTEGER AUTOINCREMENT PK),
    but kept for backward compatibility with existing test call sites.
    """
    cursor = conn.execute(
        "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
        (name, "tracked"),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_season(conn: sqlite3.Connection, season_id: str) -> None:
    """Insert a minimal season row."""
    conn.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
        (season_id, f"Season {season_id}", "spring-hs", 2025),
    )
    conn.commit()


def _insert_scouting_run(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    run_type: str = "full",
    started_at: str = "2026-03-12T10:00:00Z",
    status: str = "running",
) -> None:
    """Insert a minimal scouting_run row.

    team_id must be an INTEGER (the teams.id value), not a string.
    """
    conn.execute(
        "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
        "VALUES (?, ?, ?, ?, ?)",
        (team_id, season_id, run_type, started_at, status),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Tests: Migration 007 -- scouting_runs table
# ---------------------------------------------------------------------------


class TestMigration007ScoutingRuns:
    """Verify migration 007: scouting_runs table (AC-1, AC-2, AC-3, AC-4, AC-7)."""

    def test_table_exists(self, migrated_db: sqlite3.Connection) -> None:
        """scouting_runs table exists after running all migrations (AC-1)."""
        cursor = migrated_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='scouting_runs';"
        )
        assert cursor.fetchone() is not None, "scouting_runs table not found"

    def test_all_required_columns_present(self, migrated_db: sqlite3.Connection) -> None:
        """scouting_runs table has all required columns including fetch timestamps (AC-1, AC-7)."""
        cursor = migrated_db.execute("PRAGMA table_info(scouting_runs);")
        columns = {row[1] for row in cursor.fetchall()}
        expected = {
            "id",
            "team_id",
            "season_id",
            "run_type",
            "started_at",
            "completed_at",
            "status",
            "games_found",
            "games_crawled",
            "players_found",
            "error_message",
            "first_fetched",
            "last_checked",
        }
        missing = expected - columns
        assert not missing, f"Missing columns in scouting_runs: {missing}"

    def test_index_on_team_season_exists(self, migrated_db: sqlite3.Connection) -> None:
        """idx_scouting_runs_team_season index exists after migration (AC-3)."""
        cursor = migrated_db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND name='idx_scouting_runs_team_season';"
        )
        assert cursor.fetchone() is not None, "idx_scouting_runs_team_season index not found"

    def test_first_fetched_set_by_default(self, migrated_db: sqlite3.Connection) -> None:
        """first_fetched is populated automatically via DEFAULT on insert (AC-1, AC-7)."""
        team_id = _insert_team(migrated_db, "team-001", "Opponent A")
        _insert_season(migrated_db, "2025-spring-hs")
        _insert_scouting_run(migrated_db, team_id, "2025-spring-hs")

        cursor = migrated_db.execute(
            "SELECT first_fetched FROM scouting_runs WHERE team_id = ?",
            (team_id,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] is not None, "first_fetched should be set by DEFAULT, got NULL"

    def test_last_checked_set_by_default(self, migrated_db: sqlite3.Connection) -> None:
        """last_checked is populated automatically via DEFAULT on insert (AC-1, AC-7)."""
        team_id = _insert_team(migrated_db, "team-002", "Opponent B")
        _insert_season(migrated_db, "2025-spring-hs")
        _insert_scouting_run(migrated_db, team_id, "2025-spring-hs")

        cursor = migrated_db.execute(
            "SELECT last_checked FROM scouting_runs WHERE team_id = ?",
            (team_id,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] is not None, "last_checked should be set by DEFAULT, got NULL"

    def test_unique_constraint_enforced(self, migrated_db: sqlite3.Connection) -> None:
        """Inserting a duplicate (team_id, season_id, run_type) raises IntegrityError (AC-4)."""
        team_id = _insert_team(migrated_db, "team-003", "Opponent C")
        _insert_season(migrated_db, "2025-spring-hs")
        _insert_scouting_run(migrated_db, team_id, "2025-spring-hs", run_type="boxscores")

        with pytest.raises(sqlite3.IntegrityError):
            migrated_db.execute(
                "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at) "
                "VALUES (?, ?, ?, ?)",
                (team_id, "2025-spring-hs", "boxscores", "2026-03-12T11:00:00Z"),
            )
            migrated_db.commit()

    def test_on_conflict_preserves_first_fetched(self, migrated_db: sqlite3.Connection) -> None:
        """ON CONFLICT DO UPDATE updates last_checked without overwriting first_fetched (AC-4)."""
        team_id = _insert_team(migrated_db, "team-004", "Opponent D")
        _insert_season(migrated_db, "2025-spring-hs")

        original_first_fetched = "2026-01-01T10:00:00.000Z"
        migrated_db.execute(
            "INSERT INTO scouting_runs "
            "(team_id, season_id, run_type, started_at, status, first_fetched, last_checked) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                team_id,
                "2025-spring-hs",
                "full",
                "2026-01-01T10:00:00Z",
                "completed",
                original_first_fetched,
                original_first_fetched,
            ),
        )
        migrated_db.commit()

        # Simulate a re-run: update last_checked and status, but NOT first_fetched.
        new_last_checked = "2026-03-12T12:00:00.000Z"
        migrated_db.execute(
            "INSERT INTO scouting_runs "
            "(team_id, season_id, run_type, started_at, status, first_fetched, last_checked) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(team_id, season_id, run_type) DO UPDATE SET "
            "last_checked = excluded.last_checked, "
            "started_at   = excluded.started_at, "
            "status       = excluded.status",
            (
                team_id,
                "2025-spring-hs",
                "full",
                "2026-03-12T12:00:00Z",
                "running",
                "2026-03-12T12:00:00.000Z",  # excluded.first_fetched -- NOT applied
                new_last_checked,
            ),
        )
        migrated_db.commit()

        cursor = migrated_db.execute(
            "SELECT first_fetched, last_checked FROM scouting_runs WHERE team_id = ?",
            (team_id,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == original_first_fetched, (
            f"first_fetched was overwritten: expected {original_first_fetched}, got {row[0]}"
        )
        assert row[1] == new_last_checked, (
            f"last_checked not updated: expected {new_last_checked}, got {row[1]}"
        )

    def test_completed_at_is_nullable(self, migrated_db: sqlite3.Connection) -> None:
        """completed_at defaults to NULL (run is in progress until explicitly set)."""
        team_id = _insert_team(migrated_db, "team-005", "Opponent E")
        _insert_season(migrated_db, "2025-spring-hs")
        _insert_scouting_run(migrated_db, team_id, "2025-spring-hs")

        cursor = migrated_db.execute(
            "SELECT completed_at FROM scouting_runs WHERE team_id = ?",
            (team_id,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] is None, "completed_at should be NULL by default"

    def test_status_check_constraint_rejects_invalid(self, migrated_db: sqlite3.Connection) -> None:
        """Inserting a status value not in ('pending','running','completed','failed') raises."""
        team_id = _insert_team(migrated_db, "team-006", "Opponent F")
        _insert_season(migrated_db, "2025-spring-hs")

        with pytest.raises(sqlite3.IntegrityError):
            migrated_db.execute(
                "INSERT INTO scouting_runs "
                "(team_id, season_id, run_type, started_at, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (team_id, "2025-spring-hs", "full", "2026-03-12T10:00:00Z", "bad_status"),
            )
            migrated_db.commit()

    def test_nullable_count_columns(self, migrated_db: sqlite3.Connection) -> None:
        """games_found, games_crawled, and players_found are nullable."""
        team_id = _insert_team(migrated_db, "team-007", "Opponent G")
        _insert_season(migrated_db, "2025-spring-hs")
        _insert_scouting_run(migrated_db, team_id, "2025-spring-hs")

        cursor = migrated_db.execute(
            "SELECT games_found, games_crawled, players_found FROM scouting_runs "
            "WHERE team_id = ?",
            (team_id,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] is None, "games_found should be NULL by default"
        assert row[1] is None, "games_crawled should be NULL by default"
        assert row[2] is None, "players_found should be NULL by default"

    def test_migration_idempotent(self, fresh_db: Path) -> None:
        """Running all migrations twice does not raise errors or duplicate tables (AC-2)."""
        run_migrations(db_path=fresh_db)
        run_migrations(db_path=fresh_db)  # second run -- must not raise

        conn = sqlite3.connect(str(fresh_db))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='scouting_runs';"
        )
        assert cursor.fetchone() is not None, "scouting_runs missing after idempotent run"
        conn.close()


# ---------------------------------------------------------------------------
# Tests: Migration 008 -- teams.gc_uuid column
# ---------------------------------------------------------------------------


class TestMigration008TeamsGcUuid:
    """Verify migration 008: gc_uuid column on teams table (AC-8, AC-9)."""

    def test_gc_uuid_column_exists(self, migrated_db: sqlite3.Connection) -> None:
        """After all migrations, teams table has a gc_uuid column (AC-8)."""
        cursor = migrated_db.execute("PRAGMA table_info(teams);")
        columns = {row[1] for row in cursor.fetchall()}
        assert "gc_uuid" in columns, "gc_uuid column not found in teams table"

    def test_gc_uuid_is_nullable(self, migrated_db: sqlite3.Connection) -> None:
        """Inserting a team without gc_uuid succeeds; column defaults to NULL."""
        cursor = migrated_db.execute(
            "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
            ("Test Opponent", "tracked"),
        )
        migrated_db.commit()
        team_id = cursor.lastrowid

        row = migrated_db.execute(
            "SELECT gc_uuid FROM teams WHERE id = ?",
            (team_id,),
        ).fetchone()
        assert row is not None
        assert row[0] is None, f"Expected NULL gc_uuid, got: {row[0]}"

    def test_gc_uuid_unique_constraint_on_non_null(self, migrated_db: sqlite3.Connection) -> None:
        """Two teams with the same non-NULL gc_uuid raises IntegrityError."""
        migrated_db.execute(
            "INSERT INTO teams (name, membership_type, gc_uuid) VALUES (?, ?, ?)",
            ("Team A", "tracked", "uuid-aabbccdd-1122-3344"),
        )
        migrated_db.commit()

        with pytest.raises(sqlite3.IntegrityError):
            migrated_db.execute(
                "INSERT INTO teams (name, membership_type, gc_uuid) VALUES (?, ?, ?)",
                ("Team B", "tracked", "uuid-aabbccdd-1122-3344"),
            )
            migrated_db.commit()

    def test_multiple_null_gc_uuids_allowed(self, migrated_db: sqlite3.Connection) -> None:
        """Multiple teams with gc_uuid = NULL succeeds (partial index, not regular UNIQUE)."""
        for i in range(3):
            migrated_db.execute(
                "INSERT INTO teams (name, membership_type, gc_uuid) VALUES (?, ?, ?)",
                (f"Null Team {i}", "tracked", None),
            )
        migrated_db.commit()

        # All three should be NULL (partial index allows multiple NULLs)
        cursor = migrated_db.execute(
            "SELECT COUNT(*) FROM teams WHERE gc_uuid IS NULL;"
        )
        count = cursor.fetchone()[0]
        assert count >= 3, f"Expected at least 3 NULL-gc_uuid rows, got: {count}"

    def test_gc_uuid_index_exists(self, migrated_db: sqlite3.Connection) -> None:
        """idx_teams_gc_uuid index exists after migration."""
        cursor = migrated_db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND name='idx_teams_gc_uuid';"
        )
        assert cursor.fetchone() is not None, "idx_teams_gc_uuid index not found"

    def test_gc_uuid_can_store_uuid_string(self, migrated_db: sqlite3.Connection) -> None:
        """A team can store a valid UUID in gc_uuid."""
        gc_uuid = "a1b2c3d4-e5f6-aaaa-bbbb-ccddeeaabbcc"
        cursor = migrated_db.execute(
            "INSERT INTO teams (name, membership_type, gc_uuid) VALUES (?, ?, ?)",
            ("Team With UUID", "tracked", gc_uuid),
        )
        migrated_db.commit()
        team_id = cursor.lastrowid

        row = migrated_db.execute(
            "SELECT gc_uuid FROM teams WHERE id = ?",
            (team_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == gc_uuid, f"Expected {gc_uuid}, got: {row[0]}"

    def test_scouting_runs_and_gc_uuid_coexist(self, fresh_db: Path) -> None:
        """scouting_runs table and gc_uuid column both exist in the initial schema."""
        run_migrations(db_path=fresh_db)

        conn = sqlite3.connect(str(fresh_db))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='scouting_runs';"
        )
        assert cursor.fetchone() is not None, "scouting_runs table missing"

        cursor = conn.execute("PRAGMA table_info(teams);")
        columns = {row[1] for row in cursor.fetchall()}
        assert "gc_uuid" in columns, "gc_uuid column missing from teams"
        conn.close()
