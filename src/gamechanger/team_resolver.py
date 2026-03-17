"""Public API team resolver for GameChanger team profiles.

Resolves a GameChanger ``public_id`` slug to a ``TeamProfile`` dataclass by
calling the public (unauthenticated) ``GET /public/teams/{public_id}`` endpoint.

Also provides ``discover_opponents()`` which fetches a team's public game
schedule and extracts unique opponent names from it.

No auth headers (``gc-token``, ``gc-device-id``) are sent.  All public endpoints
do not require authentication.

Example::

    from src.gamechanger.team_resolver import resolve_team, discover_opponents, TeamNotFoundError

    try:
        profile = resolve_team("a1GFM9Ku0BbF")
    except TeamNotFoundError:
        print("Team not found")

    opponents = discover_opponents("a1GFM9Ku0BbF")
    for opp in opponents:
        print(opp.name)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

from src.gamechanger.exceptions import GameChangerAPIError, TeamNotFoundError
from src.http.session import create_session

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.team-manager.gc.com"
_ACCEPT_HEADER = "application/vnd.gc.com.public_team_profile+json; version=0.1.0"
_ACCEPT_GAMES_HEADER = "application/vnd.gc.com.public_team_schedule_event:list+json; version=0.0.0"
_TIMEOUT_SECONDS = 10


@dataclass
class DiscoveredOpponent:
    """A unique opponent discovered from a team's public game schedule.

    Attributes:
        name: Opponent team display name (e.g. ``"Jr Bluejays 15U"``).
    """

    name: str


@dataclass
class TeamProfile:
    """Public profile for a GameChanger team."""

    public_id: str
    name: str
    sport: str
    city: str | None = None
    state: str | None = None
    age_group: str | None = None
    season: str | None = None
    year: int | None = None
    record_wins: int | None = None
    record_losses: int | None = None
    staff: list[str] = field(default_factory=list)


def resolve_team(public_id: str) -> TeamProfile:
    """Fetch a team's public profile from the GameChanger API.

    Calls ``GET /public/teams/{public_id}`` with the web header profile.
    No authentication headers are sent -- this is a public endpoint.

    Args:
        public_id: The team's short alphanumeric public identifier
            (e.g. ``"a1GFM9Ku0BbF"``).

    Returns:
        A ``TeamProfile`` populated from the API response.

    Raises:
        TeamNotFoundError: If the API returns 404.
        GameChangerAPIError: If the API returns a non-200/non-404 status code,
            or if the 200 response body is missing required fields.
    """
    url = f"{_BASE_URL}/public/teams/{public_id}"
    logger.debug("Resolving team profile for public_id=%s", public_id)

    with create_session(min_delay_ms=0, jitter_ms=0, proxy_url=None) as session:
        # Override Accept header and add gc-app-name; do not send auth headers
        try:
            response = session.get(
                url,
                headers={
                    "Accept": _ACCEPT_HEADER,
                    "gc-app-name": "web",
                },
                timeout=_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as exc:
            raise GameChangerAPIError(
                f"Request timed out after {_TIMEOUT_SECONDS}s for public_id={public_id!r}"
            ) from exc

    if response.status_code == 404:
        raise TeamNotFoundError(
            f"Team not found: public_id={public_id!r} returned HTTP 404"
        )

    if response.status_code != 200:
        raise GameChangerAPIError(
            f"Unexpected HTTP {response.status_code} from GET /public/teams/{public_id}"
        )

    data = response.json()

    name = data.get("name")
    sport = data.get("sport")
    if not name or not sport:
        missing = [f for f in ("name", "sport") if not data.get(f)]
        raise GameChangerAPIError(
            f"Unexpected response shape from GET /public/teams/{public_id}: "
            f"missing required fields {missing}"
        )

    location = data.get("location") or {}
    team_season = data.get("team_season") or {}
    record = team_season.get("record") or {}

    return TeamProfile(
        public_id=data.get("id", public_id),
        name=name,
        sport=sport,
        city=location.get("city") or None,
        state=location.get("state") or None,
        age_group=data.get("age_group") or None,
        season=team_season.get("season") or None,
        year=team_season.get("year"),
        record_wins=record.get("win"),
        record_losses=record.get("loss"),
        staff=data.get("staff") or [],
    )


def discover_opponents(public_id: str) -> list[DiscoveredOpponent]:
    """Fetch unique opponent names from a team's public game schedule.

    Calls ``GET /public/teams/{public_id}/games`` (no authentication required)
    and extracts deduplicated opponent names.  Games with a missing or empty
    ``opponent_team.name`` are skipped silently.

    Args:
        public_id: The team's short alphanumeric public identifier
            (e.g. ``"a1GFM9Ku0BbF"``).

    Returns:
        List of ``DiscoveredOpponent`` instances with unique names (deduplicated
        case-insensitively; order matches first occurrence).

    Raises:
        GameChangerAPIError: If the API returns a non-200 status code.
    """
    url = f"{_BASE_URL}/public/teams/{public_id}/games"
    logger.debug("Discovering opponents for public_id=%s", public_id)

    with create_session(min_delay_ms=0, jitter_ms=0, proxy_url=None) as session:
        try:
            response = session.get(
                url,
                headers={
                    "Accept": _ACCEPT_GAMES_HEADER,
                    "gc-app-name": "web",
                },
                timeout=_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as exc:
            raise GameChangerAPIError(
                f"Request timed out after {_TIMEOUT_SECONDS}s for public_id={public_id!r}"
            ) from exc

    if response.status_code != 200:
        raise GameChangerAPIError(
            f"Unexpected HTTP {response.status_code} from GET /public/teams/{public_id}/games"
        )

    games = response.json()
    seen: set[str] = set()
    opponents: list[DiscoveredOpponent] = []

    for game in games:
        opp = game.get("opponent_team") or {}
        name = opp.get("name")
        if not name:
            continue
        key = name.lower()
        if key not in seen:
            seen.add(key)
            opponents.append(DiscoveredOpponent(name=name))

    logger.debug(
        "Discovered %d unique opponents for public_id=%s", len(opponents), public_id
    )
    return opponents
