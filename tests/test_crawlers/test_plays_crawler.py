"""Tests for src/gamechanger/crawlers/plays.py.

All HTTP calls are mocked -- no real network requests are made.
Tests cover: completed games are fetched using event_id as path param,
already-cached games are skipped, missing game-summaries file is handled
gracefully, API errors are logged and crawl continues,
CredentialExpiredError propagates, correct Accept header is used,
CrawlResult counts are accurate.
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
from src.gamechanger.crawlers.plays import PlaysCrawler, _PLAYS_ACCEPT


# ---------------------------------------------------------------------------
# Test fixtures and helpers
# ---------------------------------------------------------------------------

_TEAM_ID = "team-uuid-001"
_SEASON = "2025"

_GAME_STREAM_ID_1 = "stream-aaa-111"
_GAME_STREAM_ID_2 = "stream-bbb-222"
_EVENT_ID_1 = "event-aaa-111"
_EVENT_ID_2 = "event-bbb-222"

_SAMPLE_PLAYS = {
    "sport": "baseball",
    "team_players": {
        "pub-slug-abc": [
            {"id": "player-001", "first_name": "A", "last_name": "One", "number": "1"},
        ],
        "opponent-uuid-999": [
            {"id": "player-002", "first_name": "B", "last_name": "Two", "number": "2"},
        ],
    },
    "plays": [
        {
            "order": 0,
            "inning": 1,
            "half": "top",
            "name_template": {"template": "Walk"},
            "home_score": 0,
            "away_score": 0,
            "did_score_change": False,
            "outs": 0,
            "did_outs_change": False,
            "at_plate_details": [{"template": "Ball 1"}],
            "final_details": [{"template": "${player-001} walks, ${player-002} pitching"}],
            "messages": [],
        },
    ],
}


def _make_summary(
    game_stream_id: str,
    event_id: str,
    game_status: str = "completed",
) -> dict:
    """Build a minimal game-summaries record."""
    return {
        "event_id": event_id,
        "game_status": game_status,
        "game_stream": {
            "id": game_stream_id,
            "game_id": event_id,
            "game_status": game_status,
        },
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
        client.get.return_value = return_value if return_value is not None else _SAMPLE_PLAYS
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
# AC-1: Completed games are fetched and written to plays/ using event_id
# ---------------------------------------------------------------------------


def test_crawl_all_writes_plays_for_completed_game(tmp_path: Path) -> None:
    """Completed game produces a plays file at plays/{event_id}.json."""
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [_make_summary(_GAME_STREAM_ID_1, _EVENT_ID_1, "completed")],
    )
    client = _make_client()
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)

    result = crawler.crawl_all()

    expected = tmp_path / _SEASON / "teams" / _TEAM_ID / "plays" / f"{_EVENT_ID_1}.json"
    assert expected.exists()
    assert json.loads(expected.read_text()) == _SAMPLE_PLAYS
    assert result.files_written == 1
    assert result.files_skipped == 0
    assert result.errors == 0


def test_crawl_all_writes_multiple_completed_games(tmp_path: Path) -> None:
    """Multiple completed games in one game-summaries file all get fetched."""
    records = [
        _make_summary(_GAME_STREAM_ID_1, _EVENT_ID_1, "completed"),
        _make_summary(_GAME_STREAM_ID_2, _EVENT_ID_2, "completed"),
    ]
    _write_summaries(tmp_path, _SEASON, _TEAM_ID, records)
    client = _make_client()
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.files_written == 2
    assert client.get.call_count == 2


def test_written_json_is_unmodified_api_response(tmp_path: Path) -> None:
    """The plays file content exactly matches the raw API response."""
    raw_response = {
        "sport": "baseball",
        "team_players": {},
        "plays": [{"order": 0, "inning": 1}],
    }
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [_make_summary(_GAME_STREAM_ID_1, _EVENT_ID_1, "completed")],
    )
    client = _make_client(return_value=raw_response)
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)

    crawler.crawl_all()

    dest = tmp_path / _SEASON / "teams" / _TEAM_ID / "plays" / f"{_EVENT_ID_1}.json"
    assert json.loads(dest.read_text()) == raw_response


# ---------------------------------------------------------------------------
# AC-2: Already-cached games are skipped (existence-only idempotency)
# ---------------------------------------------------------------------------


def test_existing_plays_file_is_skipped(tmp_path: Path) -> None:
    """A game whose plays file already exists is not re-fetched."""
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [_make_summary(_GAME_STREAM_ID_1, _EVENT_ID_1, "completed")],
    )
    # Pre-populate the plays file.
    dest = tmp_path / _SEASON / "teams" / _TEAM_ID / "plays" / f"{_EVENT_ID_1}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"cached": True}), encoding="utf-8")

    client = _make_client()
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)

    result = crawler.crawl_all()

    client.get.assert_not_called()
    assert result.files_written == 0
    assert result.files_skipped == 1
    assert result.errors == 0


def test_mix_of_cached_and_new_games(tmp_path: Path) -> None:
    """Cached games are skipped; new games are fetched."""
    records = [
        _make_summary(_GAME_STREAM_ID_1, _EVENT_ID_1, "completed"),
        _make_summary(_GAME_STREAM_ID_2, _EVENT_ID_2, "completed"),
    ]
    _write_summaries(tmp_path, _SEASON, _TEAM_ID, records)

    # Pre-populate only game 1.
    cached = tmp_path / _SEASON / "teams" / _TEAM_ID / "plays" / f"{_EVENT_ID_1}.json"
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text("{}", encoding="utf-8")

    client = _make_client()
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.files_skipped == 1
    assert result.files_written == 1
    client.get.assert_called_once_with(
        f"/game-stream-processing/{_EVENT_ID_2}/plays",
        accept=_PLAYS_ACCEPT,
    )


# ---------------------------------------------------------------------------
# AC-3: Missing game-summaries file is handled gracefully
# ---------------------------------------------------------------------------


def test_missing_game_summaries_file_is_skipped_gracefully(tmp_path: Path) -> None:
    """If game_summaries.json does not exist, the team is skipped with no crash."""
    client = _make_client()
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)

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
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)

    with caplog.at_level(logging.WARNING, logger="src.gamechanger.crawlers.plays"):
        crawler.crawl_all()

    assert "not found" in caplog.text or "Game summaries" in caplog.text


# ---------------------------------------------------------------------------
# AC-4: API errors are logged and counted; crawl continues.
#        CredentialExpiredError propagates.
# ---------------------------------------------------------------------------


def test_api_error_is_logged_and_crawl_continues(tmp_path: Path) -> None:
    """An API error on one game is caught; subsequent games are still crawled."""
    records = [
        _make_summary(_GAME_STREAM_ID_1, _EVENT_ID_1, "completed"),
        _make_summary(_GAME_STREAM_ID_2, _EVENT_ID_2, "completed"),
    ]
    _write_summaries(tmp_path, _SEASON, _TEAM_ID, records)

    call_count = 0

    def side_effect(*args: object, **kwargs: object) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise GameChangerAPIError("HTTP 500 Server Error")
        return _SAMPLE_PLAYS

    client = MagicMock()
    client.get.side_effect = side_effect
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.errors == 1
    assert result.files_written == 1


def test_api_error_log_includes_event_id(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Error log includes event_id for traceability."""
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [_make_summary(_GAME_STREAM_ID_1, _EVENT_ID_1, "completed")],
    )
    client = _make_client(side_effect=GameChangerAPIError("HTTP 500"))
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)

    with caplog.at_level(logging.ERROR, logger="src.gamechanger.crawlers.plays"):
        crawler.crawl_all()

    assert _EVENT_ID_1 in caplog.text


def test_credential_expired_error_propagates(tmp_path: Path) -> None:
    """CredentialExpiredError raised during plays fetch aborts crawl_all()."""
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [_make_summary(_GAME_STREAM_ID_1, _EVENT_ID_1, "completed")],
    )
    client = _make_client(side_effect=CredentialExpiredError("Token expired"))
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)

    with pytest.raises(CredentialExpiredError):
        crawler.crawl_all()


# ---------------------------------------------------------------------------
# AC-5: CrawlResult accuracy
# ---------------------------------------------------------------------------


def test_crawl_result_is_crawl_result_instance(tmp_path: Path) -> None:
    """crawl_all always returns a CrawlResult instance."""
    client = _make_client()
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)
    result = crawler.crawl_all()
    assert isinstance(result, CrawlResult)


def test_multiple_teams_accumulate_crawl_result(tmp_path: Path) -> None:
    """crawl_all aggregates counts across all teams."""
    team_a = "team-aaa"
    team_b = "team-bbb"

    _write_summaries(
        tmp_path, _SEASON, team_a,
        [_make_summary("stream-a", "event-aaa", "completed")],
    )
    _write_summaries(
        tmp_path, _SEASON, team_b,
        [_make_summary("stream-b", "event-bbb", "completed")],
    )

    client = _make_client()
    config = _make_config([team_a, team_b])
    crawler = PlaysCrawler(client, config, data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.files_written == 2
    assert result.files_skipped == 0
    assert result.errors == 0
    assert client.get.call_count == 2


# ---------------------------------------------------------------------------
# AC-6: Correct Accept header
# ---------------------------------------------------------------------------


def test_correct_accept_header_is_used(tmp_path: Path) -> None:
    """Plays request uses the plays-specific Accept header."""
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [_make_summary(_GAME_STREAM_ID_1, _EVENT_ID_1, "completed")],
    )
    client = _make_client()
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)

    crawler.crawl_all()

    _, kwargs = client.get.call_args
    assert kwargs.get("accept") == "application/vnd.gc.com.event_plays+json; version=0.0.0"


# ---------------------------------------------------------------------------
# AC-7: Uses event_id, not game_stream.id
# ---------------------------------------------------------------------------


def test_crawl_all_uses_event_id_as_path_param(tmp_path: Path) -> None:
    """The plays API call uses event_id (not game_stream.id) in the URL."""
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [_make_summary(_GAME_STREAM_ID_1, _EVENT_ID_1, "completed")],
    )
    # Confirm the two IDs are distinct in the test fixture.
    assert _EVENT_ID_1 != _GAME_STREAM_ID_1

    client = _make_client()
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)
    crawler.crawl_all()

    # API must be called with event_id, NOT game_stream.id.
    client.get.assert_called_once_with(
        f"/game-stream-processing/{_EVENT_ID_1}/plays",
        accept=_PLAYS_ACCEPT,
    )
    # File must also be named by event_id.
    expected = tmp_path / _SEASON / "teams" / _TEAM_ID / "plays" / f"{_EVENT_ID_1}.json"
    assert expected.exists()


def test_event_id_differs_from_game_stream_id_uses_event_id(tmp_path: Path) -> None:
    """When event_id and game_stream.id differ, event_id is used for the API call."""
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [_make_summary(_GAME_STREAM_ID_1, _EVENT_ID_1, "completed")],
    )
    assert _EVENT_ID_1 != _GAME_STREAM_ID_1

    client = _make_client()
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)
    crawler.crawl_all()

    client.get.assert_called_once_with(
        f"/game-stream-processing/{_EVENT_ID_1}/plays",
        accept=_PLAYS_ACCEPT,
    )
    expected = tmp_path / _SEASON / "teams" / _TEAM_ID / "plays" / f"{_EVENT_ID_1}.json"
    assert expected.exists()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_non_completed_games_are_skipped(tmp_path: Path) -> None:
    """Games with non-completed status are not fetched."""
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [_make_summary(_GAME_STREAM_ID_1, _EVENT_ID_1, "scheduled")],
    )
    client = _make_client()
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)

    result = crawler.crawl_all()

    client.get.assert_not_called()
    assert result.files_written == 0
    assert result.files_skipped == 0


def test_record_missing_event_id_is_counted_as_error(tmp_path: Path) -> None:
    """A completed record with no event_id is counted as an error."""
    bad_record = {
        "game_status": "completed",
        "game_stream": {"id": "stream-bad", "game_id": None},
    }
    _write_summaries(tmp_path, _SEASON, _TEAM_ID, [bad_record])
    client = _make_client()
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)

    result = crawler.crawl_all()

    client.get.assert_not_called()
    assert result.errors == 1


def test_record_with_null_event_id_is_counted_as_error(tmp_path: Path) -> None:
    """A completed record with event_id=null is counted as an error."""
    bad_record = {
        "event_id": None,
        "game_status": "completed",
        "game_stream": {"id": "stream-bad"},
    }
    _write_summaries(tmp_path, _SEASON, _TEAM_ID, [bad_record])
    client = _make_client()
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)

    result = crawler.crawl_all()

    client.get.assert_not_called()
    assert result.errors == 1


def test_game_summaries_not_a_list_treated_as_empty(tmp_path: Path) -> None:
    """If game_summaries.json is not a list, treat as empty (no crash)."""
    dest = tmp_path / _SEASON / "teams" / _TEAM_ID / "game_summaries.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"not": "a list"}), encoding="utf-8")

    client = _make_client()
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)

    result = crawler.crawl_all()

    client.get.assert_not_called()
    assert result.files_written == 0
    assert result.errors == 0


def test_summary_log_is_produced(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """crawl_all logs a summary of fetched/cached/errored counts."""
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [_make_summary(_GAME_STREAM_ID_1, _EVENT_ID_1, "completed")],
    )
    client = _make_client()
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)

    with caplog.at_level(logging.INFO, logger="src.gamechanger.crawlers.plays"):
        crawler.crawl_all()

    assert "PlaysCrawler complete" in caplog.text


def test_unexpected_exception_is_caught_and_counted(tmp_path: Path) -> None:
    """Unexpected (non-API) exceptions are caught, logged, and counted."""
    _write_summaries(
        tmp_path, _SEASON, _TEAM_ID,
        [_make_summary(_GAME_STREAM_ID_1, _EVENT_ID_1, "completed")],
    )
    client = _make_client(side_effect=RuntimeError("unexpected"))
    crawler = PlaysCrawler(client, _make_config(), data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.errors == 1
    assert result.files_written == 0
