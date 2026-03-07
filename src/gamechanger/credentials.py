"""Credential validation logic for the GameChanger API.

Provides functions to check whether stored credentials are valid by making
a lightweight API call (GET /me/user).  Used by both the ``bb creds check``
command and the ``bb status`` dashboard.
"""

from __future__ import annotations

import logging

import httpx

from src.gamechanger.client import (
    ConfigurationError,
    CredentialExpiredError,
    ForbiddenError,
    GameChangerClient,
)

logger = logging.getLogger(__name__)

_ME_USER_ACCEPT = "application/vnd.gc.com.user+json; version=0.3.0"
_ALL_PROFILES: tuple[str, ...] = ("web", "mobile")


def check_single_profile(profile: str) -> tuple[int, str]:
    """Validate credentials for one profile by calling GET /me/user.

    Args:
        profile: The credential profile to validate (``"web"`` or ``"mobile"``).

    Returns:
        A tuple of (exit_code, message) where exit_code is:
        - 0: credentials valid
        - 1: credentials expired, revoked, or network error
        - 2: required credentials missing from .env
    """
    try:
        client = GameChangerClient(min_delay_ms=0, jitter_ms=0, profile=profile)
    except ConfigurationError as exc:
        return (2, f"Missing required credential(s): {exc}")

    try:
        user = client.get("/me/user", accept=_ME_USER_ACCEPT)
    except ForbiddenError:
        return (1, "Access denied -- credentials may be expired or revoked")
    except CredentialExpiredError:
        return (1, "Credentials expired -- refresh via proxy capture")
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        return (1, f"Network error reaching GameChanger API: {exc}")
    except Exception as exc:  # noqa: BLE001
        return (1, f"Unexpected error: {exc}")

    first = (user.get("first_name") or "").strip()
    last = (user.get("last_name") or "").strip()
    display = f"{first} {last}".strip() if (first and last) else user.get("email", "(unknown)")
    return (0, f"valid -- logged in as {display}")


def check_credentials(profile: str | None = None) -> tuple[int, str]:
    """Validate GameChanger credentials from .env.

    When *profile* is given, checks only that profile's credentials.
    When *profile* is ``None``, checks all profiles and returns a summary.

    Args:
        profile: The credential profile (``"web"`` or ``"mobile"``), or ``None``
            to check all profiles.

    Returns:
        A tuple of (exit_code, message).

        Single-profile exit codes:
        - 0: credentials valid
        - 1: credentials expired, revoked, or network error
        - 2: required credentials missing from .env

        Multi-profile exit codes:
        - 0: at least one profile is valid
        - 1: all profiles failed
    """
    if profile is not None:
        code, msg = check_single_profile(profile)
        return (code, f"Credentials {msg}" if code == 0 else msg)

    # Multi-profile summary
    results: dict[str, tuple[int, str]] = {}
    for p in _ALL_PROFILES:
        results[p] = check_single_profile(p)

    lines = ["Credential status:"]
    for p, (code, msg) in results.items():
        lines.append(f"  {p}:  {msg}" if code == 0 else f"  {p}:  {msg}")

    summary = "\n".join(lines)
    any_valid = any(code == 0 for code, _ in results.values())
    return (0 if any_valid else 1, summary)
