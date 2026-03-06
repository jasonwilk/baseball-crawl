#!/usr/bin/env python3
"""Bootstrap pipeline -- validate credentials and run the full crawl + load pipeline.

Runs four stages in order:
  1. Credential check    -- verifies .env credentials are valid (GET /me/user)
  2. Team config check   -- verifies config/teams.yaml has real team IDs
  3. Crawl               -- fetches all data from the GameChanger API
  4. Load                -- writes crawled data into the SQLite database

Exits early with a clear message if any pre-flight check fails. Crawl
failures are non-fatal -- partial crawl data is still loaded.

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

# ---------------------------------------------------------------------------
# Project root on sys.path so src.* and scripts.* imports work when run directly.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.check_credentials import check_credentials  # noqa: E402
from scripts import crawl as crawl_module  # noqa: E402
from scripts import load as load_module  # noqa: E402
from src.gamechanger.config import load_config  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s -- %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

_CONFIG_PATH = _PROJECT_ROOT / "config" / "teams.yaml"


def _check_team_config() -> tuple[int, str]:
    """Validate that config/teams.yaml has at least one non-placeholder team.

    Returns:
        (exit_code, message): 0 with team summary on success,
        1 with actionable message on failure.
    """
    try:
        config = load_config(_CONFIG_PATH)
    except FileNotFoundError:
        return (1, f"Team config file not found: {_CONFIG_PATH.relative_to(_PROJECT_ROOT)}")

    real_teams = [t for t in config.owned_teams if not t.id.startswith("REPLACE_WITH_")]
    if not real_teams:
        return (
            1,
            "No teams configured -- edit config/teams.yaml (or use the admin UI once available)",
        )

    names = ", ".join(t.name for t in real_teams)
    return (0, f"{len(real_teams)} team(s) configured: {names}")


def run(
    check_only: bool = False,
    profile: str = "web",
    dry_run: bool = False,
) -> int:
    """Execute the bootstrap pipeline.

    Args:
        check_only: If True, run only credential and team config checks, then exit.
        profile: Header profile ("web" or "mobile") passed to the crawl stage.
        dry_run: If True, pass --dry-run through to crawl and load stages.

    Returns:
        Exit code: 0 if all stages succeeded, 1 on any failure.
    """
    summary: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Stage 1: Credential check
    # ------------------------------------------------------------------
    print("Checking credentials...")
    cred_code, cred_msg = check_credentials()
    print(f"  {cred_msg}")
    summary["credentials"] = "valid" if cred_code == 0 else "expired/error"

    if cred_code != 0:
        print("\nBootstrap aborted -- credentials must be valid before crawling.")
        _print_summary(summary)
        return 1

    # ------------------------------------------------------------------
    # Stage 2: Team config check
    # ------------------------------------------------------------------
    print("Checking team configuration...")
    team_code, team_msg = _check_team_config()
    print(f"  {team_msg}")
    summary["teams"] = team_msg if team_code == 0 else "not configured"

    if team_code != 0:
        print("\nBootstrap aborted -- configure teams before crawling.")
        _print_summary(summary)
        return 1

    if check_only:
        print("\nCheck-only mode -- skipping crawl and load.")
        _print_summary(summary)
        return 0

    # ------------------------------------------------------------------
    # Stage 3: Crawl
    # ------------------------------------------------------------------
    print("Crawling data...")
    crawl_code = crawl_module.run(dry_run=dry_run, profile=profile)
    if crawl_code != 0:
        print("  WARNING: Crawl completed with errors. Partial data will still be loaded.")
        summary["crawl"] = "warning (errors)"
    else:
        summary["crawl"] = "success"

    # ------------------------------------------------------------------
    # Stage 4: Load
    # ------------------------------------------------------------------
    print("Loading data...")
    load_code = load_module.run(dry_run=dry_run)
    if load_code != 0:
        print("  ERROR: Load stage failed.")
        summary["load"] = "failed"
    else:
        summary["load"] = "success"

    _print_summary(summary)
    return 0 if (crawl_code == 0 and load_code == 0) else 1


def _print_summary(summary: dict[str, str]) -> None:
    """Print the pipeline summary to stdout.

    Args:
        summary: Mapping of stage name to outcome string.
    """
    print("\n--- Bootstrap summary ---")
    for stage, outcome in summary.items():
        print(f"  {stage}: {outcome}")


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
