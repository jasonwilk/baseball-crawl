"""Tests for src/gamechanger/crawlers/schedule.py.

All HTTP calls are mocked -- no real network requests are made.
Tests cover: successful crawl of schedule and game-summaries, freshness check,
stale file re-fetch, API error handling, game-summaries pagination, and
CrawlResult counts.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from src.gamechanger.client import CredentialExpiredError, GameChangerAPIError
from src.gamechanger.config import CrawlConfig, TeamEntry
from src.gamechanger.crawlers import CrawlResult
from src.gamechanger.crawlers.schedule import ScheduleCrawler


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

_SAMPLE_SCHEDULE = [
    {
        "event": {
            "id": "event-uuid-001",
            "event_type": "game",
            "status": "scheduled",
            "team_id": "team-uuid-001",
        }
    },
    {
        "event": {
            "id": "event-uuid-002",
            "event_type": "practice",
            "status": "scheduled",
            "team_id": "team-uuid-001",
        }
    },
]

_SAMPLE_GAME_SUMMARIES_PAGE1 = [
    {"game_stream": {"game_id": "game-001", "id": "stream-001"}, "game_status": "completed"},
    {"game_stream": {"game_id": "game-002", "id": "stream-002"}, "game_status": "completed"},
]

_SAMPLE_GAME_SUMMARIES_PAGE2 = [
    {"game_stream": {"game_id": "game-003", "id": "stream-003"}, "game_status": "completed"},
]

_TEAM_ID = "team-uuid-001"
_SEASON = "2025"


def _make_config(team_ids: list[str] | None = None) -> CrawlConfig:
    """Build a CrawlConfig with the given team IDs (or a single default team)."""
    ids = team_ids if team_ids is not None else [_TEAM_ID]
    teams = [TeamEntry(id=tid, name=f"Team {tid}", classification="jv") for tid in ids]
    return CrawlConfig(season=_SEASON, member_teams=teams)


def _make_client(
    schedule_response: object = None,
    game_summaries_response: object = None,
) -> MagicMock:
    """Return a mock GameChangerClient with preset responses for get() and get_paginated()."""
    client = MagicMock()
    client.get.return_value = (
        schedule_response if schedule_response is not None else _SAMPLE_SCHEDULE
    )
    client.get_paginated.return_value = (
        game_summaries_response
        if game_summaries_response is not None
        else _SAMPLE_GAME_SUMMARIES_PAGE1
    )
    return client


# ---------------------------------------------------------------------------
# AC-1: Schedule file is written
# ---------------------------------------------------------------------------

def test_crawl_schedule_writes_schedule_json(tmp_path: Path) -> None:
    """Successful fetch writes schedule.json with the raw API response."""
    client = _make_client()
    config = _make_config()
    crawler = ScheduleCrawler(client, config, data_root=tmp_path)

    result_path = crawler._crawl_schedule(_TEAM_ID, _SEASON)

    assert result_path is not None
    assert result_path.exists()
    assert result_path == tmp_path / _SEASON / "teams" / _TEAM_ID / "schedule.json"

    written = json.loads(result_path.read_text())
    assert written == _SAMPLE_SCHEDULE


def test_crawl_schedule_uses_correct_endpoint_and_accept(tmp_path: Path) -> None:
    """_crawl_schedule calls the schedule endpoint with the right params and Accept header."""
    client = _make_client()
    config = _make_config()
    crawler = ScheduleCrawler(client, config, data_root=tmp_path)

    crawler._crawl_schedule(_TEAM_ID, _SEASON)

    client.get.assert_called_once_with(
        f"/teams/{_TEAM_ID}/schedule",
        params={"fetch_place_details": "true"},
        accept="application/vnd.gc.com.event:list+json; version=0.2.0",
    )


# ---------------------------------------------------------------------------
# AC-2: Written schedule JSON is unmodified
# ---------------------------------------------------------------------------

def test_crawl_schedule_writes_raw_unmodified_response(tmp_path: Path) -> None:
    """The written schedule JSON matches the API response exactly."""
    raw_response = [{"event": {"id": "raw-event", "event_type": "game"}}]
    client = _make_client(schedule_response=raw_response)
    config = _make_config()
    crawler = ScheduleCrawler(client, config, data_root=tmp_path)

    path = crawler._crawl_schedule(_TEAM_ID, _SEASON)

    assert path is not None
    assert json.loads(path.read_text()) == raw_response


# ---------------------------------------------------------------------------
# AC-3: Freshness check for schedule
# ---------------------------------------------------------------------------

def test_crawl_schedule_skips_fresh_file(tmp_path: Path) -> None:
    """A schedule.json younger than freshness_hours is not re-fetched."""
    client = _make_client()
    config = _make_config()
    crawler = ScheduleCrawler(client, config, freshness_hours=1, data_root=tmp_path)

    dest = tmp_path / _SEASON / "teams" / _TEAM_ID / "schedule.json"
    dest.parent.mkdir(parents=True)
    dest.write_text(json.dumps(_SAMPLE_SCHEDULE), encoding="utf-8")

    result = crawler._crawl_schedule(_TEAM_ID, _SEASON)

    assert result is None
    client.get.assert_not_called()


def test_crawl_schedule_refetches_stale_file(tmp_path: Path) -> None:
    """A schedule.json older than freshness_hours is re-fetched and overwritten."""
    client = _make_client()
    config = _make_config()
    crawler = ScheduleCrawler(client, config, freshness_hours=1, data_root=tmp_path)

    dest = tmp_path / _SEASON / "teams" / _TEAM_ID / "schedule.json"
    dest.parent.mkdir(parents=True)
    old_data = [{"event": {"id": "old-event"}}]
    dest.write_text(json.dumps(old_data), encoding="utf-8")

    stale_mtime = time.time() - (2 * 3600)  # 2 hours ago
    os.utime(dest, (stale_mtime, stale_mtime))

    result = crawler._crawl_schedule(_TEAM_ID, _SEASON)

    assert result == dest
    client.get.assert_called_once()
    written = json.loads(dest.read_text())
    assert written == _SAMPLE_SCHEDULE


# ---------------------------------------------------------------------------
# AC-4: API errors are logged; crawl continues
# ---------------------------------------------------------------------------

def test_crawl_all_continues_after_schedule_api_error(tmp_path: Path) -> None:
    """An API error on schedule for one team is caught; other teams still crawled."""
    team_ok = "team-ok-001"
    team_bad = "team-bad-002"

    call_count = 0

    def get_side_effect(*args: object, **kwargs: object) -> list[dict]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise GameChangerAPIError("Server error (HTTP 500)")
        return _SAMPLE_SCHEDULE

    client = _make_client()
    client.get.side_effect = get_side_effect

    config = _make_config([team_bad, team_ok])
    crawler = ScheduleCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.errors == 1
    # team_bad schedule failed, team_bad summaries and team_ok both written
    assert result.files_written >= 1


def test_crawl_all_continues_after_game_summaries_api_error(tmp_path: Path) -> None:
    """An API error on game-summaries for one team does not stop other teams."""
    team_ok = "team-ok-001"
    team_bad = "team-bad-002"

    call_count = 0

    def get_paginated_side_effect(*args: object, **kwargs: object) -> list[dict]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise GameChangerAPIError("Server error (HTTP 500)")
        return _SAMPLE_GAME_SUMMARIES_PAGE1

    client = _make_client()
    client.get_paginated.side_effect = get_paginated_side_effect

    config = _make_config([team_bad, team_ok])
    crawler = ScheduleCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.errors == 1
    assert result.files_written >= 1


def test_crawl_all_logs_error_with_team_id(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """When an API error occurs, the error log includes the team ID."""
    import logging

    client = _make_client()
    client.get.side_effect = GameChangerAPIError("HTTP 500")

    config = _make_config([_TEAM_ID])
    crawler = ScheduleCrawler(client, config, data_root=tmp_path)

    with caplog.at_level(logging.ERROR, logger="src.gamechanger.crawlers.schedule"):
        crawler.crawl_all()

    assert _TEAM_ID in caplog.text


# ---------------------------------------------------------------------------
# AC-5: freshness_hours is configurable
# ---------------------------------------------------------------------------

def test_freshness_hours_is_configurable(tmp_path: Path) -> None:
    """A custom freshness_hours=0 makes any existing file considered stale."""
    client = _make_client()
    config = _make_config()
    crawler = ScheduleCrawler(client, config, freshness_hours=0, data_root=tmp_path)

    dest = tmp_path / _SEASON / "teams" / _TEAM_ID / "schedule.json"
    dest.parent.mkdir(parents=True)
    dest.write_text(json.dumps(_SAMPLE_SCHEDULE), encoding="utf-8")

    result = crawler._crawl_schedule(_TEAM_ID, _SEASON)

    # freshness_hours=0 means any file is stale -- should re-fetch.
    assert result == dest
    client.get.assert_called_once()


# ---------------------------------------------------------------------------
# AC-6: Game summaries written with pagination
# ---------------------------------------------------------------------------

def test_crawl_game_summaries_writes_file(tmp_path: Path) -> None:
    """Successful paginated fetch writes game_summaries.json."""
    all_records = _SAMPLE_GAME_SUMMARIES_PAGE1 + _SAMPLE_GAME_SUMMARIES_PAGE2
    client = _make_client(game_summaries_response=all_records)
    config = _make_config()
    crawler = ScheduleCrawler(client, config, data_root=tmp_path)

    result_path = crawler._crawl_game_summaries(_TEAM_ID, _SEASON)

    assert result_path is not None
    assert result_path.exists()
    assert result_path == tmp_path / _SEASON / "teams" / _TEAM_ID / "game_summaries.json"

    written = json.loads(result_path.read_text())
    assert written == all_records


def test_crawl_game_summaries_uses_correct_accept_header(tmp_path: Path) -> None:
    """_crawl_game_summaries calls get_paginated with the right Accept header."""
    client = _make_client()
    config = _make_config()
    crawler = ScheduleCrawler(client, config, data_root=tmp_path)

    crawler._crawl_game_summaries(_TEAM_ID, _SEASON)

    client.get_paginated.assert_called_once_with(
        f"/teams/{_TEAM_ID}/game-summaries",
        accept="application/vnd.gc.com.game_summary:list+json; version=0.1.0",
    )


def test_crawl_game_summaries_combines_all_pages(tmp_path: Path) -> None:
    """All pages of game-summaries are combined into a single JSON array."""
    combined = _SAMPLE_GAME_SUMMARIES_PAGE1 + _SAMPLE_GAME_SUMMARIES_PAGE2
    client = _make_client(game_summaries_response=combined)
    config = _make_config()
    crawler = ScheduleCrawler(client, config, data_root=tmp_path)

    path = crawler._crawl_game_summaries(_TEAM_ID, _SEASON)

    assert path is not None
    written = json.loads(path.read_text())
    assert len(written) == 3
    assert written == combined


def test_crawl_game_summaries_skips_fresh_file(tmp_path: Path) -> None:
    """A game_summaries.json younger than freshness_hours is not re-fetched."""
    client = _make_client()
    config = _make_config()
    crawler = ScheduleCrawler(client, config, freshness_hours=1, data_root=tmp_path)

    dest = tmp_path / _SEASON / "teams" / _TEAM_ID / "game_summaries.json"
    dest.parent.mkdir(parents=True)
    dest.write_text(json.dumps(_SAMPLE_GAME_SUMMARIES_PAGE1), encoding="utf-8")

    result = crawler._crawl_game_summaries(_TEAM_ID, _SEASON)

    assert result is None
    client.get_paginated.assert_not_called()


def test_crawl_game_summaries_refetches_stale_file(tmp_path: Path) -> None:
    """A game_summaries.json older than freshness_hours is re-fetched."""
    client = _make_client()
    config = _make_config()
    crawler = ScheduleCrawler(client, config, freshness_hours=1, data_root=tmp_path)

    dest = tmp_path / _SEASON / "teams" / _TEAM_ID / "game_summaries.json"
    dest.parent.mkdir(parents=True)
    old_data = [{"old": True}]
    dest.write_text(json.dumps(old_data), encoding="utf-8")

    stale_mtime = time.time() - (2 * 3600)
    os.utime(dest, (stale_mtime, stale_mtime))

    result = crawler._crawl_game_summaries(_TEAM_ID, _SEASON)

    assert result == dest
    client.get_paginated.assert_called_once()
    written = json.loads(dest.read_text())
    assert written == _SAMPLE_GAME_SUMMARIES_PAGE1  # mock default


def test_crawl_game_summaries_raw_unmodified(tmp_path: Path) -> None:
    """The written game_summaries.json matches the combined API response exactly."""
    raw = [{"game_stream": {"game_id": "raw-001"}, "game_status": "completed"}]
    client = _make_client(game_summaries_response=raw)
    config = _make_config()
    crawler = ScheduleCrawler(client, config, data_root=tmp_path)

    path = crawler._crawl_game_summaries(_TEAM_ID, _SEASON)

    assert path is not None
    assert json.loads(path.read_text()) == raw


# ---------------------------------------------------------------------------
# crawl_all integration: CrawlResult counts
# ---------------------------------------------------------------------------

def test_crawl_all_returns_crawl_result(tmp_path: Path) -> None:
    """crawl_all returns a CrawlResult with correct counts for one team."""
    client = _make_client()
    config = _make_config([_TEAM_ID])
    crawler = ScheduleCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert isinstance(result, CrawlResult)
    assert result.files_written == 2  # schedule + game_summaries
    assert result.files_skipped == 0
    assert result.errors == 0


def test_crawl_all_skips_both_files_when_fresh(tmp_path: Path) -> None:
    """crawl_all counts both files as skipped when both are fresh."""
    client = _make_client()
    config = _make_config([_TEAM_ID])
    crawler = ScheduleCrawler(client, config, freshness_hours=1, data_root=tmp_path)

    # Pre-populate both files.
    schedule_dest = tmp_path / _SEASON / "teams" / _TEAM_ID / "schedule.json"
    summaries_dest = tmp_path / _SEASON / "teams" / _TEAM_ID / "game_summaries.json"
    schedule_dest.parent.mkdir(parents=True)
    schedule_dest.write_text(json.dumps(_SAMPLE_SCHEDULE), encoding="utf-8")
    summaries_dest.write_text(json.dumps(_SAMPLE_GAME_SUMMARIES_PAGE1), encoding="utf-8")

    result = crawler.crawl_all()

    assert result.files_written == 0
    assert result.files_skipped == 2
    assert result.errors == 0
    client.get.assert_not_called()
    client.get_paginated.assert_not_called()


def test_crawl_all_multiple_teams(tmp_path: Path) -> None:
    """crawl_all accumulates counts across multiple teams."""
    team_ids = ["team-aaa", "team-bbb"]
    client = _make_client()
    config = _make_config(team_ids)
    crawler = ScheduleCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.files_written == 4  # 2 files per team * 2 teams
    assert result.files_skipped == 0
    assert result.errors == 0


# ---------------------------------------------------------------------------
# _is_fresh helper
# ---------------------------------------------------------------------------

def test_is_fresh_returns_false_when_file_missing(tmp_path: Path) -> None:
    """_is_fresh returns False when the file does not exist."""
    client = _make_client()
    config = _make_config()
    crawler = ScheduleCrawler(client, config, data_root=tmp_path)

    assert crawler._is_fresh(tmp_path / "nonexistent.json", 1) is False


def test_is_fresh_returns_true_for_newly_created_file(tmp_path: Path) -> None:
    """_is_fresh returns True for a file written moments ago."""
    client = _make_client()
    config = _make_config()
    crawler = ScheduleCrawler(client, config, data_root=tmp_path)

    f = tmp_path / "fresh.json"
    f.write_text("{}")

    assert crawler._is_fresh(f, 1) is True


def test_is_fresh_returns_false_for_stale_file(tmp_path: Path) -> None:
    """_is_fresh returns False when the file is older than freshness_hours."""
    client = _make_client()
    config = _make_config()
    crawler = ScheduleCrawler(client, config, data_root=tmp_path)

    f = tmp_path / "stale.json"
    f.write_text("{}")
    stale_mtime = time.time() - (2 * 3600)
    os.utime(f, (stale_mtime, stale_mtime))

    assert crawler._is_fresh(f, 1) is False


# ---------------------------------------------------------------------------
# CredentialExpiredError propagation
# ---------------------------------------------------------------------------

def test_crawl_all_propagates_credential_expired_error(tmp_path: Path) -> None:
    """CredentialExpiredError raised by the client aborts crawl_all() immediately."""
    client = _make_client()
    client.get.side_effect = CredentialExpiredError("Token expired")

    config = _make_config([_TEAM_ID])
    crawler = ScheduleCrawler(client, config, data_root=tmp_path)

    with pytest.raises(CredentialExpiredError):
        crawler.crawl_all()
