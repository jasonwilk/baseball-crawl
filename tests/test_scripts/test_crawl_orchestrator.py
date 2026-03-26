"""Tests for the crawl pipeline orchestrator (src/pipeline/crawl.py).

All crawlers are mocked -- no real network requests or file I/O to data/.
Tests use tmp_path for manifest output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.crawl import run, _write_manifest, _CRAWLER_NAMES
from src.gamechanger.crawlers import CrawlResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_config(season: str = "2025", team_ids: list[str] | None = None) -> MagicMock:
    """Return a mock CrawlConfig."""
    config = MagicMock()
    config.season = season
    ids = team_ids or ["team-001"]
    config.member_teams = [MagicMock(id=tid) for tid in ids]
    return config


def _make_result(written: int = 1, skipped: int = 0, errors: int = 0) -> CrawlResult:
    return CrawlResult(files_written=written, files_skipped=skipped, errors=errors)


def _make_crawler_class(name: str, called: list[str]) -> type:
    """Return a crawler class that appends *name* to *called* when crawl_all() runs."""
    class _MockCrawler:
        def __init__(self, client: object, config: object) -> None:
            pass

        def crawl_all(self) -> CrawlResult:
            called.append(name)
            return _make_result()

    return _MockCrawler


# patch.multiple keys must be bare attribute names (not "scripts.crawl.X").
def _all_crawler_patches(
    roster_cls: type | None = None,
    schedule_cls: type | None = None,
    opponent_cls: type | None = None,
    player_stats_cls: type | None = None,
    game_stats_cls: type | None = None,
    spray_chart_cls: type | None = None,
    called: list[str] | None = None,
) -> dict[str, object]:
    """Build a patches dict for patch.multiple('src.pipeline.crawl', ...)."""
    c = called if called is not None else []

    def _cls(name: str, override: type | None) -> type:
        return override if override is not None else _make_crawler_class(name, c)

    return {
        "RosterCrawler": _cls("roster", roster_cls),
        "ScheduleCrawler": _cls("schedule", schedule_cls),
        "OpponentCrawler": _cls("opponent", opponent_cls),
        "PlayerStatsCrawler": _cls("player-stats", player_stats_cls),
        "GameStatsCrawler": _cls("game-stats", game_stats_cls),
        "SprayChartCrawler": _cls("spray-chart", spray_chart_cls),
        "GameChangerClient": MagicMock,
        "load_config": lambda: _make_mock_config(),
    }


# ---------------------------------------------------------------------------
# AC-1: All crawlers run in order
# ---------------------------------------------------------------------------

def test_run_calls_all_crawlers(tmp_path: Path) -> None:
    """run() calls all 6 crawlers when no filter is set."""
    called: list[str] = []

    with patch.multiple("src.pipeline.crawl",**_all_crawler_patches(called=called)):
        exit_code = run(data_root=tmp_path)

    assert exit_code == 0
    assert called == ["roster", "schedule", "opponent", "player-stats", "game-stats", "spray-chart"]


def test_run_roster_before_schedule_before_game_stats(tmp_path: Path) -> None:
    """Crawlers run in the mandated dependency order."""
    order: list[str] = []

    with patch.multiple("src.pipeline.crawl",**_all_crawler_patches(called=order)):
        run(data_root=tmp_path)

    schedule_idx = order.index("schedule")
    game_stats_idx = order.index("game-stats")
    assert schedule_idx < game_stats_idx


# ---------------------------------------------------------------------------
# AC-2: --dry-run prints plan, makes no API calls
# ---------------------------------------------------------------------------

def test_dry_run_returns_zero_and_no_client(tmp_path: Path) -> None:
    """Dry run exits 0 and never instantiates GameChangerClient."""
    with patch("src.pipeline.crawl.load_config", return_value=_make_mock_config()):
        with patch("src.pipeline.crawl.GameChangerClient") as mock_client_cls:
            exit_code = run(dry_run=True, data_root=tmp_path)

    assert exit_code == 0
    mock_client_cls.assert_not_called()


def test_dry_run_no_manifest_written(tmp_path: Path) -> None:
    """Dry run does not write manifest.json."""
    with patch("src.pipeline.crawl.load_config", return_value=_make_mock_config()):
        with patch("src.pipeline.crawl.GameChangerClient"):
            run(dry_run=True, data_root=tmp_path)

    manifest = tmp_path / "2025" / "manifest.json"
    assert not manifest.exists()


def test_dry_run_prints_crawlers(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Dry run logs all crawler names."""
    import logging

    with caplog.at_level(logging.INFO, logger="src.pipeline.crawl"):
        with patch("src.pipeline.crawl.load_config", return_value=_make_mock_config()):
            with patch("src.pipeline.crawl.GameChangerClient"):
                run(dry_run=True, data_root=tmp_path)

    for name in _CRAWLER_NAMES:
        assert name in caplog.text


# ---------------------------------------------------------------------------
# AC-3: --crawler filter runs only the named crawler
# ---------------------------------------------------------------------------

def test_crawler_filter_runs_only_roster(tmp_path: Path) -> None:
    """--crawler roster runs only RosterCrawler."""
    called: list[str] = []

    with patch.multiple("src.pipeline.crawl",**_all_crawler_patches(called=called)):
        exit_code = run(crawler_filter="roster", data_root=tmp_path)

    assert exit_code == 0
    assert called == ["roster"]


def test_crawler_filter_schedule(tmp_path: Path) -> None:
    """--crawler schedule runs only ScheduleCrawler."""
    called: list[str] = []

    with patch.multiple("src.pipeline.crawl",**_all_crawler_patches(called=called)):
        exit_code = run(crawler_filter="schedule", data_root=tmp_path)

    assert exit_code == 0
    assert called == ["schedule"]


def test_crawler_filter_opponent(tmp_path: Path) -> None:
    """--crawler opponent runs only OpponentCrawler."""
    called: list[str] = []

    with patch.multiple("src.pipeline.crawl",**_all_crawler_patches(called=called)):
        exit_code = run(crawler_filter="opponent", data_root=tmp_path)

    assert exit_code == 0
    assert called == ["opponent"]


# ---------------------------------------------------------------------------
# AC-4: Manifest written after successful run
# ---------------------------------------------------------------------------

def test_manifest_written_after_run(tmp_path: Path) -> None:
    """manifest.json is written to data/raw/{season}/manifest.json."""

    def _cls(written: int) -> type:
        class _C:
            def __init__(self, *a: object, **kw: object) -> None:
                pass

            def crawl_all(self) -> CrawlResult:
                return _make_result(written=written)

        return _C

    patches = {
        "RosterCrawler": _cls(3),
        "ScheduleCrawler": _cls(2),
        "OpponentCrawler": _cls(5),
        "PlayerStatsCrawler": _cls(1),
        "GameStatsCrawler": _cls(10),
        "GameChangerClient": MagicMock,
        "load_config": lambda: _make_mock_config(season="2025"),
    }

    with patch.multiple("src.pipeline.crawl",**patches):
        run(data_root=tmp_path)

    manifest_path = tmp_path / "2025" / "manifest.json"
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["season"] == "2025"
    assert "crawled_at" in manifest
    assert manifest["crawlers"]["roster"]["files_written"] == 3
    assert manifest["crawlers"]["schedule"]["files_written"] == 2
    assert manifest["crawlers"]["game-stats"]["files_written"] == 10


def test_manifest_includes_skipped_and_errors(tmp_path: Path) -> None:
    """Manifest captures files_skipped and errors per crawler."""

    class _C:
        def __init__(self, *a: object, **kw: object) -> None:
            pass

        def crawl_all(self) -> CrawlResult:
            return CrawlResult(files_written=2, files_skipped=5, errors=1)

    patches = {
        "RosterCrawler": _C,
        "ScheduleCrawler": _C,
        "OpponentCrawler": _C,
        "PlayerStatsCrawler": _C,
        "GameStatsCrawler": _C,
        "GameChangerClient": MagicMock,
        "load_config": lambda: _make_mock_config(),
    }

    with patch.multiple("src.pipeline.crawl",**patches):
        run(data_root=tmp_path)

    manifest = json.loads((tmp_path / "2025" / "manifest.json").read_text())
    roster_entry = manifest["crawlers"]["roster"]
    assert roster_entry["files_written"] == 2
    assert roster_entry["files_skipped"] == 5
    assert roster_entry["errors"] == 1


# ---------------------------------------------------------------------------
# AC-5: Unhandled exception in a crawler is caught; others still run
# ---------------------------------------------------------------------------

def test_unhandled_exception_continues_to_next_crawler(tmp_path: Path) -> None:
    """An unhandled exception in one crawler does not abort the others."""
    called: list[str] = []

    class _BadRoster:
        def __init__(self, *a: object, **kw: object) -> None:
            pass

        def crawl_all(self) -> CrawlResult:
            raise RuntimeError("Simulated crash")

    patches = _all_crawler_patches(called=called, roster_cls=_BadRoster)

    with patch.multiple("src.pipeline.crawl",**patches):
        exit_code = run(data_root=tmp_path)

    # All crawlers after roster still ran.
    assert "schedule" in called
    assert "opponent" in called
    assert "player-stats" in called
    assert "game-stats" in called
    # Exit code is 1 because one crawler raised.
    assert exit_code == 1


# ---------------------------------------------------------------------------
# AC-6: Exit codes
# ---------------------------------------------------------------------------

def test_exit_code_0_when_all_crawlers_succeed(tmp_path: Path) -> None:
    """Exit code is 0 when all crawlers complete (even with per-record errors)."""

    class _C:
        def __init__(self, *a: object, **kw: object) -> None:
            pass

        def crawl_all(self) -> CrawlResult:
            return CrawlResult(files_written=1, files_skipped=0, errors=3)  # per-record errors ok

    patches = {
        "RosterCrawler": _C,
        "ScheduleCrawler": _C,
        "OpponentCrawler": _C,
        "PlayerStatsCrawler": _C,
        "GameStatsCrawler": _C,
        "GameChangerClient": MagicMock,
        "load_config": lambda: _make_mock_config(),
    }

    with patch.multiple("src.pipeline.crawl",**patches):
        exit_code = run(data_root=tmp_path)

    assert exit_code == 0


def test_exit_code_1_when_crawler_raises(tmp_path: Path) -> None:
    """Exit code is 1 when any crawler raises an unhandled exception."""

    class _BadOpponent:
        def __init__(self, *a: object, **kw: object) -> None:
            pass

        def crawl_all(self) -> CrawlResult:
            raise ValueError("Boom")

    patches = _all_crawler_patches(opponent_cls=_BadOpponent)

    with patch.multiple("src.pipeline.crawl",**patches):
        exit_code = run(data_root=tmp_path)

    assert exit_code == 1


# ---------------------------------------------------------------------------
# _write_manifest unit tests
# ---------------------------------------------------------------------------

def test_write_manifest_structure(tmp_path: Path) -> None:
    """_write_manifest writes valid JSON with the expected structure."""
    results = {
        "roster": CrawlResult(files_written=4, files_skipped=0, errors=0),
        "schedule": CrawlResult(files_written=4, files_skipped=0, errors=0),
    }

    path = _write_manifest("2025", results, data_root=tmp_path)

    assert path.exists()
    manifest = json.loads(path.read_text())

    assert manifest["season"] == "2025"
    assert "crawled_at" in manifest
    # ISO 8601 UTC format ends with Z.
    assert manifest["crawled_at"].endswith("Z")

    assert manifest["crawlers"]["roster"]["files_written"] == 4
    assert manifest["crawlers"]["schedule"]["files_written"] == 4


def test_write_manifest_overwrites_existing(tmp_path: Path) -> None:
    """_write_manifest overwrites an existing manifest."""
    (tmp_path / "2025").mkdir()
    manifest_path = tmp_path / "2025" / "manifest.json"
    manifest_path.write_text('{"old": true}')

    _write_manifest(
        "2025",
        {"roster": CrawlResult(files_written=99)},
        data_root=tmp_path,
    )

    manifest = json.loads(manifest_path.read_text())
    assert "old" not in manifest
    assert manifest["crawlers"]["roster"]["files_written"] == 99


# ---------------------------------------------------------------------------
# AC-1 / AC-3: team_ids filter (source="db")
# ---------------------------------------------------------------------------


def _make_db_config(
    season: str = "2025",
    teams: list[tuple[str, int]] | None = None,
) -> MagicMock:
    """Return a mock CrawlConfig with internal_id populated (simulates source='db')."""
    config = MagicMock()
    config.season = season
    team_list = teams or [("team-001", 1)]
    config.member_teams = [MagicMock(id=gc_uuid, internal_id=iid) for gc_uuid, iid in team_list]
    return config


def test_team_ids_filter_db_source_single_team(tmp_path: Path) -> None:
    """team_ids=[2] with source='db' passes only the matching team to crawlers."""
    teams = [("team-a", 1), ("team-b", 2), ("team-c", 3)]
    db_config = _make_db_config(teams=teams)

    captured_configs: list[list] = []

    class _CapturingCrawler:
        def __init__(self, client: object, config: object) -> None:
            captured_configs.append(list(config.member_teams))

        def crawl_all(self) -> CrawlResult:
            return _make_result()

    patches = {
        "RosterCrawler": _CapturingCrawler,
        "ScheduleCrawler": _CapturingCrawler,
        "OpponentCrawler": _CapturingCrawler,
        "PlayerStatsCrawler": _CapturingCrawler,
        "GameStatsCrawler": _CapturingCrawler,
        "SprayChartCrawler": _CapturingCrawler,
        "GameChangerClient": MagicMock,
        "load_config_from_db": lambda _: db_config,
    }

    with patch.multiple("src.pipeline.crawl", **patches):
        exit_code = run(source="db", team_ids=[2], data_root=tmp_path, db_path=tmp_path / "app.db")

    assert exit_code == 0
    # All 6 crawlers should have seen exactly 1 team (internal_id=2)
    assert len(captured_configs) == 6
    for teams_seen in captured_configs:
        assert len(teams_seen) == 1
        assert teams_seen[0].internal_id == 2


def test_team_ids_none_db_source_processes_all_teams(tmp_path: Path) -> None:
    """team_ids=None with source='db' passes all teams to crawlers (unfiltered)."""
    teams = [("team-a", 1), ("team-b", 2), ("team-c", 3)]
    db_config = _make_db_config(teams=teams)

    captured_configs: list[list] = []

    class _CapturingCrawler:
        def __init__(self, client: object, config: object) -> None:
            captured_configs.append(list(config.member_teams))

        def crawl_all(self) -> CrawlResult:
            return _make_result()

    patches = {
        "RosterCrawler": _CapturingCrawler,
        "ScheduleCrawler": _CapturingCrawler,
        "OpponentCrawler": _CapturingCrawler,
        "PlayerStatsCrawler": _CapturingCrawler,
        "GameStatsCrawler": _CapturingCrawler,
        "SprayChartCrawler": _CapturingCrawler,
        "GameChangerClient": MagicMock,
        "load_config_from_db": lambda _: db_config,
    }

    with patch.multiple("src.pipeline.crawl", **patches):
        exit_code = run(source="db", team_ids=None, data_root=tmp_path, db_path=tmp_path / "app.db")

    assert exit_code == 0
    # Each crawler sees all 3 teams
    for teams_seen in captured_configs:
        assert len(teams_seen) == 3


def test_team_ids_with_crawler_filter(tmp_path: Path) -> None:
    """team_ids=[2] + crawler_filter='game-stats' runs only game-stats for team 2."""
    teams = [("team-a", 1), ("team-b", 2)]
    db_config = _make_db_config(teams=teams)

    captured_configs: list[list] = []
    called: list[str] = []

    class _CapturingGameStats:
        def __init__(self, client: object, config: object) -> None:
            captured_configs.append(list(config.member_teams))

        def crawl_all(self) -> CrawlResult:
            called.append("game-stats")
            return _make_result()

    patches = {
        "RosterCrawler": _make_crawler_class("roster", []),
        "ScheduleCrawler": _make_crawler_class("schedule", []),
        "OpponentCrawler": _make_crawler_class("opponent", []),
        "PlayerStatsCrawler": _make_crawler_class("player-stats", []),
        "GameStatsCrawler": _CapturingGameStats,
        "GameChangerClient": MagicMock,
        "load_config_from_db": lambda _: db_config,
    }

    with patch.multiple("src.pipeline.crawl", **patches):
        exit_code = run(
            source="db",
            team_ids=[2],
            crawler_filter="game-stats",
            data_root=tmp_path,
            db_path=tmp_path / "app.db",
        )

    assert exit_code == 0
    assert called == ["game-stats"]
    assert len(captured_configs) == 1
    assert captured_configs[0][0].internal_id == 2
