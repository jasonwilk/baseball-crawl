"""GameChanger credential extraction mitmproxy addon.

Watches proxied traffic for GameChanger authentication headers and writes them
to the project ``.env`` file using ``merge_env_file()``. Only processes traffic
from GameChanger domains; ignores all other hosts. Deduplicates writes so the
``.env`` file is only updated when the token value changes.

Credentials are written to profile-scoped env keys:
  - Web browser traffic  -> ``_WEB``  suffix (e.g. ``GAMECHANGER_AUTH_TOKEN_WEB``)
  - iOS app traffic      -> ``_MOBILE`` suffix (e.g. ``GAMECHANGER_AUTH_TOKEN_MOBILE``)
  - Unknown traffic      -> logged as WARNING and dropped (no write)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from proxy.addons import gc_filter
from src.gamechanger.credential_parser import merge_env_file

if TYPE_CHECKING:
    from mitmproxy import http

logger = logging.getLogger(__name__)

# Env file path inside the container (project root mounted at /app).
_ENV_PATH = "/app/.env"

# Base header-to-env-key mapping (without profile suffix).
# The suffix is applied at runtime based on the detected traffic source.
_BASE_CREDENTIAL_HEADERS: dict[str, str] = {
    "gc-token": "GAMECHANGER_AUTH_TOKEN",
    "gc-device-id": "GAMECHANGER_DEVICE_ID",
    "gc-app-name": "GAMECHANGER_APP_NAME",
    "gc-signature": "GAMECHANGER_SIGNATURE",
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

    Hooks into ``request()`` to inspect headers on every proxied request.
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
            if value:
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
