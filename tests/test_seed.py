"""Tests for reset_dev_db.py and reset_database() (E-228-01).

Verifies that:
- reset_database() creates a database at a given path with the migrated schema.
- The reset produces an EMPTY schema: every user data table has zero rows,
  while the migration-inserted ``programs`` bootstrap row is present.
- All core tables exist after reset.
- The production guard prevents accidental resets when APP_ENV=production.
- Running reset_database() twice (idempotent reset) succeeds.

Tests use a temporary SQLite database; no Docker required, no network calls.

Run with:
    pytest tests/test_seed.py -v
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from src.db.reset import (
    check_production_guard,
    delete_database,
    get_db_path,
    reset_database,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# All core tables that must exist after migration.
_CORE_TABLES = {
    "seasons",
    "players",
    "teams",
    "team_rosters",
    "games",
    "player_game_batting",
    "player_game_pitching",
    # player_season_* dropped by migration 011 (E-259-03).
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fresh_db(tmp_path: Path) -> Path:
    """Return a path to a non-existent database in a temporary directory.

    The database file does not exist yet; reset_database will create it.

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Path object pointing to the future database file.
    """
    return tmp_path / "test_reset.db"


@pytest.fixture()
def reset_db(fresh_db: Path) -> Path:
    """Return a path to a freshly reset (empty-schema) database.

    Runs reset_database() once so subsequent tests can query it directly.

    Args:
        fresh_db: Path to the non-existent database file.

    Returns:
        Path to the reset database (file now exists).
    """
    reset_database(db_path=fresh_db, force=False)
    return fresh_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _table_names(db_path: Path) -> set[str]:
    """Return the set of user-defined table names in the database.

    Excludes internal SQLite and migration-tracking tables.

    Args:
        db_path: Path to the SQLite database.

    Returns:
        Set of table name strings.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name != '_migrations';"
        )
        return {row[0] for row in cursor.fetchall()}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tests: reset_database()
# ---------------------------------------------------------------------------


class TestResetDatabase:
    """Verify reset_database() creates an empty-schema database."""

    def test_creates_database_file(self, fresh_db: Path) -> None:
        """reset_database() creates the .db file when it does not exist."""
        assert not fresh_db.exists()
        reset_database(db_path=fresh_db)
        assert fresh_db.exists()

    def test_returns_table_count(self, fresh_db: Path) -> None:
        """reset_database() returns a non-zero table count."""
        tables, _ = reset_database(db_path=fresh_db)
        assert tables >= len(_CORE_TABLES), (
            f"Expected at least {len(_CORE_TABLES)} tables, got {tables}"
        )

    def test_returns_zero_row_count(self, fresh_db: Path) -> None:
        """reset_database() returns 0 as the second tuple element (no seed)."""
        _, rows = reset_database(db_path=fresh_db)
        assert rows == 0, "Reset must not load any seed rows"

    def test_overwrites_existing_database(self, fresh_db: Path) -> None:
        """reset_database() replaces an existing database cleanly."""
        reset_database(db_path=fresh_db)
        assert fresh_db.exists()

        # Reset again -- should not raise and should overwrite.
        tables2, rows2 = reset_database(db_path=fresh_db)
        assert tables2 >= len(_CORE_TABLES)
        assert rows2 == 0

    def test_wal_mode_preserved(self, reset_db: Path) -> None:
        """WAL mode is enabled after reset."""
        conn = sqlite3.connect(str(reset_db))
        try:
            mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        finally:
            conn.close()
        assert mode == "wal", f"Expected WAL mode, got: {mode}"


# ---------------------------------------------------------------------------
# Tests: core tables exist
# ---------------------------------------------------------------------------


class TestCoreTables:
    """Verify all core tables are present after reset."""

    def test_all_core_tables_exist(self, reset_db: Path) -> None:
        """All core schema tables are present in the reset database."""
        actual = _table_names(reset_db)
        missing = _CORE_TABLES - actual
        assert not missing, f"Missing tables after reset: {missing}"

    def test_migrations_table_exists(self, reset_db: Path) -> None:
        """The _migrations tracking table is present."""
        conn = sqlite3.connect(str(reset_db))
        try:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='_migrations';"
            ).fetchone()
        finally:
            conn.close()
        assert result is not None, "_migrations table not found"


# ---------------------------------------------------------------------------
# Tests: empty schema (TN-1 inverse assertion)
# ---------------------------------------------------------------------------


class TestEmptySchema:
    """Verify a reset produces an empty schema (no seed data).

    "Empty" per TN-1 means: every table the migrations create has zero rows,
    EXCEPT the migration-tracking table (``_migrations``) and ``programs``.
    The ``programs`` table must contain exactly the one ``lsb-hs`` bootstrap
    row inserted by migration 001.
    """

    def test_all_user_tables_empty(self, reset_db: Path) -> None:
        """Every user data table has zero rows after reset.

        Tables are enumerated dynamically from sqlite_master so a newly added
        table cannot silently escape the assertion.  ``_migrations`` and
        ``programs`` are excluded (they hold migration/bootstrap state).
        """
        conn = sqlite3.connect(str(reset_db))
        try:
            # Exclude the migration-tracking table, the programs bootstrap
            # table, and SQLite's internal bookkeeping tables (e.g.
            # sqlite_sequence, which tracks AUTOINCREMENT counters).
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT IN ('_migrations', 'programs') "
                "AND name NOT LIKE 'sqlite_%';"
            )
            table_names = [row[0] for row in cursor.fetchall()]
            assert table_names, "No user tables found -- schema not migrated?"

            non_empty: dict[str, int] = {}
            for table in table_names:
                count: int = conn.execute(
                    f"SELECT COUNT(*) FROM {table};"  # noqa: S608 -- names from schema
                ).fetchone()[0]
                if count != 0:
                    non_empty[table] = count
        finally:
            conn.close()

        assert not non_empty, f"Expected empty tables, found rows in: {non_empty}"

    def test_programs_bootstrap_row_present(self, reset_db: Path) -> None:
        """The programs table contains exactly the one lsb-hs bootstrap row."""
        conn = sqlite3.connect(str(reset_db))
        try:
            total = conn.execute("SELECT COUNT(*) FROM programs;").fetchone()[0]
            lsb = conn.execute(
                "SELECT COUNT(*) FROM programs WHERE program_id = 'lsb-hs';"
            ).fetchone()[0]
        finally:
            conn.close()
        assert total == 1, f"Expected exactly 1 programs row, got {total}"
        assert lsb == 1, "Expected the 'lsb-hs' bootstrap row to be present"


# ---------------------------------------------------------------------------
# Tests: production guard
# ---------------------------------------------------------------------------


class TestProductionGuard:
    """Verify reset_database() refuses to run in production without --force."""

    def test_production_without_force_exits(self, fresh_db: Path) -> None:
        """reset_database() calls sys.exit when APP_ENV=production and not force."""
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            with pytest.raises(SystemExit) as exc_info:
                reset_database(db_path=fresh_db, force=False)
        assert exc_info.value.code == 1

    def test_production_with_force_proceeds(self, fresh_db: Path) -> None:
        """reset_database() proceeds when APP_ENV=production and force=True."""
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            tables, rows = reset_database(db_path=fresh_db, force=True)
        assert tables >= len(_CORE_TABLES)
        assert rows == 0

    def test_development_without_force_proceeds(self, fresh_db: Path) -> None:
        """reset_database() proceeds normally in development without --force."""
        with patch.dict(os.environ, {"APP_ENV": "development"}):
            tables, rows = reset_database(db_path=fresh_db, force=False)
        assert tables >= len(_CORE_TABLES)
        assert rows == 0


# ---------------------------------------------------------------------------
# Tests: delete_database()
# ---------------------------------------------------------------------------


class TestDeleteDatabase:
    """Verify delete_database() removes the database and sidecar files."""

    def test_deletes_main_file(self, tmp_path: Path) -> None:
        """delete_database() removes the .db file when it exists."""
        db = tmp_path / "app.db"
        db.write_bytes(b"SQLite format 3\x00")
        assert db.exists()
        delete_database(db)
        assert not db.exists()

    def test_no_error_when_file_missing(self, tmp_path: Path) -> None:
        """delete_database() does not raise if the database does not exist."""
        db = tmp_path / "nonexistent.db"
        assert not db.exists()
        delete_database(db)  # Should not raise.

    def test_deletes_wal_sidecar(self, tmp_path: Path) -> None:
        """delete_database() also removes the -wal sidecar file if present."""
        db = tmp_path / "app.db"
        wal = tmp_path / "app.db-wal"
        db.write_bytes(b"")
        wal.write_bytes(b"")
        delete_database(db)
        assert not wal.exists()

    def test_deletes_shm_sidecar(self, tmp_path: Path) -> None:
        """delete_database() also removes the -shm sidecar file if present."""
        db = tmp_path / "app.db"
        shm = tmp_path / "app.db-shm"
        db.write_bytes(b"")
        shm.write_bytes(b"")
        delete_database(db)
        assert not shm.exists()


# ---------------------------------------------------------------------------
# Tests: get_db_path()
# ---------------------------------------------------------------------------


class TestGetDbPath:
    """Verify get_db_path() resolves paths correctly."""

    def test_override_takes_precedence(self, tmp_path: Path) -> None:
        """An explicit override path is returned as an absolute Path."""
        override = str(tmp_path / "custom.db")
        result = get_db_path(override=override)
        assert result == Path(override).resolve()

    def test_env_var_used_when_no_override(self, tmp_path: Path) -> None:
        """DATABASE_PATH env var is used when no override is given."""
        expected = str(tmp_path / "env.db")
        with patch.dict(os.environ, {"DATABASE_PATH": expected}):
            result = get_db_path()
        assert result == Path(expected).resolve()

    def test_default_path_when_no_env_or_override(self) -> None:
        """Falls back to the default path when no env var or override is set."""
        env_without_db_path = {k: v for k, v in os.environ.items() if k != "DATABASE_PATH"}
        with patch.dict(os.environ, env_without_db_path, clear=True):
            result = get_db_path()
        assert result.name == "app.db"
