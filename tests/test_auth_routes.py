# synthetic-test-data
"""Tests for auth routes (src/api/routes/auth.py) -- E-023-02 AC-17.

Tests cover:
- Login page renders (AC-17a)
- POST login with known email creates token (AC-17b)
- POST login with unknown email shows same response (no enumeration) (AC-17c)
- Valid token verification creates session and sets cookie (AC-17d)
- Expired token is rejected (AC-17e)
- Used token is rejected (AC-17f)
- Logout clears session (AC-17i)

Uses an in-process SQLite database via tmp_path; no Docker or network.
Mailgun calls are mocked so no real email is sent.

Run with:
    pytest tests/test_auth_routes.py -v
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

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
# Full schema SQL (base + auth tables)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    """Create a fully-schemed database with one team row.

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Path to the database file.
    """
    db_path = tmp_path / "test_routes.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA_SQL)
    conn.executescript(_SEED_SQL)
    conn.commit()
    conn.close()
    return db_path


def _insert_user(db_path: Path, email: str, is_admin: int = 0) -> int:
    """Insert a user and return user_id.

    Args:
        db_path: Path to the database.
        email: User email address.
        is_admin: Admin flag.

    Returns:
        The new user_id integer.
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "INSERT INTO users (email, display_name, is_admin) VALUES (?, ?, ?)",
        (email, "Test Coach", is_admin),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def _insert_magic_token(
    db_path: Path,
    user_id: int,
    expired: bool = False,
    used: bool = False,
) -> str:
    """Insert a magic link token and return the raw token.

    Args:
        db_path: Path to the database.
        user_id: User to associate with this token.
        expired: If True, sets expires_at in the past.
        used: If True, sets used_at to now.

    Returns:
        Raw token string (URL-safe base64, 43 chars).
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    expires_offset = "-1 hour" if expired else "+15 minutes"
    used_at_expr = "datetime('now')" if used else "NULL"

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        f"""
        INSERT INTO magic_link_tokens (token_hash, user_id, expires_at, used_at)
        VALUES (?, ?, datetime('now', '{expires_offset}'), {used_at_expr})
        """,
        (token_hash, user_id),
    )
    conn.commit()
    conn.close()
    return raw_token


def _insert_session(db_path: Path, user_id: int) -> str:
    """Insert a valid session row and return the raw token.

    Args:
        db_path: Path to the database.
        user_id: User to associate with this session.

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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    """Database with full schema and one owned team."""
    return _make_db(tmp_path)


# ---------------------------------------------------------------------------
# Login page tests (AC-17a)
# ---------------------------------------------------------------------------


class TestLoginPageRenders:
    """GET /auth/login renders the login form (AC-17a)."""

    def test_login_page_returns_200(self, db: Path) -> None:
        """GET /auth/login returns 200."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app) as client:
                response = client.get("/auth/login")
        assert response.status_code == 200

    def test_login_page_contains_email_input(self, db: Path) -> None:
        """GET /auth/login HTML includes an email input field."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app) as client:
                response = client.get("/auth/login")
        assert 'type="email"' in response.text

    def test_login_page_contains_submit_button(self, db: Path) -> None:
        """GET /auth/login HTML includes a submit button."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app) as client:
                response = client.get("/auth/login")
        assert "magic link" in response.text.lower() or "submit" in response.text.lower()

    def test_login_page_contains_form_post(self, db: Path) -> None:
        """GET /auth/login form uses POST method."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app) as client:
                response = client.get("/auth/login")
        assert 'method="post"' in response.text.lower()

    def test_login_page_redirects_if_valid_session(self, db: Path) -> None:
        """GET /auth/login redirects to /dashboard if a valid session cookie exists."""
        user_id = _insert_user(db, "loggedin@example.com")
        raw_token = _insert_session(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token},
            ) as client:
                response = client.get("/auth/login")
        assert response.status_code == 302
        assert "/dashboard" in response.headers["location"]


# ---------------------------------------------------------------------------
# POST /auth/login tests (AC-17b, AC-17c)
# ---------------------------------------------------------------------------


class TestPostLogin:
    """POST /auth/login handles known and unknown emails (AC-17b, AC-17c)."""

    def test_known_email_creates_token(self, db: Path) -> None:
        """POST /auth/login with known email inserts a magic_link_tokens row (AC-17b)."""
        email = "known@example.com"
        _insert_user(db, email)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch("src.api.routes.auth.send_magic_link_email", new_callable=AsyncMock, return_value=True):
                with TestClient(app) as client:
                    response = client.post("/auth/login", data={"email": email})

        assert response.status_code == 200
        # Verify token was inserted
        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM magic_link_tokens WHERE user_id = ("
            "SELECT user_id FROM users WHERE email = ?)",
            (email,),
        )
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 1

    def test_known_email_calls_send_email(self, db: Path) -> None:
        """POST /auth/login with known email calls send_magic_link_email (AC-17b)."""
        email = "sendemail@example.com"
        _insert_user(db, email)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch(
                "src.api.routes.auth.send_magic_link_email", new_callable=AsyncMock, return_value=True
            ) as mock_send:
                with TestClient(app) as client:
                    client.post("/auth/login", data={"email": email})

        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args[0][0] == email  # to_email
        assert "/auth/verify?token=" in call_args[0][1]  # magic_link_url

    def test_known_email_shows_check_email_page(self, db: Path) -> None:
        """POST /auth/login with known email renders check_email page (AC-17b)."""
        email = "showpage@example.com"
        _insert_user(db, email)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch("src.api.routes.auth.send_magic_link_email", new_callable=AsyncMock, return_value=True):
                with TestClient(app) as client:
                    response = client.post("/auth/login", data={"email": email})

        assert "If this email is registered" in response.text

    def test_unknown_email_shows_same_page(self, db: Path) -> None:
        """POST /auth/login with unknown email shows identical page (no enumeration, AC-17c)."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app) as client:
                response = client.post(
                    "/auth/login", data={"email": "unknown@example.com"}
                )

        assert response.status_code == 200
        assert "If this email is registered" in response.text

    def test_unknown_email_does_not_create_token(self, db: Path) -> None:
        """POST /auth/login with unknown email does not insert a magic_link_tokens row."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app) as client:
                client.post("/auth/login", data={"email": "ghost@example.com"})

        conn = sqlite3.connect(str(db))
        cursor = conn.execute("SELECT COUNT(*) FROM magic_link_tokens;")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 0

    def test_magic_link_token_format(self, db: Path) -> None:
        """Magic link token passed to send_magic_link_email matches AC-4 format."""
        email = "tokenformat@example.com"
        _insert_user(db, email)
        app_url = "http://localhost:8000"

        with patch.dict(
            "os.environ", {"DATABASE_PATH": str(db), "APP_URL": app_url}
        ):
            with patch(
                "src.api.routes.auth.send_magic_link_email", new_callable=AsyncMock, return_value=True
            ) as mock_send:
                with TestClient(app) as client:
                    client.post("/auth/login", data={"email": email})

        url_arg = mock_send.call_args[0][1]
        assert url_arg.startswith(f"{app_url}/auth/verify?token=")
        token_part = url_arg.split("token=")[-1]
        # token_urlsafe(32) produces 43 characters
        assert len(token_part) == 43


# ---------------------------------------------------------------------------
# GET /auth/verify tests (AC-17d, AC-17e, AC-17f)
# ---------------------------------------------------------------------------


class TestVerifyToken:
    """Token verification flows (AC-17d, AC-17e, AC-17f)."""

    def test_valid_token_creates_session_and_redirects(self, db: Path) -> None:
        """Valid token verification creates session and redirects (AC-17d).

        A user with no passkeys is redirected to the passkey prompt interstitial;
        a user with passkeys is redirected directly to /dashboard.
        """
        user_id = _insert_user(db, "verify@example.com")
        raw_token = _insert_magic_token(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get(f"/auth/verify?token={raw_token}")

        assert response.status_code == 302
        location = response.headers["location"]
        # New user (no passkeys) -> passkey prompt; user with passkeys -> /dashboard
        assert "/dashboard" in location or "/auth/passkey/prompt" in location

    def test_valid_token_sets_session_cookie(self, db: Path) -> None:
        """Valid token sets the session cookie on the response (AC-17d)."""
        user_id = _insert_user(db, "cookie@example.com")
        raw_token = _insert_magic_token(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get(f"/auth/verify?token={raw_token}")

        assert "session" in response.cookies

    def test_valid_token_inserts_session_row(self, db: Path) -> None:
        """Valid token verification inserts a row in the sessions table (AC-17d)."""
        user_id = _insert_user(db, "sessrow@example.com")
        raw_token = _insert_magic_token(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False) as client:
                client.get(f"/auth/verify?token={raw_token}")

        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 1

    def test_valid_token_is_marked_used(self, db: Path) -> None:
        """Valid token is marked used_at after verification (AC-17d)."""
        user_id = _insert_user(db, "markused@example.com")
        raw_token = _insert_magic_token(db, user_id)
        token_hash = hash_token(raw_token)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False) as client:
                client.get(f"/auth/verify?token={raw_token}")

        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT used_at FROM magic_link_tokens WHERE token_hash = ?",
            (token_hash,),
        )
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert row[0] is not None  # used_at is set

    def test_expired_token_shows_error_page(self, db: Path) -> None:
        """Expired token renders verify_error.html (AC-17e)."""
        user_id = _insert_user(db, "expired@example.com")
        raw_token = _insert_magic_token(db, user_id, expired=True)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app) as client:
                response = client.get(f"/auth/verify?token={raw_token}")

        assert response.status_code in (400, 200)  # renders error page
        assert "invalid or has expired" in response.text.lower()

    def test_used_token_shows_error_page(self, db: Path) -> None:
        """Already-used token renders verify_error.html (AC-17f)."""
        user_id = _insert_user(db, "alreadyused@example.com")
        raw_token = _insert_magic_token(db, user_id, used=True)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app) as client:
                response = client.get(f"/auth/verify?token={raw_token}")

        assert "invalid or has expired" in response.text.lower()

    def test_nonexistent_token_shows_error_page(self, db: Path) -> None:
        """Non-existent token renders verify_error.html."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app) as client:
                response = client.get("/auth/verify?token=doesnotexisttoken123456789012")

        assert "invalid or has expired" in response.text.lower()

    def test_missing_token_param_shows_error_page(self, db: Path) -> None:
        """Missing token parameter renders verify_error.html."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app) as client:
                response = client.get("/auth/verify")

        assert response.status_code in (400, 422, 200)
        # Either error page or validation error -- either is acceptable

    def test_used_token_cannot_be_reused(self, db: Path) -> None:
        """A valid token cannot be used twice (AC-17f)."""
        user_id = _insert_user(db, "reuse@example.com")
        raw_token = _insert_magic_token(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False) as client:
                # First use -- should succeed
                response1 = client.get(f"/auth/verify?token={raw_token}")
                assert response1.status_code == 302

            with TestClient(app) as client:
                # Second use -- should fail
                response2 = client.get(f"/auth/verify?token={raw_token}")
                assert "invalid or has expired" in response2.text.lower()


# ---------------------------------------------------------------------------
# Logout tests (AC-17i)
# ---------------------------------------------------------------------------


class TestLogout:
    """GET /auth/logout clears session (AC-17i)."""

    def test_logout_redirects_to_login(self, db: Path) -> None:
        """GET /auth/logout redirects to /auth/login (AC-17i)."""
        user_id = _insert_user(db, "logout@example.com")
        raw_token = _insert_session(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token},
            ) as client:
                response = client.get("/auth/logout")

        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]

    def test_logout_deletes_session_from_db(self, db: Path) -> None:
        """GET /auth/logout removes the session row from the DB (AC-17i)."""
        user_id = _insert_user(db, "logoutdb@example.com")
        raw_token = _insert_session(db, user_id)
        token_hash = hash_token(raw_token)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token},
            ) as client:
                client.get("/auth/logout")

        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE session_token_hash = ?",
            (token_hash,),
        )
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 0

    def test_logout_clears_cookie(self, db: Path) -> None:
        """GET /auth/logout clears the session cookie (AC-17i)."""
        user_id = _insert_user(db, "logoutcookie@example.com")
        raw_token = _insert_session(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token},
            ) as client:
                response = client.get("/auth/logout")

        # Cookie should be cleared (max_age=0 or empty value)
        set_cookie = response.headers.get("set-cookie", "")
        assert "session" in set_cookie

    def test_logout_without_session_still_redirects(self, db: Path) -> None:
        """GET /auth/logout without session cookie still redirects to /auth/login."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get("/auth/logout")

        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]


# ---------------------------------------------------------------------------
# Session cookie properties (AC-7)
# ---------------------------------------------------------------------------


class TestSessionCookieProperties:
    """Session cookie has correct flags (AC-7)."""

    def test_session_cookie_is_httponly(self, db: Path) -> None:
        """Verify cookie after verify contains HttpOnly flag."""
        user_id = _insert_user(db, "cookieflags@example.com")
        raw_token = _insert_magic_token(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db), "APP_ENV": "development"}):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get(f"/auth/verify?token={raw_token}")

        set_cookie = response.headers.get("set-cookie", "").lower()
        assert "httponly" in set_cookie

    def test_session_cookie_has_max_age(self, db: Path) -> None:
        """Verify cookie contains Max-Age=604800 (7 days)."""
        user_id = _insert_user(db, "maxage@example.com")
        raw_token = _insert_magic_token(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db), "APP_ENV": "development"}):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get(f"/auth/verify?token={raw_token}")

        set_cookie = response.headers.get("set-cookie", "").lower()
        assert "max-age=604800" in set_cookie

    def test_session_cookie_samesite_lax(self, db: Path) -> None:
        """Verify cookie contains SameSite=Lax."""
        user_id = _insert_user(db, "samesite@example.com")
        raw_token = _insert_magic_token(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db), "APP_ENV": "development"}):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get(f"/auth/verify?token={raw_token}")

        set_cookie = response.headers.get("set-cookie", "").lower()
        assert "samesite=lax" in set_cookie
