"""GameChanger credential extraction mitmproxy addon.

Watches proxied traffic for GameChanger authentication headers and writes them
to the project ``.env`` file using ``merge_env_file()``. Only processes traffic
from GameChanger domains; ignores all other hosts. Deduplicates writes so the
``.env`` file is only updated when the token value changes.
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

# Headers that carry persistent credentials and the .env key to store them under.
# Extends credential_parser._CREDENTIAL_HEADERS with gc-signature.
_CREDENTIAL_HEADERS: dict[str, str] = {
    "gc-token": "GAMECHANGER_AUTH_TOKEN",
    "gc-device-id": "GAMECHANGER_DEVICE_ID",
    "gc-app-name": "GAMECHANGER_APP_NAME",
    "gc-signature": "GAMECHANGER_SIGNATURE",
}


class CredentialExtractor:
    """mitmproxy addon that extracts GameChanger credentials from live traffic.

    Hooks into ``request()`` to inspect headers on every proxied request.
    Non-GameChanger requests are ignored immediately. When a ``gc-token`` header
    is seen for the first time (or its value changes), all present credential
    headers are written to ``.env`` via ``merge_env_file()``.
    """

    def __init__(self) -> None:
        # In-memory cache: env_key -> last-written value.
        # Used to skip redundant .env writes.
        self._cache: dict[str, str] = {}

    def request(self, flow: http.HTTPFlow) -> None:
        """Process each proxied request.

        Ignores non-GameChanger hosts. Extracts credential headers when present,
        deduplicates against the in-memory cache, and writes to ``.env`` when
        the token value has changed.

        Args:
            flow: The mitmproxy HTTP flow for this request.
        """
        host = flow.request.host
        if not gc_filter.is_gamechanger_domain(host):
            return

        # Extract credential headers present in this request.
        credentials: dict[str, str] = {}
        for header_name, env_key in _CREDENTIAL_HEADERS.items():
            value = flow.request.headers.get(header_name)
            if value:
                credentials[env_key] = value

        if not credentials:
            return

        # Deduplicate: skip write if nothing has changed.
        if credentials == {k: self._cache.get(k) for k in credentials}:
            return

        # Detect traffic source for logging.
        user_agent = flow.request.headers.get("user-agent", "")
        source = gc_filter.detect_source(user_agent)

        # Write updated credentials to .env.
        try:
            merge_env_file(_ENV_PATH, credentials)
        except OSError as exc:
            logger.error("Failed to write credentials to %s: %s", _ENV_PATH, exc)
            return

        # Update cache and log -- never log values.
        self._cache.update(credentials)
        written_keys = ", ".join(sorted(credentials.keys()))
        logger.info(
            "Credentials updated from %s source: %s", source, written_keys
        )
