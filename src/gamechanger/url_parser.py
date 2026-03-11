"""URL parser for extracting team identifiers from GameChanger team URLs.

Accepts full GameChanger team URLs, bare public_id slugs, or bare UUIDs.
Returns a structured result indicating the identifier type.

Example::

    from src.gamechanger.url_parser import parse_team_url

    result = parse_team_url("https://web.gc.com/teams/a1GFM9Ku0BbF/2025-rebels-14u")
    # result.value == "a1GFM9Ku0BbF", result.id_type == "public_id"

    result = parse_team_url("a1GFM9Ku0BbF")
    # result.value == "a1GFM9Ku0BbF", result.id_type == "public_id"

    result = parse_team_url("72bb77d8-54ca-42d2-8547-9da4880d0cb4")
    # result.value == "72bb77d8-54ca-42d2-8547-9da4880d0cb4", result.id_type == "uuid"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

_PUBLIC_ID_RE = re.compile(r"^[A-Za-z0-9]{6,20}$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TeamIdResult:
    """Result of parsing a GameChanger team identifier.

    Attributes:
        value: The extracted identifier string (public_id slug or UUID).
        id_type: Either ``"public_id"`` or ``"uuid"``.
    """

    value: str
    id_type: str

    @property
    def is_uuid(self) -> bool:
        """Return True if this result holds a UUID."""
        return self.id_type == "uuid"

    @property
    def is_public_id(self) -> bool:
        """Return True if this result holds a public_id slug."""
        return self.id_type == "public_id"


def parse_team_url(input: str) -> TeamIdResult:
    """Extract a GameChanger team identifier from a URL, bare slug, or bare UUID.

    Accepts:
    - Full GC URL: ``https://web.gc.com/teams/{public_id}/some-slug``
    - Full GC URL with UUID: ``https://web.gc.com/teams/{uuid}/some-slug``
    - Any URL with a ``/teams/{id}`` path (mobile share links, etc.)
    - Bare ``public_id`` slug (e.g. ``"a1GFM9Ku0BbF"``)
    - Bare UUID (e.g. ``"72bb77d8-54ca-42d2-8547-9da4880d0cb4"``)

    Args:
        input: A GameChanger team URL, bare public_id string, or bare UUID.

    Returns:
        A :class:`TeamIdResult` with the extracted identifier and its type.

    Raises:
        ValueError: If the input is empty, contains no ``/teams/`` segment,
            or the extracted value fails both UUID and public_id validation.
    """
    value = input.strip()
    if not value:
        raise ValueError("Input must not be empty")

    parsed = urlparse(value)

    # If no scheme and no netloc, treat as a bare identifier (no path separators)
    if not parsed.scheme and not parsed.netloc:
        candidate = value.split("?")[0].split("#")[0].strip("/")
        if "/" not in candidate:
            return _classify(candidate)

    # It has a scheme/netloc (or looks like a URL) -- extract from path
    path = parsed.path

    # Look for /teams/ segment
    teams_pattern = re.compile(r"/teams/([^/?#]+)")
    match = teams_pattern.search(path)
    if not match:
        raise ValueError(
            f"Could not find a /teams/ segment in the URL path {value!r}. "
            "Expected a URL like https://web.gc.com/teams/<public_id>/..."
        )

    candidate = match.group(1).strip("/")
    return _classify(candidate)


def _classify(candidate: str) -> TeamIdResult:
    """Return a TeamIdResult for the given candidate string.

    Args:
        candidate: A potential public_id or UUID string.

    Raises:
        ValueError: If the candidate matches neither format.
    """
    if _UUID_RE.match(candidate):
        return TeamIdResult(value=candidate, id_type="uuid")
    if _PUBLIC_ID_RE.match(candidate):
        return TeamIdResult(value=candidate, id_type="public_id")
    raise ValueError(
        f"Invalid team identifier {candidate!r}: must be a UUID "
        "(xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx) or an alphanumeric public_id "
        "(letters and digits only, 6-20 characters)."
    )
