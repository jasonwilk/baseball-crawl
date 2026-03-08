"""Token lifecycle manager for the GameChanger API.

Handles programmatic token refresh via POST /auth: signs the request using the
gc-signature algorithm, exchanges the refresh token for a short-lived access
token, caches it in memory, and persists the rotated refresh token back to
``.env`` atomically.

For the mobile profile, programmatic refresh requires the client key (embedded
in the iOS binary -- not yet extracted).  As a workaround, callers may provide
a manually-captured access token via the ``access_token`` constructor parameter
(loaded from ``GAMECHANGER_ACCESS_TOKEN_MOBILE`` in ``.env``).

Usage::

    from src.gamechanger.token_manager import TokenManager

    tm = TokenManager(
        profile="web",
        client_id="...",
        client_key="...",
        refresh_token="...",
        device_id="...",
        base_url="https://api.team-manager.gc.com",
    )
    access_token = tm.get_access_token()
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import httpx

from src.gamechanger.exceptions import ConfigurationError, CredentialExpiredError
from src.gamechanger.credential_parser import atomic_merge_env_file
from src.gamechanger.signing import build_signature_headers

logger = logging.getLogger(__name__)

# Default repo-root .env path (two levels up from src/gamechanger/).
_DEFAULT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

# Refresh the access token this many seconds before actual expiry to avoid
# edge-case failures from clock skew or slow requests.
_EXPIRY_SAFETY_MARGIN_SECONDS = 300  # 5 minutes

# POST /auth endpoint path.
_AUTH_PATH = "/auth"

# Profile-specific POST /auth header values.
_PROFILE_HEADERS: dict[str, dict[str, str]] = {
    "web": {
        "Content-Type": "application/json; charset=utf-8",
        "gc-app-name": "web",
        "gc-app-version": "0.0.0",
    },
    "mobile": {
        "Content-Type": "application/vnd.gc.com.post_eden_auth+json; version=1.0.0",
        "gc-app-version": "2026.7.0.0",
    },
}


class AuthSigningError(Exception):
    """Raised when POST /auth returns HTTP 400 (signature rejected by server).

    This indicates a stale timestamp, bad HMAC, or malformed signature -- NOT
    an expired refresh token.  The caller should not retry without regenerating
    the signature.
    """


class TokenManager:
    """Manages the access token lifecycle for GameChanger API calls.

    Obtains short-lived access tokens by exchanging the refresh token via
    POST /auth, caches them in memory, and persists rotated refresh tokens back
    to ``.env`` atomically.

    Args:
        profile: Credential profile -- ``"web"`` or ``"mobile"``.
        client_id: GC client UUID (``gc-client-id`` header; required for web).
        client_key: Base64-encoded HMAC-SHA256 secret key (required for web;
            ``None`` for mobile when client key is unavailable).
        refresh_token: Refresh token JWT (required for web; optional for mobile
            when using the manual access token fallback).
        device_id: Device identifier for ``gc-device-id`` header.
        base_url: API base URL (e.g. ``"https://api.team-manager.gc.com"``).
        access_token: Optional manually-captured access token string.  For
            mobile profile without a client key, this is the only way to
            authenticate -- set via ``GAMECHANGER_ACCESS_TOKEN_MOBILE`` in ``.env``.
        app_name_mobile: Value for ``gc-app-name`` header on mobile profile.
            When ``None``, the header is omitted (iOS app behaviour).
        env_path: Path to the ``.env`` file for refresh-token write-back.
            Defaults to the repo-root ``.env``.

    Raises:
        ConfigurationError: If required credentials are missing for the profile.
    """

    def __init__(
        self,
        *,
        profile: str,
        client_id: str | None = None,
        client_key: str | None = None,
        refresh_token: str | None = None,
        device_id: str,
        base_url: str,
        access_token: str | None = None,
        app_name_mobile: str | None = None,
        env_path: Path | None = None,
    ) -> None:
        self._profile = profile
        self._client_id = client_id
        self._client_key = client_key
        self._refresh_token = refresh_token
        self._device_id = device_id
        self._base_url = base_url.rstrip("/")
        self._access_token: str | None = access_token
        self._access_token_expires_at: int = 0  # Unix timestamp
        self._app_name_mobile = app_name_mobile
        self._env_path = str(env_path or _DEFAULT_ENV_PATH)

        self._validate_credentials()

    def _validate_credentials(self) -> None:
        """Validate that required credentials are present for the profile."""
        if self._client_key is not None:
            # Full programmatic refresh capability -- require web-style credentials.
            missing = []
            if not self._client_id:
                missing.append(f"GAMECHANGER_CLIENT_ID_{self._profile.upper()}")
            if not self._refresh_token:
                missing.append(f"GAMECHANGER_REFRESH_TOKEN_{self._profile.upper()}")
            if missing:
                raise ConfigurationError(
                    f"Missing required credential(s) for {self._profile} profile "
                    f"with signing capability: {', '.join(missing)}. "
                    "Ensure they are set in your .env file."
                )
        elif self._profile == "mobile":
            # Mobile without client key -- only manual access token supported.
            if not self._access_token:
                raise ConfigurationError(
                    "Mobile profile programmatic token refresh requires the client key "
                    f"(GAMECHANGER_CLIENT_KEY_MOBILE), which has not been extracted from "
                    "the iOS binary. As a workaround, capture an access token manually "
                    "from mitmweb and set it as GAMECHANGER_ACCESS_TOKEN_MOBILE in .env."
                )
        else:
            # Web profile without a client key -- cannot sign.
            raise ConfigurationError(
                f"Missing required credential GAMECHANGER_CLIENT_KEY_{self._profile.upper()}. "
                "Ensure it is set in your .env file."
            )

    def get_access_token(self) -> str:
        """Return a valid access token, refreshing if necessary.

        On first call, performs a POST /auth refresh.  On subsequent calls,
        returns the cached token unless it is within ``_EXPIRY_SAFETY_MARGIN_SECONDS``
        of expiry.

        For mobile profile without a client key, returns the manually-provided
        access token without expiry tracking.

        Returns:
            A valid access token JWT string.

        Raises:
            ConfigurationError: If mobile profile has no key and no manual token.
            AuthSigningError: If POST /auth returns HTTP 400 (bad signature).
            CredentialExpiredError: If POST /auth returns HTTP 401 (bad token).
        """
        # Mobile no-key fallback: return manual access token as-is.
        if self._client_key is None:
            assert self._access_token is not None  # validated in __init__
            return self._access_token

        now = int(time.time())
        if self._access_token and now < self._access_token_expires_at - _EXPIRY_SAFETY_MARGIN_SECONDS:
            remaining = self._access_token_expires_at - now
            logger.debug(
                "Access token cached for %s profile, expires in %ds", self._profile, remaining
            )
            return self._access_token

        return self._do_refresh()

    def force_refresh(self) -> str:
        """Unconditionally refresh the access token, bypassing the cache.

        Used by the GameChangerClient for 401 retry logic -- when the server
        rejects the current access token, the client calls this to obtain a
        fresh one before retrying.

        For mobile profile without a client key, programmatic refresh is not
        possible.  Raises ``CredentialExpiredError`` so the caller can surface
        a meaningful message rather than hitting an ``AssertionError`` inside
        ``_do_refresh()``.

        Returns:
            A new valid access token JWT string.

        Raises:
            AuthSigningError: If no client key is available (mobile no-key path),
                or if POST /auth returns HTTP 400 (bad signature).
            CredentialExpiredError: If POST /auth returns HTTP 401 (bad token).
        """
        if self._client_key is None:
            raise AuthSigningError(
                f"Programmatic token refresh is not available for the {self._profile} profile "
                "because the client key has not been configured. "
                f"Capture a fresh access token manually and set "
                f"GAMECHANGER_ACCESS_TOKEN_{self._profile.upper()} in .env."
            )
        logger.debug("Force-refreshing access token for %s profile", self._profile)
        return self._do_refresh()

    def _do_refresh(self) -> str:
        """Perform a POST /auth token refresh and update internal state.

        Returns:
            The new access token JWT string.

        Raises:
            AuthSigningError: On HTTP 400 (signature rejected).
            CredentialExpiredError: On HTTP 401 (refresh token invalid/expired).
        """
        logger.debug("Refreshing access token for %s profile", self._profile)

        body: dict[str, Any] = {"type": "refresh"}
        assert self._client_key is not None
        assert self._client_id is not None
        assert self._refresh_token is not None

        sig_headers = build_signature_headers(
            client_id=self._client_id,
            client_key_b64=self._client_key,
            body=body,
        )

        profile_hdrs = _PROFILE_HEADERS.get(self._profile, _PROFILE_HEADERS["web"])
        headers: dict[str, str] = {
            "Accept": "*/*",
            **profile_hdrs,
            **sig_headers,
            "gc-device-id": self._device_id,
            "gc-token": self._refresh_token,
        }

        # Mobile: optionally include gc-app-name if configured.
        if self._profile == "mobile" and self._app_name_mobile:
            headers["gc-app-name"] = self._app_name_mobile

        url = f"{self._base_url}{_AUTH_PATH}"

        with httpx.Client(timeout=30, trust_env=False) as client:
            response = client.post(url, json=body, headers=headers)

        self._handle_auth_error(response)

        data = response.json()
        new_access_token: str = data["access"]["data"]
        new_access_expires: int = int(data["access"]["expires"])
        new_refresh_token: str = data["refresh"]["data"]

        # Update in-memory state.
        self._access_token = new_access_token
        self._access_token_expires_at = new_access_expires
        self._refresh_token = new_refresh_token

        remaining = new_access_expires - int(time.time())
        logger.debug(
            "Access token refreshed for %s profile, expires in %ds", self._profile, remaining
        )

        # Persist the rotated refresh token back to .env atomically.
        self._persist_refresh_token(new_refresh_token)

        return new_access_token

    def _handle_auth_error(self, response: httpx.Response) -> None:
        """Inspect response status and raise appropriate exceptions on failure.

        Args:
            response: The httpx Response from POST /auth.

        Raises:
            AuthSigningError: On HTTP 400 (signature rejected by server).
            CredentialExpiredError: On HTTP 401 (refresh token invalid/expired).
        """
        if response.status_code == 200:
            return

        if response.status_code == 400:
            server_ts = response.headers.get("gc-timestamp", "(not present)")
            raise AuthSigningError(
                f"POST /auth signature rejected by server (HTTP 400). "
                f"Server gc-timestamp: {server_ts}. "
                "This may indicate clock skew or a stale signature. "
                "Check system clock and regenerate credentials if needed."
            )

        if response.status_code == 401:
            raise CredentialExpiredError(
                "Refresh token rejected by server (HTTP 401). "
                f"The {self._profile} refresh token may be expired or invalid. "
                "Re-capture credentials via the proxy or mitmweb."
            )

        raise CredentialExpiredError(
            f"POST /auth returned unexpected status {response.status_code}. "
            "Check credentials and try again."
        )

    def _persist_refresh_token(self, new_refresh_token: str) -> None:
        """Write the rotated refresh token back to .env atomically.

        Logs a WARNING if the write fails (permission error, disk full, etc.)
        but does NOT raise -- the access token is still valid for ~60 minutes,
        giving the operator time to notice and fix the issue.

        Args:
            new_refresh_token: The new refresh token JWT to persist.
        """
        env_key = f"GAMECHANGER_REFRESH_TOKEN_{self._profile.upper()}"
        try:
            atomic_merge_env_file(self._env_path, {env_key: new_refresh_token})
            logger.debug("Persisted rotated refresh token to %s", self._env_path)
        except OSError as exc:
            logger.warning(
                "Failed to persist rotated refresh token to %s (%s: %s). "
                "The access token is valid for ~60 minutes. "
                "Fix the .env write permissions to avoid credential loss on next expiry.",
                self._env_path,
                type(exc).__name__,
                exc.strerror,
            )
