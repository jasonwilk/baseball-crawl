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

from src.api.main import app  # noqa: E402

# Derive season_id the same way the route does, so tests stay valid across years.
_CURRENT_SEASON_ID = f"{datetime.date.today().year}-spring-hs"
_ALT_SEASON_ID = "2025-spring-hs"

# ---------------------------------------------------------------------------
# E-100 schema (subset needed by dashboard tests)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS _migrations (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        filename   TEXT    NOT NULL UNIQUE,
        applied_at TEXT    NOT NULL DEFAULT (datetime('now'))
    );
    INSERT OR IGNORE INTO _migrations (filename)
        VALUES ('001_initial_schema.sql');

    -- E-100: users -- id INTEGER PK
    CREATE TABLE IF NOT EXISTS users (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        email      TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- E-100: teams -- id INTEGER PK AUTOINCREMENT, membership_type replaces is_owned
    CREATE TABLE IF NOT EXISTS teams (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT NOT NULL,
        membership_type TEXT NOT NULL DEFAULT 'member',
        classification  TEXT,
        public_id       TEXT,
        gc_uuid         TEXT,
        source          TEXT NOT NULL DEFAULT 'gamechanger',
        is_active       INTEGER NOT NULL DEFAULT 1,
        last_synced     TEXT,
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- E-100: user_team_access -- team_id is INTEGER FK
    CREATE TABLE IF NOT EXISTS user_team_access (
        user_id INTEGER NOT NULL REFERENCES users(id),
        team_id INTEGER NOT NULL REFERENCES teams(id),
        UNIQUE(user_id, team_id)
    );

    -- E-100: sessions
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id    INTEGER NOT NULL REFERENCES users(id),
        expires_at TEXT NOT NULL
    );

    -- E-100: magic_link_tokens
    CREATE TABLE IF NOT EXISTS magic_link_tokens (
        token      TEXT PRIMARY KEY,
        user_id    INTEGER NOT NULL REFERENCES users(id),
        expires_at TEXT NOT NULL
    );

    -- E-100: passkey_credentials
    CREATE TABLE IF NOT EXISTS passkey_credentials (
        credential_id TEXT PRIMARY KEY,
        user_id       INTEGER NOT NULL REFERENCES users(id),
        public_key    TEXT NOT NULL,
        sign_count    INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS seasons (
        season_id   TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        season_type TEXT NOT NULL,
        year        INTEGER NOT NULL,
        start_date  TEXT,
        end_date    TEXT,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS players (
        player_id   TEXT PRIMARY KEY,
        first_name  TEXT NOT NULL,
        last_name   TEXT NOT NULL,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- E-100: team_rosters -- team_id is INTEGER FK
    CREATE TABLE IF NOT EXISTS team_rosters (
        team_id       INTEGER NOT NULL REFERENCES teams(id),
        player_id     TEXT NOT NULL REFERENCES players(player_id),
        season_id     TEXT NOT NULL REFERENCES seasons(season_id),
        jersey_number TEXT,
        position      TEXT,
        PRIMARY KEY(team_id, player_id, season_id)
    );

    -- E-100: games -- home_team_id / away_team_id are INTEGER FKs
    CREATE TABLE IF NOT EXISTS games (
        game_id      TEXT PRIMARY KEY,
        season_id    TEXT NOT NULL REFERENCES seasons(season_id),
        game_date    TEXT NOT NULL,
        home_team_id INTEGER NOT NULL REFERENCES teams(id),
        away_team_id INTEGER NOT NULL REFERENCES teams(id),
        home_score   INTEGER,
        away_score   INTEGER,
        status       TEXT NOT NULL DEFAULT 'completed'
    );

    -- E-100: player_game_batting -- team_id is INTEGER FK
    CREATE TABLE IF NOT EXISTS player_game_batting (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id   TEXT NOT NULL REFERENCES games(game_id),
        player_id TEXT NOT NULL REFERENCES players(player_id),
        team_id   INTEGER NOT NULL REFERENCES teams(id),
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

    -- E-100: player_game_pitching -- team_id is INTEGER FK
    CREATE TABLE IF NOT EXISTS player_game_pitching (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id   TEXT NOT NULL REFERENCES games(game_id),
        player_id TEXT NOT NULL REFERENCES players(player_id),
        team_id   INTEGER NOT NULL REFERENCES teams(id),
        ip_outs   INTEGER,
        h         INTEGER,
        er        INTEGER,
        bb        INTEGER,
        so        INTEGER,
        hr        INTEGER,
        UNIQUE(game_id, player_id)
    );

    -- E-100: player_season_batting -- team_id INTEGER FK, gp column (was 'games')
    CREATE TABLE IF NOT EXISTS player_season_batting (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id         TEXT NOT NULL REFERENCES players(player_id),
        team_id           INTEGER NOT NULL REFERENCES teams(id),
        season_id         TEXT NOT NULL REFERENCES seasons(season_id),
        stat_completeness TEXT NOT NULL DEFAULT 'boxscore_only',
        gp        INTEGER,
        ab        INTEGER,
        h         INTEGER,
        doubles   INTEGER,
        triples   INTEGER,
        hr        INTEGER,
        rbi       INTEGER,
        bb        INTEGER,
        so        INTEGER,
        sb        INTEGER,
        UNIQUE(player_id, team_id, season_id)
    );

    -- E-100: player_season_pitching -- team_id INTEGER FK, gp_pitcher column (was 'games')
    CREATE TABLE IF NOT EXISTS player_season_pitching (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id         TEXT NOT NULL REFERENCES players(player_id),
        team_id           INTEGER NOT NULL REFERENCES teams(id),
        season_id         TEXT NOT NULL REFERENCES seasons(season_id),
        stat_completeness TEXT NOT NULL DEFAULT 'boxscore_only',
        gp_pitcher INTEGER,
        ip_outs    INTEGER,
        h          INTEGER,
        er         INTEGER,
        bb         INTEGER,
        so         INTEGER,
        hr         INTEGER,
        pitches    INTEGER,
        UNIQUE(player_id, team_id, season_id)
    );

    CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_gc_uuid
        ON teams(gc_uuid) WHERE gc_uuid IS NOT NULL;
    CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_public_id
        ON teams(public_id) WHERE public_id IS NOT NULL;
"""


# ---------------------------------------------------------------------------
# Database fixture helpers -- Python parameterized inserts (no TEXT team_id)
# ---------------------------------------------------------------------------


def _apply_schema(conn: sqlite3.Connection) -> None:
    """Apply the E-100 schema to a fresh SQLite connection."""
    conn.executescript(_SCHEMA_SQL)


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
        " (game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("game-001", _CURRENT_SEASON_ID, "2026-03-01", lsb_team_id, opp_team_id, 7, 3),
            ("game-002", _CURRENT_SEASON_ID, "2026-02-20", opp_team_id, lsb_team_id, 2, 5),
        ],
    )

    # Unrelated game (not involving lsb_team_id)
    conn.execute(
        "INSERT OR IGNORE INTO games"
        " (game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("game-unrelated", _CURRENT_SEASON_ID, "2026-03-05", other_team_id1, other_team_id2, 4, 1),
    )

    # Alt-season game
    conn.execute(
        "INSERT OR IGNORE INTO games"
        " (game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("game-2025", _ALT_SEASON_ID, "2025-03-15", lsb_team_id, opp_team_id, 6, 4),
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
        " (game_id, player_id, team_id, ip_outs, h, er, bb, so, hr)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("game-001", "gc-p-001", lsb_team_id, 18, 3, 1, 2, 8, 0),
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
        " (game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("game-opp-2025", _ALT_SEASON_ID, "2025-03-10", lsb_team_id, opp_team_id, 4, 2),
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
        " (game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("game-001", _CURRENT_SEASON_ID, "2026-03-01", lsb_team_id, opp_team_id, 7, 3),
            ("game-002", _CURRENT_SEASON_ID, "2026-02-20", opp_team_id, lsb_team_id, 2, 5),
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
        " (game_id, player_id, team_id, ip_outs, h, er, bb, so, hr)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("game-001", "gc-p-001", lsb_team_id, 9, 2, 0, 1, 5, 0),
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
    conn = sqlite3.connect(str(db_path))
    _apply_schema(conn)
    lsb_team_id, _ = _insert_lsb_team_and_user(conn)
    _insert_players_and_batting(conn, lsb_team_id)
    conn.commit()
    conn.close()
    return db_path, lsb_team_id


def _make_pitching_seeded_db(tmp_path: Path) -> tuple[Path, int]:
    """Create database with batting + pitching data. Returns (db_path, lsb_team_id)."""
    db_path = tmp_path / "test_pitching.db"
    conn = sqlite3.connect(str(db_path))
    _apply_schema(conn)
    lsb_team_id, _ = _insert_lsb_team_and_user(conn)
    _insert_players_and_batting(conn, lsb_team_id)
    _insert_pitching(conn, lsb_team_id)
    conn.commit()
    conn.close()
    return db_path, lsb_team_id


def _make_games_seeded_db(tmp_path: Path) -> tuple[Path, int, int]:
    """Create database with game log data. Returns (db_path, lsb_team_id, opp_team_id)."""
    db_path = tmp_path / "test_games.db"
    conn = sqlite3.connect(str(db_path))
    _apply_schema(conn)
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
    conn = sqlite3.connect(str(db_path))
    _apply_schema(conn)
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
    conn = sqlite3.connect(str(db_path))
    _apply_schema(conn)
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
        assert any(str(v) in html for v in [6, 8, 7]), (
            "Expected at least one stat value in dashboard HTML."
        )

    def test_dashboard_shows_at_least_three_players(
        self, seeded_client: TestClient
    ) -> None:
        """GET /dashboard renders at least 3 players in the table (AC-3)."""
        response = seeded_client.get("/dashboard")
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
        response = seeded_client.get("/dashboard")
        html = response.text
        for header in ("AB", "H", "BB", "SO"):
            assert header in html, (
                f"Expected column header '{header}' in dashboard HTML."
            )

    def test_dashboard_contains_viewport_meta(
        self, seeded_client: TestClient
    ) -> None:
        """GET /dashboard HTML includes a viewport meta tag for mobile."""
        response = seeded_client.get("/dashboard")
        assert 'name="viewport"' in response.text

    def test_dashboard_contains_tailwind_cdn(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML includes the Tailwind CSS CDN script tag."""
        response = seeded_client.get("/dashboard")
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
        response = seeded_client.get("/dashboard")
        assert "overflow-x-auto" in response.text


class TestEnhancedBattingStats:
    """Tests for enhanced batting stats on GET /dashboard (E-004-02)."""

    def test_batting_returns_200(self, seeded_client: TestClient) -> None:
        """GET /dashboard returns HTTP 200 with seeded data."""
        response = seeded_client.get("/dashboard")
        assert response.status_code == 200

    def test_batting_contains_seeded_player_name(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML contains at least one seeded player last name."""
        response = seeded_client.get("/dashboard")
        html = response.text
        player_names = ["Whitehorse", "Runningwater", "Strongbow", "Redcloud", "Eagleheart"]
        assert any(name in html for name in player_names)

    def test_batting_computed_avg_value(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML contains a correctly computed AVG for gc-p-001.

        gc-p-001 has 3 H in 6 AB => AVG = .500.
        """
        response = seeded_client.get("/dashboard")
        assert ".500" in response.text

    def test_batting_column_headers(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML includes AVG, OBP, SLG column headers."""
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
        """GET /dashboard HTML contains player profile links."""
        response = seeded_client.get("/dashboard")
        assert "/dashboard/players/" in response.text

    def test_batting_zero_ab_shows_dash(self, seeded_client: TestClient) -> None:
        """AVG/OBP/SLG display '-' for player with zero AB.

        gc-p-006 has 0 AB; all rate stats should display '-'.
        """
        response = seeded_client.get("/dashboard")
        html = response.text
        assert "Noatbats" in html
        assert "-" in html

    def test_batting_sticky_thead(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML uses sticky top-0 on thead."""
        response = seeded_client.get("/dashboard")
        assert "sticky top-0" in response.text

    def test_batting_overflow_x_auto(self, seeded_client: TestClient) -> None:
        """GET /dashboard HTML wraps table in overflow-x-auto."""
        response = seeded_client.get("/dashboard")
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
        for header in ("IP", "H", "ER", "BB", "SO", "HR"):
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
        """GET /dashboard/opponents/{id} shows Key Players card (AC-5, AC-15)."""
        client, _, opp_team_id, _ = opponent_client
        response = client.get(f"/dashboard/opponents/{opp_team_id}")
        assert "Key Players" in response.text

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
        """Key Players card shows 'Insufficient data.' when no players meet threshold (AC-15).

        games_client has games vs opp but no opponent batting/pitching rows.
        """
        client, _, opp_team_id = games_client
        response = client.get(f"/dashboard/opponents/{opp_team_id}")
        assert response.status_code == 200
        assert "Insufficient data." in response.text

    def test_opponent_detail_no_stats_shows_message(self, games_client) -> None:
        """GET /dashboard/opponents/{id} shows 'Insufficient data.' when no stats loaded (AC-5).

        games_client has games vs opp but no opponent batting/pitching rows.
        """
        client, _, opp_team_id = games_client
        response = client.get(f"/dashboard/opponents/{opp_team_id}")
        assert response.status_code == 200
        assert "Insufficient data." in response.text

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
        """'First meeting this season.' shown when only scheduled (not completed) games exist."""
        db_path = tmp_path / "test_no_completed.db"
        conn = sqlite3.connect(str(db_path))
        _apply_schema(conn)
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

    def test_player_profile_two_way_player_dedup(self, player_profile_client) -> None:
        """Recent Games deduplicates by game_id for two-way players (AC-13).

        gc-p-001 has both batting and pitching lines in game-001.
        game-001 should appear only once in Recent Games.
        """
        client, _ = player_profile_client
        response = client.get("/dashboard/players/gc-p-001")
        html = response.text
        occurrences = html.count("/dashboard/games/game-001")
        assert occurrences == 1


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
        """All six dashboard templates contain no 'is_admin' references (AC-4)."""
        for filename in self._DASHBOARD_TEMPLATES:
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
