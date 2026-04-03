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

    season_id = "2026-spring-hs"
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, 'Spring 2026 HS', 'spring-hs', 2026)",
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
        "INSERT INTO player_game_batting (game_id, player_id, team_id) VALUES (?, 'player1', ?)",
        (game_id, team_id),
    )
    conn.execute(
        "INSERT INTO player_game_pitching (game_id, player_id, team_id) VALUES (?, 'player1', ?)",
        (game_id, team_id),
    )
    conn.execute(
        "INSERT INTO spray_charts (game_id, team_id, player_id, season_id, chart_type, x, y) "
        "VALUES (?, ?, 'player1', ?, 'offensive', 100, 200)",
        (game_id, team_id, season_id),
    )

    cursor = conn.execute(
        "INSERT INTO plays (game_id, play_order, inning, half, season_id, "
        "batting_team_id, batter_id, pitcher_id) VALUES (?, 1, 1, 'top', ?, ?, 'player1', 'player1')",
        (game_id, season_id, team_id),
    )
    play_id = cursor.lastrowid
    conn.execute(
        "INSERT INTO play_events (play_id, event_order, event_type) VALUES (?, 1, 'pitch')",
        (play_id,),
    )

    conn.execute(
        "INSERT INTO reconciliation_discrepancies (game_id, run_id, team_id, player_id, "
        "signal_name, category, status) VALUES (?, 'run1', ?, 'player1', 'bf', 'pitching', 'MATCH')",
        (game_id, team_id),
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

    def test_ac2_preserved_when_tracked_via_team_opponents(self, setup):
        """Team with team_opponents rows: data preserved on report delete."""
        db_path, client = setup
        team_id = _insert_team_for_cascade(db_path, is_active=0)
        _seed_full_team_data(db_path, team_id)
        report_id = _insert_report(db_path, team_id, slug="guard-opp")

        conn = _get_conn(db_path)
        other_team = conn.execute(
            "INSERT INTO teams (name, membership_type, is_active) VALUES ('Other', 'member', 1)"
        ).lastrowid
        conn.execute(
            "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
            (other_team, team_id),
        )
        conn.commit()
        conn.close()

        client.post(f"/admin/reports/{report_id}/delete", data={"csrf_token": _CSRF}, follow_redirects=False)

        assert _count_rows(db_path, "reports", "id = ?", (report_id,)) == 0
        assert _count_rows(db_path, "teams", "id = ?", (team_id,)) == 1

    def test_ac3_preserved_when_is_active(self, setup):
        """Active team: data preserved on report delete."""
        db_path, client = setup
        team_id = _insert_team_for_cascade(db_path, is_active=1)
        _seed_full_team_data(db_path, team_id)
        report_id = _insert_report(db_path, team_id, slug="guard-active")

        client.post(f"/admin/reports/{report_id}/delete", data={"csrf_token": _CSRF}, follow_redirects=False)

        assert _count_rows(db_path, "reports", "id = ?", (report_id,)) == 0
        assert _count_rows(db_path, "teams", "id = ?", (team_id,)) == 1

    def test_ac4_preserved_when_shared_games_with_tracked_team(self, setup):
        """Shared games with a tracked team: data preserved."""
        db_path, client = setup
        team_id = _insert_team_for_cascade(db_path, is_active=0)
        data = _seed_full_team_data(db_path, team_id)
        report_id = _insert_report(db_path, team_id, slug="guard-shared")

        # Make the opponent team a tracked team
        conn = _get_conn(db_path)
        tracked_team = conn.execute(
            "INSERT INTO teams (name, membership_type, is_active) VALUES ('Tracked', 'member', 1)"
        ).lastrowid
        conn.execute(
            "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
            (tracked_team, data["opp_id"]),
        )
        conn.commit()
        conn.close()

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
