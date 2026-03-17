#!/usr/bin/env python3
"""Refresh src/http/headers.py from the latest mitmproxy header capture report.

Reads ``proxy/data/current/header-report.json`` (or falls back to
``proxy/data/header-report.json``) and regenerates the BROWSER_HEADERS and
MOBILE_HEADERS dicts in ``src/http/headers.py`` to match captured traffic.

By default (dry-run mode), prints a unified diff of what would change without
writing any files.  Pass ``--apply`` to write the updated file.

Exit codes
----------
0 -- Success (dry-run diff printed, or file written successfully).
1 -- No capture data found.

Usage::

    python scripts/proxy-refresh-headers.py           # dry-run: show diff
    python scripts/proxy-refresh-headers.py --apply   # write updated headers.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to sys.path so ``src`` is importable when run directly.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.http.proxy_refresh import run  # noqa: E402


def main() -> None:
    """Entry point: parse args and run."""
    parser = argparse.ArgumentParser(
        description="Refresh src/http/headers.py from the latest mitmproxy header capture."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the updated headers.py (default: dry-run, print diff only).",
    )
    args = parser.parse_args()

    sys.exit(run(apply=args.apply))


if __name__ == "__main__":
    main()
