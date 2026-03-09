"""Credential validation logic for the GameChanger API.

Provides functions to check whether stored credentials are valid by making
a lightweight API call (GET /me/user).  Used by both the ``bb creds check``
command and the ``bb status`` dashboard.

Two APIs are exposed:

* :func:`check_credentials` / :func:`check_single_profile` -- lightweight
  helpers returning ``(exit_code, message)`` tuples.  Used by ``bb status``
  and the bootstrap pipeline.

* :func:`check_profile_detailed` -- comprehensive diagnostic returning a
  :class:`ProfileCheckResult`.  Used by the enhanced ``bb creds check`` output.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass

import httpx
from dotenv import dotenv_values

from src.gamechanger.client import (
    ConfigurationError,
    CredentialExpiredError,
    ForbiddenError,
    GameChangerClient,
    _required_keys,
)
from src.http.proxy_check import ProxyCheckResult, check_proxy_routing, get_direct_ip

logger = logging.getLogger(__name__)

_ME_USER_ACCEPT = "application/vnd.gc.com.user+json; version=0.3.0"
_ME_USER_ENDPOINT = "/me/user"
_ALL_PROFILES: tuple[str, ...] = ("web", "mobile")


# ---------------------------------------------------------------------------
# JWT helper
# ---------------------------------------------------------------------------


def decode_jwt_exp(token: str) -> int | None:
    """Extract the ``exp`` claim from a JWT payload without verification.

    Args:
        token: A JWT string (``header.payload.signature``).

    Returns:
        The ``exp`` Unix timestamp integer, or ``None`` if the token cannot
        be decoded (malformed, truncated, or missing the ``exp`` claim).
    """
    try:
        payload_segment = token.split(".")[1]
        # Add padding so length is a multiple of 4.
        padding = 4 - len(payload_segment) % 4
        payload_segment += "=" * (padding % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_segment))
        return int(payload["exp"])
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Diagnostic dataclasses (used by check_profile_detailed)
# ---------------------------------------------------------------------------


@dataclass
class CredentialPresence:
    """Which required .env keys are present and which are missing."""

    keys_present: list[str]
    keys_missing: list[str]


@dataclass
class TokenHealth:
    """JWT expiry status decoded locally from a refresh token."""

    exp: int | None
    """Unix timestamp from the ``exp`` claim, or ``None`` if undecodable."""

    is_expired: bool | None
    """``True`` if the token is past its expiry time.  ``None`` when *exp* is ``None``."""


@dataclass
class ApiCheckResult:
    """Result of a GET /me/user health check."""

    exit_code: int
    """0 = ok, 1 = expired / network error, 2 = missing credentials."""

    display_name: str | None
    """User display name (first + last, or email).  ``None`` when the check failed."""

    message: str
    """Human-readable status description."""


@dataclass
class ProfileCheckResult:
    """Comprehensive credential diagnostic for one profile."""

    profile: str
    presence: CredentialPresence
    token_health: TokenHealth | None
    """``None`` when the refresh-token key is absent from ``.env``."""
    api_result: ApiCheckResult
    proxy_result: ProxyCheckResult
    exit_code: int
    """0 = valid, 1 = expired / error, 2 = missing credentials."""


# ---------------------------------------------------------------------------
# Detailed check (used by enhanced bb creds check)
# ---------------------------------------------------------------------------


def _extract_display_name(user: dict) -> str:
    """Extract a display-safe name from a /me/user response dict.

    Returns first + last name when both are present, otherwise returns
    ``"(authenticated user)"`` to avoid exposing PII.
    """
    first = (user.get("first_name") or "").strip()
    last = (user.get("last_name") or "").strip()
    return f"{first} {last}".strip() if (first and last) else "(authenticated user)"


def _run_api_check(profile: str) -> ApiCheckResult:
    """Attempt GET /me/user and return a structured result.

    Never raises -- all errors are captured into the returned object.

    Args:
        profile: The credential profile (``"web"`` or ``"mobile"``).

    Returns:
        An :class:`ApiCheckResult` describing the outcome.
    """
    try:
        client = GameChangerClient(min_delay_ms=0, jitter_ms=0, profile=profile)
    except ConfigurationError as exc:
        return ApiCheckResult(exit_code=2, display_name=None, message=f"Missing credentials: {exc}")

    try:
        user = client.get(_ME_USER_ENDPOINT, accept=_ME_USER_ACCEPT)
    except ForbiddenError:
        return ApiCheckResult(
            exit_code=1,
            display_name=None,
            message="Access denied -- credentials may be expired or revoked",
        )
    except CredentialExpiredError:
        return ApiCheckResult(
            exit_code=1,
            display_name=None,
            message="Credentials expired -- refresh via proxy capture",
        )
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        return ApiCheckResult(
            exit_code=1,
            display_name=None,
            message=f"Network error reaching GameChanger API: {exc}",
        )
    except Exception as exc:  # noqa: BLE001
        return ApiCheckResult(exit_code=1, display_name=None, message=f"Unexpected error: {exc}")

    display = _extract_display_name(user)
    return ApiCheckResult(exit_code=0, display_name=display, message=f"200 OK, logged in as {display}")


def _check_presence(profile: str, env: dict) -> CredentialPresence:
    """Return which required keys are present and which are missing."""
    required = _required_keys(profile)
    return CredentialPresence(
        keys_present=[k for k in required if env.get(k)],
        keys_missing=[k for k in required if not env.get(k)],
    )


def _check_token_health(profile: str, env: dict) -> TokenHealth | None:
    """Decode the refresh token JWT locally and return expiry status.

    Returns ``None`` when the refresh-token key is absent from the env dict.
    """
    raw_token = env.get(f"GAMECHANGER_REFRESH_TOKEN_{profile.upper()}")
    if not raw_token:
        return None
    exp = decode_jwt_exp(raw_token)
    return TokenHealth(
        exp=exp,
        is_expired=(exp < int(time.time())) if exp is not None else None,
    )


def _check_api(profile: str, keys_missing: list[str]) -> tuple[ApiCheckResult, int]:
    """Run the API health check and return ``(result, exit_code)``.

    Skips the network call when *keys_missing* is non-empty.
    """
    if keys_missing:
        result = ApiCheckResult(
            exit_code=2,
            display_name=None,
            message="Skipped (required credentials missing)",
        )
        return result, 2
    result = _run_api_check(profile)
    return result, result.exit_code


def check_profile_detailed(profile: str) -> ProfileCheckResult:
    """Run a comprehensive credential diagnostic for one profile.

    Checks credential presence, refresh-token JWT expiry (decoded locally
    without a network call), API reachability via ``GET /me/user``, and
    Bright Data proxy routing status.  Never raises -- all errors are
    captured into the returned object.

    Args:
        profile: The credential profile (``"web"`` or ``"mobile"``).

    Returns:
        A :class:`ProfileCheckResult` with per-dimension diagnostic data.
        ``exit_code`` mirrors :func:`check_single_profile` semantics:
        0 = valid, 1 = expired / network error, 2 = missing credentials.
    """
    env = dotenv_values()
    presence = _check_presence(profile, env)
    token_health = _check_token_health(profile, env)
    api_result, exit_code = _check_api(profile, presence.keys_missing)
    proxy_result = check_proxy_routing(profile, get_direct_ip())
    return ProfileCheckResult(
        profile=profile,
        presence=presence,
        token_health=token_health,
        api_result=api_result,
        proxy_result=proxy_result,
        exit_code=exit_code,
    )


# ---------------------------------------------------------------------------
# Legacy helpers (used by bb status and the bootstrap pipeline)
# ---------------------------------------------------------------------------


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
    display = f"{first} {last}".strip() if (first and last) else "(authenticated user)"
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
