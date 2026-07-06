# synthetic-test-data
"""Tests for src.reports.morning_run + the bb report morning-run CLI (E-240-07).

The integration story: multi-team sequential iteration, the LOCAL-date filter
(incl. a late-evening game crossing UTC midnight), the three-way outcome + TN-11
mapping, idempotent re-run (UPSERT dedupe + skip predicate), --dry-run (no
reports, prints the verification line), the preflight-failure path (alert + early
exit), per-game isolation (one failure does not abort), the always-sent summary,
and the unresolved-mappable line + alert. No real HTTP -- the client is a
MagicMock and generate_fn is injected; per .claude/rules/testing.md.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.gamechanger.crawlers.opponents import OpponentRecord
from src.gamechanger.crawlers.schedule import ScheduledGame
from src.gamechanger.exceptions import (
    CredentialExpiredError,
    ForbiddenError,
    GameChangerAPIError,
    RateLimitError,
)
from src.gamechanger.team_resolver import TeamProfile
from src.reports.generator import GenerationResult
from src.reports.morning_run import (
    MorningRunResult,
    PreflightError,
    SlotResult,
    _process_opponent,
    map_outcome_to_vocabulary,
    preflight_credential_check,
    run_morning,
)
from src.gamechanger.opponent_ladder import LadderResult, ResolutionOutcome
from src.util.timezone import derive_local_date, get_operating_timezone, operating_today
from tests.conftest import load_real_schema

_PUBLIC_A = "publicAAAA"
_PUBLIC_B = "publicBBBB"
_GC_UUID_A = "aaaaaaaa-0000-4000-8000-000000000001"
_GC_UUID_B = "bbbbbbbb-0000-4000-8000-000000000002"
_TARGET = date(2026, 6, 20)


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------


@pytest.fixture()
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    load_real_schema(conn)
    return conn


@pytest.fixture()
def disk_db(tmp_path):
    """A DISK-backed schema DB + its path, for tests that open a SECOND connection.

    ``:memory:`` cannot be shared across connections, so the E-252-07 lock-release
    / durability tests (which open a FRESH connection to observe committed state)
    need a real file. Returns ``(conn, path_str)``; the schema is committed so a
    fresh connection sees the tables.
    """
    path = tmp_path / "morning.db"
    conn = sqlite3.connect(str(path))
    load_real_schema(conn)
    conn.commit()
    return conn, str(path)


def _game(
    *,
    event_id: str,
    opponent_id: str,
    opponent_name: str,
    start_datetime: str = "2026-06-20T22:00:00.000Z",
    timezone: str = "America/Chicago",
) -> ScheduledGame:
    # game_date is the UTC date prefix (what schedule.py stores).
    return ScheduledGame(
        opponent_id=opponent_id,
        opponent_name=opponent_name,
        game_date=start_datetime[:10],
        start_datetime=start_datetime,
        timezone=timezone,
        home_away=None,
        event_id=event_id,
        full_day=False,
    )


def _linked_registry(opponent_id: str, progenitor: str = "prog-x") -> list[OpponentRecord]:
    return [
        OpponentRecord(
            root_team_id=opponent_id,
            name="Linked",
            progenitor_team_id=progenitor,
            has_progenitor=True,
            owning_team_id="own",
            is_hidden=False,
        )
    ]


def _ready_result(slug: str = "rep-slug-1") -> GenerationResult:
    return GenerationResult(
        success=True,
        slug=slug,
        title="Scouting Report",
        url=f"https://bbstats.ai/reports/{slug}",
        outcome="ready",
    )


# ---------------------------------------------------------------------------
# derive_local_date (TN-9 / B3)
# ---------------------------------------------------------------------------


def test_derive_local_date_shifts_late_evening_game_back_a_day() -> None:
    """A 22:00 America/Chicago game stored as UTC next-day still has local date today."""
    # 2026-06-21T03:00Z == 2026-06-20 22:00 America/Chicago (CDT, UTC-5).
    local = derive_local_date("2026-06-21T03:00:00.000Z", "America/Chicago")
    assert local == "2026-06-20"


def test_derive_local_date_none_datetime_returns_none() -> None:
    assert derive_local_date(None, "America/Chicago") is None


def test_derive_local_date_unknown_tz_falls_back_to_utc_date() -> None:
    local = derive_local_date("2026-06-20T12:00:00.000Z", "Not/AZone")
    assert local == "2026-06-20"


# ---------------------------------------------------------------------------
# map_outcome_to_vocabulary (TN-11)
# ---------------------------------------------------------------------------


def test_map_outcome_resolved_to_auto_resolved() -> None:
    r = LadderResult(outcome=ResolutionOutcome.RESOLVED, public_id="x", method="progenitor")
    assert map_outcome_to_vocabulary(r) == "auto_resolved"


def test_map_outcome_placeholder() -> None:
    r = LadderResult(outcome=ResolutionOutcome.DEFERRED_PLACEHOLDER)
    assert map_outcome_to_vocabulary(r) == "deferred_placeholder"


def test_map_outcome_unresolved_mappable() -> None:
    r = LadderResult(outcome=ResolutionOutcome.UNRESOLVED_MAPPABLE)
    assert map_outcome_to_vocabulary(r) == "unresolved_mappable"


def test_map_outcome_no_presence_cached_maps_to_no_gc_presence() -> None:
    r = LadderResult(
        outcome=ResolutionOutcome.UNRESOLVED_MAPPABLE,
        method="no_presence",
        from_cache=True,
    )
    assert map_outcome_to_vocabulary(r) == "no_gc_presence"


# ---------------------------------------------------------------------------
# preflight_credential_check (TN-9 / TN-4)
# ---------------------------------------------------------------------------


def test_preflight_ok_when_get_succeeds() -> None:
    client = MagicMock()
    client.get.return_value = {"first_name": "A", "last_name": "B"}
    preflight_credential_check(client)  # no raise
    client.get.assert_called_once()


def test_preflight_credential_expired_raises_preflight_error() -> None:
    client = MagicMock()
    client.get.side_effect = CredentialExpiredError("dead")
    with pytest.raises(PreflightError, match="token refresh"):
        preflight_credential_check(client)


def test_preflight_forbidden_distinguished_from_auth_expiry() -> None:
    client = MagicMock()
    client.get.side_effect = ForbiddenError("denied")
    with pytest.raises(PreflightError, match="403"):
        preflight_credential_check(client)


@pytest.mark.parametrize(
    "exc",
    [
        GameChangerAPIError("5xx after retries"),
        RateLimitError("429"),
        httpx.ConnectError("connection refused"),
    ],
)
def test_preflight_transient_error_raises_preflight_error(exc) -> None:
    """AC-6: a transient (non-auth) preflight failure surfaces as a PreflightError
    (operator alert + abort), NOT an unhandled crash -- and is not collapsed into
    the 403/401 auth meanings (the message says 'transient').
    """
    client = MagicMock()
    client.get.side_effect = exc
    with pytest.raises(PreflightError, match="transient"):
        preflight_credential_check(client)


# ---------------------------------------------------------------------------
# run_morning -- happy path, multi-team, sequential
# ---------------------------------------------------------------------------


def _run(db, client, *, dry_run=False, generate_fn=None, **patches):
    """Invoke run_morning with the team seams patched per test."""
    gen = generate_fn or (lambda pid: _ready_result())
    with (
        patch("src.reports.morning_run.resolve_own_team_gc_uuid", patches["resolve_uuid"]),
        patch("src.reports.morning_run.fetch_schedule", patches["fetch_schedule"]),
        patch("src.reports.morning_run.fetch_opponents", patches["fetch_opponents"]),
        patch("src.reports.morning_run.resolve_opponent", patches["resolve_opponent"]),
        patch("src.reports.morning_run.resolve_team", patches.get("resolve_team", MagicMock(
            return_value=TeamProfile(public_id="x", name="Opp HS", sport="baseball",
                                     record_wins=12, record_losses=8)))),
    ):
        return run_morning(
            patches["team_urls"],
            conn=db,
            client=client,
            target_date=_TARGET,
            dry_run=dry_run,
            generate_fn=gen,
        )


def test_multi_team_sequential_generation(db: sqlite3.Connection) -> None:
    client = MagicMock()
    game_a = _game(event_id="ea", opponent_id="opp-a", opponent_name="Team A Opp")
    game_b = _game(event_id="eb", opponent_id="opp-b", opponent_name="Team B Opp")

    schedules = {_GC_UUID_A: [game_a], _GC_UUID_B: [game_b]}
    gen_calls: list[str] = []

    def fake_gen(pid: str) -> GenerationResult:
        gen_calls.append(pid)
        return _ready_result(slug=f"slug-{pid}")

    result = _run(
        db, client,
        generate_fn=fake_gen,
        team_urls=[_PUBLIC_A, _PUBLIC_B],
        resolve_uuid=MagicMock(side_effect=lambda c, pid: {_PUBLIC_A: _GC_UUID_A, _PUBLIC_B: _GC_UUID_B}[pid]),
        fetch_schedule=MagicMock(side_effect=lambda c, uuid: schedules[uuid]),
        fetch_opponents=MagicMock(side_effect=lambda c, uuid: _linked_registry(
            "opp-a" if uuid == _GC_UUID_A else "opp-b")),
        resolve_opponent=MagicMock(side_effect=lambda **kw: LadderResult(
            outcome=ResolutionOutcome.RESOLVED, public_id=f"pub-{kw['opponent_id']}",
            method="progenitor")),
    )

    assert result.teams_processed == 2
    assert result.generated == 2
    assert gen_calls == ["pub-opp-a", "pub-opp-b"]
    # Two scheduled_report_runs rows written.
    rows = db.execute("SELECT own_team_id, resolution_outcome, delivery_status, report_slug "
                      "FROM scheduled_report_runs ORDER BY id").fetchall()
    assert len(rows) == 2
    assert all(r[1] == "auto_resolved" and r[2] == "generated" for r in rows)


def test_local_date_filter_keeps_late_game_and_drops_off_date(db: sqlite3.Connection) -> None:
    client = MagicMock()
    # on_date: 2026-06-21T03:00Z == 2026-06-20 local (kept)
    on_date = _game(event_id="e1", opponent_id="opp-1", opponent_name="On Date",
                    start_datetime="2026-06-21T03:00:00.000Z")
    # off_date: a game two days later (dropped)
    off_date = _game(event_id="e2", opponent_id="opp-2", opponent_name="Off Date",
                     start_datetime="2026-06-22T18:00:00.000Z")

    result = _run(
        db, client,
        team_urls=[_PUBLIC_A],
        resolve_uuid=MagicMock(return_value=_GC_UUID_A),
        fetch_schedule=MagicMock(return_value=[on_date, off_date]),
        fetch_opponents=MagicMock(return_value=_linked_registry("opp-1")),
        resolve_opponent=MagicMock(side_effect=lambda **kw: LadderResult(
            outcome=ResolutionOutcome.RESOLVED, public_id="pub-1", method="progenitor")),
    )

    # Only the on-date (local) game is processed.
    assert len(result.slots) == 1
    assert result.slots[0].opponent_name == "On Date"
    assert result.slots[0].game_date == "2026-06-20"


def test_dry_run_generates_nothing_and_writes_no_rows(db: sqlite3.Connection) -> None:
    client = MagicMock()
    game = _game(event_id="e1", opponent_id="opp-1", opponent_name="Dry Opp")
    gen = MagicMock()

    result = _run(
        db, client,
        dry_run=True,
        generate_fn=gen,
        team_urls=[_PUBLIC_A],
        resolve_uuid=MagicMock(return_value=_GC_UUID_A),
        fetch_schedule=MagicMock(return_value=[game]),
        fetch_opponents=MagicMock(return_value=_linked_registry("opp-1")),
        resolve_opponent=MagicMock(return_value=LadderResult(
            outcome=ResolutionOutcome.RESOLVED, public_id="pub-1", method="progenitor")),
    )

    gen.assert_not_called()
    # No scheduled_report_runs rows in dry-run.
    assert db.execute("SELECT COUNT(*) FROM scheduled_report_runs").fetchone()[0] == 0
    # The slot carries the resolved name + record (the eyeball line; TN-5).
    assert result.slots[0].resolved_team_name == "Opp HS"
    assert result.slots[0].resolved_record == "12-8"


def test_unresolved_mappable_outcome_recorded(db: sqlite3.Connection) -> None:
    client = MagicMock()
    game = _game(event_id="e1", opponent_id="opp-x", opponent_name="Unindexed HS")

    result = _run(
        db, client,
        team_urls=[_PUBLIC_A],
        resolve_uuid=MagicMock(return_value=_GC_UUID_A),
        fetch_schedule=MagicMock(return_value=[game]),
        fetch_opponents=MagicMock(return_value=[]),
        resolve_opponent=MagicMock(return_value=LadderResult(
            outcome=ResolutionOutcome.UNRESOLVED_MAPPABLE)),
    )

    assert result.unresolved == 1
    row = db.execute("SELECT resolution_outcome, delivery_status FROM scheduled_report_runs").fetchone()
    assert row[0] == "unresolved_mappable"
    assert row[1] is None  # no generation attempted


def test_cached_no_presence_persists_no_gc_presence_and_not_requeued(
    db: sqlite3.Connection,
) -> None:
    """BINDING TIGHTENING regression (resurrection bug at the run-record layer).

    A cached operator-declared no_presence opponent surfaces from the ladder as
    UNRESOLVED_MAPPABLE with method='no_presence', from_cache=True. The run MUST:
      (1) persist scheduled_report_runs.resolution_outcome='no_gc_presence'
          (NOT 'unresolved_mappable'), keying on LadderResult.method, AND
      (2) NOT re-queue it to the operator -- it is NOT counted as unresolved, so
          the CLI emits no operator alert for it.
    If the run mapped on the outcome enum alone, this opponent would be marked
    unresolved_mappable and re-alerted every morning.
    """
    client = MagicMock()
    game = _game(event_id="e1", opponent_id="opp-gone", opponent_name="Gone Team")

    result = _run(
        db, client,
        team_urls=[_PUBLIC_A],
        resolve_uuid=MagicMock(return_value=_GC_UUID_A),
        fetch_schedule=MagicMock(return_value=[game]),
        fetch_opponents=MagicMock(return_value=[]),
        resolve_opponent=MagicMock(return_value=LadderResult(
            outcome=ResolutionOutcome.UNRESOLVED_MAPPABLE,
            method="no_presence",
            from_cache=True,
        )),
    )

    # (1) persisted as no_gc_presence, NOT unresolved_mappable.
    row = db.execute(
        "SELECT resolution_outcome, delivery_status FROM scheduled_report_runs"
    ).fetchone()
    assert row[0] == "no_gc_presence"
    assert row[1] is None  # no generation attempted
    # (2) NOT re-queued: not counted as unresolved (the CLI alert gate is the
    # unresolved_mappable outcome, so no operator alert fires for this slot).
    assert result.unresolved == 0
    assert result.slots[0].resolution_outcome == "no_gc_presence"


def test_placeholder_outcome_recorded_no_generation(db: sqlite3.Connection) -> None:
    client = MagicMock()
    game = _game(event_id="e1", opponent_id="opp-tbd", opponent_name="Winner of Game 3")
    gen = MagicMock()

    result = _run(
        db, client,
        generate_fn=gen,
        team_urls=[_PUBLIC_A],
        resolve_uuid=MagicMock(return_value=_GC_UUID_A),
        fetch_schedule=MagicMock(return_value=[game]),
        fetch_opponents=MagicMock(return_value=[]),
        resolve_opponent=MagicMock(return_value=LadderResult(
            outcome=ResolutionOutcome.DEFERRED_PLACEHOLDER)),
    )

    gen.assert_not_called()
    assert result.deferred == 1
    row = db.execute("SELECT resolution_outcome, delivery_status FROM scheduled_report_runs").fetchone()
    assert row[0] == "deferred_placeholder"
    assert row[1] is None


# ---------------------------------------------------------------------------
# Idempotency (TN-9 / TN-6): UPSERT dedupe + skip predicate
# ---------------------------------------------------------------------------


def test_rerun_is_idempotent_single_row(db: sqlite3.Connection) -> None:
    client = MagicMock()
    game = _game(event_id="e1", opponent_id="opp-1", opponent_name="Opp")

    def fake_gen(pid: str) -> GenerationResult:
        # Faithful to real generate_report: it creates the reports row (so the
        # slug resolves to a reports.id) before returning. The non-expired
        # expires_at is what the skip predicate checks on the re-run.
        db.execute(
            "INSERT OR IGNORE INTO reports (slug, team_id, title, expires_at) "
            "VALUES ('dup-slug', (SELECT id FROM teams LIMIT 1), 'T', "
            "'2999-01-01T00:00:00Z')"
        )
        db.commit()
        return _ready_result(slug="dup-slug")

    def do_run():
        return _run(
            db, client,
            generate_fn=fake_gen,
            team_urls=[_PUBLIC_A],
            resolve_uuid=MagicMock(return_value=_GC_UUID_A),
            fetch_schedule=MagicMock(return_value=[game]),
            fetch_opponents=MagicMock(return_value=_linked_registry("opp-1")),
            resolve_opponent=MagicMock(return_value=LadderResult(
                outcome=ResolutionOutcome.RESOLVED, public_id="pub-1", method="progenitor")),
        )

    # First run generates a report (and its reports row) -> auto_resolved/generated.
    result1 = do_run()
    assert result1.generated == 1

    # Second run: same (team, opponent, date) -> UPSERT (one row), and the prior
    # non-expired success is a SKIP (no regeneration).
    result2 = do_run()
    count = db.execute("SELECT COUNT(*) FROM scheduled_report_runs").fetchone()[0]
    assert count == 1  # UPSERT, not a duplicate
    assert result2.skipped == 1
    assert result2.slots[0].delivery_status == "skipped"


def test_skip_preserves_report_linkage_across_reruns(db: sqlite3.Connection) -> None:
    """F-H2 regression: the idempotency skip must NOT wipe the audit row's
    report_id/report_slug, so a later run still recognizes the prior success and
    does not wastefully regenerate.

    Sequence (per the epic's HIGH finding): run 1 generates; run 2 hits the skip
    branch; run 3 checks the linkage survived and skips again (no regeneration).
    The generator is a fake (no real HTTP) whose call log proves regeneration is
    never attempted after the first run.
    """
    client = MagicMock()
    game = _game(event_id="e1", opponent_id="opp-1", opponent_name="Opp")

    gen_calls: list[str] = []

    def fake_gen(pid: str) -> GenerationResult:
        gen_calls.append(pid)
        # Faithful to real generate_report: it creates the reports row (so the
        # slug resolves to a reports.id) with a non-expired expires_at before
        # returning. The skip predicate keys on that non-expired report_id.
        db.execute(
            "INSERT OR IGNORE INTO reports (slug, team_id, title, expires_at) "
            "VALUES ('dup-slug', (SELECT id FROM teams LIMIT 1), 'T', "
            "'2999-01-01T00:00:00Z')"
        )
        db.commit()
        return _ready_result(slug="dup-slug")

    def do_run():
        return _run(
            db, client,
            generate_fn=fake_gen,
            team_urls=[_PUBLIC_A],
            resolve_uuid=MagicMock(return_value=_GC_UUID_A),
            fetch_schedule=MagicMock(return_value=[game]),
            fetch_opponents=MagicMock(return_value=_linked_registry("opp-1")),
            resolve_opponent=MagicMock(return_value=LadderResult(
                outcome=ResolutionOutcome.RESOLVED, public_id="pub-1", method="progenitor")),
        )

    # Run 1: generates the report + writes the audit row with a real linkage.
    r1 = do_run()
    assert r1.generated == 1
    assert gen_calls == ["pub-1"]
    linked = db.execute(
        "SELECT report_id, report_slug FROM scheduled_report_runs"
    ).fetchone()
    assert linked[0] is not None  # report_id linked
    assert linked[1] == "dup-slug"

    # Run 2: same (team, opponent, date) -> idempotency skip. AC-1: the report
    # linkage must be UNCHANGED after the skip upsert (not nulled), and AC-3: the
    # skip still records delivery_status='skipped' and refreshes the other cols.
    r2 = do_run()
    assert r2.skipped == 1
    assert r2.slots[0].delivery_status == "skipped"
    assert gen_calls == ["pub-1"]  # the skip did NOT regenerate
    after_skip = db.execute(
        "SELECT report_id, report_slug, delivery_status, resolution_outcome, "
        "resolved_public_id FROM scheduled_report_runs"
    ).fetchone()
    assert after_skip[0] == linked[0]  # report_id preserved (still non-NULL)
    assert after_skip[1] == "dup-slug"  # report_slug preserved
    assert after_skip[2] == "skipped"
    assert after_skip[3] == "auto_resolved"
    assert after_skip[4] == "pub-1"

    # Run 3: AC-2: _prior_success still sees the surviving linkage -> skip again,
    # and the injected generator is STILL not called (the F-H2 bug would have
    # regenerated here because run 2 had nulled report_id).
    r3 = do_run()
    assert r3.skipped == 1
    assert gen_calls == ["pub-1"]  # never regenerated across all three runs
    assert db.execute(
        "SELECT COUNT(*) FROM scheduled_report_runs"
    ).fetchone()[0] == 1  # still one audit row (UPSERT, no duplicate)


def test_non_null_key_fallback_when_opponent_id_missing(db: sqlite3.Connection) -> None:
    """A null opponent_id falls back to the event-id token so the key is non-NULL."""
    client = MagicMock()
    game = ScheduledGame(
        opponent_id=None, opponent_name="No ID Opp", game_date="2026-06-20",
        start_datetime="2026-06-20T22:00:00.000Z", timezone="America/Chicago",
        home_away=None, event_id="evt-7", full_day=False,
    )

    _run(
        db, client,
        team_urls=[_PUBLIC_A],
        resolve_uuid=MagicMock(return_value=_GC_UUID_A),
        fetch_schedule=MagicMock(return_value=[game]),
        fetch_opponents=MagicMock(return_value=[]),
        resolve_opponent=MagicMock(return_value=LadderResult(
            outcome=ResolutionOutcome.UNRESOLVED_MAPPABLE)),
    )

    root = db.execute("SELECT opponent_root_team_id FROM scheduled_report_runs").fetchone()[0]
    assert root == "unknown-evt-7"  # non-NULL fallback


# ---------------------------------------------------------------------------
# Per-game isolation (TN-9): one opponent's failure does not abort the loop
# ---------------------------------------------------------------------------


def test_per_game_failure_isolated_loop_continues(db: sqlite3.Connection) -> None:
    client = MagicMock()
    g1 = _game(event_id="e1", opponent_id="opp-1", opponent_name="Boom Opp")
    g2 = _game(event_id="e2", opponent_id="opp-2", opponent_name="Good Opp")

    def flaky_resolve(**kw):
        if kw["opponent_id"] == "opp-1":
            raise RuntimeError("ladder blew up")
        return LadderResult(outcome=ResolutionOutcome.RESOLVED, public_id="pub-2",
                            method="progenitor")

    result = _run(
        db, client,
        team_urls=[_PUBLIC_A],
        resolve_uuid=MagicMock(return_value=_GC_UUID_A),
        fetch_schedule=MagicMock(return_value=[g1, g2]),
        fetch_opponents=MagicMock(return_value=_linked_registry("opp-2")),
        resolve_opponent=MagicMock(side_effect=flaky_resolve),
    )

    # Both slots recorded; the first failed but the loop continued to the second.
    assert len(result.slots) == 2
    assert result.failed == 1
    assert result.generated == 1
    failed_row = db.execute(
        "SELECT error_message FROM scheduled_report_runs WHERE opponent_root_team_id='opp-1'"
    ).fetchone()
    assert "ladder blew up" in failed_row[0]


def test_generate_failure_recorded_as_failed(db: sqlite3.Connection) -> None:
    client = MagicMock()
    game = _game(event_id="e1", opponent_id="opp-1", opponent_name="Opp")

    def failing_gen(pid: str) -> GenerationResult:
        return GenerationResult(success=False, slug="f1", outcome="failed",
                                error_message="all boxscores blocked")

    result = _run(
        db, client,
        generate_fn=failing_gen,
        team_urls=[_PUBLIC_A],
        resolve_uuid=MagicMock(return_value=_GC_UUID_A),
        fetch_schedule=MagicMock(return_value=[game]),
        fetch_opponents=MagicMock(return_value=_linked_registry("opp-1")),
        resolve_opponent=MagicMock(return_value=LadderResult(
            outcome=ResolutionOutcome.RESOLVED, public_id="pub-1", method="progenitor")),
    )

    assert result.failed == 1
    row = db.execute("SELECT delivery_status, error_message FROM scheduled_report_runs").fetchone()
    assert row[0] == "failed"
    assert "boxscores blocked" in row[1]


def test_generate_raises_after_resolution_stays_auto_resolved(
    db: sqlite3.Connection,
) -> None:
    """Codex Finding 1: generate_report RAISING on a RESOLVED opponent must map
    to resolution_outcome='auto_resolved' + delivery_status='failed', NOT
    unresolved_mappable — so the operator is NOT told to map an already-resolved
    opponent. It must also NOT count as unresolved (no operator prompt).
    """
    client = MagicMock()
    game = _game(event_id="e1", opponent_id="opp-1", opponent_name="Resolved Opp")

    def raising_gen(pid: str) -> GenerationResult:
        raise RuntimeError("generator exploded mid-pipeline")

    result = _run(
        db, client,
        generate_fn=raising_gen,
        team_urls=[_PUBLIC_A],
        resolve_uuid=MagicMock(return_value=_GC_UUID_A),
        fetch_schedule=MagicMock(return_value=[game]),
        fetch_opponents=MagicMock(return_value=_linked_registry("opp-1")),
        resolve_opponent=MagicMock(return_value=LadderResult(
            outcome=ResolutionOutcome.RESOLVED, public_id="pub-1", method="progenitor")),
    )

    # Counted as a failure, NOT as unresolved (no map-opponent prompt for it).
    assert result.failed == 1
    assert result.unresolved == 0
    row = db.execute(
        "SELECT resolution_outcome, delivery_status, resolved_public_id, error_message "
        "FROM scheduled_report_runs"
    ).fetchone()
    assert row[0] == "auto_resolved"  # NOT unresolved_mappable
    assert row[1] == "failed"
    assert row[2] == "pub-1"  # the opponent IS resolved
    assert "generator exploded" in row[3]
    # The slot object reflects the same classification.
    slot = result.slots[0]
    assert slot.resolution_outcome == "auto_resolved"
    assert slot.resolved_public_id == "pub-1"


def test_resolution_phase_crash_not_misclassified_as_mappable(
    db: sqlite3.Connection,
) -> None:
    """A crash DURING resolution (resolve_opponent raises) is a failure WITH an
    error_message — it must NOT be counted as unresolved (the error_message gate
    suppresses the operator map-opponent prompt). Per-game isolation preserved.
    """
    client = MagicMock()
    game = _game(event_id="e1", opponent_id="opp-x", opponent_name="Crash Opp")

    result = _run(
        db, client,
        team_urls=[_PUBLIC_A],
        resolve_uuid=MagicMock(return_value=_GC_UUID_A),
        fetch_schedule=MagicMock(return_value=[game]),
        fetch_opponents=MagicMock(return_value=[]),
        resolve_opponent=MagicMock(side_effect=RuntimeError("ladder crashed")),
    )

    # Failure, with an error, and NOT counted as unresolved.
    assert result.failed == 1
    assert result.unresolved == 0
    row = db.execute(
        "SELECT delivery_status, error_message FROM scheduled_report_runs"
    ).fetchone()
    assert row[0] == "failed"
    assert "ladder crashed" in row[1]
    # The slot carries an error_message (the discriminator that suppresses the
    # operator map-opponent prompt downstream).
    assert result.slots[0].error_message is not None


def test_no_games_outcome_recorded(db: sqlite3.Connection) -> None:
    client = MagicMock()
    game = _game(event_id="e1", opponent_id="opp-1", opponent_name="Opp")

    def no_games_gen(pid: str) -> GenerationResult:
        return GenerationResult(success=False, slug="ng1", outcome="no_games",
                                completed_games=0)

    result = _run(
        db, client,
        generate_fn=no_games_gen,
        team_urls=[_PUBLIC_A],
        resolve_uuid=MagicMock(return_value=_GC_UUID_A),
        fetch_schedule=MagicMock(return_value=[game]),
        fetch_opponents=MagicMock(return_value=_linked_registry("opp-1")),
        resolve_opponent=MagicMock(return_value=LadderResult(
            outcome=ResolutionOutcome.RESOLVED, public_id="pub-1", method="progenitor")),
    )

    assert result.no_games == 1
    row = db.execute("SELECT delivery_status FROM scheduled_report_runs").fetchone()
    assert row[0] == "no_games"


def test_unresolvable_team_uuid_skips_team(db: sqlite3.Connection) -> None:
    """A team whose gc_uuid cannot be resolved is skipped, not crashed."""
    client = MagicMock()

    result = _run(
        db, client,
        team_urls=[_PUBLIC_A],
        resolve_uuid=MagicMock(return_value=None),  # resolution fails
        fetch_schedule=MagicMock(),
        fetch_opponents=MagicMock(),
        resolve_opponent=MagicMock(),
    )

    assert result.teams_processed == 1
    assert result.slots == []


# ---------------------------------------------------------------------------
# AC-12: 403 (per-team denial) isolated; 401 (token death) run-fatal
# ---------------------------------------------------------------------------


def test_forbidden_on_one_team_isolated_others_continue(db: sqlite3.Connection) -> None:
    """A 403 on team A is isolated; team B still processes (AC-12 distinction)."""
    client = MagicMock()
    game_b = _game(event_id="eb", opponent_id="opp-b", opponent_name="Team B Opp")

    def schedule_side(c, uuid):
        if uuid == _GC_UUID_A:
            raise ForbiddenError("denied for A")
        return [game_b]

    result = _run(
        db, client,
        team_urls=[_PUBLIC_A, _PUBLIC_B],
        resolve_uuid=MagicMock(side_effect=lambda c, pid: {
            _PUBLIC_A: _GC_UUID_A, _PUBLIC_B: _GC_UUID_B}[pid]),
        fetch_schedule=MagicMock(side_effect=schedule_side),
        fetch_opponents=MagicMock(return_value=_linked_registry("opp-b")),
        resolve_opponent=MagicMock(return_value=LadderResult(
            outcome=ResolutionOutcome.RESOLVED, public_id="pub-b", method="progenitor")),
    )

    # Team A's 403 was isolated; team B generated.
    assert result.teams_processed == 2
    assert result.generated == 1
    assert len(result.slots) == 1
    assert result.slots[0].opponent_name == "Team B Opp"
    # SHOULD FIX: the per-team 403 is counted and surfaced in the summary detail.
    assert result.denied == 1
    assert "1 team(s) skipped: access denied (403)." in result.detail_lines
    # Not the systematic-all-denied wording (only 1 of 2 denied).
    assert "ALL" not in result.denied_detail


def test_all_teams_denied_surfaces_systematic_signal(db: sqlite3.Connection) -> None:
    """denied == teams_processed -> the FALSE-403 / check-pins signal (SHOULD FIX).

    A misconfigured CRAWLER version pin passes the /me/user preflight (different
    pin) but 403s EVERY team. The summary detail must make this explicit so a
    0-generated/0-unresolved summary is not mistaken for 'no games today'.
    """
    client = MagicMock()

    result = _run(
        db, client,
        team_urls=[_PUBLIC_A, _PUBLIC_B],
        resolve_uuid=MagicMock(side_effect=lambda c, pid: {
            _PUBLIC_A: _GC_UUID_A, _PUBLIC_B: _GC_UUID_B}[pid]),
        fetch_schedule=MagicMock(side_effect=ForbiddenError("false 403 on every team")),
        fetch_opponents=MagicMock(),
        resolve_opponent=MagicMock(),
    )

    assert result.teams_processed == 2
    assert result.denied == 2
    assert result.generated == 0
    assert result.unresolved == 0
    # The systematic signal: ALL teams denied + the check-credentials/pins hint.
    detail = result.denied_detail
    assert "ALL 2 team(s) were denied (403)" in detail
    assert "version-pin" in detail
    assert detail in result.detail_lines


def test_credential_expired_mid_run_propagates(db: sqlite3.Connection) -> None:
    """A 401 (true token death) is run-fatal and surfaces, not swallowed."""
    client = MagicMock()

    with pytest.raises(CredentialExpiredError):
        _run(
            db, client,
            team_urls=[_PUBLIC_A],
            resolve_uuid=MagicMock(return_value=_GC_UUID_A),
            fetch_schedule=MagicMock(side_effect=CredentialExpiredError("token died")),
            fetch_opponents=MagicMock(),
            resolve_opponent=MagicMock(),
        )


# ---------------------------------------------------------------------------
# E-252-02: broadened per-team isolation (transient + 429) + 429 escalation
# ---------------------------------------------------------------------------

_PUBLIC_C = "publicCCCC"
_GC_UUID_C = "cccccccc-0000-4000-8000-000000000003"


@pytest.mark.parametrize(
    "transient_exc",
    [GameChangerAPIError("5xx after retries"), httpx.ConnectError("connection refused")],
)
def test_transient_error_on_one_team_isolated_and_counted(
    db: sqlite3.Connection, transient_exc
) -> None:
    """AC-1: a transient 5xx / connection error on team A is isolated (team B still
    processes, the run does not abort) and counted in the DISTINCT `transient`
    tally + surfaced in the summary detail. NOT the slot-level `failed`.
    """
    client = MagicMock()
    game_b = _game(event_id="eb", opponent_id="opp-b", opponent_name="Team B Opp")

    def schedule_side(c, uuid):
        if uuid == _GC_UUID_A:
            raise transient_exc
        return [game_b]

    result = _run(
        db, client,
        team_urls=[_PUBLIC_A, _PUBLIC_B],
        resolve_uuid=MagicMock(side_effect=lambda c, pid: {
            _PUBLIC_A: _GC_UUID_A, _PUBLIC_B: _GC_UUID_B}[pid]),
        fetch_schedule=MagicMock(side_effect=schedule_side),
        fetch_opponents=MagicMock(return_value=_linked_registry("opp-b")),
        resolve_opponent=MagicMock(return_value=LadderResult(
            outcome=ResolutionOutcome.RESOLVED, public_id="pub-b", method="progenitor")),
    )

    assert result.teams_processed == 2
    assert result.transient == 1  # distinct per-team tally
    assert result.failed == 0  # NOT the slot-level generation-failure counter
    assert result.denied == 0
    assert result.rate_limited == 0
    assert result.generated == 1  # team B still processed
    assert len(result.slots) == 1
    assert "transient error" in result.detail_lines


def test_rate_limit_on_one_team_isolated_and_tallied(db: sqlite3.Connection) -> None:
    """AC-3: a single team-level 429 is isolated (team B still processes, the
    always-sent summary still fires) and recorded in the run-level `rate_limited`
    tally (NOT a CHECK-constrained scheduled_report_runs value). No early abort.
    """
    client = MagicMock()
    game_b = _game(event_id="eb", opponent_id="opp-b", opponent_name="Team B Opp")

    def schedule_side(c, uuid):
        if uuid == _GC_UUID_A:
            raise RateLimitError("429 on team A schedule")
        return [game_b]

    result = _run(
        db, client,
        team_urls=[_PUBLIC_A, _PUBLIC_B],
        resolve_uuid=MagicMock(side_effect=lambda c, pid: {
            _PUBLIC_A: _GC_UUID_A, _PUBLIC_B: _GC_UUID_B}[pid]),
        fetch_schedule=MagicMock(side_effect=schedule_side),
        fetch_opponents=MagicMock(return_value=_linked_registry("opp-b")),
        resolve_opponent=MagicMock(return_value=LadderResult(
            outcome=ResolutionOutcome.RESOLVED, public_id="pub-b", method="progenitor")),
    )

    assert result.teams_processed == 2
    assert result.rate_limited == 1
    assert result.rate_limit_aborted is False  # a single 429 does NOT escalate
    assert result.generated == 1  # team B still processed
    # No 429 slot was written to the audit table (a team-level 429 has zero slots).
    assert db.execute(
        "SELECT COUNT(*) FROM scheduled_report_runs WHERE opponent_root_team_id='opp-a'"
    ).fetchone()[0] == 0
    assert "rate limited (429)" in result.detail_lines


def test_recurring_rate_limit_escalates_to_early_stop(db: sqlite3.Connection) -> None:
    """AC-4: a 429 that RECURS across teams (2nd occurrence) stops the run early --
    no further GC calls for the remaining teams -- and the summary reports
    'rate-limited -- aborted early'.
    """
    client = MagicMock()
    game_c = _game(event_id="ec", opponent_id="opp-c", opponent_name="Team C Opp")

    resolve_calls: list[str] = []

    def resolve_side(c, pid):
        resolve_calls.append(pid)
        return {_PUBLIC_A: _GC_UUID_A, _PUBLIC_B: _GC_UUID_B, _PUBLIC_C: _GC_UUID_C}[pid]

    def schedule_side(c, uuid):
        if uuid in (_GC_UUID_A, _GC_UUID_B):
            raise RateLimitError("429 storm")
        return [game_c]  # team C would generate -- but must never be reached

    result = _run(
        db, client,
        team_urls=[_PUBLIC_A, _PUBLIC_B, _PUBLIC_C],
        resolve_uuid=MagicMock(side_effect=resolve_side),
        fetch_schedule=MagicMock(side_effect=schedule_side),
        fetch_opponents=MagicMock(return_value=_linked_registry("opp-c")),
        resolve_opponent=MagicMock(return_value=LadderResult(
            outcome=ResolutionOutcome.RESOLVED, public_id="pub-c", method="progenitor")),
    )

    assert result.rate_limited == 2
    assert result.rate_limit_aborted is True
    # Team C was never started: teams_processed stopped at 2 and no GC call
    # (resolve_own_team_gc_uuid) was made for it.
    assert result.teams_processed == 2
    assert _PUBLIC_C not in resolve_calls
    assert result.generated == 0
    assert "aborted early" in result.detail_lines


def test_bare_401_run_fatal_across_multiple_teams(db: sqlite3.Connection) -> None:
    """AC-2: a bare CredentialExpiredError (401) is NOT swallowed by the broadened
    transient/429 isolation -- it stays run-fatal (propagates), so a real token
    death is never collapsed into a per-team skip. Team B is never reached.
    """
    client = MagicMock()

    resolve_calls: list[str] = []

    def resolve_side(c, pid):
        resolve_calls.append(pid)
        return {_PUBLIC_A: _GC_UUID_A, _PUBLIC_B: _GC_UUID_B}[pid]

    with pytest.raises(CredentialExpiredError):
        _run(
            db, client,
            team_urls=[_PUBLIC_A, _PUBLIC_B],
            resolve_uuid=MagicMock(side_effect=resolve_side),
            fetch_schedule=MagicMock(side_effect=CredentialExpiredError("token died")),
            fetch_opponents=MagicMock(),
            resolve_opponent=MagicMock(),
        )

    # The 401 propagated out of team A; team B was never processed.
    assert resolve_calls == [_PUBLIC_A]


def test_broadened_catch_rolls_back_partial_dml_before_next_team(
    db: sqlite3.Connection,
) -> None:
    """AC-5 / TN-10: a per-team failure whose crawl partially wrote to the SHARED
    connection must roll that DML back before the next team, so the next
    successful team's commit does NOT silently persist the failed team's write.
    """
    client = MagicMock()
    game_b = _game(event_id="eb", opponent_id="opp-b", opponent_name="Team B Opp")

    def opponents_side(c, uuid):
        if uuid == _GC_UUID_A:
            # Simulate the ladder partially writing to the shared conn (an audit
            # row) BEFORE the crawl fails. team A's own row exists by now
            # (ensure_team_row ran before fetch_opponents).
            own_id = db.execute(
                "SELECT id FROM teams WHERE public_id = ?", (_PUBLIC_A,)
            ).fetchone()[0]
            db.execute(
                "INSERT INTO scheduled_report_runs "
                "(game_date, own_team_id, opponent_root_team_id, resolution_outcome) "
                "VALUES ('2026-06-20', ?, 'SENTINEL-partial', 'unresolved_mappable')",
                (own_id,),
            )
            raise GameChangerAPIError("crawl blew up after a partial write")
        return _linked_registry("opp-b")

    result = _run(
        db, client,
        team_urls=[_PUBLIC_A, _PUBLIC_B],
        resolve_uuid=MagicMock(side_effect=lambda c, pid: {
            _PUBLIC_A: _GC_UUID_A, _PUBLIC_B: _GC_UUID_B}[pid]),
        fetch_schedule=MagicMock(side_effect=lambda c, uuid: [game_b] if uuid == _GC_UUID_B else []),
        fetch_opponents=MagicMock(side_effect=opponents_side),
        resolve_opponent=MagicMock(return_value=LadderResult(
            outcome=ResolutionOutcome.RESOLVED, public_id="pub-b", method="progenitor")),
    )

    # Team B generated (and committed) -- proving the connection survived the
    # rollback and remained usable.
    assert result.transient == 1
    assert result.generated == 1
    # The partial sentinel write from failed team A was rolled back, NOT carried
    # into team B's commit.
    assert db.execute(
        "SELECT COUNT(*) FROM scheduled_report_runs WHERE opponent_root_team_id='SENTINEL-partial'"
    ).fetchone()[0] == 0
    # Team B's real audit row IS persisted.
    assert db.execute(
        "SELECT COUNT(*) FROM scheduled_report_runs WHERE opponent_root_team_id='opp-b'"
    ).fetchone()[0] == 1


# ---------------------------------------------------------------------------
# E-252-05: operating-timezone seam + default target date
# ---------------------------------------------------------------------------


def _fullday_game(*, event_id: str, opponent_id: str, opponent_name: str, game_date: str) -> ScheduledGame:
    """A full-day ScheduledGame (no start_datetime) whose local date == game_date."""
    return ScheduledGame(
        opponent_id=opponent_id,
        opponent_name=opponent_name,
        game_date=game_date,
        start_datetime=None,
        timezone=None,
        home_away=None,
        event_id=event_id,
        full_day=True,
    )


def test_get_operating_timezone_defaults_to_chicago_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-2: unset OPERATING_TIMEZONE -> the venue default (America/Chicago)."""
    monkeypatch.delenv("OPERATING_TIMEZONE", raising=False)
    assert get_operating_timezone().key == "America/Chicago"


def test_get_operating_timezone_reads_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-2: an explicit OPERATING_TIMEZONE is honored."""
    monkeypatch.setenv("OPERATING_TIMEZONE", "America/New_York")
    assert get_operating_timezone().key == "America/New_York"


def test_get_operating_timezone_invalid_value_falls_back_with_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-4: an unknown/invalid tz degrades to the default WITH a logged WARNING
    (mirrors derive_local_date), never crashing.
    """
    monkeypatch.setenv("OPERATING_TIMEZONE", "Not/AZone")
    with caplog.at_level(logging.WARNING, logger="src.util.timezone"):
        tz = get_operating_timezone()
    assert tz.key == "America/Chicago"
    assert any("Not/AZone" in r.getMessage() for r in caplog.records)


def test_operating_today_evening_rollover_uses_operating_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-1 (seam unit): an instant that is 'tomorrow' in UTC but 'today' in the
    operating tz resolves to the operating-tz (today) date.
    """
    monkeypatch.delenv("OPERATING_TIMEZONE", raising=False)  # default Chicago
    # 2026-06-21T02:00Z == 2026-06-20 21:00 America/Chicago (CDT, UTC-5).
    frozen = datetime(2026, 6, 21, 2, 0, tzinfo=timezone.utc)
    assert operating_today(now=frozen) == date(2026, 6, 20)  # operating today
    assert frozen.date() == date(2026, 6, 21)  # UTC would say tomorrow


def test_operating_today_respects_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-2: the seam's date derivation honors the env override too."""
    monkeypatch.setenv("OPERATING_TIMEZONE", "Pacific/Kiritimati")  # UTC+14
    # 2026-06-20T20:00Z == 2026-06-21 10:00 in UTC+14.
    frozen = datetime(2026, 6, 20, 20, 0, tzinfo=timezone.utc)
    assert operating_today(now=frozen) == date(2026, 6, 21)


def test_run_morning_default_target_date_uses_operating_tz_not_utc(
    db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-1 (through run_morning): with NO --date, an evening run defaults to the
    operating-tz date (today), NOT the container UTC date (tomorrow) -- so it
    filters to today's games, not tomorrow's. The wall clock is frozen (TN-8).
    """
    monkeypatch.delenv("OPERATING_TIMEZONE", raising=False)  # default Chicago
    client = MagicMock()
    # 2026-06-21T02:00Z == 2026-06-20 21:00 America/Chicago: UTC=tomorrow, op=today.
    frozen = datetime(2026, 6, 21, 2, 0, tzinfo=timezone.utc)
    game_today = _fullday_game(
        event_id="e1", opponent_id="opp-1", opponent_name="Today Game", game_date="2026-06-20"
    )
    game_tomorrow = _fullday_game(
        event_id="e2", opponent_id="opp-2", opponent_name="Tomorrow Game", game_date="2026-06-21"
    )

    with (
        # Freeze the seam's wall clock without bypassing its tz logic.
        patch("src.reports.morning_run.operating_today", lambda: operating_today(now=frozen)),
        patch("src.reports.morning_run.resolve_own_team_gc_uuid", MagicMock(return_value=_GC_UUID_A)),
        patch("src.reports.morning_run.fetch_schedule", MagicMock(return_value=[game_today, game_tomorrow])),
        patch("src.reports.morning_run.fetch_opponents", MagicMock(return_value=_linked_registry("opp-1"))),
        patch("src.reports.morning_run.resolve_opponent", MagicMock(return_value=LadderResult(
            outcome=ResolutionOutcome.RESOLVED, public_id="pub-1", method="progenitor"))),
        patch("src.reports.morning_run.resolve_team", MagicMock(return_value=TeamProfile(
            public_id="x", name="Opp HS", sport="baseball", record_wins=1, record_losses=0))),
    ):
        result = run_morning(
            [_PUBLIC_A],
            conn=db,
            client=client,
            target_date=None,  # exercise the default-date path
            generate_fn=lambda pid: _ready_result(),
        )

    # Only the operating-tz-today (2026-06-20) game is processed; the UTC-today
    # (2026-06-21) game is filtered out -- proving the default used the operating
    # date, not the UTC date.
    assert len(result.slots) == 1
    assert result.slots[0].game_date == "2026-06-20"
    assert result.slots[0].opponent_name == "Today Game"


# ---------------------------------------------------------------------------
# E-252-07: write-transaction discipline + slot lifecycle
# ---------------------------------------------------------------------------


def _seed_team(conn: sqlite3.Connection, public_id: str) -> int:
    """Insert a team row and return its integer id (for _process_opponent tests)."""
    from src.db.teams import ensure_team_row

    tid = ensure_team_row(conn, public_id=public_id, gc_uuid=_GC_UUID_A, source="test")
    conn.commit()
    return tid


def _patched_run(conn, client, path=None, **overrides):
    """run_morning with the team seams patched; caller supplies overrides."""
    defaults = dict(
        resolve_uuid=MagicMock(return_value=_GC_UUID_A),
        fetch_opponents=MagicMock(return_value=_linked_registry("opp-1")),
        resolve_opponent=MagicMock(return_value=LadderResult(
            outcome=ResolutionOutcome.RESOLVED, public_id="pub-1", method="progenitor")),
        resolve_team=MagicMock(return_value=TeamProfile(
            public_id="x", name="Opp HS", sport="baseball", record_wins=1, record_losses=0)),
        team_urls=[_PUBLIC_A],
        generate_fn=lambda pid: _ready_result(),
    )
    defaults.update(overrides)
    with (
        patch("src.reports.morning_run.resolve_own_team_gc_uuid", defaults["resolve_uuid"]),
        patch("src.reports.morning_run.fetch_schedule", defaults["fetch_schedule"]),
        patch("src.reports.morning_run.fetch_opponents", defaults["fetch_opponents"]),
        patch("src.reports.morning_run.resolve_opponent", defaults["resolve_opponent"]),
        patch("src.reports.morning_run.resolve_team", defaults["resolve_team"]),
    ):
        return run_morning(
            defaults["team_urls"], conn=conn, client=client,
            target_date=_TARGET, generate_fn=defaults["generate_fn"],
        )


def test_own_team_row_committed_before_network_fetch(disk_db) -> None:
    """AC-1 (TN-5): the own-team row is conn.commit()ed IMMEDIATELY after
    ensure_team_row -- before fetch_schedule -- so no write transaction is held
    across the network crawl. Mechanism (per DE): the mocked fetch_schedule opens
    a FRESH connection and the own-team row is already visible.
    """
    conn, path = disk_db
    client = MagicMock()
    game = _game(event_id="e1", opponent_id="opp-1", opponent_name="Opp")
    seen: dict = {}

    def fake_schedule(c, uuid):
        fresh = sqlite3.connect(path)
        seen["team_row"] = fresh.execute(
            "SELECT id FROM teams WHERE public_id = ?", (_PUBLIC_A,)
        ).fetchone()
        fresh.close()
        return [game]

    _patched_run(conn, client, fetch_schedule=MagicMock(side_effect=fake_schedule))

    # The own-team row was already committed (visible from a fresh connection)
    # at the moment fetch_schedule ran -- proving the commit landed before the fetch.
    assert seen["team_row"] is not None


def test_no_slot_team_own_row_persists_after_close(disk_db) -> None:
    """AC-2 (TN-5): a team whose schedule yields ZERO target-date slots still keeps
    its own-team row after conn.close() -- it is NOT rolled back (previously the
    no-slot path committed nothing, so close() rolled the INSERT back).
    """
    conn, path = disk_db
    client = MagicMock()
    # A game two days off the target date -> filtered out -> zero slots.
    off_date = _game(
        event_id="e1", opponent_id="opp-1", opponent_name="Off Date",
        start_datetime="2026-06-22T18:00:00.000Z",
    )

    result = _patched_run(conn, client, fetch_schedule=MagicMock(return_value=[off_date]))
    assert result.slots == []  # zero slots for the target date
    conn.close()  # default isolation: an uncommitted own-team INSERT would roll back here

    fresh = sqlite3.connect(path)
    row = fresh.execute("SELECT id FROM teams WHERE public_id = ?", (_PUBLIC_A,)).fetchone()
    fresh.close()
    assert row is not None  # own-team row survived (was committed, not rolled back)


def test_upsert_slot_error_isolated_run_continues(db: sqlite3.Connection) -> None:
    """AC-3: a DB error from the per-slot audit write (_upsert_slot) is caught,
    logged, and the run continues -- one slot-recording error no longer aborts the
    remaining slots/teams.
    """
    client = MagicMock()
    game_a = _game(event_id="ea", opponent_id="opp-a", opponent_name="A Opp")
    game_b = _game(event_id="eb", opponent_id="opp-b", opponent_name="B Opp")
    schedules = {_GC_UUID_A: [game_a], _GC_UUID_B: [game_b]}

    # UNRESOLVED_MAPPABLE slots: no reservation write, so the ONLY _upsert_slot
    # call is the FINAL run-loop audit write -- exactly the item-3 seam under test.
    def flaky_upsert(conn, slot):
        if slot.opponent_root_team_id == "opp-a":
            raise sqlite3.OperationalError("database is locked")
        # team B: succeed (no-op is fine; we only assert the run continued)

    with patch("src.reports.morning_run._upsert_slot", side_effect=flaky_upsert):
        result = _patched_run(
            db, client,
            team_urls=[_PUBLIC_A, _PUBLIC_B],
            resolve_uuid=MagicMock(side_effect=lambda c, pid: {
                _PUBLIC_A: _GC_UUID_A, _PUBLIC_B: _GC_UUID_B}[pid]),
            fetch_schedule=MagicMock(side_effect=lambda c, uuid: schedules[uuid]),
            fetch_opponents=MagicMock(return_value=[]),
            resolve_opponent=MagicMock(return_value=LadderResult(
                outcome=ResolutionOutcome.UNRESOLVED_MAPPABLE)),
        )

    # Both slots were still processed -- team A's audit-write error did not abort
    # the run before team B.
    assert len(result.slots) == 2
    assert {s.opponent_root_team_id for s in result.slots} == {"opp-a", "opp-b"}


class _RollbackSpyConnection(sqlite3.Connection):
    """A sqlite3.Connection that counts rollback() calls.

    sqlite3.Connection.rollback is read-only (can't be patched), so we subclass to
    observe the E-252-07 AC-4 per-game rollback.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.rollback_calls = 0

    def rollback(self):  # type: ignore[override]
        self.rollback_calls += 1
        return super().rollback()


def test_per_game_crash_rolls_back_and_no_open_txn() -> None:
    """AC-4 (TN-10 defense-in-depth): the pre-existing per-game except calls
    conn.rollback() when _process_opponent raises, and the connection has no open
    transaction afterward.
    """
    conn = sqlite3.connect(":memory:", factory=_RollbackSpyConnection)
    load_real_schema(conn)
    client = MagicMock()
    game = _game(event_id="e1", opponent_id="opp-x", opponent_name="Crash Opp")

    result = _patched_run(
        conn, client,
        fetch_schedule=MagicMock(return_value=[game]),
        fetch_opponents=MagicMock(return_value=[]),
        resolve_opponent=MagicMock(side_effect=RuntimeError("ladder crashed")),
    )

    assert conn.rollback_calls >= 1  # the :513 branch rollback ran
    assert conn.in_transaction is False  # no dangling open write transaction
    assert result.failed == 1  # the crash slot was still recorded


def test_reserve_before_generate_row_exists_at_generation(disk_db) -> None:
    """AC-5: the slot's audit row is RESERVED (written, auto_resolved,
    delivery_status IS NULL) BEFORE generate_fn runs, then finalized after.
    """
    conn, path = disk_db
    client = MagicMock()
    game = _game(event_id="e1", opponent_id="opp-1", opponent_name="Opp")
    seen: dict = {}

    def fake_gen(pid):
        fresh = sqlite3.connect(path)
        seen["row"] = fresh.execute(
            "SELECT resolution_outcome, delivery_status FROM scheduled_report_runs "
            "WHERE opponent_root_team_id = 'opp-1'"
        ).fetchone()
        fresh.close()
        return _ready_result(slug="gen-slug")

    _patched_run(conn, client,
                 fetch_schedule=MagicMock(return_value=[game]),
                 generate_fn=fake_gen)

    # At generation time the slot was already reserved (row present, delivery NULL).
    assert seen["row"] is not None
    assert seen["row"][0] == "auto_resolved"
    assert seen["row"][1] is None
    # After the run it is finalized to generated.
    final = conn.execute(
        "SELECT delivery_status, report_slug FROM scheduled_report_runs "
        "WHERE opponent_root_team_id = 'opp-1'"
    ).fetchone()
    assert final[0] == "generated"
    assert final[1] == "gen-slug"


def test_fresh_reservation_skips_generation(db: sqlite3.Connection) -> None:
    """AC-5: a FRESH reservation (a concurrent run's in-progress slot) makes
    _process_opponent SKIP generation rather than double-generate.
    """
    team_id = _seed_team(db, _PUBLIC_A)
    # A concurrent run's fresh reservation: auto_resolved, delivery_status NULL, now.
    db.execute(
        "INSERT INTO scheduled_report_runs "
        "(game_date, own_team_id, opponent_root_team_id, resolution_outcome, "
        " delivery_status, updated_at) "
        "VALUES ('2026-06-20', ?, 'opp-1', 'auto_resolved', NULL, datetime('now'))",
        (team_id,),
    )
    db.commit()
    gen = MagicMock(return_value=_ready_result())

    with (
        patch("src.reports.morning_run.resolve_opponent", MagicMock(return_value=LadderResult(
            outcome=ResolutionOutcome.RESOLVED, public_id="pub-1", method="progenitor"))),
        patch("src.reports.morning_run.resolve_team", MagicMock(return_value=TeamProfile(
            public_id="x", name="Opp HS", sport="baseball", record_wins=1, record_losses=0))),
    ):
        slot = _process_opponent(
            conn=db, client=MagicMock(), own_team_id=team_id,
            game=_game(event_id="e1", opponent_id="opp-1", opponent_name="Opp"),
            game_date="2026-06-20", registry=[], dry_run=False, generate_fn=gen,
        )

    gen.assert_not_called()  # a concurrent fresh reservation -> no double-generation
    assert slot.delivery_status == "skipped"


def test_fresh_reservation_skip_does_not_clobber_concurrent_reservation(
    db: sqlite3.Connection,
) -> None:
    """P1#1 regression: the fresh-reservation SKIP must NOT persist (clobber) the
    concurrent run's in-flight `delivery_status IS NULL` reservation. Drives the
    REAL run_morning flow (not _process_opponent directly, which the prior test
    could not catch) across two overlapping runs and asserts the reservation stays
    NULL and the generator is never called -- so a third overlapping run still sees
    it fresh and skips (no double-generation)."""
    client = MagicMock()
    game = _game(event_id="e1", opponent_id="opp-1", opponent_name="Opp")

    # Run A (in-flight, mid-generation): the team + a FRESH NULL reservation.
    team_id = _seed_team(db, _PUBLIC_A)
    db.execute(
        "INSERT INTO scheduled_report_runs "
        "(game_date, own_team_id, opponent_root_team_id, resolution_outcome, "
        " delivery_status, updated_at) "
        "VALUES ('2026-06-20', ?, 'opp-1', 'auto_resolved', NULL, datetime('now'))",
        (team_id,),
    )
    db.commit()
    gen = MagicMock(return_value=_ready_result())

    # Run B: run_morning processes the same slot -> fresh reservation -> skip.
    r_b = _patched_run(
        db, client, fetch_schedule=MagicMock(return_value=[game]), generate_fn=gen
    )
    assert r_b.skipped == 1  # still tallied as skipped in-memory
    assert gen.call_count == 0  # run B did not generate
    row = db.execute(
        "SELECT delivery_status FROM scheduled_report_runs WHERE opponent_root_team_id='opp-1'"
    ).fetchone()
    assert row[0] is None  # the concurrent NULL reservation was NOT clobbered to 'skipped'

    # Run C: still sees the fresh reservation -> skips; the generator is STILL never
    # called -> no double-generation with the (still-running) run A.
    _patched_run(
        db, client, fetch_schedule=MagicMock(return_value=[game]), generate_fn=gen
    )
    row2 = db.execute(
        "SELECT delivery_status FROM scheduled_report_runs WHERE opponent_root_team_id='opp-1'"
    ).fetchone()
    assert row2[0] is None
    assert gen.call_count == 0  # generator called ZERO times across B and C
    # Exactly one audit row for the slot (no duplicate from the skip).
    assert db.execute(
        "SELECT COUNT(*) FROM scheduled_report_runs WHERE opponent_root_team_id='opp-1'"
    ).fetchone()[0] == 1


def test_stale_reservation_regenerates(db: sqlite3.Connection) -> None:
    """AC-5 (crash self-heal): a STALE reservation (a crashed run's NULL row, older
    than the lease) is abandoned and regenerated -- a crash does not block forever.
    """
    team_id = _seed_team(db, _PUBLIC_A)
    db.execute(
        "INSERT INTO scheduled_report_runs "
        "(game_date, own_team_id, opponent_root_team_id, resolution_outcome, "
        " delivery_status, updated_at) "
        "VALUES ('2026-06-20', ?, 'opp-1', 'auto_resolved', NULL, "
        " datetime('now', '-3600 seconds'))",
        (team_id,),
    )
    db.commit()
    gen = MagicMock(return_value=_ready_result(slug="fresh-gen"))

    with (
        patch("src.reports.morning_run.resolve_opponent", MagicMock(return_value=LadderResult(
            outcome=ResolutionOutcome.RESOLVED, public_id="pub-1", method="progenitor"))),
        patch("src.reports.morning_run.resolve_team", MagicMock(return_value=TeamProfile(
            public_id="x", name="Opp HS", sport="baseball", record_wins=1, record_losses=0))),
    ):
        slot = _process_opponent(
            conn=db, client=MagicMock(), own_team_id=team_id,
            game=_game(event_id="e1", opponent_id="opp-1", opponent_name="Opp"),
            game_date="2026-06-20", registry=[], dry_run=False, generate_fn=gen,
        )

    gen.assert_called_once()  # stale reservation -> regenerate (self-heal)
    assert slot.delivery_status == "generated"


# ---------------------------------------------------------------------------
# CLI command: preflight failure path + summary always sent
# ---------------------------------------------------------------------------


class TestMorningRunCLI:
    """CLI-level tests (preflight + alert wiring) for bb report morning-run."""

    def _invoke(self, args, db_path, **mocks):
        from typer.testing import CliRunner

        from src.cli.report import app

        runner = CliRunner()
        with patch.dict("os.environ", {"DATABASE_PATH": str(db_path)}, clear=False):
            with (
                patch("src.gamechanger.client.GameChangerClient", mocks["client_cls"]),
                patch("src.reports.morning_run.preflight_credential_check",
                      mocks["preflight"]),
                patch("src.reports.morning_run.run_morning", mocks.get("run_morning", MagicMock(
                    return_value=MorningRunResult()))),
                # E-252-03: the non-dry-run alerting-config preflight. Default to a
                # deliverable channel (None) so existing tests are unaffected; the
                # AC-2 test overrides it with an error string.
                patch("src.api.email.validate_alerting_config",
                      mocks.get("validate_alerting", MagicMock(return_value=None))),
                patch("src.api.email.send_preflight_failure_alert_sync",
                      mocks.get("preflight_alert", MagicMock(return_value=True))),
                patch("src.api.email.send_end_of_run_summary_sync",
                      mocks.get("summary_alert", MagicMock(return_value=True))),
                patch("src.api.email.send_unresolved_opponent_alert_sync",
                      mocks.get("unresolved_alert", MagicMock(return_value=True))),
            ):
                return runner.invoke(app, args)

    @pytest.fixture()
    def db_path(self, tmp_path):
        p = tmp_path / "app.db"
        conn = sqlite3.connect(str(p))
        load_real_schema(conn)
        conn.close()
        return p

    def test_preflight_failure_alerts_and_exits_nonzero(self, db_path):
        preflight = MagicMock(side_effect=PreflightError("refresh dead"))
        alert = MagicMock(return_value=True)
        run = MagicMock()

        result = self._invoke(
            ["morning-run", _PUBLIC_A], db_path,
            client_cls=MagicMock(),
            preflight=preflight,
            preflight_alert=alert,
            run_morning=run,
        )

        assert result.exit_code == 1
        assert "Preflight credential check failed" in result.output
        alert.assert_called_once()
        # The run never started.
        run.assert_not_called()

    def test_summary_always_sent_on_success(self, db_path):
        summary = MagicMock(return_value=True)

        result = self._invoke(
            ["morning-run", _PUBLIC_A], db_path,
            client_cls=MagicMock(),
            preflight=MagicMock(),  # passes
            run_morning=MagicMock(return_value=MorningRunResult(generated=2)),
            summary_alert=summary,
        )

        assert result.exit_code == 0
        summary.assert_called_once()
        assert summary.call_args.kwargs["generated"] == 2

    def test_crashing_run_body_still_emails_summary_and_exits_nonzero(self, db_path):
        """AC-1: an unexpected crash in the run body still fires the summary (with
        the failure surfaced in its detail) and exits non-zero -- the run never
        dies silently.
        """
        summary = MagicMock(return_value=True)
        result = self._invoke(
            ["morning-run", _PUBLIC_A], db_path,
            client_cls=MagicMock(),
            preflight=MagicMock(),  # passes
            run_morning=MagicMock(side_effect=RuntimeError("run body exploded")),
            summary_alert=summary,
        )

        assert result.exit_code == 1
        # The heartbeat still went out, once, with the crash in the detail.
        summary.assert_called_once()
        assert "RUN ABORTED" in summary.call_args.kwargs["detail"]
        assert "run body exploded" in summary.call_args.kwargs["detail"]

    def test_misconfigured_alerting_aborts_in_preflight(self, db_path):
        """AC-2: a misconfigured alerting channel aborts BEFORE the run body -- the
        run never starts, no summary is attempted, non-zero exit + operator message.
        """
        run = MagicMock()
        summary = MagicMock(return_value=True)
        result = self._invoke(
            ["morning-run", _PUBLIC_A], db_path,
            client_cls=MagicMock(),
            preflight=MagicMock(),
            run_morning=run,
            summary_alert=summary,
            validate_alerting=MagicMock(
                return_value="ADMIN_EMAIL is unset -- no operator recipient."
            ),
        )

        assert result.exit_code == 1
        assert "misconfigured" in result.output.lower()
        run.assert_not_called()  # aborted before the run body
        summary.assert_not_called()  # no run -> no summary attempt

    def test_failed_summary_send_exits_nonzero_after_retry(self, db_path):
        """AC-3: when the summary send fails (and the retry also fails), the CLI
        does NOT report false success -- it exits non-zero and the send was retried.
        """
        summary = MagicMock(return_value=False)  # every attempt fails
        result = self._invoke(
            ["morning-run", _PUBLIC_A], db_path,
            client_cls=MagicMock(),
            preflight=MagicMock(),
            run_morning=MagicMock(return_value=MorningRunResult(generated=1)),
            summary_alert=summary,
        )

        assert result.exit_code == 1
        assert summary.call_count == 2  # retried once before declaring failure
        assert "FAILED to send" in result.output

    def test_dry_run_exempt_from_alerting_preflight_and_summary(self, db_path):
        """AC-1/AC-2: --dry-run sends no summary AND is exempt from the alerting
        preflight (a misconfigured channel does not block a dry-run).
        """
        run = MagicMock(return_value=MorningRunResult())
        summary = MagicMock(return_value=True)
        validate = MagicMock(return_value="ADMIN_EMAIL is unset")  # would block a real run
        result = self._invoke(
            ["morning-run", _PUBLIC_A, "--dry-run"], db_path,
            client_cls=MagicMock(),
            preflight=MagicMock(),
            run_morning=run,
            summary_alert=summary,
            validate_alerting=validate,
        )

        assert result.exit_code == 0
        run.assert_called_once()  # the dry-run still resolves + previews
        summary.assert_not_called()  # no summary in dry-run
        validate.assert_not_called()  # alerting preflight is skipped in dry-run

    def test_all_denied_systematic_signal_in_cli_and_summary_detail(self, db_path):
        """SHOULD FIX: an all-teams-denied run surfaces the FALSE-403 signal.

        The systematic line appears on the CLI (stderr) AND rides into the
        summary email's `detail` (no email-helper signature change).
        """
        summary = MagicMock(return_value=True)
        run_result = MorningRunResult(teams_processed=2, denied=2)

        result = self._invoke(
            ["morning-run", _PUBLIC_A, _PUBLIC_B], db_path,
            client_cls=MagicMock(),
            preflight=MagicMock(),
            run_morning=MagicMock(return_value=run_result),
            summary_alert=summary,
        )

        assert result.exit_code == 0
        assert "2 denied (403)" in result.output
        assert "ALL 2 team(s) were denied (403)" in result.output
        # The systematic line rides into the summary email detail.
        summary.assert_called_once()
        assert "ALL 2 team(s) were denied (403)" in summary.call_args.kwargs["detail"]

    def test_dry_run_does_not_send_summary(self, db_path):
        summary = MagicMock(return_value=True)

        result = self._invoke(
            ["morning-run", _PUBLIC_A, "--dry-run"], db_path,
            client_cls=MagicMock(),
            preflight=MagicMock(),
            run_morning=MagicMock(return_value=MorningRunResult()),
            summary_alert=summary,
        )

        assert result.exit_code == 0
        summary.assert_not_called()

    def test_invalid_date_exits_2(self, db_path):
        result = self._invoke(
            ["morning-run", _PUBLIC_A, "--date", "not-a-date"], db_path,
            client_cls=MagicMock(),
            preflight=MagicMock(),
        )
        assert result.exit_code == 2
        assert "Invalid --date" in result.output

    def test_unresolved_mappable_emits_alert(self, db_path):
        from rich.console import Console

        unresolved = MagicMock(return_value=True)
        slots = [SlotResult(
            own_team_id=1, opponent_root_team_id="root-9", opponent_name="Unindexed",
            game_date="2026-06-20", resolution_outcome="unresolved_mappable",
        )]
        # Wide console so the templated map-opponent command is not line-wrapped
        # (matches the existing test_no_games_report_shows_shareable_url pattern).
        with patch("src.cli.report.console", Console(width=200)):
            result = self._invoke(
                ["morning-run", _PUBLIC_A], db_path,
                client_cls=MagicMock(),
                preflight=MagicMock(),
                run_morning=MagicMock(return_value=MorningRunResult(unresolved=1, slots=slots)),
                unresolved_alert=unresolved,
            )

        assert result.exit_code == 0
        assert "UNRESOLVED" in result.output
        assert "map-opponent root-9 <PASTE-GC-TEAM-URL>" in result.output
        unresolved.assert_called_once_with(
            root_team_id="root-9", opponent_name="Unindexed"
        )

    def test_no_gc_presence_slot_emits_no_unresolved_alert(self, db_path):
        """A no_gc_presence slot must NOT trigger the operator unresolved alert.

        Run-record-layer half of the resurrection-bug guard: a cached
        no_presence opponent (resolution_outcome='no_gc_presence') is terminal
        and must not be re-queued to the operator every morning.
        """
        unresolved = MagicMock(return_value=True)
        slots = [SlotResult(
            own_team_id=1, opponent_root_team_id="root-gone", opponent_name="Gone",
            game_date="2026-06-20", resolution_outcome="no_gc_presence",
        )]
        result = self._invoke(
            ["morning-run", _PUBLIC_A], db_path,
            client_cls=MagicMock(),
            preflight=MagicMock(),
            run_morning=MagicMock(return_value=MorningRunResult(slots=slots)),
            unresolved_alert=unresolved,
        )

        assert result.exit_code == 0
        unresolved.assert_not_called()

    def test_failed_slot_emits_no_map_opponent_prompt(self, db_path):
        """Codex Finding 1 (CLI half): a failed slot (error_message set) must NOT
        get the map-opponent prompt/alert — even if its outcome string happens to
        be unresolved_mappable (a resolution crash) or auto_resolved (a generation
        failure on a resolved opponent).
        """
        unresolved = MagicMock(return_value=True)
        slots = [
            # generation-failed on a RESOLVED opponent: auto_resolved + error.
            SlotResult(
                own_team_id=1, opponent_root_team_id="opp-1", opponent_name="Resolved",
                game_date="2026-06-20", resolution_outcome="auto_resolved",
                resolved_public_id="pub-1", delivery_status="failed",
                error_message="gen blew up",
            ),
            # resolution-crash slot: unresolved_mappable string BUT error set.
            SlotResult(
                own_team_id=1, opponent_root_team_id="opp-2", opponent_name="Crashed",
                game_date="2026-06-20", resolution_outcome="unresolved_mappable",
                delivery_status="failed", error_message="ladder crashed",
            ),
        ]
        result = self._invoke(
            ["morning-run", _PUBLIC_A], db_path,
            client_cls=MagicMock(),
            preflight=MagicMock(),
            run_morning=MagicMock(return_value=MorningRunResult(failed=2, slots=slots)),
            unresolved_alert=unresolved,
        )

        assert result.exit_code == 0
        # No map-opponent prompt for either failed slot.
        assert "map-opponent" not in result.output
        unresolved.assert_not_called()
        # The failures are shown as failures.
        assert "FAILED" in result.output

    def test_help(self, db_path):
        from typer.testing import CliRunner
        from src.cli.report import app
        result = CliRunner().invoke(app, ["morning-run", "--help"])
        assert result.exit_code == 0
        assert "morning-run" in result.output or "team" in result.output.lower()
