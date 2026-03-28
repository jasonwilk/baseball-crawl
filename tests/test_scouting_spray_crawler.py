"""Tests for src/gamechanger/crawlers/scouting_spray.py.

All HTTP calls are mocked -- no real network requests are made.
Tests cover: happy path, skip-on-existing (idempotency), opponent without
gc_uuid, CredentialExpiredError propagation, per-game API error tolerance,
missing games.json, event_id-missing edge case, and crawl_all aggregation.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.gamechanger.client import CredentialExpiredError, GameChangerAPIError
from src.gamechanger.crawlers import CrawlResult
from src.gamechanger.crawlers.scouting_spray import (
    ScoutingSprayChartCrawler,
    _PLAYER_STATS_ACCEPT,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PUBLIC_ID = "opp-team-public-id"
_GC_UUID = "aaaabbbb-cccc-dddd-eeee-ffffffffffff"
_SEASON = "2025-spring-hs"
_EVENT_ID_1 = "event-001"
_EVENT_ID_2 = "event-002"

_SAMPLE_PLAYER_STATS = {
    "stream_id": "stream-001",
    "event_id": _EVENT_ID_1,
    "player_stats": {"players": {}},
    "cumulative_player_stats": {"players": {}},
    "spray_chart_data": {
        "offense": {
            "player-uuid-1": [
                {
                    "code": "ball_in_play",
                    "id": "gc-event-001",
                    "attributes": {
                        "playResult": "single",
                        "playType": "hard_ground_ball",
                        "defenders": [
                            {
                                "error": False,
                                "position": "CF",
                                "location": {"x": 129.0, "y": 79.0},
                            }
                        ],
                    },
                }
            ]
        },
        "defense": {},
    },
}


# ---------------------------------------------------------------------------
# In-memory DB helpers
# ---------------------------------------------------------------------------


def _make_db(
    public_id: str = _PUBLIC_ID,
    gc_uuid: str | None = _GC_UUID,
    add_opponent_link: bool = True,
) -> sqlite3.Connection:
    """Return an in-memory SQLite connection with minimal scouting schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(
        """
        CREATE TABLE teams (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            membership_type TEXT NOT NULL DEFAULT 'tracked',
            public_id       TEXT UNIQUE,
            gc_uuid         TEXT
        );
        CREATE TABLE opponent_links (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            public_id  TEXT,
            is_hidden  INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.execute(
        "INSERT INTO teams (name, public_id, gc_uuid) VALUES (?, ?, ?)",
        (public_id, public_id, gc_uuid),
    )
    if add_opponent_link:
        conn.execute(
            "INSERT INTO opponent_links (public_id, is_hidden) VALUES (?, 0)",
            (public_id,),
        )
    conn.commit()
    return conn


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


def _write_games_json(
    tmp_path: Path,
    season: str,
    public_id: str,
    games: list[dict],
) -> Path:
    """Write games.json to the scouting directory and return its path."""
    dest = tmp_path / season / "scouting" / public_id / "games.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(games), encoding="utf-8")
    return dest


def _make_game(
    event_id: str = _EVENT_ID_1,
    game_status: str = "completed",
) -> dict:
    """Build a minimal game record matching the public games.json schema."""
    return {"id": event_id, "game_status": game_status}


# ---------------------------------------------------------------------------
# AC-1: Completed game → file written at correct path
# ---------------------------------------------------------------------------


def test_crawl_team_writes_spray_file_for_completed_game(tmp_path: Path) -> None:
    """A completed game produces a spray file under spray/ subdirectory."""
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_team(_PUBLIC_ID)

    expected = tmp_path / _SEASON / "scouting" / _PUBLIC_ID / "spray" / f"{_EVENT_ID_1}.json"
    assert expected.exists()
    assert json.loads(expected.read_text()) == _SAMPLE_PLAYER_STATS
    assert result.files_written == 1
    assert result.files_skipped == 0
    assert result.errors == 0


def test_crawl_team_uses_correct_api_url(tmp_path: Path) -> None:
    """API call uses /teams/{gc_uuid}/schedule/events/{event_id}/player-stats."""
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    crawler.crawl_team(_PUBLIC_ID)

    client.get.assert_called_once_with(
        f"/teams/{_GC_UUID}/schedule/events/{_EVENT_ID_1}/player-stats",
        accept=_PLAYER_STATS_ACCEPT,
    )


def test_correct_accept_header_used(tmp_path: Path) -> None:
    """Player-stats request uses 'application/json, text/plain, */*' Accept header."""
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    crawler.crawl_team(_PUBLIC_ID)

    _, kwargs = client.get.call_args
    assert kwargs.get("accept") == "application/json, text/plain, */*"


def test_spray_file_path_includes_season_scouting_public_id(tmp_path: Path) -> None:
    """File is written to data/raw/{season}/scouting/{public_id}/spray/{event_id}.json."""
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    crawler.crawl_team(_PUBLIC_ID)

    dest = tmp_path / _SEASON / "scouting" / _PUBLIC_ID / "spray" / f"{_EVENT_ID_1}.json"
    assert dest.exists()


# ---------------------------------------------------------------------------
# AC-2: Opponent without gc_uuid is skipped
# ---------------------------------------------------------------------------


def test_opponent_without_gc_uuid_is_skipped_with_info(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Opponent with NULL gc_uuid logs INFO and returns empty result."""
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    db = _make_db(gc_uuid=None)
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    with caplog.at_level(logging.INFO, logger="src.gamechanger.crawlers.scouting_spray"):
        result = crawler.crawl_team(_PUBLIC_ID)

    client.get.assert_not_called()
    assert result.files_written == 0
    assert result.files_skipped == 0
    assert result.errors == 0
    assert _PUBLIC_ID in caplog.text


def test_opponent_not_in_teams_table_is_skipped(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Opponent with no teams row (gc_uuid lookup returns None) is skipped."""
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    db = sqlite3.connect(":memory:")
    db.executescript(
        "CREATE TABLE teams (id INTEGER PRIMARY KEY, name TEXT, public_id TEXT UNIQUE, gc_uuid TEXT);"
        "CREATE TABLE opponent_links (id INTEGER PRIMARY KEY, public_id TEXT, is_hidden INTEGER DEFAULT 0);"
    )
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    with caplog.at_level(logging.INFO, logger="src.gamechanger.crawlers.scouting_spray"):
        result = crawler.crawl_team(_PUBLIC_ID)

    client.get.assert_not_called()
    assert result.errors == 0


# ---------------------------------------------------------------------------
# AC-3: Existence-only idempotency (skip if file exists)
# ---------------------------------------------------------------------------


def test_existing_spray_file_is_skipped(tmp_path: Path) -> None:
    """A game whose spray file already exists is not re-fetched."""
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    dest = tmp_path / _SEASON / "scouting" / _PUBLIC_ID / "spray" / f"{_EVENT_ID_1}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"cached": True}), encoding="utf-8")

    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_team(_PUBLIC_ID)

    client.get.assert_not_called()
    assert result.files_skipped == 1
    assert result.files_written == 0
    assert result.errors == 0


def test_mix_of_cached_and_new_games(tmp_path: Path) -> None:
    """Cached games are skipped; new games are fetched."""
    _write_games_json(
        tmp_path,
        _SEASON,
        _PUBLIC_ID,
        [_make_game(_EVENT_ID_1), _make_game(_EVENT_ID_2)],
    )
    cached = tmp_path / _SEASON / "scouting" / _PUBLIC_ID / "spray" / f"{_EVENT_ID_1}.json"
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text("{}", encoding="utf-8")

    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_team(_PUBLIC_ID)

    assert result.files_skipped == 1
    assert result.files_written == 1
    client.get.assert_called_once_with(
        f"/teams/{_GC_UUID}/schedule/events/{_EVENT_ID_2}/player-stats",
        accept=_PLAYER_STATS_ACCEPT,
    )


def test_null_spray_chart_data_is_written(tmp_path: Path) -> None:
    """Response with null spray_chart_data is written (not skipped)."""
    payload = {**_SAMPLE_PLAYER_STATS, "spray_chart_data": None}
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    db = _make_db()
    client = _make_client(return_value=payload)
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_team(_PUBLIC_ID)

    dest = tmp_path / _SEASON / "scouting" / _PUBLIC_ID / "spray" / f"{_EVENT_ID_1}.json"
    assert dest.exists()
    assert result.files_written == 1


# ---------------------------------------------------------------------------
# AC-4: Error handling
# ---------------------------------------------------------------------------


def test_credential_expired_error_propagates(tmp_path: Path) -> None:
    """CredentialExpiredError raised during fetch propagates immediately."""
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    db = _make_db()
    client = _make_client(side_effect=CredentialExpiredError("Token expired"))
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    with pytest.raises(CredentialExpiredError):
        crawler.crawl_team(_PUBLIC_ID)


def test_api_error_is_counted_and_crawl_continues(tmp_path: Path) -> None:
    """A GameChangerAPIError on one game is caught; subsequent games continue."""
    _write_games_json(
        tmp_path,
        _SEASON,
        _PUBLIC_ID,
        [_make_game(_EVENT_ID_1), _make_game(_EVENT_ID_2)],
    )
    call_count = 0

    def side_effect(*args: object, **kwargs: object) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise GameChangerAPIError("HTTP 500")
        return _SAMPLE_PLAYER_STATS

    db = _make_db()
    client = MagicMock()
    client.get.side_effect = side_effect
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_team(_PUBLIC_ID)

    assert result.errors == 1
    assert result.files_written == 1


def test_api_error_log_includes_event_id(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Error log includes event_id and public_id of the failing game."""
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    db = _make_db()
    client = _make_client(side_effect=GameChangerAPIError("HTTP 500"))
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    with caplog.at_level(logging.ERROR, logger="src.gamechanger.crawlers.scouting_spray"):
        crawler.crawl_team(_PUBLIC_ID)

    assert _EVENT_ID_1 in caplog.text


def test_credential_expired_propagates_through_crawl_all(tmp_path: Path) -> None:
    """CredentialExpiredError from crawl_team propagates out of crawl_all."""
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    db = _make_db()
    client = _make_client(side_effect=CredentialExpiredError("expired"))
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    with pytest.raises(CredentialExpiredError):
        crawler.crawl_all()


# ---------------------------------------------------------------------------
# Missing games.json
# ---------------------------------------------------------------------------


def test_no_games_json_is_skipped_gracefully(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """If no games.json exists for the opponent, crawl_team returns empty result."""
    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    with caplog.at_level(logging.WARNING, logger="src.gamechanger.crawlers.scouting_spray"):
        result = crawler.crawl_team(_PUBLIC_ID)

    client.get.assert_not_called()
    assert result.files_written == 0
    assert result.files_skipped == 0
    assert result.errors == 0
    assert "No games.json" in caplog.text


def test_non_completed_game_not_fetched(tmp_path: Path) -> None:
    """A game with game_status='scheduled' is not fetched."""
    _write_games_json(
        tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1, game_status="scheduled")]
    )
    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_team(_PUBLIC_ID)

    client.get.assert_not_called()
    assert result.files_written == 0


# ---------------------------------------------------------------------------
# Edge case: game missing 'id' field
# ---------------------------------------------------------------------------


def test_game_missing_id_field_is_counted_as_error(tmp_path: Path) -> None:
    """A completed game record with no 'id' field is counted as an error."""
    bad_game = {"game_status": "completed"}  # no 'id'
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [bad_game])
    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_team(_PUBLIC_ID)

    client.get.assert_not_called()
    assert result.errors == 1


# ---------------------------------------------------------------------------
# crawl_all aggregation
# ---------------------------------------------------------------------------

_PUBLIC_ID_2 = "opp-team-2"
_GC_UUID_2 = "11112222-3333-4444-5555-666677778888"


def _make_db_two_opponents(tmp_path: Path) -> sqlite3.Connection:
    """Return an in-memory DB with two opponents, both with gc_uuid."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            membership_type TEXT NOT NULL DEFAULT 'tracked',
            public_id TEXT UNIQUE,
            gc_uuid TEXT
        );
        CREATE TABLE opponent_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            public_id TEXT,
            is_hidden INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.execute(
        "INSERT INTO teams (name, public_id, gc_uuid) VALUES (?, ?, ?)",
        (_PUBLIC_ID, _PUBLIC_ID, _GC_UUID),
    )
    conn.execute(
        "INSERT INTO teams (name, public_id, gc_uuid) VALUES (?, ?, ?)",
        (_PUBLIC_ID_2, _PUBLIC_ID_2, _GC_UUID_2),
    )
    conn.execute(
        "INSERT INTO opponent_links (public_id, is_hidden) VALUES (?, 0)", (_PUBLIC_ID,)
    )
    conn.execute(
        "INSERT INTO opponent_links (public_id, is_hidden) VALUES (?, 0)", (_PUBLIC_ID_2,)
    )
    conn.commit()
    return conn


def test_crawl_all_aggregates_across_opponents(tmp_path: Path) -> None:
    """crawl_all aggregates files_written and files_skipped across opponents."""
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID_2, [_make_game(_EVENT_ID_2)])
    db = _make_db_two_opponents(tmp_path)
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.files_written == 2
    assert result.errors == 0
    assert client.get.call_count == 2


def test_crawl_all_skips_hidden_opponents(tmp_path: Path) -> None:
    """crawl_all ignores opponents with is_hidden=1 in opponent_links."""
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    db = sqlite3.connect(":memory:")
    db.executescript(
        """
        CREATE TABLE teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            membership_type TEXT NOT NULL DEFAULT 'tracked',
            public_id TEXT UNIQUE,
            gc_uuid TEXT
        );
        CREATE TABLE opponent_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            public_id TEXT,
            is_hidden INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    db.execute(
        "INSERT INTO teams (name, public_id, gc_uuid) VALUES (?, ?, ?)",
        (_PUBLIC_ID, _PUBLIC_ID, _GC_UUID),
    )
    db.execute(
        "INSERT INTO opponent_links (public_id, is_hidden) VALUES (?, 1)",
        (_PUBLIC_ID,),
    )
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_all()

    client.get.assert_not_called()
    assert result.files_written == 0


def test_crawl_all_returns_crawl_result_instance(tmp_path: Path) -> None:
    """crawl_all always returns a CrawlResult instance."""
    db = _make_db(add_opponent_link=False)
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_all()

    assert isinstance(result, CrawlResult)


def test_crawl_all_logs_summary(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """crawl_all logs a completion summary."""
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    with caplog.at_level(logging.INFO, logger="src.gamechanger.crawlers.scouting_spray"):
        crawler.crawl_all()

    assert "ScoutingSprayChartCrawler complete" in caplog.text


# ---------------------------------------------------------------------------
# AC-8: Boxscore-UUID fallback tests
# ---------------------------------------------------------------------------

_OPPONENT_UUID = "99990000-aaaa-bbbb-cccc-ddddeeee1111"


def _write_boxscore(
    tmp_path: Path,
    season: str,
    public_id: str,
    event_id: str,
    opponent_uuid: str,
) -> Path:
    """Write a minimal boxscore JSON file with two top-level keys.

    The boxscore has two keys: the scouted team's ``public_id`` (slug) and
    the opponent's UUID.  This mirrors the real GameChanger boxscore format
    per TN-1.
    """
    dest = tmp_path / season / "scouting" / public_id / "boxscores" / f"{event_id}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    boxscore = {
        public_id: {"batting": {}, "pitching": {}},
        opponent_uuid: {"batting": {}, "pitching": {}},
    }
    dest.write_text(json.dumps(boxscore), encoding="utf-8")
    return dest


def test_fallback_path_crawls_spray_via_boxscore_uuids(tmp_path: Path) -> None:
    """AC-8a: gc_uuid=NULL + cached boxscores => spray files written via fallback."""
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    _write_boxscore(tmp_path, _SEASON, _PUBLIC_ID, _EVENT_ID_1, _OPPONENT_UUID)
    db = _make_db(gc_uuid=None)
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_team(_PUBLIC_ID)

    expected = tmp_path / _SEASON / "scouting" / _PUBLIC_ID / "spray" / f"{_EVENT_ID_1}.json"
    assert expected.exists()
    assert result.files_written == 1
    assert result.errors == 0
    # API called with the UUID extracted from the boxscore (opponent's UUID).
    client.get.assert_called_once_with(
        f"/teams/{_OPPONENT_UUID}/schedule/events/{_EVENT_ID_1}/player-stats",
        accept=_PLAYER_STATS_ACCEPT,
    )


def test_fallback_no_boxscores_returns_empty(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-8b: gc_uuid=NULL + no boxscores => INFO log, empty CrawlResult."""
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    db = _make_db(gc_uuid=None)
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    with caplog.at_level(logging.INFO, logger="src.gamechanger.crawlers.scouting_spray"):
        result = crawler.crawl_team(_PUBLIC_ID)

    client.get.assert_not_called()
    assert result.files_written == 0
    assert result.files_skipped == 0
    assert result.errors == 0
    assert "No gc_uuid and no boxscore UUIDs" in caplog.text


def test_direct_uuid_path_does_not_scan_boxscores(tmp_path: Path) -> None:
    """AC-8c: gc_uuid available => direct path used, no boxscore scanning."""
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    # Write a boxscore that should NOT be scanned.
    _write_boxscore(tmp_path, _SEASON, _PUBLIC_ID, _EVENT_ID_1, _OPPONENT_UUID)
    db = _make_db(gc_uuid=_GC_UUID)
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_team(_PUBLIC_ID)

    assert result.files_written == 1
    # API called with the team's own gc_uuid, NOT the boxscore-extracted UUID.
    client.get.assert_called_once_with(
        f"/teams/{_GC_UUID}/schedule/events/{_EVENT_ID_1}/player-stats",
        accept=_PLAYER_STATS_ACCEPT,
    )


def test_fallback_mixed_some_games_have_boxscores(tmp_path: Path) -> None:
    """AC-8d: Only games with cached boxscores are crawled; others skipped."""
    _write_games_json(
        tmp_path,
        _SEASON,
        _PUBLIC_ID,
        [_make_game(_EVENT_ID_1), _make_game(_EVENT_ID_2)],
    )
    # Only event-001 has a boxscore; event-002 does not.
    _write_boxscore(tmp_path, _SEASON, _PUBLIC_ID, _EVENT_ID_1, _OPPONENT_UUID)
    db = _make_db(gc_uuid=None)
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_team(_PUBLIC_ID)

    assert result.files_written == 1
    assert result.files_skipped == 0
    assert result.errors == 0
    # Only event-001 should be fetched (has boxscore UUID).
    client.get.assert_called_once_with(
        f"/teams/{_OPPONENT_UUID}/schedule/events/{_EVENT_ID_1}/player-stats",
        accept=_PLAYER_STATS_ACCEPT,
    )
    # event-002 spray file should NOT exist.
    missing = tmp_path / _SEASON / "scouting" / _PUBLIC_ID / "spray" / f"{_EVENT_ID_2}.json"
    assert not missing.exists()


def test_fallback_idempotency_skips_existing_spray_file(tmp_path: Path) -> None:
    """AC-7: Fallback path skips games whose spray file already exists."""
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    _write_boxscore(tmp_path, _SEASON, _PUBLIC_ID, _EVENT_ID_1, _OPPONENT_UUID)
    # Pre-create the spray file.
    spray_file = tmp_path / _SEASON / "scouting" / _PUBLIC_ID / "spray" / f"{_EVENT_ID_1}.json"
    spray_file.parent.mkdir(parents=True, exist_ok=True)
    spray_file.write_text(json.dumps({"cached": True}), encoding="utf-8")
    db = _make_db(gc_uuid=None)
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_team(_PUBLIC_ID)

    client.get.assert_not_called()
    assert result.files_skipped == 1
    assert result.files_written == 0


def test_fallback_credential_expired_propagates(tmp_path: Path) -> None:
    """AC-5: CredentialExpiredError propagates from the fallback path."""
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    _write_boxscore(tmp_path, _SEASON, _PUBLIC_ID, _EVENT_ID_1, _OPPONENT_UUID)
    db = _make_db(gc_uuid=None)
    client = _make_client(side_effect=CredentialExpiredError("expired"))
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    with pytest.raises(CredentialExpiredError):
        crawler.crawl_team(_PUBLIC_ID)


def test_fallback_api_error_counted_and_continues(tmp_path: Path) -> None:
    """AC-6: API errors in fallback path are caught and counted."""
    _write_games_json(
        tmp_path,
        _SEASON,
        _PUBLIC_ID,
        [_make_game(_EVENT_ID_1), _make_game(_EVENT_ID_2)],
    )
    _write_boxscore(tmp_path, _SEASON, _PUBLIC_ID, _EVENT_ID_1, _OPPONENT_UUID)
    _write_boxscore(tmp_path, _SEASON, _PUBLIC_ID, _EVENT_ID_2, _OPPONENT_UUID)

    call_count = 0

    def side_effect(*args: object, **kwargs: object) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise GameChangerAPIError("HTTP 500")
        return _SAMPLE_PLAYER_STATS

    db = _make_db(gc_uuid=None)
    client = MagicMock()
    client.get.side_effect = side_effect
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_team(_PUBLIC_ID)

    assert result.errors == 1
    assert result.files_written == 1


def test_boxscore_uuid_regex_ignores_slug_keys(tmp_path: Path) -> None:
    """AC-4: UUID regex correctly distinguishes UUIDs from public_id slugs."""
    # Boxscore with a slug key (not a UUID) and a UUID key.
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    _write_boxscore(tmp_path, _SEASON, _PUBLIC_ID, _EVENT_ID_1, _OPPONENT_UUID)
    db = _make_db(gc_uuid=None)
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_team(_PUBLIC_ID)

    # The slug key (_PUBLIC_ID = "opp-team-public-id") is not a UUID, so only
    # _OPPONENT_UUID should be extracted and used for the API call.
    client.get.assert_called_once_with(
        f"/teams/{_OPPONENT_UUID}/schedule/events/{_EVENT_ID_1}/player-stats",
        accept=_PLAYER_STATS_ACCEPT,
    )
    assert result.files_written == 1


# ---------------------------------------------------------------------------
# Multi-season support: games.json files across multiple seasons
# ---------------------------------------------------------------------------


def test_crawl_team_handles_multiple_seasons(tmp_path: Path) -> None:
    """crawl_team processes games.json from all seasons found on disk."""
    season_a = "2024-spring-hs"
    season_b = "2025-spring-hs"
    event_a = "event-2024-001"
    event_b = "event-2025-001"
    _write_games_json(tmp_path, season_a, _PUBLIC_ID, [_make_game(event_a)])
    _write_games_json(tmp_path, season_b, _PUBLIC_ID, [_make_game(event_b)])
    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_team(_PUBLIC_ID)

    assert result.files_written == 2
    assert client.get.call_count == 2


# ---------------------------------------------------------------------------
# E-176-04: Direct-add team discovery in crawl_all
# ---------------------------------------------------------------------------

_DIRECT_ADD_PUBLIC_ID = "direct-add-team"
_DIRECT_ADD_GC_UUID = "ddddaaaa-1111-2222-3333-444455556666"


def _make_db_with_direct_add_team(
    *,
    has_opponent_link: bool = False,
    is_hidden: bool = False,
) -> sqlite3.Connection:
    """Return a DB with a tracked team that has no opponent_links row (direct-add).

    Optionally adds an opponent_links row for the team (to test dedup/hidden).
    """
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE teams (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            membership_type TEXT NOT NULL DEFAULT 'tracked',
            public_id       TEXT UNIQUE,
            gc_uuid         TEXT
        );
        CREATE TABLE opponent_links (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            public_id  TEXT,
            is_hidden  INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.execute(
        "INSERT INTO teams (name, membership_type, public_id, gc_uuid) "
        "VALUES (?, 'tracked', ?, ?)",
        (_DIRECT_ADD_PUBLIC_ID, _DIRECT_ADD_PUBLIC_ID, _DIRECT_ADD_GC_UUID),
    )
    if has_opponent_link:
        conn.execute(
            "INSERT INTO opponent_links (public_id, is_hidden) VALUES (?, ?)",
            (_DIRECT_ADD_PUBLIC_ID, 1 if is_hidden else 0),
        )
    conn.commit()
    return conn


def test_crawl_all_includes_direct_add_tracked_team(tmp_path: Path) -> None:
    """AC-1: Tracked team with public_id but no opponent_links row is crawled."""
    _write_games_json(
        tmp_path, _SEASON, _DIRECT_ADD_PUBLIC_ID, [_make_game(_EVENT_ID_1)]
    )
    db = _make_db_with_direct_add_team(has_opponent_link=False)
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.files_written == 1
    assert result.errors == 0
    client.get.assert_called_once()


def test_crawl_all_excludes_hidden_opponent_with_direct_add_team(
    tmp_path: Path,
) -> None:
    """AC-2: Tracked team with is_hidden=1 in opponent_links is excluded."""
    _write_games_json(
        tmp_path, _SEASON, _DIRECT_ADD_PUBLIC_ID, [_make_game(_EVENT_ID_1)]
    )
    db = _make_db_with_direct_add_team(has_opponent_link=True, is_hidden=True)
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_all()

    client.get.assert_not_called()
    assert result.files_written == 0


def test_crawl_all_no_duplicate_for_team_in_both_sources(tmp_path: Path) -> None:
    """AC-3: Team in both opponent_links and teams table is processed once."""
    _write_games_json(
        tmp_path, _SEASON, _DIRECT_ADD_PUBLIC_ID, [_make_game(_EVENT_ID_1)]
    )
    db = _make_db_with_direct_add_team(
        has_opponent_link=True, is_hidden=False
    )
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_all()

    # Should be called exactly once despite team being in both sources.
    assert result.files_written == 1
    assert client.get.call_count == 1


def test_crawl_all_existing_opponent_links_behavior_unchanged(
    tmp_path: Path,
) -> None:
    """AC-5d: Existing opponent_links-only discovery still works."""
    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    # Standard DB: team in opponent_links with is_hidden=0.
    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db, data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.files_written == 1
    assert result.errors == 0


def test_crawl_all_member_team_not_included(tmp_path: Path) -> None:
    """Member teams are never included in the direct-add branch."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE teams (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            membership_type TEXT NOT NULL DEFAULT 'tracked',
            public_id       TEXT UNIQUE,
            gc_uuid         TEXT
        );
        CREATE TABLE opponent_links (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            public_id  TEXT,
            is_hidden  INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.execute(
        "INSERT INTO teams (name, membership_type, public_id, gc_uuid) "
        "VALUES ('Member Team', 'member', 'member-pub-id', ?)",
        (_GC_UUID,),
    )
    conn.commit()
    _write_games_json(tmp_path, _SEASON, "member-pub-id", [_make_game(_EVENT_ID_1)])
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, conn, data_root=tmp_path)

    result = crawler.crawl_all()

    client.get.assert_not_called()
    assert result.files_written == 0


def test_crawl_all_mixed_opponent_links_and_direct_add(tmp_path: Path) -> None:
    """Both opponent_links teams and direct-add teams are crawled together."""
    # Team 1: in opponent_links only
    # Team 2: direct-add (tracked, no opponent_links row)
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE teams (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            membership_type TEXT NOT NULL DEFAULT 'tracked',
            public_id       TEXT UNIQUE,
            gc_uuid         TEXT
        );
        CREATE TABLE opponent_links (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            public_id  TEXT,
            is_hidden  INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.execute(
        "INSERT INTO teams (name, membership_type, public_id, gc_uuid) "
        "VALUES (?, 'tracked', ?, ?)",
        (_PUBLIC_ID, _PUBLIC_ID, _GC_UUID),
    )
    conn.execute(
        "INSERT INTO teams (name, membership_type, public_id, gc_uuid) "
        "VALUES (?, 'tracked', ?, ?)",
        (_DIRECT_ADD_PUBLIC_ID, _DIRECT_ADD_PUBLIC_ID, _DIRECT_ADD_GC_UUID),
    )
    conn.execute(
        "INSERT INTO opponent_links (public_id, is_hidden) VALUES (?, 0)",
        (_PUBLIC_ID,),
    )
    conn.commit()

    _write_games_json(tmp_path, _SEASON, _PUBLIC_ID, [_make_game(_EVENT_ID_1)])
    _write_games_json(
        tmp_path, _SEASON, _DIRECT_ADD_PUBLIC_ID, [_make_game(_EVENT_ID_2)]
    )
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, conn, data_root=tmp_path)

    result = crawler.crawl_all()

    assert result.files_written == 2
    assert client.get.call_count == 2
    assert result.errors == 0
