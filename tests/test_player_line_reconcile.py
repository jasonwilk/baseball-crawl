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
from contextlib import contextmanager
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


def _player(
    pid: str,
    first: str | None = None,
    last: str | None = None,
    number: str | None = None,
) -> dict:
    """One entry of a boxscore ``players`` array.

    Names default to being DERIVED FROM THE ID and therefore distinct per
    player. That is not cosmetic: ``dedup_team_players`` merges same-team players
    whose last names match and whose first names are prefixes of one another, so
    a shared placeholder name would silently collapse every fixture player into
    one and make these tests measure the dedup sweep instead of the reconcile.
    Tests that WANT a merge pass explicit prefix names.

    ``number`` is derived from the id for exactly the same reason, one field
    over (E-276-01). The AC-15 matched-victim diagnostic treats a shared
    ``team_rosters.jersey_number`` as evidence of a re-issued ``player_id``, so
    a constant placeholder number would make every fixture player match every
    other one and the diagnostic's negative control would be unwritable.
    """
    suffix = pid.replace("-", "")
    return {
        "id": pid,
        "first_name": first if first is not None else f"First{suffix}",
        "last_name": last if last is not None else f"Last{suffix}",
        "number": number if number is not None else f"n{suffix}",
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
    numbers: dict[str, str] | None = None,
    empty_stats: bool = False,
) -> dict:
    """One team's boxscore block.

    ``empty_stats=True`` produces the MODAL scored-but-EMPTY shape: the players
    array and both group categories are present, but every per-player ``stats``
    list is ``[]``.

    ``names`` / ``numbers`` override the id-derived defaults for the tests that
    deliberately construct a same-human collision (E-276-01 AC-15).
    """
    pitchers = pitchers if pitchers is not None else []
    names = names or {}
    numbers = numbers or {}
    listed = [
        _player(pid, *names.get(pid, (None, None)), number=numbers.get(pid))
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
# E-276-01 helpers: reaching the structural gate record
# ---------------------------------------------------------------------------


@contextmanager
def _capture_player_line_results():
    """Call-through spy yielding ``[(game_id, PlayerLineRetireResult), ...]``.

    The gate record mandated by TN-11 is NOT reachable by default from a test
    driving ``ScoutingLoader.load_team``: the player-line wrapper returns only an
    int error increment and discards the result object. TN-17 sanctions two
    means; this is the spy.

    Patches the name in ``game_loader``, NOT in ``reconcile_at_load``. The
    player-line helper is imported at MODULE level there, so rebinding the source
    module's attribute would not be seen at the call site -- and a test that gets
    this wrong and asserts only on row survival passes for the wrong reason,
    because the spy silently never fires. **That is why every test using this
    asserts positively that a result object was captured.**

    Each entry is appended AFTER the wrapped call returns, so a non-empty list
    certifies the helper COMPLETED rather than merely that it was entered.
    """
    from unittest.mock import patch

    from src.db.reconcile_at_load import retire_absent_player_lines
    from src.gamechanger.loaders import game_loader as _game_loader

    captured: list[tuple[str, object]] = []

    def _call_through(*args, **kwargs):
        result = retire_absent_player_lines(*args, **kwargs)
        captured.append((kwargs["game_id"], result))
        return result

    with patch.object(
        _game_loader, "retire_absent_player_lines", side_effect=_call_through
    ):
        yield captured


def _assert_captured_result_objects(captured) -> None:
    """The spy fired AND recorded real result objects, not ``None``s."""
    from src.db.reconcile_at_load import PlayerLineRetireResult

    assert captured, (
        "the player-line reconcile never ran -- row survival alone is satisfied "
        "by a spy that never fired (wrong patch module)"
    )
    for _game_id, result in captured:
        assert isinstance(result, PlayerLineRetireResult), (
            f"the spy recorded {result!r}, not a result object"
        )


def _batting_gate(result, team_id: int):
    """The keyed batting gate record for one team block.

    Keyed, never scalar: this grain evaluates up to FOUR independent gates per
    call (2 team blocks x 2 stat tables), each with its own prior count and
    verdict, so a scalar field would capture only the last iteration and the
    "9, not 18" assertion would be unambiguous only by accident.
    """
    return result.gate_outcomes[("player_game_batting", team_id)]


def _accumulate_then_delete_fires(prev, cur) -> bool:
    """The regime-B detection predicate, across invocations (E-276-01 AC-14).

    TEST-SIDE ONLY, and it cannot move into the production record: it needs the
    PREVIOUS invocation's record for the same key, and nothing in production
    retains one -- the record is built per call and returned in the result
    dataclass. Persisting it would be a snapshot table by another name, which
    TN-2 rejects outright.

    No tolerance and no arithmetic. The ``> 0`` clause is REQUIRED, not
    defensive: without it a game ADDED on invocation 2 records
    ``prior=0, permitted=True`` under the vacuous-permit rule, so invocation 3's
    perfectly clean load reads as growth-with-permit and the predicate misfires
    on every new game of the season.
    """
    return (
        cur.gate_permitted is True
        and cur.gate_prior_count > prev.gate_prior_count
        and prev.gate_prior_count > 0
    )


def _fires_without_the_positivity_clause(prev, cur) -> bool:
    """The same predicate with the ``> 0`` clause DROPPED -- the control."""
    return cur.gate_permitted is True and cur.gate_prior_count > prev.gate_prior_count


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
    NOT interchangeable in this code path -- they take different branches through
    ``_resolve_team_ids`` (own is the loader's own ``TeamRef``; the opponent is
    resolved by identifier, then name, then a sentinel stub) -- so a fix that
    happened to special-case one side would pass the primary test and fail here.
    The branch split is NOT slug-vs-UUID: ``_detect_team_keys`` classifies by
    IDENTITY, and a key's form does not mark which side it is (both keys are
    slugs on a minority of live payloads). This fixture happens to use a slug
    own key, which is the common pairing.
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


# ---------------------------------------------------------------------------
# E-270-04: the REAL per-game skip path
# ---------------------------------------------------------------------------
# The test directly above is CORRECT but INSUFFICIENT, and the gap is specific:
# its ``{}`` boxscores dict trips the global ``if not boxscores`` short-circuit
# in ``_load_team_core``, so the reconcile never runs at all. It therefore says
# nothing about the PER-GAME shape -- one previously-loaded game's key absent
# from an otherwise-POPULATED dict -- which is what a real per-game 404 produces
# and what the loader's "iterate only present boxscores" behaviour actually
# governs. Mutation-verified: deleting that global guard does not fail it.
#
# The two tests below drive the per-game shape. Their design point is that
# "game A's lines survived" is NOT self-validating: it is equally true when the
# reconcile ran and correctly skipped A, when the reconcile never ran, when the
# loader crashed first, and when A was never loaded to begin with. Each of those
# is a passing test that proves nothing. So both tests pair the survival claim
# with POSITIVE evidence that the per-game reconcile executed -- a spy on
# ``retire_absent_player_lines`` asserting it ran, and ran for game B ONLY.

_GAME_A = "game-A-0001"
_GAME_B = "game-B-0002"


def _two_game_crawl(
    team_id: int, boxscores: dict[str, dict]
) -> SimpleNamespace:
    """A crawl whose SCHEDULE always lists both games, whatever ``boxscores`` holds.

    Keeping both games on the schedule is load-bearing: it isolates the
    player-line grain. If game A fell out of the schedule array too, the
    GAME-grain reconcile would retire the whole game row and A's lines would
    vanish for an entirely different reason -- a passing assertion attributed to
    the wrong mechanism.
    """
    return _crawl(
        team_id,
        boxscores,
        games=[
            _game_entry(_GAME_A, opponent="Opp One"),
            dict(_game_entry(_GAME_B, opponent="Opp Two"),
                 start_ts="2026-04-17T18:00:00Z"),
        ],
    )


def _spy_on_player_line_retire():
    """Patch the player-line retire with a call-through recording spy.

    Patches the name in ``game_loader``, NOT in ``reconcile_at_load``: the
    former imports it at MODULE level (its top-level ``from
    src.db.reconcile_at_load import ...``), so rebinding the source module's
    attribute would not be seen at the call site. Verified against that import,
    not assumed. *(Cited by anchor rather than by line: the line number rotted
    when E-276-01 widened that import.)*
    """
    from unittest.mock import patch

    from src.db.reconcile_at_load import retire_absent_player_lines
    from src.gamechanger.loaders import game_loader as _game_loader

    return patch.object(
        _game_loader,
        "retire_absent_player_lines",
        side_effect=retire_absent_player_lines,
    )


def _reconciled_game_ids(spy) -> list[str]:
    """The ``game_id`` the per-game reconcile actually ran for, per call."""
    return [call.kwargs["game_id"] for call in spy.call_args_list]


def test_absent_game_key_in_a_populated_dict_retires_nothing(
    db: sqlite3.Connection,
) -> None:
    """A game missing from an otherwise-POPULATED boxscore dict is never diffed.

    The real per-game 404: the crawler skips the failed game and returns the
    others, so the dict is non-empty and the global short-circuit does NOT fire.
    Game A has no fresh evidence, so bias-to-refuse leaves its lines alone --
    the loader simply never reaches it.

    **Why this is not the survival tautology it looks like.** The spy
    assertions are the discriminators, not the survival ones: they establish
    that the per-game reconcile RAN (so the pass is not "the code never
    executed"), and that it ran for B *only* (so A was skipped rather than
    diffed-and-refused). Drop them and this test passes with the entire
    reconcile deleted -- which is precisely the defect the test above has and
    this one exists to avoid reproducing.

    **The ``errors == 0`` assertions close a further world the spy cannot see.**
    ``GameLoader._retire_absent_player_lines`` catches EVERY exception, logs at
    ERROR and returns 1 -- deliberately, so a failed cleanup never loses a good
    load. ``unittest.mock`` records a call BEFORE invoking ``side_effect``, so a
    reconcile that raises still satisfies ``call_count > 0`` AND
    ``== [_GAME_B]``, the ERROR is invisible to ``_retire_warnings`` (WARNING
    only), and nothing is deleted -- this test would go green against a
    reconcile that blew up. The returned 1 reaches ``LoadResult.errors`` via
    ``GameLoader._upsert_game_and_stats``'s
    ``result.errors += self._retire_absent_player_lines(...)`` and then
    ``ScoutingLoader._load_team_core``'s ``total.errors += bs_result.errors``;
    verified empirically, not read off the code. So the spy proves the path was
    ENTERED and ``errors == 0`` proves it COMPLETED. *(Re-anchored from line
    numbers, which E-276-01's capture anchor rotted.)*

    **Companion:** ``test_dropped_player_in_a_covered_game_is_retired_while_absent_game_survives``
    is the other half of this pair -- it proves the reconcile is LIVE rather
    than inert. Deleting it degrades this test (see that docstring).
    """
    team = _insert_team(db)
    first = ScoutingLoader(db).load_team(
        _two_game_crawl(
            team,
            {
                _GAME_A: _boxscore(_SLUG_A, _team_block(["a-1", "a-2", "a-3"])),
                _GAME_B: _boxscore(_SLUG_A, _team_block(["b-1", "b-2", "b-3"])),
            },
        )
    )
    assert first.errors == 0, "the first load itself failed"
    # Both games really loaded -- otherwise "A survived" would be vacuously true
    # of a game that was never there.
    assert _batting_players(db, _GAME_A) == {"a-1", "a-2", "a-3"}
    assert _batting_players(db, _GAME_B) == {"b-1", "b-2", "b-3"}

    # Re-scout: game A's boxscore 404'd, game B's came back intact. The dict is
    # NON-EMPTY, so the global `if not boxscores` guard does not fire.
    with _spy_on_player_line_retire() as spy:
        second = ScoutingLoader(db).load_team(
            _two_game_crawl(
                team,
                {_GAME_B: _boxscore(_SLUG_A, _team_block(["b-1", "b-2", "b-3"]))},
            )
        )

    # POSITIVE evidence the per-game path executed, for B alone, and CLEANLY.
    assert spy.call_count > 0, (
        "the per-game reconcile never ran -- this test would otherwise 'pass' "
        "on survival alone, exactly like the whole-empty-dict test above"
    )
    assert _reconciled_game_ids(spy) == [_GAME_B], (
        "game A was diffed despite having no fresh boxscore; the loader must "
        "iterate only PRESENT boxscores"
    )
    assert second.errors == 0, (
        "the player-line reconcile RAISED and was swallowed -- every other "
        "assertion here is still satisfied by that failure"
    )

    # ...and nothing was retired from either game.
    assert _batting_players(db, _GAME_A) == {"a-1", "a-2", "a-3"}
    assert _batting_players(db, _GAME_B) == {"b-1", "b-2", "b-3"}


def test_dropped_player_in_a_covered_game_is_retired_while_absent_game_survives(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """The paired variant: the reconcile RAN, and it only touched the covered game.

    Same shape as the test above, but game B's fresh block drops one player
    while staying populated. That player's line must be retired, proving the
    reconcile is live on the covered game -- while game A, absent from the dict,
    is untouched. Together the two assertions separate "skipped because absent"
    from "the reconcile is not running at all", which neither claim does alone.

    B's block is sized 3 -> 2 so the drop clears the 0.5 floor unambiguously
    (2 comparable of 3 prior); at 2 -> 1 the gate sits exactly on the boundary.

    **Do not delete this test as redundant with its companion.** It is the ONLY
    one of the pair that distinguishes a LIVE reconcile from an INERT one. In
    ``test_absent_game_key_in_a_populated_dict_retires_nothing`` game B's block
    is unchanged, so "ran and correctly found nothing absent", "ran and refused"
    and "ran and is a no-op that deletes nothing" are observationally
    identical there. Only a real deletion separates them, and only this test
    performs one. The pair splits the work: the companion proves
    skipped-vs-diffed, this one proves live-vs-inert, and neither does both.
    """
    team = _insert_team(db)
    first = ScoutingLoader(db).load_team(
        _two_game_crawl(
            team,
            {
                _GAME_A: _boxscore(_SLUG_A, _team_block(["a-1", "a-2", "a-3"])),
                _GAME_B: _boxscore(_SLUG_A, _team_block(["b-1", "b-2", "b-3"])),
            },
        )
    )
    assert first.errors == 0, "the first load itself failed"
    assert _batting_players(db, _GAME_A) == {"a-1", "a-2", "a-3"}
    assert _batting_players(db, _GAME_B) == {"b-1", "b-2", "b-3"}

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        with _spy_on_player_line_retire() as spy:
            second = ScoutingLoader(db).load_team(
                _two_game_crawl(
                    team,
                    {_GAME_B: _boxscore(_SLUG_A, _team_block(["b-1", "b-2"]))},
                )
            )

    assert _reconciled_game_ids(spy) == [_GAME_B]
    # See the companion's docstring: a swallowed reconcile failure satisfies the
    # spy assertions, so the clean-completion check belongs here too.
    assert second.errors == 0, "the player-line reconcile RAISED and was swallowed"
    # The covered game's dropped line is GONE -- the reconcile is live.
    assert _batting_players(db, _GAME_B) == {"b-1", "b-2"}
    # The absent game is untouched, including the player that shares its index.
    assert _batting_players(db, _GAME_A) == {"a-1", "a-2", "a-3"}

    warnings = _retire_warnings(caplog)
    assert any("b-3" in w for w in warnings), warnings
    assert not any("a-" in w for w in warnings), warnings


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
    from src.db.reconcile_at_load import (
        PlayerLineBlock,
        retire_absent_player_lines,
        snapshot_prior_line_player_ids,
    )

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

    # No writes intervene between here and the call below, so the pre-upsert
    # snapshot IS the current state (E-276-01 mechanical churn).
    snapshots = snapshot_prior_line_player_ids(
        db,
        game_id=_GAME,
        perspective_team_id=team_a,
        team_ids=(team_a, team_b),
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
        prior_snapshots=snapshots,
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


# ===========================================================================
# E-276-01: the health gate's prior set is captured BEFORE the run's own writes
# ===========================================================================
#
# Every test below drives the real ``ScoutingLoader.load_team``. That is not a
# style preference: the defect lives in the ORDERING between the producer and
# the reconcile, so a test that hand-INSERTs prior rows and calls the retire
# helper directly passes before AND after the fix. And every existing shrink
# test uses a fresh set that is a strict SUBSET of prior, which is why none of
# them can see this -- the new tests drive genuinely NEW ids.


def _gen(prefix: str, n: int) -> list[str]:
    return [f"{prefix}-{i}" for i in range(n)]


# ---------------------------------------------------------------------------
# AC-1 / AC-2: the commissioned defect -- a full player_id churn
# ---------------------------------------------------------------------------


def test_full_id_churn_refuses_on_the_run_it_arrives(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-1/AC-2/AC-13: 9 stored lines, 9 brand-new ids, ZERO hard-deleted.

    The input the audit executed. Pre-fix the gate reads its prior set AFTER the
    fresh upsert, so the population is 18 (9 stale + 9 just written) with an
    overlap of 9 -- a comfortable ``9 >= 9`` that permits and hard-deletes every
    prior batting line for the game, uncapped. Post-fix the gate reads the
    pre-upsert snapshot: 0 of 9, refused.

    **The discriminating assertion is ``gate_prior_count == 9``, not the
    surviving row count.** A surviving-row count alone can pass post-fix for a
    wrong reason (someone disabling the grain); the count is the numeric tell,
    and it is asserted on the KEYED record for the block and table under test,
    because this grain evaluates up to four independent gates per call.

    ``errors == 0`` is not decoration either: ``_retire_absent_player_lines``
    sits inside a broad swallow-and-count ``except``, so a CRASH anywhere in it
    produces *nothing retired, rows intact, no refusal WARN* -- byte-identical
    to a healthy refusal by row count. On this grain the row count is not an
    admissible witness for a refusal.
    """
    team = _insert_team(db)
    gen1, gen2 = _gen("g1", 9), _gen("g2", 9)

    first = ScoutingLoader(db).load_team(
        _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(gen1))})
    )
    assert first.errors == 0
    assert _batting_players(db) == set(gen1)

    caplog.clear()
    with caplog.at_level(logging.WARNING), _capture_player_line_results() as captured:
        second = ScoutingLoader(db).load_team(
            _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(gen2))})
        )

    assert second.errors == 0, (
        "the reconcile RAISED and was swallowed -- every row-state assertion "
        "below is still satisfied by that failure"
    )
    _assert_captured_result_objects(captured)
    _game_id, result = captured[-1]
    key = ("player_game_batting", team)
    gate = result.gate_outcomes[key]

    # WHICH mechanism refused, and on WHOSE counts.
    assert gate.refused_by == "gate"
    assert gate.gate_evaluated is True
    assert gate.gate_permitted is False
    assert gate.permitted is False
    assert gate.gate_prior_count == 9, (
        "the gate measured the POST-upsert population (18) -- its prior set is "
        "being read after this run's own rows were written"
    )
    assert gate.gate_comparable_count == 0

    # Unit-level refusal AND the per-id surface both checked (neither alone
    # closes the wrong-reason trap).
    assert result.retired == {}
    assert key in result.refusals
    assert "refused_by=gate" in result.refusals[key]

    # Nothing was hard-deleted: both generations are live.
    assert _batting_players(db) == set(gen1) | set(gen2)

    # AC-13: the operator's only production signal names the mechanism and
    # carries THAT mechanism's own counts.
    refusals = [m for m in _retire_warnings(caplog) if "REFUSED" in m]
    assert len(refusals) == 1
    assert "refused_by=gate" in refusals[0]
    assert "0 of the 9 batting line(s)" in refusals[0]
    assert "START of this load" in refusals[0]


@pytest.mark.parametrize(
    ("label", "fresh_size"),
    [("stale_9_fresh_8", 8), ("stale_9_fresh_9", 9), ("stale_9_fresh_10", 10)],
)
def test_zero_overlap_sweep_refuses_at_every_size(
    db: sqlite3.Connection, label: str, fresh_size: int
) -> None:
    """AC-3: the zero-overlap boundary sweep. EVERY case refuses.

    Pre-fix these produce refuse / delete-9 / delete-9 respectively, so the
    parametrization discriminates as a SET even though the 9/8 case refuses
    under both regimes (it is a floor, not a ratio pin).
    """
    team = _insert_team(db)
    gen1, gen2 = _gen("g1", 9), _gen("g2", fresh_size)

    ScoutingLoader(db).load_team(
        _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(gen1))})
    )
    with _capture_player_line_results() as captured:
        second = ScoutingLoader(db).load_team(
            _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(gen2))})
        )

    assert second.errors == 0, label
    _assert_captured_result_objects(captured)
    gate = _batting_gate(captured[-1][1], team)
    assert gate.gate_permitted is False, label
    assert gate.refused_by == "gate", label
    assert gate.gate_prior_count == 9, label
    assert captured[-1][1].retired == {}, label
    assert set(gen1) <= _batting_players(db), label


@pytest.mark.parametrize(
    ("label", "survivors", "new_ids", "expect_permit"),
    [
        ("floor_met_5_of_10", 5, 6, True),
        ("floor_missed_4_of_10", 4, 6, False),
    ],
)
def test_overlap_bearing_cases_follow_the_honest_verdict_through_the_loader(
    db: sqlite3.Connection, label: str, survivors: int, new_ids: int,
    expect_permit: bool,
) -> None:
    """AC-4: the two cases differ by ONE survivor and land on opposite sides.

    The polluted computation permits BOTH -- post-upsert prior 16, floor 8,
    numerators 11 and 10 -- so this pair pins the ratio ARITHMETIC, which the
    zero-overlap sweep above cannot.
    """
    team = _insert_team(db)
    stored = _gen("old", 10)
    fresh = stored[:survivors] + _gen("new", new_ids)

    ScoutingLoader(db).load_team(
        _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(stored))})
    )
    with _capture_player_line_results() as captured:
        second = ScoutingLoader(db).load_team(
            _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(fresh))})
        )

    assert second.errors == 0, label
    _assert_captured_result_objects(captured)
    result = captured[-1][1]
    gate = _batting_gate(result, team)
    assert gate.gate_prior_count == 10, label
    assert gate.gate_comparable_count == survivors, label
    assert gate.gate_permitted is expect_permit, label

    if expect_permit:
        assert result.retired[("player_game_batting", team)] == stored[survivors:]
        assert _batting_players(db) == set(fresh)
    else:
        assert result.retired == {}
        assert gate.refused_by == "gate", label
        assert _batting_players(db) == set(stored) | set(fresh)


# ---------------------------------------------------------------------------
# AC-5: the first-ever load computes a gate; it does NOT short-circuit
# ---------------------------------------------------------------------------


def test_first_ever_load_evaluates_a_vacuously_permitted_gate_and_retires_nothing(
    db: sqlite3.Connection,
) -> None:
    """AC-5: nothing is retired because every LIVE prior id is in ``fresh``.

    NOT because the pass short-circuits on an empty prior. The candidate
    population is the LIVE read, which on a first-ever load holds the rows
    written moments earlier -- so the pass runs and a gate IS computed
    (permitted vacuously, because the SNAPSHOT is what is empty).

    Gating an early return on the snapshot instead would re-open the TN-3
    deadlock, which is why this asserts the gate was EVALUATED rather than
    merely that nothing happened.

    The absence claim is paired with positive evidence per AC-1's rule: a bare
    "nothing was retired" is satisfied identically by the reconcile never
    running.
    """
    team = _insert_team(db)
    players = ["p-1", "p-2", "p-3"]

    with _capture_player_line_results() as captured:
        first = ScoutingLoader(db).load_team(
            _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(players))})
        )

    assert first.errors == 0
    _assert_captured_result_objects(captured)
    result = captured[-1][1]
    assert result.retired == {}
    assert result.refusals == {}

    gate = _batting_gate(result, team)
    assert gate.gate_evaluated is True, "the pass short-circuited on the snapshot"
    assert gate.gate_permitted is True, "the vacuous-permit rule did not fire"
    assert gate.refused_by is None
    assert gate.gate_prior_count == 0, "the SNAPSHOT is the empty one"
    assert _batting_players(db) == set(players), "...the LIVE prior set is not"


# ---------------------------------------------------------------------------
# AC-7: the evidence parameter cannot be omitted
# ---------------------------------------------------------------------------


def test_prior_snapshots_is_required_and_has_no_default() -> None:
    """AC-7 / TN-1(a): a default here silently restores the whole defect.

    Pinned as an executable check rather than a review note, in the manner of
    ``test_floor_is_not_overridable_by_callers``: the property this protects is
    precisely the one a future edit restores by accident, and a note evaporates
    the moment the signature changes.
    """
    from src.db.reconcile_at_load import retire_absent_player_lines

    with pytest.raises(TypeError, match="prior_snapshots"):
        retire_absent_player_lines(
            MagicMock(), game_id=_GAME, perspective_team_id=1, blocks=[]
        )


# ---------------------------------------------------------------------------
# AC-9a / AC-9b: what reaches the classifier
# ---------------------------------------------------------------------------


def _classifier_spy():
    """Spy on ``classify_absences`` as the retire helpers see it."""
    from unittest.mock import patch

    import src.db.reconcile_at_load as recon

    return patch.object(
        recon, "classify_absences", side_effect=recon.classify_absences
    )


def _player_line_classifier_calls(spy):
    """The PLAYER-LINE calls only.

    The game and roster grains call the same classifier in the same load and
    both pass an ``extra_guard``; this grain has no cap and passes none.
    """
    return [c for c in spy.call_args_list if "extra_guard" not in c.kwargs]


def test_exactly_one_gate_value_reaches_the_classifier(
    db: sqlite3.Connection,
) -> None:
    """AC-9a / precondition (c): ONE value, and it is the corrected gate's.

    Pinned with a test rather than by inspection: of five attacks on the
    neutrality formulation this is the only one that landed, so it is an
    implementation risk rather than a logic one. No second gate may be composed
    at the call site.
    """
    team = _insert_team(db)
    gen1, gen2 = _gen("g1", 9), _gen("g2", 9)
    ScoutingLoader(db).load_team(
        _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(gen1))})
    )

    with _classifier_spy() as spy:
        second = ScoutingLoader(db).load_team(
            _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(gen2))})
        )

    assert second.errors == 0
    calls = _player_line_classifier_calls(spy)
    assert calls, "the player-line grain never reached the classifier"
    for call in calls:
        assert set(call.kwargs) == {"crawl_authoritative"}, (
            f"an extra gate input reached the classifier: {sorted(call.kwargs)}"
        )
        assert call.kwargs["crawl_authoritative"] is False, (
            "the value reaching the classifier is not the corrected gate's "
            "verdict on a full id churn"
        )


def test_the_classifier_receives_the_LIVE_prior_set_not_the_snapshot(
    db: sqlite3.Connection,
) -> None:
    """AC-9b / precondition (d) -- the slip no other AC can catch.

    The classifier returns a classification covering exactly the ids it is
    handed, so that argument IS the candidate universe. The natural slip --
    "the corrected gate uses the snapshot, so pass the snapshot to the
    classifier" -- reads as obviously correct while writing it, and makes the
    candidate set ``snapshot - fresh``.

    Deletion-neutrality cannot catch it: the slip only ever SHRINKS the
    candidate set, so it permits strictly fewer deletions and the neutrality
    absolute stays TRUE while the thing it guards breaks. Hence its own test.

    This is the PRIMITIVE-LEVEL CONTRACT at the grain this story wires. The
    executed two-run construction -- where the slip's consequence becomes
    permanent -- belongs to the roster grain (story 03 AC-8), which is the only
    grain where ``W`` is not a subset of ``fresh`` and so the only one where
    the two candidate sets differ at all.
    """
    team = _insert_team(db)
    gen1, gen2 = _gen("g1", 9), _gen("g2", 9)
    ScoutingLoader(db).load_team(
        _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(gen1))})
    )

    with _classifier_spy() as spy:
        ScoutingLoader(db).load_team(
            _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(gen2))})
        )

    calls = _player_line_classifier_calls(spy)
    batting = [c for c in calls if set(c.args[0]) & set(gen1)]
    assert batting, "no player-line call carried the stored batting ids"
    for call in batting:
        prior_ids = set(call.args[0])
        assert prior_ids == set(gen1) | set(gen2), (
            "the classifier was handed the SNAPSHOT as its candidate universe; "
            f"got {len(prior_ids)} ids, expected the live 18"
        )


# ---------------------------------------------------------------------------
# AC-14: MULTI-RUN. Every probe run during this epic's planning was single-run,
# and the failure class that reopened the design three times is multi-run -- it
# needs a refusal to strand rows that a later run then counts. A grain with no
# multi-run regression test is untested against that whole class.
# ---------------------------------------------------------------------------


def _batting_ids_for_team(
    db: sqlite3.Connection, team_id: int, game_id: str = _GAME
) -> set[str]:
    return {
        r[0]
        for r in db.execute(
            "SELECT player_id FROM player_game_batting "
            "WHERE game_id = ? AND team_id = ?",
            (game_id, team_id),
        )
    }


def _drive(db: sqlite3.Connection, crawls: list, observe=None) -> list:
    """Run each crawl through the REAL loader, one invocation at a time.

    Returns ``[(LoadResult, {(game_id, table, team_id): GateOutcome}, obs), ...]``
    in invocation order. The record key carries ``game_id`` and that is REQUIRED:
    omit it and a season's games overwrite each other's records, which is a
    silent wrong answer rather than an error.

    ``observe(db)`` is called AFTER each invocation and its value stored with
    that run. **Per-invocation observation is the deliverable, not an
    implementation nicety**: reading DB state once the whole sequence has
    finished yields the FINAL state repeated N times, which still satisfies an
    endpoint assertion while hiding every intermediate step -- precisely the
    accumulation this AC exists to pin.
    """
    runs = []
    for crawl in crawls:
        with _capture_player_line_results() as captured:
            result = ScoutingLoader(db).load_team(crawl)
        _assert_captured_result_objects(captured)
        records = {}
        for game_id, res in captured:
            for (table, tid), outcome in res.gate_outcomes.items():
                records[(game_id, table, tid)] = outcome
        runs.append((result, records, observe(db) if observe else None))
    return runs


_MERGEABLE_ORIGINAL = "Alexander"
_MERGEABLE_CHURN = "Alex"  # a strict prefix -> dedup collapses it away
_UNMERGEABLE_ORIGINAL = "Mike"
_UNMERGEABLE_CHURN = "Michael"  # NOT a prefix of "Mike" -> invisible to dedup


def _named_block(ids: list[str], first: str) -> dict:
    """A block whose players share ``first`` and carry paired surnames."""
    return _team_block(
        ids,
        names={pid: (first, f"Sur{pid.rsplit('-', 1)[1]}") for pid in ids},
    )


def test_regime_A_dedup_mergeable_churn_leaves_the_originals_intact_every_run(
    db: sqlite3.Connection,
) -> None:
    """AC-14 regime A: the sweep CAN merge, so the originals survive N runs.

    9-line own block. Run 1 loads the originals; runs 2-4 present the SAME
    churn generation, whose first names are strict prefixes of the originals'
    (so ``dedup_team_players`` collapses each pair back onto the longer name).

    The gate refuses on every churn run -- ``prior=9 comparable=0`` -- and the
    sweep then merges the fresh generation away, so the row count returns to the
    block size with the ORIGINAL ids.

    **The required observable is the post-sweep ID-IDENTITY assertion, and both
    halves are load-bearing.** A run where the sweep silently did nothing fails
    it, finding either 2x the block or the churned ids surviving. A spy on the
    sweep would NOT be sufficient and must not be substituted: a failing collapse
    is logged and swallowed WITHOUT incrementing ``LoadResult.errors``, so a spy
    certifies ENTERED and never COMPLETED. The genuinely stronger option --
    ``dedup_team_players``' merged-away count -- is discarded by
    ``_load_team_core``; id-identity is the floor, not the ceiling.

    Classification: REGRESSION GUARD. It holds under both regimes and catches a
    future change, not this one.
    """
    team = _insert_team(db)
    block = 9  # the gate's denominator -- roster-sized
    originals = _gen("orig", block)
    churn = _gen("churn", block)

    runs = _drive(
        db,
        [
            _crawl(team, {_GAME: _boxscore(_SLUG_A, _named_block(originals, _MERGEABLE_ORIGINAL))}),
            *[
                _crawl(team, {_GAME: _boxscore(_SLUG_A, _named_block(churn, _MERGEABLE_CHURN))})
                for _ in range(3)
            ],
        ],
        observe=lambda conn: _batting_ids_for_team(conn, team),
    )
    assert len(runs) == 4

    rows_per_run = []
    originals_alive = []
    for index, (result, records, live) in enumerate(runs):
        assert result.errors == 0, f"run {index + 1} raised and was swallowed"
        rows_per_run.append(len(live))
        originals_alive.append(len(live & set(originals)))

        gate = records[(_GAME, "player_game_batting", team)]
        if index == 0:
            assert gate.gate_prior_count == 0 and gate.gate_permitted is True
        else:
            assert gate.gate_prior_count == block, (
                f"run {index + 1}: the gate measured the post-upsert population"
            )
            assert gate.gate_comparable_count == 0
            assert gate.gate_permitted is False
            assert gate.refused_by == "gate"

    assert rows_per_run == [9, 9, 9, 9]
    assert originals_alive == [9, 9, 9, 9]

    # The post-sweep id-identity assertion, both halves.
    assert _batting_ids_for_team(db, team) == set(originals)

    # The accumulate-then-delete predicate stays SILENT here. Note the silence
    # comes from the ``gate_permitted`` conjunct, not the growth one: the sweep
    # merges the fresh generation away each run, so ``comparable`` is 0 and the
    # gate refuses every invocation. The predicate keys on permit-AND-growth and
    # nothing else; it does not distinguish merged from unmerged.
    key = (_GAME, "player_game_batting", team)
    gates = [records[key] for _result, records, _obs in runs]
    for prev, cur in zip(gates, gates[1:], strict=False):
        assert not _accumulate_then_delete_fires(prev, cur)


@pytest.mark.parametrize(
    ("block", "n_runs", "expected_rows", "expected_originals"),
    [
        (9, 4, [9, 18, 9, 9], [9, 9, 0, 0]),
        (12, 5, [12, 24, 12, 12, 12], [12, 12, 0, 0, 0]),
    ],
)
def test_regime_B_unmergeable_churn_deletes_the_prior_generation_on_run_3(
    db: sqlite3.Connection, block: int, n_runs: int,
    expected_rows: list[int], expected_originals: list[int],
) -> None:
    """AC-14 regime B: pinned as an ACCEPTED, DOCUMENTED RESIDUAL.

    ⚠️ **This test asserts that a known defect still behaves exactly as
    measured.** It is NOT a discrimination of the fix and NOT a guard on a
    healthy property -- reporting it as either would overclaim in opposite
    directions. Its job is to make a later change that WORSENS the residual fail
    loudly.

    **A refusal WRITES.** The retire is refused; the upsert is not. So a churn
    the dedup sweep cannot merge (here a non-prefix first-name change, invisible
    to a detector that matches on name prefix) grows the stored population every
    run. Because the gate's floor is a RATIO over that population, run 3 reaches
    ``m >= P`` -- an exact equality at ``m == P``, a knife edge rather than a
    margin -- the gate PERMITS, and the entire prior generation is hard-deleted,
    uncapped: this grain has no ``MAX_*`` beneath the gate.

    ``W subset-of fresh`` does NOT rescue this and that is the crux. It
    constrains the CANDIDATE set (what may be deleted); it says nothing about
    the GATE population (what the floor is computed over), and it is the
    population that grows.

    The rule is ``m >= P`` where ``m`` is the churn block size from run 2 on and
    ``P`` the original block -- not "m >= 12". Below the boundary the outcome is
    DIFFERENT, not merely smaller: the two generations become permanently
    co-resident and the originals all survive, so a fixture built there pins the
    wrong thing and reads as passing.
    """
    team = _insert_team(db)
    originals = _gen("orig", block)
    churn = _gen("churn", block)  # m == P: the knife edge

    crawls = [
        _crawl(team, {_GAME: _boxscore(_SLUG_A, _named_block(originals, _UNMERGEABLE_ORIGINAL))}),
        *[
            _crawl(team, {_GAME: _boxscore(_SLUG_A, _named_block(churn, _UNMERGEABLE_CHURN))})
            for _ in range(n_runs - 1)
        ],
    ]
    runs = _drive(
        db, crawls, observe=lambda conn: _batting_ids_for_team(conn, team)
    )

    rows_per_run = []
    originals_alive = []
    for index, (result, _records, live) in enumerate(runs):
        assert result.errors == 0, f"run {index + 1} raised and was swallowed"
        rows_per_run.append(len(live))
        originals_alive.append(len(live & set(originals)))

    assert rows_per_run == expected_rows
    assert originals_alive == expected_originals

    key = (_GAME, "player_game_batting", team)
    gates = [records[key] for _result, records, _obs in runs]

    # Run 1: empty snapshot, vacuous permit, nothing absent.
    assert (gates[0].gate_prior_count, gates[0].gate_permitted) == (0, True)

    # Run 2: the DISCRIMINATING assertion. Pre-fix this reads the post-upsert
    # population (2 * block); post-fix the pre-run one.
    assert gates[1].gate_prior_count == block
    assert gates[1].gate_comparable_count == 0
    assert gates[1].gate_permitted is False
    assert gates[1].refused_by == "gate"
    assert runs[1][1][key].permitted is False

    # Run 3: the residual. The population the run-2 refusal STRANDED is now the
    # denominator, the fresh generation covers exactly half of it, and the floor
    # is met at equality.
    assert gates[2].gate_prior_count == 2 * block
    assert gates[2].gate_comparable_count == block
    assert gates[2].gate_permitted is True
    assert runs[2][1][key].permitted is True

    # Runs 4+: steady state on the new generation.
    for gate in gates[3:]:
        assert gate.gate_prior_count == block
        assert gate.gate_permitted is True

    # The accumulate-then-delete predicate fires EXACTLY on the run-3 window.
    fired = [
        index + 2
        for index, (prev, cur) in enumerate(zip(gates, gates[1:], strict=False))
        if _accumulate_then_delete_fires(prev, cur)
    ]
    assert fired == [3]


def test_regime_B_on_the_OPPONENT_block_is_closed_by_the_dedup_sweep(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-14 regime B on the opponent block -- INVERTED, and deliberately kept.

    This test previously asserted the opposite property under the name
    ``test_regime_B_on_the_OPPONENT_block_has_no_closer_in_any_shape``: that
    ``dedup_team_players`` was scoped to the SCOUTED team while the opponent
    block's rows are written under ``opp_team_id``, so the opponent block had **no
    closer in ANY shape**. That is precisely the defect the opponent-roster dedup
    chunk removed -- the sweep now runs for every team whose ``team_rosters`` rows
    the load wrote -- so the assertions are inverted rather than deleted, and the
    pinned sequence is re-derived from an EXECUTED run, not edited by hand.

    Still the HARDEST shape: an IDENTICAL-name re-issue, the churn the sweep
    exists to close.

    **The regime-B coverage is the part to preserve, and it survives intact: the
    closer is the DEDUP SWEEP, not the retire.** The player-line retire still
    REFUSES on run 2 exactly as before (the gate sees a fresh block vouching for 0
    of 9 prior lines, and its population is the pre-upsert snapshot), so nothing
    about the gate got weaker. What changed is that the sweep collapses the two
    generations inside the same load, so the accumulation the run-2 refusal used
    to strand never forms -- and the accumulate-then-delete predicate, which fired
    on run 3, now never fires. The unmergeable-churn sibling above keeps the
    coverage for the shape where no closer exists in any regime.
    """
    team = _insert_team(db)
    block = 9
    own = _gen("own", 3)
    originals = _gen("orig", block)
    churn = _gen("churn", block)
    # Identical names across generations -- mergeable in principle, unreachable
    # in practice.
    shared = {"first": "Jordan"}

    def _opp_crawl(ids: list[str]) -> SimpleNamespace:
        return _crawl(
            team,
            {
                _GAME: _boxscore(
                    _SLUG_A,
                    _team_block(own),
                    _team_block(
                        ids,
                        names={
                            pid: (shared["first"], f"Sur{pid.rsplit('-', 1)[1]}")
                            for pid in ids
                        },
                    ),
                )
            },
        )

    def _opponent_lines(conn: sqlite3.Connection) -> set[str]:
        # The opponent's own block, identified as "the participant team that is
        # not the scouted one" rather than by a hard-coded id.
        return {
            r[0]
            for r in conn.execute(
                "SELECT player_id FROM player_game_batting "
                "WHERE game_id = ? AND team_id != ?",
                (_GAME, team),
            )
        }

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        runs = _drive(
            db,
            [_opp_crawl(originals), *[_opp_crawl(churn) for _ in range(3)]],
            observe=_opponent_lines,
        )

    opp_team = db.execute(
        "SELECT DISTINCT team_id FROM player_game_batting "
        "WHERE game_id = ? AND team_id != ?",
        (_GAME, team),
    ).fetchone()[0]

    rows_per_run = []
    originals_alive = []
    churn_alive = []
    for index, (result, _records, live) in enumerate(runs):
        assert result.errors == 0, f"run {index + 1} raised and was swallowed"
        rows_per_run.append(len(live))
        originals_alive.append(len(live & set(originals)))
        churn_alive.append(len(live & set(churn)))

    # One block's worth of lines at EVERY step -- run 2 no longer doubles. The
    # 18-row accumulation the old pin recorded is what the sweep now prevents.
    assert rows_per_run == [9, 9, 9, 9]
    # The generations swap inside run 2: the sweep merges each original into its
    # re-issued twin, so the originals are gone by the end of that run instead of
    # surviving until a run-3 deletion. WHICH id survives is fixture-incidental --
    # both names are "Jordan Sur<n>" of equal length with equal stat counts, so the
    # component canonical falls through to the alphabetical player_id tiebreak and
    # ``churn-*`` < ``orig-*``. It is the COUNT that carries the property.
    assert originals_alive == [9, 0, 0, 0]
    assert churn_alive == [0, 9, 9, 9]

    key = (_GAME, "player_game_batting", opp_team)
    gates = [records[key] for _result, records, _obs in runs]
    # UNCHANGED from the pre-fix run, and that is the regime-B half worth keeping:
    # the retire still refuses on run 2 over the same (9, 0) population. The gate
    # did not get weaker; a different mechanism resolved the churn.
    assert (gates[1].gate_prior_count, gates[1].gate_comparable_count) == (9, 0)
    assert gates[1].gate_permitted is False
    assert gates[1].refused_by == "gate"
    # Run 3's prior population is ONE block (9), not the stranded 18: with nothing
    # accumulated, the fresh block vouches for all of it and there is nothing
    # absent left to delete.
    assert (gates[2].gate_prior_count, gates[2].gate_comparable_count) == (9, 9)
    assert gates[2].gate_permitted is True

    # The accumulate-then-delete window is CLOSED on the opponent block. Asserted
    # via the predicate itself (it fired on run 3 before this chunk), not via the
    # tuple it is computed from.
    fired = [
        index + 2
        for index, (prev, cur) in enumerate(zip(gates, gates[1:], strict=False))
        if _accumulate_then_delete_fires(prev, cur)
    ]
    assert fired == []

    # No run has anything absent-and-mergeable left for the victim diagnostic to
    # name, because the sweep merged the pair before a later run could delete it.
    # The diagnostic itself is still covered on the shapes that reach it (see the
    # jersey-corroborated and cross-season cases below).
    for gate in gates:
        assert not gate.matched_victim_player_ids
    assert not [m for m in _retire_warnings(caplog) if "bb data dedup-players" in m]

    # The own block is untouched throughout -- the sweep reaching the opponent is
    # an addition, not a whole-payload behavior change.
    assert _batting_ids_for_team(db, team) == set(own)

    # The convergence is on the ROSTER too, which is where a coach sees it: the
    # report's roster block prints one entry per row with no grouping.
    assert db.execute(
        "SELECT COUNT(*) FROM team_rosters WHERE team_id = ?", (opp_team,)
    ).fetchone()[0] == block


def test_partial_churn_at_production_SEASON_scale_deletes_on_run_2(
    db: sqlite3.Connection,
) -> None:
    """AC-14 at production scale. Two denominators, and only one reaches the gate.

    Fixture figures, stated because they are different denominators:

    * **season size = 24 completed games** (CLAUDE.md "Scope": ~30 per team) --
      this MULTIPLIES the loss and reaches no gate;
    * **block size = 13 lines** -- this is the grain's actual gate denominator.

    3 of the 13 ids churn per game. 3 is BELOW the floor over 13, so the gate
    permits immediately and the loss lands on RUN 2 -- this is the stated
    partial-churn residual at season scale, NOT the regime-B accumulate-then-
    delete window, and attaching it to that window would cite one residual as
    evidence for another.

    ``24 * 3 = 72`` batting lines die. Total rows stay 312 (``24 * 13``)
    throughout, each churned line replaced one-for-one -- which is exactly why a
    total-row-count assertion is blind to it and the ORIGINALS-ALIVE count is
    not. The pitching group is ``stats: []``, so no ``player_game_pitching`` rows
    exist at all.
    """
    team = _insert_team(db)
    season_games = 24
    block = 13
    churn_per_game = 3

    roster = _gen("p", block)
    fresh_roster = _gen("p", block - churn_per_game) + _gen("new", churn_per_game)

    def _season_crawl(ids: list[str]) -> SimpleNamespace:
        games = [
            dict(
                _game_entry(f"game-{i:04d}"),
                start_ts=f"2026-04-{i + 1:02d}T18:00:00Z",
            )
            for i in range(season_games)
        ]
        return _crawl(
            team,
            {
                f"game-{i:04d}": _boxscore(_SLUG_A, _team_block(ids))
                for i in range(season_games)
            },
            games=games,
        )

    def _totals(conn: sqlite3.Connection) -> tuple[int, int]:
        total = conn.execute("SELECT COUNT(*) FROM player_game_batting").fetchone()[0]
        alive = conn.execute(
            "SELECT COUNT(*) FROM player_game_batting WHERE player_id LIKE 'p-%'"
        ).fetchone()[0]
        return total, alive

    runs = _drive(
        db,
        [_season_crawl(roster), *[_season_crawl(fresh_roster) for _ in range(4)]],
        observe=_totals,
    )

    observed = []
    for index, (result, _records, totals) in enumerate(runs):
        assert result.errors == 0, f"run {index + 1} raised and was swallowed"
        observed.append(totals)

    assert observed == [
        (312, 312), (312, 240), (312, 240), (312, 240), (312, 240)
    ]
    assert db.execute("SELECT COUNT(*) FROM player_game_pitching").fetchone()[0] == 0

    # The loss is on run 2, and the gate PERMITTED it: 10 of 13 clears the floor.
    gate = runs[1][1][("game-0000", "player_game_batting", team)]
    assert gate.gate_prior_count == block
    assert gate.gate_comparable_count == block - churn_per_game
    assert gate.gate_permitted is True

    # ...and it is not the regime-B window: the predicate never fires here.
    for game_index in range(season_games):
        key = (f"game-{game_index:04d}", "player_game_batting", team)
        for prev, cur in zip(runs, runs[1:], strict=False):
            if key in prev[1] and key in cur[1]:
                assert not _accumulate_then_delete_fires(prev[1][key], cur[1][key])


def test_the_predicates_positivity_clause_is_required_not_defensive(
    db: sqlite3.Connection,
) -> None:
    """AC-14: dropping ``prev.gate_prior_count > 0`` misfires on ORDINARY play.

    Proved by RUNNING WITHOUT IT rather than by argument. A game added on
    invocation 2 records ``prior=0, permitted=True`` under the vacuous-permit
    rule, so invocation 3's perfectly clean load reads as growth-with-permit. A
    diagnostic that cries wolf on every new game of the season is worse than
    none.
    """
    team = _insert_team(db)
    roster = _gen("p", 13)
    game_b = "game-B-0002"

    def _crawl_with(game_ids: list[str]) -> SimpleNamespace:
        entries = {
            _GAME: _game_entry(_GAME),
            game_b: dict(_game_entry(game_b), start_ts="2026-04-17T18:00:00Z"),
        }
        return _crawl(
            team,
            {gid: _boxscore(_SLUG_A, _team_block(roster)) for gid in game_ids},
            games=[entries[gid] for gid in game_ids],
        )

    runs = _drive(
        db,
        [
            _crawl_with([_GAME]),
            _crawl_with([_GAME, game_b]),  # game B JOINS the season
            _crawl_with([_GAME, game_b]),  # a perfectly clean re-scout
        ],
    )
    for index, (result, _records, _obs) in enumerate(runs):
        assert result.errors == 0, f"run {index + 1} raised and was swallowed"

    key = (game_b, "player_game_batting", team)
    prev, cur = runs[1][1][key], runs[2][1][key]
    assert (prev.gate_prior_count, prev.gate_permitted) == (0, True)
    assert (cur.gate_prior_count, cur.gate_permitted) == (13, True)

    assert _fires_without_the_positivity_clause(prev, cur) is True, (
        "the control must reproduce the false fire, or this pins nothing"
    )
    assert _accumulate_then_delete_fires(prev, cur) is False


# ---------------------------------------------------------------------------
# AC-15: the single-invocation matched-victim diagnostic
# ---------------------------------------------------------------------------


def test_a_permitted_retire_whose_victim_matches_a_survivor_is_named(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-15: on a PERMITTED retire, surface the deletions that look routine.

    Not AC-13's subject and it must not be folded into it: AC-13 explains a
    REFUSAL, this explains a deletion that happened. Complementary halves of one
    operator-facing surface.

    Three mechanisms that would CLOSE this window were evaluated by construction
    and none adopted -- every one closes it by refusing forever, and a permanent
    refusal on this grain doubles the coach-facing season aggregate. So: surface
    it, do not gate it. Deletion behaviour is unchanged by construction, which is
    why deletion-neutrality is untouched.

    Classification: REGRESSION GUARD. Nothing here discriminates the fix; the
    diagnostic does not exist pre-fix.
    """
    team = _insert_team(db)
    stable = ["p-a", "p-b", "p-c"]
    same_human = {"old-mike": ("Michael", "Rivera"), "new-mike": ("Michael", "Rivera")}

    ScoutingLoader(db).load_team(
        _crawl(
            team,
            {
                _GAME: _boxscore(
                    _SLUG_A,
                    _team_block([*stable, "old-mike"], names=same_human),
                )
            },
        )
    )
    assert _batting_players(db) == {*stable, "old-mike"}

    caplog.clear()
    with caplog.at_level(logging.WARNING), _capture_player_line_results() as captured:
        second = ScoutingLoader(db).load_team(
            _crawl(
                team,
                {
                    _GAME: _boxscore(
                        _SLUG_A,
                        _team_block([*stable, "new-mike"], names=same_human),
                    )
                },
            )
        )

    assert second.errors == 0, (
        "the diagnostic sits inside the same broad swallow as everything else "
        "here -- a diagnostic whose failure is invisible converts 'no warning' "
        "from evidence into noise"
    )
    _assert_captured_result_objects(captured)
    gate = _batting_gate(captured[-1][1], team)

    assert gate.gate_permitted is True and gate.permitted is True
    assert gate.gate_prior_count == 4 and gate.gate_comparable_count == 3
    assert gate.matched_victim_player_ids == ("old-mike",)

    warnings = _retire_warnings(caplog)
    named = [m for m in warnings if "bb data dedup-players" in m]
    assert len(named) == 1
    assert "old-mike" in named[0]
    assert "1 of the 1 hard-deleted batting line(s)" in named[0]


def test_a_permitted_retire_of_a_genuine_departure_is_NOT_named(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-15's negative control -- without it the positive test pins nothing.

    Same shape, same permitted retire, but the victim shares no name and no
    jersey with any surviving fresh id. The diagnostic must stay silent, or it
    is a warning that fires on every deletion and tells an operator nothing.
    """
    team = _insert_team(db)
    stable = ["p-a", "p-b", "p-c"]

    ScoutingLoader(db).load_team(
        _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block([*stable, "p-gone"]))})
    )
    assert _batting_players(db) == {*stable, "p-gone"}

    caplog.clear()
    with caplog.at_level(logging.WARNING), _capture_player_line_results() as captured:
        second = ScoutingLoader(db).load_team(
            _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block([*stable, "p-new"]))})
        )

    assert second.errors == 0
    _assert_captured_result_objects(captured)
    gate = _batting_gate(captured[-1][1], team)

    assert gate.gate_permitted is True
    assert gate.matched_victim_player_ids == ()
    assert _batting_players(db) == {*stable, "p-new"}
    assert not [m for m in _retire_warnings(caplog) if "bb data dedup-players" in m]


# ---------------------------------------------------------------------------
# TN-11 per-grain ``refused_by`` membership -- EXECUTED, not reasoned
# ---------------------------------------------------------------------------


def test_every_refused_by_member_this_grain_declares_is_actually_reachable(
    db: sqlite3.Connection,
) -> None:
    """All three declared members are produced by a real payload shape.

    ``refused_by`` membership is PER GRAIN and the enum has drifted before, so a
    declared member that no payload can produce is a state a test could assert
    and never reach. This grain has no cap and no boxscore-completeness signal,
    so ``"cap"`` and ``"boxscores_incomplete"`` are correctly absent from
    ``_PLAYER_LINE_REFUSERS``; the three that ARE declared are each driven here.

    The ``"empty_payload"`` / ``"gate"`` split is the one worth executing: a full
    id churn is populated AND non-empty, and it is the OVERLAP with the
    protected population that is zero, so it must land on ``"gate"``.
    """
    from src.db.reconcile_at_load import _PLAYER_LINE_REFUSERS

    assert "cap" not in _PLAYER_LINE_REFUSERS
    assert "boxscores_incomplete" not in _PLAYER_LINE_REFUSERS

    seen: dict[str, str] = {}

    # (a) fetch_not_ok -- the MODAL scored-but-EMPTY block.
    team_a = _insert_team(db, _SLUG_A, _UUID_A, "Team A")
    game_a = "game-refuse-a"
    ScoutingLoader(db).load_team(
        _crawl(
            team_a,
            {game_a: _boxscore(_SLUG_A, _team_block(_gen("e", 9)))},
            games=[_game_entry(game_a)],
        )
    )
    with _capture_player_line_results() as captured:
        assert (
            ScoutingLoader(db)
            .load_team(
                _crawl(
                    team_a,
                    {
                        game_a: _boxscore(
                            _SLUG_A, _team_block(_gen("e", 9), empty_stats=True)
                        )
                    },
                    games=[_game_entry(game_a)],
                )
            )
            .errors
            == 0
        )
    _assert_captured_result_objects(captured)
    seen["fetch_not_ok"] = _batting_gate(captured[-1][1], team_a).refused_by

    # (b) empty_payload -- populated block, but this TABLE's fresh set is empty.
    team_b = _insert_team(db, _SLUG_B, _UUID_B, "Team B")
    game_b = "game-refuse-b"
    batters, pitchers = _gen("b", 9), _gen("pit", 4)
    ScoutingLoader(db).load_team(
        _crawl(
            team_b,
            {game_b: _boxscore(_SLUG_B, _team_block(batters, pitchers))},
            games=[_game_entry(game_b)],
        )
    )
    with _capture_player_line_results() as captured:
        assert (
            ScoutingLoader(db)
            .load_team(
                _crawl(
                    team_b,
                    {game_b: _boxscore(_SLUG_B, _team_block(batters))},
                    games=[_game_entry(game_b)],
                )
            )
            .errors
            == 0
        )
    _assert_captured_result_objects(captured)
    pitching = captured[-1][1].gate_outcomes[("player_game_pitching", team_b)]
    seen["empty_payload"] = pitching.refused_by
    assert pitching.gate_permitted is False
    assert _pitching_players(db, game_b) == set(pitchers), "no pitching line may be retired"

    # (c) gate -- a full id churn: populated, non-empty, zero OVERLAP.
    team_c = _insert_team(db, "team-c-slug", "cccccccc-0000-0000-0000-00000000000c", "C")
    game_c = "game-refuse-c"
    ScoutingLoader(db).load_team(
        _crawl(
            team_c,
            {game_c: _boxscore("team-c-slug", _team_block(_gen("c1", 9)))},
            games=[_game_entry(game_c)],
        )
    )
    with _capture_player_line_results() as captured:
        assert (
            ScoutingLoader(db)
            .load_team(
                _crawl(
                    team_c,
                    {game_c: _boxscore("team-c-slug", _team_block(_gen("c2", 9)))},
                    games=[_game_entry(game_c)],
                )
            )
            .errors
            == 0
        )
    _assert_captured_result_objects(captured)
    seen["gate"] = _batting_gate(captured[-1][1], team_c).refused_by

    assert seen == {
        "fetch_not_ok": "fetch_not_ok",
        "empty_payload": "empty_payload",
        "gate": "gate",
    }
    assert set(seen.values()) == set(_PLAYER_LINE_REFUSERS)


def test_a_MISSING_snapshot_key_fails_closed_rather_than_permitting_vacuously(
    db: sqlite3.Connection,
) -> None:
    """A mis-keyed capture must raise, not default to an empty snapshot.

    The evidence-parameter rule (``.claude/rules/python-style.md``): a signal
    whose ABSENCE is indistinguishable from its safe value must default to the
    refusing side. Here "nothing loaded yet" is carried as an EMPTY frozenset
    PRESENT at the key -- so an absent key is unambiguously a wiring mistake,
    and defaulting it to empty would hand it straight to the vacuous-permit
    rule: every prior line hard-deleted, ``gate_prior_count == 0``, and no
    refusal WARN anywhere. A gate that fails open is worse than the defect it
    corrects, because it looks like a gate.
    """
    from src.db.reconcile_at_load import PlayerLineBlock, retire_absent_player_lines

    team = _insert_team(db)
    stored = _gen("old", 9)
    ScoutingLoader(db).load_team(
        _crawl(team, {_GAME: _boxscore(_SLUG_A, _team_block(stored))})
    )
    assert _batting_players(db) == set(stored)

    with pytest.raises(KeyError, match="prior snapshot is missing"):
        retire_absent_player_lines(
            db,
            game_id=_GAME,
            perspective_team_id=team,
            blocks=[
                PlayerLineBlock(
                    team_id=team,
                    batting_player_ids=frozenset(_gen("new", 9)),
                    pitching_player_ids=frozenset(),
                    populated=True,
                )
            ],
            prior_snapshots={},  # mis-keyed capture
        )

    assert _batting_players(db) == set(stored), "rows were deleted before raising"


def test_a_jersey_only_match_is_caught_when_the_name_changed_too(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-15's JERSEY half -- the one name matching provably cannot cover.

    Without this the jersey branch is dead weight: deleting it outright leaves
    the entire suite green (executed), because both other AC-15 tests match on
    NAME and the negative control shares neither key. An implementation with the
    wrong dict, the wrong ``team_id``, or a ``jersey_number`` filter that
    excludes every row would ship unnoticed.

    The shape it covers is a re-issued ``player_id`` whose DISPLAYED NAME also
    changed -- ``Mike`` -> ``Michael``, which is not a prefix either way and is
    exactly regime B's premise. Here the surnames differ too, so name matching
    cannot fire and only the shared number can.
    """
    team = _insert_team(db)
    stable = ["p-a", "p-b", "p-c"]
    # Different first names AND different surnames -> name_match is impossible.
    names = {"old-12": ("Mike", "Alvarez"), "new-12": ("Michael", "Booker")}
    numbers = {"old-12": "12", "new-12": "12"}

    ScoutingLoader(db).load_team(
        _crawl(
            team,
            {
                _GAME: _boxscore(
                    _SLUG_A,
                    _team_block([*stable, "old-12"], names=names, numbers=numbers),
                )
            },
        )
    )
    assert _batting_players(db) == {*stable, "old-12"}

    caplog.clear()
    with caplog.at_level(logging.WARNING), _capture_player_line_results() as captured:
        second = ScoutingLoader(db).load_team(
            _crawl(
                team,
                {
                    _GAME: _boxscore(
                        _SLUG_A,
                        _team_block(
                            [*stable, "new-12"], names=names, numbers=numbers
                        ),
                    )
                },
            )
        )

    assert second.errors == 0
    _assert_captured_result_objects(captured)
    gate = _batting_gate(captured[-1][1], team)
    assert gate.gate_permitted is True
    assert gate.matched_victim_player_ids == ("old-12",)

    # The jersey really is the only thing they share -- if name matching could
    # have fired, this test would not isolate the branch it exists to cover.
    stored = dict(
        db.execute(
            "SELECT player_id, last_name FROM players WHERE player_id IN "
            "('old-12', 'new-12')"
        )
    )
    assert stored["old-12"] != stored["new-12"]

    named = [m for m in _retire_warnings(caplog) if "bb data dedup-players" in m]
    assert len(named) == 1
    assert "old-12" in named[0]


def test_a_blank_first_name_does_not_manufacture_a_match(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """Two DIFFERENT humans under one surname must not be named as a re-issue.

    ``ScoutingLoader._load_roster_from_data`` stores
    ``first_name=str(player.get("first_name") or "")``, so a GC roster entry
    with no first name lands as ``''`` -- and it STAYS blank, because
    ``ensure_player_row`` only overwrites when the incoming value is
    ``!= 'Unknown'`` and the boxscore path substitutes exactly ``'Unknown'``
    for a missing name. Hence the roster in this fixture: the blank is only
    reachable through that path, which is why it loads first.

    Unguarded, ``s_first.startswith("")`` is True for every string, so a blank
    first name plus a shared surname matched ANY teammate -- and the diagnostic
    would name the pair and point the operator at ``bb data dedup-players``,
    which cannot act, because detection guards that pair with
    ``LENGTH(_dedup_fold(first_name)) > 0``.

    A false-positive channel does to a warning what a silent failure does to its
    absence: it converts the signal into noise. And the population is not random
    -- it concentrates on players GC has no first name for, which skews toward
    the opponent-roster entries this diagnostic exists to watch.
    """
    team = _insert_team(db)
    stable = ["p-a", "p-b", "p-c"]
    # Same surname, DIFFERENT humans, different jerseys; victim has no first name.
    names = {"blank-1": ("Unknown", "Rivera"), "dana-2": ("Dana", "Rivera")}
    numbers = {"blank-1": "7", "dana-2": "23"}

    def _roster() -> list[dict]:
        """Lists every player in BOTH runs, so the roster grain stays inert."""
        entries = [
            {"id": pid, "first_name": f"First{pid.replace('-', '')}",
             "last_name": f"Last{pid.replace('-', '')}", "number": f"n{pid}"}
            for pid in stable
        ]
        # No ``first_name`` key at all -> the roster path stores ''.
        entries.append({"id": "blank-1", "last_name": "Rivera", "number": "7"})
        entries.append(
            {"id": "dana-2", "first_name": "Dana", "last_name": "Rivera",
             "number": "23"}
        )
        return entries

    def _crawl_with(block_ids: list[str]) -> SimpleNamespace:
        crawl = _crawl(
            team,
            {
                _GAME: _boxscore(
                    _SLUG_A, _team_block(block_ids, names=names, numbers=numbers)
                )
            },
        )
        crawl.roster = _roster()
        return crawl

    ScoutingLoader(db).load_team(_crawl_with([*stable, "blank-1"]))
    assert db.execute(
        "SELECT first_name FROM players WHERE player_id = 'blank-1'"
    ).fetchone()[0] == "", "the fixture must actually store a blank first name"

    caplog.clear()
    with caplog.at_level(logging.WARNING), _capture_player_line_results() as captured:
        second = ScoutingLoader(db).load_team(_crawl_with([*stable, "dana-2"]))

    assert second.errors == 0
    _assert_captured_result_objects(captured)
    gate = _batting_gate(captured[-1][1], team)
    assert gate.gate_permitted is True, "the retire must still be permitted"
    assert gate.matched_victim_player_ids == ()
    assert not [m for m in _retire_warnings(caplog) if "bb data dedup-players" in m]

    # ...and the instrument the WARN would have recommended agrees: it cannot
    # see this pair either.
    from src.db.player_dedup import find_duplicate_players

    pairs = find_duplicate_players(db, team_id=team, season_id=_SEASON)
    assert not [
        p
        for p in pairs
        if {p.canonical_player_id, p.duplicate_player_id} == {"blank-1", "dana-2"}
    ]


def test_the_content_refusal_leaves_regime_B_open_on_a_DIFFERING_opponent_line(
    db: sqlite3.Connection
) -> None:
    """The boundary of what the opponent sweep closes -- pinned, not assumed.

    The sibling test above shows the sweep closing the accumulate-then-delete
    window on the opponent block. It closes it only where the merge is SAFE. When
    the re-issued id's line DISAGREES with the prior generation's for the same
    ``(game_id, perspective_team_id)`` -- a scorekeeper edit between re-scouts --
    the content-aware refusal declines the component, and this grain reverts to
    the regime-B sequence exactly as it behaved before the sweep reached
    opponents at all: ``[9, 18, 9, 9]``, prior generation hard-deleted on run 3.

    **Unimproved subset, NOT a regression** -- that pinned sequence is character
    for character the one the pre-chunk test asserted for ALL opponent churn.
    What is worth seeing is the shape of the interaction: the content refusal
    stops the DEDUP path from deleting a differing row, and then the player-line
    retire deletes it anyway on run 3 -- after which the component carries no
    conflict, the sweep merges it, and run 4 is converged. So the guard defers
    that deletion to the grain the operator already ruled on (surface it, do not
    gate it -- a permanent refusal there doubles the coach-facing season
    aggregate; IDEA-185), rather than preventing it outright.

    Found by ``/code-review`` on this chunk, which is why it is a test and not a
    sentence: the assertion is what stops the boundary moving silently.
    """
    team = _insert_team(db)
    block = 9
    own = _gen("own", 3)
    originals = _gen("orig", block)
    churn = _gen("churn", block)

    def _opp_block(ids: list[str], ab: int) -> dict:
        """One opponent block whose AB value marks the generation."""
        return {
            "players": [
                _player(pid, "Jordan", f"Sur{pid.rsplit('-', 1)[1]}") for pid in ids
            ],
            "groups": [
                {
                    "category": "lineup",
                    "stats": [
                        {
                            "player_id": pid,
                            "stats": {"AB": ab, "R": 1, "H": 1, "RBI": 1,
                                      "BB": 0, "SO": 0},
                        }
                        for pid in ids
                    ],
                    "extra": [],
                },
                {"category": "pitching", "stats": [], "extra": []},
            ],
        }

    def _opp_crawl(ids: list[str], ab: int) -> SimpleNamespace:
        return _crawl(
            team,
            {_GAME: _boxscore(_SLUG_A, _team_block(own), _opp_block(ids, ab))},
        )

    def _opponent_lines(conn: sqlite3.Connection) -> set[str]:
        return {
            r[0]
            for r in conn.execute(
                "SELECT player_id FROM player_game_batting "
                "WHERE game_id = ? AND team_id != ?",
                (_GAME, team),
            )
        }

    # AB 3 -> 4 is the scorekeeper edit: same game, same perspective, different
    # content, so the colliding rows disagree and the component is refused.
    runs = _drive(
        db,
        [_opp_crawl(originals, 3), *[_opp_crawl(churn, 4) for _ in range(3)]],
        observe=_opponent_lines,
    )

    rows_per_run = [len(live) for _r, _rec, live in runs]
    originals_alive = [len(live & set(originals)) for _r, _rec, live in runs]
    assert all(result.errors == 0 for result, _rec, _live in runs)

    # The pre-chunk sequence, reproduced exactly: run 2 accumulates both
    # generations because the refusal declines to merge them, run 3 deletes the
    # prior one through the player-line grain.
    assert rows_per_run == [9, 18, 9, 9]
    assert originals_alive == [9, 9, 0, 0]

    opp_team = db.execute(
        "SELECT DISTINCT team_id FROM player_game_batting "
        "WHERE game_id = ? AND team_id != ?",
        (_GAME, team),
    ).fetchone()[0]
    gates = [records[(_GAME, "player_game_batting", opp_team)]
             for _r, records, _o in runs]
    assert gates[1].gate_permitted is False
    assert (gates[2].gate_prior_count, gates[2].gate_comparable_count) == (18, 9)
    assert gates[2].gate_permitted is True
    fired = [
        index + 2
        for index, (prev, cur) in enumerate(zip(gates, gates[1:], strict=False))
        if _accumulate_then_delete_fires(prev, cur)
    ]
    assert fired == [3], "the window this shape leaves open must stay visible"

    # ...and once the retire has removed the conflicting rows, the component is
    # mergeable again and the roster converges. The refusal is a deferral, not a
    # permanent split.
    assert db.execute(
        "SELECT COUNT(*) FROM team_rosters WHERE team_id = ?", (opp_team,)
    ).fetchone()[0] == block


def test_a_placeholder_first_name_does_not_manufacture_a_match(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """The stub sibling of the blank-name case above, one dimension over.

    ``"Unknown"`` is not a blank string, so the non-empty guard does not cover
    it -- and ``"unknown"`` IS a prefix of itself, so two placeholder-named ids
    under one surname name-matched here. Detection now EXCLUDES that pair (two ids
    carrying the stub are not evidence they are one human; merging them destroyed a
    real pitching appearance on the live corpus), so an unguarded diagnostic would
    name a re-issue and point the operator at ``bb data dedup-players``, which
    cannot act on it. Same false-positive channel, same reason it matters: the
    population concentrates precisely on the players GC gave no name for.

    The jersey half is deliberately still able to catch these -- so this fixture
    gives the two ids DIFFERENT numbers, isolating the name half under test.
    """
    team = _insert_team(db)
    stable = ["p-a", "p-b", "p-c"]
    # Two DIFFERENT humans, both nameless in the boxscore, different jerseys.
    names = {
        "stub-1": ("Unknown", "Unknown"),
        "stub-2": ("Unknown", "Unknown"),
    }
    numbers = {"stub-1": "7", "stub-2": "23"}

    def _crawl_with(block_ids: list[str]) -> SimpleNamespace:
        return _crawl(
            team,
            {
                _GAME: _boxscore(
                    _SLUG_A, _team_block(block_ids, names=names, numbers=numbers)
                )
            },
        )

    ScoutingLoader(db).load_team(_crawl_with([*stable, "stub-1"]))
    assert db.execute(
        "SELECT first_name FROM players WHERE player_id = 'stub-1'"
    ).fetchone()[0] == "Unknown", "the fixture must actually store the stub name"

    caplog.clear()
    with caplog.at_level(logging.WARNING), _capture_player_line_results() as captured:
        second = ScoutingLoader(db).load_team(_crawl_with([*stable, "stub-2"]))

    assert second.errors == 0
    _assert_captured_result_objects(captured)
    gate = _batting_gate(captured[-1][1], team)
    assert gate.gate_permitted is True, "the retire must still be permitted"
    assert gate.matched_victim_player_ids == ()
    assert not [m for m in _retire_warnings(caplog) if "bb data dedup-players" in m]

    # ...and the instrument the WARN would have recommended agrees.
    from src.db.player_dedup import find_duplicate_players

    pairs = find_duplicate_players(db, team_id=team, season_id=_SEASON)
    assert not [
        p
        for p in pairs
        if {p.canonical_player_id, p.duplicate_player_id} == {"stub-1", "stub-2"}
    ]


@pytest.mark.parametrize("churn_block", [9, 10, 11])
def test_sub_boundary_churn_stays_co_resident_and_never_deletes(
    db: sqlite3.Connection, churn_block: int
) -> None:
    """AC-14: BELOW the ``m >= P`` boundary the outcome is DIFFERENT, not smaller.

    With ``P = 12`` originals and a churn block of ``m < 12``, the gate refuses
    on EVERY run -- the floor ``m >= 0.5 * (P + m)`` reduces to ``m >= P`` -- so
    the two generations become permanently CO-RESIDENT at ``P + m`` rows and the
    originals all survive. This is not "duplicates": the churn block is smaller
    than the original, so exact doubling appears only at ``m == P``.

    Pinned because a regime-B fixture accidentally built here pins permanent
    co-residence instead of the delete and READS AS PASSING. The knife edge is
    measured, not a safe margin: ``m = 11`` refuses and ``m = 12`` deletes, with
    no gap between them.
    """
    team = _insert_team(db)
    block = 12
    originals = _gen("orig", block)
    churn = _gen("churn", churn_block)

    runs = _drive(
        db,
        [
            _crawl(team, {_GAME: _boxscore(_SLUG_A, _named_block(originals, _UNMERGEABLE_ORIGINAL))}),
            *[
                _crawl(team, {_GAME: _boxscore(_SLUG_A, _named_block(churn, _UNMERGEABLE_CHURN))})
                for _ in range(3)
            ],
        ],
        observe=lambda conn: _batting_ids_for_team(conn, team),
    )

    rows_per_run = []
    originals_alive = []
    for index, (result, _records, live) in enumerate(runs):
        assert result.errors == 0, f"run {index + 1} raised and was swallowed"
        rows_per_run.append(len(live))
        originals_alive.append(len(live & set(originals)))

    assert rows_per_run == [block, block + churn_block, block + churn_block,
                            block + churn_block]
    assert originals_alive == [block] * 4

    key = (_GAME, "player_game_batting", team)
    gates = [records[key] for _result, records, _obs in runs]
    for gate in gates[1:]:
        assert gate.gate_permitted is False
        assert gate.refused_by == "gate"

    # The accumulate-then-delete predicate must stay silent below the boundary.
    for prev, cur in zip(gates, gates[1:], strict=False):
        assert not _accumulate_then_delete_fires(prev, cur)


def test_a_jersey_reused_in_a_DIFFERENT_season_is_not_a_match(
    db: sqlite3.Connection,
) -> None:
    """The season-scoping negative control for the AC-15 jersey branch.

    ``team_rosters``' PK is ``(team_id, player_id, season_id)``, so a jersey read
    keyed on team+player alone returns one row PER SEASON and keeps whichever
    SQLite returns last. That made the diagnostic decide on row ORDERING, in
    **both** directions: a cross-season reuse could false-positive, and a genuine
    same-season collision could be suppressed if the other year's row landed
    last.

    Two DIFFERENT humans with no name overlap, so only the jersey branch can
    fire. The victim wears #12 in 2025; the survivor wears #99 in 2025 and #12 in
    2026. Nothing here is a same-season collision, so nothing may be named --
    whichever game (and therefore season) the diagnostic is asked about.

    **Why this test is mandatory rather than tidy**: without it the season
    scoping is an unpinned branch, deletable in silence. That is exactly the
    MF-1 situation from this story's own round 1, where the entire jersey half
    could be removed with the full suite still green. Do not ship the fix with
    the hole the fix's own sibling was found in.
    """
    from src.db.reconcile_at_load import _dedup_candidate_victims

    team = _insert_team(db)
    for season in ("2025", "2026"):
        db.execute(
            "INSERT OR IGNORE INTO seasons (season_id, name, year) VALUES (?, ?, ?)",
            (season, season, int(season)),
        )
    for pid, first, last in (
        ("v-cross", "Ana", "Alvarez"),
        ("s-cross", "Bo", "Booker"),
    ):
        db.execute(
            "INSERT INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
            (pid, first, last),
        )
    for pid, season, number in (
        ("v-cross", "2025", "12"),
        ("s-cross", "2025", "99"),
        ("s-cross", "2026", "12"),   # same number, DIFFERENT season
    ):
        db.execute(
            "INSERT INTO team_rosters (team_id, player_id, season_id, jersey_number) "
            "VALUES (?, ?, ?, ?)",
            (team, pid, season, number),
        )
    for game_id, season in (("g-2025", "2025"), ("g-2026", "2026")):
        db.execute(
            "INSERT INTO games (game_id, season_id, game_date, home_team_id, "
            "away_team_id) VALUES (?, ?, '2026-04-01', ?, ?)",
            (game_id, season, team, team),
        )
    db.commit()

    # Names cannot match, so a hit here could only come from the jersey branch.
    for game_id in ("g-2025", "g-2026"):
        assert _dedup_candidate_victims(
            db,
            game_id=game_id,
            team_id=team,
            victim_ids=["v-cross"],
            surviving_fresh_ids=["s-cross"],
        ) == (), f"{game_id}: a cross-season jersey reuse was named as a re-issue"

    # POSITIVE control in the same fixture: a genuine SAME-season collision must
    # still fire, or the assertions above would also pass with the jersey branch
    # deleted outright -- which is the failure this test exists to prevent.
    db.execute(
        "INSERT INTO players (player_id, first_name, last_name) "
        "VALUES ('v-same', 'Cy', 'Cortez')"
    )
    db.execute(
        "INSERT INTO team_rosters (team_id, player_id, season_id, jersey_number) "
        "VALUES (?, 'v-same', '2026', '12')",
        (team,),
    )
    db.commit()
    assert _dedup_candidate_victims(
        db,
        game_id="g-2026",
        team_id=team,
        victim_ids=["v-same"],
        surviving_fresh_ids=["s-cross"],
    ) == ("v-same",), "a same-season jersey collision must still be named"


