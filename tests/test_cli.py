"""Tests for the CLI skeleton (E-055-01).

Uses typer.testing.CliRunner -- no real network calls, no subprocesses.
"""

from __future__ import annotations

from unittest.mock import patch

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
            "src.cli.status._check_single_profile",
            return_value=(0, "valid -- logged in as Jason Smith"),
        ),
        patch("src.cli.status._get_last_crawl", return_value=("2026-03-05T14:30:00Z", 47)),
        patch("src.cli.status._get_db_info", return_value=(True, "data/app.db (2.4 MB)")),
        patch("src.cli.status._get_proxy_sessions", return_value=None),
    ):
        result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
