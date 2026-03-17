# synthetic-test-data
"""Tests for auth-scoped dashboard behavior (E-023-04), updated for E-100 schema.

Verifies:
- Team access control (AC-2, AC-8): users cannot view teams they don't have access to
- Team selector visibility (AC-3, AC-4, AC-9): multi-team users see selector, single-team don't
- Logout link presence (AC-5, AC-10)
- No-assignments message (AC-7)
- Dynamic team_id replaces hardcoded value (AC-6)

Run with:
    pytest tests/test_dashboard_auth.py -v
"""

from __future__ import annotations

import datetime
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
from src.api.main import app  # noqa: E402

# Derive season_id the same way the route does, so tests stay valid across years.
_CURRENT_SEASON_ID = f"{datetime.date.today().year}-spring-hs"


def _make_seeded_db(tmp_path: Path) -> tuple[Path, int, int]:
    """Create a fully migrated and seeded SQLite database for testing.

    Inserts three teams: alpha (id=1), beta (id=2), gamma (id=3).

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Tuple of (db_path, team_alpha_id, team_beta_id).
    """
    db_path = tmp_path / "test_app.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))

    # Insert seasons row needed for FK constraints
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year)"
        " VALUES (?, 'Test Season', 'spring-hs', ?)",
        (_CURRENT_SEASON_ID, datetime.date.today().year),
    )

    # Insert teams -- IDs assigned by AUTOINCREMENT
    cursor = conn.execute(
        "INSERT INTO teams (name, membership_type) VALUES ('Alpha Team', 'member')"
    )
    team_alpha_id: int = cursor.lastrowid  # type: ignore[assignment]
    cursor = conn.execute(
        "INSERT INTO teams (name, membership_type) VALUES ('Beta Team', 'member')"
    )
    team_beta_id: int = cursor.lastrowid  # type: ignore[assignment]
    conn.execute(
        "INSERT INTO teams (name, membership_type) VALUES ('Gamma Team', 'member')"
    )

    # Insert players and season batting stats
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES"
        " ('gc-p-001', 'Marcus', 'Whitehorse'),"
        " ('gc-p-002', 'Diego', 'Runningwater')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO player_season_batting"
        " (player_id, team_id, season_id, gp, ab, h, bb, so)"
        " VALUES ('gc-p-001', ?, ?, 2, 6, 3, 2, 1)",
        (team_alpha_id, _CURRENT_SEASON_ID),
    )
    conn.execute(
        "INSERT OR IGNORE INTO player_season_batting"
        " (player_id, team_id, season_id, gp, ab, h, bb, so)"
        " VALUES ('gc-p-002', ?, ?, 2, 8, 2, 1, 2)",
        (team_beta_id, _CURRENT_SEASON_ID),
    )

    conn.commit()
    conn.close()
    return db_path, team_alpha_id, team_beta_id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_info(tmp_path: Path) -> tuple[Path, int, int]:
    """Seeded database path and team IDs."""
    return _make_seeded_db(tmp_path)


@pytest.fixture()
def single_team_client(tmp_path: Path, db_info: tuple[Path, int, int]):
    """Client for a user with access to only team-alpha."""
    db_path, team_alpha_id, _team_beta_id = db_info
    conn = sqlite3.connect(str(db_path))
    # Insert user (E-100: email only, no display_name, no is_admin)
    cursor = conn.execute(
        "INSERT OR IGNORE INTO users (email) VALUES (?)",
        ("coach-alpha@example.com",),
    )
    conn.commit()
    user_id = cursor.lastrowid or conn.execute(
        "SELECT id FROM users WHERE email = 'coach-alpha@example.com'"
    ).fetchone()[0]
    conn.execute(
        "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
        (user_id, team_alpha_id),
    )
    conn.commit()
    conn.close()

    env_overrides = {
        "DATABASE_PATH": str(db_path),
        "DEV_USER_EMAIL": "coach-alpha@example.com",
    }
    with patch.dict("os.environ", env_overrides):
        with TestClient(app, follow_redirects=False) as client:
            yield client, team_alpha_id, _team_beta_id


@pytest.fixture()
def multi_team_client(tmp_path: Path, db_info: tuple[Path, int, int]):
    """Client for a user with access to team-alpha and team-beta."""
    db_path, team_alpha_id, team_beta_id = db_info
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "INSERT OR IGNORE INTO users (email) VALUES (?)",
        ("coach-multi@example.com",),
    )
    conn.commit()
    user_id = cursor.lastrowid or conn.execute(
        "SELECT id FROM users WHERE email = 'coach-multi@example.com'"
    ).fetchone()[0]
    for tid in (team_alpha_id, team_beta_id):
        conn.execute(
            "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
            (user_id, tid),
        )
    conn.commit()
    conn.close()

    env_overrides = {
        "DATABASE_PATH": str(db_path),
        "DEV_USER_EMAIL": "coach-multi@example.com",
    }
    with patch.dict("os.environ", env_overrides):
        with TestClient(app, follow_redirects=False) as client:
            yield client, team_alpha_id, team_beta_id


@pytest.fixture()
def no_teams_client(tmp_path: Path, db_info: tuple[Path, int, int]):
    """Client for a user with no team assignments."""
    db_path, _alpha, _beta = db_info
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR IGNORE INTO users (email) VALUES (?)",
        ("coach-none@example.com",),
    )
    conn.commit()
    conn.close()

    env_overrides = {
        "DATABASE_PATH": str(db_path),
        "DEV_USER_EMAIL": "coach-none@example.com",
    }
    with patch.dict("os.environ", env_overrides):
        with TestClient(app, follow_redirects=False) as client:
            yield client


# ---------------------------------------------------------------------------
# AC-8: user with access to team A cannot view team B
# ---------------------------------------------------------------------------


class TestTeamAccessControl:
    """Verify team-scoped authorization (AC-2, AC-8)."""

    def test_permitted_team_returns_200(self, single_team_client) -> None:
        """User with team-alpha access can view team-alpha dashboard."""
        client, team_alpha_id, _ = single_team_client
        response = client.get(f"/dashboard?team_id={team_alpha_id}")
        assert response.status_code == 200

    def test_forbidden_team_returns_403(self, single_team_client) -> None:
        """AC-8: user with access to team-alpha cannot view team-beta."""
        client, _, team_beta_id = single_team_client
        response = client.get(f"/dashboard?team_id={team_beta_id}")
        assert response.status_code == 403

    def test_completely_unknown_team_returns_403(
        self, single_team_client
    ) -> None:
        """Requesting a nonexistent team_id (non-integer) also returns 403."""
        client, _, _ = single_team_client
        response = client.get("/dashboard?team_id=9999")
        assert response.status_code == 403

    def test_non_integer_team_id_returns_400(self, single_team_client) -> None:
        """AC-8(d): a non-numeric team_id query param returns HTTP 400."""
        client, _, _ = single_team_client
        response = client.get("/dashboard?team_id=no-such-team")
        assert response.status_code == 400

    def test_default_view_uses_first_permitted_team(
        self, single_team_client
    ) -> None:
        """AC-1: /dashboard with no team_id defaults to first permitted team."""
        client, _, _ = single_team_client
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "Alpha Team" in response.text


# ---------------------------------------------------------------------------
# AC-3, AC-4, AC-9: team selector visibility
# ---------------------------------------------------------------------------


class TestTeamSelectorVisibility:
    """Verify team selector rendering (AC-3, AC-4, AC-9)."""

    def test_multi_team_user_sees_selector(self, multi_team_client) -> None:
        """AC-3, AC-9: multi-team user sees team selector with all permitted teams."""
        client, _, _ = multi_team_client
        response = client.get("/dashboard")
        assert response.status_code == 200
        html = response.text
        # Both team names must appear as selector links
        assert "Alpha Team" in html
        assert "Beta Team" in html
        # Links should contain integer team_id query params
        assert "team_id=" in html

    def test_single_team_user_no_selector(self, single_team_client) -> None:
        """AC-4, AC-9: single-team user does not see team selector."""
        client, team_alpha_id, team_beta_id = single_team_client
        response = client.get("/dashboard")
        assert response.status_code == 200
        html = response.text
        # team_id link for team-beta should not appear (not permitted)
        assert f"team_id={team_beta_id}" not in html

    def test_multi_team_user_can_switch_teams(
        self, multi_team_client
    ) -> None:
        """AC-3: multi-team user can navigate to a specific permitted team."""
        client, _, team_beta_id = multi_team_client
        response = client.get(f"/dashboard?team_id={team_beta_id}")
        assert response.status_code == 200
        assert "Beta Team" in response.text


# ---------------------------------------------------------------------------
# AC-5, AC-10: logout link
# ---------------------------------------------------------------------------


class TestLogoutLink:
    """Verify logout link presence in dashboard header (AC-5, AC-10)."""

    def test_logout_link_present_single_team(
        self, single_team_client
    ) -> None:
        """AC-10: logout link present for single-team user."""
        client, _, _ = single_team_client
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "/auth/logout" in response.text
        assert "Logout" in response.text

    def test_logout_link_present_multi_team(
        self, multi_team_client
    ) -> None:
        """AC-10: logout link present for multi-team user."""
        client, _, _ = multi_team_client
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "/auth/logout" in response.text
        assert "Logout" in response.text

    def test_user_email_shown(self, single_team_client) -> None:
        """AC-5: user's email shown in dashboard header (display_name removed in E-100)."""
        client, _, _ = single_team_client
        response = client.get("/dashboard")
        assert response.status_code == 200
        # E-100: no display_name column; email is the identity shown
        assert "coach-alpha@example.com" in response.text


# ---------------------------------------------------------------------------
# AC-7: no team assignments message
# ---------------------------------------------------------------------------


class TestNoAssignments:
    """Verify no-assignments message (AC-7)."""

    def test_no_assignments_shows_message(
        self, no_teams_client: TestClient
    ) -> None:
        """AC-7: user with no teams sees the no-assignments message."""
        response = no_teams_client.get("/dashboard")
        assert response.status_code == 200
        assert "no team assignments" in response.text.lower()
        assert "administrator" in response.text.lower()

    def test_no_assignments_no_table(self, no_teams_client: TestClient) -> None:
        """AC-7: no-assignments page does not show the stats table."""
        response = no_teams_client.get("/dashboard")
        assert response.status_code == 200
        # Stats table should not be present
        assert "<table" not in response.text


# ---------------------------------------------------------------------------
# AC-8(c): INTEGER team references in team selector (AC-5, AC-6)
# ---------------------------------------------------------------------------


class TestIntegerTeamSelectorLinks:
    """Verify team selector renders INTEGER team_id values in links (AC-5, AC-6, AC-8c)."""

    def test_team_selector_contains_integer_team_id(
        self, multi_team_client
    ) -> None:
        """AC-8(c): team selector href contains the INTEGER team_id, not a text slug."""
        client, team_alpha_id, team_beta_id = multi_team_client
        response = client.get("/dashboard")
        assert response.status_code == 200
        html = response.text
        # The team selector must render links with integer team IDs
        assert f"team_id={team_alpha_id}" in html
        assert f"team_id={team_beta_id}" in html

    def test_non_numeric_team_id_returns_400_pitching(
        self, single_team_client
    ) -> None:
        """AC-8(d): non-numeric team_id returns 400 on pitching route."""
        client, _, _ = single_team_client
        response = client.get("/dashboard/pitching?team_id=not-a-number")
        assert response.status_code == 400

    def test_non_numeric_team_id_returns_400_games(
        self, single_team_client
    ) -> None:
        """AC-8(d): non-numeric team_id returns 400 on games route."""
        client, _, _ = single_team_client
        response = client.get("/dashboard/games?team_id=not-a-number")
        assert response.status_code == 400

    def test_unpermitted_integer_team_id_returns_403(
        self, single_team_client
    ) -> None:
        """AC-8(e): a valid integer team_id not in permitted_teams returns 403."""
        client, _, team_beta_id = single_team_client
        response = client.get(f"/dashboard?team_id={team_beta_id}")
        assert response.status_code == 403

    def test_nonexistent_integer_team_id_returns_403(
        self, single_team_client
    ) -> None:
        """AC-8(e): an integer team_id that doesn't exist returns 403 (not 404)."""
        client, _, _ = single_team_client
        response = client.get("/dashboard?team_id=99999")
        assert response.status_code == 403
