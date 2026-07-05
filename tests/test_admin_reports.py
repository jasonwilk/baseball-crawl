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
    conn.execute(
        "INSERT INTO player_season_batting (player_id, team_id, season_id) VALUES ('player1', ?, ?)",
        (team_id, season_id),
    )
    conn.execute(
        "INSERT INTO player_season_pitching (player_id, team_id, season_id) VALUES ('player1', ?, ?)",
        (team_id, season_id),
    )

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
        assert _count_rows(db_path, "player_season_batting", "team_id = ?", (team_id,)) == 0
        assert _count_rows(db_path, "player_season_pitching", "team_id = ?", (team_id,)) == 0
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
        """AC-1: deleting a report removes its run record. The team is kept
        INELIGIBLE for cleanup (is_active=1), so the run-row removal is
        attributable to the report->run cascade, not the team cascade."""
        db_path, client = setup
        team_id = _insert_team_for_cascade(db_path, is_active=1)  # ineligible
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

    The deliberate mirror-image of TestRunRecordCleanupMirror. The team is kept
    INELIGIBLE for cleanup (is_active=1) so the row's survival is attributable
    to the report->run FK behavior, not a (missing) team cascade.
    """

    def test_audit_row_survives_report_delete_with_report_id_nulled(self, setup):
        db_path, client = setup
        team_id = _insert_team_for_cascade(db_path, is_active=1)  # ineligible
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
