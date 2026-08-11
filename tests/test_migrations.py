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
            "team_rosters",
            "games",
            "player_game_batting",
            "player_game_pitching",
            # player_season_batting / player_season_pitching dropped by migration
            # 011 (E-259-03) -- the season line is derived at query time.
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


class TestMigrationRunnerAtomicity:
    """E-253-03: applying a migration is atomic (all-or-nothing).

    A multi-statement migration whose Nth statement (N > 1) fails must leave
    ZERO of that file's statements applied and no ``_migrations`` row, so the
    database never wedges into a permanent duplicate-column crash-loop. Before
    the fix, ``executescript()`` ran the body in autocommit mode: statement 1
    committed, the failing statement 2 aborted, no ``_migrations`` row was
    written, and every re-run re-attempted the already-applied statement 1
    forever.
    """

    @staticmethod
    def _players_columns(db_path: Path) -> set[str]:
        conn = sqlite3.connect(str(db_path))
        try:
            return {row[1] for row in conn.execute("PRAGMA table_info(players);")}
        finally:
            conn.close()

    @staticmethod
    def _migration_recorded(db_path: Path, filename: str) -> bool:
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT 1 FROM _migrations WHERE filename = ?;", (filename,)
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def test_midfile_failure_applies_nothing_and_records_no_row(
        self, fresh_db: Path
    ) -> None:
        """AC-1: a failing 2nd statement leaves the schema unchanged, no row.

        Statement 1 adds a column (would succeed); statement 2 references a
        non-existent table (fails). After the atomic runner rolls back, the
        column from statement 1 must be ABSENT and no ``_migrations`` row must
        exist for the file. Under the pre-fix autocommit runner the column
        would survive -- so this is a genuine failing-input test.
        """
        run_migrations(db_path=fresh_db)
        assert "de_atomic_probe" not in self._players_columns(fresh_db)

        bad_migration = fresh_db.parent / "900_atomic_midfile_fail.sql"
        bad_migration.write_text(
            "ALTER TABLE players ADD COLUMN de_atomic_probe TEXT;\n"
            "ALTER TABLE de_no_such_table ADD COLUMN x TEXT;\n",
            encoding="utf-8",
        )

        conn = sqlite3.connect(str(fresh_db))
        try:
            with pytest.raises(sqlite3.OperationalError):
                apply_migration(conn, bad_migration)
        finally:
            conn.close()

        # Statement 1 was rolled back with statement 2's failure.
        assert "de_atomic_probe" not in self._players_columns(fresh_db), (
            "statement 1 leaked past the rollback -- migration is not atomic"
        )
        # No tracking row: the migration is not falsely recorded as applied.
        assert not self._migration_recorded(fresh_db, bad_migration.name), (
            "_migrations row written despite mid-file failure"
        )

    def test_failed_migration_is_recoverable_no_crash_loop(
        self, fresh_db: Path
    ) -> None:
        """AC-2: after the cause is fixed, the migration applies cleanly.

        The classic wedge: attempt 1 adds a column then fails on a later
        statement. With the atomic runner the column is rolled back, so the
        corrected file (which adds the column once) applies without a
        "duplicate column" already-applied crash-loop.
        """
        run_migrations(db_path=fresh_db)
        migration_path = fresh_db.parent / "901_atomic_recoverable.sql"

        # Attempt 1: add column, then fail on a bad statement.
        migration_path.write_text(
            "ALTER TABLE players ADD COLUMN de_recover_probe TEXT;\n"
            "ALTER TABLE de_no_such_table ADD COLUMN x TEXT;\n",
            encoding="utf-8",
        )
        conn = sqlite3.connect(str(fresh_db))
        try:
            with pytest.raises(sqlite3.OperationalError):
                apply_migration(conn, migration_path)
        finally:
            conn.close()
        assert "de_recover_probe" not in self._players_columns(fresh_db)

        # Fix the cause: the corrected file adds the column exactly once.
        migration_path.write_text(
            "ALTER TABLE players ADD COLUMN de_recover_probe TEXT;\n",
            encoding="utf-8",
        )
        conn = sqlite3.connect(str(fresh_db))
        try:
            # Must NOT raise "duplicate column name" -- the wedge is gone.
            apply_migration(conn, migration_path)
        finally:
            conn.close()

        assert "de_recover_probe" in self._players_columns(fresh_db), (
            "corrected migration did not apply -- recovery failed"
        )
        assert self._migration_recorded(fresh_db, migration_path.name), (
            "recovered migration not recorded in _migrations"
        )

    def test_passing_multistatement_migration_records_row_once(
        self, fresh_db: Path
    ) -> None:
        """AC-3: a normal (passing) multi-statement migration commits fully and
        records exactly one ``_migrations`` row."""
        run_migrations(db_path=fresh_db)
        migration_path = fresh_db.parent / "902_atomic_passing.sql"
        migration_path.write_text(
            "ALTER TABLE players ADD COLUMN de_pass_a TEXT;\n"
            "ALTER TABLE players ADD COLUMN de_pass_b TEXT;\n",
            encoding="utf-8",
        )
        conn = sqlite3.connect(str(fresh_db))
        try:
            apply_migration(conn, migration_path)
        finally:
            conn.close()

        cols = self._players_columns(fresh_db)
        assert {"de_pass_a", "de_pass_b"} <= cols, (
            "both statements of a passing migration must apply"
        )
        conn = sqlite3.connect(str(fresh_db))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM _migrations WHERE filename = ?;",
                (migration_path.name,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert count == 1, f"expected exactly one _migrations row, got {count}"

    def test_fk_enforcement_active_for_migration_body(self, fresh_db: Path) -> None:
        """AC-4: FK enforcement is active for the migration body.

        The PRAGMA is set before BEGIN, so an FK-violating INSERT in the body
        is rejected. teams.program_id references programs(program_id); a
        non-existent program must fail with IntegrityError (proving FKs are on)
        and, being atomic, leave no tracking row.
        """
        run_migrations(db_path=fresh_db)
        fk_migration = fresh_db.parent / "903_atomic_fk.sql"
        fk_migration.write_text(
            "INSERT INTO teams (program_id, name, membership_type, source, is_active) "
            "VALUES ('de-nonexistent-program', 'Bad Team', 'tracked', 'manual', 1);\n",
            encoding="utf-8",
        )
        conn = sqlite3.connect(str(fresh_db))
        try:
            with pytest.raises(sqlite3.IntegrityError):
                apply_migration(conn, fk_migration)
        finally:
            conn.close()
        assert not self._migration_recorded(fresh_db, fk_migration.name), (
            "FK-violating migration must not be recorded as applied"
        )


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


class TestPlayEventsPitchColumnsMigration:
    """Verify migration 007_play_events_pitch_columns.sql (E-245-01, TN-4).

    The migration adds two nullable columns to play_events: pitch_type (TEXT,
    no CHECK constraint) and pitch_speed_mph (INTEGER). Both default to NULL.
    These tests assert the columns exist with the right type/nullability, carry
    no CHECK constraint on pitch_type, and round-trip values + NULL.

    play_events has an FK chain (play_id -> plays -> games/seasons/teams/
    players). These tests target the new columns only, so they insert directly
    into play_events on a connection at the default foreign_keys=OFF -- the
    column round-trip does not depend on the parent chain.
    """

    _NEW_COLUMNS = {"pitch_type", "pitch_speed_mph"}

    def test_new_pitch_columns_exist(self, fresh_db: Path) -> None:
        """Both new columns are present on play_events after migration."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        columns = {row[1] for row in conn.execute("PRAGMA table_info(play_events);")}
        conn.close()
        missing = self._NEW_COLUMNS - columns
        assert not missing, f"Migration 007 columns missing: {missing}"

    def test_pitch_columns_types_and_nullable(self, fresh_db: Path) -> None:
        """pitch_type is nullable TEXT; pitch_speed_mph is nullable INTEGER."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        # table_info: (cid, name, type, notnull, dflt_value, pk)
        info = {
            row[1]: row
            for row in conn.execute("PRAGMA table_info(play_events);").fetchall()
        }
        conn.close()
        expected_types = {"pitch_type": "TEXT", "pitch_speed_mph": "INTEGER"}
        for col, want_type in expected_types.items():
            assert col in info, f"{col} not found"
            _cid, _name, col_type, notnull, dflt, _pk = info[col]
            assert col_type == want_type, f"{col} type is {col_type!r}, want {want_type}"
            assert notnull == 0, f"{col} is NOT NULL; should be nullable"
            assert dflt is None, f"{col} has a DEFAULT {dflt!r}; should have none"

    def test_pitch_type_has_no_check_constraint(self, fresh_db: Path) -> None:
        """pitch_type carries no CHECK constraint (TN-4: vocabulary may grow).

        An out-of-vocabulary value must insert cleanly. Run with FKs OFF
        (the connection default) so the parent chain is not required.
        """
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute(
            "INSERT INTO play_events (play_id, event_order, event_type, pitch_type) "
            "VALUES (1, 1, 'pitch', 'Knuckleball');"
        )
        conn.commit()
        value = conn.execute(
            "SELECT pitch_type FROM play_events WHERE play_id = 1 AND event_order = 1;"
        ).fetchone()[0]
        conn.close()
        assert value == "Knuckleball", (
            "Out-of-vocabulary pitch_type should insert -- no CHECK constraint expected"
        )

    def test_pitch_columns_round_trip_values_and_null(self, fresh_db: Path) -> None:
        """The new columns round-trip explicit values and read back NULL when omitted.

        Also covers AC-4: an insert that does not set the new columns succeeds
        and they default to NULL.
        """
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))

        # Row 1: explicit values for both new columns.
        conn.execute(
            "INSERT INTO play_events "
            "(play_id, event_order, event_type, pitch_type, pitch_speed_mph) "
            "VALUES (1, 1, 'pitch', 'Fastball', 82);"
        )
        # Row 2: omit the new columns -> they must read back NULL.
        conn.execute(
            "INSERT INTO play_events (play_id, event_order, event_type) "
            "VALUES (1, 2, 'pitch');"
        )
        conn.commit()

        valued = conn.execute(
            "SELECT pitch_type, pitch_speed_mph FROM play_events "
            "WHERE play_id = 1 AND event_order = 1;"
        ).fetchone()
        omitted = conn.execute(
            "SELECT pitch_type, pitch_speed_mph FROM play_events "
            "WHERE play_id = 1 AND event_order = 2;"
        ).fetchone()
        conn.close()

        assert valued == ("Fastball", 82), f"value round-trip mismatch: {valued}"
        assert omitted == (None, None), (
            f"omitted columns should read back NULL: {omitted}"
        )

    def test_migration_idempotent_second_run(self, fresh_db: Path) -> None:
        """A second run_migrations does not error or duplicate the columns (AC-3)."""
        run_migrations(db_path=fresh_db)
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        cols = [row[1] for row in conn.execute("PRAGMA table_info(play_events);")]
        conn.close()
        # No column name appears twice and both new columns are present once.
        assert len(cols) == len(set(cols)), f"Duplicate columns found: {cols}"
        for col in self._NEW_COLUMNS:
            assert cols.count(col) == 1, f"{col} not present exactly once: {cols}"


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
            -- spray_charts carries its FULL column shape (incl.
            -- perspective_team_id) so pending migration 009's table REBUILD
            -- (INSERT INTO spray_charts_new SELECT <all columns> FROM
            -- spray_charts) applies cleanly under FK enforcement before the
            -- E-220 guard runs. The guard still fires on the OTHER three stat
            -- tables here (player_game_batting/pitching/plays), which remain
            -- drifted (no perspective_team_id). games/teams stubs (below) exist
            -- because 009's spray_charts_new FKs -> games/teams/players must
            -- resolve for the copy INSERT to prepare under FK ON.
            -- game_stream_id column present so pending migration 010's partial
            -- UNIQUE index (games(game_stream_id) WHERE game_stream_id IS NOT
            -- NULL) applies cleanly before the E-220 guard runs.
            CREATE TABLE games (game_id TEXT PRIMARY KEY, game_stream_id TEXT);
            CREATE TABLE teams (id INTEGER PRIMARY KEY);
            CREATE TABLE spray_charts (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id             TEXT,
                player_id           TEXT,
                team_id             INTEGER,
                perspective_team_id INTEGER,
                pitcher_id          TEXT,
                chart_type          TEXT,
                play_type           TEXT,
                play_result         TEXT,
                x                   REAL,
                y                   REAL,
                fielder_position    TEXT,
                error               INTEGER,
                event_gc_id         TEXT,
                created_at_ms       INTEGER,
                season_id           TEXT,
                UNIQUE(event_gc_id, perspective_team_id)
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
            -- play_events must exist so pending additive migration 007
            -- (ALTER TABLE play_events ADD COLUMN ...) applies cleanly before
            -- the E-220 guard runs; it is not one of the perspective-checked
            -- tables, so its shape is otherwise immaterial here.
            CREATE TABLE play_events (id INTEGER PRIMARY KEY);
            -- players/seasons/team_opponents must exist so pending migration
            -- 008 (drop gc_athlete_profile_id / season_type / team_opponents)
            -- applies cleanly before the E-220 guard runs; not perspective-
            -- checked tables, so their shape is otherwise immaterial here.
            CREATE TABLE players (player_id TEXT PRIMARY KEY, gc_athlete_profile_id TEXT);
            CREATE TABLE seasons (season_id TEXT PRIMARY KEY, season_type TEXT NOT NULL);
            CREATE TABLE team_opponents (id INTEGER PRIMARY KEY);
            -- player_season_batting/pitching must exist so pending migration 011
            -- (drop the season-aggregate tables) applies cleanly before the
            -- E-220 guard runs; not perspective-checked tables. stat_completeness
            -- is present because 011's refuse-on-member-row preflight reads it.
            CREATE TABLE player_season_batting (id INTEGER PRIMARY KEY, stat_completeness TEXT);
            CREATE TABLE player_season_pitching (id INTEGER PRIMARY KEY, stat_completeness TEXT);
            -- game_perspectives must exist so pending additive migration 013
            -- (ALTER TABLE game_perspectives ADD COLUMN plays_final_*_score)
            -- applies cleanly before the E-220 guard runs; not a perspective-
            -- checked table, so its shape is otherwise immaterial here.
            CREATE TABLE game_perspectives (game_id TEXT, perspective_team_id INTEGER);
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
            -- Full spray_charts shape + games/teams stubs so pending migration
            -- 009's table rebuild applies under FK ON before the guard runs
            -- (see sibling test for rationale). The guard still fires on the
            -- other three drifted stat tables.
            -- game_stream_id column present so pending migration 010's partial
            -- UNIQUE index (games(game_stream_id) WHERE game_stream_id IS NOT
            -- NULL) applies cleanly before the E-220 guard runs.
            CREATE TABLE games (game_id TEXT PRIMARY KEY, game_stream_id TEXT);
            CREATE TABLE teams (id INTEGER PRIMARY KEY);
            CREATE TABLE spray_charts (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id             TEXT,
                player_id           TEXT,
                team_id             INTEGER,
                perspective_team_id INTEGER,
                pitcher_id          TEXT,
                chart_type          TEXT,
                play_type           TEXT,
                play_result         TEXT,
                x                   REAL,
                y                   REAL,
                fielder_position    TEXT,
                error               INTEGER,
                event_gc_id         TEXT,
                created_at_ms       INTEGER,
                season_id           TEXT,
                UNIQUE(event_gc_id, perspective_team_id)
            );
            CREATE TABLE plays (id INTEGER PRIMARY KEY, team_id INTEGER);
            -- play_events must exist so pending additive migration 007 applies
            -- before the E-220 guard runs (see sibling test for rationale).
            CREATE TABLE play_events (id INTEGER PRIMARY KEY);
            -- players/seasons/team_opponents must exist so pending migration
            -- 008 (drop gc_athlete_profile_id / season_type / team_opponents)
            -- applies cleanly before the E-220 guard runs; not perspective-
            -- checked tables, so their shape is otherwise immaterial here.
            CREATE TABLE players (player_id TEXT PRIMARY KEY, gc_athlete_profile_id TEXT);
            CREATE TABLE seasons (season_id TEXT PRIMARY KEY, season_type TEXT NOT NULL);
            CREATE TABLE team_opponents (id INTEGER PRIMARY KEY);
            -- Season-aggregate tables for pending migration 011's DROP (see the
            -- sibling test above for the rationale).
            CREATE TABLE player_season_batting (id INTEGER PRIMARY KEY, stat_completeness TEXT);
            CREATE TABLE player_season_pitching (id INTEGER PRIMARY KEY, stat_completeness TEXT);
            -- game_perspectives must exist so pending additive migration 013
            -- (ALTER TABLE game_perspectives ADD COLUMN plays_final_*_score)
            -- applies cleanly before the E-220 guard runs; not a perspective-
            -- checked table, so its shape is otherwise immaterial here.
            CREATE TABLE game_perspectives (game_id TEXT, perspective_team_id INTEGER);
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


class TestSprayChartTypeUniqueMigration:
    """Verify migration 009_spray_chart_type_unique.sql (E-253-02).

    Migration 009 widens spray_charts uniqueness from
    ``UNIQUE(event_gc_id, perspective_team_id)`` to
    ``UNIQUE(event_gc_id, perspective_team_id, chart_type)`` via a table
    rebuild, so offense and defense for one event no longer collide. These
    tests assert the widened constraint, index/FK preservation, and -- on a
    POPULATED table -- that the rebuild drops no rows (AC-6).
    """

    @staticmethod
    def _mig(name: str) -> Path:
        for f in collect_migration_files():
            if f.name == name:
                return f
        raise AssertionError(f"migration not found: {name}")

    @staticmethod
    def _spray_unique_cols(conn: sqlite3.Connection) -> list[str] | None:
        """Return the key columns of the table-origin UNIQUE on spray_charts."""
        for _seq, name, unique, origin, *_rest in conn.execute(
            "PRAGMA index_list(spray_charts);"
        ):
            if unique and origin == "u":
                return [
                    r[2]
                    for r in conn.execute(f"PRAGMA index_info({name!r});").fetchall()
                ]
        return None

    def test_migration_009_present(self) -> None:
        """AC-5: migration 009 exists in migrations/ (008 was the prior latest)."""
        names = [f.name for f in collect_migration_files()]
        assert "009_spray_chart_type_unique.sql" in names

    def test_unique_widened_on_fresh_db(self, fresh_db: Path) -> None:
        """AC-1: a fully-migrated fresh DB carries the 3-column UNIQUE."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        try:
            cols = self._spray_unique_cols(conn)
        finally:
            conn.close()
        assert cols == ["event_gc_id", "perspective_team_id", "chart_type"]

    def test_indexes_preserved_after_rebuild(self, fresh_db: Path) -> None:
        """AC-1: both spray_charts indexes survive the table rebuild."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        try:
            idx = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND tbl_name='spray_charts' AND name LIKE 'idx_%';"
                )
            }
        finally:
            conn.close()
        assert {"idx_spray_charts_player", "idx_spray_charts_game"} <= idx

    def test_offense_and_defense_same_event_coexist(self, fresh_db: Path) -> None:
        """AC-2: offense + defense for one event+perspective both persist."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            team_id = conn.execute(
                "INSERT INTO teams (name, membership_type) VALUES ('T', 'tracked');"
            ).lastrowid
            for chart_type in ("offensive", "defensive"):
                conn.execute(
                    "INSERT OR IGNORE INTO spray_charts "
                    "(perspective_team_id, chart_type, event_gc_id, season_id) "
                    "VALUES (?, ?, 'ev1', '2026');",
                    (team_id, chart_type),
                )
            conn.commit()
            got = [
                r[0]
                for r in conn.execute(
                    "SELECT chart_type FROM spray_charts "
                    "WHERE event_gc_id='ev1' AND perspective_team_id=? "
                    "ORDER BY chart_type;",
                    (team_id,),
                )
            ]
        finally:
            conn.close()
        assert got == ["defensive", "offensive"]

    def test_rebuild_preserves_all_rows_on_populated_db(self) -> None:
        """AC-6: applying 009 through the runner to a POPULATED spray_charts
        preserves every row and widens the UNIQUE.

        Build the pre-009 state (001 + 008), populate spray_charts (including a
        NULL-key row), then apply migration 009 via ``apply_migration`` (the
        real, atomic E-253-03 runner -- FK enforced). Post-rebuild row count
        equals pre-rebuild count: closes the table-rebuild silent-drop footgun.
        """
        conn = sqlite3.connect(":memory:")
        try:
            conn.executescript(
                self._mig("001_initial_schema.sql").read_text(encoding="utf-8")
            )
            conn.executescript(
                self._mig(
                    "008_drop_identity_opponent_season_type.sql"
                ).read_text(encoding="utf-8")
            )
            # _migrations table so apply_migration can record 009.
            conn.executescript(
                "CREATE TABLE IF NOT EXISTS _migrations ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "filename TEXT NOT NULL UNIQUE, "
                "applied_at TEXT NOT NULL DEFAULT (datetime('now')));"
            )
            conn.execute("PRAGMA foreign_keys=ON;")
            team_id = conn.execute(
                "INSERT INTO teams (name, membership_type) VALUES ('T', 'tracked');"
            ).lastrowid
            rows = [
                (team_id, "offensive", "ev1", "2026"),
                (team_id, "offensive", "ev2", "2026"),
                (team_id, "offensive", "ev3", "2026"),
                (team_id, "defensive", "ev4", "2026"),
                (team_id, None, None, "2026"),  # NULL event_gc_id + NULL chart_type
            ]
            conn.executemany(
                "INSERT INTO spray_charts "
                "(perspective_team_id, chart_type, event_gc_id, season_id) "
                "VALUES (?, ?, ?, ?);",
                rows,
            )
            conn.commit()
            pre = conn.execute("SELECT COUNT(*) FROM spray_charts;").fetchone()[0]
            # Narrow UNIQUE still in force pre-rebuild.
            assert self._spray_unique_cols(conn) == [
                "event_gc_id",
                "perspective_team_id",
            ]

            apply_migration(
                conn, self._mig("009_spray_chart_type_unique.sql")
            )

            post = conn.execute("SELECT COUNT(*) FROM spray_charts;").fetchone()[0]
            assert post == pre, f"row count changed in rebuild: {pre} -> {post}"
            # Widened now, and both indexes back.
            assert self._spray_unique_cols(conn) == [
                "event_gc_id",
                "perspective_team_id",
                "chart_type",
            ]
            idx = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND tbl_name='spray_charts' AND name LIKE 'idx_%';"
                )
            }
            assert {"idx_spray_charts_player", "idx_spray_charts_game"} <= idx
            # AC-2 on the populated+rebuilt DB: a defensive row for an existing
            # offensive event now inserts (collided under the narrow key).
            conn.execute("PRAGMA foreign_keys=ON;")
            cur = conn.execute(
                "INSERT OR IGNORE INTO spray_charts "
                "(perspective_team_id, chart_type, event_gc_id, season_id) "
                "VALUES (?, 'defensive', 'ev1', '2026');",
                (team_id,),
            )
            conn.commit()
            assert cur.rowcount == 1
            # Migration recorded exactly once; FK integrity intact.
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM _migrations "
                    "WHERE filename='009_spray_chart_type_unique.sql';"
                ).fetchone()[0]
                == 1
            )
            assert conn.execute("PRAGMA foreign_key_check;").fetchall() == []
        finally:
            conn.close()


class TestGameDedupBackstopMigration:
    """Verify migration 010_game_dedup_backstop.sql (E-253-05).

    Migration 010 adds a PARTIAL UNIQUE INDEX on games(game_stream_id) gated on
    ``game_stream_id IS NOT NULL``. It backstops the cross-perspective
    SELECT-then-INSERT dedup race for games carrying the stable game_stream_id,
    WITHOUT rejecting doubleheaders (distinct game_stream_ids) or affecting
    tracked/public games whose game_stream_id is NULL.
    """

    _INDEX = "idx_games_stream_id_unique"

    @staticmethod
    def _seed_game_parents(conn: sqlite3.Connection) -> tuple[int, int]:
        """Seed one season + two teams so games FK constraints are satisfied."""
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            "INSERT INTO seasons (season_id, name, year) VALUES ('2026', 'S', 2026);"
        )
        t1 = conn.execute(
            "INSERT INTO teams (name, membership_type) VALUES ('Home', 'tracked');"
        ).lastrowid
        t2 = conn.execute(
            "INSERT INTO teams (name, membership_type) VALUES ('Away', 'tracked');"
        ).lastrowid
        conn.commit()
        return t1, t2

    @staticmethod
    def _insert_game(
        conn: sqlite3.Connection,
        game_id: str,
        home: int,
        away: int,
        stream_id: str | None,
        game_date: str = "2026-05-01",
    ) -> None:
        conn.execute(
            "INSERT INTO games (game_id, season_id, game_date, home_team_id, "
            "away_team_id, home_score, away_score, status, game_stream_id) "
            "VALUES (?, '2026', ?, ?, ?, 5, 3, 'completed', ?);",
            (game_id, game_date, home, away, stream_id),
        )

    def test_migration_010_present(self) -> None:
        """AC-5: migration 010 exists (010 follows 009 from E-253-02)."""
        names = [f.name for f in collect_migration_files()]
        assert "010_game_dedup_backstop.sql" in names

    def test_partial_unique_index_shape(self, fresh_db: Path) -> None:
        """AC-1: a UNIQUE + PARTIAL index on games(game_stream_id) exists, with
        the ``game_stream_id IS NOT NULL`` predicate."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        try:
            shape = None
            cols: list[str] = []
            # index_list: (seq, name, unique, origin, partial)
            for _seq, name, unique, _origin, partial in conn.execute(
                "PRAGMA index_list(games);"
            ):
                if name == self._INDEX:
                    shape = (unique, partial)
                    cols = [
                        r[2]
                        for r in conn.execute(
                            f"PRAGMA index_info({name!r});"
                        ).fetchall()
                    ]
            sql_row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' AND name=?;",
                (self._INDEX,),
            ).fetchone()
        finally:
            conn.close()
        assert shape is not None, f"{self._INDEX} not found on games"
        unique, partial = shape
        assert unique == 1, "index must be UNIQUE"
        assert partial == 1, "index must be PARTIAL"
        assert cols == ["game_stream_id"]
        assert sql_row is not None
        assert "game_stream_id IS NOT NULL" in sql_row[0]

    def test_duplicate_non_null_stream_id_rejected(self, fresh_db: Path) -> None:
        """AC-1: a second games row with the same non-null game_stream_id (the
        race-created duplicate of one real game) is rejected."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        try:
            t1, t2 = self._seed_game_parents(conn)
            self._insert_game(conn, "g1", t1, t2, "stream-A")
            conn.commit()
            with pytest.raises(sqlite3.IntegrityError):
                self._insert_game(conn, "g2", t1, t2, "stream-A")
        finally:
            conn.close()

    def test_doubleheader_not_rejected(self, fresh_db: Path) -> None:
        """AC-2: two distinct games -- same date + same team pair but DIFFERENT
        game_stream_id -- both persist (the backstop does NOT reject a real
        doubleheader)."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        try:
            t1, t2 = self._seed_game_parents(conn)
            self._insert_game(conn, "g1", t1, t2, "stream-A")
            self._insert_game(conn, "g2", t1, t2, "stream-B")  # 2nd game of DH
            conn.commit()
            n = conn.execute(
                "SELECT COUNT(*) FROM games WHERE game_date='2026-05-01' "
                "AND home_team_id=? AND away_team_id=?;",
                (t1, t2),
            ).fetchone()[0]
        finally:
            conn.close()
        assert n == 2

    def test_null_stream_id_passthrough(self, fresh_db: Path) -> None:
        """AC-3: rows with NULL game_stream_id are not indexed -> multiple such
        rows on the same date+pair are allowed; the partial index does not apply
        and the existing SELECT-then-INSERT dedup path still governs them."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        try:
            t1, t2 = self._seed_game_parents(conn)
            self._insert_game(conn, "n1", t1, t2, None)
            self._insert_game(conn, "n2", t1, t2, None)  # same date+pair, NULL stream
            conn.commit()
            n = conn.execute(
                "SELECT COUNT(*) FROM games WHERE game_stream_id IS NULL;"
            ).fetchone()[0]
        finally:
            conn.close()
        assert n == 2

    def test_migration_idempotent_second_run(self, fresh_db: Path) -> None:
        """AC-1: a second run_migrations does not error or duplicate the index."""
        run_migrations(db_path=fresh_db)
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        try:
            names = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name=?;",
                    (self._INDEX,),
                )
            ]
        finally:
            conn.close()
        assert names.count(self._INDEX) == 1


class TestMigration011DropSeasonAggregates:
    """E-259-03 migration 011: drop the season-aggregate tables with a
    refuse-on-member-row preflight.

    Clean input (zero ``full``/``supplemented`` rows) -> both tables dropped and
    the migration recorded. Member-row input -> REFUSED: the migration raises,
    BOTH tables stay intact, and it is NOT recorded (so a corrected DB can re-run
    it later). Uses ``apply_migration`` directly to run 011 in isolation after
    building the pre-011 schema, since ``run_migrations`` would apply 011 too.
    """

    _FILENAME = "011_drop_season_aggregate_tables.sql"
    _SEASON_TABLES = {"player_season_batting", "player_season_pitching"}
    _MIGRATIONS_DDL = (
        "CREATE TABLE IF NOT EXISTS _migrations ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "filename TEXT NOT NULL UNIQUE, "
        "applied_at TEXT NOT NULL DEFAULT (datetime('now')));"
    )

    def _apply_through_010(self, db_path: Path) -> sqlite3.Connection:
        """Apply every migration BEFORE 011 to a fresh DB; return an open conn."""
        conn = sqlite3.connect(str(db_path))
        conn.executescript("PRAGMA foreign_keys=ON;\n" + self._MIGRATIONS_DDL)
        conn.commit()
        for f in collect_migration_files():
            if f.name < self._FILENAME:
                apply_migration(conn, f)
        return conn

    def _mig_011(self) -> Path:
        return next(
            f for f in collect_migration_files() if f.name == self._FILENAME
        )

    def _present_season_tables(self, conn: sqlite3.Connection) -> set[str]:
        return {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name IN ('player_season_batting', 'player_season_pitching')"
            ).fetchall()
        }

    def test_clean_input_drops_tables_and_records(self, fresh_db: Path) -> None:
        """AC-1: zero member rows -> both tables dropped, migration recorded."""
        conn = self._apply_through_010(fresh_db)
        try:
            assert self._present_season_tables(conn) == self._SEASON_TABLES
            apply_migration(conn, self._mig_011())
            assert self._present_season_tables(conn) == set(), "tables not dropped"
            assert self._FILENAME in get_applied_migrations(conn)
        finally:
            conn.close()

    def test_member_row_refuses_and_preserves(self, fresh_db: Path) -> None:
        """AC-2/AC-3: a member row -> REFUSED (raises), both tables intact, and
        the migration is NOT recorded so a corrected run can proceed later."""
        conn = self._apply_through_010(fresh_db)
        try:
            conn.execute(
                "INSERT INTO seasons (season_id, name, year) VALUES ('2026', '2026', 2026)"
            )
            conn.execute(
                "INSERT INTO teams (id, name, membership_type) VALUES (1, 'T', 'member')"
            )
            conn.execute(
                "INSERT INTO players (player_id, first_name, last_name) VALUES ('p1', 'A', 'B')"
            )
            # A member (full) row -- non-re-derivable; the preflight must refuse.
            conn.execute(
                "INSERT INTO player_season_pitching "
                "(player_id, team_id, season_id, stat_completeness) "
                "VALUES ('p1', 1, '2026', 'full')"
            )
            conn.commit()

            with pytest.raises(sqlite3.Error, match="REFUSED"):
                apply_migration(conn, self._mig_011())

            # Both tables intact and the migration was NOT recorded.
            assert self._present_season_tables(conn) == self._SEASON_TABLES
            assert self._FILENAME not in get_applied_migrations(conn)
        finally:
            conn.close()

    def test_member_row_in_batting_also_refuses(self, fresh_db: Path) -> None:
        """AC-2: a member row in player_season_batting (the other table) also
        refuses and names that table in the message."""
        conn = self._apply_through_010(fresh_db)
        try:
            conn.execute(
                "INSERT INTO seasons (season_id, name, year) VALUES ('2026', '2026', 2026)"
            )
            conn.execute(
                "INSERT INTO teams (id, name, membership_type) VALUES (1, 'T', 'member')"
            )
            conn.execute(
                "INSERT INTO players (player_id, first_name, last_name) VALUES ('p1', 'A', 'B')"
            )
            conn.execute(
                "INSERT INTO player_season_batting "
                "(player_id, team_id, season_id, stat_completeness) "
                "VALUES ('p1', 1, '2026', 'supplemented')"
            )
            conn.commit()

            with pytest.raises(sqlite3.Error, match="player_season_batting"):
                apply_migration(conn, self._mig_011())
            assert self._present_season_tables(conn) == self._SEASON_TABLES
            assert self._FILENAME not in get_applied_migrations(conn)
        finally:
            conn.close()


class TestTeamsInningsPerGameMigration:
    """Verify migration 012_teams_innings_per_game.sql (E-264-01, TN-2).

    The migration adds one nullable INTEGER column to teams. NULL is
    load-bearing provenance (never fetched -> ERA assumed on the 7-inning
    fallback), so the column MUST stay nullable with no DEFAULT and no NOT NULL.
    """

    def test_innings_per_game_column_exists(self, fresh_db: Path) -> None:
        """After migrations, teams has an innings_per_game column."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        columns = {row[1] for row in conn.execute("PRAGMA table_info(teams);")}
        conn.close()
        assert "innings_per_game" in columns, (
            "innings_per_game column not found on teams after migration 012"
        )

    def test_column_is_nullable_integer_no_default(self, fresh_db: Path) -> None:
        """The column is INTEGER, nullable, with no DEFAULT (TN-2, AC-2).

        A DEFAULT or NOT NULL here would collapse the fetched-vs-assumed
        distinction the display layer depends on, so it is guarded explicitly.
        """
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        # table_info: (cid, name, type, notnull, dflt_value, pk)
        info = {
            row[1]: row
            for row in conn.execute("PRAGMA table_info(teams);").fetchall()
        }
        conn.close()
        assert "innings_per_game" in info, "innings_per_game not found"
        _cid, _name, col_type, notnull, dflt, _pk = info["innings_per_game"]
        assert col_type == "INTEGER", (
            f"innings_per_game type is {col_type!r}, want INTEGER"
        )
        assert notnull == 0, "innings_per_game is NOT NULL; should be nullable"
        assert dflt is None, f"innings_per_game has a DEFAULT {dflt!r}; want none"

    def test_existing_rows_read_back_null(self, fresh_db: Path) -> None:
        """A team inserted without the column reads back NULL (every pre-existing
        row is NULL after the ALTER)."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(
            "INSERT INTO teams (name, membership_type, source, is_active) "
            "VALUES ('No-Basis Team', 'tracked', 'manual', 1);"
        )
        conn.commit()
        value = conn.execute(
            "SELECT innings_per_game FROM teams WHERE name = 'No-Basis Team';"
        ).fetchone()[0]
        conn.close()
        assert value is None, "an omitted innings_per_game must read back NULL"

    def test_column_round_trips_integer(self, fresh_db: Path) -> None:
        """The column accepts and reads back an explicit integer basis."""
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(
            "INSERT INTO teams (name, membership_type, source, is_active, "
            "innings_per_game) VALUES ('Basis Team', 'tracked', 'manual', 1, 6);"
        )
        conn.commit()
        value = conn.execute(
            "SELECT innings_per_game FROM teams WHERE name = 'Basis Team';"
        ).fetchone()[0]
        conn.close()
        assert value == 6, f"integer basis round-trip mismatch: {value}"

    def test_migration_idempotent_second_run(self, fresh_db: Path) -> None:
        """A second run does not error or duplicate the column."""
        run_migrations(db_path=fresh_db)
        run_migrations(db_path=fresh_db)
        conn = sqlite3.connect(str(fresh_db))
        cols = [row[1] for row in conn.execute("PRAGMA table_info(teams);")]
        conn.close()
        assert cols.count("innings_per_game") == 1, (
            f"innings_per_game not present exactly once: {cols}"
        )

