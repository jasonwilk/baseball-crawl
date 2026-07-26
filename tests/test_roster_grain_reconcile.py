"""Roster-grain reconcile-at-load tests (E-267-04, closes H2).

The defect: roster upserts update present players but never retire absent ones,
and `_query_roster` reads `team_rosters` directly -- so a departed player renders
on the coach-facing roster grid indefinitely, as a false lineup option.

The guard here is deliberately NOT the flat floor ratio. A roster is small and
bounded (12-15) with roughly one departure per crawl, so `FLOOR_RATIO = 0.5`
would permit deleting seven of fourteen. The absolute
`MAX_ROSTER_DEPARTURES = 2` cap (shipped by E-267-01, consumed here as
`extra_guard`) is what actually refuses a truncated crawl -- and the ">= 3 drop"
test below is sized so the FLOOR PASSES and only the cap refuses, or it would
prove nothing.

All tests drive the real `ScoutingLoader.load_team` entry point against a
migrated on-disk SQLite database. No network calls.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from migrations.apply_migrations import run_migrations
from src.api.db import get_season_batting, get_season_pitching
from src.gamechanger.loaders.scouting_loader import ScoutingLoader
from src.reports.generator import _query_roster

_SEASON = "2026"
_SLUG_A = "team-a-slug"
_SLUG_B = "team-b-slug"
_UUID_A = "aaaaaaaa-0000-0000-0000-000000000001"
_UUID_B = "bbbbbbbb-0000-0000-0000-000000000002"
_OPP_UUID = "cccccccc-0000-0000-0000-000000000003"
_GAME = "game-0001"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def _insert_team(
    db: sqlite3.Connection,
    public_id: str = _SLUG_A,
    gc_uuid: str = _UUID_A,
    name: str = "Team A",
) -> int:
    cur = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, public_id, is_active, "
        "season_year) VALUES (?, 'tracked', ?, ?, 0, 2026)",
        (name, gc_uuid, public_id),
    )
    db.commit()
    return cur.lastrowid


def _roster_entry(pid: str, first: str, last: str, number: str = "9") -> dict:
    """One roster payload entry with EXPLICIT names.

    **This deliberately breaks the unique-name convention `_roster` enforces
    below. Do not "fix" it.**

    Every other fixture here derives names from the player id so the dedup sweep
    cannot collapse them -- hardening added after an E-267-03 fixture
    accidentally measured the dedup sweep instead of the reconcile. But that
    hardening also makes the file structurally incapable of holding a
    dedup-MERGEABLE pair, and therefore incapable of detecting a mis-ordering
    relative to `dedup_team_players`: a fixture hardened against one hazard was
    unable to detect its neighbour.

    `test_reconcile_runs_before_dedup_so_a_merged_roster_row_is_not_retired`
    needs exactly what the convention forbids -- matching last names with one
    first name a prefix of the other ("John Smith" / "J Smith") -- so it builds
    its roster through this helper instead.

    Making these names unique silently disarms the only guard on the reconcile's
    upper placement boundary. Precisely (measured under both orderings in
    E-270-05, and stated loosely here before): a non-mergeable pair leaves the
    dedup sweep with nothing to merge, so BOTH orderings converge on the same end
    state and the test loses all discriminating power. It does not go green by
    itself -- it FAILS, still expecting the merged id. The disarming happens at
    the natural repair, when the expectation is updated to match and the test
    then passes under both orderings for good.
    """
    return {"id": pid, "first_name": first, "last_name": last, "number": number}


def _roster(*player_ids: str) -> list[dict]:
    """A roster payload. Names are derived per id so the dedup sweep -- which
    merges same-team players with matching last names and prefix first names --
    cannot silently collapse the fixture (the trap E-267-03 hit)."""
    return [
        {
            "id": pid,
            "first_name": f"First{pid.replace('-', '')}",
            "last_name": f"Last{pid.replace('-', '')}",
            "number": str(10 + i),
        }
        for i, pid in enumerate(player_ids)
    ]


def _game_entry(game_id: str = _GAME) -> dict:
    return {
        "id": game_id,
        "game_status": "completed",
        "home_away": "home",
        "start_ts": "2026-04-10T18:00:00Z",
        "timezone": "America/Chicago",
        "score": {"team": 5, "opponent_team": 3},
        "opponent_team": {"name": "Opp Town"},
    }


def _boxscore(
    own_key: str,
    batters: list[str],
    pitchers: list[str] | None = None,
    names: dict[str, tuple[str, str]] | None = None,
) -> dict:
    """One game's boxscore payload.

    ``names`` MUST be supplied for any player whose real name matters to the
    dedup sweep. The boxscore ``players`` array flows through
    ``ensure_player_row``, so a derived placeholder here OVERWRITES the name the
    roster crawl set -- which silently destroys a prefix-name pair and makes
    ``find_duplicate_players`` return nothing. In production the two payloads
    agree; a fixture where they disagree is testing something that cannot happen.
    """
    pitchers = pitchers or []
    names = names or {}
    listed = [
        {
            "id": pid,
            "first_name": names.get(pid, (f"First{pid.replace('-', '')}", ""))[0],
            "last_name": (
                names[pid][1] if pid in names else f"Last{pid.replace('-', '')}"
            ),
            "number": "9",
        }
        for pid in dict.fromkeys([*batters, *pitchers])
    ]
    return {
        own_key: {
            "players": listed,
            "groups": [
                {
                    "category": "lineup",
                    "stats": [
                        {
                            "player_id": pid,
                            "stats": {
                                "AB": 3, "R": 1, "H": 2, "RBI": 1, "BB": 0, "SO": 0
                            },
                        }
                        for pid in batters
                    ],
                    "extra": [],
                },
                {
                    "category": "pitching",
                    "stats": [
                        {
                            "player_id": pid,
                            "stats": {
                                "IP": 2.0, "H": 1, "R": 0, "ER": 0, "BB": 0, "SO": 2
                            },
                        }
                        for pid in pitchers
                    ],
                    "extra": [],
                },
            ],
        },
        _OPP_UUID: {"players": [], "groups": []},
    }


def _crawl(
    team_id: int,
    roster: list[dict],
    *,
    batters: list[str] | None = None,
    pitchers: list[str] | None = None,
    own_key: str = _SLUG_A,
    names: dict[str, tuple[str, str]] | None = None,
) -> SimpleNamespace:
    """A crawl result. Boxscores are included by default so the load reaches the
    post-boxscore reconcile -- the roster retire deliberately runs there, since
    the jersey backfill would otherwise re-add a departed player."""
    return SimpleNamespace(
        team_id=team_id,
        roster=roster,
        games=[_game_entry()],
        boxscores={_GAME: _boxscore(own_key, batters or [], pitchers, names)},
        schedule_fetch_ok=True,
    )


def _roster_ids(db: sqlite3.Connection, team_id: int, season: str = _SEASON) -> set[str]:
    return {
        r[0]
        for r in db.execute(
            "SELECT player_id FROM team_rosters WHERE team_id = ? AND season_id = ?",
            (team_id, season),
        )
    }


def _roster_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING and "Roster retire" in r.getMessage()
    ]


# ---------------------------------------------------------------------------
# AC-1 / AC-7: the stale roster row
# ---------------------------------------------------------------------------


def test_departed_player_is_retired_from_the_roster_grid(
    db: sqlite3.Connection,
) -> None:
    """AC-1/AC-7: a player dropped from the fresh roster stops rendering.

    Pre-fix this fails: the upsert paths never removed anything, so the ex-player
    kept appearing in ``_query_roster`` -- a false lineup option on the
    coach-facing grid.
    """
    db.row_factory = sqlite3.Row
    team = _insert_team(db)

    ScoutingLoader(db).load_team(
        _crawl(team, _roster("p-1", "p-2", "p-3"), batters=["p-1"])
    )
    assert _roster_ids(db, team) == {"p-1", "p-2", "p-3"}

    ScoutingLoader(db).load_team(
        _crawl(team, _roster("p-1", "p-3"), batters=["p-1"])
    )

    assert _roster_ids(db, team) == {"p-1", "p-3"}
    grid_names = {row["name"] for row in _query_roster(db, team, _SEASON)}
    assert not any("p2" in n for n in grid_names), (
        f"the departed player still renders on the roster grid: {grid_names}"
    )


def test_two_departures_are_retired_at_the_cap_boundary(
    db: sqlite3.Connection,
) -> None:
    """AC-2: exactly MAX_ROSTER_DEPARTURES is a boundary, not a veto."""
    team = _insert_team(db)
    ScoutingLoader(db).load_team(
        _crawl(team, _roster("p-1", "p-2", "p-3", "p-4", "p-5"), batters=["p-1"])
    )

    ScoutingLoader(db).load_team(
        _crawl(team, _roster("p-1", "p-2", "p-3"), batters=["p-1"])
    )

    assert _roster_ids(db, team) == {"p-1", "p-2", "p-3"}


# ---------------------------------------------------------------------------
# AC-2 / AC-7(b): the ABSOLUTE cap, not the ratio
# ---------------------------------------------------------------------------


def test_three_or_more_departures_refuse_with_the_ac2_warn(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-2/AC-7(b): a >=3 drop refuses -- and the CAP fires, not the floor.

    Sized so the FLOOR RATIO PASSES: 14 prior, 9 fresh, 5 absent. ``9 >= 7``
    clears the 0.5 floor comfortably, so if this test went green with the cap
    removed it would be proving the wrong guard. Only ``5 > 2`` refuses.

    This is the mid-edit roster a coach saves halfway through, and it is the
    reason TN-12 rejected the ratio for this grain outright.
    """
    team = _insert_team(db)
    fourteen = [f"p-{i}" for i in range(1, 15)]
    ScoutingLoader(db).load_team(_crawl(team, _roster(*fourteen), batters=["p-1"]))
    assert len(_roster_ids(db, team)) == 14

    nine = fourteen[:9]
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ScoutingLoader(db).load_team(_crawl(team, _roster(*nine), batters=["p-1"]))

    assert _roster_ids(db, team) == set(fourteen), "a mid-edit roster was reaped"

    warnings = _roster_warnings(caplog)
    assert len(warnings) == 1, f"AC-2 requires exactly ONE WARN, got {warnings}"
    message = warnings[0]
    # AC-2 names the payload fields explicitly -- assert each one.
    assert "REFUSED" in message
    assert f"team_id={team}" in message
    assert f"season_id={_SEASON}" in message
    assert "roster_db_count=14" in message
    assert "fresh_crawl_count=9" in message
    assert "absent_count=5" in message
    for departed in fourteen[9:]:
        assert departed in message, f"absent player {departed} missing from the WARN"
    # It must be the CAP that fired, not the floor.
    assert "MAX_ROSTER_DEPARTURES" in message


def test_empty_roster_payload_retires_nothing(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-2/AC-7(a): an empty/incomplete roster crawl proves no departures."""
    team = _insert_team(db)
    ScoutingLoader(db).load_team(
        _crawl(team, _roster("p-1", "p-2", "p-3"), batters=["p-1"])
    )

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ScoutingLoader(db).load_team(_crawl(team, [], batters=["p-1"]))

    assert _roster_ids(db, team) == {"p-1", "p-2", "p-3"}
    assert not _roster_warnings(caplog), "an empty payload is not a refusal DECISION"


def test_catastrophic_roster_shrink_refuses_on_the_cap(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """A catastrophic shrink still refuses -- but the CAP is what refuses it.

    **RENAMED and RE-REASONED at E-276-03, keeping its OUTCOME and losing its
    REASON.** It was ``..._refuses_on_the_floor`` and asserted
    ``"floor_ratio" in warnings[0]`` with a docstring reading *"the flat floor
    still applies underneath the cap"*. **Under V1 there is no floor** -- the
    roster grain's permit condition is a non-empty payload AND the departure
    cap, nothing else -- so the old name asserted a design that no longer
    exists.

    Sized 14 prior / 1 fresh. The outcome is unchanged because 13 genuine
    absences is far above ``MAX_ROSTER_DEPARTURES``, so this refuses under both
    regimes and is a REGRESSION GUARD, not a discriminating test.

    Its opposite number is ``test_an_empty_previously_rostered_ids_leaves_the
    _grain_unguarded``, which is this same shape with ONE input varied and the
    opposite outcome. Read the two together: they are what shows
    ``previously_rostered_ids`` is no longer a cap-scoping refinement but the
    input the sole guard is built from.
    """
    team = _insert_team(db)
    fourteen = [f"p-{i}" for i in range(1, 15)]
    ScoutingLoader(db).load_team(_crawl(team, _roster(*fourteen), batters=["p-1"]))

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ScoutingLoader(db).load_team(_crawl(team, _roster("p-1"), batters=["p-1"]))

    assert _roster_ids(db, team) == set(fourteen)
    warnings = _roster_warnings(caplog)
    assert len(warnings) == 1
    assert "refused_by=cap" in warnings[0], "the cap is the only refuser left"
    assert "floor_ratio=" not in warnings[0], (
        "the message still cites a floor that no longer decides anything"
    )
    # ⚠️ The token is ``floor_ratio=`` -- the PARAMETER, which used to carry a
    # number -- not the bare word. The message deliberately contains the English
    # phrase "there is no floor ratio beneath it", which differs from the old
    # parameter token by a single underscore. Asserting on the bare word would
    # make this test fail the moment someone backticks that phrase to
    # ``floor_ratio``, which this codebase does constantly -- a failure with
    # nothing to do with the defect being guarded.



# ---------------------------------------------------------------------------
# AC-3 / AC-5: leaf-only delete, stats survive
# ---------------------------------------------------------------------------


def test_players_parent_row_survives_a_roster_retire(
    db: sqlite3.Connection,
) -> None:
    """AC-3/AC-7: only the team_rosters row goes; the players parent stays.

    A roster departure is not a player deletion -- the same human may hold stat
    rows for games already played and may appear on another team.
    """
    team = _insert_team(db)
    ScoutingLoader(db).load_team(
        _crawl(team, _roster("p-1", "p-2", "p-3"), batters=["p-1"])
    )
    ScoutingLoader(db).load_team(
        _crawl(team, _roster("p-1", "p-3"), batters=["p-1"])
    )

    assert _roster_ids(db, team) == {"p-1", "p-3"}
    assert db.execute(
        "SELECT COUNT(*) FROM players WHERE player_id = 'p-2'"
    ).fetchone()[0] == 1


def test_cut_mid_season_player_keeps_their_stat_rows(
    db: sqlite3.Connection,
) -> None:
    """AC-5/AC-7: a backfilled-then-cut player loses the grid, keeps the stats.

    ``p-2`` batted and pitched in an early game (so the boxscore backfill also
    gave them a roster row), then was cut. The roster grid must drop them --
    it answers "who is on this team now" -- while ``player_game_*`` retains what
    actually happened. The two are independent by construction: the stat tables
    FK to ``players``, never to ``team_rosters``.
    """
    team = _insert_team(db)
    ScoutingLoader(db).load_team(
        _crawl(
            team,
            _roster("p-1", "p-2", "p-3"),
            batters=["p-1", "p-2"],
            pitchers=["p-2"],
        )
    )
    assert _roster_ids(db, team) == {"p-1", "p-2", "p-3"}

    # Cut: p-2 is off the fresh roster, but the same historical boxscore is
    # re-crawled (so the jersey backfill would happily re-add them).
    ScoutingLoader(db).load_team(
        _crawl(
            team,
            _roster("p-1", "p-3"),
            batters=["p-1", "p-2"],
            pitchers=["p-2"],
        )
    )

    assert _roster_ids(db, team) == {"p-1", "p-3"}, (
        "the boxscore jersey backfill resurrected a cut player -- the roster "
        "reconcile must run AFTER the boxscore load"
    )
    assert db.execute(
        "SELECT COUNT(*) FROM player_game_batting WHERE player_id = 'p-2'"
    ).fetchone()[0] == 1
    assert db.execute(
        "SELECT COUNT(*) FROM player_game_pitching WHERE player_id = 'p-2'"
    ).fetchone()[0] == 1


# ---------------------------------------------------------------------------
# AC-6 / TN-13: the leaderboard must survive a departure
# ---------------------------------------------------------------------------


def test_departed_player_still_appears_in_the_season_leaderboards(
    db: sqlite3.Connection,
) -> None:
    """AC-6: LOCKS the already-correct behavior -- no production change expected.

    ``get_season_batting`` / ``get_season_pitching`` resolve names through
    ``players`` and LEFT JOIN ``team_rosters`` only for a jersey number
    (verified against both queries), so retiring a roster row cannot drop a
    player from the season leaderboards. This asserts that, so a future change
    regressing the join to gate on ``team_rosters`` membership -- which would
    silently erase a cut player's whole season from the report -- fails here.
    """
    db.row_factory = sqlite3.Row
    team = _insert_team(db)
    ScoutingLoader(db).load_team(
        _crawl(
            team,
            _roster("p-1", "p-2"),
            batters=["p-1", "p-2"],
            pitchers=["p-2"],
        )
    )
    ScoutingLoader(db).load_team(
        _crawl(team, _roster("p-1"), batters=["p-1", "p-2"], pitchers=["p-2"])
    )
    assert _roster_ids(db, team) == {"p-1"}, "precondition: p-2 was retired"

    batting = {row["player_id"]: row for row in get_season_batting(db, team, _SEASON)}
    assert "p-2" in batting, "a departed player vanished from the batting leaderboard"
    assert batting["p-2"]["ab"] > 0, "their production must be intact"
    assert "Firstp2" in batting["p-2"]["name"], "the name must resolve via players"

    pitching = {row["player_id"]: row for row in get_season_pitching(db, team, _SEASON)}
    assert "p-2" in pitching, "a departed player vanished from the pitching leaderboard"
    assert pitching["p-2"]["ip_outs"] > 0


# ---------------------------------------------------------------------------
# AC-4 / AC-7: GAP-4 cross-team-season scoping
# ---------------------------------------------------------------------------


def test_another_teams_roster_is_untouched(db: sqlite3.Connection) -> None:
    """AC-4/AC-7 [GAP-4]: the delete is scoped to (team_id, season_id).

    Team B's roster shares player ids with A's departed players, so a delete
    missing its ``team_id`` predicate would reap B's rows too. Guards the
    natural-key scoping on the retire.
    """
    five = ["p-1", "p-2", "p-3", "p-4", "p-5"]
    team_a = _insert_team(db, _SLUG_A, _UUID_A, "Team A")
    team_b = _insert_team(db, _SLUG_B, _UUID_B, "Team B")

    ScoutingLoader(db).load_team(_crawl(team_a, _roster(*five), batters=["p-1"]))
    ScoutingLoader(db).load_team(
        _crawl(team_b, _roster(*five), batters=["p-1"], own_key=_SLUG_B)
    )
    assert _roster_ids(db, team_a) == set(five)
    assert _roster_ids(db, team_b) == set(five)

    # A drops p-4 and p-5 (2 absent of 5: clears the floor AND the cap, so the
    # retire genuinely PROCEEDS -- a refused run would prove nothing about
    # scoping). B is not re-crawled at all.
    ScoutingLoader(db).load_team(
        _crawl(team_a, _roster("p-1", "p-2", "p-3"), batters=["p-1"])
    )

    assert _roster_ids(db, team_a) == {"p-1", "p-2", "p-3"}
    assert _roster_ids(db, team_b) == set(five), (
        "team B's roster was reaped by team A's reconcile"
    )


def test_another_season_of_the_same_team_is_untouched(
    db: sqlite3.Connection,
) -> None:
    """AC-4: the season half of the natural key is scoped too.

    Without the ``season_id`` predicate, reconciling 2026 would reap the same
    team's 2025 roster, since those players are absent from the 2026 crawl.
    """
    from src.gamechanger.loaders import ensure_season_row

    five = ["p-1", "p-2", "p-3", "p-4", "p-5"]
    team = _insert_team(db)
    ScoutingLoader(db).load_team(_crawl(team, _roster(*five), batters=["p-1"]))
    # A prior season's roster for the SAME team.
    ensure_season_row(db, "2025")
    for pid in five:
        db.execute(
            "INSERT INTO team_rosters (team_id, player_id, season_id) "
            "VALUES (?, ?, '2025')",
            (team, pid),
        )
    db.commit()

    # 2 absent of 5 -- inside both gates, so the 2026 retire actually proceeds.
    ScoutingLoader(db).load_team(
        _crawl(team, _roster("p-1", "p-2", "p-3"), batters=["p-1"])
    )

    assert _roster_ids(db, team, "2026") == {"p-1", "p-2", "p-3"}
    assert _roster_ids(db, team, "2025") == set(five), (
        "the prior season's roster was reaped"
    )


def test_reconcile_runs_before_dedup_so_a_merged_roster_row_is_not_retired(
    db: sqlite3.Connection,
) -> None:
    """The UPPER placement boundary: the reconcile must precede the dedup sweep.

    **DO NOT DELETE THIS TEST IN A CLEANUP PASS (E-270-05 AC-3).** It is the SOLE
    test in this file structurally capable of catching the roster reconcile being
    mis-ordered below ``dedup_team_players``, and it will look redundant to a
    future reader: its subject (a roster row surviving) is asserted by several
    neighbours, and its fixture violates the file's own unique-name convention,
    which reads like an oversight to be tidied up.

    Both impressions are wrong, and the second is the trap. That convention --
    derive every fixture name from the player id so the dedup sweep cannot
    collapse them -- makes every OTHER test in this file structurally blind to
    this ordering, because a dedup-mergeable pair is precisely what it forbids
    (see ``_roster_entry``'s docstring). This test needs the forbidden shape.

    What "normalising" the names actually does, measured under both orderings
    rather than assumed: with a NON-mergeable pair the dedup sweep finds nothing
    to merge, so both orderings converge on the SAME end state
    (``{p-short, p-a, p-b, p-c}``) and the test can no longer tell them apart.
    It does not pass at that point -- it FAILS, because it still expects
    ``p-long``. The danger is the natural repair: update the expectation to the
    new end state and it goes green under BOTH orderings, permanently disarmed
    with no signal. With the mergeable pair the two orderings genuinely diverge
    (``p-long`` survives correctly ordered; ``p-long`` is HARD-DELETED
    mis-ordered), which is the entire discriminating power of this test.

    The two calls sit ~11 lines apart in one function and nothing structural
    keeps them in order, so this pins it. Same defect class as E-267-03's
    TN-10 risk 2, different call site -- and NOT covered by that story's test,
    which asserts ``player_game_batting`` and never touches ``team_rosters``.

    Setup: run 2's roster re-issues the same human under a NEW id with a prefix
    name -- ``p-long`` ("John Smith") becomes ``p-short`` ("J Smith") -- which is
    exactly what ``dedup_team_players`` collapses (shorter name merges INTO the
    longer, so ``p-long`` is the canonical that survives).

    * Reconcile FIRST (correct): the split-identity guard exempts the pending
      collapse, so nothing is retired; dedup then merges ``p-short`` ->
      ``p-long`` (longer first name wins) and re-points the roster row. End state
      ``{p-long, p-a, p-b, p-c}`` with the stats ALSO under ``p-long`` -- one
      human, one id.
    * Reconcile AFTER dedup (wrong): dedup merges first, so by the time the
      reconcile runs there is no pair left to exempt; prior holds ``p-long``
      while the raw crawl holds ``p-short``, ``comparable = 3 >= 2`` clears the
      floor, and ``absent = {p-long}`` sits inside the cap -- so the
      freshly-merged, genuinely-rostered row is hard-deleted and **the player
      vanishes from the grid entirely** despite being on the fresh roster.

    Both end states were confirmed by running each ordering.

    Asserts STAT ownership as well as roster survival: the round-2 version
    checked only the roster, which is exactly why it could not see the
    split-identity defect (roster under one id, stats under another).

    The three filler players are load-bearing: without them the mutant's
    ``comparable`` falls under the floor and the health gate would refuse
    anyway, making the test pass for the wrong reason.
    """
    db.row_factory = sqlite3.Row
    names = {"p-long": ("John", "Smith"), "p-short": ("J", "Smith")}
    filler = ["p-a", "p-b", "p-c"]
    run1 = [_roster_entry("p-long", "John", "Smith"), *_roster(*filler)]
    run2 = [_roster_entry("p-short", "J", "Smith"), *_roster(*filler)]

    team = _insert_team(db)
    ScoutingLoader(db).load_team(
        _crawl(team, run1, batters=["p-long", "p-a"], names=names)
    )
    assert _roster_ids(db, team) == {"p-long", "p-a", "p-b", "p-c"}

    ScoutingLoader(db).load_team(
        _crawl(team, run2, batters=["p-long", "p-a"], names=names)
    )

    survivors = _roster_ids(db, team)
    assert survivors & {"p-short", "p-long"}, (
        "the player is on the FRESH roster yet holds no team_rosters row -- the "
        "reconcile ran after dedup and hard-deleted the merged canonical"
    )
    assert survivors == {"p-long", "p-a", "p-b", "p-c"}

    # Stat ownership must agree with the roster -- one human, one id.
    batting = {r["player_id"]: r for r in get_season_batting(db, team, _SEASON)}
    smiths = {pid for pid in batting if pid in {"p-long", "p-short"}}
    assert smiths == {"p-long"}, f"stats are split or misfiled: {smiths}"


def test_recurring_backfill_churn_warns_once_then_drops_to_info(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """A real cut WARNs once; the perpetual re-removal afterwards is INFO.

    A player cut mid-season who appears in an already-played boxscore is
    re-created by the jersey backfill on EVERY re-scout and retired again here,
    forever. TN-4 makes the retire WARN the sole audit record, so an identical
    line every run would train an operator to ignore it. The row is deleted
    either way -- only the level differs.
    """
    team = _insert_team(db)
    played = ["p-1", "p-2"]
    ScoutingLoader(db).load_team(
        _crawl(team, _roster("p-1", "p-2", "p-3"), batters=played)
    )

    # First crawl after the cut: p-2 was rostered when this load began.
    caplog.clear()
    with caplog.at_level(logging.INFO):
        ScoutingLoader(db).load_team(
            _crawl(team, _roster("p-1", "p-3"), batters=played)
        )
    assert _roster_ids(db, team) == {"p-1", "p-3"}
    assert len(_roster_warnings(caplog)) == 1, "a genuine departure must WARN"

    # Every subsequent crawl: the backfill re-creates the row, we remove it
    # again -- same end state, but this is churn, not news.
    for _ in range(2):
        caplog.clear()
        with caplog.at_level(logging.INFO):
            ScoutingLoader(db).load_team(
                _crawl(team, _roster("p-1", "p-3"), batters=played)
            )
        assert _roster_ids(db, team) == {"p-1", "p-3"}
        assert not _roster_warnings(caplog), (
            "recurring backfill churn must not WARN every run"
        )
        assert any(
            "Roster retire (recurring)" in r.getMessage()
            for r in caplog.records
            if r.levelno == logging.INFO
        ), "the churn must still be recorded, at INFO"


def test_reissued_player_id_does_not_split_roster_from_stats(
    db: sqlite3.Connection,
) -> None:
    """The retire must not destroy dedup's detection signal (split identity).

    ``find_duplicate_players`` joins ``team_rosters`` TWICE, so it can only see a
    duplicate pair while BOTH ids are co-rostered. This retire runs before dedup,
    so retiring one half first leaves the human SPLIT -- roster row under the new
    id, every stat row still under the old one -- and no pair remains for dedup
    to find. It does not self-heal: each later crawl re-backfills the old id and
    the retire removes it again, forever.

    Reproduced before fixing: roster ``p-short`` / stats ``p-long`` /
    ``find_duplicate_players`` returning zero.

    NOTE the boxscore carries the SAME names as the roster crawl. That is not
    decoration: the boxscore ``players`` array flows through
    ``ensure_player_row``, so placeholder names there would overwrite the roster
    names, destroy the prefix pair, and make this test pass for an unrelated
    reason. (It did, on my first attempt.)
    """
    db.row_factory = sqlite3.Row
    names = {"p-long": ("John", "Smith"), "p-short": ("J", "Smith")}
    filler = ["p-a", "p-b", "p-c"]
    run1 = [_roster_entry("p-long", "John", "Smith"), *_roster(*filler)]
    run2 = [_roster_entry("p-short", "J", "Smith"), *_roster(*filler)]

    team = _insert_team(db)
    ScoutingLoader(db).load_team(
        _crawl(team, run1, batters=["p-long", "p-a"], names=names)
    )
    ScoutingLoader(db).load_team(
        _crawl(team, run2, batters=["p-long", "p-a"], names=names)
    )

    batting = {r["player_id"]: r for r in get_season_batting(db, team, _SEASON)}
    smiths = {pid for pid in batting if pid in {"p-long", "p-short"}}
    assert len(smiths) == 1, f"the human is split across ids in the leaderboard: {smiths}"

    # The surviving stat id must be the one holding the roster row -- otherwise
    # the grid and the leaderboard disagree about who is on this team.
    stat_id = next(iter(smiths))
    roster = _roster_ids(db, team)
    assert stat_id in roster, (
        f"stats are under {stat_id!r} but the roster row is not -- "
        f"roster={sorted(roster)}"
    )
    assert batting[stat_id]["ab"] == 3, "production must be intact after the merge"


def test_a_refused_fork_member_stays_retirable(db: sqlite3.Connection) -> None:
    """A fork member must NOT be exempted -- only executable collapses are.

    The split-identity guard exempts ids a pending dedup COLLAPSE will merge. A
    blanket exemption keyed on raw ``find_duplicate_players`` pairs would also
    cover FORKS -- a stub prefix-matching two distinct fuller names -- which the
    planner REFUSES to merge. Exempting those would preserve the departed row
    every run forever: a new permanently-unretirable class, strictly worse than
    the defect being fixed.

    Here ``J Smith`` prefix-matches BOTH ``John Smith`` and ``Janet Smith``, so
    the planner refuses the fork. When ``J Smith`` then departs the roster, the
    retire must still remove them.
    """
    names = {
        "p-stub": ("J", "Smith"),
        "p-john": ("John", "Smith"),
        "p-janet": ("Janet", "Smith"),
    }
    filler = ["p-a", "p-b", "p-c"]
    present = [
        _roster_entry("p-john", "John", "Smith"),
        _roster_entry("p-janet", "Janet", "Smith"),
        *_roster(*filler),
    ]
    team = _insert_team(db)
    ScoutingLoader(db).load_team(
        _crawl(
            team,
            [_roster_entry("p-stub", "J", "Smith"), *present],
            batters=["p-a"],
            names=names,
        )
    )
    assert "p-stub" in _roster_ids(db, team)

    # Precondition: the planner really does treat this as a REFUSED fork, or the
    # test proves nothing about fork handling.
    from src.db.player_dedup import plan_player_dedup

    plan = plan_player_dedup(db, team, season_id=_SEASON)
    assert plan.refused_forks, "fixture must produce a refused fork"
    assert not plan.collapses, "fixture must produce no executable collapse"

    # p-stub departs.
    ScoutingLoader(db).load_team(
        _crawl(team, present, batters=["p-a"], names=names)
    )

    assert "p-stub" not in _roster_ids(db, team), (
        "a refused-fork member was exempted -- it can never be merged, so it "
        "would stay on the roster permanently"
    )


def test_planner_failure_skips_the_retire_entirely(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-8: a dedup-planner failure must FAIL CLOSED, not proceed unprotected.

    Without the exemption plan this retire cannot tell a genuine departure from
    a pending merge. Proceeding anyway is exactly the pre-round-3 behavior, which
    splits the identity PERMANENTLY with no self-heal. Skipping costs one stale
    roster row until the next successful crawl.

    So a transient, recoverable failure must never be able to cause permanent,
    unrecoverable corruption -- the same refuse-when-the-signal-is-missing
    posture every other grain in this epic takes.

    Note the departure here WOULD otherwise be retired (2 absent of 5 clears both
    the floor and the cap), so a green result proves the skip fired rather than
    the gates refusing for an unrelated reason.
    """
    five = ["p-1", "p-2", "p-3", "p-4", "p-5"]
    team = _insert_team(db)
    ScoutingLoader(db).load_team(_crawl(team, _roster(*five), batters=["p-1"]))
    assert _roster_ids(db, team) == set(five)

    caplog.clear()
    with patch(
        "src.db.player_dedup.plan_player_dedup",
        side_effect=sqlite3.OperationalError("planner blew up"),
    ):
        with caplog.at_level(logging.WARNING):
            ScoutingLoader(db).load_team(
                _crawl(team, _roster("p-1", "p-2", "p-3"), batters=["p-1"])
            )

    assert _roster_ids(db, team) == set(five), (
        "the retire proceeded without exemptions -- fail-open into the "
        "split-identity defect"
    )
    skips = [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING and "Roster retire SKIPPED" in r.getMessage()
    ]
    assert len(skips) == 1, f"exactly one skip WARN expected, got {skips}"
    assert f"team_id={team}" in skips[0]

    # And it recovers: the next healthy crawl retires the real departures.
    ScoutingLoader(db).load_team(
        _crawl(team, _roster("p-1", "p-2", "p-3"), batters=["p-1"])
    )
    assert _roster_ids(db, team) == {"p-1", "p-2", "p-3"}


def test_cap_counts_genuine_departures_not_backfill_churn(
    db: sqlite3.Connection,
) -> None:
    """Three cut-but-already-played players must still be retirable.

    ``_upsert_roster_jersey`` re-creates a ``team_rosters`` row for every player
    in every loaded boxscore, so a player cut mid-season who already appeared in
    a completed game is re-added on EVERY re-scout. Counting those toward
    ``MAX_ROSTER_DEPARTURES`` made the cap self-trapping: three such players put
    ``absent_count`` permanently above the cap, and because the refusal is
    whole-set, they rendered forever AND every later genuine departure was
    blocked too -- reinstating H2, the defect this grain exists to close.

    Churn ids are a deterministic artifact of this run's own backfill, not
    evidence of a truncated crawl, so the cap counts genuine departures only.
    """
    played = ["p-1", "p-2", "p-3", "p-4"]
    roster = ["p-1", "p-2", "p-3", "p-4", "p-5", "p-6"]
    team = _insert_team(db)
    ScoutingLoader(db).load_team(_crawl(team, _roster(*roster), batters=played))
    assert _roster_ids(db, team) == set(roster)

    # Cut THREE already-played players at once. All three are still in the
    # pre-load snapshot, so all three are genuine -> above the cap -> refuse.
    ScoutingLoader(db).load_team(
        _crawl(team, _roster("p-1", "p-5", "p-6"), batters=played)
    )
    assert _roster_ids(db, team) == set(roster), "3 genuine departures must refuse"

    # The cap is intact; it just must not be tripped by the backfill's own
    # re-creations. Retire two, as a real roster edit would.
    ScoutingLoader(db).load_team(
        _crawl(team, _roster("p-1", "p-4", "p-5", "p-6"), batters=played)
    )
    assert _roster_ids(db, team) == {"p-1", "p-4", "p-5", "p-6"}

    # p-2 and p-3 are now CHURN -- re-created by the backfill every run, absent
    # from the pre-load snapshot. They must NOT consume cap budget, so cutting
    # p-4 (1 genuine departure, alongside 2 churn ids) must still proceed. If
    # churn counted, absent_count would be 3 and this would refuse forever.
    ScoutingLoader(db).load_team(
        _crawl(team, _roster("p-1", "p-5", "p-6"), batters=played)
    )
    surviving = _roster_ids(db, team)
    assert surviving == {"p-1", "p-5", "p-6"}, (
        f"churn consumed the cap budget and blocked a real departure: {surviving}"
    )


def test_previously_rostered_ids_scopes_the_cap_population(
    db: sqlite3.Connection,
) -> None:
    """The snapshot defines WHICH absences the cap counts -- it is a real input.

    This replaces an earlier test asserting the snapshot could never affect a
    retire. That was true when it only picked a log level; it stopped being true
    once the cap was scoped to genuine departures. The old test kept passing
    only because its fixture sat exactly at the cap boundary either way -- a
    coincidence, not a property, so it is stated correctly here instead.
    """
    from src.db.reconcile_at_load import retire_departed_roster_players

    six = [f"p-{i}" for i in range(1, 7)]
    fresh = {"p-1", "p-2", "p-3"}
    team_a = _insert_team(db, _SLUG_A, _UUID_A, "Team A")
    team_b = _insert_team(db, _SLUG_B, _UUID_B, "Team B")
    ScoutingLoader(db).load_team(_crawl(team_a, _roster(*six), batters=["p-1"]))
    ScoutingLoader(db).load_team(
        _crawl(team_b, _roster(*six), batters=["p-1"], own_key=_SLUG_B)
    )

    # Snapshot present: 3 genuine departures -> above the cap -> whole-set refuse.
    with_snapshot = retire_departed_roster_players(
        db, team_id=team_a, season_id=_SEASON, fresh_player_ids=fresh,
        previously_rostered_ids=set(six), exempt_player_ids=(),
    )
    assert with_snapshot.refused and not with_snapshot.retired_player_ids

    # Empty snapshot means "nothing was rostered before this load", so every
    # absence reads as churn and the cap has nothing to count. That is exactly
    # why the parameter is REQUIRED -- a default would silently disable the cap.
    without_snapshot = retire_departed_roster_players(
        db, team_id=team_b, season_id=_SEASON, fresh_player_ids=fresh,
        previously_rostered_ids=(), exempt_player_ids=(),
    )
    assert without_snapshot.retired_player_ids == ["p-4", "p-5", "p-6"]
    db.commit()


def test_roster_additions_are_never_gated(db: sqlite3.Connection) -> None:
    """AC-2: only DELETEs are capped -- a growing roster is not a signal.

    Ten additions in one crawl is far above MAX_ROSTER_DEPARTURES and must pass
    without comment.
    """
    team = _insert_team(db)
    ScoutingLoader(db).load_team(_crawl(team, _roster("p-1"), batters=["p-1"]))

    twelve = [f"p-{i}" for i in range(1, 13)]
    ScoutingLoader(db).load_team(_crawl(team, _roster(*twelve), batters=["p-1"]))

    assert _roster_ids(db, team) == set(twelve)


# ===========================================================================
# E-276-03: the roster grain loses its floor (V1)
# ===========================================================================
#
# ⛔ This story REMOVES a guard rather than fixing one. The permit condition is
# now exactly `(fresh payload non-empty) AND (cap permits)`, and
# MAX_ROSTER_DEPARTURES is the SOLE safety control on this grain.
#
# It does NOT fix the post-upsert prior read here -- it removes the gate that
# carried it. What it fixes is the CONCEALMENT: a floor that appeared to
# protect, could not (the cap fires first), and would have locked the grain
# permanently if it had been repaired instead of removed.
#
# ⚠️ FIXTURE TRAP: any test needing two DISTINCT games for one team MUST vary
# the DATE. Two games for one team on the same date collapse into a single
# `games` row via the cross-perspective natural key, and the tell is silent -- a
# player holding zero batting rows after a run in which he batted.


@contextmanager
def _capture_roster_results():
    """Call-through spy yielding each ``RosterRetireResult``.

    Patch target is ``reconcile_at_load`` for this grain (function-local import
    in ``_reconcile_departed_roster``). Appended AFTER the call returns, so a
    non-empty list certifies the helper COMPLETED -- that wrapper swallows every
    exception WITHOUT incrementing ``LoadResult.errors``, so on this grain
    ``errors == 0`` is vacuous as completion evidence.
    """
    from src.db import reconcile_at_load as _recon

    real = _recon.retire_departed_roster_players
    captured: list[object] = []

    def _call_through(*args, **kwargs):
        result = real(*args, **kwargs)
        captured.append(result)
        return result

    with patch.object(
        _recon, "retire_departed_roster_players", _call_through
    ):
        yield captured


def _assert_captured_roster_results(captured) -> None:
    from src.db.reconcile_at_load import RosterRetireResult

    assert captured, (
        "the roster reconcile never ran -- row survival alone is satisfied by a "
        "spy that never fired (wrong patch module)"
    )
    for result in captured:
        assert isinstance(result, RosterRetireResult), (
            f"the spy recorded {result!r}, not a result object"
        )


def test_a_three_row_roster_with_one_survivor_now_retires_both_departures(
    db: sqlite3.Connection,
) -> None:
    """AC-1: the floor is gone -- this story's discriminating case.

    3 stored rows, fresh crawl carries 1, churn-free. **Pre-fix the floor fires**
    (``1 >= 0.5 * 3`` fails) and nothing is retired; **post-fix** the cap sees 2
    genuine departures, permits, and both absent rows go.

    **The sizing rule, so a variant is derivable**: a floor can only refuse where
    the cap permits when ``a < b <= MAX_ROSTER_DEPARTURES``, with ``a`` stored
    rows still present and ``b`` stored rows absent -- so churn-free, every
    discriminating shape has a stored roster of <= 3 rows, exactly
    ``(a,b) in {(0,1), (0,2), (1,2)}``. This is ``(1,2)``. That bound holds ONLY
    at churn 0; with backfill churn the divergence is unbounded in churn rows,
    which is what the whole-set test below exercises.

    **NOT the 9-stored/9-brand-new shape**: at this grain ``absent & previously``
    would be 9, over the cap, so the cap refuses under BOTH regimes and the test
    could not fail. That shape discriminates at the player-line grain only.
    """
    team = _insert_team(db)
    stored = ["p-1", "p-2", "p-3"]
    ScoutingLoader(db).load_team(_crawl(team, _roster(*stored), batters=["p-1"]))
    assert _roster_ids(db, team) == set(stored)

    with _capture_roster_results() as captured:
        ScoutingLoader(db).load_team(
            _crawl(team, _roster("p-1"), batters=["p-1"])
        )

    _assert_captured_roster_results(captured)
    result = captured[-1]
    assert result.refused is False
    assert result.retired_player_ids == ["p-2", "p-3"]
    assert result.gate_outcome.refused_by is None
    assert _roster_ids(db, team) == {"p-1"}


def test_the_whole_set_construction_retires_the_churn_and_exactly_two_pre_existing(
    db: sqlite3.Connection,
) -> None:
    """AC-2: the churn-region divergence at ordinary roster size.

    10 rostered, fresh crawl drops 2, and 20 backfill-churn rows created by this
    run's own jersey backfill. **Pre-fix the floor refuses and ZERO rows are
    retired** (the live population is 30 with an overlap of 8). **Post-fix** the
    cap sees ``absent & previously == 2`` -- exactly at the cap -- permits, and
    **22 rows are retired: the 20 churn rows plus exactly 2 pre-existing ones**,
    with the 8 survivors intact.

    The pre-existing count is asserted explicitly, not just the total: **this is
    what pins the CAP -- and not a floor -- as the thing bounding pre-existing
    loss**, and it is the executable form of the accepted rate residual. It was
    built to defeat a deletion-neutrality claim; under V1 it executes, which is
    the change of régime this story ships.
    """
    team = _insert_team(db)
    rostered = [f"r-{i}" for i in range(10)]
    churn = [f"c-{i}" for i in range(20)]

    # Run 1 establishes the 10-row pre-load snapshot. The churn rows must be
    # created by RUN 2's own backfill, not run 1's: a first load retires its own
    # churn immediately (that is the AC-4 behaviour below), so churn seeded here
    # would simply be gone before run 2 started.
    ScoutingLoader(db).load_team(
        _crawl(team, _roster(*rostered), batters=rostered)
    )
    assert _roster_ids(db, team) == set(rostered)

    survivors = rostered[:8]
    with _capture_roster_results() as captured:
        # Fresh roster carries 8; the boxscore lists 20 players who are NOT on
        # it, so the jersey backfill creates 20 churn rows during this run.
        ScoutingLoader(db).load_team(
            _crawl(team, _roster(*survivors), batters=[*survivors, *churn])
        )

    _assert_captured_roster_results(captured)
    result = captured[-1]
    assert result.refused is False
    assert len(result.retired_player_ids) == 22
    pre_existing = [p for p in result.retired_player_ids if p in rostered]
    assert sorted(pre_existing) == ["r-8", "r-9"], (
        "exactly 2 PRE-EXISTING rows may go -- that is the cap, not a floor"
    )
    assert result.genuine_departure_count == 2
    assert _roster_ids(db, team) == set(survivors)


def test_an_empty_previously_rostered_ids_leaves_the_grain_unguarded(
    db: sqlite3.Connection,
) -> None:
    """AC-5b: with the floor gone, an empty snapshot disables the ONLY guard.

    This is ``test_catastrophic_roster_shrink_refuses_on_the_cap`` with **one
    input varied** -- which is what makes it evidence rather than illustration.
    Same 13-row stored roster, same 1-row fresh crawl; the only difference is
    ``previously_rostered_ids``.

    ``_cap_on_genuine_departures`` computes ``absent & previously``. Empty
    ``previously`` makes that intersection empty, so the guard sees zero
    departures and permits **unconditionally at any roster size**. That part is
    unchanged by this story. What changed is what sits underneath: **today the
    floor still refuses; under V1 nothing does.**

    ⚠️ DISCRIMINATING, not a characterization: pre-fix the floor refuses here and
    retires 0; post-fix all 12 absences go.
    """
    from src.db.reconcile_at_load import retire_departed_roster_players

    team = _insert_team(db)
    thirteen = [f"p-{i}" for i in range(1, 14)]
    ScoutingLoader(db).load_team(_crawl(team, _roster(*thirteen), batters=["p-1"]))
    assert _roster_ids(db, team) == set(thirteen)

    result = retire_departed_roster_players(
        db,
        team_id=team,
        season_id=_SEASON,
        fresh_player_ids={"p-1"},
        previously_rostered_ids=set(),  # THE one varied input
        exempt_player_ids=set(),
    )

    assert result.refused is False, "with an empty snapshot nothing refuses"
    assert result.genuine_departure_count == 0, "the cap sees no departures"
    assert len(result.retired_player_ids) == 12, (
        "every absent pre-existing row went, with no bound at all"
    )
    assert _roster_ids(db, team) == {"p-1"}


def test_churn_retirement_is_unchanged_on_a_first_load_and_in_steady_state(
    db: sqlite3.Connection,
) -> None:
    """AC-4: behaviour-unchanged regression -- the churn retire must not move.

    Two shapes, both identical to today and both required to stay identical: a
    FIRST load (empty ``previously_rostered_ids``, 13 rostered + 3 backfill
    churn rows) and the ordinary steady state (13 roster, 13 fresh, 3 churn).
    Exactly the 3 churn rows are retired, unrefused, in each.

    This is what keeps a mid-season cut who still appears in a completed
    boxscore from being re-added to the grid forever.

    **⚠️ Asserted on STATE, deliberately NOT on the retire WARN.** On a first
    load every churn row takes the **INFO-level** recurring-churn branch, so the
    WARNING-level hard-deleted line is never emitted at all: a log-grep
    assertion reports "nothing retired" on a run that retired all three. That is
    a false NEGATIVE, not a failure, and this file's own ``_roster_warnings``
    helper filters to WARNING -- so reusing it here would satisfy nothing.
    """
    team = _insert_team(db)
    rostered = [f"p-{i}" for i in range(13)]
    churn = [f"c-{i}" for i in range(3)]

    # FIRST load: previously_rostered_ids is empty; the boxscore backfills 3
    # rows for players absent from the roster crawl.
    with _capture_roster_results() as captured:
        ScoutingLoader(db).load_team(
            _crawl(team, _roster(*rostered), batters=[*rostered, *churn])
        )
    _assert_captured_roster_results(captured)
    first = captured[-1]
    assert first.refused is False
    assert sorted(first.retired_player_ids) == sorted(churn)
    assert _roster_ids(db, team) == set(rostered)

    # STEADY state: same 13 rostered, same 3 churn rows re-created this run.
    with _capture_roster_results() as captured:
        ScoutingLoader(db).load_team(
            _crawl(team, _roster(*rostered), batters=[*rostered, *churn])
        )
    _assert_captured_roster_results(captured)
    steady = captured[-1]
    assert steady.refused is False
    assert sorted(steady.retired_player_ids) == sorted(churn)
    assert steady.genuine_departure_count == 0, "churn is never a departure"
    assert _roster_ids(db, team) == set(rostered)


@pytest.mark.parametrize(
    ("cap", "expected_survivors"), [(2, 16), (5, 1)]
)
def test_erosion_a_progressively_degrading_crawl_empties_a_roster_by_the_RATE(
    db: sqlite3.Connection, cap: int, expected_survivors: int
) -> None:
    """AC-7: the executable form of "rate, not bound" (epic TN-19).

    26-row roster against a crawl that degrades progressively over 5
    invocations. **At cap 2, 16 survive; at cap 5, only 1 does.** Raising the cap
    from 2 to 5 does not mean "5 lost" -- it means 5 PER INVOCATION, i.e. ``5N``,
    unbounded in N, and morning-run walks several teams per process so N is not
    one.

    **Why the existing tests do not substitute for this.** Three tests do fire
    when the cap is raised -- the constant pin plus two behavioural ones -- but
    every one fails for the reason *"the cap moved"*, which is exactly what a
    tuner intends. They are items on the tuner's own change list. **No other test
    in the suite encodes the CONSEQUENCE of a cap value at any value**, so a
    tuner who raises it and correctly updates all three gets a green suite and
    learns nothing about ``5N``.

    **The cap is varied through the INJECTION POINT, not by monkeypatching the
    constant**: ``roster_departure_guard``'s ``max_departures`` default binds at
    DEFINITION time, so rebinding ``MAX_ROSTER_DEPARTURES`` does not reach the
    guard. Note that parameter had **zero callers** in ``src/`` or ``tests/``
    before this test -- "no caller does X" is an observation about the tree, not
    an invariant, and this test is its first caller.
    """
    from src.db.reconcile_at_load import (
        classify_absences,
        retire_departed_roster_players,
        roster_departure_guard,
    )

    team = _insert_team(db)
    roster26 = [f"p-{i:02d}" for i in range(26)]
    ScoutingLoader(db).load_team(_crawl(team, _roster(*roster26), batters=["p-00"]))
    assert len(_roster_ids(db, team)) == 26

    real_classify = classify_absences

    def _classify_with_cap(*args, **kwargs):
        # Re-point extra_guard at the INJECTION POINT with this run's cap.
        kwargs["extra_guard"] = lambda absent: roster_departure_guard(
            frozenset(absent & set(surviving)), max_departures=cap
        )
        return real_classify(*args, **kwargs)

    per_invocation: list[int] = []
    for step in range(5):
        surviving = set(_roster_ids(db, team))
        # The crawl sheds exactly ``cap`` players per invocation. That is
        # DELIBERATELY tuned to the cap, and it is the whole demonstration: the
        # cap does not bound how much a degrading crawl can take, it sets the
        # RATE at which it takes it. Shed fewer and the loss is crawl-limited;
        # shed more and the cap refuses the whole set and nothing is lost at all
        # -- which is the catastrophic case, and is why protection here runs
        # BACKWARDS with respect to severity.
        fresh = sorted(surviving)[: max(1, len(surviving) - cap)]
        before = len(surviving)
        with patch(
            "src.db.reconcile_at_load.classify_absences", _classify_with_cap
        ):
            retire_departed_roster_players(
                db,
                team_id=team,
                season_id=_SEASON,
                fresh_player_ids=set(fresh),
                previously_rostered_ids=surviving,
                exempt_player_ids=set(),
            )
        db.commit()
        per_invocation.append(before - len(_roster_ids(db, team)))
        assert per_invocation[-1] <= cap, (
            f"invocation {step + 1} exceeded the per-invocation rate"
        )

    survivors = len(_roster_ids(db, team))
    assert survivors == expected_survivors, (
        f"cap={cap}: per-invocation {per_invocation}, {survivors} survivors"
    )
    assert sum(per_invocation) == 26 - expected_survivors


def test_two_stored_against_two_brand_new_permits_and_retires_both(
    db: sqlite3.Connection,
) -> None:
    """AC-8(a): CHARACTERIZATION -- passes under both regimes by design.

    2 stored ids against 2 brand-new fresh ids. This was the DISCRIMINATING
    fixture for a floor-bearing design; under V1 it is a characterization test of
    the accepted behaviour. It pins that this grain does NOT refuse here, and it
    fails if someone re-adds a floor.

    Note why it also permitted BEFORE this story, so the "identical to today"
    claim is not mysterious: the two brand-new ids get ``team_rosters`` rows from
    the same run's roster load, so the old live-population read saw 4 with an
    overlap of 2 and cleared ``2 >= 0.5 * 4``. The floor never bit here.
    """
    team = _insert_team(db)
    ScoutingLoader(db).load_team(
        _crawl(team, _roster("old-1", "old-2"), batters=["old-1"])
    )
    assert _roster_ids(db, team) == {"old-1", "old-2"}

    with _capture_roster_results() as captured:
        ScoutingLoader(db).load_team(
            _crawl(team, _roster("new-1", "new-2"), batters=["new-1"])
        )

    _assert_captured_roster_results(captured)
    result = captured[-1]
    assert result.refused is False
    assert sorted(result.retired_player_ids) == ["old-1", "old-2"]
    assert _roster_ids(db, team) == {"new-1", "new-2"}


def test_passing_the_pre_load_set_as_the_classification_universe_locks_the_grain(
    db: sqlite3.Connection,
) -> None:
    """AC-8(b): the classification-universe slip, executed over two runs.

    The slip is passing ``previously_rostered_ids`` (or any pre-load-derived
    set) to ``classify_absences`` as its prior population, instead of the LIVE
    exempt-filtered read. It reads as obviously correct while writing it.

    **Run 1** (first load, so the pre-load set is EMPTY): the slipped classifier
    has no candidates and retires nothing, where the correct form retires the 3
    backfill-churn rows. **Run 2**: those rows are now pre-existing, so they land
    in ``absent & previously`` -- 3 genuine departures against a cap of 2 -- and
    the cap refuses. **Every subsequent run repeats it: permanently unretirable.**

    **More consequential under V1, not less.** The cap is now the only guard on
    the grain, so a slip that feeds it a wrong population has nothing beneath it.

    Story 01 AC-9b owns the primitive-level contract test that the live set is
    what reaches the classifier; this is the executed two-run consequence, which
    is demonstrable only at this grain.
    """
    from src.db import reconcile_at_load as _recon

    team = _insert_team(db)
    rostered = [f"p-{i}" for i in range(13)]
    churn = [f"c-{i}" for i in range(3)]
    real_classify = _recon.classify_absences

    def _slipped(prior_ids, fresh_ids, **kwargs):
        # THE SLIP: the pre-load set replaces the live read as the universe.
        # On a first load that set is empty, so nothing is even a candidate.
        return real_classify(set(), fresh_ids, **kwargs)

    with patch.object(_recon, "classify_absences", _slipped):
        ScoutingLoader(db).load_team(
            _crawl(team, _roster(*rostered), batters=[*rostered, *churn])
        )

    assert _roster_ids(db, team) == {*rostered, *churn}, (
        "the slip must leave the churn rows behind -- the correct form retires "
        "them on run 1"
    )

    # Run 2 onward: correct code, but the stranded rows are now PRE-EXISTING.
    for run in (2, 3):
        with _capture_roster_results() as captured:
            ScoutingLoader(db).load_team(
                _crawl(team, _roster(*rostered), batters=[*rostered, *churn])
            )
        _assert_captured_roster_results(captured)
        result = captured[-1]
        assert result.refused is True, f"run {run}: expected the cap to refuse"
        assert result.gate_outcome.refused_by == "cap"
        assert result.genuine_departure_count == 3, (
            f"run {run}: the stranded churn now counts as genuine departures"
        )
        assert _roster_ids(db, team) == {*rostered, *churn}, (
            f"run {run}: still unretirable -- the lock is permanent"
        )


def test_every_refused_by_value_this_grain_can_emit_is_reachable(
    db: sqlite3.Connection,
) -> None:
    """AC-3: the COMPLETE five-value set, each driven to.

    Per epic TN-11's per-grain membership table this grain's set is
    ``None | "cap" | "empty_payload" | "fetch_not_ok" |
    "skipped_no_exemption_plan"``. **``"gate"`` is UNREACHABLE here** -- V1 runs
    no floor gate -- so a test asserting it would assert a state the code cannot
    produce.

    **The two SYNTHESIZED values are the ones that matter most.** Both
    ``if not fresh_player_ids: return`` and ``if exempt_player_ids is None:
    return`` in ``_reconcile_departed_roster`` occur BEFORE the helper is ever
    called, so without synthesis two mechanisms that each produce "0 retired"
    would sit upstream of the record meant to disambiguate them -- on the one
    grain that has no gate and where ``refused_by`` is the only structural
    discriminator there is.

    The sixth state -- *no absences, nothing to decide* -- must read as ``None``
    and not as any refusal.
    """
    from src.db.reconcile_at_load import retire_departed_roster_players

    team = _insert_team(db)
    thirteen = [f"p-{i}" for i in range(1, 14)]
    ScoutingLoader(db).load_team(_crawl(team, _roster(*thirteen), batters=["p-1"]))

    seen: dict[str, str | None] = {}

    # cap -- 13 genuine departures against a cap of 2.
    seen["cap"] = retire_departed_roster_players(
        db, team_id=team, season_id=_SEASON, fresh_player_ids={"p-1"},
        previously_rostered_ids=set(thirteen), exempt_player_ids=set(),
    ).gate_outcome.refused_by

    # fetch_not_ok -- the AUTHORITY check inside the helper sees no fresh ids.
    seen["fetch_not_ok"] = retire_departed_roster_players(
        db, team_id=team, season_id=_SEASON, fresh_player_ids=set(),
        previously_rostered_ids=set(thirteen), exempt_player_ids=set(),
    ).gate_outcome.refused_by

    # None -- every prior id is present, so nothing was decided.
    seen["none"] = retire_departed_roster_players(
        db, team_id=team, season_id=_SEASON, fresh_player_ids=set(thirteen),
        previously_rostered_ids=set(thirteen), exempt_player_ids=set(),
    ).gate_outcome.refused_by

    # empty_payload -- the WRAPPER's early return, a DIFFERENT site from
    # fetch_not_ok above. Collapsing the two would re-create the ambiguity the
    # record exists to remove.
    loader = ScoutingLoader(db)
    seen["empty_payload"] = loader._reconcile_departed_roster(
        team, _SEASON, [], set(thirteen)
    ).gate_outcome.refused_by

    # skipped_no_exemption_plan -- the dedup pre-plan failed, so pending merges
    # cannot be told from departures. Roster-ONLY value.
    with patch.object(
        ScoutingLoader, "_pending_collapse_player_ids", return_value=None
    ):
        seen["skipped_no_exemption_plan"] = loader._reconcile_departed_roster(
            team, _SEASON, _roster("p-1"), set(thirteen)
        ).gate_outcome.refused_by

    assert seen == {
        "cap": "cap",
        "fetch_not_ok": "fetch_not_ok",
        "none": None,
        "empty_payload": "empty_payload",
        "skipped_no_exemption_plan": "skipped_no_exemption_plan",
    }
    # Nothing was retired on any of these paths.
    assert _roster_ids(db, team) == set(thirteen)


def test_the_refusal_WARN_names_the_cap_and_carries_the_caps_own_counts(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-10: the operator-facing message, which in production is the only signal.

    Removing the floor CHANGED the first refusal branch's meaning -- it is no
    longer "suspected partial crawl" but "the fresh crawl was empty" -- so
    ``fresh_comparable_count`` and ``floor_ratio`` stop being numbers that
    decided anything. Leaving them would ship a message whose figures do not
    explain the decision.

    This matters more under V1 than before: the cap is the ONLY refuser left, so
    this string is the only thing separating a healthy bias-to-refuse from the
    permanent lock in IDEA-186, whose whole difficulty is that a recurring cap
    refusal *"looks exactly like the guard working"*.

    A test may assert on the message here because the message IS the deliverable
    (AC-3 forbids it as a proxy for behaviour, which is a different thing).
    """
    team = _insert_team(db)
    thirteen = [f"p-{i}" for i in range(1, 14)]
    ScoutingLoader(db).load_team(_crawl(team, _roster(*thirteen), batters=["p-1"]))

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ScoutingLoader(db).load_team(_crawl(team, _roster("p-1"), batters=["p-1"]))

    warnings = [w for w in _roster_warnings(caplog) if "REFUSED" in w]
    assert len(warnings) == 1
    message = warnings[0]
    assert "refused_by=cap" in message
    assert "genuine_departure_count=12" in message, "the CAP's own count"
    from src.db.reconcile_at_load import MAX_ROSTER_DEPARTURES

    assert f"MAX_ROSTER_DEPARTURES={MAX_ROSTER_DEPARTURES}" in message
    assert "SOLE guard" in message, (
        "an operator meeting a recurring cap refusal must be told there is "
        "nothing beneath it"
    )
    # The floor's numbers are gone: they no longer decide anything.
    # Both asserted as PARAMETER tokens (trailing ``=``), not bare words: the
    # message itself says "there is no floor ratio beneath it" in English, one
    # underscore away from the old parameter name. See the note in
    # ``test_catastrophic_roster_shrink_refuses_on_the_cap``.
    assert "floor_ratio=" not in message
    assert "fresh_comparable_count=" not in message
