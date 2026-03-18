# synthetic-test-data
"""Tests for CSRF protection (E-125-01).

Tests cover:
- AC-2: POST without valid CSRF token receives 403
- AC-4: Health endpoint excluded from CSRF validation
- AC-5: POST requests without a valid CSRF token receive 403
- AC-6: POST requests with a valid CSRF token succeed
- AC-7: Logout is POST with CSRF validation
- AC-8: JS-initiated POST with X-CSRF-Token header succeeds

Run with:
    pytest tests/test_csrf.py -v
"""

from __future__ import annotations

import secrets
import sqlite3
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from migrations.apply_migrations import run_migrations  # noqa: E402
from src.api.auth import hash_token  # noqa: E402
from src.api.csrf import CSRF_COOKIE_NAME, CSRF_FORM_FIELD, CSRF_HEADER  # noqa: E402
from src.api.main import app  # noqa: E402

_CSRF_TOKEN = "test-csrf-token-e125"

_SEED_SQL = """
    INSERT OR IGNORE INTO programs (program_id, name, program_type) VALUES
        ('lsb-hs', 'Lincoln Standing Bear HS', 'hs');
    INSERT OR IGNORE INTO teams (name, membership_type, classification) VALUES
        ('LSB Varsity 2026', 'member', 'varsity');
"""


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test_csrf.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SEED_SQL)
    conn.commit()
    conn.close()
    return db_path


def _insert_user(db_path: Path, email: str) -> int:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("INSERT INTO users (email) VALUES (?)", (email,))
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def _insert_session(db_path: Path, user_id: int) -> str:
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


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    return _make_db(tmp_path)


# ---------------------------------------------------------------------------
# AC-5: POST without CSRF token returns 403
# ---------------------------------------------------------------------------


class TestCSRFRejection:
    """POST requests without a valid CSRF token receive 403 (AC-5)."""

    def test_post_without_csrf_cookie_returns_403(self, db: Path) -> None:
        """POST without csrf_token cookie returns 403."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app) as client:
                response = client.post("/auth/login", data={"email": "x@x.com"})
        assert response.status_code == 403

    def test_post_without_csrf_form_field_returns_403(self, db: Path) -> None:
        """POST with csrf cookie but no form field returns 403."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, cookies={CSRF_COOKIE_NAME: _CSRF_TOKEN}) as client:
                response = client.post("/auth/login", data={"email": "x@x.com"})
        assert response.status_code == 403

    def test_post_with_wrong_csrf_token_returns_403(self, db: Path) -> None:
        """POST with mismatched csrf tokens returns 403."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, cookies={CSRF_COOKIE_NAME: _CSRF_TOKEN}) as client:
                response = client.post(
                    "/auth/login",
                    data={"email": "x@x.com", CSRF_FORM_FIELD: "wrong-token"},
                )
        assert response.status_code == 403

    def test_admin_post_without_csrf_returns_403(self, db: Path) -> None:
        """Admin POST without CSRF token returns 403 (not 302 redirect)."""
        user_id = _insert_user(db, "admin@example.com")
        session_token = _insert_session(db, user_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": session_token},
            ) as client:
                response = client.post(
                    "/admin/users", data={"email": "new@example.com"}
                )
        assert response.status_code == 403

    def test_json_post_without_csrf_header_returns_403(self, db: Path) -> None:
        """JSON POST without X-CSRF-Token header returns 403."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app, cookies={CSRF_COOKIE_NAME: _CSRF_TOKEN}) as client:
                response = client.post(
                    "/auth/passkey/login/verify",
                    json={"id": "fake", "rawId": "fake"},
                )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# AC-6: POST with valid CSRF token succeeds
# ---------------------------------------------------------------------------


class TestCSRFAcceptance:
    """POST requests with a valid CSRF token succeed (AC-6)."""

    def test_post_login_with_csrf_succeeds(self, db: Path) -> None:
        """POST /auth/login with valid CSRF cookie+field returns 200."""
        _insert_user(db, "test@example.com")

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with patch(
                "src.api.routes.auth.send_magic_link_email",
                new_callable=AsyncMock,
                return_value=True,
            ):
                with TestClient(
                    app, cookies={CSRF_COOKIE_NAME: _CSRF_TOKEN}
                ) as client:
                    response = client.post(
                        "/auth/login",
                        data={
                            "email": "test@example.com",
                            CSRF_FORM_FIELD: _CSRF_TOKEN,
                        },
                    )
        assert response.status_code == 200

    def test_admin_post_with_csrf_succeeds(self, db: Path) -> None:
        """Admin POST with valid CSRF token creates user (not 403)."""
        user_id = _insert_user(db, "admin@example.com")
        session_token = _insert_session(db, user_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={
                    "session": session_token,
                    CSRF_COOKIE_NAME: _CSRF_TOKEN,
                },
            ) as client:
                response = client.post(
                    "/admin/users",
                    data={
                        "email": "new@example.com",
                        CSRF_FORM_FIELD: _CSRF_TOKEN,
                    },
                )
        assert response.status_code == 303

    def test_json_post_with_csrf_header_succeeds(self, db: Path) -> None:
        """JSON POST with X-CSRF-Token header passes CSRF validation.

        The passkey endpoint will return 400/401 (no valid credential),
        but NOT 403 (CSRF passed).
        """
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(
                app, cookies={CSRF_COOKIE_NAME: _CSRF_TOKEN}
            ) as client:
                response = client.post(
                    "/auth/passkey/login/verify",
                    json={"id": "fake", "rawId": "fake", "response": {}},
                    headers={CSRF_HEADER: _CSRF_TOKEN},
                )
        # Should be 400 (bad payload) not 403 (CSRF)
        assert response.status_code != 403


# ---------------------------------------------------------------------------
# AC-4: Health endpoint excluded
# ---------------------------------------------------------------------------


class TestCSRFExemptions:
    """Health endpoint is excluded from CSRF validation (AC-4)."""

    def test_health_endpoint_excluded(self, db: Path) -> None:
        """GET /health does not set a CSRF cookie."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app) as client:
                response = client.get("/health")
        assert CSRF_COOKIE_NAME not in response.cookies


# ---------------------------------------------------------------------------
# AC-7: Logout is POST with CSRF
# ---------------------------------------------------------------------------


class TestLogoutPostCSRF:
    """GET /auth/logout no longer exists; POST /auth/logout requires CSRF (AC-7)."""

    def test_get_logout_returns_405(self, db: Path) -> None:
        """GET /auth/logout returns 405 Method Not Allowed."""
        user_id = _insert_user(db, "logout@example.com")
        session_token = _insert_session(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": session_token},
            ) as client:
                response = client.get("/auth/logout")
        assert response.status_code == 405

    def test_post_logout_without_csrf_returns_403(self, db: Path) -> None:
        """POST /auth/logout without CSRF token returns 403."""
        user_id = _insert_user(db, "logout2@example.com")
        session_token = _insert_session(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": session_token},
            ) as client:
                response = client.post("/auth/logout")
        assert response.status_code == 403

    def test_post_logout_with_csrf_redirects(self, db: Path) -> None:
        """POST /auth/logout with valid CSRF token redirects to /auth/login."""
        user_id = _insert_user(db, "logout3@example.com")
        session_token = _insert_session(db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={
                    "session": session_token,
                    CSRF_COOKIE_NAME: _CSRF_TOKEN,
                },
            ) as client:
                response = client.post(
                    "/auth/logout",
                    data={CSRF_FORM_FIELD: _CSRF_TOKEN},
                )
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]


# ---------------------------------------------------------------------------
# AC-1, AC-3: CSRF cookie set on GET pages
# ---------------------------------------------------------------------------


class TestCSRFCookieDelivery:
    """GET requests to form pages deliver the CSRF token (AC-3)."""

    def test_login_page_sets_csrf_cookie(self, db: Path) -> None:
        """GET /auth/login sets a csrf_token cookie."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app) as client:
                response = client.get("/auth/login")
        assert CSRF_COOKIE_NAME in response.cookies
        assert len(response.cookies[CSRF_COOKIE_NAME]) > 20

    def test_login_page_includes_csrf_hidden_field(self, db: Path) -> None:
        """GET /auth/login HTML includes hidden csrf_token field."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(db)}):
            with TestClient(app) as client:
                response = client.get("/auth/login")
        assert 'name="csrf_token"' in response.text

    def test_admin_page_sets_csrf_cookie(self, db: Path) -> None:
        """GET /admin/users sets a csrf_token cookie."""
        user_id = _insert_user(db, "admin@example.com")
        session_token = _insert_session(db, user_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(
                app, cookies={"session": session_token}
            ) as client:
                response = client.get("/admin/users")
        assert CSRF_COOKIE_NAME in response.cookies
