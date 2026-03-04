"""Tests for src/gamechanger/crawlers/player_stats.py.

All HTTP calls are mocked -- no real network requests are made.
Tests cover: successful crawl, fresh file skip, stale file re-fetch,
API error handling, CrawlResult counts, and empty stats response.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.gamechanger.client import GameChangerAPIError
from src.gamechanger.config import CrawlConfig, TeamEntry
from src.gamechanger.crawlers import CrawlResult
from src.gamechanger.crawlers.player_stats import PlayerStatsCrawler


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_TEAM_ID = "team-uuid-001"
_SEASON = "2025"

_SAMPLE_STATS = {
    "id": _TEAM_ID,
    "team_id": _TEAM_ID,
    "stats_data": {
        "players": {
            "player-aaa-111": {
                "stats": {
                    "offense": {"AB": 50, "H": 15, "HR": 2},
                    "defense": {"IP": 9, "SO": 12},
                }
            },
            "player-bbb-222": {
                "stats": {
                    "offense": {"AB": 40, "H": 10, "HR": 0},
                }
            },
        },
        "streaks": {},
        "stats": {"offense": {"AB": 90, "H": 25}},
    },
}


def _make_config(team_ids: list[str] | None = None) -> CrawlConfig:
    """Build a CrawlConfig with given team IDs (or a single default team)."""
    ids = team_ids if team_ids is not None else [_TEAM_ID]
    teams = [TeamEntry(id=tid, name=f"Team {tid}", level="jv") for tid in ids]
    return CrawlConfig(season=_SEASON, owned_teams=teams)


def _make_client(
    return_value: object = None, side_effect: Exception | None = None
) -> MagicMock:
    """Return a mock GameChangerClient."""
    client = MagicMock()
    if side_effect is not None:
        client.get.side_effect = side_effect
    else:
        client.get.return_value = return_value if return_value is not None else _SAMPLE_STATS
    return client


# ---------------------------------------------------------------------------
# AC-1: Successful crawl fetches and writes stats
# ---------------------------------------------------------------------------

def test_crawl_team_writes_stats_json(tmp_path: Path) -> None:
    """Successful fetch writes stats.json with the raw API response."""
    client = _make_client()
    config = _make_config()
    crawler = PlayerStatsCrawler(client, config, data_root=tmp_path)

    result_path = crawler.crawl_team(_TEAM_ID, _SEASON)

    assert result_path is not None
    assert result_path.exists()
    assert result_path == tmp_path / _SEASON / "teams" / _TEAM_ID / "stats.json"

    written = json.loads(result_path.read_text())
    assert written == _SAMPLE_STATS


def test_crawl_team_uses_correct_endpoint_and_accept_header(tmp_path: Path) -> None:
    """crawl_team calls the correct endpoint with the season-stats Accept header."""
    client = _make_client()
    config = _make_config()
    crawler = PlayerStatsCrawler(client, config, data_root=tmp_path)

    crawler.crawl_team(_TEAM_ID, _SEASON)

    client.get.assert_called_once_with(
        f"/teams/{_TEAM_ID}/season-stats",
        accept="application/vnd.gc.com.team_season_stats+json; version=0.2.0",
    )


def test_crawl_all_returns_crawl_result_with_correct_counts(tmp_path: Path) -> None:
    """crawl_all returns a CrawlResult with files_written incremented."""
    client = _make_client()
    config = _make_config([_TEAM_ID])
    crawler = PlayerStatsCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert isinstance(result, CrawlResult)
    assert result.files_written == 1
    assert result.files_skipped == 0
    assert result.errors == 0


def test_crawl_all_one_request_per_team(tmp_path: Path) -> None:
    """crawl_all makes exactly one API request per team."""
    team_ids = ["team-aaa", "team-bbb", "team-ccc"]
    client = _make_client()
    config = _make_config(team_ids)
    crawler = PlayerStatsCrawler(client, config, data_root=tmp_path)

    crawler.crawl_all()

    assert client.get.call_count == 3


# ---------------------------------------------------------------------------
# AC-3: Full response written as-is (including empty players)
# ---------------------------------------------------------------------------

def test_crawl_team_writes_raw_unmodified_response(tmp_path: Path) -> None:
    """The written JSON matches the API response exactly, no fields stripped."""
    raw_response = {
        "id": _TEAM_ID,
        "team_id": _TEAM_ID,
        "stats_data": {
            "players": {"player-zzz-999": {"stats": {"offense": {"AB": 99}}}},
            "streaks": {},
            "stats": {},
        },
    }
    client = _make_client(return_value=raw_response)
    config = _make_config()
    crawler = PlayerStatsCrawler(client, config, data_root=tmp_path)

    path = crawler.crawl_team(_TEAM_ID, _SEASON)
    assert path is not None
    assert json.loads(path.read_text()) == raw_response


def test_crawl_team_writes_empty_players_response(tmp_path: Path) -> None:
    """Empty stats_data.players is written without error."""
    empty_response: dict = {
        "id": _TEAM_ID,
        "team_id": _TEAM_ID,
        "stats_data": {"players": {}, "streaks": {}, "stats": {}},
    }
    client = _make_client(return_value=empty_response)
    config = _make_config()
    crawler = PlayerStatsCrawler(client, config, data_root=tmp_path)

    path = crawler.crawl_team(_TEAM_ID, _SEASON)
    assert path is not None
    written = json.loads(path.read_text())
    assert written == empty_response


def test_crawl_team_does_not_filter_unknown_players(tmp_path: Path) -> None:
    """Players not on the roster are written as-is -- no filtering applied."""
    response_with_extra = {
        "id": _TEAM_ID,
        "team_id": _TEAM_ID,
        "stats_data": {
            "players": {
                "known-roster-player": {"stats": {"offense": {"AB": 20}}},
                "not-on-roster-player": {"stats": {"offense": {"AB": 5}}},
            },
            "streaks": {},
            "stats": {},
        },
    }
    client = _make_client(return_value=response_with_extra)
    config = _make_config()
    crawler = PlayerStatsCrawler(client, config, data_root=tmp_path)

    path = crawler.crawl_team(_TEAM_ID, _SEASON)
    assert path is not None
    written = json.loads(path.read_text())
    assert "not-on-roster-player" in written["stats_data"]["players"]


# ---------------------------------------------------------------------------
# AC-2: Idempotency -- fresh file skip
# ---------------------------------------------------------------------------

def test_crawl_team_skips_fresh_file(tmp_path: Path) -> None:
    """A stats.json younger than freshness_hours is not re-fetched."""
    client = _make_client()
    config = _make_config()
    crawler = PlayerStatsCrawler(client, config, freshness_hours=24, data_root=tmp_path)

    dest = tmp_path / _SEASON / "teams" / _TEAM_ID / "stats.json"
    dest.parent.mkdir(parents=True)
    dest.write_text(json.dumps(_SAMPLE_STATS), encoding="utf-8")

    result = crawler.crawl_team(_TEAM_ID, _SEASON)

    assert result is None
    client.get.assert_not_called()


def test_crawl_all_counts_skipped_fresh_files(tmp_path: Path) -> None:
    """crawl_all increments files_skipped for fresh files."""
    client = _make_client()
    config = _make_config([_TEAM_ID])
    crawler = PlayerStatsCrawler(client, config, freshness_hours=24, data_root=tmp_path)

    dest = tmp_path / _SEASON / "teams" / _TEAM_ID / "stats.json"
    dest.parent.mkdir(parents=True)
    dest.write_text(json.dumps(_SAMPLE_STATS), encoding="utf-8")

    result = crawler.crawl_all()

    assert result.files_written == 0
    assert result.files_skipped == 1
    assert result.errors == 0


def test_crawl_team_refetches_stale_file(tmp_path: Path) -> None:
    """A stats.json older than freshness_hours is re-fetched and overwritten."""
    client = _make_client()
    config = _make_config()
    crawler = PlayerStatsCrawler(client, config, freshness_hours=24, data_root=tmp_path)

    dest = tmp_path / _SEASON / "teams" / _TEAM_ID / "stats.json"
    dest.parent.mkdir(parents=True)
    old_content = {"id": _TEAM_ID, "team_id": _TEAM_ID, "stats_data": {"players": {}, "streaks": {}, "stats": {}}}
    dest.write_text(json.dumps(old_content), encoding="utf-8")

    stale_mtime = time.time() - (25 * 3600)
    os.utime(dest, (stale_mtime, stale_mtime))

    result = crawler.crawl_team(_TEAM_ID, _SEASON)

    assert result == dest
    client.get.assert_called_once()
    written = json.loads(dest.read_text())
    assert written == _SAMPLE_STATS


# ---------------------------------------------------------------------------
# AC-4: API error is logged; crawl continues to next team
# ---------------------------------------------------------------------------

def test_crawl_all_continues_after_api_error(tmp_path: Path) -> None:
    """An API error on one team is caught; other teams are still crawled."""
    team_ok = "team-ok-001"
    team_bad = "team-bad-002"

    call_count = 0

    def side_effect(*args: object, **kwargs: object) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise GameChangerAPIError("Server error (HTTP 500)")
        return _SAMPLE_STATS

    client = MagicMock()
    client.get.side_effect = side_effect

    config = _make_config([team_bad, team_ok])
    crawler = PlayerStatsCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.errors == 1
    assert result.files_written == 1
    assert result.files_skipped == 0


def test_crawl_all_logs_error_with_team_id(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """When an API error occurs, the error log includes the team ID."""
    import logging

    client = _make_client(side_effect=GameChangerAPIError("HTTP 500"))
    config = _make_config([_TEAM_ID])
    crawler = PlayerStatsCrawler(client, config, data_root=tmp_path)

    with caplog.at_level(logging.ERROR, logger="src.gamechanger.crawlers.player_stats"):
        crawler.crawl_all()

    assert _TEAM_ID in caplog.text


# ---------------------------------------------------------------------------
# _is_fresh helper
# ---------------------------------------------------------------------------

def test_is_fresh_returns_false_when_file_missing(tmp_path: Path) -> None:
    """_is_fresh returns False when the file does not exist."""
    client = _make_client()
    config = _make_config()
    crawler = PlayerStatsCrawler(client, config, data_root=tmp_path)

    assert crawler._is_fresh(tmp_path / "nonexistent.json", 24) is False


def test_is_fresh_returns_true_for_newly_created_file(tmp_path: Path) -> None:
    """_is_fresh returns True for a file written moments ago."""
    client = _make_client()
    config = _make_config()
    crawler = PlayerStatsCrawler(client, config, data_root=tmp_path)

    f = tmp_path / "fresh.json"
    f.write_text("{}")

    assert crawler._is_fresh(f, 24) is True


def test_freshness_hours_zero_treats_any_file_as_stale(tmp_path: Path) -> None:
    """freshness_hours=0 means any existing file is considered stale."""
    client = _make_client()
    config = _make_config()
    crawler = PlayerStatsCrawler(client, config, freshness_hours=0, data_root=tmp_path)

    dest = tmp_path / _SEASON / "teams" / _TEAM_ID / "stats.json"
    dest.parent.mkdir(parents=True)
    dest.write_text(json.dumps(_SAMPLE_STATS), encoding="utf-8")

    result = crawler.crawl_team(_TEAM_ID, _SEASON)

    assert result == dest
    client.get.assert_called_once()


# ---------------------------------------------------------------------------
# CrawlResult accumulation
# ---------------------------------------------------------------------------

def test_crawl_result_multiple_teams_mixed_outcomes(tmp_path: Path) -> None:
    """CrawlResult accumulates counts across all teams in crawl_all."""
    team_ids = ["team-aaa", "team-bbb", "team-ccc"]

    call_count = 0

    def side_effect(*args: object, **kwargs: object) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise GameChangerAPIError("Simulated error on team-bbb")
        return _SAMPLE_STATS

    client = MagicMock()
    client.get.side_effect = side_effect

    dest_aaa = tmp_path / _SEASON / "teams" / "team-aaa" / "stats.json"
    dest_aaa.parent.mkdir(parents=True)
    dest_aaa.write_text(json.dumps(_SAMPLE_STATS), encoding="utf-8")

    config = _make_config(team_ids)
    crawler = PlayerStatsCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.files_skipped == 1
    assert result.errors == 1
    assert result.files_written == 1
