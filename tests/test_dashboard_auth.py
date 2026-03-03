# synthetic-test-data
"""Tests for auth-scoped dashboard behavior (E-023-04).

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

from src.api.main import app  # noqa: E402


# ---------------------------------------------------------------------------
# Database fixture helpers
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS _migrations (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        filename   TEXT    NOT NULL UNIQUE,
        applied_at TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS users (
        user_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        email        TEXT    NOT NULL UNIQUE,
        display_name TEXT    NOT NULL,
        is_admin     INTEGER NOT NULL DEFAULT 0,
        created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS user_team_access (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id  INTEGER NOT NULL REFERENCES users(user_id),
        team_id  TEXT    NOT NULL REFERENCES teams(team_id),
        UNIQUE(user_id, team_id)
    );
    CREATE TABLE IF NOT EXISTS magic_link_tokens (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        token_hash TEXT    NOT NULL UNIQUE,
        user_id    INTEGER NOT NULL REFERENCES users(user_id),
        expires_at TEXT    NOT NULL,
        used_at    TEXT,
        created_at TEXT    NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS sessions (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        session_token_hash  TEXT    NOT NULL UNIQUE,
        user_id             INTEGER NOT NULL REFERENCES users(user_id),
        expires_at          TEXT    NOT NULL,
        created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS passkey_credentials (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id       INTEGER NOT NULL REFERENCES users(user_id),
        credential_id BLOB    NOT NULL UNIQUE,
        public_key    BLOB    NOT NULL,
        sign_count    INTEGER NOT NULL DEFAULT 0,
        created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS players (
        player_id   TEXT PRIMARY KEY,
        first_name  TEXT NOT NULL,
        last_name   TEXT NOT NULL,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS teams (
        team_id    TEXT PRIMARY KEY,
        name       TEXT NOT NULL,
        level      TEXT,
        is_owned   INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS team_rosters (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id       TEXT NOT NULL,
        player_id     TEXT NOT NULL,
        season        TEXT NOT NULL,
        jersey_number TEXT,
        position      TEXT,
        UNIQUE(team_id, player_id, season)
    );

    CREATE TABLE IF NOT EXISTS games (
        game_id      TEXT PRIMARY KEY,
        season       TEXT NOT NULL,
        game_date    TEXT NOT NULL,
        home_team_id TEXT NOT NULL,
        away_team_id TEXT NOT NULL,
        home_score   INTEGER,
        away_score   INTEGER,
        status       TEXT NOT NULL DEFAULT 'completed'
    );

    CREATE TABLE IF NOT EXISTS player_game_batting (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id   TEXT NOT NULL,
        player_id TEXT NOT NULL,
        team_id   TEXT NOT NULL,
        ab        INTEGER,
        h         INTEGER,
        doubles   INTEGER,
        triples   INTEGER,
        hr        INTEGER,
        rbi       INTEGER,
        bb        INTEGER,
        so        INTEGER,
        sb        INTEGER,
        UNIQUE(game_id, player_id)
    );

    CREATE TABLE IF NOT EXISTS player_game_pitching (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id   TEXT NOT NULL,
        player_id TEXT NOT NULL,
        team_id   TEXT NOT NULL,
        ip_outs   INTEGER,
        h         INTEGER,
        er        INTEGER,
        bb        INTEGER,
        so        INTEGER,
        hr        INTEGER,
        UNIQUE(game_id, player_id)
    );

    CREATE TABLE IF NOT EXISTS player_season_batting (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id TEXT NOT NULL,
        team_id   TEXT NOT NULL,
        season    TEXT NOT NULL,
        games     INTEGER,
        ab        INTEGER,
        h         INTEGER,
        doubles   INTEGER,
        triples   INTEGER,
        hr        INTEGER,
        rbi       INTEGER,
        bb        INTEGER,
        so        INTEGER,
        sb        INTEGER,
        home_ab   INTEGER,
        home_h    INTEGER,
        away_ab   INTEGER,
        away_h    INTEGER,
        vs_lhp_ab INTEGER,
        vs_lhp_h  INTEGER,
        vs_rhp_ab INTEGER,
        vs_rhp_h  INTEGER,
        UNIQUE(player_id, team_id, season)
    );
"""

_SEED_SQL = """
    INSERT OR IGNORE INTO teams (team_id, name, level, is_owned) VALUES
        ('team-alpha', 'Alpha Team', 'varsity', 1),
        ('team-beta',  'Beta Team',  'jv',      1),
        ('team-gamma', 'Gamma Team', 'freshman', 1);

    INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES
        ('gc-p-001', 'Marcus',  'Whitehorse'),
        ('gc-p-002', 'Diego',   'Runningwater');

    INSERT OR IGNORE INTO player_season_batting
        (player_id, team_id, season, games, ab, h, bb, so) VALUES
        ('gc-p-001', 'team-alpha', '2026', 2, 6, 3, 2, 1),
        ('gc-p-002', 'team-beta',  '2026', 2, 8, 2, 1, 2);
"""


def _make_seeded_db(tmp_path: Path) -> Path:
    """Create a fully migrated and seeded SQLite database for testing.

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Path to the seeded database file.
    """
    db_path = tmp_path / "test_app.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA_SQL)
    conn.executescript(_SEED_SQL)
    conn.commit()
    conn.close()
    return db_path


def _make_client(
    tmp_path: Path,
    dev_email: str,
    follow_redirects: bool = False,
) -> TestClient:
    """Create a TestClient with the given DEV_USER_EMAIL.

    Args:
        tmp_path: pytest tmp_path directory.
        dev_email: Email to set as DEV_USER_EMAIL (bypasses real auth).
        follow_redirects: Whether the client follows redirects automatically.

    Returns:
        Configured TestClient.
    """
    db_path = _make_seeded_db(tmp_path)
    env_overrides = {
        "DATABASE_PATH": str(db_path),
        "DEV_USER_EMAIL": dev_email,
    }
    with patch.dict("os.environ", env_overrides):
        client = TestClient(app, follow_redirects=follow_redirects)
        client.__enter__()
    return client, db_path, env_overrides


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Seeded database path."""
    return _make_seeded_db(tmp_path)


@pytest.fixture()
def single_team_client(tmp_path: Path, db_path: Path):
    """Client for a user with access to only team-alpha.

    The DEV_USER_EMAIL creates an admin user (is_admin=1) by default, so we
    use a non-admin user and add team access manually.
    """
    # Use a non-admin user with explicit team access
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR IGNORE INTO users (email, display_name, is_admin) VALUES (?, ?, 0)",
        ("coach-alpha@example.com", "Coach Alpha"),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO user_team_access (user_id, team_id)
        SELECT user_id, 'team-alpha' FROM users WHERE email = 'coach-alpha@example.com'
        """
    )
    conn.commit()
    conn.close()

    env_overrides = {
        "DATABASE_PATH": str(db_path),
        "DEV_USER_EMAIL": "coach-alpha@example.com",
    }
    with patch.dict("os.environ", env_overrides):
        with TestClient(app, follow_redirects=False) as client:
            yield client


@pytest.fixture()
def multi_team_client(tmp_path: Path, db_path: Path):
    """Client for a user with access to team-alpha and team-beta."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR IGNORE INTO users (email, display_name, is_admin) VALUES (?, ?, 0)",
        ("coach-multi@example.com", "Coach Multi"),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO user_team_access (user_id, team_id)
        SELECT user_id, 'team-alpha' FROM users WHERE email = 'coach-multi@example.com'
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO user_team_access (user_id, team_id)
        SELECT user_id, 'team-beta' FROM users WHERE email = 'coach-multi@example.com'
        """
    )
    conn.commit()
    conn.close()

    env_overrides = {
        "DATABASE_PATH": str(db_path),
        "DEV_USER_EMAIL": "coach-multi@example.com",
    }
    with patch.dict("os.environ", env_overrides):
        with TestClient(app, follow_redirects=False) as client:
            yield client


@pytest.fixture()
def no_teams_client(tmp_path: Path, db_path: Path):
    """Client for a user with no team assignments."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR IGNORE INTO users (email, display_name, is_admin) VALUES (?, ?, 0)",
        ("coach-none@example.com", "Coach None"),
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

    def test_permitted_team_returns_200(self, single_team_client: TestClient) -> None:
        """User with team-alpha access can view team-alpha dashboard."""
        response = single_team_client.get("/dashboard?team_id=team-alpha")
        assert response.status_code == 200

    def test_forbidden_team_returns_403(self, single_team_client: TestClient) -> None:
        """AC-8: user with access to team-alpha cannot view team-beta (AC-8)."""
        response = single_team_client.get("/dashboard?team_id=team-beta")
        assert response.status_code == 403

    def test_completely_unknown_team_returns_403(
        self, single_team_client: TestClient
    ) -> None:
        """Requesting a nonexistent team_id also returns 403."""
        response = single_team_client.get("/dashboard?team_id=no-such-team")
        assert response.status_code == 403

    def test_default_view_uses_first_permitted_team(
        self, single_team_client: TestClient
    ) -> None:
        """AC-1: /dashboard with no team_id defaults to first permitted team."""
        response = single_team_client.get("/dashboard")
        assert response.status_code == 200
        assert "Alpha Team" in response.text


# ---------------------------------------------------------------------------
# AC-3, AC-4, AC-9: team selector visibility
# ---------------------------------------------------------------------------


class TestTeamSelectorVisibility:
    """Verify team selector rendering (AC-3, AC-4, AC-9)."""

    def test_multi_team_user_sees_selector(self, multi_team_client: TestClient) -> None:
        """AC-3, AC-9: multi-team user sees team selector with all permitted teams."""
        response = multi_team_client.get("/dashboard")
        assert response.status_code == 200
        html = response.text
        # Both team names must appear as selector links
        assert "Alpha Team" in html
        assert "Beta Team" in html
        # Links should contain team_id query params
        assert "team_id=team-alpha" in html
        assert "team_id=team-beta" in html

    def test_single_team_user_no_selector(self, single_team_client: TestClient) -> None:
        """AC-4, AC-9: single-team user does not see team selector."""
        response = single_team_client.get("/dashboard")
        assert response.status_code == 200
        html = response.text
        # team_id links should not appear for single-team users
        assert "team_id=team-alpha" not in html
        assert "team_id=team-beta" not in html

    def test_multi_team_user_can_switch_teams(
        self, multi_team_client: TestClient
    ) -> None:
        """AC-3: multi-team user can navigate to a specific permitted team."""
        response = multi_team_client.get("/dashboard?team_id=team-beta")
        assert response.status_code == 200
        assert "Beta Team" in response.text


# ---------------------------------------------------------------------------
# AC-5, AC-10: logout link
# ---------------------------------------------------------------------------


class TestLogoutLink:
    """Verify logout link presence in dashboard header (AC-5, AC-10)."""

    def test_logout_link_present_single_team(
        self, single_team_client: TestClient
    ) -> None:
        """AC-10: logout link present for single-team user."""
        response = single_team_client.get("/dashboard")
        assert response.status_code == 200
        assert "/auth/logout" in response.text
        assert "Logout" in response.text

    def test_logout_link_present_multi_team(
        self, multi_team_client: TestClient
    ) -> None:
        """AC-10: logout link present for multi-team user."""
        response = multi_team_client.get("/dashboard")
        assert response.status_code == 200
        assert "/auth/logout" in response.text
        assert "Logout" in response.text

    def test_user_display_name_shown(self, single_team_client: TestClient) -> None:
        """AC-5: user's display name shown in dashboard header."""
        response = single_team_client.get("/dashboard")
        assert response.status_code == 200
        assert "Coach Alpha" in response.text


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
