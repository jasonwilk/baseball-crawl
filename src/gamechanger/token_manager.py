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
    access_token = tm.get_access_token()  # pii-ok
"""

from __future__ import annotations

import logging
import secrets
import time
from pathlib import Path
from typing import Any

import httpx

from src.gamechanger.exceptions import ConfigurationError, CredentialExpiredError, LoginFailedError
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
        device_id: str | None = None,
        base_url: str,
        access_token: str | None = None,
        app_name_mobile: str | None = None,
        env_path: Path | None = None,
        email: str | None = None,
        password: str | None = None,
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
        self._email = email
        self._password = password

        self._validate_credentials()

    def _validate_credentials(self) -> None:
        """Validate that required credentials are present for the profile."""
        if self._client_key is not None:
            # Full programmatic refresh capability -- require web-style credentials.
            missing = []
            if not self._client_id:
                missing.append(f"GAMECHANGER_CLIENT_ID_{self._profile.upper()}")
            # refresh_token is optional for web profile when email+password are provided (login bootstrap).
            if not self._refresh_token and not (self._profile == "web" and self._email and self._password):
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

        return self._do_refresh(allow_login_fallback=True)

    def force_refresh(self, allow_login_fallback: bool = False) -> str:
        """Unconditionally refresh the access token, bypassing the cache.

        Used by the GameChangerClient for 401 retry logic -- when the server
        rejects the current access token, the client calls this to obtain a
        fresh one before retrying.

        For mobile profile without a client key, programmatic refresh is not
        possible.  Raises ``CredentialExpiredError`` so the caller can surface
        a meaningful message rather than hitting an ``AssertionError`` inside
        ``_do_refresh()``.

        Args:
            allow_login_fallback: When True and the profile is web, a HTTP 401
                response (expired refresh token) triggers the 3-step login flow
                if email/password are configured.  Defaults to False for the
                GameChangerClient 401-retry path; set True from the CLI refresh
                command so an expired refresh token auto-recovers via login.

        Returns:
            A new valid access token JWT string.

        Raises:
            AuthSigningError: If no client key is available (mobile no-key path),
                or if POST /auth returns HTTP 400 (bad signature).
            CredentialExpiredError: If POST /auth returns HTTP 401 (bad token)
                and login fallback is disabled or credentials are absent.
            LoginFailedError: If login fallback is attempted but any step fails.
        """
        if self._client_key is None:
            raise AuthSigningError(
                f"Programmatic token refresh is not available for the {self._profile} profile "
                "because the client key has not been configured. "
                f"Capture a fresh access token manually and set "
                f"GAMECHANGER_ACCESS_TOKEN_{self._profile.upper()} in .env."
            )
        logger.debug("Force-refreshing access token for %s profile", self._profile)
        return self._do_refresh(allow_login_fallback=allow_login_fallback)

    def _do_refresh(self, allow_login_fallback: bool = False) -> str:
        """Perform a POST /auth token refresh and update internal state.

        Args:
            allow_login_fallback: When True and the profile is web, a HTTP 401
                response triggers the 3-step login flow if email/password are
                configured.  When False (``force_refresh`` path), 401 raises
                ``CredentialExpiredError`` without attempting login.

        Returns:
            The new access token JWT string.

        Raises:
            AuthSigningError: On HTTP 400 (signature rejected).
            CredentialExpiredError: On HTTP 401 without login fallback capability.
            LoginFailedError: If login fallback is attempted but any step fails.
        """
        logger.debug("Refreshing access token for %s profile", self._profile)
        response = self._post_refresh_request()

        if response.status_code == 401 and allow_login_fallback and self._profile == "web":
            return self._handle_401_with_fallback()

        self._handle_auth_error(response)
        return self._apply_refresh_response(response)

    def _post_refresh_request(self) -> httpx.Response:
        """Build and POST the refresh request to POST /auth.

        Returns:
            The raw httpx Response from POST /auth.
        """
        body: dict[str, Any] = {"type": "refresh"}
        assert self._client_key is not None
        assert self._client_id is not None
        assert self._refresh_token is not None
        assert self._device_id is not None, (
            f"device_id is required for token refresh ({self._profile} profile) "
            f"but was not provided. Set GAMECHANGER_DEVICE_ID_{self._profile.upper()} in .env."
        )

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
        if self._profile == "mobile" and self._app_name_mobile:
            headers["gc-app-name"] = self._app_name_mobile

        url = f"{self._base_url}{_AUTH_PATH}"
        with httpx.Client(timeout=30, trust_env=False) as client:
            return client.post(url, json=body, headers=headers)

    def _handle_401_with_fallback(self) -> str:
        """Handle a 401 on refresh by attempting the login fallback flow.

        Returns:
            New access token from the login flow.

        Raises:
            CredentialExpiredError: If email/password are not configured.
            LoginFailedError: If the login flow fails.
        """
        if self._email and self._password:
            logger.info("Refresh token expired (HTTP 401); attempting login fallback")
            return self._do_login_fallback()
        raise CredentialExpiredError(
            "Refresh token expired (HTTP 401). "
            "Auto-recovery requires GAMECHANGER_USER_EMAIL and "
            "GAMECHANGER_USER_PASSWORD in .env. "
            "Set login credentials for automatic recovery, or re-import: bb creds import"
        )

    def _apply_refresh_response(self, response: httpx.Response) -> str:
        """Extract tokens from a successful refresh response and persist state.

        Args:
            response: A 200 OK response from POST /auth.

        Returns:
            The new access token JWT string.
        """
        data = response.json()
        new_access_token: str = data["access"]["data"]
        new_access_expires: int = int(data["access"]["expires"])
        new_refresh_token: str = data["refresh"]["data"]

        self._access_token = new_access_token  # pii-ok
        self._access_token_expires_at = new_access_expires
        self._refresh_token = new_refresh_token

        remaining = new_access_expires - int(time.time())
        logger.debug(
            "Access token refreshed for %s profile, expires in %ds", self._profile, remaining
        )
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
                "Possible causes: clock skew, or stale client key (GAMECHANGER_CLIENT_KEY_WEB). "
                "Run `bb creds check --profile web` to validate the client key. "
                "Also check your system clock if skew is suspected."
            )

        if response.status_code == 401:
            raise CredentialExpiredError(
                "Refresh token rejected by server (HTTP 401). "
                f"The {self._profile} refresh token may be expired or invalid. "
                "If this persists after re-importing credentials, the client key "
                "(GAMECHANGER_CLIENT_KEY_WEB) may be stale -- "
                "run `bb creds check --profile web`."
            )

        raise CredentialExpiredError(
            f"POST /auth returned unexpected status {response.status_code}. "
            "Check credentials and try again."
        )

    def _extract_chain_sig(self, response: httpx.Response, step_name: str) -> str | None:
        """Extract the HMAC part of the gc-signature response header for chaining.

        Args:
            response: The httpx Response from a POST /auth step.
            step_name: Step name for warning message (e.g., ``"client-auth"``).

        Returns:
            The HMAC part (after the dot) for use as ``previous_signature_b64``,
            or ``None`` if the header is absent.
        """
        sig = response.headers.get("gc-signature")
        if sig is None:
            logger.warning(
                "gc-signature response header absent after login step %s; "
                "signature chaining contract may have changed",
                step_name,
            )
            return None
        return sig.split(".", 1)[1] if "." in sig else sig

    def _check_login_step_status(
        self, response: httpx.Response, step_num: int, step_name: str
    ) -> None:
        """Raise appropriate errors for a failed login step.

        Args:
            response: The httpx Response from a POST /auth step.
            step_num: Step number (2, 3, or 4) for error messages.
            step_name: Step name (e.g., ``"client-auth"``) for error messages.

        Raises:
            AuthSigningError: If status is 400 (clock skew or bad signature).
            LoginFailedError: If status is non-200 (and not 400).
        """
        if response.status_code == 400:
            server_ts = response.headers.get("gc-timestamp", "(not present)")
            raise AuthSigningError(
                f"Login step {step_num} ({step_name}) signature rejected (HTTP 400). "
                f"Server gc-timestamp: {server_ts}. "
                "Possible causes: clock skew, or stale client key (GAMECHANGER_CLIENT_KEY_WEB). "
                "Run `bb creds check --profile web` to validate the client key."
            )
        if response.status_code != 200:
            raise LoginFailedError(
                f"Login step {step_num} ({step_name}) failed with HTTP {response.status_code}. "
                "Check email/password in .env."
            )

    def _validate_client_auth_response(self, data: dict[str, Any]) -> str:
        """Validate step 2 response shape and extract the client token.

        Args:
            data: Parsed JSON body from the step 2 POST /auth response.

        Returns:
            The client token string.

        Raises:
            LoginFailedError: If type is not ``"client-token"`` or token is absent.
        """
        if data.get("type") != "client-token":
            logger.error(
                "Login step 2 returned unexpected response type %r (expected 'client-token'). "
                "Response keys: %s",
                data.get("type"),
                list(data.keys()),
            )
            raise LoginFailedError(
                f"Login step 2 response has unexpected type {data.get('type')!r} "
                "(expected 'client-token'). Check email/password in .env."
            )
        client_token = data.get("token")
        if client_token is None:
            logger.error(
                "Login step 2 response missing 'token' field. Response keys: %s",
                list(data.keys()),
            )
            raise LoginFailedError(
                "Login step 2 response missing 'token' field "
                "(type was 'client-token' but no token value returned). "
                "Check email/password in .env."
            )
        return client_token

    def _login_step2_client_auth(
        self,
        client: httpx.Client,
        url: str,
        profile_hdrs: dict[str, str],
    ) -> tuple[str, str | None]:
        """POST /auth step 2: establish anonymous client session (no gc-token).

        Args:
            client: Shared httpx.Client for the login chain.
            url: Full POST /auth URL.
            profile_hdrs: Profile-specific Content-Type and app headers.

        Returns:
            Tuple of ``(client_token, previous_signature_b64_or_none)``.

        Raises:
            AuthSigningError: On HTTP 400 (clock skew).
            LoginFailedError: On non-200 or unexpected response shape.
        """
        assert self._client_id is not None
        assert self._client_key is not None
        body: dict[str, Any] = {"type": "client-auth", "client_id": self._client_id}
        sig = build_signature_headers(
            client_id=self._client_id,
            client_key_b64=self._client_key,
            body=body,
            # No previous_signature_b64 (usePreviousSignature: false)
        )
        headers: dict[str, str] = {"Accept": "*/*", **profile_hdrs, **sig, "gc-device-id": self._device_id}
        response = client.post(url, json=body, headers=headers)
        self._check_login_step_status(response, step_num=2, step_name="client-auth")
        client_token = self._validate_client_auth_response(response.json())
        return client_token, self._extract_chain_sig(response, step_name="client-auth")

    def _login_step3_user_auth(
        self,
        client: httpx.Client,
        url: str,
        profile_hdrs: dict[str, str],
        client_token: str,
        prev_sig: str | None,
    ) -> str | None:
        """POST /auth step 3: identify user by email (uses client token from step 2).

        Args:
            client: Shared httpx.Client.
            url: Full POST /auth URL.
            profile_hdrs: Profile-specific headers.
            client_token: Client token returned by step 2.
            prev_sig: gc-signature HMAC from step 2 for chaining.

        Returns:
            gc-signature HMAC from this response for chaining to step 4.

        Raises:
            AuthSigningError: On HTTP 400.
            LoginFailedError: On non-200.
        """
        assert self._client_id is not None
        assert self._client_key is not None
        assert self._email is not None
        body: dict[str, Any] = {"type": "user-auth", "email": self._email}
        sig = build_signature_headers(
            client_id=self._client_id,
            client_key_b64=self._client_key,
            body=body,
            previous_signature_b64=prev_sig,
        )
        headers: dict[str, str] = {
            "Accept": "*/*", **profile_hdrs, **sig,
            "gc-device-id": self._device_id, "gc-token": client_token,
        }
        response = client.post(url, json=body, headers=headers)
        self._check_login_step_status(response, step_num=3, step_name="user-auth")
        return self._extract_chain_sig(response, step_name="user-auth")

    def _login_step4_password(
        self,
        client: httpx.Client,
        url: str,
        profile_hdrs: dict[str, str],
        client_token: str,
        prev_sig: str | None,
    ) -> tuple[str, int, str]:
        """POST /auth step 4: authenticate with password; returns tokens.

        Args:
            client: Shared httpx.Client.
            url: Full POST /auth URL.
            profile_hdrs: Profile-specific headers.
            client_token: Client token from step 2 (same token used for step 3).
            prev_sig: gc-signature HMAC from step 3 for chaining.

        Returns:
            Tuple of ``(access_token, access_expires_unix, refresh_token)``.

        Raises:
            AuthSigningError: On HTTP 400.
            LoginFailedError: On non-200.
        """
        assert self._client_id is not None
        assert self._client_key is not None
        assert self._password is not None
        body: dict[str, Any] = {"type": "password", "password": self._password}
        sig = build_signature_headers(
            client_id=self._client_id,
            client_key_b64=self._client_key,
            body=body,
            previous_signature_b64=prev_sig,
        )
        headers: dict[str, str] = {
            "Accept": "*/*", **profile_hdrs, **sig,
            "gc-device-id": self._device_id, "gc-token": client_token,
        }
        response = client.post(url, json=body, headers=headers)
        self._check_login_step_status(response, step_num=4, step_name="password")
        self._extract_chain_sig(response, step_name="password")  # warn if absent
        data = response.json()
        return data["access"]["data"], int(data["access"]["expires"]), data["refresh"]["data"]

    def _do_login_fallback(self) -> str:
        """Execute the 3-step login flow (steps 2-4) as fallback for an expired refresh token.

        Delegates each step to a dedicated helper.  Called when ``_do_refresh()``
        receives HTTP 401 and email/password are configured (web profile only).

        Returns:
            New access token JWT string.

        Raises:
            AuthSigningError: If any step returns 400 (clock skew).
            LoginFailedError: If any step returns non-200 or step 2 shape is wrong.
        """
        logger.info("Attempting 3-step login fallback for %s profile", self._profile)
        assert self._client_key is not None
        assert self._client_id is not None
        assert self._email is not None
        assert self._password is not None

        profile_hdrs = _PROFILE_HEADERS.get(self._profile, _PROFILE_HEADERS["web"])
        url = f"{self._base_url}{_AUTH_PATH}"

        with httpx.Client(timeout=30, trust_env=False) as client:
            client_token, prev_sig2 = self._login_step2_client_auth(client, url, profile_hdrs)
            prev_sig3 = self._login_step3_user_auth(client, url, profile_hdrs, client_token, prev_sig2)
            new_access_token, new_access_expires, new_refresh_token = self._login_step4_password(
                client, url, profile_hdrs, client_token, prev_sig3
            )

        self._access_token = new_access_token  # pii-ok
        self._access_token_expires_at = new_access_expires
        self._refresh_token = new_refresh_token

        remaining = new_access_expires - int(time.time())
        logger.info(
            "Login fallback succeeded for %s profile, access token expires in %ds",
            self._profile,
            remaining,
        )
        self._persist_refresh_token(new_refresh_token)
        return new_access_token

    def do_login(self) -> str:
        """Execute the 3-step login flow directly as the primary bootstrap path.

        Called by the CLI when no refresh token exists but email + password are
        configured.  If ``device_id`` was not provided at construction time, a
        synthetic 32-char hex value is generated via ``secrets.token_hex(16)``
        and persisted to ``.env`` before the login flow runs.

        Returns:
            New access token JWT string (refresh token is also persisted to
            ``.env`` via ``_do_login_fallback``).

        Raises:
            ConfigurationError: If email or password are not configured.
            AuthSigningError: If any login step returns HTTP 400.
            LoginFailedError: If any login step fails.
        """
        if not self._email or not self._password:
            raise ConfigurationError(
                "Login bootstrap requires GAMECHANGER_USER_EMAIL and "
                "GAMECHANGER_USER_PASSWORD in .env."
            )

        if not self._device_id:
            new_device_id = secrets.token_hex(16)
            self._device_id = new_device_id
            logger.info("Generated synthetic device ID for %s profile", self._profile)
            env_key = f"GAMECHANGER_DEVICE_ID_{self._profile.upper()}"
            try:
                atomic_merge_env_file(self._env_path, {env_key: new_device_id})
                logger.debug("Persisted synthetic device ID to %s", self._env_path)
            except OSError as exc:
                logger.warning(
                    "Failed to persist synthetic device ID to %s (%s: %s). "
                    "Login will proceed but device ID will not be saved for next run.",
                    self._env_path,
                    type(exc).__name__,
                    exc.strerror,
                )

        logger.info("Running login bootstrap flow for %s profile", self._profile)
        return self._do_login_fallback()

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
