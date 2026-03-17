"""Tests for the ``bb proxy`` CLI sub-app (src/cli/proxy.py).

Tests use CliRunner to exercise argument mapping only -- actual script
execution is mocked. For bash-wrapped commands, subprocess.run is mocked
and the command list and cwd are verified. For refresh-headers,
src.http.proxy_refresh.run is mocked.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_completed_process(returncode: int = 0) -> MagicMock:
    mock = MagicMock()
    mock.returncode = returncode
    return mock


# ---------------------------------------------------------------------------
# bb proxy report
# ---------------------------------------------------------------------------


class TestProxyReport:
    """Argument mapping tests for ``bb proxy report``."""

    def _invoke(self, args: list[str], returncode: int = 0):
        with patch("src.cli.proxy.subprocess.run", return_value=_make_completed_process(returncode)) as mock_run:
            result = runner.invoke(app, args)
            return result, mock_run

    def test_report_no_flags_calls_script_with_no_extra_args(self) -> None:
        """``bb proxy report`` with no flags invokes proxy-report.sh with no extra args."""
        result, mock_run = self._invoke(["proxy", "report"])
        assert result.exit_code == 0
        call_kwargs = mock_run.call_args
        cmd = call_kwargs[0][0]
        assert cmd == ["scripts/proxy-report.sh"]
        assert call_kwargs[1]["cwd"] == _PROJECT_ROOT

    def test_report_session_flag_passes_session_id(self) -> None:
        """``--session abc123`` passes ['--session', 'abc123'] to the script."""
        result, mock_run = self._invoke(["proxy", "report", "--session", "abc123"])
        assert result.exit_code == 0
        cmd = mock_run.call_args[0][0]
        assert "--session" in cmd
        assert "abc123" in cmd

    def test_report_all_flag_passes_all(self) -> None:
        """``--all`` passes '--all' to the script."""
        result, mock_run = self._invoke(["proxy", "report", "--all"])
        assert result.exit_code == 0
        cmd = mock_run.call_args[0][0]
        assert "--all" in cmd

    def test_report_passes_exit_code_through(self) -> None:
        """Exit code from subprocess is passed through."""
        result, _ = self._invoke(["proxy", "report"], returncode=1)
        assert result.exit_code == 1

    def test_report_no_unreviewed_flag(self) -> None:
        """proxy report has no --unreviewed flag (unlike endpoints)."""
        result = runner.invoke(app, ["proxy", "report", "--unreviewed"])
        assert result.exit_code != 0

    def test_report_cwd_is_project_root(self) -> None:
        """cwd passed to subprocess.run equals the project root."""
        _, mock_run = self._invoke(["proxy", "report"])
        assert mock_run.call_args[1]["cwd"] == _PROJECT_ROOT


# ---------------------------------------------------------------------------
# bb proxy endpoints
# ---------------------------------------------------------------------------


class TestProxyEndpoints:
    """Argument mapping tests for ``bb proxy endpoints``."""

    def _invoke(self, args: list[str], returncode: int = 0):
        with patch("src.cli.proxy.subprocess.run", return_value=_make_completed_process(returncode)) as mock_run:
            result = runner.invoke(app, args)
            return result, mock_run

    def test_endpoints_no_flags_calls_script(self) -> None:
        """``bb proxy endpoints`` invokes proxy-endpoints.sh with no extra args."""
        result, mock_run = self._invoke(["proxy", "endpoints"])
        assert result.exit_code == 0
        cmd = mock_run.call_args[0][0]
        assert cmd == ["scripts/proxy-endpoints.sh"]

    def test_endpoints_session_flag(self) -> None:
        """``--session sess1`` passes ['--session', 'sess1'] to the script."""
        result, mock_run = self._invoke(["proxy", "endpoints", "--session", "sess1"])
        assert result.exit_code == 0
        cmd = mock_run.call_args[0][0]
        assert "--session" in cmd
        assert "sess1" in cmd

    def test_endpoints_all_flag(self) -> None:
        """``--all`` passes '--all' to the script."""
        result, mock_run = self._invoke(["proxy", "endpoints", "--all"])
        assert result.exit_code == 0
        cmd = mock_run.call_args[0][0]
        assert "--all" in cmd

    def test_endpoints_unreviewed_flag(self) -> None:
        """``--unreviewed`` passes '--unreviewed' to the script."""
        result, mock_run = self._invoke(["proxy", "endpoints", "--unreviewed"])
        assert result.exit_code == 0
        cmd = mock_run.call_args[0][0]
        assert "--unreviewed" in cmd

    def test_endpoints_passes_exit_code_through(self) -> None:
        """Exit code from subprocess is passed through."""
        result, _ = self._invoke(["proxy", "endpoints"], returncode=2)
        assert result.exit_code == 2

    def test_endpoints_cwd_is_project_root(self) -> None:
        """cwd passed to subprocess.run equals the project root."""
        _, mock_run = self._invoke(["proxy", "endpoints"])
        assert mock_run.call_args[1]["cwd"] == _PROJECT_ROOT


# ---------------------------------------------------------------------------
# bb proxy refresh-headers
# ---------------------------------------------------------------------------


class TestProxyRefreshHeaders:
    """Argument mapping tests for ``bb proxy refresh-headers``."""

    def _invoke(self, args: list[str], run_return: int = 0):
        mock_run = MagicMock(return_value=run_return)
        with patch("src.cli.proxy._run_refresh_headers", mock_run) as mock_patch:
            result = runner.invoke(app, args)
            return result, mock_patch

    def test_refresh_headers_default_is_dry_run(self) -> None:
        """``bb proxy refresh-headers`` with no flags calls run(apply=False)."""
        result, mock_run = self._invoke(["proxy", "refresh-headers"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(apply=False)

    def test_refresh_headers_apply_flag(self) -> None:
        """``--apply`` calls run(apply=True)."""
        result, mock_run = self._invoke(["proxy", "refresh-headers", "--apply"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(apply=True)

    def test_refresh_headers_passes_exit_code_through(self) -> None:
        """Exit code from run() is passed through."""
        result, _ = self._invoke(["proxy", "refresh-headers"], run_return=1)
        assert result.exit_code == 1

    def test_refresh_headers_calls_run_once(self) -> None:
        """_run_refresh_headers is called exactly once."""
        _, mock_run = self._invoke(["proxy", "refresh-headers"])
        mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# bb proxy review
# ---------------------------------------------------------------------------


class TestProxyReview:
    """Argument mapping tests for ``bb proxy review``."""

    def _invoke(self, args: list[str], returncode: int = 0):
        with patch("src.cli.proxy.subprocess.run", return_value=_make_completed_process(returncode)) as mock_run:
            result = runner.invoke(app, args)
            return result, mock_run

    def test_review_calls_proxy_review_sh(self) -> None:
        """``bb proxy review`` invokes scripts/proxy-review.sh."""
        result, mock_run = self._invoke(["proxy", "review"])
        assert result.exit_code == 0
        cmd = mock_run.call_args[0][0]
        assert cmd == ["scripts/proxy-review.sh"]

    def test_review_list_forwards_subcommand(self) -> None:
        """``bb proxy review list`` forwards 'list' to the script."""
        result, mock_run = self._invoke(["proxy", "review", "list"])
        assert result.exit_code == 0
        cmd = mock_run.call_args[0][0]
        assert cmd == ["scripts/proxy-review.sh", "list"]

    def test_review_mark_session_forwards_args(self) -> None:
        """``bb proxy review mark <session-id>`` forwards both args."""
        result, mock_run = self._invoke(["proxy", "review", "mark", "2026-03-06_204244"])
        assert result.exit_code == 0
        cmd = mock_run.call_args[0][0]
        assert cmd == ["scripts/proxy-review.sh", "mark", "2026-03-06_204244"]

    def test_review_mark_all_forwards_args(self) -> None:
        """``bb proxy review mark --all`` forwards both args."""
        result, mock_run = self._invoke(["proxy", "review", "mark", "--all"])
        assert result.exit_code == 0
        cmd = mock_run.call_args[0][0]
        assert cmd == ["scripts/proxy-review.sh", "mark", "--all"]

    def test_review_cwd_is_project_root(self) -> None:
        """cwd passed to subprocess.run equals the project root."""
        _, mock_run = self._invoke(["proxy", "review"])
        assert mock_run.call_args[1]["cwd"] == _PROJECT_ROOT

    def test_review_passes_exit_code_through(self) -> None:
        """Exit code from subprocess is passed through."""
        result, _ = self._invoke(["proxy", "review"], returncode=1)
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# bb proxy --help
# ---------------------------------------------------------------------------


class TestProxyHelp:
    def test_help_lists_all_five_commands(self) -> None:
        """``bb proxy --help`` lists all five sub-commands."""
        result = runner.invoke(app, ["proxy", "--help"])
        assert result.exit_code == 0
        assert "report" in result.output
        assert "endpoints" in result.output
        assert "refresh-headers" in result.output
        assert "review" in result.output
        assert "check" in result.output


# ---------------------------------------------------------------------------
# bb proxy check
# ---------------------------------------------------------------------------


class TestProxyCheck:
    """Tests for ``bb proxy check`` command."""

    def _invoke_check(
        self,
        direct_ip: str | None,
        profile_results: dict[str, object],
    ):
        """Invoke ``bb proxy check`` with mocked check logic.

        Args:
            direct_ip: Return value for ``get_direct_ip()``.
            profile_results: Maps profile name to ``ProxyCheckResult`` to return
                from ``check_proxy_routing()``.
        """
        from src.http.proxy_check import ProxyCheckOutcome, ProxyCheckResult

        def fake_check(profile: str, direct_ip_arg: str | None) -> ProxyCheckResult:
            return profile_results.get(
                profile,
                ProxyCheckResult(
                    profile=profile, outcome=ProxyCheckOutcome.NOT_CONFIGURED
                ),
            )

        with (
            patch("src.cli.proxy.get_direct_ip", return_value=direct_ip),
            patch("src.cli.proxy.check_proxy_routing", side_effect=fake_check),
        ):
            return runner.invoke(app, ["proxy", "check"])

    def test_check_always_exits_zero(self) -> None:
        """AC-5: ``bb proxy check`` always exits with code 0."""
        from src.http.proxy_check import ProxyCheckOutcome, ProxyCheckResult

        results = {
            "web": ProxyCheckResult(profile="web", outcome=ProxyCheckOutcome.FAIL),
            "mobile": ProxyCheckResult(profile="mobile", outcome=ProxyCheckOutcome.ERROR, error="refused"),
        }
        result = self._invoke_check("1.2.3.4", results)
        assert result.exit_code == 0

    def test_check_shows_pass_outcome(self) -> None:
        """AC-2: PASS outcome is displayed with both IPs."""
        from src.http.proxy_check import ProxyCheckOutcome, ProxyCheckResult

        results = {
            "web": ProxyCheckResult(
                profile="web",
                outcome=ProxyCheckOutcome.PASS,
                proxy_ip="5.6.7.8",
                direct_ip="1.2.3.4",
            ),
            "mobile": ProxyCheckResult(profile="mobile", outcome=ProxyCheckOutcome.NOT_CONFIGURED),
        }
        result = self._invoke_check("1.2.3.4", results)
        assert result.exit_code == 0
        assert "PASS" in result.output
        assert "5.6.7.8" in result.output

    def test_check_shows_fail_outcome(self) -> None:
        """AC-2: FAIL outcome is displayed when proxy IP matches direct IP."""
        from src.http.proxy_check import ProxyCheckOutcome, ProxyCheckResult

        results = {
            "web": ProxyCheckResult(
                profile="web",
                outcome=ProxyCheckOutcome.FAIL,
                proxy_ip="1.2.3.4",
                direct_ip="1.2.3.4",
            ),
            "mobile": ProxyCheckResult(profile="mobile", outcome=ProxyCheckOutcome.NOT_CONFIGURED),
        }
        result = self._invoke_check("1.2.3.4", results)
        assert result.exit_code == 0
        assert "FAIL" in result.output

    def test_check_shows_error_outcome(self) -> None:
        """AC-2, AC-7: ERROR outcome is displayed with descriptive message (not stack trace)."""
        from src.http.proxy_check import ProxyCheckOutcome, ProxyCheckResult

        results = {
            "web": ProxyCheckResult(
                profile="web",
                outcome=ProxyCheckOutcome.ERROR,
                error="connection refused",
            ),
            "mobile": ProxyCheckResult(profile="mobile", outcome=ProxyCheckOutcome.NOT_CONFIGURED),
        }
        result = self._invoke_check("1.2.3.4", results)
        assert result.exit_code == 0
        assert "ERROR" in result.output
        assert "connection refused" in result.output
        assert "Traceback" not in result.output

    def test_check_shows_pass_unverified_outcome(self) -> None:
        """AC-2: PASS-UNVERIFIED outcome is displayed when direct baseline is unavailable."""
        from src.http.proxy_check import ProxyCheckOutcome, ProxyCheckResult

        results = {
            "web": ProxyCheckResult(
                profile="web",
                outcome=ProxyCheckOutcome.PASS_UNVERIFIED,
                proxy_ip="5.6.7.8",
            ),
            "mobile": ProxyCheckResult(profile="mobile", outcome=ProxyCheckOutcome.NOT_CONFIGURED),
        }
        result = self._invoke_check(None, results)
        assert result.exit_code == 0
        assert "PASS-UNVERIFIED" in result.output
        assert "5.6.7.8" in result.output

    def test_check_shows_not_configured_when_proxy_disabled(self) -> None:
        """AC-3: NOT CONFIGURED is shown when proxy is not enabled."""
        from src.http.proxy_check import ProxyCheckOutcome, ProxyCheckResult

        results = {
            "web": ProxyCheckResult(profile="web", outcome=ProxyCheckOutcome.NOT_CONFIGURED),
            "mobile": ProxyCheckResult(profile="mobile", outcome=ProxyCheckOutcome.NOT_CONFIGURED),
        }
        result = self._invoke_check("1.2.3.4", results)
        assert result.exit_code == 0
        assert "NOT CONFIGURED" in result.output

    def test_check_shows_direct_ip_on_success(self) -> None:
        """AC-1: Direct IP is displayed when the baseline request succeeds."""
        from src.http.proxy_check import ProxyCheckOutcome, ProxyCheckResult

        results = {
            "web": ProxyCheckResult(profile="web", outcome=ProxyCheckOutcome.NOT_CONFIGURED),
            "mobile": ProxyCheckResult(profile="mobile", outcome=ProxyCheckOutcome.NOT_CONFIGURED),
        }
        result = self._invoke_check("1.2.3.4", results)
        assert "1.2.3.4" in result.output

    def test_check_handles_direct_ip_failure(self) -> None:
        """AC-2: If direct request fails, proxy results still displayed."""
        from src.http.proxy_check import ProxyCheckOutcome, ProxyCheckResult

        results = {
            "web": ProxyCheckResult(
                profile="web",
                outcome=ProxyCheckOutcome.PASS_UNVERIFIED,
                proxy_ip="5.6.7.8",
            ),
            "mobile": ProxyCheckResult(profile="mobile", outcome=ProxyCheckOutcome.NOT_CONFIGURED),
        }
        result = self._invoke_check(None, results)
        assert result.exit_code == 0
        assert "FAILED" in result.output or "network error" in result.output.lower()
        assert "PASS-UNVERIFIED" in result.output
