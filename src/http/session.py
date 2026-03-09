"""HTTP session factory with dual header profiles, cookie jar, and rate limiting.

Provides a single ``create_session()`` entry point that returns a configured
``httpx.Client``.  The caller selects the header profile via the ``profile``
parameter:

- ``"web"`` (default): Chrome 145 browser fingerprint (``BROWSER_HEADERS``).
- ``"mobile"``: iOS Odyssey app fingerprint (``MOBILE_HEADERS``).

Every outgoing request automatically carries the selected header profile,
maintains a persistent cookie jar, and sleeps between requests to enforce
rate-limiting with jitter.

Proxy support is profile-aware and uses one of two resolution paths:

- **Default path** (``create_session()`` with no explicit ``proxy_url``): reads
  ``PROXY_ENABLED`` and ``PROXY_URL_{PROFILE}`` from ``os.environ`` via
  ``get_proxy_config()``.
- **Dict path** (callers with a dotenv dict not merged into ``os.environ``):
  call ``resolve_proxy_from_dict(env_dict, profile)`` first, then pass the
  result as ``proxy_url=...`` to ``create_session()``.  Used by
  ``GameChangerClient``, which loads credentials via ``dotenv_values()``
  (returns a dict) rather than ``load_dotenv()`` (mutates ``os.environ``).

When a proxy URL is resolved, ``create_session()`` automatically sets
``verify=False`` on the httpx client (required by Bright Data's self-signed
CONNECT tunnel certificate) and emits a WARNING-level log.  System proxy
environment variables (``HTTP_PROXY``, ``HTTPS_PROXY``) are intentionally
ignored (``trust_env=False``).

Usage::

    session = create_session()                         # web profile (default)
    session = create_session(profile="mobile")         # mobile profile
    session.headers["gc-token"] = token                # auth injected by caller
    response = session.get("https://api.team-manager.gc.com/me/teams")

See ``docs/http-integration-guide.md`` for the full integration guide.
"""

from __future__ import annotations

import logging
import os
import random
import time
import urllib.parse
from typing import Any, Literal

import httpx

from src.http.headers import BROWSER_HEADERS, MOBILE_HEADERS

logger = logging.getLogger(__name__)

_PROFILES: dict[str, dict[str, str]] = {
    "web": BROWSER_HEADERS,
    "mobile": MOBILE_HEADERS,
}

# Sentinel object used as default for proxy_url to distinguish "not provided"
# from explicitly passed None.
_UNSET: Any = object()


def _inject_session_id(proxy_url: str, session_id: str) -> str:
    """Inject a Bright Data sticky session ID into the proxy URL username.

    Appends ``-session-<id>`` to the username component of the URL.
    The returned URL contains credentials and must never be logged.

    Args:
        proxy_url: Proxy URL in the format ``http://USERNAME:PASS@HOST:PORT``.
        session_id: Alphanumeric session identifier (e.g., from
            ``secrets.token_hex(8)``).

    Returns:
        The proxy URL with the session suffix appended to the username.
    """
    parsed = urllib.parse.urlparse(proxy_url)
    if not parsed.username:
        # No username present (bare proxy URL) -- cannot inject; return unmodified.
        return proxy_url
    new_username = f"{parsed.username}-session-{session_id}"
    password = urllib.parse.quote(parsed.password or "", safe="")
    netloc = f"{new_username}:{password}@{parsed.hostname}"
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urllib.parse.urlunparse(parsed._replace(netloc=netloc))


def resolve_proxy_from_dict(
    env_dict: dict[str, str],
    profile: str,
    session_id: str | None = None,
) -> str | None:
    """Resolve proxy configuration from an explicit env dict for the given profile.

    Reads ``PROXY_ENABLED`` and ``PROXY_URL_{profile.upper()}`` from *env_dict*.
    Returns the proxy URL string when proxy is enabled and the URL is valid;
    returns ``None`` when proxy is disabled, the URL is unset, or the URL has
    an unsupported scheme.

    When *session_id* is provided, injects ``-session-<id>`` into the proxy URL
    username to enable Bright Data sticky sessions.  The injected URL is never
    logged -- only the session ID itself may be logged by callers.

    Proxy URL values are never logged.  Only the env var name appears in
    WARNING messages.

    This function mirrors ``get_proxy_config()`` but reads from a supplied dict
    instead of ``os.environ``.  Use it when proxy config lives in a dotenv dict
    that has not been merged into ``os.environ`` (e.g., ``dotenv_values()``).

    Args:
        env_dict: Dict of environment variable names to values (e.g. from
            ``dotenv_values()``).
        profile: Session profile (``"web"`` or ``"mobile"``).  Determines
            which ``PROXY_URL_*`` key is read.
        session_id: Optional alphanumeric Bright Data sticky session identifier.
            When provided, appended as ``-session-<id>`` to the proxy URL
            username.  When ``None`` (default), the URL is returned unmodified
            (rotating IP behavior).

    Returns:
        The proxy URL string when enabled and valid, or ``None``.
    """
    enabled = env_dict.get("PROXY_ENABLED", "").strip().lower()
    if enabled != "true":
        return None

    url_var = f"PROXY_URL_{profile.upper()}"
    url = env_dict.get(url_var, "").strip()

    if not url:
        logger.warning(
            "PROXY_ENABLED is true but %s is not set",
            url_var,
        )
        return None

    if not (url.startswith("http://") or url.startswith("https://")):
        logger.warning(
            "PROXY_ENABLED is true but %s has an invalid scheme (must be http:// or https://)",
            url_var,
        )
        return None

    if session_id is not None:
        url = _inject_session_id(url, session_id)

    return url


def get_proxy_config(profile: str) -> str | None:
    """Read proxy configuration from environment variables for the given profile.

    Reads ``PROXY_ENABLED`` and ``PROXY_URL_{profile.upper()}`` from the
    environment.  Returns the proxy URL string when proxy is enabled and the
    URL is valid; returns ``None`` when proxy is disabled, the URL is unset,
    or the URL has an unsupported scheme.

    Proxy URL values are never logged.  Only the env var name appears in
    WARNING messages.

    Args:
        profile: Session profile (``"web"`` or ``"mobile"``).  Determines
            which ``PROXY_URL_*`` env var is read.

    Returns:
        The proxy URL string when enabled and valid, or ``None``.
    """
    enabled = os.environ.get("PROXY_ENABLED", "").strip().lower()
    if enabled != "true":
        return None

    url_var = f"PROXY_URL_{profile.upper()}"
    url = os.environ.get(url_var, "").strip()

    if not url:
        logger.warning(
            "PROXY_ENABLED is true but %s is not set",
            url_var,
        )
        return None

    if not (url.startswith("http://") or url.startswith("https://")):
        logger.warning(
            "PROXY_ENABLED is true but %s has an invalid scheme (must be http:// or https://)",
            url_var,
        )
        return None

    return url


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
    proxy_url: str | None = _UNSET,  # type: ignore[assignment]
) -> httpx.Client:
    """Return a configured ``httpx.Client`` for all project HTTP requests.

    The client:
    - Sends the selected header profile on every request.
    - Maintains a persistent cookie jar across requests.
    - Enforces a per-request delay of *min_delay_ms + random(0, jitter_ms)* ms
      via an httpx response event hook.
    - Routes traffic through a proxy when configured (see below).
    - Ignores system proxy environment variables (``HTTP_PROXY``,
      ``HTTPS_PROXY``) -- proxy routing is exclusively controlled by
      ``PROXY_ENABLED`` and ``PROXY_URL_*`` env vars.

    Auth credentials (``gc-token``, ``gc-device-id``) must be injected by the
    caller after receiving the client -- they are **not** included in the base
    session.

    **Proxy routing**: When *proxy_url* is not explicitly provided, the session
    calls ``get_proxy_config(profile)`` to auto-read proxy settings from the
    environment.  Pass ``proxy_url=None`` to disable proxy even when env vars
    are set.  Pass an explicit URL string to override env vars.

    Args:
        min_delay_ms: Minimum delay in milliseconds between requests.
        jitter_ms: Maximum additional random delay in milliseconds.
        profile: Header profile to use.  ``"web"`` selects Chrome 145 browser
            headers; ``"mobile"`` selects iOS Odyssey app headers.  Also
            determines which proxy zone is used when proxy is enabled.
        proxy_url: Explicit proxy URL (e.g. ``"http://user:pass@host:port"``).
            When not provided (default), the proxy URL is read from
            ``PROXY_ENABLED`` + ``PROXY_URL_{profile.upper()}`` env vars.
            Pass ``None`` to force no proxy regardless of env vars.

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

    # Resolve proxy URL: explicit value takes precedence; sentinel triggers env-var read.
    if proxy_url is _UNSET:
        resolved_proxy: str | None = get_proxy_config(profile)
    else:
        resolved_proxy = proxy_url  # type: ignore[assignment]

    if resolved_proxy is not None:
        logger.warning(
            "SSL verification disabled: proxy configured for %s profile",
            profile,
        )

    return httpx.Client(
        headers=dict(headers),
        cookies=httpx.Cookies(),
        event_hooks={"response": [_make_rate_limit_hook(min_delay_ms, jitter_ms)]},
        proxy=resolved_proxy,
        trust_env=False,
        verify=resolved_proxy is None,
    )
