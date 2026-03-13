"""Tests for scripts/check_codex_rtk.py.

All subprocess calls are mocked -- no live network or real RTK invocations.
Binary presence checks use a temporary directory fixture.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the helpers under test directly from the script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_codex_rtk import (
    _REPO_ROOT,
    check_binary_present,
    resolve_rtk_binary,
    run_rtk_check,
    main,
)


# ---------------------------------------------------------------------------
# resolve_rtk_binary
# ---------------------------------------------------------------------------


def test_resolve_rtk_binary_default_path():
    """resolve_rtk_binary() returns a path under .tools/rtk/."""
    path = resolve_rtk_binary()
    assert path.parts[-3:] == (".tools", "rtk", "rtk")


def test_resolve_rtk_binary_custom_root(tmp_path: Path):
    """resolve_rtk_binary() uses the supplied repo_root override."""
    path = resolve_rtk_binary(repo_root=tmp_path)
    assert path == tmp_path / ".tools" / "rtk" / "rtk"


# ---------------------------------------------------------------------------
# check_binary_present
# ---------------------------------------------------------------------------


def test_check_binary_present_missing(tmp_path: Path):
    """Returns False when the binary does not exist."""
    ok, msg = check_binary_present(tmp_path / "rtk")
    assert ok is False
    assert "not found" in msg


def test_check_binary_present_not_a_file(tmp_path: Path):
    """Returns False when the path is a directory, not a file."""
    rtk_dir = tmp_path / "rtk"
    rtk_dir.mkdir()
    ok, msg = check_binary_present(rtk_dir)
    assert ok is False
    assert "not a regular file" in msg


def test_check_binary_present_not_executable(tmp_path: Path):
    """Returns False when the file exists but is not executable."""
    rtk_bin = tmp_path / "rtk"
    rtk_bin.write_bytes(b"fake binary")
    rtk_bin.chmod(0o644)  # readable, not executable
    ok, msg = check_binary_present(rtk_bin)
    assert ok is False
    assert "not executable" in msg


def test_check_binary_present_happy_path(tmp_path: Path):
    """Returns True when the binary exists and is executable."""
    rtk_bin = tmp_path / "rtk"
    rtk_bin.write_bytes(b"fake binary")
    rtk_bin.chmod(0o755)
    ok, msg = check_binary_present(rtk_bin)
    assert ok is True
    assert str(rtk_bin) in msg


# ---------------------------------------------------------------------------
# run_rtk_check
# ---------------------------------------------------------------------------


def _make_completed_process(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_run_rtk_check_version_success(tmp_path: Path):
    """Returns True and the first output line on a successful --version call."""
    rtk_bin = tmp_path / "rtk"
    with patch("check_codex_rtk.subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(stdout="rtk 0.29.0\n")
        ok, msg = run_rtk_check(rtk_bin, ["--version"])

    assert ok is True
    assert msg == "rtk 0.29.0"
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert call_args[-1] == "--version"


def test_run_rtk_check_git_status_success(tmp_path: Path):
    """Returns True and the first output line on a successful git status call."""
    rtk_bin = tmp_path / "rtk"
    with patch("check_codex_rtk.subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            stdout="On branch main\nYour branch is up to date.\n"
        )
        ok, msg = run_rtk_check(rtk_bin, ["git", "status"])

    assert ok is True
    assert msg == "On branch main"
    assert mock_run.call_args.kwargs.get("cwd") == _REPO_ROOT


def test_run_rtk_check_accepts_stderr_output(tmp_path: Path):
    """Returns True when output arrives on stderr instead of stdout."""
    rtk_bin = tmp_path / "rtk"
    with patch("check_codex_rtk.subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(stderr="rtk 0.29.0\n")
        ok, msg = run_rtk_check(rtk_bin, ["--version"])

    assert ok is True
    assert "0.29.0" in msg


def test_run_rtk_check_nonzero_exit(tmp_path: Path):
    """Returns False when the command exits with a nonzero code."""
    rtk_bin = tmp_path / "rtk"
    with patch("check_codex_rtk.subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(returncode=1, stderr="error\n")
        ok, msg = run_rtk_check(rtk_bin, ["--version"])

    assert ok is False
    assert "exited 1" in msg


def test_run_rtk_check_no_output(tmp_path: Path):
    """Returns False when the command succeeds but produces no output."""
    rtk_bin = tmp_path / "rtk"
    with patch("check_codex_rtk.subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(returncode=0)
        ok, msg = run_rtk_check(rtk_bin, ["git", "status"])

    assert ok is False
    assert "no output" in msg


def test_run_rtk_check_file_not_found(tmp_path: Path):
    """Returns False when the binary cannot be found by the OS."""
    rtk_bin = tmp_path / "rtk"
    with patch("check_codex_rtk.subprocess.run", side_effect=FileNotFoundError):
        ok, msg = run_rtk_check(rtk_bin, ["--version"])

    assert ok is False
    assert "not found" in msg


def test_run_rtk_check_timeout(tmp_path: Path):
    """Returns False when the subprocess times out."""
    rtk_bin = tmp_path / "rtk"
    with patch(
        "check_codex_rtk.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=[], timeout=15),
    ):
        ok, msg = run_rtk_check(rtk_bin, ["git", "status"])

    assert ok is False
    assert "timed out" in msg


def test_run_rtk_check_permission_error(tmp_path: Path):
    """Returns False when the binary is not executable."""
    rtk_bin = tmp_path / "rtk"
    with patch(
        "check_codex_rtk.subprocess.run",
        side_effect=PermissionError,
    ):
        ok, msg = run_rtk_check(rtk_bin, ["--version"])

    assert ok is False
    assert "not executable" in msg


# ---------------------------------------------------------------------------
# main() integration
# ---------------------------------------------------------------------------


def test_main_all_checks_pass(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """main() exits 0 and logs [OK  ] lines when all checks pass."""
    rtk_bin = tmp_path / "rtk"
    rtk_bin.write_bytes(b"fake binary")
    rtk_bin.chmod(0o755)

    with caplog.at_level(logging.INFO, logger="check_codex_rtk"), patch(
        "check_codex_rtk.resolve_rtk_binary", return_value=rtk_bin
    ), patch("check_codex_rtk.subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(stdout="rtk 0.29.0\n")
        exit_code = main()

    assert exit_code == 0
    assert "[OK  ]" in caplog.text
    assert "FAIL" not in caplog.text
    assert mock_run.call_args.kwargs.get("cwd") == _REPO_ROOT


def test_main_binary_missing(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """main() exits 1 and logs [FAIL] when the binary is absent."""
    rtk_bin = tmp_path / "rtk"  # does not exist

    with caplog.at_level(logging.ERROR, logger="check_codex_rtk"), patch(
        "check_codex_rtk.resolve_rtk_binary", return_value=rtk_bin
    ):
        exit_code = main()

    assert exit_code == 1
    assert "[FAIL]" in caplog.text


def test_main_binary_not_executable(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """main() exits 1 and logs [FAIL] when binary exists but is not executable."""
    rtk_bin = tmp_path / "rtk"
    rtk_bin.write_bytes(b"fake binary")
    rtk_bin.chmod(0o644)  # readable, not executable

    with caplog.at_level(logging.ERROR, logger="check_codex_rtk"), patch(
        "check_codex_rtk.resolve_rtk_binary", return_value=rtk_bin
    ):
        exit_code = main()

    assert exit_code == 1
    assert "[FAIL]" in caplog.text
    assert "not executable" in caplog.text


def test_main_version_check_fails(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """main() exits 1 and logs [FAIL] when --version returns a nonzero exit code."""
    rtk_bin = tmp_path / "rtk"
    rtk_bin.write_bytes(b"fake binary")
    rtk_bin.chmod(0o755)

    with caplog.at_level(logging.ERROR, logger="check_codex_rtk"), patch(
        "check_codex_rtk.resolve_rtk_binary", return_value=rtk_bin
    ), patch("check_codex_rtk.subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(returncode=1, stderr="err\n")
        exit_code = main()

    assert exit_code == 1
    assert "[FAIL]" in caplog.text
