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
