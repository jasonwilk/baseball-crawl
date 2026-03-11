"""Bridge API helpers for resolving team identifiers via the GameChanger API.

Provides authenticated calls to the two bridge endpoints that convert between
team UUIDs and public_id slugs.  Both endpoints are restricted to teams the
authenticated user belongs to; opponent teams return HTTP 403.

Example::

    from src.gamechanger.bridge import resolve_public_id_to_uuid, BridgeForbiddenError

    try:
        team_uuid = resolve_public_id_to_uuid("a1GFM9Ku0BbF")
    except BridgeForbiddenError:
        print("Team not on authenticated account")
"""

from __future__ import annotations

import logging

from src.gamechanger.client import GameChangerClient
from src.gamechanger.exceptions import ForbiddenError

logger = logging.getLogger(__name__)

_REVERSE_BRIDGE_ACCEPT = "application/vnd.gc.com.team_id+json; version=0.0.0"
_FORWARD_BRIDGE_ACCEPT = "application/vnd.gc.com.team_public_profile_id+json; version=0.0.0"


class BridgeForbiddenError(Exception):
    """Raised when a bridge endpoint returns 403 -- team not on user's account."""


def resolve_public_id_to_uuid(public_id: str) -> str:
    """Resolve a public_id slug to its internal UUID via the reverse bridge.

    Calls ``GET /teams/public/{public_id}/id``.  Only succeeds for teams the
    authenticated user belongs to; opponent teams return 403.

    Args:
        public_id: The team's public_id slug (e.g. ``"a1GFM9Ku0BbF"``).

    Returns:
        The team's UUID string.

    Raises:
        BridgeForbiddenError: If the bridge returns 403 (not on user's account).
        CredentialExpiredError: If the access token is expired or invalid.
        ConfigurationError: If GC credentials are not configured in .env.
    """
    client = GameChangerClient(min_delay_ms=0, jitter_ms=0)
    try:
        data = client.get(
            f"/teams/public/{public_id}/id",
            accept=_REVERSE_BRIDGE_ACCEPT,
        )
    except ForbiddenError as exc:
        raise BridgeForbiddenError(
            f"Team public_id={public_id!r} not found on authenticated account. "
            "Only teams the user belongs to can be resolved to a UUID via the reverse bridge."
        ) from exc
    team_uuid: str = data["id"]
    logger.debug("Reverse bridge: public_id=%s -> uuid=%s", public_id, team_uuid)
    return team_uuid


def resolve_uuid_to_public_id(team_uuid: str) -> str:
    """Resolve a team UUID to its public_id slug via the forward bridge.

    Calls ``GET /teams/{team_uuid}/public-team-profile-id``.  Only succeeds
    for teams the authenticated user belongs to; opponent teams return 403.

    Args:
        team_uuid: The team's internal UUID string.

    Returns:
        The team's public_id slug.

    Raises:
        BridgeForbiddenError: If the bridge returns 403 (not on user's account).
        CredentialExpiredError: If the access token is expired or invalid.
        ConfigurationError: If GC credentials are not configured in .env.
    """
    client = GameChangerClient(min_delay_ms=0, jitter_ms=0)
    try:
        data = client.get(
            f"/teams/{team_uuid}/public-team-profile-id",
            accept=_FORWARD_BRIDGE_ACCEPT,
        )
    except ForbiddenError as exc:
        raise BridgeForbiddenError(
            f"Team UUID {team_uuid!r} not found on authenticated account. "
            "Only teams the user belongs to can use the forward bridge."
        ) from exc
    slug: str = data["id"]
    logger.debug("Forward bridge: uuid=%s -> public_id=%s", team_uuid, slug)
    return slug
