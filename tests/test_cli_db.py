"""Tests for the ``bb db`` CLI sub-app (src/cli/db.py).

Tests use CliRunner to exercise argument mapping only -- database operations
(backup, migrations, seeding) are mocked.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# bb db backup
# ---------------------------------------------------------------------------


class TestDbBackup:
    """Argument mapping tests for ``bb db backup``."""

    _BACKUP_PATH = Path("/data/backups/app-2026-01-01T000000.db")

    def test_backup_success_exit_0(self) -> None:
        """Successful backup exits 0."""
        with patch("src.cli.db.backup_database", return_value=self._BACKUP_PATH) as mock_fn:
            result = runner.invoke(app, ["db", "backup"])
        assert result.exit_code == 0
        mock_fn.assert_called_once_with(db_path=None)

    def test_backup_prints_backup_path(self) -> None:
        """Output contains the path to the backup file."""
        with patch("src.cli.db.backup_database", return_value=self._BACKUP_PATH):
            result = runner.invoke(app, ["db", "backup"])
        assert str(self._BACKUP_PATH) in result.output

    def test_backup_db_path_flag_passed_through(self, tmp_path: Path) -> None:
        """--db-path flag is forwarded to backup_database."""
        db_file = tmp_path / "custom.db"
        with patch("src.cli.db.backup_database", return_value=self._BACKUP_PATH) as mock_fn:
            result = runner.invoke(app, ["db", "backup", "--db-path", str(db_file)])
        assert result.exit_code == 0
        mock_fn.assert_called_once_with(db_path=db_file)

    def test_backup_file_not_found_exits_1(self) -> None:
        """FileNotFoundError from backup_database exits 1 with actionable message."""
        with patch(
            "src.cli.db.backup_database",
            side_effect=FileNotFoundError("Database not found: /data/app.db"),
        ):
            result = runner.invoke(app, ["db", "backup"])
        assert result.exit_code == 1

    def test_backup_file_not_found_message_hints_sync(self) -> None:
        """Error output mentions the actual path and running ``bb data sync``."""
        with patch(
            "src.cli.db.backup_database",
            side_effect=FileNotFoundError("Database not found: /data/app.db"),
        ):
            result = runner.invoke(app, ["db", "backup"])
        assert "bb data sync" in result.output
        assert "Database not found: /data/app.db" in result.output


# ---------------------------------------------------------------------------
# bb db reset
# ---------------------------------------------------------------------------


class TestDbReset:
    """Argument mapping tests for ``bb db reset``."""

    def test_reset_with_force_skips_confirmation(self) -> None:
        """--force bypasses the confirmation prompt and exits 0."""
        with patch("src.cli.db.reset_database", return_value=(5, 42)) as mock_fn:
            result = runner.invoke(app, ["db", "reset", "--force"])
        assert result.exit_code == 0
        mock_fn.assert_called_once_with(db_path=None, force=True)

    def test_reset_prints_summary_on_success(self) -> None:
        """Output contains tables created and rows inserted counts."""
        with patch("src.cli.db.reset_database", return_value=(5, 42)):
            result = runner.invoke(app, ["db", "reset", "--force"])
        assert "5" in result.output
        assert "42" in result.output

    def test_reset_db_path_flag_passed_through(self, tmp_path: Path) -> None:
        """--db-path flag is forwarded to reset_database."""
        db_file = tmp_path / "custom.db"
        with patch("src.cli.db.reset_database", return_value=(3, 10)) as mock_fn:
            result = runner.invoke(app, ["db", "reset", "--force", "--db-path", str(db_file)])
        assert result.exit_code == 0
        mock_fn.assert_called_once_with(db_path=db_file, force=True)

    def test_reset_without_force_triggers_confirmation_prompt(self) -> None:
        """Without --force, the confirmation prompt appears."""
        with patch("src.cli.db.reset_database", return_value=(5, 42)):
            # Provide "y" to confirm.
            result = runner.invoke(app, ["db", "reset"], input="y\n")
        assert "Confirm?" in result.output

    def test_reset_without_force_confirm_yes_proceeds(self) -> None:
        """Answering 'y' to the prompt proceeds to reset."""
        with patch("src.cli.db.reset_database", return_value=(5, 42)) as mock_fn:
            result = runner.invoke(app, ["db", "reset"], input="y\n")
        assert result.exit_code == 0
        mock_fn.assert_called_once()

    def test_reset_without_force_confirm_no_aborts(self) -> None:
        """Answering 'n' (default) aborts without calling reset_database."""
        with patch("src.cli.db.reset_database", return_value=(5, 42)) as mock_fn:
            result = runner.invoke(app, ["db", "reset"], input="n\n")
        assert result.exit_code != 0
        mock_fn.assert_not_called()

    def test_reset_production_guard_without_force_exits_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """APP_ENV=production without --force exits 1 before the confirmation prompt."""
        monkeypatch.setenv("APP_ENV", "production")
        with patch("src.cli.db.reset_database", return_value=(5, 42)) as mock_fn:
            result = runner.invoke(app, ["db", "reset"])
        assert result.exit_code == 1
        mock_fn.assert_not_called()

    def test_reset_production_guard_fires_before_prompt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Production guard output appears; confirmation prompt does NOT."""
        monkeypatch.setenv("APP_ENV", "production")
        with patch("src.cli.db.reset_database", return_value=(5, 42)):
            result = runner.invoke(app, ["db", "reset"])
        assert "production" in result.output.lower() or "APP_ENV" in result.output
        assert "Confirm?" not in result.output

    def test_reset_production_with_force_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """APP_ENV=production with --force bypasses guard and confirmation."""
        monkeypatch.setenv("APP_ENV", "production")
        with patch("src.cli.db.reset_database", return_value=(5, 42)) as mock_fn:
            result = runner.invoke(app, ["db", "reset", "--force"])
        assert result.exit_code == 0
        mock_fn.assert_called_once_with(db_path=None, force=True)

    def test_reset_file_not_found_exits_1(self) -> None:
        """FileNotFoundError (missing seed file) exits 1."""
        with patch(
            "src.cli.db.reset_database",
            side_effect=FileNotFoundError("Seed file not found: /data/seeds/seed_dev.sql"),
        ):
            result = runner.invoke(app, ["db", "reset", "--force"])
        assert result.exit_code == 1

    def test_reset_system_exit_propagated(self) -> None:
        """SystemExit raised by reset_database is converted to a non-zero Typer exit."""
        with patch("src.cli.db.reset_database", side_effect=SystemExit(1)):
            result = runner.invoke(app, ["db", "reset", "--force"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# bb db --help
# ---------------------------------------------------------------------------


class TestDbHelp:
    def test_help_lists_backup_and_reset(self) -> None:
        """``bb db --help`` lists both backup and reset sub-commands."""
        result = runner.invoke(app, ["db", "--help"])
        assert result.exit_code == 0
        assert "backup" in result.output
        assert "reset" in result.output
