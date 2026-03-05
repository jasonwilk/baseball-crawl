"""mitmproxy addon: capture GameChanger request headers and generate a parity report.

For each GameChanger request, this addon captures the full header set (minus
credential headers), groups headers by traffic source (ios/web/unknown), and
writes a JSON parity report comparing captured headers against the project's
canonical ``BROWSER_HEADERS`` in ``src.http.headers``.

The report is written to ``/app/data/mitmproxy/header-report.json`` and is
overwritten on each update (latest snapshot only).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure the project root is on sys.path so we can import from src/
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from proxy.addons.gc_filter import detect_source, is_gamechanger_domain
from src.http.headers import BROWSER_HEADERS

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Credential headers excluded from capture (handled by credential_extractor)
_CREDENTIAL_HEADERS: frozenset[str] = frozenset(
    {
        "gc-token",
        "gc-device-id",
        "gc-signature",
        "gc-app-name",
        "cookie",
    }
)

# Per-request / connection-level headers that vary per call and are not
# fingerprint-relevant -- excluded from the parity diff.
_SKIP_DIFF_HEADERS: frozenset[str] = frozenset(
    {
        "content-length",
        "host",
        "connection",
        "transfer-encoding",
        "te",
        "trailer",
        "upgrade",
        "proxy-authorization",
        "proxy-authenticate",
    }
)

_REPORT_PATH = Path("/app/data/mitmproxy/header-report.json")


# ---------------------------------------------------------------------------
# Pure diff logic (unit-testable, no mitmproxy dependency)
# ---------------------------------------------------------------------------


def compute_header_diff(
    captured: dict[str, str],
    canonical: dict[str, str],
    *,
    skip: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Compute a three-way diff between *captured* and *canonical* header dicts.

    Headers in *skip* (lower-cased) are excluded from the diff computation.

    Returns a dict with keys:
      - ``missing_in_captured``: list of keys present in canonical but not in captured
      - ``extra_in_captured``: list of keys present in captured but not in canonical
      - ``value_differences``: list of ``{"key", "captured", "canonical"}`` dicts
        for keys present in both but with differing values

    Comparisons are case-insensitive on the *key* side (normalise to lower-case),
    but values are compared exactly as provided.
    """
    if skip is None:
        skip = _SKIP_DIFF_HEADERS

    def _normalise(headers: dict[str, str]) -> dict[str, str]:
        """Return a lower-cased-key copy, excluding skipped keys."""
        return {k.lower(): v for k, v in headers.items() if k.lower() not in skip}

    norm_captured = _normalise(captured)
    norm_canonical = _normalise(canonical)

    captured_keys = set(norm_captured)
    canonical_keys = set(norm_canonical)

    missing_in_captured = sorted(canonical_keys - captured_keys)
    extra_in_captured = sorted(captured_keys - canonical_keys)
    value_differences = [
        {
            "key": key,
            "captured": norm_captured[key],
            "canonical": norm_canonical[key],
        }
        for key in sorted(captured_keys & canonical_keys)
        if norm_captured[key] != norm_canonical[key]
    ]

    return {
        "missing_in_captured": missing_in_captured,
        "extra_in_captured": extra_in_captured,
        "value_differences": value_differences,
    }


def build_report(
    captured_by_source: dict[str, dict[str, str]],
    browser_headers: dict[str, str],
) -> dict[str, Any]:
    """Build the full parity report dict from per-source captured headers.

    Args:
        captured_by_source: Mapping of source name -> latest captured headers dict.
        browser_headers: The canonical BROWSER_HEADERS to diff against.

    Returns:
        Report dict matching the AC-3 JSON schema.
    """
    sources: list[dict[str, Any]] = []
    for source, captured in captured_by_source.items():
        diff = compute_header_diff(captured, browser_headers)
        sources.append(
            {
                "source": source,
                "captured_headers": captured,
                "browser_headers": browser_headers,
                "missing_in_captured": diff["missing_in_captured"],
                "extra_in_captured": diff["extra_in_captured"],
                "value_differences": diff["value_differences"],
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
    }


# ---------------------------------------------------------------------------
# mitmproxy addon class
# ---------------------------------------------------------------------------


class HeaderCapture:
    """mitmproxy addon that captures GameChanger request headers per source.

    Stores the *latest* seen header set per traffic source and rewrites the
    parity report to disk after each GameChanger request.
    """

    def __init__(self) -> None:
        # source -> latest captured headers (credential headers excluded)
        self._captured_by_source: dict[str, dict[str, str]] = {}

    def request(self, flow: Any) -> None:  # noqa: ANN401
        """Hook called by mitmproxy for every client request."""
        host = flow.request.pretty_host
        if not is_gamechanger_domain(host):
            return

        user_agent: str = flow.request.headers.get("user-agent", "")
        source = detect_source(user_agent)

        # Build header dict, excluding credential headers (case-insensitive key match)
        headers: dict[str, str] = {
            name: value
            for name, value in flow.request.headers.items()
            if name.lower() not in _CREDENTIAL_HEADERS
        }

        # Overwrite previous capture for this source (latest snapshot)
        self._captured_by_source[source] = headers
        log.debug("header_capture: recorded %d headers from source=%s", len(headers), source)

        self._write_report()

    def _write_report(self) -> None:
        """Generate and write the parity report JSON to disk."""
        report = build_report(self._captured_by_source, BROWSER_HEADERS)

        try:
            _REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
            _REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
            log.debug("header_capture: wrote report to %s", _REPORT_PATH)
        except OSError:
            log.exception("header_capture: failed to write report to %s", _REPORT_PATH)


addons = [HeaderCapture()]
