"""Tests for src/gamechanger/crawlers/opponent.py.

All HTTP calls are mocked -- no real network requests are made.
Tests cover:
- Opponents endpoint called with pagination (Phase 1)
- opponents.json written for each owned team (Phase 1)
- Opponents without progenitor_team_id skipped (no roster fetch)
- Hidden opponents skipped
- Freshness check for opponents.json registry
- Summary log produced (AC-3)
- No authenticated roster calls for any opponent (AC-5)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.gamechanger.client import GameChangerAPIError
from src.gamechanger.config import CrawlConfig, TeamEntry
from src.gamechanger.crawlers import CrawlResult
from src.gamechanger.crawlers.opponent import OpponentCrawler


# ---------------------------------------------------------------------------
# Constants and fixtures
# ---------------------------------------------------------------------------

_OWNED_TEAM_ID = "owned-team-uuid-001"
_SEASON = "2025"

_OPPONENT_WITH_ID = {
    "root_team_id": "root-aaa",
    "owning_team_id": _OWNED_TEAM_ID,
    "name": "SE Elites 14U",
    "is_hidden": False,
    "progenitor_team_id": "progenitor-aaa-001",
}

_OPPONENT_NO_PROGENITOR = {
    "root_team_id": "root-bbb",
    "owning_team_id": _OWNED_TEAM_ID,
    "name": "Opponent TBD",
    "is_hidden": False,
    # No progenitor_team_id key
}

_OPPONENT_HIDDEN = {
    "root_team_id": "root-ccc",
    "owning_team_id": _OWNED_TEAM_ID,
    "name": "Old Duplicate (bad)",
    "is_hidden": True,
    "progenitor_team_id": "progenitor-ccc-001",
}


def _make_config(
    owned_team_ids: list[str] | None = None,
) -> CrawlConfig:
    """Build a CrawlConfig with given team IDs (or a single default team)."""
    ids = owned_team_ids if owned_team_ids is not None else [_OWNED_TEAM_ID]
    teams = [TeamEntry(id=tid, name=f"Team {tid}", classification="jv") for tid in ids]
    return CrawlConfig(season=_SEASON, member_teams=teams)


def _make_client(
    paginated_return: list | None = None,
    paginated_side_effect: Exception | None = None,
) -> MagicMock:
    """Return a mock GameChangerClient with configurable return values."""
    client = MagicMock()
    if paginated_side_effect is not None:
        client.get_paginated.side_effect = paginated_side_effect
    else:
        client.get_paginated.return_value = (
            paginated_return if paginated_return is not None else []
        )
    return client


# ---------------------------------------------------------------------------
# Phase 1: Opponents endpoint called and opponents.json written
# ---------------------------------------------------------------------------


def test_crawl_all_calls_opponents_endpoint(tmp_path: Path) -> None:
    """crawl_all calls GET /teams/{team_id}/opponents for each owned team."""
    opponents = [_OPPONENT_WITH_ID]
    client = _make_client(paginated_return=opponents)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    crawler.crawl_all()

    client.get_paginated.assert_called_once_with(
        f"/teams/{_OWNED_TEAM_ID}/opponents",
        accept="application/vnd.gc.com.opponent_team:list+json; version=0.0.0",
    )


def test_crawl_all_writes_opponents_json(tmp_path: Path) -> None:
    """crawl_all writes the full opponents list to opponents.json."""
    opponents = [_OPPONENT_WITH_ID, _OPPONENT_NO_PROGENITOR]
    client = _make_client(paginated_return=opponents)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    crawler.crawl_all()

    dest = tmp_path / _SEASON / "teams" / _OWNED_TEAM_ID / "opponents.json"
    assert dest.exists()
    written = json.loads(dest.read_text())
    assert written == opponents


def test_crawl_all_calls_opponents_for_each_owned_team(tmp_path: Path) -> None:
    """crawl_all iterates over every owned team for the registry fetch."""
    team_a = "owned-aaa"
    team_b = "owned-bbb"
    client = _make_client(paginated_return=[])
    config = _make_config([team_a, team_b])
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    crawler.crawl_all()

    assert client.get_paginated.call_count == 2
    called_paths = [c.args[0] for c in client.get_paginated.call_args_list]
    assert f"/teams/{team_a}/opponents" in called_paths
    assert f"/teams/{team_b}/opponents" in called_paths


# ---------------------------------------------------------------------------
# AC-5: No authenticated roster calls for any opponent
# ---------------------------------------------------------------------------


def test_crawl_all_does_not_make_authenticated_roster_calls(tmp_path: Path) -> None:
    """crawl_all never calls authenticated roster endpoints for opponent teams."""
    opponents = [_OPPONENT_WITH_ID]
    client = _make_client(paginated_return=opponents)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    crawler.crawl_all()

    # client.get is the authenticated single-resource endpoint; must not be called.
    client.get.assert_not_called()


def test_crawl_all_skips_opponent_without_progenitor(tmp_path: Path) -> None:
    """Opponents without progenitor_team_id produce no roster fetch."""
    opponents = [_OPPONENT_NO_PROGENITOR]
    client = _make_client(paginated_return=opponents)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    client.get.assert_not_called()
    assert result.files_written == 1  # Only the opponents.json registry
    assert result.errors == 0


def test_crawl_all_skips_hidden_opponents(tmp_path: Path) -> None:
    """Hidden opponents (is_hidden=True) are not crawled for rosters."""
    opponents = [_OPPONENT_HIDDEN]
    client = _make_client(paginated_return=opponents)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    client.get.assert_not_called()
    assert result.errors == 0


# ---------------------------------------------------------------------------
# AC-3: Summary log produced after Phase 1
# ---------------------------------------------------------------------------


def test_crawl_all_logs_summary(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """crawl_all produces a summary log with opponent registry statistics."""
    opponents = [_OPPONENT_WITH_ID, _OPPONENT_NO_PROGENITOR, _OPPONENT_HIDDEN]
    client = _make_client(paginated_return=opponents)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    with caplog.at_level(logging.INFO, logger="src.gamechanger.crawlers.opponent"):
        crawler.crawl_all()

    summary_records = [r for r in caplog.records if "Opponent crawl summary" in r.message]
    assert len(summary_records) == 1
    summary = summary_records[0].message

    assert "total_unique_opponents=3" in summary
    assert "with_progenitor_id=1" in summary
    assert "without_progenitor_id=1" in summary
    assert "hidden=1" in summary


# ---------------------------------------------------------------------------
# Freshness check for opponents.json registry
# ---------------------------------------------------------------------------


def test_crawl_registry_skips_fresh_opponents_json(tmp_path: Path) -> None:
    """A fresh opponents.json is not re-fetched from the API."""
    stored_opponents = [_OPPONENT_WITH_ID]
    dest = tmp_path / _SEASON / "teams" / _OWNED_TEAM_ID / "opponents.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(stored_opponents), encoding="utf-8")

    client = _make_client()
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    crawler.crawl_all()

    # Registry endpoint not called -- loaded from cache.
    client.get_paginated.assert_not_called()
    # No authenticated roster endpoint called either.
    client.get.assert_not_called()


def test_crawl_registry_counts_fresh_file_as_skipped(tmp_path: Path) -> None:
    """files_skipped is incremented when the opponents.json is fresh."""
    stored_opponents: list = []
    dest = tmp_path / _SEASON / "teams" / _OWNED_TEAM_ID / "opponents.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(stored_opponents), encoding="utf-8")

    client = _make_client()
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.files_skipped >= 1


def test_crawl_registry_refetches_stale_opponents_json(tmp_path: Path) -> None:
    """A stale opponents.json (older than freshness_hours) is re-fetched."""
    dest = tmp_path / _SEASON / "teams" / _OWNED_TEAM_ID / "opponents.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps([]), encoding="utf-8")

    # Set mtime to 25 hours ago.
    import os
    stale_mtime = time.time() - (25 * 3600)
    os.utime(dest, (stale_mtime, stale_mtime))

    client = _make_client(paginated_return=[_OPPONENT_WITH_ID])
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    crawler.crawl_all()

    client.get_paginated.assert_called_once()


# ---------------------------------------------------------------------------
# CrawlResult counts
# ---------------------------------------------------------------------------


def test_crawl_all_returns_crawl_result(tmp_path: Path) -> None:
    """crawl_all returns a CrawlResult instance."""
    client = _make_client(paginated_return=[])
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert isinstance(result, CrawlResult)


def test_crawl_all_files_written_reflects_registry_only(tmp_path: Path) -> None:
    """files_written reflects only the opponents.json registry (Phase 1 only)."""
    opponents = [_OPPONENT_WITH_ID]
    client = _make_client(paginated_return=opponents)
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    # 1 opponents.json registry only -- no roster files.
    assert result.files_written == 1
    assert result.files_skipped == 0
    assert result.errors == 0


def test_crawl_all_registry_api_error_counted_in_result(tmp_path: Path) -> None:
    """An API error fetching the opponent registry increments errors."""
    client = _make_client(paginated_side_effect=GameChangerAPIError("Server error"))
    config = _make_config()
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.errors == 1
    assert result.files_written == 0


def test_crawl_all_registry_error_does_not_abort_other_teams(tmp_path: Path) -> None:
    """A registry error on one team does not prevent fetching for other teams."""
    team_bad = "owned-bad"
    team_ok = "owned-ok"

    def paginated_side_effect(path: str, **kwargs: object) -> list:
        if team_bad in path:
            raise GameChangerAPIError("Server error")
        return [_OPPONENT_WITH_ID]

    client = MagicMock()
    client.get_paginated.side_effect = paginated_side_effect
    config = _make_config([team_bad, team_ok])
    crawler = OpponentCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.errors == 1
    assert result.files_written >= 1  # team_ok's registry
