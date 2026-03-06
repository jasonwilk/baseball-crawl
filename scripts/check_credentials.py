#!/usr/bin/env python3
"""Verify GameChanger credentials stored in .env are present and valid.

Makes a single API call (GET /me/user) and reports the result with a clear,
actionable message.

Exit codes
----------
0 -- Credentials are valid and the API accepted them.
1 -- Credentials are present but expired, revoked, or unreachable.
2 -- Required credentials are missing from .env.

Usage::

    python scripts/check_credentials.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Add project root to sys.path so ``src`` is importable when run directly.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import httpx
from dotenv import dotenv_values

from src.gamechanger.client import (
    ConfigurationError,
    CredentialExpiredError,
    ForbiddenError,
    GameChangerClient,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_REQUIRED_KEYS: tuple[str, ...] = (
    "GAMECHANGER_AUTH_TOKEN",
    "GAMECHANGER_DEVICE_ID",
    "GAMECHANGER_BASE_URL",
)

_ME_USER_ACCEPT = "application/vnd.gc.com.user+json; version=0.3.0"


def check_credentials() -> tuple[int, str]:
    """Validate GameChanger credentials from .env by calling GET /me/user.

    Returns:
        A tuple of (exit_code, message) where exit_code is:
        - 0: credentials valid
        - 1: credentials expired, revoked, or network error
        - 2: required credentials missing from .env
    """
    env_values = dotenv_values()
    missing = [key for key in _REQUIRED_KEYS if not env_values.get(key)]
    if missing:
        return (
            2,
            f"Missing required credential(s): {', '.join(missing)}\n"
            "Set them in .env via proxy capture or scripts/refresh_credentials.py",
        )

    try:
        client = GameChangerClient(min_delay_ms=0, jitter_ms=0)
    except ConfigurationError as exc:
        # ConfigurationError lists missing keys without revealing values.
        return (2, f"Missing required credential(s): {exc}")

    try:
        user = client.get("/me/user", accept=_ME_USER_ACCEPT)
    except ForbiddenError:
        return (
            1,
            "Access denied -- credentials may be expired or revoked",
        )
    except CredentialExpiredError:
        return (
            1,
            "Credentials expired -- refresh via proxy capture or scripts/refresh_credentials.py",
        )
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        return (1, f"Network error reaching GameChanger API: {exc}")
    except Exception as exc:  # noqa: BLE001
        return (1, f"Unexpected error: {exc}")

    first = (user.get("first_name") or "").strip()
    last = (user.get("last_name") or "").strip()
    if first and last:
        display = f"{first} {last}"
    else:
        display = user.get("email", "(unknown)")

    return (0, f"Credentials valid -- logged in as {display}")


def main() -> None:
    """Entry point: check credentials and exit with the appropriate code."""
    exit_code, message = check_credentials()
    print(message)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
