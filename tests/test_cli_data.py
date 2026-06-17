"""Tests for src/cli/data.py -- bb data sub-commands (surviving set).

After E-239-03 the member/opponent-flow commands (sync, crawl, load, scout,
resolve-opponents, dedup, repair-opponents) and their pipeline coupling were
removed; only reconcile, dedup-players, and backfill-appearance-order remain.
reconcile and backfill-appearance-order have their own dedicated test modules
(test_reconciliation.py, test_backfill_appearance_order.py); this module covers
the surviving CLI surface and the dedup-players error path.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# bb data --help (surviving command set)
# ---------------------------------------------------------------------------


def test_data_help_lists_surviving_commands() -> None:
    """bb data --help lists only the surviving maintenance commands."""
    result = runner.invoke(app, ["data", "--help"])
    assert result.exit_code == 0
    assert "reconcile" in result.output
    assert "dedup-players" in result.output
    assert "backfill-appearance-order" in result.output
    # The removed member/opponent-flow commands must not reappear.
    for removed in (
        "sync",
        "crawl",
        "load",
        "scout",
        "resolve-opponents",
        "repair-opponents",
    ):
        assert removed not in result.output, removed


# ---------------------------------------------------------------------------
# bb data dedup-players (E-215-02)
# ---------------------------------------------------------------------------


def test_dedup_players_error_path() -> None:
    """dedup-players prints error and exits 1 when detection raises."""
    mock_conn = MagicMock()
    mock_conn.execute = MagicMock()
    with patch("src.cli.data.sqlite3.connect", return_value=mock_conn):
        with patch(
            "src.db.player_dedup.find_duplicate_players",
            side_effect=RuntimeError("table missing"),
        ):
            result = runner.invoke(app, ["data", "dedup-players"])

    assert result.exit_code != 0
    assert "Error finding duplicate players" in result.output
    assert "table missing" in result.output
