"""Player-line grain reconcile-at-load tests (E-267-03, closes H1).

The defect: the per-player stat writers iterate only the incoming payload and do
no set-difference delete, so a player dropped from a boxscore between runs keeps
their ``player_game_*`` row forever -- and since ``get_season_batting`` /
``get_season_pitching`` SUM those rows at query time, that team's season totals
stay permanently inflated.

The load-bearing correctness rule here is NOT the retire, it is the REFUSAL: a
"scored but EMPTY" boxscore (envelope and lineup/pitching categories present,
every per-player ``stats`` array ``[]``) is the MODAL opponent-scouting shape.
An implementation that treats a bare HTTP 200 as authority would retire live
lines on the most common payload in the data. Several tests below exist purely
to pin that.

All tests drive the real ``ScoutingLoader.load_team`` entry point against a
migrated on-disk SQLite database. No network calls.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from migrations.apply_migrations import run_migrations
from src.api.db import get_season_batting, get_season_pitching
from src.gamechanger.loaders.scouting_loader import ScoutingLoader

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


def _game_entry(game_id: str = _GAME, opponent: str = "Opp Town") -> dict:
    return {
        "id": game_id,
        "game_status": "completed",
        "home_away": "home",
        "start_ts": "2026-04-10T18:00:00Z",
        "timezone": "America/Chicago",
        "score": {"team": 5, "opponent_team": 3},
        "opponent_team": {"name": opponent},
    }


def _player(pid: str, first: str | None = None, last: str | None = None) -> dict:
    """One entry of a boxscore ``players`` array.

    Names default to being DERIVED FROM THE ID and therefore distinct per
    player. That is not cosmetic: ``dedup_team_players`` merges same-team players
    whose last names match and whose first names are prefixes of one another, so
    a shared placeholder name would silently collapse every fixture player into
    one and make these tests measure the dedup sweep instead of the reconcile.
    Tests that WANT a merge pass explicit prefix names.
    """
    suffix = pid.replace("-", "")
    return {
        "id": pid,
        "first_name": first if first is not None else f"First{suffix}",
        "last_name": last if last is not None else f"Last{suffix}",
        "number": "9",
    }


def _batting_row(pid: str, ab: int = 3, h: int = 1) -> dict:
    return {
        "player_id": pid,
        "stats": {"AB": ab, "R": 1, "H": h, "RBI": 1, "BB": 0, "SO": 0},
    }


def _pitching_row(pid: str, ip: float = 2.0) -> dict:
    return {
        "player_id": pid,
        "stats": {"IP": ip, "H": 1, "R": 0, "ER": 0, "BB": 0, "SO": 2},
    }


def _team_block(
    batters: list[str],
    pitchers: list[str] | None = None,
    *,
    names: dict[str, tuple[str, str]] | None = None,
    empty_stats: bool = False,
) -> dict:
    """One team's boxscore block.

    ``empty_stats=True`` produces the MODAL scored-but-EMPTY shape: the players
    array and both group categories are present, but every per-player ``stats``
    list is ``[]``.
    """
    pitchers = pitchers if pitchers is not None else []
    names = names or {}
    listed = [
        _player(pid, *names[pid]) if pid in names else _player(pid)
        for pid in dict.fromkeys([*batters, *pitchers])
    ]
    return {
        "players": listed,
        "groups": [
            {
                "category": "lineup",
                "stats": [] if empty_stats else [_batting_row(p) for p in batters],
                "extra": [],
            },
            {
                "category": "pitching",
                "stats": [] if empty_stats else [_pitching_row(p) for p in pitchers],
                "extra": [],
            },
        ],
    }


def _boxscore(
    own_key: str,
    own_block: dict,
    opp_block: dict | None = None,
    opp_key: str = _OPP_UUID,
) -> dict:
    return {
        own_key: own_block,
        opp_key: opp_block if opp_block is not None else _team_block([], []),
    }


def _crawl(
    team_id: int,
    boxscores: dict[str, dict],
    games: list[dict] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        team_id=team_id,
        roster=[],
        games=games if games is not None else [_game_entry()],
        boxscores=boxscores,
        schedule_fetch_ok=True,
    )


def _batting_players(db: sqlite3.Connection, game_id: str = _GAME) -> set[str]:
    return {
        r[0]
        for r in db.execute(
            "SELECT player_id FROM player_game_batting WHERE game_id = ?", (game_id,)
        )
    }


def _pitching_players(db: sqlite3.Connection, game_id: str = _GAME) -> set[str]:
    return {
        r[0]
        for r in db.execute(
            "SELECT player_id FROM player_game_pitching WHERE game_id = ?", (game_id,)
        )
    }


def _retire_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING and "Player-line retire" in r.getMessage()
    ]


# ---------------------------------------------------------------------------
# AC-1 / AC-6: the inflated season aggregate
# ---------------------------------------------------------------------------


def test_dropped_player_line_is_retired_and_aggregate_corrected(
    db: sqlite3.Connection,
) -> None:
    """AC-1/AC-6: a player dropped from the fresh boxscore stops inflating totals.

    Pre-fix this fails on the aggregate assertion: the load never deleted the
    stale row, so ``get_season_batting`` kept SUMming the departed player.
    """
    db.row_factory = sqlite3.Row
    team = _insert_team(db)

    ScoutingLoader(db).load_team(
        _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(["p-1", "p-2", "p-3"]))})
    )
    assert _batting_players(db) == {"p-1", "p-2", "p-3"}
    before = {r["player_id"]: r for r in get_season_batting(db, team, _SEASON)}
    assert set(before) == {"p-1", "p-2", "p-3"}

    # Re-scout: the scorekeeper removed p-2's mis-credited line.
    ScoutingLoader(db).load_team(
        _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(["p-1", "p-3"]))})
    )

    assert _batting_players(db) == {"p-1", "p-3"}
    after = {r["player_id"]: r for r in get_season_batting(db, team, _SEASON)}
    assert set(after) == {"p-1", "p-3"}, "the dropped player still inflates the season"


def test_dropped_pitcher_line_is_retired(db: sqlite3.Connection) -> None:
    """AC-1: the pitching table is reconciled too, independently of batting."""
    db.row_factory = sqlite3.Row
    team = _insert_team(db)

    ScoutingLoader(db).load_team(
        _crawl(
            team,
            {_GAME: _boxscore(_SLUG_A, _team_block(["p-1", "p-2"], ["p-1", "p-2"]))},
        )
    )
    assert _pitching_players(db) == {"p-1", "p-2"}

    ScoutingLoader(db).load_team(
        _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(["p-1", "p-2"], ["p-1"]))})
    )

    assert _pitching_players(db) == {"p-1"}
    # Batting is untouched -- the two tables carry different populations.
    assert _batting_players(db) == {"p-1", "p-2"}
    assert {r["player_id"] for r in get_season_pitching(db, team, _SEASON)} == {"p-1"}


def test_position_player_absent_from_pitching_is_not_retired_from_batting(
    db: sqlite3.Connection,
) -> None:
    """The two tables are diffed independently, never merged.

    A position player is legitimately absent from every pitching group; a single
    merged diff would read that as a removal.
    """
    team = _insert_team(db)

    ScoutingLoader(db).load_team(
        _crawl(
            team,
            {_GAME: _boxscore(_SLUG_A, _team_block(["p-1", "p-2", "p-3"], ["p-1"]))},
        )
    )
    ScoutingLoader(db).load_team(
        _crawl(
            team,
            {_GAME: _boxscore(_SLUG_A, _team_block(["p-1", "p-2", "p-3"], ["p-1"]))},
        )
    )

    assert _batting_players(db) == {"p-1", "p-2", "p-3"}
    assert _pitching_players(db) == {"p-1"}


def test_opponent_block_players_are_not_retired(db: sqlite3.Connection) -> None:
    """Both teams' blocks are written under ONE perspective, so the opponent's
    rows must be covered by their OWN block's fresh set.

    Fixture margin is deliberate: own is strictly LARGER than opp (4 vs 2). If
    the opponent block were dropped from the candidate set, the own block's
    fresh ids alone would give ``comparable = 4`` against ``prior = 6``, clearing
    ``4 >= 3`` and deleting both opponent lines. A symmetric fixture (2 vs 2)
    would sit exactly on the inclusive ``2 >= 2.0`` boundary and could pass
    without the per-block scoping -- and an own-smaller fixture would pass
    vacuously, silently disarming this story's highest-consequence guard.
    """
    team = _insert_team(db)
    own = _team_block(["p-1", "p-2", "p-3", "p-4"])
    opp = _team_block(["o-1", "o-2"])

    ScoutingLoader(db).load_team(_crawl(team, {_GAME: _boxscore(_SLUG_A, own, opp)}))
    assert _batting_players(db) == {"p-1", "p-2", "p-3", "p-4", "o-1", "o-2"}

    ScoutingLoader(db).load_team(_crawl(team, {_GAME: _boxscore(_SLUG_A, own, opp)}))

    assert _batting_players(db) == {"p-1", "p-2", "p-3", "p-4", "o-1", "o-2"}


def test_opponent_blocks_own_dropped_player_is_retired(
    db: sqlite3.Connection,
) -> None:
    """The OPPONENT block is genuinely reconciled, not silently skipped.

    Under per-block scoping, rows whose ``team_id`` matches no block are left
    untouched -- so omitting the opponent block from the candidate set can no
    longer WIPE its rows (the old union failure mode is now structurally
    impossible). The remaining hazard flips direction: the opponent side would
    never be reconciled at all, and H1 would persist there forever.

    This is the test that discriminates that: drop one opponent player from a
    POPULATED opponent block and assert the stale line is retired. It fails if
    the opponent block is dropped from the candidate set.
    """
    team = _insert_team(db)
    own = _team_block(["p-1", "p-2"])

    ScoutingLoader(db).load_team(
        _crawl(
            team,
            {_GAME: _boxscore(_SLUG_A, own, _team_block(["o-1", "o-2", "o-3"]))},
        )
    )
    assert _batting_players(db) == {"p-1", "p-2", "o-1", "o-2", "o-3"}

    ScoutingLoader(db).load_team(
        _crawl(team, {_GAME: _boxscore(_SLUG_A, own, _team_block(["o-1", "o-3"]))})
    )

    assert _batting_players(db) == {"p-1", "p-2", "o-1", "o-3"}


def test_half_populated_payload_does_not_retire_the_empty_blocks_lines(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """A populated OWN block must not authorize retiring an EMPTY opponent block.

    The half-populated payload is real: the scouted team's book is filled in
    while the opponent's side comes back with ``stats: []``. With one global
    "populated" flag the populated half supplies the whole numerator -- 5 own
    fresh ids against a prior of 5 own + 3 opponent = 8, clearing ``5 >= 4`` --
    and all three live opponent lines are hard-deleted.

    Sized so the ratio WOULD otherwise pass (own 5 >= opp-prior 3), or this
    test would pass for the wrong reason.
    """
    team = _insert_team(db)
    own = _team_block(["p-1", "p-2", "p-3", "p-4", "p-5"])
    opp_full = _team_block(["o-1", "o-2", "o-3"])

    ScoutingLoader(db).load_team(
        _crawl(team, {_GAME: _boxscore(_SLUG_A, own, opp_full)})
    )
    assert _batting_players(db) == {
        "p-1", "p-2", "p-3", "p-4", "p-5", "o-1", "o-2", "o-3",
    }

    # Re-scout: own block still populated, opponent block scored-but-EMPTY.
    opp_empty = _team_block(["o-1", "o-2", "o-3"], empty_stats=True)
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ScoutingLoader(db).load_team(
            _crawl(team, {_GAME: _boxscore(_SLUG_A, own, opp_empty)})
        )

    assert _batting_players(db) == {
        "p-1", "p-2", "p-3", "p-4", "p-5", "o-1", "o-2", "o-3",
    }, "the empty opponent block's live lines were retired"
    warnings = _retire_warnings(caplog)
    assert warnings, "the empty block's refusal must be logged"
    assert any("payload_populated=False" in w for w in warnings)


def test_half_populated_mirror_empty_own_block_is_not_retired(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-6(g) mirror: a populated OPPONENT block must not authorize the OWN block.

    The failure is symmetric -- which side is populated is irrelevant, only that
    ONE of them is. Here the opponent block carries 5 fresh ids against a prior
    of 3 own + 5 opponent = 8, so a payload-level flag again clears ``5 >= 4``
    and deletes all three live OWN lines.

    Worth testing separately rather than assuming symmetry: own and opponent are
    NOT interchangeable in this code path (own resolves from the slug key,
    opponent from a UUID key, and they take different branches through
    ``_resolve_team_ids``), so a fix that happened to special-case one side
    would pass the primary test and fail here.
    """
    team = _insert_team(db)
    own_full = _team_block(["p-1", "p-2", "p-3"])
    opp = _team_block(["o-1", "o-2", "o-3", "o-4", "o-5"])

    ScoutingLoader(db).load_team(
        _crawl(team, {_GAME: _boxscore(_SLUG_A, own_full, opp)})
    )
    assert _batting_players(db) == {
        "p-1", "p-2", "p-3", "o-1", "o-2", "o-3", "o-4", "o-5",
    }

    own_empty = _team_block(["p-1", "p-2", "p-3"], empty_stats=True)
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ScoutingLoader(db).load_team(
            _crawl(team, {_GAME: _boxscore(_SLUG_A, own_empty, opp)})
        )

    assert _batting_players(db) == {
        "p-1", "p-2", "p-3", "o-1", "o-2", "o-3", "o-4", "o-5",
    }, "the empty OWN block's live lines were retired"
    warnings = _retire_warnings(caplog)
    assert warnings and any("payload_populated=False" in w for w in warnings)


# ---------------------------------------------------------------------------
# AC-2 / AC-6(a,b,c): bias to refuse -- the load-bearing rule
# ---------------------------------------------------------------------------


def test_scored_but_empty_boxscore_retires_nothing(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-2/AC-6(a): the MODAL shape -- categories present, per-player stats [].

    A bare HTTP 200 is not authority. This payload IS a 200 and IS well-formed;
    only the per-player ``stats`` arrays are empty. Retiring here would wipe
    live lines on the most common opponent-scouting payload in the data.
    """
    team = _insert_team(db)
    ScoutingLoader(db).load_team(
        _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(["p-1", "p-2", "p-3"]))})
    )
    assert _batting_players(db) == {"p-1", "p-2", "p-3"}

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ScoutingLoader(db).load_team(
            _crawl(
                team,
                {
                    _GAME: _boxscore(
                        _SLUG_A,
                        _team_block(["p-1", "p-2", "p-3"], empty_stats=True),
                    )
                },
            )
        )

    assert _batting_players(db) == {"p-1", "p-2", "p-3"}
    warnings = _retire_warnings(caplog)
    assert warnings, "a refusal must be logged"
    assert all("REFUSED" in w for w in warnings)
    assert any("payload_populated=False" in w for w in warnings)


def test_missing_boxscore_404_retires_nothing(db: sqlite3.Connection) -> None:
    """AC-2/AC-6(b): a 404 yields no payload, so no reconcile can run.

    The crawler logs and skips a game whose boxscore fetch 404s, so the game
    never reaches ``load_payload``. The refusal is therefore structural: with no
    payload there is no fresh set to diff against, and the prior lines stand.
    """
    team = _insert_team(db)
    ScoutingLoader(db).load_team(
        _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(["p-1", "p-2"]))})
    )
    assert _batting_players(db) == {"p-1", "p-2"}

    # Re-scout: game still on the schedule, boxscore fetch 404'd -> absent.
    ScoutingLoader(db).load_team(_crawl(team, {}))

    assert _batting_players(db) == {"p-1", "p-2"}


def test_credential_expiry_401_aborts_before_any_load(
    db: sqlite3.Connection,
) -> None:
    """AC-2/AC-6(c): a 401 propagates out of the crawl -- nothing is loaded.

    Unlike a 404 (per-game skip), ``CredentialExpiredError`` is deliberately
    re-raised by the boxscore fetch loop, so the whole crawl aborts and no
    loader ever runs. Asserted at the CRAWLER, since that is where the
    distinction actually lives.
    """
    from src.gamechanger.client import CredentialExpiredError
    from src.gamechanger.crawlers.scouting import ScoutingCrawler

    team = _insert_team(db)
    ScoutingLoader(db).load_team(
        _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(["p-1", "p-2"]))})
    )
    before = _batting_players(db)
    assert before == {"p-1", "p-2"}

    def _get(path: str, **_kwargs):
        # The roster fetch must SUCCEED so the crawl reaches the boxscore loop --
        # otherwise the roster's own except-clause aborts first and the boxscore
        # re-raise this test exists to prove is never exercised.
        if path.endswith("/players"):
            return []
        raise CredentialExpiredError("token expired")

    client = MagicMock()
    client.get_public.return_value = [_game_entry()]
    client.get.side_effect = _get

    with pytest.raises(CredentialExpiredError):
        ScoutingCrawler(client, db).scout_team(_SLUG_A)

    assert _batting_players(db) == before


def test_catastrophic_shrink_of_the_player_set_retires_nothing(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """The floor ratio applies at this grain too: a mostly-vanished lineup refuses.

    Four prior players, a fresh payload listing one. That is a 0.25 overlap,
    under the 0.5 floor -- far more likely a truncated payload than three
    genuine removals, so nothing is retired.
    """
    team = _insert_team(db)
    ScoutingLoader(db).load_team(
        _crawl(
            team,
            {_GAME: _boxscore(_SLUG_A, _team_block(["p-1", "p-2", "p-3", "p-4"]))},
        )
    )
    assert len(_batting_players(db)) == 4

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ScoutingLoader(db).load_team(
            _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(["p-1"]))})
        )

    assert _batting_players(db) == {"p-1", "p-2", "p-3", "p-4"}
    warnings = _retire_warnings(caplog)
    assert warnings and all("REFUSED" in w for w in warnings)
    # It must be the RATIO that fired, not the populated-payload gate.
    assert any("payload_populated=True" in w for w in warnings)


def test_shrink_at_the_floor_still_retires(db: sqlite3.Connection) -> None:
    """The floor is a boundary, not a blanket veto: exactly 0.5 retires."""
    team = _insert_team(db)
    ScoutingLoader(db).load_team(
        _crawl(
            team,
            {_GAME: _boxscore(_SLUG_A, _team_block(["p-1", "p-2", "p-3", "p-4"]))},
        )
    )

    ScoutingLoader(db).load_team(
        _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(["p-1", "p-2"]))})
    )

    assert _batting_players(db) == {"p-1", "p-2"}


# ---------------------------------------------------------------------------
# AC-3 / AC-5: perspective scoping and leaf-only deletes
# ---------------------------------------------------------------------------


def test_other_perspectives_rows_are_never_retired(db: sqlite3.Connection) -> None:
    """AC-3/AC-6(d): the diff AND the delete are perspective-scoped.

    Fixture design matters here, and a simpler one does NOT discriminate. Since
    the reconcile is now also scoped by ``team_id``, two perspectives whose rows
    carry DISJOINT ``team_id`` values can never collide -- the team predicate
    alone would keep them apart, and dropping the perspective predicate would
    change nothing.

    So this builds the case where they genuinely OVERLAP: each perspective
    reports BOTH teams (its own block plus the opponent block), so rows with
    ``team_id = Team A`` exist under perspective A (``a-*``) AND under
    perspective B (``aa-*``, B's view of the same humans, with GC's different
    per-perspective ids).

    Sized so that dropping the perspective predicate from the prior-id query
    DELETES rather than merely refusing: without it, prior for ``team_id = A``
    is 8 rows (6 ``a-*`` + 2 ``aa-*``), fresh is the 5 surviving ``a-*``, and
    ``5 >= 4`` clears the floor -- so ``a-6`` AND both of B's ``aa-*`` rows are
    reaped, corrupting B's report.
    """
    team_a = _insert_team(db, _SLUG_A, _UUID_A, "Team A")
    team_b = _insert_team(db, _SLUG_B, _UUID_B, "Team B")

    a_own = ["a-1", "a-2", "a-3", "a-4", "a-5", "a-6"]
    ScoutingLoader(db).load_team(
        _crawl(
            team_a,
            {
                _GAME: _boxscore(
                    _SLUG_A,
                    _team_block(a_own),
                    _team_block(["bb-1", "bb-2"]),
                )
            },
            games=[_game_entry(opponent="Team B")],
        )
    )
    # B's view of team A deliberately SHARES one player_id with A's own view
    # (``a-6``). GC normally issues distinct ids per perspective, but a mutation
    # detector need not model the common case: this shared (player_id, team_id)
    # is what makes an unscoped DELETE observable -- without it, A's delete of
    # ``a-6`` cannot collide with any of B's rows no matter how it is scoped.
    ScoutingLoader(db).load_team(
        _crawl(
            team_b,
            {
                _GAME: _boxscore(
                    _SLUG_B,
                    _team_block(["b-1", "b-2", "b-3"]),
                    _team_block(["aa-1", "aa-2", "a-6"]),
                )
            },
            games=[_game_entry(opponent="Team A")],
        )
    )

    def _by_perspective(persp: int) -> set[str]:
        return {
            r[0]
            for r in db.execute(
                "SELECT player_id FROM player_game_batting "
                "WHERE game_id = ? AND perspective_team_id = ?",
                (_GAME, persp),
            )
        }

    # Precondition: both perspectives really do hold rows for team_a, or the
    # overlap this test depends on does not exist and it proves nothing.
    team_a_perspectives = {
        r[0]
        for r in db.execute(
            "SELECT DISTINCT perspective_team_id FROM player_game_batting "
            "WHERE game_id = ? AND team_id = ?",
            (_GAME, team_a),
        )
    }
    assert team_a_perspectives == {team_a, team_b}, (
        "fixture must produce team_a rows under BOTH perspectives"
    )
    assert _by_perspective(team_b) == {"b-1", "b-2", "b-3", "aa-1", "aa-2", "a-6"}

    # A re-scouts without a-6.
    ScoutingLoader(db).load_team(
        _crawl(
            team_a,
            {
                _GAME: _boxscore(
                    _SLUG_A,
                    _team_block(["a-1", "a-2", "a-3", "a-4", "a-5"]),
                    _team_block(["bb-1", "bb-2"]),
                )
            },
            games=[_game_entry(opponent="Team B")],
        )
    )

    assert _by_perspective(team_a) == {
        "a-1", "a-2", "a-3", "a-4", "a-5", "bb-1", "bb-2",
    }
    assert _by_perspective(team_b) == {
        "b-1", "b-2", "b-3", "aa-1", "aa-2", "a-6",
    }, "cross-perspective wipe: B's rows were reaped by A's reconcile"


def test_perspective_predicate_on_the_diff_is_observable_in_the_proposal(
    db: sqlite3.Connection,
) -> None:
    """AC-3, diff half: the PROPOSAL must not name another perspective's players.

    The diff's ``perspective_team_id`` predicate cannot be caught in row state --
    the DELETE is the only thing that mutates rows, and its own predicate blocks
    the damage even when the diff over-proposes. So this asserts the RESULT
    OBJECT instead, which records exactly what the diff decided to retire.

    With the diff unscoped, prior for ``team_id = Team A`` picks up B's ``aa-*``
    rows and the retire proposal becomes ``[a-6, aa-1, aa-2]`` -- visibly wrong,
    and reported as such in the WARN, even though no B rows are removed.
    Asserted via a direct helper call rather than through the loader so the
    proposal is inspected structurally rather than parsed out of log text.
    """
    from src.db.reconcile_at_load import PlayerLineBlock, retire_absent_player_lines

    team_a = _insert_team(db, _SLUG_A, _UUID_A, "Team A")
    team_b = _insert_team(db, _SLUG_B, _UUID_B, "Team B")

    a_own = ["a-1", "a-2", "a-3", "a-4", "a-5", "a-6"]
    ScoutingLoader(db).load_team(
        _crawl(
            team_a,
            {_GAME: _boxscore(_SLUG_A, _team_block(a_own), _team_block(["bb-1"]))},
            games=[_game_entry(opponent="Team B")],
        )
    )
    ScoutingLoader(db).load_team(
        _crawl(
            team_b,
            {
                _GAME: _boxscore(
                    _SLUG_B, _team_block(["b-1"]), _team_block(["aa-1", "aa-2"])
                )
            },
            games=[_game_entry(opponent="Team A")],
        )
    )

    result = retire_absent_player_lines(
        db,
        game_id=_GAME,
        perspective_team_id=team_a,
        blocks=[
            PlayerLineBlock(
                team_id=team_a,
                batting_player_ids=frozenset(a_own[:-1]),  # a-6 dropped
                pitching_player_ids=frozenset(),
                populated=True,
            )
        ],
    )

    proposal = result.retired.get(("player_game_batting", team_a), [])
    assert proposal == ["a-6"], (
        f"the diff proposed {proposal} -- an unscoped diff pulls in the other "
        "perspective's rows (aa-1, aa-2)"
    )


def test_absent_opponent_block_leaves_an_observable_uncovered_residual(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """Uncovered rows are REPORTED, not retired (and not silently ignored).

    A boxscore whose only key is the own-team slug has no opponent block at all
    (``_detect_team_keys`` finds no UUID key), so the opponent's prior rows are
    covered by nothing. They must NOT be retired -- a payload carrying no
    evidence for a side cannot authorize deleting that side -- but leaving that
    silent would make the staleness permanent AND invisible.

    Asserts both halves: the rows survive, and the residual is surfaced on the
    result/log so it is monitorable.
    """
    team = _insert_team(db)

    ScoutingLoader(db).load_team(
        _crawl(
            team,
            {
                _GAME: _boxscore(
                    _SLUG_A, _team_block(["p-1", "p-2"]), _team_block(["o-1", "o-2"])
                )
            },
        )
    )
    assert _batting_players(db) == {"p-1", "p-2", "o-1", "o-2"}

    # Re-scout: boxscore carries ONLY the own-team key -> no opponent block.
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ScoutingLoader(db).load_team(
            _crawl(team, {_GAME: {_SLUG_A: _team_block(["p-1", "p-2"])}})
        )

    assert _batting_players(db) == {"p-1", "p-2", "o-1", "o-2"}, (
        "uncovered opponent rows must never be retired"
    )
    residual = [
        r.getMessage()
        for r in caplog.records
        if "NO block in this payload covers" in r.getMessage()
    ]
    assert residual, "the uncovered residual must be observable, not silent"

    # The log must carry enough to chase a downstream symptom back to its cause:
    # the game, the perspective, the uncovered team, and HOW MANY rows it holds.
    # `_completed_games_with_data` counts a game by perspective alone (verified:
    # generator.py, both EXISTS subqueries filter perspective_team_id with no
    # team_id predicate), so these rows can inflate N and freeze the "Through
    # {date}" line -- an operator seeing that needs the row count to recognize it.
    message = residual[0]
    opp_team_id = db.execute(
        "SELECT DISTINCT team_id FROM player_game_batting "
        "WHERE game_id = ? AND player_id = 'o-1'",
        (_GAME,),
    ).fetchone()[0]
    assert _GAME in message
    assert f"{opp_team_id}: 2" in message, (
        f"the per-team row count is missing from the diagnostic: {message}"
    )


def test_players_parent_row_survives_a_line_retire(db: sqlite3.Connection) -> None:
    """AC-5/AC-6(e): only the leaf stat row is deleted, never the players row.

    Other games, other perspectives, and ``team_rosters`` all reference the
    parent, so deleting it would cascade damage far outside this game.
    """
    team = _insert_team(db)
    ScoutingLoader(db).load_team(
        _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(["p-1", "p-2", "p-3"]))})
    )
    ScoutingLoader(db).load_team(
        _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(["p-1", "p-3"]))})
    )

    assert _batting_players(db) == {"p-1", "p-3"}
    assert db.execute(
        "SELECT COUNT(*) FROM players WHERE player_id = 'p-2'"
    ).fetchone()[0] == 1
    assert db.execute(
        "SELECT COUNT(*) FROM team_rosters WHERE player_id = 'p-2'"
    ).fetchone()[0] == 1


def test_a_players_other_games_are_untouched(db: sqlite3.Connection) -> None:
    """The delete is game-scoped: the same player's line in another game stands."""
    team = _insert_team(db)
    other = "game-0002"
    games = [_game_entry(), _game_entry(other, opponent="Opp Two")]
    games[1]["start_ts"] = "2026-04-12T18:00:00Z"

    ScoutingLoader(db).load_team(
        _crawl(
            team,
            {
                _GAME: _boxscore(_SLUG_A, _team_block(["p-1", "p-2", "p-3"])),
                other: _boxscore(_SLUG_A, _team_block(["p-1", "p-2", "p-3"])),
            },
            games=games,
        )
    )

    ScoutingLoader(db).load_team(
        _crawl(
            team,
            {
                _GAME: _boxscore(_SLUG_A, _team_block(["p-1", "p-3"])),
                other: _boxscore(_SLUG_A, _team_block(["p-1", "p-2", "p-3"])),
            },
            games=games,
        )
    )

    assert _batting_players(db, _GAME) == {"p-1", "p-3"}
    assert _batting_players(db, other) == {"p-1", "p-2", "p-3"}


# ---------------------------------------------------------------------------
# AC-4 / AC-6(f): GAP-3 -- the reconcile must run BEFORE the dedup sweep
# ---------------------------------------------------------------------------


def test_reconcile_runs_before_dedup_so_a_merged_player_is_not_retired(
    db: sqlite3.Connection,
) -> None:
    """AC-4/AC-6(f): a player who survives only because of the ORDERING.

    Setup: run 1 loads "John Smith" (``p-long``) plus three others. Run 2's
    payload re-issues that human under a NEW id "J Smith" (``p-short``) -- a
    prefix-name variant, exactly what ``dedup_team_players`` exists to collapse
    (it merges the shorter name INTO the longer, so ``p-long`` is the canonical
    that survives).

    Ordering matters because the two passes disagree about which ids exist:

    * Reconcile FIRST (correct): prior still holds the raw ``p-long`` row, the
      fresh payload holds ``p-short``, and the freshly-written ``p-short`` row is
      also in prior -- so 4 of 5 prior ids are vouched for, the stale ``p-long``
      row is retired, and dedup then merges ``p-short`` -> ``p-long``, leaving one
      line carrying the FRESH stats.
    * Reconcile AFTER dedup (wrong): dedup has already re-pointed the fresh row
      onto ``p-long``, so prior holds ``p-long`` while the raw payload holds
      ``p-short`` -- ``p-long`` reads as absent and the LIVE, freshly-merged line
      is deleted.

    The three extra players keep the overlap above the 0.5 floor, so the health
    gate does NOT mask the ordering: this test discriminates on ordering alone.
    """
    names_long = {"p-long": ("John", "Smith")}
    names_short = {"p-short": ("J", "Smith")}

    team = _insert_team(db)
    ScoutingLoader(db).load_team(
        _crawl(
            team,
            {
                _GAME: _boxscore(
                    _SLUG_A,
                    _team_block(
                        ["p-long", "p-a", "p-b", "p-c"], names=names_long
                    ),
                )
            },
        )
    )
    assert _batting_players(db) == {"p-long", "p-a", "p-b", "p-c"}

    ScoutingLoader(db).load_team(
        _crawl(
            team,
            {
                _GAME: _boxscore(
                    _SLUG_A,
                    _team_block(
                        ["p-short", "p-a", "p-b", "p-c"], names=names_short
                    ),
                )
            },
        )
    )

    # dedup collapsed p-short into the canonical p-long; the line must SURVIVE.
    survivors = _batting_players(db)
    assert "p-long" in survivors, (
        "the merged player's line was retired -- the reconcile ran after dedup"
    )
    assert survivors == {"p-long", "p-a", "p-b", "p-c"}
