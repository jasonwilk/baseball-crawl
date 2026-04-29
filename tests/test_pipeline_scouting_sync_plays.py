"""Tests for run_scouting_sync plays-stage wiring (E-229-03).

Covers:
- AC-1: helper invoked once per scouted team after dedup, with sorted game_ids.
- AC-2: partial failure UPDATEs crawl_jobs.error_message with structured prefix.
- AC-3: helper-raises-unexpected-exception leaves status='completed';
  greppable PLAYS STAGE FAILED token in WARNING log.
- AC-4: golden path -- plays/play_events rows persisted, status='completed',
  last_synced updated.
- AC-5: idempotency-on-rerun -- zero new HTTP, zero new rows.
- AC-6: auth-expiry persists already-loaded games; status='completed';
  error_message includes deferred count.
- AC-7: scout-load failure short-circuits before plays-stage.
- AC-8: format-string helper rules across reconcile-only / load / auth combos.

All HTTP calls are mocked.  No real network or scouting-pipeline I/O.
"""

from __future__ import annotations

import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from migrations.apply_migrations import run_migrations  # noqa: E402
from src.gamechanger.client import CredentialExpiredError  # noqa: E402
from src.gamechanger.crawlers.scouting import ScoutingCrawlResult  # noqa: E402
from src.gamechanger.loaders import LoadResult  # noqa: E402
from src.gamechanger.pipelines import PlaysStageResult  # noqa: E402
from src.pipeline import trigger  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEASON_ID = "2026-spring-hs"
_GAME_ID_1 = "11111111-1111-1111-1111-111111111111"
_GAME_ID_2 = "22222222-2222-2222-2222-222222222222"
_GAME_ID_3 = "33333333-3333-3333-3333-333333333333"
_BATTER_1 = "ba000001-aaaa-bbbb-cccc-000000000001"
_PITCHER_1 = "01000001-aaaa-bbbb-cccc-000000000001"


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _make_db_with_tracked_team(tmp_path: Path) -> tuple[Path, int, int]:
    """Create migrated DB + a tracked + opponent team. Return (db_path, team_id, opp_team_id)."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute(
            "INSERT INTO teams (id, name, membership_type, public_id, season_year) "
            "VALUES (1, 'Tracked Opp', 'tracked', 'tracked-opp', 2026)"
        )
        conn.execute(
            "INSERT INTO teams (id, name, membership_type) "
            "VALUES (2, 'Other Side', 'tracked')"
        )
        conn.commit()
    return db_path, 1, 2


def _insert_crawl_job(db_path: Path, team_id: int) -> int:
    with closing(sqlite3.connect(str(db_path))) as conn:
        cur = conn.execute(
            "INSERT INTO crawl_jobs (team_id, sync_type, status, started_at) "
            "VALUES (?, 'scouting_crawl', 'running', datetime('now'))",
            (team_id,),
        )
        conn.commit()
        return cur.lastrowid


def _insert_scouting_run(db_path: Path, team_id: int, season_id: str) -> None:
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) "
            "VALUES (?, 'Spring 2026', 'spring-hs', 2026)",
            (season_id,),
        )
        conn.execute(
            "INSERT INTO scouting_runs (team_id, season_id, status, last_checked) "
            "VALUES (?, ?, 'running', '2099-12-31T00:00:00.000Z')",
            (team_id, season_id),
        )
        conn.commit()


def _seed_game_for_reconcile(
    db_path: Path,
    *,
    game_id: str,
    home_team_id: int,
    away_team_id: int,
    perspective_team_id: int,
    pitcher_id: str = _PITCHER_1,
    batter_id: str = _BATTER_1,
) -> None:
    """Seed a games + player_game_pitching/batting row for reconcile."""
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
            "VALUES (?, 'Pitcher', 'One')",
            (pitcher_id,),
        )
        conn.execute(
            "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
            "VALUES (?, 'Batter', 'One')",
            (batter_id,),
        )
        conn.execute(
            "INSERT INTO games "
            "(game_id, season_id, game_date, home_team_id, away_team_id, status) "
            "VALUES (?, ?, '2026-04-10', ?, ?, 'completed')",
            (game_id, _SEASON_ID, home_team_id, away_team_id),
        )
        # Mirror the upstream GameLoader write
        # (src/gamechanger/loaders/game_loader.py:640-647).  E2E tests mock
        # the ScoutingLoader, so the real GameLoader never runs -- a
        # regression in the upstream INSERT OR IGNORE would leave the web
        # suite green without this seed.  Mirrors the shared
        # seed_boxscore_for_plays fixture in tests/conftest.py.
        conn.execute(
            "INSERT OR IGNORE INTO game_perspectives "
            "(game_id, perspective_team_id) VALUES (?, ?)",
            (game_id, perspective_team_id),
        )
        conn.execute(
            "INSERT INTO player_game_pitching "
            "(game_id, team_id, player_id, perspective_team_id, "
            " appearance_order, ip_outs, h, r, er, bb, so, pitches, total_strikes, bf) "
            "VALUES (?, ?, ?, ?, 1, 6, 0, 0, 0, 0, 0, 6, 4, 2)",
            (game_id, away_team_id, pitcher_id, perspective_team_id),
        )
        conn.execute(
            "INSERT INTO player_game_batting "
            "(game_id, team_id, player_id, perspective_team_id, "
            " ab, r, h, bb, so, hbp) "
            "VALUES (?, ?, ?, ?, 2, 0, 2, 0, 0, 0)",
            (game_id, away_team_id, batter_id, perspective_team_id),
        )
        conn.commit()


def _get_crawl_job(db_path: Path, job_id: int) -> dict:
    with closing(sqlite3.connect(str(db_path))) as conn:
        row = conn.execute(
            "SELECT status, completed_at, error_message FROM crawl_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    return {"status": row[0], "completed_at": row[1], "error_message": row[2]}


def _get_last_synced(db_path: Path, team_id: int) -> str | None:
    with closing(sqlite3.connect(str(db_path))) as conn:
        row = conn.execute(
            "SELECT last_synced FROM teams WHERE id = ?", (team_id,)
        ).fetchone()
    return row[0] if row else None


def _make_crawl_result(team_id: int, public_id: str, game_ids: list[str]) -> ScoutingCrawlResult:
    return ScoutingCrawlResult(
        team_id=team_id,
        season_id=_SEASON_ID,
        public_id=public_id,
        games=[{"id": gid, "game_status": "completed"} for gid in game_ids],
        roster=[],
        boxscores={gid: {} for gid in game_ids},
        games_crawled=len(game_ids),
    )


# ---------------------------------------------------------------------------
# AC-1: helper invoked after dedup with sorted game_ids
# ---------------------------------------------------------------------------


def test_helper_invoked_with_sorted_game_ids(tmp_path: Path) -> None:
    """AC-1: run_plays_stage called once per scouted team with sorted IDs."""
    db_path, team_id, _ = _make_db_with_tracked_team(tmp_path)
    job_id = _insert_crawl_job(db_path, team_id)
    _insert_scouting_run(db_path, team_id=team_id, season_id=_SEASON_ID)

    cr = _make_crawl_result(team_id, "tracked-opp", [_GAME_ID_2, _GAME_ID_1])
    mock_crawler = MagicMock()
    mock_crawler.scout_team.return_value = cr
    mock_loader = MagicMock()
    mock_loader.load_team.return_value = LoadResult(loaded=5, errors=0)

    # Games-count semantics: loaded <= attempted is invariant.  Use a valid
    # all-loaded shape (attempted == loaded == 2).
    helper_mock = MagicMock(
        return_value=PlaysStageResult(
            attempted=2, loaded=2, skipped=0, errored=0,
            reconcile_errors=0, auth_expired=False, deferred_game_ids=[],
        ),
    )

    with (
        patch("src.pipeline.trigger.get_db_path", return_value=db_path),
        patch("src.pipeline.trigger._refresh_auth_token"),
        patch("src.pipeline.trigger.ScoutingCrawler", return_value=mock_crawler),
        patch("src.pipeline.trigger.ScoutingLoader", return_value=mock_loader),
        patch("src.pipeline.trigger.resolve_gc_uuid", return_value=None),
        patch("src.pipeline.trigger._run_spray_stages"),
        # Patch the imported binding inside src.pipeline.trigger -- the
        # trigger module imports run_plays_stage at module level, so the
        # canonical seam is the trigger module's reference, not the source
        # module.  Same Python import-binding pattern used in test_trigger.py.
        patch("src.pipeline.trigger.run_plays_stage", helper_mock),
    ):
        trigger.run_scouting_sync(team_id, "tracked-opp", job_id)

    helper_mock.assert_called_once()
    _, kwargs = helper_mock.call_args
    assert kwargs["perspective_team_id"] == team_id
    assert kwargs["public_id"] == "tracked-opp"
    assert kwargs["game_ids"] == sorted([_GAME_ID_1, _GAME_ID_2])

    job = _get_crawl_job(db_path, job_id)
    assert job["status"] == "completed"
    assert job["error_message"] is None  # helper returned clean


# ---------------------------------------------------------------------------
# AC-2: partial failure UPDATEs crawl_jobs.error_message with structured prefix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "result_kwargs,expected_prefix",
    [
        (
            {"attempted": 14, "loaded": 12, "skipped": 0, "errored": 2,
             "reconcile_errors": 0, "auth_expired": False,
             "deferred_game_ids": []},
            "plays: 12/14 loaded, 2 errored",
        ),
        (
            {"attempted": 14, "loaded": 14, "skipped": 0, "errored": 0,
             "reconcile_errors": 3, "auth_expired": False,
             "deferred_game_ids": []},
            "plays: 14/14 loaded, 3 reconcile errors",
        ),
        (
            {"attempted": 14, "loaded": 12, "skipped": 0, "errored": 0,
             "reconcile_errors": 0, "auth_expired": True,
             "deferred_game_ids": [_GAME_ID_2, _GAME_ID_3]},
            "plays: 12/14 loaded, 2 deferred (auth)",
        ),
        (
            {"attempted": 14, "loaded": 8, "skipped": 0, "errored": 2,
             "reconcile_errors": 2, "auth_expired": True,
             "deferred_game_ids": [_GAME_ID_2, _GAME_ID_3]},
            "plays: 8/14 loaded, 2 errored, 2 reconcile errors, 2 deferred (auth)",
        ),
    ],
)
def test_partial_failure_updates_error_message(
    tmp_path: Path,
    result_kwargs: dict,
    expected_prefix: str,
) -> None:
    """AC-2: partial failure UPDATEs error_message with structured prefix."""
    db_path, team_id, _ = _make_db_with_tracked_team(tmp_path)
    job_id = _insert_crawl_job(db_path, team_id)
    _insert_scouting_run(db_path, team_id=team_id, season_id=_SEASON_ID)

    cr = _make_crawl_result(team_id, "tracked-opp", [_GAME_ID_1])
    mock_crawler = MagicMock()
    mock_crawler.scout_team.return_value = cr
    mock_loader = MagicMock()
    mock_loader.load_team.return_value = LoadResult(loaded=5, errors=0)

    helper_mock = MagicMock(return_value=PlaysStageResult(**result_kwargs))

    with (
        patch("src.pipeline.trigger.get_db_path", return_value=db_path),
        patch("src.pipeline.trigger._refresh_auth_token"),
        patch("src.pipeline.trigger.ScoutingCrawler", return_value=mock_crawler),
        patch("src.pipeline.trigger.ScoutingLoader", return_value=mock_loader),
        patch("src.pipeline.trigger.resolve_gc_uuid", return_value=None),
        patch("src.pipeline.trigger._run_spray_stages"),
        patch("src.pipeline.trigger.run_plays_stage", helper_mock),
    ):
        trigger.run_scouting_sync(team_id, "tracked-opp", job_id)

    job = _get_crawl_job(db_path, job_id)
    assert job["status"] == "completed"  # status untouched by plays
    assert job["error_message"] == expected_prefix


def test_clean_result_leaves_error_message_null(tmp_path: Path) -> None:
    """AC-2 (corollary): when helper returns fully clean, no UPDATE issued."""
    db_path, team_id, _ = _make_db_with_tracked_team(tmp_path)
    job_id = _insert_crawl_job(db_path, team_id)
    _insert_scouting_run(db_path, team_id=team_id, season_id=_SEASON_ID)

    cr = _make_crawl_result(team_id, "tracked-opp", [_GAME_ID_1])
    mock_crawler = MagicMock()
    mock_crawler.scout_team.return_value = cr
    mock_loader = MagicMock()
    mock_loader.load_team.return_value = LoadResult(loaded=5, errors=0)

    helper_mock = MagicMock(
        return_value=PlaysStageResult(
            attempted=1, loaded=2, skipped=0, errored=0,
            reconcile_errors=0, auth_expired=False, deferred_game_ids=[],
        ),
    )

    with (
        patch("src.pipeline.trigger.get_db_path", return_value=db_path),
        patch("src.pipeline.trigger._refresh_auth_token"),
        patch("src.pipeline.trigger.ScoutingCrawler", return_value=mock_crawler),
        patch("src.pipeline.trigger.ScoutingLoader", return_value=mock_loader),
        patch("src.pipeline.trigger.resolve_gc_uuid", return_value=None),
        patch("src.pipeline.trigger._run_spray_stages"),
        patch("src.pipeline.trigger.run_plays_stage", helper_mock),
    ):
        trigger.run_scouting_sync(team_id, "tracked-opp", job_id)

    job = _get_crawl_job(db_path, job_id)
    assert job["status"] == "completed"
    assert job["error_message"] is None


# ---------------------------------------------------------------------------
# AC-3: helper-raises-unexpected-exception leaves status='completed'
# ---------------------------------------------------------------------------


def test_helper_unexpected_exception_status_remains_completed(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC-3: helper crash logs PLAYS STAGE FAILED, status stays completed."""
    db_path, team_id, _ = _make_db_with_tracked_team(tmp_path)
    job_id = _insert_crawl_job(db_path, team_id)
    _insert_scouting_run(db_path, team_id=team_id, season_id=_SEASON_ID)

    cr = _make_crawl_result(team_id, "tracked-opp", [_GAME_ID_1])
    mock_crawler = MagicMock()
    mock_crawler.scout_team.return_value = cr
    mock_loader = MagicMock()
    mock_loader.load_team.return_value = LoadResult(loaded=5, errors=0)

    helper_mock = MagicMock(side_effect=RuntimeError("simulated helper crash"))

    import logging
    caplog.set_level(logging.WARNING, logger="src.pipeline.trigger")

    with (
        patch("src.pipeline.trigger.get_db_path", return_value=db_path),
        patch("src.pipeline.trigger._refresh_auth_token"),
        patch("src.pipeline.trigger.ScoutingCrawler", return_value=mock_crawler),
        patch("src.pipeline.trigger.ScoutingLoader", return_value=mock_loader),
        patch("src.pipeline.trigger.resolve_gc_uuid", return_value=None),
        patch("src.pipeline.trigger._run_spray_stages"),
        patch("src.pipeline.trigger.run_plays_stage", helper_mock),
    ):
        trigger.run_scouting_sync(team_id, "tracked-opp", job_id)

    job = _get_crawl_job(db_path, job_id)
    assert job["status"] == "completed"
    assert any(
        "PLAYS STAGE FAILED" in r.getMessage() for r in caplog.records
    ), [r.getMessage() for r in caplog.records]


# ---------------------------------------------------------------------------
# AC-4 + AC-5 + AC-6: end-to-end DB-write scenarios using the real helper
# ---------------------------------------------------------------------------


def _patch_e2e(stack: list, db_path: Path, cr: ScoutingCrawlResult, fake_get):
    """Common patches for end-to-end tests (real helper runs, mocked HTTP)."""
    mock_crawler = MagicMock()
    mock_crawler.scout_team.return_value = cr
    mock_loader = MagicMock()
    mock_loader.load_team.return_value = LoadResult(loaded=5, errors=0)

    def _client_factory(*args, **kwargs):
        c = MagicMock()
        c.get.side_effect = fake_get
        return c

    stack.extend([
        patch("src.pipeline.trigger.get_db_path", return_value=db_path),
        patch("src.pipeline.trigger._refresh_auth_token", side_effect=_client_factory),
        patch("src.pipeline.trigger.ScoutingCrawler", return_value=mock_crawler),
        patch("src.pipeline.trigger.ScoutingLoader", return_value=mock_loader),
        patch("src.pipeline.trigger.resolve_gc_uuid", return_value=None),
        patch("src.pipeline.trigger._run_spray_stages"),
    ])
    return stack


def test_end_to_end_golden_path_persists_plays_rows(
    tmp_path: Path,
    plays_json_factory,
) -> None:
    """AC-4: plays + play_events rows persisted, status=completed, last_synced set."""
    db_path, team_id, away_id = _make_db_with_tracked_team(tmp_path)
    _seed_game_for_reconcile(
        db_path,
        game_id=_GAME_ID_1,
        home_team_id=team_id,
        away_team_id=away_id,
        perspective_team_id=team_id,
    )
    job_id = _insert_crawl_job(db_path, team_id)
    _insert_scouting_run(db_path, team_id=team_id, season_id=_SEASON_ID)

    cr = _make_crawl_result(team_id, "tracked-opp", [_GAME_ID_1])
    plays_json = plays_json_factory(
        _GAME_ID_1, _PITCHER_1, _BATTER_1, num_plays=3,
    )

    def _fake_get(path, *args, **kwargs):
        if "plays" in path:
            return plays_json
        return {}

    stack: list = []
    _patch_e2e(stack, db_path, cr, _fake_get)
    with stack[0], stack[1], stack[2], stack[3], stack[4], stack[5]:
        trigger.run_scouting_sync(team_id, "tracked-opp", job_id)

    job = _get_crawl_job(db_path, job_id)
    assert job["status"] == "completed"
    assert job["error_message"] is None
    assert _get_last_synced(db_path, team_id) is not None

    with closing(sqlite3.connect(str(db_path))) as conn:
        plays_count = conn.execute(
            "SELECT COUNT(DISTINCT game_id) FROM plays "
            "WHERE perspective_team_id = ?",
            (team_id,),
        ).fetchone()[0]
        assert plays_count == 1
        play_count = conn.execute(
            "SELECT COUNT(*) FROM plays WHERE perspective_team_id = ?",
            (team_id,),
        ).fetchone()[0]
        assert play_count == 3


def test_idempotency_on_rerun_no_new_rows(
    tmp_path: Path,
    plays_json_factory,
) -> None:
    """AC-5: rerun emits no plays HTTP, no new rows."""
    db_path, team_id, away_id = _make_db_with_tracked_team(tmp_path)
    _seed_game_for_reconcile(
        db_path,
        game_id=_GAME_ID_1,
        home_team_id=team_id,
        away_team_id=away_id,
        perspective_team_id=team_id,
    )
    cr = _make_crawl_result(team_id, "tracked-opp", [_GAME_ID_1])
    plays_json = plays_json_factory(
        _GAME_ID_1, _PITCHER_1, _BATTER_1, num_plays=3,
    )

    first_calls: list[str] = []

    def _first_get(path, *args, **kwargs):
        first_calls.append(path)
        if "plays" in path:
            return plays_json
        return {}

    job_id_1 = _insert_crawl_job(db_path, team_id)
    _insert_scouting_run(db_path, team_id=team_id, season_id=_SEASON_ID)

    stack1: list = []
    _patch_e2e(stack1, db_path, cr, _first_get)
    with stack1[0], stack1[1], stack1[2], stack1[3], stack1[4], stack1[5]:
        trigger.run_scouting_sync(team_id, "tracked-opp", job_id_1)

    assert any(_GAME_ID_1 in p for p in first_calls)

    second_calls: list[str] = []

    def _second_get(path, *args, **kwargs):
        second_calls.append(path)
        if "plays" in path:
            return plays_json
        return {}

    job_id_2 = _insert_crawl_job(db_path, team_id)
    cr2 = _make_crawl_result(team_id, "tracked-opp", [_GAME_ID_1])

    stack2: list = []
    _patch_e2e(stack2, db_path, cr2, _second_get)
    with stack2[0], stack2[1], stack2[2], stack2[3], stack2[4], stack2[5]:
        trigger.run_scouting_sync(team_id, "tracked-opp", job_id_2)

    # Second run did not hit the plays endpoint.
    assert not any("plays" in p for p in second_calls)
    job2 = _get_crawl_job(db_path, job_id_2)
    assert job2["status"] == "completed"
    # AC-5 (web): clean rerun must not surface a plays-stage failure via
    # error_message.  _format_plays_error_message returns None when there
    # are no errors/reconcile_errors/deferred, so the value set by
    # _mark_job_terminal('completed', None) must remain.  This is the
    # web-path equivalent of the CLI's "loaded=0 skipped=N" contract --
    # both assert that pre-skipped games are not reported as a failure.
    assert job2["error_message"] is None
    assert _get_last_synced(db_path, team_id) is not None

    # Plays row count unchanged.
    with closing(sqlite3.connect(str(db_path))) as conn:
        play_count = conn.execute(
            "SELECT COUNT(*) FROM plays WHERE perspective_team_id = ?",
            (team_id,),
        ).fetchone()[0]
        assert play_count == 3


def test_auth_expiry_persists_already_loaded_games(
    tmp_path: Path,
    plays_json_factory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC-6: auth-expiry mid-stage persists already-loaded games; error_message has count."""
    db_path, team_id, away_id = _make_db_with_tracked_team(tmp_path)
    _seed_game_for_reconcile(
        db_path,
        game_id=_GAME_ID_1,
        home_team_id=team_id,
        away_team_id=away_id,
        perspective_team_id=team_id,
    )
    _seed_game_for_reconcile(
        db_path,
        game_id=_GAME_ID_2,
        home_team_id=team_id,
        away_team_id=away_id,
        perspective_team_id=team_id,
    )

    cr = _make_crawl_result(
        team_id, "tracked-opp", [_GAME_ID_1, _GAME_ID_2],
    )
    game_1_json = plays_json_factory(
        _GAME_ID_1, _PITCHER_1, _BATTER_1, num_plays=2,
    )
    plays_calls = {"count": 0}

    def _fake_get(path, *args, **kwargs):
        if "plays" not in path:
            return {}
        plays_calls["count"] += 1
        if plays_calls["count"] == 1:
            return game_1_json
        raise CredentialExpiredError("token rejected during plays fetch")

    job_id = _insert_crawl_job(db_path, team_id)
    _insert_scouting_run(db_path, team_id=team_id, season_id=_SEASON_ID)

    import logging
    caplog.set_level(logging.WARNING, logger="src.pipeline.trigger")

    stack: list = []
    _patch_e2e(stack, db_path, cr, _fake_get)
    with stack[0], stack[1], stack[2], stack[3], stack[4], stack[5]:
        trigger.run_scouting_sync(team_id, "tracked-opp", job_id)

    job = _get_crawl_job(db_path, job_id)
    assert job["status"] == "completed"
    assert job["error_message"] is not None
    assert "deferred (auth)" in job["error_message"]
    assert "1 deferred" in job["error_message"]

    # AC-6 Context: web wrapper logs a WARNING naming the deferred game
    # count on the auth-expired path so operators have a discoverable
    # signal (the helper otherwise swallows the auth error).  Greppable
    # token: "PLAYS STAGE auth-expired".
    warning_records = [
        r for r in caplog.records
        if r.levelno == logging.WARNING
        and "PLAYS STAGE auth-expired" in r.getMessage()
    ]
    assert warning_records, [
        (r.levelname, r.getMessage()) for r in caplog.records
    ]
    assert any(
        "1 games deferred" in r.getMessage() for r in warning_records
    ), [r.getMessage() for r in warning_records]
    assert any(
        "idempotent" in r.getMessage() for r in warning_records
    ), [r.getMessage() for r in warning_records]

    with closing(sqlite3.connect(str(db_path))) as conn:
        g1_rows = conn.execute(
            "SELECT COUNT(*) FROM plays "
            "WHERE game_id = ? AND perspective_team_id = ?",
            (_GAME_ID_1, team_id),
        ).fetchone()[0]
        assert g1_rows == 2
        g2_rows = conn.execute(
            "SELECT COUNT(*) FROM plays "
            "WHERE game_id = ? AND perspective_team_id = ?",
            (_GAME_ID_2, team_id),
        ).fetchone()[0]
        assert g2_rows == 0


def test_per_game_http_error_isolation_in_web_path(
    tmp_path: Path,
    plays_json_factory,
) -> None:
    """AC-8 (web path): per-game HTTP error isolates -- one game fails, others load.

    Exercises the real run_plays_stage helper through run_scouting_sync with
    two seeded games: game 1's plays HTTP fetch raises a generic Exception,
    game 2's returns valid JSON.  The wrapper must:

    * Leave the crawl_jobs row at status='completed' (per AC-3 -- helper
      survives per-game errors).
    * UPDATE error_message with the structured "plays: 1/2 loaded, 1 errored"
      prefix (per AC-2 / format-string contract).
    * Persist plays + play_events rows for game 2 only (game 1's HTTP error
      means no JSON to load).
    """
    db_path, team_id, away_id = _make_db_with_tracked_team(tmp_path)
    _seed_game_for_reconcile(
        db_path,
        game_id=_GAME_ID_1,
        home_team_id=team_id,
        away_team_id=away_id,
        perspective_team_id=team_id,
    )
    _seed_game_for_reconcile(
        db_path,
        game_id=_GAME_ID_2,
        home_team_id=team_id,
        away_team_id=away_id,
        perspective_team_id=team_id,
    )

    cr = _make_crawl_result(team_id, "tracked-opp", [_GAME_ID_1, _GAME_ID_2])
    game_2_json = plays_json_factory(
        _GAME_ID_2, _PITCHER_1, _BATTER_1, num_plays=2,
    )

    def _fake_get(path, *args, **kwargs):
        if "plays" not in path:
            return {}
        # Differentiate by game_id in URL path
        # (/game-stream-processing/{game_id}/plays).
        if _GAME_ID_1 in path:
            raise RuntimeError("simulated HTTP failure for game 1")
        if _GAME_ID_2 in path:
            return game_2_json
        return {}

    job_id = _insert_crawl_job(db_path, team_id)
    _insert_scouting_run(db_path, team_id=team_id, season_id=_SEASON_ID)

    stack: list = []
    _patch_e2e(stack, db_path, cr, _fake_get)
    with stack[0], stack[1], stack[2], stack[3], stack[4], stack[5]:
        trigger.run_scouting_sync(team_id, "tracked-opp", job_id)

    job = _get_crawl_job(db_path, job_id)
    # AC-3: wrapper survives helper-internal per-game isolation.
    assert job["status"] == "completed"
    # AC-2 / format-string: 1 of 2 loaded, 1 errored.
    assert job["error_message"] is not None
    assert "plays: 1/2 loaded" in job["error_message"]
    assert "1 errored" in job["error_message"]

    with closing(sqlite3.connect(str(db_path))) as conn:
        # Game 1: HTTP error -- no plays inserted.
        g1_plays = conn.execute(
            "SELECT COUNT(*) FROM plays "
            "WHERE game_id = ? AND perspective_team_id = ?",
            (_GAME_ID_1, team_id),
        ).fetchone()[0]
        assert g1_plays == 0
        g1_events = conn.execute(
            "SELECT COUNT(*) FROM play_events pe "
            "JOIN plays p ON pe.play_id = p.id "
            "WHERE p.game_id = ? AND p.perspective_team_id = ?",
            (_GAME_ID_1, team_id),
        ).fetchone()[0]
        assert g1_events == 0

        # Game 2: plays + events loaded successfully.
        g2_plays = conn.execute(
            "SELECT COUNT(*) FROM plays "
            "WHERE game_id = ? AND perspective_team_id = ?",
            (_GAME_ID_2, team_id),
        ).fetchone()[0]
        assert g2_plays == 2
        g2_events = conn.execute(
            "SELECT COUNT(*) FROM play_events pe "
            "JOIN plays p ON pe.play_id = p.id "
            "WHERE p.game_id = ? AND p.perspective_team_id = ?",
            (_GAME_ID_2, team_id),
        ).fetchone()[0]
        assert g2_events > 0


# ---------------------------------------------------------------------------
# AC-7: scout-load failure short-circuits before plays-stage
# ---------------------------------------------------------------------------


def test_scout_load_failure_skips_plays_stage(tmp_path: Path) -> None:
    """AC-7: when crawl_result has errors and 0 games_crawled, plays not invoked."""
    db_path, team_id, _ = _make_db_with_tracked_team(tmp_path)
    job_id = _insert_crawl_job(db_path, team_id)

    failed_cr = ScoutingCrawlResult(
        team_id=team_id,
        season_id=_SEASON_ID,
        public_id="tracked-opp",
        games=[],
        roster=[],
        boxscores={},
        games_crawled=0,
        errors=2,
    )
    mock_crawler = MagicMock()
    mock_crawler.scout_team.return_value = failed_cr
    mock_loader = MagicMock()

    helper_mock = MagicMock()

    with (
        patch("src.pipeline.trigger.get_db_path", return_value=db_path),
        patch("src.pipeline.trigger._refresh_auth_token"),
        patch("src.pipeline.trigger.ScoutingCrawler", return_value=mock_crawler),
        patch("src.pipeline.trigger.ScoutingLoader", return_value=mock_loader),
        patch("src.pipeline.trigger.run_plays_stage", helper_mock),
    ):
        trigger.run_scouting_sync(team_id, "tracked-opp", job_id)

    helper_mock.assert_not_called()
    job = _get_crawl_job(db_path, job_id)
    assert job["status"] == "failed"


# ---------------------------------------------------------------------------
# AC-8: format-string helper unit-test the rule
# ---------------------------------------------------------------------------


def test_format_plays_error_message_returns_none_when_clean() -> None:
    """Clean result yields None (caller skips UPDATE)."""
    result = PlaysStageResult(
        attempted=5, loaded=5, skipped=0, errored=0,
        reconcile_errors=0, auth_expired=False, deferred_game_ids=[],
    )
    assert trigger._format_plays_error_message(result) is None


def test_format_plays_error_message_orders_fragments() -> None:
    """Multi-failure prefix orders fragments: errored, reconcile, deferred."""
    result = PlaysStageResult(
        attempted=14, loaded=8, skipped=0, errored=2,
        reconcile_errors=2, auth_expired=True,
        deferred_game_ids=[_GAME_ID_2, _GAME_ID_3],
    )
    msg = trigger._format_plays_error_message(result)
    assert msg == (
        "plays: 8/14 loaded, 2 errored, 2 reconcile errors, 2 deferred (auth)"
    )
