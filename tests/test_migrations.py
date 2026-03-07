"""Tests for apply_migrations.py (E-009-02 AC-3, AC-4).

Verifies that:
- Migrations apply correctly to a fresh database (AC-3).
- Applying migrations twice is idempotent -- no duplicates, clean exit (AC-4).
- The _migrations tracking table records each migration exactly once.
- WAL mode is enabled after running migrations.

Tests use a temporary SQLite database; no Docker required.

Run with:
    pytest tests/test_migrations.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from migrations.apply_migrations import (  # noqa: E402
    collect_migration_files,
    get_applied_migrations,
    run_migrations,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fresh_db(tmp_path: Path) -> Path:
    """Return a path to a non-existent database in a temporary directory.

    The database file does not exist yet; run_migrations will create it.

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Path object pointing to the future database file.
    """
    return tmp_path / "test_app.db"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMigrationFiles:
    """Verify that migration files are discovered correctly."""

    def test_at_least_one_migration_file_exists(self) -> None:
        """collect_migration_files returns at least one .sql file."""
        files = collect_migration_files()
        assert len(files) >= 1, "No migration files found in migrations/"

    def test_migration_files_sorted_by_name(self) -> None:
        """Migration files are returned in ascending order."""
        files = collect_migration_files()
        names = [f.name for f in files]
        assert names == sorted(names)

    def test_migration_files_have_sql_extension(self) -> None:
        """All discovered migration files end with .sql."""
        files = collect_migration_files()
        for f in files:
            assert f.suffix == ".sql", f"Unexpected file: {f}"


class TestRunMigrations:
    """Verify apply behavior on a fresh and an existing database."""

    def test_creates_database_file(self, fresh_db: Path) -> None:
        """run_migrations creates the .db file if it does not exist."""
        assert not fresh_db.exists()
        run_migrations(db_path=fresh_db)
        assert fresh_db.exists()

    def test_creates_migrations_tracking_table(self, fresh_db: Path) -> None:
        """run_migrations creates _migrations table."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='_migrations';"
        )
        result = cursor.fetchone()
        conn.close()
        assert result is not None, "_migrations table not found"

    def test_creates_core_schema_tables(self, fresh_db: Path) -> None:
        """run_migrations creates all expected schema tables."""
        run_migrations(db_path=fresh_db)
        expected_tables = {
            "players",
            "teams",
            "team_rosters",
            "games",
            "player_game_batting",
            "player_game_pitching",
            "player_season_batting",
        }
        conn = sqlite3.connect(str(fresh_db))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        )
        actual_tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        missing = expected_tables - actual_tables
        assert not missing, f"Missing tables after migration: {missing}"

    def test_records_migration_in_tracking_table(self, fresh_db: Path) -> None:
        """Each applied migration is recorded exactly once in _migrations."""
        run_migrations(db_path=fresh_db)
        migration_files = collect_migration_files()
        conn = sqlite3.connect(str(fresh_db))
        applied = get_applied_migrations(conn)
        conn.close()
        for f in migration_files:
            assert f.name in applied, f"{f.name} not recorded in _migrations"

    def test_wal_mode_enabled(self, fresh_db: Path) -> None:
        """WAL journal mode is set after running migrations."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        cursor = conn.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        conn.close()
        assert mode == "wal", f"Expected WAL mode, got: {mode}"

    def test_idempotent_second_run(self, fresh_db: Path) -> None:
        """Running migrations twice does not duplicate rows or raise errors."""
        run_migrations(db_path=fresh_db)

        conn = sqlite3.connect(str(fresh_db))
        count_after_first = conn.execute(
            "SELECT COUNT(*) FROM _migrations;"
        ).fetchone()[0]
        conn.close()

        # Second run -- must not raise and must not add duplicate rows.
        run_migrations(db_path=fresh_db)

        conn = sqlite3.connect(str(fresh_db))
        count_after_second = conn.execute(
            "SELECT COUNT(*) FROM _migrations;"
        ).fetchone()[0]
        conn.close()

        assert count_after_first == count_after_second, (
            f"Migration count changed on second run: "
            f"{count_after_first} -> {count_after_second}"
        )

    def test_idempotent_tables_not_duplicated(self, fresh_db: Path) -> None:
        """Running migrations twice does not create duplicate tables."""
        run_migrations(db_path=fresh_db)
        run_migrations(db_path=fresh_db)

        conn = sqlite3.connect(str(fresh_db))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        )
        table_names = [row[0] for row in cursor.fetchall()]
        conn.close()

        # No table name should appear more than once.
        assert len(table_names) == len(set(table_names)), (
            f"Duplicate tables found: {table_names}"
        )

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        """run_migrations creates parent directories as needed."""
        nested_db = tmp_path / "sub" / "nested" / "app.db"
        assert not nested_db.parent.exists()
        run_migrations(db_path=nested_db)
        assert nested_db.exists()


class TestMigration005TeamsPublicId:
    """Verify migration 005: public_id column added to teams table (E-042-01)."""

    def test_public_id_column_exists(self, fresh_db: Path) -> None:
        """After migration 005, teams table has a public_id column."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        cursor = conn.execute("PRAGMA table_info(teams);")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert "public_id" in columns, "public_id column not found in teams table"

    def test_existing_rows_have_null_public_id(self, fresh_db: Path) -> None:
        """Existing teams rows have public_id = NULL after migration (no data loss)."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        # Insert a team without public_id (simulating a pre-migration row)
        conn.execute(
            "INSERT INTO teams (team_id, name) VALUES (?, ?)",
            ("team-uuid-001", "Test Team"),
        )
        conn.commit()
        cursor = conn.execute(
            "SELECT public_id FROM teams WHERE team_id = ?", ("team-uuid-001",)
        )
        row = cursor.fetchone()
        conn.close()
        assert row is not None, "Team row not found"
        assert row[0] is None, f"Expected NULL public_id, got: {row[0]}"

    def test_unique_constraint_rejects_duplicate_public_id(self, fresh_db: Path) -> None:
        """Inserting two teams with the same non-NULL public_id raises IntegrityError."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute(
            "INSERT INTO teams (team_id, name, public_id) VALUES (?, ?, ?)",
            ("team-uuid-002", "Team A", "abc123"),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO teams (team_id, name, public_id) VALUES (?, ?, ?)",
                ("team-uuid-003", "Team B", "abc123"),
            )
            conn.commit()
        conn.close()

    def test_multiple_null_public_ids_allowed(self, fresh_db: Path) -> None:
        """Inserting multiple teams with public_id = NULL succeeds (partial index)."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute(
            "INSERT INTO teams (team_id, name, public_id) VALUES (?, ?, ?)",
            ("team-uuid-004", "Opponent A", None),
        )
        conn.execute(
            "INSERT INTO teams (team_id, name, public_id) VALUES (?, ?, ?)",
            ("team-uuid-005", "Opponent B", None),
        )
        conn.execute(
            "INSERT INTO teams (team_id, name, public_id) VALUES (?, ?, ?)",
            ("team-uuid-006", "Opponent C", None),
        )
        conn.commit()
        cursor = conn.execute(
            "SELECT COUNT(*) FROM teams WHERE public_id IS NULL;"
        )
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 3, f"Expected 3 NULL-public_id rows, got: {count}"

    def test_unique_index_exists(self, fresh_db: Path) -> None:
        """After migration 005, idx_teams_public_id index exists."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_teams_public_id';"
        )
        result = cursor.fetchone()
        conn.close()
        assert result is not None, "idx_teams_public_id index not found"
