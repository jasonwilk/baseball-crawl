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


class MultipleKeysFoundError(RuntimeError):
    """Raised when multiple EDEN_AUTH_CLIENT_KEY entries are found and cannot be disambiguated.

    Attributes:
        candidates: All parsed :class:`ExtractedKey` instances discovered in the bundle.
    """

    def __init__(self, candidates: list[ExtractedKey]) -> None:
        self.candidates = candidates
        super().__init__(
            f"Found {len(candidates)} EDEN_AUTH_CLIENT_KEY entries; "
            "disambiguation required. "
            "Set GAMECHANGER_CLIENT_ID_WEB in .env and re-run."
        )


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


def extract_client_key(known_client_id: str | None = None) -> ExtractedKey:
    """Fetch the GC homepage and extract the current client key from the JS bundle.

    When the bundle contains multiple ``EDEN_AUTH_CLIENT_KEY`` entries (web and
    mobile), ``known_client_id`` is used to select the correct one.  All
    discovered UUIDs are logged at INFO level for auditability.

    Args:
        known_client_id: The expected ``GAMECHANGER_CLIENT_ID_WEB`` value from
            ``.env``.  When provided and a match is found among multiple
            candidates, that key is returned automatically.  When ``None`` and
            multiple candidates exist, :class:`MultipleKeysFoundError` is raised.

    Returns:
        An :class:`ExtractedKey` with ``client_id``, ``client_key``, and the
        ``bundle_url`` used.

    Raises:
        KeyExtractionError: On any network failure, missing bundle URL, or
            missing ``EDEN_AUTH_CLIENT_KEY`` in the bundle.
        MultipleKeysFoundError: When multiple keys are found and ``known_client_id``
            is not set or does not match any candidate.
    """
    with httpx.Client(trust_env=False, follow_redirects=True) as client:
        html = _fetch_homepage(client)
        bundle_url = _find_bundle_url(html)
        bundle_js = _fetch_bundle(client, bundle_url)

    composites = _find_composites(bundle_js)
    candidates = [_parse_composite(c, bundle_url) for c in composites]

    # AC-1: log all discovered UUIDs (never the key material).
    logger.info(
        "Found %d EDEN_AUTH_CLIENT_KEY entry(s) in bundle: %s",
        len(candidates),
        [c.client_id for c in candidates],
    )

    if len(candidates) == 1:
        # AC-4: single match -- unchanged behavior.
        return candidates[0]

    # Multiple matches -- disambiguation required.
    if known_client_id:
        for candidate in candidates:
            if candidate.client_id == known_client_id:
                logger.info(
                    "Selected key matching known client ID %s", known_client_id
                )
                return candidate
        logger.warning(
            "GAMECHANGER_CLIENT_ID_WEB (%s) did not match any discovered key UUID. "
            "Candidates: %s",
            known_client_id,
            [c.client_id for c in candidates],
        )

    # AC-3: no known ID set, or known ID didn't match -- cannot disambiguate.
    raise MultipleKeysFoundError(candidates)


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


def _find_composites(bundle_js: str) -> list[str]:
    """Find all raw ``EDEN_AUTH_CLIENT_KEY`` composite values in the bundle.

    Uses ``findall()`` to capture every occurrence (web and mobile keys may
    both be present in recent GC bundles).

    Args:
        bundle_js: The full JS bundle content.

    Returns:
        A list of raw ``clientId:clientKey`` composite strings (one or more).

    Raises:
        KeyExtractionError: When no ``EDEN_AUTH_CLIENT_KEY`` entry is found.
    """
    matches = _EDEN_KEY_PATTERN.findall(bundle_js)
    if not matches:
        raise KeyExtractionError(
            "EDEN_AUTH_CLIENT_KEY not found in the JS bundle. "
            "The variable name may have changed in a GC deployment."
        )
    logger.debug(
        "Found %d EDEN_AUTH_CLIENT_KEY composite value(s)", len(matches)
    )
    return matches


def _extract_composite(bundle_js: str) -> str:
    """Find the raw ``EDEN_AUTH_CLIENT_KEY`` composite value in the bundle.

    Returns only the **first** match.  Use :func:`_find_composites` when all
    matches are needed (e.g., multi-key disambiguation).

    Args:
        bundle_js: The full JS bundle content.

    Returns:
        The raw ``clientId:clientKey`` composite string.

    Raises:
        KeyExtractionError: When ``EDEN_AUTH_CLIENT_KEY`` is not found.
    """
    return _find_composites(bundle_js)[0]


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
