"""Tests for the CLI skeleton (E-055-01).

Uses typer.testing.CliRunner -- no real network calls, no subprocesses.
Also includes a subprocess-based smoke test for the actual bb console script
entry point, which catches ModuleNotFoundError failures that CliRunner misses.
"""

from __future__ import annotations

import shutil
import subprocess
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


def test_help_exits_zero() -> None:
    """bb --help exits with code 0 and contains the CLI help string."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "baseball-crawl operator CLI" in result.output


def test_no_args_exits_zero() -> None:
    """bb with no arguments prints help and exits with code 0."""
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "baseball-crawl operator CLI" in result.output


def test_help_lists_all_command_groups() -> None:
    """bb --help lists all command groups and the status command."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "creds" in result.output
    assert "data" in result.output
    assert "proxy" in result.output
    assert "db" in result.output
    assert "status" in result.output


def test_creds_subapp_has_help() -> None:
    """bb creds --help is accessible."""
    result = runner.invoke(app, ["creds", "--help"])
    assert result.exit_code == 0
    assert "credential" in result.output.lower()


def test_data_subapp_has_help() -> None:
    """bb data --help is accessible."""
    result = runner.invoke(app, ["data", "--help"])
    assert result.exit_code == 0


def test_proxy_subapp_has_help() -> None:
    """bb proxy --help is accessible."""
    result = runner.invoke(app, ["proxy", "--help"])
    assert result.exit_code == 0


def test_db_subapp_has_help() -> None:
    """bb db --help is accessible."""
    result = runner.invoke(app, ["db", "--help"])
    assert result.exit_code == 0


def test_status_command_runs() -> None:
    """bb status runs and exits with code 0 when all credentials are valid."""
    with (
        patch(
            "src.cli.status.check_single_profile",
            return_value=(0, "valid -- logged in as Jason Smith"),
        ),
        patch("src.cli.status._get_last_crawl", return_value=("2026-03-05T14:30:00Z", 47)),
        patch("src.cli.status._get_db_info", return_value=(True, "data/app.db (2.4 MB)")),
        patch("src.cli.status._get_proxy_sessions", return_value=None),
    ):
        result = runner.invoke(app, ["status"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Subprocess smoke test -- verifies the actual bb console script entry point
# ---------------------------------------------------------------------------


_bb_installed = pytest.mark.skipif(shutil.which("bb") is None, reason="bb not installed")


@_bb_installed
def test_bb_help_subprocess() -> None:
    """bb --help works as a console script entry point (exit code 0).

    This test catches ModuleNotFoundError failures at import time that
    CliRunner tests miss, because CliRunner runs in-process and inherits
    pytest's sys.path (which includes the project root).  When bb runs as
    a real console script, only site-packages and the editable install
    finder are on sys.path -- not the project root.
    """
    result = subprocess.run(
        ["bb", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"bb --help failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


@_bb_installed
def test_bb_status_help_subprocess() -> None:
    """bb status --help works as a console script (exercises status import chain)."""
    result = subprocess.run(["bb", "status", "--help"], capture_output=True, text=True)
    assert result.returncode == 0, (
        f"bb status --help failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


@_bb_installed
def test_bb_creds_help_subprocess() -> None:
    """bb creds --help works as a console script (exercises creds import chain)."""
    result = subprocess.run(["bb", "creds", "--help"], capture_output=True, text=True)
    assert result.returncode == 0, (
        f"bb creds --help failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


@_bb_installed
def test_bb_db_help_subprocess() -> None:
    """bb db --help works as a console script (exercises db import chain)."""
    result = subprocess.run(["bb", "db", "--help"], capture_output=True, text=True)
    assert result.returncode == 0, (
        f"bb db --help failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


@_bb_installed
def test_bb_data_help_subprocess() -> None:
    """bb data --help works as a console script (exercises data import chain)."""
    result = subprocess.run(["bb", "data", "--help"], capture_output=True, text=True)
    assert result.returncode == 0, (
        f"bb data --help failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
