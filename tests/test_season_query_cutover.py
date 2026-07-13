"""Guards for the E-259-01 query-time season-aggregate cutover.

``src.api.db.get_season_batting`` / ``get_season_pitching`` no longer read the
stored ``player_season_*`` tables -- they derive the season line at query time by
SUMming ``player_game_*`` (perspective-filtered), reusing the single shared SUM
projection ``src.db.season_projection.batting_recompute_select`` /
``pitching_recompute_select``.

Two properties carry the cutover and both need POPULATED fixtures (a green test
on an empty DB proves nothing -- epic Technical Notes Sec.4, the E-247 lesson):

* **The perspective filter (AC-2, the epic's #1 hazard).** A game loaded from two
  perspectives writes two ``player_game_*`` rows with the SAME ``team_id`` and
  DIFFERENT ``perspective_team_id``. Without the ``perspective_team_id = team_id``
  filter the reader would SUM both and silently DOUBLE the season line. See
  :class:`TestPerspectiveFilterNoDoubleCount`.

* **The equality pin (AC-4).** On a populated fixture whose per-game rows produce
  a KNOWN season line, the reader output must equal the independent per-game SUM
  oracle for the same data. See :class:`TestEqualityPinDerivesFromPerGame`. (The
  pin originally compared the reader to ``canonical_recompute``'s output; E-259-02
  retired that writer and E-259-03 dropped the stored tables, so the pin now uses
  a raw-SQL per-game SUM computed independently of the reader -- stronger teeth,
  since it shares no code with the projection.)
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

from src.api.db import get_season_batting, get_season_pitching  # noqa: E402
from tests.conftest import load_real_schema  # noqa: E402


def _team_id(conn: sqlite3.Connection, gc_uuid: str) -> int:
    return conn.execute(
        "SELECT id FROM teams WHERE gc_uuid = ?", (gc_uuid,)
    ).fetchone()[0]


# ===========================================================================
# AC-2: the perspective filter prevents the two-perspective double-count.
# ===========================================================================
class TestPerspectiveFilterNoDoubleCount:
    """A game loaded from two perspectives must NOT double the season line.

    THE SINGLE MOST IMPORTANT AC IN THE EPIC (Technical Notes Sec.2). The stored
    rows carried perspective scoping implicitly (``canonical_recompute`` filtered
    ``perspective_team_id`` at write time); the query-time reader must carry it
    explicitly or a two-perspective game silently doubles -- nothing crashes.
    """

    @pytest.fixture()
    def two_perspective_db(self) -> sqlite3.Connection:
        """One game, one player, TWO perspective rows with IDENTICAL stats.

        Both rows have ``team_id = TEAM_HOME`` (so the team filter admits both);
        they differ only in ``perspective_team_id`` (HOME vs AWAY). An unfiltered
        SUM would double the line; the correct reader returns a single
        perspective's values and ``games = 1``.
        """
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        load_real_schema(conn)
        conn.executescript(
            """
            INSERT INTO seasons (season_id, name, year)
                VALUES ('2026', 'Spring 2026', 2026);
            INSERT INTO teams (name, membership_type, gc_uuid) VALUES
                ('Home Team', 'tracked', 'TEAM_HOME'),
                ('Away Team', 'tracked', 'TEAM_AWAY');
            INSERT INTO players (player_id, first_name, last_name)
                VALUES ('PX', 'Two', 'Perspective');
            INSERT INTO games (game_id, season_id, game_date,
                               home_team_id, away_team_id, status)
                VALUES ('G1', '2026', '2026-03-10',
                        (SELECT id FROM teams WHERE gc_uuid='TEAM_HOME'),
                        (SELECT id FROM teams WHERE gc_uuid='TEAM_AWAY'),
                        'completed');
            """
        )
        home = _team_id(conn, "TEAM_HOME")
        away = _team_id(conn, "TEAM_AWAY")
        # Same team_id=HOME, same game, IDENTICAL stats, two perspectives.
        for persp in (home, away):
            conn.execute(
                "INSERT INTO player_game_batting "
                "(game_id, player_id, team_id, perspective_team_id, "
                " ab, h, doubles, triples, hr, rbi, bb, so, sb, cs, hbp, shf) "
                "VALUES ('G1','PX',?,?, 4,2,1,0,0,1,1,1,1,0,0,0)",
                (home, persp),
            )
            conn.execute(
                "INSERT INTO player_game_pitching "
                "(game_id, player_id, team_id, perspective_team_id, "
                " appearance_order, ip_outs, h, r, er, bb, so, pitches, total_strikes) "
                "VALUES ('G1','PX',?,?, 1, 9, 3, 1, 1, 1, 4, 40, 26)",
                (home, persp),
            )
        conn.commit()
        yield conn
        conn.close()

    def test_input_is_genuinely_doubled(
        self, two_perspective_db: sqlite3.Connection
    ) -> None:
        """The fixture's UNFILTERED sum genuinely doubles (proves teeth).

        If this assertion is ever wrong, the double-count test below is vacuous.
        """
        raw = two_perspective_db.execute(
            "SELECT COUNT(*) c, SUM(ab) ab, SUM(h) h FROM player_game_batting "
            "WHERE player_id='PX'"
        ).fetchone()
        assert (raw["c"], raw["ab"], raw["h"]) == (2, 8, 4)

    def test_batting_not_doubled(
        self, two_perspective_db: sqlite3.Connection
    ) -> None:
        home = _team_id(two_perspective_db, "TEAM_HOME")
        rows = get_season_batting(two_perspective_db, home, "2026")
        assert len(rows) == 1
        row = rows[0]
        # Single-perspective values, NOT the doubled (ab=8, h=4, games=2).
        assert row["games"] == 1
        assert row["ab"] == 4
        assert row["h"] == 2
        assert row["bb"] == 1
        assert row["so"] == 1
        assert row["doubles"] == 1
        assert row["sb"] == 1

    def test_pitching_not_doubled(
        self, two_perspective_db: sqlite3.Connection
    ) -> None:
        home = _team_id(two_perspective_db, "TEAM_HOME")
        rows = get_season_pitching(two_perspective_db, home, "2026")
        assert len(rows) == 1
        row = rows[0]
        # Single-perspective values, NOT the doubled (ip_outs=18, games=2).
        assert row["games"] == 1
        assert row["ip_outs"] == 9
        assert row["so"] == 4
        assert row["h"] == 3
        assert row["pitches"] == 40
        assert row["total_strikes"] == 26
        assert row["gs"] == 1


# ===========================================================================
# AC-4: equality pin -- reader == independent per-game SUM oracle.
# ===========================================================================
# Independently hand-computed season line for the rollup-consistent
# ``parity_consistent.sql`` fixture, scoped to (TEAM_T, 2026). These are the SUM
# of the fixture's IN-SCOPE per-game rows, restricted to the columns the reader
# returns. The cross-perspective (persp=OPP, 9s/99s), cross-season (2025), and
# cross-team (OPP) rows in the fixture are excluded by the reader's three filters,
# so any leak would break these expectations.
_EXPECTED_BATTING = {
    "PB_01": {"games": 3, "ab": 11, "h": 4, "doubles": 1, "triples": 1,
              "hr": 1, "rbi": 3, "bb": 3, "so": 3, "sb": 2, "cs": 1,
              "hbp": 1, "shf": 1},
    "PB_02": {"games": 3, "ab": 11, "h": 4, "doubles": 1, "triples": 0,
              "hr": 0, "rbi": 2, "bb": 1, "so": 4, "sb": 1, "cs": 0,
              "hbp": 1, "shf": 0},
}
_EXPECTED_PITCHING = {
    "PP_01": {"games": 2, "ip_outs": 24, "h": 6, "er": 2, "bb": 2, "so": 10,
              "pitches": 113, "total_strikes": 75, "gs": 1},
    "PP_02": {"games": 2, "ip_outs": 36, "h": 11, "er": 5, "bb": 4, "so": 9,
              "pitches": 170, "total_strikes": 108, "gs": 2},
    "PP_03": {"games": 1, "ip_outs": 12, "h": 4, "er": 2, "bb": 1, "so": 3,
              "pitches": 50, "total_strikes": 32, "gs": None},
}



class TestEqualityPinDerivesFromPerGame:
    """Reader derives the season line from ``player_game_*`` (the stored season
    tables no longer exist -- E-259-03 dropped them)."""

    @pytest.fixture()
    def parity_db(self) -> sqlite3.Connection:
        """Populated rollup-consistent fixture (per-game rows only; the stored
        season tables are gone)."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        load_real_schema(conn)
        conn.executescript(
            (_FIXTURES_DIR / "parity_consistent.sql").read_text(encoding="utf-8")
        )
        conn.commit()
        yield conn
        conn.close()

    def test_batting_equals_known_line(
        self, parity_db: sqlite3.Connection
    ) -> None:
        team = _team_id(parity_db, "TEAM_T")
        rows = {r["player_id"]: r for r in get_season_batting(parity_db, team, "2026")}
        assert set(rows) == set(_EXPECTED_BATTING)
        for pid, expected in _EXPECTED_BATTING.items():
            for key, val in expected.items():
                assert rows[pid][key] == val, f"batting {pid}.{key}"

    def test_pitching_equals_known_line(
        self, parity_db: sqlite3.Connection
    ) -> None:
        team = _team_id(parity_db, "TEAM_T")
        rows = {r["player_id"]: r for r in get_season_pitching(parity_db, team, "2026")}
        assert set(rows) == set(_EXPECTED_PITCHING)
        for pid, expected in _EXPECTED_PITCHING.items():
            for key, val in expected.items():
                assert rows[pid][key] == val, f"pitching {pid}.{key}"

    def test_reader_equals_independent_per_game_sum(
        self, parity_db: sqlite3.Connection
    ) -> None:
        """The equality pin: reader output == an INDEPENDENT raw-SQL per-game SUM
        (perspective- and season-scoped), computed without touching the reader's
        projection code -- so the two cannot share a bug."""
        team = _team_id(parity_db, "TEAM_T")
        reader_bat = {r["player_id"]: dict(r)
                      for r in get_season_batting(parity_db, team, "2026")}
        reader_pit = {r["player_id"]: dict(r)
                      for r in get_season_pitching(parity_db, team, "2026")}

        # Independent oracle: raw SUM over the in-scope per-game rows.
        oracle_bat = {
            r["player_id"]: r
            for r in parity_db.execute(
                "SELECT pgb.player_id, COUNT(*) AS games, "
                "SUM(pgb.ab) AS ab, SUM(pgb.h) AS h, SUM(pgb.bb) AS bb, "
                "SUM(pgb.so) AS so, SUM(pgb.sb) AS sb, SUM(pgb.cs) AS cs, "
                "SUM(pgb.hbp) AS hbp, SUM(pgb.shf) AS shf "
                "FROM player_game_batting pgb "
                "JOIN games g ON g.game_id = pgb.game_id "
                "WHERE pgb.team_id=? AND g.season_id='2026' "
                "AND pgb.perspective_team_id=? GROUP BY pgb.player_id",
                (team, team),
            ).fetchall()
        }
        oracle_pit = {
            r["player_id"]: r
            for r in parity_db.execute(
                "SELECT pgp.player_id, COUNT(*) AS games, "
                "SUM(pgp.ip_outs) AS ip_outs, SUM(pgp.h) AS h, SUM(pgp.er) AS er, "
                "SUM(pgp.bb) AS bb, SUM(pgp.so) AS so, SUM(pgp.pitches) AS pitches, "
                "SUM(pgp.total_strikes) AS total_strikes "
                "FROM player_game_pitching pgp "
                "JOIN games g ON g.game_id = pgp.game_id "
                "WHERE pgp.team_id=? AND g.season_id='2026' "
                "AND pgp.perspective_team_id=? GROUP BY pgp.player_id",
                (team, team),
            ).fetchall()
        }

        assert set(reader_bat) == set(oracle_bat)
        for pid, oracle in oracle_bat.items():
            for col in ("games", "ab", "h", "bb", "so", "sb", "cs", "hbp", "shf"):
                assert reader_bat[pid][col] == oracle[col], f"batting {pid}.{col}"
        assert set(reader_pit) == set(oracle_pit)
        for pid, oracle in oracle_pit.items():
            for col in ("games", "ip_outs", "h", "er", "bb", "so",
                        "pitches", "total_strikes"):
                assert reader_pit[pid][col] == oracle[col], f"pitching {pid}.{col}"

    def test_order_reproduced_over_sum_projection(
        self, parity_db: sqlite3.Connection
    ) -> None:
        """ORDER BY reproduces the prior semantics over the per-game SUM
        (batting PA-proxy DESC; pitching ip_outs DESC) -- Technical Notes Sec.8."""
        team = _team_id(parity_db, "TEAM_T")
        bat = [r["player_id"] for r in get_season_batting(parity_db, team, "2026")]
        # PB_01 PA-proxy = 11+3+1+1 = 16 > PB_02 = 11+1+1+0 = 13.
        assert bat == ["PB_01", "PB_02"]
        pit = [r["player_id"] for r in get_season_pitching(parity_db, team, "2026")]
        # ip_outs: PP_02(36) > PP_01(24) > PP_03(12).
        assert pit == ["PP_02", "PP_01", "PP_03"]
