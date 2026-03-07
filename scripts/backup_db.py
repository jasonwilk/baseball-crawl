#!/usr/bin/env python3
"""Create a timestamped backup of the SQLite database.

Thin wrapper around ``src.db.backup``.  Business logic lives in the src
package; this script provides the CLI interface.

Usage::

    python scripts/backup_db.py [--db-path PATH]

Options:
    --db-path PATH   Override DATABASE_PATH env var (absolute or relative path).

Environment variables (loaded from .env if present):
    DATABASE_PATH   Path to the SQLite file.  Defaults to ``data/app.db``.
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

# Load .env if python-dotenv is available.
try:
    from dotenv import load_dotenv

    _env_file = _PROJECT_ROOT / ".env"
    if _env_file.exists():
        load_dotenv(_env_file)
except ImportError:
    pass  # dotenv is optional; env vars may be injected directly (Docker)

from src.db.backup import backup_database  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [backup_db] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Create a timestamped backup of the SQLite database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/backup_db.py\n"
            "  python scripts/backup_db.py --db-path /tmp/custom.db\n"
        ),
    )
    parser.add_argument(
        "--db-path",
        metavar="PATH",
        default=None,
        help="Override DATABASE_PATH env var. Accepts absolute or relative paths.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    db_path = Path(args.db_path).resolve() if args.db_path else None

    try:
        result = backup_database(db_path=db_path)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    print(f"Backup saved to {result}")
