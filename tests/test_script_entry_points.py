"""Subprocess smoke tests for standalone operator scripts in scripts/.

Each test verifies that a script can be invoked with --help in an isolated
subprocess without import errors, missing-module failures, or non-zero exits.
This pattern catches import-time side effects (e.g., root logger mutation,
missing dependencies) that pytest's in-process runner misses because it
inherits the full sys.path and module cache from the test session.

Pattern mirrors tests/test_cli.py lines 92-158 (the bb console script tests).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"

_bb_installed = pytest.mark.skipif(
    shutil.which("bb") is None, reason="bb console script not installed"
)


def _run_help(script_name: str) -> subprocess.CompletedProcess[str]:
    """Run ``python scripts/<script_name> --help`` and return the result."""
    return subprocess.run(
        [sys.executable, str(_SCRIPTS_DIR / script_name), "--help"],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# AC-4: scripts/check_credentials.py --help
# ---------------------------------------------------------------------------


def test_check_credentials_help_exits_0() -> None:
    """scripts/check_credentials.py --help exits 0 (no import errors, --help handled)."""
    result = _run_help("check_credentials.py")
    assert result.returncode == 0, (
        f"check_credentials.py --help failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# AC-5: scripts/backup_db.py --help
# ---------------------------------------------------------------------------


def test_backup_db_help_exits_0() -> None:
    """scripts/backup_db.py --help exits 0 (no import errors, --help handled)."""
    result = _run_help("backup_db.py")
    assert result.returncode == 0, (
        f"backup_db.py --help failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# AC-6: scripts/reset_dev_db.py --help
# ---------------------------------------------------------------------------


def test_reset_dev_db_help_exits_0() -> None:
    """scripts/reset_dev_db.py --help exits 0 (no import errors, --help handled)."""
    result = _run_help("reset_dev_db.py")
    assert result.returncode == 0, (
        f"reset_dev_db.py --help failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# AC-9: scripts/refresh_credentials.py --help
# ---------------------------------------------------------------------------


def test_refresh_credentials_help_exits_0() -> None:
    """scripts/refresh_credentials.py --help exits 0 (no import errors, --help handled)."""
    result = _run_help("refresh_credentials.py")
    assert result.returncode == 0, (
        f"refresh_credentials.py --help failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# AC-10: scripts/smoke_test.py --help
# ---------------------------------------------------------------------------


def test_smoke_test_help_exits_0() -> None:
    """scripts/smoke_test.py --help exits 0 (no import errors, --help handled)."""
    result = _run_help("smoke_test.py")
    assert result.returncode == 0, (
        f"smoke_test.py --help failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# E-257-01 AC-8: bb report reconcile-scoreboard --help (console-script subprocess)
# ---------------------------------------------------------------------------


@_bb_installed
def test_bb_reconcile_scoreboard_help_exits_0() -> None:
    """bb report reconcile-scoreboard --help works as a console script (exit 0).

    Runs the real ``bb`` entry point in a subprocess so the reconcile-scoreboard
    import chain (recon_scoreboard -> plays_parser) is exercised outside pytest's
    inherited sys.path -- catching ModuleNotFoundError / import-time failures the
    in-process CliRunner tests miss.
    """
    result = subprocess.run(
        ["bb", "report", "reconcile-scoreboard", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"bb report reconcile-scoreboard --help failed with exit code "
        f"{result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
