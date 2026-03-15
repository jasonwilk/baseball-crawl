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

E-100 schema notes:
    - magic_link_tokens: (token TEXT PK, user_id, expires_at) -- no token_hash,
      no used_at, no created_at, no id row.
    - Token verification DELETES the row (single-use enforcement).
    - Rate limiting uses expires_at > datetime('now', '+14 minutes') as a proxy
      for "issued within last 60 seconds" (tokens expire after 15 minutes).
    - Prior tokens are invalidated via DELETE WHERE user_id (not used_at update).
    - users: id INTEGER PK (no user_id alias, no display_name, no is_admin)
    - sessions: session_id TEXT PK (no session_token_hash, no challenge, no id)

Uses an in-process SQLite database via tmp_path; no Docker or network.
Mailgun calls are mocked so no real email is sent.

Run with:
    pytest tests/test_auth_routes.py -v
"""

from __future__ import annotations

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
# Full schema SQL -- E-100 schema
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
"""

_SEED_SQL = """
    INSERT OR IGNORE INTO programs (program_id, name, program_type) VALUES
        ('lsb-hs', 'Lincoln Standing Bear HS', 'hs');
    INSERT OR IGNORE INTO teams (name, membership_type, classification) VALUES
        ('LSB Varsity 2026', 'member', 'varsity');
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    """Create a fully-schemed E-100 database with one team row.

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


def _insert_user(db_path: Path, email: str) -> int:
    """Insert a user and return user id.

    Args:
        db_path: Path to the database.
        email: User email address.

    Returns:
        The new user id integer (INTEGER PK).
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


def _insert_magic_token(
    db_path: Path,
    user_id: int,
    expired: bool = False,
) -> str:
    """Insert a magic link token and return the raw token.

    In the E-100 schema, the token IS the PRIMARY KEY (raw token stored
    directly, no hashing). Single-use enforcement is done via DELETE on use.

    Args:
        db_path: Path to the database.
        user_id: User to associate with this token.
        expired: If True, sets expires_at in the past.

    Returns:
        Raw token string (URL-safe base64, 43 chars).
    """
    raw_token = secrets.token_urlsafe(32)
    expires_offset = "-1 hour" if expired else "+15 minutes"

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        f"""
        INSERT INTO magic_link_tokens (token, user_id, expires_at)
        VALUES (?, ?, datetime('now', '{expires_offset}'))
        """,
        (raw_token, user_id),
    )
    conn.commit()
    conn.close()
    return raw_token


def _insert_magic_token_with_age(
    db_path: Path,
    user_id: int,
    seconds_ago: int,
) -> str:
    """Insert a magic link token that appears to have been issued N seconds ago.

    In the E-100 schema, rate limiting is approximated by checking if a token
    has expires_at > datetime('now', '+14 minutes'). A token issued N seconds
    ago would have expires_at = issued_at + 15 minutes.

    For N seconds_ago, expires_at = now - N seconds + 15 minutes
                                  = now + (15*60 - N) seconds.
    If N < 60, expires_at > now + 14 minutes -- rate limited.
    If N >= 60, expires_at <= now + 14 minutes -- not rate limited.

    Args:
        db_path: Path to the database.
        user_id: User to associate with this token.
        seconds_ago: How many seconds ago the token was issued.

    Returns:
        Raw token string (URL-safe base64, 43 chars).
    """
    raw_token = secrets.token_urlsafe(32)
    # Calculate remaining lifetime: 15 minutes - seconds_ago seconds
    remaining_seconds = 15 * 60 - seconds_ago
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        f"""
        INSERT INTO magic_link_tokens (token, user_id, expires_at)
        VALUES (?, ?, datetime('now', '{remaining_seconds} seconds'))
        """,
        (raw_token, user_id),
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    """Database with full E-100 schema and one member team."""
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
        user_id = _insert_user(db, email)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch("src.api.routes.auth.send_magic_link_email", new_callable=AsyncMock, return_value=True):
                with TestClient(app) as client:
                    response = client.post("/auth/login", data={"email": email})

        assert response.status_code == 200
        # Verify token was inserted
        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM magic_link_tokens WHERE user_id = ?",
            (user_id,),
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

    def test_valid_token_is_deleted_after_use(self, db: Path) -> None:
        """Valid token is deleted from magic_link_tokens after verification (AC-17d).

        E-100 schema uses DELETE for single-use enforcement (no used_at column).
        """
        user_id = _insert_user(db, "markused@example.com")
        raw_token = _insert_magic_token(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False) as client:
                client.get(f"/auth/verify?token={raw_token}")

        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM magic_link_tokens WHERE token = ?",
            (raw_token,),
        )
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 0  # Row was deleted on use

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
        """Already-used token (deleted) renders verify_error.html (AC-17f).

        After first use the token row is deleted, so a second attempt gets
        'not found' -> same verify_error.html response.
        """
        user_id = _insert_user(db, "alreadyused@example.com")
        raw_token = _insert_magic_token(db, user_id)

        # First use consumes (deletes) the token.
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False) as client:
                client.get(f"/auth/verify?token={raw_token}")

        # Second attempt -- token is gone.
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
                # Second use -- should fail (token was deleted)
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
        session_id = hash_token(raw_token)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token},
            ) as client:
                client.get("/auth/logout")

        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE session_id = ?",
            (session_id,),
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


# ---------------------------------------------------------------------------
# Stale token invalidation tests (E-063-04)
# ---------------------------------------------------------------------------


class TestStaleMagicLinkInvalidation:
    """Issuing a new magic link invalidates all prior tokens for the user (E-063-04).

    E-100 schema: prior tokens are invalidated by DELETE WHERE user_id (not
    used_at update). A token issued 60+ seconds ago has expires_at at or below
    datetime('now', '+14 minutes') so the rate limit check passes.
    """

    def test_prior_token_deleted_when_new_link_issued(self, db: Path) -> None:
        """AC-1: Prior token is deleted when new link is issued."""
        email = "staletoken@example.com"
        user_id = _insert_user(db, email)
        # Insert a prior token that is old enough to bypass the rate limiter
        # (61 seconds ago => expires_at = now + (15*60 - 61) = now + 839 seconds < 14 min).
        prior_raw = _insert_magic_token_with_age(db, user_id, seconds_ago=61)

        # Request a new magic link -- this should delete the prior token.
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch(
                "src.api.routes.auth.send_magic_link_email",
                new_callable=AsyncMock,
                return_value=True,
            ):
                with TestClient(app) as client:
                    client.post("/auth/login", data={"email": email})

        # Prior token should be gone.
        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM magic_link_tokens WHERE token = ?",
            (prior_raw,),
        )
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 0  # Prior token deleted

    def test_old_token_fails_verification_after_new_link_issued(self, db: Path) -> None:
        """AC-2: Verifying the older token fails after a new link is issued."""
        email = "oldfails@example.com"
        user_id = _insert_user(db, email)
        prior_raw = _insert_magic_token_with_age(db, user_id, seconds_ago=61)

        # Issue a second magic link, deleting the first.
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch(
                "src.api.routes.auth.send_magic_link_email",
                new_callable=AsyncMock,
                return_value=True,
            ):
                with TestClient(app) as client:
                    client.post("/auth/login", data={"email": email})

        # Attempting to verify the prior (now-deleted) token must fail.
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app) as client:
                response = client.get(f"/auth/verify?token={prior_raw}")

        assert "invalid or has expired" in response.text.lower()

    def test_new_token_succeeds_after_prior_deleted(self, db: Path) -> None:
        """AC-3: The newest token still verifies successfully after prior tokens are deleted."""
        email = "newworks@example.com"
        user_id = _insert_user(db, email)
        _insert_magic_token_with_age(db, user_id, seconds_ago=61)

        captured_url: list[str] = []

        async def capture_email(to_email: str, magic_link_url: str) -> None:
            captured_url.append(magic_link_url)

        # Issue a new link (deletes the prior one) and capture the new token.
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch(
                "src.api.routes.auth.send_magic_link_email",
                side_effect=capture_email,
            ):
                with TestClient(app) as client:
                    client.post("/auth/login", data={"email": email})

        assert len(captured_url) == 1
        new_token = captured_url[0].split("token=")[-1]

        # The new token must verify successfully.
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get(f"/auth/verify?token={new_token}")

        assert response.status_code == 302
        location = response.headers["location"]
        assert "/dashboard" in location or "/auth/passkey/prompt" in location

    def test_issue_token_a_then_b_verify_a_fails_b_succeeds(self, db: Path) -> None:
        """AC-4: Issue token A, issue token B; verify A fails, verify B succeeds."""
        email = "ab_tokens@example.com"
        user_id = _insert_user(db, email)
        token_a_raw = _insert_magic_token_with_age(db, user_id, seconds_ago=61)

        captured_url: list[str] = []

        async def capture_email(to_email: str, magic_link_url: str) -> None:
            captured_url.append(magic_link_url)

        # Issue token B via POST /auth/login (deletes token A).
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch(
                "src.api.routes.auth.send_magic_link_email",
                side_effect=capture_email,
            ):
                with TestClient(app) as client:
                    client.post("/auth/login", data={"email": email})

        assert len(captured_url) == 1
        token_b_raw = captured_url[0].split("token=")[-1]

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app) as client:
                # Verify A -- must fail (deleted by B issuance).
                response_a = client.get(f"/auth/verify?token={token_a_raw}")
            assert "invalid or has expired" in response_a.text.lower()

            with TestClient(app, follow_redirects=False) as client:
                # Verify B -- must succeed.
                response_b = client.get(f"/auth/verify?token={token_b_raw}")
            assert response_b.status_code == 302

    def test_only_newest_token_exists_after_new_issuance(self, db: Path) -> None:
        """After new link issuance, exactly one token exists for the user."""
        email = "single_token@example.com"
        user_id = _insert_user(db, email)
        # Two prior tokens (both old enough to bypass rate limiter).
        _insert_magic_token_with_age(db, user_id, seconds_ago=61)
        # The second prior token -- pretend it's a manual insert to bypass rate limit.
        conn = sqlite3.connect(str(db))
        conn.execute(
            """
            INSERT INTO magic_link_tokens (token, user_id, expires_at)
            VALUES (?, ?, datetime('now', '839 seconds'))
            """,
            (secrets.token_urlsafe(32), user_id),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch(
                "src.api.routes.auth.send_magic_link_email",
                new_callable=AsyncMock,
                return_value=True,
            ):
                with TestClient(app) as client:
                    client.post("/auth/login", data={"email": email})

        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM magic_link_tokens WHERE user_id = ?", (user_id,)
        )
        total = cursor.fetchone()[0]
        conn.close()
        # Only the newly issued token should exist.
        assert total == 1


# ---------------------------------------------------------------------------
# Magic link rate limiting tests (E-063-05)
# ---------------------------------------------------------------------------


class TestMagicLinkRateLimiting:
    """POST /auth/login enforces a 60-second per-user cooldown (E-063-05).

    E-100 rate limiting: a token with expires_at > datetime('now', '+14 minutes')
    was issued within the last 60 seconds. Tokens expire at issued_at + 15 min.
    """

    def test_first_request_issues_link(self, db: Path) -> None:
        """AC-5a: First magic link request issues a link and calls send_magic_link_email."""
        email = "ratelimit_first@example.com"
        user_id = _insert_user(db, email)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch(
                "src.api.routes.auth.send_magic_link_email",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_send:
                with TestClient(app) as client:
                    response = client.post("/auth/login", data={"email": email})

        assert response.status_code == 200
        assert "If this email is registered" in response.text
        mock_send.assert_called_once()

        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM magic_link_tokens WHERE user_id = ?",
            (user_id,),
        )
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_second_request_within_cooldown_suppressed(self, db: Path) -> None:
        """AC-1 & AC-5b: Second request within 60s sends no email and adds no token row."""
        email = "ratelimit_suppress@example.com"
        user_id = _insert_user(db, email)
        # Token issued 10 seconds ago => expires_at = now + 890 seconds > 14 min.
        _insert_magic_token_with_age(db, user_id, seconds_ago=10)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch(
                "src.api.routes.auth.send_magic_link_email",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_send:
                with TestClient(app) as client:
                    response = client.post("/auth/login", data={"email": email})

        # Same confirmation page shown regardless.
        assert response.status_code == 200
        assert "If this email is registered" in response.text
        # No email sent.
        mock_send.assert_not_called()
        # No new token inserted -- still just the one we seeded.
        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM magic_link_tokens WHERE user_id = ?", (user_id,)
        )
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_request_after_cooldown_issues_new_link(self, db: Path) -> None:
        """AC-2 & AC-5c: Request after 60s cooldown issues a new link normally."""
        email = "ratelimit_after@example.com"
        user_id = _insert_user(db, email)
        # Token issued 61 seconds ago => expires_at = now + 839 seconds <= 14 min.
        _insert_magic_token_with_age(db, user_id, seconds_ago=61)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch(
                "src.api.routes.auth.send_magic_link_email",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_send:
                with TestClient(app) as client:
                    response = client.post("/auth/login", data={"email": email})

        assert response.status_code == 200
        assert "If this email is registered" in response.text
        mock_send.assert_called_once()
        # Old token deleted, new token inserted -- net count is 1.
        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM magic_link_tokens WHERE user_id = ?", (user_id,)
        )
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_unknown_email_still_shows_confirmation_page(self, db: Path) -> None:
        """AC-3: Unknown email returns the same check_email page (no enumeration)."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app) as client:
                response = client.post(
                    "/auth/login", data={"email": "nobody@example.com"}
                )

        assert response.status_code == 200
        assert "If this email is registered" in response.text

    def test_cooldown_boundary_at_exactly_60_seconds_allows_issuance(
        self, db: Path
    ) -> None:
        """AC-2: A token issued exactly 60 seconds ago is NOT rate-limited.

        At 60 seconds ago, expires_at = now + (15*60 - 60) = now + 840 seconds
        = now + 14 minutes exactly. The rate limit check is
        expires_at > datetime('now', '+14 minutes'), which is a strict greater-than,
        so now + 14 minutes is NOT rate-limited.
        """
        email = "ratelimit_boundary@example.com"
        user_id = _insert_user(db, email)
        # 60 seconds ago => expires_at = now + 840 seconds = now + 14 minutes exactly.
        _insert_magic_token_with_age(db, user_id, seconds_ago=60)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch(
                "src.api.routes.auth.send_magic_link_email",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_send:
                with TestClient(app) as client:
                    client.post("/auth/login", data={"email": email})

        mock_send.assert_called_once()
