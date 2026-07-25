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


def test_catastrophic_roster_shrink_refuses_on_the_floor(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """The flat floor still applies underneath the cap (it can only tighten).

    Sized so the FLOOR is what fires: 14 prior, 1 fresh -> ``1 >= 7`` fails.
    Complements the test above, where the floor passes and the cap fires.
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
    assert "floor_ratio" in warnings[0], "the floor should be the named cause here"


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
