"""Tests for src/reconciliation/engine.py -- plays-vs-boxscore reconciliation."""

from __future__ import annotations

import sqlite3
import json
from pathlib import Path

import pytest

from src.reconciliation.engine import (
    GAME_LEVEL_PLAYER_ID,
    ReconciliationSummary,
    reconcile_all,
    reconcile_game,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db() -> sqlite3.Connection:
    """Create an in-memory SQLite database with the required schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = OFF")  # Simplify test setup

    # Minimal schema for reconciliation
    conn.executescript("""
        CREATE TABLE seasons (
            season_id TEXT PRIMARY KEY
        );

        CREATE TABLE teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            gc_uuid TEXT,
            public_id TEXT,
            membership_type TEXT DEFAULT 'member',
            is_active INTEGER DEFAULT 1,
            season_year INTEGER
        );

        CREATE TABLE players (
            player_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            team_id INTEGER
        );

        CREATE TABLE games (
            game_id TEXT PRIMARY KEY,
            season_id TEXT NOT NULL,
            game_date TEXT NOT NULL,
            home_team_id INTEGER NOT NULL,
            away_team_id INTEGER NOT NULL,
            home_score INTEGER,
            away_score INTEGER,
            status TEXT NOT NULL DEFAULT 'completed',
            game_stream_id TEXT
        );

        CREATE TABLE player_game_batting (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            player_id TEXT NOT NULL,
            team_id INTEGER NOT NULL,
            batting_order INTEGER,
            positions_played TEXT,
            is_primary INTEGER,
            stat_completeness TEXT DEFAULT 'boxscore_only',
            ab INTEGER, r INTEGER, h INTEGER, rbi INTEGER,
            bb INTEGER, so INTEGER,
            doubles INTEGER, triples INTEGER, hr INTEGER,
            tb INTEGER, hbp INTEGER, shf INTEGER,
            sb INTEGER, cs INTEGER, e INTEGER,
            UNIQUE(game_id, player_id)
        );

        CREATE TABLE player_game_pitching (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            player_id TEXT NOT NULL,
            team_id INTEGER NOT NULL,
            decision TEXT,
            stat_completeness TEXT DEFAULT 'boxscore_only',
            ip_outs INTEGER, h INTEGER, r INTEGER, er INTEGER,
            bb INTEGER, so INTEGER,
            wp INTEGER, hbp INTEGER,
            pitches INTEGER, total_strikes INTEGER, bf INTEGER,
            UNIQUE(game_id, player_id)
        );

        CREATE TABLE plays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            play_order INTEGER NOT NULL,
            inning INTEGER NOT NULL,
            half TEXT NOT NULL,
            season_id TEXT NOT NULL,
            batting_team_id INTEGER NOT NULL,
            batter_id TEXT NOT NULL,
            pitcher_id TEXT,
            outcome TEXT,
            pitch_count INTEGER NOT NULL DEFAULT 0,
            is_first_pitch_strike INTEGER NOT NULL DEFAULT 0,
            is_qab INTEGER NOT NULL DEFAULT 0,
            home_score INTEGER,
            away_score INTEGER,
            did_score_change INTEGER,
            outs_after INTEGER,
            did_outs_change INTEGER,
            UNIQUE(game_id, play_order)
        );

        CREATE TABLE play_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            play_id INTEGER NOT NULL,
            event_order INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            pitch_result TEXT,
            is_first_pitch INTEGER NOT NULL DEFAULT 0,
            raw_template TEXT,
            UNIQUE(play_id, event_order)
        );

        CREATE TABLE reconciliation_discrepancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            team_id INTEGER NOT NULL,
            player_id TEXT NOT NULL,
            signal_name TEXT NOT NULL,
            category TEXT NOT NULL,
            boxscore_value INTEGER,
            plays_value INTEGER,
            delta INTEGER,
            status TEXT NOT NULL CHECK(status IN ('MATCH', 'CORRECTABLE', 'CORRECTED', 'AMBIGUOUS', 'UNCORRECTABLE')),
            correction_detail TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(run_id, game_id, team_id, player_id, signal_name)
        );

        INSERT INTO seasons VALUES ('2025-spring-hs');
        INSERT INTO teams (id, name, gc_uuid, membership_type) VALUES (1, 'Home Team', 'uuid-home', 'member');
        INSERT INTO teams (id, name, gc_uuid, membership_type) VALUES (2, 'Away Team', 'uuid-away', 'member');

        INSERT INTO players VALUES ('pitcher-h1', 'Home', 'Pitcher1', 1);
        INSERT INTO players VALUES ('pitcher-h2', 'Home', 'Pitcher2', 1);
        INSERT INTO players VALUES ('pitcher-a1', 'Away', 'Pitcher1', 2);
        INSERT INTO players VALUES ('batter-h1', 'Home', 'Batter1', 1);
        INSERT INTO players VALUES ('batter-h2', 'Home', 'Batter2', 1);
        INSERT INTO players VALUES ('batter-a1', 'Away', 'Batter1', 2);
        INSERT INTO players VALUES ('batter-a2', 'Away', 'Batter2', 2);
    """)
    return conn


def _insert_game(conn: sqlite3.Connection, game_id: str = "game-1") -> None:
    """Insert a test game."""
    conn.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, "
        "home_score, away_score, status) VALUES (?, '2025-spring-hs', '2025-04-01', 1, 2, 5, 3, 'completed')",
        (game_id,),
    )


def _insert_pitching_boxscore(
    conn: sqlite3.Connection,
    game_id: str,
    player_id: str,
    team_id: int,
    *,
    ip_outs: int = 0,
    h: int = 0,
    r: int = 0,
    er: int = 0,
    bb: int = 0,
    so: int = 0,
    wp: int = 0,
    hbp: int = 0,
    pitches: int = 0,
    total_strikes: int = 0,
    bf: int = 0,
    decision: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO player_game_pitching "
        "(game_id, player_id, team_id, decision, ip_outs, h, r, er, bb, so, wp, hbp, pitches, total_strikes, bf) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_id, player_id, team_id, decision, ip_outs, h, r, er, bb, so, wp, hbp, pitches, total_strikes, bf),
    )


def _insert_batting_boxscore(
    conn: sqlite3.Connection,
    game_id: str,
    player_id: str,
    team_id: int,
    *,
    ab: int = 0,
    r: int = 0,
    h: int = 0,
    bb: int = 0,
    so: int = 0,
    hbp: int = 0,
) -> None:
    conn.execute(
        "INSERT INTO player_game_batting "
        "(game_id, player_id, team_id, ab, r, h, rbi, bb, so, hbp) "
        "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
        (game_id, player_id, team_id, ab, r, h, bb, so, hbp),
    )


def _insert_play(
    conn: sqlite3.Connection,
    game_id: str,
    play_order: int,
    *,
    inning: int = 1,
    half: str = "top",
    batting_team_id: int = 2,
    batter_id: str = "batter-a1",
    pitcher_id: str = "pitcher-h1",
    outcome: str = "Flyout",
    pitch_count: int = 3,
    home_score: int = 0,
    away_score: int = 0,
    did_outs_change: int = 1,
) -> int:
    """Insert a play and return the play id."""
    conn.execute(
        "INSERT INTO plays "
        "(game_id, play_order, inning, half, season_id, batting_team_id, batter_id, "
        "pitcher_id, outcome, pitch_count, home_score, away_score, did_outs_change) "
        "VALUES (?, ?, ?, ?, '2025-spring-hs', ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_id, play_order, inning, half, batting_team_id, batter_id,
         pitcher_id, outcome, pitch_count, home_score, away_score, did_outs_change),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_play_event(
    conn: sqlite3.Connection,
    play_id: int,
    event_order: int,
    *,
    event_type: str = "pitch",
    pitch_result: str | None = None,
    raw_template: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO play_events (play_id, event_order, event_type, pitch_result, is_first_pitch, raw_template) "
        "VALUES (?, ?, ?, ?, 0, ?)",
        (play_id, event_order, event_type, pitch_result, raw_template),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSkipNoPlays:
    """Games without plays data should be skipped."""

    def test_skip_game_without_plays(self, db: sqlite3.Connection) -> None:
        _insert_game(db, "game-no-plays")
        _insert_pitching_boxscore(db, "game-no-plays", "pitcher-h1", 1, bf=10, so=3)

        summary = reconcile_game(db, "game-no-plays")
        assert summary.games_skipped_no_plays == 1
        assert summary.games_processed == 0
        assert summary.signal_counts == {}


class TestPerfectPitcherAttribution:
    """All signals should be MATCH when plays data perfectly matches boxscore."""

    def test_perfect_match(self, db: sqlite3.Connection) -> None:
        _insert_game(db, "game-perfect")

        # Home team pitcher: 3 BF, 1 SO, 0 BB, 0 HBP, 1 H, 9 pitches, 6 strikes, 2 outs
        _insert_pitching_boxscore(
            db, "game-perfect", "pitcher-h1", 1,
            bf=3, so=1, bb=0, hbp=0, h=1, ip_outs=2,
            pitches=9, total_strikes=6, wp=0,
        )
        # Away team pitcher: 3 BF, 1 SO, 1 BB, 0 HBP, 0 H, 12 pitches, 6 strikes, 1 out
        _insert_pitching_boxscore(
            db, "game-perfect", "pitcher-a1", 2,
            bf=3, so=1, bb=1, hbp=0, h=0, ip_outs=1,
            pitches=12, total_strikes=6, wp=0,
        )

        # Home batters (batting in bottom half)
        _insert_batting_boxscore(db, "game-perfect", "batter-h1", 1, ab=2, r=1, h=0, bb=1, so=0)
        _insert_batting_boxscore(db, "game-perfect", "batter-h2", 1, ab=1, r=0, h=0, bb=0, so=1)

        # Away batters (batting in top half)
        _insert_batting_boxscore(db, "game-perfect", "batter-a1", 2, ab=1, r=0, h=1, bb=0, so=0)
        _insert_batting_boxscore(db, "game-perfect", "batter-a2", 2, ab=1, r=0, h=0, bb=0, so=1)

        # Plays: top of 1st (away batting, home pitching)
        p1 = _insert_play(db, "game-perfect", 1, inning=1, half="top",
                          batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1",
                          outcome="Single", pitch_count=2, did_outs_change=0,
                          home_score=0, away_score=0)
        _insert_play_event(db, p1, 1, pitch_result="ball")
        _insert_play_event(db, p1, 2, pitch_result="in_play")

        p2 = _insert_play(db, "game-perfect", 2, inning=1, half="top",
                          batting_team_id=2, batter_id="batter-a2", pitcher_id="pitcher-h1",
                          outcome="Strikeout", pitch_count=3, did_outs_change=1,
                          home_score=0, away_score=0)
        _insert_play_event(db, p2, 1, pitch_result="strike_looking")
        _insert_play_event(db, p2, 2, pitch_result="foul")
        _insert_play_event(db, p2, 3, pitch_result="strike_swinging")

        # Third batter grounds out (4 pitches: ball, foul, ball, in_play)
        p3 = _insert_play(db, "game-perfect", 3, inning=1, half="top",
                          batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1",
                          outcome="Groundout", pitch_count=4, did_outs_change=1,
                          home_score=0, away_score=0)
        _insert_play_event(db, p3, 1, pitch_result="ball")
        _insert_play_event(db, p3, 2, pitch_result="foul")
        _insert_play_event(db, p3, 3, pitch_result="ball")
        _insert_play_event(db, p3, 4, pitch_result="in_play")

        # Plays: bottom of 1st (home batting, away pitching)
        p4 = _insert_play(db, "game-perfect", 4, inning=1, half="bottom",
                          batting_team_id=1, batter_id="batter-h1", pitcher_id="pitcher-a1",
                          outcome="Walk", pitch_count=5, did_outs_change=0,
                          home_score=1, away_score=0)

        p5 = _insert_play(db, "game-perfect", 5, inning=1, half="bottom",
                          batting_team_id=1, batter_id="batter-h2", pitcher_id="pitcher-a1",
                          outcome="Strikeout", pitch_count=3, did_outs_change=1,
                          home_score=1, away_score=0)
        _insert_play_event(db, p5, 1, pitch_result="strike_looking")
        _insert_play_event(db, p5, 2, pitch_result="strike_looking")
        _insert_play_event(db, p5, 3, pitch_result="strike_swinging")

        p6 = _insert_play(db, "game-perfect", 6, inning=1, half="bottom",
                          batting_team_id=1, batter_id="batter-h1", pitcher_id="pitcher-a1",
                          outcome="Flyout", pitch_count=4, did_outs_change=0,
                          home_score=1, away_score=0)
        _insert_play_event(db, p6, 1, pitch_result="ball")
        _insert_play_event(db, p6, 2, pitch_result="foul")
        _insert_play_event(db, p6, 3, pitch_result="foul")
        _insert_play_event(db, p6, 4, pitch_result="in_play")

        summary = reconcile_game(db, "game-perfect")
        assert summary.games_processed == 1
        assert summary.games_skipped_no_plays == 0

        # Check that pitcher BF signals match
        pitcher_bf = summary.signal_counts.get("pitcher_bf", {})
        assert pitcher_bf.get("MATCH", 0) >= 2  # both pitchers

        # Check all pitcher signals for MATCH
        for sig in ["pitcher_bf", "pitcher_so", "pitcher_bb", "pitcher_hbp",
                     "pitcher_h", "pitcher_pitches", "pitcher_total_strikes"]:
            counts = summary.signal_counts.get(sig, {})
            # All entries should be MATCH
            non_match = sum(v for k, v in counts.items() if k != "MATCH")
            assert non_match == 0, f"Signal {sig} has non-MATCH entries: {counts}"


class TestPitcherMisattribution:
    """Tests for games with known pitcher misattribution (CORRECTABLE signals)."""

    def test_bf_mismatch_is_correctable(self, db: sqlite3.Connection) -> None:
        """When BF doesn't match due to pitcher boundary drift, status is CORRECTABLE."""
        _insert_game(db, "game-drift")

        # Boxscore says pitcher-h1 faced 2 batters, pitcher-h2 faced 1
        _insert_pitching_boxscore(db, "game-drift", "pitcher-h1", 1, bf=2, so=1)
        _insert_pitching_boxscore(db, "game-drift", "pitcher-h2", 1, bf=1, so=0)
        # Away pitcher
        _insert_pitching_boxscore(db, "game-drift", "pitcher-a1", 2, bf=2, so=0)

        # Home batters
        _insert_batting_boxscore(db, "game-drift", "batter-h1", 1, ab=1, h=0)
        _insert_batting_boxscore(db, "game-drift", "batter-h2", 1, ab=1, h=0)

        # Away batters
        _insert_batting_boxscore(db, "game-drift", "batter-a1", 2, ab=2, h=0)
        _insert_batting_boxscore(db, "game-drift", "batter-a2", 2, ab=1, h=0)

        # Plays: all 3 top-half plays attributed to pitcher-h1 (drift error)
        _insert_play(db, "game-drift", 1, inning=1, half="top",
                      batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1,
                      home_score=0, away_score=0)
        _insert_play(db, "game-drift", 2, inning=1, half="top",
                      batting_team_id=2, batter_id="batter-a2", pitcher_id="pitcher-h1",
                      outcome="Strikeout", pitch_count=3, did_outs_change=1,
                      home_score=0, away_score=0)
        # This play should be pitcher-h2 but is misattributed to pitcher-h1
        _insert_play(db, "game-drift", 3, inning=1, half="top",
                      batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Groundout", pitch_count=2, did_outs_change=1,
                      home_score=0, away_score=0)

        # Bottom half plays
        _insert_play(db, "game-drift", 4, inning=1, half="bottom",
                      batting_team_id=1, batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", pitch_count=2, did_outs_change=1,
                      home_score=0, away_score=0)
        _insert_play(db, "game-drift", 5, inning=1, half="bottom",
                      batting_team_id=1, batter_id="batter-h2", pitcher_id="pitcher-a1",
                      outcome="Groundout", pitch_count=3, did_outs_change=1,
                      home_score=0, away_score=0)

        summary = reconcile_game(db, "game-drift")
        assert summary.games_processed == 1

        # pitcher-h1 BF: boxscore=2, plays=3 -> CORRECTABLE
        bf_counts = summary.signal_counts.get("pitcher_bf", {})
        assert "CORRECTABLE" in bf_counts, f"Expected CORRECTABLE in pitcher_bf: {bf_counts}"

        # pitcher-h2 BF: boxscore=1, plays=0 -> UNCORRECTABLE (missing from plays)
        assert "UNCORRECTABLE" in bf_counts, f"Expected UNCORRECTABLE in pitcher_bf: {bf_counts}"


class TestBatterSignals:
    """Batter detection signals use MATCH or AMBIGUOUS only."""

    def test_batter_signals_match(self, db: sqlite3.Connection) -> None:
        _insert_game(db, "game-bat")

        # Away pitcher
        _insert_pitching_boxscore(db, "game-bat", "pitcher-a1", 2, bf=2)
        # Home pitcher
        _insert_pitching_boxscore(db, "game-bat", "pitcher-h1", 1, bf=2)

        # Home batter: 1 AB, 1 H (Single)
        _insert_batting_boxscore(db, "game-bat", "batter-h1", 1, ab=1, h=1, so=0, bb=0)
        _insert_batting_boxscore(db, "game-bat", "batter-h2", 1, ab=0, h=0, so=0, bb=1, hbp=0)

        # Away batter
        _insert_batting_boxscore(db, "game-bat", "batter-a1", 2, ab=1, h=0, so=1)
        _insert_batting_boxscore(db, "game-bat", "batter-a2", 2, ab=1, h=0, so=0)

        # Bottom (home batting): batter-h1 singles, batter-h2 walks
        _insert_play(db, "game-bat", 1, inning=1, half="bottom",
                      batting_team_id=1, batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Single", pitch_count=2, did_outs_change=0,
                      home_score=0, away_score=0)
        _insert_play(db, "game-bat", 2, inning=1, half="bottom",
                      batting_team_id=1, batter_id="batter-h2", pitcher_id="pitcher-a1",
                      outcome="Walk", pitch_count=4, did_outs_change=0,
                      home_score=0, away_score=0)

        # Top (away batting)
        _insert_play(db, "game-bat", 3, inning=1, half="top",
                      batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Strikeout", pitch_count=3, did_outs_change=1,
                      home_score=0, away_score=0)
        _insert_play(db, "game-bat", 4, inning=1, half="top",
                      batting_team_id=2, batter_id="batter-a2", pitcher_id="pitcher-h1",
                      outcome="Groundout", pitch_count=2, did_outs_change=1,
                      home_score=0, away_score=0)

        summary = reconcile_game(db, "game-bat")

        # All batter signals should be MATCH
        for sig in ["batter_ab", "batter_h", "batter_so", "batter_bb", "batter_hbp"]:
            counts = summary.signal_counts.get(sig, {})
            non_match = sum(v for k, v in counts.items() if k != "MATCH")
            assert non_match == 0, f"Signal {sig} has non-MATCH entries: {counts}"

    def test_batter_ab_excludes_walks_and_hbp(self, db: sqlite3.Connection) -> None:
        """AB should exclude walks, HBP, sac fly, sac bunt, CI, IBB."""
        _insert_game(db, "game-ab-excl")

        _insert_pitching_boxscore(db, "game-ab-excl", "pitcher-h1", 1, bf=3)
        _insert_pitching_boxscore(db, "game-ab-excl", "pitcher-a1", 2, bf=1)

        # Batter with 0 AB: walk + HBP + sac fly
        _insert_batting_boxscore(db, "game-ab-excl", "batter-a1", 2, ab=0, h=0, bb=1, hbp=1)
        _insert_batting_boxscore(db, "game-ab-excl", "batter-a2", 2, ab=0, h=0, bb=0, hbp=0)

        _insert_batting_boxscore(db, "game-ab-excl", "batter-h1", 1, ab=1, h=0)

        _insert_play(db, "game-ab-excl", 1, inning=1, half="top",
                      batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Walk", pitch_count=4, did_outs_change=0)
        _insert_play(db, "game-ab-excl", 2, inning=1, half="top",
                      batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Hit By Pitch", pitch_count=1, did_outs_change=0)
        _insert_play(db, "game-ab-excl", 3, inning=1, half="top",
                      batting_team_id=2, batter_id="batter-a2", pitcher_id="pitcher-h1",
                      outcome="Sacrifice Fly", pitch_count=2, did_outs_change=1)

        _insert_play(db, "game-ab-excl", 4, inning=1, half="bottom",
                      batting_team_id=1, batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Groundout", pitch_count=2, did_outs_change=1)

        summary = reconcile_game(db, "game-ab-excl")
        ab_counts = summary.signal_counts.get("batter_ab", {})
        # Both batter-a1 (0 AB from exclusions) and batter-a2 (0 AB sac fly) should match
        non_match = sum(v for k, v in ab_counts.items() if k != "MATCH")
        assert non_match == 0, f"AB signal has non-MATCH: {ab_counts}"


class TestGameLevelSignals:
    """Game-level sanity checks produce one row per team."""

    def test_game_runs_and_hits(self, db: sqlite3.Connection) -> None:
        _insert_game(db, "game-gl")

        # Home pitcher
        _insert_pitching_boxscore(db, "game-gl", "pitcher-h1", 1, bf=2)
        # Away pitcher
        _insert_pitching_boxscore(db, "game-gl", "pitcher-a1", 2, bf=2)

        # Home batters: 2R, 1H total
        _insert_batting_boxscore(db, "game-gl", "batter-h1", 1, ab=1, r=2, h=1)
        _insert_batting_boxscore(db, "game-gl", "batter-h2", 1, ab=1, r=0, h=0)

        # Away batters: 0R, 1H total
        _insert_batting_boxscore(db, "game-gl", "batter-a1", 2, ab=1, r=0, h=1)
        _insert_batting_boxscore(db, "game-gl", "batter-a2", 2, ab=1, r=0, h=0)

        # Top: away batting
        _insert_play(db, "game-gl", 1, inning=1, half="top",
                      batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Single", pitch_count=2, did_outs_change=0,
                      home_score=0, away_score=0)
        _insert_play(db, "game-gl", 2, inning=1, half="top",
                      batting_team_id=2, batter_id="batter-a2", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1,
                      home_score=0, away_score=0)

        # Bottom: home batting -- final score 2-0
        _insert_play(db, "game-gl", 3, inning=1, half="bottom",
                      batting_team_id=1, batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Home Run", pitch_count=1, did_outs_change=0,
                      home_score=2, away_score=0)
        _insert_play(db, "game-gl", 4, inning=1, half="bottom",
                      batting_team_id=1, batter_id="batter-h2", pitcher_id="pitcher-a1",
                      outcome="Groundout", pitch_count=3, did_outs_change=1,
                      home_score=2, away_score=0)

        summary = reconcile_game(db, "game-gl")

        # game_runs: home=2 (match), away=0 (match)
        runs_counts = summary.signal_counts.get("game_runs", {})
        assert runs_counts.get("MATCH", 0) == 2, f"game_runs: {runs_counts}"

        # game_hits: home=1 (HR counts as hit), away=1 (Single)
        hits_counts = summary.signal_counts.get("game_hits", {})
        assert hits_counts.get("MATCH", 0) == 2, f"game_hits: {hits_counts}"

    def test_game_pa_count(self, db: sqlite3.Connection) -> None:
        """PA count: SUM(pitcher.bf) vs count of plays in that half."""
        _insert_game(db, "game-pa")

        # Home pitcher faced 3
        _insert_pitching_boxscore(db, "game-pa", "pitcher-h1", 1, bf=3)
        # Away pitcher faced 2
        _insert_pitching_boxscore(db, "game-pa", "pitcher-a1", 2, bf=2)

        _insert_batting_boxscore(db, "game-pa", "batter-h1", 1, ab=1)
        _insert_batting_boxscore(db, "game-pa", "batter-h2", 1, ab=1)
        _insert_batting_boxscore(db, "game-pa", "batter-a1", 2, ab=2)
        _insert_batting_boxscore(db, "game-pa", "batter-a2", 2, ab=1)

        # 3 plays in top (home pitching) -- matches bf=3
        _insert_play(db, "game-pa", 1, half="top", batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1", outcome="Flyout")
        _insert_play(db, "game-pa", 2, half="top", batting_team_id=2, batter_id="batter-a2", pitcher_id="pitcher-h1", outcome="Groundout")
        _insert_play(db, "game-pa", 3, half="top", batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1", outcome="Flyout")

        # 2 plays in bottom (away pitching) -- matches bf=2
        _insert_play(db, "game-pa", 4, half="bottom", batting_team_id=1, batter_id="batter-h1", pitcher_id="pitcher-a1", outcome="Flyout")
        _insert_play(db, "game-pa", 5, half="bottom", batting_team_id=1, batter_id="batter-h2", pitcher_id="pitcher-a1", outcome="Groundout")

        summary = reconcile_game(db, "game-pa")
        pa_counts = summary.signal_counts.get("game_pa_count", {})
        assert pa_counts.get("MATCH", 0) == 2, f"game_pa_count: {pa_counts}"


class TestIPOutsAlwaysAmbiguous:
    """IP/outs signal should always be AMBIGUOUS when delta != 0."""

    def test_ip_outs_ambiguous_on_mismatch(self, db: sqlite3.Connection) -> None:
        _insert_game(db, "game-ip")

        # Boxscore says 6 outs (2 IP), plays only see 5 did_outs_change
        _insert_pitching_boxscore(db, "game-ip", "pitcher-h1", 1, ip_outs=6, bf=5)
        _insert_pitching_boxscore(db, "game-ip", "pitcher-a1", 2, bf=3)

        _insert_batting_boxscore(db, "game-ip", "batter-h1", 1, ab=2)
        _insert_batting_boxscore(db, "game-ip", "batter-h2", 1, ab=1)
        _insert_batting_boxscore(db, "game-ip", "batter-a1", 2, ab=3)
        _insert_batting_boxscore(db, "game-ip", "batter-a2", 2, ab=2)

        for i in range(1, 6):
            _insert_play(db, "game-ip", i, half="top", batting_team_id=2,
                          batter_id="batter-a1", pitcher_id="pitcher-h1",
                          outcome="Groundout", did_outs_change=1)
        for i in range(6, 9):
            _insert_play(db, "game-ip", i, half="bottom", batting_team_id=1,
                          batter_id="batter-h1", pitcher_id="pitcher-a1",
                          outcome="Flyout", did_outs_change=1)

        summary = reconcile_game(db, "game-ip")
        ip_counts = summary.signal_counts.get("pitcher_ip_outs", {})
        # pitcher-h1: boxscore=6, plays=5 -> AMBIGUOUS
        assert "AMBIGUOUS" in ip_counts, f"pitcher_ip_outs: {ip_counts}"


class TestWPAlwaysAmbiguous:
    """WP signal should always be AMBIGUOUS when delta != 0."""

    def test_wp_ambiguous_on_mismatch(self, db: sqlite3.Connection) -> None:
        _insert_game(db, "game-wp")

        _insert_pitching_boxscore(db, "game-wp", "pitcher-h1", 1, bf=2, wp=2)
        _insert_pitching_boxscore(db, "game-wp", "pitcher-a1", 2, bf=1)

        _insert_batting_boxscore(db, "game-wp", "batter-a1", 2, ab=2)
        _insert_batting_boxscore(db, "game-wp", "batter-h1", 1, ab=1)

        p1 = _insert_play(db, "game-wp", 1, half="top", batting_team_id=2,
                           batter_id="batter-a1", pitcher_id="pitcher-h1",
                           outcome="Groundout")
        # Only one WP template found, but boxscore says 2
        _insert_play_event(db, p1, 1, event_type="baserunner",
                           raw_template="advances to 2nd on wild pitch")
        _insert_play(db, "game-wp", 2, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Flyout")

        _insert_play(db, "game-wp", 3, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout")

        summary = reconcile_game(db, "game-wp")
        wp_counts = summary.signal_counts.get("pitcher_wp", {})
        # boxscore=2, plays=1 -> AMBIGUOUS
        assert "AMBIGUOUS" in wp_counts, f"pitcher_wp: {wp_counts}"


class TestCLISmokeTest:
    """Verify the reconcile command is registered and callable."""

    def test_reconcile_command_exists(self) -> None:
        """Verify the reconcile command is registered in the data app."""
        from src.cli.data import app

        command_names = [cmd.name for cmd in app.registered_commands]
        assert "reconcile" in command_names


class TestReconcileAll:
    """Test reconcile_all processes multiple games."""

    def test_processes_all_games_with_plays(self, db: sqlite3.Connection) -> None:
        for gid in ("game-a", "game-b"):
            _insert_game(db, gid)
            _insert_pitching_boxscore(db, gid, "pitcher-h1", 1, bf=1)
            _insert_pitching_boxscore(db, gid, "pitcher-a1", 2, bf=1)
            _insert_batting_boxscore(db, gid, "batter-h1", 1, ab=1)
            _insert_batting_boxscore(db, gid, "batter-a1", 2, ab=1)
            _insert_play(db, gid, 1, half="top", batting_team_id=2,
                          batter_id="batter-a1", pitcher_id="pitcher-h1",
                          outcome="Flyout")
            _insert_play(db, gid, 2, half="bottom", batting_team_id=1,
                          batter_id="batter-h1", pitcher_id="pitcher-a1",
                          outcome="Groundout")

        summary = reconcile_all(db)
        assert summary.games_processed == 2
        assert summary.games_skipped_no_plays == 0

    def test_per_game_outcome_counts(self, db: sqlite3.Connection) -> None:
        """reconcile_all tracks games_all_match, games_with_correctable, games_with_ambiguous."""
        # game-match: everything matches (all boxscore values align with plays)
        _insert_game(db, "game-match")
        _insert_pitching_boxscore(db, "game-match", "pitcher-h1", 1,
                                   bf=1, ip_outs=1, pitches=3)
        _insert_pitching_boxscore(db, "game-match", "pitcher-a1", 2,
                                   bf=1, ip_outs=1, pitches=3)
        _insert_batting_boxscore(db, "game-match", "batter-h1", 1, ab=1)
        _insert_batting_boxscore(db, "game-match", "batter-a1", 2, ab=1)
        _insert_play(db, "game-match", 1, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-match", 2, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Groundout", pitch_count=3, did_outs_change=1)

        # game-drift: BF mismatch -> CORRECTABLE
        _insert_game(db, "game-drift")
        _insert_pitching_boxscore(db, "game-drift", "pitcher-h1", 1, bf=1)
        _insert_pitching_boxscore(db, "game-drift", "pitcher-h2", 1, bf=1)
        _insert_pitching_boxscore(db, "game-drift", "pitcher-a1", 2, bf=1)
        _insert_batting_boxscore(db, "game-drift", "batter-h1", 1, ab=1)
        _insert_batting_boxscore(db, "game-drift", "batter-a1", 2, ab=1)
        _insert_batting_boxscore(db, "game-drift", "batter-a2", 2, ab=1)
        # Both plays attributed to pitcher-h1 (should be 1 each)
        _insert_play(db, "game-drift", 1, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Flyout", did_outs_change=1)
        _insert_play(db, "game-drift", 2, half="top", batting_team_id=2,
                      batter_id="batter-a2", pitcher_id="pitcher-h1",
                      outcome="Groundout", did_outs_change=1)
        _insert_play(db, "game-drift", 3, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", did_outs_change=1)

        summary = reconcile_all(db)
        assert summary.games_processed == 2
        assert summary.games_all_match >= 1  # game-match
        assert summary.games_with_correctable >= 1  # game-drift


class TestCLIErrorPath:
    """CLI reconcile command handles errors gracefully."""

    def test_reconcile_game_db_error(self, tmp_path: Path) -> None:
        """reconcile_game raises when the database is missing required tables."""
        from src.reconciliation.engine import reconcile_game

        bad_db = sqlite3.connect(":memory:")
        # No tables at all -- querying plays will fail
        with pytest.raises(sqlite3.OperationalError):
            reconcile_game(bad_db, "nonexistent-game")


# ---------------------------------------------------------------------------
# E-198-02: Correction tests
# ---------------------------------------------------------------------------


class TestPitcherCorrection:
    """Tests for pitcher attribution correction (execute mode)."""

    def test_correction_reassigns_pitcher_ids(self, db: sqlite3.Connection) -> None:
        """BF-boundary correction reassigns misattributed plays."""
        _insert_game(db, "game-fix")

        # Boxscore: pitcher-h1 faced 2, pitcher-h2 faced 1
        _insert_pitching_boxscore(db, "game-fix", "pitcher-h1", 1,
                                   bf=2, so=1, pitches=6, ip_outs=2)
        _insert_pitching_boxscore(db, "game-fix", "pitcher-h2", 1,
                                   bf=1, so=0, pitches=3, ip_outs=1)
        # Away pitcher
        _insert_pitching_boxscore(db, "game-fix", "pitcher-a1", 2,
                                   bf=2, pitches=6, ip_outs=2)

        # Batting boxscores
        _insert_batting_boxscore(db, "game-fix", "batter-h1", 1, ab=1)
        _insert_batting_boxscore(db, "game-fix", "batter-h2", 1, ab=1)
        _insert_batting_boxscore(db, "game-fix", "batter-a1", 2, ab=2)
        _insert_batting_boxscore(db, "game-fix", "batter-a2", 2, ab=1)

        # Plays: all 3 top-half plays misattributed to pitcher-h1
        # Play 3 should be pitcher-h2 per BF boundary
        _insert_play(db, "game-fix", 1, inning=1, half="top",
                      batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Strikeout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-fix", 2, inning=1, half="top",
                      batting_team_id=2, batter_id="batter-a2", pitcher_id="pitcher-h1",
                      outcome="Groundout", pitch_count=3, did_outs_change=1)
        # This one is misattributed -- should be pitcher-h2
        _insert_play(db, "game-fix", 3, inning=1, half="top",
                      batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)

        # Bottom half
        _insert_play(db, "game-fix", 4, inning=1, half="bottom",
                      batting_team_id=1, batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-fix", 5, inning=1, half="bottom",
                      batting_team_id=1, batter_id="batter-h2", pitcher_id="pitcher-a1",
                      outcome="Groundout", pitch_count=3, did_outs_change=1)

        # Execute mode
        summary = reconcile_game(db, "game-fix", dry_run=False)

        assert summary.games_processed == 1
        assert summary.total_plays_reassigned == 1

        # Verify the play was corrected in the DB
        corrected = db.execute(
            "SELECT pitcher_id FROM plays WHERE game_id = 'game-fix' AND play_order = 3"
        ).fetchone()
        assert corrected[0] == "pitcher-h2"

        # BF should now match -- signals that were CORRECTABLE are now CORRECTED
        bf_counts = summary.signal_counts.get("pitcher_bf", {})
        assert bf_counts.get("CORRECTED", 0) > 0 or bf_counts.get("MATCH", 0) >= 2

        # Verify CORRECTED rows have correction_detail populated
        corrected_signals = [
            (sig, counts) for sig, counts in summary.signal_counts.items()
            if counts.get("CORRECTED", 0) > 0
        ]
        assert len(corrected_signals) > 0, "Expected at least one CORRECTED signal"

        # Away team pitcher (pitcher-a1) should NOT be CORRECTED -- was already correct
        # This validates Fix #1: per-(signal, team, player) status tracking
        # pitcher-a1 BF was MATCH pre-correction and should stay MATCH (not CORRECTED)
        assert summary.signal_counts.get("pitcher_bf", {}).get("MATCH", 0) >= 1

    def test_correction_idempotent(self, db: sqlite3.Connection) -> None:
        """Running correction twice produces the same result."""
        _insert_game(db, "game-idem")

        _insert_pitching_boxscore(db, "game-idem", "pitcher-h1", 1,
                                   bf=1, pitches=3, ip_outs=1)
        _insert_pitching_boxscore(db, "game-idem", "pitcher-h2", 1,
                                   bf=1, pitches=3, ip_outs=1)
        _insert_pitching_boxscore(db, "game-idem", "pitcher-a1", 2,
                                   bf=1, pitches=3, ip_outs=1)

        _insert_batting_boxscore(db, "game-idem", "batter-h1", 1, ab=1)
        _insert_batting_boxscore(db, "game-idem", "batter-a1", 2, ab=1)
        _insert_batting_boxscore(db, "game-idem", "batter-a2", 2, ab=1)

        # Play 2 misattributed
        _insert_play(db, "game-idem", 1, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-idem", 2, half="top", batting_team_id=2,
                      batter_id="batter-a2", pitcher_id="pitcher-h1",
                      outcome="Groundout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-idem", 3, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)

        # First run
        s1 = reconcile_game(db, "game-idem", dry_run=False)
        assert s1.total_plays_reassigned == 1

        # Second run -- should be idempotent (0 reassigned)
        s2 = reconcile_game(db, "game-idem", dry_run=False)
        assert s2.total_plays_reassigned == 0

        # Verify the DB still has the correct pitcher
        row = db.execute(
            "SELECT pitcher_id FROM plays WHERE game_id = 'game-idem' AND play_order = 2"
        ).fetchone()
        assert row[0] == "pitcher-h2"


class TestCorrectionEdgeCases:
    """Edge cases for the correction algorithm."""

    def test_single_pitcher_no_correction(self, db: sqlite3.Connection) -> None:
        """Single pitcher per team: no boundary to correct, skip."""
        _insert_game(db, "game-single")

        _insert_pitching_boxscore(db, "game-single", "pitcher-h1", 1,
                                   bf=2, pitches=6, ip_outs=2)
        _insert_pitching_boxscore(db, "game-single", "pitcher-a1", 2,
                                   bf=1, pitches=3, ip_outs=1)

        _insert_batting_boxscore(db, "game-single", "batter-h1", 1, ab=1)
        _insert_batting_boxscore(db, "game-single", "batter-a1", 2, ab=2)

        _insert_play(db, "game-single", 1, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-single", 2, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Groundout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-single", 3, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)

        summary = reconcile_game(db, "game-single", dry_run=False)
        assert summary.total_plays_reassigned == 0

    def test_pitcher_reentry_skips_correction(
        self, db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pitcher re-entry (duplicate in order): skip correction."""
        import src.reconciliation.engine as engine_mod

        _insert_game(db, "game-reentry")

        # Two pitchers in boxscore, but JSON order will have re-entry
        _insert_pitching_boxscore(db, "game-reentry", "pitcher-h1", 1,
                                   bf=2, pitches=6, ip_outs=2)
        _insert_pitching_boxscore(db, "game-reentry", "pitcher-h2", 1,
                                   bf=1, pitches=3, ip_outs=1)
        _insert_pitching_boxscore(db, "game-reentry", "pitcher-a1", 2,
                                   bf=2, pitches=6, ip_outs=2)

        _insert_batting_boxscore(db, "game-reentry", "batter-h1", 1, ab=1)
        _insert_batting_boxscore(db, "game-reentry", "batter-h2", 1, ab=1)
        _insert_batting_boxscore(db, "game-reentry", "batter-a1", 2, ab=2)
        _insert_batting_boxscore(db, "game-reentry", "batter-a2", 2, ab=1)

        _insert_play(db, "game-reentry", 1, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-reentry", 2, half="top", batting_team_id=2,
                      batter_id="batter-a2", pitcher_id="pitcher-h2",
                      outcome="Groundout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-reentry", 3, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-reentry", 4, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-reentry", 5, half="bottom", batting_team_id=1,
                      batter_id="batter-h2", pitcher_id="pitcher-a1",
                      outcome="Groundout", pitch_count=3, did_outs_change=1)

        # Monkeypatch _extract_pitcher_order to return re-entry order for home team
        original_extract = engine_mod._extract_pitcher_order

        def _mock_extract(conn, game_id, game_stream_id, season_id, team_id, is_home):
            if team_id == 1:  # Home team: simulate re-entry
                return [
                    {"player_id": "pitcher-h1"},
                    {"player_id": "pitcher-h2"},
                    {"player_id": "pitcher-h1"},  # re-entry
                ]
            return original_extract(conn, game_id, game_stream_id, season_id, team_id, is_home)

        monkeypatch.setattr(engine_mod, "_extract_pitcher_order", _mock_extract)

        summary = reconcile_game(db, "game-reentry", dry_run=False)
        # Home team correction should be skipped due to re-entry
        assert summary.total_plays_reassigned == 0

    def test_bf_total_mismatch_skips_correction(self, db: sqlite3.Connection) -> None:
        """When boxscore BF total doesn't match plays count, skip correction."""
        _insert_game(db, "game-bf-mismatch")

        # Boxscore says 4 total BF, but only 3 plays exist
        _insert_pitching_boxscore(db, "game-bf-mismatch", "pitcher-h1", 1,
                                   bf=3, pitches=9, ip_outs=2)
        _insert_pitching_boxscore(db, "game-bf-mismatch", "pitcher-h2", 1,
                                   bf=1, pitches=3, ip_outs=1)
        _insert_pitching_boxscore(db, "game-bf-mismatch", "pitcher-a1", 2,
                                   bf=2, pitches=6, ip_outs=2)

        _insert_batting_boxscore(db, "game-bf-mismatch", "batter-h1", 1, ab=1)
        _insert_batting_boxscore(db, "game-bf-mismatch", "batter-h2", 1, ab=1)
        _insert_batting_boxscore(db, "game-bf-mismatch", "batter-a1", 2, ab=2)
        _insert_batting_boxscore(db, "game-bf-mismatch", "batter-a2", 2, ab=1)

        # Only 3 top-half plays but BF total is 4
        _insert_play(db, "game-bf-mismatch", 1, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-bf-mismatch", 2, half="top", batting_team_id=2,
                      batter_id="batter-a2", pitcher_id="pitcher-h1",
                      outcome="Groundout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-bf-mismatch", 3, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-bf-mismatch", 4, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-bf-mismatch", 5, half="bottom", batting_team_id=1,
                      batter_id="batter-h2", pitcher_id="pitcher-a1",
                      outcome="Groundout", pitch_count=3, did_outs_change=1)

        summary = reconcile_game(db, "game-bf-mismatch", dry_run=False)
        # Correction should be skipped due to BF total mismatch
        assert summary.total_plays_reassigned == 0


class TestGetSummaryFromDB:
    """Test the --summary aggregate query."""

    def test_summary_from_empty_db(self, db: sqlite3.Connection) -> None:
        """No reconciliation records should produce zero counts."""
        from src.reconciliation.engine import get_summary_from_db

        # Create the discrepancy table
        db.execute("""
            CREATE TABLE IF NOT EXISTS reconciliation_discrepancies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                team_id INTEGER NOT NULL,
                player_id TEXT NOT NULL,
                signal_name TEXT NOT NULL,
                category TEXT NOT NULL,
                boxscore_value INTEGER,
                plays_value INTEGER,
                delta INTEGER,
                status TEXT NOT NULL,
                correction_detail TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(run_id, game_id, team_id, player_id, signal_name)
            )
        """)

        result = get_summary_from_db(db)
        assert result["total_records"] == 0
        assert result["total_corrected"] == 0

    def test_summary_from_populated_db(self, db: sqlite3.Connection) -> None:
        """Summary reflects data across all runs."""
        from src.reconciliation.engine import get_summary_from_db

        db.execute("""
            CREATE TABLE IF NOT EXISTS reconciliation_discrepancies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                team_id INTEGER NOT NULL,
                player_id TEXT NOT NULL,
                signal_name TEXT NOT NULL,
                category TEXT NOT NULL,
                boxscore_value INTEGER,
                plays_value INTEGER,
                delta INTEGER,
                status TEXT NOT NULL,
                correction_detail TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(run_id, game_id, team_id, player_id, signal_name)
            )
        """)

        # Insert some records
        db.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(game_id, run_id, team_id, player_id, signal_name, category, "
            "boxscore_value, plays_value, delta, status) "
            "VALUES ('g1', 'r1', 1, 'p1', 'pitcher_bf', 'pitcher', 5, 5, 0, 'MATCH')"
        )
        db.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(game_id, run_id, team_id, player_id, signal_name, category, "
            "boxscore_value, plays_value, delta, status) "
            "VALUES ('g1', 'r1', 1, 'p1', 'pitcher_so', 'pitcher', 3, 2, 1, 'CORRECTED')"
        )

        result = get_summary_from_db(db)
        assert result["total_records"] == 2
        assert result["total_corrected"] == 1
        assert result["pitcher_signals"]["pitcher_bf"]["MATCH"] == 1
        assert result["pitcher_signals"]["pitcher_so"]["CORRECTED"] == 1
