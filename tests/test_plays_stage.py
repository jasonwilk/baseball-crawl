"""Unit tests for src/gamechanger/pipelines/plays_stage.py (E-229-01).

Covers:
- AC-4: Auth-expiry mid-stage handling.
- AC-5: Per-game error isolation (HTTP errors, reconcile errors).
- AC-6: Idempotency on rerun (zero HTTP, zero rows, zero reconcile work).
- AC-7: Empty game_ids returns immediately.
- AC-8: Golden path -- helper crawls + loads + reconciles plays.

All tests use an on-disk SQLite database (per-test ``tmp_path``) with
``PRAGMA foreign_keys=ON`` enabled by the migration.  No real network calls.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from migrations.apply_migrations import run_migrations
from src.gamechanger.client import CredentialExpiredError
from src.gamechanger.pipelines import PlaysStageResult, run_plays_stage


# ---------------------------------------------------------------------------
# Constants (real-shape UUIDs; matches plays endpoint doc examples).
# ---------------------------------------------------------------------------

_SEASON_ID = "2026-spring-hs"
_GAME_ID_1 = "11111111-1111-1111-1111-111111111111"
_GAME_ID_2 = "22222222-2222-2222-2222-222222222222"
_GAME_ID_3 = "33333333-3333-3333-3333-333333333333"
_BATTER_1 = "ba000001-aaaa-bbbb-cccc-000000000001"
_BATTER_2 = "ba000002-aaaa-bbbb-cccc-000000000002"
_PITCHER_1 = "01000001-aaaa-bbbb-cccc-000000000001"
_PITCHER_2 = "01000002-aaaa-bbbb-cccc-000000000002"
_HOME_GC_UUID = "aaaa1111-cccc-dddd-eeee-ffff00000001"
_AWAY_GC_UUID = "aaaa2222-cccc-dddd-eeee-ffff00000002"
_PUBLIC_ID = "tracked-opponent"


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
def team_ids(db: sqlite3.Connection) -> tuple[int, int]:
    """Insert home + away team rows; return (home_team_id, away_team_id)."""
    db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, public_id, is_active) "
        "VALUES (?, 'tracked', ?, ?, 1)",
        ("Home Team", _HOME_GC_UUID, _PUBLIC_ID),
    )
    db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) "
        "VALUES (?, 'tracked', ?, 1)",
        ("Away Team", _AWAY_GC_UUID),
    )
    home_id = db.execute(
        "SELECT id FROM teams WHERE gc_uuid = ?", (_HOME_GC_UUID,)
    ).fetchone()[0]
    away_id = db.execute(
        "SELECT id FROM teams WHERE gc_uuid = ?", (_AWAY_GC_UUID,)
    ).fetchone()[0]

    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, ?, ?, ?)",
        (_SEASON_ID, "Spring 2026 HS", "spring-hs", 2026),
    )

    db.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES (?, ?, ?)",
        (_BATTER_1, "Batter", "One"),
    )
    db.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES (?, ?, ?)",
        (_BATTER_2, "Batter", "Two"),
    )
    db.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES (?, ?, ?)",
        (_PITCHER_1, "Pitcher", "One"),
    )
    db.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES (?, ?, ?)",
        (_PITCHER_2, "Pitcher", "Two"),
    )
    db.commit()
    return home_id, away_id


@pytest.fixture()
def seeded_games(
    db: sqlite3.Connection,
    team_ids: tuple[int, int],
    seed_boxscore_for_plays,
) -> tuple[int, int]:
    """Seed two games with boxscore rows; return team_ids for convenience."""
    home_id, away_id = team_ids
    seed_boxscore_for_plays(
        db,
        game_id=_GAME_ID_1,
        home_team_id=home_id,
        away_team_id=away_id,
        season_id=_SEASON_ID,
        perspective_team_id=home_id,
        pitcher_appearances=[
            {
                "team_id": away_id,
                "player_id": _PITCHER_1,
                "appearance_order": 1,
                "ip_outs": 9,
                "bf": 3,
                "pitches": 9,
                "total_strikes": 6,
            },
        ],
        batter_appearances=[
            {"team_id": away_id, "player_id": _BATTER_1, "ab": 3, "h": 3},
        ],
    )
    seed_boxscore_for_plays(
        db,
        game_id=_GAME_ID_2,
        home_team_id=home_id,
        away_team_id=away_id,
        season_id=_SEASON_ID,
        perspective_team_id=home_id,
        pitcher_appearances=[
            {
                "team_id": away_id,
                "player_id": _PITCHER_2,
                "appearance_order": 1,
                "ip_outs": 6,
                "bf": 2,
                "pitches": 6,
                "total_strikes": 4,
            },
        ],
        batter_appearances=[
            {"team_id": away_id, "player_id": _BATTER_2, "ab": 2, "h": 2},
        ],
    )
    return home_id, away_id


# ---------------------------------------------------------------------------
# AC-1 / AC-2: Public API surface
# ---------------------------------------------------------------------------


def test_helper_and_dataclass_are_importable_from_package():
    """The helper and result type re-export from src.gamechanger.pipelines."""
    from src.gamechanger.pipelines import (  # noqa: F401 -- import-only test
        PlaysStageResult as ResultFromPkg,
        run_plays_stage as RunFromPkg,
    )
    assert ResultFromPkg is PlaysStageResult
    assert RunFromPkg is run_plays_stage


def test_plays_stage_result_field_names_use_bare_convention():
    """AC-1: bare-name convention matching LoadResult."""
    result = PlaysStageResult(
        attempted=0,
        loaded=0,
        skipped=0,
        errored=0,
        reconcile_errors=0,
        auth_expired=False,
    )
    field_names = {
        "attempted", "loaded", "skipped", "errored",
        "reconcile_errors", "auth_expired", "deferred_game_ids",
    }
    assert set(result.__dict__.keys()) == field_names


# ---------------------------------------------------------------------------
# AC-7: Empty game_ids
# ---------------------------------------------------------------------------


def test_empty_game_ids_returns_immediately(db: sqlite3.Connection):
    """AC-7: empty game_ids does no work, returns attempted=0."""
    client = MagicMock()

    result = run_plays_stage(
        client,
        db,
        perspective_team_id=1,
        public_id=_PUBLIC_ID,
        game_ids=[],
    )

    assert result == PlaysStageResult(
        attempted=0,
        loaded=0,
        skipped=0,
        errored=0,
        reconcile_errors=0,
        auth_expired=False,
        deferred_game_ids=[],
    )
    client.get.assert_not_called()


# ---------------------------------------------------------------------------
# AC-8 (golden path): helper crawls, loads, and reconciles plays
# ---------------------------------------------------------------------------


def test_golden_path_loads_and_reconciles_plays(
    db: sqlite3.Connection,
    seeded_games: tuple[int, int],
    plays_json_factory,
    mock_gc_client_with_plays,
):
    """AC-8 + AC-1: helper fetches, loads, reconciles; PlaysStageResult is populated."""
    home_id, away_id = seeded_games

    plays_by_game = {
        _GAME_ID_1: plays_json_factory(_GAME_ID_1, _PITCHER_1, _BATTER_1, num_plays=3),
        _GAME_ID_2: plays_json_factory(_GAME_ID_2, _PITCHER_2, _BATTER_2, num_plays=2),
    }
    client = mock_gc_client_with_plays(plays_by_game)

    result = run_plays_stage(
        client,
        db,
        perspective_team_id=home_id,
        public_id=_PUBLIC_ID,
        game_ids=[_GAME_ID_1, _GAME_ID_2],
    )

    assert isinstance(result, PlaysStageResult)
    assert result.attempted == 2
    assert result.errored == 0
    assert result.reconcile_errors == 0
    assert result.auth_expired is False
    assert result.deferred_game_ids == []
    # `loaded` is a games count (post-load DB probe), NOT a record count --
    # the operator-facing summary "plays: {loaded}/{attempted} loaded" reads
    # coherently only with games semantics.
    assert result.loaded == 2  # both games' plays were loaded

    plays_count = db.execute(
        "SELECT COUNT(*) FROM plays WHERE perspective_team_id = ?",
        (home_id,),
    ).fetchone()[0]
    assert plays_count == 5  # 3 + 2 plays inserted (record count)

    events_count = db.execute(
        "SELECT COUNT(*) FROM play_events pe "
        "JOIN plays p ON pe.play_id = p.id "
        "WHERE p.perspective_team_id = ?",
        (home_id,),
    ).fetchone()[0]
    assert events_count > 0

    # Two HTTP requests (one per game), no extras.
    assert client.get.call_count == 2


# ---------------------------------------------------------------------------
# AC-6: Idempotency on rerun
# ---------------------------------------------------------------------------


def test_rerun_is_zero_http_zero_rows_zero_reconcile(
    db: sqlite3.Connection,
    seeded_games: tuple[int, int],
    plays_json_factory,
    mock_gc_client_with_plays,
):
    """AC-6: second call performs zero HTTP, zero new rows, zero reconcile work."""
    home_id, _ = seeded_games

    plays_by_game = {
        _GAME_ID_1: plays_json_factory(_GAME_ID_1, _PITCHER_1, _BATTER_1, num_plays=3),
        _GAME_ID_2: plays_json_factory(_GAME_ID_2, _PITCHER_2, _BATTER_2, num_plays=2),
    }

    # First call: full work.
    client_first = mock_gc_client_with_plays(plays_by_game)
    first = run_plays_stage(
        client_first,
        db,
        perspective_team_id=home_id,
        public_id=_PUBLIC_ID,
        game_ids=[_GAME_ID_1, _GAME_ID_2],
    )
    assert first.loaded == 2  # both games loaded (games count)

    plays_count_after_first = db.execute(
        "SELECT COUNT(*) FROM plays WHERE perspective_team_id = ?",
        (home_id,),
    ).fetchone()[0]

    # Second call: monkeypatch reconcile_game in the module under test and
    # reuse a fresh mock client so both call_counts are observable.
    client_second = mock_gc_client_with_plays(plays_by_game)

    with patch(
        "src.gamechanger.pipelines.plays_stage.reconcile_game"
    ) as reconcile_mock:
        second = run_plays_stage(
            client_second,
            db,
            perspective_team_id=home_id,
            public_id=_PUBLIC_ID,
            game_ids=[_GAME_ID_1, _GAME_ID_2],
        )

    assert client_second.get.call_count == 0
    assert reconcile_mock.call_count == 0
    assert second.loaded == 0
    # AC-6: rerun summary reports `loaded=0 skipped=N` -- pre-fetch-skipped
    # games (already loaded by a prior run) fold into `skipped`.
    assert second.skipped == 2
    assert second.errored == 0
    assert second.attempted == 2
    assert second.auth_expired is False
    assert second.deferred_game_ids == []

    plays_count_after_second = db.execute(
        "SELECT COUNT(*) FROM plays WHERE perspective_team_id = ?",
        (home_id,),
    ).fetchone()[0]
    assert plays_count_after_second == plays_count_after_first


# ---------------------------------------------------------------------------
# AC-4: Auth-expiry mid-stage
# ---------------------------------------------------------------------------


def test_auth_expiry_midstage_defers_remaining(
    db: sqlite3.Connection,
    seeded_games: tuple[int, int],
    plays_json_factory,
):
    """AC-4: auth expiry mid-loop sets auth_expired, records deferred IDs."""
    home_id, _ = seeded_games

    # Add a third seeded game so there are two unfetched after the second
    # raises CredentialExpiredError.
    db.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, status) "
        "VALUES (?, ?, ?, ?, ?, 'completed')",
        (_GAME_ID_3, _SEASON_ID, "2026-04-12",
         seeded_games[0], seeded_games[1]),
    )
    db.commit()

    game_1_json = plays_json_factory(_GAME_ID_1, _PITCHER_1, _BATTER_1, num_plays=2)

    client = MagicMock()
    call_counter = {"count": 0}

    def _fake_get(path: str, *args, **kwargs):
        call_counter["count"] += 1
        if call_counter["count"] == 1:
            return game_1_json
        raise CredentialExpiredError("token rejected during plays fetch")

    client.get.side_effect = _fake_get

    result = run_plays_stage(
        client,
        db,
        perspective_team_id=home_id,
        public_id=_PUBLIC_ID,
        game_ids=[_GAME_ID_1, _GAME_ID_2, _GAME_ID_3],
    )

    assert result.auth_expired is True
    assert result.deferred_game_ids == [_GAME_ID_2, _GAME_ID_3]
    assert result.attempted == 3
    assert result.loaded == 1  # the first game still loaded successfully (games count)

    # First game's plays are persisted.
    persisted = db.execute(
        "SELECT COUNT(*) FROM plays WHERE game_id = ? AND perspective_team_id = ?",
        (_GAME_ID_1, home_id),
    ).fetchone()[0]
    assert persisted == 2

    # No plays for the deferred games.
    for deferred in (_GAME_ID_2, _GAME_ID_3):
        rows = db.execute(
            "SELECT COUNT(*) FROM plays "
            "WHERE game_id = ? AND perspective_team_id = ?",
            (deferred, home_id),
        ).fetchone()[0]
        assert rows == 0


def test_auth_expiry_partitions_remaining_into_skipped_and_deferred(
    db: sqlite3.Connection,
    seeded_games: tuple[int, int],
    plays_json_factory,
):
    """AC-4: auth-expiry suffix partition -- already-loaded games go to
    ``skipped`` (not ``deferred_game_ids``).

    Setup:
        - game_ids = [g1, g2, g3].
        - g1: not loaded -> HTTP fetch raises ``CredentialExpiredError``.
        - g2: already loaded (a ``plays`` row exists for this perspective).
        - g3: not loaded.

    Pre-fix behavior: ``deferred_game_ids = [g1, g2, g3]`` (overstated by 1)
    and ``skipped = 0`` (understated by 1).

    Post-fix behavior: ``deferred_game_ids = [g1, g3]`` (only games that
    actually need a re-fetch), ``skipped = 1`` (g2 was already loaded so
    folds into skipped).
    """
    home_id, away_id = seeded_games

    # Seed a third game (boxscore + perspective) for completeness; the helper
    # only probes ``plays`` rows for the pre-fetch skip and would happily
    # iterate a game_id whose ``games`` row didn't exist, but seeding keeps
    # the fixture aligned with what the upstream pipeline produces.
    db.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, status) "
        "VALUES (?, ?, ?, ?, ?, 'completed')",
        (_GAME_ID_3, _SEASON_ID, "2026-04-12", home_id, away_id),
    )
    db.execute(
        "INSERT OR IGNORE INTO game_perspectives (game_id, perspective_team_id) "
        "VALUES (?, ?)",
        (_GAME_ID_3, home_id),
    )

    # Pre-seed a ``plays`` row for g2 so the pre-fetch DB skip hits when the
    # helper reaches g2 in the suffix-partition step.  The columns chosen are
    # the minimum set required by the schema (NOT NULLs); reconcile is never
    # invoked on this synthetic row because g2 is in the suffix at break.
    db.execute(
        "INSERT INTO plays "
        "(game_id, play_order, inning, half, season_id, batting_team_id, "
        " perspective_team_id, batter_id, pitcher_id) "
        "VALUES (?, 0, 1, 'top', ?, ?, ?, ?, ?)",
        (_GAME_ID_2, _SEASON_ID, away_id, home_id, _BATTER_2, _PITCHER_2),
    )
    db.commit()

    # Mock client: g1 -> auth expiry; g3 would also be requested but the
    # CredentialExpiredError on g1 breaks the loop before g3 is reached.
    client = MagicMock()

    def _fake_get(path: str, *args, **kwargs):
        if _GAME_ID_1 in path:
            raise CredentialExpiredError("token rejected during plays fetch")
        # The g3 request never happens because the loop breaks at g1.  But
        # if the iteration order ever changes, fail loudly rather than
        # silently returning a stub.
        raise AssertionError(f"unexpected HTTP call after auth-expiry: {path}")

    client.get.side_effect = _fake_get

    result = run_plays_stage(
        client,
        db,
        perspective_team_id=home_id,
        public_id=_PUBLIC_ID,
        game_ids=[_GAME_ID_1, _GAME_ID_2, _GAME_ID_3],
    )

    assert result.auth_expired is True
    # Already-loaded suffix games fold into ``skipped``; only the truly
    # unfetched games appear in ``deferred_game_ids``.  Pre-fix this was
    # [_GAME_ID_1, _GAME_ID_2, _GAME_ID_3] -- overstated by 1.
    assert result.deferred_game_ids == [_GAME_ID_1, _GAME_ID_3]
    # g2 (already-loaded suffix game) folds into skipped; g1 and g3 do not.
    assert result.skipped == 1
    assert result.attempted == 3
    # No new plays loaded this run (auth expired before any HTTP fetch
    # succeeded; g2's pre-existing row is not "loaded by this run").
    assert result.loaded == 0
    # Only one HTTP call attempted before the loop broke on auth-expiry.
    assert client.get.call_count == 1


# ---------------------------------------------------------------------------
# AC-5: Per-game error isolation
# ---------------------------------------------------------------------------


def test_per_game_http_error_does_not_abort_remaining(
    db: sqlite3.Connection,
    seeded_games: tuple[int, int],
    plays_json_factory,
):
    """AC-5: HTTP error on one game increments errored, other games still load."""
    home_id, _ = seeded_games

    game_2_json = plays_json_factory(_GAME_ID_2, _PITCHER_2, _BATTER_2, num_plays=2)

    client = MagicMock()

    def _fake_get(path: str, *args, **kwargs):
        if _GAME_ID_1 in path:
            raise RuntimeError("simulated transient HTTP failure")
        if _GAME_ID_2 in path:
            return game_2_json
        raise KeyError(path)

    client.get.side_effect = _fake_get

    result = run_plays_stage(
        client,
        db,
        perspective_team_id=home_id,
        public_id=_PUBLIC_ID,
        game_ids=[_GAME_ID_1, _GAME_ID_2],
    )

    assert result.errored == 1
    assert result.loaded == 1  # game 2 loaded (games count); game 1 errored
    assert result.auth_expired is False
    assert result.deferred_game_ids == []

    # Only game 2's plays are loaded; game 1 produced no rows.
    g1_rows = db.execute(
        "SELECT COUNT(*) FROM plays "
        "WHERE game_id = ? AND perspective_team_id = ?",
        (_GAME_ID_1, home_id),
    ).fetchone()[0]
    assert g1_rows == 0

    g2_rows = db.execute(
        "SELECT COUNT(*) FROM plays "
        "WHERE game_id = ? AND perspective_team_id = ?",
        (_GAME_ID_2, home_id),
    ).fetchone()[0]
    assert g2_rows == 2


def test_per_game_reconcile_failure_does_not_abort_remaining(
    db: sqlite3.Connection,
    seeded_games: tuple[int, int],
    plays_json_factory,
    mock_gc_client_with_plays,
):
    """AC-5: reconcile failure on one game increments reconcile_errors only."""
    home_id, _ = seeded_games

    plays_by_game = {
        _GAME_ID_1: plays_json_factory(_GAME_ID_1, _PITCHER_1, _BATTER_1, num_plays=2),
        _GAME_ID_2: plays_json_factory(_GAME_ID_2, _PITCHER_2, _BATTER_2, num_plays=2),
    }
    client = mock_gc_client_with_plays(plays_by_game)

    call_counter = {"count": 0}

    def _flaky_reconcile(conn, game_id, dry_run, perspective_team_id):
        call_counter["count"] += 1
        if game_id == _GAME_ID_1:
            raise RuntimeError("simulated reconcile failure")
        return None

    with patch(
        "src.gamechanger.pipelines.plays_stage.reconcile_game",
        side_effect=_flaky_reconcile,
    ):
        result = run_plays_stage(
            client,
            db,
            perspective_team_id=home_id,
            public_id=_PUBLIC_ID,
            game_ids=[_GAME_ID_1, _GAME_ID_2],
        )

    assert result.reconcile_errors == 1
    assert result.errored == 0  # reconcile failures don't increment `errored`
    assert result.loaded == 2  # both games' plays loaded (games count)
    # Both games attempted reconcile.
    assert call_counter["count"] == 2
