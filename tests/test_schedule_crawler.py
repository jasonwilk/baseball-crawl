"""Tests for src.gamechanger.crawlers.schedule.

Probe-confirmation + regression tests pinning the 2026-06-17 live schedule
probe findings (api-scout, against MBA Top Dogg Gold 14U, followed-not-managed):
200 at fan/follower level, future-dated games carrying pregame_data with
non-null opponent_id + opponent_name, canceled games present and filtered,
home_away can be null. Fixtures mirror the authoritative shape documented in
docs/api/endpoints/get-teams-team_id-schedule.md (Test-Validates-Spec).

The crawler is tested against a MagicMock client (the established pattern for
higher-level GameChanger helpers, e.g. tests/test_gamechanger_search.py) -- no
real HTTP, per .claude/rules/testing.md.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from src.gamechanger.crawlers.schedule import (
    SCHEDULE_ACCEPT,
    ScheduledGame,
    fetch_schedule,
)
from src.gamechanger.exceptions import (
    CredentialExpiredError,
    ForbiddenError,
)

_GC_UUID = "72bb77d8-0000-4000-8000-000000000001"


# ---------------------------------------------------------------------------
# Fixture builders -- mirror the authoritative schedule shape
# ---------------------------------------------------------------------------


def _timed_game(
    *,
    event_id: str,
    opponent_id: str,
    opponent_name: str,
    start_datetime: str,
    timezone: str = "America/Chicago",
    status: str = "scheduled",
    home_away: str | None = None,
) -> dict[str, Any]:
    """Build a timed game schedule item (event + pregame_data)."""
    return {
        "event": {
            "id": event_id,
            "event_type": "game",
            "status": status,
            "full_day": False,
            "team_id": _GC_UUID,
            "start": {"datetime": start_datetime},
            "end": {"datetime": start_datetime},
            "timezone": timezone,
            "title": f"Game vs. {opponent_name}",
        },
        "pregame_data": {
            "id": event_id,
            "game_id": event_id,
            "opponent_name": opponent_name,
            "opponent_id": opponent_id,
            "home_away": home_away,
            "lineup_id": None,
        },
    }


def _full_day_other(*, event_id: str, status: str = "scheduled") -> dict[str, Any]:
    """Build a full-day non-game event (no pregame_data)."""
    return {
        "event": {
            "id": event_id,
            "event_type": "other",
            "status": status,
            "full_day": True,
            "team_id": _GC_UUID,
            "start": {"date": "2026-06-26"},
            "end": {"date": "2026-06-28"},
            "timezone": None,
            "title": "Flatrock Tournament",
        }
    }


def _practice(*, event_id: str) -> dict[str, Any]:
    """Build a practice event (no pregame_data)."""
    return {
        "event": {
            "id": event_id,
            "event_type": "practice",
            "status": "scheduled",
            "full_day": False,
            "team_id": _GC_UUID,
            "start": {"datetime": "2026-06-21T16:00:00.000Z"},
            "end": {"datetime": "2026-06-21T18:00:00.000Z"},
            "timezone": "America/Chicago",
            "title": "Practice",
        }
    }


def _make_client(get_return: Any) -> MagicMock:
    client = MagicMock()
    client.get.return_value = get_return
    return client


# ---------------------------------------------------------------------------
# AC-1: structured records with opponent_id, opponent_name, date, raw UTC dt + tz
# ---------------------------------------------------------------------------


def test_fetch_schedule_returns_structured_records_with_required_fields() -> None:
    raw = [
        _timed_game(
            event_id="event-1",
            opponent_id="opp-root-1",
            opponent_name="Kearney Mavericks 14U",
            start_datetime="2026-06-26T16:00:00.000Z",
            timezone="America/Chicago",
            home_away="home",
        )
    ]
    client = _make_client(raw)

    games = fetch_schedule(client, _GC_UUID)

    assert len(games) == 1
    game = games[0]
    assert isinstance(game, ScheduledGame)
    assert game.opponent_id == "opp-root-1"
    assert game.opponent_name == "Kearney Mavericks 14U"
    assert game.game_date == "2026-06-26"
    assert game.start_datetime == "2026-06-26T16:00:00.000Z"
    assert game.timezone == "America/Chicago"
    assert game.home_away == "home"
    assert game.event_id == "event-1"
    assert game.full_day is False


def test_fetch_schedule_uses_correct_version_pin() -> None:
    client = _make_client([])

    fetch_schedule(client, _GC_UUID)

    client.get.assert_called_once()
    call = client.get.call_args
    assert call.args[0] == f"/teams/{_GC_UUID}/schedule"
    assert call.kwargs["accept"] == SCHEDULE_ACCEPT
    assert SCHEDULE_ACCEPT == (
        "application/vnd.gc.com.event:list+json; version=0.2.0"
    )


# ---------------------------------------------------------------------------
# AC-2: inclusive date boundary -- no pre-filter to strictly future dates
# ---------------------------------------------------------------------------


def test_fetch_schedule_returns_past_present_and_future_games_unfiltered() -> None:
    raw = [
        _timed_game(
            event_id="past",
            opponent_id="opp-past",
            opponent_name="Past Opp",
            start_datetime="2025-04-01T16:00:00.000Z",
        ),
        _timed_game(
            event_id="today",
            opponent_id="opp-today",
            opponent_name="Today Opp",
            start_datetime="2026-06-20T23:00:00.000Z",
        ),
        _timed_game(
            event_id="future",
            opponent_id="opp-future",
            opponent_name="Future Opp",
            start_datetime="2026-07-15T16:00:00.000Z",
        ),
    ]
    client = _make_client(raw)

    games = fetch_schedule(client, _GC_UUID)

    # The crawler does no date pre-filter -- all three non-canceled games stay.
    returned_ids = {g.event_id for g in games}
    assert returned_ids == {"past", "today", "future"}


def test_fetch_schedule_retains_same_day_game() -> None:
    raw = [
        _timed_game(
            event_id="same-day",
            opponent_id="opp-1",
            opponent_name="Same Day Opp",
            start_datetime="2026-06-20T23:00:00.000Z",
        )
    ]
    client = _make_client(raw)

    games = fetch_schedule(client, _GC_UUID)

    assert len(games) == 1
    assert games[0].game_date == "2026-06-20"


# ---------------------------------------------------------------------------
# AC-3: canceled games filtered; null home_away tolerated; non-games dropped
# ---------------------------------------------------------------------------


def test_fetch_schedule_filters_canceled_games() -> None:
    raw = [
        _timed_game(
            event_id="live",
            opponent_id="opp-live",
            opponent_name="Live Opp",
            start_datetime="2026-06-26T16:00:00.000Z",
            status="scheduled",
        ),
        _timed_game(
            event_id="dead",
            opponent_id="opp-dead",
            opponent_name="Canceled Opp",
            start_datetime="2026-06-27T16:00:00.000Z",
            status="canceled",
        ),
    ]
    client = _make_client(raw)

    games = fetch_schedule(client, _GC_UUID)

    assert len(games) == 1
    assert games[0].event_id == "live"


def test_fetch_schedule_tolerates_null_home_away() -> None:
    raw = [
        _timed_game(
            event_id="event-1",
            opponent_id="opp-1",
            opponent_name="Opp",
            start_datetime="2026-06-26T16:00:00.000Z",
            home_away=None,
        )
    ]
    client = _make_client(raw)

    games = fetch_schedule(client, _GC_UUID)

    assert len(games) == 1
    assert games[0].home_away is None


def test_fetch_schedule_drops_practice_and_other_events() -> None:
    raw = [
        _practice(event_id="practice-1"),
        _full_day_other(event_id="other-1"),
        _timed_game(
            event_id="game-1",
            opponent_id="opp-1",
            opponent_name="Opp",
            start_datetime="2026-06-26T16:00:00.000Z",
        ),
    ]
    client = _make_client(raw)

    games = fetch_schedule(client, _GC_UUID)

    assert [g.event_id for g in games] == ["game-1"]


def test_fetch_schedule_skips_game_with_missing_pregame_data() -> None:
    raw = [
        {
            "event": {
                "id": "no-pregame",
                "event_type": "game",
                "status": "scheduled",
                "full_day": False,
                "start": {"datetime": "2026-06-26T16:00:00.000Z"},
                "timezone": "America/Chicago",
                "title": "Game vs. Mystery",
            }
            # pregame_data intentionally absent
        }
    ]
    client = _make_client(raw)

    games = fetch_schedule(client, _GC_UUID)

    assert games == []


# ---------------------------------------------------------------------------
# Full-day game: start.date used for game_date; start_datetime + timezone None
# ---------------------------------------------------------------------------


def test_fetch_schedule_full_day_game_uses_date_field() -> None:
    raw = [
        {
            "event": {
                "id": "full-day-game",
                "event_type": "game",
                "status": "scheduled",
                "full_day": True,
                "start": {"date": "2026-06-26"},
                "end": {"date": "2026-06-26"},
                "timezone": None,
                "title": "Game vs. All-Day Opp",
            },
            "pregame_data": {
                "id": "full-day-game",
                "game_id": "full-day-game",
                "opponent_name": "All-Day Opp",
                "opponent_id": "opp-allday",
                "home_away": None,
                "lineup_id": None,
            },
        }
    ]
    client = _make_client(raw)

    games = fetch_schedule(client, _GC_UUID)

    assert len(games) == 1
    game = games[0]
    assert game.full_day is True
    assert game.game_date == "2026-06-26"
    assert game.start_datetime is None
    assert game.timezone is None


# ---------------------------------------------------------------------------
# AC-6: 403 surfaces as ForbiddenError (distinct from auth-expiry 401)
# ---------------------------------------------------------------------------


def test_fetch_schedule_propagates_forbidden_error() -> None:
    client = MagicMock()
    client.get.side_effect = ForbiddenError("Access denied for /teams/x/schedule")

    with pytest.raises(ForbiddenError):
        fetch_schedule(client, _GC_UUID)


def test_fetch_schedule_forbidden_is_not_collapsed_into_plain_auth_expiry() -> None:
    """A 403 must remain distinguishable from a true 401-after-refresh.

    ForbiddenError is a subclass of CredentialExpiredError, but the crawler
    must surface the MORE specific type so the caller can branch on it (TN-4).
    """
    client = MagicMock()
    client.get.side_effect = ForbiddenError("Access denied")

    with pytest.raises(CredentialExpiredError) as exc_info:
        fetch_schedule(client, _GC_UUID)

    assert isinstance(exc_info.value, ForbiddenError)


def test_fetch_schedule_propagates_credential_expired_error() -> None:
    client = MagicMock()
    client.get.side_effect = CredentialExpiredError("token expired")

    with pytest.raises(CredentialExpiredError):
        fetch_schedule(client, _GC_UUID)


# ---------------------------------------------------------------------------
# Defensive: non-list response and empty schedule
# ---------------------------------------------------------------------------


def test_fetch_schedule_empty_array_returns_empty_list() -> None:
    client = _make_client([])

    assert fetch_schedule(client, _GC_UUID) == []


def test_fetch_schedule_non_list_response_returns_empty_list() -> None:
    client = _make_client({"unexpected": "object"})

    assert fetch_schedule(client, _GC_UUID) == []
