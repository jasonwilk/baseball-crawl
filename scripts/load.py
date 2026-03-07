#!/usr/bin/env python3
"""Load orchestrator -- load all raw JSON files into the SQLite database.

Thin wrapper around ``src.pipeline.load``.  Business logic lives in the
src package; this script provides the CLI interface.

Usage::

    python scripts/load.py                        # run all loaders
    python scripts/load.py --dry-run              # preview without touching the DB
    python scripts/load.py --loader roster        # run one loader only
    python scripts/load.py --loader game          # run game loader only
    python scripts/load.py --loader season-stats  # run season-stats loader only

Available loader names: roster, game, season-stats
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

from src.pipeline.load import _LOADER_NAMES, run  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s -- %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


def _build_arg_parser() -> argparse.ArgumentParser:
    """Return the argument parser for load.py."""
    parser = argparse.ArgumentParser(
        description="Load raw GameChanger JSON files into the database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would load without touching the database.",
    )
    parser.add_argument(
        "--loader",
        metavar="NAME",
        choices=_LOADER_NAMES,
        help=f"Run only one loader. Choices: {', '.join(_LOADER_NAMES)}",
    )
    parser.add_argument(
        "--source",
        choices=["yaml", "db"],
        default="yaml",
        help="Config source: 'yaml' (default) reads config/teams.yaml; 'db' reads from SQLite.",
    )
    return parser


def main() -> None:
    """Entry point for ``python scripts/load.py``."""
    parser = _build_arg_parser()
    args = parser.parse_args()
    sys.exit(run(dry_run=args.dry_run, loader_filter=args.loader, source=args.source))


if __name__ == "__main__":
    main()
