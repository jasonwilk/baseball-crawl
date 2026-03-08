#!/usr/bin/env python3
"""Smoke test: verifies GameChanger API access end-to-end.

Calls three endpoints in sequence, prints a summary table, and exits with
status code 0 if all calls succeeded or 1 if any failed.

Usage:
    python scripts/smoke_test.py
    python scripts/smoke_test.py --team-id <UUID>

Requires valid credentials in .env. If credentials are expired, run:
    bb creds check
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any

# Add the project root to sys.path so ``src`` is importable when the script is
# run directly (i.e., without an editable install).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.gamechanger.client import (
    ConfigurationError,
    CredentialExpiredError,
    GameChangerAPIError,
    GameChangerClient,
    RateLimitError,
)

# Suppress DEBUG/INFO noise from the HTTP client during smoke test output.
logging.basicConfig(level=logging.WARNING)

# Accept headers per docs/api/ endpoint files (YAML frontmatter 'accept' field).
_ACCEPT_TEAMS = "application/vnd.gc.com.team:list+json; version=0.10.0"
_ACCEPT_GAME_SUMMARIES = "application/vnd.gc.com.game_summary:list+json; version=0.1.0"
_ACCEPT_PLAYERS = "application/vnd.gc.com.player:list+json; version=0.1.0"

_COL_WIDTH = 60


def _print_row(endpoint: str, status: str, elapsed_ms: float, summary: str) -> None:
    """Print one result row to stdout."""
    print(f"  {endpoint:<40}  {status:<8}  {elapsed_ms:>7.0f}ms  {summary}")


def _print_header() -> None:
    print()
    print(f"  {'Endpoint':<40}  {'Status':<8}  {'Time':>8}  Description")
    print("  " + "-" * 80)


def _call(
    client: GameChangerClient,
    path: str,
    accept: str,
    params: dict[str, Any] | None = None,
) -> tuple[Any, float]:
    """Call an endpoint and return (response_data, elapsed_ms).

    elapsed_ms covers only the HTTP round-trip (excluding rate-limit delays,
    which are applied by the session after the response is received).
    """
    t0 = time.perf_counter()
    data = client.get(path, params=params, accept=accept)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return data, elapsed_ms


def run_smoke_test(team_id: str | None = None) -> bool:
    """Run the smoke test against the live GameChanger API.

    Args:
        team_id: Optional team UUID. When provided, skips /me/teams discovery.

    Returns:
        True if all tested endpoints returned successfully, False otherwise.
    """
    all_passed = True

    try:
        client = GameChangerClient()
    except ConfigurationError as exc:
        print(f"\nConfiguration error: {exc}")
        print("Ensure the following are set in your .env file:")
        print("  GAMECHANGER_REFRESH_TOKEN_WEB, GAMECHANGER_CLIENT_ID_WEB,")
        print("  GAMECHANGER_CLIENT_KEY_WEB, GAMECHANGER_DEVICE_ID_WEB,")
        print("  GAMECHANGER_BASE_URL")
        print("Run: bb creds check")
        return False

    _print_header()

    # ------------------------------------------------------------------
    # Step 1: Discover teams (unless --team-id provided)
    # ------------------------------------------------------------------
    resolved_team_id = team_id

    if team_id is None:
        path = "/me/teams"
        try:
            data, elapsed_ms = _call(
                client,
                path,
                _ACCEPT_TEAMS,
                params={"include": "user_team_associations"},
            )
            if isinstance(data, list) and data:
                resolved_team_id = data[0].get("id") or data[0].get("team_id")
                team_names = [
                    t.get("name") or t.get("team_name") or t.get("id", "?")
                    for t in data
                ]
                summary = f"{len(data)} team(s): {', '.join(str(n) for n in team_names)}"
            else:
                resolved_team_id = None
                summary = "0 teams returned"
            _print_row(path, "OK", elapsed_ms, summary)
        except CredentialExpiredError:
            print("\nCredentials expired. Re-capture via proxy or run: bb creds check")
            return False
        except (RateLimitError, GameChangerAPIError) as exc:
            _print_row(path, "FAIL", 0, str(exc))
            all_passed = False
    else:
        print(f"\n  Using provided --team-id: {team_id}")

    if resolved_team_id is None:
        print("\n  Cannot proceed: no team UUID available.")
        return False

    # ------------------------------------------------------------------
    # Step 2: Game summaries
    # ------------------------------------------------------------------
    path = f"/teams/{resolved_team_id}/game-summaries"
    try:
        data, elapsed_ms = _call(client, path, _ACCEPT_GAME_SUMMARIES)
        count = len(data) if isinstance(data, list) else "?"
        _print_row(path, "OK", elapsed_ms, f"{count} game(s) found")
    except CredentialExpiredError:
        print("\nCredentials expired. Re-capture via proxy or run: bb creds check")
        return False
    except (RateLimitError, GameChangerAPIError) as exc:
        _print_row(path, "FAIL", 0, str(exc))
        all_passed = False

    # ------------------------------------------------------------------
    # Step 3: Players
    # ------------------------------------------------------------------
    path = f"/teams/{resolved_team_id}/players"
    try:
        data, elapsed_ms = _call(client, path, _ACCEPT_PLAYERS)
        count = len(data) if isinstance(data, list) else "?"
        _print_row(path, "OK", elapsed_ms, f"{count} player(s) on roster")
    except CredentialExpiredError:
        print("\nCredentials expired. Re-capture via proxy or run: bb creds check")
        return False
    except (RateLimitError, GameChangerAPIError) as exc:
        _print_row(path, "FAIL", 0, str(exc))
        all_passed = False

    print()
    if all_passed:
        print("  All endpoints OK.")
    else:
        print("  One or more endpoints FAILED.")
    print()

    return all_passed


def main() -> None:
    """Parse arguments and run the smoke test."""
    parser = argparse.ArgumentParser(
        description="Smoke test: verify GameChanger API access end-to-end."
    )
    parser.add_argument(
        "--team-id",
        metavar="UUID",
        help="Team UUID to use for team-scoped endpoints. "
             "If omitted, discovered from /me/teams.",
    )
    args = parser.parse_args()

    try:
        passed = run_smoke_test(team_id=args.team_id)
    except CredentialExpiredError:
        print("\nCredentials expired. Re-capture via proxy or run: bb creds check")
        sys.exit(1)

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
