"""Authenticated GameChanger API HTTP client.

Wraps the project-standard session factory with GameChanger-specific
authentication headers and structured error handling.  All callers
(ingestion scripts, smoke tests, etc.) must use this client -- never
make raw httpx calls directly.

Usage::

    from src.gamechanger.client import GameChangerClient

    client = GameChangerClient()
    games = client.get(
        "/teams/{team_id}/game-summaries",
        accept="application/vnd.gc.com.game_summary:list+json; version=0.1.0",
    )

Credentials are loaded from a .env file (see GAMECHANGER_AUTH_TOKEN,
GAMECHANGER_DEVICE_ID, GAMECHANGER_BASE_URL).  Missing credentials
raise ``ConfigurationError`` at instantiation time.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from dotenv import dotenv_values

from src.http.session import create_session

logger = logging.getLogger(__name__)

# Profile suffix mapping for credential keys.
_PROFILE_SUFFIXES: dict[str, str] = {
    "web": "_WEB",
    "mobile": "_MOBILE",
}

# Credential key base names that are profile-scoped (suffix applied per profile).
_PROFILE_SCOPED_KEYS: tuple[str, ...] = (
    "GAMECHANGER_AUTH_TOKEN",
    "GAMECHANGER_DEVICE_ID",
    "GAMECHANGER_APP_NAME",
    "GAMECHANGER_SIGNATURE",
)


def _required_keys(profile: str) -> tuple[str, ...]:
    """Return the required env key names for the given profile.

    Args:
        profile: The credential profile (``"web"`` or ``"mobile"``).

    Returns:
        Tuple of required env key names with the appropriate profile suffix.
        ``GAMECHANGER_BASE_URL`` is always required and remains unsuffixed.
    """
    suffix = _PROFILE_SUFFIXES.get(profile, f"_{profile.upper()}")
    return (
        f"GAMECHANGER_AUTH_TOKEN{suffix}",
        f"GAMECHANGER_DEVICE_ID{suffix}",
        "GAMECHANGER_BASE_URL",
    )

_GC_CONTENT_TYPE = "application/vnd.gc.com.none+json; version=undefined"


class CredentialExpiredError(Exception):
    """Raised when the API returns 401 (token has expired or is invalid)."""


class ForbiddenError(CredentialExpiredError):
    """Raised when the API returns 403 (per-resource access denial).

    Subclass of ``CredentialExpiredError`` for backward compatibility -- existing
    ``except CredentialExpiredError`` clauses will still catch 403 responses.
    Use ``except ForbiddenError`` before ``except CredentialExpiredError`` to
    distinguish per-resource denial from token expiry.
    """


class RateLimitError(Exception):
    """Raised when the API returns 429 (rate limit hit)."""


class GameChangerAPIError(Exception):
    """Raised when the API returns a 5xx error after all retries are exhausted."""


class ConfigurationError(Exception):
    """Raised at instantiation when required environment variables are missing."""


class GameChangerClient:
    """Authenticated HTTP client for the GameChanger API.

    Loads credentials from the .env file and injects them as custom headers
    on every request.  Rate limiting and browser-realistic headers are
    delegated to the session factory.

    Args:
        min_delay_ms: Minimum delay in milliseconds between requests.
            Forwarded to ``create_session()``.
        jitter_ms: Maximum additional random jitter in milliseconds.
            Forwarded to ``create_session()``.
        profile: Header profile to use.  ``"web"`` (default) selects the
            Chrome 145 browser fingerprint; ``"mobile"`` selects the iOS
            Odyssey app fingerprint.  Forwarded to ``create_session()``,
            which raises ``ValueError`` for unknown profiles.  The profile
            also controls ``gc-app-name`` when the ``GAMECHANGER_APP_NAME``
            env var is absent: ``"web"`` defaults the header to ``"web"``,
            ``"mobile"`` omits the header entirely (iOS app does not send it).
    """

    def __init__(
        self, min_delay_ms: int = 1000, jitter_ms: int = 500, profile: str = "web"
    ) -> None:
        self._credentials = self._load_credentials(profile)
        self._base_url = self._credentials["GAMECHANGER_BASE_URL"].rstrip("/")
        self._session = create_session(
            min_delay_ms=min_delay_ms, jitter_ms=jitter_ms, profile=profile
        )
        suffix = _PROFILE_SUFFIXES.get(profile, f"_{profile.upper()}")
        self._session.headers["gc-token"] = self._credentials[f"GAMECHANGER_AUTH_TOKEN{suffix}"]
        self._session.headers["gc-device-id"] = self._credentials[f"GAMECHANGER_DEVICE_ID{suffix}"]
        app_name = self._credentials.get(f"GAMECHANGER_APP_NAME{suffix}")
        if app_name:
            self._session.headers["gc-app-name"] = app_name
        elif profile == "web":
            self._session.headers["gc-app-name"] = "web"
        # mobile profile with no GAMECHANGER_APP_NAME_MOBILE: omit gc-app-name entirely

    def get_paginated(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        timeout: int = 30,
        accept: str | None = None,
    ) -> list[Any]:
        """Fetch all pages of a paginated endpoint and return the combined list.

        Sends ``x-pagination: true`` on every request and follows ``x-next-page``
        response headers until the header is absent (last page).  Each page must
        return a JSON array; pages are concatenated in order.

        Args:
            path: API path for the first page (e.g. ``"/teams/abc/game-summaries"``).
            params: Optional query parameters for the first page.
            timeout: Request timeout in seconds (default: 30).
            accept: Optional endpoint-specific ``Accept`` header.

        Returns:
            Flat list of all records across all pages.

        Raises:
            CredentialExpiredError: On 401 or 403 responses.
            RateLimitError: On 429 responses.
            GameChangerAPIError: On 5xx responses after retries.
        """
        records: list[Any] = []
        base_url = self._base_url
        url: str = f"{base_url}{path}"
        extra_headers: dict[str, str] = {"x-pagination": "true"}
        if accept is not None:
            extra_headers["Accept"] = accept
        extra_headers["Content-Type"] = _GC_CONTENT_TYPE

        current_params = params
        backoff_delays = [1, 2, 4]

        while True:
            logger.debug("GET paginated %s", url)

            # Retry each page individually on 5xx -- does not restart pagination.
            last_error: GameChangerAPIError | None = None
            page_response: httpx.Response | None = None

            for attempt, backoff in enumerate(backoff_delays):
                logger.debug("GET paginated %s (attempt %d)", url, attempt + 1)
                response = self._session.get(
                    url, params=current_params, timeout=timeout, headers=extra_headers
                )
                logger.debug("GET paginated %s -> %d", url, response.status_code)

                if response.status_code == 200:
                    page_response = response
                    break

                if response.status_code == 401:
                    raise CredentialExpiredError(
                        f"Credentials rejected for {url} "
                        f"(HTTP {response.status_code}). "
                        "Refresh by running: python scripts/refresh_credentials.py"
                    )

                if response.status_code == 403:
                    raise ForbiddenError(
                        f"Access denied for {url} "
                        f"(HTTP {response.status_code}). "
                        "Refresh by running: python scripts/refresh_credentials.py"
                    )

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "60"))
                    logger.warning(
                        "Rate limit hit on %s (HTTP 429). Waiting %ds before raising.",
                        url,
                        retry_after,
                    )
                    time.sleep(retry_after)
                    raise RateLimitError(
                        f"Rate limit exceeded for {url} (HTTP 429). "
                        f"Waited {retry_after}s."
                    )

                if 500 <= response.status_code < 600:
                    last_error = GameChangerAPIError(
                        f"Server error for {url} "
                        f"(HTTP {response.status_code}) after {attempt + 1} attempt(s)."
                    )
                    if attempt < len(backoff_delays) - 1:
                        logger.warning(
                            "Server error %d on paginated %s -- retrying in %ds (attempt %d/3)",
                            response.status_code,
                            url,
                            backoff,
                            attempt + 1,
                        )
                        time.sleep(backoff)
                        continue

                else:
                    # Non-5xx, non-200, non-401/403, non-429 -- raise immediately.
                    raise GameChangerAPIError(
                        f"Unexpected status {response.status_code} for {url}."
                    )

            if page_response is None:
                assert last_error is not None
                raise last_error

            page_data = page_response.json()
            if isinstance(page_data, list):
                records.extend(page_data)
            else:
                records.append(page_data)

            next_page_url = page_response.headers.get("x-next-page")
            if not next_page_url:
                break

            # Next page URL is absolute -- use it directly, no params needed.
            url = next_page_url
            current_params = None

        logger.info("Paginated fetch complete: %d total records from %s", len(records), path)
        return records

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        timeout: int = 30,
        accept: str | None = None,
    ) -> Any:
        """Make an authenticated GET request and return the parsed JSON response.

        Args:
            path: API path (e.g. ``"/teams/abc/game-summaries"``).  Must start
                with ``/``.
            params: Optional query parameters dict.
            timeout: Request timeout in seconds (default: 30).
            accept: Optional endpoint-specific ``Accept`` header value.  When
                provided, overrides the session default for this request.
                Required for most GameChanger endpoints.
            timeout: Request timeout in seconds.

        Returns:
            Parsed JSON response (dict or list depending on the endpoint).

        Raises:
            CredentialExpiredError: On 401 or 403 responses.
            RateLimitError: On 429 responses (after waiting Retry-After).
            GameChangerAPIError: On 5xx responses after 3 retries.
        """
        url = f"{self._base_url}{path}"
        headers: dict[str, str] = {
            "Content-Type": _GC_CONTENT_TYPE,
        }
        if accept is not None:
            headers["Accept"] = accept

        return self._get_with_retries(url, path, params, timeout, headers)

    def _get_with_retries(
        self,
        url: str,
        path: str,
        params: dict[str, Any] | None,
        timeout: int,
        headers: dict[str, str],
    ) -> Any:
        """Execute GET with up to 3 retries on 5xx (exponential backoff).

        Args:
            url: Full URL to request.
            path: Path segment (used in error messages).
            params: Query parameters.
            timeout: Request timeout in seconds.
            headers: Per-request headers to merge with session defaults.

        Returns:
            Parsed JSON response body.

        Raises:
            CredentialExpiredError: On 401 or 403.
            RateLimitError: On 429 (after waiting).
            GameChangerAPIError: On 5xx after all retries exhausted.
        """
        backoff_delays = [1, 2, 4]
        last_error: GameChangerAPIError | None = None

        for attempt, backoff in enumerate(backoff_delays):
            logger.debug("GET %s (attempt %d)", url, attempt + 1)
            response = self._session.get(url, params=params, timeout=timeout, headers=headers)
            logger.debug("GET %s -> %d", path, response.status_code)

            if response.status_code == 200:
                return response.json()

            if response.status_code == 401:
                raise CredentialExpiredError(
                    f"Credentials rejected for {path} "
                    f"(HTTP {response.status_code}). "
                    "Refresh by running: python scripts/refresh_credentials.py"
                )

            if response.status_code == 403:
                raise ForbiddenError(
                    f"Access denied for {path} "
                    f"(HTTP {response.status_code}). "
                    "Refresh by running: python scripts/refresh_credentials.py"
                )

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "60"))
                logger.warning(
                    "Rate limit hit on %s (HTTP 429). Waiting %ds before raising.",
                    path,
                    retry_after,
                )
                time.sleep(retry_after)
                raise RateLimitError(
                    f"Rate limit exceeded for {path} (HTTP 429). "
                    f"Waited {retry_after}s."
                )

            if 500 <= response.status_code < 600:
                last_error = GameChangerAPIError(
                    f"Server error for {path} "
                    f"(HTTP {response.status_code}) after {attempt + 1} attempt(s)."
                )
                if attempt < len(backoff_delays) - 1:
                    logger.warning(
                        "Server error %d on %s -- retrying in %ds (attempt %d/3)",
                        response.status_code,
                        path,
                        backoff,
                        attempt + 1,
                    )
                    time.sleep(backoff)
                    continue

            # Unexpected non-success status -- treat as a non-retryable API error.
            raise GameChangerAPIError(
                f"Unexpected status {response.status_code} for {path}."
            )

        assert last_error is not None  # appease mypy; loop always sets this before here
        raise last_error

    def _load_credentials(self, profile: str) -> dict[str, str]:
        """Load profile-scoped credentials from the .env file.

        Reads the .env file (if present) using python-dotenv and validates that
        all required profile-scoped keys are present. No fallback to flat
        (unsuffixed) keys -- if the profile-scoped key is absent, raises
        ``ConfigurationError`` naming the expected key.

        Args:
            profile: The credential profile (``"web"`` or ``"mobile"``).

        Returns:
            Dict mapping env variable names to their values.

        Raises:
            ConfigurationError: If any required profile-scoped key is missing.
        """
        env_values = dotenv_values()
        required = _required_keys(profile)
        missing = [key for key in required if not env_values.get(key)]
        if missing:
            raise ConfigurationError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                "Ensure they are set in your .env file."
            )
        # Cast to dict[str, str] -- dotenv_values returns dict[str, str | None]
        # but we've already validated all required keys are non-empty.
        return {k: v for k, v in env_values.items() if v is not None}
