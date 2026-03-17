"""Tests for src/cli/data.py -- bb data sub-commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# bb data sync
# ---------------------------------------------------------------------------


def test_sync_default_args() -> None:
    """sync calls bootstrap.run with default arguments."""
    with patch("src.pipeline.bootstrap.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "sync"])
    mock_run.assert_called_once_with(check_only=False, profile="web", dry_run=False)
    assert result.exit_code == 0


def test_sync_check_only() -> None:
    """sync --check-only forwards check_only=True."""
    with patch("src.pipeline.bootstrap.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "sync", "--check-only"])
    mock_run.assert_called_once_with(check_only=True, profile="web", dry_run=False)
    assert result.exit_code == 0


def test_sync_profile_mobile() -> None:
    """sync --profile mobile forwards profile='mobile'."""
    with patch("src.pipeline.bootstrap.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "sync", "--profile", "mobile"])
    mock_run.assert_called_once_with(check_only=False, profile="mobile", dry_run=False)
    assert result.exit_code == 0


def test_sync_dry_run() -> None:
    """sync --dry-run forwards dry_run=True."""
    with patch("src.pipeline.bootstrap.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "sync", "--dry-run"])
    mock_run.assert_called_once_with(check_only=False, profile="web", dry_run=True)
    assert result.exit_code == 0


def test_sync_propagates_nonzero_exit() -> None:
    """sync propagates non-zero exit codes from bootstrap.run."""
    with patch("src.pipeline.bootstrap.run", return_value=1):
        result = runner.invoke(app, ["data", "sync"])
    assert result.exit_code == 1


def test_sync_has_no_source_flag() -> None:
    """sync intentionally has no --source flag."""
    result = runner.invoke(app, ["data", "sync", "--source", "db"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# bb data crawl
# ---------------------------------------------------------------------------


def test_crawl_default_args() -> None:
    """crawl calls crawl.run with default arguments."""
    with patch("src.pipeline.crawl.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "crawl"])
    mock_run.assert_called_once_with(
        dry_run=False,
        crawler_filter=None,
        profile="web",
        source="yaml",
    )
    assert result.exit_code == 0


def test_crawl_dry_run() -> None:
    """crawl --dry-run forwards dry_run=True."""
    with patch("src.pipeline.crawl.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "crawl", "--dry-run"])
    mock_run.assert_called_once_with(
        dry_run=True,
        crawler_filter=None,
        profile="web",
        source="yaml",
    )
    assert result.exit_code == 0


def test_crawl_with_crawler_filter() -> None:
    """crawl --crawler roster forwards crawler_filter='roster'."""
    with patch("src.pipeline.crawl.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "crawl", "--crawler", "roster"])
    mock_run.assert_called_once_with(
        dry_run=False,
        crawler_filter="roster",
        profile="web",
        source="yaml",
    )
    assert result.exit_code == 0


def test_crawl_with_profile() -> None:
    """crawl --profile mobile forwards profile='mobile'."""
    with patch("src.pipeline.crawl.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "crawl", "--profile", "mobile"])
    mock_run.assert_called_once_with(
        dry_run=False,
        crawler_filter=None,
        profile="mobile",
        source="yaml",
    )
    assert result.exit_code == 0


def test_crawl_source_db() -> None:
    """crawl --source db forwards source='db'."""
    with patch("src.pipeline.crawl.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "crawl", "--source", "db"])
    mock_run.assert_called_once_with(
        dry_run=False,
        crawler_filter=None,
        profile="web",
        source="db",
    )
    assert result.exit_code == 0


def test_crawl_source_yaml_explicit() -> None:
    """crawl --source yaml explicitly forwards source='yaml'."""
    with patch("src.pipeline.crawl.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "crawl", "--source", "yaml"])
    mock_run.assert_called_once_with(
        dry_run=False,
        crawler_filter=None,
        profile="web",
        source="yaml",
    )
    assert result.exit_code == 0


def test_crawl_invalid_crawler_name() -> None:
    """crawl rejects unrecognised --crawler names with exit code 1."""
    with patch("src.pipeline.crawl.run", return_value=0):
        result = runner.invoke(app, ["data", "crawl", "--crawler", "nonexistent"])
    assert result.exit_code == 1


def test_crawl_all_valid_crawler_names() -> None:
    """crawl accepts all documented crawler names."""
    valid_names = ["roster", "schedule", "opponent", "player-stats", "game-stats"]
    for name in valid_names:
        with patch("src.pipeline.crawl.run", return_value=0) as mock_run:
            result = runner.invoke(app, ["data", "crawl", "--crawler", name])
        assert result.exit_code == 0, f"Crawler '{name}' should be valid"
        mock_run.assert_called_once_with(
            dry_run=False,
            crawler_filter=name,
            profile="web",
            source="yaml",
        )


# ---------------------------------------------------------------------------
# bb data load
# ---------------------------------------------------------------------------


def test_load_default_args() -> None:
    """load calls load.run with default arguments."""
    with patch("src.pipeline.load.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "load"])
    mock_run.assert_called_once_with(
        dry_run=False,
        loader_filter=None,
        source="yaml",
    )
    assert result.exit_code == 0


def test_load_dry_run() -> None:
    """load --dry-run forwards dry_run=True."""
    with patch("src.pipeline.load.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "load", "--dry-run"])
    mock_run.assert_called_once_with(
        dry_run=True,
        loader_filter=None,
        source="yaml",
    )
    assert result.exit_code == 0


def test_load_with_loader_filter() -> None:
    """load --loader roster forwards loader_filter='roster'."""
    with patch("src.pipeline.load.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "load", "--loader", "roster"])
    mock_run.assert_called_once_with(
        dry_run=False,
        loader_filter="roster",
        source="yaml",
    )
    assert result.exit_code == 0


def test_load_source_db() -> None:
    """load --source db forwards source='db'."""
    with patch("src.pipeline.load.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "load", "--source", "db"])
    mock_run.assert_called_once_with(
        dry_run=False,
        loader_filter=None,
        source="db",
    )
    assert result.exit_code == 0


def test_load_source_yaml_explicit() -> None:
    """load --source yaml explicitly forwards source='yaml'."""
    with patch("src.pipeline.load.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "load", "--source", "yaml"])
    mock_run.assert_called_once_with(
        dry_run=False,
        loader_filter=None,
        source="yaml",
    )
    assert result.exit_code == 0


def test_load_invalid_loader_name() -> None:
    """load rejects unrecognised --loader names with exit code 1."""
    with patch("src.pipeline.load.run", return_value=0):
        result = runner.invoke(app, ["data", "load", "--loader", "nonexistent"])
    assert result.exit_code == 1


def test_load_all_valid_loader_names() -> None:
    """load accepts all documented loader names."""
    valid_names = ["roster", "game", "season-stats"]
    for name in valid_names:
        with patch("src.pipeline.load.run", return_value=0) as mock_run:
            result = runner.invoke(app, ["data", "load", "--loader", name])
        assert result.exit_code == 0, f"Loader '{name}' should be valid"
        mock_run.assert_called_once_with(
            dry_run=False,
            loader_filter=name,
            source="yaml",
        )


# ---------------------------------------------------------------------------
# bb data --help
# ---------------------------------------------------------------------------


def test_data_help_lists_commands() -> None:
    """bb data --help lists sync, crawl, and load commands."""
    result = runner.invoke(app, ["data", "--help"])
    assert result.exit_code == 0
    assert "sync" in result.output
    assert "crawl" in result.output
    assert "load" in result.output


# ---------------------------------------------------------------------------
# bb data resolve-opponents
# ---------------------------------------------------------------------------


def test_resolve_opponents_passes_db_path_to_load_config() -> None:
    """resolve_opponents() calls load_config with the db_path keyword argument.

    This is a regression test for the bug fixed in E-120-01 where load_config()
    was called without db_path, causing it to always use the default path.
    """
    fake_db_path = Path("/fake/path/app.db")

    mock_result = MagicMock()
    mock_result.resolved = 1
    mock_result.unlinked = 0
    mock_result.stored_hidden = 0
    mock_result.errors = 0

    with (
        patch("src.cli.data._resolve_db_path", return_value=fake_db_path),
        patch("src.gamechanger.config.load_config") as mock_load_config,
        patch("src.gamechanger.client.GameChangerClient"),
        patch(
            "src.gamechanger.crawlers.opponent_resolver.OpponentResolver"
        ) as mock_resolver_cls,
        patch("src.cli.data.sqlite3.connect"),
    ):
        mock_resolver_cls.return_value.resolve.return_value = mock_result
        result = runner.invoke(app, ["data", "resolve-opponents"])

    mock_load_config.assert_called_once_with(db_path=fake_db_path)
    assert result.exit_code == 0
