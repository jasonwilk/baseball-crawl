# synthetic-test-data
"""Tests for src/api/db.py -- E-100 INTEGER PK contract (surviving surface).

Covers the reports-era survivors of src/api/db.py: AC-11 (_get_permitted_teams
returns list[int]) and get_db_path default-path resolution. The opponent-helper
coverage was removed with those functions in E-239.

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

from tests.conftest import load_real_schema

# ---------------------------------------------------------------------------
# Schema fixture
# ---------------------------------------------------------------------------


def _make_db() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the production schema applied."""
    conn = sqlite3.connect(":memory:")
    load_real_schema(conn)
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


def _insert_season(conn: sqlite3.Connection, season_id: str = "2026") -> str:
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year)"
        " VALUES (?, 'Spring 2026 HS', 2026)",
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

    def test_nonadmin_with_partial_grants_no_leak(self, tmp_path: Path) -> None:
        """AC-3: non-admin granted team A but not team B → exactly [A], no leak."""
        conn = _make_db()
        cursor = conn.execute("INSERT INTO users (email) VALUES ('partial@test.com')")
        conn.commit()
        user_id: int = cursor.lastrowid  # type: ignore[assignment]

        team_a = _insert_team(conn, "Granted Team A")
        team_b = _insert_team(conn, "Ungranted Team B")  # exists but not granted

        conn.execute(
            "INSERT INTO user_team_access (user_id, team_id) VALUES (?, ?)",
            (user_id, team_a),
        )
        conn.commit()

        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, {**env, "ADMIN_EMAIL": ""}):
            from importlib import reload

            import src.api.auth as auth_module

            reload(auth_module)
            with closing(auth_module.get_connection()) as db_conn:
                db_conn.row_factory = sqlite3.Row
                result = auth_module._get_permitted_teams(
                    db_conn, {"id": user_id, "email": "partial@test.com"}
                )

        assert result == [team_a]
        assert team_b not in result

    def test_admin_via_admin_email_sees_all_teams(self, tmp_path: Path) -> None:
        """AC-1: admin via ADMIN_EMAIL match, 0 grants → ALL team ids."""
        conn = _make_db()
        cursor = conn.execute("INSERT INTO users (email) VALUES ('boss@test.com')")
        conn.commit()
        user_id: int = cursor.lastrowid  # type: ignore[assignment]

        # 2+ teams; the admin has NO user_team_access rows on any of them.
        tid1 = _insert_team(conn, "Admin Team 1")
        tid2 = _insert_team(conn, "Admin Team 2", membership_type="tracked")

        env = _db_env(tmp_path, conn)
        with patch.dict(os.environ, {**env, "ADMIN_EMAIL": "boss@test.com"}):
            from importlib import reload

            import src.api.auth as auth_module

            reload(auth_module)
            with closing(auth_module.get_connection()) as db_conn:
                db_conn.row_factory = sqlite3.Row
                result = auth_module._get_permitted_teams(
                    db_conn, {"id": user_id, "email": "boss@test.com"}
                )

        assert sorted(result) == sorted([tid1, tid2])
        assert all(isinstance(t, int) for t in result)

    def test_admin_via_db_role_sees_all_teams(self, tmp_path: Path) -> None:
        """AC-2: admin via users.role='admin' (ADMIN_EMAIL unset) → ALL team ids."""
        conn = _make_db()
        cursor = conn.execute(
            "INSERT INTO users (email, role) VALUES ('roleadmin@test.com', 'admin')"
        )
        conn.commit()
        user_id: int = cursor.lastrowid  # type: ignore[assignment]

        tid1 = _insert_team(conn, "Role Admin Team 1")
        tid2 = _insert_team(conn, "Role Admin Team 2", membership_type="tracked")

        env = _db_env(tmp_path, conn)
        # ADMIN_EMAIL explicitly unset so only the DB role branch can match.
        with patch.dict(os.environ, {**env, "ADMIN_EMAIL": ""}):
            from importlib import reload

            import src.api.auth as auth_module

            reload(auth_module)
            with closing(auth_module.get_connection()) as db_conn:
                db_conn.row_factory = sqlite3.Row
                result = auth_module._get_permitted_teams(
                    db_conn, {"id": user_id, "email": "roleadmin@test.com"}
                )

        assert sorted(result) == sorted([tid1, tid2])


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
