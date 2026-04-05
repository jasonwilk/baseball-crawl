"""Tests for get_pitching_history() and build_pitcher_profiles() in src/api/db.py."""

from __future__ import annotations

import sqlite3

import pytest

from src.api.db import build_pitcher_profiles, get_pitching_history


def _create_schema(conn: sqlite3.Connection) -> None:
    """Create minimal schema needed for pitching history queries."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS seasons (
            season_id TEXT PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS programs (
            program_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            program_type TEXT NOT NULL DEFAULT 'hs'
        );
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gc_uuid TEXT UNIQUE,
            public_id TEXT UNIQUE,
            membership_type TEXT NOT NULL DEFAULT 'tracked',
            season_year INTEGER,
            is_active INTEGER NOT NULL DEFAULT 1,
            program_id TEXT REFERENCES programs(program_id),
            classification TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS players (
            player_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            bats TEXT,
            throws TEXT,
            gc_athlete_profile_id TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS team_rosters (
            team_id INTEGER NOT NULL REFERENCES teams(id),
            player_id TEXT NOT NULL REFERENCES players(player_id),
            season_id TEXT NOT NULL REFERENCES seasons(season_id),
            jersey_number TEXT,
            position TEXT,
            PRIMARY KEY (team_id, player_id, season_id)
        );
        CREATE TABLE IF NOT EXISTS games (
            game_id TEXT PRIMARY KEY,
            season_id TEXT NOT NULL REFERENCES seasons(season_id),
            game_date TEXT NOT NULL,
            start_time TEXT,
            home_team_id INTEGER NOT NULL REFERENCES teams(id),
            away_team_id INTEGER NOT NULL REFERENCES teams(id),
            home_score INTEGER,
            away_score INTEGER,
            status TEXT NOT NULL DEFAULT 'scheduled',
            game_stream_id TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS player_game_pitching (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL REFERENCES games(game_id),
            player_id TEXT NOT NULL REFERENCES players(player_id),
            team_id INTEGER NOT NULL REFERENCES teams(id),
            decision TEXT,
            stat_completeness TEXT NOT NULL DEFAULT 'boxscore_only',
            ip_outs INTEGER,
            h INTEGER,
            r INTEGER,
            er INTEGER,
            bb INTEGER,
            so INTEGER,
            wp INTEGER,
            hbp INTEGER,
            pitches INTEGER,
            total_strikes INTEGER,
            bf INTEGER,
            appearance_order INTEGER,
            UNIQUE(game_id, player_id)
        );
    """)


def _seed_season_and_team(conn: sqlite3.Connection, *, team_id: int = 1,
                          season_id: str = "2026-spring-hs") -> tuple[int, str]:
    """Insert a season and team, return (team_id, season_id)."""
    conn.execute("INSERT OR IGNORE INTO seasons VALUES (?)", (season_id,))
    conn.execute(
        "INSERT OR IGNORE INTO teams (id, name) VALUES (?, ?)",
        (team_id, f"Team {team_id}"),
    )
    return team_id, season_id


def _insert_player(conn: sqlite3.Connection, player_id: str,
                   first_name: str, last_name: str,
                   *, team_id: int = 1, season_id: str = "2026-spring-hs",
                   jersey_number: str | None = None) -> None:
    """Insert a player and roster entry."""
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (player_id, first_name, last_name),
    )
    conn.execute(
        "INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id, jersey_number) "
        "VALUES (?, ?, ?, ?)",
        (team_id, player_id, season_id, jersey_number),
    )


def _insert_game(conn: sqlite3.Connection, game_id: str, game_date: str,
                 *, season_id: str = "2026-spring-hs", team_id: int = 1,
                 start_time: str | None = None,
                 status: str = "completed") -> None:
    """Insert a game with team as home team."""
    conn.execute(
        "INSERT OR IGNORE INTO games "
        "(game_id, season_id, game_date, start_time, home_team_id, away_team_id, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (game_id, season_id, game_date, start_time, team_id, 999, status),
    )
    # Ensure away team exists
    conn.execute(
        "INSERT OR IGNORE INTO teams (id, name) VALUES (999, 'Opponent')"
    )


def _insert_pitching_line(
    conn: sqlite3.Connection,
    game_id: str,
    player_id: str,
    *,
    team_id: int = 1,
    ip_outs: int = 0,
    pitches: int | None = None,
    so: int = 0,
    bb: int = 0,
    h: int = 0,
    r: int = 0,
    er: int = 0,
    bf: int | None = None,
    decision: str | None = None,
    appearance_order: int | None = None,
) -> None:
    """Insert a player_game_pitching row."""
    conn.execute(
        "INSERT INTO player_game_pitching "
        "(game_id, player_id, team_id, ip_outs, pitches, so, bb, h, r, er, bf, "
        "decision, appearance_order) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_id, player_id, team_id, ip_outs, pitches, so, bb, h, r, er, bf,
         decision, appearance_order),
    )


@pytest.fixture
def db():
    """In-memory SQLite database with schema."""
    conn = sqlite3.connect(":memory:")
    _create_schema(conn)
    yield conn
    conn.close()


# ── AC-5: Normal team with 10+ games and 4-5 pitchers ──────────────────


class TestNormalTeam:
    """Test a team with 12 games and 4 pitchers."""

    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        team_id, season_id = _seed_season_and_team(db)
        # 4 pitchers
        _insert_player(db, "p1", "Ace", "Smith", jersey_number="22")
        _insert_player(db, "p2", "Two", "Jones", jersey_number="15")
        _insert_player(db, "p3", "Three", "Garcia", jersey_number="31")
        _insert_player(db, "p4", "Four", "Lee", jersey_number="8")

        # 12 games over ~3 weeks
        dates = [
            ("g01", "2026-03-10", "14:00"),
            ("g02", "2026-03-12", "16:00"),
            ("g03", "2026-03-14", "14:00"),
            ("g04", "2026-03-17", "16:00"),
            ("g05", "2026-03-19", "14:00"),
            ("g06", "2026-03-21", "16:00"),
            ("g07", "2026-03-24", "14:00"),
            ("g08", "2026-03-26", "16:00"),
            ("g09", "2026-03-28", "14:00"),
            ("g10", "2026-03-31", "16:00"),
            ("g11", "2026-04-02", "14:00"),
            ("g12", "2026-04-02", "16:30"),  # doubleheader
        ]
        for gid, gd, st in dates:
            _insert_game(db, gid, gd, start_time=st)

        # Rotation: p1, p2, p3, p4 cycle as starters
        starters = ["p1", "p2", "p3", "p4", "p1", "p2", "p3", "p4", "p1", "p2", "p3", "p4"]
        for i, (gid, gd, st) in enumerate(dates):
            starter = starters[i]
            _insert_pitching_line(db, gid, starter, ip_outs=18, so=5,
                                 bb=2, h=4, r=2, er=1, pitches=85, bf=22,
                                 appearance_order=1, decision="W")
            # Relief: next pitcher in rotation throws relief
            reliever = starters[(i + 1) % 4]
            if reliever != starter:
                _insert_pitching_line(db, gid, reliever, ip_outs=3, so=1,
                                     bb=0, h=1, r=0, er=0, pitches=15, bf=4,
                                     appearance_order=2)

        db.commit()
        self.db = db
        self.team_id = team_id
        self.season_id = season_id

    def test_returns_all_appearances(self, db):
        rows = get_pitching_history(self.team_id, self.season_id, db=db)
        # 12 starts + relief appearances
        assert len(rows) > 12

    def test_row_fields_present(self, db):
        rows = get_pitching_history(self.team_id, self.season_id, db=db)
        required_fields = {
            "player_id", "first_name", "last_name", "jersey_number",
            "game_id", "game_date", "start_time", "ip_outs", "pitches",
            "so", "bb", "h", "r", "er", "bf", "decision",
            "appearance_order", "rest_days", "team_game_number",
        }
        for row in rows:
            assert required_fields.issubset(row.keys()), (
                f"Missing fields: {required_fields - row.keys()}"
            )

    def test_chronological_order(self, db):
        rows = get_pitching_history(self.team_id, self.season_id, db=db)
        dates = [(r["game_date"], r["start_time"]) for r in rows]
        assert dates == sorted(dates, key=lambda x: (x[0], x[1] or ""))

    def test_rest_days_computed(self, db):
        rows = get_pitching_history(self.team_id, self.season_id, db=db)
        p1_rows = [r for r in rows if r["player_id"] == "p1"]
        # First appearance has NULL rest_days
        assert p1_rows[0]["rest_days"] is None
        # Second appearance should have rest_days > 0
        assert p1_rows[1]["rest_days"] is not None
        assert p1_rows[1]["rest_days"] > 0

    def test_team_game_number_sequential(self, db):
        rows = get_pitching_history(self.team_id, self.season_id, db=db)
        game_numbers = sorted(set(r["team_game_number"] for r in rows))
        assert game_numbers == list(range(1, 13))  # 12 games

    def test_doubleheader_distinct_game_numbers(self, db):
        rows = get_pitching_history(self.team_id, self.season_id, db=db)
        # Games g11 and g12 are on the same date, different start_time
        g11_rows = [r for r in rows if r["game_id"] == "g11"]
        g12_rows = [r for r in rows if r["game_id"] == "g12"]
        assert g11_rows[0]["team_game_number"] != g12_rows[0]["team_game_number"]

    def test_same_game_same_game_number(self, db):
        rows = get_pitching_history(self.team_id, self.season_id, db=db)
        # All appearances in the same game share team_game_number
        game_numbers_by_game: dict[str, set[int]] = {}
        for r in rows:
            game_numbers_by_game.setdefault(r["game_id"], set()).add(
                r["team_game_number"]
            )
        for gid, nums in game_numbers_by_game.items():
            assert len(nums) == 1, f"Game {gid} has multiple team_game_numbers: {nums}"

    def test_build_pitcher_profiles_keys(self, db):
        rows = get_pitching_history(self.team_id, self.season_id, db=db)
        profiles = build_pitcher_profiles(rows)
        assert set(profiles.keys()) == {"p1", "p2", "p3", "p4"}
        for pid, prof in profiles.items():
            assert prof["player_id"] == pid
            assert "first_name" in prof
            assert "last_name" in prof
            assert "jersey_number" in prof
            assert "appearances" in prof
            assert "starts" in prof
            assert "total_games" in prof
            assert "total_starts" in prof
            assert "season_ip_outs" in prof
            assert "season_k9" in prof
            assert "start_to_start_rest" in prof

    def test_build_pitcher_profiles_starts(self, db):
        rows = get_pitching_history(self.team_id, self.season_id, db=db)
        profiles = build_pitcher_profiles(rows)
        # Each pitcher starts 3 games in 12-game rotation
        for pid in ["p1", "p2", "p3", "p4"]:
            assert profiles[pid]["total_starts"] == 3

    def test_build_pitcher_profiles_start_to_start_rest(self, db):
        rows = get_pitching_history(self.team_id, self.season_id, db=db)
        profiles = build_pitcher_profiles(rows)
        # p1 starts g01 (Mar 10), g05 (Mar 19), g09 (Mar 28)
        rest = profiles["p1"]["start_to_start_rest"]
        assert len(rest) == 2
        assert rest[0] == 9   # Mar 19 - Mar 10
        assert rest[1] == 9   # Mar 28 - Mar 19

    def test_season_k9_computed(self, db):
        rows = get_pitching_history(self.team_id, self.season_id, db=db)
        profiles = build_pitcher_profiles(rows)
        for prof in profiles.values():
            assert prof["season_k9"] is not None
            assert prof["season_k9"] > 0


# ── AC-5: Single pitcher (all starts) ──────────────────────────────────


class TestSinglePitcher:
    """Test team where one pitcher throws every game."""

    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        team_id, season_id = _seed_season_and_team(db)
        _insert_player(db, "ace", "Iron", "Arm", jersey_number="1")
        for i in range(1, 6):
            gid = f"sg{i:02d}"
            _insert_game(db, gid, f"2026-03-{10 + i * 2}")
            _insert_pitching_line(db, gid, "ace", ip_outs=21, so=7,
                                 bb=1, h=3, r=1, er=1, pitches=95, bf=25,
                                 appearance_order=1, decision="W")
        db.commit()
        self.db = db
        self.team_id = team_id
        self.season_id = season_id

    def test_all_starts(self, db):
        rows = get_pitching_history(self.team_id, self.season_id, db=db)
        profiles = build_pitcher_profiles(rows)
        assert len(profiles) == 1
        prof = profiles["ace"]
        assert prof["total_games"] == 5
        assert prof["total_starts"] == 5
        assert len(prof["start_to_start_rest"]) == 4

    def test_rest_days_pattern(self, db):
        rows = get_pitching_history(self.team_id, self.season_id, db=db)
        # All games are 2 days apart
        for r in rows[1:]:
            assert r["rest_days"] == 2


# ── AC-5: NULL appearance_order rows ───────────────────────────────────


class TestNullAppearanceOrder:
    """Test fallback heuristic when appearance_order is NULL for all rows."""

    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        team_id, season_id = _seed_season_and_team(db)
        _insert_player(db, "sp1", "Star", "Pitcher")
        _insert_player(db, "rp1", "Relief", "Guy")

        for i in range(1, 4):
            gid = f"ng{i:02d}"
            _insert_game(db, gid, f"2026-03-{10 + i * 3}")
            # Starter: more IP
            _insert_pitching_line(db, gid, "sp1", ip_outs=18, so=5,
                                 bb=2, h=4, r=2, er=1,
                                 appearance_order=None)
            # Reliever: less IP
            _insert_pitching_line(db, gid, "rp1", ip_outs=3, so=1,
                                 bb=0, h=1, r=0, er=0,
                                 appearance_order=None)
        db.commit()
        self.db = db
        self.team_id = team_id
        self.season_id = season_id

    def test_fallback_identifies_starters(self, db):
        rows = get_pitching_history(self.team_id, self.season_id, db=db)
        profiles = build_pitcher_profiles(rows)
        # sp1 has more IP in every game -> starter via heuristic
        assert profiles["sp1"]["total_starts"] == 3
        assert profiles["rp1"]["total_starts"] == 0

    def test_start_to_start_rest_with_fallback(self, db):
        rows = get_pitching_history(self.team_id, self.season_id, db=db)
        profiles = build_pitcher_profiles(rows)
        rest = profiles["sp1"]["start_to_start_rest"]
        assert len(rest) == 2
        # Games are 3 days apart
        assert all(r == 3 for r in rest)


# ── AC-5: No completed games (empty result) ───────────────────────────


class TestNoCompletedGames:
    """Test team with no completed games returns empty results."""

    def test_empty_when_no_games(self, db):
        team_id, season_id = _seed_season_and_team(db)
        db.commit()
        rows = get_pitching_history(team_id, season_id, db=db)
        assert rows == []

    def test_empty_profiles_from_empty_history(self):
        profiles = build_pitcher_profiles([])
        assert profiles == {}

    def test_scheduled_games_excluded(self, db):
        team_id, season_id = _seed_season_and_team(db)
        _insert_player(db, "px", "Some", "Pitcher")
        _insert_game(db, "sched1", "2026-03-15", status="scheduled")
        _insert_pitching_line(db, "sched1", "px", ip_outs=18, so=5,
                             appearance_order=1)
        db.commit()
        rows = get_pitching_history(team_id, season_id, db=db)
        assert rows == []


# ── Additional edge cases ──────────────────────────────────────────────


class TestEdgeCases:
    """Additional edge case coverage."""

    def test_season_k9_none_when_zero_ip(self, db):
        team_id, season_id = _seed_season_and_team(db)
        _insert_player(db, "noip", "Zero", "IP")
        _insert_game(db, "zip1", "2026-03-10")
        _insert_pitching_line(db, "zip1", "noip", ip_outs=0, so=0)
        db.commit()
        rows = get_pitching_history(team_id, season_id, db=db)
        profiles = build_pitcher_profiles(rows)
        assert profiles["noip"]["season_k9"] is None

    def test_jersey_number_from_roster(self, db):
        team_id, season_id = _seed_season_and_team(db)
        _insert_player(db, "jn1", "Has", "Jersey", jersey_number="42")
        _insert_game(db, "jg1", "2026-03-10")
        _insert_pitching_line(db, "jg1", "jn1", ip_outs=18, so=5,
                             appearance_order=1)
        db.commit()
        rows = get_pitching_history(team_id, season_id, db=db)
        assert rows[0]["jersey_number"] == "42"

    def test_no_roster_entry_returns_null_jersey(self, db):
        """Player with no roster entry should have jersey_number = None."""
        team_id, season_id = _seed_season_and_team(db)
        # Insert player WITHOUT roster entry
        db.execute(
            "INSERT INTO players (player_id, first_name, last_name) "
            "VALUES ('noroster', 'No', 'Roster')"
        )
        _insert_game(db, "nr1", "2026-03-10")
        _insert_pitching_line(db, "nr1", "noroster", ip_outs=9, so=3,
                             appearance_order=1)
        db.commit()
        rows = get_pitching_history(team_id, season_id, db=db)
        assert rows[0]["jersey_number"] is None

    def test_multi_season_isolation(self, db):
        """Query for one season should not return data from another."""
        team_id, _ = _seed_season_and_team(db, season_id="2026-spring-hs")
        _seed_season_and_team(db, season_id="2025-spring-hs")
        _insert_player(db, "ms1", "Multi", "Season")

        _insert_game(db, "ms_g1", "2026-03-10", season_id="2026-spring-hs")
        _insert_pitching_line(db, "ms_g1", "ms1", ip_outs=18, so=5,
                             appearance_order=1)
        _insert_game(db, "ms_g2", "2025-03-10", season_id="2025-spring-hs")
        _insert_pitching_line(db, "ms_g2", "ms1", ip_outs=15, so=4,
                             appearance_order=1)
        db.commit()

        rows_2026 = get_pitching_history(team_id, "2026-spring-hs", db=db)
        rows_2025 = get_pitching_history(team_id, "2025-spring-hs", db=db)
        assert len(rows_2026) == 1
        assert len(rows_2025) == 1
        assert rows_2026[0]["game_date"] == "2026-03-10"
        assert rows_2025[0]["game_date"] == "2025-03-10"

    def test_rest_days_cross_appearance_types(self, db):
        """Rest days should count from ANY previous appearance, not just starts."""
        team_id, season_id = _seed_season_and_team(db)
        _insert_player(db, "xr1", "Cross", "Rest")

        _insert_game(db, "xr_g1", "2026-03-10")
        _insert_pitching_line(db, "xr_g1", "xr1", ip_outs=18, so=5,
                             appearance_order=1)  # start
        _insert_game(db, "xr_g2", "2026-03-12")
        _insert_pitching_line(db, "xr_g2", "xr1", ip_outs=3, so=1,
                             appearance_order=2)  # relief
        _insert_game(db, "xr_g3", "2026-03-15")
        _insert_pitching_line(db, "xr_g3", "xr1", ip_outs=18, so=5,
                             appearance_order=1)  # start
        db.commit()

        rows = get_pitching_history(team_id, season_id, db=db)
        xr_rows = [r for r in rows if r["player_id"] == "xr1"]
        assert xr_rows[0]["rest_days"] is None      # first appearance
        assert xr_rows[1]["rest_days"] == 2          # Mar 12 - Mar 10
        assert xr_rows[2]["rest_days"] == 3          # Mar 15 - Mar 12 (from relief!)
