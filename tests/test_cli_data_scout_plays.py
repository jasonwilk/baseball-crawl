"""Tests for `bb data scout` plays-stage wiring (E-229-02).

Covers:
- AC-1: helper invoked per scouted team with sorted game_ids.
- AC-2: typer.echo summary surfaces loaded/skipped/errored/reconcile_errors/deferred.
- AC-3: auth-expiry summary names deferred count + actionable message.
- AC-4: helper-raises-unexpected-exception keeps exit_code unchanged + greppable
  PLAYS STAGE FAILED token.
- AC-5: end-to-end golden path -- plays + play_events rows persisted, CLI exits 0.
- AC-6: idempotency on rerun -- zero new HTTP, zero new rows.
- AC-7: auth-expiry mid-stage persists already-loaded games, exit code unchanged.
- AC-8: --help subprocess smoke test.
- AC-9: bulk mode invokes the helper once per team with each team's args.

All HTTP calls are mocked.  No real network or scouting-pipeline I/O.
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from migrations.apply_migrations import run_migrations
from src.cli import app
from src.gamechanger.client import CredentialExpiredError
from src.gamechanger.crawlers.scouting import ScoutingCrawlResult
from src.gamechanger.pipelines import PlaysStageResult


runner = CliRunner()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEASON_ID = "2026-spring-hs"
_GAME_ID_1 = "11111111-1111-1111-1111-111111111111"
_GAME_ID_2 = "22222222-2222-2222-2222-222222222222"
_GAME_ID_3 = "33333333-3333-3333-3333-333333333333"
_BATTER_1 = "ba000001-aaaa-bbbb-cccc-000000000001"
_PITCHER_1 = "01000001-aaaa-bbbb-cccc-000000000001"

_FAKE_CREDENTIALS = {
    "GAMECHANGER_REFRESH_TOKEN_WEB": "fake-refresh-token",
    "GAMECHANGER_CLIENT_ID_WEB": "07cb985d-ff6c-429d-992c-b8a0d44e6fc3",
    "GAMECHANGER_CLIENT_KEY_WEB": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    "GAMECHANGER_DEVICE_ID_WEB": "abcdefabcdefabcdefabcdefabcdefab",
    "GAMECHANGER_BASE_URL": "https://api.team-manager.gc.com",
    "GAMECHANGER_APP_NAME_WEB": "web",
}


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def _patch_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.gamechanger.client.dotenv_values",
        lambda *_a, **_kw: _FAKE_CREDENTIALS,
    )


def _patch_token_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_tm = MagicMock()
    mock_tm.get_access_token.return_value = "fake-access-token"
    mock_tm.force_refresh.return_value = "fake-access-token"
    monkeypatch.setattr("src.gamechanger.client.TokenManager", lambda **_: mock_tm)


def _make_crawl_result(
    *,
    public_id: str,
    team_id: int,
    game_ids: list[str],
    errors: int = 0,
) -> ScoutingCrawlResult:
    """Build a non-empty ScoutingCrawlResult with deterministic boxscore keys.

    ``errors`` defaults to 0 (success).  Pass ``errors>0`` to simulate a
    partially-failed scout where the crawl produced some boxscores but the
    load reported errors -- i.e., a team whose plays stage MUST be skipped
    by the per-team gate in ``_scout_live``.
    """
    return ScoutingCrawlResult(
        team_id=team_id,
        season_id=_SEASON_ID,
        public_id=public_id,
        games=[{"id": gid, "game_status": "completed"} for gid in game_ids],
        roster=[],
        boxscores={gid: {} for gid in game_ids},
        games_crawled=len(game_ids),
        errors=errors,
    )


def _mock_spray_result() -> MagicMock:
    r = MagicMock()
    r.files_written = 0
    r.files_skipped = 0
    r.errors = 0
    r.games_crawled = 0
    r.games_skipped = 0
    r.spray_data = {}
    return r


@pytest.fixture()
def fresh_db(tmp_path: Path) -> Path:
    """Apply migrations and return the DB path."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    return db_path


@pytest.fixture()
def seeded_db(
    fresh_db: Path,
    seed_boxscore_for_plays,
) -> tuple[Path, int, int]:
    """Seed teams, season, players, and a games + boxscore row for one game.

    Returns (db_path, perspective_team_id, opponent_team_id).
    """
    conn = sqlite3.connect(str(fresh_db))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, public_id, is_active) "
        "VALUES (?, 'tracked', ?, ?, 1)",
        ("Tracked Opponent", "aaaa1111-cccc-dddd-eeee-ffff00000001", "tracked-opp"),
    )
    conn.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) "
        "VALUES (?, 'tracked', ?, 1)",
        ("Other Side", "aaaa2222-cccc-dddd-eeee-ffff00000002"),
    )
    home = conn.execute(
        "SELECT id FROM teams WHERE public_id = ?", ("tracked-opp",)
    ).fetchone()[0]
    away = conn.execute(
        "SELECT id FROM teams WHERE name = ?", ("Other Side",)
    ).fetchone()[0]
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, ?, ?, ?)",
        (_SEASON_ID, "Spring 2026 HS", "spring-hs", 2026),
    )
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES (?, ?, ?)",
        (_BATTER_1, "Batter", "One"),
    )
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES (?, ?, ?)",
        (_PITCHER_1, "Pitcher", "One"),
    )
    conn.commit()

    seed_boxscore_for_plays(
        conn,
        game_id=_GAME_ID_1,
        home_team_id=home,
        away_team_id=away,
        season_id=_SEASON_ID,
        perspective_team_id=home,
        pitcher_appearances=[
            {
                "team_id": away,
                "player_id": _PITCHER_1,
                "appearance_order": 1,
                "ip_outs": 6,
                "bf": 2,
                "pitches": 6,
                "total_strikes": 4,
            },
        ],
        batter_appearances=[
            {"team_id": away, "player_id": _BATTER_1, "ab": 2, "h": 2},
        ],
    )
    conn.close()
    return fresh_db, home, away


# ---------------------------------------------------------------------------
# AC-1 + AC-2: helper invoked per team; summary surfaces all counters
# ---------------------------------------------------------------------------


def test_helper_invoked_per_team_with_sorted_game_ids(
    monkeypatch: pytest.MonkeyPatch,
    fresh_db: Path,
) -> None:
    """AC-1: run_plays_stage called once per scouted team with sorted game IDs."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    cr = _make_crawl_result(
        public_id="opp-x",
        team_id=42,
        game_ids=[_GAME_ID_2, _GAME_ID_1],  # unsorted on purpose
    )
    mock_crawler = MagicMock()
    mock_crawler.scout_team.return_value = cr
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_team.return_value = _mock_spray_result()

    # Games-count semantics: loaded <= attempted is invariant.  Use a valid
    # all-loaded shape (attempted == loaded == 2).
    helper_mock = MagicMock(
        return_value=PlaysStageResult(
            attempted=2, loaded=2, skipped=0, errored=0,
            reconcile_errors=0, auth_expired=False, deferred_game_ids=[],
        ),
    )

    with (
        patch("src.gamechanger.client.GameChangerClient"),
        patch(
            "src.gamechanger.crawlers.scouting.ScoutingCrawler",
            return_value=mock_crawler,
        ),
        patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"),
        patch("src.cli.data._load_scouted_team_in_memory", return_value=0),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch("src.cli.data._resolve_db_path", return_value=fresh_db),
        patch("src.gamechanger.pipelines.run_plays_stage", helper_mock),
    ):
        result = runner.invoke(app, ["data", "scout", "--team", "opp-x"])

    assert result.exit_code == 0, result.output
    helper_mock.assert_called_once()
    _, kwargs = helper_mock.call_args
    assert kwargs["perspective_team_id"] == 42
    assert kwargs["public_id"] == "opp-x"
    # Sorted order is required for the parity-test contract.
    assert kwargs["game_ids"] == sorted([_GAME_ID_1, _GAME_ID_2])
    # AC-2: summary surfaces all counters.
    assert "Plays stage for opp-x:" in result.output
    assert "loaded=2" in result.output
    assert "skipped=0" in result.output
    assert "errored=0" in result.output
    assert "reconcile_errors=0" in result.output
    assert "deferred=0" in result.output


# ---------------------------------------------------------------------------
# AC-3: auth-expiry summary names deferred count + actionable message
# ---------------------------------------------------------------------------


def test_auth_expiry_summary_names_deferred_and_actionable_message(
    monkeypatch: pytest.MonkeyPatch,
    fresh_db: Path,
) -> None:
    """AC-3: when helper returns auth_expired=True, summary names count + bb creds setup web."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    cr = _make_crawl_result(
        public_id="opp-x",
        team_id=42,
        game_ids=[_GAME_ID_1, _GAME_ID_2, _GAME_ID_3],
    )
    mock_crawler = MagicMock()
    mock_crawler.scout_team.return_value = cr
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_team.return_value = _mock_spray_result()

    helper_mock = MagicMock(
        return_value=PlaysStageResult(
            attempted=3, loaded=2, skipped=0, errored=0,
            reconcile_errors=0, auth_expired=True,
            deferred_game_ids=[_GAME_ID_2, _GAME_ID_3],
        ),
    )

    with (
        patch("src.gamechanger.client.GameChangerClient"),
        patch(
            "src.gamechanger.crawlers.scouting.ScoutingCrawler",
            return_value=mock_crawler,
        ),
        patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"),
        patch("src.cli.data._load_scouted_team_in_memory", return_value=0),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch("src.cli.data._resolve_db_path", return_value=fresh_db),
        patch("src.gamechanger.pipelines.run_plays_stage", helper_mock),
    ):
        result = runner.invoke(app, ["data", "scout", "--team", "opp-x"])

    # CLI did not crash.
    assert result.exit_code == 0, result.output
    # AC-3: deferred count appears in the line (via the base `deferred={N}`),
    # plus the actionable command and idempotency reassurance.
    assert "deferred=2" in result.output
    assert "bb creds setup web" in result.output
    assert "re-running scout is idempotent" in result.output


# ---------------------------------------------------------------------------
# AC-4: helper-raises-unexpected-exception keeps exit_code unchanged
# ---------------------------------------------------------------------------


def test_helper_raises_unexpected_exception_cli_still_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
    fresh_db: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC-4: helper unexpected exception logs PLAYS STAGE FAILED, exit_code unchanged."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    cr = _make_crawl_result(
        public_id="opp-x", team_id=42, game_ids=[_GAME_ID_1],
    )
    mock_crawler = MagicMock()
    mock_crawler.scout_team.return_value = cr
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_team.return_value = _mock_spray_result()

    helper_mock = MagicMock(side_effect=RuntimeError("simulated helper crash"))

    import logging
    caplog.set_level(logging.WARNING, logger="src.cli.data")

    with (
        patch("src.gamechanger.client.GameChangerClient"),
        patch(
            "src.gamechanger.crawlers.scouting.ScoutingCrawler",
            return_value=mock_crawler,
        ),
        patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"),
        patch("src.cli.data._load_scouted_team_in_memory", return_value=0),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch("src.cli.data._resolve_db_path", return_value=fresh_db),
        patch("src.gamechanger.pipelines.run_plays_stage", helper_mock),
    ):
        result = runner.invoke(app, ["data", "scout", "--team", "opp-x"])

    # CLI exit code unchanged from its post-dedup value (0 here).
    assert result.exit_code == 0, result.output
    # Greppable token must be in the WARNING log line.
    assert any(
        "PLAYS STAGE FAILED" in record.getMessage()
        for record in caplog.records
    ), [r.getMessage() for r in caplog.records]


# ---------------------------------------------------------------------------
# AC-5 + AC-6 + AC-7: end-to-end DB-write golden path, idempotency, auth-expiry
# ---------------------------------------------------------------------------


def _patch_for_e2e(
    stack: list,
    db_path: Path,
    crawl_result: ScoutingCrawlResult,
    fake_get,
):
    """Common patches for end-to-end tests where the real helper runs.

    ``fake_get`` is a callable invoked as ``fake_get(path, *args, **kwargs)``
    that returns the canned plays JSON or raises an exception.  It replaces
    ``GameChangerClient.get`` on the constructed mock client.
    """
    mock_crawler = MagicMock()
    mock_crawler.scout_team.return_value = crawl_result
    mock_crawler.scout_all_in_memory.return_value = [crawl_result]
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_team.return_value = _mock_spray_result()

    # Mock GC client class: every instantiation returns a MagicMock whose
    # `.get(...)` invokes fake_get.  This isolates the helper from real HTTP.
    def _client_factory(*args, **kwargs):
        c = MagicMock()
        c.get.side_effect = fake_get
        return c

    stack.extend([
        patch("src.gamechanger.client.GameChangerClient", side_effect=_client_factory),
        patch(
            "src.gamechanger.crawlers.scouting.ScoutingCrawler",
            return_value=mock_crawler,
        ),
        patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"),
        patch("src.cli.data._load_scouted_team_in_memory", return_value=0),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch("src.cli.data._resolve_db_path", return_value=db_path),
    ])
    return stack


def test_end_to_end_golden_path_persists_plays_rows(
    monkeypatch: pytest.MonkeyPatch,
    seeded_db: tuple[Path, int, int],
    plays_json_factory,
) -> None:
    """AC-5: plays + play_events rows persisted; CLI exits 0."""
    db_path, perspective_team_id, _ = seeded_db
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    cr = _make_crawl_result(
        public_id="tracked-opp",
        team_id=perspective_team_id,
        game_ids=[_GAME_ID_1],
    )

    plays_json = plays_json_factory(
        _GAME_ID_1, _PITCHER_1, _BATTER_1, num_plays=3,
    )

    call_log: list[str] = []

    def _fake_get(path, *args, **kwargs):
        call_log.append(path)
        return plays_json

    stack: list = []
    _patch_for_e2e(stack, db_path, cr, _fake_get)
    with stack[0], stack[1], stack[2], stack[3], stack[4], stack[5]:
        result = runner.invoke(app, ["data", "scout", "--team", "tracked-opp"])

    assert result.exit_code == 0, result.output
    assert any(_GAME_ID_1 in p for p in call_log)

    conn = sqlite3.connect(str(db_path))
    plays_count = conn.execute(
        "SELECT COUNT(DISTINCT game_id) FROM plays "
        "WHERE perspective_team_id = ?",
        (perspective_team_id,),
    ).fetchone()[0]
    assert plays_count == 1
    play_count = conn.execute(
        "SELECT COUNT(*) FROM plays WHERE perspective_team_id = ?",
        (perspective_team_id,),
    ).fetchone()[0]
    assert play_count == 3
    conn.close()


def test_idempotency_on_rerun_no_new_rows(
    monkeypatch: pytest.MonkeyPatch,
    seeded_db: tuple[Path, int, int],
    plays_json_factory,
) -> None:
    """AC-6: rerun emits no new HTTP, no new rows; summary shows loaded=0."""
    db_path, perspective_team_id, _ = seeded_db
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    cr = _make_crawl_result(
        public_id="tracked-opp",
        team_id=perspective_team_id,
        game_ids=[_GAME_ID_1],
    )
    plays_json = plays_json_factory(
        _GAME_ID_1, _PITCHER_1, _BATTER_1, num_plays=3,
    )

    first_calls: list[str] = []

    def _first_get(path, *args, **kwargs):
        first_calls.append(path)
        return plays_json

    # First invocation: full work.
    stack: list = []
    _patch_for_e2e(stack, db_path, cr, _first_get)
    with stack[0], stack[1], stack[2], stack[3], stack[4], stack[5]:
        first = runner.invoke(app, ["data", "scout", "--team", "tracked-opp"])
    assert first.exit_code == 0, first.output
    assert any(_GAME_ID_1 in p for p in first_calls)

    # Second invocation against the SAME db: pre-fetch DB skip, no new HTTP
    # to the plays endpoint.
    cr2 = _make_crawl_result(
        public_id="tracked-opp",
        team_id=perspective_team_id,
        game_ids=[_GAME_ID_1],
    )
    second_calls: list[str] = []

    def _second_get(path, *args, **kwargs):
        second_calls.append(path)
        return plays_json

    stack2: list = []
    _patch_for_e2e(stack2, db_path, cr2, _second_get)
    with stack2[0], stack2[1], stack2[2], stack2[3], stack2[4], stack2[5]:
        second = runner.invoke(app, ["data", "scout", "--team", "tracked-opp"])
    assert second.exit_code == 0, second.output

    # No HTTP fetches to the plays endpoint on rerun.
    assert not any("plays" in p for p in second_calls)
    assert "loaded=0" in second.output
    # AC-6: pre-skipped games must fold into the skipped count surfaced by
    # the typer.echo summary.  Without this assertion, the F2 bug
    # (pre_skipped not folded into skipped) would slip past E2E coverage.
    expected_skipped = len(cr2.games)
    assert f"skipped={expected_skipped}" in second.output
    # Plays row count unchanged.
    conn = sqlite3.connect(str(db_path))
    play_count = conn.execute(
        "SELECT COUNT(*) FROM plays WHERE perspective_team_id = ?",
        (perspective_team_id,),
    ).fetchone()[0]
    assert play_count == 3
    conn.close()


def test_auth_expiry_persists_already_loaded_games(
    monkeypatch: pytest.MonkeyPatch,
    seeded_db: tuple[Path, int, int],
    plays_json_factory,
) -> None:
    """AC-7: auth expiry mid-stage persists loaded games; CLI exits 0."""
    db_path, perspective_team_id, away_id = seeded_db
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    # Seed a second game so the helper has two to iterate.
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, status) "
        "VALUES (?, ?, ?, ?, ?, 'completed')",
        (_GAME_ID_2, _SEASON_ID, "2026-04-12", perspective_team_id, away_id),
    )
    conn.commit()
    conn.close()

    cr = _make_crawl_result(
        public_id="tracked-opp",
        team_id=perspective_team_id,
        game_ids=[_GAME_ID_1, _GAME_ID_2],
    )

    game_1_json = plays_json_factory(
        _GAME_ID_1, _PITCHER_1, _BATTER_1, num_plays=2,
    )

    plays_calls = {"count": 0}

    def _fake_get(path, *args, **kwargs):
        # Only intercept the plays endpoint; other calls return empty dict.
        if "plays" not in path:
            return {}
        plays_calls["count"] += 1
        if plays_calls["count"] == 1:
            return game_1_json
        raise CredentialExpiredError("token rejected during plays fetch")

    stack: list = []
    _patch_for_e2e(stack, db_path, cr, _fake_get)
    with stack[0], stack[1], stack[2], stack[3], stack[4], stack[5]:
        result = runner.invoke(app, ["data", "scout", "--team", "tracked-opp"])

    assert result.exit_code == 0, result.output
    # First game's plays are persisted.
    conn = sqlite3.connect(str(db_path))
    g1_rows = conn.execute(
        "SELECT COUNT(*) FROM plays "
        "WHERE game_id = ? AND perspective_team_id = ?",
        (_GAME_ID_1, perspective_team_id),
    ).fetchone()[0]
    assert g1_rows == 2
    g2_rows = conn.execute(
        "SELECT COUNT(*) FROM plays "
        "WHERE game_id = ? AND perspective_team_id = ?",
        (_GAME_ID_2, perspective_team_id),
    ).fetchone()[0]
    assert g2_rows == 0
    conn.close()
    # Summary surfaces the deferred count and the actionable message.
    assert "deferred=1" in result.output
    assert "bb creds setup web" in result.output


# ---------------------------------------------------------------------------
# AC-8: subprocess --help smoke test (console-script entry point)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("bb") is None, reason="bb not installed")
def test_bb_data_scout_help_subprocess() -> None:
    """The console script entry point loads without import errors.

    Invokes the actual `bb` console-script shim from pyproject.toml
    [project.scripts] (per .claude/rules/testing.md).  Running via
    `python -m src.cli ...` would bypass the shim and inherit pytest's
    sys.path, masking packaging/install regressions.
    """
    result = subprocess.run(
        ["bb", "data", "scout", "--help"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, (
        f"bb data scout --help failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    assert "scout" in result.stdout.lower()


# ---------------------------------------------------------------------------
# AC-9: bulk mode -- helper invoked once per scouted team
# ---------------------------------------------------------------------------


def test_bulk_mode_invokes_helper_per_team(
    monkeypatch: pytest.MonkeyPatch,
    fresh_db: Path,
) -> None:
    """AC-9: bb data scout (no --team) calls run_plays_stage once per crawl_result."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    cr_a = _make_crawl_result(
        public_id="opp-a", team_id=11, game_ids=[_GAME_ID_1],
    )
    cr_b = _make_crawl_result(
        public_id="opp-b", team_id=22, game_ids=[_GAME_ID_2, _GAME_ID_3],
    )
    mock_crawler = MagicMock()
    mock_crawler.scout_all_in_memory.return_value = [cr_a, cr_b]
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_team.return_value = _mock_spray_result()

    captured_calls: list = []

    def _capture(*args, **kwargs):
        captured_calls.append(kwargs)
        return PlaysStageResult(
            attempted=len(kwargs["game_ids"]),
            loaded=len(kwargs["game_ids"]),
            skipped=0, errored=0, reconcile_errors=0,
            auth_expired=False, deferred_game_ids=[],
        )

    helper_mock = MagicMock(side_effect=_capture)

    with (
        patch("src.gamechanger.client.GameChangerClient"),
        patch(
            "src.gamechanger.crawlers.scouting.ScoutingCrawler",
            return_value=mock_crawler,
        ),
        patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"),
        patch("src.cli.data._load_scouted_team_in_memory", return_value=0),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch("src.cli.data._resolve_db_path", return_value=fresh_db),
        patch("src.gamechanger.pipelines.run_plays_stage", helper_mock),
    ):
        result = runner.invoke(app, ["data", "scout"])

    assert result.exit_code == 0, result.output
    assert helper_mock.call_count == 2
    by_team = {kw["public_id"]: kw for kw in captured_calls}
    assert by_team["opp-a"]["perspective_team_id"] == 11
    assert by_team["opp-a"]["game_ids"] == [_GAME_ID_1]
    assert by_team["opp-b"]["perspective_team_id"] == 22
    assert by_team["opp-b"]["game_ids"] == sorted([_GAME_ID_2, _GAME_ID_3])
    # Both teams' summary lines emitted.
    assert "Plays stage for opp-a:" in result.output
    assert "Plays stage for opp-b:" in result.output


# ---------------------------------------------------------------------------
# Plays stage per-team gating: empty crawl_results / mixed outcomes
# ---------------------------------------------------------------------------
#
# Per-team gating contract (E-229-02): the plays stage runs unconditionally
# at the orchestrator level and gates per-team on the per-iteration check
# (`cr_public_id`, `cr_team_id`, `cr_boxscores` presence).  This mirrors
# the web path (`run_scouting_sync`), which is invoked once per team and
# has no aggregate exit_code to gate against.  Aggregate gating regressed
# CLI/web parity in bulk mode -- one team's scout failure caused plays to
# be skipped for every other successful team in the same batch.


def test_plays_stage_not_called_when_crawl_results_empty_after_pipeline_raises(
    monkeypatch: pytest.MonkeyPatch,
    fresh_db: Path,
) -> None:
    """When `_run_scout_pipeline` raises, `crawl_results` stays [].

    The plays loop iterates 0 times and `run_plays_stage` is never called.
    The pre-loop ``crawl_results: list = []`` initialization protects
    against NameError when the pipeline raises before populating the list.
    """
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    helper_mock = MagicMock()  # MUST NOT be called.
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_team.return_value = _mock_spray_result()

    with (
        patch("src.gamechanger.client.GameChangerClient"),
        patch("src.gamechanger.crawlers.scouting.ScoutingCrawler"),
        patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch("src.cli.data._resolve_db_path", return_value=fresh_db),
        # Force the scout pipeline to raise.  The CLI catches this, sets
        # exit_code=1, and the plays loop iterates over the empty
        # crawl_results list.
        patch(
            "src.cli.data._run_scout_pipeline",
            side_effect=RuntimeError("simulated scout failure"),
        ),
        patch("src.gamechanger.pipelines.run_plays_stage", helper_mock),
    ):
        result = runner.invoke(app, ["data", "scout", "--team", "opp-x"])

    # Scout failure surfaces a non-zero exit code.
    assert result.exit_code != 0, result.output
    # Plays stage MUST NOT have been invoked: the loop saw zero crawl_results.
    helper_mock.assert_not_called()


def test_plays_stage_not_called_when_crawl_results_empty_with_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch,
    fresh_db: Path,
) -> None:
    """When `_run_scout_pipeline` returns (1, []), plays stage MUST NOT run.

    Companion to the raises-case test: covers the path where scout reports
    failure cleanly (non-zero exit_code, empty crawl_results) instead of
    raising.  The empty crawl_results list -- not the exit_code -- is what
    correctly skips the plays loop.
    """
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    helper_mock = MagicMock()  # MUST NOT be called.
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_team.return_value = _mock_spray_result()

    with (
        patch("src.gamechanger.client.GameChangerClient"),
        patch("src.gamechanger.crawlers.scouting.ScoutingCrawler"),
        patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch("src.cli.data._resolve_db_path", return_value=fresh_db),
        # Scout pipeline reports failure cleanly (no exception).
        patch(
            "src.cli.data._run_scout_pipeline",
            return_value=(1, []),
        ),
        patch("src.gamechanger.pipelines.run_plays_stage", helper_mock),
    ):
        result = runner.invoke(app, ["data", "scout", "--team", "opp-x"])

    assert result.exit_code != 0, result.output
    helper_mock.assert_not_called()


def test_plays_stage_skipped_per_team_when_team_load_errored(
    monkeypatch: pytest.MonkeyPatch,
    fresh_db: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Bulk-mode partial failure: plays MUST be skipped per-team when cr.errors > 0.

    Production shape: in bulk mode, ``_run_scout_pipeline`` returns ALL
    attempted teams' crawl_results, including teams whose load reported
    errors (those teams have ``cr.errors > 0`` and may have partially-loaded
    boxscores).  Running the plays stage against partial state corrupts
    downstream reconciliation.

    The CLI must mirror the web path's per-team contract: skip plays for
    teams with ``cr.errors > 0`` and run plays for teams with ``cr.errors == 0``.
    Aggregate gating (``if exit_code == 0:``) would over-skip in bulk mode --
    one team's failure would silence plays for every other team in the same
    batch.  Removing the ``cr.errors`` gate entirely would under-skip and
    run plays against partial state.  This test guards the narrow correct
    behavior between those two failure modes.
    """
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    # Bulk mode (no --team).  Team A's load errored mid-crawl -- its
    # crawl_result is INCLUDED in the returned list (production shape) with
    # `errors=2` and a partial boxscores dict.  Team B succeeded with full
    # boxscores and `errors=0`.
    cr_a_failed = _make_crawl_result(
        public_id="failing-team",
        team_id=11,
        game_ids=[_GAME_ID_1],  # partial -- only one boxscore loaded
        errors=2,
    )
    cr_b_succeeded = _make_crawl_result(
        public_id="succeeding-team",
        team_id=22,
        game_ids=[_GAME_ID_2, _GAME_ID_3],
        errors=0,
    )
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_team.return_value = _mock_spray_result()

    captured_calls: list = []

    def _capture(*args, **kwargs):
        captured_calls.append(kwargs)
        return PlaysStageResult(
            attempted=len(kwargs["game_ids"]),
            loaded=len(kwargs["game_ids"]),
            skipped=0, errored=0, reconcile_errors=0,
            auth_expired=False, deferred_game_ids=[],
        )

    helper_mock = MagicMock(side_effect=_capture)

    import logging
    caplog.set_level(logging.WARNING, logger="src.cli.data")

    with (
        patch("src.gamechanger.client.GameChangerClient"),
        patch("src.gamechanger.crawlers.scouting.ScoutingCrawler"),
        patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch("src.cli.data._resolve_db_path", return_value=fresh_db),
        # exit_code=1 (team A failed) and BOTH teams' crawl_results are
        # present in the returned list -- this matches what
        # `_run_scout_pipeline` actually does in production.
        patch(
            "src.cli.data._run_scout_pipeline",
            return_value=(1, [cr_a_failed, cr_b_succeeded]),
        ),
        patch("src.gamechanger.pipelines.run_plays_stage", helper_mock),
    ):
        result = runner.invoke(app, ["data", "scout"])

    # CLI exits with the aggregate exit_code -- plays must not change it.
    assert result.exit_code == 1, result.output
    # Plays MUST have run exactly once -- for the succeeding team only.
    # The failing team is naturally skipped by the per-team `cr.errors > 0`
    # gate, NOT by an aggregate exit_code check.
    assert helper_mock.call_count == 1
    kwargs = captured_calls[0]
    assert kwargs["public_id"] == "succeeding-team"
    assert kwargs["perspective_team_id"] == 22
    assert kwargs["game_ids"] == sorted([_GAME_ID_2, _GAME_ID_3])
    # The failing team's public_id MUST NOT appear in plays-stage call args.
    assert all(kw["public_id"] != "failing-team" for kw in captured_calls)
    # Summary output: succeeding team's line is emitted; failing team's is not.
    assert "Plays stage for succeeding-team:" in result.output
    assert "Plays stage for failing-team:" not in result.output
    # WARNING log line names the failing team and the error count -- this is
    # the operator's signal that plays was deliberately skipped, not silently
    # dropped.
    skip_records = [
        r for r in caplog.records
        if "Skipping plays stage" in r.getMessage()
    ]
    assert len(skip_records) == 1, [r.getMessage() for r in caplog.records]
    skip_msg = skip_records[0].getMessage()
    assert "failing-team" in skip_msg
    assert "2 error" in skip_msg  # matches "2 error(s)"
