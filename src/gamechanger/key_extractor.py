"""Extract the GameChanger client key from the public JS bundle.

The ``EDEN_AUTH_CLIENT_KEY`` is embedded in the GC web JavaScript bundle as a
composite value in the format ``clientId:clientKey``.  The bundle URL changes
with each deployment, but the HTML page at ``https://web.gc.com`` always links
to the current bundle via a ``<script>`` tag.

Extraction steps:
1. Fetch the GC homepage HTML.
2. Find the ``<script>`` tag whose ``src`` matches ``static/js/index.*.js``.
3. Fetch the JS bundle.
4. Regex-extract ``EDEN_AUTH_CLIENT_KEY:"<uuid>:<base64-key>"``.
5. Split on the first ``:`` only -- left side is ``client_id`` (UUID), right
   side is ``client_key`` (44-character base64 HMAC-SHA256 secret).

All HTTP requests use a public browser profile (no auth headers, no proxy).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

from src.http.headers import BROWSER_HEADERS

logger = logging.getLogger(__name__)

# --- constants ---------------------------------------------------------------

_GC_HOME_URL = "https://web.gc.com"
_BUNDLE_SRC_PATTERN = re.compile(r'src=["\']([^"\']*static/js/index\.[^"\']+\.js)["\']')
_EDEN_KEY_PATTERN = re.compile(r'EDEN_AUTH_CLIENT_KEY:"([^"]+)"')

# Public-web request headers: no gc-token, no gc-device-id.
# Use a minimal subset of BROWSER_HEADERS that is appropriate for a plain
# HTML/JS fetch (Accept-Language, User-Agent, etc.).
_PUBLIC_HEADERS: dict[str, str] = {
    k: v
    for k, v in BROWSER_HEADERS.items()
    if k.lower()
    not in {
        "sec-fetch-site",
        "sec-fetch-mode",
        "sec-fetch-dest",
        "referer",
    }
}


# --- exceptions --------------------------------------------------------------


class KeyExtractionError(RuntimeError):
    """Raised when the client key cannot be extracted."""


# --- result dataclass --------------------------------------------------------


@dataclass(frozen=True)
class ExtractedKey:
    """Parsed composite ``EDEN_AUTH_CLIENT_KEY`` value.

    Attributes:
        client_id: The UUID portion of the composite key (left of first ``:``)
        client_key: The base64 HMAC-SHA256 secret (right of first ``:``)
        bundle_url: The JS bundle URL the key was extracted from.
    """

    client_id: str
    client_key: str
    bundle_url: str


# --- public API --------------------------------------------------------------


def extract_client_key() -> ExtractedKey:
    """Fetch the GC homepage and extract the current client key from the JS bundle.

    Returns:
        An :class:`ExtractedKey` with ``client_id``, ``client_key``, and the
        ``bundle_url`` used.

    Raises:
        KeyExtractionError: On any network failure, missing bundle URL, or
            missing ``EDEN_AUTH_CLIENT_KEY`` in the bundle.
    """
    with httpx.Client(trust_env=False, follow_redirects=True) as client:
        html = _fetch_homepage(client)
        bundle_url = _find_bundle_url(html)
        bundle_js = _fetch_bundle(client, bundle_url)

    composite = _extract_composite(bundle_js)
    return _parse_composite(composite, bundle_url)


# --- internal helpers --------------------------------------------------------


def _fetch_homepage(client: httpx.Client) -> str:
    """Fetch the GC homepage HTML.

    Args:
        client: An ``httpx.Client`` instance.

    Returns:
        The response body as a string.

    Raises:
        KeyExtractionError: On network error or non-200 response.
    """
    url = _GC_HOME_URL
    try:
        response = client.get(url, headers=_PUBLIC_HEADERS)
    except httpx.HTTPError as exc:
        raise KeyExtractionError(
            f"Network error fetching GC homepage ({url}): {exc}"
        ) from exc

    if response.status_code != 200:
        raise KeyExtractionError(
            f"Failed to fetch GC homepage ({url}): HTTP {response.status_code}"
        )

    logger.debug("Fetched GC homepage: %d bytes", len(response.text))
    return response.text


def _find_bundle_url(html: str) -> str:
    """Find the JS bundle URL in the GC homepage HTML.

    Searches for ``<script>`` tags whose ``src`` matches the
    ``static/js/index.*.js`` pattern.  If multiple matches are found, the first
    is used and a warning is logged.

    Args:
        html: The homepage HTML string.

    Returns:
        The full bundle URL (absolute or relative resolved to ``https://web.gc.com``).

    Raises:
        KeyExtractionError: When no matching ``<script>`` tag is found.
    """
    matches = _BUNDLE_SRC_PATTERN.findall(html)

    if not matches:
        raise KeyExtractionError(
            "Could not find JS bundle URL in GC homepage HTML. "
            "Looked for <script src='...static/js/index.*.js...'>. "
            "The page structure may have changed."
        )

    if len(matches) > 1:
        logger.warning(
            "Multiple JS bundle <script> tags matched; using first match. "
            "Matches: %s",
            matches,
        )

    src = matches[0]

    # Resolve relative URLs against the GC home origin.
    if src.startswith("http://") or src.startswith("https://"):
        bundle_url = src
    elif src.startswith("/"):
        bundle_url = f"{_GC_HOME_URL}{src}"
    else:
        bundle_url = f"{_GC_HOME_URL}/{src}"

    logger.debug("Found JS bundle URL: %s", bundle_url)
    return bundle_url


def _fetch_bundle(client: httpx.Client, bundle_url: str) -> str:
    """Download the JS bundle.

    Args:
        client: An ``httpx.Client`` instance.
        bundle_url: The full URL of the JS bundle.

    Returns:
        The JS bundle content as a string.

    Raises:
        KeyExtractionError: On network error or non-200 response.
    """
    try:
        response = client.get(bundle_url, headers=_PUBLIC_HEADERS)
    except httpx.HTTPError as exc:
        raise KeyExtractionError(
            f"Network error fetching JS bundle ({bundle_url}): {exc}"
        ) from exc

    if response.status_code != 200:
        raise KeyExtractionError(
            f"Failed to fetch JS bundle ({bundle_url}): HTTP {response.status_code}"
        )

    logger.debug("Fetched JS bundle: %d bytes", len(response.text))
    return response.text


def _extract_composite(bundle_js: str) -> str:
    """Find the raw ``EDEN_AUTH_CLIENT_KEY`` composite value in the bundle.

    Args:
        bundle_js: The full JS bundle content.

    Returns:
        The raw ``clientId:clientKey`` composite string.

    Raises:
        KeyExtractionError: When ``EDEN_AUTH_CLIENT_KEY`` is not found.
    """
    match = _EDEN_KEY_PATTERN.search(bundle_js)
    if not match:
        raise KeyExtractionError(
            "EDEN_AUTH_CLIENT_KEY not found in the JS bundle. "
            "The variable name may have changed in a GC deployment."
        )

    composite = match.group(1)
    logger.debug("Found EDEN_AUTH_CLIENT_KEY composite value (length: %d)", len(composite))
    return composite


def _parse_composite(composite: str, bundle_url: str) -> ExtractedKey:
    """Split the composite ``clientId:clientKey`` value.

    Splits on the **first** ``:`` only -- the base64 key may contain ``=``
    padding but not ``:``.

    Args:
        composite: Raw composite string from the bundle.
        bundle_url: Bundle URL (stored in the result for traceability).

    Returns:
        An :class:`ExtractedKey` instance.

    Raises:
        KeyExtractionError: If the composite does not contain a ``:`` separator.
    """
    if ":" not in composite:
        raise KeyExtractionError(
            f"EDEN_AUTH_CLIENT_KEY value does not contain ':' separator: {composite!r}"
        )

    client_id, _, client_key = composite.partition(":")
    return ExtractedKey(
        client_id=client_id,
        client_key=client_key,
        bundle_url=bundle_url,
    )
