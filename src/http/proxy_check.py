"""Bright Data proxy routing diagnostic.

Provides ``check_proxy_routing()`` to verify that HTTP requests are travelling
through the configured Bright Data proxy.  The check hits an IP-echo service
once directly (no proxy) and once per profile through the proxy, then compares
the returned IP addresses.

This module is an HTTP-layer diagnostic tool and has no dependency on
GameChanger credentials.  It only reads ``PROXY_ENABLED`` and
``PROXY_URL_{PROFILE}`` from the dotenv dict.

Proxy URLs are never logged or displayed -- they contain credentials.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import httpx
from dotenv import dotenv_values

from src.http.session import create_session, resolve_proxy_from_dict

logger = logging.getLogger(__name__)

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

_IP_ECHO_URL = "https://api.ipify.org?format=json"
_CHECK_TIMEOUT = 10  # seconds -- short, it's a diagnostic


class ProxyCheckOutcome(str, Enum):
    """Result of a single proxy routing check."""

    PASS = "PASS"
    """Proxy IP differs from direct IP -- proxy is routing correctly."""

    FAIL = "FAIL"
    """Proxy IP matches direct IP -- proxy is not routing."""

    ERROR = "ERROR"
    """Proxy request failed (connection refused, timeout, etc.)."""

    PASS_UNVERIFIED = "PASS-UNVERIFIED"
    """Proxy request succeeded but direct IP baseline is unavailable."""

    NOT_CONFIGURED = "NOT-CONFIGURED"
    """Proxy is not enabled or no URL configured for this profile."""


@dataclass
class ProxyCheckResult:
    """Result of a proxy routing check for one profile."""

    profile: str
    outcome: ProxyCheckOutcome
    proxy_ip: str | None = None
    direct_ip: str | None = None
    error: str | None = None


def _fetch_ip(session: httpx.Client, label: str) -> str | None:
    """Fetch IP address from the echo service.  Returns None on any failure.

    Args:
        session: Configured httpx.Client to use for the request.
        label: Human-readable label for log context (e.g. ``"direct"``).

    Returns:
        IP address string, or ``None`` if the request fails.
    """
    try:
        response = session.get(_IP_ECHO_URL, timeout=_CHECK_TIMEOUT)
        response.raise_for_status()
        return response.json().get("ip")
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        logger.debug("IP fetch failed for %s: %s", label, exc)
        return None


def get_direct_ip() -> str | None:
    """Fetch the real (un-proxied) IP address of this machine.

    Returns:
        IP address string, or ``None`` if the request fails.
    """
    with create_session(min_delay_ms=0, jitter_ms=0, proxy_url=None) as session:
        return _fetch_ip(session, "direct")


def check_proxy_routing(profile: str, direct_ip: str | None) -> ProxyCheckResult:
    """Check whether requests for *profile* route through the configured proxy.

    Reads proxy config from the dotenv dict (not ``os.environ``).  Passes the
    resolved URL explicitly to ``create_session()`` so the dotenv dict values
    are honoured even when not merged into ``os.environ``.

    Proxy URLs are never logged.

    Args:
        profile: Session profile to check (``"web"`` or ``"mobile"``).
        direct_ip: The real (un-proxied) IP address, or ``None`` if the direct
            baseline request failed.

    Returns:
        A ``ProxyCheckResult`` describing the outcome for this profile.
    """
    env = dotenv_values(_ENV_PATH)
    proxy_url = resolve_proxy_from_dict(env, profile)

    if proxy_url is None:
        return ProxyCheckResult(
            profile=profile,
            outcome=ProxyCheckOutcome.NOT_CONFIGURED,
        )

    try:
        with create_session(
            min_delay_ms=0, jitter_ms=0, profile=profile, proxy_url=proxy_url
        ) as session:
            proxy_ip = _fetch_ip(session, f"{profile} proxy")
    except (httpx.RequestError, httpx.HTTPStatusError, OSError) as exc:
        return ProxyCheckResult(
            profile=profile,
            outcome=ProxyCheckOutcome.ERROR,
            error=str(exc),
        )

    if proxy_ip is None:
        return ProxyCheckResult(
            profile=profile,
            outcome=ProxyCheckOutcome.ERROR,
            error="IP echo service returned no response through proxy",
        )

    if direct_ip is None:
        return ProxyCheckResult(
            profile=profile,
            outcome=ProxyCheckOutcome.PASS_UNVERIFIED,
            proxy_ip=proxy_ip,
        )

    if proxy_ip != direct_ip:
        return ProxyCheckResult(
            profile=profile,
            outcome=ProxyCheckOutcome.PASS,
            proxy_ip=proxy_ip,
            direct_ip=direct_ip,
        )

    return ProxyCheckResult(
        profile=profile,
        outcome=ProxyCheckOutcome.FAIL,
        proxy_ip=proxy_ip,
        direct_ip=direct_ip,
    )
