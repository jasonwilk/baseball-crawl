"""Refresh src/http/headers.py from the latest mitmproxy header capture report.

Reads ``proxy/data/current/header-report.json`` (or falls back to
``proxy/data/header-report.json``) and regenerates the BROWSER_HEADERS and
MOBILE_HEADERS dicts in ``src/http/headers.py`` to match captured traffic.

By default (dry-run mode), prints a unified diff of what would change without
writing any files.  Pass ``apply=True`` to write the updated file.

Exit codes
----------
0 -- Success (dry-run diff printed, or file written successfully).
1 -- No capture data found.
"""

from __future__ import annotations

import difflib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_HEADERS_PATH = _PROJECT_ROOT / "src" / "http" / "headers.py"
_REPORT_PATH_SESSION = _PROJECT_ROOT / "proxy" / "data" / "current" / "header-report.json"
_REPORT_PATH_FLAT = _PROJECT_ROOT / "proxy" / "data" / "header-report.json"

# ---------------------------------------------------------------------------
# Headers to exclude from the update
# ---------------------------------------------------------------------------

# Credential headers -- never written to headers.py
_CREDENTIAL_HEADERS: frozenset[str] = frozenset(
    {
        "gc-token",
        "gc-device-id",
        "gc-signature",
        "gc-app-name",
        "cookie",
    }
)

# Per-request headers -- vary by API call, not fingerprint-relevant
_PER_REQUEST_HEADERS: frozenset[str] = frozenset(
    {
        "content-type",
        "accept",
        "gc-user-action-id",
        "gc-user-action",
        "x-pagination",
    }
)

# Connection-level headers -- not fingerprint-relevant
_CONNECTION_HEADERS: frozenset[str] = frozenset(
    {
        "host",
        "connection",
        "content-length",
        "transfer-encoding",
        "te",
        "trailer",
        "upgrade",
        "proxy-authorization",
        "proxy-authenticate",
    }
)

_EXCLUDED_HEADERS: frozenset[str] = (
    _CREDENTIAL_HEADERS | _PER_REQUEST_HEADERS | _CONNECTION_HEADERS
)


# ---------------------------------------------------------------------------
# Header report loading
# ---------------------------------------------------------------------------


def find_report_path() -> Path | None:
    """Return the first existing report path, or None if neither exists."""
    if _REPORT_PATH_SESSION.exists():
        return _REPORT_PATH_SESSION
    if _REPORT_PATH_FLAT.exists():
        return _REPORT_PATH_FLAT
    return None


def load_report(path: Path) -> dict[str, Any]:
    """Load and return the header report JSON from *path*."""
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Captured header extraction
# ---------------------------------------------------------------------------


def extract_headers_by_source(report: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Extract filtered captured_headers per source from the report.

    Only ``"web"`` and ``"ios"`` sources are returned; ``"unknown"`` is ignored.
    Each header dict has excluded headers removed and keys lowercased.

    Returns:
        Mapping of source name (``"web"`` or ``"ios"``) -> filtered header dict.
    """
    result: dict[str, dict[str, str]] = {}
    for entry in report.get("sources", []):
        source = entry.get("source", "")
        if source not in ("web", "ios"):
            continue
        captured: dict[str, str] = entry.get("captured_headers", {})
        filtered = {
            k: v
            for k, v in captured.items()
            if k.lower() not in _EXCLUDED_HEADERS
        }
        result[source] = filtered
    return result


# ---------------------------------------------------------------------------
# Parse existing headers.py for unchanged dicts
# ---------------------------------------------------------------------------


def parse_existing_headers(headers_text: str) -> dict[str, dict[str, str]]:
    """Parse BROWSER_HEADERS and MOBILE_HEADERS from *headers_text*.

    Uses exec() on the file content (safe -- it is our own file, no user input).

    Returns:
        Dict with keys ``"BROWSER_HEADERS"`` and ``"MOBILE_HEADERS"``.
    """
    namespace: dict[str, Any] = {}
    exec(compile(headers_text, "<headers.py>", "exec"), namespace)  # noqa: S102
    return {
        "BROWSER_HEADERS": namespace.get("BROWSER_HEADERS", {}),
        "MOBILE_HEADERS": namespace.get("MOBILE_HEADERS", {}),
    }


# ---------------------------------------------------------------------------
# File generation
# ---------------------------------------------------------------------------


def _format_header_dict(var_name: str, headers: dict[str, str]) -> str:
    """Format a single header dict as Python source.

    Keys are sorted alphabetically (case-insensitive).  User-Agent values that
    contain a space are split across multiple lines using parenthesised
    concatenation.  All other values are single-line double-quoted strings.
    """
    lines: list[str] = [f"{var_name}: dict[str, str] = {{"]
    for key in sorted(headers.keys(), key=str.lower):
        value = headers[key]
        escaped_key = key.replace('"', '\\"')
        escaped_value = value.replace("\\", "\\\\").replace('"', '\\"')
        # Multi-line for long User-Agent values (split on spaces between tokens)
        if key.lower() == "user-agent" and " " in value:
            # Split at reasonable token boundaries
            parts = _split_user_agent(escaped_value)
            if len(parts) > 1:
                lines.append(f'    "{escaped_key}": (')
                for part in parts:
                    lines.append(f'        "{part} "')
                # Remove the trailing space from the last part
                last = lines[-1]
                lines[-1] = last.rstrip()[:-2] + '"'  # strip trailing space before closing "
                lines.append("    ),")
                continue
        lines.append(f'    "{escaped_key}": "{escaped_value}",')
    lines.append("}")
    return "\n".join(lines)


def _split_user_agent(ua: str) -> list[str]:
    """Split a User-Agent string into logical sub-tokens for multi-line formatting.

    Splits on the spaces between major tokens (e.g., ``Mozilla/5.0 ...``,
    ``AppleWebKit/...``, ``Chrome/...``).  Only splits if the result would span
    multiple lines; short UAs are returned as a single-element list.
    """
    import re

    # Split before known browser token prefixes
    tokens = re.split(r" (?=[A-Z][a-zA-Z]+/)", ua)
    if len(tokens) <= 1:
        return [ua]
    return tokens


def generate_headers_file(
    browser_headers: dict[str, str],
    mobile_headers: dict[str, str],
    source_date: str,
) -> str:
    """Generate the full content of ``src/http/headers.py``.

    Args:
        browser_headers: Headers to write as ``BROWSER_HEADERS``.
        mobile_headers: Headers to write as ``MOBILE_HEADERS``.
        source_date: Date string for the "Source" line in the module docstring.

    Returns:
        The complete file content as a string.
    """
    browser_block = _format_header_dict("BROWSER_HEADERS", browser_headers)
    mobile_block = _format_header_dict("MOBILE_HEADERS", mobile_headers)

    return f'''"""
Dual header profiles for all HTTP requests to GameChanger.

Two profiles are available:

- **BROWSER_HEADERS** (web): Chrome 145 on macOS fingerprint, used by default.
  Matches the header set observed in web browser captures of web.gc.com.
  Source: Real GameChanger API curl commands captured through {source_date}.

- **MOBILE_HEADERS** (mobile): iOS Odyssey app fingerprint.
  Matches the header set observed in mitmproxy capture of the iOS GameChanger
  (Odyssey) app on {source_date}.

Select the profile via ``create_session(profile="web")`` or
``create_session(profile="mobile")`` in ``src.http.session``.

IMPORTANT: Neither profile includes credentials (gc-token, gc-device-id, etc.).
Auth headers are injected by the consuming client (e.g., GameChangerClient).
"""

from __future__ import annotations

{browser_block}

{mobile_block}
'''


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


def run(*, apply: bool) -> int:
    """Execute the header refresh.

    Args:
        apply: If True, write the updated file.  If False, only print the diff.

    Returns:
        Exit code (0 = success, 1 = error).
    """
    report_path = find_report_path()
    if report_path is None:
        print(
            "No capture data found. Run mitmproxy and capture GameChanger traffic first.",
            file=sys.stderr,
        )
        return 1

    report = load_report(report_path)
    captured_by_source = extract_headers_by_source(report)

    # Read existing file to preserve unchanged dicts
    existing_text = _HEADERS_PATH.read_text(encoding="utf-8")
    existing_dicts = parse_existing_headers(existing_text)

    # Determine final header dicts: prefer captured, fall back to existing.
    # When a capture source is present, merge back any _PER_REQUEST_HEADERS keys
    # (e.g., Accept) that existed in the prior dict but were stripped during
    # capture filtering.  This preserves intentionally-set stable values while
    # still filtering volatile per-request headers from the capture.
    def _merge_preserved(
        captured: dict[str, str],
        existing: dict[str, str],
    ) -> dict[str, str]:
        preserved = {
            k: v
            for k, v in existing.items()
            if k.lower() in _PER_REQUEST_HEADERS and k.lower() not in {ck.lower() for ck in captured}
        }
        return {**preserved, **captured}

    if "web" in captured_by_source:
        browser_headers = _merge_preserved(
            captured_by_source["web"], existing_dicts["BROWSER_HEADERS"]
        )
    else:
        browser_headers = existing_dicts["BROWSER_HEADERS"]

    if "ios" in captured_by_source:
        mobile_headers = _merge_preserved(
            captured_by_source["ios"], existing_dicts["MOBILE_HEADERS"]
        )
    else:
        mobile_headers = existing_dicts["MOBILE_HEADERS"]

    today = date.today().isoformat()
    new_text = generate_headers_file(browser_headers, mobile_headers, today)

    if apply:
        _HEADERS_PATH.write_text(new_text, encoding="utf-8")
        sources_updated = []
        if "web" in captured_by_source:
            sources_updated.append("BROWSER_HEADERS (web)")
        if "ios" in captured_by_source:
            sources_updated.append("MOBILE_HEADERS (ios)")
        if sources_updated:
            print(f"Updated: {', '.join(sources_updated)}")
        else:
            print("No web or ios sources in capture -- no dicts updated.")
        print(f"Written: {_HEADERS_PATH}")
    else:
        # Dry-run: show unified diff
        diff_lines = list(
            difflib.unified_diff(
                existing_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile="src/http/headers.py (current)",
                tofile="src/http/headers.py (proposed)",
            )
        )
        if diff_lines:
            print("".join(diff_lines))
        else:
            print("No changes -- headers are already up to date.")

    return 0
