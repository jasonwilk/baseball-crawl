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

Credentials are loaded from a .env file (see GAMECHANGER_REFRESH_TOKEN_WEB,
GAMECHANGER_CLIENT_ID_WEB, GAMECHANGER_CLIENT_KEY_WEB, GAMECHANGER_DEVICE_ID_WEB,
GAMECHANGER_BASE_URL).  Missing credentials raise ``ConfigurationError`` at
instantiation time.
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from dotenv import dotenv_values

from src.gamechanger.exceptions import (  # noqa: F401 -- re-exported for callers
    ConfigurationError,
    CredentialExpiredError,
    ForbiddenError,
    GameChangerAPIError,
    LoginFailedError,
    RateLimitError,
)
from src.gamechanger.token_manager import AuthSigningError, TokenManager
from src.http.session import create_session, resolve_proxy_from_dict

# Default fallback when Retry-After header cannot be parsed as an integer.
_DEFAULT_RETRY_AFTER_SECONDS = 60


def _parse_retry_after(value: str) -> int:
    """Parse a Retry-After header value, returning seconds to wait.

    Per RFC 7231 section 7.1.3, Retry-After can be an integer (delay-seconds)
    or an HTTP-date string.  We attempt integer parsing first; on failure,
    fall back to ``_DEFAULT_RETRY_AFTER_SECONDS`` rather than crashing.

    Args:
        value: Raw header value (e.g. ``"30"`` or ``"Fri, 31 Dec 1999 23:59:59 GMT"``).

    Returns:
        Seconds to wait (always >= 1).
    """
    try:
        return max(1, int(value))
    except (ValueError, TypeError):
        logger.warning(
            "Could not parse Retry-After header %r as integer; "
            "defaulting to %ds",
            value,
            _DEFAULT_RETRY_AFTER_SECONDS,
        )
        return _DEFAULT_RETRY_AFTER_SECONDS

logger = logging.getLogger(__name__)

# Profile suffix mapping for credential keys.
_PROFILE_SUFFIXES: dict[str, str] = {
    "web": "_WEB",
    "mobile": "_MOBILE",
}

_GC_CONTENT_TYPE = "application/vnd.gc.com.none+json; version=undefined"

# Default .env path: two levels up from src/gamechanger/.
_DEFAULT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def _required_keys(profile: str) -> tuple[str, ...]:
    """Return the unconditionally required env key names for the given profile.

    For web profile, all signing credentials are required. For mobile, only
    device_id and base_url are unconditionally required -- client_key and
    refresh_token are optional (manual access token fallback path). The
    TokenManager validates the conditional requirements at construction time.

    Args:
        profile: The credential profile (``"web"`` or ``"mobile"``).

    Returns:
        Tuple of required env key names.
        ``GAMECHANGER_BASE_URL`` is always required and remains unsuffixed.
    """
    suffix = _PROFILE_SUFFIXES.get(profile, f"_{profile.upper()}")
    if profile == "web":
        return (
            f"GAMECHANGER_REFRESH_TOKEN{suffix}",
            f"GAMECHANGER_CLIENT_ID{suffix}",
            f"GAMECHANGER_CLIENT_KEY{suffix}",
            f"GAMECHANGER_DEVICE_ID{suffix}",
            "GAMECHANGER_BASE_URL",
        )
    # Mobile: only device_id and base_url are unconditionally required.
    return (
        f"GAMECHANGER_DEVICE_ID{suffix}",
        "GAMECHANGER_BASE_URL",
    )


class GameChangerClient:
    """Authenticated HTTP client for the GameChanger API.

    Loads credentials from the .env file and uses a ``TokenManager`` to obtain
    short-lived access tokens.  The first API call triggers the token fetch
    lazily; subsequent calls reuse the cached token until it expires (the
    TokenManager manages expiry and refresh transparently).  On 401 responses,
    the client calls ``force_refresh()`` and retries once.

    Args:
        min_delay_ms: Minimum delay in milliseconds between requests.
            Forwarded to ``create_session()``.
        jitter_ms: Maximum additional random jitter in milliseconds.
            Forwarded to ``create_session()``.
        profile: Header profile to use.  ``"web"`` (default) selects the
            Chrome 145 browser fingerprint; ``"mobile"`` selects the iOS
            Odyssey app fingerprint.  Forwarded to ``create_session()``,
            which raises ``ValueError`` for unknown profiles.  The profile
            also controls ``gc-app-name`` when the profile-scoped app name env
            var is absent.
    """

    def __init__(
        self, min_delay_ms: int = 1000, jitter_ms: int = 500, profile: str = "web"
    ) -> None:
        self._profile = profile
        self._credentials = self._load_credentials(profile)
        self._base_url = self._credentials["GAMECHANGER_BASE_URL"].rstrip("/")
        self._session_id = secrets.token_hex(8)
        logger.debug("GameChangerClient session ID: %s", self._session_id)
        proxy_url = resolve_proxy_from_dict(self._credentials, profile, session_id=self._session_id)
        self._session = create_session(
            min_delay_ms=min_delay_ms, jitter_ms=jitter_ms, profile=profile,
            proxy_url=proxy_url,
        )
        suffix = _PROFILE_SUFFIXES.get(profile, f"_{profile.upper()}")

        # Set device-id and app-name on the session (non-sensitive, set eagerly).
        self._session.headers["gc-device-id"] = self._credentials[f"GAMECHANGER_DEVICE_ID{suffix}"]
        app_name = self._credentials.get(f"GAMECHANGER_APP_NAME{suffix}")
        if app_name:
            self._session.headers["gc-app-name"] = app_name
        elif profile == "web":
            self._session.headers["gc-app-name"] = "web"
        # mobile profile with no GAMECHANGER_APP_NAME_MOBILE: omit gc-app-name entirely

        # Public session: same network config as the main session but NO auth headers.
        # Used by get_public() for unauthenticated GameChanger public API endpoints.
        self._public_session = create_session(
            min_delay_ms=min_delay_ms, jitter_ms=jitter_ms, profile=profile,
            proxy_url=proxy_url,
        )

        # Build the token manager. Token fetch is lazy -- happens on first API call.
        self._token_manager = self._build_token_manager(profile, suffix)

    def _build_token_manager(self, profile: str, suffix: str) -> TokenManager:
        """Construct a TokenManager from loaded credentials.

        Args:
            profile: The credential profile (``"web"`` or ``"mobile"``).
            suffix: Profile suffix (e.g. ``"_WEB"``).

        Returns:
            A configured ``TokenManager`` instance.

        Raises:
            ConfigurationError: If the TokenManager rejects the credential set.
        """
        creds = self._credentials
        client_id = creds.get(f"GAMECHANGER_CLIENT_ID{suffix}") or None
        client_key = creds.get(f"GAMECHANGER_CLIENT_KEY{suffix}") or None
        refresh_token = creds.get(f"GAMECHANGER_REFRESH_TOKEN{suffix}") or None
        device_id = creds[f"GAMECHANGER_DEVICE_ID{suffix}"]
        access_token = creds.get(f"GAMECHANGER_ACCESS_TOKEN{suffix}") or None
        app_name_mobile = (
            creds.get(f"GAMECHANGER_APP_NAME{suffix}") if profile == "mobile" else None
        )
        # Login fallback credentials (optional -- web profile only)
        email = creds.get("GAMECHANGER_USER_EMAIL") or None
        password = creds.get("GAMECHANGER_USER_PASSWORD") or None
        try:
            return TokenManager(
                profile=profile,
                client_id=client_id,
                client_key=client_key,
                refresh_token=refresh_token,
                device_id=device_id,
                base_url=self._base_url,
                access_token=access_token,
                app_name_mobile=app_name_mobile,
                env_path=_DEFAULT_ENV_PATH,
                email=email,
                password=password,
            )
        except ConfigurationError:
            raise
        except Exception as exc:
            # Re-wrap TokenManager's ConfigurationError (imported from client module
            # by token_manager) so callers see our ConfigurationError type.
            raise ConfigurationError(str(exc)) from exc

    def _ensure_access_token(self) -> None:
        """Obtain a valid access token and set it as gc-token on the session.

        Called before every API request. The TokenManager caches the token and
        handles expiry internally -- this method only triggers a network call when
        the token is absent or expired.
        """
        token = self._token_manager.get_access_token()
        self._session.headers["gc-token"] = token

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

        On 401, performs a single token refresh and retries the failing page.

        Args:
            path: API path for the first page (e.g. ``"/teams/abc/game-summaries"``).
            params: Optional query parameters for the first page.
            timeout: Request timeout in seconds (default: 30).
            accept: Optional endpoint-specific ``Accept`` header.

        Returns:
            Flat list of all records across all pages.

        Raises:
            CredentialExpiredError: On 401 or 403 responses (after retry on 401).
            RateLimitError: On 429 responses.
            GameChangerAPIError: On 5xx responses after retries.
        """
        self._ensure_access_token()

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
                    # Re-raise immediately if refresh fails -- don't retry with stale token.
                    new_token = self._token_manager.force_refresh()
                    self._session.headers["gc-token"] = new_token
                    retry_response = self._session.get(
                        url, params=current_params, timeout=timeout, headers=extra_headers
                    )
                    if retry_response.status_code == 200:
                        page_response = retry_response
                        break
                    if retry_response.status_code == 401:
                        raise CredentialExpiredError(
                            f"Credentials rejected for {url} "
                            f"(HTTP {retry_response.status_code}). "
                            "Credentials may be expired -- check .env or run: bb creds check"
                        )
                    # Route the retry response through the same error handling so
                    # 403, 429, and 5xx are surfaced with the correct exception type.
                    response = retry_response

                if response.status_code == 403:
                    raise ForbiddenError(
                        f"Access denied for {url} "
                        f"(HTTP {response.status_code}). "
                        "Credentials may be expired -- check .env or run: bb creds check"
                    )

                if response.status_code == 429:
                    retry_after = _parse_retry_after(
                        response.headers.get("Retry-After", str(_DEFAULT_RETRY_AFTER_SECONDS))
                    )
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

            # Validate that the next-page URL's host matches our base URL's host.
            # Defense-in-depth: a malicious server response could redirect auth
            # tokens to an attacker-controlled host.
            next_host = urlparse(next_page_url).hostname
            base_host = urlparse(self._base_url).hostname
            if next_host != base_host:
                logger.warning(
                    "Pagination URL host mismatch: expected %s, got %s. "
                    "Stopping pagination.",
                    base_host,
                    next_host,
                )
                break

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

        Returns:
            Parsed JSON response (dict or list depending on the endpoint).

        Raises:
            CredentialExpiredError: On 401 (after refresh retry) or 403.
            RateLimitError: On 429 responses (after waiting Retry-After).
            GameChangerAPIError: On 5xx responses after 3 retries.
        """
        self._ensure_access_token()

        url = f"{self._base_url}{path}"
        headers: dict[str, str] = {
            "Content-Type": _GC_CONTENT_TYPE,
        }
        if accept is not None:
            headers["Accept"] = accept

        return self._get_with_retries(url, path, params, timeout, headers)

    def get_public(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        timeout: int = 30,
        accept: str | None = None,
    ) -> Any:
        """Make a public (unauthenticated) GET request and return the parsed JSON response.

        Does NOT inject ``gc-token`` or ``gc-device-id`` headers.  Used for
        GameChanger public API endpoints that require no authentication (e.g.
        ``GET /public/teams/{public_id}/games``).  Rate limiting and retry
        behaviour are consistent with ``get()``.

        Args:
            path: API path (e.g. ``"/public/teams/abc/games"``).  Must start
                with ``/``.
            params: Optional query parameters dict.
            timeout: Request timeout in seconds (default: 30).
            accept: Optional endpoint-specific ``Accept`` header value.

        Returns:
            Parsed JSON response (dict or list depending on the endpoint).

        Raises:
            RateLimitError: On 429 responses (after waiting Retry-After).
            GameChangerAPIError: On 5xx responses after 3 retries.
        """
        url = f"{self._base_url}{path}"
        headers: dict[str, str] = {
            "Content-Type": _GC_CONTENT_TYPE,
        }
        if accept is not None:
            headers["Accept"] = accept

        backoff_delays = [1, 2, 4]
        last_error: GameChangerAPIError | None = None

        for attempt, backoff in enumerate(backoff_delays):
            logger.debug("GET public %s (attempt %d)", url, attempt + 1)
            response = self._public_session.get(
                url, params=params, timeout=timeout, headers=headers
            )
            logger.debug("GET public %s -> %d", path, response.status_code)

            if response.status_code == 200:
                return response.json()

            if response.status_code == 429:
                retry_after = _parse_retry_after(
                    response.headers.get("Retry-After", str(_DEFAULT_RETRY_AFTER_SECONDS))
                )
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
                        "Server error %d on public %s -- retrying in %ds (attempt %d/3)",
                        response.status_code,
                        path,
                        backoff,
                        attempt + 1,
                    )
                    time.sleep(backoff)
                    continue
            else:
                raise GameChangerAPIError(
                    f"Unexpected status {response.status_code} for {path}."
                )

        assert last_error is not None
        raise last_error

    def _get_with_retries(
        self,
        url: str,
        path: str,
        params: dict[str, Any] | None,
        timeout: int,
        headers: dict[str, str],
    ) -> Any:
        """Execute GET with up to 3 retries on 5xx and a single retry on 401.

        Args:
            url: Full URL to request.
            path: Path segment (used in error messages).
            params: Query parameters.
            timeout: Request timeout in seconds.
            headers: Per-request headers to merge with session defaults.

        Returns:
            Parsed JSON response body.

        Raises:
            CredentialExpiredError: On 401 (after refresh retry) or 403.
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
                # Re-raise immediately if refresh fails -- don't retry with stale token.
                new_token = self._token_manager.force_refresh()
                self._session.headers["gc-token"] = new_token
                retry_response = self._session.get(
                    url, params=params, timeout=timeout, headers=headers
                )
                if retry_response.status_code == 200:
                    return retry_response.json()
                if retry_response.status_code == 401:
                    raise CredentialExpiredError(
                        f"Credentials rejected for {path} "
                        f"(HTTP {retry_response.status_code}). "
                        "Credentials may be expired -- check .env or run: bb creds check"
                    )
                # Route the retry response through the same error handling so
                # 403, 429, and 5xx are surfaced with the correct exception type.
                response = retry_response

            if response.status_code == 403:
                raise ForbiddenError(
                    f"Access denied for {path} "
                    f"(HTTP {response.status_code}). "
                    "Credentials may be expired -- check .env or run: bb creds check"
                )

            if response.status_code == 429:
                retry_after = _parse_retry_after(
                    response.headers.get("Retry-After", str(_DEFAULT_RETRY_AFTER_SECONDS))
                )
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
                raise last_error

            # Unexpected non-success status -- treat as a non-retryable API error.
            raise GameChangerAPIError(
                f"Unexpected status {response.status_code} for {path}."
            )

    def post(
        self,
        path: str,
        timeout: int = 30,
    ) -> None:
        """Make an authenticated POST request. Returns None on 204 No Content success.

        Does not attempt JSON parsing.  Used for state-changing endpoints that
        return no body (e.g., ``POST /teams/{id}/follow``).

        Args:
            path: API path (e.g. ``"/teams/abc/follow"``).  Must start with ``/``.
            timeout: Request timeout in seconds (default: 30).

        Returns:
            None on 204 success.

        Raises:
            CredentialExpiredError: On 401 (after refresh retry) or 403.
            RateLimitError: On 429 responses.
            GameChangerAPIError: On unexpected status codes.
        """
        self._ensure_access_token()
        url = f"{self._base_url}{path}"
        headers = {"Content-Type": _GC_CONTENT_TYPE}
        logger.debug("POST %s", url)
        response = self._session.post(url, timeout=timeout, headers=headers)
        logger.debug("POST %s -> %d", path, response.status_code)

        if response.status_code == 204:
            return None

        if response.status_code == 401:
            new_token = self._token_manager.force_refresh()
            self._session.headers["gc-token"] = new_token
            retry_response = self._session.post(url, timeout=timeout, headers=headers)
            if retry_response.status_code == 204:
                return None
            if retry_response.status_code == 401:
                raise CredentialExpiredError(
                    f"Credentials rejected for {path} "
                    f"(HTTP {retry_response.status_code}). "
                    "Credentials may be expired -- check .env or run: bb creds check"
                )
            response = retry_response

        if response.status_code == 403:
            raise ForbiddenError(
                f"Access denied for {path} "
                f"(HTTP {response.status_code}). "
                "Credentials may be expired -- check .env or run: bb creds check"
            )

        if response.status_code == 429:
            retry_after = _parse_retry_after(
                response.headers.get("Retry-After", str(_DEFAULT_RETRY_AFTER_SECONDS))
            )
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

        raise GameChangerAPIError(
            f"Unexpected status {response.status_code} for {path}."
        )

    def delete(
        self,
        path: str,
        timeout: int = 30,
    ) -> None:
        """Make an authenticated DELETE request. Returns None on success.

        Accepts both 204 No Content and 200 with text body ``"OK"`` as success
        (the GameChanger API uses both depending on the endpoint).

        Args:
            path: API path (e.g. ``"/teams/abc/users/user-id"``).  Must start
                with ``/``.
            timeout: Request timeout in seconds (default: 30).

        Returns:
            None on 200 or 204 success.

        Raises:
            CredentialExpiredError: On 401 (after refresh retry) or 403.
            RateLimitError: On 429 responses.
            GameChangerAPIError: On unexpected status codes.
        """
        self._ensure_access_token()
        url = f"{self._base_url}{path}"
        headers = {"Content-Type": _GC_CONTENT_TYPE}
        logger.debug("DELETE %s", url)
        response = self._session.delete(url, timeout=timeout, headers=headers)
        logger.debug("DELETE %s -> %d", path, response.status_code)

        if response.status_code in (200, 204):
            return None

        if response.status_code == 401:
            new_token = self._token_manager.force_refresh()
            self._session.headers["gc-token"] = new_token
            retry_response = self._session.delete(url, timeout=timeout, headers=headers)
            if retry_response.status_code in (200, 204):
                return None
            if retry_response.status_code == 401:
                raise CredentialExpiredError(
                    f"Credentials rejected for {path} "
                    f"(HTTP {retry_response.status_code}). "
                    "Credentials may be expired -- check .env or run: bb creds check"
                )
            response = retry_response

        if response.status_code == 403:
            raise ForbiddenError(
                f"Access denied for {path} "
                f"(HTTP {response.status_code}). "
                "Credentials may be expired -- check .env or run: bb creds check"
            )

        if response.status_code == 429:
            retry_after = _parse_retry_after(
                response.headers.get("Retry-After", str(_DEFAULT_RETRY_AFTER_SECONDS))
            )
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

        raise GameChangerAPIError(
            f"Unexpected status {response.status_code} for {path}."
        )

    def _load_credentials(self, profile: str) -> dict[str, str]:
        """Load profile-scoped credentials from the .env file.

        Reads the .env file (if present) using python-dotenv and validates that
        always-required profile-scoped keys are present. Conditional requirements
        (e.g., client_key vs. access_token for mobile) are validated by the
        TokenManager at construction time.

        Args:
            profile: The credential profile (``"web"`` or ``"mobile"``).

        Returns:
            Dict mapping env variable names to their values.

        Raises:
            ConfigurationError: If any unconditionally required key is missing.
        """
        env_values = {**dotenv_values(_DEFAULT_ENV_PATH)}
        # Fall back to process environment for keys not found in .env file
        # (e.g., when running inside a Docker container where env vars are
        # injected by Docker Compose rather than read from a mounted file).
        # Covers all keys -- required, optional, and proxy -- not just
        # _required_keys(), so that GAMECHANGER_USER_EMAIL/PASSWORD and
        # profile-scoped optional keys are available in Docker deployments.
        for key, val in os.environ.items():
            if not env_values.get(key) and val:
                env_values[key] = val
        required = _required_keys(profile)
        missing = [key for key in required if not env_values.get(key)]
        if missing:
            raise ConfigurationError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                "Ensure they are set in your .env file or environment."
            )
        return {k: v for k, v in env_values.items() if v is not None}
