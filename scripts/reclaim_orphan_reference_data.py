#!/usr/bin/env python3
"""One-time backlog reclamation of orphaned reference data (E-273-05).

A throwaway operator one-shot.  It IMPORTS and calls
``reclaim_orphan_reference_data`` from ``src.reports.lifecycle`` -- it does NOT
re-implement the reclamation or re-inline any orphan query (TN-9, DRY: one
predicate definition, no duplicated SQL, no permanent ``bb data`` subcommand).
The ongoing pass wired into the delete paths (E-273-02) reclaims the backlog
automatically on its first invocation; this script is the controlled,
quiescent-DB, decoupled-from-generation way to do it once, on demand.

OPERATOR SEQUENCE (TN-10)
-------------------------
Run these in order against a QUIESCENT database (no report generation in
flight -- a live ``generating`` report makes the pass DEFER):

  1. Re-snapshot the reconciliation baseline FIRST.  This is OPERATOR-OWNED --
     no agent runs ``--update-baseline``::

         bb report reconcile-scoreboard --update-baseline

  2. Run this one-shot::

         python scripts/reclaim_orphan_reference_data.py

  3. Expect an EXACT no-diff and clean integrity.  A pure reference-data sweep
     touches NO stat rows, so ANY scoreboard movement means the sweep
     overreached::

         bb report reconcile-scoreboard        # expect exact no-diff
         sqlite3 data/app.db 'PRAGMA foreign_key_check;'   # expect empty
         sqlite3 data/app.db 'PRAGMA integrity_check;'     # expect 'ok'

Exit codes (the three outcomes are DISTINCT -- do not conflate, TN-5):

  0  SUCCESS   -- reclamation ran and the post-run ownership invariant is zero.
  2  DEFERRED  -- a report generation was in flight; the reap-then-gate guard
                  refused and NOTHING was deleted.  Re-run against a quiescent
                  DB.  This is a liveness delay, NOT a leak.
  3  RESIDUAL  -- reclamation ran but orphans remain -- investigate (possible
                  overreach or an unhandled reachability edge).
  1  ERROR     -- an operational failure (e.g. the DB could not be opened).

Usage::

    python scripts/reclaim_orphan_reference_data.py [--db-path PATH]

Environment variables (loaded from .env if present):
    DATABASE_PATH   Path to the SQLite file.  Defaults to ``data/app.db``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from contextlib import closing
from pathlib import Path

# Add project root to sys.path so ``src`` is importable when run directly.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.api.db import get_connection  # noqa: E402
from src.db.paths import resolve_db_path  # noqa: E402
from src.reports.lifecycle import (  # noqa: E402
    OrphanCounts,
    count_orphan_reference_data,
    reclaim_orphan_reference_data,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [reclaim_orphans] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Exit-code contract (see the module docstring). Named so the tests and any
# monitor key on the same constants.
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_DEFERRED = 2
EXIT_RESIDUAL = 3


def _fmt(counts: OrphanCounts) -> str:
    return (
        f"teams={counts.teams}, players={counts.players}, "
        f"roster_rows={counts.roster_rows}"
    )


def run_reclamation(db_path: str | Path | None = None) -> int:
    """Run the one-time backlog reclamation and return the process exit code.

    Thin orchestration around the src pass: resolve the DB, print the pre-run
    orphan counts, invoke ``reclaim_orphan_reference_data``, print the deletion
    counts and the post-run orphan counts, and map the outcome to the three-way
    exit-code contract (AC-3).  Reusable logic lives in ``src``; this is a
    wrapper.

    Args:
        db_path: Optional explicit DB path (``resolve_db_path`` precedence:
            explicit override > ``DATABASE_PATH`` env > default).

    Returns:
        One of :data:`EXIT_SUCCESS` / :data:`EXIT_DEFERRED` /
        :data:`EXIT_RESIDUAL` / :data:`EXIT_ERROR`.
    """
    try:
        resolved = resolve_db_path(db_path)
    except Exception as exc:  # noqa: BLE001 -- surface any resolution failure
        logger.error("Could not resolve the database path: %s", exc)
        return EXIT_ERROR

    logger.info("Reclaiming orphaned reference data in %s", resolved)
    try:
        with closing(get_connection(resolved)) as conn:
            pre = count_orphan_reference_data(conn)
            print(f"Pre-run orphan counts:  {_fmt(pre)}")

            result = reclaim_orphan_reference_data(conn)

            if result.deferred:
                print(
                    "DEFERRED: a report generation is in flight; the "
                    "reap-then-gate guard refused and NOTHING was deleted. "
                    "Re-run against a quiescent DB (no 'generating' reports). "
                    "This is a liveness delay, not a leak."
                )
                return EXIT_DEFERRED

            print(
                f"Reclaimed: teams={result.teams_deleted}, "
                f"players={result.players_deleted}, "
                f"roster_rows={result.roster_rows_deleted}"
            )

            post = count_orphan_reference_data(conn)
            print(f"Post-run orphan counts: {_fmt(post)}")

            if post.teams or post.players or post.roster_rows:
                print(
                    "RESIDUAL: reclamation ran but orphaned reference data "
                    "remains -- investigate (possible overreach or an "
                    "unhandled reachability edge)."
                )
                return EXIT_RESIDUAL

            print(
                "SUCCESS: ownership invariant is zero -- no orphaned reference "
                "data remains. Now verify: `bb report reconcile-scoreboard` "
                "should show an EXACT no-diff, and PRAGMA foreign_key_check / "
                "integrity_check should be clean (a pure reference-data sweep "
                "touches no stat rows)."
            )
            return EXIT_SUCCESS
    except Exception as exc:  # noqa: BLE001 -- operational failure -> exit 1
        logger.error("Reclamation failed: %s", exc, exc_info=True)
        return EXIT_ERROR


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "One-time backlog reclamation of orphaned reference data "
            "(teams / players / rosters no longer reachable from any report)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Operator sequence (TN-10), against a QUIESCENT DB:\n"
            "  1. bb report reconcile-scoreboard --update-baseline   "
            "(operator-owned; no agent runs this)\n"
            "  2. python scripts/reclaim_orphan_reference_data.py\n"
            "  3. bb report reconcile-scoreboard                     "
            "(expect EXACT no-diff)\n"
            "     PRAGMA foreign_key_check / PRAGMA integrity_check   "
            "(expect clean)\n\n"
            "Exit codes: 0 success | 2 deferred (re-run when quiescent) | "
            "3 residual (investigate) | 1 error.\n"
        ),
    )
    parser.add_argument(
        "--db-path",
        metavar="PATH",
        default=None,
        help="Override DATABASE_PATH env var. Accepts absolute or relative paths.",
    )
    return parser.parse_args(argv)


def _load_env() -> None:
    """Load ``.env`` into ``os.environ`` when running as a CLI process.

    Deliberately NOT called at import time or from :func:`run_reclamation`:
    importing this one-shot must not mutate process-global ``os.environ`` (that
    pollution leaked ``.env`` values into unrelated tests via import order). The
    operator runtime behavior is preserved -- when the script is actually RUN as
    a process, ``.env`` still loads before DB resolution so a ``DATABASE_PATH``
    set in ``.env`` is honored (``resolve_db_path`` reads the env).
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return  # dotenv is optional; env vars may be injected directly (Docker)

    _env_file = _PROJECT_ROOT / ".env"
    if _env_file.exists():
        load_dotenv(_env_file)


def main(argv: list[str] | None = None) -> int:
    _load_env()
    args = _parse_args(argv)
    return run_reclamation(args.db_path)


if __name__ == "__main__":
    sys.exit(main())
