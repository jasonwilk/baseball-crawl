"""URL parser for extracting public_id from GameChanger team URLs.

Accepts full GameChanger team URLs or bare public_id slugs.  Returns the
public_id string in either case.

Example::

    from src.gamechanger.url_parser import parse_team_url

    public_id = parse_team_url("https://web.gc.com/teams/a1GFM9Ku0BbF/2025-rebels-14u")
    # Returns: "a1GFM9Ku0BbF"

    public_id = parse_team_url("a1GFM9Ku0BbF")
    # Returns: "a1GFM9Ku0BbF"
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

_PUBLIC_ID_RE = re.compile(r"^[A-Za-z0-9]{6,20}$")


def parse_team_url(input: str) -> str:
    """Extract a GameChanger team public_id from a URL or bare slug.

    Accepts:
    - Full GC URL: ``https://web.gc.com/teams/{public_id}/some-slug``
    - Any URL with a ``/teams/{public_id}`` path (mobile share links, etc.)
    - Bare ``public_id`` slug (e.g. ``"a1GFM9Ku0BbF"``)

    Args:
        input: A GameChanger team URL or bare public_id string.

    Returns:
        The extracted ``public_id`` slug.

    Raises:
        ValueError: If the input is empty, contains no ``/teams/`` segment,
            or the extracted public_id fails alphanumeric validation.
    """
    value = input.strip()
    if not value:
        raise ValueError("Input must not be empty")

    parsed = urlparse(value)

    # If no scheme and no netloc, treat as a bare public_id (or relative path)
    if not parsed.scheme and not parsed.netloc:
        # Could be a bare public_id slug -- validate directly
        candidate = value.split("?")[0].split("#")[0].strip("/")
        # If it looks like a bare slug with no path separators, validate it
        if "/" not in candidate:
            _validate_public_id(candidate)
            return candidate

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
    _validate_public_id(candidate)
    return candidate


def _validate_public_id(value: str) -> None:
    """Raise ValueError if value is not a valid public_id.

    A valid public_id is alphanumeric (letters and digits only), 6-20 chars.

    Args:
        value: The candidate public_id string.

    Raises:
        ValueError: If the value does not match the expected format.
    """
    if not _PUBLIC_ID_RE.match(value):
        raise ValueError(
            f"Invalid public_id {value!r}: must be alphanumeric (letters and digits only), "
            "6-20 characters. Got a URL with an unexpected path segment or an invalid slug."
        )
