"""Subprocess smoke tests for standalone operator scripts in scripts/.

Each test verifies that a script can be invoked with --help in an isolated
subprocess without import errors, missing-module failures, or non-zero exits.
This pattern catches import-time side effects (e.g., root logger mutation,
missing dependencies) that pytest's in-process runner misses because it
inherits the full sys.path and module cache from the test session.

Pattern mirrors tests/test_cli.py lines 92-158 (the bb console script tests).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def _run_help(script_name: str) -> subprocess.CompletedProcess[str]:
    """Run ``python scripts/<script_name> --help`` and return the result."""
    return subprocess.run(
        [sys.executable, str(_SCRIPTS_DIR / script_name), "--help"],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# AC-1: scripts/bootstrap.py --help
# ---------------------------------------------------------------------------


def test_bootstrap_help_exits_0() -> None:
    """scripts/bootstrap.py --help exits 0 (no import errors, --help handled)."""
    result = _run_help("bootstrap.py")
    assert result.returncode == 0, (
        f"bootstrap.py --help failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# AC-2: scripts/crawl.py --help
# ---------------------------------------------------------------------------


def test_crawl_help_exits_0() -> None:
    """scripts/crawl.py --help exits 0 (no import errors, --help handled)."""
    result = _run_help("crawl.py")
    assert result.returncode == 0, (
        f"crawl.py --help failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# AC-3: scripts/load.py --help
# ---------------------------------------------------------------------------


def test_load_help_exits_0() -> None:
    """scripts/load.py --help exits 0 (no import errors, --help handled)."""
    result = _run_help("load.py")
    assert result.returncode == 0, (
        f"load.py --help failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
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
