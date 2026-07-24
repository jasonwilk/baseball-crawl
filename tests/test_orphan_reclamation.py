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
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from src.reports import lifecycle
from src.reports.lifecycle import (
    OrphanCounts,
    ReclaimResult,
    _orphan_player_ids,
    _orphan_team_ids,
    count_orphan_reference_data,
    reclaim_orphan_reference_data,
)
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
    conn.execute(
        "INSERT INTO scheduled_report_runs "
        "(own_team_id, opponent_root_team_id, game_date, resolution_outcome) "
        "VALUES (?, 'root-1', '2026-04-01', 'no_gc_presence')",
        (orphan,),
    )
    conn.commit()

    result = reclaim_orphan_reference_data(conn)

    assert isinstance(result, ReclaimResult)
    assert result.deferred is False
    assert result.teams_deleted == 1
    assert result.roster_rows_deleted == 1
    assert result.players_deleted == 1  # p-orphan was roster-only on the orphan

    assert conn.execute("SELECT COUNT(*) FROM teams WHERE id=?", (orphan,)).fetchone()[0] == 0
    for table, col in [
        ("team_rosters", "team_id"),
        ("scouting_runs", "team_id"),
        ("crawl_jobs", "team_id"),
        ("coaching_assignments", "team_id"),
        ("scheduled_report_runs", "own_team_id"),
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
# AC-4: the three root survivors -- resolved_team_id, our_team_id, grant --
#       each survives in isolation; no operator/user-decision row is touched
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
    # A genuine orphan proves the pass actually ran (anti-vacuity).
    orphan = _add_team(conn, "Orphan")
    conn.commit()

    orphan_ids = _orphan_team_ids(conn)
    assert resolved not in orphan_ids
    assert our_owner not in orphan_ids
    assert granted not in orphan_ids
    assert orphan in orphan_ids

    result = reclaim_orphan_reference_data(conn)
    assert result.teams_deleted == 1  # only the genuine orphan

    for tid in (resolved, our_owner, granted):
        assert conn.execute("SELECT COUNT(*) FROM teams WHERE id=?", (tid,)).fetchone()[0] == 1
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
