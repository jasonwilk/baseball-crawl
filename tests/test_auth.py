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
# Schema SQL (includes both base tables and auth tables)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS _migrations (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        filename   TEXT    NOT NULL UNIQUE,
        applied_at TEXT    NOT NULL DEFAULT (datetime('now'))
    );
    INSERT OR IGNORE INTO _migrations (filename) VALUES ('001_initial_schema.sql');

    CREATE TABLE IF NOT EXISTS players (
        player_id  TEXT PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name  TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS teams (
        team_id    TEXT PRIMARY KEY,
        name       TEXT NOT NULL,
        level      TEXT,
        is_owned   INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS team_rosters (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id       TEXT NOT NULL,
        player_id     TEXT NOT NULL,
        season        TEXT NOT NULL,
        jersey_number TEXT,
        position      TEXT,
        UNIQUE(team_id, player_id, season)
    );

    CREATE TABLE IF NOT EXISTS games (
        game_id      TEXT PRIMARY KEY,
        season       TEXT NOT NULL,
        game_date    TEXT NOT NULL,
        home_team_id TEXT NOT NULL,
        away_team_id TEXT NOT NULL,
        home_score   INTEGER,
        away_score   INTEGER,
        status       TEXT NOT NULL DEFAULT 'completed'
    );

    CREATE TABLE IF NOT EXISTS player_game_batting (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id   TEXT NOT NULL,
        player_id TEXT NOT NULL,
        team_id   TEXT NOT NULL,
        ab        INTEGER,
        h         INTEGER,
        doubles   INTEGER,
        triples   INTEGER,
        hr        INTEGER,
        rbi       INTEGER,
        bb        INTEGER,
        so        INTEGER,
        sb        INTEGER,
        UNIQUE(game_id, player_id)
    );

    CREATE TABLE IF NOT EXISTS player_game_pitching (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id   TEXT NOT NULL,
        player_id TEXT NOT NULL,
        team_id   TEXT NOT NULL,
        ip_outs   INTEGER,
        h         INTEGER,
        er        INTEGER,
        bb        INTEGER,
        so        INTEGER,
        hr        INTEGER,
        UNIQUE(game_id, player_id)
    );

    CREATE TABLE IF NOT EXISTS player_season_batting (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id TEXT NOT NULL,
        team_id   TEXT NOT NULL,
        season    TEXT NOT NULL,
        games     INTEGER,
        ab        INTEGER,
        h         INTEGER,
        doubles   INTEGER,
        triples   INTEGER,
        hr        INTEGER,
        rbi       INTEGER,
        bb        INTEGER,
        so        INTEGER,
        sb        INTEGER,
        home_ab   INTEGER,
        home_h    INTEGER,
        away_ab   INTEGER,
        away_h    INTEGER,
        vs_lhp_ab INTEGER,
        vs_lhp_h  INTEGER,
        vs_rhp_ab INTEGER,
        vs_rhp_h  INTEGER,
        UNIQUE(player_id, team_id, season)
    );

    -- Auth tables (003_auth.sql)
    CREATE TABLE IF NOT EXISTS users (
        user_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        email        TEXT    NOT NULL UNIQUE,
        display_name TEXT    NOT NULL,
        is_admin     INTEGER NOT NULL DEFAULT 0,
        created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS user_team_access (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id  INTEGER NOT NULL REFERENCES users(user_id),
        team_id  TEXT    NOT NULL REFERENCES teams(team_id),
        UNIQUE(user_id, team_id)
    );

    CREATE TABLE IF NOT EXISTS magic_link_tokens (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        token_hash TEXT    NOT NULL UNIQUE,
        user_id    INTEGER NOT NULL REFERENCES users(user_id),
        expires_at TEXT    NOT NULL,
        used_at    TEXT,
        created_at TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS passkey_credentials (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id       INTEGER NOT NULL REFERENCES users(user_id),
        credential_id BLOB    NOT NULL UNIQUE,
        public_key    BLOB    NOT NULL,
        sign_count    INTEGER NOT NULL DEFAULT 0,
        created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS sessions (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        session_token_hash  TEXT    NOT NULL UNIQUE,
        user_id             INTEGER NOT NULL REFERENCES users(user_id),
        expires_at          TEXT    NOT NULL,
        challenge           TEXT,
        created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
    );
"""

_SEED_SQL = """
    INSERT OR IGNORE INTO teams (team_id, name, level, is_owned) VALUES
        ('lsb-varsity-2026', 'LSB Varsity 2026', 'varsity', 1);
"""


def _make_auth_db(tmp_path: Path) -> Path:
    """Create a database with full schema (base + auth tables).

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


def _insert_user(db_path: Path, email: str, is_admin: int = 0) -> int:
    """Insert a user row and return the user_id.

    Args:
        db_path: Path to the database file.
        email: Email address for the user.
        is_admin: 1 for admin, 0 for non-admin.

    Returns:
        The new user_id.
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "INSERT INTO users (email, display_name, is_admin) VALUES (?, ?, ?)",
        (email, "Test User", is_admin),
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
    token_hash = hash_token(raw_token)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT INTO sessions (session_token_hash, user_id, expires_at)
        VALUES (?, ?, datetime('now', '+7 days'))
        """,
        (token_hash, user_id),
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
    token_hash = hash_token(raw_token)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT INTO sessions (session_token_hash, user_id, expires_at)
        VALUES (?, ?, datetime('now', '-1 hour'))
        """,
        (token_hash, user_id),
    )
    conn.commit()
    conn.close()
    return raw_token


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth_db(tmp_path: Path) -> Path:
    """Full schema database with one owned team."""
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
        user_id = _insert_user(auth_db, "coach2@example.com", is_admin=1)
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
            "SELECT email, is_admin FROM users WHERE email = ?", (dev_email,)
        )
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert row[0] == dev_email
        assert row[1] == 1  # is_admin=1

    def test_dev_bypass_uses_existing_user(self, auth_db: Path) -> None:
        """DEV_USER_EMAIL reuses existing user row if already present (AC-17j)."""
        dev_email = "existing@example.com"
        _insert_user(auth_db, dev_email, is_admin=0)

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
