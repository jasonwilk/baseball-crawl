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

_REQUIRED_KEYS: tuple[str, ...] = (
    "GAMECHANGER_AUTH_TOKEN",
    "GAMECHANGER_DEVICE_ID",
    "GAMECHANGER_BASE_URL",
)

_GC_CONTENT_TYPE = "application/vnd.gc.com.none+json; version=undefined"


class CredentialExpiredError(Exception):
    """Raised when the API returns 401 or 403 (credentials have expired)."""


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
    """

    def __init__(self, min_delay_ms: int = 1000, jitter_ms: int = 500) -> None:
        self._credentials = self._load_credentials()
        self._base_url = self._credentials["GAMECHANGER_BASE_URL"].rstrip("/")
        self._session = create_session(min_delay_ms=min_delay_ms, jitter_ms=jitter_ms)
        self._session.headers["gc-token"] = self._credentials["GAMECHANGER_AUTH_TOKEN"]
        self._session.headers["gc-device-id"] = self._credentials["GAMECHANGER_DEVICE_ID"]
        self._session.headers["gc-app-name"] = self._credentials.get(
            "GAMECHANGER_APP_NAME", "web"
        )

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

            if response.status_code in (401, 403):
                raise CredentialExpiredError(
                    f"Credentials rejected for {path} "
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

    def _load_credentials(self) -> dict[str, str]:
        """Load credentials from the .env file.

        Reads the .env file (if present) using python-dotenv and validates that
        all required keys are present.

        Returns:
            Dict mapping env variable names to their values.

        Raises:
            ConfigurationError: If any required key is missing.
        """
        env_values = dotenv_values()
        missing = [key for key in _REQUIRED_KEYS if not env_values.get(key)]
        if missing:
            raise ConfigurationError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                "Ensure they are set in your .env file."
            )
        # Cast to dict[str, str] -- dotenv_values returns dict[str, str | None]
        # but we've already validated all required keys are non-empty.
        return {k: v for k, v in env_values.items() if v is not None}
