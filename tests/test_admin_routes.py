# synthetic-test-data
"""Tests for E-127-04: Admin Nav Discoverability.

Covers:
- AC-1: "Admin" link in top nav bar pointing to /admin/teams
- AC-2: Bottom coaching nav suppressed on admin pages; present on non-admin pages
- AC-3: Empty-state message links to /admin/teams in dev mode (DEV_USER_EMAIL set)
- AC-4: Admin link is on the right side of the nav bar (styled text-blue-200)
- AC-5: Existing admin sub-nav (Users/Teams/Opponents) continues to function

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
    """AC-1: Top nav contains an Admin link pointing to /admin/teams."""

    def test_admin_page_has_admin_link(self, tmp_path: Path) -> None:
        """GET /admin/teams HTML includes Admin link to /admin/teams in top nav."""
        db_path = _make_db(tmp_path)
        email = "admin@example.com"
        token = _admin_client(db_path, email)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db_path), "ADMIN_EMAIL": email}):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                resp = client.get("/admin/teams")

        assert resp.status_code == 200
        html = resp.text
        assert 'href="/admin/teams"' in html
        assert ">Admin<" in html

    def test_dashboard_page_has_admin_link(self, tmp_path: Path) -> None:
        """GET /dashboard HTML also includes the Admin link (link is in base.html)."""
        db_path = _make_db(tmp_path)
        team_id = _insert_member_team(db_path)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            # Insert user and assign team so dashboard renders with data
            conn = sqlite3.connect(str(db_path))
            user_id = conn.execute(
                "INSERT INTO users (email) VALUES (?) RETURNING id", ("dev@example.com",)
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO user_team_access (user_id, team_id) VALUES (?, ?)",
                (user_id, team_id),
            )
            conn.commit()
            conn.close()

            with TestClient(app) as client:
                resp = client.get("/dashboard")

        assert resp.status_code == 200
        html = resp.text
        assert 'href="/admin/teams"' in html
        assert ">Admin<" in html


# ---------------------------------------------------------------------------
# AC-2: Bottom coaching nav suppressed on admin pages
# ---------------------------------------------------------------------------


class TestBottomNavSuppression:
    """AC-2: Bottom coaching nav not rendered on admin pages; present on dashboard."""

    def test_bottom_nav_absent_on_admin_teams(self, tmp_path: Path) -> None:
        """Bottom nav (Batting/Pitching/Games/Opponents) absent on GET /admin/teams."""
        db_path = _make_db(tmp_path)
        email = "admin@example.com"
        token = _admin_client(db_path, email)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db_path), "ADMIN_EMAIL": email}):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                resp = client.get("/admin/teams")

        assert resp.status_code == 200
        html = resp.text
        # Bottom coaching nav links should not be present
        assert 'href="/dashboard"' not in html or ">Batting<" not in html
        # More specific: the bottom nav tab for Batting/Pitching should be absent
        assert ">Batting<" not in html
        assert ">Pitching<" not in html

    def test_bottom_nav_present_on_dashboard(self, tmp_path: Path) -> None:
        """Bottom nav (Batting/Pitching/Games/Opponents) is present on dashboard pages."""
        db_path = _make_db(tmp_path)
        team_id = _insert_member_team(db_path)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            conn = sqlite3.connect(str(db_path))
            user_id = conn.execute(
                "INSERT INTO users (email) VALUES (?) RETURNING id", ("dev@example.com",)
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO user_team_access (user_id, team_id) VALUES (?, ?)",
                (user_id, team_id),
            )
            conn.commit()
            conn.close()

            with TestClient(app) as client:
                resp = client.get("/dashboard")

        assert resp.status_code == 200
        html = resp.text
        assert ">Batting<" in html
        assert ">Pitching<" in html
        assert ">Games<" in html
        assert ">Opponents<" in html

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
# AC-3: Dev-mode empty-state links to /admin/teams
# ---------------------------------------------------------------------------


class TestDevModeEmptyState:
    """AC-3: Empty-state message links to /admin/teams when DEV_USER_EMAIL is set."""

    def test_empty_state_with_dev_mode_shows_admin_link(self, tmp_path: Path) -> None:
        """No team assignments + DEV_USER_EMAIL → empty state includes /admin/teams link."""
        db_path = _make_db(tmp_path)
        # No team assignments for dev user -- permitted_teams will be empty

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            with TestClient(app) as client:
                resp = client.get("/dashboard")

        assert resp.status_code == 200
        html = resp.text
        assert 'href="/admin/teams"' in html
        assert "Add a team in Admin" in html

    def test_empty_state_without_dev_mode_shows_contact_message(self, tmp_path: Path) -> None:
        """No team assignments + session auth (no DEV_USER_EMAIL) → 'Contact your administrator'."""
        db_path = _make_db(tmp_path)
        email = "coach@example.com"
        user_id = _insert_user(db_path, email)
        token = _insert_session(db_path, user_id)
        # No team assignments

        with patch.dict("os.environ", {"DATABASE_PATH": str(db_path)}):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                resp = client.get("/dashboard")

        assert resp.status_code == 200
        html = resp.text
        assert "Contact your administrator" in html
        assert "Add a team in Admin" not in html


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
                resp = client.get("/admin/teams")

        html = resp.text
        # Check the Admin link has the correct Tailwind classes
        assert 'class="text-blue-200 hover:text-white"' in html or (
            "text-blue-200" in html and "hover:text-white" in html
        )


# ---------------------------------------------------------------------------
# AC-5: Admin sub-nav continues to function
# ---------------------------------------------------------------------------


class TestAdminSubNav:
    """AC-5: Existing admin sub-nav (Users/Teams/Opponents) still renders on admin pages."""

    def test_admin_teams_has_subnav(self, tmp_path: Path) -> None:
        """GET /admin/teams includes Users/Teams/Opponents sub-nav tabs."""
        db_path = _make_db(tmp_path)
        email = "admin@example.com"
        token = _admin_client(db_path, email)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db_path), "ADMIN_EMAIL": email}):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                resp = client.get("/admin/teams")

        assert resp.status_code == 200
        html = resp.text
        assert 'href="/admin/users"' in html
        assert 'href="/admin/teams"' in html
        assert 'href="/admin/opponents"' in html

    def test_admin_users_has_subnav(self, tmp_path: Path) -> None:
        """GET /admin/users includes Users/Teams/Opponents sub-nav tabs."""
        db_path = _make_db(tmp_path)
        email = "admin@example.com"
        token = _admin_client(db_path, email)

        with patch.dict("os.environ", {"DATABASE_PATH": str(db_path), "ADMIN_EMAIL": email}):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                resp = client.get("/admin/users")

        assert resp.status_code == 200
        html = resp.text
        assert 'href="/admin/users"' in html
        assert 'href="/admin/teams"' in html
        assert 'href="/admin/opponents"' in html
