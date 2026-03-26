"""Tests for src/gamechanger/crawlers/spray_chart.py.

All HTTP calls are mocked -- no real network requests are made.
Tests cover: skip-on-existing behavior, CrawlResult counting, error handling
for API failures, CredentialExpiredError propagation, missing game-summaries
handling, and correct Accept header and URL construction.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.gamechanger.client import CredentialExpiredError, GameChangerAPIError
from src.gamechanger.config import CrawlConfig, TeamEntry
from src.gamechanger.crawlers import CrawlResult
from src.gamechanger.crawlers.spray_chart import SprayChartCrawler, _PLAYER_STATS_ACCEPT


# ---------------------------------------------------------------------------
# Test fixtures and helpers
# ---------------------------------------------------------------------------

_TEAM_ID = "team-uuid-001"
_SEASON = "2025"

_EVENT_ID_1 = "event-aaa-111"
_EVENT_ID_2 = "event-bbb-222"

_SAMPLE_PLAYER_STATS = {
    "stream_id": "stream-aaa-111",
    "team_id": _TEAM_ID,
    "event_id": _EVENT_ID_1,
    "player_stats": {"players": {}},
    "cumulative_player_stats": {"players": {}},
    "spray_chart_data": {
        "offense": {
            "player-uuid-1": [
                {
                    "code": "ball_in_play",
                    "id": "event-gc-uuid-1",
                    "attributes": {
                        "playResult": "single",
                        "playType": "hard_ground_ball",
                        "defenders": [
                            {"error": False, "position": "CF", "location": {"x": 129.0, "y": 79.0}}
                        ],
                    },
                    "createdAt": 1752607496602,
                }
            ]
        },
        "defense": {},
    },
}


def _make_summary(
    event_id: str,
    game_status: str = "completed",
) -> dict:
    """Build a minimal game-summaries record."""
    return {
        "event_id": event_id,
        "game_status": game_status,
    }


def _make_config(team_ids: list[str] | None = None) -> CrawlConfig:
    """Build a CrawlConfig with the given team IDs (or a single default team)."""
    ids = team_ids if team_ids is not None else [_TEAM_ID]
    teams = [TeamEntry(id=tid, name=f"Team {tid}", classification="jv") for tid in ids]
    return CrawlConfig(season=_SEASON, member_teams=teams)


def _make_client(
    return_value: object = None,
    side_effect: Exception | None = None,
) -> MagicMock:
    """Return a mock GameChangerClient."""
    client = MagicMock()
    if side_effect is not None:
        client.get.side_effect = side_effect
    else:
        client.get.return_value = (
            return_value if return_value is not None else _SAMPLE_PLAYER_STATS
        )
    return client


def _write_summaries(
    tmp_path: Path,
    season: str,
    team_id: str,
    records: list[dict],
) -> Path:
    """Write a game_summaries.json file for a team and return its path."""
    dest = tmp_path / season / "teams" / team_id / "game_summaries.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(records), encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# AC-1: Constructor pattern
# ---------------------------------------------------------------------------

def test_constructor_accepts_client_config_and_data_root(tmp_path: Path) -> None:
    """SprayChartCrawler can be constructed with client, config, and data_root."""
    client = _make_client()
    config = _make_config()
    crawler = SprayChartCrawler(client, config, data_root=tmp_path)
    assert crawler is not None


# ---------------------------------------------------------------------------
# AC-2 / AC-4: Completed games are fetched and written
# ---------------------------------------------------------------------------

def test_crawl_all_writes_spray_file_for_completed_game(tmp_path: Path) -> None:
    """Completed game produces a spray chart file under spray/ subdirectory."""
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [_make_summary(_EVENT_ID_1, "completed")],
    )
    client = _make_client()
    crawler = SprayChartCrawler(client, _make_config(), data_root=tmp_path)

    result = crawler.crawl_all()

    expected = tmp_path / _SEASON / "teams" / _TEAM_ID / "spray" / f"{_EVENT_ID_1}.json"
    assert expected.exists()
    assert json.loads(expected.read_text()) == _SAMPLE_PLAYER_STATS
    assert result.files_written == 1
    assert result.files_skipped == 0
    assert result.errors == 0


def test_crawl_all_uses_correct_api_url(tmp_path: Path) -> None:
    """API call uses /teams/{team_id}/schedule/events/{event_id}/player-stats."""
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [_make_summary(_EVENT_ID_1, "completed")],
    )
    client = _make_client()
    crawler = SprayChartCrawler(client, _make_config(), data_root=tmp_path)

    crawler.crawl_all()

    client.get.assert_called_once_with(
        f"/teams/{_TEAM_ID}/schedule/events/{_EVENT_ID_1}/player-stats",
        accept=_PLAYER_STATS_ACCEPT,
    )


# ---------------------------------------------------------------------------
# AC-3: Accept header
# ---------------------------------------------------------------------------

def test_correct_accept_header_is_used(tmp_path: Path) -> None:
    """Player-stats request uses 'application/json, text/plain, */*' Accept header."""
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [_make_summary(_EVENT_ID_1, "completed")],
    )
    client = _make_client()
    crawler = SprayChartCrawler(client, _make_config(), data_root=tmp_path)

    crawler.crawl_all()

    _, kwargs = client.get.call_args
    assert kwargs.get("accept") == "application/json, text/plain, */*"


# ---------------------------------------------------------------------------
# AC-5: Skip-on-existing behavior
# ---------------------------------------------------------------------------

def test_existing_spray_file_is_skipped(tmp_path: Path) -> None:
    """A game whose spray file already exists is not re-fetched."""
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [_make_summary(_EVENT_ID_1, "completed")],
    )
    dest = tmp_path / _SEASON / "teams" / _TEAM_ID / "spray" / f"{_EVENT_ID_1}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"cached": True}), encoding="utf-8")

    client = _make_client()
    crawler = SprayChartCrawler(client, _make_config(), data_root=tmp_path)

    result = crawler.crawl_all()

    client.get.assert_not_called()
    assert result.files_written == 0
    assert result.files_skipped == 1
    assert result.errors == 0


def test_mix_of_cached_and_new_games(tmp_path: Path) -> None:
    """Cached games are skipped; new games are fetched."""
    records = [
        _make_summary(_EVENT_ID_1, "completed"),
        _make_summary(_EVENT_ID_2, "completed"),
    ]
    _write_summaries(tmp_path, _SEASON, _TEAM_ID, records)

    cached = tmp_path / _SEASON / "teams" / _TEAM_ID / "spray" / f"{_EVENT_ID_1}.json"
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text("{}", encoding="utf-8")

    client = _make_client()
    crawler = SprayChartCrawler(client, _make_config(), data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.files_skipped == 1
    assert result.files_written == 1
    client.get.assert_called_once_with(
        f"/teams/{_TEAM_ID}/schedule/events/{_EVENT_ID_2}/player-stats",
        accept=_PLAYER_STATS_ACCEPT,
    )


# ---------------------------------------------------------------------------
# AC-6: CrawlResult counting
# ---------------------------------------------------------------------------

def test_crawl_result_is_crawl_result_instance(tmp_path: Path) -> None:
    """crawl_all always returns a CrawlResult instance."""
    client = _make_client()
    crawler = SprayChartCrawler(client, _make_config(), data_root=tmp_path)
    result = crawler.crawl_all()
    assert isinstance(result, CrawlResult)


def test_multiple_completed_games_counted_correctly(tmp_path: Path) -> None:
    """files_written reflects all fetched games."""
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [
            _make_summary(_EVENT_ID_1, "completed"),
            _make_summary(_EVENT_ID_2, "completed"),
        ],
    )
    client = _make_client()
    crawler = SprayChartCrawler(client, _make_config(), data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.files_written == 2
    assert result.files_skipped == 0
    assert result.errors == 0
    assert client.get.call_count == 2


def test_multiple_teams_accumulate_crawl_result(tmp_path: Path) -> None:
    """crawl_all aggregates counts across all teams."""
    team_a = "team-aaa"
    team_b = "team-bbb"

    _write_summaries(
        tmp_path, _SEASON, team_a,
        [_make_summary("event-aaa", "completed")],
    )
    _write_summaries(
        tmp_path, _SEASON, team_b,
        [_make_summary("event-bbb", "completed")],
    )

    client = _make_client()
    config = _make_config([team_a, team_b])
    crawler = SprayChartCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.files_written == 2
    assert result.errors == 0
    assert client.get.call_count == 2


# ---------------------------------------------------------------------------
# AC-8: Error handling
# ---------------------------------------------------------------------------

def test_api_error_is_counted_and_crawl_continues(tmp_path: Path) -> None:
    """An API error on one game is caught; subsequent games are still crawled."""
    records = [
        _make_summary(_EVENT_ID_1, "completed"),
        _make_summary(_EVENT_ID_2, "completed"),
    ]
    _write_summaries(tmp_path, _SEASON, _TEAM_ID, records)

    call_count = 0

    def side_effect(*args: object, **kwargs: object) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise GameChangerAPIError("HTTP 500 Server Error")
        return _SAMPLE_PLAYER_STATS

    client = MagicMock()
    client.get.side_effect = side_effect
    crawler = SprayChartCrawler(client, _make_config(), data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.errors == 1
    assert result.files_written == 1


def test_api_error_log_includes_event_id(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Error log includes the event_id of the failing game."""
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [_make_summary(_EVENT_ID_1, "completed")],
    )
    client = _make_client(side_effect=GameChangerAPIError("HTTP 500"))
    crawler = SprayChartCrawler(client, _make_config(), data_root=tmp_path)

    with caplog.at_level(logging.ERROR, logger="src.gamechanger.crawlers.spray_chart"):
        crawler.crawl_all()

    assert _EVENT_ID_1 in caplog.text


def test_credential_expired_error_propagates(tmp_path: Path) -> None:
    """CredentialExpiredError raised during fetch aborts crawl_all()."""
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [_make_summary(_EVENT_ID_1, "completed")],
    )
    client = _make_client(side_effect=CredentialExpiredError("Token expired"))
    crawler = SprayChartCrawler(client, _make_config(), data_root=tmp_path)

    with pytest.raises(CredentialExpiredError):
        crawler.crawl_all()


# ---------------------------------------------------------------------------
# AC-9: Non-completed games are skipped
# ---------------------------------------------------------------------------

def test_scheduled_game_is_not_fetched(tmp_path: Path) -> None:
    """A game with game_status='scheduled' is not fetched."""
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [_make_summary(_EVENT_ID_1, "scheduled")],
    )
    client = _make_client()
    crawler = SprayChartCrawler(client, _make_config(), data_root=tmp_path)

    result = crawler.crawl_all()

    client.get.assert_not_called()
    assert result.files_written == 0


# ---------------------------------------------------------------------------
# Missing game-summaries file is handled gracefully
# ---------------------------------------------------------------------------

def test_missing_game_summaries_file_is_skipped_gracefully(tmp_path: Path) -> None:
    """If game_summaries.json does not exist, the team is skipped with no crash."""
    client = _make_client()
    crawler = SprayChartCrawler(client, _make_config(), data_root=tmp_path)

    result = crawler.crawl_all()

    client.get.assert_not_called()
    assert result.files_written == 0
    assert result.files_skipped == 0
    assert result.errors == 0


def test_missing_summaries_file_logs_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A warning is logged when the game-summaries file does not exist."""
    client = _make_client()
    crawler = SprayChartCrawler(client, _make_config(), data_root=tmp_path)

    with caplog.at_level(logging.WARNING, logger="src.gamechanger.crawlers.spray_chart"):
        crawler.crawl_all()

    assert "not found" in caplog.text or "Game summaries" in caplog.text


# ---------------------------------------------------------------------------
# Edge case: event_id missing from record
# ---------------------------------------------------------------------------

def test_record_missing_event_id_is_counted_as_error(tmp_path: Path) -> None:
    """A completed record with no event_id is counted as an error."""
    bad_record = {"game_status": "completed"}
    _write_summaries(tmp_path, _SEASON, _TEAM_ID, [bad_record])
    client = _make_client()
    crawler = SprayChartCrawler(client, _make_config(), data_root=tmp_path)

    result = crawler.crawl_all()

    client.get.assert_not_called()
    assert result.errors == 1


# ---------------------------------------------------------------------------
# Summary log
# ---------------------------------------------------------------------------

def test_summary_log_is_produced(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """crawl_all logs a summary of fetched/cached/errored counts."""
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [_make_summary(_EVENT_ID_1, "completed")],
    )
    client = _make_client()
    crawler = SprayChartCrawler(client, _make_config(), data_root=tmp_path)

    with caplog.at_level(logging.INFO, logger="src.gamechanger.crawlers.spray_chart"):
        crawler.crawl_all()

    assert "SprayChartCrawler complete" in caplog.text
