"""Shared synthetic-DB harness for the reconcile_at_load audit."""
from __future__ import annotations

import pathlib
import sqlite3
import sys

REPO = pathlib.Path("/workspaces/baseball-crawl")
sys.path.insert(0, str(REPO))

MIG = REPO / "migrations"


def fresh_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    sql_files = sorted(MIG.glob("[0-9][0-9][0-9]_*.sql"))
    combined = "\n".join(p.read_text() for p in sql_files)
    conn.executescript("PRAGMA foreign_keys=ON;\n" + combined)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def seed_base(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO seasons (season_id, name, year) VALUES ('2026', '2026', 2026)"
    )
    for tid, name in ((1, "TeamOne"), (2, "TeamTwo"), (3, "TeamThree")):
        conn.execute(
            "INSERT INTO teams (id, name, membership_type) VALUES (?,?,'tracked')",
            (tid, name),
        )


def add_game(conn, game_id, *, home=1, away=2, season="2026", date="2026-04-01",
             perspectives=(1,)):
    conn.execute(
        "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
        "game_date, status) VALUES (?,?,?,?,?,'completed')",
        (game_id, season, home, away, date),
    )
    for p in perspectives:
        conn.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?,?)",
            (game_id, p),
        )


def add_player(conn, pid, name="Player X"):
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?,?,?)",
        (pid, name, "Last"),
    )


def add_batting(conn, game_id, player_id, team_id, perspective_team_id):
    add_player(conn, player_id)
    conn.execute(
        "INSERT INTO player_game_batting (game_id, player_id, team_id, "
        "perspective_team_id) VALUES (?,?,?,?)",
        (game_id, player_id, team_id, perspective_team_id),
    )


def add_pitching(conn, game_id, player_id, team_id, perspective_team_id):
    add_player(conn, player_id)
    conn.execute(
        "INSERT INTO player_game_pitching (game_id, player_id, team_id, "
        "perspective_team_id) VALUES (?,?,?,?)",
        (game_id, player_id, team_id, perspective_team_id),
    )


def cols(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
