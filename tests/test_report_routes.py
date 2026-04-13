"""Tests for the public report serving route (E-172-03)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

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
