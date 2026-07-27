"""Unit tests for the orphan-reference-data reclamation pass (E-273-01).

Covers ``reclaim_orphan_reference_data`` and the single-source id-set producers
(``_orphan_team_ids`` / ``_orphan_player_ids`` / ``count_orphan_reference_data``)
in ``src/reports/lifecycle.py``: the three predicates (team / player / roots
exclusion), the belt-and-suspenders stat clause + WARN-on-fire, the
single-transaction reap-then-gate concurrency guard + deferral, and the
TOCTOU regression.

A NEW dedicated file (TN-15) -- avoids the shared-file collision with the other
E-273 stories.  The two behavior-pinning cascade tests (AC-9) live in
``tests/test_report_generator.py`` and are run there as a no-regression check;
this file does not edit them.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Repo root, for the ``python -O`` subprocess probe in the E-277-02 guard tests.
_REPO_ROOT_FOR_TESTS = Path(__file__).resolve().parents[1]

from src.db.teams import ensure_team_row
from src.reports import lifecycle
from src.reports.lifecycle import (
    OrphanCounts,
    ReclaimResult,
    _orphan_player_ids,
    _orphan_team_ids,
    cascade_delete_team,
    count_orphan_reference_data,
    reclaim_orphan_reference_data,
)
from src.reports.morning_run import SlotResult, _upsert_slot
from unittest.mock import patch

from src.reports.lifecycle import cleanup_expired_reports
from src.util.timezone import UTC_ISO_FORMAT
from tests.conftest import load_real_schema

# ---------------------------------------------------------------------------
# Fixtures / seed helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path):
    """Disk-backed DB with the production schema and FK enforcement on."""
    db_path = tmp_path / "reclaim.db"
    c = sqlite3.connect(str(db_path))
    load_real_schema(c)
    c.commit()
    yield c
    c.close()


def _add_season(c, season_id="2026"):
    c.execute(
        "INSERT INTO seasons (season_id, name, year) VALUES (?, ?, 2026)",
        (season_id, season_id),
    )
    c.commit()


def _add_team(c, name, membership="tracked"):
    cur = c.execute(
        "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
        (name, membership),
    )
    c.commit()
    return cur.lastrowid


def _add_player(c, player_id, first="First", last="Last"):
    c.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (player_id, first, last),
    )
    c.commit()
    return player_id


def _add_roster(c, team_id, player_id, season_id="2026"):
    c.execute(
        "INSERT INTO team_rosters (team_id, player_id, season_id) VALUES (?, ?, ?)",
        (team_id, player_id, season_id),
    )
    c.commit()


def _add_report(c, team_id, slug, status="ready", generated_at=None):
    if generated_at is None:
        c.execute(
            "INSERT INTO reports (slug, team_id, title, status, expires_at) "
            "VALUES (?, ?, ?, ?, '2099-01-01T00:00:00Z')",
            (slug, team_id, slug, status),
        )
    else:
        c.execute(
            "INSERT INTO reports (slug, team_id, title, status, generated_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, '2099-01-01T00:00:00Z')",
            (slug, team_id, slug, status, generated_at),
        )
    c.commit()


def _add_game(c, game_id, home_team_id, away_team_id, season_id="2026", date="2026-04-01"):
    c.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (game_id, season_id, date, home_team_id, away_team_id),
    )
    c.commit()
    return game_id


def _add_user(c, email="coach@example.com"):
    cur = c.execute("INSERT INTO users (email) VALUES (?)", (email,))
    c.commit()
    return cur.lastrowid


def _add_slot(
    c,
    own_team_id,
    root_team_id="root-slot",
    outcome="deferred_placeholder",
    game_date="2026-04-01",
):
    """Seed a ``scheduled_report_runs`` audit row (the E-277-01 keep-root).

    ``resolution_outcome`` is CHECK-constrained to a four-value vocabulary;
    ``deferred_placeholder`` is the rung that persists NO ``opponent_links``
    row, which is the shape that leaves a team exposed without this root.
    """
    c.execute(
        "INSERT INTO scheduled_report_runs "
        "(game_date, own_team_id, opponent_root_team_id, opponent_name, "
        " resolution_outcome) VALUES (?, ?, ?, 'Placeholder Opp', ?)",
        (game_date, own_team_id, root_team_id, outcome),
    )
    c.commit()


# ---------------------------------------------------------------------------
# AC-1: tracked orphan teams + their pins are reclaimed; counts reported
# ---------------------------------------------------------------------------


def test_reclaims_tracked_orphan_team_and_its_pins(conn):
    _add_season(conn)
    orphan = _add_team(conn, "Orphan")
    # Team-scoped pins that must be swept with the team row.
    _add_player(conn, "p-orphan")
    _add_roster(conn, orphan, "p-orphan")
    conn.execute(
        "INSERT INTO scouting_runs (team_id, season_id) VALUES (?, '2026')", (orphan,)
    )
    conn.execute(
        "INSERT INTO crawl_jobs (team_id, sync_type, status) "
        "VALUES (?, 'scouting_crawl', 'completed')",
        (orphan,),
    )
    user = _add_user(conn)
    conn.execute(
        "INSERT INTO coaching_assignments (user_id, team_id) VALUES (?, ?)",
        (user, orphan),
    )
    # NO scheduled_report_runs row here since E-277-01: that table is now a
    # reachability ROOT, so a team carrying one is excluded from the orphan set
    # by design and this fixture would no longer BE an orphan.  The row was
    # removed rather than the assertion weakened -- seeding it would make the
    # test assert the opposite of the keep-root.  Audit-row deletion on the
    # DELIBERATE path is covered by
    # ``test_cascade_delete_team_still_removes_audit_rows``.
    conn.commit()

    result = reclaim_orphan_reference_data(conn)

    assert isinstance(result, ReclaimResult)
    assert result.deferred is False
    assert result.teams_deleted == 1
    assert result.roster_rows_deleted == 1
    assert result.players_deleted == 1  # p-orphan was roster-only on the orphan

    assert conn.execute("SELECT COUNT(*) FROM teams WHERE id=?", (orphan,)).fetchone()[0] == 0
    # Pin tables the sweep can still REACH.  ``scheduled_report_runs`` is
    # deliberately absent from this list since E-277-01: it remains in
    # ``_TEAM_PIN_TABLES`` as an FK safety net, but the keep-root makes it
    # unreachable from this pass, so asserting the sweep deletes it would
    # assert against the story's own change.
    for table, col in [
        ("team_rosters", "team_id"),
        ("scouting_runs", "team_id"),
        ("crawl_jobs", "team_id"),
        ("coaching_assignments", "team_id"),
    ]:
        assert (
            conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {col}=?", (orphan,)
            ).fetchone()[0]
            == 0
        ), f"{table} pin should be swept with the orphan team"
    # Invariant holds afterward.
    assert count_orphan_reference_data(conn) == OrphanCounts(0, 0, 0)


def test_survivor_with_report_is_not_reclaimed(conn):
    _add_season(conn)
    kept = _add_team(conn, "HasReport")
    _add_report(conn, kept, "rpt-1")
    orphan = _add_team(conn, "Orphan")
    conn.commit()

    result = reclaim_orphan_reference_data(conn)

    assert result.teams_deleted == 1
    assert conn.execute("SELECT COUNT(*) FROM teams WHERE id=?", (kept,)).fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM teams WHERE id=?", (orphan,)).fetchone()[0] == 0


def test_team_with_game_is_not_reclaimed(conn):
    _add_season(conn)
    a = _add_team(conn, "A")
    b = _add_team(conn, "B")
    _add_game(conn, "g-1", a, b)
    conn.commit()

    assert _orphan_team_ids(conn) == set()
    result = reclaim_orphan_reference_data(conn)
    assert result.teams_deleted == 0


# ---------------------------------------------------------------------------
# AC-2: belt-and-suspenders -- synthetic non-participant stat reference excludes
#       the team AND logs a WARN
# ---------------------------------------------------------------------------


def _make_surviving_game(c, season_id="2026"):
    """Create a game between two participants (both therefore survive)."""
    a = _add_team(c, "GameHome")
    b = _add_team(c, "GameAway")
    _add_game(c, "g-live", a, b, season_id)
    return a, b


@pytest.mark.parametrize(
    "table,cols",
    [
        ("player_game_batting", ("team_id", "perspective_team_id")),
        ("player_game_pitching", ("team_id", "perspective_team_id")),
        ("spray_charts", ("team_id", "perspective_team_id")),
        ("reconciliation_discrepancies", ("team_id", "perspective_team_id")),
        ("plays", ("batting_team_id", "perspective_team_id")),
    ],
)
@pytest.mark.parametrize("via", (0, 1))
def test_stat_referenced_gameless_team_excluded(conn, table, cols, via):
    """A gameless team referenced by a surviving game's stat row -- through
    EITHER of the table's two team columns -- is NOT an orphan (vacuous on real
    data; fires only in this synthetic corrupt state)."""
    _add_season(conn)
    home, away = _make_surviving_game(conn)
    _add_player(conn, "p-stat")
    synthetic = _add_team(conn, "SyntheticNonParticipant")  # never home/away

    # The referencing column carries the synthetic team; the OTHER team column
    # carries a real participant so only ONE column points at `synthetic`.
    ref_col = cols[via]
    other_col = cols[1 - via]
    if table == "player_game_batting":
        conn.execute(
            f"INSERT INTO player_game_batting (game_id, player_id, {ref_col}, {other_col}) "
            "VALUES ('g-live', 'p-stat', ?, ?)",
            (synthetic, home),
        )
    elif table == "player_game_pitching":
        conn.execute(
            f"INSERT INTO player_game_pitching (game_id, player_id, {ref_col}, {other_col}) "
            "VALUES ('g-live', 'p-stat', ?, ?)",
            (synthetic, home),
        )
    elif table == "spray_charts":
        conn.execute(
            f"INSERT INTO spray_charts (game_id, player_id, {ref_col}, {other_col}) "
            "VALUES ('g-live', 'p-stat', ?, ?)",
            (synthetic, home),
        )
    elif table == "reconciliation_discrepancies":
        conn.execute(
            f"INSERT INTO reconciliation_discrepancies "
            f"(game_id, run_id, {ref_col}, {other_col}, player_id, signal_name, category, status) "
            "VALUES ('g-live', 'run-1', ?, ?, 'p-stat', 'sig', 'cat', 'MATCH')",
            (synthetic, home),
        )
    else:  # plays
        conn.execute(
            f"INSERT INTO plays "
            f"(game_id, play_order, inning, half, season_id, {ref_col}, {other_col}, batter_id) "
            "VALUES ('g-live', 1, 1, 'top', '2026', ?, ?, 'p-stat')",
            (synthetic, home),
        )
    conn.commit()

    assert synthetic not in _orphan_team_ids(conn)


def test_belt_and_suspenders_logs_warning(conn, caplog):
    _add_season(conn)
    home, away = _make_surviving_game(conn)
    _add_player(conn, "p-stat")
    synthetic = _add_team(conn, "SyntheticNonParticipant")
    conn.execute(
        "INSERT INTO player_game_batting "
        "(game_id, player_id, team_id, perspective_team_id) "
        "VALUES ('g-live', 'p-stat', ?, ?)",
        (home, synthetic),
    )
    conn.commit()

    with caplog.at_level("WARNING", logger="src.reports.lifecycle"):
        result = reclaim_orphan_reference_data(conn)

    # Synthetic team survives (excluded, not deleted) and the corruption is logged.
    assert conn.execute("SELECT COUNT(*) FROM teams WHERE id=?", (synthetic,)).fetchone()[0] == 1
    assert result.teams_deleted == 0
    messages = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any(
        f"id={synthetic}" in m and "player_game_batting" in m and "no games" in m
        for m in messages
    ), messages


def test_warn_emitted_once_per_pass(conn, caplog):
    """The self-assert recompute must not double-log the WARN (warn=False)."""
    _add_season(conn)
    home, away = _make_surviving_game(conn)
    _add_player(conn, "p-stat")
    synthetic = _add_team(conn, "SyntheticNonParticipant")
    conn.execute(
        "INSERT INTO player_game_batting "
        "(game_id, player_id, team_id, perspective_team_id) "
        "VALUES ('g-live', 'p-stat', ?, ?)",
        (home, synthetic),
    )
    conn.commit()

    with caplog.at_level("WARNING", logger="src.reports.lifecycle"):
        reclaim_orphan_reference_data(conn)

    warns = [
        r for r in caplog.records
        if r.levelname == "WARNING" and f"id={synthetic}" in r.getMessage()
    ]
    assert len(warns) == 1, "belt-and-suspenders WARN should fire exactly once per pass"


def test_game_perspectives_referenced_gameless_team_excluded(conn, caplog):
    """Codex-F1 remediation: ``game_perspectives.perspective_team_id`` is a
    ``teams(id)`` FK child that the ORIGINAL grep-based FK sweep filtered out.
    A gameless team referenced ONLY by a game_perspectives row (the same
    synthetic non-participant-perspective corruption class as AC-2, but a SINGLE
    team column so it needs a dedicated case) must be EXCLUDED, not orphan-
    classified -- otherwise ``DELETE FROM teams`` would abort with an
    IntegrityError and ROLL BACK the ENTIRE sweep. Asserts (a) the team is NOT
    reclaimed and the pass completes without raising, and (b) the WARN fires
    naming the team + ``game_perspectives``.
    """
    _add_season(conn)
    home, away = _make_surviving_game(conn)  # participants of g-live
    # A team that is NOT a participant of g-live (never home/away) but carries a
    # game_perspectives row for it -- gameless yet FK-referenced.
    synthetic = _add_team(conn, "SyntheticPerspectiveOnly")
    conn.execute(
        "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES ('g-live', ?)",
        (synthetic,),
    )
    conn.commit()

    # Predicate-level: excluded from the orphan set.
    assert synthetic not in _orphan_team_ids(conn)

    with caplog.at_level("WARNING", logger="src.reports.lifecycle"):
        result = reclaim_orphan_reference_data(conn)  # must NOT raise / rollback

    assert conn.execute("SELECT COUNT(*) FROM teams WHERE id=?", (synthetic,)).fetchone()[0] == 1
    assert result.teams_deleted == 0
    messages = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any(
        f"id={synthetic}" in m and "game_perspectives" in m and "no games" in m
        for m in messages
    ), messages


# ---------------------------------------------------------------------------
# AC-3: member teams are never orphans
# ---------------------------------------------------------------------------


def test_member_team_with_no_reports_or_games_is_not_reclaimed(conn):
    _add_season(conn)
    member = _add_team(conn, "MemberTeam", membership="member")
    orphan = _add_team(conn, "Orphan")
    conn.commit()

    result = reclaim_orphan_reference_data(conn)

    assert member not in _orphan_team_ids(conn)  # already gone from the set
    assert conn.execute("SELECT COUNT(*) FROM teams WHERE id=?", (member,)).fetchone()[0] == 1
    assert result.teams_deleted == 1  # only the orphan


# ---------------------------------------------------------------------------
# AC-4: the root survivors -- resolved_team_id, our_team_id, grant, and
#       (E-277-01) scheduled_report_runs.own_team_id -- each survives in
#       isolation; no operator/user-decision or audit row is touched
# ---------------------------------------------------------------------------


def test_root_survivors_are_excluded_and_untouched(conn):
    _add_season(conn)
    # (a) resolved_team_id target -- isolated: our_team_id points at a member team.
    member = _add_team(conn, "OurMember", membership="member")
    resolved = _add_team(conn, "ResolvedTarget")  # tracked, orphan-shaped otherwise
    conn.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, resolved_team_id) "
        "VALUES (?, 'root-a', 'Resolved Opp', ?)",
        (member, resolved),
    )
    # (b) our_team_id owner -- SYNTHETIC tracked shape, resolved_team_id NULL so
    #     the our_team_id root exclusion is proven to fire IN ISOLATION.
    our_owner = _add_team(conn, "OurOwnerSynthetic")
    conn.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, resolved_team_id) "
        "VALUES (?, 'root-b', 'Manual Opp', NULL)",
        (our_owner,),
    )
    # (c) user_team_access grant.
    granted = _add_team(conn, "GrantedTeam")
    user = _add_user(conn)
    conn.execute(
        "INSERT INTO user_team_access (user_id, team_id) VALUES (?, ?)",
        (user, granted),
    )
    # (d) scheduled_report_runs.own_team_id -- the E-277-01 audit root, in
    #     isolation: no opponent_links row at all, which is precisely the
    #     placeholder-deferral shape that leaves a team exposed without it.
    slot_owner = _add_team(conn, "SlotOwner")
    _add_slot(conn, slot_owner)
    # A genuine orphan proves the pass actually ran (anti-vacuity).
    orphan = _add_team(conn, "Orphan")
    conn.commit()

    orphan_ids = _orphan_team_ids(conn)
    assert resolved not in orphan_ids
    assert our_owner not in orphan_ids
    assert granted not in orphan_ids
    assert slot_owner not in orphan_ids
    assert orphan in orphan_ids

    result = reclaim_orphan_reference_data(conn)
    assert result.teams_deleted == 1  # only the genuine orphan

    for tid in (resolved, our_owner, granted, slot_owner):
        assert conn.execute("SELECT COUNT(*) FROM teams WHERE id=?", (tid,)).fetchone()[0] == 1
    # The audit row itself is untouched.
    assert conn.execute("SELECT COUNT(*) FROM scheduled_report_runs").fetchone()[0] == 1
    # No opponent_links row deleted, no resolved_team_id NULLed.
    assert conn.execute("SELECT COUNT(*) FROM opponent_links").fetchone()[0] == 2
    assert (
        conn.execute(
            "SELECT resolved_team_id FROM opponent_links WHERE root_team_id='root-a'"
        ).fetchone()[0]
        == resolved
    )
    # No grant deleted.
    assert conn.execute("SELECT COUNT(*) FROM user_team_access").fetchone()[0] == 1


# ---------------------------------------------------------------------------
# E-277-01 AC-1/AC-2/AC-3: the audit keep-root, exercised through the
#       PRODUCTION path -- the canonical team upsert and the real slot writer,
#       not hand-seeded rows.  Building the fixture that way is what makes the
#       present/removed contrast settle a VERDICT rather than merely
#       demonstrate that a conjunctive clause does something (story AC-6a/6c).
# ---------------------------------------------------------------------------


def _seed_exposed_own_team(conn, name="OwnTeamPlaceholderOnly"):
    """Build the exposed morning-run shape through production entry points.

    ``ensure_team_row`` is the canonical team upsert -- it hardcodes
    ``membership_type='tracked'`` and ``is_active=0``, which is precisely why
    own teams sit inside the orphan base set at all -- and ``_upsert_slot`` is
    the real morning-run slot writer.  NO ``opponent_links`` row is created:
    the ``deferred_placeholder`` rung persists none, and that absence is the
    whole exposure this keep-root closes.
    """
    team_id = ensure_team_row(conn, name=name, public_id="pid-own-exposed")
    _upsert_slot(
        conn,
        SlotResult(
            own_team_id=team_id,
            opponent_root_team_id="root-tbd",
            opponent_name="TBD",
            game_date="2026-04-01",
            resolution_outcome="deferred_placeholder",
        ),
    )
    conn.commit()
    return team_id


def test_audit_root_keeps_placeholder_only_own_team(conn):
    """AC-1: the exposed own team, its audit rows, its roster and its
    roster-only players all survive the sweep."""
    _add_season(conn)
    team_id = _seed_exposed_own_team(conn)
    _add_player(conn, "p-own")
    _add_roster(conn, team_id, "p-own")

    # Anti-vacuity: no opponent_links row exists, so the OTHER live root cannot
    # be what produces this outcome; and the team really is in the base set.
    assert conn.execute("SELECT COUNT(*) FROM opponent_links").fetchone()[0] == 0
    assert conn.execute(
        "SELECT membership_type FROM teams WHERE id=?", (team_id,)
    ).fetchone()[0] == "tracked"

    result = reclaim_orphan_reference_data(conn)

    assert result.teams_deleted == 0
    assert conn.execute("SELECT COUNT(*) FROM teams WHERE id=?", (team_id,)).fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM scheduled_report_runs").fetchone()[0] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM team_rosters WHERE team_id=?", (team_id,)
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM players WHERE player_id='p-own'"
    ).fetchone()[0] == 1


def test_same_own_team_is_swept_once_its_audit_rows_are_removed(conn):
    """AC-2: with the audit rows gone the SAME team IS deleted -- so AC-1's
    outcome is attributable to this root and not to some unrelated exclusion."""
    _add_season(conn)
    team_id = _seed_exposed_own_team(conn)
    _add_player(conn, "p-own")
    _add_roster(conn, team_id, "p-own")

    conn.execute("DELETE FROM scheduled_report_runs WHERE own_team_id = ?", (team_id,))
    conn.commit()

    result = reclaim_orphan_reference_data(conn)

    assert result.teams_deleted == 1
    assert conn.execute("SELECT COUNT(*) FROM teams WHERE id=?", (team_id,)).fetchone()[0] == 0


def test_retained_pin_entry_is_structurally_guarded():
    """The retained ``scheduled_report_runs`` pin entry has a MECHANICAL guard.

    E-277-01 keeps ``("scheduled_report_runs", "own_team_id")`` in
    ``_TEAM_PIN_TABLES`` as an FK safety net even though the keep-root makes it
    unreachable.  An unreachable entry carrying only a "DO NOT REMOVE" comment
    is defended by prose alone -- the instrument this epic exists to distrust --
    and deleting it makes the team DELETE raise ``IntegrityError`` and roll back
    the ENTIRE sweep.  This assertion fails loudly if it is ever removed.
    """
    assert ("scheduled_report_runs", "own_team_id") in lifecycle._TEAM_PIN_TABLES
    # ``teams`` must stay LAST for FK-safe ordering.
    assert lifecycle._TEAM_PIN_TABLES[-1] == ("teams", "id")


def test_audit_root_suppresses_the_gameless_stat_warn(conn, caplog):
    """BEHAVIORAL CHANGE, declared and pinned: the new clause narrows the
    population of ``_warn_stat_referenced_gameless_teams``.

    That WARN is a FOURTH consumer of ``_TEAM_BASE_PRED`` -- it composes
    ``base AND stat_exists`` -- so adding a root narrows it too.  A gameless
    team carrying BOTH a stat row and an audit row no longer warns.

    Verdict: CORRECT.  The WARN exists to surface a team the belt-and-suspenders
    stat clause silently excluded from the orphan set, because that exclusion
    swallows the corruption signal a reclamation-halting ``IntegrityError``
    would have made loud.  A team pinned by the audit root is excluded on a
    LEGITIMATE root before the stat clause is ever reached, so there is no
    swallowed signal to report -- warning about it would be a false alarm.  The
    WARN still fires for the same team without the audit row, which is what the
    second half asserts.
    """
    import logging

    _add_season(conn)
    home, _away = _make_surviving_game(conn)
    _add_player(conn, "p-stat")
    synthetic = _add_team(conn, "SyntheticNonParticipant")  # never home/away
    conn.execute(
        "INSERT INTO player_game_batting (game_id, player_id, team_id, "
        "perspective_team_id) VALUES ('g-live', 'p-stat', ?, ?)",
        (synthetic, home),
    )
    conn.commit()

    # Without an audit row: the stat clause is what excludes it, so it WARNS.
    with caplog.at_level(logging.WARNING, logger="src.reports.lifecycle"):
        lifecycle._warn_stat_referenced_gameless_teams(conn)
    assert any("excluded from reclamation despite no games" in r.message for r in caplog.records)

    # With an audit row: excluded on a legitimate root first, so NO warning.
    _add_slot(conn, synthetic, root_team_id="root-warn")
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="src.reports.lifecycle"):
        lifecycle._warn_stat_referenced_gameless_teams(conn)
    assert not any(
        "excluded from reclamation despite no games" in r.message for r in caplog.records
    )


def test_cascade_delete_team_still_removes_audit_rows(conn):
    """AC-3: a DELIBERATE deletion still takes the audit rows with it.

    The keep-root governs how the sweep's unreachability INFERENCE is made; it
    does not change what a decided deletion does.  Migration 005's CASCADE
    MIRROR INVARIANT requires a deleted team's audit rows to go with it, and
    that is unchanged by this story.
    """
    _add_season(conn)
    team_id = _seed_exposed_own_team(conn)
    assert conn.execute("SELECT COUNT(*) FROM scheduled_report_runs").fetchone()[0] == 1

    cascade_delete_team(conn, team_id)

    assert conn.execute("SELECT COUNT(*) FROM teams WHERE id=?", (team_id,)).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM scheduled_report_runs WHERE own_team_id=?", (team_id,)
    ).fetchone()[0] == 0


# ---------------------------------------------------------------------------
# AC-5: orphan-player predicate, incl. the load-bearing `plays` inclusion
# ---------------------------------------------------------------------------


def test_plays_only_player_survives_genuine_orphans_deleted(conn):
    _add_season(conn)
    home, away = _make_surviving_game(conn)
    batter = _add_player(conn, "p-batter")
    pitcher = _add_player(conn, "p-pitcher")
    dead = _add_player(conn, "p-dead")  # genuinely orphaned, no refs anywhere
    # Plays-only references: one via batter_id, one via pitcher_id.
    conn.execute(
        "INSERT INTO plays "
        "(game_id, play_order, inning, half, season_id, batting_team_id, "
        "perspective_team_id, batter_id, pitcher_id) "
        "VALUES ('g-live', 1, 1, 'top', '2026', ?, ?, ?, ?)",
        (home, home, batter, pitcher),
    )
    conn.commit()

    orphans = _orphan_player_ids(conn)
    assert batter not in orphans
    assert pitcher not in orphans
    assert dead in orphans

    reclaim_orphan_reference_data(conn)
    assert conn.execute("SELECT COUNT(*) FROM players WHERE player_id='p-batter'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM players WHERE player_id='p-pitcher'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM players WHERE player_id='p-dead'").fetchone()[0] == 0


def test_player_kept_by_surviving_team_roster(conn):
    _add_season(conn)
    kept_team = _add_team(conn, "Kept")
    _add_report(conn, kept_team, "rpt-keep")  # kept_team survives
    q = _add_player(conn, "p-q")
    _add_roster(conn, kept_team, q)
    conn.commit()

    assert q not in _orphan_player_ids(conn)
    reclaim_orphan_reference_data(conn)
    assert conn.execute("SELECT COUNT(*) FROM players WHERE player_id='p-q'").fetchone()[0] == 1


@pytest.mark.parametrize(
    "table,sql",
    [
        (
            "player_game_batting",
            "INSERT INTO player_game_batting (game_id, player_id, team_id, perspective_team_id) "
            "VALUES ('g-live', ?, ?, ?)",
        ),
        (
            "player_game_pitching",
            "INSERT INTO player_game_pitching (game_id, player_id, team_id, perspective_team_id) "
            "VALUES ('g-live', ?, ?, ?)",
        ),
    ],
)
def test_player_kept_by_game_stat_row(conn, table, sql):
    _add_season(conn)
    home, away = _make_surviving_game(conn)
    p = _add_player(conn, "p-stat")
    conn.execute(sql, (p, home, home))
    conn.commit()
    assert p not in _orphan_player_ids(conn)


def test_player_kept_by_spray_chart(conn):
    _add_season(conn)
    home, away = _make_surviving_game(conn)
    p = _add_player(conn, "p-spray")
    conn.execute(
        "INSERT INTO spray_charts (game_id, player_id, team_id, perspective_team_id) "
        "VALUES ('g-live', ?, ?, ?)",
        (p, home, home),
    )
    conn.commit()
    assert p not in _orphan_player_ids(conn)


# ---------------------------------------------------------------------------
# AC-6 / AC-10: two-phase ordering -- roster-only players transitively orphaned
#               by a deleted orphan team are reclaimed in the SAME invocation
# ---------------------------------------------------------------------------


def test_roster_only_players_reclaimed_after_team_tier(conn):
    _add_season(conn)
    orphan = _add_team(conn, "OrphanWithRoster")
    for i in range(4):
        pid = f"p-roster-{i}"
        _add_player(conn, pid)
        _add_roster(conn, orphan, pid)
    conn.commit()

    # Pre-pass: the roster-only players are orphans ONLY because their sole
    # roster is on an orphan team (state-independent predicate).
    assert len(_orphan_player_ids(conn)) == 4

    result = reclaim_orphan_reference_data(conn)

    assert result.teams_deleted == 1
    assert result.roster_rows_deleted == 4
    assert result.players_deleted == 4
    assert conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM team_rosters").fetchone()[0] == 0
    # Fixed point: invariant is zero afterward (zero-delta self-assert held).
    assert count_orphan_reference_data(conn) == OrphanCounts(0, 0, 0)


def test_player_on_two_teams_orphan_and_survivor_is_kept(conn):
    """A player rostered on BOTH an orphan team and a surviving team is kept."""
    _add_season(conn)
    survivor = _add_team(conn, "Survivor")
    _add_report(conn, survivor, "rpt-surv")
    orphan = _add_team(conn, "Orphan2")
    shared = _add_player(conn, "p-shared")
    _add_roster(conn, survivor, shared)
    _add_roster(conn, orphan, shared)
    conn.commit()

    assert shared not in _orphan_player_ids(conn)
    reclaim_orphan_reference_data(conn)
    assert conn.execute("SELECT COUNT(*) FROM players WHERE player_id='p-shared'").fetchone()[0] == 1
    # The orphan team's roster row for the shared player is gone; the survivor's remains.
    assert conn.execute("SELECT COUNT(*) FROM team_rosters WHERE team_id=?", (orphan,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM team_rosters WHERE team_id=?", (survivor,)).fetchone()[0] == 1


# ---------------------------------------------------------------------------
# E-277-03: the chunked-delete path, pinned so that it DISCRIMINATES
# ---------------------------------------------------------------------------
#
# The obvious version of this test -- seed enough orphans to cross two chunk
# boundaries, assert they are all deleted -- passes IDENTICALLY against an
# unchunked implementation, because ``SQLITE_LIMIT_VARIABLE_NUMBER`` is 250,000
# on this build rather than the 999 the module's docstrings used to cite.  A
# test that goes green against the mutant it exists to catch is worse than no
# test, because it also reports that the path is covered (epic TN-8).
#
# What makes it discriminate is LOWERING the connection's variable limit.  Two
# quantities and the limit are then coupled, and the coupling is asserted rather
# than assumed -- see ``_seed_chunking_fixture`` and ``_assert_chunking_fixture``.


def _seed_chunking_fixture(c):
    """Seed an all-orphan player set that spans more than two chunks.

    Returns ``(chunk, limit, seeded)``.  ``chunk`` is captured from
    :data:`lifecycle._RECLAIM_CHUNK` HERE, at seed time and BEFORE any mutation,
    which is what lets the mutation probe below raise the live constant without
    the fixture growing to match it (E-277-03 AC-2.1b / AC-5).

    Both derived quantities are expressed in terms of the captured chunk so the
    fixture keeps discriminating if the constant is ever changed:

    * ``limit  = 2 * chunk``  -- at or above ``chunk`` (so every CHUNKED
      statement fits and the intact arm passes)...
    * ``seeded = 2 * chunk + chunk // 2`` -- ...and strictly below the seed (so
      the single UNCHUNKED statement exceeds it and the removed arm raises),
      while also being more than two chunks and not an exact multiple of one.

    A player with no roster, no batting/pitching row, no play and no spray-chart
    row is an orphan, so a bare ``players`` insert is the whole fixture.  Seeded
    with one ``executemany`` and one commit rather than the per-row
    ``_add_player`` helper purely for runtime; the statement is the same.  The
    commit is REQUIRED, not stylistic: E-277-02's precondition guard raises at
    the pass's entry on a connection with an open transaction.
    """
    chunk = lifecycle._RECLAIM_CHUNK
    limit = 2 * chunk
    seeded = 2 * chunk + chunk // 2
    c.executemany(
        "INSERT INTO players (player_id, first_name, last_name) "
        "VALUES (?, 'Chunk', 'Fixture')",
        [(f"p-chunk-{i:05d}",) for i in range(seeded)],
    )
    c.commit()
    c.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, limit)
    return chunk, limit, seeded


def _assert_chunking_fixture(c, chunk, limit, seeded):
    """Assert the three-way invariant, then return the pass's real orphan set.

    The invariant is expressed over ``len(orphan_ids)`` -- the set the pass
    actually MATERIALIZES and binds -- not over ``seeded``.  Those coincide only
    because this fixture is all-orphan, and a mixed fixture (say 950 orphans
    among 1801 players) satisfies a ``seeded``-based invariant while binding a
    count that sits inside the very dead band the invariant exists to exclude
    (E-277-03 AC-2.1c).  ``seeded`` is checked separately, as an equality.

    ``chunk`` MUST be the seed-time captured value, never a fresh read of
    :data:`lifecycle._RECLAIM_CHUNK`: read live, this assertion fires first under
    the mutation probe and the probe then "fails" for the wrong reason -- an
    ``AssertionError`` about the fixture rather than the ``OperationalError``
    that proves chunking was load-bearing (E-277-03 AC-2.1b).
    """
    orphan_ids = sorted(_orphan_player_ids(c))
    assert len(orphan_ids) == seeded, (
        f"fixture is not all-orphan: seeded={seeded}, orphan set={len(orphan_ids)}"
    )
    assert chunk <= limit < len(orphan_ids), (
        f"fixture no longer discriminates: _RECLAIM_CHUNK={chunk} (captured at "
        f"seed time), variable limit={limit}, orphan set={len(orphan_ids)}. "
        "Both inequalities are load-bearing and they fail in OPPOSITE "
        "directions: chunk <= limit is what keeps the chunking-INTACT arm "
        "passing (every chunked statement must fit under the limit), and "
        "limit < orphans is the only thing that makes the chunking-REMOVED arm "
        "raise (one statement must EXCEED it).  Break either and this test "
        "still reports success while proving nothing."
    )
    assert len(orphan_ids) > 2 * chunk, (
        f"AC-1 wants MORE than two chunks: orphan set={len(orphan_ids)}, "
        f"_RECLAIM_CHUNK={chunk}"
    )
    return orphan_ids


def test_chunked_player_delete_spans_more_than_two_chunks(conn):
    """The real pass deletes a >2-chunk orphan set under a lowered variable limit.

    Lowering the limit is a REQUIREMENT, not a detail (epic TN-8): at this
    build's default of 250,000 the whole set binds in one statement and the test
    would pass against an unchunked implementation.

    Nothing else in the pass binds a variable per id -- the orphan producers use
    correlated ``NOT EXISTS`` -- so lowering the limit exercises the chunker and
    nothing else.  If a later change materializes an ``IN`` list somewhere else
    in the pass, this test starts raising ``too many SQL variables``; that is
    the test WORKING, not a flaky fixture.
    """
    chunk, limit, seeded = _seed_chunking_fixture(conn)
    orphan_ids = _assert_chunking_fixture(conn, chunk, limit, seeded)

    # AC-3: the test asserts its own precondition.  Without this, the validity
    # of everything below rests silently on ``setlimit`` having taken effect --
    # delete that call, or let a future runtime make it a no-op, and the
    # row-count assertions go green again against an unchunked implementation.
    # Run on the SAME connection the pass will use, so it is that connection's
    # limit being demonstrated and not another's.
    placeholders = ",".join("?" for _ in orphan_ids)
    with pytest.raises(sqlite3.OperationalError, match="too many SQL variables"):
        conn.execute(
            f"SELECT COUNT(*) FROM players WHERE player_id IN ({placeholders})",
            orphan_ids,
        )
    # The failed probe must not leave the connection dirty, or E-277-02's
    # precondition guard would refuse the pass below and this test would fail
    # for a reason that has nothing to do with chunking.
    assert not conn.in_transaction

    result = reclaim_orphan_reference_data(conn)

    assert result.players_deleted == seeded
    assert result.players_deleted == len(orphan_ids)
    assert conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 0
    # AC-6: the fixed-point self-assert was satisfied, not bypassed.
    assert count_orphan_reference_data(conn) == OrphanCounts(0, 0, 0)


def test_chunking_is_load_bearing_removing_it_raises(conn, monkeypatch):
    """The anti-vacuity guard: with chunking removed, the fixture above RAISES.

    This is the mutation probe kept as a permanent test rather than run once and
    written up, so the sibling above cannot quietly go vacuous later -- if a
    future edit lets the whole orphan set bind in one statement, THIS test is
    what notices.

    The failure MODE is pinned, not merely the fact of failure: only
    ``OperationalError: too many SQL variables`` shows that chunking was
    load-bearing.  An ``AssertionError`` here would mean the fixture's own
    invariant tripped first, which demonstrates nothing about the chunker
    (E-277-03 AC-4a).

    ``monkeypatch.setattr`` rather than a bare ``setattr``: it defaults to
    ``raising=True``, so if the anchor attribute is ever renamed this probe
    aborts loudly instead of silently creating a new one and reporting a
    meaningless green (AC-4b).
    """
    chunk, limit, seeded = _seed_chunking_fixture(conn)
    orphan_ids = _assert_chunking_fixture(conn, chunk, limit, seeded)

    # Chunking removed: one chunk larger than the whole set, so ``_delete_where_in``
    # emits a single statement binding every id.  Applied AFTER seeding, so the
    # fixture is derived from the pre-mutation constant and does not grow with it.
    monkeypatch.setattr(lifecycle, "_RECLAIM_CHUNK", len(orphan_ids) + 1)

    with pytest.raises(sqlite3.OperationalError, match="too many SQL variables"):
        reclaim_orphan_reference_data(conn)

    # The pass rolled its transaction back, so nothing was half-deleted.
    assert conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == seeded


# ---------------------------------------------------------------------------
# E-277-02: the clean-connection precondition at all THREE entry points
# ---------------------------------------------------------------------------


def _dirty(conn):
    """Leave ``conn`` with uncommitted DML in flight, as a caller mid-work would."""
    conn.execute(
        "INSERT INTO teams (name, membership_type, is_active) "
        "VALUES ('InFlight', 'tracked', 0)"
    )
    assert conn.in_transaction, "fixture precondition: connection must be dirty"
    return conn


def _visible_to_another_connection(db_path):
    """Team count as seen by a SEPARATE connection -- i.e. what is COMMITTED."""
    probe = sqlite3.connect(str(db_path))
    try:
        return probe.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    finally:
        probe.close()


def test_reclaim_refuses_dirty_connection_and_preserves_caller_work(conn, tmp_path):
    """AC-1: reclaim raises; the caller's work is neither committed nor deleted,
    and the caller's own rollback still discards it as intended."""
    _dirty(conn)

    with pytest.raises(RuntimeError, match="no open transaction"):
        reclaim_orphan_reference_data(conn)

    # Not committed: an independent connection cannot see the row.
    assert _visible_to_another_connection(tmp_path / "reclaim.db") == 0
    # Not deleted: the caller's own view still has it, and rollback still works.
    assert conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 1
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 0


def test_reap_refuses_dirty_connection_before_committing(conn, tmp_path):
    """AC-2: the reaper raises before its unconditional commit fires."""
    _dirty(conn)

    with pytest.raises(RuntimeError, match="no open transaction"):
        lifecycle.reap_stale_generating_reports(conn)

    assert _visible_to_another_connection(tmp_path / "reclaim.db") == 0
    assert conn.in_transaction, "the caller's transaction must still be open"
    # AC-2: observe the OUTCOME as AC-1 does, not merely the flag -- the caller's
    # subsequent rollback still discards the DML as it intended. `in_transaction`
    # being True is the mechanism; this is the property that matters.
    assert conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 1
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 0


def test_cleanup_refuses_dirty_connection_before_reap_and_before_commit(
    conn, tmp_path, monkeypatch
):
    """AC-2.1: cleanup raises at ENTRY -- before the reap is invoked at all.

    The guard sits outside the ``try`` that swallows reaper failures. Placed
    inside it the raise would be caught, execution would continue into cleanup's
    own unconditional commit, and the bypass would reproduce verbatim: the
    caller's work committed, then deleted by the reclamation at the end.
    """
    called = []
    monkeypatch.setattr(
        lifecycle,
        "reap_stale_generating_reports",
        lambda *a, **k: called.append(1),
    )
    _dirty(conn)

    with pytest.raises(RuntimeError, match="no open transaction"):
        cleanup_expired_reports(conn)

    assert called == [], "the guard must fire BEFORE the reap is invoked"
    assert _visible_to_another_connection(tmp_path / "reclaim.db") == 0
    assert conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 1
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 0


def test_reclaim_guard_fires_before_the_reap(conn, monkeypatch):
    """AC-3: below the reap the guard could never observe the dirty state, because
    the reap's unconditional commit would already have cleared it."""
    called = []
    monkeypatch.setattr(
        lifecycle,
        "reap_stale_generating_reports",
        lambda *a, **k: called.append(1),
    )
    _dirty(conn)

    with pytest.raises(RuntimeError):
        reclaim_orphan_reference_data(conn)

    assert called == []


def test_guard_is_not_an_assertion(conn):
    """AC-4 (first half): the raise is NOT an ``AssertionError``.

    Runs under both normal and ``-O`` interpreters, so it fails immediately if a
    later change swaps the ``RuntimeError`` for a bare ``assert`` -- which ``-O``
    would strip, silently removing the protection with no test failing.
    """
    _dirty(conn)
    with pytest.raises(RuntimeError) as excinfo:
        reclaim_orphan_reference_data(conn)
    assert not isinstance(excinfo.value, AssertionError)


def test_guard_survives_python_dash_O(tmp_path):
    """AC-4 (second half): the guard still raises under ``python -O``.

    A COMMITTED test rather than a one-time demonstration -- a manual check
    leaves no regression signal, which is the gap this AC exists to close.
    """
    db_path = tmp_path / "opt.db"
    script = tmp_path / "probe.py"
    script.write_text(
        "import sqlite3, sys\n"
        f"sys.path.insert(0, {str(_REPO_ROOT_FOR_TESTS)!r})\n"
        "from tests.conftest import load_real_schema\n"
        "from src.reports.lifecycle import reclaim_orphan_reference_data\n"
        f"c = sqlite3.connect({str(db_path)!r})\n"
        "load_real_schema(c); c.commit()\n"
        "c.execute(\"INSERT INTO teams (name, membership_type) VALUES ('X','tracked')\")\n"
        # NOT `assert c.in_transaction` -- `python -O` STRIPS asserts, which is
        # this very test's subject. A stripped precondition guard would let the
        # probe run against a clean connection and report a false PASS.
        "if not c.in_transaction:\n"
        "    print('PRECONDITION_FAILED'); sys.exit(2)\n"
        "try:\n"
        "    reclaim_orphan_reference_data(c)\n"
        "except RuntimeError:\n"
        "    print('GUARD_RAISED'); sys.exit(0)\n"
        "print('GUARD_DID_NOT_RAISE'); sys.exit(1)\n"
    )
    proc = subprocess.run(
        [sys.executable, "-O", str(script)],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    # Tokens are disjoint on purpose. The earlier pair was 'RAISED' / 'NOT
    # RAISED', and `"RAISED" in "NOT RAISED"` is True -- so the substring check
    # was satisfied by the FAILURE output and discriminated only because the
    # returncode assertion happened to precede it.
    assert "GUARD_RAISED" in proc.stdout
    assert "GUARD_DID_NOT_RAISE" not in proc.stdout
    assert "PRECONDITION_FAILED" not in proc.stdout


def test_guard_skips_the_owned_connection_path(tmp_path, monkeypatch):
    """AC-5: ``conn=None`` must NOT raise.

    ``bb report cleanup`` passes no connection and does NOT wrap the call in a
    try/except, so an unconditional guard crashes it outright -- where
    ``generate_report`` would merely log at ERROR and continue. An implementer
    testing only the generator path would not notice.
    """
    db_path = tmp_path / "owned.db"
    seed = sqlite3.connect(str(db_path))
    load_real_schema(seed)
    seed.commit()
    seed.close()

    monkeypatch.setattr(
        lifecycle, "get_connection", lambda: sqlite3.connect(str(db_path))
    )
    monkeypatch.setattr(lifecycle, "_REPO_ROOT", tmp_path)

    # Neither call raises, and neither returns an error result.
    assert lifecycle.reap_stale_generating_reports().errors == 0
    assert cleanup_expired_reports().errors == 0


def test_clean_borrowed_connection_is_unchanged(conn):
    """AC-5: a clean borrowed connection behaves exactly as before the guard."""
    _add_season(conn)
    orphan = _add_team(conn, "Orphan")
    conn.commit()
    assert not conn.in_transaction

    result = reclaim_orphan_reference_data(conn)

    assert result.teams_deleted == 1
    assert conn.execute("SELECT COUNT(*) FROM teams WHERE id=?", (orphan,)).fetchone()[0] == 0


def test_precondition_check_is_single_sourced(conn, monkeypatch):
    """AC-5a: the reap and the reclaim route through ONE shared check.

    Patching the shared helper and asserting each consults it pins the
    single-sourcing behaviourally: an inlined copy in **either of these two**
    would bypass the patch and fail here.

    **This test covers TWO of the three entry points, not three.** It never
    invokes ``cleanup_expired_reports``, so an inlined copy THERE leaves this
    test GREEN -- measured, not assumed: under code-reviewer's ac5a mutation
    (a duplicated check in cleanup) this test PASSES and only
    ``test_cleanup_also_routes_through_the_shared_check`` fails. That sibling is
    the third entry point's only coverage and is why it exists; see its
    docstring. Do not read this one as covering all three.

    Three hand-maintained copies is the second-path shape
    ``canonical-seams.md`` names as this repo's recurring defect.
    """
    seen = []
    monkeypatch.setattr(
        lifecycle,
        "_require_clean_connection",
        lambda c, name: seen.append(name),
    )

    lifecycle.reap_stale_generating_reports(conn)
    reclaim_orphan_reference_data(conn)

    assert "reap_stale_generating_reports" in seen
    assert "reclaim_orphan_reference_data" in seen


def test_cleanup_also_routes_through_the_shared_check(conn, monkeypatch, tmp_path):
    """AC-5a, third entry point (kept separate so a cleanup-only regression is
    not masked by the other two passing).

    **DO NOT REMOVE AS REDUNDANT WITH THE TEST ABOVE.** Under the
    duplicate-the-check mutation, ``test_precondition_check_is_single_sourced``
    PASSES and only this one fails -- so the two are not interchangeable, and
    the pair's coverage is carried by this half. Measured by code-reviewer's
    scoped mutation, not assumed.
    """
    seen = []
    monkeypatch.setattr(
        lifecycle, "_require_clean_connection", lambda c, name: seen.append(name)
    )
    monkeypatch.setattr(lifecycle, "_REPO_ROOT", tmp_path)

    cleanup_expired_reports(conn)

    assert "cleanup_expired_reports" in seen


def test_every_rollback_in_the_module_is_transaction_guarded():
    """AC-6b: EVERY ``conn.execute("ROLLBACK")`` sits inside ``if
    conn.in_transaction:``.

    Asserted structurally rather than behaviourally, and the reason is worth
    stating: for the Step-2 deferral gate there is no naturally reachable state
    in which the transaction has already ended -- ``BEGIN IMMEDIATE`` succeeds
    two statements earlier -- so any behavioural test would have to model a
    state and would then be testing the model. The property that actually
    matters is that no unguarded ROLLBACK exists at all, which is checkable
    directly and which also catches a FOURTH one added later.

    This is the invariant "safe because of what happened two statements ago"
    fails to provide: it holds no matter what the surrounding code does.
    """
    import ast

    source = (_REPO_ROOT_FOR_TESTS / "src" / "reports" / "lifecycle.py").read_text()
    tree = ast.parse(source)
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child.parent = parent  # type: ignore[attr-defined]

    def _is_rollback(node):
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "ROLLBACK"
        )

    def _guarded(node):
        cur = getattr(node, "parent", None)
        while cur is not None:
            test = getattr(cur, "test", None)
            if (
                isinstance(cur, ast.If)
                and isinstance(test, ast.Attribute)
                and test.attr == "in_transaction"
            ):
                return True
            cur = getattr(cur, "parent", None)
        return False

    rollbacks = [n for n in ast.walk(tree) if _is_rollback(n)]
    # Anti-vacuity: if the call shape ever changes, this test must not silently
    # pass by finding nothing to check.
    assert len(rollbacks) >= 2, f"expected at least 2 ROLLBACK sites, found {len(rollbacks)}"
    unguarded = [n.lineno for n in rollbacks if not _guarded(n)]
    assert not unguarded, f"unguarded conn.execute('ROLLBACK') at line(s) {unguarded}"


def test_rollback_handler_propagates_the_original_failure(conn, monkeypatch):
    """AC-6: when SQLite has ALREADY auto-rolled back, the handler must not
    replace the real cause with "cannot rollback - no transaction is active".

    The precondition is MODELLED rather than forced: a genuine ``SQLITE_FULL``
    could not be produced (capping ``max_page_count`` does not trip it, because
    the sweep's DELETEs free pages rather than allocating them). Here an internal
    step ends the transaction and then raises, which is the same state.
    """
    original = sqlite3.OperationalError("database or disk is full")

    def _boom(c):
        c.execute("ROLLBACK")  # SQLite's auto-rollback, modelled
        raise original

    monkeypatch.setattr(lifecycle, "count_orphan_reference_data", _boom)

    with pytest.raises(sqlite3.OperationalError) as excinfo:
        reclaim_orphan_reference_data(conn)

    assert excinfo.value is original
    assert "cannot rollback" not in str(excinfo.value)


# ---------------------------------------------------------------------------
# AC-8: single-source count == len(sets) + roster count; roots-excluded count
# ---------------------------------------------------------------------------


def test_count_matches_producers(conn):
    _add_season(conn)
    o1 = _add_team(conn, "O1")
    o2 = _add_team(conn, "O2")
    _add_player(conn, "p-1")
    _add_roster(conn, o1, "p-1")
    _add_player(conn, "p-2")  # bare orphan player, no roster
    conn.commit()

    counts = count_orphan_reference_data(conn)
    assert counts.teams == len(_orphan_team_ids(conn)) == 2
    assert counts.players == len(_orphan_player_ids(conn)) == 2
    assert counts.roster_rows == 1


def test_count_excludes_roots_no_false_leak(conn):
    """A tracked, resolved-but-unreported opponent is orphan-SHAPED but a ROOT;
    the count must not flag it as a leak."""
    _add_season(conn)
    member = _add_team(conn, "Member", membership="member")
    resolved = _add_team(conn, "ResolvedNotReported")
    conn.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, resolved_team_id) "
        "VALUES (?, 'r', 'Opp', ?)",
        (member, resolved),
    )
    conn.commit()

    assert count_orphan_reference_data(conn) == OrphanCounts(0, 0, 0)

    # The case above covers the ``resolved_team_id`` root; the two seeded below
    # cover ``user_team_access`` and ``scheduled_report_runs``.  Every root is
    # covered -- ``our_team_id`` TRANSITIVELY, via ``_orphan_team_ids``, the
    # producer this count derives from, which
    # ``test_root_survivors_are_excluded_and_untouched`` asserts on directly.
    # That test does NOT call ``count_orphan_reference_data`` (E-277-01).
    granted = _add_team(conn, "GrantedNotReported")
    user = _add_user(conn)
    conn.execute(
        "INSERT INTO user_team_access (user_id, team_id) VALUES (?, ?)", (user, granted)
    )
    slot_owner = _add_team(conn, "SlotOwnerNotReported")
    _add_slot(conn, slot_owner, root_team_id="root-count")
    conn.commit()

    assert count_orphan_reference_data(conn) == OrphanCounts(0, 0, 0)


# ---------------------------------------------------------------------------
# AC-7: reap-then-gate concurrency guard + deferral, single-transaction TOCTOU
# ---------------------------------------------------------------------------


def test_defers_when_live_generating_report_exists(conn):
    _add_season(conn)
    live = _add_team(conn, "LiveGen")
    # A FRESH generating report (recent generated_at) survives the reap.
    _add_report(conn, live, "rpt-live", status="generating")
    orphan = _add_team(conn, "Orphan")
    conn.commit()

    result = reclaim_orphan_reference_data(conn)

    assert result.deferred is True
    assert result.teams_deleted == 0
    assert result.players_deleted == 0
    # Nothing deleted -- the orphan survives the deferral.
    assert conn.execute("SELECT COUNT(*) FROM teams WHERE id=?", (orphan,)).fetchone()[0] == 1


def test_proceeds_after_reaping_stale_generating(conn):
    _add_season(conn)
    stale_team = _add_team(conn, "StaleGen")
    old_ts = (
        datetime.now(timezone.utc) - timedelta(seconds=7200)
    ).strftime(UTC_ISO_FORMAT)
    _add_report(conn, stale_team, "rpt-stale", status="generating", generated_at=old_ts)
    orphan = _add_team(conn, "Orphan")
    conn.commit()

    result = reclaim_orphan_reference_data(conn)

    # The stale generating report was reaped to failed, so the gate passed.
    assert result.deferred is False
    assert (
        conn.execute(
            "SELECT status FROM reports WHERE slug='rpt-stale'"
        ).fetchone()[0]
        == "failed"
    )
    assert result.teams_deleted == 1
    assert conn.execute("SELECT COUNT(*) FROM teams WHERE id=?", (orphan,)).fetchone()[0] == 0


def test_single_transaction_does_not_lose_concurrent_stub(tmp_path, monkeypatch):
    """TOCTOU regression: a generation committing an opponent stub on ANOTHER
    connection mid-sweep must not be deleted.  The pass owns a single
    write-locked (``BEGIN IMMEDIATE``) transaction, so the stub -- committed
    after the pass's snapshot -- is never in the orphan set."""
    db_path = tmp_path / "toctou.db"
    setup = sqlite3.connect(str(db_path))
    setup.execute("PRAGMA journal_mode=WAL")
    load_real_schema(setup)
    _add_season(setup)
    orphan = _add_team(setup, "GenuineOrphan")  # deleted by the pass
    setup.commit()
    setup.close()

    conn_pass = sqlite3.connect(str(db_path))
    conn_pass.execute("PRAGMA busy_timeout=10000")

    stub = {}
    proceed = threading.Event()

    def gen_worker():
        cg = sqlite3.connect(str(db_path))
        cg.execute("PRAGMA busy_timeout=10000")
        proceed.wait(timeout=10)
        cur = cg.execute(
            "INSERT INTO teams (name, membership_type) VALUES ('LiveStub', 'tracked')"
        )
        cg.commit()  # blocks on the pass's write lock, lands AFTER the snapshot
        stub["id"] = cur.lastrowid
        cg.close()

    real = lifecycle._orphan_team_ids

    def spy(conn, *, warn=False):
        ids = real(conn, warn=warn)
        if not proceed.is_set():
            proceed.set()  # let the generation attempt its (blocked) commit
            time.sleep(0.2)  # give it time to reach the blocked write
        return ids

    monkeypatch.setattr(lifecycle, "_orphan_team_ids", spy)

    worker = threading.Thread(target=gen_worker)
    worker.start()
    result = reclaim_orphan_reference_data(conn_pass)
    worker.join(timeout=15)

    assert result.teams_deleted == 1  # only the genuine orphan
    assert conn_pass.execute("SELECT COUNT(*) FROM teams WHERE id=?", (orphan,)).fetchone()[0] == 0
    # The concurrently-committed stub survived (not lost to the sweep).
    assert stub.get("id") is not None
    assert (
        conn_pass.execute("SELECT COUNT(*) FROM teams WHERE id=?", (stub["id"],)).fetchone()[0]
        == 1
    )
    conn_pass.close()


# ---------------------------------------------------------------------------
# E-273-02 AC-3: reclamation wired into cleanup_expired_reports (after its reap)
# ---------------------------------------------------------------------------


def test_cleanup_expired_reports_runs_reclamation(conn):
    """AC-3: cleanup_expired_reports invokes the reclamation pass, so an orphan
    is reclaimed by the opportunistic cleanup trigger (not just the delete path).
    """
    _add_season(conn)
    orphan = _add_team(conn, "OrphanViaCleanup")
    conn.commit()

    cleanup_expired_reports(conn)

    assert conn.execute("SELECT COUNT(*) FROM teams WHERE id=?", (orphan,)).fetchone()[0] == 0
    assert count_orphan_reference_data(conn) == OrphanCounts(0, 0, 0)


def test_cleanup_expired_reports_defers_to_live_generation(conn):
    """AC-3: the cleanup_expired_reports trigger ALSO fires at the START of every
    generate_report; that invocation must not delete an in-flight generation's
    team.  A team protected by a live 'generating' report is NOT swept (the pass
    defers via its reap-then-gate guard), and no expiry-cleanup error is raised.
    """
    _add_season(conn)
    gen_team = _add_team(conn, "InFlightGenTeam")
    _add_report(conn, gen_team, "rpt-inflight", status="generating")  # fresh -> live
    conn.commit()

    result = cleanup_expired_reports(conn)  # must not raise

    # The in-flight generation's team survives the opportunistic sweep.
    assert conn.execute("SELECT COUNT(*) FROM teams WHERE id=?", (gen_team,)).fetchone()[0] == 1
    assert result.errors == 0


# ---------------------------------------------------------------------------
# E-273-02 AC-5: the pass is NOT wired into generator._cleanup_orphans
# ---------------------------------------------------------------------------


def test_cleanup_orphans_does_not_invoke_reclamation(tmp_path):
    """AC-5: a report generation's _cleanup_orphans makes ZERO calls to
    reclaim_orphan_reference_data (created-set cleanup only), while still
    removing the run's own orphan stubs via cleanup_orphan_teams."""
    from src.reports import generator as gen_mod

    db_path = tmp_path / "cleanup_orphans.db"
    setup = sqlite3.connect(str(db_path))
    load_real_schema(setup)
    _add_season(setup)
    stub = _add_team(setup, "RunCreatedStub")  # a stub this run created
    setup.commit()
    setup.close()

    def _open():
        c = sqlite3.connect(str(db_path))
        c.execute("PRAGMA foreign_keys=ON")
        return c

    inst = gen_mod._ReportGeneration.__new__(gen_mod._ReportGeneration)
    inst.orphan_ids = {stub}

    with patch.object(gen_mod, "get_connection", side_effect=_open), patch.object(
        lifecycle, "reclaim_orphan_reference_data"
    ) as spy:
        inst._cleanup_orphans()

    assert spy.call_count == 0, "_cleanup_orphans must NOT invoke the global reclamation pass"
    # The created-set cleanup still removed the run's own orphan stub.
    check = _open()
    assert check.execute("SELECT COUNT(*) FROM teams WHERE id=?", (stub,)).fetchone()[0] == 0
    check.close()

    # Structural anti-regression guard (CR durability note): the call-count spy
    # above patches the name in the LIFECYCLE namespace, so it would NOT
    # intercept a future `from src.reports.lifecycle import
    # reclaim_orphan_reference_data` bound into the GENERATOR namespace and
    # called there. Assert directly that generator does not expose the symbol at
    # all -- this fails the moment anyone imports reclaim into generator, closing
    # the spy's blind spot.
    assert not hasattr(gen_mod, "reclaim_orphan_reference_data"), (
        "reclaim_orphan_reference_data must NOT be imported into the generator "
        "namespace (report generation is additive; the global sweep is wired "
        "only into the delete paths + cleanup_expired_reports, per TN-4)"
    )
