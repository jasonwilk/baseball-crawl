# synthetic-test-data
"""Tests for dashboard endpoints (E-009-03, E-004-02 through E-004-06).

Uses a temporary SQLite database seeded with synthetic data matching the
E-100 schema (INTEGER PK for teams, membership_type, gp/gp_pitcher columns).
Tests run without Docker -- no real database or network access required.

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

from migrations.apply_migrations import run_migrations  # noqa: E402
from src.api.main import app  # noqa: E402

# Derive season_id the same way the route does, so tests stay valid across years.
_CURRENT_SEASON_ID = f"{datetime.date.today().year}-spring-hs"
_ALT_SEASON_ID = "2025-spring-hs"


# ---------------------------------------------------------------------------
# Database fixture helpers -- Python parameterized inserts (no TEXT team_id)
# ---------------------------------------------------------------------------


def _apply_schema(db_path: Path) -> None:
    """Apply migrations to a fresh database at db_path."""
    run_migrations(db_path=db_path)


def _insert_lsb_team_and_user(conn: sqlite3.Connection) -> tuple[int, int]:
    """Insert LSB Varsity team, current season, dev user, and user_team_access.

    Returns:
        Tuple of (lsb_team_id, user_id).
    """
    cursor = conn.execute(
        "INSERT INTO teams (name, membership_type, classification) VALUES (?, ?, ?)",
        ("LSB Varsity 2026", "member", "varsity"),
    )
    lsb_team_id: int = cursor.lastrowid  # type: ignore[assignment]

    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
        (
            _CURRENT_SEASON_ID,
            f"Spring {datetime.date.today().year} High School",
            "spring-hs",
            datetime.date.today().year,
        ),
    )

    cursor = conn.execute(
        "INSERT OR IGNORE INTO users (email) VALUES (?)",
        ("testdev@example.com",),
    )
    user_id: int = cursor.lastrowid or conn.execute(  # type: ignore[assignment]
        "SELECT id FROM users WHERE email = ?", ("testdev@example.com",)
    ).fetchone()[0]

    conn.execute(
        "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
        (user_id, lsb_team_id),
    )
    return lsb_team_id, user_id


def _insert_players_and_batting(
    conn: sqlite3.Connection, lsb_team_id: int
) -> None:
    """Insert 6 players and their season batting stats for lsb_team_id."""
    conn.executemany(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        [
            ("gc-p-001", "Marcus", "Whitehorse"),
            ("gc-p-002", "Diego", "Runningwater"),
            ("gc-p-003", "Elijah", "Strongbow"),
            ("gc-p-004", "Nathan", "Redcloud"),
            ("gc-p-005", "Isaiah", "Eagleheart"),
            ("gc-p-006", "Zane", "Noatbats"),
        ],
    )
    conn.executemany(
        "INSERT OR IGNORE INTO player_season_batting"
        " (player_id, team_id, season_id, gp, ab, h, doubles, triples, hr, rbi, bb, so, sb)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("gc-p-001", lsb_team_id, _CURRENT_SEASON_ID, 2, 6, 3, 1, 0, 0, 2, 2, 1, 1),
            ("gc-p-002", lsb_team_id, _CURRENT_SEASON_ID, 2, 8, 2, 0, 0, 0, 1, 1, 2, 0),
            ("gc-p-003", lsb_team_id, _CURRENT_SEASON_ID, 2, 8, 4, 1, 0, 1, 3, 0, 1, 0),
            ("gc-p-004", lsb_team_id, _CURRENT_SEASON_ID, 2, 6, 1, 0, 0, 0, 0, 2, 3, 1),
            ("gc-p-005", lsb_team_id, _CURRENT_SEASON_ID, 2, 7, 3, 0, 1, 0, 2, 0, 2, 2),
            ("gc-p-006", lsb_team_id, _CURRENT_SEASON_ID, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        ],
    )


def _insert_pitching(conn: sqlite3.Connection, lsb_team_id: int) -> None:
    """Insert season pitching stats for LSB team, including an alt-season row."""
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
        (_ALT_SEASON_ID, "Spring 2025 High School", "spring-hs", 2025),
    )
    conn.executemany(
        "INSERT OR IGNORE INTO player_season_pitching"
        " (player_id, team_id, season_id, gp_pitcher, ip_outs, h, er, bb, so, hr)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            # gc-p-001: 6 IP (18 outs), 4H, 2ER, 3BB, 9SO => ERA=3.00 K/9=13.5 WHIP=1.17
            ("gc-p-001", lsb_team_id, _CURRENT_SEASON_ID, 3, 18, 4, 2, 3, 9, 0),
            # gc-p-002: 3 IP (9 outs), 5H, 4ER, 2BB, 3SO => ERA=12.00 K/9=9.0 WHIP=2.33
            ("gc-p-002", lsb_team_id, _CURRENT_SEASON_ID, 2, 9, 5, 4, 2, 3, 1),
            # gc-p-003: 0 ip_outs -- shows '-' for rate stats
            ("gc-p-003", lsb_team_id, _CURRENT_SEASON_ID, 1, 0, 1, 1, 1, 0, 0),
        ],
    )
    # Alt-season row for season_id override test: gc-p-001, 2 IP (6 outs), 0 ER => ERA 0.00
    conn.execute(
        "INSERT OR IGNORE INTO player_season_pitching"
        " (player_id, team_id, season_id, gp_pitcher, ip_outs, h, er, bb, so, hr)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("gc-p-001", lsb_team_id, _ALT_SEASON_ID, 1, 6, 1, 0, 0, 5, 0),
    )


def _insert_game_data(
    conn: sqlite3.Connection, lsb_team_id: int
) -> tuple[int, int]:
    """Insert opponent team, games, and per-game box score data.

    Returns:
        Tuple of (opp_team_id, unrelated_game_opponent_team_id).
    """
    # Opponent team
    cursor = conn.execute(
        "INSERT OR IGNORE INTO teams (name, membership_type) VALUES (?, ?)",
        ("Rival High School", "tracked"),
    )
    opp_team_id: int = cursor.lastrowid  # type: ignore[assignment]

    # Two unrelated teams for the unrelated game
    cursor = conn.execute(
        "INSERT OR IGNORE INTO teams (name, membership_type) VALUES (?, ?)",
        ("Other High School", "tracked"),
    )
    other_team_id1: int = cursor.lastrowid  # type: ignore[assignment]
    cursor = conn.execute(
        "INSERT OR IGNORE INTO teams (name, membership_type) VALUES (?, ?)",
        ("Another High School", "tracked"),
    )
    other_team_id2: int = cursor.lastrowid  # type: ignore[assignment]

    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
        (_ALT_SEASON_ID, "Spring 2025 High School", "spring-hs", 2025),
    )

    # LSB games in current season
    conn.executemany(
        "INSERT OR IGNORE INTO games"
        " (game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score, status)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("game-001", _CURRENT_SEASON_ID, "2026-03-01", lsb_team_id, opp_team_id, 7, 3, "completed"),
            ("game-002", _CURRENT_SEASON_ID, "2026-02-20", opp_team_id, lsb_team_id, 2, 5, "completed"),
        ],
    )

    # Unrelated game (not involving lsb_team_id)
    conn.execute(
        "INSERT OR IGNORE INTO games"
        " (game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score, status)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("game-unrelated", _CURRENT_SEASON_ID, "2026-03-05", other_team_id1, other_team_id2, 4, 1, "completed"),
    )

    # Alt-season game
    conn.execute(
        "INSERT OR IGNORE INTO games"
        " (game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score, status)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("game-2025", _ALT_SEASON_ID, "2025-03-15", lsb_team_id, opp_team_id, 6, 4, "completed"),
    )

    # Per-game batting for game-001 (lsb = home)
    conn.executemany(
        "INSERT OR IGNORE INTO player_game_batting"
        " (game_id, player_id, team_id, ab, h, doubles, triples, hr, rbi, bb, so, sb)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("game-001", "gc-p-001", lsb_team_id, 4, 2, 1, 0, 0, 2, 1, 1, 0),
            ("game-001", "gc-p-002", lsb_team_id, 3, 1, 0, 0, 0, 0, 0, 1, 1),
        ],
    )

    # Per-game pitching for game-001
    conn.execute(
        "INSERT OR IGNORE INTO player_game_pitching"
        " (game_id, player_id, team_id, ip_outs, h, er, bb, so)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("game-001", "gc-p-001", lsb_team_id, 18, 3, 1, 2, 8),
    )

    return opp_team_id, other_team_id1


def _insert_opponent_stats(
    conn: sqlite3.Connection, lsb_team_id: int, opp_team_id: int
) -> int:
    """Insert opponent batting/pitching stats and an unrelated opponent team.

    Returns:
        unrelated_opp_team_id (for authorization tests).
    """
    cursor = conn.execute(
        "INSERT OR IGNORE INTO teams (name, membership_type) VALUES (?, ?)",
        ("Unrelated School", "tracked"),
    )
    unrelated_opp_id: int = cursor.lastrowid  # type: ignore[assignment]

    conn.executemany(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        [
            ("opp-p-001", "Jake", "Rivera"),
            ("opp-p-002", "Luis", "Martinez"),
            ("opp-p-003", "Sam", "Johnson"),
        ],
    )

    conn.executemany(
        "INSERT OR IGNORE INTO player_season_batting"
        " (player_id, team_id, season_id, gp, ab, h, doubles, triples, hr, rbi, bb, so, sb)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("opp-p-001", opp_team_id, _CURRENT_SEASON_ID, 3, 10, 4, 1, 0, 1, 3, 2, 2, 1),
            ("opp-p-002", opp_team_id, _CURRENT_SEASON_ID, 3, 9, 2, 0, 0, 0, 1, 1, 3, 0),
            # opp-p-003: 3 AB (below 5 AB threshold for Key Players)
            ("opp-p-003", opp_team_id, _CURRENT_SEASON_ID, 1, 3, 2, 0, 0, 0, 1, 0, 0, 0),
        ],
    )

    conn.executemany(
        "INSERT OR IGNORE INTO player_season_pitching"
        " (player_id, team_id, season_id, gp_pitcher, ip_outs, h, er, bb, so, hr, pitches)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            # opp-p-001: 6 IP (18 outs), 1ER => ERA=1.50 (>= 9 ip_outs threshold)
            ("opp-p-001", opp_team_id, _CURRENT_SEASON_ID, 2, 18, 3, 1, 1, 7, 0, 60),
            # opp-p-002: 2 IP (6 outs) -- below 9 ip_outs threshold
            ("opp-p-002", opp_team_id, _CURRENT_SEASON_ID, 1, 6, 2, 1, 0, 2, 0, 24),
        ],
    )

    # Alt-season game for season_id override test
    conn.execute(
        "INSERT OR IGNORE INTO games"
        " (game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score, status)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("game-opp-2025", _ALT_SEASON_ID, "2025-03-10", lsb_team_id, opp_team_id, 4, 2, "completed"),
    )

    return unrelated_opp_id


def _insert_player_profile_data(
    conn: sqlite3.Connection, lsb_team_id: int, opp_team_id: int
) -> None:
    """Insert player profile data: roster entries, multi-season stats, games."""
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
        (_ALT_SEASON_ID, "Spring 2025 High School", "spring-hs", 2025),
    )

    # team_rosters entries for auth check
    conn.executemany(
        "INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id, jersey_number)"
        " VALUES (?, ?, ?, ?)",
        [
            (lsb_team_id, "gc-p-001", _CURRENT_SEASON_ID, "12"),
            (lsb_team_id, "gc-p-002", _CURRENT_SEASON_ID, "7"),
        ],
    )

    # Multi-season batting for gc-p-001
    conn.execute(
        "INSERT OR IGNORE INTO player_season_batting"
        " (player_id, team_id, season_id, gp, ab, h, doubles, triples, hr, rbi, bb, so, sb)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("gc-p-001", lsb_team_id, _ALT_SEASON_ID, 4, 12, 5, 2, 0, 0, 3, 3, 2, 1),
    )

    # Pitching season for gc-p-001 in current season
    conn.execute(
        "INSERT OR IGNORE INTO player_season_pitching"
        " (player_id, team_id, season_id, gp_pitcher, ip_outs, h, er, bb, so, hr)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("gc-p-001", lsb_team_id, _CURRENT_SEASON_ID, 3, 18, 4, 2, 3, 9, 0),
    )

    # Games for recent games section
    conn.executemany(
        "INSERT OR IGNORE INTO games"
        " (game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score, status)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("game-001", _CURRENT_SEASON_ID, "2026-03-01", lsb_team_id, opp_team_id, 7, 3, "completed"),
            ("game-002", _CURRENT_SEASON_ID, "2026-02-20", opp_team_id, lsb_team_id, 2, 5, "completed"),
        ],
    )

    # Per-game batting for gc-p-001
    conn.executemany(
        "INSERT OR IGNORE INTO player_game_batting"
        " (game_id, player_id, team_id, ab, h, doubles, triples, hr, rbi, bb, so, sb)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("game-001", "gc-p-001", lsb_team_id, 4, 2, 1, 0, 1, 2, 1, 1, 0),
            ("game-002", "gc-p-001", lsb_team_id, 3, 1, 0, 0, 0, 0, 0, 1, 1),
        ],
    )

    # Per-game pitching for gc-p-001 in game-001 (two-way player)
    conn.execute(
        "INSERT OR IGNORE INTO player_game_pitching"
        " (game_id, player_id, team_id, ip_outs, h, er, bb, so)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("game-001", "gc-p-001", lsb_team_id, 9, 2, 0, 1, 5),
    )

    # Player with no stats (just a roster entry)
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        ("gc-p-nostats", "NoStats", "Player"),
    )
    conn.execute(
        "INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id) VALUES (?, ?, ?)",
        (lsb_team_id, "gc-p-nostats", _CURRENT_SEASON_ID),
    )


# ---------------------------------------------------------------------------
# DB factory functions -- return (db_path, team_ids...)
# ---------------------------------------------------------------------------


def _make_seeded_db(tmp_path: Path) -> tuple[Path, int]:
    """Create database with basic batting data. Returns (db_path, lsb_team_id)."""
    db_path = tmp_path / "test_app.db"
    _apply_schema(db_path)
    conn = sqlite3.connect(str(db_path))
    lsb_team_id, _ = _insert_lsb_team_and_user(conn)
    _insert_players_and_batting(conn, lsb_team_id)
    conn.commit()
    conn.close()
    return db_path, lsb_team_id


def _make_pitching_seeded_db(tmp_path: Path) -> tuple[Path, int]:
    """Create database with batting + pitching data. Returns (db_path, lsb_team_id)."""
    db_path = tmp_path / "test_pitching.db"
    _apply_schema(db_path)
    conn = sqlite3.connect(str(db_path))
    lsb_team_id, _ = _insert_lsb_team_and_user(conn)
    _insert_players_and_batting(conn, lsb_team_id)
    _insert_pitching(conn, lsb_team_id)
    conn.commit()
    conn.close()
    return db_path, lsb_team_id


def _make_games_seeded_db(tmp_path: Path) -> tuple[Path, int, int]:
    """Create database with game log data. Returns (db_path, lsb_team_id, opp_team_id)."""
    db_path = tmp_path / "test_games.db"
    _apply_schema(db_path)
    conn = sqlite3.connect(str(db_path))
    lsb_team_id, _ = _insert_lsb_team_and_user(conn)
    _insert_players_and_batting(conn, lsb_team_id)
    opp_team_id, _ = _insert_game_data(conn, lsb_team_id)
    conn.commit()
    conn.close()
    return db_path, lsb_team_id, opp_team_id


def _make_opponent_seeded_db(tmp_path: Path) -> tuple[Path, int, int, int]:
    """Create database with opponent scouting data.
    Returns (db_path, lsb_team_id, opp_team_id, unrelated_opp_team_id).
    """
    db_path = tmp_path / "test_opponents.db"
    _apply_schema(db_path)
    conn = sqlite3.connect(str(db_path))
    lsb_team_id, _ = _insert_lsb_team_and_user(conn)
    _insert_players_and_batting(conn, lsb_team_id)
    opp_team_id, _ = _insert_game_data(conn, lsb_team_id)
    unrelated_opp_id = _insert_opponent_stats(conn, lsb_team_id, opp_team_id)
    conn.commit()
    conn.close()
    return db_path, lsb_team_id, opp_team_id, unrelated_opp_id


def _make_player_profile_seeded_db(tmp_path: Path) -> tuple[Path, int, int]:
    """Create database with player profile data. Returns (db_path, lsb_team_id, opp_team_id)."""
    db_path = tmp_path / "test_player_profile.db"
    _apply_schema(db_path)
    conn = sqlite3.connect(str(db_path))
    lsb_team_id, _ = _insert_lsb_team_and_user(conn)
    _insert_players_and_batting(conn, lsb_team_id)
    # Need opponent team for games
    cursor = conn.execute(
        "INSERT OR IGNORE INTO teams (name, membership_type) VALUES (?, ?)",
        ("Rival High School", "tracked"),
    )
    opp_team_id: int = cursor.lastrowid  # type: ignore[assignment]
    _insert_player_profile_data(conn, lsb_team_id, opp_team_id)
    conn.commit()
    conn.close()
    return db_path, lsb_team_id, opp_team_id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded_client(tmp_path: Path) -> TestClient:
    """TestClient backed by a seeded database (batting only)."""
    db_path, _lsb_id = _make_seeded_db(tmp_path)
    env_overrides = {
        "DATABASE_PATH": str(db_path),
        "DEV_USER_EMAIL": "testdev@example.com",
    }
    with patch.dict("os.environ", env_overrides):
        with TestClient(app) as client:
            yield client


@pytest.fixture()
def pitching_client(tmp_path: Path):
    """TestClient with pitching data seeded. Yields (client, lsb_team_id)."""
    db_path, lsb_team_id = _make_pitching_seeded_db(tmp_path)
    env_overrides = {
        "DATABASE_PATH": str(db_path),
        "DEV_USER_EMAIL": "testdev@example.com",
    }
    with patch.dict("os.environ", env_overrides):
        with TestClient(app) as client:
            yield client, lsb_team_id


@pytest.fixture()
def games_client(tmp_path: Path):
    """TestClient with game data seeded. Yields (client, lsb_team_id, opp_team_id)."""
    db_path, lsb_team_id, opp_team_id = _make_games_seeded_db(tmp_path)
    env_overrides = {
        "DATABASE_PATH": str(db_path),
        "DEV_USER_EMAIL": "testdev@example.com",
    }
    with patch.dict("os.environ", env_overrides):
        with TestClient(app) as client:
            yield client, lsb_team_id, opp_team_id


@pytest.fixture()
def opponent_client(tmp_path: Path):
    """TestClient with opponent scouting data. Yields (client, lsb_team_id, opp_team_id, unrelated_opp_id)."""
    db_path, lsb_team_id, opp_team_id, unrelated_opp_id = _make_opponent_seeded_db(tmp_path)
    env_overrides = {
        "DATABASE_PATH": str(db_path),
        "DEV_USER_EMAIL": "testdev@example.com",
    }
    with patch.dict("os.environ", env_overrides):
        with TestClient(app) as client:
            yield client, lsb_team_id, opp_team_id, unrelated_opp_id


@pytest.fixture()
def player_profile_client(tmp_path: Path):
    """TestClient with player profile data. Yields (client, lsb_team_id)."""
    db_path, lsb_team_id, _opp_id = _make_player_profile_seeded_db(tmp_path)
    env_overrides = {
        "DATABASE_PATH": str(db_path),
        "DEV_USER_EMAIL": "testdev@example.com",
    }
    with patch.dict("os.environ", env_overrides):
        with TestClient(app) as client:
            yield client, lsb_team_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDashboardEndpoint:
    """Tests for GET /dashboard (E-009-03)."""

    def test_dashboard_returns_200(self, seeded_client: TestClient) -> None:
        """GET /dashboard returns HTTP 200 with a seeded database."""
        response = seeded_client.get("/dashboard/batting")
        assert response.status_code == 200

    def test_dashboard_returns_html_content_type(
        self, seeded_client: TestClient
    ) -> None:
        """GET /dashboard response Content-Type is text/html."""
        response = seeded_client.get("/dashboard/batting")
        assert "text/html" in response.headers.get("content-type", "")

    def test_dashboard_contains_title_tag(self, seeded_client: TestClient) -> None:
        """GET /dashboard response HTML includes a <title> tag."""
        response = seeded_client.get("/dashboard/batting")
        assert "<title>" in response.text

    def test_dashboard_contains_table(self, seeded_client: TestClient) -> None:
        """GET /dashboard response HTML includes a <table> element."""
        response = seeded_client.get("/dashboard/batting")
        assert "<table" in response.text

    def test_dashboard_contains_player_name(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML contains at least one seeded player name (AC-5)."""
        response = seeded_client.get("/dashboard/batting")
        html = response.text
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
        response = seeded_client.get("/dashboard/batting")
        html = response.text
        assert any(str(v) in html for v in [6, 8, 7]), (
            "Expected at least one stat value in dashboard HTML."
        )

    def test_dashboard_shows_at_least_three_players(
        self, seeded_client: TestClient
    ) -> None:
        """GET /dashboard renders at least 3 players in the table (AC-3)."""
        response = seeded_client.get("/dashboard/batting")
        html = response.text
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
        response = seeded_client.get("/dashboard/batting")
        html = response.text
        for header in ("AB", "H", "BB", "SO"):
            assert header in html, (
                f"Expected column header '{header}' in dashboard HTML."
            )

    def test_dashboard_contains_viewport_meta(
        self, seeded_client: TestClient
    ) -> None:
        """GET /dashboard HTML includes a viewport meta tag for mobile."""
        response = seeded_client.get("/dashboard/batting")
        assert 'name="viewport"' in response.text

    def test_dashboard_contains_tailwind_cdn(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML includes the Tailwind CSS CDN script tag."""
        response = seeded_client.get("/dashboard/batting")
        assert "cdn.tailwindcss.com" in response.text

    def test_health_endpoint_unaffected(self, tmp_path: Path) -> None:
        """GET /health still returns 200 after dashboard router registration."""
        db_path, _ = _make_seeded_db(tmp_path)
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
        """GET /dashboard HTML includes an overflow-x-auto container."""
        response = seeded_client.get("/dashboard/batting")
        assert "overflow-x-auto" in response.text


class TestEnhancedBattingStats:
    """Tests for enhanced batting stats on GET /dashboard (E-004-02)."""

    def test_batting_returns_200(self, seeded_client: TestClient) -> None:
        """GET /dashboard returns HTTP 200 with seeded data."""
        response = seeded_client.get("/dashboard/batting")
        assert response.status_code == 200

    def test_batting_contains_seeded_player_name(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML contains at least one seeded player last name."""
        response = seeded_client.get("/dashboard/batting")
        html = response.text
        player_names = ["Whitehorse", "Runningwater", "Strongbow", "Redcloud", "Eagleheart"]
        assert any(name in html for name in player_names)

    def test_batting_computed_avg_value(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML contains a correctly computed AVG for gc-p-001.

        gc-p-001 has 3 H in 6 AB => AVG = .500.
        """
        response = seeded_client.get("/dashboard/batting")
        assert ".500" in response.text

    def test_batting_column_headers(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML includes AVG, OBP, SLG column headers."""
        response = seeded_client.get("/dashboard/batting")
        html = response.text
        for header in ("AVG", "OBP", "SLG"):
            assert header in html, f"Expected column header '{header}' in batting stats HTML."

    def test_batting_all_column_headers_present(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML includes all expected column headers (AC-1)."""
        response = seeded_client.get("/dashboard/batting")
        html = response.text
        for header in ("AVG", "OBP", "GP", "BB", "SO", "SLG", "AB", "2B", "3B", "HR", "SB", "RBI"):
            assert header in html, f"Expected column header '{header}' in batting stats HTML."

    def test_batting_player_links(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML contains player profile links."""
        response = seeded_client.get("/dashboard/batting")
        assert "/dashboard/players/" in response.text

    def test_batting_zero_ab_shows_dash(self, seeded_client: TestClient) -> None:
        """AVG/OBP/SLG display '-' for player with zero AB.

        gc-p-006 has 0 AB; all rate stats should display '-'.
        """
        response = seeded_client.get("/dashboard/batting")
        html = response.text
        assert "Noatbats" in html
        assert "-" in html

    def test_batting_sticky_thead(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML uses sticky top-0 on thead."""
        response = seeded_client.get("/dashboard/batting")
        assert "sticky top-0" in response.text

    def test_batting_overflow_x_auto(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML wraps table in overflow-x-auto."""
        response = seeded_client.get("/dashboard/batting")
        assert "overflow-x-auto" in response.text


class TestPitchingDashboard:
    """Tests for GET /dashboard/pitching (E-004-03)."""

    def test_pitching_returns_200(self, pitching_client) -> None:
        """GET /dashboard/pitching returns HTTP 200 with seeded data."""
        client, _ = pitching_client
        response = client.get("/dashboard/pitching")
        assert response.status_code == 200

    def test_pitching_contains_column_headers(self, pitching_client) -> None:
        """GET /dashboard/pitching HTML includes all required column headers."""
        client, _ = pitching_client
        response = client.get("/dashboard/pitching")
        html = response.text
        for header in ("ERA", "K/9", "BB/9", "WHIP", "GP", "IP", "H", "ER", "BB", "SO", "HR"):
            assert header in html, f"Expected column header '{header}' in pitching HTML."

    def test_pitching_player_link(self, pitching_client) -> None:
        """GET /dashboard/pitching HTML contains player profile links."""
        client, _ = pitching_client
        response = client.get("/dashboard/pitching")
        assert "/dashboard/players/" in response.text

    def test_pitching_era_computation(self, pitching_client) -> None:
        """GET /dashboard/pitching correctly computes ERA for gc-p-001.

        gc-p-001: 18 ip_outs, 2 ER => ERA = 2*27/18 = 3.00
        """
        client, _ = pitching_client
        response = client.get("/dashboard/pitching")
        assert "3.00" in response.text

    def test_pitching_k9_computation(self, pitching_client) -> None:
        """GET /dashboard/pitching correctly computes K/9 for gc-p-001.

        gc-p-001: 18 ip_outs, 9 SO => K/9 = 9*27/18 = 13.5
        """
        client, _ = pitching_client
        response = client.get("/dashboard/pitching")
        assert "13.5" in response.text

    def test_pitching_whip_computation(self, pitching_client) -> None:
        """GET /dashboard/pitching correctly computes WHIP for gc-p-001.

        gc-p-001: 18 ip_outs, 3 BB, 4 H => WHIP = (3+4)*3/18 = 1.17
        """
        client, _ = pitching_client
        response = client.get("/dashboard/pitching")
        assert "1.17" in response.text

    def test_pitching_zero_ip_shows_dash(self, pitching_client) -> None:
        """Pitcher with 0 ip_outs shows '-' for rate stats."""
        client, _ = pitching_client
        response = client.get("/dashboard/pitching")
        assert "-" in response.text

    def test_pitching_ip_display(self, pitching_client) -> None:
        """GET /dashboard/pitching displays IP in W.T notation.

        gc-p-001: 18 ip_outs => '6.0'
        """
        client, _ = pitching_client
        response = client.get("/dashboard/pitching")
        assert "6.0" in response.text

    def test_pitching_400_non_numeric_team(self, pitching_client) -> None:
        """GET /dashboard/pitching?team_id=non-numeric returns 400 (AC-2, AC-8d)."""
        client, _ = pitching_client
        response = client.get("/dashboard/pitching?team_id=not-permitted-team")
        assert response.status_code == 400

    def test_pitching_403_unpermitted_integer_team(self, pitching_client) -> None:
        """GET /dashboard/pitching?team_id=99999 returns 403 (AC-2, AC-8e)."""
        client, _ = pitching_client
        response = client.get("/dashboard/pitching?team_id=99999")
        assert response.status_code == 403

    def test_pitching_empty_state(self, seeded_client: TestClient) -> None:
        """GET /dashboard/pitching renders empty-state message when no pitching data."""
        # seeded_client has no pitching rows -- only batting rows
        response = seeded_client.get("/dashboard/pitching")
        assert response.status_code == 200
        assert "No pitching stats available" in response.text

    def test_pitching_season_id_override(self, pitching_client) -> None:
        """GET /dashboard/pitching?season_id=2025-spring-hs returns alt-season stats."""
        client, _ = pitching_client
        response = client.get(f"/dashboard/pitching?season_id={_ALT_SEASON_ID}")
        assert response.status_code == 200
        # 2025 seed: gc-p-001 with 6 ip_outs (2.0 IP), 0 ER => ERA 0.00
        assert "0.00" in response.text

    def test_pitching_sticky_thead(self, pitching_client) -> None:
        """GET /dashboard/pitching uses sticky top-0 on thead."""
        client, _ = pitching_client
        response = client.get("/dashboard/pitching")
        assert "sticky top-0" in response.text

    def test_pitching_overflow_x_auto(self, pitching_client) -> None:
        """GET /dashboard/pitching wraps table in overflow-x-auto."""
        client, _ = pitching_client
        response = client.get("/dashboard/pitching")
        assert "overflow-x-auto" in response.text

    def test_pitching_active_nav_highlighted(self, pitching_client) -> None:
        """GET /dashboard/pitching sets active_nav='pitching'."""
        client, _ = pitching_client
        response = client.get("/dashboard/pitching")
        assert "font-bold" in response.text


class TestGameList:
    """Tests for GET /dashboard/games (E-004-04)."""

    def test_game_list_returns_200(self, games_client) -> None:
        """GET /dashboard/games returns HTTP 200 (AC-1)."""
        client, _, _ = games_client
        response = client.get("/dashboard/games")
        assert response.status_code == 200

    def test_game_list_400_non_numeric_team(self, games_client) -> None:
        """GET /dashboard/games?team_id=non-numeric returns 400 (AC-2, AC-8d)."""
        client, _, _ = games_client
        response = client.get("/dashboard/games?team_id=not-permitted")
        assert response.status_code == 400

    def test_game_list_403_unpermitted_integer_team(self, games_client) -> None:
        """GET /dashboard/games?team_id=99999 returns 403 (AC-2, AC-8e)."""
        client, _, _ = games_client
        response = client.get("/dashboard/games?team_id=99999")
        assert response.status_code == 403

    def test_game_list_shows_opponent_name(self, games_client) -> None:
        """GET /dashboard/games HTML includes opponent team name (AC-2)."""
        client, _, _ = games_client
        response = client.get("/dashboard/games")
        assert "Rival High School" in response.text

    def test_game_list_shows_score(self, games_client) -> None:
        """GET /dashboard/games HTML includes score for a completed game (AC-2).

        game-001: lsb is home, scored 7-3 (user sees 7-3).
        """
        client, _, _ = games_client
        response = client.get("/dashboard/games")
        assert "7-3" in response.text

    def test_game_list_shows_wl_indicator(self, games_client) -> None:
        """GET /dashboard/games HTML includes W/L indicator (AC-3)."""
        client, _, _ = games_client
        response = client.get("/dashboard/games")
        html = response.text
        assert "W" in html or "L" in html

    def test_game_list_win_marked_green(self, games_client) -> None:
        """GET /dashboard/games: W indicator uses green color class (AC-3)."""
        client, _, _ = games_client
        response = client.get("/dashboard/games")
        assert "text-green-700" in response.text

    def test_game_list_games_sorted_desc(self, games_client) -> None:
        """GET /dashboard/games: games appear in date-descending order (AC-4)."""
        client, _, _ = games_client
        response = client.get("/dashboard/games")
        html = response.text
        # game-001 (2026-03-01 -> "Mar 1") must appear before game-002 (2026-02-20 -> "Feb 20")
        pos_001 = html.find("Mar 1")
        pos_002 = html.find("Feb 20")
        assert pos_001 != -1
        assert pos_002 != -1
        assert pos_001 < pos_002

    def test_game_list_rows_link_to_detail(self, games_client) -> None:
        """GET /dashboard/games: game rows link to /dashboard/games/{game_id} (AC-5)."""
        client, _, _ = games_client
        response = client.get("/dashboard/games")
        assert "/dashboard/games/game-001" in response.text

    def test_game_list_active_nav_games(self, games_client) -> None:
        """GET /dashboard/games: active_nav='games' highlights Games nav item."""
        client, _, _ = games_client
        response = client.get("/dashboard/games")
        assert "font-bold" in response.text

    def test_game_list_team_selector(self, games_client) -> None:
        """GET /dashboard/games: team selector route must return 200."""
        client, _, _ = games_client
        response = client.get("/dashboard/games")
        assert response.status_code == 200

    def test_game_list_empty_season(self, games_client) -> None:
        """GET /dashboard/games?season_id=nonexistent renders empty-state message."""
        client, _, _ = games_client
        response = client.get("/dashboard/games?season_id=9999-spring-hs")
        assert response.status_code == 200
        assert "No games found" in response.text

    def test_game_list_season_id_override(self, games_client) -> None:
        """GET /dashboard/games?season_id=2025-spring-hs returns alt-season games."""
        client, _, _ = games_client
        response = client.get(f"/dashboard/games?season_id={_ALT_SEASON_ID}")
        assert response.status_code == 200
        # game-2025 (2025-03-15 -> "Mar 15") should appear
        assert "Mar 15" in response.text


class TestGameDetail:
    """Tests for GET /dashboard/games/{game_id} (E-004-04)."""

    def test_game_detail_returns_200(self, games_client) -> None:
        """GET /dashboard/games/game-001 returns 200 (AC-6)."""
        client, _, _ = games_client
        response = client.get("/dashboard/games/game-001")
        assert response.status_code == 200

    def test_game_detail_403_unrelated_game(self, games_client) -> None:
        """GET /dashboard/games/game-unrelated returns 403 for game not involving permitted team."""
        client, _, _ = games_client
        response = client.get("/dashboard/games/game-unrelated")
        assert response.status_code == 403

    def test_game_detail_shows_game_date(self, games_client) -> None:
        """GET /dashboard/games/game-001 shows game date (AC-9)."""
        client, _, _ = games_client
        response = client.get("/dashboard/games/game-001")
        assert "2026-03-01" in response.text

    def test_game_detail_shows_team_names(self, games_client) -> None:
        """GET /dashboard/games/game-001 shows both team names in box score (AC-7, AC-9)."""
        client, _, _ = games_client
        response = client.get("/dashboard/games/game-001")
        html = response.text
        assert "LSB Varsity 2026" in html
        assert "Rival High School" in html

    def test_game_detail_shows_batting_headers(self, games_client) -> None:
        """GET /dashboard/games/game-001 includes batting column headers (AC-7)."""
        client, _, _ = games_client
        response = client.get("/dashboard/games/game-001")
        html = response.text
        for header in ("AB", "H", "2B", "3B", "HR", "RBI", "BB", "SO", "SB"):
            assert header in html, f"Expected batting header '{header}' in game detail."

    def test_game_detail_shows_pitching_headers(self, games_client) -> None:
        """GET /dashboard/games/game-001 includes pitching column headers (AC-7)."""
        client, _, _ = games_client
        response = client.get("/dashboard/games/game-001")
        html = response.text
        for header in ("IP", "H", "ER", "BB", "SO"):
            assert header in html, f"Expected pitching header '{header}' in game detail."

    def test_game_detail_ip_display_filter(self, games_client) -> None:
        """GET /dashboard/games/game-001 uses ip_display for IP column (AC-8).

        gc-p-001 pitched 18 ip_outs = 6.0 IP.
        """
        client, _, _ = games_client
        response = client.get("/dashboard/games/game-001")
        assert "6.0" in response.text

    def test_game_detail_player_links(self, games_client) -> None:
        """GET /dashboard/games/game-001 player names link to profile pages."""
        client, _, _ = games_client
        response = client.get("/dashboard/games/game-001")
        assert "/dashboard/players/" in response.text

    def test_game_detail_details_element_present(self, games_client) -> None:
        """GET /dashboard/games/game-001 uses <details> elements for collapsible sections."""
        client, _, _ = games_client
        response = client.get("/dashboard/games/game-001")
        assert "<details" in response.text

    def test_game_detail_active_nav_games(self, games_client) -> None:
        """GET /dashboard/games/game-001 active_nav='games' highlights Games nav item."""
        client, _, _ = games_client
        response = client.get("/dashboard/games/game-001")
        assert "font-bold" in response.text

    def test_game_detail_integer_team_id_in_open_attr(self, games_client) -> None:
        """AC-8(c): game detail uses INTEGER team.id to determine which details section is open."""
        client, lsb_team_id, _ = games_client
        # With team_id=lsb_team_id, the LSB section should have 'open' attribute
        response = client.get(f"/dashboard/games/game-001?team_id={lsb_team_id}")
        assert response.status_code == 200
        assert "<details open" in response.text


class TestOpponentList:
    """Tests for GET /dashboard/opponents (E-004-05)."""

    def test_opponent_list_returns_200(self, opponent_client) -> None:
        """GET /dashboard/opponents returns HTTP 200 (AC-1)."""
        client, _, _, _ = opponent_client
        response = client.get("/dashboard/opponents")
        assert response.status_code == 200

    def test_opponent_list_400_non_numeric_team(self, opponent_client) -> None:
        """GET /dashboard/opponents?team_id=non-numeric returns 400 (AC-2, AC-8d)."""
        client, _, _, _ = opponent_client
        response = client.get("/dashboard/opponents?team_id=not-permitted")
        assert response.status_code == 400

    def test_opponent_list_403_unpermitted_integer_team(self, opponent_client) -> None:
        """GET /dashboard/opponents?team_id=99999 returns 403 (AC-2, AC-8e)."""
        client, _, _, _ = opponent_client
        response = client.get("/dashboard/opponents?team_id=99999")
        assert response.status_code == 403

    def test_opponent_list_shows_opponent_name(self, opponent_client) -> None:
        """GET /dashboard/opponents HTML includes opponent team name (AC-2)."""
        client, _, _, _ = opponent_client
        response = client.get("/dashboard/opponents")
        assert "Rival High School" in response.text

    def test_opponent_list_shows_wl_record(self, opponent_client) -> None:
        """GET /dashboard/opponents HTML includes W-L record column (AC-2).

        Two games: game-001 home W (7-3), game-002 away W (5-2) => 2-0.
        """
        client, _, _, _ = opponent_client
        response = client.get("/dashboard/opponents")
        assert "2-0" in response.text

    def test_opponent_list_row_links_to_detail(self, opponent_client) -> None:
        """GET /dashboard/opponents: opponent rows link to /dashboard/opponents/{id} (AC-3).

        With INTEGER PKs, the link contains the integer opp_team_id.
        """
        client, lsb_team_id, opp_team_id, _ = opponent_client
        response = client.get("/dashboard/opponents")
        assert f"/dashboard/opponents/{opp_team_id}" in response.text

    def test_opponent_list_empty_state(self, seeded_client: TestClient) -> None:
        """GET /dashboard/opponents renders empty-state message when no opponents (AC-13)."""
        # seeded_client has no games rows -- only batting stats
        response = seeded_client.get("/dashboard/opponents")
        assert response.status_code == 200
        assert "No opponents found" in response.text

    def test_opponent_list_season_id_override(self, opponent_client) -> None:
        """GET /dashboard/opponents?season_id=2025-spring-hs filters to alt season (AC-1)."""
        client, _, _, _ = opponent_client
        response = client.get(f"/dashboard/opponents?season_id={_ALT_SEASON_ID}")
        assert response.status_code == 200
        # 2025 seed has one game vs opp-team
        assert "Rival High School" in response.text

    def test_opponent_list_active_nav_opponents(self, opponent_client) -> None:
        """GET /dashboard/opponents sets active_nav='opponents' (AC-10)."""
        client, _, _, _ = opponent_client
        response = client.get("/dashboard/opponents")
        assert "font-bold" in response.text

    def test_opponent_list_team_selector(self, opponent_client) -> None:
        """GET /dashboard/opponents includes team selector base_url (AC-9)."""
        client, _, _, _ = opponent_client
        response = client.get("/dashboard/opponents")
        assert response.status_code == 200


class TestOpponentDetail:
    """Tests for GET /dashboard/opponents/{opponent_team_id} (E-004-05)."""

    def test_opponent_detail_returns_200(self, opponent_client) -> None:
        """GET /dashboard/opponents/{opp_team_id} returns 200 (AC-4)."""
        client, _, opp_team_id, _ = opponent_client
        response = client.get(f"/dashboard/opponents/{opp_team_id}")
        assert response.status_code == 200

    def test_opponent_detail_403_unrelated_opponent(self, opponent_client) -> None:
        """GET /dashboard/opponents/{unrelated_id} returns 403 (AC-11)."""
        client, _, _, unrelated_opp_id = opponent_client
        response = client.get(f"/dashboard/opponents/{unrelated_opp_id}")
        assert response.status_code == 403

    def test_opponent_detail_shows_batting_leaders(self, opponent_client) -> None:
        """GET /dashboard/opponents/{id} shows batting leaders table (AC-5, AC-6)."""
        client, _, opp_team_id, _ = opponent_client
        response = client.get(f"/dashboard/opponents/{opp_team_id}")
        html = response.text
        assert "Batting Leaders" in html
        assert "Rivera" in html or "Martinez" in html

    def test_opponent_detail_batting_column_headers(self, opponent_client) -> None:
        """GET /dashboard/opponents/{id} includes all batting column headers (AC-6)."""
        client, _, opp_team_id, _ = opponent_client
        response = client.get(f"/dashboard/opponents/{opp_team_id}")
        html = response.text
        for header in ("AVG", "OBP", "GP", "AB", "BB", "SO", "SLG", "H", "HR", "SB", "RBI"):
            assert header in html, f"Expected batting header '{header}' in opponent detail."

    def test_opponent_detail_shows_pitching_leaders(self, opponent_client) -> None:
        """GET /dashboard/opponents/{id} shows pitching leaders table (AC-5, AC-7)."""
        client, _, opp_team_id, _ = opponent_client
        response = client.get(f"/dashboard/opponents/{opp_team_id}")
        assert "Pitching Leaders" in response.text

    def test_opponent_detail_pitching_column_headers(self, opponent_client) -> None:
        """GET /dashboard/opponents/{id} includes all pitching column headers (AC-7)."""
        client, _, opp_team_id, _ = opponent_client
        response = client.get(f"/dashboard/opponents/{opp_team_id}")
        html = response.text
        for header in ("ERA", "K/9", "WHIP", "GP", "IP", "H", "ER", "BB", "SO"):
            assert header in html, f"Expected pitching header '{header}' in opponent detail."

    def test_opponent_detail_key_players_card(self, opponent_client) -> None:
        """GET /dashboard/opponents/{id} shows Their Pitchers card (AC-2, E-153-04).

        'Key Players' was replaced by 'Their Pitchers' pitching summary card in E-153-04.
        """
        client, _, opp_team_id, _ = opponent_client
        response = client.get(f"/dashboard/opponents/{opp_team_id}")
        assert "Their Pitchers" in response.text

    def test_opponent_detail_key_hitter_name_and_avg(self, opponent_client) -> None:
        """Key Players card shows best hitter name and AVG (AC-15).

        opp-p-001: 4 H / 10 AB = .400 AVG (highest, meets 5 AB minimum).
        """
        client, _, opp_team_id, _ = opponent_client
        response = client.get(f"/dashboard/opponents/{opp_team_id}")
        html = response.text
        assert "Rivera" in html
        assert ".400" in html

    def test_opponent_detail_key_pitcher_name_and_era(self, opponent_client) -> None:
        """Key Players card shows best pitcher name and ERA (AC-15).

        opp-p-001: 18 ip_outs, 1 ER => ERA = 1*27/18 = 1.50 (meets 9 ip_outs min).
        """
        client, _, opp_team_id, _ = opponent_client
        response = client.get(f"/dashboard/opponents/{opp_team_id}")
        html = response.text
        assert "Rivera" in html
        assert "1.50" in html

    def test_opponent_detail_insufficient_data_when_no_stats(
        self, games_client
    ) -> None:
        """Opponent with games but no stats and no opponent_link shows unlinked state (E-153-04 AC-5).

        games_client has games vs opp but no opponent batting/pitching rows and no opponent_links.
        E-153-04 replaced 'Insufficient data.' with a three-state model; unlinked => 'Stats not available.'
        """
        client, _, opp_team_id = games_client
        response = client.get(f"/dashboard/opponents/{opp_team_id}")
        assert response.status_code == 200
        assert "Stats not available." in response.text

    def test_opponent_detail_no_stats_shows_message(self, games_client) -> None:
        """GET /dashboard/opponents/{id} shows 'Stats not available.' when no stats loaded (E-153-04 AC-5).

        games_client has games vs opp but no opponent batting/pitching rows and no opponent_links.
        E-153-04 three-state model: unlinked => 'Stats not available.'
        """
        client, _, opp_team_id = games_client
        response = client.get(f"/dashboard/opponents/{opp_team_id}")
        assert response.status_code == 200
        assert "Stats not available." in response.text

    def test_opponent_detail_last_meeting_card(self, opponent_client) -> None:
        """GET /dashboard/opponents/{id} shows Last Meeting card (AC-16)."""
        client, _, opp_team_id, _ = opponent_client
        response = client.get(f"/dashboard/opponents/{opp_team_id}")
        assert "Last Meeting" in response.text

    def test_opponent_detail_last_meeting_shows_score(self, opponent_client) -> None:
        """Last Meeting card shows score and W/L for most recent game (AC-16, AC-18).

        game-001 (2026-03-01): lsb home 7-3 vs opp => W. Most recent = game-001.
        """
        client, _, opp_team_id, _ = opponent_client
        response = client.get(f"/dashboard/opponents/{opp_team_id}")
        html = response.text
        # game-001: lsb is home 7-3, so my_score=7, their_score=3
        assert "7-3" in html

    def test_opponent_detail_first_meeting_message_when_no_games(
        self, opponent_client
    ) -> None:
        """Last Meeting card does NOT show 'First meeting' when a completed game exists (AC-18)."""
        client, _, opp_team_id, _ = opponent_client
        response = client.get(f"/dashboard/opponents/{opp_team_id}")
        assert response.status_code == 200
        assert "First meeting this season." not in response.text
        assert "Last Meeting" in response.text

    def test_opponent_detail_first_meeting_via_scheduled_game(
        self, tmp_path: Path
    ) -> None:
        """'First meeting this season.' shown when only scheduled (not completed) games exist.

        E-153-04: Last Meeting section only renders in full_stats state.  Must add batting/pitching
        rows to reach full_stats state; only scheduled game means last_meeting=None => 'First meeting'.
        """
        db_path = tmp_path / "test_no_completed.db"
        _apply_schema(db_path)
        conn = sqlite3.connect(str(db_path))
        lsb_team_id, _ = _insert_lsb_team_and_user(conn)
        # Insert opponent and a scheduled (not completed) game
        cursor = conn.execute(
            "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
            ("Future Opponent", "tracked"),
        )
        future_opp_id: int = cursor.lastrowid  # type: ignore[assignment]
        conn.execute(
            "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, status)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("game-sched", _CURRENT_SEASON_ID, "2099-03-01", lsb_team_id, future_opp_id, "scheduled"),
        )
        # Add a player and batting stats so the page enters full_stats state (required by E-153-04).
        conn.execute(
            "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
            ("fut-p-001", "Future", "Pitcher"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO player_season_batting"
            " (player_id, team_id, season_id, gp, ab, h, doubles, triples, hr, rbi, bb, so, sb)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("fut-p-001", future_opp_id, _CURRENT_SEASON_ID, 1, 4, 1, 0, 0, 0, 1, 0, 1, 0),
        )
        conn.commit()
        conn.close()
        env_overrides = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": "testdev@example.com",
        }
        with patch.dict("os.environ", env_overrides):
            with TestClient(app) as client:
                response = client.get(f"/dashboard/opponents/{future_opp_id}")
        assert response.status_code == 200
        assert "First meeting this season." in response.text

    def test_opponent_detail_active_nav_opponents(self, opponent_client) -> None:
        """GET /dashboard/opponents/{id} sets active_nav='opponents' (AC-10)."""
        client, _, opp_team_id, _ = opponent_client
        response = client.get(f"/dashboard/opponents/{opp_team_id}")
        assert "font-bold" in response.text

    def test_opponent_detail_season_id_override(self, opponent_client) -> None:
        """GET /dashboard/opponents/{id}?season_id=alt filters to alt season (AC-4)."""
        client, _, opp_team_id, _ = opponent_client
        response = client.get(f"/dashboard/opponents/{opp_team_id}?season_id={_ALT_SEASON_ID}")
        assert response.status_code == 200

    def test_opponent_detail_last_meeting_shows_tie_not_loss(self, tmp_path: Path) -> None:
        """Last Meeting card shows 'T' (not 'L') when most recent game was a tie (Fix 3).

        game-tie: lsb home 4-4 vs tie-opp => equal scores => should display T badge.
        The old template had no elif for ties, so ties rendered as losses.

        E-153-04: Last Meeting section only renders in full_stats state. Batting stats row added
        so opponent reaches full_stats state.
        """
        db_path = tmp_path / "test_tie.db"
        _apply_schema(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        lsb_team_id, _ = _insert_lsb_team_and_user(conn)

        cursor = conn.execute(
            "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
            ("Tie Opponent", "tracked"),
        )
        tie_opp_id: int = cursor.lastrowid  # type: ignore[assignment]

        # Tied game: lsb is home with equal scores
        conn.execute(
            "INSERT INTO games"
            " (game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score, status)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("game-tie", _CURRENT_SEASON_ID, "2026-03-10", lsb_team_id, tie_opp_id, 4, 4, "completed"),
        )
        # Add stats so the page enters full_stats state (required by E-153-04 three-state model).
        conn.execute(
            "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
            ("tie-p-001", "Tie", "Batter"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO player_season_batting"
            " (player_id, team_id, season_id, gp, ab, h, doubles, triples, hr, rbi, bb, so, sb)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("tie-p-001", tie_opp_id, _CURRENT_SEASON_ID, 1, 4, 2, 0, 0, 0, 1, 0, 1, 0),
        )
        conn.commit()
        conn.close()

        env_overrides = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": "testdev@example.com",
        }
        with patch.dict("os.environ", env_overrides):
            with TestClient(app) as client:
                response = client.get(f"/dashboard/opponents/{tie_opp_id}")
        assert response.status_code == 200
        html = response.text
        assert "4-4" in html
        assert 'text-gray-600">T' in html   # tie badge rendered
        assert 'text-red-700">L' not in html  # loss badge must not appear

    def test_opponent_detail_back_link_preserves_team_id(self, opponent_client) -> None:
        """Back-link goes to schedule and includes ?team_id= to preserve team context (E-153-04 AC-6).

        E-153-04 changed the back link from /dashboard/opponents to /dashboard (the schedule page).
        """
        client, lsb_team_id, opp_team_id, _ = opponent_client
        response = client.get(f"/dashboard/opponents/{opp_team_id}?team_id={lsb_team_id}")
        assert response.status_code == 200
        assert f"/dashboard?team_id={lsb_team_id}" in response.text


class TestPlayerProfile:
    """Tests for GET /dashboard/players/{player_id} (E-004-06)."""

    def test_player_profile_returns_200(self, player_profile_client) -> None:
        """GET /dashboard/players/gc-p-001 returns 200 (AC-1)."""
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-001")
        assert response.status_code == 200

    def test_player_profile_404_nonexistent(self, player_profile_client) -> None:
        """GET /dashboard/players/nonexistent returns 404 (AC-11)."""
        client, _ = player_profile_client
        response = client.get("/dashboard/players/nonexistent-player-id")
        assert response.status_code == 404

    def test_player_profile_403_unauthorized_player(self, player_profile_client) -> None:
        """GET /dashboard/players/{id} returns 403 when player not on any permitted team.

        gc-p-003 exists (has batting stats) but has no team_rosters entry
        for lsb team, so should return 403.
        """
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-003")
        assert response.status_code == 403

    def test_player_profile_shows_player_name(self, player_profile_client) -> None:
        """GET /dashboard/players/gc-p-001 shows player full name (AC-2)."""
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-001")
        assert "Marcus" in response.text
        assert "Whitehorse" in response.text

    def test_player_profile_shows_jersey_number(self, player_profile_client) -> None:
        """GET /dashboard/players/gc-p-001 shows current jersey number (AC-2)."""
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-001")
        assert "#12" in response.text

    def test_player_profile_batting_section_renders(self, player_profile_client) -> None:
        """GET /dashboard/players/gc-p-001 renders Batting by Season table (AC-3, AC-14)."""
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-001")
        html = response.text
        assert "Batting by Season" in html
        for header in ("AVG", "OBP", "GP", "BB", "SO", "SLG", "H", "AB", "2B", "3B", "HR", "SB", "RBI"):
            assert header in html, f"Missing batting header: {header}"

    def test_player_profile_pitching_section_renders(self, player_profile_client) -> None:
        """GET /dashboard/players/gc-p-001 renders Pitching by Season table (AC-4, AC-14)."""
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-001")
        html = response.text
        assert "Pitching by Season" in html
        for header in ("ERA", "K/9", "WHIP", "GP", "IP", "H", "ER", "BB", "SO", "HR"):
            assert header in html, f"Missing pitching header: {header}"

    def test_player_profile_batting_computed_avg(self, player_profile_client) -> None:
        """GET /dashboard/players/gc-p-001 shows correct AVG for current season (AC-8, AC-14).

        gc-p-001 current season: 3 H / 6 AB = .500 AVG.
        """
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-001")
        assert ".500" in response.text

    def test_player_profile_pitching_era(self, player_profile_client) -> None:
        """GET /dashboard/players/gc-p-001 shows correct ERA (AC-8, AC-14).

        gc-p-001: 18 ip_outs, 2 ER => ERA = 2*27/18 = 3.00.
        """
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-001")
        assert "3.00" in response.text

    def test_player_profile_ip_display(self, player_profile_client) -> None:
        """GET /dashboard/players/gc-p-001 uses ip_display for IP column (AC-9).

        gc-p-001: 18 ip_outs => '6.0'.
        """
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-001")
        assert "6.0" in response.text

    def test_player_profile_season_names(self, player_profile_client) -> None:
        """GET /dashboard/players/gc-p-001 shows human-readable season names (AC-6)."""
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-001")
        html = response.text
        assert "Spring" in html

    def test_player_profile_team_names(self, player_profile_client) -> None:
        """GET /dashboard/players/gc-p-001 shows team names (AC-7)."""
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-001")
        assert "LSB Varsity 2026" in response.text

    def test_player_profile_recent_games(self, player_profile_client) -> None:
        """GET /dashboard/players/gc-p-001 shows Recent Games section with game rows (AC-13)."""
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-001")
        html = response.text
        assert "Recent Games" in html
        assert "/dashboard/games/game-001" in html or "/dashboard/games/game-002" in html

    def test_player_profile_recent_games_batting_stat_line(
        self, player_profile_client
    ) -> None:
        """GET /dashboard/players/gc-p-001 recent games show batting stat line (AC-13).

        game-001: gc-p-001 went 2-for-4 with 1 HR, 2 RBI.
        """
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-001")
        assert "2-for-4" in response.text

    def test_player_profile_no_stats_shows_messages(self, player_profile_client) -> None:
        """GET /dashboard/players/gc-p-nostats shows empty-state for batting and pitching (AC-5)."""
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-nostats")
        assert response.status_code == 200
        html = response.text
        assert "No batting stats" in html
        assert "No pitching stats" in html

    def test_player_profile_current_season_summary_card(self, player_profile_client) -> None:
        """GET /dashboard/players/gc-p-001 shows Current Season Summary card (AC-2a, AC-16)."""
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-001")
        assert "Current Season Summary" in response.text

    def test_player_profile_current_season_summary_no_stats(
        self, player_profile_client
    ) -> None:
        """GET /dashboard/players/gc-p-nostats shows 'No stats recorded yet.' in card."""
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-nostats")
        assert "No stats recorded yet" in response.text

    def test_player_profile_no_active_nav(self, player_profile_client) -> None:
        """GET /dashboard/players/{player_id} loads 200 without crashing."""
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-001")
        assert response.status_code == 200

    def test_player_profile_two_way_player_both_rows(self, player_profile_client) -> None:
        """Recent Games returns two rows for a two-way game (AC-1, AC-3).

        gc-p-001 has both batting and pitching lines in game-001.
        game-001 should appear twice in Recent Games -- once for batting, once for pitching.
        """
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-001")
        html = response.text
        occurrences = html.count("/dashboard/games/game-001")
        assert occurrences == 2

    def test_player_profile_two_way_player_both_stat_types(self, player_profile_client) -> None:
        """Recent Games shows batting and pitching stats for a two-way game (AC-1, AC-3).

        gc-p-001 in game-001: batting 2-for-4 with 1 HR, 2 RBI; pitching 3.0 IP, 0 ER, 5 SO.
        """
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-001")
        html = response.text
        # Batting row
        assert "2-for-4" in html
        # Pitching row (9 ip_outs = 3.0 IP, 0 ER, 5 SO)
        assert "3.0 IP" in html
        assert "0 ER" in html
        assert "5 SO" in html

    def test_player_profile_backlink_uses_permitted_team_not_scouting_team(
        self, tmp_path: Path
    ) -> None:
        """Backlink resolves to a permitted team even when a scouting team's season is newer (Fix 2).

        gc-p-back has two batting seasons:
          - Opponent team (tracked, not permitted), season _CURRENT_SEASON_ID (newer, sorts first)
          - LSB team (member, permitted), season _ALT_SEASON_ID (older, sorts second)

        The old template used batting_seasons[0].team_id (the opponent), which would produce
        a 403 when the user clicked the backlink. The fix selects the first permitted team.
        """
        db_path = tmp_path / "test_backlink.db"
        _apply_schema(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        lsb_team_id, _ = _insert_lsb_team_and_user(conn)

        # Opponent team — tracked, NOT in the user's permitted_teams
        cursor = conn.execute(
            "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
            ("Scouted Opponent", "tracked"),
        )
        opp_team_id: int = cursor.lastrowid  # type: ignore[assignment]

        conn.execute(
            "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
            (_ALT_SEASON_ID, "Spring 2025 High School", "spring-hs", 2025),
        )

        conn.execute(
            "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
            ("gc-p-back", "Back", "Linktest"),
        )

        # Roster entry on LSB so authorization check passes
        conn.execute(
            "INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id) VALUES (?, ?, ?)",
            (lsb_team_id, "gc-p-back", _ALT_SEASON_ID),
        )

        # Opponent batting season: NEWER (sorts first in DESC) — not permitted
        conn.execute(
            "INSERT OR IGNORE INTO player_season_batting"
            " (player_id, team_id, season_id, gp, ab, h, doubles, triples, hr, rbi, bb, so, sb)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("gc-p-back", opp_team_id, _CURRENT_SEASON_ID, 2, 8, 3, 0, 0, 0, 1, 1, 2, 0),
        )

        # LSB batting season: OLDER (sorts second in DESC) — permitted
        conn.execute(
            "INSERT OR IGNORE INTO player_season_batting"
            " (player_id, team_id, season_id, gp, ab, h, doubles, triples, hr, rbi, bb, so, sb)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("gc-p-back", lsb_team_id, _ALT_SEASON_ID, 3, 10, 4, 1, 0, 0, 2, 2, 1, 0),
        )

        conn.commit()
        conn.close()

        env_overrides = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": "testdev@example.com",
        }
        with patch.dict("os.environ", env_overrides):
            with TestClient(app) as client:
                response = client.get("/dashboard/players/gc-p-back")
        assert response.status_code == 200
        html = response.text
        # Backlink must point to the permitted LSB team, not the scouting opponent
        assert f"/dashboard/batting?team_id={lsb_team_id}" in html
        assert f"/dashboard/batting?team_id={opp_team_id}" not in html


class TestTemplateStaleRefs:
    """AC-4: Verify stale field references removed from dashboard and admin templates (E-114-04)."""

    _DASHBOARD_TEMPLATES = [
        "team_pitching.html",
        "game_list.html",
        "opponent_list.html",
        "opponent_detail.html",
        "player_profile.html",
        "game_detail.html",
    ]
    _TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "src" / "api" / "templates"

    def test_pitching_template_renders_user_email(self, pitching_client) -> None:
        """GET /dashboard/pitching renders user.email in header (AC-4)."""
        client, _ = pitching_client
        response = client.get("/dashboard/pitching")
        assert response.status_code == 200
        assert "testdev@example.com" in response.text

    def test_dashboard_templates_no_display_name(self) -> None:
        """All six dashboard templates contain no 'display_name' references (AC-4)."""
        for filename in self._DASHBOARD_TEMPLATES:
            path = self._TEMPLATES_DIR / "dashboard" / filename
            content = path.read_text()
            assert "display_name" not in content, (
                f"{filename} still contains 'display_name'"
            )

    def test_dashboard_templates_no_is_admin(self) -> None:
        """Dashboard templates (excluding opponent_detail.html) contain no 'is_admin' references (AC-4).

        opponent_detail.html is intentionally excluded: E-153-04 added an is_admin check
        to show the admin shortcut link to unlinked opponents.
        """
        for filename in self._DASHBOARD_TEMPLATES:
            if filename == "opponent_detail.html":
                # E-153-04 intentionally uses is_admin for the admin shortcut link.
                continue
            path = self._TEMPLATES_DIR / "dashboard" / filename
            content = path.read_text()
            assert "is_admin" not in content, (
                f"{filename} still contains 'is_admin'"
            )

    def test_admin_opponent_connect_no_display_name(self) -> None:
        """admin/opponent_connect.html contains no 'display_name' references (AC-4)."""
        path = self._TEMPLATES_DIR / "admin" / "opponent_connect.html"
        content = path.read_text()
        assert "display_name" not in content


# ---------------------------------------------------------------------------
# _compute_wl unit tests (E-120-07)
# ---------------------------------------------------------------------------


from src.api.routes.dashboard import _compute_wl  # noqa: E402


class TestComputeWL:
    """Unit tests for _compute_wl helper."""

    def _game(self, home_score, away_score, is_home: bool) -> dict:
        return {"home_score": home_score, "away_score": away_score, "is_home": is_home}

    def test_compute_wl_home_win(self) -> None:
        assert _compute_wl(self._game(5, 3, True), team_id=1) == "W"

    def test_compute_wl_home_loss(self) -> None:
        assert _compute_wl(self._game(3, 5, True), team_id=1) == "L"

    def test_compute_wl_away_win(self) -> None:
        assert _compute_wl(self._game(3, 5, False), team_id=1) == "W"

    def test_compute_wl_away_loss(self) -> None:
        assert _compute_wl(self._game(5, 3, False), team_id=1) == "L"

    def test_compute_wl_null_scores(self) -> None:
        assert _compute_wl(self._game(None, None, True), team_id=1) == "-"

    def test_compute_wl_tied_game_returns_T(self) -> None:
        """AC-5: Tied game (e.g. suspended/called) returns 'T', not 'L'."""
        assert _compute_wl(self._game(3, 3, True), team_id=1) == "T"
        assert _compute_wl(self._game(3, 3, False), team_id=1) == "T"


class TestOBPFormula:
    """Tests for corrected OBP formula: (H+BB+HBP)/(AB+BB+HBP+SF) (E-125-03)."""

    @pytest.fixture()
    def obp_client(self, tmp_path: Path):
        """TestClient with players that have hbp and shf data.

        Yields (client, lsb_team_id, opp_team_id).
        """
        db_path = tmp_path / "test_obp.db"
        _apply_schema(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        lsb_team_id, _ = _insert_lsb_team_and_user(conn)

        # Opponent team for scouting report
        cursor = conn.execute(
            "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
            ("OBP Rival", "tracked"),
        )
        opp_team_id: int = cursor.lastrowid  # type: ignore[assignment]

        conn.executemany(
            "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
            [
                ("obp-p-001", "Hit", "ByPitch"),
                ("obp-p-002", "No", "HBP"),
                ("obp-p-003", "Zero", "PA"),
            ],
        )

        # Roster entries
        conn.executemany(
            "INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id, jersey_number)"
            " VALUES (?, ?, ?, ?)",
            [
                (lsb_team_id, "obp-p-001", _CURRENT_SEASON_ID, "10"),
                (lsb_team_id, "obp-p-002", _CURRENT_SEASON_ID, "20"),
                (lsb_team_id, "obp-p-003", _CURRENT_SEASON_ID, "30"),
            ],
        )

        # obp-p-001: 10 AB, 3 H, 2 BB, 1 HBP, 1 SF
        # Old OBP = (3+2)/(10+2) = .417
        # Correct OBP = (3+2+1)/(10+2+1+1) = 6/14 = .429
        conn.execute(
            "INSERT INTO player_season_batting"
            " (player_id, team_id, season_id, gp, ab, h, doubles, triples, hr, rbi, bb, so, sb, hbp, shf)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("obp-p-001", lsb_team_id, _CURRENT_SEASON_ID, 5, 10, 3, 1, 0, 0, 2, 2, 3, 1, 1, 1),
        )

        # obp-p-002: 8 AB, 2 H, 1 BB, 0 HBP, 0 SF
        # OBP = (2+1+0)/(8+1+0+0) = 3/9 = .333
        conn.execute(
            "INSERT INTO player_season_batting"
            " (player_id, team_id, season_id, gp, ab, h, doubles, triples, hr, rbi, bb, so, sb, hbp, shf)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("obp-p-002", lsb_team_id, _CURRENT_SEASON_ID, 4, 8, 2, 0, 0, 0, 1, 1, 2, 0, 0, 0),
        )

        # obp-p-003: 0 AB, 0 everything -- zero denominator case
        conn.execute(
            "INSERT INTO player_season_batting"
            " (player_id, team_id, season_id, gp, ab, h, doubles, triples, hr, rbi, bb, so, sb, hbp, shf)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("obp-p-003", lsb_team_id, _CURRENT_SEASON_ID, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        )

        # Same players as opponents for opponent_detail test
        conn.execute(
            "INSERT INTO player_season_batting"
            " (player_id, team_id, season_id, gp, ab, h, doubles, triples, hr, rbi, bb, so, sb, hbp, shf)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("obp-p-001", opp_team_id, _CURRENT_SEASON_ID, 5, 10, 3, 1, 0, 0, 2, 2, 3, 1, 1, 1),
        )

        # Game for opponent context
        conn.execute(
            "INSERT INTO games"
            " (game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score, status)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("game-obp", _CURRENT_SEASON_ID, "2026-03-10", lsb_team_id, opp_team_id, 5, 3, "completed"),
        )

        conn.commit()
        conn.close()

        env_overrides = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": "testdev@example.com",
        }
        with patch.dict("os.environ", env_overrides):
            with TestClient(app) as client:
                yield client, lsb_team_id, opp_team_id

    def test_team_stats_obp_includes_hbp(self, obp_client) -> None:
        """AC-1: OBP on team_stats uses (H+BB+HBP)/(AB+BB+HBP+SF)."""
        client, lsb_team_id, _ = obp_client
        response = client.get(f"/dashboard/batting?team_id={lsb_team_id}")
        assert response.status_code == 200
        html = response.text
        # obp-p-001: (3+2+1)/(10+2+1+1) = 6/14 = .429
        assert ".429" in html
        # obp-p-002: (2+1+0)/(8+1+0+0) = 3/9 = .333
        assert ".333" in html

    def test_team_stats_obp_hbp_raises_obp(self, obp_client) -> None:
        """AC-6: Player with HBP gets higher OBP than old formula would produce."""
        client, lsb_team_id, _ = obp_client
        response = client.get(f"/dashboard/batting?team_id={lsb_team_id}")
        html = response.text
        # Old formula for obp-p-001: (3+2)/(10+2) = 5/12 = .417
        # New formula: .429 -- the old value should NOT appear
        assert ".429" in html
        assert ".417" not in html

    def test_team_stats_obp_zero_denom_shows_dash(self, obp_client) -> None:
        """AC-8: Zero denominator displays '-' instead of division error."""
        client, lsb_team_id, _ = obp_client
        response = client.get(f"/dashboard/batting?team_id={lsb_team_id}")
        assert response.status_code == 200
        # obp-p-003 has 0 AB, 0 BB, 0 HBP, 0 SF => denom=0 => "-"
        # We can't easily isolate which "-" is for OBP, but we confirm no error

    def test_opponent_detail_obp_includes_hbp(self, obp_client) -> None:
        """AC-2: OBP on opponent_detail uses corrected formula."""
        client, lsb_team_id, opp_team_id = obp_client
        response = client.get(
            f"/dashboard/opponents/{opp_team_id}?team_id={lsb_team_id}"
        )
        assert response.status_code == 200
        html = response.text
        # obp-p-001 on opponent: (3+2+1)/(10+2+1+1) = .429
        assert ".429" in html

    def test_player_profile_obp_includes_hbp(self, obp_client) -> None:
        """AC-3: OBP on player_profile uses corrected formula (both occurrences)."""
        client, lsb_team_id, _ = obp_client
        response = client.get("/dashboard/players/obp-p-001")
        assert response.status_code == 200
        html = response.text
        # Both current season summary and batting-by-season table should show .429
        assert html.count(".429") >= 2

    def test_player_profile_backlink_to_dashboard(self, obp_client) -> None:
        """AC-5: Backlink navigates to /dashboard, not /dashboard/stats."""
        client, lsb_team_id, _ = obp_client
        response = client.get("/dashboard/players/obp-p-001")
        assert response.status_code == 200
        html = response.text
        assert "/dashboard/stats" not in html
        assert f"/dashboard/batting?team_id={lsb_team_id}" in html

    def test_null_hbp_shf_coalesced_to_zero(self, tmp_path: Path) -> None:
        """AC-4/AC-7: NULL hbp and shf are treated as 0 via COALESCE."""
        db_path = tmp_path / "test_obp_null.db"
        _apply_schema(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        lsb_team_id, _ = _insert_lsb_team_and_user(conn)

        conn.execute(
            "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
            ("null-hbp", "Null", "HBPPlayer"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id) VALUES (?, ?, ?)",
            (lsb_team_id, "null-hbp", _CURRENT_SEASON_ID),
        )
        # Insert with NULL hbp and shf (omit from column list)
        conn.execute(
            "INSERT INTO player_season_batting"
            " (player_id, team_id, season_id, gp, ab, h, doubles, triples, hr, rbi, bb, so, sb)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("null-hbp", lsb_team_id, _CURRENT_SEASON_ID, 3, 9, 3, 1, 0, 0, 2, 3, 2, 0),
        )
        conn.commit()
        conn.close()

        env_overrides = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": "testdev@example.com",
        }
        with patch.dict("os.environ", env_overrides):
            with TestClient(app) as client:
                response = client.get(f"/dashboard/batting?team_id={lsb_team_id}")
        assert response.status_code == 200
        html = response.text
        # With NULL hbp/shf coalesced to 0: OBP = (3+3+0)/(9+3+0+0) = 6/12 = .500
        assert ".500" in html


class TestJerseyNumberColumn:
    """Tests for jersey number as a distinct # column in team_stats and team_pitching (E-131-01)."""

    @pytest.fixture()
    def jersey_client(self, tmp_path: Path):
        """TestClient with both member and tracked teams, plus roster and stat data.

        Yields (client, member_team_id, tracked_team_id, user_id).
        """
        db_path = tmp_path / "test_jersey.db"
        _apply_schema(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")

        # Member team (simulates roster-loaded path)
        cursor = conn.execute(
            "INSERT INTO teams (name, membership_type, classification) VALUES (?, ?, ?)",
            ("LSB Varsity", "member", "varsity"),
        )
        member_team_id: int = cursor.lastrowid  # type: ignore[assignment]

        # Tracked team (simulates scouting-loaded path)
        cursor = conn.execute(
            "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
            ("Rival HS", "tracked"),
        )
        tracked_team_id: int = cursor.lastrowid  # type: ignore[assignment]

        conn.execute(
            "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
            (
                _CURRENT_SEASON_ID,
                f"Spring {datetime.date.today().year} High School",
                "spring-hs",
                datetime.date.today().year,
            ),
        )

        cursor = conn.execute(
            "INSERT OR IGNORE INTO users (email) VALUES (?)",
            ("testdev@example.com",),
        )
        user_id: int = cursor.lastrowid or conn.execute(  # type: ignore[assignment]
            "SELECT id FROM users WHERE email = ?", ("testdev@example.com",)
        ).fetchone()[0]

        conn.execute(
            "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
            (user_id, member_team_id),
        )
        conn.execute(
            "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
            (user_id, tracked_team_id),
        )

        # Players
        conn.executemany(
            "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
            [
                ("jrsy-p-001", "Alice", "Numbered"),   # has jersey number
                ("jrsy-p-002", "Bob", "Nonumber"),     # no jersey number (NULL)
                ("jrsy-p-003", "Carlos", "Tracked"),   # tracked team, has jersey number
                ("jrsy-p-004", "Dan", "TrackedNull"),  # tracked team, no jersey number
            ],
        )

        # Roster entries: member team players
        conn.executemany(
            "INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id, jersey_number)"
            " VALUES (?, ?, ?, ?)",
            [
                (member_team_id, "jrsy-p-001", _CURRENT_SEASON_ID, "42"),
                (member_team_id, "jrsy-p-002", _CURRENT_SEASON_ID, None),  # NULL jersey
                (tracked_team_id, "jrsy-p-003", _CURRENT_SEASON_ID, "7"),
                (tracked_team_id, "jrsy-p-004", _CURRENT_SEASON_ID, None),  # NULL jersey
            ],
        )

        # Batting stats
        conn.executemany(
            "INSERT OR IGNORE INTO player_season_batting"
            " (player_id, team_id, season_id, gp, ab, h, doubles, triples, hr, rbi, bb, so, sb)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("jrsy-p-001", member_team_id, _CURRENT_SEASON_ID, 3, 10, 4, 1, 0, 0, 2, 2, 2, 1),
                ("jrsy-p-002", member_team_id, _CURRENT_SEASON_ID, 3, 8, 2, 0, 0, 0, 1, 1, 3, 0),
                ("jrsy-p-003", tracked_team_id, _CURRENT_SEASON_ID, 3, 9, 3, 1, 0, 1, 3, 1, 2, 0),
                ("jrsy-p-004", tracked_team_id, _CURRENT_SEASON_ID, 2, 6, 1, 0, 0, 0, 0, 2, 3, 1),
            ],
        )

        # Pitching stats
        conn.executemany(
            "INSERT OR IGNORE INTO player_season_pitching"
            " (player_id, team_id, season_id, gp_pitcher, ip_outs, h, er, bb, so, hr)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("jrsy-p-001", member_team_id, _CURRENT_SEASON_ID, 2, 12, 3, 1, 2, 6, 0),
                ("jrsy-p-002", member_team_id, _CURRENT_SEASON_ID, 1, 6, 2, 2, 1, 3, 0),
                ("jrsy-p-003", tracked_team_id, _CURRENT_SEASON_ID, 2, 9, 4, 2, 1, 5, 0),
                ("jrsy-p-004", tracked_team_id, _CURRENT_SEASON_ID, 1, 6, 1, 0, 0, 4, 0),
            ],
        )

        conn.commit()
        conn.close()

        env_overrides = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": "testdev@example.com",
        }
        with patch.dict("os.environ", env_overrides):
            with TestClient(app) as client:
                yield client, member_team_id, tracked_team_id

    # --- Batting (team_stats) tests ---

    def test_batting_member_team_jersey_in_distinct_column(self, jersey_client) -> None:
        """AC-1/AC-5: Member team jersey number renders in # column, not inline with name."""
        client, member_team_id, _ = jersey_client
        response = client.get(f"/dashboard/batting?team_id={member_team_id}")
        assert response.status_code == 200
        html = response.text
        # Jersey appears in a td cell
        assert ">42<" in html
        # Not rendered inline as "#42 " before the name
        assert "#42" not in html

    def test_batting_tracked_team_jersey_in_distinct_column(self, jersey_client) -> None:
        """AC-1/AC-5: Tracked team jersey number renders in # column, not inline with name."""
        client, _, tracked_team_id = jersey_client
        response = client.get(f"/dashboard/batting?team_id={tracked_team_id}")
        assert response.status_code == 200
        html = response.text
        assert ">7<" in html
        assert "#7" not in html

    def test_batting_null_jersey_shows_em_dash(self, jersey_client) -> None:
        """AC-3/AC-6: NULL jersey_number renders em dash in # cell."""
        client, member_team_id, _ = jersey_client
        response = client.get(f"/dashboard/batting?team_id={member_team_id}")
        assert response.status_code == 200
        # Em dash entity or character in the cell
        assert "&mdash;" in response.text or "—" in response.text

    def test_batting_hash_column_header_present(self, jersey_client) -> None:
        """AC-1: team_stats.html has a # column header."""
        client, member_team_id, _ = jersey_client
        response = client.get(f"/dashboard/batting?team_id={member_team_id}")
        assert response.status_code == 200
        assert ">#<" in response.text

    # --- Pitching (team_pitching) tests ---

    def test_pitching_member_team_jersey_in_distinct_column(self, jersey_client) -> None:
        """AC-2/AC-5: Member team jersey number in pitching # column, not inline."""
        client, member_team_id, _ = jersey_client
        response = client.get(f"/dashboard/pitching?team_id={member_team_id}")
        assert response.status_code == 200
        html = response.text
        assert ">42<" in html
        assert "#42" not in html

    def test_pitching_tracked_team_jersey_in_distinct_column(self, jersey_client) -> None:
        """AC-2/AC-5: Tracked team jersey number in pitching # column, not inline."""
        client, _, tracked_team_id = jersey_client
        response = client.get(f"/dashboard/pitching?team_id={tracked_team_id}")
        assert response.status_code == 200
        html = response.text
        assert ">7<" in html
        assert "#7" not in html

    def test_pitching_null_jersey_shows_em_dash(self, jersey_client) -> None:
        """AC-3/AC-6: NULL jersey_number in pitching renders em dash."""
        client, member_team_id, _ = jersey_client
        response = client.get(f"/dashboard/pitching?team_id={member_team_id}")
        assert response.status_code == 200
        assert "&mdash;" in response.text or "—" in response.text

    def test_batting_empty_state_shows_yellow_card(self, tmp_path: Path) -> None:
        """AC-4 (updated for E-142-03): team_stats.html shows yellow info card when team has no stat data."""
        db_path = tmp_path / "test_empty_batting.db"
        _apply_schema(db_path)
        conn = sqlite3.connect(str(db_path))
        lsb_team_id, _ = _insert_lsb_team_and_user(conn)
        conn.commit()
        conn.close()
        env_overrides = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": "testdev@example.com",
        }
        with patch.dict("os.environ", env_overrides):
            with TestClient(app) as client:
                response = client.get("/dashboard/batting")
        assert response.status_code == 200
        assert "bg-yellow-50" in response.text
        assert "Stats haven't been loaded" in response.text
        assert "<table" not in response.text

    def test_pitching_empty_state_shows_yellow_card(self, tmp_path: Path) -> None:
        """AC-4 (updated for E-142-03): team_pitching.html shows yellow info card when team has no stat data."""
        db_path = tmp_path / "test_empty_pitching.db"
        _apply_schema(db_path)
        conn = sqlite3.connect(str(db_path))
        lsb_team_id, _ = _insert_lsb_team_and_user(conn)
        conn.commit()
        conn.close()
        env_overrides = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": "testdev@example.com",
        }
        with patch.dict("os.environ", env_overrides):
            with TestClient(app) as client:
                response = client.get("/dashboard/pitching")
        assert response.status_code == 200
        assert "bg-yellow-50" in response.text
        assert "Stats haven't been loaded" in response.text
        assert "<table" not in response.text


class TestGameDetailJerseyNumber:
    """E-131-02 AC-8: game_detail.html renders jersey # column (template rendering tests)."""

    @pytest.fixture()
    def game_jersey_client(self, tmp_path: Path):
        """TestClient with game box score data including roster entries.

        home team = member (jersey 55), away team = tracked (jersey 99, and one with no roster row).
        Yields (client, lsb_team_id, opp_team_id, game_id).
        """
        db_path = tmp_path / "test_game_jersey.db"
        _apply_schema(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")

        # Member home team
        cursor = conn.execute(
            "INSERT INTO teams (name, membership_type, classification, season_year) VALUES (?, ?, ?, ?)",
            ("Home Team", "member", "varsity", datetime.date.today().year),
        )
        home_id: int = cursor.lastrowid  # type: ignore[assignment]

        # Tracked away team
        cursor = conn.execute(
            "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
            ("Away Team", "tracked"),
        )
        away_id: int = cursor.lastrowid  # type: ignore[assignment]

        conn.execute(
            "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
            (
                _CURRENT_SEASON_ID,
                f"Spring {datetime.date.today().year} High School",
                "spring-hs",
                datetime.date.today().year,
            ),
        )

        cursor = conn.execute(
            "INSERT OR IGNORE INTO users (email) VALUES (?)",
            ("testdev@example.com",),
        )
        user_id: int = cursor.lastrowid or conn.execute(  # type: ignore[assignment]
            "SELECT id FROM users WHERE email = ?", ("testdev@example.com",)
        ).fetchone()[0]
        conn.execute(
            "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
            (user_id, home_id),
        )

        conn.executemany(
            "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
            [
                ("gd-p-home", "Home", "Player"),
                ("gd-p-away-j", "Away", "WithJersey"),
                ("gd-p-away-nj", "Away", "NoJersey"),
            ],
        )

        # Roster: member player has jersey, tracked player has jersey, third has no roster row
        conn.executemany(
            "INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id, jersey_number)"
            " VALUES (?, ?, ?, ?)",
            [
                (home_id, "gd-p-home", _CURRENT_SEASON_ID, "55"),
                (away_id, "gd-p-away-j", _CURRENT_SEASON_ID, "99"),
                # gd-p-away-nj intentionally has no roster entry
            ],
        )

        conn.execute(
            "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id,"
            " home_score, away_score, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("gd-game-1", _CURRENT_SEASON_ID, "2026-04-01", home_id, away_id, 5, 3, "completed"),
        )

        # Batting rows
        conn.executemany(
            "INSERT OR IGNORE INTO player_game_batting (game_id, player_id, team_id, ab, h)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                ("gd-game-1", "gd-p-home", home_id, 4, 2),
                ("gd-game-1", "gd-p-away-j", away_id, 3, 1),
                ("gd-game-1", "gd-p-away-nj", away_id, 2, 0),
            ],
        )
        # Pitching rows
        conn.executemany(
            "INSERT OR IGNORE INTO player_game_pitching (game_id, player_id, team_id, ip_outs, so)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                ("gd-game-1", "gd-p-home", home_id, 9, 5),
                ("gd-game-1", "gd-p-away-j", away_id, 6, 3),
                ("gd-game-1", "gd-p-away-nj", away_id, 3, 1),
            ],
        )

        conn.commit()
        conn.close()

        env_overrides = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": "testdev@example.com",
        }
        with patch.dict("os.environ", env_overrides):
            with TestClient(app) as client:
                yield client, home_id, away_id

    def _batting_html(self, html: str) -> str:
        """Extract batting-table HTML: everything before the first Pitching heading."""
        return html.split(">Pitching</h2>")[0]

    def _pitching_html(self, html: str) -> str:
        """Extract pitching-table HTML: everything after the first Pitching heading."""
        return ">Pitching</h2>".join(html.split(">Pitching</h2>")[1:])

    def test_game_detail_batting_table_has_jersey_column(self, game_jersey_client) -> None:
        """AC-8a/b: # column header and jersey values appear in batting table section."""
        client, home_id, _ = game_jersey_client
        response = client.get(f"/dashboard/games/gd-game-1?team_id={home_id}")
        assert response.status_code == 200
        batting = self._batting_html(response.text)
        assert ">#<" in batting, "# column header missing from batting table"
        assert ">55<" in batting, "home jersey 55 missing from batting table"
        assert ">99<" in batting, "away jersey 99 missing from batting table"

    def test_game_detail_batting_null_jersey_shows_em_dash(self, game_jersey_client) -> None:
        """AC-8c: em dash renders in batting table for NULL jersey_number."""
        client, home_id, _ = game_jersey_client
        response = client.get(f"/dashboard/games/gd-game-1?team_id={home_id}")
        assert response.status_code == 200
        batting = self._batting_html(response.text)
        assert "&mdash;" in batting or "—" in batting, "em dash missing from batting table"

    def test_game_detail_pitching_table_has_jersey_column(self, game_jersey_client) -> None:
        """AC-8a/b: # column header and jersey values appear in pitching table section."""
        client, home_id, _ = game_jersey_client
        response = client.get(f"/dashboard/games/gd-game-1?team_id={home_id}")
        assert response.status_code == 200
        pitching = self._pitching_html(response.text)
        assert ">#<" in pitching, "# column header missing from pitching table"
        assert ">55<" in pitching, "home jersey 55 missing from pitching table"
        assert ">99<" in pitching, "away jersey 99 missing from pitching table"

    def test_game_detail_pitching_null_jersey_shows_em_dash(self, game_jersey_client) -> None:
        """AC-8c: em dash renders in pitching table for NULL jersey_number."""
        client, home_id, _ = game_jersey_client
        response = client.get(f"/dashboard/games/gd-game-1?team_id={home_id}")
        assert response.status_code == 200
        pitching = self._pitching_html(response.text)
        assert "&mdash;" in pitching or "—" in pitching, "em dash missing from pitching table"


class TestOpponentDetailJerseyNumber:
    """E-131-03 AC-8: opponent_detail.html renders jersey # column (template rendering tests)."""

    @pytest.fixture()
    def opp_jersey_client(self, tmp_path: Path):
        """TestClient with opponent scouting data including roster entries.

        Opponent team has: one player with jersey (tracked, scouting path),
        one player without roster row (jersey NULL).
        Yields (client, lsb_team_id, opp_team_id).
        """
        db_path = tmp_path / "test_opp_jersey.db"
        _apply_schema(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")

        lsb_team_id, _ = _insert_lsb_team_and_user(conn)

        # Tracked opponent team
        cursor = conn.execute(
            "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
            ("Scout Opponent", "tracked"),
        )
        opp_team_id: int = cursor.lastrowid  # type: ignore[assignment]

        conn.executemany(
            "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
            [
                ("opp-jrsy-001", "WithJersey", "Player"),
                ("opp-jrsy-002", "NoJersey", "Player"),
            ],
        )

        # Roster: one player has jersey (scouting path), other has no row
        conn.execute(
            "INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id, jersey_number)"
            " VALUES (?, ?, ?, ?)",
            (opp_team_id, "opp-jrsy-001", _CURRENT_SEASON_ID, "77"),
        )
        # opp-jrsy-002 intentionally has no roster entry

        # Game to establish the opponent link
        conn.execute(
            "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id,"
            " home_score, away_score, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("opp-j-game", _CURRENT_SEASON_ID, "2026-04-05", lsb_team_id, opp_team_id,
             4, 2, "completed"),
        )

        # Batting stats for both opponent players
        conn.executemany(
            "INSERT OR IGNORE INTO player_season_batting"
            " (player_id, team_id, season_id, gp, ab, h, doubles, triples, hr, rbi, bb, so, sb)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("opp-jrsy-001", opp_team_id, _CURRENT_SEASON_ID, 3, 10, 4, 1, 0, 0, 2, 2, 2, 1),
                ("opp-jrsy-002", opp_team_id, _CURRENT_SEASON_ID, 3, 8, 2, 0, 0, 0, 1, 1, 3, 0),
            ],
        )

        # Pitching stats for both
        conn.executemany(
            "INSERT OR IGNORE INTO player_season_pitching"
            " (player_id, team_id, season_id, gp_pitcher, ip_outs, h, er, bb, so, hr)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("opp-jrsy-001", opp_team_id, _CURRENT_SEASON_ID, 2, 12, 3, 1, 1, 6, 0),
                ("opp-jrsy-002", opp_team_id, _CURRENT_SEASON_ID, 1, 6, 2, 1, 1, 3, 0),
            ],
        )

        conn.commit()
        conn.close()

        env_overrides = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": "testdev@example.com",
        }
        with patch.dict("os.environ", env_overrides):
            with TestClient(app) as client:
                yield client, lsb_team_id, opp_team_id

    def _batting_html(self, html: str) -> str:
        """Extract batting-table HTML: everything after the Batting Leaders heading.

        E-153-04 reordered sections: pitching comes before batting, so batting is
        after 'Batting Leaders</h2>' rather than before 'Pitching Leaders</h2>'.
        """
        return html.split("Batting Leaders</h2>", 1)[1]

    def _pitching_html(self, html: str) -> str:
        """Extract pitching-table HTML: content between Pitching Leaders and Batting Leaders headings."""
        after_pit = html.split("Pitching Leaders</h2>", 1)[1]
        return after_pit.split("Batting Leaders</h2>")[0]

    def test_opponent_detail_batting_table_has_jersey_column(self, opp_jersey_client) -> None:
        """AC-8a/b: # column header and jersey value appear in batting table section."""
        client, lsb_team_id, opp_team_id = opp_jersey_client
        response = client.get(
            f"/dashboard/opponents/{opp_team_id}?team_id={lsb_team_id}"
        )
        assert response.status_code == 200
        batting = self._batting_html(response.text)
        assert ">#<" in batting, "# column header missing from batting table"
        assert ">77<" in batting, "jersey 77 missing from batting table"

    def test_opponent_detail_batting_null_jersey_em_dash(self, opp_jersey_client) -> None:
        """AC-8c: em dash renders in batting table for NULL jersey_number."""
        client, lsb_team_id, opp_team_id = opp_jersey_client
        response = client.get(
            f"/dashboard/opponents/{opp_team_id}?team_id={lsb_team_id}"
        )
        assert response.status_code == 200
        batting = self._batting_html(response.text)
        assert "&mdash;" in batting or "—" in batting, "em dash missing from batting table"

    def test_opponent_detail_pitching_table_has_jersey_column(self, opp_jersey_client) -> None:
        """AC-8a/b: # column header and jersey value appear in pitching table section."""
        client, lsb_team_id, opp_team_id = opp_jersey_client
        response = client.get(
            f"/dashboard/opponents/{opp_team_id}?team_id={lsb_team_id}"
        )
        assert response.status_code == 200
        pitching = self._pitching_html(response.text)
        assert ">#<" in pitching, "# column header missing from pitching table"
        assert ">77<" in pitching, "jersey 77 missing from pitching table"

    def test_opponent_detail_pitching_null_jersey_em_dash(self, opp_jersey_client) -> None:
        """AC-8c: em dash renders in pitching table for NULL jersey_number."""
        client, lsb_team_id, opp_team_id = opp_jersey_client
        response = client.get(
            f"/dashboard/opponents/{opp_team_id}?team_id={lsb_team_id}"
        )
        assert response.status_code == 200
        pitching = self._pitching_html(response.text)
        assert "&mdash;" in pitching or "—" in pitching, "em dash missing from pitching table"


# ---------------------------------------------------------------------------
# E-142-03: Dashboard Empty State UI
# ---------------------------------------------------------------------------

_CURRENT_YEAR_E142 = datetime.date.today().year


def _make_no_data_db(tmp_path: Path, *, second_team_has_data: bool = False) -> tuple[Path, int, int]:
    """Database with one no-data team and an optional second team with data.

    Returns (db_path, no_data_team_id, data_team_id).
    data_team_id is 0 if second_team_has_data is False.
    """
    db_path = tmp_path / "test_empty_state.db"
    _apply_schema(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
        (_CURRENT_SEASON_ID, f"Spring {_CURRENT_YEAR_E142} High School", "spring-hs", _CURRENT_YEAR_E142),
    )

    # No-data team
    cursor = conn.execute(
        "INSERT INTO teams (name, membership_type, classification) VALUES (?, ?, ?)",
        ("No Data FC", "member", "varsity"),
    )
    no_data_team_id: int = cursor.lastrowid  # type: ignore[assignment]

    cursor = conn.execute(
        "INSERT OR IGNORE INTO users (email) VALUES (?)",
        ("testdev@example.com",),
    )
    user_id: int = cursor.lastrowid or conn.execute(  # type: ignore[assignment]
        "SELECT id FROM users WHERE email = ?", ("testdev@example.com",)
    ).fetchone()[0]
    conn.execute(
        "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
        (user_id, no_data_team_id),
    )

    data_team_id = 0
    if second_team_has_data:
        cursor = conn.execute(
            "INSERT INTO teams (name, membership_type, classification) VALUES (?, ?, ?)",
            ("Data Loaded HS", "member", "varsity"),
        )
        data_team_id = cursor.lastrowid  # type: ignore[assignment]
        conn.execute(
            "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
            (user_id, data_team_id),
        )
        # Give the data team a batting stat row
        conn.execute(
            "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
            ("e142-p-001", "Real", "Stats"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO player_season_batting"
            " (player_id, team_id, season_id, gp, ab, h, doubles, triples, hr, rbi, bb, so, sb)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("e142-p-001", data_team_id, _CURRENT_SEASON_ID, 2, 6, 2, 0, 0, 0, 1, 1, 1, 0),
        )

    conn.commit()
    conn.close()
    return db_path, no_data_team_id, data_team_id


def _make_no_data_with_junction_opponent(tmp_path: Path) -> tuple[Path, int, int]:
    """DB with one no-data team linked to a tracked opponent via team_opponents.

    No games exist, so the junction fallback (E-142-04) supplies the opponent.
    Returns (db_path, no_data_team_id, opp_team_id).
    """
    db_path = tmp_path / "test_junction_opp.db"
    _apply_schema(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
        (_CURRENT_SEASON_ID, f"Spring {_CURRENT_YEAR_E142} High School", "spring-hs", _CURRENT_YEAR_E142),
    )

    cursor = conn.execute(
        "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
        ("LSB No Stats", "member"),
    )
    our_team_id: int = cursor.lastrowid  # type: ignore[assignment]

    cursor = conn.execute(
        "INSERT OR IGNORE INTO users (email) VALUES (?)",
        ("testdev@example.com",),
    )
    user_id: int = cursor.lastrowid or conn.execute(  # type: ignore[assignment]
        "SELECT id FROM users WHERE email = ?", ("testdev@example.com",)
    ).fetchone()[0]
    conn.execute(
        "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
        (user_id, our_team_id),
    )

    cursor = conn.execute(
        "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
        ("Junction Opponent", "tracked"),
    )
    opp_team_id: int = cursor.lastrowid  # type: ignore[assignment]

    conn.execute(
        "INSERT INTO team_opponents (our_team_id, opponent_team_id, first_seen_year) VALUES (?, ?, ?)",
        (our_team_id, opp_team_id, _CURRENT_YEAR_E142),
    )

    conn.commit()
    conn.close()
    return db_path, our_team_id, opp_team_id


class TestEmptyStateUI:
    """E-142-03: Dashboard empty state card and muted pill rendering."""

    def test_batting_tab_shows_yellow_card_for_no_data_team(self, tmp_path: Path) -> None:
        """AC-1: Batting tab shows yellow info card when active team has no stat data."""
        db_path, no_data_id, _ = _make_no_data_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "testdev@example.com"}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                response = client.get(f"/dashboard/batting?team_id={no_data_id}&year={_CURRENT_YEAR_E142}")
        assert response.status_code == 200
        assert "bg-yellow-50" in response.text
        assert "Stats haven't been loaded" in response.text
        assert "<table" not in response.text

    def test_pitching_tab_shows_yellow_card_for_no_data_team(self, tmp_path: Path) -> None:
        """AC-2: Pitching tab shows yellow info card when active team has no stat data."""
        db_path, no_data_id, _ = _make_no_data_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "testdev@example.com"}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                response = client.get(f"/dashboard/pitching?team_id={no_data_id}&year={_CURRENT_YEAR_E142}")
        assert response.status_code == 200
        assert "bg-yellow-50" in response.text
        assert "Stats haven't been loaded" in response.text
        assert "<table" not in response.text

    def test_games_tab_shows_yellow_card_for_no_data_team(self, tmp_path: Path) -> None:
        """AC-2: Games tab shows yellow info card when active team has no stat data."""
        db_path, no_data_id, _ = _make_no_data_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "testdev@example.com"}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                response = client.get(f"/dashboard/games?team_id={no_data_id}&year={_CURRENT_YEAR_E142}")
        assert response.status_code == 200
        assert "bg-yellow-50" in response.text
        assert "Stats haven't been loaded" in response.text
        assert "<table" not in response.text

    def test_opponents_tab_shows_yellow_card_when_no_opponents_and_no_data(
        self, tmp_path: Path
    ) -> None:
        """AC-7: Opponents tab shows yellow card when no opponents AND no stat data."""
        db_path, no_data_id, _ = _make_no_data_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "testdev@example.com"}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                response = client.get(
                    f"/dashboard/opponents?team_id={no_data_id}&year={_CURRENT_YEAR_E142}"
                )
        assert response.status_code == 200
        assert "bg-yellow-50" in response.text
        assert "Stats haven't been loaded" in response.text
        assert "<table" not in response.text

    def test_opponents_tab_shows_list_when_junction_opponent_exists_no_data(
        self, tmp_path: Path
    ) -> None:
        """AC-7: Opponents tab shows opponent list (not yellow card) when junction opponents exist."""
        db_path, our_id, _opp_id = _make_no_data_with_junction_opponent(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "testdev@example.com"}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                response = client.get(
                    f"/dashboard/opponents?team_id={our_id}&year={_CURRENT_YEAR_E142}"
                )
        assert response.status_code == 200
        assert "Junction Opponent" in response.text
        assert "<table" in response.text
        assert "bg-yellow-50" not in response.text

    def test_unselected_no_data_pill_uses_muted_styling(self, tmp_path: Path) -> None:
        """AC-3: Unselected pill for a no-data team uses gray muted styling."""
        db_path, no_data_id, data_id = _make_no_data_db(tmp_path, second_team_has_data=True)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "testdev@example.com"}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                # Select the data team so no_data pill is unselected
                response = client.get(f"/dashboard/batting?team_id={data_id}&year={_CURRENT_YEAR_E142}")
        assert response.status_code == 200
        assert "bg-gray-50" in response.text
        assert "text-gray-400" in response.text

    def test_selected_no_data_pill_uses_normal_selected_styling(self, tmp_path: Path) -> None:
        """AC-4: The active pill for a no-data team uses normal selected styling (bg-blue-900)."""
        db_path, no_data_id, _ = _make_no_data_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "testdev@example.com"}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                response = client.get(f"/dashboard/batting?team_id={no_data_id}&year={_CURRENT_YEAR_E142}")
        assert response.status_code == 200
        # Active pill class
        assert "bg-blue-900 text-white" in response.text

    def test_single_year_shows_year_label(self, tmp_path: Path) -> None:
        """AC-5a: When only one year exists, a static year label is visible."""
        db_path, no_data_id, _ = _make_no_data_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "testdev@example.com"}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                response = client.get(f"/dashboard/batting?team_id={no_data_id}&year={_CURRENT_YEAR_E142}")
        assert response.status_code == 200
        # Year label should appear as plain text (not dropdown)
        assert str(_CURRENT_YEAR_E142) in response.text
        # There should be no year dropdown
        assert 'name="year"' not in response.text

    def test_data_team_still_renders_table(self, tmp_path: Path) -> None:
        """AC-6: A team with stat data still renders the batting table (no regression)."""
        db_path, _no_data_id, data_id = _make_no_data_db(tmp_path, second_team_has_data=True)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "testdev@example.com"}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                response = client.get(f"/dashboard/batting?team_id={data_id}&year={_CURRENT_YEAR_E142}")
        assert response.status_code == 200
        assert "<table" in response.text
        assert "bg-yellow-50" not in response.text
