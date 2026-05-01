"""Tests for E-228-01 CLI: ``bb report generate --our-team`` flag.

Covers AC-7, AC-8, AC-9 and the corresponding test ACs (AC-T5, AC-T6).

Two test paths:

1. **Subprocess smoke** (AC-T5): runs ``bb report generate --help`` via
   ``subprocess.run`` and asserts ``--our-team`` appears in the output.
   This catches packaging/import errors that the in-process Typer test
   runner masks (per ``.claude/rules/testing.md``).
2. **In-process flag parsing** (AC-T6): exercises the resolution helper +
   typer ``CliRunner`` to verify success and error paths.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from migrations.apply_migrations import run_migrations
from src.cli.report import app, resolve_our_team
from src.reports.generator import GenerationResult


runner = CliRunner()


# ---------------------------------------------------------------------------
# AC-T5: subprocess smoke -- catches packaging/import regressions
# ---------------------------------------------------------------------------


class TestSubprocessSmoke:
    """``bb report generate --help`` exits 0 and lists ``--our-team``."""

    def test_bb_report_generate_help_lists_our_team_flag(self):
        bb = shutil.which("bb")
        if bb is None:
            pytest.skip("'bb' CLI is not on PATH (editable install required)")

        # Use the same Python environment in the subprocess
        result = subprocess.run(
            [bb, "report", "generate", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, (
            f"bb report generate --help exited {result.returncode}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        # The flag must appear in --help output.  Typer renders flags with
        # any of several decorations (``--our-team``, ``--our_team``, etc.);
        # match the canonical form documented in the story.
        assert "--our-team" in result.stdout, (
            f"--our-team flag not found in help output:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# AC-T6: in-process flag parsing via Typer's CliRunner
# ---------------------------------------------------------------------------


class TestFlagParsingInProcess:
    """``--our-team`` resolves and routes to ``generate_report`` correctly."""

    def _make_success_result(self) -> GenerationResult:
        return GenerationResult(
            success=True,
            slug="abc123def456",
            title="Scouting Report — Subject",
            url="http://localhost:8001/reports/abc123def456",
        )

    def test_no_flag_preserves_existing_behavior(self, monkeypatch):
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")
        result_value = self._make_success_result()
        with patch(
            "src.cli.report.generate_report", return_value=result_value,
        ) as mock_gen:
            result = runner.invoke(app, ["generate", "abc123"])

        assert result.exit_code == 0
        # Flag absent -> our_team_id=None
        mock_gen.assert_called_once_with("abc123", our_team_id=None)

    def test_flag_with_integer_id_resolves_via_int_path(self, monkeypatch):
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")
        result_value = self._make_success_result()
        with patch(
            "src.cli.report.resolve_our_team", return_value=42,
        ) as mock_resolve, patch(
            "src.cli.report.generate_report", return_value=result_value,
        ) as mock_gen:
            result = runner.invoke(
                app, ["generate", "abc123", "--our-team", "42"],
            )

        assert result.exit_code == 0
        mock_resolve.assert_called_once_with("42")
        mock_gen.assert_called_once_with("abc123", our_team_id=42)

    def test_flag_with_public_id_resolves_via_lookup(self, monkeypatch):
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")
        result_value = self._make_success_result()
        with patch(
            "src.cli.report.resolve_our_team", return_value=7,
        ) as mock_resolve, patch(
            "src.cli.report.generate_report", return_value=result_value,
        ) as mock_gen:
            result = runner.invoke(
                app, ["generate", "abc123", "--our-team", "lsb-varsity"],
            )

        assert result.exit_code == 0
        mock_resolve.assert_called_once_with("lsb-varsity")
        mock_gen.assert_called_once_with("abc123", our_team_id=7)

    def test_flag_with_unknown_value_exits_non_zero(self, monkeypatch):
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")
        with patch(
            "src.cli.report.resolve_our_team", return_value=None,
        ), patch(
            "src.cli.report.generate_report",
        ) as mock_gen:
            result = runner.invoke(
                app, ["generate", "abc123", "--our-team", "ghost-team"],
            )

        assert result.exit_code != 0
        # generate_report must not be called when resolution fails.
        mock_gen.assert_not_called()

        combined = result.output + result.stdout
        # The error message names the unknown value and points to bb status.
        assert "ghost-team" in combined
        assert "bb status" in combined

    def test_flag_disabled_warns_and_drops(self, monkeypatch):
        monkeypatch.delenv("FEATURE_MATCHUP_ANALYSIS", raising=False)
        result_value = self._make_success_result()
        with patch(
            "src.cli.report.resolve_our_team",
        ) as mock_resolve, patch(
            "src.cli.report.generate_report", return_value=result_value,
        ) as mock_gen:
            result = runner.invoke(
                app, ["generate", "abc123", "--our-team", "42"],
            )

        # Generation proceeds; resolver is never invoked when the feature is
        # disabled -- the value is dropped at the gate.
        assert result.exit_code == 0
        mock_resolve.assert_not_called()
        mock_gen.assert_called_once_with("abc123", our_team_id=None)
        # AC-9: a warning must be emitted explaining why --our-team was
        # ignored.  Assert on the deterministic substring of the CLI's
        # warning text.
        combined = result.output + result.stdout
        assert "FEATURE_MATCHUP_ANALYSIS" in combined
        assert "disabled" in combined


# ---------------------------------------------------------------------------
# AC-2a / AC-8 helper: ``resolve_our_team`` integer + public_id + missing paths
# ---------------------------------------------------------------------------


class TestResolveOurTeam:
    """The resolution helper accepts integer ids, public_id slugs, and signals
    failure with ``None``."""

    @pytest.fixture()
    def db_with_teams(self, tmp_path):
        db_path = tmp_path / "test.db"
        run_migrations(db_path=db_path)

        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")

        member_a = conn.execute(
            "INSERT INTO teams (name, public_id, membership_type) "
            "VALUES ('Alpha', 'alpha-slug', 'member')"
        ).lastrowid
        # A tracked team -- must NOT be resolvable
        conn.execute(
            "INSERT INTO teams (name, public_id, membership_type) "
            "VALUES ('Tracked', 'tracked-slug', 'tracked')"
        )
        conn.commit()
        conn.close()

        def _open():
            c = sqlite3.connect(str(db_path))
            c.execute("PRAGMA foreign_keys=ON;")
            return c

        return db_path, _open, member_a

    def test_int_path_matches_member_team(self, db_with_teams):
        _db_path, opener, member_id = db_with_teams
        with patch("src.cli.report.get_connection", side_effect=opener):
            assert resolve_our_team(str(member_id)) == member_id

    def test_int_path_rejects_tracked_team(self, db_with_teams):
        db_path, opener, _member_id = db_with_teams
        # Find the tracked team's id
        conn = opener()
        tracked_id = conn.execute(
            "SELECT id FROM teams WHERE membership_type = 'tracked'"
        ).fetchone()[0]
        conn.close()

        with patch("src.cli.report.get_connection", side_effect=opener):
            assert resolve_our_team(str(tracked_id)) is None

    def test_public_id_path_matches_member_team(self, db_with_teams):
        _db_path, opener, member_id = db_with_teams
        with patch("src.cli.report.get_connection", side_effect=opener):
            assert resolve_our_team("alpha-slug") == member_id

    def test_public_id_path_rejects_tracked_team(self, db_with_teams):
        _db_path, opener, _member_id = db_with_teams
        with patch("src.cli.report.get_connection", side_effect=opener):
            assert resolve_our_team("tracked-slug") is None

    def test_unknown_value_returns_none(self, db_with_teams):
        _db_path, opener, _member_id = db_with_teams
        with patch("src.cli.report.get_connection", side_effect=opener):
            assert resolve_our_team("ghost-team") is None

    def test_numeric_string_falls_back_to_public_id(self, db_with_teams):
        """A value like ``"123"`` that does not match a member-team integer
        id should still be tried as a public_id slug -- some real public_ids
        are numeric strings."""
        db_path, opener, _member_id = db_with_teams
        # Insert a member team whose public_id is a numeric string
        conn = opener()
        numeric_id = conn.execute(
            "INSERT INTO teams (name, public_id, membership_type) "
            "VALUES ('Numeric', '999000', 'member')"
        ).lastrowid
        conn.commit()
        conn.close()

        with patch("src.cli.report.get_connection", side_effect=opener):
            # 999000 is unlikely to match any teams.id; falls through to
            # public_id lookup.
            assert resolve_our_team("999000") == numeric_id
