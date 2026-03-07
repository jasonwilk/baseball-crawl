#!/usr/bin/env python3
"""Bootstrap pipeline -- validate credentials and run the full crawl + load pipeline.

Thin wrapper around ``src.pipeline.bootstrap``.  Business logic lives in the
src package; this script provides the CLI interface.

Usage::

    python scripts/bootstrap.py                  # full pipeline
    python scripts/bootstrap.py --check-only     # validate only, no crawl/load
    python scripts/bootstrap.py --profile mobile # use mobile header profile
    python scripts/bootstrap.py --dry-run        # preview without API calls or DB writes
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add project root to sys.path so ``src`` is importable when run directly.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.pipeline.bootstrap import run  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s -- %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


def _build_arg_parser() -> argparse.ArgumentParser:
    """Return the argument parser for bootstrap.py."""
    parser = argparse.ArgumentParser(
        description="Validate credentials and run the full crawl + load pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Run credential and team config checks only -- skip crawl and load.",
    )
    parser.add_argument(
        "--profile",
        choices=["web", "mobile"],
        default="web",
        help="HTTP header profile for API requests (default: web).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pass --dry-run through to crawl and load stages (no API calls or DB writes).",
    )
    return parser


def main() -> None:
    """Entry point for ``python scripts/bootstrap.py``."""
    parser = _build_arg_parser()
    args = parser.parse_args()
    sys.exit(run(check_only=args.check_only, profile=args.profile, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
