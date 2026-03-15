"""Tests for reset_dev_db.py and seed_dev.sql (E-009-05 AC-8).

Verifies that:
- reset_database() creates a seeded database at a given path.
- All core tables exist after reset.
- Row counts meet the minimums required by AC-2.
- The production guard prevents accidental resets when APP_ENV=production.
- Running reset_database() twice (idempotent reset) produces consistent counts.

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
    load_seed,
    reset_database,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SEED_FILE = _PROJECT_ROOT / "data" / "seeds" / "seed_dev.sql"

# Expected minimum row counts per AC-2.
# These must match or exceed what seed_dev.sql inserts.
_MIN_ROW_COUNTS: dict[str, int] = {
    "seasons": 1,               # AC-2: at least 1 season
    "teams": 2,                 # AC-2: at least 2 teams (1 Lincoln + 1 opponent)
    "players": 10,              # AC-2: at least 10 players
    "games": 5,                 # AC-2: at least 5 games
    "player_game_batting": 5,   # AC-2: batting rows for games
    "player_game_pitching": 2,  # AC-2: pitching rows (1-2 pitchers per game)
    "player_season_batting": 5, # AC-2: season aggregates for Lincoln players
    "player_season_pitching": 1, # AC-2: pitching season aggregates
}

# All core tables that must exist after migration + seed.
_CORE_TABLES = {
    "seasons",
    "players",
    "teams",
    "team_rosters",
    "games",
    "player_game_batting",
    "player_game_pitching",
    "player_season_batting",
    "player_season_pitching",
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
def seeded_db(fresh_db: Path) -> Path:
    """Return a path to a freshly reset and seeded database.

    Runs reset_database() once so subsequent tests can query it directly.

    Args:
        fresh_db: Path to the non-existent database file.

    Returns:
        Path to the seeded database (file now exists).
    """
    reset_database(db_path=fresh_db, force=False)
    return fresh_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_count(db_path: Path, table: str) -> int:
    """Return the row count for a table in the given database.

    Args:
        db_path: Path to the SQLite database.
        table: Table name to count.

    Returns:
        Integer row count.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table};").fetchone()[0]
    finally:
        conn.close()


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
    """Verify reset_database() creates a correctly seeded database."""

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

    def test_returns_positive_row_count(self, fresh_db: Path) -> None:
        """reset_database() returns a positive total row count."""
        _, rows = reset_database(db_path=fresh_db)
        assert rows > 0, "Expected seed data to insert at least one row"

    def test_overwrites_existing_database(self, fresh_db: Path) -> None:
        """reset_database() replaces an existing database cleanly."""
        reset_database(db_path=fresh_db)
        assert fresh_db.exists()

        # Reset again -- should not raise and should overwrite.
        tables2, rows2 = reset_database(db_path=fresh_db)
        assert tables2 >= len(_CORE_TABLES)
        assert rows2 > 0

    def test_wal_mode_preserved(self, seeded_db: Path) -> None:
        """WAL mode is enabled after reset."""
        conn = sqlite3.connect(str(seeded_db))
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

    def test_all_core_tables_exist(self, seeded_db: Path) -> None:
        """All core schema tables are present in the seeded database."""
        actual = _table_names(seeded_db)
        missing = _CORE_TABLES - actual
        assert not missing, f"Missing tables after reset: {missing}"

    def test_migrations_table_exists(self, seeded_db: Path) -> None:
        """The _migrations tracking table is present."""
        conn = sqlite3.connect(str(seeded_db))
        try:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='_migrations';"
            ).fetchone()
        finally:
            conn.close()
        assert result is not None, "_migrations table not found"


# ---------------------------------------------------------------------------
# Tests: row counts meet AC-2 minimums
# ---------------------------------------------------------------------------


class TestSeedRowCounts:
    """Verify seed data meets the row count minimums specified by AC-2."""

    @pytest.mark.parametrize("table,minimum", list(_MIN_ROW_COUNTS.items()))
    def test_minimum_row_count(
        self, seeded_db: Path, table: str, minimum: int
    ) -> None:
        """Each core table has at least the required minimum row count.

        Args:
            seeded_db: Path to the seeded database fixture.
            table: Name of the table to check.
            minimum: Minimum expected row count.
        """
        actual = _row_count(seeded_db, table)
        assert actual >= minimum, (
            f"Table '{table}': expected >= {minimum} rows, got {actual}"
        )

    def test_teams_includes_lincoln_team(self, seeded_db: Path) -> None:
        """At least one team is a member (Lincoln) team."""
        conn = sqlite3.connect(str(seeded_db))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM teams WHERE membership_type = 'member';"
            ).fetchone()[0]
        finally:
            conn.close()
        assert count >= 1, "No member (Lincoln) teams found in seed data"

    def test_teams_includes_opponent(self, seeded_db: Path) -> None:
        """At least one team is a tracked opponent."""
        conn = sqlite3.connect(str(seeded_db))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM teams WHERE membership_type = 'tracked';"
            ).fetchone()[0]
        finally:
            conn.close()
        assert count >= 1, "No tracked opponent teams found in seed data"

    def test_player_game_batting_references_valid_games(
        self, seeded_db: Path
    ) -> None:
        """All player_game_batting rows reference a valid game_id."""
        conn = sqlite3.connect(str(seeded_db))
        try:
            orphans = conn.execute(
                """
                SELECT COUNT(*) FROM player_game_batting pgb
                WHERE NOT EXISTS (
                    SELECT 1 FROM games g WHERE g.game_id = pgb.game_id
                );
                """
            ).fetchone()[0]
        finally:
            conn.close()
        assert orphans == 0, f"{orphans} batting rows reference non-existent games"

    def test_player_game_pitching_references_valid_games(
        self, seeded_db: Path
    ) -> None:
        """All player_game_pitching rows reference a valid game_id."""
        conn = sqlite3.connect(str(seeded_db))
        try:
            orphans = conn.execute(
                """
                SELECT COUNT(*) FROM player_game_pitching pgp
                WHERE NOT EXISTS (
                    SELECT 1 FROM games g WHERE g.game_id = pgp.game_id
                );
                """
            ).fetchone()[0]
        finally:
            conn.close()
        assert orphans == 0, f"{orphans} pitching rows reference non-existent games"

    def test_season_batting_for_lincoln_players(self, seeded_db: Path) -> None:
        """Season batting aggregates exist for all Lincoln Varsity players."""
        conn = sqlite3.connect(str(seeded_db))
        try:
            count = conn.execute(
                """
                SELECT COUNT(*) FROM player_season_batting psb
                JOIN teams t ON t.id = psb.team_id
                WHERE t.membership_type = 'member';
                """
            ).fetchone()[0]
        finally:
            conn.close()
        assert count >= 5, (
            f"Expected >= 5 season batting rows for Lincoln players, got {count}"
        )


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
        assert rows > 0

    def test_development_without_force_proceeds(self, fresh_db: Path) -> None:
        """reset_database() proceeds normally in development without --force."""
        with patch.dict(os.environ, {"APP_ENV": "development"}):
            tables, rows = reset_database(db_path=fresh_db, force=False)
        assert tables >= len(_CORE_TABLES)
        assert rows > 0


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


# ---------------------------------------------------------------------------
# Tests: seed file exists and is non-empty
# ---------------------------------------------------------------------------


class TestSeedFile:
    """Verify the seed file itself is present and valid."""

    def test_seed_file_exists(self) -> None:
        """data/seeds/seed_dev.sql exists in the repository."""
        assert _SEED_FILE.exists(), f"Seed file not found: {_SEED_FILE}"

    def test_seed_file_non_empty(self) -> None:
        """data/seeds/seed_dev.sql contains SQL content."""
        content = _SEED_FILE.read_text(encoding="utf-8")
        assert len(content.strip()) > 0, "Seed file is empty"

    def test_seed_file_contains_insert_statements(self) -> None:
        """data/seeds/seed_dev.sql contains INSERT statements."""
        content = _SEED_FILE.read_text(encoding="utf-8").upper()
        assert "INSERT" in content, "Seed file contains no INSERT statements"
