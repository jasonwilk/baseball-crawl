"""Tests for the public report serving route (E-172-03)."""

from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.auth import hash_token
from src.api.main import app
from tests.conftest import load_real_schema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _future_iso(days: int = 14) -> str:
    dt = datetime.now(timezone.utc) + timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _past_iso(days: int = 1) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_db(tmp_path: Path) -> Path:
    """Create a disk-backed DB with the production schema. Return db path."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    load_real_schema(conn)
    conn.execute(
        "INSERT INTO teams (name, membership_type) VALUES ('Test Team', 'tracked')"
    )
    conn.commit()
    conn.close()
    return db_path


def _insert_report(
    db_path: Path,
    slug: str,
    status: str = "ready",
    expires_at: str | None = None,
    report_path: str | None = None,
) -> None:
    conn = sqlite3.connect(str(db_path))
    if expires_at is None:
        expires_at = _future_iso()
    conn.execute(
        "INSERT INTO reports (slug, team_id, title, status, generated_at, expires_at, report_path) "
        "VALUES (?, 1, 'Test Report', ?, ?, ?, ?)",
        (slug, status, _utcnow_iso(), expires_at, report_path),
    )
    conn.commit()
    conn.close()


@pytest.fixture()
def setup(tmp_path):
    """Set up test DB and report file, yield (db_path, data_dir, client)."""
    db_path = _make_db(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    reports_dir = data_dir / "reports"
    reports_dir.mkdir()

    def _mock_get_conn():
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    with (
        patch("src.api.routes.reports.get_connection", side_effect=_mock_get_conn),
        patch("src.api.routes.reports._PROJECT_ROOT", tmp_path),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        yield db_path, reports_dir, client


# ---------------------------------------------------------------------------
# AC-7(a): 200 for valid ready report
# ---------------------------------------------------------------------------


class TestServeReport:
    """Test successful report serving."""

    def test_200_for_ready_report(self, setup):
        db_path, reports_dir, client = setup
        (reports_dir / "test-slug.html").write_text(
            "<html><body>Report</body></html>", encoding="utf-8"
        )
        _insert_report(db_path, "test-slug", report_path="reports/test-slug.html")

        response = client.get("/reports/test-slug")

        assert response.status_code == 200
        assert "<html><body>Report</body></html>" in response.text

    def test_content_type_is_html(self, setup):
        """AC-7(e): Content-Type is text/html."""
        db_path, reports_dir, client = setup
        (reports_dir / "ct-slug.html").write_text("<html></html>", encoding="utf-8")
        _insert_report(db_path, "ct-slug", report_path="reports/ct-slug.html")

        response = client.get("/reports/ct-slug")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_cache_control_header(self, setup):
        db_path, reports_dir, client = setup
        (reports_dir / "cache-slug.html").write_text("<html></html>", encoding="utf-8")
        _insert_report(db_path, "cache-slug", report_path="reports/cache-slug.html")

        response = client.get("/reports/cache-slug")

        assert response.status_code == 200
        assert "public" in response.headers.get("cache-control", "")


# ---------------------------------------------------------------------------
# AC-7(b): 404 for unknown slug
# ---------------------------------------------------------------------------


class TestUnknownSlug:
    """Test 404 for nonexistent slugs."""

    def test_404_for_unknown_slug(self, setup):
        _db_path, _reports_dir, client = setup

        response = client.get("/reports/nonexistent-slug")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# AC-7(c): 404 for expired report
# ---------------------------------------------------------------------------


class TestExpiredReport:
    """Test 404 for expired reports."""

    def test_404_for_expired_report(self, setup):
        db_path, reports_dir, client = setup
        (reports_dir / "expired-slug.html").write_text("<html></html>", encoding="utf-8")
        _insert_report(
            db_path, "expired-slug",
            status="ready",
            expires_at=_past_iso(1),
            report_path="reports/expired-slug.html",
        )

        response = client.get("/reports/expired-slug")

        assert response.status_code == 404

    def test_expired_response_identical_to_unknown(self, setup):
        """Expired response should not reveal the report ever existed."""
        db_path, reports_dir, client = setup
        (reports_dir / "exp-slug.html").write_text("<html></html>", encoding="utf-8")
        _insert_report(
            db_path, "exp-slug",
            status="ready",
            expires_at=_past_iso(1),
            report_path="reports/exp-slug.html",
        )

        expired_resp = client.get("/reports/exp-slug")
        unknown_resp = client.get("/reports/totally-unknown")

        assert expired_resp.status_code == unknown_resp.status_code


# ---------------------------------------------------------------------------
# AC-7(d): 404 for generating/failed status
# ---------------------------------------------------------------------------


class TestNonReadyStatus:
    """Test 404 for non-ready report statuses."""

    def test_404_for_generating_status(self, setup):
        db_path, reports_dir, client = setup
        _insert_report(db_path, "gen-slug", status="generating")

        response = client.get("/reports/gen-slug")

        assert response.status_code == 404

    def test_404_for_failed_status(self, setup):
        db_path, reports_dir, client = setup
        _insert_report(db_path, "fail-slug", status="failed")

        response = client.get("/reports/fail-slug")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# E-235-03 AC-2: no_games reports are SERVED (shareable), not 404
# ---------------------------------------------------------------------------


class TestNoGamesStatusServed:
    """The E-235-03 gate (a) no-games page is shareable -- the serve route
    renders its file (200), it does not 404 like generating/failed."""

    def test_200_for_no_games_status(self, setup):
        db_path, reports_dir, client = setup
        (reports_dir / "ng-slug.html").write_text(
            "<html><body>No completed games found for Test Team this season."
            "</body></html>",
            encoding="utf-8",
        )
        _insert_report(
            db_path, "ng-slug", status="no_games",
            report_path="reports/ng-slug.html",
        )

        response = client.get("/reports/ng-slug")

        assert response.status_code == 200
        assert "No completed games found" in response.text

    def test_no_games_still_respects_expiry(self, setup):
        """A no_games report still 404s once expired (same as ready)."""
        db_path, reports_dir, client = setup
        (reports_dir / "ng-exp.html").write_text("<html></html>", encoding="utf-8")
        _insert_report(
            db_path, "ng-exp", status="no_games",
            expires_at=_past_iso(1),
            report_path="reports/ng-exp.html",
        )

        response = client.get("/reports/ng-exp")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# No auth required
# ---------------------------------------------------------------------------


class TestNoAuth:
    """Verify the route works without authentication."""

    def test_no_auth_redirect(self, setup):
        """The route should return 200/404, never 302 to /auth/login."""
        db_path, reports_dir, client = setup
        (reports_dir / "noauth.html").write_text("<html></html>", encoding="utf-8")
        _insert_report(db_path, "noauth", report_path="reports/noauth.html")

        response = client.get("/reports/noauth", follow_redirects=False)

        assert response.status_code == 200
        # Should NOT redirect to login
        assert response.status_code != 302


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test edge cases."""

    def test_missing_file_returns_404(self, setup):
        """DB row exists but file is missing on disk."""
        db_path, _reports_dir, client = setup
        _insert_report(
            db_path, "missing-file",
            report_path="reports/missing-file.html",
        )

        response = client.get("/reports/missing-file")

        assert response.status_code == 404

    def test_null_report_path_returns_404(self, setup):
        db_path, _reports_dir, client = setup
        _insert_report(db_path, "null-path", report_path=None)

        response = client.get("/reports/null-path")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# E-238-05: Navigation retarget canary
#
# AC-8 (testable half): the reports flow is the live product surface. A
# seeded report's share link must still serve via the public serve route,
# and the admin reports page (the post-login landing) must NOT render the
# removed /dashboard bottom-nav links or the removed Dashboard header
# link. /admin/reports requires admin (auth-scope shift, epic Risks), so the
# canary uses an admin-authenticated client.
# ---------------------------------------------------------------------------


class TestShareLinkStillServes:
    """E-238-05 AC-8: a seeded report's public share link still serves."""

    def test_seeded_report_share_link_serves(self, setup):
        """The public /reports/{slug} share link serves the report (no auth)."""
        db_path, reports_dir, client = setup
        (reports_dir / "share-canary.html").write_text(
            "<html><body>Scouting report</body></html>", encoding="utf-8"
        )
        _insert_report(
            db_path, "share-canary", report_path="reports/share-canary.html"
        )

        response = client.get("/reports/share-canary", follow_redirects=False)

        assert response.status_code == 200
        assert "Scouting report" in response.text
        # The share link is the live surface -- it must not bounce to /dashboard.
        assert response.status_code != 302


def _make_admin_db(tmp_path: Path) -> tuple[Path, str, str]:
    """Create a real-schema DB with an admin user + session.

    Returns (db_path, admin_email, raw_session_token).
    """
    db_path = tmp_path / "admin.db"
    conn = sqlite3.connect(str(db_path))
    load_real_schema(conn)
    email = "operator@example.com"
    user_id = conn.execute(
        "INSERT INTO users (email) VALUES (?) RETURNING id", (email,)
    ).fetchone()[0]
    raw_token = secrets.token_hex(32)
    conn.execute(
        "INSERT INTO sessions (session_id, user_id, expires_at) "
        "VALUES (?, ?, datetime('now', '+7 days'))",
        (hash_token(raw_token), user_id),
    )
    conn.commit()
    conn.close()
    return db_path, email, raw_token


class TestAdminReportsSuppressesDashboardNav:
    """E-239: /admin/reports renders without the removed dashboard nav."""

    def test_admin_reports_has_no_dashboard_nav(self, tmp_path: Path) -> None:
        """GET /admin/reports renders without bottom dashboard nav or header link.

        E-239 removed base.html's bottom fixed nav (the 3 /dashboard* links)
        and the page's own Dashboard header link; this canary asserts no
        /dashboard links remain.
        """
        db_path, email, raw_token = _make_admin_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "ADMIN_EMAIL": email},
        ):
            with TestClient(
                app, cookies={"session": raw_token, "csrf_token": "test-csrf-token"}
            ) as client:
                response = client.get("/admin/reports")

        assert response.status_code == 200
        html = response.text
        assert "Reports" in html
        # The bottom dashboard nav was removed from base.html (E-239) -- its
        # /dashboard* links and labels must be absent.
        assert "/dashboard/batting" not in html
        assert "/dashboard/pitching" not in html
        assert ">Batting<" not in html
        assert ">Pitching<" not in html
        # AC-4: the page's own Dashboard header link was removed.
        assert 'href="/dashboard"' not in html
