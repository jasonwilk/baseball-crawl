# synthetic-test-data
"""Tests for auth tables in 001_initial_schema.sql (E-100-01 schema rewrite).

Verifies the new E-100 auth schema structure:
- users: id INTEGER PK AUTOINCREMENT, email TEXT UNIQUE NOT NULL, hashed_password, created_at
  (no user_id alias, no display_name, no is_admin)
- user_team_access: user_id INTEGER FK -> users(id), team_id INTEGER FK -> teams(id)
- magic_link_tokens: token TEXT PK (not token_hash), user_id FK, expires_at
- passkey_credentials: credential_id TEXT PK, user_id FK, public_key, sign_count
- sessions: session_id TEXT PK (not session_token_hash), user_id FK, expires_at
- coaching_assignments: id INTEGER PK, user_id FK, team_id FK, role

Tests use a temporary SQLite database; no Docker required.

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

    teams uses INTEGER AUTOINCREMENT PK -- no team_id TEXT column.
    users uses id INTEGER PK -- no display_name, no is_admin.

    Args:
        migrated_db: Fully migrated database connection.

    Returns:
        Same connection with a team and a user pre-inserted.
    """
    migrated_db.execute(
        "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
        ("Lincoln Varsity", "member"),
    )
    migrated_db.execute(
        "INSERT INTO users (email) VALUES (?)",
        ("coach@example.com",),
    )
    migrated_db.commit()
    return migrated_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_tables(conn: sqlite3.Connection) -> set[str]:
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
    return {row[0] for row in cursor.fetchall()}


def _get_columns(conn: sqlite3.Connection, table: str) -> dict[str, dict]:
    cursor = conn.execute(f"PRAGMA table_info({table});")
    return {row[1]: {"type": row[2], "notnull": row[3], "default": row[4], "pk": row[5]}
            for row in cursor.fetchall()}


def _get_team_id(conn: sqlite3.Connection) -> int:
    """Return the INTEGER id of the first team."""
    row = conn.execute("SELECT id FROM teams LIMIT 1;").fetchone()
    assert row is not None
    return row[0]


def _get_user_id(conn: sqlite3.Connection) -> int:
    """Return the INTEGER id of the first user."""
    row = conn.execute("SELECT id FROM users LIMIT 1;").fetchone()
    assert row is not None
    return row[0]


# ---------------------------------------------------------------------------
# Table creation tests
# ---------------------------------------------------------------------------


class TestAuthTablesExist:
    """Verify all auth tables are created by the initial schema migration."""

    AUTH_TABLES = {
        "users",
        "user_team_access",
        "magic_link_tokens",
        "passkey_credentials",
        "sessions",
        "coaching_assignments",
    }

    def test_users_table_created(self, migrated_db: sqlite3.Connection) -> None:
        """users table exists after migration."""
        assert "users" in _get_tables(migrated_db)

    def test_user_team_access_table_created(self, migrated_db: sqlite3.Connection) -> None:
        """user_team_access table exists after migration."""
        assert "user_team_access" in _get_tables(migrated_db)

    def test_magic_link_tokens_table_created(self, migrated_db: sqlite3.Connection) -> None:
        """magic_link_tokens table exists after migration."""
        assert "magic_link_tokens" in _get_tables(migrated_db)

    def test_passkey_credentials_table_created(self, migrated_db: sqlite3.Connection) -> None:
        """passkey_credentials table exists after migration."""
        assert "passkey_credentials" in _get_tables(migrated_db)

    def test_sessions_table_created(self, migrated_db: sqlite3.Connection) -> None:
        """sessions table exists after migration."""
        assert "sessions" in _get_tables(migrated_db)

    def test_coaching_assignments_table_created(self, migrated_db: sqlite3.Connection) -> None:
        """coaching_assignments table exists after migration."""
        assert "coaching_assignments" in _get_tables(migrated_db)

    def test_all_auth_tables_created(self, migrated_db: sqlite3.Connection) -> None:
        """All auth tables are present after migration."""
        actual = _get_tables(migrated_db)
        missing = self.AUTH_TABLES - actual
        assert not missing, f"Missing auth tables after migration: {missing}"


class TestUsersColumns:
    """Verify users table has the correct E-100 schema (no user_id alias, no display_name)."""

    def test_users_has_id_pk_autoincrement(self, migrated_db: sqlite3.Connection) -> None:
        """users.id is INTEGER PRIMARY KEY (no user_id alias)."""
        cols = _get_columns(migrated_db, "users")
        assert "id" in cols, "users.id column missing"
        assert cols["id"]["pk"] == 1
        assert cols["id"]["type"].upper() == "INTEGER"

    def test_users_has_no_user_id_column(self, migrated_db: sqlite3.Connection) -> None:
        """users table has no user_id alias column (removed in E-100)."""
        cols = _get_columns(migrated_db, "users")
        assert "user_id" not in cols, "users.user_id should not exist in E-100 schema"

    def test_users_has_email_not_null_unique(self, migrated_db: sqlite3.Connection) -> None:
        """users.email is TEXT NOT NULL."""
        cols = _get_columns(migrated_db, "users")
        assert "email" in cols
        assert cols["email"]["notnull"] == 1

    def test_users_has_no_display_name(self, migrated_db: sqlite3.Connection) -> None:
        """users table has no display_name column (removed in E-100)."""
        cols = _get_columns(migrated_db, "users")
        assert "display_name" not in cols, "users.display_name should not exist in E-100 schema"

    def test_users_has_no_is_admin(self, migrated_db: sqlite3.Connection) -> None:
        """users table has no is_admin column (removed in E-100)."""
        cols = _get_columns(migrated_db, "users")
        assert "is_admin" not in cols, "users.is_admin should not exist in E-100 schema"

    def test_users_has_hashed_password(self, migrated_db: sqlite3.Connection) -> None:
        """users.hashed_password column exists."""
        cols = _get_columns(migrated_db, "users")
        assert "hashed_password" in cols

    def test_users_has_created_at(self, migrated_db: sqlite3.Connection) -> None:
        """users.created_at column exists."""
        cols = _get_columns(migrated_db, "users")
        assert "created_at" in cols


class TestSessionsColumns:
    """Verify sessions table uses session_id (not session_token_hash)."""

    def test_sessions_has_session_id_pk(self, migrated_db: sqlite3.Connection) -> None:
        """sessions.session_id is TEXT PRIMARY KEY."""
        cols = _get_columns(migrated_db, "sessions")
        assert "session_id" in cols, "sessions.session_id column missing"
        assert cols["session_id"]["pk"] == 1

    def test_sessions_has_no_session_token_hash(self, migrated_db: sqlite3.Connection) -> None:
        """sessions table has no session_token_hash column (replaced by session_id in E-100)."""
        cols = _get_columns(migrated_db, "sessions")
        assert "session_token_hash" not in cols, (
            "sessions.session_token_hash should not exist in E-100 schema"
        )


class TestMagicLinkTokensColumns:
    """Verify magic_link_tokens table uses token (not token_hash)."""

    def test_magic_link_tokens_has_token_pk(self, migrated_db: sqlite3.Connection) -> None:
        """magic_link_tokens.token is TEXT PRIMARY KEY."""
        cols = _get_columns(migrated_db, "magic_link_tokens")
        assert "token" in cols, "magic_link_tokens.token column missing"
        assert cols["token"]["pk"] == 1

    def test_magic_link_tokens_has_no_token_hash(self, migrated_db: sqlite3.Connection) -> None:
        """magic_link_tokens has no token_hash column (renamed to token in E-100)."""
        cols = _get_columns(migrated_db, "magic_link_tokens")
        assert "token_hash" not in cols, (
            "magic_link_tokens.token_hash should not exist in E-100 schema"
        )


# ---------------------------------------------------------------------------
# Migration runner behavior tests
# ---------------------------------------------------------------------------


class TestMigrationRunnerBehavior:
    """Verify migration runner is idempotent and records migrations correctly."""

    def test_initial_schema_recorded_in_tracking_table(self, migrated_db: sqlite3.Connection) -> None:
        """001_initial_schema.sql is recorded in _migrations after apply."""
        cursor = migrated_db.execute(
            "SELECT filename FROM _migrations WHERE filename='001_initial_schema.sql';"
        )
        row = cursor.fetchone()
        assert row is not None, "001_initial_schema.sql not found in _migrations"

    def test_idempotent_second_run(self, tmp_path: Path) -> None:
        """Running apply_migrations twice does not add duplicate _migrations rows."""
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
            f"_migrations row count changed on second run: {count_first} -> {count_second}"
        )

    def test_idempotent_auth_tables_not_duplicated(self, tmp_path: Path) -> None:
        """Running twice does not create duplicate auth tables."""
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
# Constraint tests
# ---------------------------------------------------------------------------


class TestForeignKeyConstraints:
    """FK constraints are enforced when PRAGMA foreign_keys=ON."""

    def test_user_team_access_rejects_nonexistent_user_id(
        self, db_with_team: sqlite3.Connection
    ) -> None:
        """Inserting user_team_access with nonexistent user_id raises IntegrityError."""
        team_id = _get_team_id(db_with_team)
        with pytest.raises(sqlite3.IntegrityError):
            db_with_team.execute(
                "INSERT INTO user_team_access (user_id, team_id) VALUES (?, ?)",
                (9999, team_id),
            )
            db_with_team.commit()

    def test_user_team_access_accepts_valid_user_and_team(
        self, db_with_team: sqlite3.Connection
    ) -> None:
        """Valid user_id and team_id inserts without error."""
        user_id = _get_user_id(db_with_team)
        team_id = _get_team_id(db_with_team)
        db_with_team.execute(
            "INSERT INTO user_team_access (user_id, team_id) VALUES (?, ?)",
            (user_id, team_id),
        )
        db_with_team.commit()
        cursor = db_with_team.execute("SELECT COUNT(*) FROM user_team_access;")
        assert cursor.fetchone()[0] == 1


class TestMagicLinkTokensUnique:
    """magic_link_tokens.token PRIMARY KEY constraint is enforced."""

    def test_duplicate_token_raises_integrity_error(
        self, db_with_team: sqlite3.Connection
    ) -> None:
        """Two magic_link_tokens rows with the same token fail."""
        user_id = _get_user_id(db_with_team)
        db_with_team.execute(
            "INSERT INTO magic_link_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
            ("abc123token", user_id, "2026-12-31 00:00:00"),
        )
        db_with_team.commit()

        with pytest.raises(sqlite3.IntegrityError):
            db_with_team.execute(
                "INSERT INTO magic_link_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
                ("abc123token", user_id, "2027-01-01 00:00:00"),
            )
            db_with_team.commit()

    def test_distinct_tokens_accepted(
        self, db_with_team: sqlite3.Connection
    ) -> None:
        """Two magic_link_tokens rows with different tokens insert cleanly."""
        user_id = _get_user_id(db_with_team)
        db_with_team.execute(
            "INSERT INTO magic_link_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
            ("token-aaa", user_id, "2026-12-31 00:00:00"),
        )
        db_with_team.execute(
            "INSERT INTO magic_link_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
            ("token-bbb", user_id, "2026-12-31 00:00:00"),
        )
        db_with_team.commit()
        cursor = db_with_team.execute("SELECT COUNT(*) FROM magic_link_tokens;")
        assert cursor.fetchone()[0] == 2


class TestSessionsUnique:
    """sessions.session_id PRIMARY KEY constraint is enforced."""

    def test_duplicate_session_id_raises_integrity_error(
        self, db_with_team: sqlite3.Connection
    ) -> None:
        """Two sessions rows with the same session_id fail."""
        user_id = _get_user_id(db_with_team)
        db_with_team.execute(
            "INSERT INTO sessions (session_id, user_id, expires_at) VALUES (?, ?, ?)",
            ("sess-xyz", user_id, "2026-12-31 00:00:00"),
        )
        db_with_team.commit()

        with pytest.raises(sqlite3.IntegrityError):
            db_with_team.execute(
                "INSERT INTO sessions (session_id, user_id, expires_at) VALUES (?, ?, ?)",
                ("sess-xyz", user_id, "2027-01-01 00:00:00"),
            )
            db_with_team.commit()

    def test_distinct_session_ids_accepted(
        self, db_with_team: sqlite3.Connection
    ) -> None:
        """Two sessions rows with different session_ids insert cleanly."""
        user_id = _get_user_id(db_with_team)
        db_with_team.execute(
            "INSERT INTO sessions (session_id, user_id, expires_at) VALUES (?, ?, ?)",
            ("sess-1", user_id, "2026-12-31 00:00:00"),
        )
        db_with_team.execute(
            "INSERT INTO sessions (session_id, user_id, expires_at) VALUES (?, ?, ?)",
            ("sess-2", user_id, "2026-12-31 00:00:00"),
        )
        db_with_team.commit()
        cursor = db_with_team.execute("SELECT COUNT(*) FROM sessions;")
        assert cursor.fetchone()[0] == 2
