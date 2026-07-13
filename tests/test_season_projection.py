"""Golden + single-source guards for the shared season-aggregate SUM projection.

Ported from ``tests/test_aggregate_parity.py`` (deleted in E-259-02) so the
coverage of the SURVIVING projection is not lost when the parity apparatus is
retired. Unlike the original, these reference only the public projection symbols
that outlive the cutover -- ``src.db.season_projection.batting_recompute_select``
/ ``pitching_recompute_select`` and the ``*_RECOMPUTE_KEYS`` tuples -- which the
query-time season readers (``src.api.db.get_season_*``, E-259-01) now consume.

Independent-oracle fixture: ``tests/fixtures/parity_consistent.sql`` is
rollup-consistent by construction (each expected season value hand-computed from
the per-game rows, independently of the projection code), and carries
cross-perspective / cross-season / cross-team out-of-scope rows so the
projection's WHERE scope is load-bearing.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_FIXTURES_DIR = _PROJECT_ROOT / "tests" / "fixtures"

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.db.season_projection import (  # noqa: E402
    BATTING_RECOMPUTE_KEYS,
    PITCHING_RECOMPUTE_KEYS,
    batting_recompute_select,
    pitching_recompute_select,
)
from tests.conftest import load_real_schema  # noqa: E402

# Hand-verified SUM of the fixture's IN-SCOPE (TEAM_T, 2026) per-game rows, in
# the projection's column order (``*_RECOMPUTE_KEYS``). PP_03's ``gs`` is NULL
# (its only appearance has NULL appearance_order -> MAX IS NULL).
_GOLDEN_BATTING: dict[str, tuple] = {
    "PB_01": ("PB_01", 3, 11, 4, 1, 1, 1, 3, 3, 3, 3, 2, 10, 1, 1, 1),
    "PB_02": ("PB_02", 3, 11, 4, 1, 0, 0, 2, 2, 1, 4, 1, 5, 1, 0, 0),
}
_GOLDEN_PITCHING: dict[str, tuple] = {
    "PP_01": ("PP_01", 2, 24, 6, 3, 2, 2, 10, 1, 1, 113, 75, 31, 1),
    "PP_02": ("PP_02", 2, 36, 11, 5, 5, 4, 9, 2, 1, 170, 108, 49, 2),
    "PP_03": ("PP_03", 1, 12, 4, 2, 2, 1, 3, 0, 0, 50, 32, 15, None),
}


@pytest.fixture()
def projection_db() -> sqlite3.Connection:
    """In-memory DB with schema + the rollup-consistent fixture."""
    conn = sqlite3.connect(":memory:")
    load_real_schema(conn)
    conn.executescript(
        (_FIXTURES_DIR / "parity_consistent.sql").read_text(encoding="utf-8")
    )
    conn.commit()
    yield conn
    conn.close()


def _team_t_id(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT id FROM teams WHERE gc_uuid = 'TEAM_T'").fetchone()[0]


def _scoped(select_body: str) -> str:
    """Append the perspective + season scope the readers apply."""
    alias = "pgb" if "player_game_batting" in select_body else "pgp"
    return (
        select_body
        + f"\nWHERE {alias}.team_id = ? AND g.season_id = ?"
        + f"\n  AND {alias}.perspective_team_id = ?"
        + f"\nGROUP BY {alias}.player_id"
    )


class TestProjectionOutputPinned:
    """The shared SUM projection yields the hand-computed golden rows exactly,
    and the out-of-scope rows are excluded (the WHERE scope is load-bearing)."""

    def test_batting_projection_output_is_pinned(
        self, projection_db: sqlite3.Connection
    ) -> None:
        t_id = _team_t_id(projection_db)
        rows = projection_db.execute(
            _scoped(batting_recompute_select()), (t_id, "2026", t_id)
        ).fetchall()
        got = {row[0]: tuple(row) for row in rows}
        assert got == _GOLDEN_BATTING

    def test_pitching_projection_output_is_pinned(
        self, projection_db: sqlite3.Connection
    ) -> None:
        t_id = _team_t_id(projection_db)
        rows = projection_db.execute(
            _scoped(pitching_recompute_select()), (t_id, "2026", t_id)
        ).fetchall()
        got = {row[0]: tuple(row) for row in rows}
        assert got == _GOLDEN_PITCHING


class TestKeysTrackProjection:
    """The ``*_RECOMPUTE_KEYS`` tuples describe the projection's columns in
    order -- a column added to the SELECT must land in the keys in lock-step
    (single-source guard)."""

    def test_batting_keys_match_projection_columns(
        self, projection_db: sqlite3.Connection
    ) -> None:
        t_id = _team_t_id(projection_db)
        cur = projection_db.execute(
            _scoped(batting_recompute_select()), (t_id, "2026", t_id)
        )
        col_names = tuple(d[0] for d in cur.description)
        assert col_names == BATTING_RECOMPUTE_KEYS

    def test_pitching_keys_match_projection_columns(
        self, projection_db: sqlite3.Connection
    ) -> None:
        t_id = _team_t_id(projection_db)
        cur = projection_db.execute(
            _scoped(pitching_recompute_select()), (t_id, "2026", t_id)
        )
        col_names = tuple(d[0] for d in cur.description)
        assert col_names == PITCHING_RECOMPUTE_KEYS
