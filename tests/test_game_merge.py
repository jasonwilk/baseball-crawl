"""Tests for src/db/game_merge.py (E-261-02).

``merge_duplicate_game`` merges a cross-perspective duplicate ``games`` row into
its canonical twin: every FK child of the losing row is re-pointed (perspectives
unioned) onto the canonical ``game_id`` and the losing ``games`` row is deleted
LAST. A non-disjoint pair (both rows carry data for the same perspective) is
REFUSED by pre-classification, leaving zero rows modified.

Covers:
- AC-1: disjoint twin across all six child tables (incl. play_events + spray)
  re-points cleanly; source games row deleted; no FK/UNIQUE violation.
- AC-2: same-perspective pair refuses; no rows modified; structured refusal.
- AC-3: caller-owned open transaction + foreign_keys=ON -> a mid-merge failure
  is rollback-able with no partial merge visible.
- AC-4: bare source (zero children) is deleted; canonical untouched.

All tests apply the FULL current migration set (through 011) via
``run_migrations`` against an on-disk SQLite database (needed so AC-3 can prove a
real, caller-owned transaction rolls back). No network calls.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from migrations.apply_migrations import run_migrations
from src.db.game_merge import (
    GameMergeError,
    is_offline_same_game,
    merge_duplicate_game,
)

_SEASON_ID = "2026"
_SOURCE = "dup-game-source"
_CANON = "dup-game-canonical"
_BATTER = "ba11e100-0001-0001-0001-000000000001"
_PITCHER = "01c4e100-0001-0001-0001-000000000001"

# Perspective convention for the twin: canonical was loaded from team 1's
# perspective, the duplicate source from team 2's -- disjoint, the genuine twin
# case.
_PERSP_CANON = 1
_PERSP_SOURCE = 2


# ---------------------------------------------------------------------------
# Fixtures + seed helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    """Apply all migrations (through 011) and seed seasons/teams/players/games."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    c = sqlite3.connect(str(db_path))
    c.execute("PRAGMA foreign_keys=ON;")

    c.execute(
        "INSERT INTO seasons (season_id, name, year) VALUES (?, ?, ?)",
        (_SEASON_ID, "Spring 2026 HS", 2026),
    )
    c.execute(
        "INSERT INTO teams (id, name, membership_type, is_active) "
        "VALUES (1, 'Home Team', 'member', 1)",
    )
    c.execute(
        "INSERT INTO teams (id, name, membership_type, is_active) "
        "VALUES (2, 'Away Team', 'tracked', 1)",
    )
    c.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (_BATTER, "Bat", "Ter"),
    )
    c.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (_PITCHER, "Pit", "Cher"),
    )
    for gid in (_SOURCE, _CANON):
        c.execute(
            "INSERT INTO games (game_id, season_id, game_date, home_team_id, "
            "away_team_id, status) VALUES (?, ?, '2026-04-10', 1, 2, 'completed')",
            (gid, _SEASON_ID),
        )
    c.commit()
    return c


def _seed_perspective(c: sqlite3.Connection, game_id: str, *, perspective: int) -> None:
    c.execute(
        "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?, ?)",
        (game_id, perspective),
    )


def _seed_batting(c: sqlite3.Connection, game_id: str, *, perspective: int) -> None:
    c.execute(
        "INSERT INTO player_game_batting (game_id, player_id, team_id, "
        "perspective_team_id, ab, h) VALUES (?, ?, ?, ?, 4, 2)",
        (game_id, _BATTER, perspective, perspective),
    )


def _seed_pitching(c: sqlite3.Connection, game_id: str, *, perspective: int) -> None:
    c.execute(
        "INSERT INTO player_game_pitching (game_id, player_id, team_id, "
        "perspective_team_id, ip_outs, so) VALUES (?, ?, ?, ?, 18, 7)",
        (game_id, _PITCHER, perspective, perspective),
    )


def _seed_play_with_event(
    c: sqlite3.Connection, game_id: str, *, perspective: int
) -> int:
    """Insert a plays row + one child play_events row. Returns the plays.id."""
    cur = c.execute(
        "INSERT INTO plays (game_id, play_order, inning, half, season_id, "
        "batting_team_id, perspective_team_id, batter_id, pitcher_id, outcome) "
        "VALUES (?, 0, 1, 'top', ?, ?, ?, ?, ?, 'Strikeout')",
        (game_id, _SEASON_ID, perspective, perspective, _BATTER, _PITCHER),
    )
    play_id = cur.lastrowid
    c.execute(
        "INSERT INTO play_events (play_id, event_order, event_type, pitch_result) "
        "VALUES (?, 0, 'pitch', 'strike_swinging')",
        (play_id,),
    )
    return play_id


def _seed_spray(c: sqlite3.Connection, game_id: str, *, perspective: int) -> None:
    c.execute(
        "INSERT INTO spray_charts (game_id, player_id, team_id, "
        "perspective_team_id, chart_type, event_gc_id) "
        "VALUES (?, ?, ?, ?, 'offensive', ?)",
        (game_id, _BATTER, perspective, perspective, f"evt-{game_id}-{perspective}"),
    )


def _seed_recon(c: sqlite3.Connection, game_id: str, *, perspective: int) -> None:
    c.execute(
        "INSERT INTO reconciliation_discrepancies (game_id, run_id, "
        "perspective_team_id, team_id, player_id, signal_name, category, status) "
        "VALUES (?, 'run-1', ?, ?, ?, 'so', 'batting', 'MATCH')",
        (game_id, perspective, perspective, _BATTER),
    )


def _seed_all_children(
    c: sqlite3.Connection, game_id: str, *, perspective: int
) -> int:
    """Seed one row in all six child tables (plus a play_events child)."""
    _seed_perspective(c, game_id, perspective=perspective)
    _seed_batting(c, game_id, perspective=perspective)
    _seed_pitching(c, game_id, perspective=perspective)
    play_id = _seed_play_with_event(c, game_id, perspective=perspective)
    _seed_spray(c, game_id, perspective=perspective)
    _seed_recon(c, game_id, perspective=perspective)
    return play_id


def _count(c: sqlite3.Connection, table: str, game_id: str) -> int:
    return c.execute(
        f"SELECT COUNT(*) FROM {table} WHERE game_id = ?",  # noqa: S608
        (game_id,),
    ).fetchone()[0]


# ---------------------------------------------------------------------------
# AC-1: disjoint twin re-points cleanly across all six child tables
# ---------------------------------------------------------------------------


def test_disjoint_twin_merges_all_children(conn: sqlite3.Connection) -> None:
    # Source loaded from perspective 2; canonical from perspective 1 (disjoint).
    source_play_id = _seed_all_children(conn, _SOURCE, perspective=_PERSP_SOURCE)
    # Canonical carries its own perspective-1 children so the perspective union
    # is exercised (game_perspectives ends up {1, 2}).
    _seed_perspective(conn, _CANON, perspective=_PERSP_CANON)
    _seed_batting(conn, _CANON, perspective=_PERSP_CANON)
    conn.commit()

    result = merge_duplicate_game(conn, _SOURCE, _CANON)

    assert result.merged is True
    assert result.refused is False
    # Every child row was re-pointed off the source.
    for table in (
        "game_perspectives",
        "player_game_batting",
        "player_game_pitching",
        "plays",
        "spray_charts",
        "reconciliation_discrepancies",
    ):
        assert _count(conn, table, _SOURCE) == 0, table
        assert _count(conn, table, _CANON) >= 1, table
        assert result.table_counts[table] >= 1, table

    # The source games row is gone; the canonical remains.
    assert conn.execute(
        "SELECT COUNT(*) FROM games WHERE game_id = ?", (_SOURCE,)
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM games WHERE game_id = ?", (_CANON,)
    ).fetchone()[0] == 1

    # Perspectives unioned onto the canonical game.
    persps = {
        row[0]
        for row in conn.execute(
            "SELECT perspective_team_id FROM game_perspectives WHERE game_id = ?",
            (_CANON,),
        )
    }
    assert persps == {_PERSP_CANON, _PERSP_SOURCE}

    # play_events followed their parent plays row (plays.id unchanged, now on C).
    followed = conn.execute(
        "SELECT p.game_id FROM play_events e JOIN plays p ON p.id = e.play_id "
        "WHERE e.play_id = ?",
        (source_play_id,),
    ).fetchone()
    assert followed is not None
    assert followed[0] == _CANON

    # FK integrity holds across the whole DB after the merge.
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


# ---------------------------------------------------------------------------
# AC-2: same-perspective pair refuses without modifying any row
# ---------------------------------------------------------------------------


def test_same_perspective_pair_refuses(conn: sqlite3.Connection) -> None:
    # BOTH rows carry batting for perspective 1 -- not a cleanly mergeable twin.
    _seed_perspective(conn, _SOURCE, perspective=_PERSP_CANON)
    _seed_batting(conn, _SOURCE, perspective=_PERSP_CANON)
    _seed_perspective(conn, _CANON, perspective=_PERSP_CANON)
    _seed_batting(conn, _CANON, perspective=_PERSP_CANON)
    conn.commit()

    result = merge_duplicate_game(conn, _SOURCE, _CANON)

    assert result.refused is True
    assert result.merged is False
    assert result.shared_perspectives == [_PERSP_CANON]
    assert result.refusal_reason and "perspective" in result.refusal_reason

    # Zero rows modified: both games and all their children are intact.
    assert conn.execute(
        "SELECT COUNT(*) FROM games WHERE game_id = ?", (_SOURCE,)
    ).fetchone()[0] == 1
    assert _count(conn, "player_game_batting", _SOURCE) == 1
    assert _count(conn, "player_game_batting", _CANON) == 1
    assert _count(conn, "game_perspectives", _SOURCE) == 1


def test_same_perspective_detected_even_without_game_perspectives_row(
    conn: sqlite3.Connection,
) -> None:
    # No game_perspectives rows on either side: the disjointness test must fall
    # back to the child-table perspectives (loose games/stat-row coupling).
    _seed_batting(conn, _SOURCE, perspective=_PERSP_CANON)
    _seed_pitching(conn, _CANON, perspective=_PERSP_CANON)
    conn.commit()

    result = merge_duplicate_game(conn, _SOURCE, _CANON)

    assert result.refused is True
    assert result.shared_perspectives == [_PERSP_CANON]
    assert _count(conn, "player_game_batting", _SOURCE) == 1


# ---------------------------------------------------------------------------
# AC-3: caller-owned transaction is rollback-able on a mid-merge failure
# ---------------------------------------------------------------------------


class _FailOnGamesDeleteConn:
    """Delegates to a real connection but raises on the final ``games`` DELETE.

    Simulates a mid-merge failure AFTER every child has been re-pointed, so the
    test can prove the caller's open transaction rolls the partial merge back.
    Because it forwards to the SAME underlying connection, the caller's
    BEGIN/ROLLBACK bracket the injected writes.
    """

    def __init__(self, real: sqlite3.Connection) -> None:
        self._real = real

    def execute(self, sql: str, params: object = ()):  # noqa: ANN001, ANN201
        if sql.strip().upper().startswith("DELETE FROM GAMES"):
            raise sqlite3.OperationalError("injected mid-merge failure")
        return self._real.execute(sql, params)


def test_midmerge_failure_is_rollbackable(conn: sqlite3.Connection) -> None:
    # Source carries a full child set; canonical has none, so every canonical
    # count below is 0 -- any non-zero would be an un-rolled-back partial merge.
    _seed_all_children(conn, _SOURCE, perspective=_PERSP_SOURCE)
    conn.commit()

    # PRECONDITION: FK on (set before BEGIN -- it is a no-op inside a txn) and an
    # explicit caller-owned open transaction.
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("BEGIN")

    with pytest.raises(sqlite3.OperationalError, match="injected mid-merge failure"):
        merge_duplicate_game(_FailOnGamesDeleteConn(conn), _SOURCE, _CANON)

    # Caller owns the boundary -- roll the partial merge back.
    conn.execute("ROLLBACK")

    # No partial merge visible: every source child is still on the source game
    # and the source games row still exists.
    for table in (
        "game_perspectives",
        "player_game_batting",
        "player_game_pitching",
        "plays",
        "spray_charts",
        "reconciliation_discrepancies",
    ):
        assert _count(conn, table, _SOURCE) == 1, table
        assert _count(conn, table, _CANON) == 0, table
    assert conn.execute(
        "SELECT COUNT(*) FROM games WHERE game_id = ?", (_SOURCE,)
    ).fetchone()[0] == 1


# ---------------------------------------------------------------------------
# AC-4: bare source (zero children) is deleted; canonical untouched
# ---------------------------------------------------------------------------


def test_bare_source_deleted_canonical_untouched(conn: sqlite3.Connection) -> None:
    # Source has NO children at all. Canonical carries a full set.
    _seed_all_children(conn, _CANON, perspective=_PERSP_CANON)
    conn.commit()

    result = merge_duplicate_game(conn, _SOURCE, _CANON)

    assert result.merged is True
    assert result.table_counts == {}  # nothing re-pointed

    assert conn.execute(
        "SELECT COUNT(*) FROM games WHERE game_id = ?", (_SOURCE,)
    ).fetchone()[0] == 0
    # Canonical and every one of its children are untouched.
    assert conn.execute(
        "SELECT COUNT(*) FROM games WHERE game_id = ?", (_CANON,)
    ).fetchone()[0] == 1
    for table in (
        "game_perspectives",
        "player_game_batting",
        "player_game_pitching",
        "plays",
        "spray_charts",
        "reconciliation_discrepancies",
    ):
        assert _count(conn, table, _CANON) == 1, table


# ---------------------------------------------------------------------------
# Validation guards (programming errors raise; not the AC-2 structured refusal)
# ---------------------------------------------------------------------------


def test_same_id_raises(conn: sqlite3.Connection) -> None:
    with pytest.raises(GameMergeError, match="must be different"):
        merge_duplicate_game(conn, _SOURCE, _SOURCE)


def test_missing_source_raises(conn: sqlite3.Connection) -> None:
    with pytest.raises(GameMergeError, match="Source game .* not found"):
        merge_duplicate_game(conn, "no-such-game", _CANON)


def test_missing_canonical_raises(conn: sqlite3.Connection) -> None:
    with pytest.raises(GameMergeError, match="Canonical game .* not found"):
        merge_duplicate_game(conn, _SOURCE, "no-such-game")


# ---------------------------------------------------------------------------
# E-261-03a AC-7: offline same-game predicate (pure, no DB)
# ---------------------------------------------------------------------------
#
# is_offline_same_game merges ONLY on: disjoint cross-perspective (PRIMARY) AND
# bounded score-tolerance AND near play-count -- ALL required. It excludes the
# live-only schedule-count gate. These unit tests construct it directly and pin
# each decision (E-261-04 verifies the actual import/reuse by the repair pass).


def test_offline_predicate_merges_disjoint_score_tolerant_near_playcount() -> None:
    """All three conditions hold: disjoint perspectives, 12-4 vs 12-5 (one side
    off by 1), near play counts -> same game."""
    assert is_offline_same_game(
        source_perspectives={2},
        canonical_perspectives={1},
        source_score=(12, 5),
        canonical_score=(12, 4),
        source_play_count=78,
        canonical_play_count=80,
    ) is True


def test_offline_predicate_merges_on_exact_score_and_equal_playcount() -> None:
    """Exact score agreement is the trivial score-tolerance pass."""
    assert is_offline_same_game(
        source_perspectives={2},
        canonical_perspectives={1},
        source_score=(7, 3),
        canonical_score=(7, 3),
        source_play_count=80,
        canonical_play_count=80,
    ) is True


def test_offline_predicate_refuses_overlapping_perspectives() -> None:
    """Shared perspective -> not a clean twin -> refuse (PRIMARY gate)."""
    assert is_offline_same_game(
        source_perspectives={1, 2},
        canonical_perspectives={1},
        source_score=(12, 5),
        canonical_score=(12, 4),
        source_play_count=80,
        canonical_play_count=80,
    ) is False


def test_offline_predicate_refuses_empty_perspectives() -> None:
    """An empty perspective set on either side is not a disjoint twin."""
    assert is_offline_same_game(
        source_perspectives=set(),
        canonical_perspectives={1},
        source_score=(7, 3),
        canonical_score=(7, 3),
        source_play_count=80,
        canonical_play_count=80,
    ) is False


def test_offline_predicate_refuses_score_out_of_tolerance() -> None:
    """Two runs apart on one side exceeds the <=1 tolerance -> refuse."""
    assert is_offline_same_game(
        source_perspectives={2},
        canonical_perspectives={1},
        source_score=(12, 6),  # away off by 2 from canonical 4
        canonical_score=(12, 4),
        source_play_count=80,
        canonical_play_count=80,
    ) is False


def test_offline_predicate_refuses_both_sides_off_by_one() -> None:
    """Bounded tolerance requires ONE side exact; both sides differing fails."""
    assert is_offline_same_game(
        source_perspectives={2},
        canonical_perspectives={1},
        source_score=(11, 5),  # both home and away differ from 12-4
        canonical_score=(12, 4),
        source_play_count=80,
        canonical_play_count=80,
    ) is False


def test_offline_predicate_refuses_null_score() -> None:
    """A NULL score cannot corroborate -> refuse even when disjoint + near."""
    assert is_offline_same_game(
        source_perspectives={2},
        canonical_perspectives={1},
        source_score=(12, None),
        canonical_score=(12, 4),
        source_play_count=80,
        canonical_play_count=80,
    ) is False


def test_offline_predicate_refuses_far_playcount() -> None:
    """Play counts too far apart fail the required corroboration (P1-2): a
    disjoint + score-tolerant pair must NOT merge on score alone."""
    assert is_offline_same_game(
        source_perspectives={2},
        canonical_perspectives={1},
        source_score=(12, 5),
        canonical_score=(12, 4),
        source_play_count=40,  # 40/80 = 0.5 < 0.85 ratio
        canonical_play_count=80,
    ) is False


def test_offline_predicate_refuses_zero_playcount() -> None:
    """Absent play data (0) cannot corroborate -> refuse (never merge on
    disjoint + score alone)."""
    assert is_offline_same_game(
        source_perspectives={2},
        canonical_perspectives={1},
        source_score=(12, 5),
        canonical_score=(12, 4),
        source_play_count=0,
        canonical_play_count=0,
    ) is False
