"""Tests for src/gamechanger/crawlers/scouting_spray.py.

E-220 C2-B/C2-C: All callers pass games_data in-memory; legacy disk-based
crawl_all and games.json discovery have been removed.  All HTTP calls are
mocked -- no real network requests.
"""

from __future__ import annotations

import logging
import sqlite3
from unittest.mock import MagicMock

import pytest

from src.gamechanger.client import CredentialExpiredError, GameChangerAPIError
from src.gamechanger.crawlers.scouting_spray import (
    ScoutingSprayChartCrawler,
    SprayCrawlResult,
    _PLAYER_STATS_ACCEPT,
)
from tests.conftest import load_real_schema


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
    """Return an in-memory SQLite connection with the production schema.

    Seeds an owning team row + opponent_links row via the ensure_team_row
    contract (membership_type, name, public_id, gc_uuid). opponent_links
    requires our_team_id REFERENCES teams(id); we seed a member team first
    and use its id as our_team_id for any non-hidden opponent link.
    """
    conn = sqlite3.connect(":memory:")
    load_real_schema(conn)
    # Seed our-team (member) so opponent_links.our_team_id FK is satisfied.
    our_cursor = conn.execute(
        "INSERT INTO teams (name, membership_type) VALUES ('Our Team', 'member')"
    )
    our_team_id = our_cursor.lastrowid
    # Seed the tracked opponent team.
    conn.execute(
        "INSERT INTO teams (name, membership_type, public_id, gc_uuid) "
        "VALUES (?, 'tracked', ?, ?)",
        (public_id, public_id, gc_uuid),
    )
    if add_opponent_link:
        conn.execute(
            "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, "
            "public_id, is_hidden) VALUES (?, ?, ?, ?, 0)",
            (our_team_id, f"root-{public_id}", public_id, public_id),
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


def _make_game(
    event_id: str = _EVENT_ID_1,
    game_status: str = "completed",
) -> dict:
    """Build a minimal game record matching the public games.json schema."""
    return {"id": event_id, "game_status": game_status}


# ---------------------------------------------------------------------------
# crawl_team: in-memory happy path
# ---------------------------------------------------------------------------


def test_crawl_team_returns_spray_data_in_memory() -> None:
    """A completed game produces in-memory spray data."""
    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db)

    result = crawler.crawl_team(
        _PUBLIC_ID, games_data=[_make_game(_EVENT_ID_1)],
    )

    assert isinstance(result, SprayCrawlResult)
    assert _EVENT_ID_1 in result.spray_data
    assert result.spray_data[_EVENT_ID_1] == _SAMPLE_PLAYER_STATS
    assert result.games_crawled == 1
    assert result.errors == 0


def test_crawl_team_uses_correct_api_url() -> None:
    """API call uses /teams/{gc_uuid}/schedule/events/{event_id}/player-stats."""
    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db)

    crawler.crawl_team(_PUBLIC_ID, games_data=[_make_game(_EVENT_ID_1)])

    client.get.assert_called_once_with(
        f"/teams/{_GC_UUID}/schedule/events/{_EVENT_ID_1}/player-stats",
        accept=_PLAYER_STATS_ACCEPT,
    )


def test_correct_accept_header_used() -> None:
    """Player-stats request uses the player-stats Accept header."""
    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db)

    crawler.crawl_team(_PUBLIC_ID, games_data=[_make_game(_EVENT_ID_1)])

    _, kwargs = client.get.call_args
    assert kwargs.get("accept") == _PLAYER_STATS_ACCEPT


def test_spray_data_keyed_by_event_id() -> None:
    """In-memory result keys spray_data by event_id."""
    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db)

    result = crawler.crawl_team(_PUBLIC_ID, games_data=[_make_game(_EVENT_ID_1)])

    assert _EVENT_ID_1 in result.spray_data


def test_in_memory_crawl_fetches_all_completed_games() -> None:
    """In-memory crawl fetches all completed games (no disk-based caching)."""
    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db)

    result = crawler.crawl_team(
        _PUBLIC_ID,
        games_data=[_make_game(_EVENT_ID_1), _make_game(_EVENT_ID_2)],
    )

    assert result.games_crawled == 2
    assert len(result.spray_data) == 2
    assert client.get.call_count == 2


def test_null_spray_chart_data_is_stored_in_memory() -> None:
    """Response with null spray_chart_data is stored (not skipped)."""
    payload = {**_SAMPLE_PLAYER_STATS, "spray_chart_data": None}
    db = _make_db()
    client = _make_client(return_value=payload)
    crawler = ScoutingSprayChartCrawler(client, db)

    result = crawler.crawl_team(_PUBLIC_ID, games_data=[_make_game(_EVENT_ID_1)])

    assert _EVENT_ID_1 in result.spray_data
    assert result.games_crawled == 1


# ---------------------------------------------------------------------------
# crawl_team: skip paths
# ---------------------------------------------------------------------------


def test_opponent_without_gc_uuid_is_skipped_with_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Opponent with NULL gc_uuid logs INFO and returns empty result."""
    db = _make_db(gc_uuid=None)
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db)

    with caplog.at_level(logging.INFO, logger="src.gamechanger.crawlers.scouting_spray"):
        result = crawler.crawl_team(_PUBLIC_ID, games_data=[_make_game(_EVENT_ID_1)])

    client.get.assert_not_called()
    assert result.games_crawled == 0
    assert result.errors == 0
    assert _PUBLIC_ID in caplog.text
    assert "No gc_uuid" in caplog.text


def test_opponent_not_in_teams_table_is_skipped() -> None:
    """Opponent with no teams row (gc_uuid lookup returns None) is skipped."""
    db = sqlite3.connect(":memory:")
    load_real_schema(db)
    # Intentionally no teams row for _PUBLIC_ID so the crawler's gc_uuid lookup
    # returns None. Empty schema is sufficient for this negative-path test.
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db)

    result = crawler.crawl_team(_PUBLIC_ID, games_data=[_make_game(_EVENT_ID_1)])

    client.get.assert_not_called()
    assert result.errors == 0


def test_non_completed_game_not_fetched() -> None:
    """A game with game_status='scheduled' is not fetched."""
    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db)

    result = crawler.crawl_team(
        _PUBLIC_ID,
        games_data=[_make_game(_EVENT_ID_1, game_status="scheduled")],
    )

    client.get.assert_not_called()
    assert result.games_crawled == 0


def test_empty_games_data_returns_empty_result() -> None:
    """Passing an empty games_data list returns an empty SprayCrawlResult."""
    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db)

    result = crawler.crawl_team(_PUBLIC_ID, games_data=[])

    client.get.assert_not_called()
    assert result.games_crawled == 0
    assert result.errors == 0


# ---------------------------------------------------------------------------
# crawl_team: error handling
# ---------------------------------------------------------------------------


def test_credential_expired_error_propagates() -> None:
    """CredentialExpiredError raised during fetch propagates immediately."""
    db = _make_db()
    client = _make_client(side_effect=CredentialExpiredError("Token expired"))
    crawler = ScoutingSprayChartCrawler(client, db)

    with pytest.raises(CredentialExpiredError):
        crawler.crawl_team(_PUBLIC_ID, games_data=[_make_game(_EVENT_ID_1)])


def test_api_error_is_counted_and_crawl_continues() -> None:
    """A GameChangerAPIError on one game is caught; subsequent games continue."""
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
    crawler = ScoutingSprayChartCrawler(client, db)

    result = crawler.crawl_team(
        _PUBLIC_ID,
        games_data=[_make_game(_EVENT_ID_1), _make_game(_EVENT_ID_2)],
    )

    assert result.errors == 1
    assert result.games_crawled == 1


def test_api_error_log_includes_event_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Error log includes event_id and public_id of the failing game."""
    db = _make_db()
    client = _make_client(side_effect=GameChangerAPIError("HTTP 500"))
    crawler = ScoutingSprayChartCrawler(client, db)

    with caplog.at_level(logging.ERROR, logger="src.gamechanger.crawlers.scouting_spray"):
        crawler.crawl_team(_PUBLIC_ID, games_data=[_make_game(_EVENT_ID_1)])

    assert _EVENT_ID_1 in caplog.text


def test_game_missing_id_field_is_counted_as_error() -> None:
    """A completed game record with no 'id' field is counted as an error."""
    bad_game = {"game_status": "completed"}  # no 'id'
    db = _make_db()
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db)

    result = crawler.crawl_team(_PUBLIC_ID, games_data=[bad_game])

    client.get.assert_not_called()
    assert result.errors == 1


# ---------------------------------------------------------------------------
# crawl_team: explicit gc_uuid bypass
# ---------------------------------------------------------------------------


def test_crawl_team_with_explicit_gc_uuid_bypasses_db_lookup() -> None:
    """When gc_uuid is passed directly, no DB lookup is performed."""
    db = _make_db(gc_uuid=None)  # DB has no gc_uuid
    client = _make_client()
    crawler = ScoutingSprayChartCrawler(client, db)

    result = crawler.crawl_team(
        _PUBLIC_ID,
        games_data=[_make_game(_EVENT_ID_1)],
        gc_uuid=_GC_UUID,
    )

    assert result.games_crawled == 1
    client.get.assert_called_once_with(
        f"/teams/{_GC_UUID}/schedule/events/{_EVENT_ID_1}/player-stats",
        accept=_PLAYER_STATS_ACCEPT,
    )
