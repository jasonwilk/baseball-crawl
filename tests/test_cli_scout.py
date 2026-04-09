"""Tests for the `bb data scout` CLI command (E-097-03).

Covers:
- AC-14: --dry-run produces no API calls
- AC-14: --team filters to a single opponent by public_id
- AC-17: get_public() sends no auth headers (gc-token, gc-device-id)

All HTTP calls are mocked. No real network or DB interactions in CLI dry-run tests.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx
from typer.testing import CliRunner

from src.cli import app
from src.gamechanger.crawlers.scouting import ScoutingCrawlResult


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

runner = CliRunner()

_FAKE_CREDENTIALS = {
    "GAMECHANGER_REFRESH_TOKEN_WEB": "fake-refresh-token",
    "GAMECHANGER_CLIENT_ID_WEB": "07cb985d-ff6c-429d-992c-b8a0d44e6fc3",
    "GAMECHANGER_CLIENT_KEY_WEB": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    "GAMECHANGER_DEVICE_ID_WEB": "abcdefabcdefabcdefabcdefabcdefab",
    "GAMECHANGER_BASE_URL": "https://api.team-manager.gc.com",
    "GAMECHANGER_APP_NAME_WEB": "web",
}


def _patch_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch dotenv_values so no real .env is required."""
    monkeypatch.setattr(
        "src.gamechanger.client.dotenv_values",
        lambda *_a, **_kw: _FAKE_CREDENTIALS,
    )


def _patch_token_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch TokenManager to avoid real POST /auth flows."""
    mock_tm = MagicMock()
    mock_tm.get_access_token.return_value = "fake-access-token"
    mock_tm.force_refresh.return_value = "fake-access-token"
    monkeypatch.setattr("src.gamechanger.client.TokenManager", lambda **_: mock_tm)


# ---------------------------------------------------------------------------
# AC-14: --dry-run tests
# ---------------------------------------------------------------------------


def test_scout_dry_run_no_client_instantiated(monkeypatch: pytest.MonkeyPatch) -> None:
    """--dry-run exits before instantiating GameChangerClient."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    with patch("src.gamechanger.client.GameChangerClient") as MockClient, \
         patch("src.cli.data._resolve_db_path", return_value=Path("/tmp/test.db")):
        result = runner.invoke(app, ["data", "scout", "--dry-run"])

    assert result.exit_code == 0
    assert "Dry run" in result.output
    MockClient.assert_not_called()


def test_scout_dry_run_with_team_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """--dry-run --team shows which opponent would be scouted."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    with patch("src.cli.data._resolve_db_path", return_value=Path("/tmp/test.db")):
        result = runner.invoke(app, ["data", "scout", "--dry-run", "--team", "abc123"])

    assert result.exit_code == 0
    assert "abc123" in result.output


def test_scout_dry_run_with_season_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """--dry-run --season shows the season override."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    with patch("src.cli.data._resolve_db_path", return_value=Path("/tmp/test.db")):
        result = runner.invoke(
            app, ["data", "scout", "--dry-run", "--season", "2025-spring-hs"]
        )

    assert result.exit_code == 0
    assert "2025-spring-hs" in result.output


# ---------------------------------------------------------------------------
# AC-14: --team flag routes to scout_team()
# ---------------------------------------------------------------------------


def test_scout_team_flag_calls_scout_team(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--team <public_id> calls crawler.scout_team(public_id) not scout_all()."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.crawlers import CrawlResult

    mock_crawler = MagicMock()
    mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025-spring-hs", games_crawled=3)

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    # Patch at source location since imports happen inside the function body.
    with patch("src.gamechanger.client.GameChangerClient"), \
         patch("src.gamechanger.crawlers.scouting.ScoutingCrawler", return_value=mock_crawler), \
         patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"), \
         patch("src.cli.data._resolve_db_path", return_value=db_path):
        result = runner.invoke(app, ["data", "scout", "--team", "mypubid"])

    mock_crawler.scout_team.assert_called_once_with("mypubid", season_id=None)
    mock_crawler.scout_all.assert_not_called()


def test_scout_without_team_calls_scout_all(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Without --team, scout_all() is called."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.crawlers import CrawlResult

    mock_crawler = MagicMock()
    mock_crawler.scout_all_in_memory.return_value = []

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    with patch("src.gamechanger.client.GameChangerClient"), \
         patch("src.gamechanger.crawlers.scouting.ScoutingCrawler", return_value=mock_crawler), \
         patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"), \
         patch("src.cli.data._resolve_db_path", return_value=db_path):
        result = runner.invoke(app, ["data", "scout"])

    mock_crawler.scout_all_in_memory.assert_called_once_with(season_id=None)
    mock_crawler.scout_team.assert_not_called()


# ---------------------------------------------------------------------------
# E-156-01: --force flag tests
# ---------------------------------------------------------------------------


def test_scout_force_dry_run_shows_force_indication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--force --dry-run output includes an indication that force mode is active (AC-4)."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    with patch("src.cli.data._resolve_db_path", return_value=Path("/tmp/test.db")):
        result = runner.invoke(app, ["data", "scout", "--dry-run", "--force"])

    assert result.exit_code == 0
    assert "force" in result.output.lower(), f"Expected 'force' in output: {result.output!r}"
    assert "all opponents" in result.output.lower(), (
        f"Expected 'all opponents' in output (no --team given): {result.output!r}"
    )


def test_scout_force_dry_run_with_team_shows_redundancy_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--force --dry-run --team output notes that force has no effect with --team."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    with patch("src.cli.data._resolve_db_path", return_value=Path("/tmp/test.db")):
        result = runner.invoke(
            app, ["data", "scout", "--dry-run", "--force", "--team", "abc123"]
        )

    assert result.exit_code == 0
    assert "force" in result.output.lower(), f"Expected 'force' in output: {result.output!r}"
    assert "no effect" in result.output.lower(), (
        f"Expected 'no effect' note in output: {result.output!r}"
    )


def test_scout_force_constructs_crawler_with_freshness_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--force passes freshness_hours=0 to ScoutingCrawler (AC-2)."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.crawlers import CrawlResult

    mock_crawler = MagicMock()
    mock_crawler.scout_all_in_memory.return_value = [_mock_in_memory_crawl_result()]

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    captured_kwargs: dict = {}

    def capture_crawler(*args: object, **kwargs: object) -> MagicMock:
        captured_kwargs.update(kwargs)
        return mock_crawler

    with patch("src.gamechanger.client.GameChangerClient"), \
         patch("src.gamechanger.crawlers.scouting.ScoutingCrawler", side_effect=capture_crawler), \
         patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"), \
         patch("src.cli.data._resolve_db_path", return_value=db_path):
        runner.invoke(app, ["data", "scout", "--force"])

    assert captured_kwargs.get("freshness_hours") == 0, (
        f"Expected freshness_hours=0, got {captured_kwargs.get('freshness_hours')!r}"
    )


def test_scout_without_force_constructs_crawler_with_default_freshness(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Without --force, ScoutingCrawler is constructed with freshness_hours=24 (AC-3)."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.crawlers import CrawlResult

    mock_crawler = MagicMock()
    mock_crawler.scout_all_in_memory.return_value = [_mock_in_memory_crawl_result()]

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    captured_kwargs: dict = {}

    def capture_crawler(*args: object, **kwargs: object) -> MagicMock:
        captured_kwargs.update(kwargs)
        return mock_crawler

    with patch("src.gamechanger.client.GameChangerClient"), \
         patch("src.gamechanger.crawlers.scouting.ScoutingCrawler", side_effect=capture_crawler), \
         patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"), \
         patch("src.cli.data._resolve_db_path", return_value=db_path):
        runner.invoke(app, ["data", "scout"])

    assert captured_kwargs.get("freshness_hours") == 24, (
        f"Expected freshness_hours=24, got {captured_kwargs.get('freshness_hours')!r}"
    )


# ---------------------------------------------------------------------------
# AC-17: get_public() sends no auth headers
# ---------------------------------------------------------------------------


def test_get_public_sends_no_gc_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_public() does not send gc-token in the request."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.client import GameChangerClient

    client = GameChangerClient(min_delay_ms=0, jitter_ms=0)

    captured_headers: dict = {}

    with respx.mock:
        def capture_and_respond(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, json=[{"id": "game-1", "game_status": "completed"}])

        respx.get("https://api.team-manager.gc.com/public/teams/abc123/games").mock(
            side_effect=capture_and_respond
        )
        client.get_public("/public/teams/abc123/games")

    assert "gc-token" not in captured_headers, "gc-token must NOT be sent by get_public()"
    assert "gc-device-id" not in captured_headers, "gc-device-id must NOT be sent by get_public()"


def test_get_public_returns_parsed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_public() returns the parsed JSON response body."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.client import GameChangerClient

    client = GameChangerClient(min_delay_ms=0, jitter_ms=0)
    expected = [{"id": "game-1", "game_status": "completed"}]

    with respx.mock:
        respx.get("https://api.team-manager.gc.com/public/teams/abc123/games").mock(
            return_value=httpx.Response(200, json=expected)
        )
        result = client.get_public("/public/teams/abc123/games")

    assert result == expected


def test_get_public_retries_on_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_public() raises GameChangerAPIError after 3 failed 5xx attempts."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.client import GameChangerClient, GameChangerAPIError

    client = GameChangerClient(min_delay_ms=0, jitter_ms=0)

    with respx.mock:
        # All three attempts fail.
        respx.get("https://api.team-manager.gc.com/public/teams/abc123/games").mock(
            return_value=httpx.Response(500)
        )
        with patch("time.sleep"):  # skip backoff delays
            with pytest.raises(GameChangerAPIError):
                client.get_public("/public/teams/abc123/games")


# ---------------------------------------------------------------------------
# AC-2: scouting_runs.status is 'failed' after a load failure
# ---------------------------------------------------------------------------


def test_load_scouted_team_sets_failed_status_on_load_errors(tmp_path: Path) -> None:
    """_load_scouted_team downgrades scouting_runs.status to 'failed' on load errors (AC-2)."""
    import sqlite3 as _sqlite3

    from src.gamechanger.loaders import LoadResult
    from src.cli.data import _load_scouted_team

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    # Seed the state the crawler leaves: team + season + completed scouting run.
    # Use a far-future last_checked so last_checked >= started_at is always true.
    with _sqlite3.connect(str(db_path)) as seed_conn:
        cur = seed_conn.execute(
            "INSERT INTO teams (public_id, name, membership_type, is_active) "
            "VALUES ('mypubid', 'mypubid', 'tracked', 0)"
        )
        team_pk = cur.lastrowid
        seed_conn.execute(
            "INSERT INTO seasons (season_id, name, season_type, year) "
            "VALUES ('2025-spring-hs', '2025-spring-hs', 'unknown', 2025)"
        )
        seed_conn.execute(
            "INSERT INTO scouting_runs "
            "(team_id, season_id, run_type, started_at, status, last_checked, games_found) "
            "VALUES (?, '2025-spring-hs', 'full', '2020-01-01T00:00:00.000Z', "
            "'running', '2099-12-31T23:59:59.000Z', 3)",
            (team_pk,),
        )
        seed_conn.commit()

    # Create a scouting_dir so the directory check passes.
    scouting_dir = tmp_path / "raw" / "2025-spring-hs" / "scouting" / "mypubid"
    scouting_dir.mkdir(parents=True)

    from src.gamechanger.crawlers.scouting import ScoutingCrawler

    mock_loader = MagicMock()
    mock_loader.load_team.return_value = LoadResult(errors=2)

    started_at = "2020-01-01T00:00:00.000Z"  # far past -- row's last_checked is ahead of it

    with _sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys=ON;")
        real_crawler = ScoutingCrawler(MagicMock(), conn)
        _load_scouted_team(
            conn, real_crawler, mock_loader,
            tmp_path / "raw", "mypubid", started_at,
        )

    # Verify the DB row was downgraded to 'failed' and completed_at is NULL.
    with _sqlite3.connect(str(db_path)) as check_conn:
        row = check_conn.execute(
            "SELECT status, completed_at FROM scouting_runs WHERE team_id = ? LIMIT 1",
            (team_pk,),
        ).fetchone()
    assert row is not None
    assert row[0] == "failed", f"Expected status='failed', got '{row[0]}'"
    assert row[1] is None, f"Expected completed_at=NULL for failed run, got '{row[1]}'"


# ---------------------------------------------------------------------------
# AC-1 / AC-4 / AC-5: Load failure exits non-zero
# ---------------------------------------------------------------------------


def test_scout_single_team_load_failure_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """_load_scouted_team returning errors causes non-zero exit for --team (AC-1, AC-4, AC-5)."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.crawlers import CrawlResult

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    mock_crawler = MagicMock()
    mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025-spring-hs", games_crawled=3)

    # Patch the load helper to simulate 2 load errors -- bypasses dir/DB timing concerns.
    with patch("src.gamechanger.client.GameChangerClient"), \
         patch("src.gamechanger.crawlers.scouting.ScoutingCrawler", return_value=mock_crawler), \
         patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"), \
         patch("src.cli.data._load_scouted_team", return_value=2), \
         patch("src.cli.data._resolve_db_path", return_value=db_path):
        result = runner.invoke(app, ["data", "scout", "--team", "mypubid"])

    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}. Output: {result.output}"


def test_scout_single_team_load_success_exits_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """_load_scouted_team returning 0 errors keeps exit 0 for --team (AC-5 complement)."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.crawlers import CrawlResult

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    mock_crawler = MagicMock()
    mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025-spring-hs", games_crawled=3)

    with patch("src.gamechanger.client.GameChangerClient"), \
         patch("src.gamechanger.crawlers.scouting.ScoutingCrawler", return_value=mock_crawler), \
         patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"), \
         patch("src.cli.data._load_scouted_team_in_memory", return_value=0), \
         patch("src.cli.data._resolve_db_path", return_value=db_path):
        result = runner.invoke(app, ["data", "scout", "--team", "mypubid"])

    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}. Output: {result.output}"


# ---------------------------------------------------------------------------
# AC-3: Partial load failure in all-teams mode still exits non-zero
# ---------------------------------------------------------------------------


def test_scout_all_partial_load_failure_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """_load_all_scouted returning errors causes non-zero exit in all-teams mode (AC-3)."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.crawlers import CrawlResult

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    from src.gamechanger.crawlers.scouting import ScoutingCrawlResult
    mock_crawler = MagicMock()
    # One in-memory crawl result so the loader loop runs once
    mock_crawler.scout_all_in_memory.return_value = [
        ScoutingCrawlResult(team_id=1, season_id="2026-spring-hs", public_id="opp-x"),
    ]

    # Return 1 error (the one team failed) -- exit code test.
    with patch("src.gamechanger.client.GameChangerClient"), \
         patch("src.gamechanger.crawlers.scouting.ScoutingCrawler", return_value=mock_crawler), \
         patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"), \
         patch("src.cli.data._load_scouted_team_in_memory", return_value=1), \
         patch("src.cli.data._resolve_db_path", return_value=db_path):
        result = runner.invoke(app, ["data", "scout"])

    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}. Output: {result.output}"


def test_get_public_main_session_gc_token_unaffected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After get_public(), the main session's gc-token header is still intact."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.client import GameChangerClient

    client = GameChangerClient(min_delay_ms=0, jitter_ms=0)
    # Trigger a token fetch so gc-token is set on the main session.
    client._ensure_access_token()
    assert "gc-token" in client._session.headers

    with respx.mock:
        respx.get("https://api.team-manager.gc.com/public/teams/abc123/games").mock(
            return_value=httpx.Response(200, json=[])
        )
        client.get_public("/public/teams/abc123/games")

    # gc-token must still be present on the main session.
    assert "gc-token" in client._session.headers


# ---------------------------------------------------------------------------
# AC-7e/f: CLI sets final status after load phase (E-098-03)
# ---------------------------------------------------------------------------


def test_load_scouted_team_sets_completed_status_on_success(tmp_path: Path) -> None:
    """AC-7e: _load_scouted_team sets scouting_runs.status to 'completed' on load success."""
    import sqlite3 as _sqlite3

    from src.gamechanger.loaders import LoadResult
    from src.cli.data import _load_scouted_team

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    with _sqlite3.connect(str(db_path)) as seed_conn:
        cur = seed_conn.execute(
            "INSERT INTO teams (public_id, name, membership_type, is_active) "
            "VALUES ('mypubid', 'mypubid', 'tracked', 0)"
        )
        team_pk = cur.lastrowid
        seed_conn.execute(
            "INSERT INTO seasons (season_id, name, season_type, year) "
            "VALUES ('2025-spring-hs', '2025-spring-hs', 'unknown', 2025)"
        )
        seed_conn.execute(
            "INSERT INTO scouting_runs "
            "(team_id, season_id, run_type, started_at, status, last_checked, games_found) "
            "VALUES (?, '2025-spring-hs', 'full', '2020-01-01T00:00:00.000Z', "
            "'running', '2099-12-31T23:59:59.000Z', 3)",
            (team_pk,),
        )
        seed_conn.commit()

    scouting_dir = tmp_path / "raw" / "2025-spring-hs" / "scouting" / "mypubid"
    scouting_dir.mkdir(parents=True)

    from src.gamechanger.crawlers.scouting import ScoutingCrawler

    mock_loader = MagicMock()
    mock_loader.load_team.return_value = LoadResult(errors=0)

    started_at = "2020-01-01T00:00:00.000Z"

    with _sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys=ON;")
        real_crawler = ScoutingCrawler(MagicMock(), conn)
        errors = _load_scouted_team(
            conn, real_crawler, mock_loader,
            tmp_path / "raw", "mypubid", started_at,
        )

    assert errors == 0

    with _sqlite3.connect(str(db_path)) as check_conn:
        row = check_conn.execute(
            "SELECT status, completed_at FROM scouting_runs WHERE team_id = ? LIMIT 1",
            (team_pk,),
        ).fetchone()
    assert row is not None
    assert row[0] == "completed", f"Expected status='completed', got '{row[0]}'"
    assert row[1] is not None, "Expected completed_at to be set for completed run"


# ---------------------------------------------------------------------------
# E-163-01: scout triggers scouting spray crawl (AC-5)
# ---------------------------------------------------------------------------


def _mock_spray_result(
    files_written: int = 1,
    files_skipped: int = 0,
    errors: int = 0,
) -> MagicMock:
    """Build a mock spray crawl result (compatible with both CrawlResult and SprayCrawlResult)."""
    r = MagicMock()
    r.files_written = files_written
    r.files_skipped = files_skipped
    r.errors = errors
    # SprayCrawlResult attributes (for single-team in-memory flow).
    r.games_crawled = files_written
    r.games_skipped = files_skipped
    r.spray_data = {}
    return r


def _mock_in_memory_crawl_result(public_id: str = "opp-x") -> "ScoutingCrawlResult":
    """Build a non-empty ScoutingCrawlResult for in-memory pipeline tests."""
    return ScoutingCrawlResult(
        team_id=1,
        season_id="2025-spring-hs",
        public_id=public_id,
        games=[{"id": "g1", "game_status": "completed"}],
        games_crawled=1,
    )



def test_scout_triggers_scouting_spray_crawl_all(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """bb data scout calls ScoutingSprayChartCrawler.crawl_all() (AC-5)."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.crawlers import CrawlResult

    mock_crawler = MagicMock()
    mock_crawler.scout_all_in_memory.return_value = [_mock_in_memory_crawl_result()]
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_team.return_value = _mock_spray_result()

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    with (
        patch("src.gamechanger.client.GameChangerClient"),
        patch("src.gamechanger.crawlers.scouting.ScoutingCrawler", return_value=mock_crawler),
        patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"),
        patch("src.cli.data._load_scouted_team_in_memory", return_value=0),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch("src.cli.data._resolve_db_path", return_value=db_path),
    ):
        result = runner.invoke(app, ["data", "scout"])

    mock_spray_crawler.crawl_team.assert_called_once()
    assert result.exit_code == 0


def test_scout_with_team_calls_spray_crawl_team(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """bb data scout --team calls ScoutingSprayChartCrawler.crawl_team(public_id) (AC-5)."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.crawlers import CrawlResult

    mock_crawler = MagicMock()
    mock_crawler.scout_team.return_value = _mock_in_memory_crawl_result("some-public-id")
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_team.return_value = _mock_spray_result()

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    with (
        patch("src.gamechanger.client.GameChangerClient"),
        patch("src.gamechanger.crawlers.scouting.ScoutingCrawler", return_value=mock_crawler),
        patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"),
        patch("src.cli.data._load_scouted_team_in_memory", return_value=0),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch("src.cli.data._resolve_db_path", return_value=db_path),
    ):
        result = runner.invoke(app, ["data", "scout", "--team", "some-public-id"])

    mock_spray_crawler.crawl_team.assert_called_once()
    args, kwargs = mock_spray_crawler.crawl_team.call_args
    assert args[0] == "some-public-id"
    assert kwargs.get("games_data")  # non-empty in-memory games passed
    assert result.exit_code == 0


def test_scout_spray_errors_cause_exit_code_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """bb data scout exits 1 when the spray crawl reports errors (AC-5)."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.crawlers import CrawlResult

    mock_crawler = MagicMock()
    mock_crawler.scout_all_in_memory.return_value = [_mock_in_memory_crawl_result()]
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_team.return_value = _mock_spray_result(errors=1)

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    with (
        patch("src.gamechanger.client.GameChangerClient"),
        patch("src.gamechanger.crawlers.scouting.ScoutingCrawler", return_value=mock_crawler),
        patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"),
        patch("src.cli.data._load_scouted_team_in_memory", return_value=0),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch("src.cli.data._resolve_db_path", return_value=db_path),
    ):
        result = runner.invoke(app, ["data", "scout"])

    assert result.exit_code == 1


def test_scout_spray_exception_causes_exit_code_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """bb data scout exits 1 when the spray crawl raises an exception (AC-5)."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.crawlers import CrawlResult

    mock_crawler = MagicMock()
    mock_crawler.scout_all_in_memory.return_value = [_mock_in_memory_crawl_result()]
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_team.side_effect = RuntimeError("network failure")

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    with (
        patch("src.gamechanger.client.GameChangerClient"),
        patch("src.gamechanger.crawlers.scouting.ScoutingCrawler", return_value=mock_crawler),
        patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"),
        patch("src.cli.data._load_scouted_team_in_memory", return_value=0),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch("src.cli.data._resolve_db_path", return_value=db_path),
    ):
        result = runner.invoke(app, ["data", "scout"])

    assert result.exit_code == 1


def test_scout_dry_run_skips_spray_crawl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bb data scout --dry-run does not invoke ScoutingSprayChartCrawler (AC-5)."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    with (
        patch("src.cli.data._resolve_db_path", return_value=Path("/tmp/test.db")),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler"
        ) as mock_spray_cls,
    ):
        result = runner.invoke(app, ["data", "scout", "--dry-run"])

    mock_spray_cls.assert_not_called()
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Finding 2: spray stages skipped when main pipeline fails
# ---------------------------------------------------------------------------


def test_scout_spray_stages_skipped_when_main_pipeline_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When main scouting pipeline fails, spray crawl and load are not run."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    mock_spray_crawler = MagicMock()
    mock_spray_loader = MagicMock()

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    with (
        patch("src.gamechanger.client.GameChangerClient"),
        patch("src.cli.data._run_scout_pipeline", return_value=1),  # main pipeline fails
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch(
            "src.gamechanger.loaders.scouting_spray_loader.ScoutingSprayChartLoader",
            return_value=mock_spray_loader,
        ),
        patch("src.cli.data._resolve_db_path", return_value=db_path),
    ):
        result = runner.invoke(app, ["data", "scout"])

    mock_spray_crawler.crawl_all.assert_not_called()
    mock_spray_loader.load_all.assert_not_called()
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Finding 3: --season passed to spray stages
# ---------------------------------------------------------------------------


def test_scout_season_passed_to_spray_crawl_all(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--season override is forwarded to spray_crawler.crawl_all(season_id=...)."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.crawlers import CrawlResult

    mock_crawler = MagicMock()
    mock_crawler.scout_all_in_memory.return_value = [_mock_in_memory_crawl_result()]
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_team.return_value = _mock_spray_result()
    mock_spray_loader = MagicMock()
    mock_spray_loader.load_from_data.return_value = _mock_spray_load_result()

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    with (
        patch("src.gamechanger.client.GameChangerClient"),
        patch("src.gamechanger.crawlers.scouting.ScoutingCrawler", return_value=mock_crawler),
        patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"),
        patch("src.cli.data._load_scouted_team_in_memory", return_value=0),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch(
            "src.gamechanger.loaders.scouting_spray_loader.ScoutingSprayChartLoader",
            return_value=mock_spray_loader,
        ),
        patch("src.cli.data._resolve_db_path", return_value=db_path),
    ):
        result = runner.invoke(app, ["data", "scout", "--season", "2025-spring-hs"])

    assert mock_spray_crawler.crawl_team.call_count >= 1
    call_kwargs = mock_spray_crawler.crawl_team.call_args[1]
    assert call_kwargs.get("season_id") == "2025-spring-hs"
    assert result.exit_code == 0


def test_scout_season_passed_to_spray_load_all(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--season override is forwarded to spray_loader.load_all(season_id=...)."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.crawlers import CrawlResult

    mock_crawler = MagicMock()
    mock_crawler.scout_all_in_memory.return_value = [_mock_in_memory_crawl_result()]
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_team.return_value = _mock_spray_result()
    mock_spray_loader = MagicMock()
    mock_spray_loader.load_from_data.return_value = _mock_spray_load_result()

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    with (
        patch("src.gamechanger.client.GameChangerClient"),
        patch("src.gamechanger.crawlers.scouting.ScoutingCrawler", return_value=mock_crawler),
        patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"),
        patch("src.cli.data._load_scouted_team_in_memory", return_value=0),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch(
            "src.gamechanger.loaders.scouting_spray_loader.ScoutingSprayChartLoader",
            return_value=mock_spray_loader,
        ),
        patch("src.cli.data._resolve_db_path", return_value=db_path),
    ):
        result = runner.invoke(app, ["data", "scout", "--season", "2025-spring-hs"])

    # season_id is passed via crawl_team in the in-memory pipeline.
    _, kwargs = mock_spray_crawler.crawl_team.call_args
    assert kwargs.get("season_id") == "2025-spring-hs"
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# E-163-02: scout triggers scouting spray load (AC-6)
# ---------------------------------------------------------------------------


def _mock_spray_load_result(
    loaded: int = 1,
    skipped: int = 0,
    errors: int = 0,
) -> MagicMock:
    r = MagicMock()
    r.loaded = loaded
    r.skipped = skipped
    r.errors = errors
    return r


def test_scout_triggers_scouting_spray_load(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """bb data scout calls ScoutingSprayChartLoader.load_all() after the spray crawl (AC-6)."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.crawlers import CrawlResult

    mock_crawler = MagicMock()
    mock_crawler.scout_all_in_memory.return_value = [_mock_in_memory_crawl_result()]
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_team.return_value = _mock_spray_result()
    mock_spray_loader = MagicMock()
    mock_spray_loader.load_from_data.return_value = _mock_spray_load_result()

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    with (
        patch("src.gamechanger.client.GameChangerClient"),
        patch("src.gamechanger.crawlers.scouting.ScoutingCrawler", return_value=mock_crawler),
        patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"),
        patch("src.cli.data._load_scouted_team_in_memory", return_value=0),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch(
            "src.gamechanger.loaders.scouting_spray_loader.ScoutingSprayChartLoader",
            return_value=mock_spray_loader,
        ),
        patch("src.cli.data._resolve_db_path", return_value=db_path),
    ):
        result = runner.invoke(app, ["data", "scout"])

    mock_spray_loader.load_from_data.assert_called_once()
    assert result.exit_code == 0


def test_scout_with_team_calls_spray_load_all_with_public_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """bb data scout --team passes public_id to load_from_data() (AC-6)."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.crawlers import CrawlResult

    mock_crawler = MagicMock()
    mock_crawler.scout_team.return_value = _mock_in_memory_crawl_result("my-pub-id")
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_team.return_value = _mock_spray_result()
    mock_spray_loader = MagicMock()
    mock_spray_loader.load_from_data.return_value = _mock_spray_load_result()

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    with (
        patch("src.gamechanger.client.GameChangerClient"),
        patch("src.gamechanger.crawlers.scouting.ScoutingCrawler", return_value=mock_crawler),
        patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"),
        patch("src.cli.data._load_scouted_team_in_memory", return_value=0),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch(
            "src.gamechanger.loaders.scouting_spray_loader.ScoutingSprayChartLoader",
            return_value=mock_spray_loader,
        ),
        patch("src.cli.data._resolve_db_path", return_value=db_path),
    ):
        result = runner.invoke(app, ["data", "scout", "--team", "my-pub-id"])

    mock_spray_loader.load_from_data.assert_called_once()
    _, kwargs = mock_spray_loader.load_from_data.call_args
    assert kwargs.get("public_id") == "my-pub-id"
    assert result.exit_code == 0


def test_scout_spray_load_errors_cause_exit_code_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """bb data scout exits 1 when the spray load reports errors (AC-6)."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.crawlers import CrawlResult

    mock_crawler = MagicMock()
    mock_crawler.scout_all_in_memory.return_value = [_mock_in_memory_crawl_result()]
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_team.return_value = _mock_spray_result()
    mock_spray_loader = MagicMock()
    mock_spray_loader.load_from_data.return_value = _mock_spray_load_result(errors=1)

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    with (
        patch("src.gamechanger.client.GameChangerClient"),
        patch("src.gamechanger.crawlers.scouting.ScoutingCrawler", return_value=mock_crawler),
        patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"),
        patch("src.cli.data._load_scouted_team_in_memory", return_value=0),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch(
            "src.gamechanger.loaders.scouting_spray_loader.ScoutingSprayChartLoader",
            return_value=mock_spray_loader,
        ),
        patch("src.cli.data._resolve_db_path", return_value=db_path),
    ):
        result = runner.invoke(app, ["data", "scout"])

    assert result.exit_code == 1


def test_scout_spray_load_exception_causes_exit_code_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """bb data scout exits 1 when the spray load raises an exception (AC-6)."""
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    from src.gamechanger.crawlers import CrawlResult

    mock_crawler = MagicMock()
    mock_crawler.scout_all_in_memory.return_value = [_mock_in_memory_crawl_result()]
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_team.return_value = _mock_spray_result()
    mock_spray_loader = MagicMock()
    mock_spray_loader.load_from_data.side_effect = RuntimeError("db error")

    db_path = tmp_path / "test.db"
    from migrations.apply_migrations import run_migrations
    run_migrations(db_path=db_path)

    with (
        patch("src.gamechanger.client.GameChangerClient"),
        patch("src.gamechanger.crawlers.scouting.ScoutingCrawler", return_value=mock_crawler),
        patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"),
        patch("src.cli.data._load_scouted_team_in_memory", return_value=0),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch(
            "src.gamechanger.loaders.scouting_spray_loader.ScoutingSprayChartLoader",
            return_value=mock_spray_loader,
        ),
        patch("src.cli.data._resolve_db_path", return_value=db_path),
    ):
        result = runner.invoke(app, ["data", "scout"])

    assert result.exit_code == 1
