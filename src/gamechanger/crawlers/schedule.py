"""Authenticated schedule crawler for the morning-run scheduler (E-240).

Fetches a team's GameChanger schedule via the authenticated
``GET /teams/{gc_uuid}/schedule`` endpoint and returns its game events as
structured :class:`ScheduledGame` records. This is the upcoming-opponent
discovery source for the morning-run feature (E-240-07) and the resolution
ladder (E-240-04).

The previous authenticated schedule reader did not survive the E-239 removal
(only public, free-text-name readers remain), so this module is genuinely new.

Scope of this crawler (a thin fetch+parse seam):

* It does NOT resolve opponents to ``public_id`` (that is E-240-04's ladder).
* It does NOT filter to a single target date (E-240-07 derives each game's
  LOCAL date from ``start_datetime`` + ``timezone`` and applies the same-day
  filter). This crawler's date boundary is INCLUSIVE: every non-canceled game
  is returned, never pre-filtered to strictly future dates (AC-2).
* It DOES drop canceled games (AC-3) and tolerates a null ``home_away``.

The ``opponent_id`` carried by each record is in the ``root_team_id`` namespace
(verified 54/54 against the opponents registry) -- NEVER feed it to
``GET /teams/{id}``; the registry join that yields ``progenitor_team_id`` is
E-240-04's job.

Usage::

    from src.gamechanger.client import GameChangerClient
    from src.gamechanger.crawlers.schedule import fetch_schedule

    client = GameChangerClient()
    games = fetch_schedule(client, "72bb77d8-REDACTED")
    for game in games:
        print(game.opponent_name, game.opponent_id, game.game_date)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.gamechanger.client import GameChangerClient

logger = logging.getLogger(__name__)

# Accept version pin per epic Technical Notes TN-4. A wrong pin yields a FALSE
# 403 that must NOT be collapsed into "auth expired".
SCHEDULE_ACCEPT = "application/vnd.gc.com.event:list+json; version=0.2.0"

# Event statuses that the crawler drops (AC-3).
_CANCELED_STATUS = "canceled"


@dataclass(frozen=True)
class ScheduledGame:
    """One non-canceled game event from a team's authenticated schedule.

    This is the PINNED handoff shape consumed by E-240-04 (resolution ladder)
    and E-240-07 (orchestration). The field names are part of the contract --
    do not rename them in downstream stories without updating this module.

    Attributes:
        opponent_id: The opponent's UUID from ``pregame_data.opponent_id``.
            **This is the ``root_team_id`` namespace** (local registry key),
            NOT ``progenitor_team_id``. Join it to the opponents registry to
            reach the canonical UUID; never feed it to ``GET /teams/{id}``.
        opponent_name: The opponent's display name from
            ``pregame_data.opponent_name``.
        game_date: The naive calendar date string the event's ``start`` carries
            (``"YYYY-MM-DD"``). For timed games this is the DATE PORTION of the
            raw UTC ``start.datetime`` (so it can be UTC-shifted vs. local); for
            full-day games it is ``start.date`` directly. E-240-07 derives the
            authoritative LOCAL date from ``start_datetime`` + ``timezone`` --
            this field is a convenience/audit value, not the filter key.
        start_datetime: The raw ``start.datetime`` ISO-8601 UTC string (e.g.
            ``"2025-04-26T16:00:00.000Z"``), or ``None`` for full-day events
            (which carry ``start.date`` instead). E-240-07 uses this plus
            ``timezone`` to derive the LOCAL date.
        timezone: The event's IANA timezone string (e.g. ``"America/Chicago"``),
            or ``None`` for full-day events.
        home_away: ``"home"``, ``"away"``, or ``None``. A null value is
            acceptable (AC-3) and is NOT treated as an error.
        event_id: The event UUID (``event.id``; equals
            ``pregame_data.game_id``).
        full_day: ``True`` when the event uses ``{"date": ...}`` instead of
            ``{"datetime": ...}`` for ``start``/``end``.
    """

    opponent_id: str | None
    opponent_name: str | None
    game_date: str | None
    start_datetime: str | None
    timezone: str | None
    home_away: str | None
    event_id: str | None
    full_day: bool


def _extract_game_date(start: dict[str, Any]) -> str | None:
    """Return the calendar-date portion of a schedule event's ``start`` block.

    For timed events ``start`` is ``{"datetime": "ISO8601"}``; for full-day
    events it is ``{"date": "YYYY-MM-DD"}``. Returns the ``date`` directly when
    present, otherwise the first 10 chars of ``datetime`` (the ``YYYY-MM-DD``
    prefix). Returns ``None`` when neither key is present (defensive).
    """
    date_val = start.get("date")
    if date_val:
        return str(date_val)
    datetime_val = start.get("datetime")
    if datetime_val:
        return str(datetime_val)[:10]
    return None


def _parse_game(item: dict[str, Any]) -> ScheduledGame | None:
    """Parse one schedule array item into a :class:`ScheduledGame`.

    Returns ``None`` (skipped, not an error) for non-game events, items missing
    the ``pregame_data`` block, and canceled games. Parses defensively: a
    missing optional field becomes ``None`` rather than raising.
    """
    event = item.get("event") or {}
    if event.get("event_type") != "game":
        return None

    if event.get("status") == _CANCELED_STATUS:
        logger.debug("Skipping canceled game event %s", event.get("id"))
        return None

    pregame = item.get("pregame_data")
    if not isinstance(pregame, dict):
        # A game event with no pregame_data carries no opponent -- nothing the
        # scheduler can act on. Warn rather than crash (defensive parsing).
        logger.warning(
            "Game event %s has no pregame_data block; skipping",
            event.get("id"),
        )
        return None

    start = event.get("start") or {}

    return ScheduledGame(
        opponent_id=pregame.get("opponent_id"),
        opponent_name=pregame.get("opponent_name"),
        game_date=_extract_game_date(start),
        start_datetime=start.get("datetime"),
        timezone=event.get("timezone"),
        home_away=pregame.get("home_away"),
        event_id=event.get("id"),
        full_day=bool(event.get("full_day")),
    )


def fetch_schedule(client: GameChangerClient, gc_uuid: str) -> list[ScheduledGame]:
    """Fetch a team's schedule and return its non-canceled game events.

    Calls ``GET /teams/{gc_uuid}/schedule`` with the TN-4 version pin and parses
    the bare JSON array into :class:`ScheduledGame` records. Practice/other
    events and canceled games are dropped; the date boundary is INCLUSIVE (no
    pre-filter to strictly future dates -- AC-2). A null ``home_away`` is
    tolerated (AC-3).

    A 403 from this endpoint propagates as ``ForbiddenError`` (a DISTINCT type
    from a true 401-after-refresh ``CredentialExpiredError``) so the caller can
    distinguish a version-pin / legitimate-denial case from auth expiry (AC-6).
    This crawler does NOT catch or re-classify it.

    Args:
        client: Authenticated :class:`GameChangerClient` instance.
        gc_uuid: The team's GameChanger UUID (NOT a ``public_id`` slug and NOT
            an ``opponent_id``/``root_team_id``).

    Returns:
        List of :class:`ScheduledGame`, in schedule order, for every
        non-canceled game event.

    Raises:
        ForbiddenError: On a 403 (version-pin mismatch or legitimate denial) --
            propagated unchanged so the caller distinguishes it from 401.
        CredentialExpiredError: On a 401 that survives a single token refresh.
        RateLimitError: On a 429.
        GameChangerAPIError: On 5xx after retries.
    """
    logger.debug("Fetching authenticated schedule for gc_uuid=%s", gc_uuid)
    raw = client.get(
        f"/teams/{gc_uuid}/schedule",
        accept=SCHEDULE_ACCEPT,
    )

    if not isinstance(raw, list):
        logger.warning(
            "Schedule response for gc_uuid=%s was not a JSON array (%s); "
            "treating as empty",
            gc_uuid,
            type(raw).__name__,
        )
        return []

    games: list[ScheduledGame] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        parsed = _parse_game(item)
        if parsed is not None:
            games.append(parsed)

    logger.info(
        "Schedule fetch complete for gc_uuid=%s: %d non-canceled game(s)",
        gc_uuid,
        len(games),
    )
    return games
