"""Backfill appearance_order for existing player_game_pitching rows.

Thin wrapper around ``src.gamechanger.loaders.backfill``.

Usage::

    bb data backfill-appearance-order       # preferred (via CLI)
    python scripts/backfill_appearance_order.py  # direct invocation

See E-204-02 for context.
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path

# Add project root to sys.path so ``src`` is importable when run directly.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.gamechanger.loaders.backfill import backfill_appearance_order


def main(db_path: Path | None = None) -> None:
    """Entry point for direct script invocation."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if db_path is None:
        db_path = _PROJECT_ROOT / "data" / "app.db"

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        summary = backfill_appearance_order(conn)

    print(f"\nBackfill Summary:")
    print(f"  Games processed: {summary['games_processed']}")
    print(f"  Rows updated: {summary['rows_updated']}")
    print(f"  Games skipped (no cached file): {summary['games_skipped']}")
    print(f"  Games with errors: {summary['games_with_errors']}")
    print(f"\nReminder: run 'bb data scout' to recompute scouting season aggregates.")


if __name__ == "__main__":
    main()
