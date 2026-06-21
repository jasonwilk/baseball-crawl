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
# Helpers
# ---------------------------------------------------------------------------

_report_fixture_counter = 0


def _insert_report_fixture(conn: sqlite3.Connection) -> int:
    """Insert a minimal team + report and return the new reports.id.

    Each call mints a unique slug so reports.slug's UNIQUE constraint never
    collides across the multiple inserts a single test makes. Uses the seeded
    'lsb-hs' program so the team FK is satisfied.
    """
    global _report_fixture_counter
    _report_fixture_counter += 1
    n = _report_fixture_counter
    team_id = conn.execute(
        "INSERT INTO teams (name, program_id, membership_type, source, is_active) "
        "VALUES (?, 'lsb-hs', 'tracked', 'manual', 1);",
        (f"Fixture Team {n}",),
    ).lastrowid
    report_id = conn.execute(
        "INSERT INTO reports (slug, team_id, title, expires_at) "
        "VALUES (?, ?, ?, ?);",
        (f"fixture-report-{n}", team_id, f"Fixture Report {n}", "2099-01-01T00:00:00Z"),
    ).lastrowid
    conn.commit()
    return report_id


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



class TestReportGenerationRunsMigration:
    """Verify migration 002_report_generation_runs.sql (E-235-01).

    Asserts the table exists with the documented column set and that the
    CHECK constraints and the UNIQUE(report_id) 1:1 index from epic E-235
    Technical Notes TN-1 are present and enforced.
    """

    def test_table_exists(self, fresh_db: Path) -> None:
        """After migrations, report_generation_runs table exists."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='report_generation_runs';"
        ).fetchone()
        conn.close()
        assert row is not None, "report_generation_runs table not found"

    def test_has_documented_columns(self, fresh_db: Path) -> None:
        """Column set matches TN-1 exactly (no extra/missing columns)."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        cursor = conn.execute("PRAGMA table_info(report_generation_runs);")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        expected = {
            # identity / lifecycle
            "id",
            "report_id",
            "started_at",
            "completed_at",
            "overall_status",
            # per-stage status
            "crawl_status",
            "load_status",
            "gc_uuid_status",
            "spray_status",
            "plays_status",
            "reconciliation_status",
            "enrichment_status",
            # per-stage counts
            "completed_games",
            "completed_games_with_data",
            "spray_games",
            "plays_games_expected",
            "plays_games_covered",
            "discrepancies_found",
            "discrepancies_corrected",
            # additive count columns (migration 003, E-236-01 TN-2)
            "boxscores_fetched",
            "load_errors",
            "plays_errors",
            "spray_games_with_data",
            # trust flags
            "season_id_used",
            # season_fallback dropped by migration 006 (E-241-02)
            "identity_match_method",
            # failure
            "error_stage",
            "error_message",
        }
        assert columns == expected, (
            f"Column set drift. Missing: {expected - columns}; "
            f"Unexpected: {columns - expected}"
        )

    def test_no_generic_count_columns(self, fresh_db: Path) -> None:
        """Counts are named -- no generic count_a/count_b (wide-row convention)."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        cursor = conn.execute("PRAGMA table_info(report_generation_runs);")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert not any(c.startswith("count_") for c in columns), (
            f"Generic count_* columns found: "
            f"{[c for c in columns if c.startswith('count_')]}"
        )

    def test_unique_report_id_index_present(self, fresh_db: Path) -> None:
        """A UNIQUE index exists on report_id (1:1 enforcer + join index)."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        # index_list returns (seq, name, unique, origin, partial)
        indexes = conn.execute(
            "PRAGMA index_list(report_generation_runs);"
        ).fetchall()
        unique_on_report_id = False
        for _seq, name, unique, *_rest in indexes:
            if not unique:
                continue
            cols = [
                r[2] for r in conn.execute(f"PRAGMA index_info({name!r});").fetchall()
            ]
            if cols == ["report_id"]:
                unique_on_report_id = True
                break
        conn.close()
        assert unique_on_report_id, "No UNIQUE index on report_generation_runs(report_id)"

    def test_report_id_uniqueness_enforced(self, fresh_db: Path) -> None:
        """Two run rows for the same report_id violate the UNIQUE index."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute("PRAGMA foreign_keys = ON;")
        report_id = _insert_report_fixture(conn)
        conn.execute(
            "INSERT INTO report_generation_runs (report_id, overall_status) "
            "VALUES (?, 'running');",
            (report_id,),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO report_generation_runs (report_id, overall_status) "
                "VALUES (?, 'running');",
                (report_id,),
            )
        conn.close()

    def test_fk_cascade_delete_removes_run_row(self, fresh_db: Path) -> None:
        """Deleting the parent report cascades to its run row."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute("PRAGMA foreign_keys = ON;")
        report_id = _insert_report_fixture(conn)
        conn.execute(
            "INSERT INTO report_generation_runs (report_id, overall_status) "
            "VALUES (?, 'running');",
            (report_id,),
        )
        conn.commit()
        conn.execute("DELETE FROM reports WHERE id = ?;", (report_id,))
        conn.commit()
        remaining = conn.execute(
            "SELECT COUNT(*) FROM report_generation_runs WHERE report_id = ?;",
            (report_id,),
        ).fetchone()[0]
        conn.close()
        assert remaining == 0, "Run row not cascade-deleted with its report"

    def test_overall_status_check_rejects_bad_value(self, fresh_db: Path) -> None:
        """overall_status CHECK rejects values outside running/completed/failed."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute("PRAGMA foreign_keys = ON;")
        report_id = _insert_report_fixture(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO report_generation_runs (report_id, overall_status) "
                "VALUES (?, 'bogus');",
                (report_id,),
            )
        conn.close()

    def test_enrichment_status_check_accepts_tier2_vocab(self, fresh_db: Path) -> None:
        """enrichment_status accepts the canonical Tier-2 vocabulary and NULL."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute("PRAGMA foreign_keys = ON;")
        for value in ("success", "unavailable-no-key", "failed", None):
            report_id = _insert_report_fixture(conn)
            conn.execute(
                "INSERT INTO report_generation_runs "
                "(report_id, overall_status, enrichment_status) VALUES (?, 'running', ?);",
                (report_id, value),
            )
        conn.commit()
        conn.close()

    def test_enrichment_status_check_rejects_invented_enum(self, fresh_db: Path) -> None:
        """enrichment_status CHECK rejects values outside the Tier-2 vocabulary."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute("PRAGMA foreign_keys = ON;")
        report_id = _insert_report_fixture(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO report_generation_runs "
                "(report_id, overall_status, enrichment_status) VALUES (?, 'running', 'ok');",
                (report_id,),
            )
        conn.close()

    def test_identity_match_method_check(self, fresh_db: Path) -> None:
        """identity_match_method accepts anchor/name_only/NULL, rejects others."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute("PRAGMA foreign_keys = ON;")
        for value in ("anchor", "name_only", None):
            report_id = _insert_report_fixture(conn)
            conn.execute(
                "INSERT INTO report_generation_runs "
                "(report_id, overall_status, identity_match_method) "
                "VALUES (?, 'running', ?);",
                (report_id, value),
            )
        conn.commit()
        bad_report_id = _insert_report_fixture(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO report_generation_runs "
                "(report_id, overall_status, identity_match_method) "
                "VALUES (?, 'running', 'fuzzy');",
                (bad_report_id,),
            )
        conn.close()

    def test_season_fallback_column_absent(self, fresh_db: Path) -> None:
        """season_fallback is dropped by migration 006 (E-241-02).

        The full migration chain applies cleanly and report_generation_runs no
        longer carries a season_fallback column. (Pre-006 this test asserted the
        column existed and defaulted to 0; E-241 removed the season-derivation
        suffix taxonomy, so the fallback telemetry no longer has a signal.)
        """
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        cursor = conn.execute("PRAGMA table_info(report_generation_runs);")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert "season_fallback" not in columns, (
            "season_fallback should be dropped by migration 006; "
            f"still present in {sorted(columns)}"
        )

    def test_table_empty_after_reset(self, fresh_db: Path) -> None:
        """A fresh migrated DB has the table present with zero seed rows (AC-5)."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        count = conn.execute(
            "SELECT COUNT(*) FROM report_generation_runs;"
        ).fetchone()[0]
        conn.close()
        assert count == 0, "report_generation_runs should be empty on a fresh DB"


class TestReportRunCountColumnsMigration:
    """Verify migration 003_report_run_count_columns.sql (E-236-01, TN-2).

    The migration adds four nullable INTEGER count columns to
    report_generation_runs. NULL means "stage didn't run". These tests assert
    the columns exist and round-trip both INTEGER and NULL values.
    """

    _NEW_COLUMNS = {
        "boxscores_fetched",
        "load_errors",
        "plays_errors",
        "spray_games_with_data",
    }

    def test_new_count_columns_exist(self, fresh_db: Path) -> None:
        """All four additive count columns are present after migration."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        cursor = conn.execute("PRAGMA table_info(report_generation_runs);")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        missing = self._NEW_COLUMNS - columns
        assert not missing, f"Migration 003 columns missing: {missing}"

    def test_new_count_columns_are_nullable_integer(self, fresh_db: Path) -> None:
        """Each new column is INTEGER-typed and nullable (no NOT NULL/DEFAULT)."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        # table_info: (cid, name, type, notnull, dflt_value, pk)
        info = {
            row[1]: row
            for row in conn.execute(
                "PRAGMA table_info(report_generation_runs);"
            ).fetchall()
        }
        conn.close()
        for col in self._NEW_COLUMNS:
            assert col in info, f"{col} not found"
            _cid, _name, col_type, notnull, dflt, _pk = info[col]
            assert col_type == "INTEGER", f"{col} type is {col_type!r}, want INTEGER"
            assert notnull == 0, f"{col} is NOT NULL; should be nullable"
            assert dflt is None, f"{col} has a DEFAULT {dflt!r}; should have none"

    def test_count_columns_round_trip_integer_and_null(
        self, fresh_db: Path
    ) -> None:
        """The new columns accept INTEGER values and NULL, and read them back."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute("PRAGMA foreign_keys = ON;")

        # Row 1: explicit INTEGER values.
        report_id_int = _insert_report_fixture(conn)
        conn.execute(
            "INSERT INTO report_generation_runs "
            "(report_id, overall_status, boxscores_fetched, load_errors, "
            "plays_errors, spray_games_with_data) "
            "VALUES (?, 'running', ?, ?, ?, ?);",
            (report_id_int, 12, 3, 1, 7),
        )
        # Row 2: omit the new columns -> they must read back NULL.
        report_id_null = _insert_report_fixture(conn)
        conn.execute(
            "INSERT INTO report_generation_runs (report_id, overall_status) "
            "VALUES (?, 'running');",
            (report_id_null,),
        )
        conn.commit()

        int_row = conn.execute(
            "SELECT boxscores_fetched, load_errors, plays_errors, "
            "spray_games_with_data FROM report_generation_runs WHERE report_id = ?;",
            (report_id_int,),
        ).fetchone()
        null_row = conn.execute(
            "SELECT boxscores_fetched, load_errors, plays_errors, "
            "spray_games_with_data FROM report_generation_runs WHERE report_id = ?;",
            (report_id_null,),
        ).fetchone()
        conn.close()

        assert int_row == (12, 3, 1, 7), f"INTEGER round-trip mismatch: {int_row}"
        assert null_row == (None, None, None, None), (
            f"Omitted columns should read back NULL: {null_row}"
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
        """Simulated upgrade: pre-E-220 schema + 001 marker -> guard fires."""
        # Create the minimum pre-E-220 state: stat tables WITHOUT
        # perspective_team_id column, plus the _migrations row claiming 001
        # has been applied.
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
            INSERT INTO _migrations (filename) VALUES ('001_initial_schema.sql');
            """
        )
        conn.commit()
        conn.close()

        # Running migrations on this state should raise -- 001 is marked
        # applied so no new migrations will run, but the schema guard will
        # detect the missing columns.
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
            INSERT INTO _migrations (filename) VALUES ('001_initial_schema.sql');
            """
        )
        conn.commit()
        conn.close()

        with pytest.raises(RuntimeError) as exc_info:
            run_migrations(db_path=fresh_db)
        assert "rebuild-procedure.md" in str(exc_info.value)


class TestWebauthnChallengesMigration:
    """Verify migration 004_webauthn_challenge_store.sql (E-238-06).

    The migration adds the TTL'd webauthn_challenges table that replaces the
    in-process passkey challenge dicts. These tests double as the
    post-migration app-health check: run_migrations is exactly what the app
    runs at startup, so a clean apply here proves the app boots its schema.
    """

    def test_table_exists_after_migration(self, fresh_db: Path) -> None:
        """run_migrations (the app's startup path) creates webauthn_challenges."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='webauthn_challenges';"
        ).fetchone()
        conn.close()
        assert row is not None, "webauthn_challenges table not found"

    def test_has_documented_columns(self, fresh_db: Path) -> None:
        """Column set matches the epic schema exactly."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(webauthn_challenges);")
        }
        conn.close()
        assert columns == {"kind", "lookup_key", "challenge", "expires_at", "created_at"}

    def test_composite_primary_key(self, fresh_db: Path) -> None:
        """(kind, lookup_key) is the composite primary key."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        # table_info: (cid, name, type, notnull, dflt_value, pk)
        pk_cols = {
            row[1]: row[5]
            for row in conn.execute("PRAGMA table_info(webauthn_challenges);")
        }
        conn.close()
        assert pk_cols["kind"] > 0 and pk_cols["lookup_key"] > 0
        assert pk_cols["challenge"] == 0

    def test_expires_at_index_present(self, fresh_db: Path) -> None:
        """The expires_at index (for the sweep-on-write) is created."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name='idx_webauthn_challenges_expires_at';"
        ).fetchone()
        conn.close()
        assert row is not None, "expires_at index not found"

    def test_expires_at_default_is_future_datetime(self, fresh_db: Path) -> None:
        """The expires_at default is a SQLite datetime in the future (no epoch float)."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute(
            "INSERT INTO webauthn_challenges (kind, lookup_key, challenge) "
            "VALUES ('login', 'k', 'c');"
        )
        conn.commit()
        live, raw = conn.execute(
            "SELECT expires_at > datetime('now'), expires_at "
            "FROM webauthn_challenges WHERE lookup_key='k';"
        ).fetchone()
        conn.close()
        assert live == 1
        # Datetime text 'YYYY-MM-DD HH:MM:SS' (space, no T/Z) -- not an epoch float.
        assert " " in raw and "T" not in raw

    def test_kind_check_constraint_enforced(self, fresh_db: Path) -> None:
        """kind is constrained to 'login' / 'registration'."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO webauthn_challenges (kind, lookup_key, challenge) "
                "VALUES ('bogus', 'k', 'c');"
            )
        conn.close()

    def test_table_empty_on_fresh_db(self, fresh_db: Path) -> None:
        """A freshly migrated DB has the table present with zero rows."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        count = conn.execute("SELECT COUNT(*) FROM webauthn_challenges;").fetchone()[0]
        conn.close()
        assert count == 0

    def test_migration_idempotent_second_run(self, fresh_db: Path) -> None:
        """A second run_migrations leaves the table intact (IF NOT EXISTS)."""
        run_migrations(db_path=fresh_db)
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='webauthn_challenges';"
        ).fetchone()
        conn.close()
        assert row is not None


class TestScheduledReportRunsMigration:
    """Verify migration 005_scheduled_report_runs.sql (E-240-03, TN-6).

    Asserts the new audit table exists with the documented column set, that
    both CHECK vocabularies (`resolution_outcome` and `delivery_status`) and
    the `UNIQUE(own_team_id, opponent_root_team_id, game_date)` idempotency
    index are present and enforced, and that `report_id` is ON DELETE SET NULL
    (NOT cascade -- the audit-survival invariant). Schema tests follow
    Test-Validates-Spec against the migration file.
    """

    @staticmethod
    def _insert_slot_fixture(
        conn: sqlite3.Connection, **cols: object
    ) -> tuple[int, str]:
        """Insert a minimal team + scheduled_report_runs row.

        Returns (own_team_id, game_date). Extra columns override/extend the
        minimal NOT-NULL set so individual CHECK/UNIQUE tests stay terse.
        """
        team_id = conn.execute(
            "INSERT INTO teams (name, membership_type, source, is_active) "
            "VALUES ('Sched Fixture', 'tracked', 'manual', 1);"
        ).lastrowid
        row = {
            "game_date": "2026-06-20",
            "own_team_id": team_id,
            "opponent_root_team_id": "root-xyz",
            "resolution_outcome": "auto_resolved",
        }
        row.update(cols)
        keys = list(row.keys())
        placeholders = ",".join("?" for _ in keys)
        conn.execute(
            f"INSERT INTO scheduled_report_runs ({','.join(keys)}) "
            f"VALUES ({placeholders});",
            [row[k] for k in keys],
        )
        return team_id, str(row["game_date"])

    def test_table_exists(self, fresh_db: Path) -> None:
        """After migrations, scheduled_report_runs table exists."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='scheduled_report_runs';"
        ).fetchone()
        conn.close()
        assert row is not None, "scheduled_report_runs table not found"

    def test_has_documented_columns(self, fresh_db: Path) -> None:
        """Column set matches TN-6 exactly (no extra/missing columns)."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(scheduled_report_runs);")
        }
        conn.close()
        expected = {
            "id",
            "game_date",
            "own_team_id",
            "opponent_root_team_id",
            "opponent_name",
            "resolution_outcome",
            "resolved_public_id",
            "report_id",
            "report_slug",
            "delivery_status",
            "error_message",
            "created_at",
            "updated_at",
        }
        assert columns == expected, (
            f"Column set drift. Missing: {expected - columns}; "
            f"Unexpected: {columns - expected}"
        )

    def test_unique_slot_index_present(self, fresh_db: Path) -> None:
        """A UNIQUE index exists on (own_team_id, opponent_root_team_id, game_date)."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        indexes = conn.execute(
            "PRAGMA index_list(scheduled_report_runs);"
        ).fetchall()
        found = False
        for _seq, name, unique, *_rest in indexes:
            if not unique:
                continue
            cols = [
                r[2] for r in conn.execute(f"PRAGMA index_info({name!r});").fetchall()
            ]
            if cols == ["own_team_id", "opponent_root_team_id", "game_date"]:
                found = True
                break
        conn.close()
        assert found, (
            "No UNIQUE index on "
            "scheduled_report_runs(own_team_id, opponent_root_team_id, game_date)"
        )

    def test_slot_uniqueness_enforced(self, fresh_db: Path) -> None:
        """Two rows with the same (team, opponent, date) violate the UNIQUE index."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute("PRAGMA foreign_keys = ON;")
        team_id, game_date = self._insert_slot_fixture(conn)
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO scheduled_report_runs "
                "(game_date, own_team_id, opponent_root_team_id, resolution_outcome) "
                "VALUES (?, ?, 'root-xyz', 'auto_resolved');",
                (game_date, team_id),
            )
        conn.close()

    def test_resolution_outcome_check_accepts_vocabulary(self, fresh_db: Path) -> None:
        """resolution_outcome accepts the full TN-11 four-state vocabulary."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute("PRAGMA foreign_keys = ON;")
        for i, value in enumerate(
            (
                "auto_resolved",
                "unresolved_mappable",
                "no_gc_presence",
                "deferred_placeholder",
            )
        ):
            # Distinct opponent token per row keeps the UNIQUE index from firing.
            self._insert_slot_fixture(
                conn, opponent_root_team_id=f"root-{i}", resolution_outcome=value
            )
        conn.commit()
        conn.close()

    def test_resolution_outcome_check_rejects_bad_value(self, fresh_db: Path) -> None:
        """resolution_outcome CHECK rejects values outside the four-state set."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute("PRAGMA foreign_keys = ON;")
        with pytest.raises(sqlite3.IntegrityError):
            self._insert_slot_fixture(conn, resolution_outcome="bogus")
        conn.close()

    def test_delivery_status_check_accepts_vocabulary_and_null(
        self, fresh_db: Path
    ) -> None:
        """delivery_status accepts generated/no_games/failed/skipped and NULL."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute("PRAGMA foreign_keys = ON;")
        for i, value in enumerate(
            ("generated", "no_games", "failed", "skipped", None)
        ):
            self._insert_slot_fixture(
                conn, opponent_root_team_id=f"root-d{i}", delivery_status=value
            )
        conn.commit()
        conn.close()

    def test_delivery_status_check_rejects_bad_value(self, fresh_db: Path) -> None:
        """delivery_status CHECK rejects values outside the four-state set."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute("PRAGMA foreign_keys = ON;")
        with pytest.raises(sqlite3.IntegrityError):
            self._insert_slot_fixture(conn, delivery_status="delivered")
        conn.close()

    def test_report_id_on_delete_set_null_not_cascade(self, fresh_db: Path) -> None:
        """AUDIT SURVIVAL: deleting the report NULLs report_id; the row SURVIVES.

        The deliberate mirror-image of report_generation_runs' ON DELETE
        CASCADE -- a scheduled_report_runs row is an audit record that must
        outlive report cleanup. Run on an FK-ON connection so the FK action
        fires.
        """
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute("PRAGMA foreign_keys = ON;")
        report_id = _insert_report_fixture(conn)
        team_id, game_date = self._insert_slot_fixture(
            conn, report_id=report_id, delivery_status="generated"
        )
        conn.commit()

        conn.execute("DELETE FROM reports WHERE id = ?;", (report_id,))
        conn.commit()

        row = conn.execute(
            "SELECT report_id FROM scheduled_report_runs "
            "WHERE own_team_id = ? AND game_date = ?;",
            (team_id, game_date),
        ).fetchone()
        conn.close()
        assert row is not None, "audit row was cascade-deleted with the report"
        assert row[0] is None, "report_id should be NULLed by ON DELETE SET NULL"

    def test_timestamp_defaults_are_sqlite_datetime(self, fresh_db: Path) -> None:
        """created_at / updated_at default to SQLite datetime text (no T/Z)."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute("PRAGMA foreign_keys = ON;")
        team_id, game_date = self._insert_slot_fixture(conn)
        conn.commit()
        created, updated = conn.execute(
            "SELECT created_at, updated_at FROM scheduled_report_runs "
            "WHERE own_team_id = ? AND game_date = ?;",
            (team_id, game_date),
        ).fetchone()
        conn.close()
        for ts in (created, updated):
            assert ts is not None and " " in ts and "T" not in ts and "Z" not in ts, (
                f"timestamp default is not SQLite datetime text: {ts!r}"
            )

    def test_table_empty_on_fresh_db(self, fresh_db: Path) -> None:
        """A freshly migrated DB has the table present with zero rows."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        count = conn.execute(
            "SELECT COUNT(*) FROM scheduled_report_runs;"
        ).fetchone()[0]
        conn.close()
        assert count == 0

    def test_migration_idempotent_second_run(self, fresh_db: Path) -> None:
        """A second run_migrations leaves the table intact (IF NOT EXISTS)."""
        run_migrations(db_path=fresh_db)
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='scheduled_report_runs';"
        ).fetchone()
        conn.close()
        assert row is not None

