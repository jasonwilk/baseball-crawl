"""Tests for src/gamechanger/crawlers/roster.py.

All HTTP calls are mocked -- no real network requests are made.
Tests cover: successful crawl, fresh file skip, stale file re-fetch,
API error handling, CrawlResult counts, and configurable freshness threshold.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.gamechanger.client import GameChangerAPIError
from src.gamechanger.config import CrawlConfig, TeamEntry
from src.gamechanger.crawlers import CrawlResult
from src.gamechanger.crawlers.roster import RosterCrawler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_ROSTER = [
    {"id": "aaa-111", "first_name": "J", "last_name": "Smith", "number": "1", "avatar_url": ""},
    {"id": "bbb-222", "first_name": "M", "last_name": "Jones", "number": "7", "avatar_url": ""},
]

_TEAM_ID = "team-uuid-001"
_SEASON = "2025"


def _make_config(team_ids: list[str] | None = None) -> CrawlConfig:
    """Build a CrawlConfig with given team IDs (or a single default team)."""
    ids = team_ids if team_ids is not None else [_TEAM_ID]
    teams = [
        TeamEntry(id=tid, name=f"Team {tid}", classification="jv")
        for tid in ids
    ]
    return CrawlConfig(season=_SEASON, member_teams=teams)


def _make_client(return_value: object = None, side_effect: Exception | None = None) -> MagicMock:
    """Return a mock GameChangerClient."""
    client = MagicMock()
    if side_effect is not None:
        client.get.side_effect = side_effect
    else:
        client.get.return_value = return_value if return_value is not None else _SAMPLE_ROSTER
    return client


# ---------------------------------------------------------------------------
# AC-1: Successful crawl writes file
# ---------------------------------------------------------------------------

def test_crawl_team_writes_roster_json(tmp_path: Path) -> None:
    """Successful fetch writes roster.json with the raw API response."""
    client = _make_client()
    config = _make_config()
    crawler = RosterCrawler(client, config, data_root=tmp_path)

    result_path = crawler.crawl_team(_TEAM_ID, _SEASON)

    assert result_path is not None
    assert result_path.exists()
    assert result_path == tmp_path / _SEASON / "teams" / _TEAM_ID / "roster.json"

    written = json.loads(result_path.read_text())
    assert written == _SAMPLE_ROSTER


def test_crawl_team_uses_correct_accept_header(tmp_path: Path) -> None:
    """crawl_team passes the player-list Accept header to the client."""
    client = _make_client()
    config = _make_config()
    crawler = RosterCrawler(client, config, data_root=tmp_path)

    crawler.crawl_team(_TEAM_ID, _SEASON)

    client.get.assert_called_once_with(
        f"/teams/{_TEAM_ID}/players",
        accept="application/vnd.gc.com.player:list+json; version=0.1.0",
    )


def test_crawl_all_returns_crawl_result_with_correct_counts(tmp_path: Path) -> None:
    """crawl_all returns a CrawlResult with files_written incremented."""
    client = _make_client()
    config = _make_config([_TEAM_ID])
    crawler = RosterCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert isinstance(result, CrawlResult)
    assert result.files_written == 1
    assert result.files_skipped == 0
    assert result.errors == 0


# ---------------------------------------------------------------------------
# AC-4: Written file is unmodified API response
# ---------------------------------------------------------------------------

def test_crawl_team_writes_raw_unmodified_response(tmp_path: Path) -> None:
    """The written JSON matches the API response exactly, no fields stripped."""
    raw_response = [
        {
            "id": "ccc-333",
            "first_name": "Full",
            "last_name": "Name",
            "number": "42",
            "avatar_url": "https://example.com/avatar.png",
        }
    ]
    client = _make_client(return_value=raw_response)
    config = _make_config()
    crawler = RosterCrawler(client, config, data_root=tmp_path)

    path = crawler.crawl_team(_TEAM_ID, _SEASON)
    assert path is not None
    assert json.loads(path.read_text()) == raw_response


# ---------------------------------------------------------------------------
# AC-2: Fresh file is skipped
# ---------------------------------------------------------------------------

def test_crawl_team_skips_fresh_file(tmp_path: Path) -> None:
    """A roster.json younger than freshness_hours is not re-fetched."""
    client = _make_client()
    config = _make_config()
    crawler = RosterCrawler(client, config, freshness_hours=24, data_root=tmp_path)

    # Write a fresh file manually.
    dest = tmp_path / _SEASON / "teams" / _TEAM_ID / "roster.json"
    dest.parent.mkdir(parents=True)
    dest.write_text(json.dumps(_SAMPLE_ROSTER), encoding="utf-8")

    result = crawler.crawl_team(_TEAM_ID, _SEASON)

    assert result is None
    client.get.assert_not_called()


def test_crawl_all_counts_skipped_fresh_files(tmp_path: Path) -> None:
    """crawl_all increments files_skipped for fresh files."""
    client = _make_client()
    config = _make_config([_TEAM_ID])
    crawler = RosterCrawler(client, config, freshness_hours=24, data_root=tmp_path)

    dest = tmp_path / _SEASON / "teams" / _TEAM_ID / "roster.json"
    dest.parent.mkdir(parents=True)
    dest.write_text(json.dumps(_SAMPLE_ROSTER), encoding="utf-8")

    result = crawler.crawl_all()

    assert result.files_written == 0
    assert result.files_skipped == 1
    assert result.errors == 0


# ---------------------------------------------------------------------------
# AC-3: Stale file is re-fetched
# ---------------------------------------------------------------------------

def test_crawl_team_refetches_stale_file(tmp_path: Path) -> None:
    """A roster.json older than freshness_hours is re-fetched and overwritten."""
    client = _make_client()
    config = _make_config()
    crawler = RosterCrawler(client, config, freshness_hours=24, data_root=tmp_path)

    dest = tmp_path / _SEASON / "teams" / _TEAM_ID / "roster.json"
    dest.parent.mkdir(parents=True)
    old_content = [{"id": "old", "first_name": "Old", "last_name": "Data", "number": "0", "avatar_url": ""}]
    dest.write_text(json.dumps(old_content), encoding="utf-8")

    # Set file mtime to 25 hours ago (older than freshness_hours=24).
    stale_mtime = time.time() - (25 * 3600)
    import os
    os.utime(dest, (stale_mtime, stale_mtime))

    result = crawler.crawl_team(_TEAM_ID, _SEASON)

    assert result == dest
    client.get.assert_called_once()
    written = json.loads(dest.read_text())
    assert written == _SAMPLE_ROSTER  # overwritten with fresh data


# ---------------------------------------------------------------------------
# AC-5: API error is logged; crawl continues to next team
# ---------------------------------------------------------------------------

def test_crawl_all_continues_after_api_error(tmp_path: Path) -> None:
    """An API error on one team is caught; other teams are still crawled."""
    team_ok = "team-ok-001"
    team_bad = "team-bad-002"

    call_count = 0
    def side_effect(*args: object, **kwargs: object) -> list[dict]:
        nonlocal call_count
        call_count += 1
        if kwargs.get("accept") or True:  # called on team_bad first
            # Raise on first call (team_bad), succeed on second (team_ok).
            if call_count == 1:
                raise GameChangerAPIError("Server error (HTTP 500)")
        return _SAMPLE_ROSTER

    client = MagicMock()
    client.get.side_effect = side_effect

    config = _make_config([team_bad, team_ok])
    crawler = RosterCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.errors == 1
    assert result.files_written == 1
    assert result.files_skipped == 0


def test_crawl_all_logs_error_with_team_id(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """When an API error occurs, the error log includes the team ID."""
    import logging
    client = _make_client(side_effect=GameChangerAPIError("HTTP 500"))
    config = _make_config([_TEAM_ID])
    crawler = RosterCrawler(client, config, data_root=tmp_path)

    with caplog.at_level(logging.ERROR, logger="src.gamechanger.crawlers.roster"):
        crawler.crawl_all()

    assert _TEAM_ID in caplog.text


# ---------------------------------------------------------------------------
# AC-6: freshness_hours is configurable
# ---------------------------------------------------------------------------

def test_freshness_hours_is_configurable(tmp_path: Path) -> None:
    """A custom freshness_hours threshold is respected."""
    client = _make_client()
    config = _make_config()
    # Use a very short threshold: 0.001 hours (3.6 seconds)
    crawler = RosterCrawler(client, config, freshness_hours=0, data_root=tmp_path)

    dest = tmp_path / _SEASON / "teams" / _TEAM_ID / "roster.json"
    dest.parent.mkdir(parents=True)
    dest.write_text(json.dumps(_SAMPLE_ROSTER), encoding="utf-8")

    # freshness_hours=0 means any file (even just written) is considered stale.
    result = crawler.crawl_team(_TEAM_ID, _SEASON)

    # Should have re-fetched because threshold is 0.
    assert result == dest
    client.get.assert_called_once()


# ---------------------------------------------------------------------------
# AC-7: CrawlResult dataclass structure
# ---------------------------------------------------------------------------

def test_crawl_result_default_values() -> None:
    """CrawlResult initialises all counts to zero by default."""
    result = CrawlResult()
    assert result.files_written == 0
    assert result.files_skipped == 0
    assert result.errors == 0


def test_crawl_result_multiple_teams(tmp_path: Path) -> None:
    """CrawlResult accumulates counts across all teams in crawl_all."""
    team_ids = ["team-aaa", "team-bbb", "team-ccc"]

    call_count = 0
    def side_effect(*args: object, **kwargs: object) -> list[dict]:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise GameChangerAPIError("Simulated error on team-bbb")
        return _SAMPLE_ROSTER

    client = MagicMock()
    client.get.side_effect = side_effect

    # Pre-populate team-aaa roster to force a skip.
    dest_aaa = tmp_path / _SEASON / "teams" / "team-aaa" / "roster.json"
    dest_aaa.parent.mkdir(parents=True)
    dest_aaa.write_text(json.dumps(_SAMPLE_ROSTER), encoding="utf-8")

    config = _make_config(team_ids)
    crawler = RosterCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    # team-aaa: skipped (fresh file); team-bbb: error; team-ccc: written.
    assert result.files_skipped == 1
    assert result.errors == 1
    assert result.files_written == 1


# ---------------------------------------------------------------------------
# _is_fresh helper
# ---------------------------------------------------------------------------

def test_is_fresh_returns_false_when_file_missing(tmp_path: Path) -> None:
    """_is_fresh returns False when the file does not exist."""
    client = _make_client()
    config = _make_config()
    crawler = RosterCrawler(client, config, data_root=tmp_path)

    assert crawler._is_fresh(tmp_path / "nonexistent.json", 24) is False


def test_is_fresh_returns_true_for_newly_created_file(tmp_path: Path) -> None:
    """_is_fresh returns True for a file written moments ago."""
    client = _make_client()
    config = _make_config()
    crawler = RosterCrawler(client, config, data_root=tmp_path)

    f = tmp_path / "fresh.json"
    f.write_text("{}")

    assert crawler._is_fresh(f, 24) is True
