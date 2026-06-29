"""Tests for src/cli/data.py -- bb data sub-commands (surviving set).

After E-239-03 the member/opponent-flow commands (sync, crawl, load, scout,
resolve-opponents, dedup, repair-opponents) and their pipeline coupling were
removed; only reconcile, dedup-players, and backfill-appearance-order remain.
reconcile and backfill-appearance-order have their own dedicated test modules
(test_reconciliation.py, test_backfill_appearance_order.py); this module covers
the surviving CLI surface and the dedup-players error path.
"""

from __future__ import annotations

import re
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
    assert "reload-annotated-pitches" in result.output
    assert "fix-self-games" in result.output
    # The removed member/opponent-flow commands must not reappear. Match on a
    # word boundary so legitimate commands that merely *contain* a removed name
    # as a substring (e.g. "reload-annotated-pitches" contains "load") do not
    # trip the guard.
    for removed in (
        "sync",
        "crawl",
        "load",
        "scout",
        "resolve-opponents",
        "repair-opponents",
    ):
        assert re.search(rf"\b{re.escape(removed)}\b", result.output) is None, removed


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


# ---------------------------------------------------------------------------
# bb data reload-annotated-pitches (E-245-02)
# ---------------------------------------------------------------------------


def test_reload_annotated_pitches_success() -> None:
    """reload-annotated-pitches prints the summary and exits 0."""
    mock_conn = MagicMock()
    mock_conn.execute = MagicMock()
    summary = {
        "games_processed": 3,
        "games_changed": 2,
        "plays_updated": 40,
        "events_recovered": 120,
        "games_with_errors": 0,
    }
    with patch("src.cli.data.sqlite3.connect", return_value=mock_conn):
        with patch(
            "src.gamechanger.loaders.plays_reload.reload_all_games",
            return_value=summary,
        ):
            result = runner.invoke(app, ["data", "reload-annotated-pitches"])

    assert result.exit_code == 0
    assert "Games processed: 3" in result.output
    assert "Pitch events recovered: 120" in result.output


def test_reload_annotated_pitches_error_path() -> None:
    """reload-annotated-pitches prints error and exits 1 when the pass raises."""
    mock_conn = MagicMock()
    mock_conn.execute = MagicMock()
    with patch("src.cli.data.sqlite3.connect", return_value=mock_conn):
        with patch(
            "src.gamechanger.loaders.plays_reload.reload_all_games",
            side_effect=RuntimeError("db locked"),
        ):
            result = runner.invoke(app, ["data", "reload-annotated-pitches"])

    assert result.exit_code != 0
    assert "Error reloading annotated pitches" in result.output
    assert "db locked" in result.output


# ---------------------------------------------------------------------------
# bb data fix-self-games (E-245-04)
# ---------------------------------------------------------------------------


def test_fix_self_games_dry_run_lists_without_changing() -> None:
    """Dry-run lists the corrupt game/team, exits 0, and runs NO re-derivation."""
    mock_conn = MagicMock()
    # The only direct conn query in the command body is the per-team public_id
    # SELECT; give it a deterministic value.
    mock_conn.execute.return_value.fetchone.return_value = ("pub-1",)
    with patch("src.cli.data.sqlite3.connect", return_value=mock_conn):
        with patch(
            "src.gamechanger.loaders.self_game_fix.find_self_games",
            return_value=[("selfgame-001", 1)],
        ):
            with patch(
                "src.gamechanger.loaders.self_game_fix.affected_team_ids",
                return_value=[1],
            ):
                with patch(
                    "src.gamechanger.loaders.self_game_fix.rederive_corrected_game_plays",
                ) as mock_rederive:
                    result = runner.invoke(app, ["data", "fix-self-games"])

    assert result.exit_code == 0
    assert "Self-games found: 1" in result.output
    assert "team_id=1" in result.output
    assert "1 self-game" in result.output
    assert "Dry-run only" in result.output
    # Dry-run must not touch data.
    mock_rederive.assert_not_called()


def test_fix_self_games_none_found_exits_zero() -> None:
    """When no self-games exist, the command reports it and exits 0."""
    mock_conn = MagicMock()
    with patch("src.cli.data.sqlite3.connect", return_value=mock_conn):
        with patch(
            "src.gamechanger.loaders.self_game_fix.find_self_games",
            return_value=[],
        ):
            result = runner.invoke(app, ["data", "fix-self-games"])

    assert result.exit_code == 0
    assert "No self-games found" in result.output


def test_fix_self_games_execute_isolates_errors_and_exit_code() -> None:
    """--execute: per-team error isolation + no-public_id skip + exit 1 on remaining.

    Three affected teams exercise every distinctive branch in one run:
      - team 1 has a public_id but its re-fetch RAISES (must be isolated);
      - team 2 has NO public_id (must be skipped, not crash);
      - team 3 has a public_id and re-fetches successfully (proves the loop
        continued past team 1's exception).
    Self-games persist (find_self_games still returns rows at the end), so the
    exit code must be 1 -- the AC-5 operator success signal.
    """
    mock_conn = MagicMock()
    # Per-team public_id SELECTs, in affected-team order: pub / None / pub.
    mock_conn.execute.return_value.fetchone.side_effect = [
        ("pub-1",),
        (None,),
        ("pub-3",),
    ]

    mock_crawler_cls = MagicMock()
    # scout_team: team 1 raises, team 3 succeeds (team 2 is skipped before this).
    crawl_result_ok = MagicMock()
    mock_crawler_cls.return_value.scout_team.side_effect = [
        RuntimeError("boom"),
        crawl_result_ok,
    ]
    mock_loader_cls = MagicMock()

    with patch("src.cli.data.sqlite3.connect", return_value=mock_conn):
        with patch(
            "src.gamechanger.loaders.self_game_fix.find_self_games",
            return_value=[("g1", 1), ("g2", 2), ("g3", 3)],
        ):
            with patch(
                "src.gamechanger.loaders.self_game_fix.affected_team_ids",
                return_value=[1, 2, 3],
            ):
                with patch("src.gamechanger.client.GameChangerClient"):
                    with patch(
                        "src.gamechanger.crawlers.scouting.ScoutingCrawler",
                        mock_crawler_cls,
                    ):
                        with patch(
                            "src.gamechanger.loaders.scouting_loader.ScoutingLoader",
                            mock_loader_cls,
                        ):
                            with patch(
                                "src.gamechanger.loaders.self_game_fix.rederive_corrected_game_plays",
                                return_value={
                                    "games_rederived": 1,
                                    "plays_updated": 4,
                                    "games_with_errors": 0,
                                },
                            ):
                                result = runner.invoke(
                                    app, ["data", "fix-self-games", "--execute"]
                                )

    # team 1's failure is isolated and reported.
    assert "Re-fetch failed for team_id=1" in result.output
    # team 1's PARTIAL writes are discarded: the per-team except rolls back the
    # shared connection so a later commit can't persist orphaned rows (P1).
    mock_conn.rollback.assert_called()
    # team 2 (no public_id) is skipped, not crashed.
    assert "Skipping team_id=2: no public_id" in result.output
    # The loop continued: team 3 was loaded after team 1 raised and team 2 skipped.
    mock_loader_cls.return_value.load_team.assert_called_once()
    assert mock_loader_cls.return_value.load_team.call_args.kwargs["team_id"] == 3
    # Self-games persist -> exit 1 (AC-5 success signal is "remaining == 0").
    assert "Self-games remaining (target 0): 3" in result.output
    assert result.exit_code == 1
