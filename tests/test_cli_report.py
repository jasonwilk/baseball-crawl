"""Tests for bb report CLI commands (E-172-02)."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from src.cli.report import app
from src.reports.generator import GenerationResult

runner = CliRunner()


class TestGenerateCommand:
    """Test bb report generate CLI command."""

    def test_success_prints_url(self):
        mock_result = GenerationResult(
            success=True,
            slug="abc123def456",
            title="Scouting Report — Test Tigers",
            url="https://bbstats.ai/reports/abc123def456",
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
        )
        with patch("src.cli.report.generate_report", return_value=mock_result):
            result = runner.invoke(app, ["generate", "abc123"])

        assert result.exit_code == 1
        assert "Scouting crawl failed" in result.output

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

    def test_help_text(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "report" in result.output.lower()
