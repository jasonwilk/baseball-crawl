"""Tests for bb report CLI commands (E-172-02)."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from src.cli.report import app
from src.reports.generator import CleanupResult, GenerationResult

runner = CliRunner()


class TestGenerateCommand:
    """Test bb report generate CLI command."""

    def test_success_prints_url(self):
        mock_result = GenerationResult(
            success=True,
            slug="abc123def456",
            title="Scouting Report — Test Tigers",
            url="https://bbstats.ai/reports/abc123def456",
            outcome="ready",
        )
        with patch("src.cli.report.generate_report", return_value=mock_result):
            result = runner.invoke(app, ["generate", "https://web.gc.com/teams/test/tigers"])

        assert result.exit_code == 0
        assert "abc123def456" in result.output
        assert "https://bbstats.ai/reports/abc123def456" in result.output
        assert "Test Tigers" in result.output

    def test_failure_prints_error_and_exits_1(self):
        mock_result = GenerationResult(
            success=False,
            error_message="Scouting crawl failed.",
            outcome="failed",
        )
        with patch("src.cli.report.generate_report", return_value=mock_result):
            result = runner.invoke(app, ["generate", "abc123"])

        assert result.exit_code == 1
        assert "Scouting crawl failed" in result.output

    def test_no_games_m_zero_exits_zero_and_prints_url(self):
        """E-236-05 AC-4/AC-6 + Phase 4b MEDIUM: a no_games outcome is a
        shareable page, so the CLI exits 0 and prints the URL. M=0 (no games on
        record) reads as such."""
        mock_result = GenerationResult(
            success=False,
            slug="ng123",
            title="Scouting Report — Rival Varsity",
            url="https://bbstats.ai/reports/ng123",
            error_message=(
                "No completed games found for Rival Varsity this season. "
                "If this looks wrong, verify the team URL and try again."
            ),
            outcome="no_games",
            completed_games=0,
            completed_games_with_data=0,
        )
        with patch("src.cli.report.generate_report", return_value=mock_result):
            result = runner.invoke(app, ["generate", "abc123"])

        assert result.exit_code == 0
        assert "https://bbstats.ai/reports/ng123" in result.output
        assert "No games on record" in result.output

    def test_no_games_m_positive_says_no_box_score_data(self):
        """Phase 4b MEDIUM: the modal M>0/N=0 case (games WERE played, box-score
        data missing) must NOT print the misleading 'No completed games found'
        line; it must convey games played + no box score data, exit 0 + URL."""
        mock_result = GenerationResult(
            success=False,
            slug="ng456",
            title="Scouting Report — Rival Varsity",
            url="https://bbstats.ai/reports/ng456",
            error_message=(
                "No completed games found for Rival Varsity this season. "
                "If this looks wrong, verify the team URL and try again."
            ),
            outcome="no_games",
            completed_games=8,
            completed_games_with_data=0,
        )
        with patch("src.cli.report.generate_report", return_value=mock_result):
            result = runner.invoke(app, ["generate", "abc123"])

        assert result.exit_code == 0
        assert "https://bbstats.ai/reports/ng456" in result.output
        # Honest M-vs-N message: games played, box-score data missing.
        assert "Played 8 games this season" in result.output
        assert "no box score data" in result.output
        # Must NOT print the misleading "no completed games found" for M>0.
        assert "No completed games found" not in result.output

    def test_credential_error_prints_refresh_hint(self):
        mock_result = GenerationResult(
            success=False,
            slug="some-slug",
            error_message="Authentication credentials expired — refresh with `bb creds setup web`",
        )
        with patch("src.cli.report.generate_report", return_value=mock_result):
            result = runner.invoke(app, ["generate", "abc123"])

        assert result.exit_code == 1
        assert "bb creds setup web" in result.output


class TestListCommand:
    """Test bb report list CLI command."""

    def test_list_shows_table(self):
        mock_reports = [
            {
                "slug": "s1",
                "title": "Report A",
                "status": "ready",
                "generated_at": "2026-03-28T12:00:00Z",
                "expires_at": "2026-04-11T12:00:00Z",
                "url": "https://bbstats.ai/reports/s1",
                "is_expired": False,
            },
        ]
        with patch("src.cli.report.list_reports", return_value=mock_reports):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "Report A" in result.output
        assert "ready" in result.output

    def test_list_shows_expired_label(self):
        mock_reports = [
            {
                "slug": "old",
                "title": "Old Report",
                "status": "ready",
                "generated_at": "2026-01-01T12:00:00Z",
                "expires_at": "2026-01-15T12:00:00Z",
                "url": "https://bbstats.ai/reports/old",
                "is_expired": True,
            },
        ]
        with patch("src.cli.report.list_reports", return_value=mock_reports):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "expired" in result.output

    def test_list_empty(self):
        with patch("src.cli.report.list_reports", return_value=[]):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "No reports found" in result.output

    def test_no_games_report_shows_shareable_url(self):
        """Phase 4b MEDIUM-2: a no_games report exposes its URL (shareable
        page), while a failed report does not. A wide console avoids Rich
        truncating the URL cell."""
        from rich.console import Console

        mock_reports = [
            {
                "slug": "ng1", "title": "No Games Report", "status": "no_games",
                "generated_at": "2026-03-28T12:00:00Z",
                "expires_at": "2026-04-11T12:00:00Z",
                "url": "https://bbstats.ai/reports/ng1", "is_expired": False,
            },
            {
                "slug": "f1", "title": "Failed Report", "status": "failed",
                "generated_at": "2026-03-28T12:00:00Z",
                "expires_at": "2026-04-11T12:00:00Z",
                "url": "https://bbstats.ai/reports/f1", "is_expired": False,
            },
        ]
        with (
            patch("src.cli.report.list_reports", return_value=mock_reports),
            patch("src.cli.report.console", Console(width=200)),
        ):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "reports/ng1" in result.output  # no_games link shown
        assert "reports/f1" not in result.output  # failed stays unlinked

    def test_help_text(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "report" in result.output.lower()


class TestCleanupCommand:
    """Test bb report cleanup CLI command (E-238-07)."""

    def test_cleanup_reports_files_removed(self):
        """AC-4: the command invokes the helper and reports the file count."""
        with patch(
            "src.cli.report.cleanup_expired_reports",
            return_value=CleanupResult(files_removed=3, errors=0),
        ) as mock_cleanup:
            result = runner.invoke(app, ["cleanup"])

        mock_cleanup.assert_called_once()
        assert result.exit_code == 0
        assert "3" in result.output
        assert "removed" in result.output.lower()

    def test_cleanup_reports_zero(self):
        """A no-op sweep (nothing expired) still exits 0 and reports 0."""
        with patch(
            "src.cli.report.cleanup_expired_reports",
            return_value=CleanupResult(files_removed=0, errors=0),
        ):
            result = runner.invoke(app, ["cleanup"])

        assert result.exit_code == 0
        assert "0" in result.output

    def test_cleanup_reports_errors(self):
        """Per-file errors are surfaced (without failing the command)."""
        with patch(
            "src.cli.report.cleanup_expired_reports",
            return_value=CleanupResult(files_removed=1, errors=2),
        ):
            result = runner.invoke(app, ["cleanup"])

        assert result.exit_code == 0
        assert "1" in result.output
        assert "2" in result.output

    def test_cleanup_helper_failure_surfaces_nonzero_exit(self):
        """Error path: if the helper raises, the command exits non-zero.

        ``bb report cleanup`` is an explicit operator action (unlike the
        opportunistic call), so a hard failure should not be silently
        swallowed -- the operator must see it.
        """
        with patch(
            "src.cli.report.cleanup_expired_reports",
            side_effect=RuntimeError("db unavailable"),
        ):
            result = runner.invoke(app, ["cleanup"])

        assert result.exit_code != 0
        assert result.exception is not None

    def test_cleanup_help(self):
        result = runner.invoke(app, ["cleanup", "--help"])
        assert result.exit_code == 0
        assert "expired" in result.output.lower()
