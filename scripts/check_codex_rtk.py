"""Smoke-check the project-local RTK binary for the Codex lane.

Verifies that the project-local RTK binary (installed by the devcontainer
bootstrap into ``.tools/rtk/``) is present, executable, and functional.

Exit codes
----------
0  Binary found, ``rtk --version`` succeeds, ``rtk git status`` produces output.
1  Binary missing, not executable, or a check command failed.

Usage::

    python scripts/check_codex_rtk.py
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Repo root derived from this script's location (scripts/ is one level below root).
_REPO_ROOT = Path(__file__).resolve().parent.parent

# Project-local RTK binary path installed by the devcontainer bootstrap.
# See .devcontainer/post-create-env.sh (E-082-01) for install details.
RTK_BIN = _REPO_ROOT / ".tools" / "rtk" / "rtk"


def resolve_rtk_binary(repo_root: Path | None = None) -> Path:
    """Return the expected project-local RTK binary path.

    Args:
        repo_root: Override the repo root (used in tests). Defaults to the
            actual repo root derived from this file's location.

    Returns:
        Path to the RTK binary under ``.tools/rtk/``.
    """
    root = repo_root if repo_root is not None else _REPO_ROOT
    return root / ".tools" / "rtk" / "rtk"


def check_binary_present(rtk_bin: Path) -> tuple[bool, str]:
    """Verify the RTK binary exists and is executable.

    Args:
        rtk_bin: Path to the RTK binary.

    Returns:
        ``(True, description)`` if the binary is present and executable;
        ``(False, reason)`` otherwise.
    """
    if not rtk_bin.exists():
        return False, f"binary not found: {rtk_bin}"
    if not rtk_bin.is_file():
        return False, f"path is not a regular file: {rtk_bin}"
    if not os.access(rtk_bin, os.X_OK):
        return False, f"binary is not executable: {rtk_bin}"
    return True, str(rtk_bin)


def run_rtk_check(rtk_bin: Path, args: list[str]) -> tuple[bool, str]:
    """Run the RTK binary with the given args and verify it produces output.

    Args:
        rtk_bin: Path to the RTK binary.
        args: Command-line arguments to pass (e.g., ``["--version"]``).

    Returns:
        ``(True, first_output_line)`` on success;
        ``(False, reason)`` on failure.
    """
    cmd = f"rtk {' '.join(args)}"
    try:
        result = subprocess.run(
            [str(rtk_bin)] + args,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=_REPO_ROOT,
        )
    except FileNotFoundError:
        return False, f"binary not found when invoking: {cmd}"
    except PermissionError:
        return False, f"binary is not executable: {cmd}"
    except subprocess.TimeoutExpired:
        return False, f"timed out after 15s: {cmd}"

    if result.returncode != 0:
        return False, f"exited {result.returncode}: {cmd}"

    # Accept output on either stdout or stderr (rtk may use either).
    output = (result.stdout or result.stderr or "").strip()
    if not output:
        return False, f"produced no output: {cmd}"

    return True, output.splitlines()[0]


def main() -> int:
    """Run all smoke checks and log a status line for each.

    Returns:
        0 if all checks passed, 1 if any check failed.
    """
    rtk_bin = resolve_rtk_binary()

    # Check binary presence first; skip command checks if the binary is unusable.
    binary_ok, binary_msg = check_binary_present(rtk_bin)
    if binary_ok:
        logger.info("[OK  ] binary present: %s", binary_msg)
    else:
        logger.error("[FAIL] binary present: %s", binary_msg)
        return 1

    checks: list[tuple[str, tuple[bool, str]]] = [
        ("rtk --version", run_rtk_check(rtk_bin, ["--version"])),
        ("rtk git status", run_rtk_check(rtk_bin, ["git", "status"])),
    ]

    all_passed = True
    for label, (ok, msg) in checks:
        if ok:
            logger.info("[OK  ] %s: %s", label, msg)
        else:
            logger.error("[FAIL] %s: %s", label, msg)
            all_passed = False

    return 0 if all_passed else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(main())
