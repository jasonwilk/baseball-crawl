"""GameChanger credential extraction mitmproxy addon.

Watches proxied traffic for GameChanger authentication headers and writes them
to the project ``.env`` file using ``merge_env_file()``. Only processes traffic
from GameChanger domains; ignores all other hosts. Deduplicates writes so the
``.env`` file is only updated when the token value changes.

Credentials are written to profile-scoped env keys:
  - Web browser traffic  -> ``_WEB``  suffix (e.g. ``GAMECHANGER_REFRESH_TOKEN_WEB``)
  - iOS app traffic      -> ``_MOBILE`` suffix (e.g. ``GAMECHANGER_REFRESH_TOKEN_MOBILE``)
  - Unknown traffic      -> logged as WARNING and dropped (no write)

The ``response()`` handler additionally captures access + refresh tokens from
POST /auth response bodies (``{type: "token", access: {data: "..."}, refresh:
{data: "..."}}``). Only ``type == "token"`` responses are processed; client-auth
responses (``type == "client-token"``) are ignored.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from proxy.addons import gc_filter
from src.gamechanger.credential_parser import _decode_jwt_type, merge_env_file

if TYPE_CHECKING:
    from mitmproxy import http

logger = logging.getLogger(__name__)

# Env file path inside the container (project root mounted at /app).
_ENV_PATH = "/app/.env"

# Base header-to-env-key mapping (without profile suffix).
# The suffix is applied at runtime based on the detected traffic source.
# Note: gc-signature is NOT captured here -- signatures are computed at runtime
# from GAMECHANGER_CLIENT_KEY_* and do not need to be stored.
_BASE_CREDENTIAL_HEADERS: dict[str, str] = {
    "gc-token": "GAMECHANGER_REFRESH_TOKEN",
    "gc-device-id": "GAMECHANGER_DEVICE_ID",
    "gc-app-name": "GAMECHANGER_APP_NAME",
    "gc-client-id": "GAMECHANGER_CLIENT_ID",
}

# Mapping from detect_source() return values to env key suffixes.
# "unknown" maps to None -- credentials are dropped, not written.
_SOURCE_TO_SUFFIX: dict[str, str | None] = {
    "web": "_WEB",
    "ios": "_MOBILE",
    "unknown": None,
}


def _suffix_keys(source: str) -> dict[str, str] | None:
    """Return the header-to-env-key mapping with the profile suffix applied.

    Args:
        source: The traffic source string returned by ``detect_source()``.
            One of ``"web"``, ``"ios"``, or ``"unknown"``.

    Returns:
        A dict mapping HTTP header names to suffixed env key names, or
        ``None`` if the source is ``"unknown"`` (credentials should be dropped).
    """
    suffix = _SOURCE_TO_SUFFIX.get(source)
    if suffix is None:
        return None
    return {header: f"{base_key}{suffix}" for header, base_key in _BASE_CREDENTIAL_HEADERS.items()}


class CredentialExtractor:
    """mitmproxy addon that extracts GameChanger credentials from live traffic.

    Hooks into ``request()`` to inspect headers on every proxied request and
    ``response()`` to capture tokens from POST /auth response bodies.
    Non-GameChanger requests are ignored immediately. When a ``gc-token`` header
    is seen for the first time (or its value changes), all present credential
    headers are written to ``.env`` via ``merge_env_file()``.

    Credentials are written to profile-scoped keys based on the detected
    traffic source: ``_WEB`` for web browser traffic, ``_MOBILE`` for iOS app
    traffic. Unknown traffic sources are logged and dropped.
    """

    def __init__(self) -> None:
        # In-memory cache: suffixed_env_key -> last-written value.
        # Keyed by suffixed names so web and mobile credentials are tracked independently.
        self._cache: dict[str, str] = {}

    def request(self, flow: http.HTTPFlow) -> None:
        """Process each proxied request.

        Ignores non-GameChanger hosts. Detects traffic source and routes
        credentials to profile-scoped env keys. Deduplicates against the
        in-memory cache and writes to ``.env`` when values have changed.
        Unknown traffic sources are logged as WARNING and dropped.

        Args:
            flow: The mitmproxy HTTP flow for this request.
        """
        host = flow.request.host
        if not gc_filter.is_gamechanger_domain(host):
            return

        # Detect traffic source first -- determines which env keys to write.
        user_agent = flow.request.headers.get("user-agent", "")
        source = gc_filter.detect_source(user_agent)

        header_to_env_key = _suffix_keys(source)
        if header_to_env_key is None:
            logger.warning(
                "Unrecognised traffic source (unknown) -- credentials dropped. "
                "User-Agent snippet: %r",
                user_agent[:80],
            )
            return

        # Extract credential headers present in this request using suffixed keys.
        credentials: dict[str, str] = {}
        for header_name, env_key in header_to_env_key.items():
            value = flow.request.headers.get(header_name)
            if not value:
                continue
            # For gc-token, verify it is a refresh token (no 'type' field in payload).
            # Standard API requests carry an access token (type='user'); only POST /auth
            # refresh calls carry a refresh token.  Saving an access token in the refresh
            # slot would cause programmatic refresh to fail.
            if header_name == "gc-token":
                token_type = _decode_jwt_type(value)
                if token_type is not None:
                    logger.warning(
                        "gc-token header contains a %r token, not a refresh token -- skipping %s. "
                        "Only POST /auth requests carry refresh tokens.",
                        token_type,
                        env_key,
                    )
                    continue
            credentials[env_key] = value

        if not credentials:
            return

        # Deduplicate: skip write if nothing has changed.
        if credentials == {k: self._cache.get(k) for k in credentials}:
            return

        # Write updated credentials to .env.
        try:
            merge_env_file(_ENV_PATH, credentials)
        except OSError as exc:
            logger.error("Failed to write credentials to %s: %s", _ENV_PATH, exc)
            return

        # Update cache and log -- never log credential values.
        self._cache.update(credentials)
        written_keys = ", ".join(sorted(credentials.keys()))
        logger.info(
            "Credentials updated from %s source: %s", source, written_keys
        )

    def response(self, flow: http.HTTPFlow) -> None:
        """Process POST /auth responses to capture fresh access and refresh tokens.

        Ignores all responses except POST /auth on GameChanger domains. Parses the
        JSON response body and extracts tokens only when ``type == "token"``
        (the final step of the auth flow). Client-auth responses
        (``type == "client-token"``) and all other shapes are ignored.

        Access token is written to ``GAMECHANGER_ACCESS_TOKEN_{PROFILE}`` and
        refresh token is written to ``GAMECHANGER_REFRESH_TOKEN_{PROFILE}``.

        Args:
            flow: The mitmproxy HTTP flow for this response.
        """
        # Only process POST /auth on GameChanger domains.
        host = flow.request.host
        if not gc_filter.is_gamechanger_domain(host):
            return
        if flow.request.method.upper() != "POST":
            return
        if flow.request.path.rstrip("/") != "/auth":
            return

        # Detect traffic source from request User-Agent (available on response flows too).
        user_agent = flow.request.headers.get("user-agent", "")
        source = gc_filter.detect_source(user_agent)
        suffix = _SOURCE_TO_SUFFIX.get(source)
        if suffix is None:
            logger.warning(
                "POST /auth response from unknown source -- tokens dropped. "
                "User-Agent snippet: %r",
                user_agent[:80],
            )
            return

        # Parse the JSON response body.
        try:
            body = json.loads(flow.response.content)
        except (ValueError, AttributeError):
            logger.warning("POST /auth response body is not valid JSON -- skipping.")
            return

        # Only process type=="token" responses (step 3/4 of auth flow).
        # type=="client-token" (step 2) does not contain user access/refresh tokens.
        if body.get("type") != "token":
            return

        try:
            access_token: str = body["access"]["data"]
            refresh_token: str = body["refresh"]["data"]
        except (KeyError, TypeError):
            logger.warning(
                "POST /auth token response missing expected fields -- skipping."
            )
            return

        credentials: dict[str, str] = {
            f"GAMECHANGER_ACCESS_TOKEN{suffix}": access_token,
            f"GAMECHANGER_REFRESH_TOKEN{suffix}": refresh_token,
        }

        # Deduplicate: skip write if nothing has changed.
        if credentials == {k: self._cache.get(k) for k in credentials}:
            return

        # Write updated credentials to .env.
        try:
            merge_env_file(_ENV_PATH, credentials)
        except OSError as exc:
            logger.error("Failed to write auth response tokens to %s: %s", _ENV_PATH, exc)
            return

        # Update cache and log -- never log credential values.
        self._cache.update(credentials)
        written_keys = ", ".join(sorted(credentials.keys()))
        logger.info(
            "Auth response tokens captured from %s source: %s", source, written_keys
        )
