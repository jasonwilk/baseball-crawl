# synthetic-test-data
"""Characterization tests pinning the mixed-``appearance_order`` GS semantics.

E-253-10 / audit Watch-List (``season_aggregates.py`` GS CASE). The canonical
recompute derives games-started (``gs``) with:

    CASE WHEN MAX(pgp.appearance_order) IS NULL THEN NULL
         ELSE SUM(CASE WHEN pgp.appearance_order = 1 THEN 1 ELSE 0 END)
    END

so in a MIXED scope (some rows populated, some legacy NULL) the ``MAX`` is
non-NULL and the NULL rows fall through the inner CASE to 0 -- they count as
definite NON-starts and can silently UNDERCOUNT served GS. That behavior is
documented as intentional and self-heals at generation time; these tests PIN it
so a future refactor cannot silently change it without failing here.

HISTORICAL NOTE (E-256-02): the original remediation for an undercounting mixed
scope was ``bb data backfill-appearance-order`` -> ``canonical_recompute`` ->
``bb report verify-aggregates``.  That command is DELETED and no backfill
mechanism remains: the live DB holds zero NULL ``appearance_order`` rows and the
game loader populates the column on every load, so a mixed scope can no longer
arise from ingestion.  These tests still stand -- they pin the recompute's
CASE-expression semantics for the legacy rows a stale DB may still carry, and
the self-heal at generation time is now the only remedy.

Per ``.claude/rules/data-model.md`` ("Idempotent-recompute characterization
tests need a populated, stale-disagreeing fixture"), each test seeds a stored
``boxscore_only`` row whose ``gs`` deliberately DISAGREES with the per-game
truth, then asserts the recompute rebuilds it to the documented value -- so the
test has teeth (the rebuild is observable).
"""

from __future__ import annotations

import sqlite3

import pytest

from src.db.season_aggregates import canonical_recompute
from tests.conftest import load_real_schema

_TEAM_ID = 1
_SEASON = "2026"
_PITCHER = "pp-mixed"


@pytest.fixture()
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
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


def _seed_stale_season_gs(db: sqlite3.Connection, gs: int) -> None:
    """Pre-seed a boxscore_only season row whose gs disagrees with per-game truth."""
    db.execute(
        "INSERT INTO player_season_pitching "
        "(player_id, team_id, season_id, stat_completeness, gp_pitcher, "
        "games_tracked, gs) VALUES (?, ?, ?, 'boxscore_only', 1, 1, ?)",
        (_PITCHER, _TEAM_ID, _SEASON, gs),
    )


def _stored_gs(db: sqlite3.Connection) -> tuple[int | None, int | None]:
    row = db.execute(
        "SELECT gs, games_tracked FROM player_season_pitching "
        "WHERE player_id = ? AND team_id = ? AND season_id = ? "
        "AND stat_completeness = 'boxscore_only'",
        (_PITCHER, _TEAM_ID, _SEASON),
    ).fetchone()
    return (row[0], row[1]) if row else (None, None)


def test_mixed_appearance_order_null_rows_count_as_zero(db: sqlite3.Connection) -> None:
    """AC-1: in a MIXED scope, a legacy NULL-``appearance_order`` row contributes
    0 to GS -- gs is the count of ``appearance_order = 1`` rows only.

    Fixture: one start (order=1), one relief (order=2), one legacy NULL. The
    stored row's gs=99 deliberately disagrees; the recompute must rebuild it to
    the documented gs=1 (NOT 2 -- the NULL row is NOT counted as a start).
    """
    _seed_game_pitching(db, "g1", appearance_order=1)   # start
    _seed_game_pitching(db, "g2", appearance_order=2)   # relief
    _seed_game_pitching(db, "g3", appearance_order=None)  # legacy NULL
    _seed_stale_season_gs(db, gs=99)  # stale, disagreeing

    canonical_recompute(db, _TEAM_ID, _SEASON)

    gs, games_tracked = _stored_gs(db)
    assert games_tracked == 3, "all three game rows are tracked"
    assert gs == 1, (
        "documented mixed-scope semantics: only appearance_order=1 rows count; "
        "the legacy NULL row contributes 0 (silent undercount; self-heals at "
        "generation time -- see the module docstring's HISTORICAL NOTE)"
    )


def test_all_null_appearance_order_yields_null_gs(db: sqlite3.Connection) -> None:
    """Companion pin: when EVERY row's appearance_order is NULL (pure pre-backfill
    scope), MAX(...) IS NULL so gs is NULL (honest 'unknown', not 0)."""
    _seed_game_pitching(db, "g1", appearance_order=None)
    _seed_game_pitching(db, "g2", appearance_order=None)
    _seed_stale_season_gs(db, gs=7)  # stale, disagreeing

    canonical_recompute(db, _TEAM_ID, _SEASON)

    gs, games_tracked = _stored_gs(db)
    assert games_tracked == 2
    assert gs is None, "all-NULL scope -> gs NULL (not coerced to 0)"


def test_all_populated_appearance_order_counts_every_start(db: sqlite3.Connection) -> None:
    """Companion pin: a fully-backfilled scope counts each appearance_order=1
    row -- the post-remediation correct behavior the mixed scope self-heals to."""
    _seed_game_pitching(db, "g1", appearance_order=1)  # start
    _seed_game_pitching(db, "g2", appearance_order=1)  # start (another game)
    _seed_game_pitching(db, "g3", appearance_order=3)  # relief
    _seed_stale_season_gs(db, gs=0)  # stale, disagreeing

    canonical_recompute(db, _TEAM_ID, _SEASON)

    gs, games_tracked = _stored_gs(db)
    assert games_tracked == 3
    assert gs == 2, "two appearance_order=1 rows -> gs=2"
