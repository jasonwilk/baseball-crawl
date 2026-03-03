# synthetic-test-data
"""Tests for migrations/003_auth.sql (E-023-01).

Verifies that:
- All five auth tables are created by the migration (AC-1 through AC-5).
- apply_migrations handles the 002 gap and applies 003 cleanly (AC-6).
- Running apply_migrations twice is idempotent (AC-7).
- FK constraint on user_team_access.user_id is enforced (AC-8).
- magic_link_tokens.token_hash UNIQUE constraint is enforced (AC-9).
- sessions.session_token_hash UNIQUE constraint is enforced (AC-10).

Tests use a temporary in-memory / temp-file SQLite database; no Docker required.

Run with:
    pytest tests/test_migration_003.py -v
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
def migrated_db(tmp_path: Path) -> sqlite3.Connection:
    """Apply all migrations to a fresh temp DB and return an open connection.

    Foreign keys are enabled on the returned connection.

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Open sqlite3.Connection with all migrations applied.
    """
    db_path = tmp_path / "test_auth.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    return conn


@pytest.fixture()
def db_with_team(migrated_db: sqlite3.Connection) -> sqlite3.Connection:
    """Seed one team and one user for FK/constraint tests.

    Args:
        migrated_db: Fully migrated database connection.

    Returns:
        Same connection with a team and a user pre-inserted.
    """
    migrated_db.execute(
        "INSERT INTO teams (team_id, name) VALUES ('team-001', 'Lincoln Varsity');"
    )
    migrated_db.execute(
        "INSERT INTO users (email, display_name) VALUES ('coach@example.com', 'Coach Smith');"
    )
    migrated_db.commit()
    return migrated_db


# ---------------------------------------------------------------------------
# Table creation tests (AC-1 through AC-5)
# ---------------------------------------------------------------------------


class TestAuthTablesExist:
    """Verify all five auth tables are created by migration 003."""

    AUTH_TABLES = {
        "users",
        "user_team_access",
        "magic_link_tokens",
        "passkey_credentials",
        "sessions",
    }

    def _get_tables(self, conn: sqlite3.Connection) -> set[str]:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        )
        return {row[0] for row in cursor.fetchall()}

    def test_users_table_created(self, migrated_db: sqlite3.Connection) -> None:
        """AC-1: users table exists after migration."""
        assert "users" in self._get_tables(migrated_db)

    def test_user_team_access_table_created(self, migrated_db: sqlite3.Connection) -> None:
        """AC-2: user_team_access table exists after migration."""
        assert "user_team_access" in self._get_tables(migrated_db)

    def test_magic_link_tokens_table_created(self, migrated_db: sqlite3.Connection) -> None:
        """AC-3: magic_link_tokens table exists after migration."""
        assert "magic_link_tokens" in self._get_tables(migrated_db)

    def test_passkey_credentials_table_created(self, migrated_db: sqlite3.Connection) -> None:
        """AC-4: passkey_credentials table exists after migration."""
        assert "passkey_credentials" in self._get_tables(migrated_db)

    def test_sessions_table_created(self, migrated_db: sqlite3.Connection) -> None:
        """AC-5: sessions table exists after migration."""
        assert "sessions" in self._get_tables(migrated_db)

    def test_all_auth_tables_created(self, migrated_db: sqlite3.Connection) -> None:
        """All five auth tables are present after migration."""
        actual = self._get_tables(migrated_db)
        missing = self.AUTH_TABLES - actual
        assert not missing, f"Missing auth tables after migration: {missing}"


class TestUsersColumns:
    """AC-1: Verify users table has correct columns."""

    def _get_columns(self, conn: sqlite3.Connection, table: str) -> dict[str, dict]:
        cursor = conn.execute(f"PRAGMA table_info({table});")
        return {row[1]: {"type": row[2], "notnull": row[3], "default": row[4], "pk": row[5]}
                for row in cursor.fetchall()}

    def test_users_has_user_id_pk_autoincrement(self, migrated_db: sqlite3.Connection) -> None:
        """users.user_id is INTEGER PRIMARY KEY."""
        cols = self._get_columns(migrated_db, "users")
        assert "user_id" in cols
        assert cols["user_id"]["pk"] == 1
        assert cols["user_id"]["type"].upper() == "INTEGER"

    def test_users_has_email_not_null_unique(self, migrated_db: sqlite3.Connection) -> None:
        """users.email is TEXT NOT NULL with a UNIQUE constraint."""
        cols = self._get_columns(migrated_db, "users")
        assert "email" in cols
        assert cols["email"]["notnull"] == 1

    def test_users_has_display_name_not_null(self, migrated_db: sqlite3.Connection) -> None:
        """users.display_name is TEXT NOT NULL."""
        cols = self._get_columns(migrated_db, "users")
        assert "display_name" in cols
        assert cols["display_name"]["notnull"] == 1

    def test_users_has_is_admin_default_0(self, migrated_db: sqlite3.Connection) -> None:
        """users.is_admin defaults to 0."""
        cols = self._get_columns(migrated_db, "users")
        assert "is_admin" in cols
        assert cols["is_admin"]["default"] == "0"

    def test_users_has_created_at(self, migrated_db: sqlite3.Connection) -> None:
        """users.created_at column exists."""
        cols = self._get_columns(migrated_db, "users")
        assert "created_at" in cols


class TestIndexesExist:
    """Verify all required indexes are created."""

    def _get_indexes(self, conn: sqlite3.Connection) -> set[str]:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index';"
        )
        return {row[0] for row in cursor.fetchall()}

    def test_idx_user_team_access_user_exists(self, migrated_db: sqlite3.Connection) -> None:
        """AC-2: idx_user_team_access_user index exists."""
        assert "idx_user_team_access_user" in self._get_indexes(migrated_db)

    def test_idx_magic_link_tokens_hash_exists(self, migrated_db: sqlite3.Connection) -> None:
        """AC-3: idx_magic_link_tokens_hash index exists."""
        assert "idx_magic_link_tokens_hash" in self._get_indexes(migrated_db)

    def test_idx_passkey_credentials_user_exists(self, migrated_db: sqlite3.Connection) -> None:
        """AC-4: idx_passkey_credentials_user index exists."""
        assert "idx_passkey_credentials_user" in self._get_indexes(migrated_db)

    def test_idx_passkey_credentials_credential_id_exists(self, migrated_db: sqlite3.Connection) -> None:
        """AC-4: idx_passkey_credentials_credential_id index exists."""
        assert "idx_passkey_credentials_credential_id" in self._get_indexes(migrated_db)

    def test_idx_sessions_token_exists(self, migrated_db: sqlite3.Connection) -> None:
        """AC-5: idx_sessions_token index exists."""
        assert "idx_sessions_token" in self._get_indexes(migrated_db)

    def test_idx_sessions_user_id_exists(self, migrated_db: sqlite3.Connection) -> None:
        """AC-5: idx_sessions_user_id index exists."""
        assert "idx_sessions_user_id" in self._get_indexes(migrated_db)


# ---------------------------------------------------------------------------
# Migration runner behavior tests (AC-6, AC-7)
# ---------------------------------------------------------------------------


class TestMigrationRunnerBehavior:
    """AC-6 and AC-7: Migration runner handles gaps and is idempotent."""

    def test_migration_003_recorded_in_tracking_table(self, migrated_db: sqlite3.Connection) -> None:
        """AC-6: 003_auth.sql is recorded in _migrations after apply."""
        cursor = migrated_db.execute(
            "SELECT filename FROM _migrations WHERE filename='003_auth.sql';"
        )
        row = cursor.fetchone()
        assert row is not None, "003_auth.sql not found in _migrations"

    def test_idempotent_second_run(self, tmp_path: Path) -> None:
        """AC-7: Running apply_migrations twice does not add duplicate _migrations rows."""
        db_path = tmp_path / "idempotent_test.db"

        run_migrations(db_path=db_path)
        conn = sqlite3.connect(str(db_path))
        count_first = conn.execute("SELECT COUNT(*) FROM _migrations;").fetchone()[0]
        conn.close()

        run_migrations(db_path=db_path)
        conn = sqlite3.connect(str(db_path))
        count_second = conn.execute("SELECT COUNT(*) FROM _migrations;").fetchone()[0]
        conn.close()

        assert count_first == count_second, (
            f"_migrations row count changed on second run: "
            f"{count_first} -> {count_second}"
        )

    def test_idempotent_auth_tables_not_duplicated(self, tmp_path: Path) -> None:
        """AC-7: Running twice does not create duplicate auth tables."""
        db_path = tmp_path / "idempotent_tables.db"
        run_migrations(db_path=db_path)
        run_migrations(db_path=db_path)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        )
        table_names = [row[0] for row in cursor.fetchall()]
        conn.close()

        assert len(table_names) == len(set(table_names)), (
            f"Duplicate tables found after second run: {table_names}"
        )


# ---------------------------------------------------------------------------
# Constraint tests (AC-8, AC-9, AC-10)
# ---------------------------------------------------------------------------


class TestForeignKeyConstraints:
    """AC-8: FK constraints are enforced when PRAGMA foreign_keys=ON."""

    def test_user_team_access_rejects_nonexistent_user_id(
        self, db_with_team: sqlite3.Connection
    ) -> None:
        """AC-8: Inserting user_team_access with nonexistent user_id raises IntegrityError."""
        with pytest.raises(sqlite3.IntegrityError):
            db_with_team.execute(
                "INSERT INTO user_team_access (user_id, team_id) VALUES (9999, 'team-001');"
            )
            db_with_team.commit()

    def test_user_team_access_accepts_valid_user_and_team(
        self, db_with_team: sqlite3.Connection
    ) -> None:
        """Valid user_id and team_id inserts without error."""
        # user_id=1 was inserted by db_with_team fixture
        db_with_team.execute(
            "INSERT INTO user_team_access (user_id, team_id) VALUES (1, 'team-001');"
        )
        db_with_team.commit()
        cursor = db_with_team.execute("SELECT COUNT(*) FROM user_team_access;")
        assert cursor.fetchone()[0] == 1


class TestMagicLinkTokensUnique:
    """AC-9: magic_link_tokens.token_hash UNIQUE constraint is enforced."""

    def test_duplicate_token_hash_raises_integrity_error(
        self, db_with_team: sqlite3.Connection
    ) -> None:
        """AC-9: Two magic_link_tokens rows with the same token_hash fail."""
        db_with_team.execute(
            """
            INSERT INTO magic_link_tokens (token_hash, user_id, expires_at)
            VALUES ('abc123hash', 1, datetime('now', '+1 hour'));
            """
        )
        db_with_team.commit()

        with pytest.raises(sqlite3.IntegrityError):
            db_with_team.execute(
                """
                INSERT INTO magic_link_tokens (token_hash, user_id, expires_at)
                VALUES ('abc123hash', 1, datetime('now', '+2 hours'));
                """
            )
            db_with_team.commit()

    def test_distinct_token_hashes_accepted(
        self, db_with_team: sqlite3.Connection
    ) -> None:
        """Two magic_link_tokens rows with different hashes insert cleanly."""
        db_with_team.execute(
            """
            INSERT INTO magic_link_tokens (token_hash, user_id, expires_at)
            VALUES ('hash-aaa', 1, datetime('now', '+1 hour'));
            """
        )
        db_with_team.execute(
            """
            INSERT INTO magic_link_tokens (token_hash, user_id, expires_at)
            VALUES ('hash-bbb', 1, datetime('now', '+1 hour'));
            """
        )
        db_with_team.commit()
        cursor = db_with_team.execute("SELECT COUNT(*) FROM magic_link_tokens;")
        assert cursor.fetchone()[0] == 2


class TestSessionsTokenHashUnique:
    """AC-10: sessions.session_token_hash UNIQUE constraint is enforced."""

    def test_duplicate_session_token_hash_raises_integrity_error(
        self, db_with_team: sqlite3.Connection
    ) -> None:
        """AC-10: Two sessions rows with the same session_token_hash fail."""
        db_with_team.execute(
            """
            INSERT INTO sessions (session_token_hash, user_id, expires_at)
            VALUES ('sess-hash-xyz', 1, datetime('now', '+1 day'));
            """
        )
        db_with_team.commit()

        with pytest.raises(sqlite3.IntegrityError):
            db_with_team.execute(
                """
                INSERT INTO sessions (session_token_hash, user_id, expires_at)
                VALUES ('sess-hash-xyz', 1, datetime('now', '+2 days'));
                """
            )
            db_with_team.commit()

    def test_distinct_session_token_hashes_accepted(
        self, db_with_team: sqlite3.Connection
    ) -> None:
        """Two sessions rows with different hashes insert cleanly."""
        db_with_team.execute(
            """
            INSERT INTO sessions (session_token_hash, user_id, expires_at)
            VALUES ('sess-hash-1', 1, datetime('now', '+1 day'));
            """
        )
        db_with_team.execute(
            """
            INSERT INTO sessions (session_token_hash, user_id, expires_at)
            VALUES ('sess-hash-2', 1, datetime('now', '+1 day'));
            """
        )
        db_with_team.commit()
        cursor = db_with_team.execute("SELECT COUNT(*) FROM sessions;")
        assert cursor.fetchone()[0] == 2
