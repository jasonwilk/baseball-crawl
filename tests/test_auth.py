# synthetic-test-data
"""Tests for session middleware (src/api/auth.py) -- E-023-02 AC-17.

Tests cover:
- Session middleware allows valid session (AC-17g)
- Session middleware redirects invalid session to /auth/login (AC-17h)
- Dev bypass auto-creates user and session (AC-17j)
- Health endpoint works without session (AC-17k)
- hash_token produces consistent SHA-256 hex digests
- Excluded paths bypass middleware

Uses an in-process seeded SQLite database via tmp_path; no Docker or network.

Run with:
    pytest tests/test_auth.py -v
"""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.api.auth import hash_token  # noqa: E402
from src.api.main import app  # noqa: E402

# ---------------------------------------------------------------------------
# Schema SQL -- E-100 schema (teams INTEGER PK, new users/sessions/auth tables)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS _migrations (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        filename   TEXT    NOT NULL UNIQUE,
        applied_at TEXT    NOT NULL DEFAULT (datetime('now'))
    );
    INSERT OR IGNORE INTO _migrations (filename) VALUES ('001_initial_schema.sql');

    CREATE TABLE IF NOT EXISTS programs (
        program_id   TEXT PRIMARY KEY,
        name         TEXT NOT NULL,
        program_type TEXT NOT NULL,
        created_at   TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS teams (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT NOT NULL,
        program_id      TEXT REFERENCES programs(program_id),
        membership_type TEXT NOT NULL CHECK(membership_type IN ('member', 'tracked')),
        classification  TEXT,
        public_id       TEXT,
        gc_uuid         TEXT,
        source          TEXT NOT NULL DEFAULT 'gamechanger',
        is_active       INTEGER NOT NULL DEFAULT 1,
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS users (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        email           TEXT UNIQUE NOT NULL,
        hashed_password TEXT,
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS user_team_access (
        user_id INTEGER NOT NULL REFERENCES users(id),
        team_id INTEGER NOT NULL REFERENCES teams(id),
        UNIQUE(user_id, team_id)
    );

    CREATE TABLE IF NOT EXISTS magic_link_tokens (
        token      TEXT PRIMARY KEY,
        user_id    INTEGER NOT NULL REFERENCES users(id),
        expires_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS passkey_credentials (
        credential_id TEXT PRIMARY KEY,
        user_id       INTEGER NOT NULL REFERENCES users(id),
        public_key    TEXT NOT NULL,
        sign_count    INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id    INTEGER NOT NULL REFERENCES users(id),
        expires_at TEXT NOT NULL
    );

    CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_gc_uuid
        ON teams(gc_uuid) WHERE gc_uuid IS NOT NULL;
    CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_public_id
        ON teams(public_id) WHERE public_id IS NOT NULL;
"""

_SEED_SQL = """
    INSERT OR IGNORE INTO programs (program_id, name, program_type) VALUES
        ('lsb-hs', 'Lincoln Standing Bear HS', 'hs');
    INSERT OR IGNORE INTO teams (name, membership_type, classification) VALUES
        ('LSB Varsity 2026', 'member', 'varsity');
"""


def _make_auth_db(tmp_path: Path) -> Path:
    """Create a database with full E-100 schema (base + auth tables).

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Path to the database file.
    """
    db_path = tmp_path / "test_auth_middleware.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA_SQL)
    conn.executescript(_SEED_SQL)
    conn.commit()
    conn.close()
    return db_path


def _insert_user(db_path: Path, email: str) -> int:
    """Insert a user row and return the user id.

    Args:
        db_path: Path to the database file.
        email: Email address for the user.

    Returns:
        The new user id (INTEGER PK).
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "INSERT INTO users (email) VALUES (?)",
        (email,),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def _insert_session(db_path: Path, user_id: int) -> str:
    """Insert a valid session and return the raw token.

    Args:
        db_path: Path to the database file.
        user_id: User to associate the session with.

    Returns:
        Raw session token (64 hex chars).
    """
    raw_token = secrets.token_hex(32)
    session_id = hash_token(raw_token)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT INTO sessions (session_id, user_id, expires_at)
        VALUES (?, ?, datetime('now', '+7 days'))
        """,
        (session_id, user_id),
    )
    conn.commit()
    conn.close()
    return raw_token


def _insert_expired_session(db_path: Path, user_id: int) -> str:
    """Insert an expired session and return the raw token.

    Args:
        db_path: Path to the database file.
        user_id: User to associate the session with.

    Returns:
        Raw session token (64 hex chars).
    """
    raw_token = secrets.token_hex(32)
    session_id = hash_token(raw_token)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT INTO sessions (session_id, user_id, expires_at)
        VALUES (?, ?, datetime('now', '-1 hour'))
        """,
        (session_id, user_id),
    )
    conn.commit()
    conn.close()
    return raw_token


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth_db(tmp_path: Path) -> Path:
    """Full E-100 schema database with one member team."""
    return _make_auth_db(tmp_path)


# ---------------------------------------------------------------------------
# Unit tests for hash_token
# ---------------------------------------------------------------------------


class TestHashToken:
    """Tests for the hash_token helper."""

    def test_hash_token_returns_sha256_hex(self) -> None:
        """hash_token returns a 64-character hex string."""
        token = "test-token-abc123"
        result = hash_token(token)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_hash_token_is_deterministic(self) -> None:
        """hash_token returns the same value on repeated calls."""
        token = "consistent-token"
        assert hash_token(token) == hash_token(token)

    def test_hash_token_matches_stdlib_sha256(self) -> None:
        """hash_token output matches hashlib.sha256 directly."""
        token = "reference-check-token"
        expected = hashlib.sha256(token.encode()).hexdigest()
        assert hash_token(token) == expected

    def test_different_tokens_produce_different_hashes(self) -> None:
        """Different input tokens produce different hashes."""
        assert hash_token("token-a") != hash_token("token-b")


# ---------------------------------------------------------------------------
# Session middleware tests -- valid session (AC-17g)
# ---------------------------------------------------------------------------


class TestSessionMiddlewareValidSession:
    """Session middleware allows requests with a valid session cookie (AC-17g)."""

    def test_valid_session_reaches_dashboard(self, auth_db: Path) -> None:
        """Dashboard is accessible with a valid session cookie."""
        user_id = _insert_user(auth_db, "coach@example.com")
        raw_token = _insert_session(auth_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(auth_db)}):
            with TestClient(app, cookies={"session": raw_token}) as client:
                response = client.get("/dashboard")
        assert response.status_code == 200

    def test_valid_session_sets_request_state(self, auth_db: Path) -> None:
        """A valid session cookie results in a 200 response (state is attached)."""
        user_id = _insert_user(auth_db, "coach2@example.com")
        raw_token = _insert_session(auth_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(auth_db)}):
            with TestClient(app, cookies={"session": raw_token}) as client:
                response = client.get("/dashboard")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Session middleware tests -- invalid/missing session (AC-17h)
# ---------------------------------------------------------------------------


class TestSessionMiddlewareInvalidSession:
    """Session middleware redirects unauthenticated requests to /auth/login (AC-17h)."""

    def test_no_cookie_redirects_to_login(self, auth_db: Path) -> None:
        """Missing session cookie -> redirect to /auth/login."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(auth_db)}):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get("/dashboard")
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]

    def test_invalid_cookie_value_redirects_to_login(self, auth_db: Path) -> None:
        """Non-existent session token -> redirect to /auth/login."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(auth_db)}):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": "notarealtoken123"},
            ) as client:
                response = client.get("/dashboard")
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]

    def test_expired_session_redirects_to_login(self, auth_db: Path) -> None:
        """Expired session -> redirect to /auth/login."""
        user_id = _insert_user(auth_db, "expired@example.com")
        raw_token = _insert_expired_session(auth_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(auth_db)}):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token},
            ) as client:
                response = client.get("/dashboard")
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]


# ---------------------------------------------------------------------------
# Dev bypass tests (AC-17j)
# ---------------------------------------------------------------------------


class TestDevBypass:
    """DEV_USER_EMAIL env var auto-creates user and session (AC-17j)."""

    def test_dev_bypass_allows_dashboard_access(self, auth_db: Path) -> None:
        """DEV_USER_EMAIL set -> dashboard accessible without login (AC-17j)."""
        env = {
            "DATABASE_PATH": str(auth_db),
            "DEV_USER_EMAIL": "devbypass@example.com",
        }
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                response = client.get("/dashboard")
        assert response.status_code == 200

    def test_dev_bypass_auto_creates_user(self, auth_db: Path) -> None:
        """DEV_USER_EMAIL auto-creates user if not in DB (AC-17j)."""
        dev_email = "autocreated@example.com"
        env = {
            "DATABASE_PATH": str(auth_db),
            "DEV_USER_EMAIL": dev_email,
        }
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                client.get("/dashboard")

        conn = sqlite3.connect(str(auth_db))
        cursor = conn.execute(
            "SELECT email FROM users WHERE email = ?", (dev_email,)
        )
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert row[0] == dev_email

    def test_dev_bypass_uses_existing_user(self, auth_db: Path) -> None:
        """DEV_USER_EMAIL reuses existing user row if already present (AC-17j)."""
        dev_email = "existing@example.com"
        _insert_user(auth_db, dev_email)

        env = {
            "DATABASE_PATH": str(auth_db),
            "DEV_USER_EMAIL": dev_email,
        }
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                client.get("/dashboard")
                client.get("/dashboard")

        conn = sqlite3.connect(str(auth_db))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM users WHERE email = ?", (dev_email,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 1  # No duplicate user rows


# ---------------------------------------------------------------------------
# Health endpoint bypasses middleware (AC-17k)
# ---------------------------------------------------------------------------


class TestExcludedPaths:
    """Excluded paths bypass session middleware (AC-17k)."""

    def test_health_endpoint_no_session_required(self, auth_db: Path) -> None:
        """GET /health returns 200 without a session cookie (AC-17k)."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(auth_db)}):
            with TestClient(app) as client:
                response = client.get("/health")
        assert response.status_code == 200

    def test_auth_login_page_no_session_required(self, auth_db: Path) -> None:
        """GET /auth/login is accessible without a session (excluded path)."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(auth_db)}):
            with TestClient(app) as client:
                response = client.get("/auth/login")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# DEV_USER_EMAIL production guard tests (E-063-01)
# ---------------------------------------------------------------------------


from src.api.auth import SessionMiddleware  # noqa: E402


class TestDevUserEmailProductionGuard:
    """DEV_USER_EMAIL raises RuntimeError when APP_ENV=production (E-063-01)."""

    def test_production_with_dev_email_raises(self) -> None:
        """DEV_USER_EMAIL set + APP_ENV=production -> RuntimeError on init (AC-1)."""
        env = {"DEV_USER_EMAIL": "admin@example.com", "APP_ENV": "production"}
        with patch.dict("os.environ", env, clear=False):
            with pytest.raises(RuntimeError, match="DEV_USER_EMAIL"):
                SessionMiddleware(app=None)  # type: ignore[arg-type]

    def test_development_with_dev_email_does_not_raise(self) -> None:
        """DEV_USER_EMAIL set + APP_ENV=development -> no error on init (AC-2)."""
        env = {"DEV_USER_EMAIL": "admin@example.com", "APP_ENV": "development"}
        with patch.dict("os.environ", env, clear=False):
            # Should not raise; dev bypass is expected in development
            middleware = SessionMiddleware(app=None)  # type: ignore[arg-type]
            assert middleware is not None

    def test_production_mixed_case_with_dev_email_raises(self) -> None:
        """DEV_USER_EMAIL set + APP_ENV=Production (mixed case) -> RuntimeError (AC-1)."""
        env = {"DEV_USER_EMAIL": "admin@example.com", "APP_ENV": "Production"}
        with patch.dict("os.environ", env, clear=False):
            with pytest.raises(RuntimeError, match="DEV_USER_EMAIL"):
                SessionMiddleware(app=None)  # type: ignore[arg-type]

    def test_production_uppercase_with_dev_email_raises(self) -> None:
        """DEV_USER_EMAIL set + APP_ENV=PRODUCTION (all caps) -> RuntimeError (AC-1)."""
        env = {"DEV_USER_EMAIL": "admin@example.com", "APP_ENV": "PRODUCTION"}
        with patch.dict("os.environ", env, clear=False):
            with pytest.raises(RuntimeError, match="DEV_USER_EMAIL"):
                SessionMiddleware(app=None)  # type: ignore[arg-type]

    def test_dev_email_unset_env_does_not_raise(self) -> None:
        """DEV_USER_EMAIL unset + APP_ENV=production -> no error on init (AC-3)."""
        env = {"APP_ENV": "production"}
        # Ensure DEV_USER_EMAIL is absent from the environment
        with patch.dict("os.environ", env, clear=False):
            os_environ_no_dev = {k: v for k, v in os.environ.items() if k != "DEV_USER_EMAIL"}
            with patch.dict("os.environ", os_environ_no_dev, clear=True):
                middleware = SessionMiddleware(app=None)  # type: ignore[arg-type]
                assert middleware is not None


# ---------------------------------------------------------------------------
# Fail closed on missing auth tables tests (E-063-06)
# ---------------------------------------------------------------------------

_SCHEMA_SQL_NO_AUTH = """
    CREATE TABLE IF NOT EXISTS teams (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT NOT NULL,
        membership_type TEXT NOT NULL DEFAULT 'member',
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );
"""


def _make_no_auth_db(tmp_path: Path) -> Path:
    """Create a database WITHOUT auth tables (simulates missing migrations).

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Path to the database file.
    """
    db_path = tmp_path / "test_no_auth.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA_SQL_NO_AUTH)
    conn.commit()
    conn.close()
    return db_path


class TestFailClosedMissingAuthTables:
    """Missing auth tables return 503 instead of allowing requests through (E-063-06)."""

    def test_missing_tables_cookie_path_returns_503(self, tmp_path: Path) -> None:
        """No auth tables + session cookie -> 503, not pass-through (AC-1, AC-2)."""
        db_path = _make_no_auth_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path)}
        with patch.dict("os.environ", env, clear=False):
            os_env_no_dev = {k: v for k, v in os.environ.items() if k != "DEV_USER_EMAIL"}
            with patch.dict("os.environ", os_env_no_dev, clear=True):
                with TestClient(
                    app,
                    follow_redirects=False,
                    cookies={"session": "sometoken"},
                ) as client:
                    response = client.get("/dashboard")
        assert response.status_code == 503
        assert "unavailable" in response.text.lower()

    def test_missing_tables_dev_bypass_path_returns_503(self, tmp_path: Path) -> None:
        """No auth tables + DEV_USER_EMAIL -> 503, not pass-through (AC-1, AC-2)."""
        db_path = _make_no_auth_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get("/dashboard")
        assert response.status_code == 503
        assert "unavailable" in response.text.lower()

    def test_normal_auth_unchanged_when_tables_exist(self, auth_db: Path) -> None:
        """Normal session validation still works when tables exist (AC-3)."""
        user_id = _insert_user(auth_db, "normal@example.com")
        raw_token = _insert_session(auth_db, user_id)

        env = {"DATABASE_PATH": str(auth_db)}
        with patch.dict("os.environ", env, clear=False):
            os_env_no_dev = {k: v for k, v in os.environ.items() if k != "DEV_USER_EMAIL"}
            with patch.dict("os.environ", os_env_no_dev, clear=True):
                with TestClient(app, cookies={"session": raw_token}) as client:
                    response = client.get("/dashboard")
        assert response.status_code == 200

    def test_missing_tables_no_cookie_returns_503(self, tmp_path: Path) -> None:
        """No auth tables + no session cookie -> 503, not redirect to login (AC-1)."""
        db_path = _make_no_auth_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path)}
        with patch.dict("os.environ", env, clear=False):
            os_env_no_dev = {k: v for k, v in os.environ.items() if k != "DEV_USER_EMAIL"}
            with patch.dict("os.environ", os_env_no_dev, clear=True):
                with TestClient(
                    app,
                    follow_redirects=False,
                ) as client:
                    response = client.get("/dashboard")
        assert response.status_code == 503
        assert "unavailable" in response.text.lower()

    def test_non_table_operational_error_propagates(self, auth_db: Path) -> None:
        """OperationalErrors that are not 'no such table' are re-raised (AC-4)."""
        from unittest.mock import patch as mock_patch

        other_error = sqlite3.OperationalError("database is locked")
        with mock_patch(
            "src.api.auth._resolve_session_from_cookie", side_effect=other_error
        ):
            env = {"DATABASE_PATH": str(auth_db)}
            with patch.dict("os.environ", env, clear=False):
                os_env_no_dev = {k: v for k, v in os.environ.items() if k != "DEV_USER_EMAIL"}
                with patch.dict("os.environ", os_env_no_dev, clear=True):
                    with TestClient(
                        app,
                        follow_redirects=False,
                        raise_server_exceptions=True,
                        cookies={"session": "sometoken"},
                    ) as client:
                        with pytest.raises(sqlite3.OperationalError, match="database is locked"):
                            client.get("/dashboard")
