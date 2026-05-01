"""Tests for apply_migrations.py (E-009-02 AC-3, AC-4; updated E-100-01).

Verifies that:
- Migrations apply correctly to a fresh database (AC-3).
- Applying migrations twice is idempotent -- no duplicates, clean exit (AC-4).
- The _migrations tracking table records each migration exactly once.
- WAL mode is enabled after running migrations.

Tests use a temporary SQLite database; no Docker required.

Run with:
    pytest tests/test_migrations.py

# noqa: fixture-schema
Fixture-schema rationale (E-221-03):
This file tests the migration runner itself. Several tests deliberately
construct pre-E-220 stale schemas (stat tables WITHOUT the
perspective_team_id column that the real schema now owns) to verify the
runner detects the drift and emits an actionable error pointing at the
rebuild procedure. The intentionally-drifted inline schemas ARE the subject
under test -- using `load_real_schema` would defeat the point.
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

from migrations.apply_migrations import (  # noqa: E402
    apply_migration,
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

    def test_expected_migrations_exist(self) -> None:
        """Exactly the expected migration files exist in migrations/."""
        files = collect_migration_files()
        names = [f.name for f in files]
        assert "001_initial_schema.sql" in names
        # Archived migrations (002-015) should not be present
        archived = {
            "002_add_user_role.sql",
            "003_add_crawl_jobs.sql",
            "004_add_team_season_year.sql",
            "005_backfill_teams_public_id.sql",
        }
        unexpected = archived & set(names)
        assert not unexpected, f"Archived migrations still in migrations/: {unexpected}"


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
            "programs",
            "seasons",
            "players",
            "teams",
            "team_opponents",
            "team_rosters",
            "games",
            "player_game_batting",
            "player_game_pitching",
            "player_season_batting",
            "player_season_pitching",
            "spray_charts",
            "opponent_links",
            "scouting_runs",
            "users",
            "user_team_access",
            "magic_link_tokens",
            "passkey_credentials",
            "sessions",
            "coaching_assignments",
            "crawl_jobs",
            "plays",
            "play_events",
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

    def test_programs_seed_row_inserted(self, fresh_db: Path) -> None:
        """001_initial_schema.sql inserts the lsb-hs program seed row."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        row = conn.execute(
            "SELECT program_id, name, program_type FROM programs WHERE program_id = 'lsb-hs';"
        ).fetchone()
        conn.close()
        assert row is not None, "lsb-hs seed row not found in programs"
        assert row[0] == "lsb-hs"
        assert "Lincoln Standing Bear" in row[1]
        assert row[2] == "hs"


class TestUserRoleMigration:
    """Verify migration 002_add_user_role.sql behavior."""

    def test_users_table_has_role_column(self, fresh_db: Path) -> None:
        """After migrations, users table has a role column."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        cursor = conn.execute("PRAGMA table_info(users);")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert "role" in columns, "role column not found in users table"

    def test_role_column_defaults_to_user(self, fresh_db: Path) -> None:
        """Inserting a user row without specifying role yields role='user'."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute(
            "INSERT INTO users (email, created_at) VALUES ('test@example.com', datetime('now'));"
        )
        conn.commit()
        row = conn.execute(
            "SELECT role FROM users WHERE email = 'test@example.com';"
        ).fetchone()
        conn.close()
        assert row is not None, "Inserted user row not found"
        assert row[0] == "user", f"Expected role='user', got role='{row[0]}'"

    def test_role_migration_recorded_in_tracking_table(self, fresh_db: Path) -> None:
        """001_initial_schema.sql (which includes user role) is recorded in _migrations after apply."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        applied = get_applied_migrations(conn)
        conn.close()
        assert "001_initial_schema.sql" in applied, (
            "001_initial_schema.sql not found in _migrations tracking table"
        )


class TestFKEnforcementDuringMigration:
    """Verify that FK constraints are enforced during migration execution.

    executescript() resets connection state, so PRAGMA foreign_keys=ON must
    be included inline in the SQL string. These tests confirm that the fix
    in apply_migration() actually enforces FK constraints.
    """

    def test_fk_violation_rejected_during_migration(self, fresh_db: Path):
        """A migration containing a bad FK reference raises IntegrityError."""
        # First, apply the real schema so FK-bearing tables exist.
        run_migrations(db_path=fresh_db)

        # Create a fake migration file that inserts a row with an invalid FK.
        # teams.program_id references programs(program_id); 'nonexistent-program'
        # does not exist, so this INSERT must fail if FKs are enforced.
        bad_sql = (
            "INSERT INTO teams (program_id, name, membership_type, source, is_active) "
            "VALUES ('nonexistent-program', 'Bad Team', 'tracked', 'manual', 1);"
        )
        fake_migration = fresh_db.parent / "999_fk_violation_test.sql"
        fake_migration.write_text(bad_sql, encoding="utf-8")

        conn = sqlite3.connect(str(fresh_db))
        try:
            with pytest.raises(sqlite3.IntegrityError):
                apply_migration(conn, fake_migration)
        finally:
            conn.close()

    def test_fk_enforcement_pragma_is_inline(self, fresh_db: Path):
        """After running a migration via executescript, FK enforcement is active.

        Directly verifies that PRAGMA foreign_keys is ON after apply_migration
        runs -- proving the inline pragma approach works.
        """
        run_migrations(db_path=fresh_db)

        # Create a harmless migration that just inserts a program row.
        harmless_sql = (
            "INSERT OR IGNORE INTO programs (program_id, name, program_type) "
            "VALUES ('test-prog', 'Test Program', 'hs');"
        )
        fake_migration = fresh_db.parent / "998_harmless.sql"
        fake_migration.write_text(harmless_sql, encoding="utf-8")

        conn = sqlite3.connect(str(fresh_db))
        try:
            apply_migration(conn, fake_migration)
            # After executescript with inline PRAGMA, foreign_keys should be ON.
            fk_status = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
            assert fk_status == 1, (
                f"Expected foreign_keys=1 after migration, got {fk_status}"
            )
        finally:
            conn.close()


class TestCrawlJobsMigration:
    """Verify migration 003_add_crawl_jobs.sql behavior."""

    def test_crawl_jobs_table_exists(self, fresh_db: Path) -> None:
        """After migrations, crawl_jobs table exists."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='crawl_jobs';"
        )
        result = cursor.fetchone()
        conn.close()
        assert result is not None, "crawl_jobs table not found after migration"

    def test_crawl_jobs_has_expected_columns(self, fresh_db: Path) -> None:
        """crawl_jobs table has all required columns including sync_type."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        cursor = conn.execute("PRAGMA table_info(crawl_jobs);")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        expected = {
            "id",
            "team_id",
            "sync_type",
            "status",
            "started_at",
            "completed_at",
            "error_message",
            "games_crawled",
        }
        missing = expected - columns
        assert not missing, f"crawl_jobs missing columns: {missing}"

    def test_crawl_jobs_migration_recorded(self, fresh_db: Path) -> None:
        """001_initial_schema.sql (which includes crawl_jobs) is recorded in _migrations after apply."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        applied = get_applied_migrations(conn)
        conn.close()
        assert "001_initial_schema.sql" in applied, (
            "001_initial_schema.sql not found in _migrations tracking table"
        )



class TestE220UpgradeGuard:
    """E-220 remediation: run_migrations must detect in-place upgrade mismatch.

    The migration runner tracks by filename, so a DB populated with the old
    (pre-E-220) 001_initial_schema.sql will appear "up to date" when the new
    001 is on disk.  The guard must fail loudly in this case, pointing the
    operator to the rebuild procedure.
    """

    def test_fresh_install_passes_guard(self, fresh_db: Path) -> None:
        """Clean install (empty DB -> run migrations) must not raise."""
        run_migrations(db_path=fresh_db)
        # And idempotent second run also passes.
        run_migrations(db_path=fresh_db)

    def test_upgrade_without_wipe_raises_runtime_error(self, fresh_db: Path) -> None:
        """Simulated upgrade: pre-E-220 schema + all-migrations marker -> guard fires."""
        # Create the minimum pre-E-220 state: stat tables WITHOUT
        # perspective_team_id column, plus _migrations rows claiming all
        # migrations to date have been applied.  The guard fires AFTER the
        # pending-migrations loop, so all real migration files must be
        # marked applied for this test to exercise the guard exclusively
        # (otherwise the missing reports table would short-circuit before
        # the guard runs).
        conn = sqlite3.connect(str(fresh_db))
        conn.executescript(
            """
            CREATE TABLE _migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            -- Pre-E-220 stat tables: NO perspective_team_id column.
            CREATE TABLE player_game_batting (
                id INTEGER PRIMARY KEY,
                game_id TEXT NOT NULL,
                player_id TEXT NOT NULL,
                team_id INTEGER NOT NULL
            );
            CREATE TABLE player_game_pitching (
                id INTEGER PRIMARY KEY,
                game_id TEXT NOT NULL,
                player_id TEXT NOT NULL,
                team_id INTEGER NOT NULL
            );
            CREATE TABLE spray_charts (
                id INTEGER PRIMARY KEY,
                game_id TEXT,
                player_id TEXT,
                team_id INTEGER
            );
            CREATE TABLE plays (
                id INTEGER PRIMARY KEY,
                game_id TEXT NOT NULL,
                play_order INTEGER NOT NULL,
                inning INTEGER NOT NULL,
                half TEXT NOT NULL,
                season_id TEXT NOT NULL,
                batting_team_id INTEGER NOT NULL,
                batter_id TEXT NOT NULL
            );
            """
        )
        # Mark every existing migration file as already applied so the guard
        # is the only code path that can fail this test.  When new migrations
        # are added in future stories, they get marked here automatically --
        # no test edit required.
        for migration_file in collect_migration_files():
            conn.execute(
                "INSERT INTO _migrations (filename) VALUES (?)",
                (migration_file.name,),
            )
        conn.commit()
        conn.close()

        # Running migrations on this state should raise -- all migrations are
        # marked applied so no new migrations will run, but the schema guard
        # will detect the missing columns.
        with pytest.raises(RuntimeError, match="E-220 schema mismatch"):
            run_migrations(db_path=fresh_db)

    def test_guard_error_message_points_to_rebuild_procedure(
        self, fresh_db: Path
    ) -> None:
        """The error message must mention the rebuild procedure doc path."""
        conn = sqlite3.connect(str(fresh_db))
        conn.executescript(
            """
            CREATE TABLE _migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE player_game_batting (id INTEGER PRIMARY KEY, team_id INTEGER);
            CREATE TABLE player_game_pitching (id INTEGER PRIMARY KEY, team_id INTEGER);
            CREATE TABLE spray_charts (id INTEGER PRIMARY KEY, team_id INTEGER);
            CREATE TABLE plays (id INTEGER PRIMARY KEY, team_id INTEGER);
            """
        )
        # Mark every existing migration file as already applied so the guard
        # path is the only failure mode this test can exercise.
        for migration_file in collect_migration_files():
            conn.execute(
                "INSERT INTO _migrations (filename) VALUES (?)",
                (migration_file.name,),
            )
        conn.commit()
        conn.close()

        with pytest.raises(RuntimeError) as exc_info:
            run_migrations(db_path=fresh_db)
        assert "rebuild-procedure.md" in str(exc_info.value)

