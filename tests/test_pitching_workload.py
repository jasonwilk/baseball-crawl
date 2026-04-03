"""Tests for the pitching workload query function.

Covers AC-1 through AC-6 of E-196-03.
"""

from __future__ import annotations

import sqlite3

import pytest

from src.api.db import get_pitching_workload


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _create_schema(db: sqlite3.Connection) -> None:
    """Create minimal schema for workload tests."""
    db.executescript(
        """
        CREATE TABLE seasons (
            season_id TEXT PRIMARY KEY,
            name TEXT,
            season_type TEXT,
            year INTEGER
        );
        CREATE TABLE teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gc_uuid TEXT UNIQUE,
            public_id TEXT UNIQUE,
            membership_type TEXT DEFAULT 'tracked',
            is_active INTEGER DEFAULT 1,
            season_year INTEGER,
            program_id TEXT,
            classification TEXT
        );
        CREATE TABLE players (
            player_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT
        );
        CREATE TABLE games (
            game_id TEXT PRIMARY KEY,
            season_id TEXT REFERENCES seasons(season_id),
            game_date TEXT,
            home_team_id INTEGER REFERENCES teams(id),
            away_team_id INTEGER REFERENCES teams(id),
            home_score INTEGER,
            away_score INTEGER,
            status TEXT,
            game_stream_id TEXT,
            start_time TEXT,
            timezone TEXT
        );
        CREATE TABLE player_game_pitching (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL REFERENCES games(game_id),
            player_id TEXT NOT NULL REFERENCES players(player_id),
            team_id INTEGER NOT NULL REFERENCES teams(id),
            decision TEXT,
            stat_completeness TEXT NOT NULL DEFAULT 'boxscore_only',
            ip_outs INTEGER,
            h INTEGER, r INTEGER, er INTEGER, bb INTEGER, so INTEGER,
            wp INTEGER, hbp INTEGER,
            pitches INTEGER,
            total_strikes INTEGER, bf INTEGER,
            UNIQUE(game_id, player_id)
        );

        INSERT INTO seasons (season_id, name, season_type, year)
            VALUES ('2025-spring-hs', '2025 Spring HS', 'spring-hs', 2025);
        INSERT INTO teams (id, name) VALUES (1, 'Own Team');
        INSERT INTO teams (id, name) VALUES (2, 'Opponent');

        INSERT INTO players (player_id, first_name, last_name)
            VALUES ('p1', 'Ace', 'Pitcher');
        INSERT INTO players (player_id, first_name, last_name)
            VALUES ('p2', 'Relief', 'Pitcher');
        INSERT INTO players (player_id, first_name, last_name)
            VALUES ('p3', 'Spot', 'Starter');
        INSERT INTO players (player_id, first_name, last_name)
            VALUES ('p4', 'Null', 'Counts');
        INSERT INTO players (player_id, first_name, last_name)
            VALUES ('p5', 'Mixed', 'Nulls');
        """
    )


def _insert_game(db: sqlite3.Connection, game_id: str, game_date: str) -> None:
    db.execute(
        """
        INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id,
                           home_score, away_score, status)
        VALUES (?, '2025-spring-hs', ?, 1, 2, 5, 3, 'completed')
        """,
        (game_id, game_date),
    )


def _insert_pitching(
    db: sqlite3.Connection,
    player_id: str,
    game_id: str,
    pitches: int | None = 75,
) -> None:
    db.execute(
        """
        INSERT INTO player_game_pitching
            (game_id, player_id, team_id, ip_outs, h, r, er, bb, so, pitches)
        VALUES (?, ?, 1, 9, 3, 1, 1, 2, 5, ?)
        """,
        (game_id, player_id, pitches),
    )


@pytest.fixture()
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON;")
    _create_schema(conn)
    return conn


REFERENCE_DATE = "2025-04-26"
SEASON_ID = "2025-spring-hs"


# ---------------------------------------------------------------------------
# AC-1: Function returns per-pitcher workload data
# ---------------------------------------------------------------------------


class TestBasicWorkload:
    """AC-1 & AC-2: Function returns keyed workload data."""

    def test_returns_dict_keyed_by_player_id(self, db: sqlite3.Connection) -> None:
        _insert_game(db, "g1", "2025-04-24")
        _insert_pitching(db, "p1", "g1", pitches=85)

        result = get_pitching_workload(1, SEASON_ID, REFERENCE_DATE, db=db)

        assert "p1" in result
        data = result["p1"]
        assert "last_outing_date" in data
        assert "last_outing_days_ago" in data
        assert "pitches_7d" in data
        assert "span_days_7d" in data

    def test_last_outing_date_is_most_recent(self, db: sqlite3.Connection) -> None:
        _insert_game(db, "g1", "2025-04-20")
        _insert_game(db, "g2", "2025-04-24")
        _insert_pitching(db, "p1", "g1", pitches=80)
        _insert_pitching(db, "p1", "g2", pitches=90)

        result = get_pitching_workload(1, SEASON_ID, REFERENCE_DATE, db=db)

        assert result["p1"]["last_outing_date"] == "2025-04-24"

    def test_multiple_pitchers_returned(self, db: sqlite3.Connection) -> None:
        _insert_game(db, "g1", "2025-04-24")
        _insert_pitching(db, "p1", "g1", pitches=85)
        _insert_pitching(db, "p2", "g1", pitches=30)

        result = get_pitching_workload(1, SEASON_ID, REFERENCE_DATE, db=db)

        assert len(result) == 2
        assert "p1" in result
        assert "p2" in result


# ---------------------------------------------------------------------------
# AC-3: pitches_7d is 0 when no appearances in 7d window
# ---------------------------------------------------------------------------


class TestPitches7dZero:
    """AC-3: pitches_7d = 0 when pitcher has no appearances in 7d window."""

    def test_appearances_only_outside_7d_window(self, db: sqlite3.Connection) -> None:
        # Game 15 days ago -- outside the 7d window
        _insert_game(db, "g1", "2025-04-11")
        _insert_pitching(db, "p3", "g1", pitches=100)

        result = get_pitching_workload(1, SEASON_ID, REFERENCE_DATE, db=db)

        assert result["p3"]["pitches_7d"] == 0
        assert result["p3"]["span_days_7d"] is None
        assert result["p3"]["last_outing_date"] == "2025-04-11"
        assert result["p3"]["last_outing_days_ago"] == 15


# ---------------------------------------------------------------------------
# AC-4: last_outing_days_ago edge cases
# ---------------------------------------------------------------------------


class TestLastOutingDaysAgo:
    """AC-4: NULL when no appearances; 0 when last outing is reference date."""

    def test_days_ago_is_zero_on_reference_date(self, db: sqlite3.Connection) -> None:
        _insert_game(db, "g1", REFERENCE_DATE)
        _insert_pitching(db, "p1", "g1", pitches=90)

        result = get_pitching_workload(1, SEASON_ID, REFERENCE_DATE, db=db)

        assert result["p1"]["last_outing_days_ago"] == 0

    def test_days_ago_correct_for_past_game(self, db: sqlite3.Connection) -> None:
        _insert_game(db, "g1", "2025-04-23")
        _insert_pitching(db, "p1", "g1", pitches=80)

        result = get_pitching_workload(1, SEASON_ID, REFERENCE_DATE, db=db)

        assert result["p1"]["last_outing_days_ago"] == 3

    def test_no_appearances_returns_empty(self, db: sqlite3.Connection) -> None:
        """Pitcher with no game appearances should not appear in results."""
        result = get_pitching_workload(1, SEASON_ID, REFERENCE_DATE, db=db)

        # No pitching rows -> no results at all
        assert len(result) == 0


# ---------------------------------------------------------------------------
# AC-5: pitches_7d NULL when all pitch counts are NULL
# ---------------------------------------------------------------------------


class TestPitches7dNull:
    """AC-5: pitches_7d = NULL when appearances exist but all pitches are NULL."""

    def test_all_null_pitches_in_7d_window(self, db: sqlite3.Connection) -> None:
        _insert_game(db, "g1", "2025-04-24")
        _insert_game(db, "g2", "2025-04-25")
        _insert_pitching(db, "p4", "g1", pitches=None)
        _insert_pitching(db, "p4", "g2", pitches=None)

        result = get_pitching_workload(1, SEASON_ID, REFERENCE_DATE, db=db)

        assert result["p4"]["pitches_7d"] is None
        # span_days_7d should still be computed (appearances exist)
        assert result["p4"]["span_days_7d"] == 2

    def test_mixed_null_and_non_null_pitches(self, db: sqlite3.Connection) -> None:
        """Mixed NULL and non-NULL: pitches_7d = sum of non-NULL values."""
        _insert_game(db, "g1", "2025-04-24")
        _insert_game(db, "g2", "2025-04-25")
        _insert_pitching(db, "p5", "g1", pitches=None)
        _insert_pitching(db, "p5", "g2", pitches=60)

        result = get_pitching_workload(1, SEASON_ID, REFERENCE_DATE, db=db)

        assert result["p5"]["pitches_7d"] == 60


# ---------------------------------------------------------------------------
# AC-6: Multiple appearances in 7d window
# ---------------------------------------------------------------------------


class TestMultipleAppearances:
    """AC-6: pitcher with multiple appearances in 7d window."""

    def test_pitches_summed_across_appearances(self, db: sqlite3.Connection) -> None:
        _insert_game(db, "g1", "2025-04-22")
        _insert_game(db, "g2", "2025-04-24")
        _insert_game(db, "g3", "2025-04-26")
        _insert_pitching(db, "p1", "g1", pitches=30)
        _insert_pitching(db, "p1", "g2", pitches=25)
        _insert_pitching(db, "p1", "g3", pitches=40)

        result = get_pitching_workload(1, SEASON_ID, REFERENCE_DATE, db=db)

        assert result["p1"]["pitches_7d"] == 95
        # span: Apr 22 to Apr 26 = 5 days
        assert result["p1"]["span_days_7d"] == 5

    def test_span_days_single_appearance(self, db: sqlite3.Connection) -> None:
        _insert_game(db, "g1", "2025-04-25")
        _insert_pitching(db, "p2", "g1", pitches=50)

        result = get_pitching_workload(1, SEASON_ID, REFERENCE_DATE, db=db)

        assert result["p2"]["span_days_7d"] == 1

    def test_7d_window_boundary_inclusive(self, db: sqlite3.Connection) -> None:
        """Game exactly 6 days before reference date is included (7-day window)."""
        # reference_date = 2025-04-26
        # date('2025-04-26', '-6 days') = '2025-04-20'
        _insert_game(db, "g_boundary", "2025-04-20")
        _insert_pitching(db, "p1", "g_boundary", pitches=70)

        result = get_pitching_workload(1, SEASON_ID, REFERENCE_DATE, db=db)

        assert result["p1"]["pitches_7d"] == 70

    def test_7d_window_excludes_day_before_boundary(self, db: sqlite3.Connection) -> None:
        """Game 7 days before reference date is excluded (outside 7-day window)."""
        _insert_game(db, "g_outside", "2025-04-19")
        _insert_pitching(db, "p1", "g_outside", pitches=70)

        result = get_pitching_workload(1, SEASON_ID, REFERENCE_DATE, db=db)

        assert result["p1"]["pitches_7d"] == 0


# ---------------------------------------------------------------------------
# Edge case: reference_date defaults
# ---------------------------------------------------------------------------


class TestReferenceDate:
    """Reference date parameter behavior."""

    def test_default_reference_date_uses_today(self, db: sqlite3.Connection) -> None:
        """Without explicit reference_date, function uses today's date."""
        import datetime

        today = datetime.date.today().isoformat()
        _insert_game(db, "g1", today)
        _insert_pitching(db, "p1", "g1", pitches=80)

        result = get_pitching_workload(1, SEASON_ID, db=db)

        assert result["p1"]["last_outing_days_ago"] == 0
        assert result["p1"]["pitches_7d"] == 80


# ---------------------------------------------------------------------------
# Edge case: team scoping
# ---------------------------------------------------------------------------


class TestTeamScoping:
    """Query is scoped to the specified team."""

    def test_only_returns_pitchers_for_specified_team(
        self, db: sqlite3.Connection
    ) -> None:
        _insert_game(db, "g1", "2025-04-24")
        # p1 pitches for team 1
        _insert_pitching(db, "p1", "g1", pitches=85)
        # p2 pitches for team 2 (different team)
        db.execute(
            """
            INSERT INTO player_game_pitching
                (game_id, player_id, team_id, ip_outs, h, r, er, bb, so, pitches)
            VALUES ('g1', 'p2', 2, 6, 2, 1, 1, 1, 3, 40)
            """
        )

        result = get_pitching_workload(1, SEASON_ID, REFERENCE_DATE, db=db)

        assert "p1" in result
        assert "p2" not in result
