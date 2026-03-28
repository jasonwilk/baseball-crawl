"""Tests for admin reports page (E-172-04)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from migrations.apply_migrations import run_migrations
from src.api.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CSRF = "test-csrf-token"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _future_iso(days: int = 14) -> str:
    dt = datetime.now(timezone.utc) + timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    return db_path


def _insert_team(db_path: Path, name: str = "Test Team") -> int:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    cursor = conn.execute(
        "INSERT INTO teams (name, membership_type) VALUES (?, 'tracked')", (name,)
    )
    conn.commit()
    team_id = cursor.lastrowid
    conn.close()
    return team_id


def _insert_report(
    db_path: Path,
    team_id: int,
    slug: str = "test-slug",
    status: str = "ready",
    expires_at: str | None = None,
    report_path: str | None = "reports/test-slug.html",
    error_message: str | None = None,
) -> int:
    if expires_at is None:
        expires_at = _future_iso()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "INSERT INTO reports (slug, team_id, title, status, generated_at, expires_at, report_path, error_message) "
        "VALUES (?, ?, 'Test Report', ?, ?, ?, ?, ?)",
        (slug, team_id, status, _utcnow_iso(), expires_at, report_path, error_message),
    )
    report_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return report_id


@pytest.fixture()
def setup(tmp_path):
    """Create DB and test client using DEV_USER_EMAIL bypass."""
    db_path = _make_db(tmp_path)
    # Insert a user for the dev bypass to find
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT INTO users (email, role, hashed_password) VALUES ('user@example.com', 'admin', '')"
    )
    conn.commit()
    conn.close()

    def _mock_get_conn():
        c = sqlite3.connect(str(db_path))
        c.execute("PRAGMA foreign_keys=ON;")
        return c

    env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "user@example.com"}
    with patch("src.api.routes.admin.get_connection", side_effect=_mock_get_conn), \
         patch("src.api.db.get_connection", side_effect=_mock_get_conn), \
         patch.dict("os.environ", env, clear=False):
        client = TestClient(app, raise_server_exceptions=False, cookies={"csrf_token": _CSRF})
        yield db_path, client


# ---------------------------------------------------------------------------
# AC-9(a): Reports page renders with URL input and table
# ---------------------------------------------------------------------------


class TestReportsPage:
    """Test GET /admin/reports."""

    def test_renders_page_with_form_and_table(self, setup):
        db_path, client = setup
        team_id = _insert_team(db_path)
        _insert_report(db_path, team_id)

        response = client.get("/admin/reports")

        assert response.status_code == 200
        html = response.text
        assert "gc_url" in html  # URL input field
        assert "Generate Report" in html  # Submit button
        assert "Test Report" in html  # Report in table

    def test_empty_state(self, setup):
        _db_path, client = setup
        response = client.get("/admin/reports")

        assert response.status_code == 200
        assert "No reports yet" in response.text

    def test_reports_nav_link_present(self, setup):
        _db_path, client = setup
        response = client.get("/admin/reports")

        assert response.status_code == 200
        assert 'href="/admin/reports"' in response.text

    def test_reports_nav_on_teams_page(self, setup):
        """AC-8: Reports link appears in admin nav on other pages."""
        _db_path, client = setup
        response = client.get("/admin/teams")

        assert response.status_code == 200
        assert 'href="/admin/reports"' in response.text

    def test_status_badges(self, setup):
        db_path, client = setup
        team_id = _insert_team(db_path)
        _insert_report(db_path, team_id, slug="r1", status="ready")
        _insert_report(db_path, team_id, slug="r2", status="generating")
        _insert_report(db_path, team_id, slug="r3", status="failed", error_message="oops")

        response = client.get("/admin/reports")
        html = response.text

        assert "bg-green-100" in html  # Ready
        assert "bg-yellow-100" in html  # Generating
        assert "bg-red-100" in html  # Failed

    def test_failed_report_shows_error_tooltip(self, setup):
        """AC-7: Failed reports show error message."""
        db_path, client = setup
        team_id = _insert_team(db_path)
        _insert_report(
            db_path, team_id, slug="fail1",
            status="failed", error_message="Auth expired",
        )

        response = client.get("/admin/reports")
        assert "Auth expired" in response.text

    def test_auto_refresh_when_generating(self, setup):
        db_path, client = setup
        team_id = _insert_team(db_path)
        _insert_report(db_path, team_id, slug="gen1", status="generating")

        response = client.get("/admin/reports")
        assert 'http-equiv="refresh"' in response.text


# ---------------------------------------------------------------------------
# AC-9(b): POST with valid URL creates background task and redirects
# ---------------------------------------------------------------------------


class TestGenerateReport:
    """Test POST /admin/reports/generate."""

    def test_valid_url_redirects_with_message(self, setup):
        _db_path, client = setup

        with patch("src.reports.generator.generate_report") as mock_gen:
            response = client.post(
                "/admin/reports/generate",
                data={"gc_url": "https://web.gc.com/teams/abc123/test", "csrf_token": _CSRF},
                follow_redirects=False,
            )

        assert response.status_code == 303
        assert "/admin/reports" in response.headers["location"]
        loc = response.headers["location"].lower()
        assert "started" in loc or "generation" in loc

    def test_background_task_is_enqueued(self, setup):
        """The generate_report function is called via background tasks."""
        _db_path, client = setup

        with patch("src.reports.generator.generate_report") as mock_gen:
            response = client.post(
                "/admin/reports/generate",
                data={"gc_url": "abc123", "csrf_token": _CSRF},
                follow_redirects=True,
            )

        # Background task runs synchronously in test client
        mock_gen.assert_called_once_with("abc123")


# ---------------------------------------------------------------------------
# AC-9(c): POST with invalid URL shows error flash
# ---------------------------------------------------------------------------


class TestGenerateInvalidURL:
    """Test POST /admin/reports/generate with invalid input."""

    def test_invalid_url_shows_error(self, setup):
        _db_path, client = setup

        response = client.post(
            "/admin/reports/generate",
            data={"gc_url": "not a url !!!", "csrf_token": _CSRF},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert "error=" in response.headers["location"]

    def test_empty_url_shows_error(self, setup):
        _db_path, client = setup

        response = client.post(
            "/admin/reports/generate",
            data={"gc_url": "   ", "csrf_token": _CSRF},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert "error=" in response.headers["location"]

    def test_uuid_url_shows_error(self, setup):
        _db_path, client = setup

        response = client.post(
            "/admin/reports/generate",
            data={"gc_url": "72bb77d8-54ca-42d2-8547-9da4880d0cb4", "csrf_token": _CSRF},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert "error=" in response.headers["location"]


# ---------------------------------------------------------------------------
# AC-9(d): Delete removes the report row
# ---------------------------------------------------------------------------


class TestDeleteReport:
    """Test POST /admin/reports/{id}/delete."""

    def test_delete_removes_row(self, setup, tmp_path):
        db_path, client = setup
        team_id = _insert_team(db_path)

        # Create a report file on disk
        data_dir = Path(__file__).resolve().parents[1] / "data"
        # Instead, we'll mock the file deletion since we can't create files in
        # the actual data directory during tests. Just verify the DB row is gone.
        report_id = _insert_report(db_path, team_id, slug="del-me")

        response = client.post(
            f"/admin/reports/{report_id}/delete",
            data={"csrf_token": _CSRF},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert "/admin/reports" in response.headers["location"]

        # Verify row is deleted
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT id FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
        conn.close()
        assert row is None

    def test_delete_nonexistent_report_still_redirects(self, setup):
        _db_path, client = setup

        response = client.post(
            "/admin/reports/99999/delete",
            data={"csrf_token": _CSRF},
            follow_redirects=False,
        )

        assert response.status_code == 303
