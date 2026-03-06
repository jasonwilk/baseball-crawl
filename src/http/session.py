"""HTTP session factory with dual header profiles, cookie jar, and rate limiting.

Provides a single ``create_session()`` entry point that returns a configured
``httpx.Client``.  The caller selects the header profile via the ``profile``
parameter:

- ``"web"`` (default): Chrome 145 browser fingerprint (``BROWSER_HEADERS``).
- ``"mobile"``: iOS Odyssey app fingerprint (``MOBILE_HEADERS``).

Every outgoing request automatically carries the selected header profile,
maintains a persistent cookie jar, and sleeps between requests to enforce
rate-limiting with jitter.

Usage::

    session = create_session()                         # web profile (default)
    session = create_session(profile="mobile")         # mobile profile
    session.headers["gc-token"] = token                # auth injected by caller
    response = session.get("https://api.team-manager.gc.com/me/teams")

See ``docs/http-integration-guide.md`` for the full integration guide.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Literal

import httpx

from src.http.headers import BROWSER_HEADERS, MOBILE_HEADERS

logger = logging.getLogger(__name__)

_PROFILES: dict[str, dict[str, str]] = {
    "web": BROWSER_HEADERS,
    "mobile": MOBILE_HEADERS,
}


def _make_rate_limit_hook(
    min_delay_ms: int,
    jitter_ms: int,
) -> callable:
    """Return an httpx response event hook that sleeps between requests."""

    def response_hook(response: httpx.Response) -> None:
        logger.debug(
            "%s %s -> %d",
            response.request.method,
            response.request.url.path,
            response.status_code,
        )
        delay_s = (min_delay_ms + random.uniform(0, jitter_ms)) / 1000
        time.sleep(delay_s)

    return response_hook


def create_session(
    min_delay_ms: int = 1000,
    jitter_ms: int = 500,
    profile: Literal["web", "mobile"] = "web",
) -> httpx.Client:
    """Return a configured ``httpx.Client`` for all project HTTP requests.

    The client:
    - Sends the selected header profile on every request.
    - Maintains a persistent cookie jar across requests.
    - Enforces a per-request delay of *min_delay_ms + random(0, jitter_ms)* ms
      via an httpx response event hook.

    Auth credentials (``gc-token``, ``gc-device-id``) must be injected by the
    caller after receiving the client -- they are **not** included in the base
    session.

    Args:
        min_delay_ms: Minimum delay in milliseconds between requests.
        jitter_ms: Maximum additional random delay in milliseconds.
        profile: Header profile to use. ``"web"`` selects Chrome 145 browser
            headers; ``"mobile"`` selects iOS Odyssey app headers.

    Returns:
        A pre-configured ``httpx.Client`` that supports context-manager usage.

    Raises:
        ValueError: If *profile* is not ``"web"`` or ``"mobile"``.
    """
    headers = _PROFILES.get(profile)
    if headers is None:
        raise ValueError(
            f"Unknown header profile {profile!r}. "
            f"Valid profiles: {sorted(_PROFILES.keys())}"
        )
    return httpx.Client(
        headers=dict(headers),
        cookies=httpx.Cookies(),
        event_hooks={"response": [_make_rate_limit_hook(min_delay_ms, jitter_ms)]},
    )
