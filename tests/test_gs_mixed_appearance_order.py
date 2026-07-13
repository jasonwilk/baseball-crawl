# synthetic-test-data
"""Characterization tests pinning the mixed-``appearance_order`` GS semantics.

E-253-10 / audit Watch-List (``season_projection.py`` GS CASE). Since the E-259
query-time cutover the games-started (``gs``) value is derived at READ time by
``src.api.db.get_season_pitching`` (which wraps the shared
``pitching_recompute_select`` projection):

    CASE WHEN MAX(pgp.appearance_order) IS NULL THEN NULL
         ELSE SUM(CASE WHEN pgp.appearance_order = 1 THEN 1 ELSE 0 END)
    END

so in a MIXED scope (some rows populated, some legacy NULL) the ``MAX`` is
non-NULL and the NULL rows fall through the inner CASE to 0 -- they count as
definite NON-starts and can silently UNDERCOUNT served GS. That behavior is
documented as intentional; these tests PIN it so a future refactor cannot
silently change it without failing here.

Each test seeds per-game rows and asserts the query-time reader derives the
documented ``gs`` value from them (the stored season tables were dropped in
E-259-03).
"""

from __future__ import annotations

import sqlite3

import pytest

from src.api.db import get_season_pitching
from tests.conftest import load_real_schema

_TEAM_ID = 1
_SEASON = "2026"
_PITCHER = "pp-mixed"


@pytest.fixture()
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    load_real_schema(conn)
    conn.execute(
        "INSERT INTO seasons (season_id, name, year) VALUES (?, ?, 2026)",
        (_SEASON, _SEASON),
    )
    conn.execute(
        "INSERT INTO teams (id, name, membership_type) VALUES (?, 'LSB', 'member')",
        (_TEAM_ID,),
    )
    conn.execute(
        "INSERT INTO teams (id, name, membership_type) VALUES (99, 'Opp', 'tracked')"
    )
    conn.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, 'Pat', 'Pitcher')",
        (_PITCHER,),
    )
    yield conn
    conn.close()


def _seed_game(db: sqlite3.Connection, game_id: str) -> None:
    db.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id) "
        "VALUES (?, ?, '2026-04-01', ?, 99)",
        (game_id, _SEASON, _TEAM_ID),
    )


def _seed_game_pitching(
    db: sqlite3.Connection, game_id: str, appearance_order: int | None
) -> None:
    _seed_game(db, game_id)
    db.execute(
        "INSERT INTO player_game_pitching "
        "(game_id, player_id, team_id, perspective_team_id, appearance_order) "
        "VALUES (?, ?, ?, ?, ?)",
        (game_id, _PITCHER, _TEAM_ID, _TEAM_ID, appearance_order),
    )


def _reader_gs(db: sqlite3.Connection) -> tuple[int | None, int | None]:
    """Return (gs, games) derived by the query-time reader for the pitcher."""
    rows = {r["player_id"]: r for r in get_season_pitching(db, _TEAM_ID, _SEASON)}
    if _PITCHER not in rows:
        return (None, None)
    row = rows[_PITCHER]
    return (row["gs"], row["games"])


def test_mixed_appearance_order_null_rows_count_as_zero(db: sqlite3.Connection) -> None:
    """AC-1: in a MIXED scope, a legacy NULL-``appearance_order`` row contributes
    0 to GS -- gs is the count of ``appearance_order = 1`` rows only.

    Fixture: one start (order=1), one relief (order=2), one legacy NULL. The
    stored row's gs=99 deliberately disagrees; the reader must derive gs=1 (NOT
    2 -- the NULL row is NOT counted as a start) from the per-game rows.
    """
    _seed_game_pitching(db, "g1", appearance_order=1)   # start
    _seed_game_pitching(db, "g2", appearance_order=2)   # relief
    _seed_game_pitching(db, "g3", appearance_order=None)  # legacy NULL

    gs, games = _reader_gs(db)
    assert games == 3, "all three game rows are tracked"
    assert gs == 1, (
        "documented mixed-scope semantics: only appearance_order=1 rows count; "
        "the legacy NULL row contributes 0 (silent undercount)"
    )


def test_all_null_appearance_order_yields_null_gs(db: sqlite3.Connection) -> None:
    """Companion pin: when EVERY row's appearance_order is NULL (pure pre-backfill
    scope), MAX(...) IS NULL so gs is NULL (honest 'unknown', not 0)."""
    _seed_game_pitching(db, "g1", appearance_order=None)
    _seed_game_pitching(db, "g2", appearance_order=None)

    gs, games = _reader_gs(db)
    assert games == 2
    assert gs is None, "all-NULL scope -> gs NULL (not coerced to 0)"


def test_all_populated_appearance_order_counts_every_start(db: sqlite3.Connection) -> None:
    """Companion pin: a fully-backfilled scope counts each appearance_order=1
    row -- the correct behavior a mixed scope undercounts toward."""
    _seed_game_pitching(db, "g1", appearance_order=1)  # start
    _seed_game_pitching(db, "g2", appearance_order=1)  # start (another game)
    _seed_game_pitching(db, "g3", appearance_order=3)  # relief

    gs, games = _reader_gs(db)
    assert games == 3
    assert gs == 2, "two appearance_order=1 rows -> gs=2"
