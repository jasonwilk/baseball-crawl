"""Tests for E-069-01: double production guard fix and root logger mutation fix.

AC-1: production, no --force -> exactly one logger.error, no Rich duplicate, no prompt, exit 1
AC-2: production, --force -> exactly one logger.warning, no duplicate, reset proceeds
AC-3: importing src.db.reset does not mutate logging.root.handlers (subprocess)
AC-4: importing migrations.apply_migrations does not mutate logging.root.handlers (subprocess)
AC-5: python migrations/apply_migrations.py directly still uses [migrations] log format
AC-6: all existing tests pass (enforced by running the full suite)
AC-7: reset_database() accepts _skip_guard: bool = False; skips guard when True
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.db.reset import check_production_guard, reset_database

runner = CliRunner()

# ---------------------------------------------------------------------------
# AC-1: production + no --force -> single logger.error, no Rich duplicate, exit 1
# ---------------------------------------------------------------------------


def test_ac1_production_no_force_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    """APP_ENV=production without --force exits non-zero."""
    monkeypatch.setenv("APP_ENV", "production")
    with patch("src.cli.db.reset_database", return_value=(5, 42)):
        result = runner.invoke(app, ["db", "reset"])
    assert result.exit_code == 1


def test_ac1_production_no_force_single_error_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Exactly one ERROR log record is emitted by check_production_guard."""
    monkeypatch.setenv("APP_ENV", "production")
    with patch("src.cli.db.reset_database", return_value=(5, 42)):
        with caplog.at_level(logging.ERROR, logger="src.db.reset"):
            runner.invoke(app, ["db", "reset"])
    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(error_records) == 1, f"Expected 1 ERROR record, got {len(error_records)}"
    assert "production" in error_records[0].message.lower()


def test_ac1_production_no_force_no_rich_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    """No duplicate Rich-formatted error message in stdout (removed from CLI)."""
    monkeypatch.setenv("APP_ENV", "production")
    with patch("src.cli.db.reset_database", return_value=(5, 42)):
        result = runner.invoke(app, ["db", "reset"])
    # The Rich wrapper that said "APP_ENV=production detected..." was removed.
    # stdout should be empty (guard exits via sys.exit, not Rich print).
    assert "APP_ENV=production detected" not in result.output


def test_ac1_production_no_force_prompt_does_not_appear(monkeypatch: pytest.MonkeyPatch) -> None:
    """Confirmation prompt does NOT appear; guard blocks first."""
    monkeypatch.setenv("APP_ENV", "production")
    with patch("src.cli.db.reset_database", return_value=(5, 42)):
        result = runner.invoke(app, ["db", "reset"])
    assert "Confirm?" not in result.output


# ---------------------------------------------------------------------------
# AC-2: production + --force -> single logger.warning, no duplicate, reset proceeds
# ---------------------------------------------------------------------------


def test_ac2_production_force_exits_0(monkeypatch: pytest.MonkeyPatch) -> None:
    """APP_ENV=production with --force exits 0 (reset proceeds)."""
    monkeypatch.setenv("APP_ENV", "production")
    with patch("src.cli.db.reset_database", return_value=(5, 42)):
        result = runner.invoke(app, ["db", "reset", "--force"])
    assert result.exit_code == 0


def test_ac2_production_force_single_warning_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Exactly one WARNING log record is emitted by check_production_guard."""
    monkeypatch.setenv("APP_ENV", "production")
    with patch("src.cli.db.reset_database", return_value=(5, 42)):
        with caplog.at_level(logging.WARNING, logger="src.db.reset"):
            runner.invoke(app, ["db", "reset", "--force"])
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 1, (
        f"Expected 1 WARNING record, got {len(warning_records)}: "
        f"{[r.message for r in warning_records]}"
    )


def test_ac2_production_force_no_duplicate_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """With _skip_guard=True, reset_database does not call check_production_guard again."""
    monkeypatch.setenv("APP_ENV", "production")
    # Capture all WARNING+ records from the reset logger.
    with caplog.at_level(logging.WARNING, logger="src.db.reset"):
        with patch("src.cli.db.reset_database", return_value=(5, 42)) as mock_fn:
            runner.invoke(app, ["db", "reset", "--force"])
    # reset_database is mocked, so the only warning comes from the CLI's guard call.
    mock_fn.assert_called_once_with(db_path=None, force=True, _skip_guard=True)
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 1


# ---------------------------------------------------------------------------
# AC-3: importing src.db.reset does not mutate logging.root.handlers (subprocess)
# ---------------------------------------------------------------------------


def test_ac3_import_src_db_reset_no_root_handler_mutation() -> None:
    """Importing src.db.reset in a fresh process must not add root logger handlers."""
    code = (
        "import logging; "
        "from src.db.reset import reset_database; "
        "handlers = logging.root.handlers; "
        "print(len(handlers))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert result.returncode == 0, f"Subprocess failed:\n{result.stderr}"
    handler_count = int(result.stdout.strip())
    assert handler_count == 0, (
        f"Expected 0 root handlers after import, got {handler_count}. "
        f"stderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# AC-4: importing migrations.apply_migrations does not mutate root logger (subprocess)
# ---------------------------------------------------------------------------


def test_ac4_import_apply_migrations_no_root_handler_mutation() -> None:
    """Importing migrations.apply_migrations in a fresh process must not add root handlers."""
    code = (
        "import logging; "
        "from migrations.apply_migrations import run_migrations; "
        "handlers = logging.root.handlers; "
        "print(len(handlers))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert result.returncode == 0, f"Subprocess failed:\n{result.stderr}"
    handler_count = int(result.stdout.strip())
    assert handler_count == 0, (
        f"Expected 0 root handlers after import, got {handler_count}. "
        f"stderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# AC-5: running apply_migrations.py directly still uses [migrations] format
# ---------------------------------------------------------------------------


def test_ac5_direct_execution_uses_migrations_log_format(tmp_path: Path) -> None:
    """Running apply_migrations.py directly produces [migrations] log output."""
    db_path = tmp_path / "test.db"
    result = subprocess.run(
        [sys.executable, "migrations/apply_migrations.py"],
        capture_output=True,
        text=True,
        env={
            **__import__("os").environ,
            "DATABASE_PATH": str(db_path),
        },
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert result.returncode == 0, f"Script failed:\n{result.stderr}"
    combined = result.stdout + result.stderr
    assert "[migrations]" in combined, (
        f"Expected [migrations] format marker in output, got:\n{combined}"
    )


# ---------------------------------------------------------------------------
# AC-7: reset_database accepts _skip_guard parameter; skips guard when True
# ---------------------------------------------------------------------------


def test_ac7_reset_database_has_skip_guard_parameter() -> None:
    """reset_database() accepts _skip_guard keyword argument."""
    import inspect

    sig = inspect.signature(reset_database)
    assert "_skip_guard" in sig.parameters, (
        "reset_database() must have a _skip_guard parameter"
    )
    assert sig.parameters["_skip_guard"].default is False, (
        "_skip_guard default must be False"
    )


def test_ac7_skip_guard_true_bypasses_internal_guard(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """When _skip_guard=True, check_production_guard is not called by reset_database."""
    monkeypatch.setenv("APP_ENV", "production")
    # With _skip_guard=True in production (no force), reset_database should NOT
    # call the guard internally.  It will still try to delete/reset the DB, so
    # we need to mock the underlying operations.
    with (
        patch("src.db.reset.delete_database"),
        patch("src.db.reset._run_migrations_and_count", return_value=3),
        patch("src.db.reset.load_seed", return_value=10),
        caplog.at_level(logging.ERROR, logger="src.db.reset"),
    ):
        tables, rows = reset_database(db_path=Path("/tmp/test.db"), force=False, _skip_guard=True)
    assert tables == 3
    assert rows == 10
    # No ERROR log should have been emitted (guard was skipped).
    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(error_records) == 0, (
        f"Unexpected ERROR records with _skip_guard=True: {[r.message for r in error_records]}"
    )


def test_ac7_skip_guard_false_default_calls_guard_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When _skip_guard is omitted (default False), production guard fires."""
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(SystemExit) as exc_info:
        reset_database(db_path=Path("/tmp/test.db"), force=False)
    assert exc_info.value.code == 1


def test_ac7_cli_passes_skip_guard_true_to_reset_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI passes _skip_guard=True so the internal guard is skipped."""
    monkeypatch.delenv("APP_ENV", raising=False)
    with patch("src.cli.db.reset_database", return_value=(4, 20)) as mock_fn:
        result = runner.invoke(app, ["db", "reset", "--force"])
    assert result.exit_code == 0
    mock_fn.assert_called_once_with(db_path=None, force=True, _skip_guard=True)
