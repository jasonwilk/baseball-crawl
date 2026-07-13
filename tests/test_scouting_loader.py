"""Tests for src/gamechanger/loaders/scouting_loader.py (E-097-03, E-100-03).

Covers:
- AC-13: Roster upsert into players / team_rosters
- AC-13: Delegation to GameLoader.load_payload() for boxscore loading
- AC-13: Season aggregate computation (counting stat sums, rate stats NOT stored)
- AC-13: Idempotency (double-load produces no duplicates)
- AC-13: scouting_runs metadata (status, first_fetched / last_checked)
- AC-13: UUID opportunism (gc_uuid stub creation when discovered)
- AC-8: FK-safe stub player pattern

All tests use SQLite in-memory databases via tmp_path and drive the loader
through its in-memory ``load_team(crawl_result)`` entry point. No real network
calls.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

import pytest

from migrations.apply_migrations import run_migrations
from src.api.db import get_season_batting, get_season_pitching
from src.gamechanger.loaders.game_loader import GameSummaryEntry, _derive_game_date
from src.gamechanger.loaders.scouting_loader import ScoutingLoader
from src.gamechanger.types import TeamRef


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    """Apply all migrations and return an open connection."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@pytest.fixture()
def loader(db: sqlite3.Connection) -> ScoutingLoader:
    """Return a ScoutingLoader backed by the test database."""
    return ScoutingLoader(db)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Public ID slug used as the own_key in test boxscores (non-UUID alphanumeric).
_PUBLIC_ID = "opp-slug-abc123"
# GC UUID used as gc_uuid for the team row so GameLoader._ensure_team_row
# resolves back to the same INTEGER PK.
_GC_UUID = "aaaabbbb-cccc-dddd-eeee-ffff00000001"
# DB season_id (derived from team metadata: season_year=2025, no program).
_SEASON_ID = "2025"
_PLAYER_1 = "player-uuid-001"
_PLAYER_2 = "player-uuid-002"


def _insert_team(
    db: sqlite3.Connection,
    public_id: str = _PUBLIC_ID,
    gc_uuid: str = _GC_UUID,
    name: str = "Opp Team",
    season_year: int = 2025,
) -> int:
    """Insert a tracked team row and return its INTEGER PK."""
    cursor = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, public_id, is_active, season_year) "
        "VALUES (?, 'tracked', ?, ?, 0, ?)",
        (name, gc_uuid, public_id, season_year),
    )
    db.commit()
    return cursor.lastrowid


def _make_roster() -> list[dict]:
    """Return a minimal two-player roster payload."""
    return [
        {"id": _PLAYER_1, "first_name": "John", "last_name": "Doe", "number": "14"},
        {"id": _PLAYER_2, "first_name": "Jane", "last_name": "Smith", "number": "7"},
    ]


def _make_games(game_id: str) -> list[dict]:
    """Return a public games payload with one completed game."""
    return [
        {
            "id": game_id,
            "game_status": "completed",
            "home_away": "home",
            "start_ts": "2025-04-10T18:00:00Z",
            "score": {"team": 5, "opponent_team": 3},
        }
    ]


_OPP_UUID = "11112222-3333-4444-5555-aaaabbbbcccc"


def _make_boxscore(
    own_key: str,
    opp_key: str = _OPP_UUID,
    player_id: str = _PLAYER_1,
) -> dict:
    """Return a minimal boxscore payload with one batting player."""
    return {
        own_key: {
            "players": [
                {"id": player_id, "first_name": "John", "last_name": "Doe", "number": "14"}
            ],
            "groups": [
                {
                    "category": "lineup",
                    "stats": [
                        {
                            "player_id": player_id,
                            "stats": {"AB": 3, "R": 1, "H": 1, "RBI": 1, "BB": 0, "SO": 1},
                        }
                    ],
                    "extra": [
                        {"stat_name": "2B", "stats": [{"player_id": player_id, "value": 1}]},
                    ],
                }
            ],
        },
        opp_key: {
            "players": [],
            "groups": [],
        },
    }


def _crawl_result(
    team_id: int,
    *,
    roster: list[dict] | None = None,
    games: list[dict] | None = None,
    boxscores: dict[str, dict] | None = None,
) -> SimpleNamespace:
    """Build a ``ScoutingCrawlResult``-shaped payload for ``load_team``."""
    return SimpleNamespace(
        team_id=team_id,
        roster=_make_roster() if roster is None else roster,
        games=games if games is not None else [],
        boxscores=boxscores if boxscores is not None else {},
    )


def _one_game_crawl(
    team_id: int,
    game_id: str,
    *,
    opp_key: str = _OPP_UUID,
    player_id: str = _PLAYER_1,
) -> SimpleNamespace:
    """Crawl result with the standard roster, one completed game, one boxscore."""
    return _crawl_result(
        team_id,
        games=_make_games(game_id),
        boxscores={game_id: _make_boxscore(_PUBLIC_ID, opp_key=opp_key, player_id=player_id)},
    )


# ---------------------------------------------------------------------------
# AC-13: Roster upsert
# ---------------------------------------------------------------------------


def test_roster_upserted_into_players(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """Roster players are upserted into the players table."""
    team_pk = _insert_team(db)

    loader.load_team(_crawl_result(team_pk))

    rows = db.execute("SELECT player_id FROM players").fetchall()
    player_ids = {r[0] for r in rows}
    assert _PLAYER_1 in player_ids
    assert _PLAYER_2 in player_ids


def test_seasons_row_created_automatically(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """The seasons row is created before any FK-dependent insert.

    Ported from ``test_game_loader.py`` in E-256-01: ``GameLoader.load_all``
    used to call ``ensure_season_row``; on the surviving in-memory path that
    responsibility lives in ``ScoutingLoader._load_team_core``.
    """
    team_pk = _insert_team(db)
    assert db.execute("SELECT COUNT(*) FROM seasons;").fetchone()[0] == 0

    loader.load_team(_crawl_result(team_pk))

    row = db.execute(
        "SELECT season_id FROM seasons WHERE season_id = ?;", (_SEASON_ID,)
    ).fetchone()
    assert row is not None


def test_boxscore_without_games_entry_is_skipped(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """A boxscore whose game_stream_id has no games entry increments ``skipped``.

    Ported from ``test_game_loader.py::test_load_result_skipped_when_no_summary``
    in E-256-01: the summary-lookup miss used to live in ``GameLoader.load_all``;
    it now lives in ``ScoutingLoader._load_boxscores``.
    """
    team_pk = _insert_team(db)

    result = loader.load_team(
        _crawl_result(
            team_pk,
            games=[],  # no games entry for the boxscore below
            boxscores={"orphan-game": _make_boxscore(_PUBLIC_ID)},
        )
    )

    assert result.skipped == 1
    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0


def test_roster_upserted_into_team_rosters(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """Roster players are linked in team_rosters with correct season and jersey."""
    team_pk = _insert_team(db)

    loader.load_team(_crawl_result(team_pk))

    rows = db.execute(
        "SELECT player_id, jersey_number FROM team_rosters WHERE team_id = ? AND season_id = ?",
        (team_pk, _SEASON_ID),
    ).fetchall()
    assert len(rows) == 2
    jerseys = {r[0]: r[1] for r in rows}
    assert jerseys.get(_PLAYER_1) == "14"
    assert jerseys.get(_PLAYER_2) == "7"


# ---------------------------------------------------------------------------
# AC-13: Delegation to GameLoader.load_payload()
# ---------------------------------------------------------------------------


def test_boxscore_loading_delegates_to_game_loader(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """ScoutingLoader delegates boxscore loading to GameLoader.load_payload()."""
    team_pk = _insert_team(db)
    game_id = "game-stream-001"
    boxscore = _make_boxscore(_PUBLIC_ID)
    crawl_result = _crawl_result(
        team_pk, games=_make_games(game_id), boxscores={game_id: boxscore},
    )

    with patch("src.gamechanger.loaders.scouting_loader.GameLoader") as MockGameLoader:
        mock_gl = MagicMock()
        from src.gamechanger.loaders import LoadResult
        mock_gl.load_payload.return_value = LoadResult(loaded=2)
        MockGameLoader.return_value = mock_gl

        loader.load_team(crawl_result)

        expected_team_ref = TeamRef(id=team_pk, gc_uuid=_GC_UUID, public_id=_PUBLIC_ID)
        MockGameLoader.assert_called_once_with(
            db=loader._db,
            owned_team_ref=expected_team_ref,
            created_team_ids=loader._created_team_ids,
            # E-261-03a: ScoutingLoader now precomputes the per-(date, opponent)
            # schedule count and threads it into GameLoader. Its CONTENT (the
            # count aggregate) is asserted directly by the
            # test_build_schedule_counts_* tests below; here we only assert the
            # kwarg is passed through.
            schedule_counts=ANY,
        )
        mock_gl.load_payload.assert_called_once()
        # First arg should be the in-memory boxscore payload.
        call_args = mock_gl.load_payload.call_args
        assert call_args.args[0] == boxscore
        # Second arg should be a GameSummaryEntry.
        summary = call_args.args[1]
        assert isinstance(summary, GameSummaryEntry)
        assert summary.event_id == game_id


# ---------------------------------------------------------------------------
# E-261-03a: _build_schedule_counts (the doubleheader discriminator producer)
# ---------------------------------------------------------------------------
# The tolerant same-game signal is only as safe as the count aggregate that
# feeds it: it MUST emit count==2 for a real doubleheader (else the guard would
# fire on len(rows)==1 and SILENTLY COLLAPSE a real game -- the asymmetric
# pitcher-rest/innings-limit hazard TN-4 names). These tests exercise the
# producer directly (the load-path tests set loader._schedule_counts by hand).


def _sched_summary(
    stream_id: str,
    *,
    ts: str = "2025-05-10T14:00:00.000Z",
    tz: str | None = "America/Chicago",
) -> GameSummaryEntry:
    """A minimal GameSummaryEntry for _build_schedule_counts key derivation."""
    return GameSummaryEntry(
        event_id=stream_id,
        game_stream_id=stream_id,
        home_away="home",
        owning_team_score=5,
        opponent_team_score=2,
        opponent_id="",
        last_scoring_update=ts,
        start_time=ts,
        timezone=tz,
    )


def test_build_schedule_counts_doubleheader_counts_two(
    loader: ScoutingLoader,
) -> None:
    """Two same-date same-opponent summaries aggregate to count 2 (increment,
    not overwrite) -- the real-doubleheader signal the guard must NOT collapse."""
    games_index = {
        "g1": _sched_summary("g1", ts="2025-05-10T18:00:00.000Z"),
        "g2": _sched_summary("g2", ts="2025-05-10T22:00:00.000Z"),
    }
    opponent_name_index = {"g1": "Rival High", "g2": "Rival High"}

    counts = loader._build_schedule_counts(games_index, opponent_name_index)

    date_key = _derive_game_date(games_index["g1"])
    assert _derive_game_date(games_index["g2"]) == date_key  # same local date
    assert counts == {(date_key, "Rival High"): 2}


def test_build_schedule_counts_single_game_counts_one(
    loader: ScoutingLoader,
) -> None:
    """A lone game vs an opponent aggregates to count 1."""
    games_index = {"g1": _sched_summary("g1")}
    opponent_name_index = {"g1": "Rival High"}

    counts = loader._build_schedule_counts(games_index, opponent_name_index)

    assert counts == {(_derive_game_date(games_index["g1"]), "Rival High"): 1}


def test_build_schedule_counts_excludes_none_opponent(
    loader: ScoutingLoader,
) -> None:
    """A game with NO resolvable opponent name is EXCLUDED (AC-6 fail-safe on the
    producer side: the loader then gets a None count and declines the signal). A
    None-opponent game on a DIFFERENT date does not poison an unrelated resolved
    date -- only its own date is treated as ambiguous."""
    games_index = {
        "g1": _sched_summary("g1", ts="2025-05-10T14:00:00.000Z"),  # vs X, 10th
        "g2": _sched_summary("g2", ts="2025-05-12T14:00:00.000Z"),  # None opp, 12th
    }
    opponent_name_index = {"g1": "Rival High"}  # g2 absent -> None opponent

    counts = loader._build_schedule_counts(games_index, opponent_name_index)

    assert counts == {(_derive_game_date(games_index["g1"]), "Rival High"): 1}
    assert all(key[1] is not None for key in counts)  # no None-opponent key


def test_build_schedule_counts_ambiguous_date_fails_closed(
    loader: ScoutingLoader,
) -> None:
    """Codex P1 regression: a real doubleheader vs X on date D where ONE sibling
    summary lost its opponent name must NOT undercount (D, X) to 1 -- that would
    let the tolerant guard silently collapse the OTHER sibling into a lone
    cross-perspective candidate (deleted game data + masked pitcher-rest
    violation, the asymmetric hazard TN-4 names). The whole date is AMBIGUOUS and
    emits NO count, so the surviving sibling's lookup misses -> the loader
    declines (fails CLOSED) instead of merging on the wrong count."""
    games_index = {
        "g1": _sched_summary("g1", ts="2025-05-10T18:00:00.000Z"),  # vs X @ 6:00 PM
        "g2": _sched_summary("g2", ts="2025-05-10T22:00:00.000Z"),  # vs X but name lost
    }
    # g2's opponent name is missing -> the 2025-05-10 date is ambiguous.
    opponent_name_index = {"g1": "Rival High"}

    counts = loader._build_schedule_counts(games_index, opponent_name_index)

    date_key = _derive_game_date(games_index["g1"])
    assert _derive_game_date(games_index["g2"]) == date_key  # same local date
    # No undercounted (date, X)=1 -- the ambiguous date emits nothing (fail closed).
    assert (date_key, "Rival High") not in counts
    assert counts == {}


def test_build_schedule_counts_date_key_uses_shared_seam(
    loader: ScoutingLoader,
) -> None:
    """The produced date key equals ``_derive_game_date(summary)`` -- the SAME
    seam ``_load_boxscore_data`` uses, so the lookup cannot key-miss. Uses a
    late-evening instant that rolls to the NEXT UTC day to prove the key is the
    venue-LOCAL date, not a UTC slice (finding E(b))."""
    # 02:30Z on 2025-05-11 = 21:30 CDT on 2025-05-10 -> local date 2025-05-10.
    summary = _sched_summary("g1", ts="2025-05-11T02:30:00.000Z")
    games_index = {"g1": summary}
    opponent_name_index = {"g1": "Rival High"}

    counts = loader._build_schedule_counts(games_index, opponent_name_index)

    expected_date = _derive_game_date(summary)
    assert expected_date == "2025-05-10"  # venue-local, NOT the UTC "2025-05-11"
    assert list(counts.keys()) == [(expected_date, "Rival High")]


# ---------------------------------------------------------------------------
# AC-13: Season aggregate computation
# ---------------------------------------------------------------------------


def test_season_aggregates_computed_from_game_rows(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """Season batting aggregates are computed from player_game_batting rows."""
    team_pk = _insert_team(db)
    game_id = "game-stream-agg-001"

    loader.load_team(_one_game_crawl(team_pk, game_id))

    # Verify player_game_batting row exists.
    game_row = db.execute(
        "SELECT ab, h, doubles FROM player_game_batting WHERE player_id = ? AND game_id = ?",
        (_PLAYER_1, game_id),
    ).fetchone()
    assert game_row is not None, "Expected a player_game_batting row"
    assert game_row[0] == 3  # ab
    assert game_row[1] == 1  # h
    assert game_row[2] == 1  # doubles

    # Season line is derived at query time from the per-game rows (E-259), so
    # verify the perspective-scoped per-game SUM the reader would return.
    season_row = db.execute(
        "SELECT SUM(pgb.ab), SUM(pgb.h), SUM(pgb.doubles) FROM player_game_batting pgb "
        "JOIN games g ON g.game_id = pgb.game_id "
        "WHERE pgb.player_id = ? AND pgb.team_id = ? AND g.season_id = ? "
        "AND pgb.perspective_team_id = ?",
        (_PLAYER_1, team_pk, _SEASON_ID, team_pk),
    ).fetchone()
    assert season_row == (3, 1, 1)


def test_rate_stats_not_in_season_batting_contract(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """Season batting exposes counting stats only; rate stats (avg/obp) are
    computed at display time, never part of the query-time aggregate contract.

    Post-E-259 the stored ``player_season_batting`` table is gone, so this
    guards the surviving surface: the query-time reader ``get_season_batting``
    must return real rows whose keys carry no precomputed avg/obp.
    """
    team_pk = _insert_team(db)
    game_id = "game-stream-rate-001"
    opp_uuid = "22223333-4444-5555-6666-aaaabbbbcccc"

    loader.load_team(_one_game_crawl(team_pk, game_id, opp_key=opp_uuid))

    db.row_factory = sqlite3.Row  # get_season_batting returns dict(row)
    rows = get_season_batting(db, team_pk, _SEASON_ID)
    assert rows, "expected at least one season batting row"
    keys = set(rows[0].keys())
    # Rate stats are display-derived, not part of the aggregate contract.
    assert "avg" not in keys
    assert "obp" not in keys


# ---------------------------------------------------------------------------
# AC-13: Idempotency
# ---------------------------------------------------------------------------


def test_double_load_no_duplicates(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """Loading the same data twice produces no duplicate rows in any table."""
    team_pk = _insert_team(db)
    game_id = "game-stream-dup-001"
    opp_uuid = "33334444-5555-6666-7777-aaaabbbbcccc"

    loader.load_team(_one_game_crawl(team_pk, game_id, opp_key=opp_uuid))
    loader.load_team(_one_game_crawl(team_pk, game_id, opp_key=opp_uuid))

    player_count = db.execute("SELECT COUNT(*) FROM players WHERE player_id = ?", (_PLAYER_1,)).fetchone()[0]
    assert player_count == 1

    roster_count = db.execute(
        "SELECT COUNT(*) FROM team_rosters WHERE player_id = ? AND team_id = ? AND season_id = ?",
        (_PLAYER_1, team_pk, _SEASON_ID),
    ).fetchone()[0]
    assert roster_count == 1

    # E-259: idempotency now applies at the per-game grain (season aggregates are
    # derived at query time, not stored), so the double-load produces exactly one
    # per-game row.
    game_batting_count = db.execute(
        "SELECT COUNT(*) FROM player_game_batting WHERE player_id = ? AND game_id = ?",
        (_PLAYER_1, game_id),
    ).fetchone()[0]
    assert game_batting_count == 1


# ---------------------------------------------------------------------------
# AC-8: FK-safe stub player pattern
# ---------------------------------------------------------------------------


def test_stub_player_created_for_unknown_player_in_boxscore(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """Unknown player IDs in boxscores get stub rows (first_name='Unknown')."""
    team_pk = _insert_team(db)
    game_id = "game-stream-stub-001"
    opp_uuid = "44445555-6666-7777-8888-aaaabbbbcccc"
    unknown_player = "unknown-player-uuid-xyz"

    games = [
        {
            "id": game_id,
            "game_status": "completed",
            "start_ts": "2025-04-10T18:00:00Z",
            "score": {"team": 3, "opponent_team": 1},
        }
    ]
    boxscore = {
        _PUBLIC_ID: {
            "players": [],
            "groups": [
                {
                    "category": "lineup",
                    "stats": [
                        {
                            "player_id": unknown_player,
                            "stats": {"AB": 4, "R": 1, "H": 2, "RBI": 0, "BB": 1, "SO": 0},
                        }
                    ],
                    "extra": [],
                }
            ],
        },
        opp_uuid: {"players": [], "groups": []},
    }

    # Empty roster -- test stub creation from the boxscore only.
    loader.load_team(
        _crawl_result(team_pk, roster=[], games=games, boxscores={game_id: boxscore})
    )

    row = db.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?", (unknown_player,)
    ).fetchone()
    assert row is not None, "Stub player row should have been created"
    assert row[0] == "Unknown"
    assert row[1] == "Unknown"


# ---------------------------------------------------------------------------
# AC-13: Team row creation without UUID contamination (E-211)
# ---------------------------------------------------------------------------


def test_loader_creates_opponent_row_without_gc_uuid(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """E-211: When an opponent UUID key appears in a boxscore, a teams row is created
    with gc_uuid=NULL (not the boxscore key)."""
    team_pk = _insert_team(db)
    game_id = "game-stream-uuid-opp-001"
    uuid_key = "55556666-7777-8888-aaaa-bbbbcccc0005"

    loader.load_team(_one_game_crawl(team_pk, game_id, opp_key=uuid_key))

    # No team row should have gc_uuid == uuid_key (UUID contamination fix).
    row_by_uuid = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (uuid_key,)).fetchone()
    assert row_by_uuid is None, (
        f"No team should have gc_uuid={uuid_key} -- opponent-perspective UUIDs must not be stored"
    )
    # But the opponent row should exist by name (the UUID string as name fallback).
    row_by_name = db.execute(
        "SELECT id, gc_uuid FROM teams WHERE name = ? AND membership_type = 'tracked'",
        (uuid_key,),
    ).fetchone()
    assert row_by_name is not None, "Opponent row should exist with UUID as name fallback"
    assert row_by_name[1] is None, "gc_uuid must be NULL"


def test_loader_uuid_opportunism_does_not_create_duplicate(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """If a teams row already has gc_uuid set, no duplicate is created."""
    team_pk = _insert_team(db)
    game_id = "game-stream-uuid-opp-002"
    uuid_key = "66667777-8888-9999-aaaa-bbbbcccc0006"

    # Pre-insert a stub row with gc_uuid = uuid_key.
    db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) VALUES (?, 'tracked', ?, 0)",
        ("PreExistingOpp", uuid_key),
    )
    db.commit()

    loader.load_team(_one_game_crawl(team_pk, game_id, opp_key=uuid_key))

    # Only one row with that gc_uuid should exist.
    count = db.execute(
        "SELECT COUNT(*) FROM teams WHERE gc_uuid = ?", (uuid_key,)
    ).fetchone()[0]
    assert count == 1, f"Expected exactly 1 row for gc_uuid={uuid_key}, got {count}"


# ---------------------------------------------------------------------------
# E-098-01: Multi-season aggregate isolation (regression test)
# ---------------------------------------------------------------------------


def test_aggregate_isolated_per_season(
    db: sqlite3.Connection
) -> None:
    """Aggregates for one season do not include game rows from another season.

    Sets up two seasons ("2025" and "2026") with different stats
    for the same player, then verifies that running aggregation for "2026"
    produces only "2026" data in player_season_batting and
    player_season_pitching.
    """
    season_a = "2025"
    season_b = "2026"
    game_a = "game-season-a-001"
    game_b = "game-season-b-001"

    # -- Seed required FK rows --------------------------------------------------
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) VALUES (?, ?, ?)",
        (season_a, "Spring 2025", 2025),
    )
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) VALUES (?, ?, ?)",
        (season_b, "Spring 2026", 2026),
    )
    # Own team (member) and opponent team (tracked).
    own_pk = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) VALUES (?, 'member', ?, 1)",
        ("Own Team", "ownteam-gc-uuid-0001"),
    ).lastrowid
    opp_pk = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) VALUES (?, 'tracked', ?, 0)",
        ("Opp Team", "oppteam-gc-uuid-0002"),
    ).lastrowid
    db.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (_PLAYER_1, "John", "Doe"),
    )
    db.execute(
        "INSERT OR IGNORE INTO games (game_id, season_id, game_date, home_team_id, away_team_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (game_a, season_a, "2025-04-10", own_pk, opp_pk),
    )
    db.execute(
        "INSERT OR IGNORE INTO games (game_id, season_id, game_date, home_team_id, away_team_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (game_b, season_b, "2026-04-10", own_pk, opp_pk),
    )

    # -- 2025 batting: 5 AB, 2 H; pitching: 9 ip_outs, 3 er ------------------
    db.execute(
        "INSERT INTO player_game_batting "
        "(game_id, player_id, team_id, perspective_team_id, ab, h, doubles, triples, hr, rbi, bb, so, sb) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_a, _PLAYER_1, own_pk, own_pk, 5, 2, 0, 0, 0, 0, 0, 1, 0),
    )
    db.execute(
        "INSERT INTO player_game_pitching "
        "(game_id, player_id, team_id, perspective_team_id, ip_outs, h, er, bb, so) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_a, _PLAYER_1, own_pk, own_pk, 9, 3, 3, 1, 4),
    )

    # -- 2026 batting: 4 AB, 3 H; pitching: 6 ip_outs, 1 er ------------------
    db.execute(
        "INSERT INTO player_game_batting "
        "(game_id, player_id, team_id, perspective_team_id, ab, h, doubles, triples, hr, rbi, bb, so, sb) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_b, _PLAYER_1, own_pk, own_pk, 4, 3, 1, 0, 0, 0, 0, 0, 0),
    )
    db.execute(
        "INSERT INTO player_game_pitching "
        "(game_id, player_id, team_id, perspective_team_id, ip_outs, h, er, bb, so) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_b, _PLAYER_1, own_pk, own_pk, 6, 2, 1, 0, 3),
    )
    db.commit()

    # E-259: the season line is derived at query time; the reader filters by
    # season_id, so the 2026 query must not absorb the 2025 game rows (and vice
    # versa). This proves per-season isolation via the reader's scope.
    db.row_factory = sqlite3.Row

    bat_2026 = {r["player_id"]: r for r in get_season_batting(db, own_pk, season_b)}
    assert bat_2026[_PLAYER_1]["ab"] == 4, "2026 batting must exclude 2025 rows"
    assert bat_2026[_PLAYER_1]["h"] == 3
    assert bat_2026[_PLAYER_1]["doubles"] == 1
    pit_2026 = {r["player_id"]: r for r in get_season_pitching(db, own_pk, season_b)}
    assert pit_2026[_PLAYER_1]["ip_outs"] == 6, "2026 pitching must exclude 2025 rows"
    assert pit_2026[_PLAYER_1]["er"] == 1

    # The 2025 reader returns its OWN season's data (5 AB / 9 ip_outs), confirming
    # the two seasons are scoped independently.
    bat_2025 = {r["player_id"]: r for r in get_season_batting(db, own_pk, season_a)}
    assert bat_2025[_PLAYER_1]["ab"] == 5
    pit_2025 = {r["player_id"]: r for r in get_season_pitching(db, own_pk, season_a)}
    assert pit_2025[_PLAYER_1]["ip_outs"] == 9


def test_aggregate_isolated_per_team(
    db: sqlite3.Connection
) -> None:
    """Aggregates for one team do not include game rows from another team.

    Sets up two teams (own and opponent) with different players and stats in
    the same game/season, then verifies that running aggregation for the own
    team only includes the own team's player data.

    Verification: removing the ``WHERE team_id = ?`` clause from the aggregate
    query would cause own_team's aggregate to absorb opp_team's stats,
    producing ab=8 (3+5) instead of ab=3, and ip_outs=12 (4+8) instead of 4.
    """
    season_id = "2025-spring-team-iso"
    game_id = "game-team-iso-001"

    # -- Seed required FK rows -------------------------------------------------
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) "
        "VALUES (?, ?, ?)",
        (season_id, "Spring 2025 Iso", 2025),
    )
    own_pk = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) "
        "VALUES (?, 'member', ?, 1)",
        ("Own Team Iso", "ownteam-iso-uuid-0001"),
    ).lastrowid
    opp_pk = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) "
        "VALUES (?, 'tracked', ?, 0)",
        ("Opp Team Iso", "oppteam-iso-uuid-0002"),
    ).lastrowid
    db.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES (?, ?, ?)",
        (_PLAYER_1, "John", "Doe"),
    )
    db.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES (?, ?, ?)",
        (_PLAYER_2, "Jane", "Smith"),
    )
    db.execute(
        "INSERT OR IGNORE INTO games "
        "(game_id, season_id, game_date, home_team_id, away_team_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (game_id, season_id, "2025-04-15", own_pk, opp_pk),
    )

    # -- Own team (_PLAYER_1): ab=3, h=2; ip_outs=4, er=1 ---------------------
    db.execute(
        "INSERT INTO player_game_batting "
        "(game_id, player_id, team_id, perspective_team_id, ab, h, doubles, triples, hr, rbi, bb, so, sb) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_id, _PLAYER_1, own_pk, own_pk, 3, 2, 0, 0, 0, 0, 0, 0, 0),
    )
    db.execute(
        "INSERT INTO player_game_pitching "
        "(game_id, player_id, team_id, perspective_team_id, ip_outs, h, er, bb, so) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_id, _PLAYER_1, own_pk, own_pk, 4, 1, 1, 0, 2),
    )

    # -- Opp team (_PLAYER_2): ab=5, h=1; ip_outs=8, er=3 --------------------
    db.execute(
        "INSERT INTO player_game_batting "
        "(game_id, player_id, team_id, perspective_team_id, ab, h, doubles, triples, hr, rbi, bb, so, sb) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_id, _PLAYER_2, opp_pk, opp_pk, 5, 1, 0, 0, 0, 0, 0, 2, 0),
    )
    db.execute(
        "INSERT INTO player_game_pitching "
        "(game_id, player_id, team_id, perspective_team_id, ip_outs, h, er, bb, so) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_id, _PLAYER_2, opp_pk, opp_pk, 8, 4, 3, 1, 5),
    )
    db.commit()

    # E-259: the season line is derived at query time; the reader filters by
    # team_id, so the own-team query must reflect _PLAYER_1 only and never absorb
    # the opponent's (_PLAYER_2, team=opp_pk) rows.
    db.row_factory = sqlite3.Row

    bat = {r["player_id"]: r for r in get_season_batting(db, own_pk, season_id)}
    assert bat[_PLAYER_1]["ab"] == 3, "own-team batting must exclude opp rows"
    assert bat[_PLAYER_1]["h"] == 2
    assert _PLAYER_2 not in bat, "opp player leaked into own team's reader output"

    pit = {r["player_id"]: r for r in get_season_pitching(db, own_pk, season_id)}
    assert pit[_PLAYER_1]["ip_outs"] == 4, "own-team pitching must exclude opp rows"
    assert pit[_PLAYER_1]["er"] == 1
    assert _PLAYER_2 not in pit, "opp pitcher leaked into own team's reader output"


# ---------------------------------------------------------------------------
# E-117-04: Expanded aggregate columns (AC-4, AC-5, AC-6)
# ---------------------------------------------------------------------------


def _seed_fk_rows(
    db: sqlite3.Connection,
    season_id: str,
    game_id: str,
) -> tuple[int, int]:
    """Seed seasons, teams, players, and a game row; return (team_pk, opp_pk)."""
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) VALUES (?, ?, ?)",
        (season_id, season_id, 2025),
    )
    team_pk = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) VALUES (?, 'tracked', ?, 0)",
        (f"team-{season_id}", f"gc-uuid-{season_id}"),
    ).lastrowid
    opp_pk = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) VALUES (?, 'tracked', ?, 0)",
        (f"opp-{season_id}", f"gc-uuid-opp-{season_id}"),
    ).lastrowid
    db.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, 'Test', 'Player')",
        (_PLAYER_1,),
    )
    db.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, 'Test2', 'Player2')",
        (_PLAYER_2,),
    )
    db.execute(
        "INSERT OR IGNORE INTO games (game_id, season_id, game_date, home_team_id, away_team_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (game_id, season_id, "2025-04-20", team_pk, opp_pk),
    )
    db.commit()
    return team_pk, opp_pk


# ---------------------------------------------------------------------------
# E-132-01: Opponent name resolution (AC-2, AC-3, AC-4, AC-5)
# ---------------------------------------------------------------------------

_OPP_NAME_SCOUTING = "Kearney Mavericks 14U"


def _make_games_with_opponent_name(
    game_id: str,
    opponent_name: str = _OPP_NAME_SCOUTING,
) -> list[dict]:
    """Return a games payload with opponent_team.name populated."""
    return [
        {
            "id": game_id,
            "game_status": "completed",
            "home_away": "home",
            "start_ts": "2025-04-10T18:00:00Z",
            "score": {"team": 5, "opponent_team": 3},
            "opponent_team": {"name": opponent_name},
        }
    ]


def test_build_opponent_name_index_reads_opponent_team_name(
    loader: ScoutingLoader,
) -> None:
    """_build_opponent_name_index_from_data() extracts opponent_team.name per game."""
    game_id = "game-stream-name-001"
    games = _make_games_with_opponent_name(game_id, "Nighthawks Navy")

    index = loader._build_opponent_name_index_from_data(games)

    assert index.get(game_id) == "Nighthawks Navy"


def test_build_opponent_name_index_empty_games_returns_empty(
    loader: ScoutingLoader,
) -> None:
    """An empty games payload yields an empty opponent-name index."""
    assert loader._build_opponent_name_index_from_data([]) == {}


def test_build_opponent_name_index_missing_opponent_team_field(
    loader: ScoutingLoader,
) -> None:
    """Games without opponent_team.name are skipped gracefully (no KeyError)."""
    games = [{"id": "game-no-name", "game_status": "completed"}]

    index = loader._build_opponent_name_index_from_data(games)

    assert index == {}


def test_load_team_creates_opponent_row_with_name_from_games(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """AC-2: load_team() creates opponent team row with the name from the games payload.

    E-211: Opponent row is created with gc_uuid=NULL; looked up by name.
    """
    team_pk = _insert_team(db)
    game_id = "game-stream-opp-name-001"
    opp_uuid = "aa11bb22-cc33-dd44-ee55-ff66aabb0099"

    loader.load_team(
        _crawl_result(
            team_pk,
            games=_make_games_with_opponent_name(game_id),
            boxscores={game_id: _make_boxscore(_PUBLIC_ID, opp_key=opp_uuid)},
        )
    )

    # E-211: gc_uuid should NOT be set for opponent rows.
    row_by_uuid = db.execute("SELECT name FROM teams WHERE gc_uuid = ?", (opp_uuid,)).fetchone()
    assert row_by_uuid is None, "Opponent row must not have gc_uuid set"

    # Look up by name instead.
    row = db.execute(
        "SELECT gc_uuid FROM teams WHERE name = ? AND membership_type = 'tracked'",
        (_OPP_NAME_SCOUTING,),
    ).fetchone()
    assert row is not None, f"Expected opponent row with name='{_OPP_NAME_SCOUTING}'"
    assert row[0] is None, "gc_uuid must be NULL"


def test_load_team_fallback_to_uuid_when_games_has_no_name(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """AC-3: load_team() falls back to UUID as name when the games payload lacks
    opponent_team.name.

    E-211: The UUID string is used as the team name, but NOT stored as gc_uuid.
    """
    team_pk = _insert_team(db)
    game_id = "game-stream-no-name-001"
    opp_uuid = "bb22cc33-dd44-ee55-ff66-001122334455"

    # Games payload without opponent_team.name.
    games = [
        {
            "id": game_id,
            "game_status": "completed",
            "home_away": "home",
            "start_ts": "2025-04-10T18:00:00Z",
            "score": {"team": 3, "opponent_team": 1},
        }
    ]

    result = loader.load_team(
        _crawl_result(
            team_pk,
            games=games,
            boxscores={game_id: _make_boxscore(_PUBLIC_ID, opp_key=opp_uuid)},
        )
    )

    assert result.errors == 0
    # E-211: UUID used as name fallback, but gc_uuid column stays NULL.
    row = db.execute(
        "SELECT name, gc_uuid FROM teams WHERE name = ? AND membership_type = 'tracked'",
        (opp_uuid,),
    ).fetchone()
    assert row is not None, "Opponent row should exist with UUID as name"
    assert row[1] is None, "gc_uuid must be NULL"


def test_load_team_deduplicates_opponent_by_name_on_reload(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """E-211: Re-running load_team() deduplicates opponents by name+season_year.

    With gc_uuid=NULL, the dedup cascade uses name+season_year matching (step 3)
    to avoid creating duplicate rows on repeated loads.
    """
    team_pk = _insert_team(db)
    game_id = "game-stream-heal-001"
    opp_uuid = "cc33dd44-ee55-ff66-aa77-112233445566"

    def _crawl() -> SimpleNamespace:
        return _crawl_result(
            team_pk,
            games=_make_games_with_opponent_name(game_id),
            boxscores={game_id: _make_boxscore(_PUBLIC_ID, opp_key=opp_uuid)},
        )

    # First load.
    loader.load_team(_crawl())
    first_row = db.execute(
        "SELECT id FROM teams WHERE name = ? AND membership_type = 'tracked'",
        (_OPP_NAME_SCOUTING,),
    ).fetchone()
    assert first_row is not None, "First load should create opponent row"

    # Second load with same data.
    loader.load_team(_crawl())
    second_row = db.execute(
        "SELECT id FROM teams WHERE name = ? AND membership_type = 'tracked'",
        (_OPP_NAME_SCOUTING,),
    ).fetchone()
    assert second_row is not None
    assert second_row[0] == first_row[0], "Same name+season should reuse existing team row"



# E-211: _record_uuid_from_boxscore tests removed -- method deleted (UUID contamination fix).
# See tests/test_uuid_contamination.py for replacement coverage.


# ---------------------------------------------------------------------------
# P1-1 regression: UUID-only boxscore end-to-end (E-132 remediation)
# ---------------------------------------------------------------------------

# Two-UUID boxscore constants: both keys are UUIDs (no public_id slug).
_SCOUTED_GC_UUID = "11111111-2222-3333-4444-555555555555"
_OTHER_OPP_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_uuid_only_boxscore_does_not_store_gc_uuid(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """E-211: UUID-only boxscore creates opponent rows WITHOUT gc_uuid contamination.

    After E-211, the game loader's _ensure_team_row passes gc_uuid=None to the
    shared ensure_team_row, so opponent rows are created by name only.  The
    _record_uuid_from_boxscore safety net is removed entirely.
    """
    team_pk = _insert_team(db, gc_uuid=_SCOUTED_GC_UUID)
    game_id = "game-uuid-only-gc-known-001"

    boxscore = {
        _SCOUTED_GC_UUID: {"players": [], "groups": []},
        _OTHER_OPP_UUID: {"players": [], "groups": []},
    }

    loader.load_team(
        _crawl_result(
            team_pk,
            games=_make_games_with_opponent_name(game_id, "Real Opponent FC"),
            boxscores={game_id: boxscore},
        )
    )

    # With UUID contamination fix, no team rows should have gc_uuid == _OTHER_OPP_UUID.
    opp_row_by_uuid = db.execute(
        "SELECT name FROM teams WHERE gc_uuid = ?", (_OTHER_OPP_UUID,)
    ).fetchone()
    assert opp_row_by_uuid is None, (
        f"No team row should have gc_uuid={_OTHER_OPP_UUID} -- "
        "opponent-perspective UUIDs must not be stored as gc_uuid"
    )

    # Opponent row should exist by name (created by game_loader via ensure_team_row with gc_uuid=None).
    opp_row_by_name = db.execute(
        "SELECT gc_uuid FROM teams WHERE name = 'Real Opponent FC'"
    ).fetchone()
    if opp_row_by_name is not None:
        assert opp_row_by_name[0] is None, (
            "Opponent team row gc_uuid must be NULL"
        )


# ---------------------------------------------------------------------------
# E-197-03 AC-9: USSSA team gets the team-derived DB season_id
# ---------------------------------------------------------------------------


def test_usssa_team_gets_correct_db_season_id(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """A USSSA team gets the year-only '2025' season_id in the DB.

    The DB season_id is derived from team metadata (``season_year`` + program),
    never from the crawl payload.
    """
    # Set up a USSSA program and team
    db.execute(
        "INSERT OR IGNORE INTO programs (program_id, name, program_type) "
        "VALUES ('rebels-usssa', 'Lincoln Rebels', 'usssa')"
    )
    usssa_gc_uuid = "usssa-team-uuid-9999"
    usssa_public_id = "usssa-slug-abc"
    db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, public_id, is_active, program_id, season_year) "
        "VALUES ('Rebels 14U', 'tracked', ?, ?, 0, 'rebels-usssa', 2025)",
        (usssa_gc_uuid, usssa_public_id),
    )
    usssa_pk = db.execute(
        "SELECT id FROM teams WHERE gc_uuid = ?", (usssa_gc_uuid,)
    ).fetchone()[0]
    db.commit()

    game_id = "game-usssa-001"
    loader.load_team(
        _crawl_result(
            usssa_pk,
            games=_make_games(game_id),
            boxscores={game_id: _make_boxscore(usssa_public_id)},
        )
    )

    # Roster should be tagged with the team-derived season_id.
    roster_row = db.execute(
        "SELECT season_id FROM team_rosters WHERE team_id = ?", (usssa_pk,)
    ).fetchone()
    assert roster_row is not None, "Expected a team_rosters row"
    assert roster_row[0] == "2025", (
        f"Expected DB season_id='2025', got '{roster_row[0]}'"
    )

    # The loaded game (which the query-time season line derives from) is tagged
    # with the same team-derived season_id.
    game_row = db.execute(
        "SELECT season_id FROM games WHERE game_id = ?", (game_id,)
    ).fetchone()
    assert game_row is not None, "Expected a games row"
    assert game_row[0] == "2025", (
        f"Expected DB season_id='2025', got '{game_row[0]}'"
    )


# ---------------------------------------------------------------------------
# E-247-01: golden stat rows for the scouting loader (HARD GATE -- stats integrity)
# ---------------------------------------------------------------------------
#
# Characterization test (golden fixture): pins the stat rows produced by the
# scouting loader on a representative payload.  The golden values below were
# captured from the pre-E-247 code and must be reproduced exactly.  E-256-01
# deleted the disk twin, so the disk-vs-in-memory equivalence assertion that
# used to sit here is gone; the golden pin remains and is what guards the
# surviving in-memory path.


def _e247_games() -> list[dict]:
    """Two completed games with an opponent name (representative payload)."""
    return [
        {
            "id": "e247-game-1",
            "game_status": "completed",
            "home_away": "home",
            "start_ts": "2025-04-10T18:00:00Z",
            "timezone": "America/Chicago",
            "score": {"team": 5, "opponent_team": 3},
            "opponent_team": {"name": "Rival HS"},
        },
        {
            "id": "e247-game-2",
            "game_status": "completed",
            "home_away": "away",
            "start_ts": "2025-04-12T18:00:00Z",
            "timezone": "America/Chicago",
            "score": {"team": 2, "opponent_team": 4},
            "opponent_team": {"name": "Rival HS"},
        },
    ]


def _e247_boxscore(own_key: str) -> dict:
    """Boxscore with a batting line (incl. a 2B extra) and a pitching line."""
    return {
        own_key: {
            "players": [
                {"id": _PLAYER_1, "first_name": "John", "last_name": "Doe", "number": "14"},
                {"id": _PLAYER_2, "first_name": "Jane", "last_name": "Smith", "number": "7"},
            ],
            "groups": [
                {
                    "category": "lineup",
                    "stats": [
                        {
                            "player_id": _PLAYER_1,
                            "stats": {"AB": 4, "R": 1, "H": 2, "RBI": 1, "BB": 1, "SO": 1},
                        },
                    ],
                    "extra": [
                        {"stat_name": "2B", "stats": [{"player_id": _PLAYER_1, "value": 1}]},
                    ],
                },
                {
                    "category": "pitching",
                    "stats": [
                        {
                            "player_id": _PLAYER_2,
                            "stats": {"IP": 5, "H": 4, "R": 2, "ER": 2, "BB": 1, "SO": 7},
                        },
                    ],
                },
            ],
        },
        _OPP_UUID: {"players": [], "groups": []},
    }


def _e247_snapshot(db: sqlite3.Connection) -> dict[str, list[tuple]]:
    """Capture the stat-bearing rows as sorted tuples for equivalence checks."""
    return {
        "players": db.execute(
            "SELECT player_id, first_name, last_name FROM players ORDER BY player_id"
        ).fetchall(),
        "team_rosters": db.execute(
            "SELECT team_id, player_id, season_id, jersey_number FROM team_rosters "
            "ORDER BY team_id, player_id"
        ).fetchall(),
        "games": db.execute(
            "SELECT game_id, season_id, game_date, status, home_team_id, away_team_id "
            "FROM games ORDER BY game_id"
        ).fetchall(),
        "player_game_batting": db.execute(
            "SELECT game_id, player_id, team_id, perspective_team_id, ab, h, doubles, rbi, bb, so "
            "FROM player_game_batting ORDER BY game_id, player_id, perspective_team_id"
        ).fetchall(),
        "player_game_pitching": db.execute(
            "SELECT game_id, player_id, team_id, perspective_team_id, ip_outs, h, r, er, bb, so, "
            "appearance_order FROM player_game_pitching "
            "ORDER BY game_id, player_id, perspective_team_id"
        ).fetchall(),
    }


def _e247_load_in_memory(db: sqlite3.Connection) -> int:
    """Seed a team and load the representative payload via the in-memory path."""
    team_pk = _insert_team(db)
    crawl_result = SimpleNamespace(
        team_id=team_pk,
        roster=[
            {"id": _PLAYER_1, "first_name": "John", "last_name": "Doe", "number": "14"},
            {"id": _PLAYER_2, "first_name": "Jane", "last_name": "Smith", "number": "7"},
        ],
        games=_e247_games(),
        boxscores={
            "e247-game-1": _e247_boxscore(_PUBLIC_ID),
            "e247-game-2": _e247_boxscore(_PUBLIC_ID),
        },
    )
    ScoutingLoader(db).load_team(crawl_result)
    return team_pk


def test_e247_in_memory_matches_golden(
    db: sqlite3.Connection,
) -> None:
    """AC-4: in-memory load produces the pinned golden stat rows (byte-identical)."""
    team_pk = _e247_load_in_memory(db)
    snap = _e247_snapshot(db)

    # E-259: the season line is derived at query time from these per-game rows
    # (no stored player_season_* rows), so the golden pins the per-game grain the
    # loader writes; the query-time SUM of these is covered by
    # tests/test_season_query_cutover.py + tests/test_season_projection.py.
    # Per-game batting: one row per game for PLAYER_1.
    assert snap["player_game_batting"] == [
        ("e247-game-1", _PLAYER_1, team_pk, team_pk, 4, 2, 1, 1, 1, 1),
        ("e247-game-2", _PLAYER_1, team_pk, team_pk, 4, 2, 1, 1, 1, 1),
    ]
    # Per-game pitching: one row per game for PLAYER_2 (5 IP = 15 outs).
    assert snap["player_game_pitching"] == [
        ("e247-game-1", _PLAYER_2, team_pk, team_pk, 15, 4, 2, 2, 1, 7, 1),
        ("e247-game-2", _PLAYER_2, team_pk, team_pk, 15, 4, 2, 2, 1, 7, 1),
    ]
    assert len(snap["games"]) == 2


def test_e247_in_memory_empty_boxscores_skips_tail_fresh_db(
    db: sqlite3.Connection,
) -> None:
    """E-247-01 F1: in-memory empty-boxscores SKIPS the post-boxscore tail
    (dedup/recompute/commit), exactly as the pre-refactor early-return did.

    Fresh-DB case: roster is still loaded, the run completes cleanly, and no
    per-game / per-season / games stat rows exist (the tail neither ran nor was
    needed).  The populated-DB sibling test below proves the tail is actually
    *skipped* (not merely a no-op) on a non-empty database.
    """
    team_pk = _insert_team(db)
    crawl_result = SimpleNamespace(
        team_id=team_pk,
        roster=[
            {"id": _PLAYER_1, "first_name": "John", "last_name": "Doe", "number": "14"},
        ],
        games=[],          # no games
        boxscores={},      # empty boxscores -> tail is skipped (F1 guard)
    )

    result = ScoutingLoader(db).load_team(crawl_result)

    # Run completed cleanly: the single roster player is the only "loaded"
    # unit; the boxscore stage contributed nothing (no games).
    assert result.errors == 0
    assert result.loaded == 1      # the one roster player; no boxscore games
    assert result.redirect_map == {}

    # Roster row still written (roster loading runs before the boxscore guard).
    assert db.execute(
        "SELECT COUNT(*) FROM team_rosters WHERE team_id = ?", (team_pk,)
    ).fetchone()[0] == 1

    # No per-game stat rows exist (season aggregates are query-time since E-259).
    for table in (
        "player_game_batting",
        "player_game_pitching",
        "games",
    ):
        count = db.execute(
            f"SELECT COUNT(*) FROM {table} WHERE team_id = ?", (team_pk,)
        ).fetchone()[0] if table != "games" else db.execute(
            "SELECT COUNT(*) FROM games WHERE home_team_id = ? OR away_team_id = ?",
            (team_pk, team_pk),
        ).fetchone()[0]
        assert count == 0, f"Expected no {table} rows on empty-boxscores load, got {count}"


def test_e247_in_memory_empty_boxscores_does_not_touch_populated_db(
    db: sqlite3.Connection,
) -> None:
    """E-247-01 F1: a boxscoreless in-memory refresh must NOT run the
    post-boxscore tail (dedup + commit) on a POPULATED db, leaving existing rows
    untouched.

    Seeds an existing per-game row and asserts the empty-boxscore guard skips the
    tail so it is not perturbed. (Season aggregates are derived at query time
    since E-259; there is no stored season row for the tail to touch.)
    """
    team_pk = _insert_team(db)  # season_year=2025 -> DB season_id "2025"
    season_id = _SEASON_ID
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) "
        "VALUES (?, ?, 2025)",
        (season_id, season_id),
    )
    db.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES (?, 'John', 'Doe')",
        (_PLAYER_1,),
    )
    db.execute(
        "INSERT INTO games (game_id, season_id, game_date, status, home_team_id, away_team_id) "
        "VALUES ('pop-g1', ?, '2025-04-01', 'completed', ?, ?)",
        (season_id, team_pk, team_pk),
    )
    db.execute(
        "INSERT INTO player_game_batting (game_id, player_id, team_id, perspective_team_id, ab, h) "
        "VALUES ('pop-g1', ?, ?, ?, 4, 2)",
        (_PLAYER_1, team_pk, team_pk),
    )
    db.commit()

    def _snapshot():
        return db.execute(
            "SELECT game_id, player_id, ab, h FROM player_game_batting "
            "WHERE team_id = ? ORDER BY game_id, player_id",
            (team_pk,),
        ).fetchall()

    before = _snapshot()

    # Boxscoreless in-memory refresh (re-scout returning 0 boxscores).
    crawl_result = SimpleNamespace(
        team_id=team_pk, roster=[], games=[], boxscores={},
    )
    ScoutingLoader(db).load_team(crawl_result)

    # Tail was skipped: the existing per-game row is unchanged.
    assert _snapshot() == before, "per-game rows must be unchanged"


# ---------------------------------------------------------------------------
# E-247-01 F2: an ABSENT roster is not an error (missing != malformed)
# ---------------------------------------------------------------------------


def test_empty_roster_is_not_an_error(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """An empty roster loads cleanly with errors=0 -- missing is NOT malformed.

    Ported from the deleted ``test_e247_disk_missing_roster_no_error`` in
    E-256-01: the disk path's "roster.json not found" branch is gone, but the
    outcome it guarded survives at ``_load_roster_from_data``'s empty-roster
    early return.  Its siblings (``_malformed_roster``, ``_non_array_roster``)
    correctly died with the disk-only ``extra_errors`` read-error mechanism.

    Without this test the empty-roster branch runs in two other tests but no
    test asserts its error-free contract.
    """
    team_pk = _insert_team(db)

    result = loader.load_team(
        _crawl_result(team_pk, roster=[], games=[], boxscores={})
    )

    assert result.errors == 0, f"Expected errors=0 for an empty roster, got {result.errors}"
    assert db.execute(
        "SELECT COUNT(*) FROM team_rosters WHERE team_id = ?", (team_pk,)
    ).fetchone()[0] == 0


# ---------------------------------------------------------------------------
# E-253 Round-1 remediation: _opt_int NULL-preservation on the public path
# (E-253-04 sentinel preservation + E-253-06 AC-3 missing-score None handling)
#
# E-256-01 AC-6: these are the surviving home of the ``_opt_int`` semantic that
# used to be asserted against the deleted ``_parse_summary_record``. They assert
# it against ``_build_games_index_from_data``, which re-implements it inline.
# ---------------------------------------------------------------------------


def test_public_missing_start_ts_preserves_sentinel_game_date(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """Round-1 F1: a completed PUBLIC game with no start_ts/end_ts keeps the
    '1900-01-01' sentinel game_date -- it is NOT fabricated as
    '1900-01-01T00:00:00Z' and then localized backward to '1899-12-31'."""
    team_pk = _insert_team(db)
    games = [
        {
            "id": "g-no-ts",
            "game_status": "completed",
            "home_away": "home",
            "score": {"team": 5, "opponent_team": 3},
            # no start_ts / end_ts -> no recoverable instant
        }
    ]

    loader.load_team(
        _crawl_result(
            team_pk,
            games=games,
            boxscores={"g-no-ts": _make_boxscore(_PUBLIC_ID)},
        )
    )

    game_date = db.execute(
        "SELECT game_date FROM games WHERE game_id = 'g-no-ts'"
    ).fetchone()[0]
    assert game_date == "1900-01-01", (
        "absent-instant public game must preserve the sentinel, not shift to "
        "1899-12-31"
    )


def test_public_missing_scores_stored_as_null(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """Round-1 F2 / E-256-01 AC-6: a completed PUBLIC game with no score stores
    NULL home/away score via ``_opt_int`` (not coerced to 0)."""
    team_pk = _insert_team(db)
    games = [
        {
            "id": "g-noscore",
            "game_status": "completed",
            "home_away": "home",
            "start_ts": "2025-04-10T18:00:00Z",
            # no "score" key -> missing scores
        }
    ]

    loader.load_team(
        _crawl_result(
            team_pk,
            games=games,
            boxscores={"g-noscore": _make_boxscore(_PUBLIC_ID)},
        )
    )

    row = db.execute(
        "SELECT home_score, away_score FROM games WHERE game_id = 'g-noscore'"
    ).fetchone()
    assert row == (None, None), "missing public scores must be NULL, not 0"


def test_public_genuine_zero_score_preserved(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """E-256-01 AC-6: a real 0 score (present, value 0) stays 0 -- only a MISSING
    score becomes NULL. Ported from the deleted ``_parse_summary_record`` test so
    ``_opt_int``'s present-zero branch keeps its coverage on the surviving path."""
    team_pk = _insert_team(db)
    games = [
        {
            "id": "g-zero",
            "game_status": "completed",
            "home_away": "home",
            "start_ts": "2025-04-10T18:00:00Z",
            "score": {"team": 0, "opponent_team": 0},
        }
    ]

    loader.load_team(
        _crawl_result(
            team_pk,
            games=games,
            boxscores={"g-zero": _make_boxscore(_PUBLIC_ID)},
        )
    )

    row = db.execute(
        "SELECT home_score, away_score FROM games WHERE game_id = 'g-zero'"
    ).fetchone()
    assert row == (0, 0), "a genuine 0-0 must be preserved, not nulled"


def test_public_scoreless_doubleheader_stays_two_rows(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """Round-1 F2 (E-253-06 AC-3 on the public path): two same-date, same-team
    public games both missing scores AND start_ts do NOT collapse -- pre-fix,
    both coerced to 0-0 with equal totals and the natural-key dedup redirected
    the second onto the first."""
    team_pk = _insert_team(db)
    games = [
        {"id": "dh-1", "game_status": "completed", "home_away": "home"},
        {"id": "dh-2", "game_status": "completed", "home_away": "home"},
    ]

    loader.load_team(
        _crawl_result(
            team_pk,
            games=games,
            boxscores={
                "dh-1": _make_boxscore(_PUBLIC_ID),
                "dh-2": _make_boxscore(_PUBLIC_ID),
            },
        )
    )

    game_ids = {
        r[0] for r in db.execute("SELECT game_id FROM games").fetchall()
    }
    assert {"dh-1", "dh-2"} <= game_ids, (
        "a scoreless public doubleheader must remain two rows, not collapse"
    )
