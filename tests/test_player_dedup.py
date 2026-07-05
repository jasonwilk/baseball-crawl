"""Tests for src.db.player_dedup -- duplicate player detection and merge."""

from __future__ import annotations

import logging
import sqlite3

import pytest

from src.db.player_dedup import (
    DuplicatePlayerPair,
    PlayerMergeError,
    _select_canonical_player,
    dedup_team_players,
    find_duplicate_players,
    merge_player_pair,
    plan_player_dedup,
    preview_player_merge,
    recompute_affected_seasons,
)
from tests.conftest import load_real_schema


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


# Placeholder team id used as away_team_id for dedup-test games. The dedup
# tests only care about player rows and single-team stats; the away team
# is a throwaway FK target that must exist so games.away_team_id FK passes.
_AWAY_PLACEHOLDER_TEAM_ID = 9999


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory database using the production schema (FK enforcement on)."""
    conn = sqlite3.connect(":memory:", isolation_level=None)
    load_real_schema(conn)
    # Seed a placeholder away team so _seed_game can satisfy away_team_id FK.
    conn.execute(
        "INSERT INTO teams (id, name, membership_type) VALUES (?, 'Away Placeholder', 'tracked')",
        (_AWAY_PLACEHOLDER_TEAM_ID,),
    )
    return conn


def _seed_team(db: sqlite3.Connection, team_id: int, name: str) -> None:
    db.execute(
        "INSERT INTO teams (id, name, membership_type) VALUES (?, ?, 'member')",
        (team_id, name),
    )


def _seed_season(db: sqlite3.Connection, season_id: str) -> None:
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) "
        "VALUES (?, ?, 2026)",
        (season_id, season_id),
    )


def _seed_player(
    db: sqlite3.Connection, player_id: str, first_name: str, last_name: str
) -> None:
    db.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (player_id, first_name, last_name),
    )


def _seed_roster(
    db: sqlite3.Connection, team_id: int, player_id: str, season_id: str
) -> None:
    _seed_season(db, season_id)
    db.execute(
        "INSERT INTO team_rosters (team_id, player_id, season_id) VALUES (?, ?, ?)",
        (team_id, player_id, season_id),
    )


def _seed_game(
    db: sqlite3.Connection, game_id: str, season_id: str, team_id: int
) -> None:
    _seed_season(db, season_id)
    db.execute(
        "INSERT OR IGNORE INTO games (game_id, season_id, game_date, home_team_id, away_team_id) "
        "VALUES (?, ?, '2026-04-01', ?, ?)",
        (game_id, season_id, team_id, _AWAY_PLACEHOLDER_TEAM_ID),
    )


def _seed_game_batting(
    db: sqlite3.Connection,
    game_id: str,
    player_id: str,
    team_id: int,
    *,
    stat_completeness: str = "boxscore_only",
    ab: int = 0,
    h: int = 0,
    bb: int = 0,
    hr: int = 0,
    r: int = 0,
    rbi: int = 0,
    so: int = 0,
    hbp: int = 0,
    shf: int = 0,
    perspective_team_id: int | None = None,
) -> None:
    ptid = perspective_team_id if perspective_team_id is not None else team_id
    db.execute(
        "INSERT INTO player_game_batting "
        "(game_id, player_id, team_id, perspective_team_id, stat_completeness, ab, h, bb, hr, r, rbi, so, hbp, shf) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_id, player_id, team_id, ptid, stat_completeness, ab, h, bb, hr, r, rbi, so, hbp, shf),
    )


def _seed_game_pitching(
    db: sqlite3.Connection,
    game_id: str,
    player_id: str,
    team_id: int,
    *,
    stat_completeness: str = "boxscore_only",
    ip_outs: int = 0,
    h: int = 0,
    er: int = 0,
    bb: int = 0,
    so: int = 0,
    r: int = 0,
    decision: str | None = None,
    perspective_team_id: int | None = None,
) -> None:
    ptid = perspective_team_id if perspective_team_id is not None else team_id
    db.execute(
        "INSERT INTO player_game_pitching "
        "(game_id, player_id, team_id, perspective_team_id, stat_completeness, ip_outs, h, r, er, bb, so, decision) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_id, player_id, team_id, ptid, stat_completeness, ip_outs, h, r, er, bb, so, decision),
    )


# ---------------------------------------------------------------------------
# AC-3: "O" / "Oliver" Holbein -> Oliver is canonical
# ---------------------------------------------------------------------------


class TestPrefixMatch:
    def test_holbein_o_oliver(self, db: sqlite3.Connection) -> None:
        """AC-3: Oliver Holbein is canonical over O Holbein."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-oliver", "Oliver", "Holbein")
        _seed_player(db, "p-o", "O", "Holbein")
        _seed_roster(db, 1, "p-oliver", "2026")
        _seed_roster(db, 1, "p-o", "2026")

        pairs = find_duplicate_players(db, season_id="2026")
        assert len(pairs) == 1
        assert pairs[0].canonical_player_id == "p-oliver"
        assert pairs[0].duplicate_player_id == "p-o"
        assert pairs[0].team_id == 1


# ---------------------------------------------------------------------------
# AC-4: Rob/Robert flagged; Mike/Mark not flagged
# ---------------------------------------------------------------------------


class TestPrefixVsNonPrefix:
    def test_rob_robert_flagged(self, db: sqlite3.Connection) -> None:
        """AC-4: Rob is a prefix of Robert -- should be flagged."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-robert", "Robert", "Smith")
        _seed_player(db, "p-rob", "Rob", "Smith")
        _seed_roster(db, 1, "p-robert", "2026")
        _seed_roster(db, 1, "p-rob", "2026")

        pairs = find_duplicate_players(db, season_id="2026")
        assert len(pairs) == 1
        assert pairs[0].canonical_player_id == "p-robert"
        assert pairs[0].duplicate_player_id == "p-rob"

    def test_mike_mark_not_flagged(self, db: sqlite3.Connection) -> None:
        """AC-4: Mike is NOT a prefix of Mark -- should not be flagged."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-mike", "Mike", "Smith")
        _seed_player(db, "p-mark", "Mark", "Smith")
        _seed_roster(db, 1, "p-mike", "2026")
        _seed_roster(db, 1, "p-mark", "2026")

        pairs = find_duplicate_players(db, season_id="2026")
        assert len(pairs) == 0


# ---------------------------------------------------------------------------
# AC-5: Different teams -> no match
# ---------------------------------------------------------------------------


class TestDifferentTeams:
    def test_same_name_different_teams(self, db: sqlite3.Connection) -> None:
        """AC-5: Same last_name, prefix first_name, but different teams."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_team(db, 2, "LSB JV")
        _seed_player(db, "p-oliver", "Oliver", "Holbein")
        _seed_player(db, "p-o", "O", "Holbein")
        _seed_roster(db, 1, "p-oliver", "2026")
        _seed_roster(db, 2, "p-o", "2026")

        pairs = find_duplicate_players(db, season_id="2026")
        assert len(pairs) == 0


# ---------------------------------------------------------------------------
# AC-2: Canonical selection tiebreaker logic
# ---------------------------------------------------------------------------


class TestCanonicalSelection:
    def test_longer_first_name_wins(self) -> None:
        """TN-3: Longer first_name is canonical."""
        c, d, cf, df = _select_canonical_player(
            "p-a", "Rob", "p-b", "Robert", {}
        )
        assert c == "p-b"  # Robert is longer
        assert d == "p-a"

    def test_equal_length_stat_count_wins(self) -> None:
        """TN-3: Equal length -> more stat rows wins."""
        stats = {"p-a": 10, "p-b": 5}
        c, d, cf, df = _select_canonical_player(
            "p-a", "Mike", "p-b", "Mark", stats
        )
        assert c == "p-a"  # More stat rows

    def test_equal_length_equal_stats_alphabetical(self) -> None:
        """TN-3: Equal length, equal stats -> alphabetical player_id wins."""
        stats = {"p-a": 5, "p-b": 5}
        c, d, cf, df = _select_canonical_player(
            "p-b", "Mike", "p-a", "Mark", stats
        )
        assert c == "p-a"  # Alphabetically first


# ---------------------------------------------------------------------------
# Scoping filters
# ---------------------------------------------------------------------------


class TestFilters:
    def test_team_id_filter(self, db: sqlite3.Connection) -> None:
        """Filtering by team_id scopes results."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_team(db, 2, "LSB JV")
        _seed_player(db, "p-oliver", "Oliver", "Holbein")
        _seed_player(db, "p-o", "O", "Holbein")
        _seed_player(db, "p-robert", "Robert", "Jones")
        _seed_player(db, "p-rob", "Rob", "Jones")
        _seed_roster(db, 1, "p-oliver", "2026")
        _seed_roster(db, 1, "p-o", "2026")
        _seed_roster(db, 2, "p-robert", "2026")
        _seed_roster(db, 2, "p-rob", "2026")

        pairs_t1 = find_duplicate_players(db, team_id=1, season_id="2026")
        assert len(pairs_t1) == 1
        assert pairs_t1[0].canonical_last_name == "Holbein"

        pairs_t2 = find_duplicate_players(db, team_id=2, season_id="2026")
        assert len(pairs_t2) == 1
        assert pairs_t2[0].canonical_last_name == "Jones"

    def test_season_id_filter(self, db: sqlite3.Connection) -> None:
        """Filtering by season_id scopes results."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-oliver", "Oliver", "Holbein")
        _seed_player(db, "p-o", "O", "Holbein")
        _seed_roster(db, 1, "p-oliver", "2025")
        _seed_roster(db, 1, "p-o", "2025")
        # Only on roster in 2025, not 2026

        pairs_2025 = find_duplicate_players(db, season_id="2025")
        assert len(pairs_2025) == 1

        pairs_2026 = find_duplicate_players(db, season_id="2026")
        assert len(pairs_2026) == 0


# ---------------------------------------------------------------------------
# Confidence indicator (AC-6)
# ---------------------------------------------------------------------------


class TestConfidenceIndicator:
    def test_overlapping_games_high_confidence(
        self, db: sqlite3.Connection
    ) -> None:
        """Pairs with overlapping game appearances are high confidence."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-oliver", "Oliver", "Holbein")
        _seed_player(db, "p-o", "O", "Holbein")
        _seed_roster(db, 1, "p-oliver", "2026")
        _seed_roster(db, 1, "p-o", "2026")
        # Both appear in the same game
        _seed_game(db, "game-1", "2026", 1)
        _seed_game_batting(db, "game-1", "p-oliver", 1)
        _seed_game_batting(db, "game-1", "p-o", 1)

        pairs = find_duplicate_players(db, season_id="2026")
        assert len(pairs) == 1
        assert pairs[0].has_overlapping_games is True

    def test_no_overlapping_games_low_confidence(
        self, db: sqlite3.Connection
    ) -> None:
        """Pairs with zero overlapping game appearances are low confidence."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-oliver", "Oliver", "Holbein")
        _seed_player(db, "p-o", "O", "Holbein")
        _seed_roster(db, 1, "p-oliver", "2026")
        _seed_roster(db, 1, "p-o", "2026")
        # Different games, no overlap
        _seed_game(db, "game-1", "2026", 1)
        _seed_game(db, "game-2", "2026", 1)
        _seed_game_batting(db, "game-1", "p-oliver", 1)
        _seed_game_batting(db, "game-2", "p-o", 1)

        pairs = find_duplicate_players(db, season_id="2026")
        assert len(pairs) == 1
        assert pairs[0].has_overlapping_games is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_first_name_not_matched(self, db: sqlite3.Connection) -> None:
        """Empty first_name must not match as prefix of everything."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-oliver", "Oliver", "Holbein")
        _seed_player(db, "p-empty", "", "Holbein")
        _seed_roster(db, 1, "p-oliver", "2026")
        _seed_roster(db, 1, "p-empty", "2026")

        pairs = find_duplicate_players(db, season_id="2026")
        assert len(pairs) == 0

    def test_case_insensitive_match(self, db: sqlite3.Connection) -> None:
        """Detection is case-insensitive for both first and last names."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-oliver", "OLIVER", "holbein")
        _seed_player(db, "p-o", "o", "HOLBEIN")
        _seed_roster(db, 1, "p-oliver", "2026")
        _seed_roster(db, 1, "p-o", "2026")

        pairs = find_duplicate_players(db, season_id="2026")
        assert len(pairs) == 1

    def test_no_players_returns_empty(self, db: sqlite3.Connection) -> None:
        """Empty database returns empty list."""
        pairs = find_duplicate_players(db, season_id="2026")
        assert pairs == []

    def test_exact_same_first_name_flagged(self, db: sqlite3.Connection) -> None:
        """Two players with identical first and last names are flagged
        (a name is a prefix of itself)."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-a", "Oliver", "Holbein")
        _seed_player(db, "p-b", "Oliver", "Holbein")
        _seed_roster(db, 1, "p-a", "2026")
        _seed_roster(db, 1, "p-b", "2026")

        pairs = find_duplicate_players(db, season_id="2026")
        assert len(pairs) == 1


# ===========================================================================
# Merge tests (E-215-03)
# ===========================================================================


def _count(db: sqlite3.Connection, table: str, col: str, val: str) -> int:
    """Count rows in table where col = val."""
    return db.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {col} = ?", (val,)  # noqa: S608
    ).fetchone()[0]


# ---------------------------------------------------------------------------
# AC-10: Full integration test -- rows in all 8 affected tables
# ---------------------------------------------------------------------------


class TestMergeIntegration:
    def test_full_merge_all_tables(self, db: sqlite3.Connection) -> None:
        """AC-10: Merge with rows in all 8 tables, including same-game conflicts."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-canonical", "Oliver", "Holbein")
        _seed_player(db, "p-dup", "O", "Holbein")
        _seed_roster(db, 1, "p-canonical", "2026")
        _seed_roster(db, 1, "p-dup", "2026")

        # Games
        _seed_game(db, "game-1", "2026", 1)
        _seed_game(db, "game-2", "2026", 1)
        _seed_game(db, "game-3", "2026", 1)

        # 1. player_game_batting -- game-1 has BOTH (same-game conflict)
        #    canonical has boxscore_only, duplicate has supplemented (better)
        _seed_game_batting(
            db, "game-1", "p-canonical", 1,
            stat_completeness="boxscore_only", ab=3, h=1, bb=0, r=0, rbi=1,
        )
        _seed_game_batting(
            db, "game-1", "p-dup", 1,
            stat_completeness="supplemented", ab=3, h=1, bb=0, r=0, rbi=1,
        )
        # game-2: only duplicate (no conflict, should be reassigned)
        _seed_game_batting(
            db, "game-2", "p-dup", 1,
            stat_completeness="boxscore_only", ab=4, h=2, bb=1, r=1, rbi=0,
        )
        # game-3: only canonical (no conflict)
        _seed_game_batting(
            db, "game-3", "p-canonical", 1,
            stat_completeness="boxscore_only", ab=3, h=0, bb=0, r=0, rbi=0,
        )

        # 2. player_game_pitching -- game-1 has BOTH (same-game conflict)
        #    both boxscore_only (tied) -> canonical wins
        _seed_game_pitching(
            db, "game-1", "p-canonical", 1,
            ip_outs=9, h=3, er=1, bb=1, so=5, r=2,
        )
        _seed_game_pitching(
            db, "game-1", "p-dup", 1,
            ip_outs=9, h=3, er=1, bb=1, so=5, r=2,
        )
        # game-2: only duplicate
        _seed_game_pitching(
            db, "game-2", "p-dup", 1,
            ip_outs=6, h=2, er=0, bb=0, so=3, r=0, decision="W",
        )

        # 3. player_season_batting -- both have rows (will be deleted for recomputation)
        db.execute(
            "INSERT INTO player_season_batting (player_id, team_id, season_id, gp, ab, h) "
            "VALUES ('p-canonical', 1, '2026', 5, 15, 3)"
        )
        db.execute(
            "INSERT INTO player_season_batting (player_id, team_id, season_id, gp, ab, h) "
            "VALUES ('p-dup', 1, '2026', 3, 10, 4)"
        )

        # 4. player_season_pitching -- both have rows
        db.execute(
            "INSERT INTO player_season_pitching (player_id, team_id, season_id, gp_pitcher, ip_outs) "
            "VALUES ('p-canonical', 1, '2026', 2, 18)"
        )
        db.execute(
            "INSERT INTO player_season_pitching (player_id, team_id, season_id, gp_pitcher, ip_outs) "
            "VALUES ('p-dup', 1, '2026', 1, 6)"
        )

        # 5. plays -- duplicate has rows as both batter and pitcher
        db.execute(
            "INSERT INTO plays (game_id, play_order, inning, half, season_id, batting_team_id, perspective_team_id, batter_id, pitcher_id) "
            "VALUES ('game-1', 1, 1, 'top', '2026', 1, 1, 'p-dup', 'p-canonical')"
        )
        db.execute(
            "INSERT INTO plays (game_id, play_order, inning, half, season_id, batting_team_id, perspective_team_id, batter_id, pitcher_id) "
            "VALUES ('game-2', 1, 1, 'top', '2026', 1, 1, 'p-canonical', 'p-dup')"
        )

        # 6. spray_charts -- duplicate as both player and pitcher
        db.execute(
            "INSERT INTO spray_charts (game_id, player_id, team_id, perspective_team_id, pitcher_id) "
            "VALUES ('game-1', 'p-dup', 1, 1, 'p-canonical')"
        )
        db.execute(
            "INSERT INTO spray_charts (game_id, player_id, team_id, perspective_team_id, pitcher_id) "
            "VALUES ('game-2', 'p-canonical', 1, 1, 'p-dup')"
        )

        # 7. reconciliation_discrepancies -- both have rows + a __game__ sentinel
        db.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(game_id, run_id, perspective_team_id, team_id, player_id, signal_name, category, status) "
            "VALUES ('game-1', 'run-1', 1, 1, 'p-dup', 'ab', 'batter', 'MATCH')"
        )
        db.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(game_id, run_id, perspective_team_id, team_id, player_id, signal_name, category, status) "
            "VALUES ('game-1', 'run-1', 1, 1, '__game__', 'total_r', 'game', 'MATCH')"
        )

        # --- Execute merge ---
        affected = merge_player_pair(db, "p-canonical", "p-dup")

        # (a) All rows reference canonical
        assert _count(db, "plays", "batter_id", "p-canonical") == 2
        assert _count(db, "plays", "pitcher_id", "p-canonical") == 2
        assert _count(db, "spray_charts", "player_id", "p-canonical") == 2
        assert _count(db, "spray_charts", "pitcher_id", "p-canonical") == 2
        assert _count(db, "team_rosters", "player_id", "p-canonical") == 1
        assert _count(db, "reconciliation_discrepancies", "player_id", "p-canonical") == 1

        # (b) No rows reference duplicate
        for table in (
            "plays", "spray_charts", "player_game_batting",
            "player_game_pitching", "team_rosters",
        ):
            assert _count(db, table, "player_id" if table != "plays" else "batter_id", "p-dup") == 0
        assert _count(db, "reconciliation_discrepancies", "player_id", "p-dup") == 0

        # (c) Game batting: game-1 conflict -> dup's supplemented row kept (better completeness)
        #     game-2 reassigned, game-3 canonical kept
        batting_rows = db.execute(
            "SELECT game_id, stat_completeness, ab, h FROM player_game_batting "
            "WHERE player_id = 'p-canonical' ORDER BY game_id"
        ).fetchall()
        assert len(batting_rows) == 3
        # game-1: duplicate's supplemented row was kept
        assert batting_rows[0] == ("game-1", "supplemented", 3, 1)
        # game-2: reassigned from duplicate
        assert batting_rows[1] == ("game-2", "boxscore_only", 4, 2)
        # game-3: canonical's original
        assert batting_rows[2] == ("game-3", "boxscore_only", 3, 0)

        # (c) Game pitching: game-1 conflict -> both boxscore_only, canonical wins
        #     game-2 reassigned
        pitching_rows = db.execute(
            "SELECT game_id, ip_outs FROM player_game_pitching "
            "WHERE player_id = 'p-canonical' ORDER BY game_id"
        ).fetchall()
        assert len(pitching_rows) == 2
        assert pitching_rows[0] == ("game-1", 9)
        assert pitching_rows[1] == ("game-2", 6)

        # (d) Duplicate player row deleted
        assert db.execute(
            "SELECT COUNT(*) FROM players WHERE player_id = 'p-dup'"
        ).fetchone()[0] == 0

        # (e) Canonical player still exists with best name
        canonical = db.execute(
            "SELECT first_name, last_name FROM players WHERE player_id = 'p-canonical'"
        ).fetchone()
        assert canonical == ("Oliver", "Holbein")

        # (e) Post-merge stat values are from kept rows, not summed
        #     Batting PA from game-level: game-1 (ab=3), game-2 (ab=4, bb=1), game-3 (ab=3)
        #     = 3+0 + 4+1 + 3+0 = 11 PA total (from recomputation)

        # __game__ sentinel preserved
        assert db.execute(
            "SELECT COUNT(*) FROM reconciliation_discrepancies WHERE player_id = '__game__'"
        ).fetchone()[0] == 1

        # Verify affected seasons returned for recomputation
        assert ("p-canonical", 1, "2026") in affected

        # Season rows were deleted during merge
        assert _count(db, "player_season_batting", "player_id", "p-canonical") == 0
        assert _count(db, "player_season_pitching", "player_id", "p-canonical") == 0


# ---------------------------------------------------------------------------
# AC-2 (merge context): stat_completeness conflict resolution
# ---------------------------------------------------------------------------


class TestStatCompletenessConflict:
    def test_better_completeness_wins(self, db: sqlite3.Connection) -> None:
        """AC-2: Row with better stat_completeness is kept in game-level conflict."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-can", "Oliver", "Test")
        _seed_player(db, "p-dup", "O", "Test")
        _seed_roster(db, 1, "p-can", "2026")
        _seed_roster(db, 1, "p-dup", "2026")
        _seed_game(db, "g1", "2026", 1)

        # Canonical has boxscore_only, duplicate has full -> duplicate row kept
        _seed_game_batting(db, "g1", "p-can", 1, stat_completeness="boxscore_only", ab=3, h=1)
        _seed_game_batting(db, "g1", "p-dup", 1, stat_completeness="full", ab=4, h=2)

        merge_player_pair(db, "p-can", "p-dup")

        row = db.execute(
            "SELECT stat_completeness, ab, h FROM player_game_batting WHERE player_id = 'p-can'"
        ).fetchone()
        assert row == ("full", 4, 2)

    def test_tied_completeness_canonical_wins(self, db: sqlite3.Connection) -> None:
        """AC-2: When stat_completeness is tied, canonical row is kept."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-can", "Oliver", "Test")
        _seed_player(db, "p-dup", "O", "Test")
        _seed_roster(db, 1, "p-can", "2026")
        _seed_roster(db, 1, "p-dup", "2026")
        _seed_game(db, "g1", "2026", 1)

        _seed_game_batting(db, "g1", "p-can", 1, stat_completeness="boxscore_only", ab=3, h=1)
        _seed_game_batting(db, "g1", "p-dup", 1, stat_completeness="boxscore_only", ab=4, h=2)

        merge_player_pair(db, "p-can", "p-dup")

        row = db.execute(
            "SELECT ab, h FROM player_game_batting WHERE player_id = 'p-can'"
        ).fetchone()
        # Canonical's values kept
        assert row == (3, 1)


# ---------------------------------------------------------------------------
# AC-7: Rollback on failure
# ---------------------------------------------------------------------------


class TestMergeRollback:
    def test_invalid_ids_raise_error(self, db: sqlite3.Connection) -> None:
        """AC-7: Same canonical and duplicate raises PlayerMergeError."""
        with pytest.raises(PlayerMergeError, match="must be different"):
            merge_player_pair(db, "p-a", "p-a")

    def test_missing_canonical_raises_error(self, db: sqlite3.Connection) -> None:
        """AC-7: Missing canonical player raises PlayerMergeError."""
        _seed_player(db, "p-dup", "O", "Test")
        with pytest.raises(PlayerMergeError, match="not found"):
            merge_player_pair(db, "p-nonexistent", "p-dup")

    def test_missing_duplicate_raises_error(self, db: sqlite3.Connection) -> None:
        """AC-7: Missing duplicate player raises PlayerMergeError."""
        _seed_player(db, "p-can", "Oliver", "Test")
        with pytest.raises(PlayerMergeError, match="not found"):
            merge_player_pair(db, "p-can", "p-nonexistent")


# ---------------------------------------------------------------------------
# AC-3 (plays and spray_charts): simple UPDATE
# ---------------------------------------------------------------------------


class TestSimpleUpdateTables:
    def test_plays_batter_and_pitcher_updated(self, db: sqlite3.Connection) -> None:
        """AC-3: plays.batter_id and plays.pitcher_id both updated."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-can", "Oliver", "Test")
        _seed_player(db, "p-dup", "O", "Test")
        _seed_player(db, "p-other", "Jane", "Other")
        _seed_roster(db, 1, "p-can", "2026")
        _seed_roster(db, 1, "p-dup", "2026")
        _seed_game(db, "g1", "2026", 1)

        db.execute("INSERT INTO plays (game_id, play_order, inning, half, season_id, batting_team_id, perspective_team_id, batter_id, pitcher_id) VALUES ('g1', 1, 1, 'top', '2026', 1, 1, 'p-dup', 'p-other')")
        db.execute("INSERT INTO plays (game_id, play_order, inning, half, season_id, batting_team_id, perspective_team_id, batter_id, pitcher_id) VALUES ('g1', 2, 1, 'top', '2026', 1, 1, 'p-other', 'p-dup')")

        merge_player_pair(db, "p-can", "p-dup")

        assert _count(db, "plays", "batter_id", "p-can") == 1
        assert _count(db, "plays", "pitcher_id", "p-can") == 1
        assert _count(db, "plays", "batter_id", "p-dup") == 0
        assert _count(db, "plays", "pitcher_id", "p-dup") == 0

    def test_spray_charts_player_and_pitcher_updated(self, db: sqlite3.Connection) -> None:
        """AC-3: spray_charts.player_id and spray_charts.pitcher_id both updated."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-can", "Oliver", "Test")
        _seed_player(db, "p-dup", "O", "Test")
        _seed_roster(db, 1, "p-can", "2026")
        _seed_roster(db, 1, "p-dup", "2026")
        _seed_game(db, "g1", "2026", 1)

        db.execute(
            "INSERT INTO spray_charts (game_id, player_id, team_id, perspective_team_id, pitcher_id) "
            "VALUES ('g1', 'p-dup', 1, 1, NULL)"
        )
        db.execute(
            "INSERT INTO spray_charts (game_id, player_id, team_id, perspective_team_id, pitcher_id) "
            "VALUES ('g1', 'p-can', 1, 1, 'p-dup')"
        )

        merge_player_pair(db, "p-can", "p-dup")

        assert _count(db, "spray_charts", "player_id", "p-dup") == 0
        assert _count(db, "spray_charts", "pitcher_id", "p-dup") == 0
        assert _count(db, "spray_charts", "player_id", "p-can") == 2


# ---------------------------------------------------------------------------
# AC-5 + AC-4: Duplicate player row deleted
# ---------------------------------------------------------------------------


class TestDuplicateDeleted:
    def test_duplicate_player_row_deleted(self, db: sqlite3.Connection) -> None:
        """AC-5: After merge, duplicate player_id row is gone from players table."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-can", "Oliver", "Test")
        _seed_player(db, "p-dup", "O", "Test")
        _seed_roster(db, 1, "p-can", "2026")
        _seed_roster(db, 1, "p-dup", "2026")

        merge_player_pair(db, "p-can", "p-dup")

        assert db.execute(
            "SELECT COUNT(*) FROM players WHERE player_id = 'p-dup'"
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM players WHERE player_id = 'p-can'"
        ).fetchone()[0] == 1


# ---------------------------------------------------------------------------
# AC-6: ensure_player_row name preference
# ---------------------------------------------------------------------------


class TestNamePreference:
    def test_canonical_gets_best_name(self, db: sqlite3.Connection) -> None:
        """AC-6: After merge, canonical has the longer name from duplicate."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-can", "O", "Holbein")
        _seed_player(db, "p-dup", "Oliver", "Holbein")
        _seed_roster(db, 1, "p-can", "2026")
        _seed_roster(db, 1, "p-dup", "2026")

        # Even though p-can is canonical by ID, the merge should pick up
        # the longer name "Oliver" from the duplicate via ensure_player_row
        merge_player_pair(db, "p-can", "p-dup")

        row = db.execute(
            "SELECT first_name FROM players WHERE player_id = 'p-can'"
        ).fetchone()
        assert row[0] == "Oliver"


# ---------------------------------------------------------------------------
# AC-9: Season recomputation
# ---------------------------------------------------------------------------


class TestSeasonRecomputation:
    def test_batting_recomputation(self, db: sqlite3.Connection) -> None:
        """AC-9: Season batting stats recomputed from game-level data."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-can", "Oliver", "Test")
        _seed_game(db, "g1", "2026", 1)
        _seed_game(db, "g2", "2026", 1)

        _seed_game_batting(db, "g1", "p-can", 1, ab=4, h=2, bb=1, hr=1, r=1, rbi=2)
        _seed_game_batting(db, "g2", "p-can", 1, ab=3, h=1, bb=0, hr=0, r=0, rbi=0)

        recompute_affected_seasons(db, {("p-can", 1, "2026")})

        row = db.execute(
            "SELECT games_tracked, gp, pa, ab, h, hr, rbi, bb FROM player_season_batting "
            "WHERE player_id = 'p-can' AND team_id = 1 AND season_id = '2026'"
        ).fetchone()
        assert row is not None
        games_tracked, gp, pa, ab, h, hr, rbi, bb = row
        assert games_tracked == 2
        assert gp == 2
        assert ab == 7  # 4 + 3
        assert h == 3   # 2 + 1
        assert hr == 1
        assert rbi == 2
        assert bb == 1
        assert pa == 8  # ab(7) + bb(1) + hbp(0) + shf(0)

    def test_pitching_recomputation(self, db: sqlite3.Connection) -> None:
        """AC-9: Season pitching stats recomputed from game-level data."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-can", "Oliver", "Test")
        _seed_game(db, "g1", "2026", 1)
        _seed_game(db, "g2", "2026", 1)

        _seed_game_pitching(db, "g1", "p-can", 1, ip_outs=9, h=3, er=1, bb=1, so=5, r=2)
        _seed_game_pitching(db, "g2", "p-can", 1, ip_outs=6, h=2, er=0, bb=0, so=3, r=0, decision="W")

        recompute_affected_seasons(db, {("p-can", 1, "2026")})

        row = db.execute(
            "SELECT games_tracked, gp_pitcher, ip_outs, h, er, bb, so, w "
            "FROM player_season_pitching "
            "WHERE player_id = 'p-can' AND team_id = 1 AND season_id = '2026'"
        ).fetchone()
        assert row is not None
        games_tracked, gp_pitcher, ip_outs, h, er, bb, so, w = row
        assert games_tracked == 2
        assert gp_pitcher == 2
        assert ip_outs == 15  # 9 + 6
        assert h == 5         # 3 + 2
        assert er == 1
        assert so == 8        # 5 + 3
        assert w == 1

    def test_no_game_data_no_season_row(self, db: sqlite3.Connection) -> None:
        """AC-9: No game-level data -> no season row created."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-can", "Oliver", "Test")
        _seed_season(db, "2026")

        recompute_affected_seasons(db, {("p-can", 1, "2026")})
        assert _count(db, "player_season_batting", "player_id", "p-can") == 0

    def test_recompute_affected_seasons(self, db: sqlite3.Connection) -> None:
        """AC-9: recompute_affected_seasons processes all tuples."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-can", "Oliver", "Test")
        _seed_game(db, "g1", "2026", 1)
        _seed_game_batting(db, "g1", "p-can", 1, ab=4, h=2)
        _seed_game_pitching(db, "g1", "p-can", 1, ip_outs=9, so=5)

        affected = {("p-can", 1, "2026")}
        recompute_affected_seasons(db, affected)

        assert _count(db, "player_season_batting", "player_id", "p-can") == 1
        assert _count(db, "player_season_pitching", "player_id", "p-can") == 1


# ---------------------------------------------------------------------------
# Preview (AC-11)
# ---------------------------------------------------------------------------


class TestPreview:
    def test_preview_shows_table_counts(self, db: sqlite3.Connection) -> None:
        """AC-11: Preview shows per-table row counts without modifying data."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-can", "Oliver", "Test")
        _seed_player(db, "p-dup", "O", "Test")
        _seed_roster(db, 1, "p-can", "2026")
        _seed_roster(db, 1, "p-dup", "2026")
        _seed_game(db, "g1", "2026", 1)
        _seed_game_batting(db, "g1", "p-dup", 1, ab=3, h=1)

        preview = preview_player_merge(db, "p-can", "p-dup")

        assert preview.canonical_player_id == "p-can"
        assert preview.duplicate_player_id == "p-dup"
        assert preview.table_counts.get("player_game_batting") == 1
        assert preview.table_counts.get("team_rosters") == 1

        # Data was NOT modified
        assert _count(db, "player_game_batting", "player_id", "p-dup") == 1

    def test_sentinel_not_counted(self, db: sqlite3.Connection) -> None:
        """AC-11: __game__ sentinel rows are not counted in preview."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-can", "Oliver", "Test")
        _seed_player(db, "p-dup", "O", "Test")
        _seed_roster(db, 1, "p-can", "2026")
        _seed_roster(db, 1, "p-dup", "2026")

        _seed_game(db, "g1", "2026", 1)
        db.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(game_id, run_id, perspective_team_id, team_id, player_id, signal_name, category, status) "
            "VALUES ('g1', 'run-1', 1, 1, '__game__', 'total_r', 'game', 'MATCH')"
        )

        preview = preview_player_merge(db, "p-can", "p-dup")
        assert "reconciliation_discrepancies" not in preview.table_counts


# ---------------------------------------------------------------------------
# Savepoint mode (manage_transaction=False)
# ---------------------------------------------------------------------------


class TestSavepointMode:
    def test_savepoint_mode_within_caller_transaction(
        self, db: sqlite3.Connection
    ) -> None:
        """AC-1: manage_transaction=False uses SAVEPOINT inside caller's transaction."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-can", "Oliver", "Test")
        _seed_player(db, "p-dup", "O", "Test")
        _seed_roster(db, 1, "p-can", "2026")
        _seed_roster(db, 1, "p-dup", "2026")

        # Caller manages the transaction
        db.execute("BEGIN")
        merge_player_pair(db, "p-can", "p-dup", manage_transaction=False)
        db.execute("COMMIT")

        assert db.execute(
            "SELECT COUNT(*) FROM players WHERE player_id = 'p-dup'"
        ).fetchone()[0] == 0


# ---------------------------------------------------------------------------
# E-215-04: dedup_team_players() -- scoped auto-dedup
# ---------------------------------------------------------------------------


class TestDedupTeamPlayers:
    """Tests for the dedup_team_players() function (E-215-04)."""

    def test_merges_detected_pair_and_returns_count(
        self, db: sqlite3.Connection
    ) -> None:
        """AC-8: simulates a scouting load producing a duplicate pair and verifies
        that dedup_team_players merges it automatically."""
        from src.db.player_dedup import dedup_team_players

        _seed_team(db, 1, "LSB Varsity")

        # Roster perspective: player appears as "O Test"
        _seed_player(db, "p-short", "O", "Test")
        _seed_roster(db, 1, "p-short", "2026")

        # Boxscore perspective: same player appears as "Oliver Test"
        _seed_player(db, "p-full", "Oliver", "Test")
        _seed_roster(db, 1, "p-full", "2026")

        # Both have game stats
        _seed_game(db, "g1", "2026", 1)
        _seed_game_batting(db, "g1", "p-short", 1, ab=3, h=1)
        _seed_game(db, "g2", "2026", 1)
        _seed_game_batting(db, "g2", "p-full", 1, ab=4, h=2)

        merged = dedup_team_players(db, 1, "2026", manage_transaction=True)

        assert merged == 1

        # Canonical player (longer first_name = "Oliver") should remain
        assert db.execute(
            "SELECT COUNT(*) FROM players WHERE player_id = 'p-full'"
        ).fetchone()[0] == 1

        # Duplicate should be gone
        assert db.execute(
            "SELECT COUNT(*) FROM players WHERE player_id = 'p-short'"
        ).fetchone()[0] == 0

        # Both game batting rows should now belong to canonical
        batting_rows = db.execute(
            "SELECT player_id FROM player_game_batting ORDER BY game_id"
        ).fetchall()
        assert all(row[0] == "p-full" for row in batting_rows)
        assert len(batting_rows) == 2

    def test_returns_zero_when_no_duplicates(
        self, db: sqlite3.Connection
    ) -> None:
        """dedup_team_players returns 0 and logs when no duplicates found."""
        from src.db.player_dedup import dedup_team_players

        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p1", "Alice", "Smith")
        _seed_player(db, "p2", "Bob", "Jones")
        _seed_roster(db, 1, "p1", "2026")
        _seed_roster(db, 1, "p2", "2026")

        merged = dedup_team_players(db, 1, "2026", manage_transaction=True)
        assert merged == 0

    def test_scoped_to_team_and_season(
        self, db: sqlite3.Connection
    ) -> None:
        """dedup_team_players only merges within the specified (team, season)."""
        from src.db.player_dedup import dedup_team_players

        _seed_team(db, 1, "LSB Varsity")
        _seed_team(db, 2, "Other Team")

        # Duplicate pair on team 2
        _seed_player(db, "p-can", "Oliver", "Test")
        _seed_player(db, "p-dup", "O", "Test")
        _seed_roster(db, 2, "p-can", "2026")
        _seed_roster(db, 2, "p-dup", "2026")

        # Dedup team 1 -- should find nothing
        merged = dedup_team_players(db, 1, "2026", manage_transaction=True)
        assert merged == 0

        # Both players still exist
        assert db.execute(
            "SELECT COUNT(*) FROM players"
        ).fetchone()[0] == 2

    def test_continues_on_individual_pair_failure(
        self, db: sqlite3.Connection
    ) -> None:
        """AC-7: if one pair fails to merge, others still succeed."""
        from unittest.mock import patch

        from src.db.player_dedup import dedup_team_players

        _seed_team(db, 1, "LSB Varsity")

        # Pair 1: will succeed
        _seed_player(db, "p-a-full", "Alice", "Smith")
        _seed_player(db, "p-a-short", "A", "Smith")
        _seed_roster(db, 1, "p-a-full", "2026")
        _seed_roster(db, 1, "p-a-short", "2026")

        # Pair 2: will succeed
        _seed_player(db, "p-b-full", "Bobby", "Jones")
        _seed_player(db, "p-b-short", "B", "Jones")
        _seed_roster(db, 1, "p-b-full", "2026")
        _seed_roster(db, 1, "p-b-short", "2026")

        original_merge = merge_player_pair

        call_count = 0

        def failing_merge(db, canonical, duplicate, *, manage_transaction=True):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Simulated merge failure")
            return original_merge(
                db, canonical, duplicate, manage_transaction=manage_transaction
            )

        with patch("src.db.player_dedup.merge_player_pair", side_effect=failing_merge):
            merged = dedup_team_players(db, 1, "2026", manage_transaction=True)

        # One pair failed, one succeeded
        assert merged == 1

    def test_manage_transaction_false_uses_savepoint(
        self, db: sqlite3.Connection
    ) -> None:
        """Hook 1 scenario: manage_transaction=False works within caller transaction."""
        from src.db.player_dedup import dedup_team_players

        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-can", "Oliver", "Test")
        _seed_player(db, "p-dup", "O", "Test")
        _seed_roster(db, 1, "p-can", "2026")
        _seed_roster(db, 1, "p-dup", "2026")

        db.execute("BEGIN")
        merged = dedup_team_players(db, 1, "2026", manage_transaction=False)
        db.execute("COMMIT")

        assert merged == 1
        assert db.execute(
            "SELECT COUNT(*) FROM players WHERE player_id = 'p-dup'"
        ).fetchone()[0] == 0

    def test_recomputes_season_aggregates_after_merge(
        self, db: sqlite3.Connection
    ) -> None:
        """Verifies season aggregates are recomputed after dedup."""
        from src.db.player_dedup import dedup_team_players

        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-full", "Oliver", "Test")
        _seed_player(db, "p-short", "O", "Test")
        _seed_roster(db, 1, "p-full", "2026")
        _seed_roster(db, 1, "p-short", "2026")

        _seed_game(db, "g1", "2026", 1)
        _seed_game(db, "g2", "2026", 1)
        _seed_game_batting(db, "g1", "p-full", 1, ab=3, h=1)
        _seed_game_batting(db, "g2", "p-short", 1, ab=4, h=2)

        dedup_team_players(db, 1, "2026", manage_transaction=True)

        # Season aggregate should combine both games' stats
        row = db.execute(
            "SELECT ab, h FROM player_season_batting "
            "WHERE player_id = 'p-full' AND team_id = 1 AND season_id = '2026'"
        ).fetchone()
        assert row is not None
        assert row[0] == 7  # 3 + 4
        assert row[1] == 3  # 1 + 2



# ---------------------------------------------------------------------------
# E-220 regression: cross-perspective season recompute must not double-count
# ---------------------------------------------------------------------------


class TestRecomputePerspectiveFiltering:
    """Verify recompute_affected_seasons filters by perspective_team_id.

    After E-220, the same (game_id, player_id, team_id) can have multiple
    rows in player_game_batting/pitching distinguished by perspective_team_id
    (one per perspective the game was loaded from).  The canonical recompute
    must filter to the team's own perspective only, otherwise season totals
    are inflated.
    """

    def test_batting_recompute_excludes_other_perspectives(
        self, db: sqlite3.Connection
    ) -> None:
        _seed_team(db, 1, "LSB Varsity")
        _seed_team(db, 2, "Opponent")
        _seed_player(db, "p-x", "Xander", "Test")
        _seed_roster(db, 1, "p-x", "2026")
        _seed_game(db, "g-1", "2026", 1)

        # Own perspective row (team_id == perspective_team_id)
        db.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id, ab, h, hr, rbi, r, bb, so) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("g-1", "p-x", 1, 1, 4, 2, 1, 3, 1, 0, 1),
        )
        # Cross-perspective row from opponent (same team_id, different perspective)
        db.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id, ab, h, hr, rbi, r, bb, so) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("g-1", "p-x", 1, 2, 4, 2, 1, 3, 1, 0, 1),
        )

        recompute_affected_seasons(db, {("p-x", 1, "2026")})

        row = db.execute(
            "SELECT games_tracked, ab, h, hr, rbi FROM player_season_batting "
            "WHERE player_id = 'p-x' AND team_id = 1 AND season_id = '2026'"
        ).fetchone()
        assert row is not None, "season row should be created"
        # Must reflect ONE perspective only -- not 2x.
        assert row[0] == 1, f"games_tracked should be 1 (own perspective), got {row[0]}"
        assert row[1] == 4, f"ab should be 4, got {row[1]}"
        assert row[2] == 2, f"h should be 2, got {row[2]}"
        assert row[3] == 1, f"hr should be 1, got {row[3]}"
        assert row[4] == 3, f"rbi should be 3, got {row[4]}"

    def test_pitching_recompute_excludes_other_perspectives(
        self, db: sqlite3.Connection
    ) -> None:
        _seed_team(db, 1, "LSB Varsity")
        _seed_team(db, 2, "Opponent")
        _seed_player(db, "p-y", "Yancy", "Pitcher")
        _seed_roster(db, 1, "p-y", "2026")
        _seed_game(db, "g-2", "2026", 1)

        db.execute(
            "INSERT INTO player_game_pitching "
            "(game_id, player_id, team_id, perspective_team_id, ip_outs, h, r, er, bb, so, pitches, total_strikes, bf) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("g-2", "p-y", 1, 1, 18, 4, 2, 2, 1, 6, 85, 55, 24),
        )
        db.execute(
            "INSERT INTO player_game_pitching "
            "(game_id, player_id, team_id, perspective_team_id, ip_outs, h, r, er, bb, so, pitches, total_strikes, bf) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("g-2", "p-y", 1, 2, 18, 4, 2, 2, 1, 6, 85, 55, 24),
        )

        recompute_affected_seasons(db, {("p-y", 1, "2026")})

        row = db.execute(
            "SELECT games_tracked, ip_outs, pitches, so, bb FROM player_season_pitching "
            "WHERE player_id = 'p-y' AND team_id = 1 AND season_id = '2026'"
        ).fetchone()
        assert row is not None
        assert row[0] == 1, f"games_tracked should be 1, got {row[0]}"
        assert row[1] == 18, f"ip_outs should be 18, got {row[1]}"
        assert row[2] == 85, f"pitches should be 85, got {row[2]}"
        assert row[3] == 6
        assert row[4] == 1


# ---------------------------------------------------------------------------
# E-237-03: canonical recompute -- determinism + member-row provenance guard
# ---------------------------------------------------------------------------


class TestCanonicalRecomputeConsolidation:
    """E-237-03: one canonical boxscore_only recompute (Option B superset).

    Pins the two behaviours the consolidation guarantees:
    * AC-2 -- a *merged* player and a *non-merged* player in the same scope get
      the IDENTICAL deterministic superset column population (no hybrid row).
    * AC-8 -- a member-provenance ``full`` season row SURVIVES a dedup/recompute
      on its scope (neither deleted nor overwritten), fixing the latent
      data-loss the prior unconditional dedup DELETE+INSERT had.
    """

    def test_merged_and_unmerged_get_same_superset_columns(
        self, db: sqlite3.Connection
    ) -> None:
        """AC-2: superset columns are populated identically for merged + non-merged.

        Player ``p-oliver`` absorbs a merged duplicate (``p-o``); player
        ``p-zach`` is never merged.  After dedup runs the canonical recompute
        for the whole (team, season) scope, BOTH players' rows must carry the
        dedup-derived extras (batting pa/singles/xbh; pitching w/l/sv) AND the
        ScoutingLoader subset (gs) -- no NULL hybrid row for either.
        """
        from src.db.player_dedup import dedup_team_players

        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-oliver", "Oliver", "Test")
        _seed_player(db, "p-o", "O", "Test")  # prefix duplicate -> merges
        _seed_player(db, "p-zach", "Zach", "Test")  # no duplicate -> not merged
        for pid in ("p-oliver", "p-o", "p-zach"):
            _seed_roster(db, 1, pid, "2026")
        _seed_game(db, "g1", "2026", 1)
        _seed_game(db, "g2", "2026", 1)

        # Merged player: batting + a 'W' start across two games.
        _seed_game_batting(db, "g1", "p-oliver", 1, ab=3, h=2, bb=1)
        _seed_game_batting(db, "g2", "p-o", 1, ab=2, h=1)
        db.execute(
            "INSERT INTO player_game_pitching "
            "(game_id, player_id, team_id, perspective_team_id, ip_outs, decision, appearance_order) "
            "VALUES ('g1', 'p-oliver', 1, 1, 15, 'W', 1)"
        )
        # Non-merged player: batting + an 'L' start.
        _seed_game_batting(db, "g1", "p-zach", 1, ab=4, h=1, bb=0)
        db.execute(
            "INSERT INTO player_game_pitching "
            "(game_id, player_id, team_id, perspective_team_id, ip_outs, decision, appearance_order) "
            "VALUES ('g1', 'p-zach', 1, 1, 18, 'L', 1)"
        )
        db.commit()

        # Default recompute_aggregates=True -> routes through canonical recompute.
        dedup_team_players(db, 1, "2026", manage_transaction=True)

        # Both batting rows carry the superset extras (NOT NULL).
        for pid, exp_ab, exp_h in (("p-oliver", 5, 3), ("p-zach", 4, 1)):
            row = db.execute(
                "SELECT ab, h, pa, singles, xbh FROM player_season_batting "
                "WHERE player_id = ? AND team_id = 1 AND season_id = '2026'",
                (pid,),
            ).fetchone()
            assert row is not None, f"expected batting row for {pid}"
            assert row[0] == exp_ab, f"{pid} ab"
            assert row[1] == exp_h, f"{pid} h"
            assert row[2] is not None, f"{pid} pa must be populated (superset)"
            assert row[3] is not None, f"{pid} singles must be populated (superset)"
            assert row[4] is not None, f"{pid} xbh must be populated (superset)"

        # p-oliver: pa = ab(5) + bb(1) + hbp(0) + shf(0) = 6.
        olv = db.execute(
            "SELECT pa, singles, xbh FROM player_season_batting "
            "WHERE player_id = 'p-oliver' AND team_id = 1 AND season_id = '2026'"
        ).fetchone()
        assert olv == (6, 3, 0), f"p-oliver (pa, singles, xbh) wrong: {olv}"

        # Both pitching rows carry w/l/sv (never NULL) AND gs (the ScoutingLoader
        # subset column the old dedup writer omitted).
        for pid, exp_w, exp_l in (("p-oliver", 1, 0), ("p-zach", 0, 1)):
            row = db.execute(
                "SELECT w, l, sv, gs FROM player_season_pitching "
                "WHERE player_id = ? AND team_id = 1 AND season_id = '2026'",
                (pid,),
            ).fetchone()
            assert row is not None, f"expected pitching row for {pid}"
            assert row[0] == exp_w, f"{pid} w"
            assert row[1] == exp_l, f"{pid} l"
            assert row[2] == 0, f"{pid} sv"
            assert row[3] == 1, f"{pid} gs (1 start)"

    def test_member_full_row_survives_recompute(
        self, db: sqlite3.Connection
    ) -> None:
        """AC-8: a member 'full' season row survives a scope dedup/recompute.

        The provenance guard means the canonical recompute only owns
        boxscore_only rows: the member 'full' row is neither deleted nor
        overwritten, and no duplicate boxscore_only row is created for that
        player -- even though the player has per-game rows in scope.
        """
        from src.db.season_aggregates import canonical_recompute

        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-member", "Member", "Player")
        _seed_roster(db, 1, "p-member", "2026")
        _seed_game(db, "g1", "2026", 1)

        # Authoritative member 'full' season row (from the season-stats endpoint)
        # with a distinctive ab value the recompute would NOT reproduce.
        db.execute(
            "INSERT INTO player_season_batting "
            "(player_id, team_id, season_id, stat_completeness, gp, games_tracked, ab, h) "
            "VALUES ('p-member', 1, '2026', 'full', 30, 30, 99, 40)"
        )
        # The same player ALSO has a per-game boxscore row in scope (perspective=team).
        _seed_game_batting(db, "g1", "p-member", 1, ab=3, h=1)
        db.commit()

        canonical_recompute(db, 1, "2026")

        rows = db.execute(
            "SELECT stat_completeness, ab, h FROM player_season_batting "
            "WHERE player_id = 'p-member' AND team_id = 1 AND season_id = '2026' "
            "ORDER BY stat_completeness"
        ).fetchall()
        # Exactly one row: the surviving 'full' row, untouched. No boxscore_only
        # duplicate was inserted for the member player.
        assert rows == [("full", 99, 40)], f"member full row not preserved intact: {rows}"


class TestMergePreservesMemberRows:
    """E-237-03 Phase 5 invariant audit: merge_player_pair must NOT downgrade a
    member ``full``/``supplemented`` season row.

    The canonical recompute's NOT EXISTS guard closes the AC-8 data-loss class
    for NON-merged players; this pins the MERGE-path closure -- a merged
    player's authoritative member row must SURVIVE the merge, be attributed to
    the canonical id, and never be rebuilt as a boxscore sum.
    """

    def test_member_full_row_survives_and_repoints_on_merge(
        self, db: sqlite3.Connection
    ) -> None:
        """Duplicate owns a 'full' row (+ per-game rows) -> after merge+recompute
        the full row survives under the CANONICAL id, not downgraded."""
        from src.db.player_dedup import dedup_team_players

        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-oliver", "Oliver", "Test")  # canonical (longer name)
        _seed_player(db, "p-o", "O", "Test")            # duplicate
        _seed_roster(db, 1, "p-oliver", "2026")
        _seed_roster(db, 1, "p-o", "2026")
        _seed_game(db, "g1", "2026", 1)

        # Duplicate owns an authoritative member 'full' batting row (ab=99) AND
        # a per-game boxscore row (ab=3) the recompute could downgrade it to.
        db.execute(
            "INSERT INTO player_season_batting "
            "(player_id, team_id, season_id, stat_completeness, gp, games_tracked, ab, h) "
            "VALUES ('p-o', 1, '2026', 'full', 30, 30, 99, 40)"
        )
        # And a member 'full' pitching row, to cover both tables.
        db.execute(
            "INSERT INTO player_season_pitching "
            "(player_id, team_id, season_id, stat_completeness, gp_pitcher, games_tracked, ip_outs, so) "
            "VALUES ('p-o', 1, '2026', 'full', 12, 12, 220, 95)"
        )
        _seed_game_batting(db, "g1", "p-o", 1, ab=3, h=1)
        _seed_game_pitching(db, "g1", "p-o", 1, ip_outs=9, so=4)
        db.commit()

        dedup_team_players(db, 1, "2026", manage_transaction=True)

        # The duplicate is gone; the full batting row survives under canonical
        # with its authoritative ab=99 (NOT the boxscore sum of 3).
        assert db.execute(
            "SELECT COUNT(*) FROM players WHERE player_id = 'p-o'"
        ).fetchone()[0] == 0
        bat = db.execute(
            "SELECT stat_completeness, ab, h FROM player_season_batting "
            "WHERE team_id = 1 AND season_id = '2026'"
        ).fetchall()
        assert bat == [("full", 99, 40)], f"batting full row downgraded/lost: {bat}"
        pit = db.execute(
            "SELECT player_id, stat_completeness, ip_outs, so FROM player_season_pitching "
            "WHERE team_id = 1 AND season_id = '2026'"
        ).fetchall()
        assert pit == [("p-oliver", "full", 220, 95)], (
            f"pitching full row downgraded/lost or not re-pointed: {pit}"
        )

    def test_both_own_full_row_collision_canonical_wins(
        self, db: sqlite3.Connection
    ) -> None:
        """Both canonical and duplicate own a 'full' row for the SAME scope ->
        re-pointing would collide on the PK; canonical's row wins, duplicate's
        is dropped, exactly one full row remains under canonical."""
        from src.db.player_dedup import dedup_team_players

        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-oliver", "Oliver", "Test")  # canonical
        _seed_player(db, "p-o", "O", "Test")            # duplicate
        _seed_roster(db, 1, "p-oliver", "2026")
        _seed_roster(db, 1, "p-o", "2026")

        # Both own a 'full' batting row for (1, 2026): canonical ab=99, dup ab=55.
        db.execute(
            "INSERT INTO player_season_batting "
            "(player_id, team_id, season_id, stat_completeness, gp, games_tracked, ab, h) "
            "VALUES ('p-oliver', 1, '2026', 'full', 30, 30, 99, 40)"
        )
        db.execute(
            "INSERT INTO player_season_batting "
            "(player_id, team_id, season_id, stat_completeness, gp, games_tracked, ab, h) "
            "VALUES ('p-o', 1, '2026', 'full', 20, 20, 55, 22)"
        )
        db.commit()

        dedup_team_players(db, 1, "2026", manage_transaction=True)

        rows = db.execute(
            "SELECT player_id, stat_completeness, ab, h FROM player_season_batting "
            "WHERE team_id = 1 AND season_id = '2026'"
        ).fetchall()
        # Exactly one surviving row: the canonical's authoritative values.
        assert rows == [("p-oliver", "full", 99, 40)], (
            f"collision not resolved to canonical-wins: {rows}"
        )


# ---------------------------------------------------------------------------
# Round 6 Cluster 1: cross-perspective dedup safety
# ---------------------------------------------------------------------------


class TestCrossPerspectiveOverlapDetection:
    """E-220 round 6: _check_game_overlaps must not treat cross-perspective
    rows for DIFFERENT teams as overlapping.

    Before the fix, the overlap subquery filters only by player_id (not team
    or perspective), so two different-team players who happen to appear in
    the same game_id register as "overlapping" even though they're on
    different rosters and their data comes from different perspectives.
    """

    def test_cross_team_same_game_same_player_no_overlap(
        self, db: sqlite3.Connection
    ) -> None:
        """Same game_id, same canonical name, but different teams must not
        count as overlap just because the game_id string matches.
        """
        _seed_team(db, 1, "LSB Varsity")
        _seed_team(db, 2, "Rival HS")
        # Same prefix-match names on BOTH teams.  The detector only flags
        # same-team pairs, so `find_duplicate_players` returns one pair per
        # team.  We care that the team-1 pair's overlap check does NOT see
        # the team-2 rows (different team) as overlapping.
        _seed_player(db, "p-oliver-t1", "Oliver", "Holbein")
        _seed_player(db, "p-o-t1", "O", "Holbein")
        _seed_player(db, "p-oliver-t2", "Oliver", "Holbein")
        _seed_player(db, "p-o-t2", "O", "Holbein")
        _seed_roster(db, 1, "p-oliver-t1", "2026")
        _seed_roster(db, 1, "p-o-t1", "2026")
        _seed_roster(db, 2, "p-oliver-t2", "2026")
        _seed_roster(db, 2, "p-o-t2", "2026")

        # Team 1's Oliver plays in game-A ONLY (from team 1's perspective)
        _seed_game(db, "game-A", "2026", 1)
        _seed_game_batting(db, "game-A", "p-oliver-t1", 1, ab=4, perspective_team_id=1)

        # Team 2's Oliver and O BOTH play in game-A (same game_id -- a shared
        # game string) from TEAM 2's perspective.  These are different players
        # (t2-scoped) but share the game_id.
        _seed_game_batting(db, "game-A", "p-oliver-t2", 2, ab=4, perspective_team_id=2)
        _seed_game_batting(db, "game-A", "p-o-t2", 2, ab=4, perspective_team_id=2)

        pairs = find_duplicate_players(db, season_id="2026")

        # Find the team-1 pair (p-oliver-t1 vs p-o-t1)
        team1_pair = next(
            (p for p in pairs
             if p.canonical_player_id == "p-oliver-t1"
             and p.duplicate_player_id == "p-o-t1"),
            None,
        )
        assert team1_pair is not None, (
            "team 1 pair should be detected by name-prefix match"
        )
        # The team-1 pair should NOT show overlap: team 1 O never played in
        # game-A.  Before the fix, the overlap query checked game_id only
        # and would incorrectly see team-2's data as team-1 overlap.
        assert team1_pair.has_overlapping_games is False, (
            "team 1 pair should NOT show overlap -- team 1 O has no games. "
            "Before the fix, cross-team rows in the same game_id were "
            "incorrectly treated as overlapping."
        )

    def test_same_team_same_game_cross_perspective_own_perspective_only(
        self, db: sqlite3.Connection
    ) -> None:
        """Overlap detection must use the team's OWN perspective only.

        If team 1's own perspective shows O in game-A but Oliver has only
        been loaded from team 2's perspective for game-A (foreign data),
        they should NOT count as overlapping for team 1.
        """
        _seed_team(db, 1, "LSB Varsity")
        _seed_team(db, 2, "Rival HS")
        _seed_player(db, "p-oliver", "Oliver", "Holbein")
        _seed_player(db, "p-o", "O", "Holbein")
        _seed_roster(db, 1, "p-oliver", "2026")
        _seed_roster(db, 1, "p-o", "2026")

        _seed_game(db, "game-A", "2026", 1)
        # p-o is in game-A from team 1's OWN perspective (own data).
        _seed_game_batting(db, "game-A", "p-o", 1, ab=1, perspective_team_id=1)
        # p-oliver is in game-A but ONLY from team 2's perspective (foreign).
        _seed_game_batting(db, "game-A", "p-oliver", 1, ab=1, perspective_team_id=2)

        pairs = find_duplicate_players(db, season_id="2026")
        assert len(pairs) == 1
        # Overlap detection should only count rows from the team's own
        # perspective.  p-oliver has NO own-perspective data for team 1 in
        # game-A, so the overlap check should return False.
        assert pairs[0].has_overlapping_games is False, (
            "overlap detection should ignore cross-perspective foreign rows "
            "when determining overlap for the team"
        )


class TestMergeCrossPerspectiveRowsPreserved:
    """E-220 round 6 P1-2: merge_player_pair must treat the 3-column UNIQUE
    correctly -- same game_id + same canonical player_id but DIFFERENT
    perspective_team_id should NOT be treated as a conflict.
    """

    def test_merge_preserves_cross_perspective_rows(
        self, db: sqlite3.Connection
    ) -> None:
        """Canonical has game-A from perspective 1; duplicate has game-A
        from perspective 2.  After merge, BOTH rows should survive tagged
        with canonical player_id.  Before the fix, the JOIN on
        (c.game_id = d.game_id AND c.player_id = canonical) treats them as
        collision and drops one.
        """
        _seed_team(db, 1, "LSB Varsity")
        _seed_team(db, 2, "Opponent")
        _seed_player(db, "p-canonical", "Oliver", "Holbein")
        _seed_player(db, "p-duplicate", "O", "Holbein")
        _seed_roster(db, 1, "p-canonical", "2026")
        _seed_roster(db, 1, "p-duplicate", "2026")
        _seed_game(db, "game-X", "2026", 1)

        # Canonical has game-X from perspective 1 (own)
        _seed_game_batting(
            db, "game-X", "p-canonical", 1, ab=4, h=2,
            perspective_team_id=1,
        )
        # Duplicate has game-X from perspective 2 (foreign).  These are
        # legitimately different rows -- not a conflict -- because the
        # UNIQUE constraint is (game_id, player_id, perspective_team_id).
        _seed_game_batting(
            db, "game-X", "p-duplicate", 1, ab=3, h=1,
            perspective_team_id=2,
        )

        merge_player_pair(db, "p-canonical", "p-duplicate", manage_transaction=True)

        # After merge, BOTH rows should exist (tagged with canonical player_id)
        # and they should have their respective perspectives.
        rows = db.execute(
            "SELECT ab, h, perspective_team_id FROM player_game_batting "
            "WHERE game_id = 'game-X' AND player_id = 'p-canonical' "
            "ORDER BY perspective_team_id"
        ).fetchall()
        assert len(rows) == 2, (
            f"expected 2 rows (one per perspective), got {len(rows)}: {rows}. "
            "Before the fix, the JOIN treated cross-perspective as collision "
            "and deleted one row."
        )
        # Perspective 1 row: original canonical data
        assert rows[0] == (4, 2, 1), (
            f"perspective 1 row should be canonical data (4, 2, 1), got {rows[0]}"
        )
        # Perspective 2 row: duplicate's row rewritten to canonical player_id
        assert rows[1] == (3, 1, 2), (
            f"perspective 2 row should be duplicate rewritten (3, 1, 2), got {rows[1]}"
        )

    def test_merge_resolves_same_perspective_collision(
        self, db: sqlite3.Connection
    ) -> None:
        """Sanity check: same game_id + same perspective_team_id IS a
        collision and should be resolved canonical-wins.
        """
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-canonical", "Oliver", "Holbein")
        _seed_player(db, "p-duplicate", "O", "Holbein")
        _seed_roster(db, 1, "p-canonical", "2026")
        _seed_roster(db, 1, "p-duplicate", "2026")
        _seed_game(db, "game-Y", "2026", 1)

        # Both players have rows in same game, same perspective -- collision.
        _seed_game_batting(
            db, "game-Y", "p-canonical", 1, ab=4, h=2,
            perspective_team_id=1,
        )
        _seed_game_batting(
            db, "game-Y", "p-duplicate", 1, ab=3, h=1,
            perspective_team_id=1,
        )

        merge_player_pair(db, "p-canonical", "p-duplicate", manage_transaction=True)

        # After merge, exactly ONE row should remain (canonical wins).
        rows = db.execute(
            "SELECT ab, h FROM player_game_batting "
            "WHERE game_id = 'game-Y' AND player_id = 'p-canonical'"
        ).fetchall()
        assert len(rows) == 1, f"expected 1 row (canonical wins), got {len(rows)}"
        # Canonical wins on tie: (4, 2)
        assert rows[0] == (4, 2), f"expected canonical (4, 2), got {rows[0]}"


# ===========================================================================
# E-249-01: connected-components dedup with fork refusal (TN-6 fixture suite)
# ===========================================================================


def _player_ids(db: sqlite3.Connection) -> set[str]:
    """All surviving player_ids."""
    return {r[0] for r in db.execute("SELECT player_id FROM players").fetchall()}


class TestComponentCollapse:
    """TN-6 (a)/(e): single-terminal-NAME components fully collapse (AC-1)."""

    def test_total_chain_collapses_to_one_canonical(
        self, db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TN-6 (a): O subset Oli subset Oliver -> one canonical (Oliver),
        combined stats, and NO PlayerMergeError cascade (AC-1, AC-4)."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-o", "O", "Holbein")
        _seed_player(db, "p-oli", "Oli", "Holbein")
        _seed_player(db, "p-oliver", "Oliver", "Holbein")
        for pid in ("p-o", "p-oli", "p-oliver"):
            _seed_roster(db, 1, pid, "2026")

        # Distinct games -> combined batting line is 3+4+2 = 9 AB, 1+2+1 = 4 H.
        _seed_game(db, "g1", "2026", 1)
        _seed_game(db, "g2", "2026", 1)
        _seed_game(db, "g3", "2026", 1)
        _seed_game_batting(db, "g1", "p-o", 1, ab=3, h=1)
        _seed_game_batting(db, "g2", "p-oli", 1, ab=4, h=2)
        _seed_game_batting(db, "g3", "p-oliver", 1, ab=2, h=1)

        with caplog.at_level(logging.ERROR, logger="src.db.player_dedup"):
            merged = dedup_team_players(db, 1, "2026", manage_transaction=True)

        # AC-4: zero merge errors logged (no stale-worklist cascade).
        assert not [
            r for r in caplog.records if r.levelno >= logging.ERROR
        ], "no PlayerMergeError cascade should be logged"

        # Two duplicates merged into the single canonical.
        assert merged == 2
        assert _player_ids(db) == {"p-oliver"}

        row = db.execute(
            "SELECT ab, h FROM player_season_batting "
            "WHERE player_id = 'p-oliver' AND team_id = 1 AND season_id = '2026'"
        ).fetchone()
        assert row == (9, 4), f"combined batting line wrong: {row}"

    def test_equal_named_under_longer_terminal_collapses(
        self, db: sqlite3.Connection
    ) -> None:
        """TN-6 (e): {Jon, Jon, Jonathan} -> both Jons are strict prefixes of
        Jonathan -> single terminal name -> all three collapse (AC-1)."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-jon-a", "Jon", "Reyes")
        _seed_player(db, "p-jon-b", "Jon", "Reyes")
        _seed_player(db, "p-jonathan", "Jonathan", "Reyes")
        for pid in ("p-jon-a", "p-jon-b", "p-jonathan"):
            _seed_roster(db, 1, pid, "2026")

        merged = dedup_team_players(db, 1, "2026", manage_transaction=True)

        assert merged == 2
        assert _player_ids(db) == {"p-jonathan"}, (
            "Jonathan is the sole terminal name; both Jons collapse into it"
        )


class TestSingleStubCollapse:
    """TN-6 (b clean case): a two-member single-stub pair collapses (AC-1)."""

    def test_single_stub_pair_collapses(self, db: sqlite3.Connection) -> None:
        """Jo -> John, no third member -> single terminal -> collapses."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-jo", "Jo", "Adams")
        _seed_player(db, "p-john", "John", "Adams")
        _seed_roster(db, 1, "p-jo", "2026")
        _seed_roster(db, 1, "p-john", "2026")

        merged = dedup_team_players(db, 1, "2026", manage_transaction=True)

        assert merged == 1
        assert _player_ids(db) == {"p-john"}


class TestIdenticalNameCollapse:
    """TN-6 (d): the Finding-1 regression guard -- equal-named maximal members
    (same first+last under two UUIDs) COLLAPSE, they are NOT a fork (AC-3).

    This FAILS if the fork rule keys on terminal *count* rather than terminal
    *distinct names*: both Jons are non-strict-prefix "terminals" but share ONE
    terminal name, so the component must collapse via the existing tiebreak.
    """

    def test_identical_name_pair_collapses(self, db: sqlite3.Connection) -> None:
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-jon-a", "Jon", "Reyes")
        _seed_player(db, "p-jon-b", "Jon", "Reyes")
        _seed_roster(db, 1, "p-jon-a", "2026")
        _seed_roster(db, 1, "p-jon-b", "2026")

        # Give p-jon-b more stat rows so the equal-length tiebreak picks it.
        _seed_game(db, "g1", "2026", 1)
        _seed_game(db, "g2", "2026", 1)
        _seed_game_batting(db, "g1", "p-jon-b", 1, ab=4, h=2)
        _seed_game_batting(db, "g2", "p-jon-b", 1, ab=3, h=1)
        _seed_game(db, "g3", "2026", 1)
        _seed_game_batting(db, "g3", "p-jon-a", 1, ab=2, h=1)

        plan = plan_player_dedup(db, team_id=1, season_id="2026")
        assert len(plan.refused_forks) == 0, "{Jon, Jon} must NOT be a fork"
        assert len(plan.collapses) == 1
        # Tiebreak: equal length -> more stat rows wins -> p-jon-b is canonical.
        assert plan.collapses[0].canonical_player_id == "p-jon-b"

        merged = dedup_team_players(db, 1, "2026", manage_transaction=True)
        assert merged == 1
        assert _player_ids(db) == {"p-jon-b"}


class TestForkRefusal:
    """TN-6 (b)/(c): forks (>=2 distinct terminal names) are REFUSED (AC-2)."""

    def test_jo_john_jon_fork_refused(
        self, db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TN-6 (b): Jo -> John + Jo -> Jon -> John and Jon are distinct-named
        terminals -> REFUSED; all three members survive; one WARN (AC-2, AC-5)."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-jo", "Jo", "Pratt")
        _seed_player(db, "p-john", "John", "Pratt")
        _seed_player(db, "p-jon", "Jon", "Pratt")
        for pid in ("p-jo", "p-john", "p-jon"):
            _seed_roster(db, 1, pid, "2026")
        # No same-game co-occurrence between John and Jon (consistent with a
        # possible same-human fork) -- Tier 1 refuses regardless.
        _seed_game(db, "g1", "2026", 1)
        _seed_game(db, "g2", "2026", 1)
        _seed_game_batting(db, "g1", "p-john", 1, ab=3, h=1)
        _seed_game_batting(db, "g2", "p-jon", 1, ab=2, h=1)

        with caplog.at_level(logging.WARNING, logger="src.db.player_dedup"):
            merged = dedup_team_players(db, 1, "2026", manage_transaction=True)

        assert merged == 0, "a refused fork merges nothing"
        assert _player_ids(db) == {"p-jo", "p-john", "p-jon"}, (
            "every member of a refused fork survives as a distinct row"
        )

        # AC-5: exactly one WARN per refused component, naming the team and the
        # conflicting terminal names.
        warns = [
            r for r in caplog.records
            if r.levelno == logging.WARNING and "refused" in r.getMessage()
        ]
        assert len(warns) == 1, f"expected exactly one WARN, got {len(warns)}"
        msg = warns[0].getMessage()
        assert "LSB Varsity" in msg
        assert "John" in msg and "Jon" in msg

    def test_stub_to_two_distinct_refused_no_cross_merge(
        self, db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TN-6 (c): O -> Oliver + O -> Owen -> REFUSED; the two distinct-human
        terminals stay separate (the no-cross-merge assertion, AC-2).

        Co-occurrence baked in: Oliver and Owen play in the SAME game (the
        signal that they are TWO humans), making the distinction explicit even
        though Tier 1 refuses on the structural fork rule alone.
        """
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-o", "O", "Yang")
        _seed_player(db, "p-oliver", "Oliver", "Yang")
        _seed_player(db, "p-owen", "Owen", "Yang")
        for pid in ("p-o", "p-oliver", "p-owen"):
            _seed_roster(db, 1, pid, "2026")
        # Two-human signal: Oliver and Owen both appear in g1.
        _seed_game(db, "g1", "2026", 1)
        _seed_game_batting(db, "g1", "p-oliver", 1, ab=4, h=2)
        _seed_game_batting(db, "g1", "p-owen", 1, ab=3, h=1)

        with caplog.at_level(logging.WARNING, logger="src.db.player_dedup"):
            merged = dedup_team_players(db, 1, "2026", manage_transaction=True)

        assert merged == 0
        # No-cross-merge: Oliver and Owen remain DISTINCT players rows (and the
        # shared stub O survives too, since the whole component is refused).
        assert _player_ids(db) == {"p-o", "p-oliver", "p-owen"}
        assert db.execute(
            "SELECT COUNT(*) FROM players WHERE first_name IN ('Oliver', 'Owen')"
        ).fetchone()[0] == 2

        plan = plan_player_dedup(db, team_id=1, season_id="2026")
        assert len(plan.collapses) == 0
        assert len(plan.refused_forks) == 1
        assert sorted(plan.refused_forks[0].terminal_names) == ["Oliver", "Owen"]


class TestComponentMixedProvenance:
    """AC-6: a member full/supplemented row survives a multi-member collapse."""

    def test_member_full_row_survives_chain_collapse(
        self, db: sqlite3.Connection
    ) -> None:
        """A 3-member chain where the MIDDLE member owns an authoritative 'full'
        season row -> after collapse the full row is re-pointed to canonical,
        never downgraded to a boxscore sum (TN-5.1)."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-o", "O", "Cruz")
        _seed_player(db, "p-oli", "Oli", "Cruz")
        _seed_player(db, "p-oliver", "Oliver", "Cruz")
        for pid in ("p-o", "p-oli", "p-oliver"):
            _seed_roster(db, 1, pid, "2026")
        _seed_game(db, "g1", "2026", 1)

        # The middle member owns a member 'full' batting row (ab=99) AND a
        # per-game boxscore row the recompute could downgrade it to.
        db.execute(
            "INSERT INTO player_season_batting "
            "(player_id, team_id, season_id, stat_completeness, gp, games_tracked, ab, h) "
            "VALUES ('p-oli', 1, '2026', 'full', 30, 30, 99, 40)"
        )
        _seed_game_batting(db, "g1", "p-oli", 1, ab=3, h=1)
        db.commit()

        dedup_team_players(db, 1, "2026", manage_transaction=True)

        assert _player_ids(db) == {"p-oliver"}
        bat = db.execute(
            "SELECT player_id, stat_completeness, ab, h FROM player_season_batting "
            "WHERE team_id = 1 AND season_id = '2026'"
        ).fetchall()
        assert bat == [("p-oliver", "full", 99, 40)], (
            f"member full row downgraded/lost or not re-pointed: {bat}"
        )


class TestAggregateParityAfterDedup:
    """AC-7 / TN-6: the aggregate test has teeth -- seed a POPULATED state whose
    stored aggregate DISAGREES with the per-game sum, then assert the post-dedup
    recompute yields the correct COMBINED line (not the stale stored value)."""

    def test_stale_aggregate_recomputed_to_combined_line(
        self, db: sqlite3.Connection
    ) -> None:
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-o", "O", "Diaz")
        _seed_player(db, "p-oliver", "Oliver", "Diaz")
        _seed_roster(db, 1, "p-o", "2026")
        _seed_roster(db, 1, "p-oliver", "2026")

        # Per-game rows sum to ab=7, h=3.
        _seed_game(db, "g1", "2026", 1)
        _seed_game(db, "g2", "2026", 1)
        _seed_game_batting(db, "g1", "p-o", 1, ab=3, h=1)
        _seed_game_batting(db, "g2", "p-oliver", 1, ab=4, h=2)

        # Deliberately WRONG stored boxscore_only aggregate (ab=1, h=0) on the
        # canonical -- if the recompute did not run (or read stale), the test
        # would see these wrong values instead of the combined per-game sum.
        db.execute(
            "INSERT INTO player_season_batting "
            "(player_id, team_id, season_id, stat_completeness, gp, games_tracked, ab, h) "
            "VALUES ('p-oliver', 1, '2026', 'boxscore_only', 1, 1, 1, 0)"
        )
        db.commit()

        dedup_team_players(
            db, 1, "2026", manage_transaction=True, recompute_aggregates=True
        )

        rows = db.execute(
            "SELECT player_id, ab, h FROM player_season_batting "
            "WHERE team_id = 1 AND season_id = '2026'"
        ).fetchall()
        assert rows == [("p-oliver", 7, 3)], (
            f"post-dedup aggregate should be the combined per-game line, got {rows}"
        )


class TestDedupPlanShape:
    """Unit-level checks on plan_player_dedup's returned shape (for E-249-02)."""

    def test_plan_separates_collapses_and_forks(
        self, db: sqlite3.Connection
    ) -> None:
        """A roster with a chain (collapse) AND a fork (refuse) on the same team
        yields one of each in the plan, keyed correctly."""
        _seed_team(db, 1, "LSB Varsity")
        # Collapse component: Sam subset Samuel (last name Webb).
        _seed_player(db, "p-sam", "Sam", "Webb")
        _seed_player(db, "p-samuel", "Samuel", "Webb")
        # Fork component: A -> Aaron + A -> Abel (last name Vance).
        _seed_player(db, "p-a", "A", "Vance")
        _seed_player(db, "p-aaron", "Aaron", "Vance")
        _seed_player(db, "p-abel", "Abel", "Vance")
        for pid in ("p-sam", "p-samuel", "p-a", "p-aaron", "p-abel"):
            _seed_roster(db, 1, pid, "2026")

        plan = plan_player_dedup(db, team_id=1, season_id="2026")

        assert len(plan.collapses) == 1
        collapse = plan.collapses[0]
        assert collapse.canonical_player_id == "p-samuel"
        assert [d.player_id for d in collapse.duplicates] == ["p-sam"]

        assert len(plan.refused_forks) == 1
        fork = plan.refused_forks[0]
        assert sorted(fork.terminal_names) == ["Aaron", "Abel"]
        assert {m.player_id for m in fork.members} == {"p-a", "p-aaron", "p-abel"}


