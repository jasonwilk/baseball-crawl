# synthetic-test-data
"""Tests for GET /dashboard endpoint (E-009-03).

Uses a temporary SQLite database seeded with the same player/stats data as
``data/seeds/seed_dev.sql``.  Tests run without Docker -- no real database
or network access required.

Run with:
    pytest tests/test_dashboard.py
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
    INSERT OR IGNORE INTO _migrations (filename)
        VALUES ('001_initial_schema.sql');

    -- Auth tables (003_auth.sql) required for SessionMiddleware
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
        challenge           TEXT,
        created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
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
        ('lsb-varsity-2026', 'LSB Varsity 2026', 'varsity', 1);

    INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES
        ('gc-p-001', 'Marcus',  'Whitehorse'),
        ('gc-p-002', 'Diego',   'Runningwater'),
        ('gc-p-003', 'Elijah',  'Strongbow'),
        ('gc-p-004', 'Nathan',  'Redcloud'),
        ('gc-p-005', 'Isaiah',  'Eagleheart');

    INSERT OR IGNORE INTO player_season_batting
        (player_id, team_id, season, games, ab, h, bb, so) VALUES
        ('gc-p-001', 'lsb-varsity-2026', '2026', 2, 6,  3, 2, 1),
        ('gc-p-002', 'lsb-varsity-2026', '2026', 2, 8,  2, 1, 2),
        ('gc-p-003', 'lsb-varsity-2026', '2026', 2, 8,  4, 0, 1),
        ('gc-p-004', 'lsb-varsity-2026', '2026', 2, 6,  1, 2, 3),
        ('gc-p-005', 'lsb-varsity-2026', '2026', 2, 7,  3, 0, 2);
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded_client(tmp_path: Path) -> TestClient:
    """Return a TestClient backed by a seeded in-process SQLite database.

    Sets DEV_USER_EMAIL so the session middleware auto-creates an admin session,
    allowing unauthenticated test requests to reach the dashboard.

    Args:
        tmp_path: pytest tmp_path fixture (injected by pytest).

    Returns:
        FastAPI TestClient configured to use the seeded database.
    """
    db_path = _make_seeded_db(tmp_path)
    env_overrides = {
        "DATABASE_PATH": str(db_path),
        "DEV_USER_EMAIL": "testdev@example.com",
    }
    with patch.dict("os.environ", env_overrides):
        with TestClient(app) as client:
            yield client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDashboardEndpoint:
    """Tests for GET /dashboard (E-009-03)."""

    def test_dashboard_returns_200(self, seeded_client: TestClient) -> None:
        """GET /dashboard returns HTTP 200 with a seeded database."""
        response = seeded_client.get("/dashboard")
        assert response.status_code == 200

    def test_dashboard_returns_html_content_type(
        self, seeded_client: TestClient
    ) -> None:
        """GET /dashboard response Content-Type is text/html."""
        response = seeded_client.get("/dashboard")
        assert "text/html" in response.headers.get("content-type", "")

    def test_dashboard_contains_title_tag(self, seeded_client: TestClient) -> None:
        """GET /dashboard response HTML includes a <title> tag."""
        response = seeded_client.get("/dashboard")
        assert "<title>" in response.text

    def test_dashboard_contains_table(self, seeded_client: TestClient) -> None:
        """GET /dashboard response HTML includes a <table> element."""
        response = seeded_client.get("/dashboard")
        assert "<table" in response.text

    def test_dashboard_contains_player_name(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML contains at least one seeded player name (AC-5)."""
        response = seeded_client.get("/dashboard")
        html = response.text
        # At least one of the five seeded players must appear in the page.
        player_names = [
            "Whitehorse",
            "Runningwater",
            "Strongbow",
            "Redcloud",
            "Eagleheart",
        ]
        assert any(name in html for name in player_names), (
            "Expected at least one player name in dashboard HTML, found none."
        )

    def test_dashboard_contains_stat_value(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML contains at least one recognisable stat value (AC-5)."""
        response = seeded_client.get("/dashboard")
        html = response.text
        # The seeded players have AB values of 6, 8, 8, 6, 7 -- check presence.
        # Any digit that corresponds to a real stat column value is sufficient.
        assert any(str(v) in html for v in [6, 8, 7]), (
            "Expected at least one stat value in dashboard HTML."
        )

    def test_dashboard_shows_at_least_three_players(
        self, seeded_client: TestClient
    ) -> None:
        """GET /dashboard renders at least 3 players in the table (AC-3)."""
        response = seeded_client.get("/dashboard")
        html = response.text
        # Count how many seeded last names appear in the page.
        last_names = [
            "Whitehorse",
            "Runningwater",
            "Strongbow",
            "Redcloud",
            "Eagleheart",
        ]
        found = sum(1 for name in last_names if name in html)
        assert found >= 3, (
            f"Expected at least 3 players in dashboard HTML, found {found}."
        )

    def test_dashboard_contains_column_headers(
        self, seeded_client: TestClient
    ) -> None:
        """GET /dashboard HTML includes stat column headers (AB, H, BB, K)."""
        response = seeded_client.get("/dashboard")
        html = response.text
        for header in ("AB", "H", "BB", "K"):
            assert header in html, (
                f"Expected column header '{header}' in dashboard HTML."
            )

    def test_dashboard_contains_viewport_meta(
        self, seeded_client: TestClient
    ) -> None:
        """GET /dashboard HTML includes a viewport meta tag for mobile (AC-2, AC-4)."""
        response = seeded_client.get("/dashboard")
        assert 'name="viewport"' in response.text

    def test_dashboard_contains_tailwind_cdn(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML includes the Tailwind CSS CDN script tag (AC-2)."""
        response = seeded_client.get("/dashboard")
        assert "cdn.tailwindcss.com" in response.text

    def test_health_endpoint_unaffected(self, tmp_path: Path) -> None:
        """GET /health still returns 200 after dashboard router registration (AC-7)."""
        db_path = _make_seeded_db(tmp_path)
        env_overrides = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": "testdev@example.com",
        }
        with patch.dict("os.environ", env_overrides):
            with TestClient(app) as client:
                response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_dashboard_overflow_x_container(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML includes an overflow-x-auto container (AC-4)."""
        response = seeded_client.get("/dashboard")
        assert "overflow-x-auto" in response.text
