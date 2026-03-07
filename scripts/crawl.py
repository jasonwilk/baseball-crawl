#!/usr/bin/env python3
"""Crawl orchestrator -- refresh all raw data from the GameChanger API.

Thin wrapper around ``src.pipeline.crawl``.  Business logic lives in the
src package; this script provides the CLI interface.

Usage::

    python scripts/crawl.py                     # run all crawlers
    python scripts/crawl.py --dry-run           # preview without API calls
    python scripts/crawl.py --crawler roster    # run one crawler only

Available crawler names: roster, schedule, opponent, player-stats, game-stats
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

from src.pipeline.crawl import _CRAWLER_NAMES, run  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s -- %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


def _build_arg_parser() -> argparse.ArgumentParser:
    """Return the argument parser for crawl.py."""
    parser = argparse.ArgumentParser(
        description="Refresh all raw GameChanger data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would run without making API calls or writing files.",
    )
    parser.add_argument(
        "--crawler",
        metavar="NAME",
        choices=_CRAWLER_NAMES,
        help=f"Run only one crawler. Choices: {', '.join(_CRAWLER_NAMES)}",
    )
    parser.add_argument(
        "--source",
        choices=["yaml", "db"],
        default="yaml",
        help="Config source: 'yaml' (default) reads config/teams.yaml; 'db' reads from SQLite.",
    )
    return parser


def main() -> None:
    """Entry point for ``python scripts/crawl.py``."""
    parser = _build_arg_parser()
    args = parser.parse_args()
    sys.exit(run(dry_run=args.dry_run, crawler_filter=args.crawler, source=args.source))


if __name__ == "__main__":
    main()
