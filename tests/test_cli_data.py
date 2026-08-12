"""Tests for src/cli/data.py -- bb data sub-commands (surviving set).

After E-239-03 the member/opponent-flow commands (sync, crawl, load, scout,
resolve-opponents, dedup, repair-opponents) and their pipeline coupling were
removed. E-256-02 additionally deleted the dead backfill-appearance-order
command. The surviving set is reconcile, dedup-players, backfill-game-dates,
reload-annotated-pitches, and fix-self-games; reconcile has its own dedicated
test module (test_reconciliation.py). This module covers the surviving CLI
surface and the dedup-players error path.
"""

from __future__ import annotations

import inspect
import logging
import os
import re
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli import app
from tests.conftest import load_real_schema

runner = CliRunner()


# ---------------------------------------------------------------------------
# Real-DB seed helpers for the dedup-players delegation tests (E-249-02).
#
# The CLI opens its OWN connection (sqlite3.connect) against the --db path, so
# these tests seed an on-disk temp DB, invoke the command against it, then
# re-open the file to assert the persisted result (proving the merge AND the
# recompute commit survive the command's connection close).
# ---------------------------------------------------------------------------

_AWAY_PLACEHOLDER_TEAM_ID = 9999


def _make_db_file(tmp_path: Path) -> Path:
    """Create an on-disk DB with the production schema + a placeholder away team."""
    db_file = tmp_path / "dedup.db"
    conn = sqlite3.connect(str(db_file))
    load_real_schema(conn)
    conn.execute(
        "INSERT INTO teams (id, name, membership_type) "
        "VALUES (?, 'Away Placeholder', 'tracked')",
        (_AWAY_PLACEHOLDER_TEAM_ID,),
    )
    conn.commit()
    conn.close()
    return db_file


def _seed_team(conn: sqlite3.Connection, team_id: int, name: str) -> None:
    conn.execute(
        "INSERT INTO teams (id, name, membership_type) VALUES (?, ?, 'member')",
        (team_id, name),
    )


def _seed_player(conn: sqlite3.Connection, pid: str, first: str, last: str) -> None:
    conn.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (pid, first, last),
    )


def _seed_roster(conn: sqlite3.Connection, team_id: int, pid: str, season: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) "
        "VALUES (?, ?, 2026)",
        (season, season),
    )
    conn.execute(
        "INSERT INTO team_rosters (team_id, player_id, season_id) VALUES (?, ?, ?)",
        (team_id, pid, season),
    )


def _seed_game(conn: sqlite3.Connection, game_id: str, season: str, team_id: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) "
        "VALUES (?, ?, 2026)",
        (season, season),
    )
    conn.execute(
        "INSERT OR IGNORE INTO games "
        "(game_id, season_id, game_date, home_team_id, away_team_id) "
        "VALUES (?, ?, '2026-04-01', ?, ?)",
        (game_id, season, team_id, _AWAY_PLACEHOLDER_TEAM_ID),
    )


def _seed_game_batting(
    conn: sqlite3.Connection,
    game_id: str,
    pid: str,
    team_id: int,
    *,
    ab: int = 0,
    h: int = 0,
) -> None:
    conn.execute(
        "INSERT INTO player_game_batting "
        "(game_id, player_id, team_id, perspective_team_id, stat_completeness, ab, h) "
        "VALUES (?, ?, ?, ?, 'boxscore_only', ?, ?)",
        (game_id, pid, team_id, team_id, ab, h),
    )


def _surviving_player_ids(db_file: Path) -> set[str]:
    conn = sqlite3.connect(str(db_file))
    try:
        return {r[0] for r in conn.execute("SELECT player_id FROM players").fetchall()}
    finally:
        conn.close()


def _derive_game_dates_summary_keys() -> dict[str, int]:
    """The real backfill's summary shape, run once over an empty table.

    Computed at IMPORT time (below), deliberately: the helper that consumes it
    runs inside a ``patch`` of ``sqlite3.connect`` that counts calls, so opening
    a connection there would be captured as a second call and fail the very
    assertion those tests make.
    """
    from src.db.backfill_game_dates import backfill_game_dates

    conn = sqlite3.connect(":memory:")
    try:
        load_real_schema(conn)
        return backfill_game_dates(conn, dry_run=True)
    finally:
        conn.close()


_GAME_DATES_SUMMARY_SHAPE = _derive_game_dates_summary_keys()


def _game_dates_summary() -> dict[str, int]:
    """The summary dict the backfill-game-dates command prints (values irrelevant).

    DERIVED from the real implementation rather than transcribed.

    The rot is one-directional, and getting the direction right matters if you
    are deciding whether this helper needs to be derived at all. Adding a key to
    the backfill's return dict breaks NO consumer -- the CLI looks keys up by
    name and never iterates the dict, so a key it does not name is simply never
    read. (Today it happens to name all seven the backfill returns; nothing
    requires that, and nothing breaks if it stops being true.) What breaks is a
    STUB that supplies fewer keys than the CLI READS: this function feeds the
    CLI in place of the real backfill, so every `summary[...]` lookup in
    `backfill_game_dates`'s output block must find something here. E-278-04 added
    two counters AND two echo lines reading them, and the hand-written literal
    that used to live here raised `KeyError` on the second pair.
    """
    return dict(_GAME_DATES_SUMMARY_SHAPE)


def _invoke_db_path_capturing_connect(
    args: list[str],
) -> tuple[object, MagicMock]:
    """Invoke a `bb data` command with the DB layer stubbed, capturing the path.

    Patches ``sqlite3.connect`` (to capture the resolved DB path the command
    opens) and the underlying pass (to a no-op summary), so the assertion is
    purely about which path the command resolved. Returns (result, connect_mock).

    E-256-02 re-pointed this from the deleted ``backfill-appearance-order`` to
    ``backfill-game-dates``: the command is only a VEHICLE here: any `bb data`
    command with a ``--db`` option exercises the same
    ``resolve_db_path`` seam, which is what these tests actually pin.
    """
    mock_conn = MagicMock()
    with patch("src.cli.data.sqlite3.connect", return_value=mock_conn) as connect_mock:
        with patch(
            "src.db.backfill_game_dates.backfill_game_dates",
            return_value=_game_dates_summary(),
        ):
            result = runner.invoke(app, ["data", "backfill-game-dates", *args])
    return result, connect_mock


# ---------------------------------------------------------------------------
# bb data --help (surviving command set)
# ---------------------------------------------------------------------------


def test_data_help_lists_surviving_commands() -> None:
    """bb data --help lists only the surviving maintenance commands."""
    result = runner.invoke(app, ["data", "--help"])
    assert result.exit_code == 0
    assert "reconcile" in result.output
    assert "dedup-players" in result.output
    assert "backfill-game-dates" in result.output
    assert "reload-annotated-pitches" in result.output
    assert "fix-self-games" in result.output
    # The removed member/opponent-flow commands (E-239-03) and the dead
    # backfill-appearance-order command (E-256-02) must not reappear. Match on a
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
        "backfill-appearance-order",
    ):
        assert re.search(rf"\b{re.escape(removed)}\b", result.output) is None, removed


# ---------------------------------------------------------------------------
# bb data dedup-players (E-215-02)
# ---------------------------------------------------------------------------


def test_dedup_players_error_path() -> None:
    """dedup-players prints error and exits 1 when detection raises."""
    mock_conn = MagicMock()
    mock_conn.execute = MagicMock()
    # E-250-01: the command derives its season from team_rosters before
    # planning. Stub that derivation query to a single season so control
    # reaches the planner (whose find_duplicate_players is the raising path).
    mock_conn.execute.return_value.fetchall.return_value = [("2026",)]
    with patch("src.cli.data.sqlite3.connect", return_value=mock_conn):
        with patch(
            "src.db.player_dedup.find_duplicate_players",
            side_effect=RuntimeError("table missing"),
        ):
            result = runner.invoke(app, ["data", "dedup-players"])

    assert result.exit_code != 0
    assert "Error finding duplicate players" in result.output
    assert "table missing" in result.output


def test_dedup_players_dry_run_and_execute_are_mutually_exclusive() -> None:
    """E-262-01 #1: passing both --dry-run and --execute is a loud error and
    performs no merges -- the destructive path never runs.

    Regression guard: the historical bug derived is_dry_run = not execute and
    never read --dry-run, so `--dry-run --execute` silently executed. The DB
    connection and planner must not be reached; both are patched to assert they
    are never touched.
    """
    with (
        patch("src.cli.data.sqlite3.connect") as mock_connect,
        patch("src.db.player_dedup.plan_player_dedup") as mock_plan,
        patch("src.db.player_dedup.execute_collapse") as mock_execute,
    ):
        result = runner.invoke(
            app, ["data", "dedup-players", "--dry-run", "--execute"]
        )

    assert result.exit_code != 0
    assert "mutually exclusive" in result.output
    mock_connect.assert_not_called()
    mock_plan.assert_not_called()
    mock_execute.assert_not_called()


# ---------------------------------------------------------------------------
# bb data dedup-players -- E-249-02: delegation to the shared planner
# ---------------------------------------------------------------------------


def test_dedup_players_delegates_to_shared_planner() -> None:
    """AC-1: the command routes through plan_player_dedup with the CLI scope,
    and contains NO parallel inline find_duplicate_players + merge loop."""
    from src.db.player_dedup import DedupPlan

    mock_conn = MagicMock()
    with patch("src.cli.data.sqlite3.connect", return_value=mock_conn):
        with patch(
            "src.db.player_dedup.plan_player_dedup",
            return_value=DedupPlan(),
        ) as mock_plan:
            result = runner.invoke(
                app,
                ["data", "dedup-players", "--team-id", "7", "--season-id", "2026"],
            )

    assert result.exit_code == 0
    assert "No duplicate players found." in result.output
    mock_plan.assert_called_once()
    assert mock_plan.call_args.kwargs == {"team_id": 7, "season_id": "2026"}

    # No-inline-loop guard: the CLI must not re-call the detection/merge
    # primitives directly -- it delegates to the shared planner + executor.
    import src.cli.data as cli_data_mod

    src = inspect.getsource(cli_data_mod)
    assert "merge_player_pair(" not in src
    assert "find_duplicate_players(" not in src
    assert "plan_player_dedup(" in src
    assert "execute_collapse(" in src


def test_dedup_players_execute_collapses_and_refuses_fork(tmp_path: Path) -> None:
    """AC-2: a single-terminal component collapses (one canonical) while a fork
    on the same team is left unmerged with every member surviving -- identical
    collapse/refuse behavior to the load path."""
    db_file = _make_db_file(tmp_path)
    conn = sqlite3.connect(str(db_file))
    _seed_team(conn, 1, "LSB Varsity")
    # Collapse component: Sam subset Samuel.
    _seed_player(conn, "p-sam", "Sam", "Webb")
    _seed_player(conn, "p-samuel", "Samuel", "Webb")
    # Fork component: O -> Oliver + O -> Owen (distinct terminals).
    _seed_player(conn, "p-o", "O", "Yang")
    _seed_player(conn, "p-oliver", "Oliver", "Yang")
    _seed_player(conn, "p-owen", "Owen", "Yang")
    for pid in ("p-sam", "p-samuel", "p-o", "p-oliver", "p-owen"):
        _seed_roster(conn, 1, pid, "2026")
    conn.commit()
    conn.close()

    result = runner.invoke(
        app, ["data", "dedup-players", "--execute", "--db", str(db_file)]
    )

    assert result.exit_code == 0, result.output
    # Collapse: Sam merged into Samuel. Fork: all three members survive.
    assert _surviving_player_ids(db_file) == {
        "p-samuel",
        "p-o",
        "p-oliver",
        "p-owen",
    }
    assert "MERGED Sam Webb -> Samuel Webb" in result.output
    assert "refused fork" in result.output.lower()


def test_dedup_players_single_season_auto_derives(tmp_path: Path) -> None:
    """AC-1: on a one-season DB, an unscoped run (no --season-id) auto-derives
    that season and produces IDENTICAL output to an explicit --season-id run
    (zero-UX-change on the live one-season DB)."""
    db_file = _make_db_file(tmp_path)
    conn = sqlite3.connect(str(db_file))
    _seed_team(conn, 1, "LSB Varsity")
    _seed_player(conn, "p-sam", "Sam", "Webb")
    _seed_player(conn, "p-samuel", "Samuel", "Webb")
    _seed_roster(conn, 1, "p-sam", "2026")
    _seed_roster(conn, 1, "p-samuel", "2026")
    conn.commit()
    conn.close()

    derived = runner.invoke(app, ["data", "dedup-players", "--db", str(db_file)])
    explicit = runner.invoke(
        app, ["data", "dedup-players", "--season-id", "2026", "--db", str(db_file)]
    )

    assert derived.exit_code == 0, derived.output
    assert explicit.exit_code == 0, explicit.output
    # Zero-UX-change: derived-season dry-run output matches the explicit run.
    assert derived.output == explicit.output
    assert "1 collapsible component(s)" in derived.output
    assert "Sam Webb" in derived.output and "Samuel Webb" in derived.output
    # Dry-run mutates nothing.
    assert _surviving_player_ids(db_file) == {"p-sam", "p-samuel"}


def test_dedup_players_no_roster_seasons_exits_zero(tmp_path: Path) -> None:
    """AC-2: a DB with zero distinct roster seasons exits 0 (nothing to do)
    without error when --season-id is omitted."""
    db_file = _make_db_file(tmp_path)  # only the away placeholder; no rosters

    result = runner.invoke(app, ["data", "dedup-players", "--db", str(db_file)])

    assert result.exit_code == 0, result.output
    assert "nothing to dedup" in result.output.lower()


def test_dedup_players_multi_season_without_season_id_errors(tmp_path: Path) -> None:
    """AC-3: a DB with 2+ distinct roster seasons errors (listing the seasons)
    and exits non-zero when --season-id is omitted; supplying --season-id
    selects that season and proceeds."""
    db_file = _make_db_file(tmp_path)
    conn = sqlite3.connect(str(db_file))
    _seed_team(conn, 1, "LSB Varsity")
    _seed_player(conn, "p-sam", "Sam", "Webb")
    _seed_player(conn, "p-samuel", "Samuel", "Webb")
    # The same collapse rostered on TWO distinct seasons -> 2 distinct seasons.
    _seed_roster(conn, 1, "p-sam", "2025")
    _seed_roster(conn, 1, "p-samuel", "2025")
    _seed_roster(conn, 1, "p-sam", "2026")
    _seed_roster(conn, 1, "p-samuel", "2026")
    conn.commit()
    conn.close()

    # No --season-id -> error listing both seasons, non-zero, mutates nothing.
    result = runner.invoke(app, ["data", "dedup-players", "--db", str(db_file)])
    assert result.exit_code != 0
    assert "2025" in result.output and "2026" in result.output
    assert "--season-id" in result.output
    assert _surviving_player_ids(db_file) == {"p-sam", "p-samuel"}

    # Supplying --season-id selects that season and proceeds (dry-run, exit 0).
    scoped = runner.invoke(
        app, ["data", "dedup-players", "--season-id", "2026", "--db", str(db_file)]
    )
    assert scoped.exit_code == 0, scoped.output
    assert "1 collapsible component(s)" in scoped.output


def test_dedup_players_team_scoped_season_derivation(tmp_path: Path) -> None:
    """AC-11: --team-id scopes the season derivation to that team's rosters.
    Globally two seasons exist, but team 1 has only one -- so an unscoped-season
    run with --team-id 1 auto-derives team 1's single season and proceeds."""
    db_file = _make_db_file(tmp_path)
    conn = sqlite3.connect(str(db_file))
    _seed_team(conn, 1, "LSB Varsity")
    _seed_team(conn, 2, "LSB JV")
    # Team 1 rosters only in 2026 (single season for this team).
    _seed_player(conn, "p-sam", "Sam", "Webb")
    _seed_player(conn, "p-samuel", "Samuel", "Webb")
    _seed_roster(conn, 1, "p-sam", "2026")
    _seed_roster(conn, 1, "p-samuel", "2026")
    # Team 2 rosters in 2025 -> globally two distinct seasons exist.
    _seed_player(conn, "p-bob", "Bob", "Ng")
    _seed_player(conn, "p-bobby", "Bobby", "Ng")
    _seed_roster(conn, 2, "p-bob", "2025")
    _seed_roster(conn, 2, "p-bobby", "2025")
    conn.commit()
    conn.close()

    # Globally ambiguous, but the team-1-scoped derivation resolves to 2026.
    result = runner.invoke(
        app, ["data", "dedup-players", "--team-id", "1", "--db", str(db_file)]
    )
    assert result.exit_code == 0, result.output
    assert "1 collapsible component(s)" in result.output
    assert "Sam Webb" in result.output and "Samuel Webb" in result.output
    # Team 2's 2025-only collapse is out of scope and must not appear.
    assert "Bobby Ng" not in result.output


def test_dedup_players_dry_run_surfaces_refused_fork(tmp_path: Path) -> None:
    """AC-3 (dry-run): the preview lists the refused fork (team + conflicting
    terminal names) and changes NO data."""
    db_file = _make_db_file(tmp_path)
    conn = sqlite3.connect(str(db_file))
    _seed_team(conn, 1, "LSB Varsity")
    _seed_player(conn, "p-o", "O", "Yang")
    _seed_player(conn, "p-oliver", "Oliver", "Yang")
    _seed_player(conn, "p-owen", "Owen", "Yang")
    for pid in ("p-o", "p-oliver", "p-owen"):
        _seed_roster(conn, 1, pid, "2026")
    conn.commit()
    conn.close()

    result = runner.invoke(app, ["data", "dedup-players", "--db", str(db_file)])

    assert result.exit_code == 0, result.output
    assert "Refused forks" in result.output
    assert "LSB Varsity" in result.output
    assert "Oliver" in result.output and "Owen" in result.output
    # Dry-run mutates nothing.
    assert _surviving_player_ids(db_file) == {"p-o", "p-oliver", "p-owen"}


def test_dedup_players_execute_warns_per_refused_fork(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-3 (execute): exactly one WARN-level log line per refused component,
    naming the team and the conflicting terminal names."""
    db_file = _make_db_file(tmp_path)
    conn = sqlite3.connect(str(db_file))
    _seed_team(conn, 1, "LSB Varsity")
    _seed_player(conn, "p-o", "O", "Yang")
    _seed_player(conn, "p-oliver", "Oliver", "Yang")
    _seed_player(conn, "p-owen", "Owen", "Yang")
    for pid in ("p-o", "p-oliver", "p-owen"):
        _seed_roster(conn, 1, pid, "2026")
    conn.commit()
    conn.close()

    with caplog.at_level(logging.WARNING, logger="src.cli.data"):
        result = runner.invoke(
            app, ["data", "dedup-players", "--execute", "--db", str(db_file)]
        )

    assert result.exit_code == 0, result.output
    warns = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "refused" in r.getMessage()
    ]
    assert len(warns) == 1, f"expected exactly one WARN, got {len(warns)}"
    msg = warns[0].getMessage()
    assert "LSB Varsity" in msg
    assert "Oliver" in msg and "Owen" in msg


def test_dedup_players_execute_merges_and_combines_per_game_line(
    tmp_path: Path,
) -> None:
    """AC-4: after a CLI collapse the duplicate's per-game rows are attributed to
    the canonical, so the query-time season line (the SUM of the canonical's
    per-game rows) is the combined line. E-259 retired the stored recompute, so
    the combined line is now derived at read time from the merged per-game rows.
    """
    db_file = _make_db_file(tmp_path)
    conn = sqlite3.connect(str(db_file))
    _seed_team(conn, 1, "LSB Varsity")
    _seed_player(conn, "p-o", "O", "Diaz")
    _seed_player(conn, "p-oliver", "Oliver", "Diaz")
    _seed_roster(conn, 1, "p-o", "2026")
    _seed_roster(conn, 1, "p-oliver", "2026")
    # Per-game rows sum to ab=7, h=3.
    _seed_game(conn, "g1", "2026", 1)
    _seed_game(conn, "g2", "2026", 1)
    _seed_game_batting(conn, "g1", "p-o", 1, ab=3, h=1)
    _seed_game_batting(conn, "g2", "p-oliver", 1, ab=4, h=2)
    conn.commit()
    conn.close()

    result = runner.invoke(
        app, ["data", "dedup-players", "--execute", "--db", str(db_file)]
    )

    assert result.exit_code == 0, result.output
    assert "MERGED O Diaz -> Oliver Diaz" in result.output

    verify = sqlite3.connect(str(db_file))
    try:
        # The duplicate is gone; both games' per-game rows are now under the
        # canonical, so their SUM (what the query-time reader returns) is 7/3.
        survivors = {
            r[0] for r in verify.execute("SELECT player_id FROM players").fetchall()
        }
        combined = verify.execute(
            "SELECT SUM(ab), SUM(h) FROM player_game_batting "
            "WHERE player_id = 'p-oliver' AND team_id = 1 AND perspective_team_id = 1"
        ).fetchone()
    finally:
        verify.close()
    assert "p-o" not in survivors and "p-oliver" in survivors
    assert combined == (7, 3), (
        f"merged per-game line should combine to (7, 3), got {combined}"
    )


def test_dedup_players_execute_merge_failure_nonzero_exit(tmp_path: Path) -> None:
    """AC-5: a merge that raises during execute is surfaced (reported AND
    non-zero exit) -- never a misleading success."""
    db_file = _make_db_file(tmp_path)
    conn = sqlite3.connect(str(db_file))
    _seed_team(conn, 1, "LSB Varsity")
    _seed_player(conn, "p-sam", "Sam", "Webb")
    _seed_player(conn, "p-samuel", "Samuel", "Webb")
    _seed_roster(conn, 1, "p-sam", "2026")
    _seed_roster(conn, 1, "p-samuel", "2026")
    conn.commit()
    conn.close()

    with patch(
        "src.db.player_dedup.execute_collapse",
        side_effect=RuntimeError("merge boom"),
    ):
        result = runner.invoke(
            app, ["data", "dedup-players", "--execute", "--db", str(db_file)]
        )

    assert result.exit_code != 0
    assert "ERROR collapsing component into Samuel Webb" in result.output
    assert "merge boom" in result.output
    # Not a misleading success: nothing was recomputed, both players survive.
    assert "Season aggregates recomputed." not in result.output
    assert _surviving_player_ids(db_file) == {"p-sam", "p-samuel"}


class _RecordingConn:
    """Proxy over a real sqlite3.Connection that records executed SQL text.

    Only ``execute`` is wrapped (to capture transaction-control statements);
    every other attribute -- including ``close``/``commit`` invoked by the
    command's ``closing(...)`` block -- delegates to the real connection.
    """

    def __init__(self, real: sqlite3.Connection, sql_log: list[str]) -> None:
        self._real = real
        self._sql_log = sql_log

    def execute(self, sql: str, *args: object, **kwargs: object) -> object:
        self._sql_log.append(sql)
        return self._real.execute(sql, *args, **kwargs)

    def __getattr__(self, name: str) -> object:
        return getattr(self._real, name)


def test_dedup_players_execute_single_transaction_per_component(
    tmp_path: Path,
) -> None:
    """AC-6: a multi-member component is collapsed under ONE transaction owned by
    the executor (a single BEGIN IMMEDIATE), with the inner per-member merges
    running on SAVEPOINTs (manage_transaction=False) -- no nested-transaction
    error. A bare merge_player_pair(manage_transaction=True) would either raise
    a nested-BEGIN error or lose per-component atomicity."""
    db_file = _make_db_file(tmp_path)
    conn = sqlite3.connect(str(db_file))
    _seed_team(conn, 1, "LSB Varsity")
    # 3-member chain -> single component, 2 inner merges.
    _seed_player(conn, "p-o", "O", "Holbein")
    _seed_player(conn, "p-oli", "Oli", "Holbein")
    _seed_player(conn, "p-oliver", "Oliver", "Holbein")
    for pid in ("p-o", "p-oli", "p-oliver"):
        _seed_roster(conn, 1, pid, "2026")
    conn.commit()
    conn.close()

    sql_log: list[str] = []
    real = sqlite3.connect(str(db_file))
    recording = _RecordingConn(real, sql_log)
    with patch("src.cli.data.sqlite3.connect", return_value=recording):
        result = runner.invoke(
            app, ["data", "dedup-players", "--execute", "--db", str(db_file)]
        )

    # No nested-transaction error: the command completed and collapsed the chain.
    assert result.exit_code == 0, result.output
    assert _surviving_player_ids(db_file) == {"p-oliver"}

    # Exactly one explicit BEGIN IMMEDIATE for the single component; the two
    # inner merges used SAVEPOINTs (NOT their own BEGIN), and no component-level
    # SAVEPOINT (that path is manage_transaction=False, not used by the CLI).
    begins = [s for s in sql_log if s.strip().upper().startswith("BEGIN IMMEDIATE")]
    assert len(begins) == 1, f"expected one component transaction, got {begins}"
    inner_savepoints = [
        s for s in sql_log if s.strip().upper().startswith("SAVEPOINT MERGE_")
    ]
    assert len(inner_savepoints) == 2, (
        f"expected two inner-merge savepoints, got {inner_savepoints}"
    )
    assert not [
        s for s in sql_log if "DEDUP_COMP_" in s.strip().upper()
    ], "CLI must use BEGIN IMMEDIATE per component, not a component-level SAVEPOINT"


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


def test_reload_annotated_pitches_nonzero_exit_when_games_errored() -> None:
    """E-262-01 #2: a completed run with games_with_errors > 0 exits non-zero.

    The pass finishes (no exception) but reports one or more failed games, so
    the summary must not claim success -- a green exit would hide the failure
    from the operator. The summary is still printed.
    """
    mock_conn = MagicMock()
    mock_conn.execute = MagicMock()
    summary = {
        "games_processed": 3,
        "games_changed": 1,
        "plays_updated": 10,
        "events_recovered": 20,
        "games_with_errors": 2,
    }
    with patch("src.cli.data.sqlite3.connect", return_value=mock_conn):
        with patch(
            "src.gamechanger.loaders.plays_reload.reload_all_games",
            return_value=summary,
        ):
            result = runner.invoke(app, ["data", "reload-annotated-pitches"])

    assert result.exit_code != 0
    assert "Games with errors: 2" in result.output


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


# ---------------------------------------------------------------------------
# E-246-03: bb data commands honor DATABASE_PATH via the canonical resolver
# ---------------------------------------------------------------------------


def test_data_command_honors_database_path_env(tmp_path: Path) -> None:
    """AC-3 (intended behavior change): with DATABASE_PATH set and no --db, a
    `bb data` command opens the DATABASE_PATH database."""
    target = tmp_path / "honored.db"
    with patch.dict(os.environ, {"DATABASE_PATH": str(target)}):
        result, connect_mock = _invoke_db_path_capturing_connect([])

    assert result.exit_code == 0
    connect_mock.assert_called_once()
    assert connect_mock.call_args.args[0] == str(target)


def test_data_command_explicit_db_overrides_database_path(tmp_path: Path) -> None:
    """AC-4: an explicit --db override wins over DATABASE_PATH."""
    override = tmp_path / "explicit.db"
    with patch.dict(os.environ, {"DATABASE_PATH": str(tmp_path / "env.db")}):
        result, connect_mock = _invoke_db_path_capturing_connect(
            ["--db", str(override)]
        )

    assert result.exit_code == 0
    connect_mock.assert_called_once()
    # The canonical resolver resolves an explicit override to an absolute path.
    assert connect_mock.call_args.args[0] == str(Path(str(override)).resolve())


def test_data_command_falls_back_to_default_db(tmp_path: Path) -> None:
    """AC-4: with neither --db nor DATABASE_PATH, the default DB path is used."""
    env_without = {k: v for k, v in os.environ.items() if k != "DATABASE_PATH"}
    with patch.dict(os.environ, env_without, clear=True):
        result, connect_mock = _invoke_db_path_capturing_connect([])

    assert result.exit_code == 0
    connect_mock.assert_called_once()
    opened = Path(connect_mock.call_args.args[0])
    assert opened.is_absolute()
    assert opened.parts[-2:] == ("data", "app.db")


def test_resolve_db_path_precedence(tmp_path: Path) -> None:
    """Canonical resolver precedence: override > DATABASE_PATH > default.

    NOTE (worktree caveat): imports the new ``src.db.paths`` module, which only
    exists in this epic's worktree; this test is authoritatively exercised at
    the closure gate in the merged main checkout.
    """
    from src.db.paths import _DEFAULT_DB_PATH, resolve_db_path

    override = tmp_path / "override.db"
    env = tmp_path / "env.db"

    # Override wins even when DATABASE_PATH is set.
    with patch.dict(os.environ, {"DATABASE_PATH": str(env)}):
        assert resolve_db_path(override) == Path(str(override)).resolve()
        # DATABASE_PATH (absolute) used when no override.
        assert resolve_db_path() == env

    # Default used when neither override nor env is set.
    env_without = {k: v for k, v in os.environ.items() if k != "DATABASE_PATH"}
    with patch.dict(os.environ, env_without, clear=True):
        assert resolve_db_path() == _DEFAULT_DB_PATH


# ---------------------------------------------------------------------------
# bb data dedup-players -- the content-aware refusal class
# ---------------------------------------------------------------------------


def _seed_content_conflict(db_file: Path) -> None:
    """Two same-named ids whose colliding batting rows DISAGREE."""
    conn = sqlite3.connect(str(db_file))
    _seed_team(conn, 1, "LSB Varsity")
    _seed_player(conn, "p-jordan-a", "Jordan", "Rivera")
    _seed_player(conn, "p-jordan-b", "Jordan", "Rivera")
    _seed_roster(conn, 1, "p-jordan-a", "2026")
    _seed_roster(conn, 1, "p-jordan-b", "2026")
    _seed_game(conn, "g-conflict", "2026", 1)
    _seed_game_batting(conn, "g-conflict", "p-jordan-a", 1, ab=4, h=2)
    _seed_game_batting(conn, "g-conflict", "p-jordan-b", 1, ab=3, h=0)
    conn.commit()
    conn.close()


def test_dedup_players_dry_run_surfaces_the_content_refusal(tmp_path: Path) -> None:
    """The operator must be able to tell this class from a fork.

    A fork is ambiguous about WHICH human the ids name; this component is
    ambiguous about which of two disagreeing stat rows is right. The preview
    names the table, game and differing columns so the operator can adjudicate
    what the planner refuses to.
    """
    db_file = _make_db_file(tmp_path)
    _seed_content_conflict(db_file)

    result = runner.invoke(app, ["data", "dedup-players", "--db", str(db_file)])

    assert result.exit_code == 0, result.output
    assert "conflicting content" in result.output
    assert "player_game_batting" in result.output
    assert "g-conflict" in result.output
    assert "ab" in result.output and "h" in result.output
    # Nothing is presented as mergeable.
    assert "0 collapsible component(s)" in result.output


def test_dedup_players_execute_leaves_a_content_refused_component_intact(
    tmp_path: Path,
) -> None:
    """--execute must not merge it either: the refusal is at PLAN time."""
    db_file = _make_db_file(tmp_path)
    _seed_content_conflict(db_file)

    result = runner.invoke(
        app, ["data", "dedup-players", "--execute", "--db", str(db_file)]
    )

    assert result.exit_code == 0, result.output
    assert _surviving_player_ids(db_file) == {"p-jordan-a", "p-jordan-b"}
    assert "1 refused for conflicting content" in result.output
    conn = sqlite3.connect(str(db_file))
    try:
        rows = conn.execute(
            "SELECT player_id, ab, h FROM player_game_batting ORDER BY player_id"
        ).fetchall()
    finally:
        conn.close()
    assert rows == [("p-jordan-a", 4, 2), ("p-jordan-b", 3, 0)]


def test_dedup_players_reports_placeholder_stubs_as_no_duplicates(
    tmp_path: Path,
) -> None:
    """Two ``Unknown Unknown`` stubs are not a duplicate pair at all.

    The guard is in DETECTION, so they never reach the plan -- the command must
    say "no duplicates", not "refused". A regression here reads as a clean run
    while the planner quietly collapses two different players.
    """
    db_file = _make_db_file(tmp_path)
    conn = sqlite3.connect(str(db_file))
    _seed_team(conn, 1, "LSB Varsity")
    _seed_player(conn, "p-unknown-a", "Unknown", "Unknown")
    _seed_player(conn, "p-unknown-b", "Unknown", "Unknown")
    _seed_roster(conn, 1, "p-unknown-a", "2026")
    _seed_roster(conn, 1, "p-unknown-b", "2026")
    conn.commit()
    conn.close()

    result = runner.invoke(
        app, ["data", "dedup-players", "--execute", "--db", str(db_file)]
    )

    assert result.exit_code == 0, result.output
    assert "No duplicate players found." in result.output
    assert _surviving_player_ids(db_file) == {"p-unknown-a", "p-unknown-b"}
