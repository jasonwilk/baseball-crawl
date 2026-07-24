"""Tests for the one-time backlog reclamation one-shot (E-273-05).

Two required shapes (AC-6):
  (a) a SUBPROCESS smoke test invoking the script via ``sys.executable`` (the
      console/script-entry-point convention -- catches import-time failures the
      in-process runner masks), and
  (b) an IN-PROCESS test that runs the one-shot against a temp DB seeded with
      orphans and asserts the backlog is reclaimed, the post-run invariant is
      zero, AND the three-way exit-code semantics (deferred / clean-zero /
      residual-leak) hold.

The script must NEVER touch the real dev DB: every test passes an explicit
``--db-path`` / ``db_path`` to a temp DB it seeds itself. No specific backlog
magnitude is asserted -- the design keys on the INVARIANT (post-run == 0).
"""

from __future__ import annotations

import importlib.util
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.reports.lifecycle import ReclaimResult, count_orphan_reference_data
from src.util.timezone import UTC_ISO_FORMAT
from tests.conftest import load_real_schema

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "reclaim_orphan_reference_data.py"
)


def _load_script_module():
    """Import the standalone script by path (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "reclaim_orphan_oneshot", _SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed_orphans(db_path: Path, *, generating: bool = False) -> None:
    """Seed a temp DB with a schema + one orphan team and one orphan player.

    When ``generating`` is set, also seed a FRESH 'generating' report (on a
    separate live team) so the reclamation guard defers.
    """
    conn = sqlite3.connect(str(db_path))
    load_real_schema(conn)
    conn.execute(
        "INSERT INTO seasons (season_id, name, year) VALUES ('2026', '2026', 2026)"
    )
    # Orphan team: tracked, no reports, no games -> reclamation target.
    conn.execute(
        "INSERT INTO teams (name, membership_type) VALUES ('Orphan Team', 'tracked')"
    )
    # Orphan player: no roster, no stats -> reclamation target.
    conn.execute(
        "INSERT INTO players (player_id, first_name, last_name) "
        "VALUES ('p-orphan', 'Orphan', 'Player')"
    )
    if generating:
        live = conn.execute(
            "INSERT INTO teams (name, membership_type) VALUES ('Live Gen', 'tracked')"
        ).lastrowid
        conn.execute(
            "INSERT INTO reports (slug, team_id, title, status, generated_at, expires_at) "
            "VALUES ('live-gen', ?, 'Live', 'generating', ?, '2099-01-01T00:00:00Z')",
            (live, datetime.now(timezone.utc).strftime(UTC_ISO_FORMAT)),
        )
    conn.commit()
    conn.close()


def _orphan_counts(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        return count_orphan_reference_data(conn)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# (a) Subprocess smoke tests
# ---------------------------------------------------------------------------


def test_subprocess_help_exits_zero() -> None:
    """--help runs in an isolated subprocess with no import errors (AC-6a)."""
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"--help failed with exit {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # The operator sequence (TN-10) is surfaced in --help.
    assert "reconcile-scoreboard --update-baseline" in result.stdout


def test_subprocess_reclaims_backlog_and_exits_zero(tmp_path) -> None:
    """Invoked as a real script against a seeded temp DB, the one-shot reclaims
    the backlog and exits 0 (AC-6a)."""
    db_path = tmp_path / "backlog.db"
    _seed_orphans(db_path)
    assert _orphan_counts(db_path).teams == 1  # precondition: an orphan exists

    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH), "--db-path", str(db_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"exit {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "SUCCESS" in result.stdout
    # The invariant is zero afterward -- the backlog was reclaimed.
    counts = _orphan_counts(db_path)
    assert (counts.teams, counts.players, counts.roster_rows) == (0, 0, 0)


# ---------------------------------------------------------------------------
# (b) In-process tests -- backlog reclamation + three-way exit-code semantics
# ---------------------------------------------------------------------------


def test_in_process_reclaims_backlog_exit_zero(tmp_path) -> None:
    """clean-zero: ran and the post-run invariant is zero -> exit 0 (AC-3b)."""
    db_path = tmp_path / "clean.db"
    _seed_orphans(db_path)
    module = _load_script_module()

    rc = module.run_reclamation(db_path=str(db_path))

    assert rc == module.EXIT_SUCCESS == 0
    counts = _orphan_counts(db_path)
    assert (counts.teams, counts.players, counts.roster_rows) == (0, 0, 0)


def test_in_process_deferred_exit_two(tmp_path) -> None:
    """deferred: a live generation is in flight, guard refuses, nothing ran ->
    exit 2 with a DISTINCT signal (NOT a leak), and the orphan survives (AC-3a)."""
    db_path = tmp_path / "deferred.db"
    _seed_orphans(db_path, generating=True)
    module = _load_script_module()

    rc = module.run_reclamation(db_path=str(db_path))

    assert rc == module.EXIT_DEFERRED == 2
    # Nothing deleted -- the orphan is still present (liveness delay, not a leak).
    assert _orphan_counts(db_path).teams == 1


def test_in_process_residual_exit_three(tmp_path, monkeypatch) -> None:
    """residual-leak: ran but the post-run count is non-zero -> exit 3
    (a genuine overreach/leak), DISTINCT from the deferred signal (AC-3c)."""
    db_path = tmp_path / "residual.db"
    _seed_orphans(db_path)
    module = _load_script_module()

    # Simulate a broken reclamation that reports it ran (not deferred) yet leaves
    # the orphans in place -> the script's post-run count must catch the residual.
    def _fake_reclaim(conn):
        return ReclaimResult(
            teams_deleted=0, players_deleted=0, roster_rows_deleted=0, deferred=False
        )

    monkeypatch.setattr(module, "reclaim_orphan_reference_data", _fake_reclaim)

    rc = module.run_reclamation(db_path=str(db_path))

    assert rc == module.EXIT_RESIDUAL == 3
    # The orphan is still there (the fake did not delete it) -- proving the exit
    # code came from the post-run residual check, not from a real sweep.
    assert _orphan_counts(db_path).teams == 1


def test_in_process_idempotent_second_run(tmp_path) -> None:
    """AC-5: a second run against an already-clean DB deletes nothing and still
    exits 0 (the terminate-after-zero-delta property)."""
    db_path = tmp_path / "idempotent.db"
    _seed_orphans(db_path)
    module = _load_script_module()

    assert module.run_reclamation(db_path=str(db_path)) == 0  # first run sweeps
    # Second run: nothing left to reclaim.
    assert module.run_reclamation(db_path=str(db_path)) == 0
    counts = _orphan_counts(db_path)
    assert (counts.teams, counts.players, counts.roster_rows) == (0, 0, 0)


def test_prints_pre_and_post_counts(tmp_path, capfd) -> None:
    """AC-2: the one-shot prints pre-run and post-run orphan counts (via the
    single-source helper) and the ReclaimResult deletion counts."""
    db_path = tmp_path / "counts.db"
    _seed_orphans(db_path)
    module = _load_script_module()

    module.run_reclamation(db_path=str(db_path))

    out = capfd.readouterr().out
    assert "Pre-run orphan counts:" in out
    assert "Post-run orphan counts:" in out
    assert "Reclaimed: teams=" in out
