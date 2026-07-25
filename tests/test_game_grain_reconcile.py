"""Game-grain reconcile-at-load tests (E-267-02).

Covers the three regressions the story names -- all of which corrupt the
game-level reads (``_query_record``, recent form, runs-avg) and, through
``player_game_*``, the query-time season aggregates:

- AC-1: a game REMOVED upstream keeps living in the DB forever (accumulate-only
  load), inflating W-L and the freshness game count.
- AC-2: a CROSS-perspective rescheduled game is double-inserted because the
  date+team-pair dedup key breaks on a date move.
- AC-3: a SAME-perspective rescheduled game must be matched on its stable
  ``event_id`` and date-UPDATED in place -- never double-inserted, never deleted.

Plus the bias-to-refuse surface (AC-4 / AC-5 / AC-6 / AC-7): a not-final game,
a not-final game that only survives because the FULL schedule array was threaded
(not the ``completed`` subset), and the GAP-1 mass-delete safety case where the
fresh schedule fetch fails / returns empty / shrinks below the floor ratio.

All tests drive the real ``ScoutingLoader.load_team`` entry point against a
migrated on-disk SQLite database. No network calls.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from migrations.apply_migrations import run_migrations
from src.db import reconcile_at_load
from src.db.game_merge import _PERSPECTIVE_CHILD_TABLES, merge_duplicate_game
from src.db.reconcile_at_load import (
    FLOOR_RATIO,
    MAX_GAME_RETIREMENTS,
    retire_absent_games,
)
from src.gamechanger.loaders import ensure_season_row
from src.gamechanger.loaders.scouting_loader import ScoutingLoader

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_SEASON = "2026"
_SLUG_A = "team-a-slug"
_SLUG_B = "team-b-slug"
_UUID_A = "aaaaaaaa-0000-0000-0000-000000000001"
_UUID_B = "bbbbbbbb-0000-0000-0000-000000000002"
_OPP_UUID = "cccccccc-0000-0000-0000-000000000003"
_PLAYER = "player-uuid-0001"


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    """Apply all migrations and return an open connection."""
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
    cursor = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, public_id, is_active, "
        "season_year) VALUES (?, 'tracked', ?, ?, 0, 2026)",
        (name, gc_uuid, public_id),
    )
    db.commit()
    return cursor.lastrowid


def _game(
    game_id: str,
    *,
    start_ts: str = "2026-04-10T18:00:00Z",
    status: str | None = "completed",
    team_score: int = 5,
    opp_score: int = 3,
    opponent: str = "Opp Town",
) -> dict:
    """One entry of the public ``/games`` schedule array.

    ``status=None`` OMITS the ``game_status`` key entirely -- the common
    not-final shape per TN-11 Probe 1 (615 completed / 17 key-absent / 1 "new").
    """
    entry = {
        "id": game_id,
        "home_away": "home",
        "start_ts": start_ts,
        "timezone": "America/Chicago",
        "score": {"team": team_score, "opponent_team": opp_score},
        "opponent_team": {"name": opponent},
    }
    if status is not None:
        entry["game_status"] = status
    return entry


def _boxscore(own_key: str, opp_key: str = _OPP_UUID) -> dict:
    return {
        own_key: {
            "players": [
                {"id": _PLAYER, "first_name": "John", "last_name": "Doe", "number": "9"}
            ],
            "groups": [
                {
                    "category": "lineup",
                    "stats": [
                        {
                            "player_id": _PLAYER,
                            "stats": {
                                "AB": 3, "R": 1, "H": 2, "RBI": 1, "BB": 0, "SO": 0
                            },
                        }
                    ],
                    "extra": [],
                }
            ],
        },
        opp_key: {"players": [], "groups": []},
    }


def _crawl(
    team_id: int,
    games: list[dict],
    *,
    boxscore_ids: list[str] | None = None,
    own_key: str = _SLUG_A,
    schedule_fetch_ok: bool = True,
) -> SimpleNamespace:
    """A ``ScoutingCrawlResult``-shaped payload for ``load_team``.

    ``games`` is the FULL schedule array. Boxscores are fetched only for
    completed games -- mirroring ``ScoutingCrawler`` -- unless ``boxscore_ids``
    overrides the selection.
    """
    if boxscore_ids is None:
        boxscore_ids = [
            g["id"] for g in games if g.get("game_status") == "completed"
        ]
    return SimpleNamespace(
        team_id=team_id,
        roster=[],
        games=games,
        boxscores={gid: _boxscore(own_key) for gid in boxscore_ids},
        schedule_fetch_ok=schedule_fetch_ok,
    )


def _seed_child_surface(db: sqlite3.Connection, game_id: str, team_id: int) -> None:
    """Attach a plays / play_events / spray_charts / discrepancy row to a game.

    The boxscore load only ever writes ``player_game_batting`` and
    ``game_perspectives``, so without this the table-by-table retire assertions
    would be ``0 == 0`` -- true BEFORE the delete and therefore vacuous. The
    plays chain matters most: ``play_events`` FKs ``plays(id)``, so a retire that
    deletes ``plays`` before its events fails the FK under
    ``PRAGMA foreign_keys=ON``, gets swallowed by the reconcile's except block,
    and would silently never retire exactly the games carrying the most data.
    """
    play_id = db.execute(
        """
        INSERT INTO plays (game_id, play_order, inning, half, season_id,
                           batting_team_id, perspective_team_id, batter_id,
                           outcome)
        VALUES (?, 1, 1, 'top', ?, ?, ?, ?, 'single')
        """,
        (game_id, _SEASON, team_id, team_id, _PLAYER),
    ).lastrowid
    db.execute(
        "INSERT INTO play_events (play_id, event_order, event_type, pitch_result) "
        "VALUES (?, 1, 'pitch', 'in_play')",
        (play_id,),
    )
    db.execute(
        """
        INSERT INTO player_game_pitching
            (game_id, player_id, team_id, perspective_team_id, ip_outs)
        VALUES (?, ?, ?, ?, 6)
        """,
        (game_id, _PLAYER, team_id, team_id),
    )
    db.execute(
        """
        INSERT INTO spray_charts (game_id, player_id, team_id,
                                  perspective_team_id, chart_type, event_gc_id,
                                  season_id, x, y)
        VALUES (?, ?, ?, ?, 'offensive', ?, ?, 1.0, 2.0)
        """,
        (game_id, _PLAYER, team_id, team_id, f"evt-{game_id}", _SEASON),
    )
    db.execute(
        """
        INSERT INTO reconciliation_discrepancies
            (game_id, run_id, perspective_team_id, team_id, player_id,
             signal_name, category, status)
        VALUES (?, 'run-1', ?, ?, ?, 'so', 'batting', 'MATCH')
        """,
        (game_id, team_id, team_id, _PLAYER),
    )
    db.commit()


def _game_ids(db: sqlite3.Connection) -> set[str]:
    return {r[0] for r in db.execute("SELECT game_id FROM games")}


def _game_dates(db: sqlite3.Connection) -> dict[str, str]:
    return {r[0]: r[1] for r in db.execute("SELECT game_id, game_date FROM games")}


def _play_event_count(db: sqlite3.Connection, game_id: str) -> int:
    return db.execute(
        "SELECT COUNT(*) FROM play_events e JOIN plays p ON p.id = e.play_id "
        "WHERE p.game_id = ?",
        (game_id,),
    ).fetchone()[0]


def _retire_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING and "Game-grain retire" in r.getMessage()
    ]


# ---------------------------------------------------------------------------
# AC-1: removed game is retired, full child surface gone
# ---------------------------------------------------------------------------


def test_removed_game_is_retired_with_full_child_surface(
    db: sqlite3.Connection,
) -> None:
    """AC-1/AC-7: a game absent from the fresh schedule is hard-deleted whole.

    Pre-fix this test fails on the first assertion: the accumulate-only load
    never retired anything, so the removed game stayed in ``games`` and kept
    counting toward W-L / recent form / the freshness game count.
    """
    team = _insert_team(db)
    kept = _game("game-kept", start_ts="2026-04-10T18:00:00Z")
    removed = _game("game-removed", start_ts="2026-04-12T18:00:00Z", opponent="Other")

    ScoutingLoader(db).load_team(_crawl(team, [kept, removed]))
    assert _game_ids(db) == {"game-kept", "game-removed"}
    # Give the removed game the FULL child surface a reports run would attach,
    # so every table-by-table assertion below is non-vacuous.
    _seed_child_surface(db, "game-removed", team)
    for table in ("game_perspectives", *_PERSPECTIVE_CHILD_TABLES):
        before = db.execute(
            f"SELECT COUNT(*) FROM {table} WHERE game_id = 'game-removed'"  # noqa: S608
        ).fetchone()[0]
        assert before > 0, f"{table} must hold rows BEFORE the retire"
    assert _play_event_count(db, "game-removed") > 0

    # Re-scout: GC no longer returns the second game at all.
    ScoutingLoader(db).load_team(_crawl(team, [kept]))

    assert _game_ids(db) == {"game-kept"}
    # Table-by-table: a games-row-LAST partial retire would leave orphans here.
    for table in ("game_perspectives", *_PERSPECTIVE_CHILD_TABLES):
        count = db.execute(
            f"SELECT COUNT(*) FROM {table} WHERE game_id = 'game-removed'"  # noqa: S608
        ).fetchone()[0]
        assert count == 0, f"{table} still holds rows for the retired game"
    assert _play_event_count(db, "game-removed") == 0


def test_removed_game_no_longer_counts_in_season_aggregates(
    db: sqlite3.Connection,
) -> None:
    """AC-1: the retired game's player line stops inflating the season totals."""
    from src.api.db import get_season_batting

    db.row_factory = sqlite3.Row  # get_season_batting returns dict(row)
    team = _insert_team(db)
    kept = _game("game-kept")
    removed = _game("game-removed", start_ts="2026-04-12T18:00:00Z", opponent="Other")

    ScoutingLoader(db).load_team(_crawl(team, [kept, removed]))
    before = {r["player_id"]: r for r in get_season_batting(db, team, _SEASON)}
    assert before[_PLAYER]["ab"] == 6  # two games x 3 AB

    ScoutingLoader(db).load_team(_crawl(team, [kept]))
    after = {r["player_id"]: r for r in get_season_batting(db, team, _SEASON)}
    assert after[_PLAYER]["ab"] == 3


# ---------------------------------------------------------------------------
# AC-3: same-perspective reschedule -- id match, in-place date UPDATE, no delete
# ---------------------------------------------------------------------------


def test_same_perspective_reschedule_updates_date_in_place(
    db: sqlite3.Connection,
) -> None:
    """AC-3/AC-7: a moved game is id-matched and date-UPDATEd -- one row, no delete.

    The stable ``event_id`` survives GC's reschedule PATCH-in-place, so the game
    must NOT be double-inserted (the date+team-pair dedup key alone would miss
    it) and must NOT be routed through the removal path.
    """
    team = _insert_team(db)

    ScoutingLoader(db).load_team(
        _crawl(team, [_game("game-moved", start_ts="2026-04-10T18:00:00Z")])
    )
    assert _game_dates(db) == {"game-moved": "2026-04-10"}
    batting_before = db.execute(
        "SELECT COUNT(*) FROM player_game_batting WHERE game_id = 'game-moved'"
    ).fetchone()[0]

    # Same team re-scouts; GC moved the SAME event to a new date.
    ScoutingLoader(db).load_team(
        _crawl(team, [_game("game-moved", start_ts="2026-04-17T18:00:00Z")])
    )

    assert _game_ids(db) == {"game-moved"}, "reschedule must not double-insert"
    assert _game_dates(db) == {"game-moved": "2026-04-17"}
    # No delete: the child rows are still attached to the same game_id.
    assert db.execute(
        "SELECT COUNT(*) FROM player_game_batting WHERE game_id = 'game-moved'"
    ).fetchone()[0] == batting_before


# ---------------------------------------------------------------------------
# AC-2: cross-perspective reschedule -- merged via the canonical seam
# ---------------------------------------------------------------------------


def test_cross_perspective_reschedule_merges_not_double_inserts(
    db: sqlite3.Connection,
) -> None:
    """AC-2/AC-7: a moved game that is a cross-perspective twin collapses to one row.

    Team B's perspective already holds the game at its NEW date under a different
    event id. When team A re-scouts and its own event turns up at that new date,
    the pair must merge through ``merge_duplicate_game`` rather than persist as
    two rows for one real game.
    """
    team_a = _insert_team(db, _SLUG_A, _UUID_A, "Team A")
    team_b = _insert_team(db, _SLUG_B, _UUID_B, "Team B")

    def a_vs_b(start_ts: str) -> dict:
        return _game("evt-a", start_ts=start_ts, opponent="Team B")

    # A loads its event at the ORIGINAL date.
    ScoutingLoader(db).load_team(_crawl(team_a, [a_vs_b("2026-04-10T18:00:00Z")]))
    # B loads the SAME real game (its own event id) at the NEW date.
    ScoutingLoader(db).load_team(
        _crawl(
            team_b,
            [_game("evt-b", start_ts="2026-04-17T18:00:00Z", opponent="Team A")],
            own_key=_SLUG_B,
        )
    )
    assert _game_ids(db) == {"evt-a", "evt-b"}

    # A re-scouts: its event now reports the NEW date -> same date + team pair
    # as B's row -> cross-perspective twin. AC-2 requires the collapse to run
    # through the CANONICAL seam, so spy on it (wraps=real, behavior unchanged):
    # asserting one-row-two-perspectives alone would also pass for an inline
    # FK-re-pointing implementation, which CLAUDE.md forbids.
    with patch(
        "src.gamechanger.loaders.game_loader.merge_duplicate_game",
        wraps=merge_duplicate_game,
    ) as spy:
        ScoutingLoader(db).load_team(_crawl(team_a, [a_vs_b("2026-04-17T18:00:00Z")]))

    assert spy.call_count == 1, "the merge must route through merge_duplicate_game"

    remaining = _game_ids(db)
    assert len(remaining) == 1, f"expected one merged row, got {remaining}"
    canonical = next(iter(remaining))
    perspectives = {
        r[0]
        for r in db.execute(
            "SELECT perspective_team_id FROM game_perspectives WHERE game_id = ?",
            (canonical,),
        )
    }
    assert perspectives == {team_a, team_b}


# ---------------------------------------------------------------------------
# AC-4 / AC-5 / AC-6: bias to refuse
# ---------------------------------------------------------------------------


def test_not_final_game_is_not_retired_and_warns(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-4/AC-7(a): a prior-loaded game that turns not-final is kept, with a WARN.

    Exercises all three not-final shapes TN-11 Probe 1 observed: the ABSENT key,
    an explicit ``null``, and the ``"new"`` unscored stub.
    """
    # A completed sibling keeps the crawl non-empty, so the reconcile runs.
    anchor = _game("g-anchor", start_ts="2026-04-01T18:00:00Z", opponent="Anchor Opp")

    for shape in (None, "new"):
        db.execute("DELETE FROM player_game_batting")
        db.execute("DELETE FROM game_perspectives")
        db.execute("DELETE FROM games")
        db.execute("DELETE FROM teams WHERE public_id IS NULL OR public_id != ?",
                   (_SLUG_A,))
        db.commit()
        team = db.execute(
            "SELECT id FROM teams WHERE public_id = ?", (_SLUG_A,)
        ).fetchone()
        team = team[0] if team else _insert_team(db)

        ScoutingLoader(db).load_team(
            _crawl(team, [anchor, _game("g-1", opponent="Opp")])
        )
        assert "g-1" in _game_ids(db)

        caplog.clear()
        with caplog.at_level(logging.WARNING):
            ScoutingLoader(db).load_team(
                _crawl(team, [anchor, _game("g-1", status=shape, opponent="Opp")])
            )

        assert "g-1" in _game_ids(db), f"not-final ({shape!r}) must not be retired"
        warnings = _retire_warnings(caplog)
        assert len(warnings) == 1, warnings
        assert "REFUSED" in warnings[0]
        assert "NOT final" in warnings[0]


def test_explicit_null_game_status_is_not_retired(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-4: an explicit ``game_status: null`` is also not-final, not removed."""
    team = _insert_team(db)
    anchor = _game("g-anchor", start_ts="2026-04-01T18:00:00Z", opponent="Anchor Opp")
    ScoutingLoader(db).load_team(_crawl(team, [anchor, _game("g-null")]))

    entry = _game("g-null")
    entry["game_status"] = None
    with caplog.at_level(logging.WARNING):
        ScoutingLoader(db).load_team(_crawl(team, [anchor, entry]))

    assert "g-null" in _game_ids(db)
    warnings = _retire_warnings(caplog)
    assert len(warnings) == 1 and "NOT final" in warnings[0]


def test_not_final_game_survives_because_full_array_is_threaded(
    db: sqlite3.Connection,
) -> None:
    """AC-5/AC-7(b): the reconcile diffs the FULL array, not ``completed_games``.

    The harness deliberately feeds a schedule whose completed subset is a
    STRICT subset of the array: the survivor's only proof of life is its
    presence in the array with a non-``completed`` status. If the production
    code (or this test's own wiring) diffed against the completed subset, the
    not-final game would be classified REMOVED and mass-deleted here.
    """
    team = _insert_team(db)
    played = _game("g-played", start_ts="2026-04-10T18:00:00Z", opponent="Opp One")
    upcoming = _game(
        "g-upcoming", start_ts="2026-06-01T18:00:00Z", status=None, opponent="Opp Two"
    )

    # First load: both are completed, so both persist.
    ScoutingLoader(db).load_team(
        _crawl(team, [played, _game("g-upcoming", start_ts="2026-06-01T18:00:00Z",
                                   opponent="Opp Two")])
    )
    assert _game_ids(db) == {"g-played", "g-upcoming"}

    # Re-scout: GC now reports g-upcoming as not-final (key absent). It is in
    # the FULL array but NOT in the completed subset.
    full_array = [played, upcoming]
    completed_subset = [g for g in full_array if g.get("game_status") == "completed"]
    assert len(completed_subset) < len(full_array), "harness must not pre-filter"

    ScoutingLoader(db).load_team(_crawl(team, full_array))

    assert _game_ids(db) == {"g-played", "g-upcoming"}


def test_absent_from_full_array_is_a_genuine_removal(
    db: sqlite3.Connection,
) -> None:
    """AC-6: GC retains unplayed games, so full absence means removed/voided.

    A long-past unplayed game stays in the array (and is kept); only the game
    that vanished entirely is retired.
    """
    team = _insert_team(db)
    played = _game("g-played", start_ts="2026-04-10T18:00:00Z", opponent="Opp One")
    unplayed = _game("g-unplayed", start_ts="2026-04-12T18:00:00Z", opponent="Opp Two")
    voided = _game("g-voided", start_ts="2026-04-14T18:00:00Z", opponent="Opp Three")

    ScoutingLoader(db).load_team(_crawl(team, [played, unplayed, voided]))
    assert _game_ids(db) == {"g-played", "g-unplayed", "g-voided"}

    # g-unplayed is retained by GC but never played; g-voided is gone entirely.
    unplayed_now = _game(
        "g-unplayed", start_ts="2026-04-12T18:00:00Z", status=None, opponent="Opp Two"
    )
    ScoutingLoader(db).load_team(_crawl(team, [played, unplayed_now]))

    assert _game_ids(db) == {"g-played", "g-unplayed"}


# ---------------------------------------------------------------------------
# AC-7(c) GAP-1: mass-delete safety -- the highest-value guard
# ---------------------------------------------------------------------------
# SCOPE NOTE, so a future reader does not over-read this coverage: the failed-
# and empty-schedule cases below construct a crawl shape production cannot
# actually emit -- an empty ``games`` array WITH a non-empty ``boxscores`` dict.
# A real failed or empty schedule fetch returns no boxscores, so in production
# it is the ``if not boxscores`` early return in ``_load_team_core`` that stops
# the retire, and the reconcile is never reached at all. These tests therefore
# prove the HELPER's refusal logic (a genuine defense-in-depth guard), not the
# production trigger path. The truncated-array and catastrophic-shrink tests
# below DO use production-reachable shapes.


def _seed_four_games(db: sqlite3.Connection, team: int) -> list[dict]:
    games = [
        _game(f"g-{i}", start_ts=f"2026-04-1{i}T18:00:00Z", opponent=f"Opp {i}")
        for i in range(4)
    ]
    ScoutingLoader(db).load_team(_crawl(team, games))
    assert len(_game_ids(db)) == 4
    return games


def _assert_nothing_retired(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """The team's ENTIRE prior game set and its child rows survive intact."""
    assert _game_ids(db) == {"g-0", "g-1", "g-2", "g-3"}
    assert db.execute(
        "SELECT COUNT(DISTINCT game_id) FROM player_game_batting"
    ).fetchone()[0] == 4
    assert db.execute(
        "SELECT COUNT(DISTINCT game_id) FROM game_perspectives"
    ).fetchone()[0] == 4
    warnings = _retire_warnings(caplog)
    assert len(warnings) == 4, warnings
    assert all("REFUSED" in w and "not authoritative" in w for w in warnings)


def test_zero_completed_games_end_to_end_reconcile_never_runs(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """The REAL zero-boxscore control flow, built by the actual crawler.

    Every other refusal test in this file hand-builds a crawl result with
    ``games=[]`` AND a non-empty ``boxscores`` -- a shape the crawler cannot
    produce. The scope note above says so, and two independent reviewers then
    found two different defects in precisely the region that note describes. An
    annotated limitation is not coverage; it marks where the next defect lands.

    So this drives ``ScoutingCrawler.scout_team`` with a schedule containing NO
    completed games, takes whatever result it actually returns, and feeds that to
    ``load_team``. In production that result carries ``games=[]`` and
    ``boxscores={}``, so ``_load_team_core`` returns at its ``if not boxscores``
    guard -- BEFORE both the game-grain and roster-grain reconciles.

    **This test PASSES against current behavior and is not a bug report.** The
    reconcile not running here is the current design, and api-scout's live probes
    found no mechanism that produces this payload (zero reversions across 583
    previously-completed games; zero zero-completed teams across 15 team-seasons,
    2019-2026). Its value is pinning the real control flow so the next change to
    this seam cannot alter it silently -- and removing the "we cannot safely
    change this seam without a test exercising it" obstacle for whoever picks up
    IDEA-158, where the behavior question is tracked.

    Note the report path DOES reach here: ``generator.py`` calls ``load_team()``
    on a skipped crawl result.

    **What would make this stop discriminating** -- the survival assertions are
    NOT the discriminator, and relying on them alone would make this decorative.
    Move the reconcile ahead of the ``if not boxscores`` guard and the game still
    survives, because an empty fresh set gives ``fresh_count == 0`` and the
    health gate refuses. Only the final assertion -- that NO game-grain WARN was
    emitted at all -- separates "the reconcile never ran" from "it ran and
    refused". Keep it, and keep the crawl-shape assertions above: if the crawler
    ever returns the full array here, everything below stops describing
    production.
    """
    from src.gamechanger.crawlers.scouting import ScoutingCrawler

    team = _insert_team(db)
    ScoutingLoader(db).load_team(
        _crawl(team, [_game("g-prior", opponent="Opp One")])
    )
    assert _game_ids(db) == {"g-prior"}
    _seed_child_surface(db, "g-prior", team)

    # A real schedule whose games are all NOT final -> the crawler finds zero
    # completed games and returns its skipped result.
    client = MagicMock()
    client.get_public.return_value = [
        _game("g-upcoming", start_ts="2026-06-01T18:00:00Z", status=None),
    ]
    crawl_result = ScoutingCrawler(client, db).scout_team(_SLUG_A)

    # Pin the shape itself -- if the crawler ever starts returning the full
    # array here, the assertions below stop describing production.
    assert crawl_result.skipped is True
    assert crawl_result.games == []
    assert crawl_result.boxscores == {}

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ScoutingLoader(db).load_team(crawl_result)

    # Current behavior: the load exits before either reconcile, so the prior
    # game and its whole child surface survive untouched.
    assert _game_ids(db) == {"g-prior"}
    assert _play_event_count(db, "g-prior") > 0
    assert not [
        r.getMessage() for r in caplog.records if "Game-grain retire" in r.getMessage()
    ], "the game-grain reconcile ran on a zero-boxscore crawl"


def test_failed_schedule_fetch_retires_nothing(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-7(c): a FAILED schedule fetch must retire zero games (one WARN each)."""
    team = _insert_team(db)
    _seed_four_games(db, team)

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ScoutingLoader(db).load_team(
            _crawl(team, [], boxscore_ids=["g-0"], schedule_fetch_ok=False)
        )

    _assert_nothing_retired(db, caplog)


def test_empty_schedule_retires_nothing(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-7(c): an EMPTY fresh schedule proves nothing -- retire zero games."""
    team = _insert_team(db)
    _seed_four_games(db, team)

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ScoutingLoader(db).load_team(_crawl(team, [], boxscore_ids=["g-0"]))

    _assert_nothing_retired(db, caplog)


def test_catastrophic_shrink_retires_nothing(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-7(c): a schedule shrinking below FLOOR_RATIO retires zero games.

    One of four games returned is a 0.25 ratio -- under the 0.5 floor -- so the
    three absences are refused rather than treated as three removals.
    """
    team = _insert_team(db)
    games = _seed_four_games(db, team)

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ScoutingLoader(db).load_team(_crawl(team, [games[0]]))

    assert _game_ids(db) == {"g-0", "g-1", "g-2", "g-3"}
    assert db.execute(
        "SELECT COUNT(DISTINCT game_id) FROM player_game_batting"
    ).fetchone()[0] == 4
    warnings = _retire_warnings(caplog)
    assert len(warnings) == 3, warnings
    assert all("REFUSED" in w and "not authoritative" in w for w in warnings)


def test_truncated_array_padded_with_upcoming_games_retires_nothing(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """The floor ratio must compare LIKE WITH LIKE, not array-size vs loaded-count.

    The mass-delete scenario the flat ``len(full_array)`` numerator missed: a
    truncated-but-HTTP-200 response whose surviving entries are mostly UPCOMING
    games. Those can never appear in the prior-loaded denominator (only completed
    games are ever inserted), so counting them inflates the numerator past the
    floor while the completed population has collapsed.

    Here 4 loaded games meet a response of 1 completed + 3 upcoming. Counting the
    whole array gives ``4 >= 2.0`` -> authoritative -> 3 games hard-deleted.
    Counting only the comparable population gives ``1 >= 2.0`` -> refuse.
    ``boxscores_complete`` does NOT save this case: the one completed game
    fetches fine, so that guard passes.
    """
    team = _insert_team(db)
    games = _seed_four_games(db, team)
    upcoming = [
        _game(
            f"g-future-{i}",
            start_ts=f"2026-06-0{i}T18:00:00Z",
            status=None,
            opponent=f"Future Opp {i}",
        )
        for i in range(1, 4)
    ]

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ScoutingLoader(db).load_team(_crawl(team, [games[0], *upcoming]))

    assert _game_ids(db) == {"g-0", "g-1", "g-2", "g-3"}
    assert db.execute(
        "SELECT COUNT(DISTINCT game_id) FROM player_game_batting"
    ).fetchone()[0] == 4
    warnings = _retire_warnings(caplog)
    assert len(warnings) == 3, warnings
    assert all("REFUSED" in w and "not authoritative" in w for w in warnings)
    # The guard that fired must be the ratio, not the boxscore-coverage guard.
    assert all("boxscores_complete=True" in w for w in warnings)


def test_shrink_at_the_floor_still_retires(db: sqlite3.Connection) -> None:
    """The floor is a boundary, not a blanket veto: exactly 0.5 is authoritative."""
    team = _insert_team(db)
    games = _seed_four_games(db, team)

    ScoutingLoader(db).load_team(_crawl(team, games[:2]))

    assert _game_ids(db) == {"g-0", "g-1"}


# ---------------------------------------------------------------------------
# Cross-perspective safety: never delete another team's game row
# ---------------------------------------------------------------------------


def test_absent_game_owned_by_another_perspective_is_refused(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """A whole-game delete must never destroy a second perspective's data."""
    team_a = _insert_team(db, _SLUG_A, _UUID_A, "Team A")
    team_b = _insert_team(db, _SLUG_B, _UUID_B, "Team B")

    shared = _game("g-shared", start_ts="2026-04-10T18:00:00Z")
    other = _game("g-other", start_ts="2026-04-12T18:00:00Z", opponent="Opp Two")
    ScoutingLoader(db).load_team(_crawl(team_a, [shared, other]))
    # B loads the SAME game row (same event id, its own perspective).
    ScoutingLoader(db).load_team(_crawl(team_b, [shared], own_key=_SLUG_B))
    assert db.execute(
        "SELECT COUNT(*) FROM game_perspectives WHERE game_id = 'g-shared'"
    ).fetchone()[0] == 2

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        # A's fresh schedule drops the shared game; B still owns data on it.
        ScoutingLoader(db).load_team(_crawl(team_a, [other]))

    assert "g-shared" in _game_ids(db)
    warnings = _retire_warnings(caplog)
    assert len(warnings) == 1 and "another team's data" in warnings[0]


def test_redirected_canonical_row_counts_as_vouched_for(
    db: sqlite3.Connection,
) -> None:
    """A cross-perspective redirect must not read as a missing game.

    Pins the load-bearing assumption behind the health-gate population: after a
    redirect the canonical row carries THIS perspective, so it is in the
    prior-loaded set, and its canonical id is added to the fresh set -- meaning
    it lands in ``prior & fresh`` and counts toward the floor ratio.

    The scenario is tuned so the assumption is DECISIVE rather than incidental:
    3 prior games, one of them a redirected canonical row, one genuinely gone.
    If the canonical row failed to count, the numerator would be 1 against a
    1.5 floor -- the removal would be refused and this test would fail. It also
    fails if the canonical row is itself misread as REMOVED and deleted.
    """
    team_a = _insert_team(db, _SLUG_A, _UUID_A, "Team A")
    team_b = _insert_team(db, _SLUG_B, _UUID_B, "Team B")

    # B loads the shared A-vs-B game FIRST, so A's own event redirects onto it.
    ScoutingLoader(db).load_team(
        _crawl(
            team_b,
            [_game("evt-b", start_ts="2026-05-01T18:00:00Z", opponent="Team A")],
            own_key=_SLUG_B,
        )
    )
    a_shared = _game("evt-a", start_ts="2026-05-01T18:00:00Z", opponent="Team B")
    keep = _game("g-keep", start_ts="2026-04-10T18:00:00Z", opponent="Opp One")
    gone = _game("g-gone", start_ts="2026-04-12T18:00:00Z", opponent="Opp Two")

    ScoutingLoader(db).load_team(_crawl(team_a, [keep, gone, a_shared]))
    # The redirect collapsed evt-a onto evt-b; A's prior set is the other three.
    prior_a = {
        r[0]
        for r in db.execute(
            "SELECT game_id FROM game_perspectives WHERE perspective_team_id = ?",
            (team_a,),
        )
    }
    assert prior_a == {"g-keep", "g-gone", "evt-b"}

    # Re-scout: g-gone is gone; the shared game is still there under A's own id.
    ScoutingLoader(db).load_team(_crawl(team_a, [keep, a_shared]))

    assert _game_ids(db) == {"g-keep", "evt-b"}


def test_unparseable_boxscore_does_not_authorize_a_retire(
    db: sqlite3.Connection,
) -> None:
    """A boxscore that 200s but fails to PARSE must not count as loaded.

    ``boxscores_complete`` exists to catch a game whose vouching went missing.
    Keying it on the crawler's FETCHED dict makes it blind to the case where the
    fetch succeeded and the parse did not: ``_load_boxscore_data`` early-returns
    on a non-dict payload or unidentifiable team keys, both BEFORE the redirect
    map is written at the dedup site.

    The hazard needs a canonical row vouched for ONLY through a redirect, so the
    fixture builds one: run 1 stores the game under ``evt-canonical``; run 2's
    schedule re-issues the same real game (same date, opponent, start time and
    score) under ``evt-fresh``, which normally redirects onto the canonical id.
    When ``evt-fresh``'s payload cannot be parsed, no redirect is recorded and
    the canonical row looks absent -- while a fetch-keyed guard still reads
    "complete". The three filler games keep the floor ratio satisfied, so the
    health gate does not refuse for an unrelated reason.
    """
    filler = [
        _game(f"g-f{i}", start_ts=f"2026-05-0{i}T18:00:00Z", opponent=f"Filler {i}")
        for i in (1, 2, 3)
    ]
    same_game = dict(
        start_ts="2026-04-10T18:00:00Z", opponent="Opp One", team_score=5, opp_score=3
    )
    team = _insert_team(db)

    ScoutingLoader(db).load_team(
        _crawl(team, [_game("evt-canonical", **same_game), *filler])
    )
    assert _game_ids(db) == {"evt-canonical", "g-f1", "g-f2", "g-f3"}
    _seed_child_surface(db, "evt-canonical", team)

    # Re-scout: same real game under a NEW event id, whose boxscore comes back
    # as an empty JSON object -- a well-formed 200 with no identifiable team
    # keys, so ``_detect_team_keys`` returns ``(None, None)`` and the load
    # early-returns before the redirect is recorded. (Verified: a payload with
    # unrecognised STRING keys does not early-return -- the first is taken as a
    # slug -- so it would not exercise this path.)
    crawl = _crawl(team, [_game("evt-fresh", **same_game), *filler])
    crawl.boxscores["evt-fresh"] = {}

    ScoutingLoader(db).load_team(crawl)

    assert "evt-canonical" in _game_ids(db), (
        "the canonical game was retired on the evidence of a boxscore that "
        "fetched but never parsed -- boxscores_complete tracked FETCH success"
    )
    # Its child surface is intact too; a retire would have taken all of it.
    assert _play_event_count(db, "evt-canonical") > 0
    for table in ("game_perspectives", *_PERSPECTIVE_CHILD_TABLES):
        assert db.execute(
            f"SELECT COUNT(*) FROM {table} WHERE game_id = 'evt-canonical'"  # noqa: S608
        ).fetchone()[0] > 0


def test_retire_is_scoped_to_the_crawled_season(db: sqlite3.Connection) -> None:
    """The prior-loaded set is season-scoped: another season's games are untouched.

    Two seasons of data for the same team: without the ``season_id`` predicate
    the 2025 games would be absent from the 2026 fresh schedule and mass-retired.
    """
    from src.db.reconcile_at_load import retire_absent_games

    team = _insert_team(db)
    _seed_four_games(db, team)
    # Re-file half of them under a different season, as a prior season's load.
    ensure_season_row(db, "2025")
    db.execute(
        "UPDATE games SET season_id = '2025' WHERE game_id IN ('g-2', 'g-3')"
    )
    db.commit()

    # An authoritative 2026 crawl that returns only g-0.
    result = retire_absent_games(
        db,
        team_id=team,
        season_id=_SEASON,
        fresh_game_ids={"g-0"},
        fetch_ok=True,
        # Explicit now that these are required -- a caller must state its health
        # inputs rather than inherit a permissive default on a hard-delete path.
        not_final_game_ids=(),
        boxscores_complete=True,
    )
    db.commit()

    assert result.retired_game_ids == ["g-1"]
    assert _game_ids(db) == {"g-0", "g-2", "g-3"}


# ---------------------------------------------------------------------------
# E-270-01: absolute retirement cap + stripped-perspective guard
# ---------------------------------------------------------------------------
# Two protections that interlock and are therefore tested together: the cap
# refuses a mass retire the 0.5 floor waves through, and the cap's EXEMPT set is
# the same decision as the loop's REFUSAL set -- so widening the refusal (the
# foreign-child branch) automatically widens the exemption and no deadlock opens.


def _seed_games(
    db: sqlite3.Connection, team: int, count: int, *, prefix: str = "g"
) -> list[dict]:
    """Load ``count`` completed games on distinct dates and return the array."""
    games = [
        _game(
            f"{prefix}-{i}",
            start_ts=f"2026-04-{10 + i:02d}T18:00:00Z",
            opponent=f"Opp {i}",
        )
        for i in range(count)
    ]
    ScoutingLoader(db).load_team(_crawl(team, games))
    assert len(_game_ids(db)) == count
    return games


def _insert_foreign_child_row(
    db: sqlite3.Connection, table: str, game_id: str, foreign_team_id: int
) -> None:
    """Attach ONE child stat row under a FOREIGN ``perspective_team_id``.

    The ``else: raise`` is load-bearing. This helper is parametrized over the
    ``_PERSPECTIVE_CHILD_TABLES`` constant, so a future SIXTH child table makes
    this fail loudly rather than silently leaving the new table's foreign rows
    unprotected -- the same guard-surface == delete-surface discipline the
    production check follows.
    """
    if table == "player_game_batting":
        db.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id, ab, h) "
            "VALUES (?, ?, ?, ?, 4, 2)",
            (game_id, _PLAYER, foreign_team_id, foreign_team_id),
        )
    elif table == "player_game_pitching":
        db.execute(
            "INSERT INTO player_game_pitching "
            "(game_id, player_id, team_id, perspective_team_id, ip_outs) "
            "VALUES (?, ?, ?, ?, 9)",
            (game_id, _PLAYER, foreign_team_id, foreign_team_id),
        )
    elif table == "plays":
        db.execute(
            """
            INSERT INTO plays (game_id, play_order, inning, half, season_id,
                               batting_team_id, perspective_team_id, batter_id,
                               outcome)
            VALUES (?, 99, 1, 'top', ?, ?, ?, ?, 'single')
            """,
            (game_id, _SEASON, foreign_team_id, foreign_team_id, _PLAYER),
        )
    elif table == "spray_charts":
        db.execute(
            """
            INSERT INTO spray_charts (game_id, player_id, team_id,
                                      perspective_team_id, chart_type,
                                      event_gc_id, season_id, x, y)
            VALUES (?, ?, ?, ?, 'offensive', ?, ?, 1.0, 2.0)
            """,
            (
                game_id, _PLAYER, foreign_team_id, foreign_team_id,
                f"foreign-evt-{game_id}", _SEASON,
            ),
        )
    elif table == "reconciliation_discrepancies":
        db.execute(
            """
            INSERT INTO reconciliation_discrepancies
                (game_id, run_id, perspective_team_id, team_id, player_id,
                 signal_name, category, status)
            VALUES (?, 'foreign-run', ?, ?, ?, 'so', 'batting', 'MATCH')
            """,
            (game_id, foreign_team_id, foreign_team_id, _PLAYER),
        )
    else:  # pragma: no cover -- fires only when a 6th child table appears
        raise AssertionError(
            f"unhandled perspective child table {table!r} -- extend this helper "
            "and confirm the production guard covers the new table too"
        )
    db.commit()


def test_cap_refuses_a_mass_retire_that_passes_the_floor(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-2/AC-7: >MAX_GAME_RETIREMENTS absences refuse where the floor would not.

    Sizing is deliberate: 8 prior games meeting a 5-game fresh array leaves
    ``comparable = 5`` against a floor of ``8 * 0.5 = 4``, so the health gate
    PASSES and every other guard is satisfied -- ``boxscores_complete`` holds
    (all five fresh games load), none of the three absences is
    cross-perspective protected. The ONLY thing that can refuse here is the cap.
    A fixture that also failed the floor would pass against a cap-less
    implementation and prove nothing.
    """
    team = _insert_team(db)
    games = _seed_games(db, team, 8)
    assert 5 >= 8 * FLOOR_RATIO, "fixture must PASS the floor, or it proves nothing"
    assert 8 - 5 > MAX_GAME_RETIREMENTS, "fixture must exceed the cap"

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ScoutingLoader(db).load_team(_crawl(team, games[:5]))

    assert _game_ids(db) == {f"g-{i}" for i in range(8)}, "the cap must refuse ALL"
    assert db.execute(
        "SELECT COUNT(DISTINCT game_id) FROM player_game_batting"
    ).fetchone()[0] == 8
    warnings = _retire_warnings(caplog)
    assert len(warnings) == 3, warnings
    assert all("REFUSED" in w for w in warnings)
    assert all(f"MAX_GAME_RETIREMENTS={MAX_GAME_RETIREMENTS}" in w for w in warnings)
    # The floor did NOT fire -- otherwise this test would pass without a cap.
    assert not any("not authoritative" in w for w in warnings), warnings


def test_absences_at_the_cap_still_retire(db: sqlite3.Connection) -> None:
    """AC-2 boundary: the cap is a ceiling, not a veto -- exactly N still retires.

    Same 8-game fixture as the refusal test above, dropping exactly
    ``MAX_GAME_RETIREMENTS``. Without this, a cap accidentally implemented as
    ``< MAX`` (or as a blanket refusal) would still pass the test above.
    """
    team = _insert_team(db)
    games = _seed_games(db, team, 8)

    keep = 8 - MAX_GAME_RETIREMENTS
    ScoutingLoader(db).load_team(_crawl(team, games[:keep]))

    assert _game_ids(db) == {f"g-{i}" for i in range(keep)}


def test_cap_excludes_cross_perspective_games_so_a_genuine_removal_retires(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-3: no permanent-refusal deadlock -- the cap counts ``absent - exempt``.

    The real-world population api-scout measured: ~4% of a team's stored game
    ids are absent from its own fresh array and are ALL cross-perspective twins,
    which this grain refuses-and-KEEPS, so they recur in ``absent`` forever. A
    cap over raw ``len(absent)`` would let two such games permanently
    false-refuse every genuine removal after them.

    The discrimination floor is mandatory and is asserted below: at least
    ``MAX_GAME_RETIREMENTS`` protected absences PLUS at least one genuine one, so
    raw ``len(absent)`` exceeds the cap (a raw-count implementation refuses the
    whole pass and fails here) while ``len(absent - exempt) == 1`` (the correct
    implementation retires the genuine removal).
    """
    team_a = _insert_team(db, _SLUG_A, _UUID_A, "Team A")
    team_b = _insert_team(db, _SLUG_B, _UUID_B, "Team B")

    keeps = [
        _game(f"g-keep-{i}", start_ts=f"2026-04-{10 + i:02d}T18:00:00Z",
              opponent=f"Opp {i}")
        for i in range(5)
    ]
    shared = [
        _game(f"g-shared-{i}", start_ts=f"2026-05-{10 + i:02d}T18:00:00Z",
              opponent=f"Shared Opp {i}")
        for i in range(MAX_GAME_RETIREMENTS)
    ]
    gone = _game("g-gone", start_ts="2026-06-01T18:00:00Z", opponent="Gone Opp")

    ScoutingLoader(db).load_team(_crawl(team_a, [*keeps, *shared, gone]))
    # B loads the SAME game rows, so each shared game carries TWO perspectives.
    ScoutingLoader(db).load_team(_crawl(team_b, shared, own_key=_SLUG_B))
    for game in shared:
        assert db.execute(
            "SELECT COUNT(*) FROM game_perspectives WHERE game_id = ?",
            (game["id"],),
        ).fetchone()[0] == 2

    prior = 5 + len(shared) + 1
    absent = len(shared) + 1
    assert len(shared) >= MAX_GAME_RETIREMENTS, "discrimination floor"
    assert absent > MAX_GAME_RETIREMENTS, "raw count must exceed the cap"
    assert prior - absent >= prior * FLOOR_RATIO, "fixture must pass the floor"

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        # A's fresh schedule drops the shared games AND the genuine removal.
        ScoutingLoader(db).load_team(_crawl(team_a, keeps))

    assert "g-gone" not in _game_ids(db), (
        "the genuine single-perspective removal was false-refused -- the cap "
        "counted cross-perspective-protected games it can never retire"
    )
    for game in shared:
        assert game["id"] in _game_ids(db)
    warnings = _retire_warnings(caplog)
    refusals = [w for w in warnings if "REFUSED" in w]
    assert len(refusals) == len(shared), warnings
    assert all("another team's data" in w for w in refusals)
    assert not any("MAX_GAME_RETIREMENTS" in w for w in warnings), warnings


def test_stripped_perspective_games_are_exempt_from_the_cap_too(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-4: exempt == refusal, pinned on the NEW foreign-child branch.

    Same deadlock shape as the test above, but the two protected games are
    protected ONLY by surviving foreign CHILD rows -- their foreign
    ``game_perspectives`` rows are stripped, so ``_other_perspectives`` returns
    empty for them. If the cap's exempt set knew only the old junction-row
    branch while the loop refuses on both, these two would count toward the cap,
    push the raw absent count over it, and permanently false-refuse the genuine
    removal. That drift is exactly what the ONE shared predicate prevents.
    """
    team_a = _insert_team(db, _SLUG_A, _UUID_A, "Team A")
    team_b = _insert_team(db, _SLUG_B, _UUID_B, "Team B")

    keeps = [
        _game(f"g-keep-{i}", start_ts=f"2026-04-{10 + i:02d}T18:00:00Z",
              opponent=f"Opp {i}")
        for i in range(5)
    ]
    stripped = [
        _game(f"g-stripped-{i}", start_ts=f"2026-05-{10 + i:02d}T18:00:00Z",
              opponent=f"Shared Opp {i}")
        for i in range(MAX_GAME_RETIREMENTS)
    ]
    gone = _game("g-gone", start_ts="2026-06-01T18:00:00Z", opponent="Gone Opp")

    ScoutingLoader(db).load_team(_crawl(team_a, [*keeps, *stripped, gone]))
    ScoutingLoader(db).load_team(_crawl(team_b, stripped, own_key=_SLUG_B))

    # Strip B's junction rows, leaving B's child stat rows behind -- the
    # IDEA-159 state: single-perspective to the old guard, still holding another
    # team's data in fact.
    for game in stripped:
        db.execute(
            "DELETE FROM game_perspectives WHERE game_id = ? "
            "AND perspective_team_id = ?",
            (game["id"], team_b),
        )
    db.commit()
    for game in stripped:
        assert db.execute(
            "SELECT COUNT(*) FROM game_perspectives WHERE game_id = ?",
            (game["id"],),
        ).fetchone()[0] == 1, "only THIS team's junction row may survive"
        assert db.execute(
            "SELECT COUNT(*) FROM player_game_batting WHERE game_id = ? "
            "AND perspective_team_id = ?",
            (game["id"], team_b),
        ).fetchone()[0] > 0, "the foreign CHILD rows must survive, or this is vacuous"

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ScoutingLoader(db).load_team(_crawl(team_a, keeps))

    assert "g-gone" not in _game_ids(db), (
        "the genuine removal was false-refused -- the cap counted games the "
        "loop refuses on the foreign-child branch"
    )
    for game in stripped:
        assert game["id"] in _game_ids(db)
    warnings = _retire_warnings(caplog)
    refusals = [w for w in warnings if "REFUSED" in w]
    assert len(refusals) == len(stripped), warnings
    assert all("child stat row(s) under another perspective" in w for w in refusals)
    assert not any("MAX_GAME_RETIREMENTS" in w for w in warnings), warnings


@pytest.mark.parametrize("table", _PERSPECTIVE_CHILD_TABLES)
def test_foreign_child_row_in_any_child_table_refuses_the_retire(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture, table: str
) -> None:
    """AC-5: a foreign row in ANY of the five child tables protects the game.

    Parametrized over the ``_PERSPECTIVE_CHILD_TABLES`` constant itself, which is
    the point: the production guard reads the SAME constant the whole-game delete
    loops, so guard surface and delete surface cannot drift. The
    ``reconciliation_discrepancies`` case is the one a hand-written four-table
    list would miss -- a game whose ONLY foreign footprint is a reconciliation
    row, hard-deleted along with another perspective's data.

    Here the game holds exactly ONE ``game_perspectives`` row (this team's), so
    ``_other_perspectives`` is empty and the old guard would wave it through.
    """
    team_a = _insert_team(db, _SLUG_A, _UUID_A, "Team A")
    team_b = _insert_team(db, _SLUG_B, _UUID_B, "Team B")
    games = _seed_games(db, team_a, 4)
    _insert_foreign_child_row(db, table, "g-3", team_b)

    assert db.execute(
        "SELECT COUNT(*) FROM game_perspectives WHERE game_id = 'g-3'"
    ).fetchone()[0] == 1, "the foreign JUNCTION row must be absent, or this is vacuous"

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ScoutingLoader(db).load_team(_crawl(team_a, games[:3]))

    assert "g-3" in _game_ids(db), f"a foreign {table} row did not protect the game"
    assert db.execute(
        f"SELECT COUNT(*) FROM {table} WHERE game_id = 'g-3' "  # noqa: S608
        "AND perspective_team_id = ?",
        (team_b,),
    ).fetchone()[0] > 0, "the other perspective's row was destroyed"
    # This team's own rows on the refused game survive too -- a refusal keeps
    # everything, it does not half-retire.
    assert db.execute(
        "SELECT COUNT(*) FROM player_game_batting WHERE game_id = 'g-3' "
        "AND perspective_team_id = ?",
        (team_a,),
    ).fetchone()[0] > 0
    warnings = _retire_warnings(caplog)
    assert len(warnings) == 1, warnings
    assert "REFUSED" in warnings[0]
    assert "child stat row(s) under another perspective" in warnings[0]


def test_protection_with_no_matching_reason_still_refuses(
    db: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ``else`` arm, FIRST-REFUSAL case: no prior ``reason`` to fall back on.

    The refusal gate calls ``_game_is_cross_perspective_protected`` and then
    re-checks the two branches only to NAME which fired. When the predicate says
    protected and neither named branch matches, the ``else`` supplies the
    message.

    Note what the missing arm would NOT cause: the game is still refused, since
    the ``continue`` closing the gate is unconditional and no delete is reachable
    from inside it. Here -- the game is the run's FIRST refusal, so ``reason`` is
    unbound -- dropping the ``else`` raises ``UnboundLocalError``. The companion
    ``test_unmatched_protection_does_not_inherit_a_previous_games_reason``
    covers the nastier variant, where ``reason`` IS bound from an earlier game
    and the WARN silently names the wrong cause.

    Two ways to reach the arm, both real:

    * A third protection branch is added to the predicate (which the shared-
      predicate design explicitly invites) before its reason string is written.
    * A live race, in a bounded window. Before this pass's first hard delete the
      connection has no open transaction (``load_payload`` commits per boxscore)
      and Python's ``sqlite3`` opens one only before DML, so the gate and the
      re-checks are separate bare SELECTs sharing no snapshot of the WAL file: a
      concurrent writer removing the foreign row in between leaves the gate
      saying protected and both re-checks saying no. After the first delete the
      loop reads inside a write transaction and the window is closed.

    The monkeypatch reproduces the OBSERVABLE state of both: predicate True over
    a DB that genuinely holds no foreign rows for the game.
    """
    team = _insert_team(db)
    games = _seed_games(db, team, 4)
    # Precondition: g-3 is genuinely UNPROTECTED -- one perspective, no foreign
    # child rows -- so nothing but the else arm can save it.
    assert db.execute(
        "SELECT COUNT(*) FROM game_perspectives WHERE game_id = 'g-3'"
    ).fetchone()[0] == 1
    for table in _PERSPECTIVE_CHILD_TABLES:
        assert db.execute(
            f"SELECT COUNT(*) FROM {table} WHERE game_id = 'g-3' "  # noqa: S608
            "AND perspective_team_id != ?",
            (team,),
        ).fetchone()[0] == 0

    monkeypatch.setattr(
        reconcile_at_load,
        "_game_is_cross_perspective_protected",
        lambda *_args, **_kwargs: True,
    )

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        result = retire_absent_games(
            db,
            team_id=team,
            season_id=_SEASON,
            fresh_game_ids={g["id"] for g in games[:3]},
            fetch_ok=True,
            not_final_game_ids=(),
            boxscores_complete=True,
        )

    assert result.retired_game_ids == []
    assert _game_ids(db) == {"g-0", "g-1", "g-2", "g-3"}
    reason = result.refusals["g-3"]
    assert "does not name" in reason
    assert "_game_is_cross_perspective_protected" in reason
    warnings = _retire_warnings(caplog)
    assert len(warnings) == 1, warnings
    assert "REFUSED" in warnings[0]


def test_unmatched_protection_does_not_inherit_a_previous_games_reason(
    db: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ``else`` arm, STALE-CARRYOVER case -- the one a survival-only test misses.

    ``reason`` is a function-scope local reused across loop iterations, so
    dropping the ``else`` does not just lose a message: on any game AFTER a
    refusal has already bound ``reason``, the unmatched game silently inherits
    the PREVIOUS game's text. The retire is refused either way, so a test
    asserting only survival passes against that bug. What it corrupts is the
    WARN -- the operator's sole signal for WHY a retire was refused (TN-4) --
    which would name a cause that belongs to a different game.

    The fixture makes the carryover observable, which requires ordering: the
    loop walks ``sorted(prior_ids)``, so ``x-shared`` (refused via the named
    ``_other_perspectives`` branch, binding ``reason``) precedes ``y-lonely``
    (protected only by the patched predicate, matching no named branch). The
    discriminating assertion is that ``y-lonely``'s reason is NOT ``x-shared``'s.
    """
    team_a = _insert_team(db, _SLUG_A, _UUID_A, "Team A")
    team_b = _insert_team(db, _SLUG_B, _UUID_B, "Team B")

    keeps = _seed_games(db, team_a, 4)
    shared = _game("x-shared", start_ts="2026-05-01T18:00:00Z", opponent="Shared Opp")
    lonely = _game("y-lonely", start_ts="2026-05-02T18:00:00Z", opponent="Lonely Opp")
    ScoutingLoader(db).load_team(_crawl(team_a, [*keeps, shared, lonely]))
    # Only x-shared gets a second perspective, so only IT matches a named branch.
    ScoutingLoader(db).load_team(_crawl(team_b, [shared], own_key=_SLUG_B))
    assert db.execute(
        "SELECT COUNT(*) FROM game_perspectives WHERE game_id = 'x-shared'"
    ).fetchone()[0] == 2
    assert db.execute(
        "SELECT COUNT(*) FROM game_perspectives WHERE game_id = 'y-lonely'"
    ).fetchone()[0] == 1
    assert sorted(["x-shared", "y-lonely"]) == ["x-shared", "y-lonely"], (
        "iteration order is sorted(prior_ids) -- the named-branch refusal must "
        "come FIRST or there is no bound reason to inherit"
    )

    monkeypatch.setattr(
        reconcile_at_load,
        "_game_is_cross_perspective_protected",
        lambda *_args, **_kwargs: True,
    )

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        result = retire_absent_games(
            db,
            team_id=team_a,
            season_id=_SEASON,
            fresh_game_ids={g["id"] for g in keeps},
            fetch_ok=True,
            not_final_game_ids=(),
            boxscores_complete=True,
        )

    assert result.retired_game_ids == []
    assert {"x-shared", "y-lonely"} <= _game_ids(db)

    shared_reason = result.refusals["x-shared"]
    lonely_reason = result.refusals["y-lonely"]
    assert "also loaded by perspective(s)" in shared_reason
    # THE discriminator: y-lonely must carry its OWN reason, not x-shared's.
    assert lonely_reason != shared_reason, (
        "the unmatched game inherited the previous game's refusal reason -- the "
        "WARN now names a cause belonging to a different game"
    )
    assert "also loaded by perspective(s)" not in lonely_reason
    assert "does not name" in lonely_reason
    assert "_game_is_cross_perspective_protected" in lonely_reason

    warnings = _retire_warnings(caplog)
    assert len(warnings) == 2, warnings
    assert all("REFUSED" in w for w in warnings)
    lonely_warns = [w for w in warnings if "y-lonely" in w]
    assert len(lonely_warns) == 1
    assert "also loaded by perspective(s)" not in lonely_warns[0]


def test_foreign_child_row_on_a_DIFFERENT_game_does_not_protect(
    db: sqlite3.Connection,
) -> None:
    """AC-5 scoping: the guard is per-game, not "does this DB hold foreign rows".

    An unscoped existence check (one missing ``game_id`` predicate) would read as
    protective for every game the moment ANY foreign child row exists anywhere,
    silently disabling the whole grain -- and it would pass every other test in
    this section, since those attach the foreign row to the absent game itself.
    Here the foreign row sits on a game that is still PRESENT, so the absent game
    must still retire.
    """
    team_a = _insert_team(db, _SLUG_A, _UUID_A, "Team A")
    team_b = _insert_team(db, _SLUG_B, _UUID_B, "Team B")
    games = _seed_games(db, team_a, 4)
    _insert_foreign_child_row(db, "player_game_batting", "g-0", team_b)

    ScoutingLoader(db).load_team(_crawl(team_a, games[:3]))

    assert _game_ids(db) == {"g-0", "g-1", "g-2"}, (
        "a foreign child row on an unrelated game blocked the retire -- the "
        "guard is not scoped to the game under consideration"
    )


def test_boxscores_incomplete_refuses_even_below_the_cap(
    db: sqlite3.Connection,
) -> None:
    """AC-6: compose direction -- ``boxscores_complete=False`` alone refuses.

    One absence, comfortably under the cap and over the floor, so the ONLY
    condition that can refuse is the boxscore-coverage signal. Pins that the two
    guards are ANDed rather than the cap replacing the existing one.
    """
    team = _insert_team(db)
    _seed_games(db, team, 4)

    result = retire_absent_games(
        db,
        team_id=team,
        season_id=_SEASON,
        fresh_game_ids={"g-0", "g-1", "g-2"},
        fetch_ok=True,
        not_final_game_ids=(),
        boxscores_complete=False,
    )

    assert result.retired_game_ids == []
    assert set(result.refusals) == {"g-3"}
    assert _game_ids(db) == {"g-0", "g-1", "g-2", "g-3"}


def test_cap_refuses_even_when_boxscores_are_complete(
    db: sqlite3.Connection,
) -> None:
    """AC-6: compose direction -- the cap alone refuses.

    The mirror of the test above: every other signal says go (fetch ok, floor
    cleared, boxscores complete, no cross-perspective protection) and the cap
    still refuses the whole pass.
    """
    team = _insert_team(db)
    _seed_games(db, team, 8)

    result = retire_absent_games(
        db,
        team_id=team,
        season_id=_SEASON,
        fresh_game_ids={f"g-{i}" for i in range(5)},
        fetch_ok=True,
        not_final_game_ids=(),
        boxscores_complete=True,
    )

    assert result.retired_game_ids == []
    assert len(result.refusals) == 3
    assert _game_ids(db) == {f"g-{i}" for i in range(8)}


def test_refusal_reasons_distinguish_the_three_whole_set_causes(
    db: sqlite3.Connection,
) -> None:
    """AC-7: an operator can tell WHICH gate refused from the WARN alone.

    Three passes over one untouched 8-game fixture (a refusal writes nothing, so
    they are order-independent). The cap constant appears in the cap case and
    ONLY there -- the whole point of the distinction, since the remedies differ:
    a floor refusal means "suspect the crawl", a boxscores refusal means "a game
    failed to load", a cap refusal means "that many games really vanished".
    """
    team = _insert_team(db)
    _seed_games(db, team, 8)

    def _refuse(fresh: set[str], *, boxscores_complete: bool) -> dict[str, str]:
        result = retire_absent_games(
            db,
            team_id=team,
            season_id=_SEASON,
            fresh_game_ids=fresh,
            fetch_ok=True,
            not_final_game_ids=(),
            boxscores_complete=boxscores_complete,
        )
        assert result.retired_game_ids == []
        assert result.refusals
        return result.refusals

    floor = _refuse({"g-0"}, boxscores_complete=True)
    incomplete = _refuse(
        {f"g-{i}" for i in range(7)}, boxscores_complete=False
    )
    capped = _refuse({f"g-{i}" for i in range(5)}, boxscores_complete=True)

    assert all("not authoritative" in r for r in floor.values())
    assert not any("MAX_GAME_RETIREMENTS" in r for r in floor.values())

    assert all("boxscores_complete=False" in r for r in incomplete.values())
    assert not any("MAX_GAME_RETIREMENTS" in r for r in incomplete.values())
    assert not any("not authoritative" in r for r in incomplete.values())

    assert all(
        f"MAX_GAME_RETIREMENTS={MAX_GAME_RETIREMENTS}" in r for r in capped.values()
    )
    assert all("retire-eligible absent count 3" in r for r in capped.values())
    assert not any("not authoritative" in r for r in capped.values())

    assert _game_ids(db) == {f"g-{i}" for i in range(8)}


def test_reconcile_failure_rolls_back_and_does_not_fail_the_load(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """Error path: a broken reconcile logs, rolls back, and keeps the load.

    The boxscore load is already committed per game, so a reconcile blowup must
    neither lose it nor leave a partial retire riding the caller's commit.
    """
    team = _insert_team(db)
    games = _seed_four_games(db, team)

    with patch(
        "src.db.reconcile_at_load.retire_absent_games",
        side_effect=sqlite3.OperationalError("boom"),
    ):
        with caplog.at_level(logging.ERROR):
            result = ScoutingLoader(db).load_team(_crawl(team, games[:1]))

    assert result.loaded > 0, "the boxscore load must still succeed"
    assert _game_ids(db) == {"g-0", "g-1", "g-2", "g-3"}, "nothing may be deleted"
    assert any(
        "Game-grain reconcile failed" in r.getMessage() for r in caplog.records
    )
