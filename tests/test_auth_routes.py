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

import os
import secrets
import sqlite3
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.background import BackgroundTask

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from migrations.apply_migrations import run_migrations  # noqa: E402
from src.api.auth import hash_token  # noqa: E402
from src.api.main import app  # noqa: E402

_CSRF = "test-csrf-token"
_CSRF_COOKIES = {"csrf_token": _CSRF}

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
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
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
    """Insert a magic link token (hashed) and return the raw token.

    The token column stores the SHA-256 hash of the raw token. The raw
    token is returned so tests can pass it to /auth/verify, which hashes
    it before lookup.

    Args:
        db_path: Path to the database.
        user_id: User to associate with this token.
        expired: If True, sets expires_at in the past.

    Returns:
        Raw token string (URL-safe base64, 43 chars).
    """
    raw_token = secrets.token_urlsafe(32)
    token_hashed = hash_token(raw_token)
    expires_offset = "-1 hour" if expired else "+15 minutes"

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        f"""
        INSERT INTO magic_link_tokens (token, user_id, expires_at)
        VALUES (?, ?, datetime('now', '{expires_offset}'))
        """,
        (token_hashed, user_id),
    )
    conn.commit()
    conn.close()
    return raw_token


def _insert_magic_token_with_age(
    db_path: Path,
    user_id: int,
    seconds_ago: int,
) -> str:
    """Insert a magic link token (hashed) that appears to have been issued N seconds ago.

    Rate limiting is approximated by checking if a token has
    expires_at > datetime('now', '+14 minutes'). A token issued N seconds
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
    token_hashed = hash_token(raw_token)
    # Calculate remaining lifetime: 15 minutes - seconds_ago seconds
    remaining_seconds = 15 * 60 - seconds_ago
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        f"""
        INSERT INTO magic_link_tokens (token, user_id, expires_at)
        VALUES (?, ?, datetime('now', '{remaining_seconds} seconds'))
        """,
        (token_hashed, user_id),
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
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
                response = client.get("/auth/login")
        assert response.status_code == 200

    def test_login_page_contains_email_input(self, db: Path) -> None:
        """GET /auth/login HTML includes an email input field."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
                response = client.get("/auth/login")
        assert 'type="email"' in response.text

    def test_login_page_contains_submit_button(self, db: Path) -> None:
        """GET /auth/login HTML includes a submit button."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
                response = client.get("/auth/login")
        assert "magic link" in response.text.lower() or "submit" in response.text.lower()

    def test_login_page_contains_form_post(self, db: Path) -> None:
        """GET /auth/login form uses POST method."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
                response = client.get("/auth/login")
        assert 'method="post"' in response.text.lower()

    def test_login_page_redirects_if_valid_session(self, db: Path) -> None:
        """GET /auth/login redirects to /admin/reports if a valid session cookie exists."""
        user_id = _insert_user(db, "loggedin@example.com")
        raw_token = _insert_session(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token, "csrf_token": _CSRF},
            ) as client:
                response = client.get("/auth/login")
        assert response.status_code == 302
        # E-238-05: retargeted off the quarantined /dashboard to /admin/reports.
        assert "/admin/reports" in response.headers["location"]
        assert "/dashboard" not in response.headers["location"]


class TestGetLoginDelegation:
    """E-247-07 AC-2: get_login delegates the 'already logged in' check to
    _get_authenticated_user (the single cookie->session->user resolution)."""

    def test_redirects_when_authenticated_user_present(self, db: Path) -> None:
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch(
                "src.api.routes.auth._get_authenticated_user",
                return_value={"id": 1, "email": "x@example.com"},
            ) as mock_auth:
                with TestClient(
                    app, follow_redirects=False, cookies=_CSRF_COOKIES
                ) as client:
                    response = client.get("/auth/login")
        assert response.status_code == 302
        assert "/admin/reports" in response.headers["location"]
        mock_auth.assert_called_once()

    def test_renders_login_page_when_not_authenticated(self, db: Path) -> None:
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch(
                "src.api.routes.auth._get_authenticated_user",
                return_value=None,
            ) as mock_auth:
                with TestClient(
                    app, follow_redirects=False, cookies=_CSRF_COOKIES
                ) as client:
                    response = client.get("/auth/login")
        assert response.status_code == 200
        mock_auth.assert_called_once()


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
                with TestClient(app, cookies=_CSRF_COOKIES) as client:
                    response = client.post("/auth/login", data={"email": email, "csrf_token": _CSRF})

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
                with TestClient(app, cookies=_CSRF_COOKIES) as client:
                    client.post("/auth/login", data={"email": email, "csrf_token": _CSRF})

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
                with TestClient(app, cookies=_CSRF_COOKIES) as client:
                    response = client.post("/auth/login", data={"email": email, "csrf_token": _CSRF})

        assert "If this email is registered" in response.text

    def test_unknown_email_shows_same_page(self, db: Path) -> None:
        """POST /auth/login with unknown email shows identical page (no enumeration, AC-17c)."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
                response = client.post(
                    "/auth/login", data={"email": "unknown@example.com", "csrf_token": _CSRF}
                )

        assert response.status_code == 200
        assert "If this email is registered" in response.text

    def test_unknown_email_does_not_create_token(self, db: Path) -> None:
        """POST /auth/login with unknown email does not insert a magic_link_tokens row."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
                client.post("/auth/login", data={"email": "ghost@example.com", "csrf_token": _CSRF})

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
                with TestClient(app, cookies=_CSRF_COOKIES) as client:
                    client.post("/auth/login", data={"email": email, "csrf_token": _CSRF})

        url_arg = mock_send.call_args[0][1]
        assert url_arg.startswith(f"{app_url}/auth/verify?token=")
        token_part = url_arg.split("token=")[-1]
        # token_urlsafe(32) produces 43 characters
        assert len(token_part) == 43

    def test_magic_link_uses_unified_default_when_app_url_unset(self, db: Path) -> None:
        """E-247-07 AC-4: with APP_URL unset, the magic-link base URL resolves
        through get_app_url() to the unified default http://baseball.localhost:8001.

        Real teeth on the routes/auth.py read site: it drives the magic-link
        path end-to-end and pins the unified unset-default (which restores this
        site's pre-epic baseball.localhost host, coherent with the WebAuthn
        origin). Reverting it to an inline read with a different default fails here.
        """
        email = "unsetdefault@example.com"
        _insert_user(db, email)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            os.environ.pop("APP_URL", None)
            with patch(
                "src.api.routes.auth.send_magic_link_email",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_send:
                with TestClient(app, cookies=_CSRF_COOKIES) as client:
                    client.post("/auth/login", data={"email": email, "csrf_token": _CSRF})

        url_arg = mock_send.call_args[0][1]
        assert url_arg.startswith("http://baseball.localhost:8001/auth/verify?token=")


# ---------------------------------------------------------------------------
# GET /auth/verify tests (AC-17d, AC-17e, AC-17f)
# ---------------------------------------------------------------------------


class TestVerifyToken:
    """Magic-link verify flows -- GET/POST split (E-254-02 AC-1..AC-5).

    GET /auth/verify is side-effect-free (renders an interstitial); the atomic
    single-use consume + session creation moved to a CSRF-protected POST, so a
    mail-provider link scanner's GET prefetch can no longer burn the token or
    receive a live session.
    """

    def test_get_valid_token_renders_interstitial_no_consume(self, db: Path) -> None:
        """AC-1: GET valid token -> interstitial form (token + csrf), NO consume,
        NO session cookie, token row still present."""
        user_id = _insert_user(db, "verify@example.com")
        raw_token = _insert_magic_token(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                response = client.get(f"/auth/verify?token={raw_token}")

        assert response.status_code == 200
        # The interstitial embeds the live token, so it must not be cached by a
        # shared/intermediary cache (E-254-02 defense-in-depth).
        assert response.headers.get("cache-control") == "no-store"
        # No session set by the side-effect-free GET.
        assert "session" not in response.cookies
        # Interstitial form carries the token and the CSRF token as hidden fields.
        assert 'name="token"' in response.text
        assert raw_token in response.text
        assert 'name="csrf_token"' in response.text
        assert 'action="/auth/verify"' in response.text
        assert 'method="post"' in response.text.lower()
        # Token row is NOT consumed by the GET.
        conn = sqlite3.connect(str(db))
        count = conn.execute(
            "SELECT COUNT(*) FROM magic_link_tokens WHERE token = ?",
            (hash_token(raw_token),),
        ).fetchone()[0]
        conn.close()
        assert count == 1

    def test_post_valid_token_creates_session_and_redirects(self, db: Path) -> None:
        """AC-3: POST valid token + CSRF -> consume, session, redirect.

        A user with no passkeys is redirected to the passkey prompt interstitial;
        a user with passkeys is redirected directly to /admin/reports.
        """
        user_id = _insert_user(db, "verifypost@example.com")
        raw_token = _insert_magic_token(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                response = client.post(
                    "/auth/verify",
                    data={"token": raw_token, "csrf_token": _CSRF},
                )

        assert response.status_code == 302
        location = response.headers["location"]
        assert "/admin/reports" in location or "/auth/passkey/prompt" in location
        assert "/dashboard" not in location

    def test_post_valid_token_sets_session_cookie(self, db: Path) -> None:
        """AC-3: POST valid token sets the session cookie."""
        user_id = _insert_user(db, "cookie@example.com")
        raw_token = _insert_magic_token(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                response = client.post(
                    "/auth/verify",
                    data={"token": raw_token, "csrf_token": _CSRF},
                )

        assert "session" in response.cookies

    def test_post_valid_token_inserts_session_row(self, db: Path) -> None:
        """AC-3: POST valid token inserts a row in the sessions table."""
        user_id = _insert_user(db, "sessrow@example.com")
        raw_token = _insert_magic_token(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                client.post(
                    "/auth/verify",
                    data={"token": raw_token, "csrf_token": _CSRF},
                )

        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 1

    def test_post_valid_token_is_deleted_after_use(self, db: Path) -> None:
        """AC-3: POST valid token deletes the magic_link_tokens row (single-use)."""
        user_id = _insert_user(db, "markused@example.com")
        raw_token = _insert_magic_token(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                client.post(
                    "/auth/verify",
                    data={"token": raw_token, "csrf_token": _CSRF},
                )

        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM magic_link_tokens WHERE token = ?",
            (hash_token(raw_token),),
        )
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 0  # Row was deleted on use

    def test_post_without_csrf_rejected_before_consume(self, db: Path) -> None:
        """AC-5: POST without a valid CSRF token is rejected (403) and the token
        is NOT consumed (no session created)."""
        user_id = _insert_user(db, "nocsrf@example.com")
        raw_token = _insert_magic_token(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            # No csrf_token cookie/field -> CSRFMiddleware rejects with 403.
            with TestClient(app, follow_redirects=False) as client:
                response = client.post("/auth/verify", data={"token": raw_token})

        assert response.status_code == 403
        conn = sqlite3.connect(str(db))
        token_count = conn.execute(
            "SELECT COUNT(*) FROM magic_link_tokens WHERE token = ?",
            (hash_token(raw_token),),
        ).fetchone()[0]
        session_count = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        conn.close()
        assert token_count == 1  # not consumed
        assert session_count == 0  # no session

    def test_get_expired_token_shows_error_no_delete(self, db: Path) -> None:
        """AC-2: GET expired token renders the error page and does NOT delete the
        row (the side-effect-free GET performs no writes for any token state)."""
        user_id = _insert_user(db, "expired@example.com")
        raw_token = _insert_magic_token(db, user_id, expired=True)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
                response = client.get(f"/auth/verify?token={raw_token}")

        assert response.status_code == 400
        assert "invalid or has expired" in response.text.lower()
        # The verify-error response on the GET auth path is also no-store.
        assert response.headers.get("cache-control") == "no-store"
        # The GET must NOT delete the expired row (no side effects).
        conn = sqlite3.connect(str(db))
        count = conn.execute(
            "SELECT COUNT(*) FROM magic_link_tokens WHERE token = ?",
            (hash_token(raw_token),),
        ).fetchone()[0]
        conn.close()
        assert count == 1

    def test_used_token_shows_error_page(self, db: Path) -> None:
        """AC-4: after a POST consumes the token, a second POST is rejected.

        After first use the token row is deleted, so a second attempt gets
        'not found' -> same verify_error.html response.
        """
        user_id = _insert_user(db, "alreadyused@example.com")
        raw_token = _insert_magic_token(db, user_id)

        # First use (POST) consumes (deletes) the token.
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                client.post(
                    "/auth/verify",
                    data={"token": raw_token, "csrf_token": _CSRF},
                )

        # Second attempt -- token is gone.
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
                response = client.post(
                    "/auth/verify",
                    data={"token": raw_token, "csrf_token": _CSRF},
                )

        assert "invalid or has expired" in response.text.lower()

    def test_get_nonexistent_token_shows_error_page(self, db: Path) -> None:
        """GET non-existent token renders verify_error.html."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
                response = client.get("/auth/verify?token=doesnotexisttoken123456789012")

        assert "invalid or has expired" in response.text.lower()

    def test_get_missing_token_param_shows_error_page(self, db: Path) -> None:
        """GET with a missing token parameter renders verify_error.html."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
                response = client.get("/auth/verify")

        assert response.status_code in (400, 422, 200)
        # Either error page or validation error -- either is acceptable

    def test_post_used_token_cannot_be_reused(self, db: Path) -> None:
        """AC-4: a valid token cannot be POST-consumed twice."""
        user_id = _insert_user(db, "reuse@example.com")
        raw_token = _insert_magic_token(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                # First use -- should succeed
                response1 = client.post(
                    "/auth/verify",
                    data={"token": raw_token, "csrf_token": _CSRF},
                )
                assert response1.status_code == 302

            with TestClient(app, cookies=_CSRF_COOKIES) as client:
                # Second use -- should fail (token was deleted)
                response2 = client.post(
                    "/auth/verify",
                    data={"token": raw_token, "csrf_token": _CSRF},
                )
                assert "invalid or has expired" in response2.text.lower()


# ---------------------------------------------------------------------------
# Logout tests (AC-17i)
# ---------------------------------------------------------------------------


class TestLogout:
    """POST /auth/logout clears session (AC-17i)."""

    def test_logout_redirects_to_login(self, db: Path) -> None:
        """POST /auth/logout redirects to /auth/login (AC-17i)."""
        user_id = _insert_user(db, "logout@example.com")
        raw_token = _insert_session(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token, "csrf_token": _CSRF},
            ) as client:
                response = client.post("/auth/logout", data={"csrf_token": _CSRF})

        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]

    def test_logout_deletes_session_from_db(self, db: Path) -> None:
        """POST /auth/logout removes the session row from the DB (AC-17i)."""
        user_id = _insert_user(db, "logoutdb@example.com")
        raw_token = _insert_session(db, user_id)
        session_id = hash_token(raw_token)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token, "csrf_token": _CSRF},
            ) as client:
                client.post("/auth/logout", data={"csrf_token": _CSRF})

        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 0

    def test_logout_clears_cookie(self, db: Path) -> None:
        """POST /auth/logout clears the session cookie (AC-17i)."""
        user_id = _insert_user(db, "logoutcookie@example.com")
        raw_token = _insert_session(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token, "csrf_token": _CSRF},
            ) as client:
                response = client.post("/auth/logout", data={"csrf_token": _CSRF})

        # Cookie should be cleared (max_age=0 or empty value)
        set_cookie = response.headers.get("set-cookie", "")
        assert "session" in set_cookie

    def test_logout_without_session_still_redirects(self, db: Path) -> None:
        """POST /auth/logout without session cookie still redirects to /auth/login."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                response = client.post("/auth/logout", data={"csrf_token": _CSRF})

        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]


# ---------------------------------------------------------------------------
# Session cookie properties (AC-7)
# ---------------------------------------------------------------------------


class TestSessionCookieProperties:
    """Session cookie has correct flags (AC-7)."""

    def test_session_cookie_is_httponly(self, db: Path) -> None:
        """Verify cookie after POST verify contains HttpOnly flag."""
        user_id = _insert_user(db, "cookieflags@example.com")
        raw_token = _insert_magic_token(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db), "APP_ENV": "development"}):
            with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                response = client.post(
                    "/auth/verify",
                    data={"token": raw_token, "csrf_token": _CSRF},
                )

        # The session Set-Cookie is emitted alongside the CSRF cookie; select it.
        session_cookie = next(
            c for c in response.headers.get_list("set-cookie") if c.startswith("session=")
        ).lower()
        assert "httponly" in session_cookie

    def test_session_cookie_has_max_age(self, db: Path) -> None:
        """Verify cookie contains Max-Age=604800 (7 days)."""
        user_id = _insert_user(db, "maxage@example.com")
        raw_token = _insert_magic_token(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db), "APP_ENV": "development"}):
            with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                response = client.post(
                    "/auth/verify",
                    data={"token": raw_token, "csrf_token": _CSRF},
                )

        session_cookie = next(
            c for c in response.headers.get_list("set-cookie") if c.startswith("session=")
        ).lower()
        assert "max-age=604800" in session_cookie

    def test_session_cookie_samesite_lax(self, db: Path) -> None:
        """Verify cookie contains SameSite=Lax."""
        user_id = _insert_user(db, "samesite@example.com")
        raw_token = _insert_magic_token(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db), "APP_ENV": "development"}):
            with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                response = client.post(
                    "/auth/verify",
                    data={"token": raw_token, "csrf_token": _CSRF},
                )

        session_cookie = next(
            c for c in response.headers.get_list("set-cookie") if c.startswith("session=")
        ).lower()
        assert "samesite=lax" in session_cookie


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
                with TestClient(app, cookies=_CSRF_COOKIES) as client:
                    client.post("/auth/login", data={"email": email, "csrf_token": _CSRF})

        # Prior token should be gone.
        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM magic_link_tokens WHERE token = ?",
            (hash_token(prior_raw),),
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
                with TestClient(app, cookies=_CSRF_COOKIES) as client:
                    client.post("/auth/login", data={"email": email, "csrf_token": _CSRF})

        # Attempting to verify the prior (now-deleted) token must fail.
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
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
                with TestClient(app, cookies=_CSRF_COOKIES) as client:
                    client.post("/auth/login", data={"email": email, "csrf_token": _CSRF})

        assert len(captured_url) == 1
        new_token = captured_url[0].split("token=")[-1]

        # The new token must verify successfully (via the POST consume path).
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                response = client.post(
                    "/auth/verify",
                    data={"token": new_token, "csrf_token": _CSRF},
                )

        assert response.status_code == 302
        location = response.headers["location"]
        # E-238-05: retargeted off the quarantined /dashboard to /admin/reports.
        assert "/admin/reports" in location or "/auth/passkey/prompt" in location
        assert "/dashboard" not in location

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
                with TestClient(app, cookies=_CSRF_COOKIES) as client:
                    client.post("/auth/login", data={"email": email, "csrf_token": _CSRF})

        assert len(captured_url) == 1
        token_b_raw = captured_url[0].split("token=")[-1]

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
                # Verify A -- must fail (deleted by B issuance). A POST consume of
                # the deleted token hits the not-found branch -> error page.
                response_a = client.post(
                    "/auth/verify",
                    data={"token": token_a_raw, "csrf_token": _CSRF},
                )
            assert "invalid or has expired" in response_a.text.lower()

            with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                # Verify B -- must succeed.
                response_b = client.post(
                    "/auth/verify",
                    data={"token": token_b_raw, "csrf_token": _CSRF},
                )
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
            (hash_token(secrets.token_urlsafe(32)), user_id),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch(
                "src.api.routes.auth.send_magic_link_email",
                new_callable=AsyncMock,
                return_value=True,
            ):
                with TestClient(app, cookies=_CSRF_COOKIES) as client:
                    client.post("/auth/login", data={"email": email, "csrf_token": _CSRF})

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
                with TestClient(app, cookies=_CSRF_COOKIES) as client:
                    response = client.post("/auth/login", data={"email": email, "csrf_token": _CSRF})

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
                with TestClient(app, cookies=_CSRF_COOKIES) as client:
                    response = client.post("/auth/login", data={"email": email, "csrf_token": _CSRF})

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
                with TestClient(app, cookies=_CSRF_COOKIES) as client:
                    response = client.post("/auth/login", data={"email": email, "csrf_token": _CSRF})

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
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
                response = client.post(
                    "/auth/login", data={"email": "nobody@example.com", "csrf_token": _CSRF}
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
                with TestClient(app, cookies=_CSRF_COOKIES) as client:
                    client.post("/auth/login", data={"email": email, "csrf_token": _CSRF})

        mock_send.assert_called_once()


# ---------------------------------------------------------------------------
# E-238-05: Navigation retarget canary
#
# The /dashboard surface was removed in E-239.
# Every auth-success / already-authenticated redirect must now land on
# /admin/reports (the live reports flow), never on /dashboard. These tests
# are the testable half of the AC-8 canary: each retargeted redirect's
# Location contains no /dashboard, and no redirect loop occurs.
# ---------------------------------------------------------------------------


def _insert_passkey_credential(db_path: Path, user_id: int) -> None:
    """Insert a minimal passkey credential row so the user 'has passkeys'."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT INTO passkey_credentials (user_id, credential_id, public_key, sign_count)
        VALUES (?, ?, ?, 0)
        """,
        (user_id, secrets.token_bytes(32), secrets.token_bytes(64)),
    )
    conn.commit()
    conn.close()


class TestNavRetargetCanaryE238:
    """E-238-05: auth redirects retarget off the quarantined /dashboard."""

    def test_root_redirect_targets_reports_not_dashboard(self, db: Path) -> None:
        """GET / redirects to /admin/reports, never /dashboard (AC-2)."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get("/")
        assert response.status_code == 302
        assert response.headers["location"] == "/admin/reports"
        assert "/dashboard" not in response.headers["location"]

    def test_login_when_already_authenticated_redirects_to_reports(self, db: Path) -> None:
        """GET /auth/login with a valid session redirects to /admin/reports (AC-1)."""
        user_id = _insert_user(db, "already@example.com")
        raw_token = _insert_session(db, user_id)
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token, "csrf_token": _CSRF},
            ) as client:
                response = client.get("/auth/login")
        assert response.status_code == 302
        assert response.headers["location"] == "/admin/reports"
        assert "/dashboard" not in response.headers["location"]

    def test_verify_with_passkeys_redirects_to_reports(self, db: Path) -> None:
        """POST /verify for a user WITH passkeys redirects to /admin/reports (AC-1).

        This exercises the magic-link success ``has_passkeys`` branch in
        auth.py (the FIVE-site inventory) -- the branch that previously sent
        the operator to the quarantined /dashboard. E-254-02 moved the consume +
        redirect to POST /auth/verify.
        """
        user_id = _insert_user(db, "haspk@example.com")
        _insert_passkey_credential(db, user_id)
        raw_token = _insert_magic_token(db, user_id)
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                response = client.post(
                    "/auth/verify",
                    data={"token": raw_token, "csrf_token": _CSRF},
                )
        assert response.status_code == 302
        location = response.headers["location"]
        assert location == "/admin/reports"
        assert "/dashboard" not in location

    def test_no_redirect_loop_root_to_reports_to_login(self, db: Path) -> None:
        """Unauthenticated GET / terminates at /auth/login with no loop, no /dashboard.

        The hop chain is / -> /admin/reports -> /auth/login (the reports page
        requires auth; the middleware redirects unauthenticated callers to
        login). The chain must terminate (no infinite loop) and no hop may
        target the quarantined /dashboard.
        """
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, follow_redirects=True) as client:
                # TestClient raises on excessive redirects; completing proves
                # there is no loop.
                response = client.get("/")
        assert response.status_code == 200
        assert response.url.path == "/auth/login"
        # No hop in the redirect chain targeted /dashboard.
        for hop in response.history:
            assert "/dashboard" not in hop.headers.get("location", "")


# ---------------------------------------------------------------------------
# Session cookie Secure flag (E-254-01 AC-3)
# ---------------------------------------------------------------------------


class TestSessionCookieSecureFlag:
    """The session cookie carries Secure only under production APP_ENV (AC-3).

    Exercised through the full middleware stack via a real magic-link verify
    (not dev bypass) so the DEV_USER_EMAIL production guard is not tripped
    (TN-6 cookie-Secure caution). DEV_USER_EMAIL and APP_ENV are removed from
    the ambient env so each case is deterministic.
    """

    def _verify_and_get_session_setcookie(self, db: Path, env: dict[str, str]) -> str:
        user_id = _insert_user(db, "sec@example.com")
        raw_token = _insert_magic_token(db, user_id)
        base = {
            k: v
            for k, v in os.environ.items()
            if k not in ("DEV_USER_EMAIL", "APP_ENV")
        }
        base.update(env)
        base["DATABASE_PATH"] = str(db)
        # E-254-02: the session cookie is set on the CSRF-protected POST consume.
        with patch.dict("os.environ", base, clear=True):
            with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                response = client.post(
                    "/auth/verify",
                    data={"token": raw_token, "csrf_token": _CSRF},
                )
        set_cookies = response.headers.get_list("set-cookie")
        session_cookies = [c for c in set_cookies if c.startswith("session=")]
        assert session_cookies, f"no session Set-Cookie header found in {set_cookies}"
        return session_cookies[0]

    def test_session_cookie_secure_in_production(self, db: Path) -> None:
        """APP_ENV=production -> session cookie carries Secure."""
        header = self._verify_and_get_session_setcookie(db, {"APP_ENV": "production"})
        assert "Secure" in header

    def test_session_cookie_secure_production_whitespace_variant(self, db: Path) -> None:
        """APP_ENV=' production ' (whitespace variant) still carries Secure (AC-1/AC-3)."""
        header = self._verify_and_get_session_setcookie(db, {"APP_ENV": " production "})
        assert "Secure" in header

    def test_session_cookie_not_secure_when_unset(self, db: Path) -> None:
        """APP_ENV unset -> session cookie does NOT carry Secure."""
        header = self._verify_and_get_session_setcookie(db, {})
        assert "Secure" not in header


# ---------------------------------------------------------------------------
# Login-timing equalization (E-254-03 AC-3)
# ---------------------------------------------------------------------------


class TestLoginTimingEqualization:
    """POST /auth/login does not reveal registration via response timing (AC-3).

    Behavioral/structural only -- NO wall-clock assertions (TN-6/TN-8). The
    fresh-known issuance path and the unknown path must (a) return the
    byte-identical confirmation page and (b) invoke the equalizing op
    (`hash_token`) an EQUAL number of times, so a do-nothing-unknown
    implementation fails call-count parity. The Mailgun send is scheduled as a
    BackgroundTask (not awaited inline) and only on the known path.
    """

    def _post_login(self, db: Path, email: str) -> "object":
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch(
                "src.api.routes.auth.send_magic_link_email",
                new_callable=AsyncMock,
                return_value=True,
            ):
                with TestClient(app, cookies=_CSRF_COOKIES) as client:
                    return client.post(
                        "/auth/login",
                        data={"email": email, "csrf_token": _CSRF},
                    )

    def test_known_and_unknown_return_identical_page(self, db: Path) -> None:
        """AC-3: fresh-known and unknown emails return the byte-identical 200 page."""
        _insert_user(db, "known-fresh@example.com")

        known = self._post_login(db, "known-fresh@example.com")
        unknown = self._post_login(db, "never-registered@example.com")

        assert known.status_code == 200
        assert unknown.status_code == 200
        assert known.text == unknown.text

    def test_equalizing_op_call_parity(self, db: Path) -> None:
        """AC-3: `hash_token` is invoked an EQUAL number of times on the
        fresh-known issuance path and the unknown path (a do-nothing unknown
        branch would fail this)."""
        _insert_user(db, "known-parity@example.com")

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch(
                "src.api.routes.auth.send_magic_link_email",
                new_callable=AsyncMock,
                return_value=True,
            ):
                with patch(
                    "src.api.routes.auth.hash_token", wraps=hash_token
                ) as mock_hash:
                    with TestClient(app, cookies=_CSRF_COOKIES) as client:
                        client.post(
                            "/auth/login",
                            data={"email": "known-parity@example.com", "csrf_token": _CSRF},
                        )
                    known_calls = mock_hash.call_count
                    mock_hash.reset_mock()
                    with TestClient(app, cookies=_CSRF_COOKIES) as client:
                        client.post(
                            "/auth/login",
                            data={"email": "unknown-parity@example.com", "csrf_token": _CSRF},
                        )
                    unknown_calls = mock_hash.call_count

        assert known_calls == unknown_calls
        assert known_calls == 1  # exactly one hash_token per branch

    def test_send_scheduled_as_background_task_only_for_known(self, db: Path) -> None:
        """AC-3: the Mailgun send is scheduled as a BackgroundTask (not awaited
        inline) and only on the known path; the unknown path schedules nothing."""
        _insert_user(db, "known-bg@example.com")

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch(
                "src.api.routes.auth.send_magic_link_email",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_send:
                with patch(
                    "src.api.routes.auth.BackgroundTask", wraps=BackgroundTask
                ) as mock_bg:
                    # Known email -> send scheduled via BackgroundTask exactly once.
                    with TestClient(app, cookies=_CSRF_COOKIES) as client:
                        client.post(
                            "/auth/login",
                            data={"email": "known-bg@example.com", "csrf_token": _CSRF},
                        )
                    assert mock_bg.call_count == 1
                    assert mock_bg.call_args.args[0] is mock_send
                    mock_bg.reset_mock()
                    # Unknown email -> no BackgroundTask scheduled.
                    with TestClient(app, cookies=_CSRF_COOKIES) as client:
                        client.post(
                            "/auth/login",
                            data={"email": "unknown-bg@example.com", "csrf_token": _CSRF},
                        )
                    assert mock_bg.call_count == 0
