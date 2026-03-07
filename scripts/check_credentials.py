#!/usr/bin/env python3
"""Verify GameChanger credentials stored in .env are present and valid.

Thin wrapper around ``src.gamechanger.credentials``.  Business logic lives
in the src package; this script provides the CLI interface.

Exit codes (single-profile mode)
---------------------------------
0 -- Credentials are valid and the API accepted them.
1 -- Credentials are present but expired, revoked, or unreachable.
2 -- Required credentials are missing from .env.

Exit codes (multi-profile mode, no --profile flag)
----------------------------------------------------
0 -- At least one profile is valid.
1 -- All profiles failed or had errors.

Usage::

    python scripts/check_credentials.py                  # check all profiles
    python scripts/check_credentials.py --profile web    # check web profile only
    python scripts/check_credentials.py --profile mobile # check mobile profile only
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

from src.gamechanger.credentials import check_credentials  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


def main() -> None:
    """Entry point: check credentials and exit with the appropriate code."""
    parser = argparse.ArgumentParser(
        description="Verify GameChanger credentials stored in .env are present and valid."
    )
    parser.add_argument(
        "--profile",
        choices=["web", "mobile"],
        default=None,
        help="Credential profile to check (default: check all profiles).",
    )
    args = parser.parse_args()

    exit_code, message = check_credentials(profile=args.profile)
    print(message)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
