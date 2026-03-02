#!/usr/bin/env python3
"""Refresh GameChanger credentials from a curl command.

Reads a curl command (from ``secrets/gamechanger-curl.txt``, a file path, or
the ``--curl`` flag), extracts authentication-relevant headers, and writes them
to ``.env`` in the project root.  Existing non-credential values in ``.env``
are preserved.

Usage
-----
Copy a network request from browser dev tools as a cURL command, then run one
of the following:

1. Default -- reads from ``secrets/gamechanger-curl.txt``::

    python scripts/refresh_credentials.py

2. Inline curl string (wrap the whole thing in double quotes)::

    python scripts/refresh_credentials.py --curl "curl 'https://...' -H 'gc-token: ...'"

3. Explicit file path::

    python scripts/refresh_credentials.py --file /path/to/my-curl.txt

How to copy a curl command from Chrome dev tools
------------------------------------------------
1. Open https://web.gc.com and log in.
2. Open DevTools (F12) -> Network tab.
3. Trigger any GameChanger API request (e.g., load a team page).
4. Right-click the request in the Network tab -> "Copy" -> "Copy as cURL".
5. Paste into ``secrets/gamechanger-curl.txt`` or pass via ``--curl``.

Security notes
--------------
- The ``.env`` file is git-ignored.  Never commit it.
- The ``secrets/`` directory is git-ignored.  Never commit files from it.
- Credentials are only written to ``.env``; they are never printed in full.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add the project root to sys.path so ``src`` is importable when the script is
# run directly (i.e., without an editable install).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.gamechanger.credential_parser import CurlParseError, merge_env_file, parse_curl

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_DEFAULT_CURL_FILE = _PROJECT_ROOT / "secrets" / "gamechanger-curl.txt"
_ENV_FILE = _PROJECT_ROOT / ".env"


def _build_parser() -> argparse.ArgumentParser:
    """Return the configured argument parser."""
    parser = argparse.ArgumentParser(
        prog="refresh_credentials.py",
        description=(
            "Extract GameChanger auth credentials from a curl command and write "
            "them to .env."
        ),
        epilog=(
            "How to get a curl command:\n"
            "  1. Open https://web.gc.com and log in.\n"
            "  2. Open DevTools (F12) -> Network tab.\n"
            "  3. Load any GameChanger page to trigger an API request.\n"
            "  4. Right-click the request -> Copy -> Copy as cURL.\n"
            "  5. Paste into secrets/gamechanger-curl.txt or pass with --curl.\n\n"
            "The .env file and secrets/ directory are git-ignored; "
            "credentials are never committed."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--curl",
        metavar="CURL_COMMAND",
        help=(
            "Inline curl command string.  Wrap the entire command in double "
            "quotes when passing on the command line."
        ),
    )
    source.add_argument(
        "--file",
        metavar="PATH",
        help=(
            "Path to a file containing the curl command.  "
            f"Defaults to {_DEFAULT_CURL_FILE} when neither --curl nor --file is given."
        ),
    )
    return parser


def _read_curl_command(args: argparse.Namespace) -> str:
    """Return the curl command string from the appropriate source.

    Args:
        args: Parsed CLI arguments.

    Returns:
        The raw curl command string.

    Raises:
        SystemExit: If the source file cannot be read.
    """
    if args.curl:
        return args.curl

    file_path = Path(args.file) if args.file else _DEFAULT_CURL_FILE
    if not file_path.exists():
        print(
            f"ERROR: curl command file not found: {file_path}\n"
            "Provide a curl command with --curl or --file, or save one to "
            f"{_DEFAULT_CURL_FILE}.",
            file=sys.stderr,
        )
        sys.exit(1)

    return file_path.read_text(encoding="utf-8")


def main() -> None:
    """Entry point: parse args, extract credentials, write .env."""
    parser = _build_parser()
    args = parser.parse_args()

    curl_command = _read_curl_command(args)

    try:
        new_credentials = parse_curl(curl_command)
    except CurlParseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    # merge_env_file reads the existing .env, merges new values, writes it back,
    # and returns the merged dict for confirmation output.
    merged = merge_env_file(str(_ENV_FILE), new_credentials)

    # Confirmation output: show keys written (never show values).
    print(f"Credentials written to {_ENV_FILE}:")
    for key in sorted(new_credentials.keys()):
        print(f"  {key}")
    print(f"({len(new_credentials)} keys written, {len(merged)} total keys in .env)")


if __name__ == "__main__":
    main()
