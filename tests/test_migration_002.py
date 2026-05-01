"""Tests for migration 002 -- add ``our_team_id`` column to ``reports`` (E-228-01).

Covers AC-1 / AC-T1: column exists with the expected type, nullability, and
foreign-key target; existing rows survive the migration; and the migration is
idempotent via the ``_migrations`` tracking table.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from migrations.apply_migrations import (
    _MIGRATIONS_DIR,
    apply_migration,
    collect_migration_files,
    get_applied_migrations,
    run_migrations,
)


_MIGRATION_FILE = _MIGRATIONS_DIR / "002_add_our_team_id_to_reports.sql"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _column_info(
    conn: sqlite3.Connection, table: str
) -> dict[str, tuple[str, int, int]]:
    """Return ``{col_name: (type, notnull, pk)}`` for ``PRAGMA table_info``."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1]: (row[2], row[3], row[5]) for row in rows}


def _foreign_keys(
    conn: sqlite3.Connection, table: str
) -> list[tuple[str, str, str]]:
    """Return ``(from_col, ref_table, to_col)`` tuples for ``PRAGMA foreign_key_list``."""
    rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    # row layout: (id, seq, table, from, to, on_update, on_delete, match)
    return [(row[3], row[2], row[4]) for row in rows]


# ---------------------------------------------------------------------------
# AC-1 / AC-T1(a): clean DB migration succeeds and adds the expected column
# ---------------------------------------------------------------------------


class TestCleanDbMigration:
    """Migration 002 applies cleanly to a fresh DB."""

    def test_migration_file_exists(self):
        """The migration file is present in the migrations directory."""
        assert _MIGRATION_FILE.exists(), (
            f"Expected migration file at {_MIGRATION_FILE}"
        )

    def test_clean_db_migration_succeeds(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        run_migrations(db_path=db_path)

        conn = sqlite3.connect(str(db_path))
        try:
            applied = get_applied_migrations(conn)
            assert "002_add_our_team_id_to_reports.sql" in applied
        finally:
            conn.close()

    def test_column_type_nullability_and_fk(self, tmp_path: Path):
        """AC-T1: type, nullability, AND FK target are correct."""
        db_path = tmp_path / "test.db"
        run_migrations(db_path=db_path)

        conn = sqlite3.connect(str(db_path))
        try:
            cols = _column_info(conn, "reports")

            assert "our_team_id" in cols, (
                f"our_team_id column missing from reports; columns={list(cols)}"
            )
            col_type, notnull, pk = cols["our_team_id"]

            # Type must be INTEGER
            assert col_type.upper() == "INTEGER", (
                f"our_team_id should be INTEGER, got {col_type!r}"
            )
            # Must be nullable (notnull flag is 0)
            assert notnull == 0, (
                "our_team_id must be nullable so existing reports stay valid"
            )
            # Must NOT be a primary key
            assert pk == 0, "our_team_id must not be a primary key"

            # FK target must be teams(id)
            fks = _foreign_keys(conn, "reports")
            our_team_fks = [fk for fk in fks if fk[0] == "our_team_id"]
            assert len(our_team_fks) == 1, (
                f"Expected exactly one FK on our_team_id; got {our_team_fks}"
            )
            from_col, ref_table, to_col = our_team_fks[0]
            assert ref_table == "teams"
            assert to_col == "id"
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# AC-T1(b): DB with existing reports rows preserves all rows after migration
# ---------------------------------------------------------------------------


class TestExistingRowsPreserved:
    """Migrating a DB that already has reports rows preserves them with NULL."""

    def test_existing_rows_get_null_our_team_id(self, tmp_path: Path):
        db_path = tmp_path / "test.db"

        # Apply ONLY migration 001 (initial schema) so we can simulate a
        # pre-002 database with existing reports rows.
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.commit()

            # Bootstrap _migrations table the same way run_migrations does.
            from migrations.apply_migrations import _CREATE_MIGRATIONS_TABLE
            conn.executescript(
                "PRAGMA foreign_keys=ON;\n" + _CREATE_MIGRATIONS_TABLE
            )
            conn.commit()

            files = collect_migration_files()
            initial = next(
                f for f in files if f.name == "001_initial_schema.sql"
            )
            apply_migration(conn, initial)

            # Insert N=3 reports rows on the pre-002 schema
            conn.execute(
                "INSERT INTO teams (name, membership_type) "
                "VALUES ('Test', 'tracked')"
            )
            team_id = conn.execute(
                "SELECT id FROM teams WHERE name = 'Test'"
            ).fetchone()[0]
            for i in range(3):
                conn.execute(
                    "INSERT INTO reports "
                    "(slug, team_id, title, status, generated_at, expires_at) "
                    "VALUES (?, ?, 'r', 'ready', ?, ?)",
                    (f"slug-{i}", team_id, _utcnow_iso(), _utcnow_iso()),
                )
            conn.commit()
        finally:
            conn.close()

        # Now run the full migration set -- should apply 002 without error
        run_migrations(db_path=db_path)

        conn = sqlite3.connect(str(db_path))
        try:
            # All 3 rows still exist
            count = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
            assert count == 3, f"Expected 3 rows preserved, got {count}"

            # All 3 rows have our_team_id IS NULL
            null_count = conn.execute(
                "SELECT COUNT(*) FROM reports WHERE our_team_id IS NULL"
            ).fetchone()[0]
            assert null_count == 3, (
                f"Expected all 3 existing rows to have NULL our_team_id; "
                f"got {null_count}"
            )
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# AC-T1(c): idempotency -- re-running run_migrations is a no-op
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Re-running run_migrations does not re-apply 002."""

    def test_re_running_is_a_noop(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        run_migrations(db_path=db_path)

        # Capture state after first run
        conn = sqlite3.connect(str(db_path))
        try:
            applied_first = get_applied_migrations(conn)
            assert "002_add_our_team_id_to_reports.sql" in applied_first
        finally:
            conn.close()

        # Run again -- must succeed without raising and without duplicating rows
        run_migrations(db_path=db_path)

        conn = sqlite3.connect(str(db_path))
        try:
            applied_second = get_applied_migrations(conn)
            # Same set of filenames; no duplicates introduced.
            assert applied_second == applied_first

            # _migrations table records each migration file exactly once.
            count = conn.execute(
                "SELECT COUNT(*) FROM _migrations "
                "WHERE filename = '002_add_our_team_id_to_reports.sql'"
            ).fetchone()[0]
            assert count == 1, (
                f"Migration 002 recorded {count} times; expected 1 (idempotent)."
            )
        finally:
            conn.close()
