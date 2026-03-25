# synthetic-test-data
"""Tests for src/db/merge.py -- Team merge core logic (E-155-01).

Uses in-memory SQLite databases created from the full migration schema.
No real DB file is read or written.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.db.merge import (
    DuplicateTeam,
    MergeBlockedError,
    MergePreview,
    find_duplicate_teams,
    merge_teams,
    preview_merge,
)

# ---------------------------------------------------------------------------
# Schema fixture
# ---------------------------------------------------------------------------

_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "migrations" / "001_initial_schema.sql"
_CRAWL_JOBS_PATH = Path(__file__).resolve().parents[1] / "migrations" / "003_add_crawl_jobs.sql"
_SEASON_YEAR_PATH = Path(__file__).resolve().parents[1] / "migrations" / "004_add_team_season_year.sql"


def _make_db() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the full schema applied."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA_PATH.read_text())
    conn.executescript(_CRAWL_JOBS_PATH.read_text())
    conn.executescript(_SEASON_YEAR_PATH.read_text())
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _team(
    conn: sqlite3.Connection,
    name: str,
    membership_type: str = "tracked",
    gc_uuid: str | None = None,
    public_id: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, public_id) VALUES (?, ?, ?, ?)",
        (name, membership_type, gc_uuid, public_id),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def _member_team(conn: sqlite3.Connection, name: str, **kwargs: object) -> int:
    return _team(conn, name, membership_type="member", **kwargs)  # type: ignore[arg-type]


def _season(conn: sqlite3.Connection, season_id: str = "2026-spring") -> str:
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year)"
        " VALUES (?, 'Spring 2026', 'spring-hs', 2026)",
        (season_id,),
    )
    conn.commit()
    return season_id


def _player(conn: sqlite3.Connection, player_id: str) -> str:
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, 'John', 'Doe')",
        (player_id,),
    )
    conn.commit()
    return player_id


def _user(conn: sqlite3.Connection, email: str = "coach@test.com") -> int:
    cur = conn.execute(
        "INSERT OR IGNORE INTO users (email) VALUES (?)",
        (email,),
    )
    conn.commit()
    return cur.lastrowid or conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]  # type: ignore[return-value]


def _game(
    conn: sqlite3.Connection,
    game_id: str,
    home_team_id: int,
    away_team_id: int,
    season_id: str = "2026-spring",
) -> str:
    conn.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id)"
        " VALUES (?, ?, '2026-04-01', ?, ?)",
        (game_id, season_id, home_team_id, away_team_id),
    )
    conn.commit()
    return game_id


def _assert_team_gone(conn: sqlite3.Connection, team_id: int) -> None:
    count = conn.execute("SELECT COUNT(*) FROM teams WHERE id = ?", (team_id,)).fetchone()[0]
    assert count == 0, f"Team id={team_id} still exists"


def _assert_no_refs(conn: sqlite3.Connection, duplicate_id: int) -> None:
    """Assert no row in any of the 13 referencing tables still points to duplicate_id."""
    checks = [
        ("team_opponents", "our_team_id"),
        ("team_opponents", "opponent_team_id"),
        ("team_rosters", "team_id"),
        ("games", "home_team_id"),
        ("games", "away_team_id"),
        ("player_game_batting", "team_id"),
        ("player_game_pitching", "team_id"),
        ("player_season_batting", "team_id"),
        ("player_season_pitching", "team_id"),
        ("spray_charts", "team_id"),
        ("opponent_links", "our_team_id"),
        ("opponent_links", "resolved_team_id"),
        ("scouting_runs", "team_id"),
        ("user_team_access", "team_id"),
        ("coaching_assignments", "team_id"),
        ("crawl_jobs", "team_id"),
    ]
    for table, col in checks:
        n = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {col} = ?",  # noqa: S608
            (duplicate_id,),
        ).fetchone()[0]
        assert n == 0, f"Stale reference in {table}.{col} to duplicate_id={duplicate_id}"


# ---------------------------------------------------------------------------
# AC-3: Blocking checks
# ---------------------------------------------------------------------------


def test_blocking_canonical_does_not_exist() -> None:
    conn = _make_db()
    dup = _team(conn, "Dup")
    with pytest.raises(MergeBlockedError, match="Canonical team id=9999 does not exist"):
        merge_teams(9999, dup, conn)


def test_blocking_duplicate_does_not_exist() -> None:
    conn = _make_db()
    can = _team(conn, "Can")
    with pytest.raises(MergeBlockedError, match="Duplicate team id=9999 does not exist"):
        merge_teams(can, 9999, conn)


def test_blocking_same_id() -> None:
    conn = _make_db()
    can = _team(conn, "Team")
    with pytest.raises(MergeBlockedError, match="different"):
        merge_teams(can, can, conn)


def test_blocking_member_team() -> None:
    conn = _make_db()
    can = _team(conn, "Canonical")
    dup = _member_team(conn, "Duplicate Member")
    with pytest.raises(MergeBlockedError, match="membership_type='member'"):
        merge_teams(can, dup, conn)


def test_preview_blocking_issues_populated() -> None:
    conn = _make_db()
    preview = preview_merge(9999, 8888, conn)
    assert len(preview.blocking_issues) == 2  # both missing
    assert any("9999" in issue for issue in preview.blocking_issues)
    assert any("8888" in issue for issue in preview.blocking_issues)


def test_preview_blocking_same_id() -> None:
    conn = _make_db()
    can = _team(conn, "Team")
    preview = preview_merge(can, can, conn)
    assert any("different" in issue for issue in preview.blocking_issues)


def test_preview_blocking_member_duplicate() -> None:
    conn = _make_db()
    can = _team(conn, "Can")
    dup = _member_team(conn, "Dup")
    preview = preview_merge(can, dup, conn)
    assert any("member" in issue for issue in preview.blocking_issues)


# ---------------------------------------------------------------------------
# AC-1 / AC-3: Self-reference auto-deletion (opponent_links, team_opponents)
# ---------------------------------------------------------------------------


def test_self_ref_auto_delete_opponent_links_direction_a() -> None:
    """resolved_team_id=duplicate, our_team_id=canonical => self-ref after merge."""
    conn = _make_db()
    can = _team(conn, "Canonical")
    dup = _team(conn, "Duplicate")
    # self-ref: our=canonical, resolved=duplicate (would become our=can, resolved=can)
    conn.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, resolved_team_id)"
        " VALUES (?, 'root-1', 'Opp', ?)",
        (can, dup),
    )
    conn.commit()

    merge_teams(can, dup, conn)
    _assert_team_gone(conn, dup)
    _assert_no_refs(conn, dup)
    # The self-ref row must be gone
    n = conn.execute("SELECT COUNT(*) FROM opponent_links WHERE our_team_id = ? AND resolved_team_id = ?", (can, can)).fetchone()[0]
    assert n == 0


def test_self_ref_auto_delete_opponent_links_direction_b() -> None:
    """our_team_id=duplicate, resolved_team_id=canonical => self-ref after merge."""
    conn = _make_db()
    can = _team(conn, "Canonical")
    dup = _team(conn, "Duplicate")
    conn.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, resolved_team_id)"
        " VALUES (?, 'root-2', 'Opp', ?)",
        (dup, can),
    )
    conn.commit()

    merge_teams(can, dup, conn)
    _assert_team_gone(conn, dup)
    _assert_no_refs(conn, dup)


def test_self_ref_auto_delete_team_opponents_direction_a() -> None:
    """opponent_team_id=duplicate, our_team_id=canonical => would violate CHECK after merge."""
    conn = _make_db()
    can = _team(conn, "Canonical")
    dup = _team(conn, "Duplicate")
    # Insert bypassing CHECK by temporarily disabling FK (CHECK(our != opponent))
    # our=canonical, opponent=duplicate: after reassignment -> (can, can) violates CHECK
    conn.execute(
        "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
        (can, dup),
    )
    conn.commit()

    merge_teams(can, dup, conn)
    _assert_team_gone(conn, dup)
    _assert_no_refs(conn, dup)
    n = conn.execute(
        "SELECT COUNT(*) FROM team_opponents WHERE our_team_id = ? AND opponent_team_id = ?",
        (can, can),
    ).fetchone()[0]
    assert n == 0


def test_self_ref_auto_delete_team_opponents_direction_b() -> None:
    """our_team_id=duplicate, opponent_team_id=canonical => would violate CHECK after merge."""
    conn = _make_db()
    can = _team(conn, "Canonical")
    dup = _team(conn, "Duplicate")
    conn.execute(
        "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
        (dup, can),
    )
    conn.commit()

    merge_teams(can, dup, conn)
    _assert_team_gone(conn, dup)
    _assert_no_refs(conn, dup)


# ---------------------------------------------------------------------------
# AC-4: Canonical wins -- conflict deletion
# ---------------------------------------------------------------------------


def test_conflict_deletion_player_season_batting_canonical_wins() -> None:
    conn = _make_db()
    can = _team(conn, "Canonical")
    dup = _team(conn, "Duplicate")
    sid = _season(conn)
    pid = _player(conn, "p-1")

    # Both teams have batting stats for same player/season => conflict
    conn.execute(
        "INSERT INTO player_season_batting (player_id, team_id, season_id, ab) VALUES (?, ?, ?, ?)",
        (pid, can, sid, 10),
    )
    conn.execute(
        "INSERT INTO player_season_batting (player_id, team_id, season_id, ab) VALUES (?, ?, ?, ?)",
        (pid, dup, sid, 20),
    )
    conn.commit()

    merge_teams(can, dup, conn)

    # Only canonical row remains
    rows = conn.execute(
        "SELECT team_id, ab FROM player_season_batting WHERE player_id = ? AND season_id = ?",
        (pid, sid),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == can
    assert rows[0][1] == 10  # canonical's ab preserved


def test_conflict_deletion_team_opponents_canonical_wins() -> None:
    conn = _make_db()
    can = _team(conn, "Canonical")
    dup = _team(conn, "Duplicate")
    opp = _team(conn, "Opponent")

    # Both canonical and duplicate have the same opponent relationship
    conn.execute(
        "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
        (can, opp),
    )
    conn.execute(
        "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
        (dup, opp),
    )
    conn.commit()

    merge_teams(can, dup, conn)

    # Only one row for (canonical, opp) remains
    rows = conn.execute(
        "SELECT COUNT(*) FROM team_opponents WHERE our_team_id = ? AND opponent_team_id = ?",
        (can, opp),
    ).fetchone()[0]
    assert rows == 1


def test_nonconflicting_duplicate_rows_are_reassigned() -> None:
    """Rows from duplicate that don't conflict with canonical are reassigned."""
    conn = _make_db()
    can = _team(conn, "Canonical")
    dup = _team(conn, "Duplicate")
    opp = _team(conn, "Opponent")
    opp2 = _team(conn, "Opponent2")

    # canonical has opp, duplicate has opp2 (no conflict)
    conn.execute(
        "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
        (can, opp),
    )
    conn.execute(
        "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
        (dup, opp2),
    )
    conn.commit()

    merge_teams(can, dup, conn)

    # Both (can, opp) and (can, opp2) should now exist
    n = conn.execute(
        "SELECT COUNT(*) FROM team_opponents WHERE our_team_id = ?",
        (can,),
    ).fetchone()[0]
    assert n == 2


# ---------------------------------------------------------------------------
# AC-5: Atomicity / rollback
# ---------------------------------------------------------------------------


class _FailOnCallN(sqlite3.Connection):
    """sqlite3.Connection subclass that raises OperationalError on the Nth execute call."""

    _fail_counter: int
    _fail_on: int

    def set_fail_on(self, n: int) -> None:
        self._fail_on = n
        self._fail_counter = 0

    def execute(self, sql: str, *args: object, **kwargs: object) -> sqlite3.Cursor:  # type: ignore[override]
        self._fail_counter = getattr(self, "_fail_counter", 0) + 1
        fail_on = getattr(self, "_fail_on", None)
        if fail_on is not None and self._fail_counter >= fail_on:
            self._fail_on = None  # don't fail ROLLBACK
            raise sqlite3.OperationalError("Injected failure for rollback test")
        return super().execute(sql, *args, **kwargs)


def _make_failing_db() -> _FailOnCallN:
    conn = _FailOnCallN(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA_PATH.read_text())
    conn.executescript(_CRAWL_JOBS_PATH.read_text())
    conn.executescript(_SEASON_YEAR_PATH.read_text())
    conn.commit()
    return conn


def test_merge_rolls_back_on_failure() -> None:
    """Inject a failure mid-merge; verify no data was modified."""
    conn = _make_failing_db()
    can = _team(conn, "Canonical")
    dup = _team(conn, "Duplicate", gc_uuid="gc-dup")
    sid = _season(conn)
    pid = _player(conn, "p-rollback")

    conn.execute(
        "INSERT INTO player_season_batting (player_id, team_id, season_id, ab) VALUES (?, ?, ?, ?)",
        (pid, dup, sid, 50),
    )
    conn.commit()

    # Fail on the 5th execute call (mid-transaction, after identifiers are cleared)
    conn.set_fail_on(5)

    with pytest.raises(sqlite3.OperationalError, match="Injected failure"):
        merge_teams(can, dup, conn)

    # Both teams should still exist
    n_can = conn.execute("SELECT COUNT(*) FROM teams WHERE id = ?", (can,)).fetchone()[0]
    n_dup = conn.execute("SELECT COUNT(*) FROM teams WHERE id = ?", (dup,)).fetchone()[0]
    assert n_can == 1
    assert n_dup == 1

    # Duplicate's batting row unchanged
    ab = conn.execute(
        "SELECT ab FROM player_season_batting WHERE team_id = ?",
        (dup,),
    ).fetchone()[0]
    assert ab == 50

    # Duplicate's gc_uuid should be restored (rollback undid the NULL)
    dup_row = conn.execute("SELECT gc_uuid FROM teams WHERE id = ?", (dup,)).fetchone()
    assert dup_row[0] == "gc-dup"


# ---------------------------------------------------------------------------
# AC-6: Identifier gap-filling
# ---------------------------------------------------------------------------


def test_identifier_gap_fill_canonical_null_inherits_duplicate() -> None:
    conn = _make_db()
    can = _team(conn, "Canonical", gc_uuid=None, public_id=None)
    dup = _team(conn, "Duplicate", gc_uuid="gc-dup-uuid", public_id="dup-slug")

    merge_teams(can, dup, conn)

    row = conn.execute("SELECT gc_uuid, public_id FROM teams WHERE id = ?", (can,)).fetchone()
    assert row[0] == "gc-dup-uuid"
    assert row[1] == "dup-slug"


def test_identifier_gap_fill_canonical_wins_when_both_set() -> None:
    conn = _make_db()
    can = _team(conn, "Canonical", gc_uuid="gc-can-uuid", public_id="can-slug")
    dup = _team(conn, "Duplicate", gc_uuid="gc-dup-uuid", public_id="dup-slug")

    merge_teams(can, dup, conn)

    row = conn.execute("SELECT gc_uuid, public_id FROM teams WHERE id = ?", (can,)).fetchone()
    assert row[0] == "gc-can-uuid"  # canonical wins
    assert row[1] == "can-slug"


def test_identifier_gap_fill_partial_canonical_null_gc_uuid() -> None:
    """Canonical has public_id but NULL gc_uuid; should inherit dup's gc_uuid."""
    conn = _make_db()
    can = _team(conn, "Canonical", gc_uuid=None, public_id="can-slug")
    dup = _team(conn, "Duplicate", gc_uuid="gc-dup-uuid", public_id=None)

    merge_teams(can, dup, conn)

    row = conn.execute("SELECT gc_uuid, public_id FROM teams WHERE id = ?", (can,)).fetchone()
    assert row[0] == "gc-dup-uuid"
    assert row[1] == "can-slug"


def test_identifier_gap_fill_partial_unique_index_no_failure() -> None:
    """Verify the NULLing step prevents partial unique index violation."""
    conn = _make_db()
    # Duplicate has a gc_uuid; canonical has a different one.
    # The NULL-then-COALESCE pattern must not violate the partial unique index.
    can = _team(conn, "Canonical", gc_uuid="gc-can", public_id=None)
    dup = _team(conn, "Duplicate", gc_uuid="gc-dup", public_id="dup-slug")

    # Should not raise -- the NULLing step happens first
    merge_teams(can, dup, conn)

    row = conn.execute("SELECT gc_uuid, public_id FROM teams WHERE id = ?", (can,)).fetchone()
    assert row[0] == "gc-can"   # canonical wins
    assert row[1] == "dup-slug"  # filled from duplicate


# ---------------------------------------------------------------------------
# AC-7: Full merge with all 13 tables populated
# ---------------------------------------------------------------------------


def test_full_merge_all_13_tables() -> None:
    """After merge, duplicate is gone and no FK reference remains."""
    conn = _make_db()
    can = _team(conn, "Canonical", gc_uuid="gc-can", public_id="can-slug")
    dup = _team(conn, "Duplicate")
    opp = _team(conn, "Opponent")
    other_team = _team(conn, "Other")
    sid = _season(conn)
    pid1 = _player(conn, "p1")
    pid2 = _player(conn, "p2")
    uid = _user(conn)

    # team_opponents (non-conflicting)
    conn.execute(
        "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
        (dup, opp),
    )

    # team_rosters (non-conflicting)
    conn.execute(
        "INSERT INTO team_rosters (team_id, player_id, season_id) VALUES (?, ?, ?)",
        (dup, pid1, sid),
    )

    # games (home + away)
    _game(conn, "g-home", home_team_id=dup, away_team_id=opp)
    _game(conn, "g-away", home_team_id=opp, away_team_id=dup)

    # player_game_batting
    _game(conn, "g-pgb", home_team_id=dup, away_team_id=other_team, season_id=sid)
    conn.execute(
        "INSERT INTO player_game_batting (game_id, player_id, team_id) VALUES ('g-pgb', ?, ?)",
        (pid1, dup),
    )

    # player_game_pitching
    _game(conn, "g-pgp", home_team_id=dup, away_team_id=other_team, season_id=sid)
    conn.execute(
        "INSERT INTO player_game_pitching (game_id, player_id, team_id, ip_outs) VALUES ('g-pgp', ?, ?, 9)",
        (pid2, dup),
    )

    # player_season_batting (non-conflicting)
    conn.execute(
        "INSERT INTO player_season_batting (player_id, team_id, season_id, ab) VALUES (?, ?, ?, 30)",
        (pid2, dup, sid),
    )

    # player_season_pitching (non-conflicting)
    conn.execute(
        "INSERT INTO player_season_pitching (player_id, team_id, season_id, ip_outs) VALUES (?, ?, ?, 15)",
        (pid1, dup, sid),
    )

    # spray_charts
    _game(conn, "g-spray", home_team_id=dup, away_team_id=other_team, season_id=sid)
    conn.execute(
        "INSERT INTO spray_charts (game_id, player_id, team_id, x, y) VALUES ('g-spray', ?, ?, 10.0, 20.0)",
        (pid1, dup),
    )

    # opponent_links
    conn.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, resolved_team_id)"
        " VALUES (?, 'root-dup', 'Some Opp', ?)",
        (dup, opp),
    )

    # scouting_runs
    conn.execute(
        "INSERT INTO scouting_runs (team_id, season_id, status) VALUES (?, ?, 'pending')",
        (dup, sid),
    )

    # user_team_access
    conn.execute(
        "INSERT INTO user_team_access (user_id, team_id) VALUES (?, ?)",
        (uid, dup),
    )

    # coaching_assignments
    conn.execute(
        "INSERT INTO coaching_assignments (user_id, team_id, role) VALUES (?, ?, 'assistant')",
        (uid, dup),
    )

    # crawl_jobs
    conn.execute(
        "INSERT INTO crawl_jobs (team_id, sync_type, status) VALUES (?, 'scouting_crawl', 'completed')",
        (dup,),
    )

    conn.commit()

    # Run the merge
    merge_teams(can, dup, conn)

    # Duplicate is gone
    _assert_team_gone(conn, dup)

    # No stale references
    _assert_no_refs(conn, dup)


# ---------------------------------------------------------------------------
# AC-2: preview_merge return structure
# ---------------------------------------------------------------------------


def test_preview_returns_correct_structure() -> None:
    conn = _make_db()
    can = _team(conn, "Canonical", gc_uuid="gc-can", public_id="can-slug")
    dup = _team(conn, "Duplicate", gc_uuid="gc-dup", public_id="dup-slug")
    sid = _season(conn)
    pid = _player(conn, "p-prev")

    conn.execute(
        "INSERT INTO player_season_batting (player_id, team_id, season_id, ab) VALUES (?, ?, ?, 10)",
        (pid, can, sid),
    )
    conn.execute(
        "INSERT INTO player_season_batting (player_id, team_id, season_id, ab) VALUES (?, ?, ?, 20)",
        (pid, dup, sid),
    )
    conn.commit()

    preview = preview_merge(can, dup, conn)

    assert isinstance(preview, MergePreview)
    assert preview.blocking_issues == []
    assert preview.canonical_gc_uuid == "gc-can"
    assert preview.canonical_public_id == "can-slug"
    assert preview.duplicate_gc_uuid == "gc-dup"
    assert preview.duplicate_public_id == "dup-slug"
    assert preview.duplicate_is_member is False
    assert preview.conflict_counts.get("player_season_batting", 0) == 1
    # Database is unchanged
    n = conn.execute("SELECT COUNT(*) FROM teams WHERE id = ?", (dup,)).fetchone()[0]
    assert n == 1


def test_preview_games_between_teams() -> None:
    conn = _make_db()
    can = _team(conn, "Canonical")
    dup = _team(conn, "Duplicate")
    sid = _season(conn)
    _game(conn, "g1", home_team_id=can, away_team_id=dup, season_id=sid)
    _game(conn, "g2", home_team_id=dup, away_team_id=can, season_id=sid)

    preview = preview_merge(can, dup, conn)
    assert preview.games_between_teams == 2


def test_preview_self_ref_count() -> None:
    conn = _make_db()
    can = _team(conn, "Canonical")
    dup = _team(conn, "Duplicate")
    # Add a self-referencing opponent_links row
    conn.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, resolved_team_id)"
        " VALUES (?, 'root-self', 'Self', ?)",
        (can, dup),
    )
    conn.commit()

    preview = preview_merge(can, dup, conn)
    assert preview.self_ref_deletions == 1


def test_preview_duplicate_has_our_team_entries() -> None:
    conn = _make_db()
    can = _team(conn, "Canonical")
    dup = _team(conn, "Duplicate")
    opp = _team(conn, "Opponent")
    conn.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name) VALUES (?, 'root-x', 'X')",
        (dup,),
    )
    conn.commit()

    preview = preview_merge(can, dup, conn)
    assert preview.duplicate_has_our_team_entries is True


def test_preview_duplicate_member_flag() -> None:
    conn = _make_db()
    can = _team(conn, "Canonical")
    dup = _member_team(conn, "Duplicate Member")

    preview = preview_merge(can, dup, conn)
    assert preview.duplicate_is_member is True
    assert len(preview.blocking_issues) > 0


def test_preview_reassignment_counts_nonzero() -> None:
    conn = _make_db()
    can = _team(conn, "Canonical")
    dup = _team(conn, "Duplicate")
    sid = _season(conn)
    opp = _team(conn, "Opponent")

    conn.execute(
        "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
        (dup, opp),
    )
    conn.execute(
        "INSERT INTO scouting_runs (team_id, season_id, status) VALUES (?, ?, 'pending')",
        (dup, sid),
    )
    conn.commit()

    preview = preview_merge(can, dup, conn)
    assert preview.reassignment_counts.get("team_opponents", 0) >= 1
    assert preview.reassignment_counts.get("scouting_runs", 0) >= 1


# ---------------------------------------------------------------------------
# Additional edge case: simple clean merge (no data)
# ---------------------------------------------------------------------------


def test_simple_merge_empty_teams() -> None:
    conn = _make_db()
    can = _team(conn, "Canonical")
    dup = _team(conn, "Duplicate")

    merge_teams(can, dup, conn)

    _assert_team_gone(conn, dup)
    n_can = conn.execute("SELECT COUNT(*) FROM teams WHERE id = ?", (can,)).fetchone()[0]
    assert n_can == 1


def test_merge_preserves_other_teams() -> None:
    """Teams unrelated to the merge are untouched."""
    conn = _make_db()
    can = _team(conn, "Canonical")
    dup = _team(conn, "Duplicate")
    bystander = _team(conn, "Bystander")

    merge_teams(can, dup, conn)

    n = conn.execute("SELECT COUNT(*) FROM teams WHERE id = ?", (bystander,)).fetchone()[0]
    assert n == 1


def _team_year(
    conn: sqlite3.Connection,
    name: str,
    season_year: int | None = None,
    membership_type: str = "tracked",
    gc_uuid: str | None = None,
    public_id: str | None = None,
) -> int:
    """Insert a team with an explicit season_year value (may be NULL)."""
    cur = conn.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, public_id, season_year)"
        " VALUES (?, ?, ?, ?, ?)",
        (name, membership_type, gc_uuid, public_id, season_year),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def test_merge_games_both_fk_columns_reassigned() -> None:
    conn = _make_db()
    can = _team(conn, "Canonical")
    dup = _team(conn, "Duplicate")
    sid = _season(conn)
    opp = _team(conn, "Opponent")

    _game(conn, "g-home", home_team_id=dup, away_team_id=opp, season_id=sid)
    _game(conn, "g-away", home_team_id=opp, away_team_id=dup, season_id=sid)

    merge_teams(can, dup, conn)

    home_game = conn.execute("SELECT home_team_id FROM games WHERE game_id = 'g-home'").fetchone()
    away_game = conn.execute("SELECT away_team_id FROM games WHERE game_id = 'g-away'").fetchone()
    assert home_game[0] == can
    assert away_game[0] == can


def test_merge_succeeds_when_teams_played_each_other() -> None:
    """Merging teams with games against each other completes without error.

    After merge, games formerly between canonical and duplicate have both
    home_team_id and away_team_id set to canonical_id (a team that played
    itself).  This is accepted behavior -- the preview surfaces
    games_between_teams as a warning; if the admin proceeds anyway, the
    self-referencing game rows are the documented outcome.
    """
    conn = _make_db()
    can = _team(conn, "Canonical")
    dup = _team(conn, "Duplicate")
    sid = _season(conn)

    # Two games between the teams: one where canonical is home, one where it is away
    _game(conn, "g-can-home", home_team_id=can, away_team_id=dup, season_id=sid)
    _game(conn, "g-dup-home", home_team_id=dup, away_team_id=can, season_id=sid)

    # Should not raise despite games_between_teams > 0
    merge_teams(can, dup, conn)

    _assert_team_gone(conn, dup)

    # Both games now have canonical on both sides (team played itself)
    g1 = conn.execute(
        "SELECT home_team_id, away_team_id FROM games WHERE game_id = 'g-can-home'"
    ).fetchone()
    assert g1[0] == can, "home_team_id should be canonical"
    assert g1[1] == can, "away_team_id should be reassigned to canonical"

    g2 = conn.execute(
        "SELECT home_team_id, away_team_id FROM games WHERE game_id = 'g-dup-home'"
    ).fetchone()
    assert g2[0] == can, "home_team_id should be reassigned to canonical"
    assert g2[1] == can, "away_team_id should be canonical"


# ---------------------------------------------------------------------------
# find_duplicate_teams -- AC-1 through AC-6
# ---------------------------------------------------------------------------


def test_find_duplicates_basic_detection() -> None:
    """AC-1: Two tracked teams with the same name form one group of two."""
    conn = _make_db()
    t1 = _team_year(conn, "Lincoln East", season_year=2026)
    t2 = _team_year(conn, "Lincoln East", season_year=2026)

    groups = find_duplicate_teams(conn)

    assert len(groups) == 1
    assert len(groups[0]) == 2
    ids = {t.id for t in groups[0]}
    assert ids == {t1, t2}
    assert all(isinstance(t, DuplicateTeam) for t in groups[0])


def test_find_duplicates_returns_required_fields() -> None:
    """AC-1: Each DuplicateTeam has id, name, season_year, gc_uuid, public_id, game_count, has_stats."""
    conn = _make_db()
    _team_year(conn, "Lincoln East", season_year=2026, gc_uuid="gc-1", public_id="slug-1")
    _team_year(conn, "Lincoln East", season_year=2026, gc_uuid=None, public_id=None)

    groups = find_duplicate_teams(conn)
    assert len(groups) == 1
    for t in groups[0]:
        assert isinstance(t.id, int)
        assert isinstance(t.name, str)
        assert t.season_year == 2026
        assert isinstance(t.game_count, int)
        assert isinstance(t.has_stats, bool)


def test_find_duplicates_case_insensitive() -> None:
    """AC-2: 'Lincoln East', 'lincoln east', and 'LINCOLN EAST' are treated as the same."""
    conn = _make_db()
    t1 = _team_year(conn, "Lincoln East", season_year=2026)
    t2 = _team_year(conn, "lincoln east", season_year=2026)
    t3 = _team_year(conn, "LINCOLN EAST", season_year=2026)

    groups = find_duplicate_teams(conn)

    assert len(groups) == 1
    assert len(groups[0]) == 3
    ids = {t.id for t in groups[0]}
    assert ids == {t1, t2, t3}


def test_find_duplicates_excludes_member_teams() -> None:
    """AC-3: Member teams are not included in duplicate detection."""
    conn = _make_db()
    # One member, one tracked -- should NOT form a duplicate group
    _team_year(conn, "Lincoln East", season_year=2026, membership_type="member")
    _team_year(conn, "Lincoln East", season_year=2026)

    groups = find_duplicate_teams(conn)
    assert groups == []


def test_find_duplicates_member_plus_two_tracked_gives_one_group() -> None:
    """AC-3: Member team is excluded; two tracked teams with same name still detected."""
    conn = _make_db()
    _team_year(conn, "Lincoln East", season_year=2026, membership_type="member")
    t1 = _team_year(conn, "Lincoln East", season_year=2026)
    t2 = _team_year(conn, "Lincoln East", season_year=2026)

    groups = find_duplicate_teams(conn)

    assert len(groups) == 1
    ids = {t.id for t in groups[0]}
    assert ids == {t1, t2}


def test_find_duplicates_different_season_year_not_grouped() -> None:
    """AC-4: Teams with same name but different season_year are NOT flagged."""
    conn = _make_db()
    _team_year(conn, "Lincoln East", season_year=2025)
    _team_year(conn, "Lincoln East", season_year=2026)

    groups = find_duplicate_teams(conn)
    assert groups == []


def test_find_duplicates_both_null_season_year_are_grouped() -> None:
    """AC-4: Two tracked teams with same name and both NULL season_year ARE flagged."""
    conn = _make_db()
    t1 = _team_year(conn, "Lincoln East", season_year=None)
    t2 = _team_year(conn, "Lincoln East", season_year=None)

    groups = find_duplicate_teams(conn)

    assert len(groups) == 1
    ids = {t.id for t in groups[0]}
    assert ids == {t1, t2}


def test_find_duplicates_null_vs_nonnull_season_year_not_grouped() -> None:
    """AC-4: NULL season_year and non-NULL season_year with same name are NOT grouped."""
    conn = _make_db()
    _team_year(conn, "Lincoln East", season_year=None)
    _team_year(conn, "Lincoln East", season_year=2026)

    groups = find_duplicate_teams(conn)
    assert groups == []


def test_find_duplicates_game_count() -> None:
    """AC-5: game_count reflects games where team is home or away."""
    conn = _make_db()
    sid = _season(conn)
    opp = _team_year(conn, "Opponent", season_year=2026)
    t1 = _team_year(conn, "Lincoln East", season_year=2026)
    t2 = _team_year(conn, "Lincoln East", season_year=2026)

    _game(conn, "g1", home_team_id=t1, away_team_id=opp, season_id=sid)
    _game(conn, "g2", home_team_id=opp, away_team_id=t1, season_id=sid)

    groups = find_duplicate_teams(conn)
    assert len(groups) == 1

    by_id = {t.id: t for t in groups[0]}
    assert by_id[t1].game_count == 2
    assert by_id[t2].game_count == 0


def test_find_duplicates_has_stats_batting() -> None:
    """AC-5: has_stats is True when team has player_season_batting rows."""
    conn = _make_db()
    sid = _season(conn)
    pid = _player(conn, "p-batting")
    t1 = _team_year(conn, "Lincoln East", season_year=2026)
    t2 = _team_year(conn, "Lincoln East", season_year=2026)

    conn.execute(
        "INSERT INTO player_season_batting (player_id, team_id, season_id, ab) VALUES (?, ?, ?, 5)",
        (pid, t1, sid),
    )
    conn.commit()

    groups = find_duplicate_teams(conn)
    assert len(groups) == 1

    by_id = {t.id: t for t in groups[0]}
    assert by_id[t1].has_stats is True
    assert by_id[t2].has_stats is False


def test_find_duplicates_has_stats_pitching() -> None:
    """AC-5: has_stats is True when team has player_season_pitching rows."""
    conn = _make_db()
    sid = _season(conn)
    pid = _player(conn, "p-pitching")
    t1 = _team_year(conn, "Lincoln East", season_year=2026)
    t2 = _team_year(conn, "Lincoln East", season_year=2026)

    conn.execute(
        "INSERT INTO player_season_pitching (player_id, team_id, season_id, ip_outs) VALUES (?, ?, ?, 9)",
        (pid, t1, sid),
    )
    conn.commit()

    groups = find_duplicate_teams(conn)
    by_id = {t.id: t for t in groups[0]}
    assert by_id[t1].has_stats is True
    assert by_id[t2].has_stats is False


def test_find_duplicates_has_stats_scouting_runs() -> None:
    """AC-5: has_stats is True when team has scouting_runs rows."""
    conn = _make_db()
    sid = _season(conn)
    t1 = _team_year(conn, "Lincoln East", season_year=2026)
    t2 = _team_year(conn, "Lincoln East", season_year=2026)

    conn.execute(
        "INSERT INTO scouting_runs (team_id, season_id, status) VALUES (?, ?, 'completed')",
        (t1, sid),
    )
    conn.commit()

    groups = find_duplicate_teams(conn)
    by_id = {t.id: t for t in groups[0]}
    assert by_id[t1].has_stats is True
    assert by_id[t2].has_stats is False


def test_find_duplicates_empty_when_no_duplicates() -> None:
    """AC-6: Returns empty list when all tracked teams have unique names."""
    conn = _make_db()
    _team_year(conn, "Lincoln East", season_year=2026)
    _team_year(conn, "Lincoln North", season_year=2026)
    _team_year(conn, "Lincoln High", season_year=2025)

    groups = find_duplicate_teams(conn)
    assert groups == []


def test_find_duplicates_empty_when_no_teams() -> None:
    """AC-6: Returns empty list when no teams exist at all."""
    conn = _make_db()
    groups = find_duplicate_teams(conn)
    assert groups == []


# ---------------------------------------------------------------------------
# Codex P2 remediation: self-ref (dup, dup) case and BEGIN failure masking
# ---------------------------------------------------------------------------


def test_self_ref_auto_delete_same_column_opponent_links() -> None:
    """opponent_links row where both our_team_id=dup AND resolved_team_id=dup.

    After FK UPDATE this would become (canonical, canonical) -- a self-link.
    The merge must delete it before the FK reassignment.
    """
    conn = _make_db()
    can = _team(conn, "Canonical")
    dup = _team(conn, "Duplicate")

    # Row where both FK columns point to the duplicate team.
    conn.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, resolved_team_id)"
        " VALUES (?, 'root-same', 'Self', ?)",
        (dup, dup),
    )
    conn.commit()

    merge_teams(can, dup, conn)

    _assert_team_gone(conn, dup)
    _assert_no_refs(conn, dup)

    # No (can, can) self-link should remain in opponent_links
    n = conn.execute(
        "SELECT COUNT(*) FROM opponent_links WHERE our_team_id = ? AND resolved_team_id = ?",
        (can, can),
    ).fetchone()[0]
    assert n == 0


def test_preview_self_ref_count_includes_same_column_case() -> None:
    """preview_merge self_ref_deletions must count the (dup, dup) opponent_links row."""
    conn = _make_db()
    can = _team(conn, "Canonical")
    dup = _team(conn, "Duplicate")

    # Same-column self-ref: both columns point to the duplicate
    conn.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, resolved_team_id)"
        " VALUES (?, 'root-same2', 'Self2', ?)",
        (dup, dup),
    )
    conn.commit()

    preview = preview_merge(can, dup, conn)
    assert preview.self_ref_deletions >= 1


def test_begin_immediate_failure_propagates_original_error() -> None:
    """If BEGIN IMMEDIATE fails, the original error must propagate unchanged.

    A ROLLBACK on a non-active transaction previously raised a second
    OperationalError that masked the real error (e.g., 'database is locked').
    The fix tracks ``in_transaction`` so ROLLBACK is only called when BEGIN
    actually succeeded.
    """

    class _FailBeginDB(sqlite3.Connection):
        """Connection that raises on execute once armed; passes through otherwise."""

        _armed: bool = False

        def execute(self, sql: str, *args: object, **kwargs: object) -> sqlite3.Cursor:  # type: ignore[override]
            if self._armed:
                self._armed = False  # only fail once (BEGIN IMMEDIATE)
                raise sqlite3.OperationalError("database is locked")
            return super().execute(sql, *args, **kwargs)

    conn = _FailBeginDB(":memory:")
    conn.executescript(_SCHEMA_PATH.read_text())
    conn.executescript(_CRAWL_JOBS_PATH.read_text())
    conn.executescript(_SEASON_YEAR_PATH.read_text())
    # Insert teams via executescript to bypass the override entirely during setup
    conn.executescript(
        "INSERT INTO teams (name, membership_type) VALUES ('Canonical', 'tracked');"
        "INSERT INTO teams (name, membership_type) VALUES ('Duplicate', 'tracked');"
    )
    can = conn.execute("SELECT id FROM teams WHERE name = 'Canonical'").fetchone()[0]
    dup = conn.execute("SELECT id FROM teams WHERE name = 'Duplicate'").fetchone()[0]

    # Arm failure right before merge_teams; first execute call will be BEGIN IMMEDIATE
    conn._armed = True

    with pytest.raises(sqlite3.OperationalError, match="database is locked"):
        merge_teams(can, dup, conn)


def test_find_duplicates_multiple_groups() -> None:
    """Two independent duplicate groups are both returned."""
    conn = _make_db()
    a1 = _team_year(conn, "Lincoln East", season_year=2026)
    a2 = _team_year(conn, "Lincoln East", season_year=2026)
    b1 = _team_year(conn, "Millard North", season_year=2026)
    b2 = _team_year(conn, "Millard North", season_year=2026)
    # This team is unique -- should not appear in any group
    _team_year(conn, "Unique Team", season_year=2026)

    groups = find_duplicate_teams(conn)

    assert len(groups) == 2
    all_ids = {t.id for group in groups for t in group}
    assert all_ids == {a1, a2, b1, b2}
