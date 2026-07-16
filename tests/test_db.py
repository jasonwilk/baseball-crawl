# synthetic-test-data
"""Tests for src/api/db.py -- E-100 INTEGER PK contract (surviving surface).

Covers the reports-era survivors of src/api/db.py: AC-11 (_get_permitted_teams
returns list[int]) and get_db_path default-path resolution. The opponent-helper
coverage was removed with those functions in E-239.

All tests use an in-memory SQLite database created from migrations/001_initial_schema.sql.
No real DB file is read or written.

# noqa: fixture-schema -- The E-252-06 connection-contention tests
(TestConnectionContention) create a minimal ad-hoc `t` table via
_init_contention_db to exercise SQLite's database-level write-lock /
busy_timeout behavior (BEGIN IMMEDIATE + threaded lock holder). They test
connection/lock mechanics, not schema, so load_real_schema is not the natural
fit (coupling the lock test to the 704-line production schema adds nothing).
The schema-based tests in this file still use load_real_schema via _make_db.
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


# ---------------------------------------------------------------------------
# Connection factory contention -- busy_timeout (E-252-06)
# ---------------------------------------------------------------------------
#
# The morning-run cron is a THIRD SQLite writer on one shared WAL file
# alongside the admin UI and the interactive CLI. get_connection() sets a
# busy_timeout so a lock overlap WAITS instead of immediately raising
# "database is locked". These tests use REAL on-disk files under tmp_path (NOT
# :memory:, NOT the real data/app.db) with a threaded lock holder, following
# the DE-specified deterministic shape (BEGIN IMMEDIATE + a threading.Event set
# after the lock is actually held + the check_same_thread rule: each connection
# is created in the thread that uses it).

import threading  # noqa: E402
import time  # noqa: E402

from src.api.db import get_connection  # noqa: E402

HOLD_MS = 300  # how long connection A holds the write lock
TIMEOUT_MS = 2000  # connection B's busy_timeout (short so the suite stays fast)


def _init_contention_db(path: Path) -> None:
    """Create a real on-disk WAL database with a single table for the tests.

    WAL is set once up front here (it is a persistent DB-file property), so the
    contender connections in the tests inherit it without re-setting it.
    """
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT);")
        conn.commit()
    finally:
        conn.close()


class TestConnectionContention:
    """busy_timeout makes a write-lock overlap WAIT rather than raise immediately."""

    def test_busy_timeout_waits_for_lock(self, tmp_path: Path) -> None:
        """AC-4: B (with busy_timeout) WAITS for A's lock, then SUCCEEDS.

        Connection A holds a write lock (BEGIN IMMEDIATE) for HOLD_MS on a
        worker thread; connection B, with busy_timeout=TIMEOUT_MS, issues an
        INSERT and must block until A releases. Asserting B's elapsed time
        spans the hold proves it WAITED rather than raised.
        """
        db_file = tmp_path / "contention_wait.db"
        _init_contention_db(db_file)

        lock_acquired = threading.Event()

        def hold_lock() -> None:
            # check_same_thread rule: create+use the connection in THIS thread.
            holder = sqlite3.connect(str(db_file))
            try:
                holder.execute("BEGIN IMMEDIATE;")  # acquire the write lock
                lock_acquired.set()  # signal ONLY after the lock is held
                time.sleep(HOLD_MS / 1000.0)
                holder.commit()  # release the lock
            finally:
                holder.close()

        worker = threading.Thread(target=hold_lock)
        worker.start()

        # Wait until A actually holds the lock before B contends for it. Start
        # the clock here (just after the lock is confirmed held) so elapsed
        # captures the whole hold window; connection-open overhead only adds to
        # it, keeping the >= HOLD_MS assertion robust.
        assert lock_acquired.wait(timeout=5), "worker never acquired the lock"
        start = time.monotonic()

        contender = sqlite3.connect(str(db_file))
        try:
            contender.execute(f"PRAGMA busy_timeout={TIMEOUT_MS};")
            contender.execute("INSERT INTO t (val) VALUES ('b');")
            contender.commit()
        finally:
            contender.close()
        elapsed_ms = (time.monotonic() - start) * 1000.0

        worker.join(timeout=5)

        # B could not commit before A released ~HOLD_MS after acquisition. A
        # 10% slack absorbs sub-millisecond scheduling skew between the worker's
        # set() and the main thread's clock start; this is still an order of
        # magnitude above the ~1ms fast-fail path pinned by AC-5.
        assert elapsed_ms >= HOLD_MS * 0.9, (
            f"B returned in {elapsed_ms:.0f}ms; expected to WAIT ~{HOLD_MS}ms"
        )

    def test_zero_busy_timeout_fails_fast(self, tmp_path: Path) -> None:
        """AC-5 (companion): busy_timeout=0 -> B raises 'database is locked' FAST.

        Same fixture, but B sets busy_timeout=0. It must raise
        sqlite3.OperationalError immediately (elapsed well under the hold),
        pinning that the pragma is load-bearing in both directions.
        """
        db_file = tmp_path / "contention_fast.db"
        _init_contention_db(db_file)

        lock_acquired = threading.Event()
        release = threading.Event()

        def hold_lock() -> None:
            holder = sqlite3.connect(str(db_file))
            try:
                holder.execute("BEGIN IMMEDIATE;")
                lock_acquired.set()
                # Hold until the main thread has observed B's fast-fail; the
                # hold duration is irrelevant to a fast-fail, so gate it on an
                # Event rather than a sleep.
                release.wait(timeout=5)
                holder.commit()
            finally:
                holder.close()

        worker = threading.Thread(target=hold_lock)
        worker.start()
        assert lock_acquired.wait(timeout=5), "worker never acquired the lock"

        contender = sqlite3.connect(str(db_file))
        try:
            contender.execute("PRAGMA busy_timeout=0;")
            start = time.monotonic()
            with pytest.raises(sqlite3.OperationalError, match="database is locked"):
                contender.execute("INSERT INTO t (val) VALUES ('b');")
                contender.commit()
            elapsed_ms = (time.monotonic() - start) * 1000.0
        finally:
            contender.close()
            release.set()
            worker.join(timeout=5)

        assert elapsed_ms < HOLD_MS, (
            f"expected fast-fail well under {HOLD_MS}ms, got {elapsed_ms:.0f}ms"
        )


class TestConnectionFactoryPragmas:
    """Pin the get_connection() factory contract (AC-7)."""

    def test_factory_output_pragmas(self, tmp_path: Path) -> None:
        """AC-7: a connection from get_connection() carries all four pragmas.

        Reads back the factory OUTPUT (not hand-set pragmas), so a regression
        that drops or lowers busy_timeout fails HERE even though AC-4/AC-5 use
        hand-set pragmas on raw connections and would stay green. A db_path
        override in tmp_path keeps this off the real data/app.db.
        """
        db_file = tmp_path / "factory.db"
        with closing(get_connection(db_path=db_file)) as conn:
            busy = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
            fk = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
            journal = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            sync = conn.execute("PRAGMA synchronous;").fetchone()[0]

        assert busy == 30000, f"busy_timeout: expected 30000, got {busy}"
        assert fk == 1, f"foreign_keys: expected 1 (ON), got {fk}"
        assert journal == "wal", f"journal_mode: expected 'wal', got {journal!r}"
        assert sync == 1, f"synchronous: expected 1 (NORMAL), got {sync}"


# ---------------------------------------------------------------------------
# E-264-01 AC-3: get_season_pitching carries teams.innings_per_game RAW
# ---------------------------------------------------------------------------


class TestSeasonPitchingInningsPerGame:
    """AC-3: every pitcher row from get_season_pitching carries the team-season
    ``innings_per_game`` RAW (possibly NULL) -- no SQL-level COALESCE.

    The value is threaded at the OUTER wrapper level (LEFT JOIN teams on the
    already-filtered team_id), so both a stored integer and a NULL surface
    unchanged. The NULL-vs-integer distinction is the sole signal the display
    layer (E-264-03) uses to decide whether to flag "(assumed)", so it must not
    be coerced here.
    """

    _SEASON = "2026"
    _PITCHER = "pp-ipg-1"

    def _seed(
        self, conn: sqlite3.Connection, innings_per_game: int | None
    ) -> int:
        """Seed one team (with the given innings_per_game), pitcher, game, and
        one pitching row. Return the team_id."""
        _insert_season(conn, self._SEASON)
        team_id = _insert_team(conn, "LSB", membership_type="member")
        conn.execute(
            "UPDATE teams SET innings_per_game = ? WHERE id = ?",
            (innings_per_game, team_id),
        )
        opp_id = _insert_team(conn, "Opp", membership_type="tracked")
        _insert_player(conn, self._PITCHER, "Pat", "Pitcher")
        _insert_game(conn, "g-ipg-1", self._SEASON, team_id, opp_id)
        conn.execute(
            "INSERT INTO player_game_pitching "
            "(game_id, player_id, team_id, perspective_team_id, appearance_order) "
            "VALUES ('g-ipg-1', ?, ?, ?, 1)",
            (self._PITCHER, team_id, team_id),
        )
        conn.commit()
        return team_id

    def test_stored_integer_surfaces_raw(self) -> None:
        """A stored integer (6) is carried on the pitcher row unchanged."""
        from src.api.db import get_season_pitching

        conn = _make_db()
        conn.row_factory = sqlite3.Row
        team_id = self._seed(conn, 6)
        rows = {r["player_id"]: r for r in get_season_pitching(conn, team_id, self._SEASON)}
        conn.close()
        assert self._PITCHER in rows, "expected the seeded pitcher row"
        assert "innings_per_game" in rows[self._PITCHER].keys()
        assert rows[self._PITCHER]["innings_per_game"] == 6

    def test_null_surfaces_raw_not_coalesced(self) -> None:
        """A NULL innings_per_game is carried as None (NOT coerced to 7 in SQL)."""
        from src.api.db import get_season_pitching

        conn = _make_db()
        conn.row_factory = sqlite3.Row
        team_id = self._seed(conn, None)
        rows = {r["player_id"]: r for r in get_season_pitching(conn, team_id, self._SEASON)}
        conn.close()
        assert self._PITCHER in rows, "expected the seeded pitcher row"
        assert "innings_per_game" in rows[self._PITCHER].keys()
        assert rows[self._PITCHER]["innings_per_game"] is None, (
            "NULL basis must surface as None -- no SQL COALESCE; the fallback-to-7 "
            "constant belongs at the compute site, not the reader"
        )
