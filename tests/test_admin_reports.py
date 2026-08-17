"""Tests for admin reports page (E-172-04)."""

from __future__ import annotations

import os
import sqlite3
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from migrations.apply_migrations import run_migrations
from src.api.main import app
from src.api.routes import reports_admin
from src.reports import lifecycle
from src.util.timezone import UTC_ISO_FORMAT, utcnow_iso


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
# These build the same `reports.generated_at` / `expires_at` strings the app
# writes, so they MUST use the canonical UTC_ISO_FORMAT rather than a local
# copy of it -- a divergent literal here would keep passing against a format
# the code no longer emits (E-256-03).

_CSRF = "test-csrf-token"


def _future_iso(days: int = 14) -> str:
    dt = datetime.now(timezone.utc) + timedelta(days=days)
    return dt.strftime(UTC_ISO_FORMAT)


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
        (slug, team_id, status, utcnow_iso(), expires_at, report_path, error_message),
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
    with patch("src.api.routes.reports_admin.get_connection", side_effect=_mock_get_conn), \
         patch("src.api.db.get_connection", side_effect=_mock_get_conn), \
         patch("src.reports.generator.get_connection", side_effect=_mock_get_conn), \
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

    def test_reports_nav_on_users_page(self, setup):
        """AC-8: Reports link appears in admin nav on other pages."""
        _db_path, client = setup
        response = client.get("/admin/users")

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

    def test_reaped_failed_report_is_terminal_and_deletable(self, setup):
        """E-252-08 AC-4: a report reaped to 'failed' renders as terminal (NO
        indefinite meta-refresh) and shows the delete affordance -- so the operator
        recovers it through the normal admin flow instead of raw SQL. This pins the
        existing template gating (meta-refresh on has_generating; delete on
        status != 'generating') for a failed row -- the reaper only changes status,
        it does not need a template change.
        """
        db_path, client = setup
        team_id = _insert_team(db_path)
        failed_id = _insert_report(
            db_path, team_id, slug="reaped1", status="failed",
            error_message="Reaped: generation did not complete", report_path=None,
        )

        response = client.get("/admin/reports")
        html = response.text
        # Terminal: with no 'generating' row present, the page does NOT meta-refresh.
        assert 'http-equiv="refresh"' not in html
        # Deletable: the delete form for the failed row is rendered.
        assert f"/admin/reports/{failed_id}/delete" in html

    def test_generating_report_has_no_delete_affordance(self, setup):
        """E-252-08 AC-4 (contrast): a still-'generating' row is NOT deletable -- its
        delete form is withheld (so the reaper is what makes a stuck row deletable)."""
        db_path, client = setup
        team_id = _insert_team(db_path)
        gen_id = _insert_report(db_path, team_id, slug="gen2", status="generating")

        response = client.get("/admin/reports")
        assert f"/admin/reports/{gen_id}/delete" not in response.text


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


# ===========================================================================
# E-199-03: Cascade-delete team data on report deletion
# ===========================================================================


def _get_conn(db_path: Path) -> sqlite3.Connection:
    """Open a connection with FK enforcement."""
    c = sqlite3.connect(str(db_path))
    c.execute("PRAGMA foreign_keys=ON;")
    return c


def _insert_team_for_cascade(
    db_path: Path,
    *,
    name: str = "Report Team",
    is_active: int = 0,
    membership_type: str = "tracked",
) -> int:
    conn = _get_conn(db_path)
    cursor = conn.execute(
        "INSERT INTO teams (name, membership_type, is_active) VALUES (?, ?, ?)",
        (name, membership_type, is_active),
    )
    team_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return team_id


def _seed_full_team_data(db_path: Path, team_id: int) -> dict:
    """Insert a full set of dependent data for a team. Returns metadata dict."""
    conn = _get_conn(db_path)

    season_id = "2026"
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) "
        "VALUES (?, 'Spring 2026 HS', 2026)",
        (season_id,),
    )

    opp_id = conn.execute(
        "INSERT INTO teams (name, membership_type, is_active) VALUES ('Opp', 'tracked', 0)"
    ).lastrowid

    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES ('player1', 'Test', 'Player')"
    )
    conn.execute(
        "INSERT INTO team_rosters (player_id, team_id, season_id) VALUES ('player1', ?, ?)",
        (team_id, season_id),
    )
    # player_season_* dropped in E-259-03 -- no stored season rows to cascade.

    game_id = "game-cascade-001"
    conn.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, status) "
        "VALUES (?, ?, '2026-03-15', ?, ?, 'completed')",
        (game_id, season_id, team_id, opp_id),
    )
    conn.execute(
        "INSERT INTO player_game_batting (game_id, player_id, team_id, perspective_team_id) VALUES (?, 'player1', ?, ?)",
        (game_id, team_id, team_id),
    )
    conn.execute(
        "INSERT INTO player_game_pitching (game_id, player_id, team_id, perspective_team_id) VALUES (?, 'player1', ?, ?)",
        (game_id, team_id, team_id),
    )
    conn.execute(
        "INSERT INTO spray_charts (game_id, team_id, player_id, season_id, chart_type, x, y, perspective_team_id) "
        "VALUES (?, ?, 'player1', ?, 'offensive', 100, 200, ?)",
        (game_id, team_id, season_id, team_id),
    )

    cursor = conn.execute(
        "INSERT INTO plays (game_id, play_order, inning, half, season_id, "
        "batting_team_id, perspective_team_id, batter_id, pitcher_id) VALUES (?, 1, 1, 'top', ?, ?, ?, 'player1', 'player1')",
        (game_id, season_id, team_id, team_id),
    )
    play_id = cursor.lastrowid
    conn.execute(
        "INSERT INTO play_events (play_id, event_order, event_type) VALUES (?, 1, 'pitch')",
        (play_id,),
    )

    conn.execute(
        "INSERT INTO reconciliation_discrepancies (game_id, run_id, perspective_team_id, team_id, player_id, "
        "signal_name, category, status) VALUES (?, 'run1', ?, ?, 'player1', 'bf', 'pitching', 'MATCH')",
        (game_id, team_id, team_id),
    )
    conn.execute(
        "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
        "VALUES (?, ?, 'full', '2026-03-28T00:00:00Z', 'completed')",
        (team_id, season_id),
    )

    conn.commit()
    conn.close()
    return {"game_id": game_id, "opp_id": opp_id, "season_id": season_id}


def _count_rows(db_path: Path, table: str, where: str = "", params: tuple = ()) -> int:
    conn = _get_conn(db_path)
    sql = f"SELECT COUNT(*) FROM {table}"
    if where:
        sql += f" WHERE {where}"
    count = conn.execute(sql, params).fetchone()[0]
    conn.close()
    return count


class TestCascadeDeleteOnReportDeletion:
    """AC-1 through AC-8: Cascade-delete team data on report deletion."""

    def test_ac1_clean_cascade_of_report_only_team(self, setup):
        """Report-only team with full data: cascade deletes everything."""
        db_path, client = setup
        team_id = _insert_team_for_cascade(db_path, is_active=0)
        data = _seed_full_team_data(db_path, team_id)
        report_id = _insert_report(db_path, team_id, slug="cascade-1")

        assert _count_rows(db_path, "teams", "id = ?", (team_id,)) == 1
        assert _count_rows(db_path, "plays", "game_id = ?", (data["game_id"],)) == 1

        response = client.post(
            f"/admin/reports/{report_id}/delete",
            data={"csrf_token": _CSRF},
            follow_redirects=False,
        )
        assert response.status_code == 303

        assert _count_rows(db_path, "reports", "id = ?", (report_id,)) == 0
        assert _count_rows(db_path, "teams", "id = ?", (team_id,)) == 0
        assert _count_rows(db_path, "games", "game_id = ?", (data["game_id"],)) == 0
        assert _count_rows(db_path, "plays", "game_id = ?", (data["game_id"],)) == 0
        assert _count_rows(db_path, "reconciliation_discrepancies", "game_id = ?", (data["game_id"],)) == 0
        assert _count_rows(db_path, "player_game_batting", "game_id = ?", (data["game_id"],)) == 0
        assert _count_rows(db_path, "player_game_pitching", "game_id = ?", (data["game_id"],)) == 0
        assert _count_rows(db_path, "spray_charts", "team_id = ?", (team_id,)) == 0
        assert _count_rows(db_path, "team_rosters", "team_id = ?", (team_id,)) == 0
        assert _count_rows(db_path, "scouting_runs", "team_id = ?", (team_id,)) == 0
        assert _count_rows(db_path, "play_events") == 0

    def test_ac3_preserved_when_is_active(self, setup):
        """Active team: data preserved on report delete."""
        db_path, client = setup
        team_id = _insert_team_for_cascade(db_path, is_active=1)
        _seed_full_team_data(db_path, team_id)
        report_id = _insert_report(db_path, team_id, slug="guard-active")

        client.post(f"/admin/reports/{report_id}/delete", data={"csrf_token": _CSRF}, follow_redirects=False)

        assert _count_rows(db_path, "reports", "id = ?", (report_id,)) == 0
        assert _count_rows(db_path, "teams", "id = ?", (team_id,)) == 1

    def test_ac5_preserved_when_multiple_reports(self, setup):
        """Multiple reports for same team: data preserved until last report."""
        db_path, client = setup
        team_id = _insert_team_for_cascade(db_path, is_active=0)
        _seed_full_team_data(db_path, team_id)
        report_1 = _insert_report(db_path, team_id, slug="multi-1")
        report_2 = _insert_report(db_path, team_id, slug="multi-2")

        client.post(f"/admin/reports/{report_1}/delete", data={"csrf_token": _CSRF}, follow_redirects=False)
        assert _count_rows(db_path, "reports", "id = ?", (report_1,)) == 0
        assert _count_rows(db_path, "teams", "id = ?", (team_id,)) == 1

        client.post(f"/admin/reports/{report_2}/delete", data={"csrf_token": _CSRF}, follow_redirects=False)
        assert _count_rows(db_path, "reports", "id = ?", (report_2,)) == 0
        assert _count_rows(db_path, "teams", "id = ?", (team_id,)) == 0

    def test_ac6_empty_team_row_cascade(self, setup):
        """Empty team (no dependent data): cascade deletes cleanly."""
        db_path, client = setup
        team_id = _insert_team_for_cascade(db_path, is_active=0)
        report_id = _insert_report(db_path, team_id, slug="empty-team")

        client.post(f"/admin/reports/{report_id}/delete", data={"csrf_token": _CSRF}, follow_redirects=False)

        assert _count_rows(db_path, "reports", "id = ?", (report_id,)) == 0
        assert _count_rows(db_path, "teams", "id = ?", (team_id,)) == 0

    def test_ac7_opponent_links_un_resolved(self, setup):
        """Opponent links pointing to the team are un-resolved, not deleted."""
        db_path, client = setup
        team_id = _insert_team_for_cascade(db_path, is_active=0)
        report_id = _insert_report(db_path, team_id, slug="ol-unres")

        conn = _get_conn(db_path)
        member_team = conn.execute(
            "INSERT INTO teams (name, membership_type, is_active) VALUES ('Member', 'member', 1)"
        ).lastrowid
        conn.execute(
            "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, "
            "resolved_team_id, resolution_method, resolved_at) "
            "VALUES (?, 'root1', 'Some Opponent', ?, 'gc_search', '2026-03-20')",
            (member_team, team_id),
        )
        conn.commit()
        conn.close()

        client.post(f"/admin/reports/{report_id}/delete", data={"csrf_token": _CSRF}, follow_redirects=False)

        assert _count_rows(db_path, "teams", "id = ?", (team_id,)) == 0

        conn = _get_conn(db_path)
        ol = conn.execute(
            "SELECT resolved_team_id, resolution_method, resolved_at "
            "FROM opponent_links WHERE our_team_id = ?",
            (member_team,),
        ).fetchone()
        conn.close()
        assert ol is not None
        assert ol[0] is None
        assert ol[1] is None
        assert ol[2] is None


# ===========================================================================
# E-235-05: Cleanup-mirror -- report_generation_runs follows the report it
# describes through every delete path (TN-5).
# ===========================================================================


def _insert_run_row(
    db_path: Path, report_id: int, overall_status: str = "completed"
) -> int:
    conn = _get_conn(db_path)
    cursor = conn.execute(
        "INSERT INTO report_generation_runs (report_id, overall_status) VALUES (?, ?)",
        (report_id, overall_status),
    )
    conn.commit()
    run_id = cursor.lastrowid
    conn.close()
    return run_id


class TestRunRecordCleanupMirror:
    """E-235-05 / TN-5: deleting a report removes its report_generation_runs
    row, satisfying the cleanup-detection mirror invariant for the new table.

    The mechanism is the FK ``ON DELETE CASCADE`` (migration 002) firing on the
    FK-ON connection ``_delete_report`` uses (``get_connection()`` sets
    ``PRAGMA foreign_keys=ON``). These tests run the real delete route, so they
    exercise that connection rather than a bare ``sqlite3.connect()`` (which has
    FKs OFF and would give a false result).
    """

    def test_ac1_delete_report_cascades_run_record(self, setup):
        """AC-1: deleting a report removes its run record. The team is a MEMBER
        team (is_active=1), so it survives BOTH the eligibility cascade (guard 1:
        is_active != 0) AND the E-273 terminal reclamation (member teams are
        never orphans) -- making the run-row removal attributable purely to the
        report->run FK cascade, not any team-delete path. (Pre-E-273 this relied
        on is_active=1 alone; the reclamation pass ignores is_active as a dead
        guard, so the team is pinned via its real persistent signal: membership.)"""
        db_path, client = setup
        team_id = _insert_team_for_cascade(
            db_path, is_active=1, membership_type="member"
        )  # ineligible AND non-orphan
        report_id = _insert_report(
            db_path, team_id, slug="run-cascade-1", report_path=None
        )
        _insert_run_row(db_path, report_id)
        assert _count_rows(
            db_path, "report_generation_runs", "report_id = ?", (report_id,)
        ) == 1

        response = client.post(
            f"/admin/reports/{report_id}/delete",
            data={"csrf_token": _CSRF},
            follow_redirects=False,
        )
        assert response.status_code == 303

        assert _count_rows(db_path, "reports", "id = ?", (report_id,)) == 0
        assert _count_rows(
            db_path, "report_generation_runs", "report_id = ?", (report_id,)
        ) == 0
        # Ineligible team retained: confirms the cascade came from the report
        # delete (conn1), not the team-delete cascade (conn2).
        assert _count_rows(db_path, "teams", "id = ?", (team_id,)) == 1

    def test_ac4_eligible_team_cascade_with_run_row_no_integrity_error(self, setup):
        """AC-4: report deletion followed by the team-delete cascade, with a
        populated run row present, completes with no FK integrity error.

        303 (not 500 -- the client uses raise_server_exceptions=False) plus the
        team/report/run rows all gone proves both cascades ran cleanly."""
        db_path, client = setup
        team_id = _insert_team_for_cascade(db_path, is_active=0)  # eligible
        data = _seed_full_team_data(db_path, team_id)
        report_id = _insert_report(
            db_path, team_id, slug="run-cascade-2", report_path=None
        )
        _insert_run_row(db_path, report_id)

        response = client.post(
            f"/admin/reports/{report_id}/delete",
            data={"csrf_token": _CSRF},
            follow_redirects=False,
        )
        assert response.status_code == 303

        assert _count_rows(db_path, "reports", "id = ?", (report_id,)) == 0
        assert _count_rows(
            db_path, "report_generation_runs", "report_id = ?", (report_id,)
        ) == 0
        assert _count_rows(db_path, "teams", "id = ?", (team_id,)) == 0
        assert _count_rows(db_path, "games", "game_id = ?", (data["game_id"],)) == 0


# ===========================================================================
# E-240-03: scheduled_report_runs cascade + audit-survival (TN-6).
#   * Team deletion REMOVES the slot rows (own_team_id cascade).
#   * Report deletion only NULLs report_id (ON DELETE SET NULL) -- the audit
#     row SURVIVES. This is the deliberate mirror-image of E-235's "run row
#     gone after report delete", guarding against an implementer copying the
#     CASCADE pattern and destroying the audit trail.
# ===========================================================================


def _insert_scheduled_run_row(
    db_path: Path,
    own_team_id: int,
    *,
    opponent_root_team_id: str = "root-sched",
    game_date: str = "2026-06-20",
    resolution_outcome: str = "auto_resolved",
    report_id: int | None = None,
    delivery_status: str | None = None,
) -> int:
    conn = _get_conn(db_path)
    cursor = conn.execute(
        "INSERT INTO scheduled_report_runs "
        "(game_date, own_team_id, opponent_root_team_id, resolution_outcome, "
        "report_id, delivery_status) VALUES (?, ?, ?, ?, ?, ?)",
        (
            game_date,
            own_team_id,
            opponent_root_team_id,
            resolution_outcome,
            report_id,
            delivery_status,
        ),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


class TestScheduledRunCascadeOnTeamDeletion:
    """AC-5: the team-deletion cascade removes scheduled_report_runs rows.

    The slots belong to the team whose schedule produced them, so deleting an
    eligible (cleanup-eligible) team via the report-delete cascade must remove
    its scheduled_report_runs rows.
    """

    def test_team_delete_cascade_removes_scheduled_runs(self, setup):
        db_path, client = setup
        team_id = _insert_team_for_cascade(db_path, is_active=0)  # eligible
        report_id = _insert_report(db_path, team_id, slug="sched-cascade-1")
        # A scheduled slot NOT linked to the deleted report (report_id NULL),
        # so its removal is attributable to the team cascade, not a report FK.
        _insert_scheduled_run_row(db_path, team_id, resolution_outcome="unresolved_mappable")
        assert _count_rows(
            db_path, "scheduled_report_runs", "own_team_id = ?", (team_id,)
        ) == 1

        response = client.post(
            f"/admin/reports/{report_id}/delete",
            data={"csrf_token": _CSRF},
            follow_redirects=False,
        )
        assert response.status_code == 303

        assert _count_rows(db_path, "teams", "id = ?", (team_id,)) == 0
        assert _count_rows(
            db_path, "scheduled_report_runs", "own_team_id = ?", (team_id,)
        ) == 0


class TestScheduledRunAuditSurvival:
    """AC-6: a scheduled_report_runs row SURVIVES report deletion with its
    report_id NULLed (ON DELETE SET NULL) -- it is NOT cascade-deleted.

    The deliberate mirror-image of TestRunRecordCleanupMirror. The team is a
    MEMBER team (is_active=1) so it survives BOTH the eligibility cascade AND the
    E-273 terminal reclamation -- the row's survival is attributable to the
    report->audit SET NULL behavior, not a (missing) team cascade. This also
    reflects reality: ``scheduled_report_runs.own_team_id`` is the operator's
    LSB (member) team, which reclamation never reclaims, so the audit trail is
    never destroyed by the sweep. (Pre-E-273 this relied on is_active=1 alone;
    the reclamation pass ignores is_active as a dead guard.)
    """

    def test_audit_row_survives_report_delete_with_report_id_nulled(self, setup):
        db_path, client = setup
        team_id = _insert_team_for_cascade(
            db_path, is_active=1, membership_type="member"
        )  # ineligible AND non-orphan
        report_id = _insert_report(
            db_path, team_id, slug="sched-survive-1", report_path=None
        )
        row_id = _insert_scheduled_run_row(
            db_path,
            team_id,
            report_id=report_id,
            delivery_status="generated",
        )
        assert _count_rows(
            db_path, "scheduled_report_runs", "report_id = ?", (report_id,)
        ) == 1

        response = client.post(
            f"/admin/reports/{report_id}/delete",
            data={"csrf_token": _CSRF},
            follow_redirects=False,
        )
        assert response.status_code == 303

        # Report gone, but the audit row survives with report_id NULLed.
        assert _count_rows(db_path, "reports", "id = ?", (report_id,)) == 0
        conn = _get_conn(db_path)
        row = conn.execute(
            "SELECT report_id, delivery_status FROM scheduled_report_runs WHERE id = ?",
            (row_id,),
        ).fetchone()
        conn.close()
        assert row is not None, "audit row was cascade-deleted with the report"
        assert row[0] is None, "report_id should be NULLed (ON DELETE SET NULL)"
        assert row[1] == "generated", "the audit row's other columns are unchanged"
        # Ineligible team retained: confirms survival came from the report FK
        # behavior, not a team-delete cascade.
        assert _count_rows(db_path, "teams", "id = ?", (team_id,)) == 1


# ===========================================================================
# E-235-06: Surface run records + trust flags in the admin reports list (TN-6)
# ===========================================================================


def _insert_full_run_row(db_path: Path, report_id: int, **cols) -> None:
    """Insert a report_generation_runs row with caller-specified columns."""
    keys = ["report_id", *cols.keys()]
    placeholders = ",".join("?" for _ in keys)
    conn = _get_conn(db_path)
    conn.execute(
        f"INSERT INTO report_generation_runs ({','.join(keys)}) VALUES ({placeholders})",
        [report_id, *cols.values()],
    )
    conn.commit()
    conn.close()


class TestRunRecordSurfacing:
    """E-235-06 / TN-6: /admin/reports surfaces per-stage detail + operator-only
    trust flags from report_generation_runs, handles the no_games status, and
    stays NULL-safe for legacy reports with no run row."""

    def test_per_stage_detail_and_operator_flags_rendered(self, setup):
        """AC-1/AC-2: per-stage detail, counts, and operator flags appear."""
        db_path, client = setup
        team_id = _insert_team(db_path)
        # season_id_used FK-references seasons(season_id).
        _conn = _get_conn(db_path)
        _conn.execute(
            "INSERT OR IGNORE INTO seasons (season_id, name, year) "
            "VALUES ('2026', 'Spring 2026 HS', 2026)"
        )
        _conn.commit()
        _conn.close()
        report_id = _insert_report(db_path, team_id, slug="surf-1", status="ready")
        _insert_full_run_row(
            db_path, report_id,
            overall_status="completed", crawl_status="completed",
            load_status="completed", spray_status="completed", spray_games=5,
            plays_status="completed", plays_games_expected=10,
            plays_games_covered=8, reconciliation_status="completed",
            discrepancies_found=3, discrepancies_corrected=2,
            completed_games=12, completed_games_with_data=11,
            season_id_used="2026",
            identity_match_method="name_only",
        )

        html = client.get("/admin/reports").text
        assert "Pipeline:" in html        # per-stage detail block
        assert "Games:" in html           # N-of-M counts
        assert "name-only match" in html  # operator flag

    def test_no_games_status_badge(self, setup):
        """AC-1: the no_games terminal status gets its own badge."""
        db_path, client = setup
        team_id = _insert_team(db_path)
        report_id = _insert_report(db_path, team_id, slug="ng-1", status="no_games")
        _insert_full_run_row(
            db_path, report_id, overall_status="completed",
            completed_games=4, completed_games_with_data=0,
        )

        html = client.get("/admin/reports").text
        assert "No games" in html

    def test_report_without_run_row_renders_null_safe(self, setup):
        """AC-3: a legacy report with no run row renders without error and shows
        no per-stage block (LEFT join -> run columns NULL)."""
        db_path, client = setup
        team_id = _insert_team(db_path)
        _insert_report(db_path, team_id, slug="legacy-1", status="ready")

        response = client.get("/admin/reports")
        assert response.status_code == 200
        assert "Pipeline:" not in response.text

    def test_clean_run_has_no_operator_flags(self, setup):
        """A fully-anchored run shows no operator flag."""
        db_path, client = setup
        team_id = _insert_team(db_path)
        report_id = _insert_report(db_path, team_id, slug="clean-1", status="ready")
        _insert_full_run_row(
            db_path, report_id, overall_status="completed",
            identity_match_method="anchor",
            completed_games=10, completed_games_with_data=10,
        )

        html = client.get("/admin/reports").text
        assert "Pipeline:" in html
        assert "name-only match" not in html

    def test_partial_stage_distinct_and_counts_and_degraded_badge(self, setup):
        """E-236-07 AC-2/AC-3/AC-4: a 'partial' stage renders with a distinct,
        CHECKABLE CSS class; the four new count columns are surfaced for
        drill-down; and because the run completed overall WITH a degraded stage,
        the derived operator-degraded badge appears."""
        db_path, client = setup
        team_id = _insert_team(db_path)
        report_id = _insert_report(
            db_path, team_id, slug="partial-1", status="ready",
        )
        _insert_full_run_row(
            db_path, report_id,
            overall_status="completed", crawl_status="completed",
            load_status="partial", load_errors=2,
            spray_status="completed", spray_games=6, spray_games_with_data=4,
            plays_status="partial", plays_games_expected=10,
            plays_games_covered=8, plays_errors=3,
            reconciliation_status="completed", boxscores_fetched=9,
            completed_games=12, completed_games_with_data=11,
        )

        html = client.get("/admin/reports").text
        # AC-2: the NEW 'partial' value gets a distinct, assertable CSS class.
        assert "pipeline-status-partial" in html
        # AC-4: the four new count columns are surfaced.
        assert "2 err" in html               # load_errors
        assert "3 err" in html               # plays_errors
        assert "9 boxscores fetched" in html  # boxscores_fetched
        assert "(4/6)" in html               # spray_games_with_data / spray_games
        # AC-3: derived operator-degraded badge (completed overall + partial stage).
        assert "operator-degraded" in html

    def test_clean_run_has_no_operator_degraded_badge(self, setup):
        """E-236-07 AC-3 (negative): a run where every stage completed shows NO
        operator-degraded badge."""
        db_path, client = setup
        team_id = _insert_team(db_path)
        report_id = _insert_report(db_path, team_id, slug="clean-deg", status="ready")
        _insert_full_run_row(
            db_path, report_id,
            overall_status="completed", crawl_status="completed",
            load_status="completed", spray_status="completed",
            plays_status="completed", reconciliation_status="completed",
            completed_games=10, completed_games_with_data=10,
        )

        html = client.get("/admin/reports").text
        assert "operator-degraded" not in html

    def test_overall_failed_run_is_not_operator_degraded(self, setup):
        """E-236-07 AC-3 / TN-3 (orthogonality): a hard failure (overall_status
        == 'failed') is NOT 'degraded' -- degraded is specifically the
        completed-overall-but-a-stage-slipped case. The failed badge already
        communicates the hard failure."""
        db_path, client = setup
        team_id = _insert_team(db_path)
        report_id = _insert_report(db_path, team_id, slug="failed-deg", status="failed")
        _insert_full_run_row(
            db_path, report_id,
            overall_status="failed", crawl_status="completed",
            load_status="failed", load_errors=1, error_stage="load",
        )

        html = client.get("/admin/reports").text
        assert "operator-degraded" not in html

    def test_null_spray_games_with_data_renders_null_safe(self, setup):
        """Phase 4b LOW: a run row with spray_games present but
        spray_games_with_data NULL (legacy / pre-migration) must render the
        NULL-safe '–' (unknown/not recorded), NOT a false '(0/N)'. Honors the
        db.py LEFT-JOIN NULL-safe contract."""
        db_path, client = setup
        team_id = _insert_team(db_path)
        report_id = _insert_report(db_path, team_id, slug="nullspray", status="ready")
        _insert_full_run_row(
            db_path, report_id,
            overall_status="completed", crawl_status="completed",
            load_status="completed", spray_status="completed",
            spray_games=5,  # spray_games_with_data intentionally NOT set -> NULL
        )

        html = client.get("/admin/reports").text
        # NULL with_data must NOT be coerced to a false 0.
        assert "(0/5)" not in html
        # The NULL-safe en-dash treatment is shown instead.
        assert "(–/5)" in html

    def test_failed_report_error_message_surfaced(self, setup):
        """AC-2: the report-level error_message (already selected) is rendered."""
        db_path, client = setup
        team_id = _insert_team(db_path)
        _insert_report(
            db_path, team_id, slug="fail-1", status="failed",
            error_message="kaboom-error-detail",
        )

        html = client.get("/admin/reports").text
        assert "kaboom-error-detail" in html

    def test_no_games_report_exposes_shareable_link(self, setup):
        """Phase 4b MEDIUM-2: a no_games report exposes its view/copy link in
        the admin list (it is a real shareable page, not a 404)."""
        db_path, client = setup
        team_id = _insert_team(db_path)
        _insert_report(db_path, team_id, slug="ng-link-1", status="no_games")

        html = client.get("/admin/reports").text
        assert "/reports/ng-link-1" in html  # the shareable URL is linked
        assert ">View</a>" in html

    def test_failed_report_has_no_shareable_link(self, setup):
        """A failed report stays unlinked (no shareable page)."""
        db_path, client = setup
        team_id = _insert_team(db_path)
        _insert_report(db_path, team_id, slug="fail-link", status="failed")

        html = client.get("/admin/reports").text
        assert "/reports/fail-link" not in html


# ===========================================================================
# E-273-02: reclamation wired into the delete path (_delete_report).
#   The pass runs UNCONDITIONALLY at the end of every _delete_report, on a
#   fresh connection after conn1/conn2, so the ownership invariant self-heals
#   after any delete -- and it never deletes an in-flight generation's data.
# ===========================================================================


def _insert_orphan_team(db_path: Path, name: str) -> int:
    """A tracked team with no reports and no games -- a reclamation target."""
    return _insert_team_for_cascade(db_path, name=name, is_active=0)


class TestReclamationWiredIntoDeletePath:
    """AC-1, AC-2, AC-4, AC-6: the E-273-01 pass runs at the end of every
    _delete_report and honors its reap-then-gate guard at the real wiring site.
    """

    def test_ac1_delete_frees_orphan_reclaimed_invariant_zero(self, setup):
        """AC-1: a report deletion that frees an orphan team leaves the
        ownership-invariant count at ZERO -- and a PRE-EXISTING opponent stub
        the per-report cascade never targets (RC#2) is reclaimed too."""
        from src.reports.lifecycle import count_orphan_reference_data

        db_path, client = setup
        team_id = _insert_team_for_cascade(db_path, is_active=0)  # eligible
        report_id = _insert_report(db_path, team_id, slug="reclaim-1")
        # An opponent-stub orphan NOT owned by this report's team -- outside any
        # single cascade's scope; only the terminal reclamation reaches it.
        stub = _insert_orphan_team(db_path, name="OpponentStub")

        assert _count_rows(db_path, "teams", "id = ?", (stub,)) == 1

        response = client.post(
            f"/admin/reports/{report_id}/delete",
            data={"csrf_token": _CSRF},
            follow_redirects=False,
        )
        assert response.status_code == 303

        assert _count_rows(db_path, "teams", "id = ?", (team_id,)) == 0
        assert _count_rows(db_path, "teams", "id = ?", (stub,)) == 0, (
            "the terminal reclamation must reclaim the stub the cascade never targeted"
        )
        conn = _get_conn(db_path)
        counts = count_orphan_reference_data(conn)
        conn.close()
        assert (counts.teams, counts.players, counts.roster_rows) == (0, 0, 0)

    def test_ac2_reclaims_prior_orphan_when_own_team_ineligible(self, setup):
        """AC-2: even when THIS report's team is not cascade-eligible (conn2
        never opens), the unconditional terminal reclamation still runs and
        reclaims an orphan left by a PRIOR deletion."""
        from src.reports.lifecycle import count_orphan_reference_data

        db_path, client = setup
        # Report team is a MEMBER team with is_active=1 -> not cascade-eligible
        # (conn2 skipped) AND never an orphan (survives reclamation), isolating
        # the assertion to "the OTHER orphan was reclaimed".
        own_team = _insert_team_for_cascade(
            db_path, name="OwnMember", is_active=1, membership_type="member"
        )
        report_id = _insert_report(db_path, own_team, slug="ineligible-del")
        prior_orphan = _insert_orphan_team(db_path, name="PriorOrphan")

        response = client.post(
            f"/admin/reports/{report_id}/delete",
            data={"csrf_token": _CSRF},
            follow_redirects=False,
        )
        assert response.status_code == 303

        # The ineligible report team survived (conn2 never ran, reclamation skips
        # member teams); the prior orphan was reclaimed by the terminal pass.
        assert _count_rows(db_path, "teams", "id = ?", (own_team,)) == 1
        assert _count_rows(db_path, "teams", "id = ?", (prior_orphan,)) == 0
        conn = _get_conn(db_path)
        assert count_orphan_reference_data(conn).teams == 0
        conn.close()

    def test_ac4_deferred_when_live_generating_report_exists(self, setup):
        """AC-4: a genuinely-live 'generating' report defers the sweep at the
        wiring site -- no reference rows are deleted (liveness delay)."""
        db_path, client = setup
        own_team = _insert_team_for_cascade(
            db_path, name="OwnMember", is_active=1, membership_type="member"
        )
        report_id = _insert_report(db_path, own_team, slug="trigger-del")
        # A FRESH (non-stale) generating report blocks the gate.
        gen_team = _insert_team_for_cascade(db_path, name="GenTeam", is_active=0)
        _insert_report(db_path, gen_team, slug="live-gen", status="generating")
        # An orphan that WOULD be reclaimed if the pass were not deferred.
        orphan = _insert_orphan_team(db_path, name="WouldBeReclaimed")

        response = client.post(
            f"/admin/reports/{report_id}/delete",
            data={"csrf_token": _CSRF},
            follow_redirects=False,
        )
        assert response.status_code == 303

        # Deferred: nothing reference-side deleted; the orphan survives.
        assert _count_rows(db_path, "teams", "id = ?", (orphan,)) == 1

    def test_ac4_proceeds_after_stale_generating_reaped(self, setup):
        """AC-4: a STALE 'generating' report is reaped, then the sweep proceeds
        -- the orphan is reclaimed and the stale report is marked failed."""
        db_path, client = setup
        own_team = _insert_team_for_cascade(
            db_path, name="OwnMember", is_active=1, membership_type="member"
        )
        report_id = _insert_report(db_path, own_team, slug="trigger-del-2")
        stale_team = _insert_team_for_cascade(db_path, name="StaleGen", is_active=0)
        stale_ts = (
            datetime.now(timezone.utc) - timedelta(seconds=7200)
        ).strftime(UTC_ISO_FORMAT)
        # Insert a stale generating report (old generated_at).
        conn = _get_conn(db_path)
        conn.execute(
            "INSERT INTO reports (slug, team_id, title, status, generated_at, expires_at) "
            "VALUES ('stale-gen', ?, 'Stale', 'generating', ?, ?)",
            (stale_team, stale_ts, _future_iso()),
        )
        conn.commit()
        conn.close()
        orphan = _insert_orphan_team(db_path, name="ReclaimedAfterReap")

        response = client.post(
            f"/admin/reports/{report_id}/delete",
            data={"csrf_token": _CSRF},
            follow_redirects=False,
        )
        assert response.status_code == 303

        assert _count_rows(db_path, "teams", "id = ?", (orphan,)) == 0
        assert (
            _count_rows(db_path, "reports", "slug = ? AND status = 'failed'", ("stale-gen",))
            == 1
        ), "the stale generating report should have been reaped to failed"

    def test_ac6_opponent_links_and_grants_survive_deletion_path(self, setup):
        """AC-6 / TN-7: the wiring did not reintroduce §6.1 destruction -- an
        opponent_links operator decision and a user_team_access grant survive a
        deletion-path invocation of the pass, while a genuine orphan is swept."""
        db_path, client = setup
        own_team = _insert_team_for_cascade(
            db_path, name="OwnMember", is_active=1, membership_type="member"
        )
        report_id = _insert_report(db_path, own_team, slug="roots-del")

        conn = _get_conn(db_path)
        member = conn.execute(
            "INSERT INTO teams (name, membership_type) VALUES ('MemberOwner', 'member')"
        ).lastrowid
        resolved = conn.execute(
            "INSERT INTO teams (name, membership_type) VALUES ('ResolvedTarget', 'tracked')"
        ).lastrowid
        conn.execute(
            "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, "
            "resolved_team_id, resolution_method, resolved_at) "
            "VALUES (?, 'root-x', 'Opp', ?, 'operator', '2026-03-20')",
            (member, resolved),
        )
        granted = conn.execute(
            "INSERT INTO teams (name, membership_type) VALUES ('GrantedTeam', 'tracked')"
        ).lastrowid
        user = conn.execute(
            "INSERT INTO users (email) VALUES ('grantee@example.com')"
        ).lastrowid
        conn.execute(
            "INSERT INTO user_team_access (user_id, team_id) VALUES (?, ?)",
            (user, granted),
        )
        conn.commit()
        conn.close()
        orphan = _insert_orphan_team(db_path, name="GenuineOrphan6")

        response = client.post(
            f"/admin/reports/{report_id}/delete",
            data={"csrf_token": _CSRF},
            follow_redirects=False,
        )
        assert response.status_code == 303

        # The genuine orphan is reclaimed; every root survivor is untouched.
        assert _count_rows(db_path, "teams", "id = ?", (orphan,)) == 0
        assert _count_rows(db_path, "teams", "id = ?", (resolved,)) == 1
        assert _count_rows(db_path, "teams", "id = ?", (granted,)) == 1
        assert _count_rows(db_path, "opponent_links", "our_team_id = ?", (member,)) == 1
        conn = _get_conn(db_path)
        ol = conn.execute(
            "SELECT resolved_team_id FROM opponent_links WHERE our_team_id = ?",
            (member,),
        ).fetchone()
        grant = conn.execute(
            "SELECT COUNT(*) FROM user_team_access WHERE team_id = ?", (granted,)
        ).fetchone()[0]
        conn.close()
        assert ol[0] == resolved, "resolved_team_id must NOT be NULLed by the pass"
        assert grant == 1, "user_team_access grant must survive the pass"


# ===========================================================================
# E-273-04: batch invariant integration test (the epic's flagship AC).
#
#   The order-dependent, cross-perspective batch deletion that would have
#   caught this class of orphan. It reproduces BOTH root causes in ONE fixture:
#     * RC#1 -- a report team (T1) retained across the sequence by a shared,
#       cross-perspective `games` row (G12) whose OTHER perspective (T2) keeps
#       it alive after T1's own report is deleted; when T2's report is later
#       deleted the shared game dies and T1 becomes a gameless orphan that only
#       the terminal reclamation reclaims.
#     * RC#2 -- a shared opponent stub (S) referenced by all three reports'
#       games, never in any single cascade's scope, reclaimed only by the pass.
#   No single-report delete reproduces the RC#1 retention -- the ordering is
#   load-bearing, which is why the MID-SEQUENCE anti-vacuity assertion (AC-1a)
#   proves the retention was actually REALIZED before the final zero assertion.
# ===========================================================================


def _seed_batch_invariant_fixture(db_path: Path) -> dict:
    """Seed the order-dependent cross-perspective batch fixture directly (the
    orphan conditions are a DB-STATE property, not a pipeline property).

    Returns a dict of the seeded ids the test asserts against.
    """
    conn = _get_conn(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) "
        "VALUES ('2026', 'Spring 2026 HS', 2026)"
    )

    def _team(name, membership="tracked"):
        return conn.execute(
            "INSERT INTO teams (name, membership_type, is_active) VALUES (?, ?, 0)",
            (name, membership),
        ).lastrowid

    # Three report teams + the shared opponent stub (no report of its own).
    t1 = _team("Report Team 1")
    t2 = _team("Report Team 2")
    t3 = _team("Report Team 3")
    s = _team("Shared Opponent Stub")

    # Intentional survivors (TN-7) -- MANDATORY per AC-3.
    resolved = _team("Resolved Opp Survivor")          # opponent_links root
    granted = _team("Granted Team Survivor")           # user_team_access root
    member = _team("Our Member Team", membership="member")

    # Reports (quiescent -- all 'ready', no 'generating', per AC-4). Inserted on
    # THIS connection (not via _insert_report, which opens its own connection and
    # would deadlock against this open write transaction).
    def _report(slug, team_id):
        return conn.execute(
            "INSERT INTO reports (slug, team_id, title, status, generated_at, expires_at) "
            "VALUES (?, ?, 'Batch Report', 'ready', ?, ?)",
            (slug, team_id, utcnow_iso(), _future_iso()),
        ).lastrowid

    r1 = _report("batch-r1", t1)
    r2 = _report("batch-r2", t2)
    r3 = _report("batch-r3", t3)

    def _game(game_id, home, away):
        conn.execute(
            "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id) "
            "VALUES (?, '2026', '2026-04-01', ?, ?)",
            (game_id, home, away),
        )

    def _perspective(game_id, team_id):
        conn.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?, ?)",
            (game_id, team_id),
        )

    # G12: the SHARED cross-perspective game between T1 and T2 -- the RC#1
    # retention mechanism. Two perspective rows: deleting T1's report retains
    # G12 (T2's perspective keeps it alive) so T1's teams row is retained;
    # deleting T2's report removes the last perspective, G12 dies, and T1 is
    # freed as a gameless orphan.
    _game("g12", t1, t2)
    _perspective("g12", t1)
    _perspective("g12", t2)

    # Each report team also played the shared opponent stub S (single
    # perspective each -- S is a stub with no perspective of its own).
    for gid, rt in (("g1s", t1), ("g2s", t2), ("g3s", t3)):
        _game(gid, rt, s)
        _perspective(gid, rt)

    # Players: roster-only players on each team (transitively orphaned when the
    # team goes) + a plays-only player reachable ONLY via plays in the LAST game
    # deleted (G3S), so it survives the earlier reclamations and is reclaimed
    # only once its plays die (TN-3 `plays` inclusion, exercised across the
    # sequence).
    def _player(pid, first="First", last="Last"):
        conn.execute(
            "INSERT INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
            (pid, first, last),
        )

    def _roster(team_id, pid):
        conn.execute(
            "INSERT INTO team_rosters (team_id, player_id, season_id) VALUES (?, ?, '2026')",
            (team_id, pid),
        )

    for pid, team_id in (
        ("p-t1", t1), ("p-t2", t2), ("p-t3", t3), ("p-s", s),
    ):
        _player(pid)
        _roster(team_id, pid)

    _player("p-plays")
    conn.execute(
        "INSERT INTO plays "
        "(game_id, play_order, inning, half, season_id, batting_team_id, "
        "perspective_team_id, batter_id) "
        "VALUES ('g3s', 1, 1, 'top', '2026', ?, ?, 'p-plays')",
        (t3, t3),
    )

    # Intentional survivor wiring: RESOLVED as an opponent_links.resolved_team_id
    # target (our_team_id = member), GRANTED carrying a user_team_access grant.
    conn.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, "
        "resolved_team_id, resolution_method, resolved_at) "
        "VALUES (?, 'root-r', 'Resolved Opp', ?, 'operator', '2026-03-20')",
        (member, resolved),
    )
    user_id = conn.execute(
        "INSERT INTO users (email) VALUES ('grantee-batch@example.com')"
    ).lastrowid
    conn.execute(
        "INSERT INTO user_team_access (user_id, team_id) VALUES (?, ?)",
        (user_id, granted),
    )

    conn.commit()
    conn.close()
    return {
        "t1": t1, "t2": t2, "t3": t3, "s": s,
        "resolved": resolved, "granted": granted, "member": member,
        "r1": r1, "r2": r2, "r3": r3,
    }


class TestBatchInvariantReclamation:
    """AC-1..AC-5 (flagship): the order-dependent, cross-perspective batch delete
    holds the ownership invariant at zero -- the test that would have caught this
    class of orphan.
    """

    def _delete(self, client, report_id):
        resp = client.post(
            f"/admin/reports/{report_id}/delete",
            data={"csrf_token": _CSRF},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        return resp

    def test_batch_delete_holds_ownership_invariant_at_zero(self, setup):
        """AC-1..AC-5. ORDER-DEPENDENT: R1 must be deleted BEFORE R2 so the shared
        cross-perspective game (G12) retains T1 as an orphan-in-waiting; the
        single-delete path never reproduces this, which is why the mid-sequence
        anti-vacuity assertion (AC-1a) is load-bearing."""
        from src.reports.lifecycle import count_orphan_reference_data

        db_path, client = setup
        ids = _seed_batch_invariant_fixture(db_path)

        # --- Delete #1 (T1's report) -------------------------------------------
        # cascade_delete_team(T1) removes T1's G12 perspective, but G12 survives
        # on T2's perspective and still FK-references T1 (home_team_id) -> T1's
        # teams row is RETAINED even though its own report is gone.
        self._delete(client, ids["r1"])

        # AC-1a MID-SEQUENCE anti-vacuity gate: prove the RC#1 retention was
        # REALIZED -- the shared team still EXISTS, now has ZERO of its own
        # reports rows, and is retained specifically because the shared
        # cross-perspective game survived. Without this the whole test could pass
        # vacuously (no orphan ever created -> invariant trivially zero).
        assert _count_rows(db_path, "teams", "id = ?", (ids["t1"],)) == 1, (
            "RC#1: T1 must be RETAINED after the first delete (cross-perspective "
            "games FK still references it) -- the order-dependent orphan-in-waiting"
        )
        assert _count_rows(db_path, "reports", "team_id = ?", (ids["t1"],)) == 0, (
            "T1 now holds ZERO of its own reports -- a retained orphan-in-waiting"
        )
        assert _count_rows(db_path, "games", "game_id = 'g12'") == 1, (
            "the shared cross-perspective game must survive on T2's perspective "
            "(this is WHY T1 was retained)"
        )
        # The plays-only player is still reachable via its (not-yet-deleted)
        # plays row -- not falsely reclaimed early (TN-3).
        assert _count_rows(db_path, "players", "player_id = 'p-plays'") == 1

        # --- Delete #2 (T2's report) -------------------------------------------
        # Removes G12's last perspective -> G12 dies -> T1 is now a gameless
        # orphan that the terminal reclamation reclaims in THIS delete.
        self._delete(client, ids["r2"])
        assert _count_rows(db_path, "teams", "id = ?", (ids["t1"],)) == 0, (
            "RC#1 reclaimed: once the shared game died, the retained team is swept"
        )

        # --- Delete #3 (T3's report) -------------------------------------------
        # Frees the last game touching the shared opponent stub S (RC#2) and the
        # plays-only player.
        self._delete(client, ids["r3"])

        # AC-1b / AC-2 / AC-5: the SINGLE-SOURCE invariant helper returns zero for
        # all three orphan classes (NOT "the delete succeeded").
        conn = _get_conn(db_path)
        counts = count_orphan_reference_data(conn)
        conn.close()
        assert (counts.teams, counts.players, counts.roster_rows) == (0, 0, 0), (
            f"ownership invariant must be zero after the batch delete, got {counts!r}"
        )

        # AC-2 (players leak, explicit): every transitively-orphaned player --
        # roster-only AND the plays-only one -- is gone.
        for pid in ("p-t1", "p-t2", "p-t3", "p-s", "p-plays"):
            assert _count_rows(db_path, "players", "player_id = ?", (pid,)) == 0, (
                f"transitively-dead player {pid} must be reclaimed"
            )
        assert _count_rows(db_path, "teams", "id = ?", (ids["s"],)) == 0, (
            "RC#2: the shared opponent stub is reclaimed by the batch"
        )

        # AC-3: the MANDATORY intentional survivors are NOT reclaimed and the
        # invariant did NOT flag them as leaks (the zero above already proves the
        # non-flagging, since count derives from the roots-excluding predicate).
        assert _count_rows(db_path, "teams", "id = ?", (ids["resolved"],)) == 1, (
            "opponent_links.resolved_team_id target must survive"
        )
        assert _count_rows(db_path, "teams", "id = ?", (ids["granted"],)) == 1, (
            "user_team_access-granted team must survive"
        )
        conn = _get_conn(db_path)
        ol_resolved = conn.execute(
            "SELECT resolved_team_id FROM opponent_links WHERE our_team_id = ?",
            (ids["member"],),
        ).fetchone()
        grant_count = conn.execute(
            "SELECT COUNT(*) FROM user_team_access WHERE team_id = ?",
            (ids["granted"],),
        ).fetchone()[0]
        conn.close()
        assert ol_resolved is not None and ol_resolved[0] == ids["resolved"], (
            "the opponent_links operator decision must be intact (not NULLed)"
        )
        assert grant_count == 1, "the user_team_access grant must be intact"


# ---------------------------------------------------------------------------
# Generate-concurrency cap (spec 2026-08-10-admin-generate-concurrency): the
# admin generate route admits at most MAX_CONCURRENT_ADMIN_GENERATIONS in-flight
# generations started from POST /admin/reports/generate.
#
# Group (A) -- the four classes below TestAdminGenerate_WhenTheCapIsReached
# through TestAdminGenerate_WhenTwoRequestsRaceAtCapOne -- is RED-first: none
# can pass before the route change, because today's route has no admission
# check at all.
#
# Group (B) -- TestAdminGenerate_WhenTheUrlIsInvalid and
# TestTheCheckedInTopology -- passes today BY CONSTRUCTION. It pins a property
# the change must not break, so RED-first does not apply and its only proof of
# worth is mutation (M2 and M4 respectively).
# ---------------------------------------------------------------------------


@contextmanager
def _slots(n: int, wrapper=None):
    """Swap the module-level semaphore for a fresh ``BoundedSemaphore(n)``.

    The real semaphore is constructed from MAX_CONCURRENT_ADMIN_GENERATIONS at
    import time, so monkeypatching the CONSTANT changes nothing -- a test must
    replace ``_generation_slots`` itself and restore it. There is no injection
    seam at a module global; `testing.md` prefers DI and this is the stated
    exception, not an oversight. Every test that acquires a slot must release
    it, or it poisons later tests in the same process -- the restore here is the
    backstop for that.
    """
    original = reports_admin._generation_slots
    fresh = threading.BoundedSemaphore(n)
    reports_admin._generation_slots = wrapper(fresh) if wrapper else fresh
    try:
        yield fresh
    finally:
        reports_admin._generation_slots = original


def _post_generate(client, gc_url: str = "https://web.gc.com/teams/abc123/test"):
    return client.post(
        "/admin/reports/generate",
        data={"gc_url": gc_url, "csrf_token": _CSRF},
        follow_redirects=False,
    )


def _is_refusal(response) -> bool:
    location = response.headers["location"]
    return "error=" in location and "already" in location


class TestAdminGenerate_WhenTheCapIsReached:
    """Every generation slot is already held by an in-flight generation."""

    def test_redirects_with_an_error_flash(self, setup):
        _db_path, client = setup

        with _slots(2) as slots:
            assert slots.acquire(blocking=False)
            assert slots.acquire(blocking=False)
            response = _post_generate(client)
            slots.release()
            slots.release()

        assert response.status_code == 303
        assert "/admin/reports?error=" in response.headers["location"]
        assert _is_refusal(response)

    def test_does_not_enqueue_a_generation(self, setup):
        _db_path, client = setup

        with _slots(2) as slots:
            assert slots.acquire(blocking=False)
            assert slots.acquire(blocking=False)
            with patch("src.reports.generator.generate_report") as mock_gen:
                _post_generate(client)
            slots.release()
            slots.release()

        mock_gen.assert_not_called()


class TestAdminGenerate_WhenAGenerationFinishes:
    """A generation that returns normally hands its slot back."""

    def test_the_slot_is_returned(self, setup):
        _db_path, client = setup

        # Probing DURING the generation is what keeps this test honest: a fresh
        # semaphore is free whether or not the route ever acquired it, so
        # "free afterwards" alone would pass vacuously against a route with no
        # admission check at all.
        with _slots(1) as slots:
            free_during = None

            def probe(_gc_url):
                nonlocal free_during
                free_during = slots.acquire(blocking=False)
                if free_during:
                    slots.release()

            with patch("src.reports.generator.generate_report", side_effect=probe):
                # TestClient runs background tasks synchronously, so the
                # releasing wrapper's finally: has already run by the time the
                # response comes back.
                response = _post_generate(client)

            free_after = slots.acquire(blocking=False)
            if free_after:
                slots.release()

        assert not _is_refusal(response)
        assert free_during is False, "the running generation was not holding a slot"
        assert free_after is True, "the finished generation did not release its slot"


class TestAdminGenerate_WhenTheGenerationRaises:
    """A generation that blows up STILL hands its slot back."""

    def test_the_slot_is_still_returned(self, setup):
        _db_path, client = setup

        with _slots(1) as slots:
            free_during = None

            def probe_then_raise(_gc_url):
                nonlocal free_during
                free_during = slots.acquire(blocking=False)
                if free_during:
                    slots.release()
                raise RuntimeError("generation blew up")

            # The exception surfaces in the background task, after the response
            # has been sent; TestClient(raise_server_exceptions=False) does not
            # re-raise it here. The point of this test is the finally:, not the
            # exception's propagation.
            with patch("src.reports.generator.generate_report", side_effect=probe_then_raise):
                _post_generate(client)

            free_after = slots.acquire(blocking=False)
            if free_after:
                slots.release()

        assert free_during is False, "the running generation was not holding a slot"
        assert free_after is True, "a raising generation leaked its slot"


class TestAdminGenerate_WhenTheGenerationImportFails:
    """The background task cannot even IMPORT the generator.

    Regression pin for a codex P1: the call-time import used to sit ABOVE the
    try/finally, so an ImportError (a circular-import regression, a missing
    transitive dependency) skipped the release and leaked the slot PERMANENTLY.
    Two such failures wedge the generate page until the process restarts.
    """

    def test_the_slot_is_still_returned(self, setup):
        _db_path, client = setup

        with _slots(1) as slots:
            # None in sys.modules makes `from src.reports.generator import ...`
            # raise ImportError at call time, which is exactly the shape that
            # used to bypass the finally.
            with patch.dict(sys.modules, {"src.reports.generator": None}):
                _post_generate(client)

            free_after = slots.acquire(blocking=False)
            if free_after:
                slots.release()

        assert free_after is True, "a failed generator import leaked its slot"


class TestAdminGenerate_WhenTwoRequestsRaceAtCapOne:
    """Two submissions reach the acquire seam simultaneously with ONE slot free.

    Modeled on tests/test_passkey.py::test_cap_hard_bound_under_concurrent_inserts.
    A `threading.Barrier(2)` sits ON the acquire seam so both threads enter it
    together, and the winner's generation blocks inside the background task so it
    is genuinely still holding the slot when the loser arrives.
    """

    def test_exactly_one_wins(self, setup):
        _db_path, client = setup

        barrier = threading.Barrier(2)

        class _BarrieredSemaphore:
            def __init__(self, sem):
                self._sem = sem

            def acquire(self, blocking=True):
                barrier.wait(timeout=10)
                return self._sem.acquire(blocking=blocking)

            def release(self):
                self._sem.release()

        winner_is_holding = threading.Event()
        may_finish = threading.Event()
        refusal_seen = threading.Event()
        results: dict[str, bool] = {}

        def blocking_generate(_gc_url):
            winner_is_holding.set()
            may_finish.wait(timeout=10)

        def worker(name: str) -> None:
            response = _post_generate(client)
            results[name] = _is_refusal(response)
            if results[name]:
                refusal_seen.set()

        with _slots(1, wrapper=_BarrieredSemaphore):
            with patch("src.reports.generator.generate_report", side_effect=blocking_generate):
                threads = [threading.Thread(target=worker, args=(n,)) for n in ("a", "b")]
                for t in threads:
                    t.start()
                refusal_seen.wait(timeout=10)
                may_finish.set()
                for t in threads:
                    t.join(timeout=10)

        assert winner_is_holding.is_set(), "no request ever acquired the slot"
        assert len(results) == 2, "a request thread did not finish"
        assert sum(1 for refused in results.values() if not refused) == 1, (
            f"exactly one request must be admitted, got {results}"
        )
        assert sum(1 for refused in results.values() if refused) == 1, (
            f"exactly one request must be refused, got {results}"
        )


class TestAdminGenerate_WhenTheUrlIsInvalid:
    """Group (B) guard: a URL rejected by validation must not burn a slot.

    Green today because there are no slots at all; its worth is proven by mutant
    M2 (the acquire moved above the URL validations). This catches the single
    worst way to get this change wrong -- two bad pastes permanently wedging the
    page.
    """

    def test_no_slot_is_consumed(self, setup):
        _db_path, client = setup

        # Deliberately NOT routed through _slots(): this guard must be runnable
        # at the pre-change commit, where no semaphore exists at all. It runs
        # against whatever admission mechanism the route actually has.
        _post_generate(client, "   ")
        _post_generate(client, "not a url !!!")
        _post_generate(client, "72bb77d8-54ca-42d2-8547-9da4880d0cb4")

        with patch("src.reports.generator.generate_report") as mock_gen:
            response = _post_generate(client)

        assert not _is_refusal(response)
        mock_gen.assert_called_once()


class TestAdminGenerate_WhenAGenerationIsInFlightAnywhere:
    """A generation is running SOMEWHERE -- CLI, cron, or this page.

    The cross-path gate (operator ruling 2026-08-16, after a UI click raced the
    serial CLI restore run and hard-deleted stat rows on games the CLI was
    actively writing). The semaphore cannot see another PROCESS; only the shared
    `reports` table can. There is no source column anywhere, so this gate
    deliberately does not distinguish a CLI run from this page's own in-flight
    generation -- the page is one-at-a-time by ruling.
    """

    def test_redirects_with_an_error_flash(self, setup):
        db_path, client = setup
        team_id = _insert_team(db_path)
        _insert_report(db_path, team_id, slug="in-flight", status="generating")

        # Isolated from the real module semaphore deliberately: these tests drive
        # the route to a REFUSAL, and under a slot-leaking regression they would
        # otherwise drain the real semaphore and make LATER tests fail for an
        # unrelated reason (measured against mutant M6).
        with _slots(2):
            response = _post_generate(client)

        assert response.status_code == 303
        location = response.headers["location"]
        assert "/admin/reports?error=" in location
        assert "in+progress" in location

    def test_does_not_enqueue_a_generation(self, setup):
        db_path, client = setup
        team_id = _insert_team(db_path)
        _insert_report(db_path, team_id, slug="in-flight", status="generating")

        with _slots(2), patch("src.reports.generator.generate_report") as mock_gen:
            _post_generate(client)

        mock_gen.assert_not_called()

    def test_no_slot_is_consumed(self, setup):
        db_path, client = setup
        team_id = _insert_team(db_path)
        _insert_report(db_path, team_id, slug="in-flight", status="generating")

        # Asserting only the slot state would pass vacuously against a route with
        # no gate at all, so the refusal itself is asserted alongside it. This is
        # the ordering pin: the cross-path check runs BEFORE the acquire, so a
        # refusal cannot leak a slot.
        with _slots(2) as slots:
            response = _post_generate(client)
            free = [slots.acquire(blocking=False) for _ in range(2)]
            for got in free:
                if got:
                    slots.release()

        assert "error=" in response.headers["location"]
        assert free == [True, True], "the cross-path refusal consumed a semaphore slot"


class TestAdminGenerate_WhenTheOnlyGeneratingRowIsStale:
    """The sole `generating` row is older than STALE_GENERATING_SECONDS.

    Green today by construction (today nothing blocks at all); its only proof of
    worth is mutant M7, which counts before reaping. A crashed generation must
    not wedge the admin page for the full hour-long staleness threshold.
    """

    def test_the_submission_proceeds(self, setup, tmp_path):
        db_path, client = setup
        tmp_reports = tmp_path / "reports"
        tmp_reports.mkdir()
        team_id = _insert_team(db_path)
        stale = (
            datetime.now(timezone.utc)
            - timedelta(seconds=lifecycle.STALE_GENERATING_SECONDS + 600)
        ).strftime(UTC_ISO_FORMAT)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO reports (slug, team_id, title, status, generated_at, expires_at) "
            "VALUES ('stale-gen', ?, 'Stale', 'generating', ?, ?)",
            (team_id, stale, _future_iso()),
        )
        conn.commit()
        conn.close()

        # The reaper UNLINKS _REPORTS_DIR/"{slug}.html" for every row it reaps.
        # Without redirecting that seam this test would delete a real
        # data/reports/stale-gen.html from the checkout (codex P2).
        with patch("src.reports.lifecycle._REPORTS_DIR", tmp_reports), \
                patch("src.reports.generator.generate_report") as mock_gen:
            response = _post_generate(client)

        assert not _is_refusal(response) and "error=" not in response.headers["location"]
        mock_gen.assert_called_once()


class TestTheCapValue:
    """The cap's NUMBER, pinned to the operator ruling of 2026-08-16.

    Not redundant with the cap-behavior tests above, and the redundancy it looks
    like is exactly why it is here: every one of those tests installs its OWN
    ``BoundedSemaphore(n)`` (the spec-mandated mechanics -- the real semaphore is
    built from the constant at import, so patching the constant changes nothing).
    That decouples them from the constant completely. Measured: mutating
    MAX_CONCURRENT_ADMIN_GENERATIONS from 2 to 99 left the entire suite green.
    Any test whose setup DERIVES from the constant is tautological against a
    change to it, so a literal pin is the only thing that can catch one.
    """

    def test_is_the_operator_ruled_two(self):
        assert reports_admin.MAX_CONCURRENT_ADMIN_GENERATIONS == 2


class TestTheCheckedInTopology:
    """Group (B) guard for the cap's load-bearing premise (F3 / F3a).

    Named for what it CHECKS -- tracked launch files -- not for the served
    process count, which it cannot observe. Runtime replication of the container
    (a second compose project, a scaled service, a hand-run uvicorn) multiplies
    the cap to 2 x processes and no test can see it (F3b); that half is enforced
    only by the deployment invariant written into `docs/admin/operations.md`.
    """

    _BREAKAGE = (
        "MAX_CONCURRENT_ADMIN_GENERATIONS in src/api/routes/reports_admin.py is an "
        "IN-PROCESS cap on concurrent report generation. More than one server "
        "process multiplies it to 2 x processes against one SQLite file, with no "
        "warning of any kind. Re-think that cap before landing this."
    )

    def test_no_tracked_launch_file_starts_extra_workers(self):
        import yaml

        repo_root = Path(__file__).resolve().parent.parent

        launch_lines = [
            line
            for line in (repo_root / "Dockerfile").read_text().splitlines()
            if "uvicorn" in line or "gunicorn" in line
        ]
        assert launch_lines, "no uvicorn/gunicorn launch line found in Dockerfile"
        for line in launch_lines:
            for flag in ("--workers", " -w ", "--worker-class", " -k "):
                assert flag not in line, (
                    f"the Dockerfile launch line carries {flag!r}: {line.strip()}\n"
                    f"{self._BREAKAGE}"
                )

        compose_paths = [repo_root / "docker-compose.yml"]
        # F3a: docker-compose.override.yml is gitignored and untracked, so it is
        # absent in CI. Read it only if it happens to be present; its ABSENCE is
        # never a failure.
        override = repo_root / "docker-compose.override.yml"
        if override.exists():
            compose_paths.append(override)

        for path in compose_paths:
            # Parse the YAML rather than grepping: `command:` legitimately appears
            # on the `traefik` and `cloudflared` services, so a whole-file grep
            # would fail today, vacuously.
            services = (yaml.safe_load(path.read_text()) or {}).get("services") or {}
            app_service = services.get("app")
            if app_service is None:
                continue

            for key in ("command", "entrypoint"):
                # `entrypoint` overrides the Dockerfile CMD just as effectively
                # as `command` does.
                assert app_service.get(key) is None, (
                    f"{path.name} sets `{key}` on the `app` service.\n{self._BREAKAGE}"
                )
            replicas = (app_service.get("deploy") or {}).get("replicas")
            assert replicas is None, (
                f"{path.name} sets deploy.replicas={replicas} on `app`.\n{self._BREAKAGE}"
            )
            # uvicorn reads WEB_CONCURRENCY straight from the environment
            # (uvicorn/config.py: `if workers is None and "WEB_CONCURRENCY" in
            # os.environ`), so it multiplies workers with no launch-file change
            # at all. Catch the tracked ways it could be set.
            env = app_service.get("environment") or {}
            env_keys = env.keys() if isinstance(env, dict) else [
                str(e).split("=", 1)[0] for e in env
            ]
            assert "WEB_CONCURRENCY" not in env_keys, (
                f"{path.name} sets WEB_CONCURRENCY on `app`.\n{self._BREAKAGE}"
            )

    def test_web_concurrency_is_not_set_in_this_environment(self):
        # Separate from the tracked-file guard above because it observes a
        # DIFFERENT thing: the live process environment rather than a file. It is
        # the only handle any test has on the env-var route, and it is a weak one
        # -- production's value arrives via the `app` service's `env_file`, which
        # is untracked and unreadable here. See the deployment invariant in
        # docs/admin/operations.md; this asserts the dev container, not prod.
        assert os.environ.get("WEB_CONCURRENCY") in (None, "", "1"), (
            f"WEB_CONCURRENCY={os.environ.get('WEB_CONCURRENCY')!r} in this "
            f"environment.\n{self._BREAKAGE}"
        )
