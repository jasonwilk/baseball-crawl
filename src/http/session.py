"""HTTP session factory with browser-realistic headers, cookie jar, and rate limiting.

Provides a single ``create_session()`` entry point that returns a configured
``httpx.Client``.  Every outgoing request automatically carries the canonical
browser header profile from ``src.http.headers``, maintains a persistent cookie
jar, and sleeps between requests to enforce rate-limiting with jitter.

Usage::

    session = create_session()
    session.headers["Authorization"] = f"Bearer {token}"   # auth injected by caller
    response = session.get("https://api.example.com/data")

See ``docs/http-integration-guide.md`` for the full integration guide.
"""

from __future__ import annotations

import logging
import random
import time

import httpx

from src.http.headers import BROWSER_HEADERS

logger = logging.getLogger(__name__)


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
) -> httpx.Client:
    """Return a configured ``httpx.Client`` for all project HTTP requests.

    The client:
    - Sends ``BROWSER_HEADERS`` on every request (browser fingerprint).
    - Maintains a persistent cookie jar across requests.
    - Enforces a per-request delay of *min_delay_ms + random(0, jitter_ms)* ms
      via an httpx response event hook.

    Auth credentials (``Authorization`` header, cookie overrides) must be
    injected by the caller after receiving the client — they are **not**
    included in the base session.

    Args:
        min_delay_ms: Minimum delay in milliseconds between requests.
        jitter_ms: Maximum additional random delay in milliseconds.

    Returns:
        A pre-configured ``httpx.Client`` that supports context-manager usage.
    """
    return httpx.Client(
        headers=dict(BROWSER_HEADERS),
        cookies=httpx.Cookies(),
        event_hooks={"response": [_make_rate_limit_hook(min_delay_ms, jitter_ms)]},
    )
