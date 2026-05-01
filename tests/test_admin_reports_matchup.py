"""Tests for E-228-01 admin form: matchup checkbox, dropdown, and POST handler.

Covers AC-5, AC-5a, AC-6 and the corresponding test ACs (AC-T4, AC-T4a).

The form's behavior depends on two things:
1. ``FEATURE_MATCHUP_ANALYSIS`` env var (gates whether the checkbox renders).
2. Whether any ``teams.membership_type='member'`` rows exist (gates whether
   the dropdown is populated; otherwise the checkbox is disabled with a hint).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from migrations.apply_migrations import run_migrations
from src.api.main import app


_CSRF = "test-csrf-token"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    return db_path


def _insert_member_team(
    db_path: Path, name: str = "LSB Varsity",
) -> int:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    cursor = conn.execute(
        "INSERT INTO teams (name, membership_type, is_active) "
        "VALUES (?, 'member', 1)",
        (name,),
    )
    conn.commit()
    team_id = cursor.lastrowid
    conn.close()
    return team_id


@pytest.fixture()
def setup(tmp_path):
    """Build a TestClient + DB with the admin DEV_USER bypass active."""
    db_path = _make_db(tmp_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT INTO users (email, role, hashed_password) "
        "VALUES ('user@example.com', 'admin', '')"
    )
    conn.commit()
    conn.close()

    def _mock_get_conn():
        c = sqlite3.connect(str(db_path))
        c.execute("PRAGMA foreign_keys=ON;")
        return c

    env = {
        "DATABASE_PATH": str(db_path),
        "DEV_USER_EMAIL": "user@example.com",
    }
    with patch(
        "src.api.routes.admin.get_connection", side_effect=_mock_get_conn,
    ), patch(
        "src.api.db.get_connection", side_effect=_mock_get_conn,
    ), patch(
        "src.reports.generator.get_connection", side_effect=_mock_get_conn,
    ), patch.dict("os.environ", env, clear=False):
        client = TestClient(
            app, raise_server_exceptions=False, cookies={"csrf_token": _CSRF},
        )
        yield db_path, client


# ---------------------------------------------------------------------------
# AC-T4(a): FEATURE_MATCHUP_ANALYSIS=1 renders the checkbox + dropdown
# ---------------------------------------------------------------------------


class TestRenderingFlagOn:
    """When the feature flag is on, the matchup UI is present in the form."""

    def test_checkbox_and_dropdown_rendered_with_member_teams(
        self, setup, monkeypatch,
    ):
        db_path, client = setup
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")

        # Insert two member teams so we can verify dropdown population +
        # ordering.
        _insert_member_team(db_path, "Alpha")
        _insert_member_team(db_path, "Bravo")

        response = client.get("/admin/reports")
        assert response.status_code == 200
        html = response.text

        # Checkbox is rendered
        assert 'name="enable_matchup"' in html, (
            "Expected the matchup checkbox to be rendered when the flag is on."
        )
        assert "Include matchup section" in html

        # Dropdown wrapper exists and is initially hidden
        assert 'id="matchup_team_wrapper"' in html
        assert 'style="display:none;"' in html

        # Dropdown is populated and the help text is present
        assert 'name="our_team_id"' in html
        assert "Stats from this team will be used to build" in html

        # Both member team names appear in the rendered options.  The exact
        # ordering by SQL ORDER BY name is verified separately to avoid
        # over-coupling to surrounding HTML.
        assert "Alpha" in html
        assert "Bravo" in html

    def test_dropdown_options_ordered_by_name(self, setup, monkeypatch):
        db_path, client = setup
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")

        _insert_member_team(db_path, "Zebra")
        _insert_member_team(db_path, "Apple")
        _insert_member_team(db_path, "Mango")

        response = client.get("/admin/reports")
        html = response.text

        # The first occurrence of each name in the form's HTML should be in
        # name-sorted order (Apple, Mango, Zebra).
        idx_apple = html.find("Apple")
        idx_mango = html.find("Mango")
        idx_zebra = html.find("Zebra")
        assert idx_apple < idx_mango < idx_zebra, (
            f"Expected dropdown options to be name-sorted; "
            f"got positions Apple={idx_apple}, Mango={idx_mango}, Zebra={idx_zebra}"
        )

    def test_tracked_teams_excluded_from_dropdown(self, setup, monkeypatch):
        """Only ``membership_type='member'`` rows feed the dropdown."""
        db_path, client = setup
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")

        _insert_member_team(db_path, "MemberOnly")

        # Insert a tracked team -- must NOT appear in the dropdown
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO teams (name, membership_type, is_active) "
            "VALUES ('TrackedOnly', 'tracked', 0)"
        )
        conn.commit()
        conn.close()

        response = client.get("/admin/reports")
        html = response.text

        assert "MemberOnly" in html

        # Look only inside the dropdown's <option> tags for "TrackedOnly".
        # The strict assertion is that an <option ...>TrackedOnly</option>
        # block does not appear.
        assert ">TrackedOnly<" not in html, (
            "TrackedOnly should not appear as a dropdown option -- only "
            "member teams feed the matchup dropdown."
        )


# ---------------------------------------------------------------------------
# AC-T4(b): FEATURE_MATCHUP_ANALYSIS=0 hides the checkbox entirely
# ---------------------------------------------------------------------------


class TestRenderingFlagOff:
    """When the feature flag is off, the matchup UI is fully hidden."""

    def test_checkbox_not_rendered_when_flag_off(self, setup, monkeypatch):
        db_path, client = setup
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "0")
        _insert_member_team(db_path, "ShouldNotShow")

        response = client.get("/admin/reports")
        html = response.text

        assert response.status_code == 200
        assert 'name="enable_matchup"' not in html
        assert "Include matchup section" not in html
        assert 'name="our_team_id"' not in html

    def test_checkbox_not_rendered_when_flag_unset(self, setup, monkeypatch):
        _db_path, client = setup
        monkeypatch.delenv("FEATURE_MATCHUP_ANALYSIS", raising=False)

        response = client.get("/admin/reports")
        html = response.text

        assert response.status_code == 200
        assert 'name="enable_matchup"' not in html


# ---------------------------------------------------------------------------
# AC-T4a: empty member-team edge case (zero members but flag is on)
# ---------------------------------------------------------------------------


class TestEmptyMemberTeams:
    """With zero member teams, the checkbox is disabled and a hint shown."""

    def test_disabled_with_help_text(self, setup, monkeypatch):
        _db_path, client = setup
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")

        # No member teams seeded.
        response = client.get("/admin/reports")
        html = response.text

        assert response.status_code == 200
        # Checkbox is rendered but disabled
        assert 'name="enable_matchup"' in html
        assert "disabled" in html

        # The dropdown is NOT rendered (replaced by help text)
        assert 'name="our_team_id"' not in html
        assert "Add a member team" in html


# ---------------------------------------------------------------------------
# AC-T4(c-e): POST handler behavior
# ---------------------------------------------------------------------------


class TestPostHandler:
    """Form POST routing into ``generate_report``."""

    def test_unchecked_passes_our_team_id_none(self, setup, monkeypatch):
        _db_path, client = setup
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")

        with patch("src.reports.generator.generate_report") as mock_gen:
            response = client.post(
                "/admin/reports/generate",
                data={"gc_url": "abc123", "csrf_token": _CSRF},
                follow_redirects=False,
            )

        assert response.status_code == 303
        mock_gen.assert_called_once_with("abc123", our_team_id=None)

    def test_checked_with_valid_team_passes_resolved_id(
        self, setup, monkeypatch,
    ):
        db_path, client = setup
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")
        team_id = _insert_member_team(db_path, "LSB Varsity")

        with patch("src.reports.generator.generate_report") as mock_gen:
            response = client.post(
                "/admin/reports/generate",
                data={
                    "gc_url": "abc123",
                    "csrf_token": _CSRF,
                    "enable_matchup": "on",
                    "our_team_id": str(team_id),
                },
                follow_redirects=False,
            )

        assert response.status_code == 303
        # Redirect should contain the success "msg" (no error)
        assert "/admin/reports?msg=" in response.headers["location"]
        mock_gen.assert_called_once_with("abc123", our_team_id=team_id)

    def test_checked_with_empty_dropdown_re_renders_with_error(
        self, setup, monkeypatch,
    ):
        db_path, client = setup
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")
        # Member team exists but operator submits empty value
        _insert_member_team(db_path, "LSB Varsity")

        with patch("src.reports.generator.generate_report") as mock_gen:
            response = client.post(
                "/admin/reports/generate",
                data={
                    "gc_url": "abc123",
                    "csrf_token": _CSRF,
                    "enable_matchup": "on",
                    "our_team_id": "",
                },
                follow_redirects=False,
            )

        # Server-side validation: redirect with error flash, generate_report
        # never invoked.
        assert response.status_code == 303
        assert "error=" in response.headers["location"]
        mock_gen.assert_not_called()

    def test_checked_with_non_member_team_id_rejected(
        self, setup, monkeypatch,
    ):
        """Tampered POST: our_team_id pointing at a tracked team is rejected."""
        db_path, client = setup
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")

        # A tracked team exists but no member team is selectable
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "INSERT INTO teams (name, membership_type) "
            "VALUES ('NotMember', 'tracked')"
        )
        tracked_id = cursor.lastrowid
        conn.commit()
        conn.close()

        with patch("src.reports.generator.generate_report") as mock_gen:
            response = client.post(
                "/admin/reports/generate",
                data={
                    "gc_url": "abc123",
                    "csrf_token": _CSRF,
                    "enable_matchup": "on",
                    "our_team_id": str(tracked_id),
                },
                follow_redirects=False,
            )

        assert response.status_code == 303
        assert "error=" in response.headers["location"]
        mock_gen.assert_not_called()

    def test_checked_with_non_integer_value_rejected(self, setup, monkeypatch):
        _db_path, client = setup
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")
        _insert_member_team(_db_path, "LSB Varsity")

        with patch("src.reports.generator.generate_report") as mock_gen:
            response = client.post(
                "/admin/reports/generate",
                data={
                    "gc_url": "abc123",
                    "csrf_token": _CSRF,
                    "enable_matchup": "on",
                    "our_team_id": "not-an-int",
                },
                follow_redirects=False,
            )

        assert response.status_code == 303
        assert "error=" in response.headers["location"]
        mock_gen.assert_not_called()

    def test_flag_off_ignores_enable_matchup_field(self, setup, monkeypatch):
        """Tampered POST when feature flag is off: matchup fields ignored."""
        db_path, client = setup
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "0")
        team_id = _insert_member_team(db_path, "LSB Varsity")

        with patch("src.reports.generator.generate_report") as mock_gen:
            response = client.post(
                "/admin/reports/generate",
                data={
                    "gc_url": "abc123",
                    "csrf_token": _CSRF,
                    "enable_matchup": "on",
                    "our_team_id": str(team_id),
                },
                follow_redirects=False,
            )

        # Generation proceeds normally with our_team_id=None despite the
        # caller submitting a value.
        assert response.status_code == 303
        mock_gen.assert_called_once_with("abc123", our_team_id=None)
