"""Public API team resolver for GameChanger team profiles.

Resolves a GameChanger ``public_id`` slug to a ``TeamProfile`` dataclass by
calling the public (unauthenticated) ``GET /public/teams/{public_id}`` endpoint.

No auth headers (``gc-token``, ``gc-device-id``) are sent.  All public endpoints
do not require authentication.

Example::

    from src.gamechanger.team_resolver import resolve_team, TeamNotFoundError

    try:
        profile = resolve_team("a1GFM9Ku0BbF")
    except TeamNotFoundError:
        print("Team not found")
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
_TIMEOUT_SECONDS = 10


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
        GameChangerAPIError: If the API returns a non-200/non-404 status code, if
            the 200 response body is missing required fields, or if the HTTP
            request fails at the transport level (timeout, connection error, DNS,
            TLS -- any ``httpx.RequestError``).
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
        except httpx.RequestError as exc:
            # E-252-09: catch the WHOLE transport-error family (httpx.RequestError
            # supertype of TimeoutException AND ConnectError / NetworkError / etc.),
            # not just timeouts, so a connection-level blip (DNS, refused, TLS) is
            # surfaced as the documented GameChangerAPIError instead of crashing the
            # caller (e.g. the morning run). `{exc}` keeps the message accurate per
            # failure type. NOTE: httpx.HTTPStatusError is NOT a RequestError and is
            # never raised here anyway (status codes are inspected below, not via
            # raise_for_status), so no status handling is swallowed.
            raise GameChangerAPIError(
                f"HTTP request failed for public_id={public_id!r} "
                f"({type(exc).__name__}): {exc}"
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
