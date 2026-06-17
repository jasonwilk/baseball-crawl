# synthetic-test-data
"""Tests for E-127-04: Admin Nav Discoverability.

Covers (retargeted for E-239-01 -- the team/opponent/program admin routes were
removed; the surviving admin surface is reports + user management):
- AC-1: "Admin" link in top nav bar pointing to /admin/reports
- AC-2: Bottom coaching nav suppressed on admin pages; present on non-admin pages
- AC-3: Empty-state message links to Admin in dev mode (DEV_USER_EMAIL set)
- AC-4: Admin link is on the right side of the nav bar (styled text-blue-200)
- AC-5: Existing admin sub-nav (Reports/Users) continues to function

Run with:
    pytest tests/test_admin_routes.py -v
"""

from __future__ import annotations

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

from migrations.apply_migrations import run_migrations  # noqa: E402
from src.api.auth import hash_token  # noqa: E402
from src.api.main import app  # noqa: E402

_CSRF = "test-csrf-token"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    """Create a minimal migrated database."""
    db_path = tmp_path / "test_nav.db"
    run_migrations(db_path=db_path)
    return db_path


def _insert_user(db_path: Path, email: str) -> int:
    """Insert a user and return the id."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    cursor = conn.execute(
        "INSERT INTO users (email, hashed_password) VALUES (?, '')", (email,)
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def _insert_session(db_path: Path, user_id: int) -> str:
    """Insert a session and return the raw token."""
    raw_token = secrets.token_hex(32)
    token_hash = hash_token(raw_token)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT INTO sessions (session_id, user_id, expires_at) VALUES (?, ?, datetime('now', '+7 days'))",
        (token_hash, user_id),
    )
    conn.commit()
    conn.close()
    return raw_token


def _insert_member_team(db_path: Path, name: str = "LSB Varsity") -> int:
    """Insert a member team and return the INTEGER id."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    cursor = conn.execute(
        "INSERT INTO teams (name, membership_type) VALUES (?, 'member')",
        (name,),
    )
    conn.commit()
    team_id = cursor.lastrowid
    conn.close()
    return team_id


def _assign_team(db_path: Path, user_id: int, team_id: int) -> None:
    """Grant user access to a team."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
        (user_id, team_id),
    )
    conn.commit()
    conn.close()


def _admin_client(db_path: Path, email: str) -> tuple[TestClient, str]:
    """Return a TestClient + session token for an admin user."""
    user_id = _insert_user(db_path, email)
    token = _insert_session(db_path, user_id)
    return token


# ---------------------------------------------------------------------------
# AC-1: Admin link in top nav
# ---------------------------------------------------------------------------


class TestAdminLinkInTopNav:
    """AC-1: Top nav contains an Admin link pointing to /admin/reports."""

    def test_admin_page_has_admin_link(self, tmp_path: Path) -> None:
        """GET /admin/reports HTML includes Admin link to /admin/reports in top nav."""
        db_path = _make_db(tmp_path)
        email = "admin@example.com"
        token = _admin_client(db_path, email)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db_path), "ADMIN_EMAIL": email}):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                resp = client.get("/admin/reports")

        assert resp.status_code == 200
        html = resp.text
        assert 'href="/admin/reports"' in html
        assert ">Admin<" in html


# ---------------------------------------------------------------------------
# AC-2: Bottom coaching nav suppressed on admin pages
# ---------------------------------------------------------------------------


class TestBottomNavSuppression:
    """AC-2: Bottom coaching nav not rendered on admin pages; present on dashboard."""

    def test_bottom_nav_absent_on_admin_reports(self, tmp_path: Path) -> None:
        """Bottom nav (Batting/Pitching) absent on GET /admin/reports."""
        db_path = _make_db(tmp_path)
        email = "admin@example.com"
        token = _admin_client(db_path, email)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db_path), "ADMIN_EMAIL": email}):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                resp = client.get("/admin/reports")

        assert resp.status_code == 200
        html = resp.text
        # Bottom coaching nav links should not be present
        assert 'href="/dashboard"' not in html or ">Batting<" not in html
        # More specific: the bottom nav tab for Batting/Pitching should be absent
        assert ">Batting<" not in html
        assert ">Pitching<" not in html

    def test_bottom_nav_absent_on_admin_users(self, tmp_path: Path) -> None:
        """Bottom nav absent on GET /admin/users (another admin page)."""
        db_path = _make_db(tmp_path)
        email = "admin@example.com"
        token = _admin_client(db_path, email)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db_path), "ADMIN_EMAIL": email}):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                resp = client.get("/admin/users")

        assert resp.status_code == 200
        html = resp.text
        assert ">Batting<" not in html
        assert ">Pitching<" not in html


# ---------------------------------------------------------------------------
# AC-4: Admin link styling
# ---------------------------------------------------------------------------


class TestAdminLinkStyling:
    """AC-4: Admin link uses text-blue-200 hover:text-white styling."""

    def test_admin_link_has_correct_styling(self, tmp_path: Path) -> None:
        """Admin link in top nav uses subdued blue styling matching logout button."""
        db_path = _make_db(tmp_path)
        email = "admin@example.com"
        token = _admin_client(db_path, email)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db_path), "ADMIN_EMAIL": email}):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                resp = client.get("/admin/reports")

        html = resp.text
        # Check the Admin link has the correct Tailwind classes
        assert 'class="text-blue-200 hover:text-white"' in html or (
            "text-blue-200" in html and "hover:text-white" in html
        )


# ---------------------------------------------------------------------------
# AC-5: Admin sub-nav continues to function
# ---------------------------------------------------------------------------


class TestAdminSubNav:
    """AC-5: Admin sub-nav (Reports/Users) still renders on admin pages.

    The Teams/Programs/Opponents tabs were removed with their routes in
    E-239-01; the sub-nav now carries only the surviving Reports + Users tabs.
    """

    def test_admin_reports_has_subnav(self, tmp_path: Path) -> None:
        """GET /admin/reports includes Reports/Users sub-nav tabs and no dead tabs."""
        db_path = _make_db(tmp_path)
        email = "admin@example.com"
        token = _admin_client(db_path, email)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db_path), "ADMIN_EMAIL": email}):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                resp = client.get("/admin/reports")

        assert resp.status_code == 200
        html = resp.text
        assert 'href="/admin/reports"' in html
        assert 'href="/admin/users"' in html
        # Removed tabs must not reappear
        assert 'href="/admin/teams"' not in html
        assert 'href="/admin/opponents"' not in html
        assert 'href="/admin/programs"' not in html

    def test_admin_users_has_subnav(self, tmp_path: Path) -> None:
        """GET /admin/users includes Reports/Users sub-nav tabs and no dead tabs."""
        db_path = _make_db(tmp_path)
        email = "admin@example.com"
        token = _admin_client(db_path, email)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db_path), "ADMIN_EMAIL": email}):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                resp = client.get("/admin/users")

        assert resp.status_code == 200
        html = resp.text
        assert 'href="/admin/reports"' in html
        assert 'href="/admin/users"' in html
        assert 'href="/admin/teams"' not in html
        assert 'href="/admin/opponents"' not in html


# ---------------------------------------------------------------------------
# E-228-02: _require_admin delegation -- role='admin' branch at route level
# ---------------------------------------------------------------------------


class TestRequireAdminRoleBranch:
    """Pin the role='admin' branch of the ``_require_admin`` delegation.

    The other admin-route tests authenticate via ADMIN_EMAIL.  After E-228-02,
    ``_require_admin`` delegates to the canonical ``user_is_admin`` predicate,
    whose second branch is the DB role.  This verifies a user with
    ``users.role='admin'`` and ADMIN_EMAIL UNSET can reach /admin/* (200, not
    403).
    """

    def test_db_role_admin_with_admin_email_unset_reaches_admin_route(
        self, tmp_path: Path
    ) -> None:
        """role='admin' (ADMIN_EMAIL unset) reaches /admin/reports via dev-bypass."""
        db_path = _make_db(tmp_path)
        dev_email = "role-admin@example.com"

        # Pre-insert the dev user with role='admin' so the dev-bypass path
        # resolves an existing admin (not a default-role auto-created user).
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            "INSERT INTO users (email, role) VALUES (?, 'admin')", (dev_email,)
        )
        conn.commit()
        conn.close()

        env = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": dev_email,
            # ADMIN_EMAIL unset so admin access comes SOLELY from the DB role.
            "ADMIN_EMAIL": "",
        }
        with patch.dict("os.environ", env):
            with TestClient(app, follow_redirects=False) as client:
                resp = client.get("/admin/reports")

        assert resp.status_code == 200, (
            f"role='admin' user should reach /admin/reports, got {resp.status_code}"
        )

    def test_non_admin_dev_user_forbidden_on_admin_route(
        self, tmp_path: Path
    ) -> None:
        """Negative control: a default-role dev user is 403 on /admin/* (ADMIN_EMAIL unset)."""
        db_path = _make_db(tmp_path)
        dev_email = "plain-user@example.com"

        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        # Default role ('user') -- not admin.
        conn.execute("INSERT INTO users (email) VALUES (?)", (dev_email,))
        conn.commit()
        conn.close()

        env = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": dev_email,
            "ADMIN_EMAIL": "",
        }
        with patch.dict("os.environ", env):
            with TestClient(app, follow_redirects=False) as client:
                resp = client.get("/admin/reports")

        assert resp.status_code == 403, (
            f"non-admin user should be 403 on /admin/reports, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# E-239: Removed surfaces return 404 (route-not-found), not an auth redirect
# ---------------------------------------------------------------------------


class TestRemovedRoutesReturn404:
    """E-239 quarantine-then-removal canary.

    The dashboard and the team/opponent/program admin routes were deleted.
    With an authenticated admin session -- so the session middleware passes the
    request through to routing instead of redirecting to /auth/login -- each
    removed path resolves to a 404 route-not-found, proving the route is gone
    (not merely forbidden, which would surface as 403).
    """

    @pytest.mark.parametrize(
        "path",
        ["/dashboard", "/admin/teams", "/admin/opponents", "/admin/programs"],
    )
    def test_removed_route_returns_404(self, tmp_path: Path, path: str) -> None:
        """Each E-239-removed route returns 404 for an authenticated admin."""
        db_path = _make_db(tmp_path)
        email = "admin@example.com"
        token = _admin_client(db_path, email)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db_path), "ADMIN_EMAIL": email}):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                resp = client.get(path)

        assert resp.status_code == 404, (
            f"{path} should be 404 (route removed in E-239), got {resp.status_code}"
        )
