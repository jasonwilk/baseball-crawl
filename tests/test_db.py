# synthetic-test-data
"""Tests for src/api/db.py -- E-100 INTEGER PK contract.

Covers AC groups 1-7 (INTEGER team_id parameters), 10-10a (bulk_create_opponents
auto-assigned INTEGER PK and membership_type='tracked'), and AC-11
(_get_permitted_teams returns list[int]).

All tests use an in-memory SQLite database created from migrations/001_initial_schema.sql.
No real DB file is read or written.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Schema fixture
# ---------------------------------------------------------------------------

_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "migrations" / "001_initial_schema.sql"


def _make_db() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the E-100 schema applied."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON;")
    schema_sql = _SCHEMA_PATH.read_text()
    conn.executescript(schema_sql)
    # Migration 004: season_year column on teams (E-147-01).
    conn.execute("ALTER TABLE teams ADD COLUMN season_year INTEGER")
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _insert_program(conn: sqlite3.Connection, program_id: str = "lsb-hs") -> str:
    conn.execute(
        "INSERT OR IGNORE INTO programs (program_id, name, program_type)"
        " VALUES (?, 'Lincoln Standing Bear HS', 'hs')",
        (program_id,),
    )
    conn.commit()
    return program_id


def _insert_team(
    conn: sqlite3.Connection,
    name: str,
    membership_type: str = "member",
    program_id: str | None = None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO teams (name, membership_type, program_id) VALUES (?, ?, ?)",
        (name, membership_type, program_id),
    )
    conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]


def _insert_season(conn: sqlite3.Connection, season_id: str = "2026-spring-hs") -> str:
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year)"
        " VALUES (?, 'Spring 2026 HS', 'spring-hs', 2026)",
        (season_id,),
    )
    conn.commit()
    return season_id


def _insert_player(
    conn: sqlite3.Connection,
    player_id: str,
    first_name: str = "John",
    last_name: str = "Doe",
) -> str:
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (player_id, first_name, last_name),
    )
    conn.commit()
    return player_id


def _insert_game(
    conn: sqlite3.Connection,
    game_id: str,
    season_id: str,
    home_team_id: int,
    away_team_id: int,
    home_score: int | None = None,
    away_score: int | None = None,
    status: str = "completed",
) -> str:
    conn.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id,"
        " home_score, away_score, status)"
        " VALUES (?, ?, '2026-04-01', ?, ?, ?, ?, ?)",
        (game_id, season_id, home_team_id, away_team_id, home_score, away_score, status),
    )
    conn.commit()
    return game_id


def _db_env(tmp_path: Path, conn: sqlite3.Connection) -> dict[str, str]:
    """Write the in-memory DB to a tmp file and return env patch for DATABASE_PATH."""
    db_file = tmp_path / "test.db"
    # Serialize the in-memory DB to disk so db.get_connection() can open it.
    backup_conn = sqlite3.connect(str(db_file))
    conn.backup(backup_conn)
    backup_conn.close()
    return {"DATABASE_PATH": str(db_file)}


# ---------------------------------------------------------------------------
# AC-1 / AC-2: get_team_batting_stats accepts int team_id, JOINs on t.id
# ---------------------------------------------------------------------------


class TestGetTeamBattingStats:
    """AC-1: JOINs use t.id; AC-2: team_id parameter is int."""

    def test_returns_empty_for_unknown_team(self, tmp_path: Path) -> None:
        conn = _make_db()
        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from src.api.db import get_team_batting_stats

            result = get_team_batting_stats(team_id=999, season_id="2026-spring-hs")
        assert result == []

    def test_returns_batting_row_for_correct_integer_team_id(self, tmp_path: Path) -> None:
        conn = _make_db()
        _insert_program(conn)
        season_id = _insert_season(conn)
        team_id = _insert_team(conn, "LSB JV")
        other_team_id = _insert_team(conn, "Opponent A", membership_type="tracked")
        player_id = _insert_player(conn, "player-001")

        # Insert batting stats for team_id
        conn.execute(
            "INSERT INTO player_season_batting (player_id, team_id, season_id, ab, h)"
            " VALUES (?, ?, ?, 20, 6)",
            (player_id, team_id, season_id),
        )
        # Insert batting stats for other_team_id (should NOT appear)
        conn.execute(
            "INSERT INTO player_season_batting (player_id, team_id, season_id, ab, h)"
            " VALUES (?, ?, ?, 10, 3)",
            (player_id, other_team_id, season_id),
        )
        conn.commit()

        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.db as db_module

            reload(db_module)
            result = db_module.get_team_batting_stats(team_id=team_id, season_id=season_id)

        assert len(result) == 1
        assert result[0]["ab"] == 20
        assert result[0]["h"] == 6

    def test_scopes_to_correct_team_not_other(self, tmp_path: Path) -> None:
        """Multi-scope: two teams' stats -- only the queried team's rows returned."""
        conn = _make_db()
        _insert_program(conn)
        season_id = _insert_season(conn)
        team_a = _insert_team(conn, "Team A")
        team_b = _insert_team(conn, "Team B", membership_type="tracked")
        player_a = _insert_player(conn, "p-a", "Alice", "Smith")
        player_b = _insert_player(conn, "p-b", "Bob", "Jones")

        conn.execute(
            "INSERT INTO player_season_batting (player_id, team_id, season_id, ab, h)"
            " VALUES (?, ?, ?, 30, 10)",
            (player_a, team_a, season_id),
        )
        conn.execute(
            "INSERT INTO player_season_batting (player_id, team_id, season_id, ab, h)"
            " VALUES (?, ?, ?, 15, 5)",
            (player_b, team_b, season_id),
        )
        conn.commit()

        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.db as db_module

            reload(db_module)
            result = db_module.get_team_batting_stats(team_id=team_a, season_id=season_id)

        assert len(result) == 1
        assert result[0]["ab"] == 30
        # team_b's player should not appear
        ids = [r["player_id"] for r in result]
        assert "p-b" not in ids


# ---------------------------------------------------------------------------
# AC-3: get_teams_by_ids accepts list[int], queries WHERE id IN (...)
# ---------------------------------------------------------------------------


class TestGetTeamsByIds:
    """AC-3: list[int] parameter, queries by INTEGER id column."""

    def test_empty_list_returns_empty(self, tmp_path: Path) -> None:
        conn = _make_db()
        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from src.api.db import get_teams_by_ids

            result = get_teams_by_ids([])
        assert result == []

    def test_returns_correct_teams_by_integer_ids(self, tmp_path: Path) -> None:
        conn = _make_db()
        tid1 = _insert_team(conn, "LSB Varsity")
        tid2 = _insert_team(conn, "LSB JV")
        _insert_team(conn, "Other Team", membership_type="tracked")

        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.db as db_module

            reload(db_module)
            result = db_module.get_teams_by_ids([tid1, tid2])

        names = {r["name"] for r in result}
        assert names == {"LSB Varsity", "LSB JV"}

    def test_unknown_ids_not_returned(self, tmp_path: Path) -> None:
        conn = _make_db()
        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from src.api.db import get_teams_by_ids

            result = get_teams_by_ids([9998, 9999])
        assert result == []

    def test_result_contains_id_field(self, tmp_path: Path) -> None:
        conn = _make_db()
        tid = _insert_team(conn, "LSB Freshman")
        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.db as db_module

            reload(db_module)
            result = db_module.get_teams_by_ids([tid])

        assert len(result) == 1
        assert result[0]["id"] == tid
        assert result[0]["name"] == "LSB Freshman"


# ---------------------------------------------------------------------------
# AC-4: get_team_pitching_stats and get_team_games accept int team_id
# ---------------------------------------------------------------------------


class TestGetTeamPitchingStats:
    """AC-4: team_id: int parameter for pitching stats."""

    def test_returns_empty_for_unknown_team(self, tmp_path: Path) -> None:
        conn = _make_db()
        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from src.api.db import get_team_pitching_stats

            result = get_team_pitching_stats(team_id=999, season_id="2026-spring-hs")
        assert result == []

    def test_scopes_to_correct_team(self, tmp_path: Path) -> None:
        """Multi-scope: two teams' pitching stats -- only queried team returned."""
        conn = _make_db()
        season_id = _insert_season(conn)
        team_a = _insert_team(conn, "Team A Pitching")
        team_b = _insert_team(conn, "Team B Pitching", membership_type="tracked")
        pitcher_a = _insert_player(conn, "p-pitch-a", "Carl", "Anderson")
        pitcher_b = _insert_player(conn, "p-pitch-b", "Dave", "Brown")

        conn.execute(
            "INSERT INTO player_season_pitching (player_id, team_id, season_id, ip_outs, er)"
            " VALUES (?, ?, ?, 18, 2)",
            (pitcher_a, team_a, season_id),
        )
        conn.execute(
            "INSERT INTO player_season_pitching (player_id, team_id, season_id, ip_outs, er)"
            " VALUES (?, ?, ?, 9, 5)",
            (pitcher_b, team_b, season_id),
        )
        conn.commit()

        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.db as db_module

            reload(db_module)
            result = db_module.get_team_pitching_stats(team_id=team_a, season_id=season_id)

        assert len(result) == 1
        assert result[0]["ip_outs"] == 18
        assert result[0]["player_id"] == "p-pitch-a"


# ---------------------------------------------------------------------------
# AC-1 (E-123-09): dynamic season default for batting and pitching stat functions
# ---------------------------------------------------------------------------


class TestSeasonDefault:
    """Calling batting/pitching stat functions without season_id uses the most recent season."""

    def test_batting_default_uses_most_recent_season(self, tmp_path: Path) -> None:
        """get_team_batting_stats() without season_id selects the most recent season."""
        conn = _make_db()
        _insert_program(conn)
        # Insert two seasons; the newer one should be selected by default.
        _insert_season(conn, "2025-spring-hs")
        _insert_season(conn, "2026-spring-hs")
        team_id = _insert_team(conn, "LSB JV")
        player_id = _insert_player(conn, "p-season-bat")

        conn.execute(
            "INSERT INTO player_season_batting (player_id, team_id, season_id, ab, h)"
            " VALUES (?, ?, ?, 10, 3)",
            (player_id, team_id, "2025-spring-hs"),
        )
        conn.execute(
            "INSERT INTO player_season_batting (player_id, team_id, season_id, ab, h)"
            " VALUES (?, ?, ?, 20, 8)",
            (player_id, team_id, "2026-spring-hs"),
        )
        conn.commit()

        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.db as db_module

            reload(db_module)
            # No season_id argument -- should default to most recent ("2026-spring-hs")
            result = db_module.get_team_batting_stats(team_id=team_id)

        assert len(result) == 1
        assert result[0]["ab"] == 20  # 2026 row, not 2025

    def test_pitching_default_uses_most_recent_season(self, tmp_path: Path) -> None:
        """get_team_pitching_stats() without season_id selects the most recent season."""
        conn = _make_db()
        _insert_program(conn)
        _insert_season(conn, "2025-spring-hs")
        _insert_season(conn, "2026-spring-hs")
        team_id = _insert_team(conn, "LSB JV Pitching")
        player_id = _insert_player(conn, "p-season-pitch")

        conn.execute(
            "INSERT INTO player_season_pitching (player_id, team_id, season_id, ip_outs, er)"
            " VALUES (?, ?, ?, 9, 3)",
            (player_id, team_id, "2025-spring-hs"),
        )
        conn.execute(
            "INSERT INTO player_season_pitching (player_id, team_id, season_id, ip_outs, er)"
            " VALUES (?, ?, ?, 18, 1)",
            (player_id, team_id, "2026-spring-hs"),
        )
        conn.commit()

        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.db as db_module

            reload(db_module)
            # No season_id argument -- should default to most recent ("2026-spring-hs")
            result = db_module.get_team_pitching_stats(team_id=team_id)

        assert len(result) == 1
        assert result[0]["ip_outs"] == 18  # 2026 row, not 2025

    def test_batting_returns_empty_when_no_seasons(self, tmp_path: Path) -> None:
        """get_team_batting_stats() returns [] when seasons table is empty."""
        conn = _make_db()
        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from src.api.db import get_team_batting_stats

            result = get_team_batting_stats(team_id=1)
        assert result == []

    def test_pitching_returns_empty_when_no_seasons(self, tmp_path: Path) -> None:
        """get_team_pitching_stats() returns [] when seasons table is empty."""
        conn = _make_db()
        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from src.api.db import get_team_pitching_stats

            result = get_team_pitching_stats(team_id=1)
        assert result == []


class TestGetTeamGames:
    """AC-4: team_id: int parameter for get_team_games."""

    def test_returns_games_for_correct_integer_team(self, tmp_path: Path) -> None:
        conn = _make_db()
        season_id = _insert_season(conn)
        home_id = _insert_team(conn, "Home Team")
        away_id = _insert_team(conn, "Away Team", membership_type="tracked")
        _insert_game(conn, "game-g1", season_id, home_id, away_id, 5, 3)

        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.db as db_module

            reload(db_module)
            result = db_module.get_team_games(team_id=home_id, season_id=season_id)

        assert len(result) == 1
        assert result[0]["game_id"] == "game-g1"
        assert result[0]["is_home"] == 1

    def test_does_not_return_games_for_other_teams(self, tmp_path: Path) -> None:
        """Multi-scope: only games involving team_id are returned."""
        conn = _make_db()
        season_id = _insert_season(conn)
        team_a = _insert_team(conn, "Team A Games")
        team_b = _insert_team(conn, "Team B Games", membership_type="tracked")
        team_c = _insert_team(conn, "Team C Games", membership_type="tracked")
        # game between B and C -- should NOT appear for team_a
        _insert_game(conn, "game-bc", season_id, team_b, team_c, 1, 2)
        # game between A and B -- SHOULD appear for team_a
        _insert_game(conn, "game-ab", season_id, team_a, team_b, 4, 1)

        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.db as db_module

            reload(db_module)
            result = db_module.get_team_games(team_id=team_a, season_id=season_id)

        game_ids = [r["game_id"] for r in result]
        assert "game-ab" in game_ids
        assert "game-bc" not in game_ids


# ---------------------------------------------------------------------------
# AC-5: get_game_box_score returns INTEGER home/away team ids
# ---------------------------------------------------------------------------


class TestGetGameBoxScore:
    """AC-5: home_team_id and away_team_id in returned game dict are INTEGER."""

    def test_home_and_away_team_ids_are_integers(self, tmp_path: Path) -> None:
        conn = _make_db()
        season_id = _insert_season(conn)
        home_id = _insert_team(conn, "Home Box Team")
        away_id = _insert_team(conn, "Away Box Team", membership_type="tracked")
        _insert_game(conn, "game-box1", season_id, home_id, away_id, 3, 2)

        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.db as db_module

            reload(db_module)
            result = db_module.get_game_box_score("game-box1")

        assert result != {}
        game = result["game"]
        assert isinstance(game["home_team_id"], int)
        assert isinstance(game["away_team_id"], int)
        assert game["home_team_id"] == home_id
        assert game["away_team_id"] == away_id

    def test_returns_empty_dict_for_missing_game(self, tmp_path: Path) -> None:
        conn = _make_db()
        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from src.api.db import get_game_box_score

            result = get_game_box_score("nonexistent-game-id")
        assert result == {}


# ---------------------------------------------------------------------------
# E-131-02: get_game_box_score returns jersey_number via LEFT JOIN team_rosters
# ---------------------------------------------------------------------------


class TestGetGameBoxScoreJerseyNumber:
    """E-131-02 AC-1/AC-2/AC-5/AC-6/AC-7: jersey_number in box score results."""

    def _setup_game_with_rosters(
        self,
        tmp_path: Path,
        *,
        home_jersey: str | None = "12",
        away_jersey: str | None = "7",
        include_home_roster: bool = True,
        include_away_roster: bool = True,
    ) -> tuple[dict, int, int]:
        """Set up a game with member home team and tracked away team.

        Returns (env, home_id, away_id).
        """
        conn = _make_db()
        season_id = _insert_season(conn)
        home_id = _insert_team(conn, "Member Home", membership_type="member")
        away_id = _insert_team(conn, "Tracked Away", membership_type="tracked")
        _insert_game(conn, "jrsy-game-1", season_id, home_id, away_id, 5, 3)

        _insert_player(conn, "jrsy-h-001", "Home", "Batter")
        _insert_player(conn, "jrsy-a-001", "Away", "Batter")

        if include_home_roster:
            conn.execute(
                "INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id, jersey_number)"
                " VALUES (?, ?, ?, ?)",
                (home_id, "jrsy-h-001", season_id, home_jersey),
            )
        if include_away_roster:
            conn.execute(
                "INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id, jersey_number)"
                " VALUES (?, ?, ?, ?)",
                (away_id, "jrsy-a-001", season_id, away_jersey),
            )

        # Batting rows for both teams
        conn.execute(
            "INSERT INTO player_game_batting (game_id, player_id, team_id, ab, h) VALUES (?, ?, ?, ?, ?)",
            ("jrsy-game-1", "jrsy-h-001", home_id, 4, 2),
        )
        conn.execute(
            "INSERT INTO player_game_batting (game_id, player_id, team_id, ab, h) VALUES (?, ?, ?, ?, ?)",
            ("jrsy-game-1", "jrsy-a-001", away_id, 3, 1),
        )
        # Pitching rows for both teams
        conn.execute(
            "INSERT INTO player_game_pitching (game_id, player_id, team_id, ip_outs, so) VALUES (?, ?, ?, ?, ?)",
            ("jrsy-game-1", "jrsy-h-001", home_id, 9, 5),
        )
        conn.execute(
            "INSERT INTO player_game_pitching (game_id, player_id, team_id, ip_outs, so) VALUES (?, ?, ?, ?, ?)",
            ("jrsy-game-1", "jrsy-a-001", away_id, 6, 3),
        )
        conn.commit()
        return _db_env(tmp_path, conn), home_id, away_id

    def test_batting_jersey_number_present_for_member_team(self, tmp_path: Path) -> None:
        """AC-1/AC-6a: jersey_number appears in batting line when roster row exists (member path)."""
        from importlib import reload
        import src.api.db as db_module

        env, home_id, _ = self._setup_game_with_rosters(tmp_path, home_jersey="12")
        with patch.dict(os.environ, env):
            reload(db_module)
            result = db_module.get_game_box_score("jrsy-game-1")

        home_batting = next(t["batting_lines"] for t in result["teams"] if t["id"] == home_id)
        assert len(home_batting) == 1
        assert home_batting[0]["jersey_number"] == "12"

    def test_batting_jersey_number_present_for_tracked_team(self, tmp_path: Path) -> None:
        """AC-1/AC-7: jersey_number appears in batting line when scouting-loaded roster row exists."""
        from importlib import reload
        import src.api.db as db_module

        env, _, away_id = self._setup_game_with_rosters(tmp_path, away_jersey="7")
        with patch.dict(os.environ, env):
            reload(db_module)
            result = db_module.get_game_box_score("jrsy-game-1")

        away_batting = next(t["batting_lines"] for t in result["teams"] if t["id"] == away_id)
        assert len(away_batting) == 1
        assert away_batting[0]["jersey_number"] == "7"

    def test_batting_jersey_number_none_when_no_roster_row(self, tmp_path: Path) -> None:
        """AC-5/AC-6b: jersey_number is None (not missing key) when no roster row exists."""
        from importlib import reload
        import src.api.db as db_module

        env, _, away_id = self._setup_game_with_rosters(
            tmp_path, include_away_roster=False
        )
        with patch.dict(os.environ, env):
            reload(db_module)
            result = db_module.get_game_box_score("jrsy-game-1")

        away_batting = next(t["batting_lines"] for t in result["teams"] if t["id"] == away_id)
        assert len(away_batting) == 1
        assert "jersey_number" in away_batting[0]
        assert away_batting[0]["jersey_number"] is None

    def test_batting_no_rows_lost_without_roster(self, tmp_path: Path) -> None:
        """AC-5: LEFT JOIN does not drop batting rows when roster row is absent."""
        from importlib import reload
        import src.api.db as db_module

        env, home_id, away_id = self._setup_game_with_rosters(
            tmp_path, include_home_roster=False, include_away_roster=False
        )
        with patch.dict(os.environ, env):
            reload(db_module)
            result = db_module.get_game_box_score("jrsy-game-1")

        home_batting = next(t["batting_lines"] for t in result["teams"] if t["id"] == home_id)
        away_batting = next(t["batting_lines"] for t in result["teams"] if t["id"] == away_id)
        assert len(home_batting) == 1
        assert len(away_batting) == 1

    def test_pitching_jersey_number_present_for_member_team(self, tmp_path: Path) -> None:
        """AC-2/AC-6a: jersey_number appears in pitching line when roster row exists (member path)."""
        from importlib import reload
        import src.api.db as db_module

        env, home_id, _ = self._setup_game_with_rosters(tmp_path, home_jersey="12")
        with patch.dict(os.environ, env):
            reload(db_module)
            result = db_module.get_game_box_score("jrsy-game-1")

        home_pitching = next(t["pitching_lines"] for t in result["teams"] if t["id"] == home_id)
        assert len(home_pitching) == 1
        assert home_pitching[0]["jersey_number"] == "12"

    def test_pitching_jersey_number_present_for_tracked_team(self, tmp_path: Path) -> None:
        """AC-2/AC-7: jersey_number appears in pitching line when scouting-loaded roster row exists."""
        from importlib import reload
        import src.api.db as db_module

        env, _, away_id = self._setup_game_with_rosters(tmp_path, away_jersey="7")
        with patch.dict(os.environ, env):
            reload(db_module)
            result = db_module.get_game_box_score("jrsy-game-1")

        away_pitching = next(t["pitching_lines"] for t in result["teams"] if t["id"] == away_id)
        assert len(away_pitching) == 1
        assert away_pitching[0]["jersey_number"] == "7"

    def test_pitching_jersey_number_none_when_no_roster_row(self, tmp_path: Path) -> None:
        """AC-5/AC-6b: jersey_number is None in pitching line when no roster row."""
        from importlib import reload
        import src.api.db as db_module

        env, _, away_id = self._setup_game_with_rosters(
            tmp_path, include_away_roster=False
        )
        with patch.dict(os.environ, env):
            reload(db_module)
            result = db_module.get_game_box_score("jrsy-game-1")

        away_pitching = next(t["pitching_lines"] for t in result["teams"] if t["id"] == away_id)
        assert len(away_pitching) == 1
        assert "jersey_number" in away_pitching[0]
        assert away_pitching[0]["jersey_number"] is None

    def test_dual_path_both_teams_same_box_score(self, tmp_path: Path) -> None:
        """AC-7: member team (roster-loaded) and tracked team (scouting-loaded) in same game."""
        from importlib import reload
        import src.api.db as db_module

        # home = member team with jersey, away = tracked with jersey
        env, home_id, away_id = self._setup_game_with_rosters(
            tmp_path, home_jersey="42", away_jersey="99"
        )
        with patch.dict(os.environ, env):
            reload(db_module)
            result = db_module.get_game_box_score("jrsy-game-1")

        home_batting = next(t["batting_lines"] for t in result["teams"] if t["id"] == home_id)
        away_batting = next(t["batting_lines"] for t in result["teams"] if t["id"] == away_id)
        assert home_batting[0]["jersey_number"] == "42"
        assert away_batting[0]["jersey_number"] == "99"


# ---------------------------------------------------------------------------
# AC-6: get_opponent_scouting_report and get_last_meeting accept int team_id
# ---------------------------------------------------------------------------


class TestGetOpponentScoutingReport:
    """AC-6: opponent_team_id: int for scouting report."""

    def test_returns_empty_for_unknown_opponent(self, tmp_path: Path) -> None:
        conn = _make_db()
        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from src.api.db import get_opponent_scouting_report

            result = get_opponent_scouting_report(opponent_team_id=999, season_id="2026-spring-hs")
        # returns {} on empty (no team found)
        assert result == {} or result.get("batting") == []

    def test_returns_batting_and_pitching_for_integer_opponent(self, tmp_path: Path) -> None:
        conn = _make_db()
        season_id = _insert_season(conn)
        opp_id = _insert_team(conn, "Scout Target", membership_type="tracked")
        batter_id = _insert_player(conn, "p-scout-bat", "Eve", "Garcia")
        pitcher_id = _insert_player(conn, "p-scout-pit", "Frank", "Torres")

        conn.execute(
            "INSERT INTO player_season_batting (player_id, team_id, season_id, ab, h)"
            " VALUES (?, ?, ?, 12, 4)",
            (batter_id, opp_id, season_id),
        )
        conn.execute(
            "INSERT INTO player_season_pitching (player_id, team_id, season_id, ip_outs, er, so)"
            " VALUES (?, ?, ?, 9, 2, 8)",
            (pitcher_id, opp_id, season_id),
        )
        conn.commit()

        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.db as db_module

            reload(db_module)
            result = db_module.get_opponent_scouting_report(
                opponent_team_id=opp_id, season_id=season_id
            )

        assert result["team_name"] == "Scout Target"
        assert len(result["batting"]) == 1
        assert result["batting"][0]["ab"] == 12
        assert len(result["pitching"]) == 1
        assert result["pitching"][0]["ip_outs"] == 9
        assert result["pitching"][0]["er"] == 2
        assert result["pitching"][0]["so"] == 8


class TestGetOpponentScoutingReportJerseyNumber:
    """E-131-03 AC-1/AC-2/AC-5/AC-6/AC-7: jersey_number in scouting report results."""

    def _setup_scouting_db(
        self,
        tmp_path: Path,
        team_membership: str = "tracked",
        jersey: str | None = "33",
        include_roster: bool = True,
    ) -> tuple[dict, int]:
        """Set up a team with batting/pitching stats and optional roster entry.

        Returns (env, team_id).
        """
        conn = _make_db()
        season_id = _insert_season(conn)
        team_id = _insert_team(conn, "Scouted Team", membership_type=team_membership)
        player_id = _insert_player(conn, "scout-p-001", "Scout", "Player")

        if include_roster:
            conn.execute(
                "INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id, jersey_number)"
                " VALUES (?, ?, ?, ?)",
                (team_id, player_id, season_id, jersey),
            )
        conn.execute(
            "INSERT INTO player_season_batting (player_id, team_id, season_id, ab, h)"
            " VALUES (?, ?, ?, 10, 3)",
            (player_id, team_id, season_id),
        )
        conn.execute(
            "INSERT INTO player_season_pitching (player_id, team_id, season_id, ip_outs, er, so)"
            " VALUES (?, ?, ?, 9, 2, 7)",
            (player_id, team_id, season_id),
        )
        conn.commit()
        return _db_env(tmp_path, conn), team_id

    def test_batting_jersey_present_for_tracked_team(self, tmp_path: Path) -> None:
        """AC-1/AC-6a/AC-7a: jersey_number in batting row for tracked team (scouting path)."""
        from importlib import reload
        import src.api.db as db_module

        env, team_id = self._setup_scouting_db(tmp_path, team_membership="tracked", jersey="33")
        with patch.dict(os.environ, env):
            reload(db_module)
            result = db_module.get_opponent_scouting_report(
                opponent_team_id=team_id, season_id="2026-spring-hs"
            )

        assert len(result["batting"]) == 1
        assert result["batting"][0]["jersey_number"] == "33"

    def test_batting_jersey_present_for_member_team(self, tmp_path: Path) -> None:
        """AC-1/AC-7b: jersey_number in batting row when queried for member team_id."""
        from importlib import reload
        import src.api.db as db_module

        env, team_id = self._setup_scouting_db(tmp_path, team_membership="member", jersey="88")
        with patch.dict(os.environ, env):
            reload(db_module)
            result = db_module.get_opponent_scouting_report(
                opponent_team_id=team_id, season_id="2026-spring-hs"
            )

        assert len(result["batting"]) == 1
        assert result["batting"][0]["jersey_number"] == "88"

    def test_batting_jersey_none_when_no_roster_row(self, tmp_path: Path) -> None:
        """AC-5/AC-6b: jersey_number is None (not missing key) when no roster row."""
        from importlib import reload
        import src.api.db as db_module

        env, team_id = self._setup_scouting_db(tmp_path, include_roster=False)
        with patch.dict(os.environ, env):
            reload(db_module)
            result = db_module.get_opponent_scouting_report(
                opponent_team_id=team_id, season_id="2026-spring-hs"
            )

        assert len(result["batting"]) == 1
        assert "jersey_number" in result["batting"][0]
        assert result["batting"][0]["jersey_number"] is None

    def test_batting_no_rows_lost_without_roster(self, tmp_path: Path) -> None:
        """AC-5: LEFT JOIN does not drop batting rows when roster row is absent."""
        from importlib import reload
        import src.api.db as db_module

        env, team_id = self._setup_scouting_db(tmp_path, include_roster=False)
        with patch.dict(os.environ, env):
            reload(db_module)
            result = db_module.get_opponent_scouting_report(
                opponent_team_id=team_id, season_id="2026-spring-hs"
            )

        assert len(result["batting"]) == 1

    def test_pitching_jersey_present_for_tracked_team(self, tmp_path: Path) -> None:
        """AC-2/AC-6a/AC-7a: jersey_number in pitching row for tracked team."""
        from importlib import reload
        import src.api.db as db_module

        env, team_id = self._setup_scouting_db(tmp_path, team_membership="tracked", jersey="33")
        with patch.dict(os.environ, env):
            reload(db_module)
            result = db_module.get_opponent_scouting_report(
                opponent_team_id=team_id, season_id="2026-spring-hs"
            )

        assert len(result["pitching"]) == 1
        assert result["pitching"][0]["jersey_number"] == "33"

    def test_pitching_jersey_present_for_member_team(self, tmp_path: Path) -> None:
        """AC-2/AC-7b: jersey_number in pitching row when queried for member team_id."""
        from importlib import reload
        import src.api.db as db_module

        env, team_id = self._setup_scouting_db(tmp_path, team_membership="member", jersey="88")
        with patch.dict(os.environ, env):
            reload(db_module)
            result = db_module.get_opponent_scouting_report(
                opponent_team_id=team_id, season_id="2026-spring-hs"
            )

        assert len(result["pitching"]) == 1
        assert result["pitching"][0]["jersey_number"] == "88"

    def test_pitching_jersey_none_when_no_roster_row(self, tmp_path: Path) -> None:
        """AC-5/AC-6b: jersey_number is None in pitching row when no roster row."""
        from importlib import reload
        import src.api.db as db_module

        env, team_id = self._setup_scouting_db(tmp_path, include_roster=False)
        with patch.dict(os.environ, env):
            reload(db_module)
            result = db_module.get_opponent_scouting_report(
                opponent_team_id=team_id, season_id="2026-spring-hs"
            )

        assert len(result["pitching"]) == 1
        assert "jersey_number" in result["pitching"][0]
        assert result["pitching"][0]["jersey_number"] is None

    def test_pitching_no_rows_lost_without_roster(self, tmp_path: Path) -> None:
        """AC-5: LEFT JOIN does not drop pitching rows when roster row is absent."""
        from importlib import reload
        import src.api.db as db_module

        env, team_id = self._setup_scouting_db(tmp_path, include_roster=False)
        with patch.dict(os.environ, env):
            reload(db_module)
            result = db_module.get_opponent_scouting_report(
                opponent_team_id=team_id, season_id="2026-spring-hs"
            )

        assert len(result["pitching"]) == 1


class TestGetLastMeeting:
    """AC-6: team_id and opponent_team_id: int for last meeting."""

    def test_returns_none_when_no_completed_game(self, tmp_path: Path) -> None:
        conn = _make_db()
        season_id = _insert_season(conn)
        team_id = _insert_team(conn, "My Team LM")
        opp_id = _insert_team(conn, "Opponent LM", membership_type="tracked")

        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.db as db_module

            reload(db_module)
            result = db_module.get_last_meeting(
                team_id=team_id, opponent_team_id=opp_id, season_id=season_id
            )
        assert result is None

    def test_returns_most_recent_completed_game(self, tmp_path: Path) -> None:
        conn = _make_db()
        season_id = _insert_season(conn)
        team_id = _insert_team(conn, "Team LM Home")
        opp_id = _insert_team(conn, "Opponent LM Home", membership_type="tracked")
        _insert_game(conn, "lm-game1", season_id, team_id, opp_id, 5, 2)

        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.db as db_module

            reload(db_module)
            result = db_module.get_last_meeting(
                team_id=team_id, opponent_team_id=opp_id, season_id=season_id
            )
        assert result is not None
        assert result["game_id"] == "lm-game1"
        assert result["is_home"] == 1


# ---------------------------------------------------------------------------
# AC-7: get_opponent_link_count_for_team accepts int our_team_id
# ---------------------------------------------------------------------------


class TestGetOpponentLinkCountForTeam:
    """AC-7: our_team_id: int for opponent link functions."""

    def test_returns_zero_for_unknown_team(self, tmp_path: Path) -> None:
        conn = _make_db()
        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from src.api.db import get_opponent_link_count_for_team

            result = get_opponent_link_count_for_team(our_team_id=999)
        assert result == 0

    def test_counts_links_for_correct_integer_team(self, tmp_path: Path) -> None:
        conn = _make_db()
        team_id = _insert_team(conn, "Link Owner Team")
        # Insert two opponent_links rows for team_id
        for name in ("Opp Alpha", "Opp Beta"):
            conn.execute(
                "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name)"
                " VALUES (?, ?, ?)",
                (team_id, f"root-{name}", name),
            )
        conn.commit()

        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.db as db_module

            reload(db_module)
            result = db_module.get_opponent_link_count_for_team(our_team_id=team_id)
        assert result == 2

    def test_does_not_count_other_teams_links(self, tmp_path: Path) -> None:
        """Multi-scope: links for a different team are not counted."""
        conn = _make_db()
        team_a = _insert_team(conn, "Link Team A")
        team_b = _insert_team(conn, "Link Team B", membership_type="tracked")
        # Insert 3 links for team_b -- should NOT be counted for team_a
        for i in range(3):
            conn.execute(
                "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name)"
                " VALUES (?, ?, ?)",
                (team_b, f"root-b-{i}", f"Opp B{i}"),
            )
        conn.commit()

        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.db as db_module

            reload(db_module)
            result = db_module.get_opponent_link_count_for_team(our_team_id=team_a)
        assert result == 0


# ---------------------------------------------------------------------------
# AC-10 / AC-10a: bulk_create_opponents uses membership_type='tracked',
#                 INTEGER PK auto-assigned
# ---------------------------------------------------------------------------


class TestBulkCreateOpponents:
    """AC-10: membership_type='tracked'; AC-10a: INTEGER PK auto-assigned."""

    def test_inserts_new_names_with_tracked_membership_type(self, tmp_path: Path) -> None:
        conn = _make_db()
        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from src.api.db import bulk_create_opponents

            count = bulk_create_opponents(["Apex Warriors", "Blue Thunder"])
        assert count == 2

        # Verify in the written DB
        db_path = env["DATABASE_PATH"]
        verify_conn = sqlite3.connect(db_path)
        verify_conn.row_factory = sqlite3.Row
        rows = verify_conn.execute(
            "SELECT id, name, membership_type, is_active, source FROM teams WHERE name IN (?, ?)",
            ("Apex Warriors", "Blue Thunder"),
        ).fetchall()
        verify_conn.close()

        assert len(rows) == 2
        for row in rows:
            r = dict(row)
            assert r["membership_type"] == "tracked"
            assert isinstance(r["id"], int), "id should be an INTEGER"
            assert r["id"] > 0, "id should be auto-assigned positive integer"
            assert r["is_active"] == 0, "bulk_create_opponents should set is_active=0"
            assert r["source"] == "discovered", "bulk_create_opponents should set source='discovered'"

    def test_does_not_insert_duplicates(self, tmp_path: Path) -> None:
        conn = _make_db()
        _insert_team(conn, "Existing Team", membership_type="tracked")
        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.db as db_module

            reload(db_module)
            # "Existing Team" already exists; only "New Team" is new
            count = db_module.bulk_create_opponents(["Existing Team", "New Team"])
        assert count == 1

    def test_auto_assigned_ids_are_distinct_integers(self, tmp_path: Path) -> None:
        conn = _make_db()
        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.db as db_module

            reload(db_module)
            db_module.bulk_create_opponents(["Team X", "Team Y", "Team Z"])

        db_path = env["DATABASE_PATH"]
        verify_conn = sqlite3.connect(db_path)
        rows = verify_conn.execute(
            "SELECT id FROM teams WHERE name IN ('Team X', 'Team Y', 'Team Z')"
        ).fetchall()
        verify_conn.close()

        ids = [r[0] for r in rows]
        assert len(ids) == 3
        assert len(set(ids)) == 3, "All auto-assigned IDs should be distinct"
        assert all(isinstance(i, int) and i > 0 for i in ids)

    def test_empty_list_inserts_nothing(self, tmp_path: Path) -> None:
        conn = _make_db()
        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from src.api.db import bulk_create_opponents

            count = bulk_create_opponents([])
        assert count == 0


# ---------------------------------------------------------------------------
# AC-11: _get_permitted_teams returns list[int]
# ---------------------------------------------------------------------------


class TestGetPermittedTeams:
    """AC-11: _get_permitted_teams in src.api.auth returns list[int]."""

    def _make_in_memory_db_with_access(self) -> tuple[sqlite3.Connection, int, int]:
        """Return (conn, user_id, team_id) with a user_team_access row."""
        conn = _make_db()
        cursor = conn.execute("INSERT INTO users (email) VALUES ('tester@test.com')")
        conn.commit()
        user_id: int = cursor.lastrowid  # type: ignore[assignment]

        team_id = _insert_team(conn, "Access Team")

        conn.execute(
            "INSERT INTO user_team_access (user_id, team_id) VALUES (?, ?)",
            (user_id, team_id),
        )
        conn.commit()
        return conn, user_id, team_id

    def test_returns_list_of_int(self, tmp_path: Path) -> None:
        conn, user_id, team_id = self._make_in_memory_db_with_access()
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.auth as auth_module

            reload(auth_module)
            with closing(auth_module.get_connection()) as db_conn:
                db_conn.row_factory = sqlite3.Row
                result = auth_module._get_permitted_teams(
                    db_conn, {"id": user_id, "email": "tester@test.com"}
                )

        assert isinstance(result, list)
        assert all(isinstance(tid, int) for tid in result), "All team ids must be int"
        assert team_id in result

    def test_returns_empty_list_for_user_with_no_access(self, tmp_path: Path) -> None:
        conn = _make_db()
        cursor = conn.execute("INSERT INTO users (email) VALUES ('nobody@test.com')")
        conn.commit()
        user_id: int = cursor.lastrowid  # type: ignore[assignment]

        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.auth as auth_module

            reload(auth_module)
            with closing(auth_module.get_connection()) as db_conn:
                db_conn.row_factory = sqlite3.Row
                result = auth_module._get_permitted_teams(
                    db_conn, {"id": user_id, "email": "nobody@test.com"}
                )

        assert result == []

    def test_multiple_team_ids_all_returned_as_int(self, tmp_path: Path) -> None:
        conn = _make_db()
        cursor = conn.execute("INSERT INTO users (email) VALUES ('multi@test.com')")
        conn.commit()
        user_id: int = cursor.lastrowid  # type: ignore[assignment]

        tid1 = _insert_team(conn, "Multi Team 1")
        tid2 = _insert_team(conn, "Multi Team 2")
        tid3 = _insert_team(conn, "Multi Team 3")

        for tid in (tid1, tid2, tid3):
            conn.execute(
                "INSERT INTO user_team_access (user_id, team_id) VALUES (?, ?)",
                (user_id, tid),
            )
        conn.commit()

        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, env):
            from importlib import reload

            import src.api.auth as auth_module

            reload(auth_module)
            with closing(auth_module.get_connection()) as db_conn:
                db_conn.row_factory = sqlite3.Row
                result = auth_module._get_permitted_teams(
                    db_conn, {"id": user_id, "email": "multi@test.com"}
                )

        assert sorted(result) == sorted([tid1, tid2, tid3])
        assert all(isinstance(t, int) for t in result)


# ---------------------------------------------------------------------------
# get_db_path -- default path resolution (E-116-02)
# ---------------------------------------------------------------------------


class TestGetDbPathDefault:
    """Verify that the default database path is absolute and repo-root-relative."""

    def test_default_path_is_absolute(self) -> None:
        """Default path must be absolute, not cwd-relative."""
        import src.api.db as db_module

        with patch.dict(os.environ, {}, clear=False):
            # Remove DATABASE_PATH if set so the default is used
            env_without_db_path = {
                k: v for k, v in os.environ.items() if k != "DATABASE_PATH"
            }
            with patch.dict(os.environ, env_without_db_path, clear=True):
                path = db_module.get_db_path()

        assert path.is_absolute(), f"Expected absolute path, got: {path}"

    def test_default_path_ends_with_data_app_db(self) -> None:
        """Default path must end with data/app.db."""
        import src.api.db as db_module

        env_without_db_path = {
            k: v for k, v in os.environ.items() if k != "DATABASE_PATH"
        }
        with patch.dict(os.environ, env_without_db_path, clear=True):
            path = db_module.get_db_path()

        assert path.parts[-2:] == ("data", "app.db"), (
            f"Expected path ending in data/app.db, got: {path}"
        )

    def test_database_path_env_takes_precedence(self, tmp_path: Path) -> None:
        """When DATABASE_PATH is set, it overrides the default."""
        import src.api.db as db_module

        custom_path = tmp_path / "custom.db"
        with patch.dict(os.environ, {"DATABASE_PATH": str(custom_path)}):
            path = db_module.get_db_path()

        assert path == custom_path.resolve()


# ---------------------------------------------------------------------------
# E-142-02: get_team_year_map fallback and get_teams_with_stat_data
# ---------------------------------------------------------------------------


class TestGetTeamYearMapFallback:
    """get_team_year_map reads teams.season_year, falls back to current year for NULLs.

    Updated for E-147-01: function now reads from teams.season_year column
    instead of deriving years from stat tables.
    """

    def test_no_season_year_returns_current_year(self, tmp_path: Path) -> None:
        """Team with NULL season_year maps to the current calendar year."""
        import datetime

        conn = _make_db()
        team_id = _insert_team(conn, "No Year Team")
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from src.api.db import get_team_year_map

            result = get_team_year_map([team_id])

        assert team_id in result
        assert result[team_id] == datetime.date.today().year

    def test_team_with_season_year_returns_that_year(self, tmp_path: Path) -> None:
        """Team with explicit season_year returns that value, not the fallback."""
        conn = _make_db()
        team_id = _insert_team(conn, "Data Team")
        conn.execute("UPDATE teams SET season_year = 2025 WHERE id = ?", (team_id,))
        conn.commit()
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from src.api.db import get_team_year_map

            result = get_team_year_map([team_id])

        assert result[team_id] == 2025

    def test_mixed_teams_use_set_and_fallback_years(self, tmp_path: Path) -> None:
        """Mix of set and NULL season_year: set team gets its year, NULL gets current."""
        import datetime

        conn = _make_db()
        data_team = _insert_team(conn, "Has Year")
        no_data_team = _insert_team(conn, "No Year")
        conn.execute("UPDATE teams SET season_year = 2025 WHERE id = ?", (data_team,))
        conn.commit()
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from src.api.db import get_team_year_map

            result = get_team_year_map([data_team, no_data_team])

        assert result[data_team] == 2025
        assert result[no_data_team] == datetime.date.today().year

    def test_all_null_teams_include_current_year_in_values(self, tmp_path: Path) -> None:
        """When all teams have NULL season_year, the current year appears in result values."""
        import datetime

        conn = _make_db()
        team_a = _insert_team(conn, "Team A")
        team_b = _insert_team(conn, "Team B")
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from src.api.db import get_team_year_map

            result = get_team_year_map([team_a, team_b])

        current_year = datetime.date.today().year
        assert current_year in result.values()

    def test_empty_input_returns_empty_dict(self, tmp_path: Path) -> None:
        """Empty team_ids returns empty dict without hitting the DB."""
        conn = _make_db()
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from src.api.db import get_team_year_map

            result = get_team_year_map([])

        assert result == {}


class TestGetTeamsWithStatData:
    """get_teams_with_stat_data returns only teams with actual stat rows (E-142-02 AC-5)."""

    def test_team_with_batting_row_is_included(self, tmp_path: Path) -> None:
        """Team with a player_season_batting row is in the result set."""
        conn = _make_db()
        team_id = _insert_team(conn, "Batting Team")
        season_id = _insert_season(conn)
        player_id = _insert_player(conn, "p-bat")
        conn.execute(
            "INSERT INTO player_season_batting (player_id, team_id, season_id, ab, h)"
            " VALUES (?, ?, ?, 5, 2)",
            (player_id, team_id, season_id),
        )
        conn.commit()
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from src.api.db import get_teams_with_stat_data

            result = get_teams_with_stat_data([team_id])

        assert team_id in result

    def test_team_with_pitching_row_is_included(self, tmp_path: Path) -> None:
        """Team with a player_season_pitching row is in the result set."""
        conn = _make_db()
        team_id = _insert_team(conn, "Pitching Team")
        season_id = _insert_season(conn)
        player_id = _insert_player(conn, "p-pitch")
        conn.execute(
            "INSERT INTO player_season_pitching (player_id, team_id, season_id, ip_outs, er)"
            " VALUES (?, ?, ?, 9, 2)",
            (player_id, team_id, season_id),
        )
        conn.commit()
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from src.api.db import get_teams_with_stat_data

            result = get_teams_with_stat_data([team_id])

        assert team_id in result

    def test_team_with_no_stat_rows_is_excluded(self, tmp_path: Path) -> None:
        """Team with no stat rows is NOT in the result set."""
        conn = _make_db()
        team_id = _insert_team(conn, "Empty Team")
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from src.api.db import get_teams_with_stat_data

            result = get_teams_with_stat_data([team_id])

        assert team_id not in result

    def test_only_teams_with_stat_data_included_in_mixed_list(self, tmp_path: Path) -> None:
        """Only teams with stat rows appear when passing a mixed list."""
        conn = _make_db()
        data_team = _insert_team(conn, "Data Team")
        empty_team = _insert_team(conn, "Empty Team")
        season_id = _insert_season(conn)
        player_id = _insert_player(conn, "p-only")
        conn.execute(
            "INSERT INTO player_season_batting (player_id, team_id, season_id, ab, h)"
            " VALUES (?, ?, ?, 8, 2)",
            (player_id, data_team, season_id),
        )
        conn.commit()
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from src.api.db import get_teams_with_stat_data

            result = get_teams_with_stat_data([data_team, empty_team])

        assert data_team in result
        assert empty_team not in result

    def test_empty_input_returns_empty_set(self, tmp_path: Path) -> None:
        """Empty team_ids returns empty set without hitting the DB."""
        conn = _make_db()
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from src.api.db import get_teams_with_stat_data

            result = get_teams_with_stat_data([])

        assert result == set()


# ---------------------------------------------------------------------------
# E-142-04: get_team_opponents UNION fallback from team_opponents
# ---------------------------------------------------------------------------


def _insert_team_opponent(
    conn: sqlite3.Connection,
    our_team_id: int,
    opponent_team_id: int,
    first_seen_year: int,
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO team_opponents (our_team_id, opponent_team_id, first_seen_year)"
        " VALUES (?, ?, ?)",
        (our_team_id, opponent_team_id, first_seen_year),
    )
    conn.commit()


class TestGetTeamOpponentsUnionFallback:
    """get_team_opponents includes team_opponents rows when no game data exists (E-142-04)."""

    _SEASON = "2026-spring-hs"
    _YEAR = 2026

    def _setup_teams(self, conn: sqlite3.Connection) -> tuple[int, int]:
        """Insert a member team and a tracked opponent; return (our_id, opponent_id)."""
        our_id = _insert_team(conn, "LSB Varsity", membership_type="member")
        opp_id = _insert_team(conn, "Rival Hawks", membership_type="tracked")
        return our_id, opp_id

    def test_junction_only_opponent_appears(self, tmp_path: Path) -> None:
        """Opponent in team_opponents but no game row appears in result (AC-1, AC-2)."""
        conn = _make_db()
        our_id, opp_id = self._setup_teams(conn)
        _insert_team_opponent(conn, our_id, opp_id, self._YEAR)
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from src.api.db import get_team_opponents

            result = get_team_opponents(our_id, self._SEASON)

        assert len(result) == 1
        row = result[0]
        assert row["opponent_team_id"] == opp_id
        assert row["opponent_name"] == "Rival Hawks"
        assert row["games_played"] == 0
        assert row["wins"] == 0
        assert row["losses"] == 0
        assert row["next_game_date"] is None
        assert row["last_game_date"] is None

    def test_games_only_opponent_appears_with_full_stats(self, tmp_path: Path) -> None:
        """Opponent with game data appears with real stats (AC-6 regression guard)."""
        conn = _make_db()
        our_id, opp_id = self._setup_teams(conn)
        _insert_season(conn, self._SEASON)
        _insert_game(conn, "g-001", self._SEASON, our_id, opp_id, home_score=5, away_score=2)
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from src.api.db import get_team_opponents

            result = get_team_opponents(our_id, self._SEASON)

        assert len(result) == 1
        row = result[0]
        assert row["games_played"] == 1
        assert row["wins"] == 1
        assert row["losses"] == 0

    def test_opponent_in_both_sources_not_duplicated(self, tmp_path: Path) -> None:
        """Opponent in both games and team_opponents appears once with game stats (AC-3)."""
        conn = _make_db()
        our_id, opp_id = self._setup_teams(conn)
        _insert_season(conn, self._SEASON)
        _insert_game(conn, "g-002", self._SEASON, our_id, opp_id, home_score=3, away_score=4)
        _insert_team_opponent(conn, our_id, opp_id, self._YEAR)
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from src.api.db import get_team_opponents

            result = get_team_opponents(our_id, self._SEASON)

        # Must be exactly one row, with game-based stats (not zero)
        assert len(result) == 1
        assert result[0]["games_played"] == 1
        assert result[0]["losses"] == 1

    def test_first_seen_year_filters_out_wrong_year(self, tmp_path: Path) -> None:
        """team_opponents row with wrong first_seen_year is excluded (AC-4)."""
        conn = _make_db()
        our_id, opp_id = self._setup_teams(conn)
        # Link with prior year -- should NOT appear in 2026 season query
        _insert_team_opponent(conn, our_id, opp_id, self._YEAR - 1)
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from src.api.db import get_team_opponents

            result = get_team_opponents(our_id, self._SEASON)

        assert result == []

    def test_first_seen_year_matches_correct_year(self, tmp_path: Path) -> None:
        """team_opponents row with matching first_seen_year is included (AC-4)."""
        conn = _make_db()
        our_id, opp_id = self._setup_teams(conn)
        _insert_team_opponent(conn, our_id, opp_id, self._YEAR)
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from src.api.db import get_team_opponents

            result = get_team_opponents(our_id, self._SEASON)

        assert len(result) == 1
        assert result[0]["opponent_team_id"] == opp_id

    def test_multiple_junction_opponents_all_appear(self, tmp_path: Path) -> None:
        """Multiple team_opponents entries all appear when none have game data."""
        conn = _make_db()
        our_id = _insert_team(conn, "LSB Varsity", membership_type="member")
        opp_a = _insert_team(conn, "Alpha Wolves", membership_type="tracked")
        opp_b = _insert_team(conn, "Beta Bears", membership_type="tracked")
        _insert_team_opponent(conn, our_id, opp_a, self._YEAR)
        _insert_team_opponent(conn, our_id, opp_b, self._YEAR)
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from src.api.db import get_team_opponents

            result = get_team_opponents(our_id, self._SEASON)

        opp_ids = {r["opponent_team_id"] for r in result}
        assert opp_a in opp_ids
        assert opp_b in opp_ids
        assert len(result) == 2


# ---------------------------------------------------------------------------
# get_team_year_map tests (E-147-01)
# ---------------------------------------------------------------------------


class TestGetTeamYearMap:
    """Tests for get_team_year_map reading from teams.season_year."""

    def test_returns_season_year_when_set(self, tmp_path: Path) -> None:
        """AC-4a: returns season_year when the column has a value."""
        conn = _make_db()
        tid = _insert_team(conn, "LSB Varsity")
        conn.execute("UPDATE teams SET season_year = 2025 WHERE id = ?", (tid,))
        conn.commit()
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from src.api.db import get_team_year_map

            result = get_team_year_map([tid])

        assert result[tid] == 2025

    def test_falls_back_to_current_year_when_null(self, tmp_path: Path) -> None:
        """AC-4b: returns current calendar year when season_year is NULL."""
        conn = _make_db()
        tid = _insert_team(conn, "LSB JV")
        # season_year defaults to NULL -- don't set it.
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from src.api.db import get_team_year_map

            result = get_team_year_map([tid])

        import datetime

        assert result[tid] == datetime.date.today().year

    def test_empty_input_returns_empty_dict(self, tmp_path: Path) -> None:
        """AC-4c: empty input → empty dict (no DB hit needed)."""
        from src.api.db import get_team_year_map

        assert get_team_year_map([]) == {}

    def test_mixed_set_and_null(self, tmp_path: Path) -> None:
        """Teams with and without season_year are handled correctly together."""
        conn = _make_db()
        t1 = _insert_team(conn, "Team A")
        t2 = _insert_team(conn, "Team B")
        conn.execute("UPDATE teams SET season_year = 2024 WHERE id = ?", (t1,))
        conn.commit()
        env = _db_env(tmp_path, conn)

        with patch.dict(os.environ, env):
            from src.api.db import get_team_year_map

            result = get_team_year_map([t1, t2])

        import datetime

        assert result[t1] == 2024
        assert result[t2] == datetime.date.today().year
