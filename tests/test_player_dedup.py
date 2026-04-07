"""Tests for src.db.player_dedup -- duplicate player detection and merge."""

from __future__ import annotations

import sqlite3

import pytest

from src.db.player_dedup import (
    DuplicatePlayerPair,
    PlayerMergeError,
    _select_canonical_player,
    find_duplicate_players,
    merge_player_pair,
    preview_player_merge,
    recompute_affected_seasons,
    recompute_season_batting,
    recompute_season_pitching,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory database with the schema needed for detection and merge."""
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")

    conn.executescript(
        """
        CREATE TABLE teams (
            id   INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE seasons (
            season_id TEXT PRIMARY KEY
        );

        CREATE TABLE players (
            player_id  TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name  TEXT NOT NULL
        );

        CREATE TABLE team_rosters (
            team_id   INTEGER NOT NULL REFERENCES teams(id),
            player_id TEXT NOT NULL REFERENCES players(player_id),
            season_id TEXT NOT NULL REFERENCES seasons(season_id),
            PRIMARY KEY (team_id, player_id, season_id)
        );

        CREATE TABLE games (
            game_id   TEXT PRIMARY KEY,
            season_id TEXT NOT NULL REFERENCES seasons(season_id),
            home_team_id INTEGER REFERENCES teams(id),
            away_team_id INTEGER REFERENCES teams(id)
        );

        CREATE TABLE player_game_batting (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id           TEXT NOT NULL REFERENCES games(game_id),
            player_id         TEXT NOT NULL REFERENCES players(player_id),
            team_id           INTEGER NOT NULL REFERENCES teams(id),
            stat_completeness TEXT NOT NULL DEFAULT 'boxscore_only',
            ab  INTEGER,
            r   INTEGER,
            h   INTEGER,
            rbi INTEGER,
            bb  INTEGER,
            so  INTEGER,
            doubles INTEGER,
            triples INTEGER,
            hr      INTEGER,
            tb      INTEGER,
            hbp     INTEGER,
            shf     INTEGER,
            sb      INTEGER,
            cs      INTEGER,
            e       INTEGER,
            UNIQUE(game_id, player_id)
        );

        CREATE TABLE player_game_pitching (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id           TEXT NOT NULL REFERENCES games(game_id),
            player_id         TEXT NOT NULL REFERENCES players(player_id),
            team_id           INTEGER NOT NULL REFERENCES teams(id),
            stat_completeness TEXT NOT NULL DEFAULT 'boxscore_only',
            decision  TEXT,
            ip_outs   INTEGER,
            h         INTEGER,
            r         INTEGER,
            er        INTEGER,
            bb        INTEGER,
            so        INTEGER,
            wp        INTEGER,
            hbp       INTEGER,
            pitches   INTEGER,
            total_strikes INTEGER,
            bf        INTEGER,
            UNIQUE(game_id, player_id)
        );

        CREATE TABLE player_season_batting (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id         TEXT NOT NULL REFERENCES players(player_id),
            team_id           INTEGER NOT NULL REFERENCES teams(id),
            season_id         TEXT NOT NULL REFERENCES seasons(season_id),
            stat_completeness TEXT NOT NULL DEFAULT 'boxscore_only',
            games_tracked     INTEGER,
            gp      INTEGER,
            pa      INTEGER,
            ab      INTEGER,
            h       INTEGER,
            singles INTEGER,
            doubles INTEGER,
            triples INTEGER,
            hr      INTEGER,
            rbi     INTEGER,
            r       INTEGER,
            bb      INTEGER,
            so      INTEGER,
            hbp     INTEGER,
            shf     INTEGER,
            sb      INTEGER,
            cs      INTEGER,
            tb      INTEGER,
            xbh     INTEGER,
            UNIQUE(player_id, team_id, season_id)
        );

        CREATE TABLE player_season_pitching (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id         TEXT NOT NULL REFERENCES players(player_id),
            team_id           INTEGER NOT NULL REFERENCES teams(id),
            season_id         TEXT NOT NULL REFERENCES seasons(season_id),
            stat_completeness TEXT NOT NULL DEFAULT 'boxscore_only',
            games_tracked     INTEGER,
            gp_pitcher INTEGER,
            ip_outs    INTEGER,
            h          INTEGER,
            r          INTEGER,
            er         INTEGER,
            bb         INTEGER,
            so         INTEGER,
            wp         INTEGER,
            hbp        INTEGER,
            pitches    INTEGER,
            total_strikes INTEGER,
            bf         INTEGER,
            w          INTEGER,
            l          INTEGER,
            sv         INTEGER,
            UNIQUE(player_id, team_id, season_id)
        );

        CREATE TABLE plays (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id    TEXT NOT NULL REFERENCES games(game_id),
            batter_id  TEXT NOT NULL REFERENCES players(player_id),
            pitcher_id TEXT REFERENCES players(player_id)
        );

        CREATE TABLE spray_charts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id    TEXT REFERENCES games(game_id),
            player_id  TEXT REFERENCES players(player_id),
            team_id    INTEGER REFERENCES teams(id),
            pitcher_id TEXT REFERENCES players(player_id)
        );

        CREATE TABLE reconciliation_discrepancies (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id     TEXT NOT NULL,
            run_id      TEXT NOT NULL,
            team_id     INTEGER NOT NULL,
            player_id   TEXT NOT NULL,
            signal_name TEXT NOT NULL,
            category    TEXT NOT NULL DEFAULT 'test',
            status      TEXT NOT NULL DEFAULT 'MATCH',
            UNIQUE(run_id, game_id, team_id, player_id, signal_name)
        );
        """
    )
    return conn


def _seed_team(db: sqlite3.Connection, team_id: int, name: str) -> None:
    db.execute("INSERT INTO teams (id, name) VALUES (?, ?)", (team_id, name))


def _seed_season(db: sqlite3.Connection, season_id: str) -> None:
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id) VALUES (?)", (season_id,)
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
        "INSERT OR IGNORE INTO games (game_id, season_id, home_team_id) VALUES (?, ?, ?)",
        (game_id, season_id, team_id),
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
) -> None:
    db.execute(
        "INSERT INTO player_game_batting "
        "(game_id, player_id, team_id, stat_completeness, ab, h, bb, hr, r, rbi, so, hbp, shf) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_id, player_id, team_id, stat_completeness, ab, h, bb, hr, r, rbi, so, hbp, shf),
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
) -> None:
    db.execute(
        "INSERT INTO player_game_pitching "
        "(game_id, player_id, team_id, stat_completeness, ip_outs, h, r, er, bb, so, decision) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_id, player_id, team_id, stat_completeness, ip_outs, h, r, er, bb, so, decision),
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

        pairs = find_duplicate_players(db)
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

        pairs = find_duplicate_players(db)
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

        pairs = find_duplicate_players(db)
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

        pairs = find_duplicate_players(db)
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
# Deduplication across seasons
# ---------------------------------------------------------------------------


class TestSeasonDedup:
    def test_pair_across_multiple_seasons_returned_once(
        self, db: sqlite3.Connection
    ) -> None:
        """Same pair on same team across two seasons -> one result."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-oliver", "Oliver", "Holbein")
        _seed_player(db, "p-o", "O", "Holbein")
        _seed_roster(db, 1, "p-oliver", "2025")
        _seed_roster(db, 1, "p-o", "2025")
        _seed_roster(db, 1, "p-oliver", "2026")
        _seed_roster(db, 1, "p-o", "2026")

        pairs = find_duplicate_players(db)
        assert len(pairs) == 1


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

        pairs_t1 = find_duplicate_players(db, team_id=1)
        assert len(pairs_t1) == 1
        assert pairs_t1[0].canonical_last_name == "Holbein"

        pairs_t2 = find_duplicate_players(db, team_id=2)
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

        pairs = find_duplicate_players(db)
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

        pairs = find_duplicate_players(db)
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

        pairs = find_duplicate_players(db)
        assert len(pairs) == 0

    def test_case_insensitive_match(self, db: sqlite3.Connection) -> None:
        """Detection is case-insensitive for both first and last names."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-oliver", "OLIVER", "holbein")
        _seed_player(db, "p-o", "o", "HOLBEIN")
        _seed_roster(db, 1, "p-oliver", "2026")
        _seed_roster(db, 1, "p-o", "2026")

        pairs = find_duplicate_players(db)
        assert len(pairs) == 1

    def test_no_players_returns_empty(self, db: sqlite3.Connection) -> None:
        """Empty database returns empty list."""
        pairs = find_duplicate_players(db)
        assert pairs == []

    def test_exact_same_first_name_flagged(self, db: sqlite3.Connection) -> None:
        """Two players with identical first and last names are flagged
        (a name is a prefix of itself)."""
        _seed_team(db, 1, "LSB Varsity")
        _seed_player(db, "p-a", "Oliver", "Holbein")
        _seed_player(db, "p-b", "Oliver", "Holbein")
        _seed_roster(db, 1, "p-a", "2026")
        _seed_roster(db, 1, "p-b", "2026")

        pairs = find_duplicate_players(db)
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
            "INSERT INTO plays (game_id, batter_id, pitcher_id) VALUES ('game-1', 'p-dup', 'p-canonical')"
        )
        db.execute(
            "INSERT INTO plays (game_id, batter_id, pitcher_id) VALUES ('game-2', 'p-canonical', 'p-dup')"
        )

        # 6. spray_charts -- duplicate as both player and pitcher
        db.execute(
            "INSERT INTO spray_charts (game_id, player_id, team_id, pitcher_id) "
            "VALUES ('game-1', 'p-dup', 1, 'p-canonical')"
        )
        db.execute(
            "INSERT INTO spray_charts (game_id, player_id, team_id, pitcher_id) "
            "VALUES ('game-2', 'p-canonical', 1, 'p-dup')"
        )

        # 7. reconciliation_discrepancies -- both have rows + a __game__ sentinel
        db.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(game_id, run_id, team_id, player_id, signal_name) "
            "VALUES ('game-1', 'run-1', 1, 'p-dup', 'ab')"
        )
        db.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(game_id, run_id, team_id, player_id, signal_name) "
            "VALUES ('game-1', 'run-1', 1, '__game__', 'total_r')"
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

        db.execute("INSERT INTO plays (game_id, batter_id, pitcher_id) VALUES ('g1', 'p-dup', 'p-other')")
        db.execute("INSERT INTO plays (game_id, batter_id, pitcher_id) VALUES ('g1', 'p-other', 'p-dup')")

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
            "INSERT INTO spray_charts (game_id, player_id, team_id, pitcher_id) "
            "VALUES ('g1', 'p-dup', 1, NULL)"
        )
        db.execute(
            "INSERT INTO spray_charts (game_id, player_id, team_id, pitcher_id) "
            "VALUES ('g1', 'p-can', 1, 'p-dup')"
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

        recompute_season_batting(db, "p-can", 1, "2026")

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

        recompute_season_pitching(db, "p-can", 1, "2026")

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

        recompute_season_batting(db, "p-can", 1, "2026")
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

        db.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(game_id, run_id, team_id, player_id, signal_name) "
            "VALUES ('g1', 'run-1', 1, '__game__', 'total_r')"
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
