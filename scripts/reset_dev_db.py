#!/usr/bin/env python3
"""Drop and recreate the development database, then load seed data.

Thin wrapper around ``src.db.reset``.  Business logic lives in the src
package; this script provides the CLI interface.

Usage::

    python scripts/reset_dev_db.py [--db-path PATH]

Options:
    --db-path PATH   Override DATABASE_PATH env var (absolute or relative path).
    --force          Required when APP_ENV=production to prevent accidental resets.

Environment variables (loaded from .env if present):
    DATABASE_PATH   Path to the SQLite file.  Defaults to ``data/app.db``.
    APP_ENV         Runtime environment.  If ``production``, --force is required.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add project root to sys.path so ``src`` and ``migrations`` are importable
# when run directly.
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

from src.db.reset import reset_database  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [reset_dev_db] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Drop and recreate the development database with seed data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/reset_dev_db.py\n"
            "  python scripts/reset_dev_db.py --db-path /tmp/test.db\n"
            "  APP_ENV=production python scripts/reset_dev_db.py --force\n"
        ),
    )
    parser.add_argument(
        "--db-path",
        metavar="PATH",
        default=None,
        help="Override DATABASE_PATH env var. Accepts absolute or relative paths.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Required when APP_ENV=production to confirm intentional reset.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    db_path = Path(args.db_path).resolve() if args.db_path else None

    try:
        tables, rows = reset_database(db_path=db_path, force=args.force)
    except FileNotFoundError as exc:
        logger.error("Seed file error: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.error("Reset failed: %s", exc)
        sys.exit(1)

    print(f"Database reset. {tables} tables created. {rows} rows inserted.")
