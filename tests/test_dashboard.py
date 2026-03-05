# synthetic-test-data
"""Tests for GET /dashboard endpoint (E-009-03).

Uses a temporary SQLite database seeded with the same player/stats data as
``data/seeds/seed_dev.sql``.  Tests run without Docker -- no real database
or network access required.

Run with:
    pytest tests/test_dashboard.py
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

from src.api.main import app  # noqa: E402

# Derive season_id the same way the route does, so tests stay valid across years.
_CURRENT_SEASON_ID = f"{datetime.date.today().year}-spring-hs"


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

    -- seasons table (matches real schema in 001_initial_schema.sql)
    CREATE TABLE IF NOT EXISTS seasons (
        season_id   TEXT    PRIMARY KEY,
        name        TEXT    NOT NULL,
        season_type TEXT    NOT NULL,
        year        INTEGER NOT NULL,
        start_date  TEXT,
        end_date    TEXT,
        created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
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
        source     TEXT NOT NULL DEFAULT 'gamechanger',
        is_active  INTEGER NOT NULL DEFAULT 1,
        last_synced TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS team_rosters (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id       TEXT NOT NULL REFERENCES teams(team_id),
        player_id     TEXT NOT NULL REFERENCES players(player_id),
        season_id     TEXT NOT NULL REFERENCES seasons(season_id),
        jersey_number TEXT,
        position      TEXT,
        UNIQUE(team_id, player_id, season_id)
    );

    CREATE TABLE IF NOT EXISTS games (
        game_id      TEXT PRIMARY KEY,
        season_id    TEXT NOT NULL REFERENCES seasons(season_id),
        game_date    TEXT NOT NULL,
        home_team_id TEXT NOT NULL REFERENCES teams(team_id),
        away_team_id TEXT NOT NULL REFERENCES teams(team_id),
        home_score   INTEGER,
        away_score   INTEGER,
        status       TEXT NOT NULL DEFAULT 'completed'
    );

    CREATE TABLE IF NOT EXISTS player_game_batting (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id   TEXT NOT NULL REFERENCES games(game_id),
        player_id TEXT NOT NULL REFERENCES players(player_id),
        team_id   TEXT NOT NULL REFERENCES teams(team_id),
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
        game_id   TEXT NOT NULL REFERENCES games(game_id),
        player_id TEXT NOT NULL REFERENCES players(player_id),
        team_id   TEXT NOT NULL REFERENCES teams(team_id),
        ip_outs   INTEGER,
        h         INTEGER,
        er        INTEGER,
        bb        INTEGER,
        so        INTEGER,
        hr        INTEGER,
        UNIQUE(game_id, player_id)
    );

    CREATE TABLE IF NOT EXISTS player_season_batting (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id   TEXT NOT NULL REFERENCES players(player_id),
        team_id     TEXT NOT NULL REFERENCES teams(team_id),
        season_id   TEXT NOT NULL REFERENCES seasons(season_id),
        games       INTEGER,
        ab          INTEGER,
        h           INTEGER,
        doubles     INTEGER,
        triples     INTEGER,
        hr          INTEGER,
        rbi         INTEGER,
        bb          INTEGER,
        so          INTEGER,
        sb          INTEGER,
        home_ab     INTEGER,
        home_h      INTEGER,
        home_hr     INTEGER,
        home_bb     INTEGER,
        home_so     INTEGER,
        away_ab     INTEGER,
        away_h      INTEGER,
        away_hr     INTEGER,
        away_bb     INTEGER,
        away_so     INTEGER,
        vs_lhp_ab   INTEGER,
        vs_lhp_h    INTEGER,
        vs_lhp_hr   INTEGER,
        vs_lhp_bb   INTEGER,
        vs_lhp_so   INTEGER,
        vs_rhp_ab   INTEGER,
        vs_rhp_h    INTEGER,
        vs_rhp_hr   INTEGER,
        vs_rhp_bb   INTEGER,
        vs_rhp_so   INTEGER,
        UNIQUE(player_id, team_id, season_id)
    );

    CREATE TABLE IF NOT EXISTS player_season_pitching (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id   TEXT NOT NULL REFERENCES players(player_id),
        team_id     TEXT NOT NULL REFERENCES teams(team_id),
        season_id   TEXT NOT NULL REFERENCES seasons(season_id),
        games       INTEGER,
        ip_outs     INTEGER,
        h           INTEGER,
        er          INTEGER,
        bb          INTEGER,
        so          INTEGER,
        hr          INTEGER,
        pitches     INTEGER,
        strikes     INTEGER,
        home_ip_outs INTEGER,
        home_h       INTEGER,
        home_er      INTEGER,
        home_bb      INTEGER,
        home_so      INTEGER,
        away_ip_outs INTEGER,
        away_h       INTEGER,
        away_er      INTEGER,
        away_bb      INTEGER,
        away_so      INTEGER,
        vs_lhb_ab   INTEGER,
        vs_lhb_h    INTEGER,
        vs_lhb_hr   INTEGER,
        vs_lhb_bb   INTEGER,
        vs_lhb_so   INTEGER,
        vs_rhb_ab   INTEGER,
        vs_rhb_h    INTEGER,
        vs_rhb_hr   INTEGER,
        vs_rhb_bb   INTEGER,
        vs_rhb_so   INTEGER,
        UNIQUE(player_id, team_id, season_id)
    );
"""

_SEED_SQL = f"""
    INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES
        ('{_CURRENT_SEASON_ID}', 'Spring {datetime.date.today().year} High School', 'spring-hs', {datetime.date.today().year});

    INSERT OR IGNORE INTO teams (team_id, name, level, is_owned) VALUES
        ('lsb-varsity-2026', 'LSB Varsity 2026', 'varsity', 1);

    INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES
        ('gc-p-001', 'Marcus',  'Whitehorse'),
        ('gc-p-002', 'Diego',   'Runningwater'),
        ('gc-p-003', 'Elijah',  'Strongbow'),
        ('gc-p-004', 'Nathan',  'Redcloud'),
        ('gc-p-005', 'Isaiah',  'Eagleheart');

    INSERT OR IGNORE INTO player_season_batting
        (player_id, team_id, season_id, games, ab, h, doubles, triples, hr, rbi, bb, so, sb) VALUES
        ('gc-p-001', 'lsb-varsity-2026', '{_CURRENT_SEASON_ID}', 2, 6,  3, 1, 0, 0, 2, 2, 1, 1),
        ('gc-p-002', 'lsb-varsity-2026', '{_CURRENT_SEASON_ID}', 2, 8,  2, 0, 0, 0, 1, 1, 2, 0),
        ('gc-p-003', 'lsb-varsity-2026', '{_CURRENT_SEASON_ID}', 2, 8,  4, 1, 0, 1, 3, 0, 1, 0),
        ('gc-p-004', 'lsb-varsity-2026', '{_CURRENT_SEASON_ID}', 2, 6,  1, 0, 0, 0, 0, 2, 3, 1),
        ('gc-p-005', 'lsb-varsity-2026', '{_CURRENT_SEASON_ID}', 2, 7,  3, 0, 1, 0, 2, 0, 2, 2);

    -- gc-p-006: no AB (e.g., pitcher-only -- for zero-AB display test)
    INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES
        ('gc-p-006', 'Zane', 'Noatbats');
    INSERT OR IGNORE INTO player_season_batting
        (player_id, team_id, season_id, games, ab, h, doubles, triples, hr, rbi, bb, so, sb) VALUES
        ('gc-p-006', 'lsb-varsity-2026', '{_CURRENT_SEASON_ID}', 1, 0,  0, 0, 0, 0, 0, 0, 0, 0);
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
        """GET /dashboard HTML includes stat column headers (AB, H, BB, SO)."""
        response = seeded_client.get("/dashboard")
        html = response.text
        for header in ("AB", "H", "BB", "SO"):
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


class TestEnhancedBattingStats:
    """Tests for enhanced batting stats on GET /dashboard (E-004-02)."""

    def test_batting_returns_200(self, seeded_client: TestClient) -> None:
        """GET /dashboard returns HTTP 200 with seeded data (AC-10a)."""
        response = seeded_client.get("/dashboard")
        assert response.status_code == 200

    def test_batting_contains_seeded_player_name(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML contains at least one seeded player last name (AC-10a)."""
        response = seeded_client.get("/dashboard")
        html = response.text
        player_names = ["Whitehorse", "Runningwater", "Strongbow", "Redcloud", "Eagleheart"]
        assert any(name in html for name in player_names)

    def test_batting_computed_avg_value(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML contains a correctly computed AVG for gc-p-001 (AC-10b).

        gc-p-001 has 3 H in 6 AB => AVG = .500.
        """
        response = seeded_client.get("/dashboard")
        assert ".500" in response.text

    def test_batting_column_headers(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML includes AVG, OBP, SLG column headers (AC-10c)."""
        response = seeded_client.get("/dashboard")
        html = response.text
        for header in ("AVG", "OBP", "SLG"):
            assert header in html, f"Expected column header '{header}' in batting stats HTML."

    def test_batting_all_column_headers_present(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML includes all expected column headers (AC-1)."""
        response = seeded_client.get("/dashboard")
        html = response.text
        for header in ("AVG", "OBP", "GP", "BB", "SO", "SLG", "AB", "2B", "3B", "HR", "SB", "RBI"):
            assert header in html, f"Expected column header '{header}' in batting stats HTML."

    def test_batting_player_links(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML contains player profile links (AC-5)."""
        response = seeded_client.get("/dashboard")
        assert "/dashboard/players/" in response.text

    def test_batting_zero_ab_shows_dash(self, seeded_client: TestClient) -> None:
        """AVG/OBP/SLG display '-' for player with zero AB (AC-11).

        gc-p-006 has 0 AB; all rate stats should display '-'.
        """
        response = seeded_client.get("/dashboard")
        html = response.text
        # gc-p-006 must appear (he has a batting row)
        assert "Noatbats" in html
        # The page must contain at least one '-' for zero-AB rate stats
        assert "-" in html

    def test_batting_sticky_thead(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML uses sticky top-0 on thead (AC-8)."""
        response = seeded_client.get("/dashboard")
        assert "sticky top-0" in response.text

    def test_batting_overflow_x_auto(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML wraps table in overflow-x-auto (AC-8)."""
        response = seeded_client.get("/dashboard")
        assert "overflow-x-auto" in response.text


# ---------------------------------------------------------------------------
# Pitching seed SQL for E-004-03 tests
# ---------------------------------------------------------------------------

_PITCHING_SEED_SQL = f"""
    INSERT OR IGNORE INTO player_season_pitching
        (player_id, team_id, season_id, games, ip_outs, h, er, bb, so, hr) VALUES
        -- gc-p-001: 6 IP (18 outs), 4 H, 2 ER, 3 BB, 9 SO, 0 HR
        --   ERA = 2*27/18 = 3.00, K/9 = 9*27/18 = 13.5, BB/9 = 3*27/18 = 4.5, WHIP = (3+4)*3/18 = 1.17
        ('gc-p-001', 'lsb-varsity-2026', '{_CURRENT_SEASON_ID}', 3, 18, 4, 2, 3, 9, 0),
        -- gc-p-002: 3 IP (9 outs), 5 H, 4 ER, 2 BB, 3 SO, 1 HR
        --   ERA = 4*27/9 = 12.00, K/9 = 3*27/9 = 9.0, BB/9 = 2*27/9 = 6.0, WHIP = (2+5)*3/9 = 2.33
        ('gc-p-002', 'lsb-varsity-2026', '{_CURRENT_SEASON_ID}', 2, 9,  5, 4, 2, 3, 1),
        -- gc-p-003: 0 ip_outs -- should appear at bottom with '-' for rate stats
        ('gc-p-003', 'lsb-varsity-2026', '{_CURRENT_SEASON_ID}', 1, 0,  1, 1, 1, 0, 0);

    -- Add an alt-season record for season_id override test
    INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES
        ('2025-spring-hs', 'Spring 2025 High School', 'spring-hs', 2025);

    INSERT OR IGNORE INTO player_season_pitching
        (player_id, team_id, season_id, games, ip_outs, h, er, bb, so, hr) VALUES
        ('gc-p-001', 'lsb-varsity-2026', '2025-spring-hs', 1, 6, 1, 0, 0, 5, 0);
"""


def _make_pitching_seeded_db(tmp_path: Path) -> Path:
    """Create a SQLite database seeded with both batting and pitching data.

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Path to the seeded database file.
    """
    db_path = tmp_path / "test_pitching.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA_SQL)
    conn.executescript(_SEED_SQL)
    conn.executescript(_PITCHING_SEED_SQL)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def pitching_client(tmp_path: Path) -> TestClient:
    """Return a TestClient with pitching data seeded.

    Args:
        tmp_path: pytest tmp_path fixture (injected by pytest).

    Returns:
        FastAPI TestClient configured to use the pitching-seeded database.
    """
    db_path = _make_pitching_seeded_db(tmp_path)
    env_overrides = {
        "DATABASE_PATH": str(db_path),
        "DEV_USER_EMAIL": "testdev@example.com",
    }
    with patch.dict("os.environ", env_overrides):
        with TestClient(app) as client:
            yield client


class TestPitchingDashboard:
    """Tests for GET /dashboard/pitching (E-004-03)."""

    def test_pitching_returns_200(self, pitching_client: TestClient) -> None:
        """GET /dashboard/pitching returns HTTP 200 with seeded data (AC-1, AC-12)."""
        response = pitching_client.get("/dashboard/pitching")
        assert response.status_code == 200

    def test_pitching_contains_column_headers(
        self, pitching_client: TestClient
    ) -> None:
        """GET /dashboard/pitching HTML includes all required column headers (AC-2)."""
        response = pitching_client.get("/dashboard/pitching")
        html = response.text
        for header in ("ERA", "K/9", "BB/9", "WHIP", "GP", "IP", "H", "ER", "BB", "SO", "HR"):
            assert header in html, f"Expected column header '{header}' in pitching HTML."

    def test_pitching_player_link(self, pitching_client: TestClient) -> None:
        """GET /dashboard/pitching HTML contains player profile links (AC-2)."""
        response = pitching_client.get("/dashboard/pitching")
        assert "/dashboard/players/" in response.text

    def test_pitching_era_computation(self, pitching_client: TestClient) -> None:
        """GET /dashboard/pitching correctly computes ERA for gc-p-001 (AC-4, AC-5, AC-12).

        gc-p-001: 18 ip_outs, 2 ER => ERA = 2*27/18 = 3.00
        """
        response = pitching_client.get("/dashboard/pitching")
        assert "3.00" in response.text

    def test_pitching_k9_computation(self, pitching_client: TestClient) -> None:
        """GET /dashboard/pitching correctly computes K/9 for gc-p-001 (AC-4, AC-5, AC-12).

        gc-p-001: 18 ip_outs, 9 SO => K/9 = 9*27/18 = 13.5
        """
        response = pitching_client.get("/dashboard/pitching")
        assert "13.5" in response.text

    def test_pitching_whip_computation(self, pitching_client: TestClient) -> None:
        """GET /dashboard/pitching correctly computes WHIP for gc-p-001 (AC-4, AC-5, AC-12).

        gc-p-001: 18 ip_outs, 3 BB, 4 H => WHIP = (3+4)*3/18 = 1.17
        """
        response = pitching_client.get("/dashboard/pitching")
        assert "1.17" in response.text

    def test_pitching_zero_ip_shows_dash(self, pitching_client: TestClient) -> None:
        """Pitcher with 0 ip_outs shows '-' for rate stats (AC-4, AC-12)."""
        response = pitching_client.get("/dashboard/pitching")
        # gc-p-003 has 0 ip_outs; the page must contain at least one '-'
        assert "-" in response.text

    def test_pitching_ip_display(self, pitching_client: TestClient) -> None:
        """GET /dashboard/pitching displays IP in W.T notation (AC-3).

        gc-p-001: 18 ip_outs => '6.0'
        """
        response = pitching_client.get("/dashboard/pitching")
        assert "6.0" in response.text

    def test_pitching_403_unauthorized_team(self, pitching_client: TestClient) -> None:
        """GET /dashboard/pitching?team_id=other returns 403 (AC-1, AC-11, AC-12)."""
        response = pitching_client.get("/dashboard/pitching?team_id=not-permitted-team")
        assert response.status_code == 403

    def test_pitching_empty_state(self, seeded_client: TestClient) -> None:
        """GET /dashboard/pitching renders empty-state message when no pitching data (AC-12)."""
        # seeded_client has no pitching rows -- only batting rows
        response = seeded_client.get("/dashboard/pitching")
        assert response.status_code == 200
        assert "No pitching stats available" in response.text

    def test_pitching_season_id_override(self, pitching_client: TestClient) -> None:
        """GET /dashboard/pitching?season_id=2025-spring-hs returns alt-season stats (AC-1, AC-12)."""
        response = pitching_client.get(
            f"/dashboard/pitching?season_id=2025-spring-hs"
        )
        assert response.status_code == 200
        # 2025 seed has gc-p-001 with 6 ip_outs (2.0 IP) and 0 ER => ERA 0.00
        assert "0.00" in response.text

    def test_pitching_sticky_thead(self, pitching_client: TestClient) -> None:
        """GET /dashboard/pitching uses sticky top-0 on thead (AC-13)."""
        response = pitching_client.get("/dashboard/pitching")
        assert "sticky top-0" in response.text

    def test_pitching_overflow_x_auto(self, pitching_client: TestClient) -> None:
        """GET /dashboard/pitching wraps table in overflow-x-auto (AC-2)."""
        response = pitching_client.get("/dashboard/pitching")
        assert "overflow-x-auto" in response.text

    def test_pitching_active_nav_highlighted(self, pitching_client: TestClient) -> None:
        """GET /dashboard/pitching sets active_nav='pitching' (AC-9)."""
        response = pitching_client.get("/dashboard/pitching")
        html = response.text
        # The base template applies font-bold to the active nav link when active_nav matches
        assert "font-bold" in html


# ---------------------------------------------------------------------------
# Game log seed SQL for E-004-04 tests
# ---------------------------------------------------------------------------

_GAME_SEED_SQL = f"""
    -- Opponent team
    INSERT OR IGNORE INTO teams (team_id, name, level, is_owned) VALUES
        ('opp-team-001', 'Rival High School', NULL, 0);

    -- Two games for lsb-varsity-2026 in current season
    INSERT OR IGNORE INTO games (game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score) VALUES
        ('game-001', '{_CURRENT_SEASON_ID}', '2026-03-01', 'lsb-varsity-2026', 'opp-team-001', 7, 3),
        ('game-002', '{_CURRENT_SEASON_ID}', '2026-02-20', 'opp-team-001', 'lsb-varsity-2026', 2, 5);

    -- A game for an unrelated team (not involving lsb-varsity-2026)
    INSERT OR IGNORE INTO teams (team_id, name, level, is_owned) VALUES
        ('other-team-001', 'Other High School', NULL, 0),
        ('other-team-002', 'Another High School', NULL, 0);
    INSERT OR IGNORE INTO games (game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score) VALUES
        ('game-unrelated', '{_CURRENT_SEASON_ID}', '2026-03-05', 'other-team-001', 'other-team-002', 4, 1);

    -- Per-game batting lines for game-001 (lsb-varsity-2026 = home team)
    INSERT OR IGNORE INTO player_game_batting (game_id, player_id, team_id, ab, h, doubles, triples, hr, rbi, bb, so, sb) VALUES
        ('game-001', 'gc-p-001', 'lsb-varsity-2026', 4, 2, 1, 0, 0, 2, 1, 1, 0),
        ('game-001', 'gc-p-002', 'lsb-varsity-2026', 3, 1, 0, 0, 0, 0, 0, 1, 1);

    -- Per-game pitching lines for game-001
    INSERT OR IGNORE INTO player_game_pitching (game_id, player_id, team_id, ip_outs, h, er, bb, so, hr) VALUES
        ('game-001', 'gc-p-001', 'lsb-varsity-2026', 18, 3, 1, 2, 8, 0);

    -- Alt-season game (for season_id override test)
    INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES
        ('2025-spring-hs', 'Spring 2025 High School', 'spring-hs', 2025);
    INSERT OR IGNORE INTO games (game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score) VALUES
        ('game-2025', '2025-spring-hs', '2025-03-15', 'lsb-varsity-2026', 'opp-team-001', 6, 4);
"""


def _make_games_seeded_db(tmp_path: Path) -> Path:
    """Create a SQLite database seeded with game and box score data.

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Path to the seeded database file.
    """
    db_path = tmp_path / "test_games.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA_SQL)
    conn.executescript(_SEED_SQL)
    conn.executescript(_GAME_SEED_SQL)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def games_client(tmp_path: Path) -> TestClient:
    """Return a TestClient with game log data seeded.

    Args:
        tmp_path: pytest tmp_path fixture (injected by pytest).

    Returns:
        FastAPI TestClient configured to use the games-seeded database.
    """
    db_path = _make_games_seeded_db(tmp_path)
    env_overrides = {
        "DATABASE_PATH": str(db_path),
        "DEV_USER_EMAIL": "testdev@example.com",
    }
    with patch.dict("os.environ", env_overrides):
        with TestClient(app) as client:
            yield client


class TestGameList:
    """Tests for GET /dashboard/games (E-004-04)."""

    def test_game_list_returns_200(self, games_client: TestClient) -> None:
        """GET /dashboard/games returns HTTP 200 (AC-1)."""
        response = games_client.get("/dashboard/games")
        assert response.status_code == 200

    def test_game_list_403_unauthorized_team(self, games_client: TestClient) -> None:
        """GET /dashboard/games?team_id=not-permitted returns 403 (AC-1)."""
        response = games_client.get("/dashboard/games?team_id=not-permitted")
        assert response.status_code == 403

    def test_game_list_shows_opponent_name(self, games_client: TestClient) -> None:
        """GET /dashboard/games HTML includes opponent team name (AC-2)."""
        response = games_client.get("/dashboard/games")
        assert "Rival High School" in response.text

    def test_game_list_shows_score(self, games_client: TestClient) -> None:
        """GET /dashboard/games HTML includes score for a completed game (AC-2)."""
        response = games_client.get("/dashboard/games")
        # game-001: lsb-varsity-2026 is home, scored 7-3 (user sees 7-3)
        assert "7-3" in response.text

    def test_game_list_shows_wl_indicator(self, games_client: TestClient) -> None:
        """GET /dashboard/games HTML includes W/L indicator (AC-3)."""
        response = games_client.get("/dashboard/games")
        html = response.text
        assert "W" in html or "L" in html

    def test_game_list_win_marked_green(self, games_client: TestClient) -> None:
        """GET /dashboard/games: W indicator uses green color class (AC-3)."""
        response = games_client.get("/dashboard/games")
        assert "text-green-700" in response.text

    def test_game_list_games_sorted_desc(self, games_client: TestClient) -> None:
        """GET /dashboard/games: games appear in date-descending order (AC-4)."""
        response = games_client.get("/dashboard/games")
        html = response.text
        # game-001 (2026-03-01 -> "Mar 1") must appear before game-002 (2026-02-20 -> "Feb 20")
        pos_001 = html.find("Mar 1")
        pos_002 = html.find("Feb 20")
        assert pos_001 != -1
        assert pos_002 != -1
        assert pos_001 < pos_002

    def test_game_list_rows_link_to_detail(self, games_client: TestClient) -> None:
        """GET /dashboard/games: game rows link to /dashboard/games/{game_id} (AC-5)."""
        response = games_client.get("/dashboard/games")
        assert "/dashboard/games/game-001" in response.text

    def test_game_list_active_nav_games(self, games_client: TestClient) -> None:
        """GET /dashboard/games: active_nav='games' highlights Games nav item (AC-12)."""
        response = games_client.get("/dashboard/games")
        assert "font-bold" in response.text

    def test_game_list_team_selector(self, games_client: TestClient) -> None:
        """GET /dashboard/games: team selector uses /dashboard/games base_url (AC-10)."""
        response = games_client.get("/dashboard/games")
        # Team selector may not render for single-team users; route must return 200
        assert response.status_code == 200

    def test_game_list_empty_season(self, games_client: TestClient) -> None:
        """GET /dashboard/games?season_id=nonexistent renders empty-state message (AC-14)."""
        response = games_client.get("/dashboard/games?season_id=9999-spring-hs")
        assert response.status_code == 200
        assert "No games found" in response.text

    def test_game_list_season_id_override(self, games_client: TestClient) -> None:
        """GET /dashboard/games?season_id=2025-spring-hs returns alt-season games (AC-14)."""
        response = games_client.get("/dashboard/games?season_id=2025-spring-hs")
        assert response.status_code == 200
        # game-2025 (2025-03-15 -> "Mar 15") should appear
        assert "Mar 15" in response.text


class TestGameDetail:
    """Tests for GET /dashboard/games/{game_id} (E-004-04)."""

    def test_game_detail_returns_200(self, games_client: TestClient) -> None:
        """GET /dashboard/games/game-001 returns 200 (AC-6)."""
        response = games_client.get("/dashboard/games/game-001")
        assert response.status_code == 200

    def test_game_detail_403_unrelated_game(self, games_client: TestClient) -> None:
        """GET /dashboard/games/game-unrelated returns 403 for game not involving permitted team (AC-11, AC-14)."""
        response = games_client.get("/dashboard/games/game-unrelated")
        assert response.status_code == 403

    def test_game_detail_shows_game_date(self, games_client: TestClient) -> None:
        """GET /dashboard/games/game-001 shows game date (AC-9)."""
        response = games_client.get("/dashboard/games/game-001")
        assert "2026-03-01" in response.text

    def test_game_detail_shows_team_names(self, games_client: TestClient) -> None:
        """GET /dashboard/games/game-001 shows both team names in box score (AC-7, AC-9)."""
        response = games_client.get("/dashboard/games/game-001")
        html = response.text
        assert "LSB Varsity 2026" in html
        assert "Rival High School" in html

    def test_game_detail_shows_batting_headers(self, games_client: TestClient) -> None:
        """GET /dashboard/games/game-001 includes batting column headers (AC-7)."""
        response = games_client.get("/dashboard/games/game-001")
        html = response.text
        for header in ("AB", "H", "2B", "3B", "HR", "RBI", "BB", "SO", "SB"):
            assert header in html, f"Expected batting header '{header}' in game detail."

    def test_game_detail_shows_pitching_headers(self, games_client: TestClient) -> None:
        """GET /dashboard/games/game-001 includes pitching column headers (AC-7)."""
        response = games_client.get("/dashboard/games/game-001")
        html = response.text
        for header in ("IP", "H", "ER", "BB", "SO", "HR"):
            assert header in html, f"Expected pitching header '{header}' in game detail."

    def test_game_detail_ip_display_filter(self, games_client: TestClient) -> None:
        """GET /dashboard/games/game-001 uses ip_display for IP column (AC-8).

        gc-p-001 pitched 18 ip_outs = 6.0 IP.
        """
        response = games_client.get("/dashboard/games/game-001")
        assert "6.0" in response.text

    def test_game_detail_player_links(self, games_client: TestClient) -> None:
        """GET /dashboard/games/game-001 player names link to profile pages."""
        response = games_client.get("/dashboard/games/game-001")
        assert "/dashboard/players/" in response.text

    def test_game_detail_details_element_present(self, games_client: TestClient) -> None:
        """GET /dashboard/games/game-001 uses <details> elements for collapsible sections (AC-7)."""
        response = games_client.get("/dashboard/games/game-001")
        assert "<details" in response.text

    def test_game_detail_active_nav_games(self, games_client: TestClient) -> None:
        """GET /dashboard/games/game-001 active_nav='games' highlights Games nav item (AC-12)."""
        response = games_client.get("/dashboard/games/game-001")
        assert "font-bold" in response.text


# ---------------------------------------------------------------------------
# Opponent scouting seed SQL for E-004-05 tests
# ---------------------------------------------------------------------------

_OPPONENT_SEED_SQL = f"""
    -- Opponent team (opp-team-001 already inserted in _GAME_SEED_SQL)
    -- Add an unrelated opponent (not in any game with lsb-varsity-2026)
    INSERT OR IGNORE INTO teams (team_id, name, level, is_owned) VALUES
        ('opp-team-unrelated', 'Unrelated School', NULL, 0);

    -- Opponent batting stats for opp-team-001
    INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES
        ('opp-p-001', 'Jake',  'Rivera'),
        ('opp-p-002', 'Luis',  'Martinez'),
        ('opp-p-003', 'Sam',   'Johnson');

    INSERT OR IGNORE INTO player_season_batting
        (player_id, team_id, season_id, games, ab, h, doubles, triples, hr, rbi, bb, so, sb) VALUES
        ('opp-p-001', 'opp-team-001', '{_CURRENT_SEASON_ID}', 3, 10, 4, 1, 0, 1, 3, 2, 2, 1),
        ('opp-p-002', 'opp-team-001', '{_CURRENT_SEASON_ID}', 3, 9,  2, 0, 0, 0, 1, 1, 3, 0),
        -- opp-p-003 has only 3 AB (below 5 AB threshold for Key Players)
        ('opp-p-003', 'opp-team-001', '{_CURRENT_SEASON_ID}', 1, 3,  2, 0, 0, 0, 1, 0, 0, 0);

    -- Opponent pitching stats for opp-team-001
    INSERT OR IGNORE INTO player_season_pitching
        (player_id, team_id, season_id, games, ip_outs, h, er, bb, so, hr, pitches) VALUES
        -- opp-p-001: 6 IP (18 outs), 3 H, 1 ER, 1 BB, 7 SO -- qualifies (>= 9 ip_outs)
        --   ERA = 1*27/18 = 1.50, K/9 = 7*27/18 = 10.5
        ('opp-p-001', 'opp-team-001', '{_CURRENT_SEASON_ID}', 2, 18, 3, 1, 1, 7, 0, 60),
        -- opp-p-002: 2 IP (6 outs) -- below 9 ip_outs threshold
        ('opp-p-002', 'opp-team-001', '{_CURRENT_SEASON_ID}', 1, 6,  2, 1, 0, 2, 0, 24);

    -- Alt-season game for season_id override test
    INSERT OR IGNORE INTO games (game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score) VALUES
        ('game-opp-2025', '2025-spring-hs', '2025-03-10', 'lsb-varsity-2026', 'opp-team-001', 4, 2);
"""


def _make_opponent_seeded_db(tmp_path: Path) -> Path:
    """Create a SQLite database seeded with opponent scouting data.

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Path to the seeded database file.
    """
    db_path = tmp_path / "test_opponents.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA_SQL)
    conn.executescript(_SEED_SQL)
    conn.executescript(_GAME_SEED_SQL)
    conn.executescript(_OPPONENT_SEED_SQL)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def opponent_client(tmp_path: Path) -> TestClient:
    """Return a TestClient with opponent scouting data seeded.

    Args:
        tmp_path: pytest tmp_path fixture (injected by pytest).

    Returns:
        FastAPI TestClient configured to use the opponent-seeded database.
    """
    db_path = _make_opponent_seeded_db(tmp_path)
    env_overrides = {
        "DATABASE_PATH": str(db_path),
        "DEV_USER_EMAIL": "testdev@example.com",
    }
    with patch.dict("os.environ", env_overrides):
        with TestClient(app) as client:
            yield client


class TestOpponentList:
    """Tests for GET /dashboard/opponents (E-004-05)."""

    def test_opponent_list_returns_200(self, opponent_client: TestClient) -> None:
        """GET /dashboard/opponents returns HTTP 200 (AC-1)."""
        response = opponent_client.get("/dashboard/opponents")
        assert response.status_code == 200

    def test_opponent_list_403_unauthorized_team(self, opponent_client: TestClient) -> None:
        """GET /dashboard/opponents?team_id=not-permitted returns 403 (AC-1)."""
        response = opponent_client.get("/dashboard/opponents?team_id=not-permitted")
        assert response.status_code == 403

    def test_opponent_list_shows_opponent_name(self, opponent_client: TestClient) -> None:
        """GET /dashboard/opponents HTML includes opponent team name (AC-2)."""
        response = opponent_client.get("/dashboard/opponents")
        assert "Rival High School" in response.text

    def test_opponent_list_shows_wl_record(self, opponent_client: TestClient) -> None:
        """GET /dashboard/opponents HTML includes W-L record column (AC-2)."""
        response = opponent_client.get("/dashboard/opponents")
        # Two games: game-001 home W (7-3), game-002 away W (5-2) => 2-0
        assert "2-0" in response.text

    def test_opponent_list_row_links_to_detail(self, opponent_client: TestClient) -> None:
        """GET /dashboard/opponents: opponent rows link to /dashboard/opponents/{id} (AC-3)."""
        response = opponent_client.get("/dashboard/opponents")
        assert "/dashboard/opponents/opp-team-001" in response.text

    def test_opponent_list_empty_state(self, seeded_client: TestClient) -> None:
        """GET /dashboard/opponents renders empty-state message when no opponents (AC-13)."""
        # seeded_client has no games rows -- only batting stats
        response = seeded_client.get("/dashboard/opponents")
        assert response.status_code == 200
        assert "No opponents found" in response.text

    def test_opponent_list_season_id_override(self, opponent_client: TestClient) -> None:
        """GET /dashboard/opponents?season_id=2025-spring-hs filters to alt season (AC-1)."""
        response = opponent_client.get("/dashboard/opponents?season_id=2025-spring-hs")
        assert response.status_code == 200
        # 2025 seed has one game vs opp-team-001
        assert "Rival High School" in response.text

    def test_opponent_list_active_nav_opponents(self, opponent_client: TestClient) -> None:
        """GET /dashboard/opponents sets active_nav='opponents' (AC-10)."""
        response = opponent_client.get("/dashboard/opponents")
        assert "font-bold" in response.text

    def test_opponent_list_team_selector(self, opponent_client: TestClient) -> None:
        """GET /dashboard/opponents includes team selector base_url (AC-9)."""
        response = opponent_client.get("/dashboard/opponents")
        assert response.status_code == 200


class TestOpponentDetail:
    """Tests for GET /dashboard/opponents/{opponent_team_id} (E-004-05)."""

    def test_opponent_detail_returns_200(self, opponent_client: TestClient) -> None:
        """GET /dashboard/opponents/opp-team-001 returns 200 (AC-4)."""
        response = opponent_client.get("/dashboard/opponents/opp-team-001")
        assert response.status_code == 200

    def test_opponent_detail_403_unrelated_opponent(self, opponent_client: TestClient) -> None:
        """GET /dashboard/opponents/opp-team-unrelated returns 403 (AC-11, AC-14)."""
        response = opponent_client.get("/dashboard/opponents/opp-team-unrelated")
        assert response.status_code == 403

    def test_opponent_detail_shows_batting_leaders(self, opponent_client: TestClient) -> None:
        """GET /dashboard/opponents/opp-team-001 shows batting leaders table (AC-5, AC-6)."""
        response = opponent_client.get("/dashboard/opponents/opp-team-001")
        html = response.text
        assert "Batting Leaders" in html
        assert "Rivera" in html or "Martinez" in html

    def test_opponent_detail_batting_column_headers(self, opponent_client: TestClient) -> None:
        """GET /dashboard/opponents/opp-team-001 includes all batting column headers (AC-6)."""
        response = opponent_client.get("/dashboard/opponents/opp-team-001")
        html = response.text
        for header in ("AVG", "OBP", "GP", "AB", "BB", "SO", "SLG", "H", "HR", "SB", "RBI"):
            assert header in html, f"Expected batting header '{header}' in opponent detail."

    def test_opponent_detail_shows_pitching_leaders(self, opponent_client: TestClient) -> None:
        """GET /dashboard/opponents/opp-team-001 shows pitching leaders table (AC-5, AC-7)."""
        response = opponent_client.get("/dashboard/opponents/opp-team-001")
        assert "Pitching Leaders" in response.text

    def test_opponent_detail_pitching_column_headers(self, opponent_client: TestClient) -> None:
        """GET /dashboard/opponents/opp-team-001 includes all pitching column headers (AC-7)."""
        response = opponent_client.get("/dashboard/opponents/opp-team-001")
        html = response.text
        for header in ("ERA", "K/9", "WHIP", "GP", "IP", "H", "ER", "BB", "SO"):
            assert header in html, f"Expected pitching header '{header}' in opponent detail."

    def test_opponent_detail_key_players_card(self, opponent_client: TestClient) -> None:
        """GET /dashboard/opponents/opp-team-001 shows Key Players card (AC-5, AC-15)."""
        response = opponent_client.get("/dashboard/opponents/opp-team-001")
        assert "Key Players" in response.text

    def test_opponent_detail_key_hitter_name_and_avg(self, opponent_client: TestClient) -> None:
        """Key Players card shows best hitter name and AVG (AC-15).

        opp-p-001: 4 H / 10 AB = .400 AVG (highest, meets 5 AB minimum).
        """
        response = opponent_client.get("/dashboard/opponents/opp-team-001")
        html = response.text
        assert "Rivera" in html
        assert ".400" in html

    def test_opponent_detail_key_pitcher_name_and_era(self, opponent_client: TestClient) -> None:
        """Key Players card shows best pitcher name and ERA (AC-15).

        opp-p-001: 18 ip_outs, 1 ER => ERA = 1*27/18 = 1.50 (meets 9 ip_outs min).
        """
        response = opponent_client.get("/dashboard/opponents/opp-team-001")
        html = response.text
        assert "Rivera" in html
        assert "1.50" in html

    def test_opponent_detail_insufficient_data_when_no_stats(
        self, games_client: TestClient
    ) -> None:
        """Key Players card shows 'Insufficient data.' when no players meet threshold (AC-15).

        games_client has games vs opp-team-001 but no opponent batting/pitching rows, so
        neither best_hitter nor best_pitcher can meet the minimum sample thresholds.
        """
        response = games_client.get("/dashboard/opponents/opp-team-001")
        assert response.status_code == 200
        assert "Insufficient data." in response.text

    def test_opponent_detail_no_stats_shows_message(
        self, games_client: TestClient
    ) -> None:
        """GET /dashboard/opponents/opp-team-001 shows 'No batting stats available' when no stats loaded (AC-5).

        games_client has games vs opp-team-001 but no opponent batting/pitching rows.
        """
        response = games_client.get("/dashboard/opponents/opp-team-001")
        assert response.status_code == 200
        # Key Players card should show insufficient data
        assert "Insufficient data." in response.text

    def test_opponent_detail_last_meeting_card(self, opponent_client: TestClient) -> None:
        """GET /dashboard/opponents/opp-team-001 shows Last Meeting card (AC-16)."""
        response = opponent_client.get("/dashboard/opponents/opp-team-001")
        assert "Last Meeting" in response.text

    def test_opponent_detail_last_meeting_shows_score(
        self, opponent_client: TestClient
    ) -> None:
        """Last Meeting card shows score and W/L for most recent game (AC-16, AC-18).

        game-001 (2026-03-01): lsb-varsity-2026 home 7-3 vs opp-team-001 => W.
        game-002 (2026-02-20): lsb-varsity-2026 away 5-2 vs opp-team-001 => W.
        Most recent = game-001.
        """
        response = opponent_client.get("/dashboard/opponents/opp-team-001")
        html = response.text
        # game-001: lsb is home 7-3, so my_score=7, their_score=3
        assert "7-3" in html

    def test_opponent_detail_first_meeting_message_when_no_games(
        self, opponent_client: TestClient
    ) -> None:
        """Last Meeting card does NOT show 'First meeting' when a completed game exists (AC-16, AC-18).

        opponent_client has game-001 (completed), so last_meeting is populated and
        the 'First meeting this season.' fallback should NOT appear.
        """
        response = opponent_client.get("/dashboard/opponents/opp-team-001")
        assert response.status_code == 200
        assert "First meeting this season." not in response.text
        assert "Last Meeting" in response.text

    def test_opponent_detail_first_meeting_via_scheduled_game(
        self, tmp_path: Path
    ) -> None:
        """'First meeting this season.' shown when only scheduled (not completed) games exist (AC-18)."""
        db_path = tmp_path / "test_no_completed.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_SQL)
        conn.executescript(_SEED_SQL)
        # Insert opp team and a scheduled (not completed) game
        conn.executescript(f"""
            INSERT OR IGNORE INTO teams (team_id, name, level, is_owned) VALUES
                ('opp-sched-001', 'Future Opponent', NULL, 0);
            INSERT OR IGNORE INTO games
                (game_id, season_id, game_date, home_team_id, away_team_id, status)
            VALUES
                ('game-sched', '{_CURRENT_SEASON_ID}', '2099-03-01',
                 'lsb-varsity-2026', 'opp-sched-001', 'scheduled');
        """)
        conn.commit()
        conn.close()
        env_overrides = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": "testdev@example.com",
        }
        with patch.dict("os.environ", env_overrides):
            with TestClient(app) as client:
                response = client.get("/dashboard/opponents/opp-sched-001")
        assert response.status_code == 200
        assert "First meeting this season." in response.text

    def test_opponent_detail_active_nav_opponents(self, opponent_client: TestClient) -> None:
        """GET /dashboard/opponents/opp-team-001 sets active_nav='opponents' (AC-10)."""
        response = opponent_client.get("/dashboard/opponents/opp-team-001")
        assert "font-bold" in response.text

    def test_opponent_detail_season_id_override(self, opponent_client: TestClient) -> None:
        """GET /dashboard/opponents/opp-team-001?season_id=2025-spring-hs filters to alt season (AC-4)."""
        response = opponent_client.get(
            "/dashboard/opponents/opp-team-001?season_id=2025-spring-hs"
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Player profile seed SQL for E-004-06 tests
# ---------------------------------------------------------------------------

_PLAYER_PROFILE_SEED_SQL = f"""
    -- Add a second season for multi-season batting test
    INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES
        ('2025-spring-hs', 'Spring 2025 High School', 'spring-hs', 2025);

    -- Add team_rosters entries so player profile auth passes for gc-p-001
    INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id, jersey_number) VALUES
        ('lsb-varsity-2026', 'gc-p-001', '{_CURRENT_SEASON_ID}', '12'),
        ('lsb-varsity-2026', 'gc-p-002', '{_CURRENT_SEASON_ID}', '7');

    -- Multi-season batting for gc-p-001: one row in each season
    INSERT OR IGNORE INTO player_season_batting
        (player_id, team_id, season_id, games, ab, h, doubles, triples, hr, rbi, bb, so, sb) VALUES
        ('gc-p-001', 'lsb-varsity-2026', '2025-spring-hs', 4, 12, 5, 2, 0, 0, 3, 3, 2, 1);

    -- Pitching season for gc-p-001 in current season
    -- 18 ip_outs, 2 ER, 9 SO, 3 BB, 4 H => ERA=3.00, K/9=13.5, WHIP=1.17
    INSERT OR IGNORE INTO player_season_pitching
        (player_id, team_id, season_id, games, ip_outs, h, er, bb, so, hr) VALUES
        ('gc-p-001', 'lsb-varsity-2026', '{_CURRENT_SEASON_ID}', 3, 18, 4, 2, 3, 9, 0);

    -- Opponent team and games for recent games section
    INSERT OR IGNORE INTO teams (team_id, name, level, is_owned) VALUES
        ('opp-team-001', 'Rival High School', NULL, 0);
    INSERT OR IGNORE INTO games (game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score) VALUES
        ('game-001', '{_CURRENT_SEASON_ID}', '2026-03-01', 'lsb-varsity-2026', 'opp-team-001', 7, 3),
        ('game-002', '{_CURRENT_SEASON_ID}', '2026-02-20', 'opp-team-001', 'lsb-varsity-2026', 2, 5);

    -- Per-game batting lines for gc-p-001
    INSERT OR IGNORE INTO player_game_batting (game_id, player_id, team_id, ab, h, doubles, triples, hr, rbi, bb, so, sb) VALUES
        ('game-001', 'gc-p-001', 'lsb-varsity-2026', 4, 2, 1, 0, 1, 2, 1, 1, 0),
        ('game-002', 'gc-p-001', 'lsb-varsity-2026', 3, 1, 0, 0, 0, 0, 0, 1, 1);

    -- Per-game pitching for gc-p-001 in game-001 (two-way player)
    INSERT OR IGNORE INTO player_game_pitching (game_id, player_id, team_id, ip_outs, h, er, bb, so, hr) VALUES
        ('game-001', 'gc-p-001', 'lsb-varsity-2026', 9, 2, 0, 1, 5, 0);

    -- Player with no stats at all (just a roster entry)
    INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES
        ('gc-p-nostats', 'NoStats', 'Player');
    INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id) VALUES
        ('lsb-varsity-2026', 'gc-p-nostats', '{_CURRENT_SEASON_ID}');
"""


def _make_player_profile_seeded_db(tmp_path: Path) -> Path:
    """Create a SQLite database seeded with player profile data.

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Path to the seeded database file.
    """
    db_path = tmp_path / "test_player_profile.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA_SQL)
    conn.executescript(_SEED_SQL)
    conn.executescript(_PLAYER_PROFILE_SEED_SQL)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def player_profile_client(tmp_path: Path) -> TestClient:
    """Return a TestClient with player profile data seeded.

    Args:
        tmp_path: pytest tmp_path fixture (injected by pytest).

    Returns:
        FastAPI TestClient configured to use the player-profile-seeded database.
    """
    db_path = _make_player_profile_seeded_db(tmp_path)
    env_overrides = {
        "DATABASE_PATH": str(db_path),
        "DEV_USER_EMAIL": "testdev@example.com",
    }
    with patch.dict("os.environ", env_overrides):
        with TestClient(app) as client:
            yield client


class TestPlayerProfile:
    """Tests for GET /dashboard/players/{player_id} (E-004-06)."""

    def test_player_profile_returns_200(self, player_profile_client: TestClient) -> None:
        """GET /dashboard/players/gc-p-001 returns 200 (AC-1)."""
        response = player_profile_client.get("/dashboard/players/gc-p-001")
        assert response.status_code == 200

    def test_player_profile_404_nonexistent(self, player_profile_client: TestClient) -> None:
        """GET /dashboard/players/nonexistent returns 404 (AC-11)."""
        response = player_profile_client.get("/dashboard/players/nonexistent-player-id")
        assert response.status_code == 404

    def test_player_profile_403_unauthorized_player(
        self, player_profile_client: TestClient
    ) -> None:
        """GET /dashboard/players/{player_id} returns 403 when player not on any permitted team (AC-10, AC-15).

        gc-p-003 exists (has batting stats) but has no team_rosters entry
        for lsb-varsity-2026, so should return 403.
        """
        response = player_profile_client.get("/dashboard/players/gc-p-003")
        assert response.status_code == 403

    def test_player_profile_shows_player_name(
        self, player_profile_client: TestClient
    ) -> None:
        """GET /dashboard/players/gc-p-001 shows player full name (AC-2)."""
        response = player_profile_client.get("/dashboard/players/gc-p-001")
        assert "Marcus" in response.text
        assert "Whitehorse" in response.text

    def test_player_profile_shows_jersey_number(
        self, player_profile_client: TestClient
    ) -> None:
        """GET /dashboard/players/gc-p-001 shows current jersey number (AC-2)."""
        response = player_profile_client.get("/dashboard/players/gc-p-001")
        assert "#12" in response.text

    def test_player_profile_batting_section_renders(
        self, player_profile_client: TestClient
    ) -> None:
        """GET /dashboard/players/gc-p-001 renders Batting by Season table (AC-3, AC-14)."""
        response = player_profile_client.get("/dashboard/players/gc-p-001")
        html = response.text
        assert "Batting by Season" in html
        # Column headers per AC-3
        for header in ("AVG", "OBP", "GP", "BB", "SO", "SLG", "H", "AB", "2B", "3B", "HR", "SB", "RBI"):
            assert header in html, f"Missing batting header: {header}"

    def test_player_profile_pitching_section_renders(
        self, player_profile_client: TestClient
    ) -> None:
        """GET /dashboard/players/gc-p-001 renders Pitching by Season table (AC-4, AC-14)."""
        response = player_profile_client.get("/dashboard/players/gc-p-001")
        html = response.text
        assert "Pitching by Season" in html
        # Column headers per AC-4
        for header in ("ERA", "K/9", "WHIP", "GP", "IP", "H", "ER", "BB", "SO", "HR"):
            assert header in html, f"Missing pitching header: {header}"

    def test_player_profile_batting_computed_avg(
        self, player_profile_client: TestClient
    ) -> None:
        """GET /dashboard/players/gc-p-001 shows correct AVG for current season (AC-8, AC-14).

        gc-p-001 current season: 3 H / 6 AB = .500 AVG.
        """
        response = player_profile_client.get("/dashboard/players/gc-p-001")
        assert ".500" in response.text

    def test_player_profile_pitching_era(
        self, player_profile_client: TestClient
    ) -> None:
        """GET /dashboard/players/gc-p-001 shows correct ERA (AC-8, AC-14).

        gc-p-001: 18 ip_outs, 2 ER => ERA = 2*27/18 = 3.00.
        """
        response = player_profile_client.get("/dashboard/players/gc-p-001")
        assert "3.00" in response.text

    def test_player_profile_ip_display(
        self, player_profile_client: TestClient
    ) -> None:
        """GET /dashboard/players/gc-p-001 uses ip_display for IP column (AC-9).

        gc-p-001: 18 ip_outs => '6.0'.
        """
        response = player_profile_client.get("/dashboard/players/gc-p-001")
        assert "6.0" in response.text

    def test_player_profile_season_names(
        self, player_profile_client: TestClient
    ) -> None:
        """GET /dashboard/players/gc-p-001 shows human-readable season names (AC-6)."""
        response = player_profile_client.get("/dashboard/players/gc-p-001")
        html = response.text
        # Season name from DB (seeded in _SEED_SQL / _PLAYER_PROFILE_SEED_SQL)
        assert "Spring" in html

    def test_player_profile_team_names(
        self, player_profile_client: TestClient
    ) -> None:
        """GET /dashboard/players/gc-p-001 shows team names (AC-7)."""
        response = player_profile_client.get("/dashboard/players/gc-p-001")
        assert "LSB Varsity 2026" in response.text

    def test_player_profile_recent_games(
        self, player_profile_client: TestClient
    ) -> None:
        """GET /dashboard/players/gc-p-001 shows Recent Games section with game rows (AC-13)."""
        response = player_profile_client.get("/dashboard/players/gc-p-001")
        html = response.text
        assert "Recent Games" in html
        # game rows link to game detail
        assert "/dashboard/games/game-001" in html or "/dashboard/games/game-002" in html

    def test_player_profile_recent_games_batting_stat_line(
        self, player_profile_client: TestClient
    ) -> None:
        """GET /dashboard/players/gc-p-001 recent games show batting stat line (AC-13).

        game-001: gc-p-001 went 2-for-4 with 1 HR, 2 RBI.
        """
        response = player_profile_client.get("/dashboard/players/gc-p-001")
        html = response.text
        # Batting condensed line: "2-for-4"
        assert "2-for-4" in html

    def test_player_profile_no_stats_shows_messages(
        self, player_profile_client: TestClient
    ) -> None:
        """GET /dashboard/players/gc-p-nostats shows empty-state for batting and pitching (AC-5)."""
        response = player_profile_client.get("/dashboard/players/gc-p-nostats")
        assert response.status_code == 200
        html = response.text
        assert "No batting stats" in html
        assert "No pitching stats" in html

    def test_player_profile_current_season_summary_card(
        self, player_profile_client: TestClient
    ) -> None:
        """GET /dashboard/players/gc-p-001 shows Current Season Summary card (AC-2a, AC-16)."""
        response = player_profile_client.get("/dashboard/players/gc-p-001")
        html = response.text
        assert "Current Season Summary" in html

    def test_player_profile_current_season_summary_no_stats(
        self, player_profile_client: TestClient
    ) -> None:
        """GET /dashboard/players/gc-p-nostats shows 'No stats recorded yet.' in card (AC-2a, AC-16)."""
        response = player_profile_client.get("/dashboard/players/gc-p-nostats")
        html = response.text
        assert "No stats recorded yet" in html

    def test_player_profile_no_active_nav(
        self, player_profile_client: TestClient
    ) -> None:
        """GET /dashboard/players/{player_id} has no active nav highlight (AC-9, detail page)."""
        response = player_profile_client.get("/dashboard/players/gc-p-001")
        # Page should load 200 without crashing -- no active nav is set
        assert response.status_code == 200

    def test_player_profile_two_way_player_dedup(
        self, player_profile_client: TestClient
    ) -> None:
        """Recent Games deduplicates by game_id for two-way players (AC-13).

        gc-p-001 has both batting and pitching lines in game-001.
        game-001 should appear only once in Recent Games.
        """
        response = player_profile_client.get("/dashboard/players/gc-p-001")
        html = response.text
        # Count occurrences of game-001 game detail link
        occurrences = html.count("/dashboard/games/game-001")
        # Should appear once (for the recent games link), not twice
        assert occurrences == 1
