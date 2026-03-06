"""mitmproxy addon: capture GameChanger request headers and generate a parity report.

For each GameChanger request, this addon captures the full header set (minus
credential headers), groups headers by traffic source (ios/web/unknown), and
writes a JSON parity report comparing captured headers against the project's
canonical header dicts in ``src.http.headers``.

Each source is diffed against the correct canonical dict:
  - ``"web"`` -> ``BROWSER_HEADERS``
  - ``"ios"`` -> ``MOBILE_HEADERS``
  - ``"unknown"`` -> ``BROWSER_HEADERS`` (best guess)

The report is written to the session directory (or ``proxy/data/`` as fallback)
and is overwritten on each update (first-seen-wins aggregated snapshot per source).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure the project root is on sys.path so we can import from src/
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from proxy.addons.gc_filter import detect_source, is_gamechanger_domain
from src.http.headers import BROWSER_HEADERS, MOBILE_HEADERS

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

# Fallback path used when PROXY_SESSION_DIR is not set.
_REPORT_PATH = Path("/app/proxy/data/header-report.json")


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
    canonical_by_source: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Build the full parity report dict from per-source captured headers.

    Each source is diffed against the correct canonical dict:
    - ``"web"`` -> ``BROWSER_HEADERS``
    - ``"ios"`` -> ``MOBILE_HEADERS``
    - ``"unknown"`` -> ``BROWSER_HEADERS`` (best guess)

    Args:
        captured_by_source: Mapping of source name -> latest captured headers dict.
        canonical_by_source: Mapping of source name -> canonical dict to diff against.
            Must include at least the sources present in ``captured_by_source``.
            Unknown sources fall back to ``BROWSER_HEADERS``.

    Returns:
        Report dict with ``generated_at`` and ``sources`` list.
    """
    fallback = canonical_by_source.get("web", BROWSER_HEADERS)
    sources: list[dict[str, Any]] = []
    for source, captured in captured_by_source.items():
        canonical = canonical_by_source.get(source, fallback)
        diff = compute_header_diff(captured, canonical)
        sources.append(
            {
                "source": source,
                "captured_headers": captured,
                "browser_headers": canonical,
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

    Aggregates headers across multiple requests per traffic source using a
    first-seen-wins strategy: new keys are added to the captured set, but
    existing keys retain their first-seen value. Conflicting values (same key,
    different value in a later request) are logged at WARNING level. The parity
    report is rewritten to disk after each GameChanger request.
    """

    def __init__(self) -> None:
        # source -> latest captured headers (credential headers excluded)
        self._captured_by_source: dict[str, dict[str, str]] = {}

        session_dir = os.environ.get("PROXY_SESSION_DIR")
        if session_dir:
            self.report_path = Path(session_dir) / "header-report.json"
        else:
            self.report_path = _REPORT_PATH

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

        # Merge into existing capture for this source (first-seen-wins per key)
        if source not in self._captured_by_source:
            self._captured_by_source[source] = headers
        else:
            existing = self._captured_by_source[source]
            for key, value in headers.items():
                if key not in existing:
                    existing[key] = value
                elif existing[key] != value:
                    log.warning(
                        "header_capture: conflict for source=%s key=%r: "
                        "keeping %r, ignoring %r",
                        source, key, existing[key], value,
                    )
        log.debug("header_capture: recorded %d headers from source=%s", len(headers), source)

        self._write_report()

    def _write_report(self) -> None:
        """Generate and write the parity report JSON to disk."""
        canonical_by_source = {
            "web": BROWSER_HEADERS,
            "ios": MOBILE_HEADERS,
            "unknown": BROWSER_HEADERS,
        }
        report = build_report(self._captured_by_source, canonical_by_source)

        try:
            self.report_path.parent.mkdir(parents=True, exist_ok=True)
            self.report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            log.debug("header_capture: wrote report to %s", self.report_path)
        except OSError:
            log.exception("header_capture: failed to write report to %s", self.report_path)


addons = [HeaderCapture()]
