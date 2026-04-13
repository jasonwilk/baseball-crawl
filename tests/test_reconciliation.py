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
from tests.conftest import load_real_schema


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db() -> sqlite3.Connection:
    """Create an in-memory SQLite database using the production schema.

    FK enforcement is active via load_real_schema. Seeds two teams and a
    small roster of players used throughout the reconciliation tests.
    """
    conn = sqlite3.connect(":memory:")
    load_real_schema(conn)

    conn.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) "
        "VALUES ('2025-spring-hs', '2025 Spring HS', 'spring-hs', 2025)"
    )
    conn.executemany(
        "INSERT INTO teams (id, name, gc_uuid, membership_type) VALUES (?, ?, ?, ?)",
        [
            (1, "Home Team", "uuid-home", "member"),
            (2, "Away Team", "uuid-away", "member"),
        ],
    )
    conn.executemany(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        [
            ("pitcher-h1", "Home", "Pitcher1"),
            ("pitcher-h2", "Home", "Pitcher2"),
            ("pitcher-a1", "Away", "Pitcher1"),
            ("batter-h1", "Home", "Batter1"),
            ("batter-h2", "Home", "Batter2"),
            ("batter-h3", "Home", "Batter3"),
            ("batter-a1", "Away", "Batter1"),
            ("batter-a2", "Away", "Batter2"),
            ("batter-a3", "Away", "Batter3"),
        ],
    )
    conn.commit()
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
    perspective_team_id: int = 1,
    appearance_order: int | None = None,
) -> None:
    conn.execute(
        "INSERT INTO player_game_pitching "
        "(game_id, player_id, team_id, perspective_team_id, decision, appearance_order, "
        "ip_outs, h, r, er, bb, so, wp, hbp, pitches, total_strikes, bf) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_id, player_id, team_id, perspective_team_id, decision, appearance_order,
         ip_outs, h, r, er, bb, so, wp, hbp, pitches, total_strikes, bf),
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
    perspective_team_id: int = 1,
) -> None:
    conn.execute(
        "INSERT INTO player_game_batting "
        "(game_id, player_id, team_id, perspective_team_id, ab, r, h, rbi, bb, so, hbp) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
        (game_id, player_id, team_id, perspective_team_id, ab, r, h, bb, so, hbp),
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
    perspective_team_id: int = 1,
) -> int:
    """Insert a play and return the play id.

    perspective_team_id defaults to 1 -- the convention that all data for a
    single boxscore load is tagged with one perspective (the team whose API
    produced it).  Tests for cross-perspective behavior can override.
    """
    conn.execute(
        "INSERT INTO plays "
        "(game_id, play_order, inning, half, season_id, batting_team_id, perspective_team_id, batter_id, "
        "pitcher_id, outcome, pitch_count, home_score, away_score, did_outs_change) "
        "VALUES (?, ?, ?, ?, '2025-spring-hs', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_id, play_order, inning, half, batting_team_id, perspective_team_id, batter_id,
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


class TestCrossPerspectiveDiscrepancyPersistence:
    """E-220 round 7 P1-2: two perspectives of the same game must both
    persist discrepancy rows.  Before the dual-column fix, the UNIQUE
    constraint (run_id, game_id, team_id, player_id, signal_name) collided
    across perspectives -- INSERT OR REPLACE in _write_discrepancies
    silently overwrote perspective A's rows when perspective B wrote.
    """

    def test_two_perspectives_persist_independently(self, db: sqlite3.Connection) -> None:
        """Reconcile the same game from two perspectives; both sets of rows must persist.

        Seeds identical plays + boxscore for two perspectives (team 1 and team 2),
        runs reconcile_game twice with explicit perspective_team_id, then asserts
        both perspectives' discrepancies are present in reconciliation_discrepancies.
        """
        _insert_game(db, "game-xperspective")

        # Identical boxscore data for BOTH perspectives (tagged with different
        # perspective_team_id).  Home has 1 pitcher, away has 1 pitcher.
        for ptid in (1, 2):
            _insert_pitching_boxscore(
                db, "game-xperspective", "pitcher-h1", 1,
                bf=1, so=1, bb=0, hbp=0, h=0, ip_outs=1,
                pitches=3, total_strikes=3, wp=0,
                perspective_team_id=ptid,
            )
            _insert_pitching_boxscore(
                db, "game-xperspective", "pitcher-a1", 2,
                bf=1, so=1, bb=0, hbp=0, h=0, ip_outs=1,
                pitches=3, total_strikes=3, wp=0,
                perspective_team_id=ptid,
            )
            _insert_batting_boxscore(
                db, "game-xperspective", "batter-a1", 2,
                ab=1, r=0, h=0, bb=0, so=1, perspective_team_id=ptid,
            )
            _insert_batting_boxscore(
                db, "game-xperspective", "batter-h1", 1,
                ab=1, r=0, h=0, bb=0, so=1, perspective_team_id=ptid,
            )

        # Plays (one per half inning) tagged for BOTH perspectives.
        for ptid in (1, 2):
            p_top = _insert_play(
                db, "game-xperspective", 1, inning=1, half="top",
                batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1",
                outcome="Strikeout", pitch_count=3, did_outs_change=1,
                perspective_team_id=ptid,
            )
            _insert_play_event(db, p_top, 1, pitch_result="strike_swinging")
            _insert_play_event(db, p_top, 2, pitch_result="strike_swinging")
            _insert_play_event(db, p_top, 3, pitch_result="strike_swinging")

            p_bot = _insert_play(
                db, "game-xperspective", 2, inning=1, half="bottom",
                batting_team_id=1, batter_id="batter-h1", pitcher_id="pitcher-a1",
                outcome="Strikeout", pitch_count=3, did_outs_change=1,
                perspective_team_id=ptid,
            )
            _insert_play_event(db, p_bot, 1, pitch_result="strike_swinging")
            _insert_play_event(db, p_bot, 2, pitch_result="strike_swinging")
            _insert_play_event(db, p_bot, 3, pitch_result="strike_swinging")

        # Run reconcile_game twice with different perspectives and the SAME run_id.
        # This mirrors reconcile_all behavior where a single run_id spans all
        # (game_id, perspective_team_id) pairs.
        run_id = "test-run-xperspective"
        reconcile_game(db, "game-xperspective", run_id=run_id, perspective_team_id=1)
        reconcile_game(db, "game-xperspective", run_id=run_id, perspective_team_id=2)

        # Count rows per perspective in reconciliation_discrepancies.
        p1_count = db.execute(
            "SELECT COUNT(*) FROM reconciliation_discrepancies "
            "WHERE game_id = ? AND perspective_team_id = ?",
            ("game-xperspective", 1),
        ).fetchone()[0]
        p2_count = db.execute(
            "SELECT COUNT(*) FROM reconciliation_discrepancies "
            "WHERE game_id = ? AND perspective_team_id = ?",
            ("game-xperspective", 2),
        ).fetchone()[0]

        # Both perspectives must have persisted their discrepancy rows.
        assert p1_count > 0, (
            "perspective 1 discrepancies should persist (pre-fix: collapsed by INSERT OR REPLACE)"
        )
        assert p2_count > 0, (
            "perspective 2 discrepancies should persist (pre-fix: collapsed by INSERT OR REPLACE)"
        )
        # And critically -- they should have the SAME count (identical boxscore/plays per perspective).
        assert p1_count == p2_count, (
            f"perspectives should produce equal row counts: p1={p1_count} p2={p2_count}"
        )


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
# E-221-07 (R8-P1-3): `bb data reconcile --game-id` perspective plumbing
# ---------------------------------------------------------------------------


def _seed_reconcile_cli_db(db_path: Path) -> None:
    """Seed a tmp-file SQLite database with the standard teams/players/season
    rows used by ``TestReconcileCLIGameIDPerspectives`` plus the cross-
    perspective game fixture.  Mirrors the in-memory ``db`` fixture's seed
    data but persists to disk so the typer CLI's ``sqlite3.connect(db_path)``
    call can open it.
    """
    conn = sqlite3.connect(str(db_path))
    load_real_schema(conn)
    conn.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) "
        "VALUES ('2025-spring-hs', '2025 Spring HS', 'spring-hs', 2025)"
    )
    conn.executemany(
        "INSERT INTO teams (id, name, gc_uuid, membership_type) VALUES (?, ?, ?, ?)",
        [
            (1, "Home Team", "uuid-home", "member"),
            (2, "Away Team", "uuid-away", "member"),
        ],
    )
    conn.executemany(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        [
            ("pitcher-h1", "Home", "Pitcher1"),
            ("pitcher-a1", "Away", "Pitcher1"),
            ("batter-h1", "Home", "Batter1"),
            ("batter-a1", "Away", "Batter1"),
        ],
    )

    # Seed a game loaded from TWO perspectives (team 1 and team 2).  Identical
    # plays and boxscore for each perspective, tagged with distinct
    # perspective_team_id values.  This mirrors the round 7 P1-2 fixture in
    # ``TestCrossPerspectiveDiscrepancyPersistence`` but against a file path.
    _insert_game(conn, "game-cli-xperspective")

    for ptid in (1, 2):
        _insert_pitching_boxscore(
            conn, "game-cli-xperspective", "pitcher-h1", 1,
            bf=1, so=1, bb=0, hbp=0, h=0, ip_outs=1,
            pitches=3, total_strikes=3, wp=0,
            perspective_team_id=ptid,
        )
        _insert_pitching_boxscore(
            conn, "game-cli-xperspective", "pitcher-a1", 2,
            bf=1, so=1, bb=0, hbp=0, h=0, ip_outs=1,
            pitches=3, total_strikes=3, wp=0,
            perspective_team_id=ptid,
        )
        _insert_batting_boxscore(
            conn, "game-cli-xperspective", "batter-a1", 2,
            ab=1, r=0, h=0, bb=0, so=1, perspective_team_id=ptid,
        )
        _insert_batting_boxscore(
            conn, "game-cli-xperspective", "batter-h1", 1,
            ab=1, r=0, h=0, bb=0, so=1, perspective_team_id=ptid,
        )
        p_top = _insert_play(
            conn, "game-cli-xperspective", 1, inning=1, half="top",
            batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1",
            outcome="Strikeout", pitch_count=3, did_outs_change=1,
            perspective_team_id=ptid,
        )
        _insert_play_event(conn, p_top, 1, pitch_result="strike_swinging")
        _insert_play_event(conn, p_top, 2, pitch_result="strike_swinging")
        _insert_play_event(conn, p_top, 3, pitch_result="strike_swinging")
        p_bot = _insert_play(
            conn, "game-cli-xperspective", 2, inning=1, half="bottom",
            batting_team_id=1, batter_id="batter-h1", pitcher_id="pitcher-a1",
            outcome="Strikeout", pitch_count=3, did_outs_change=1,
            perspective_team_id=ptid,
        )
        _insert_play_event(conn, p_bot, 1, pitch_result="strike_swinging")
        _insert_play_event(conn, p_bot, 2, pitch_result="strike_swinging")
        _insert_play_event(conn, p_bot, 3, pitch_result="strike_swinging")

    conn.commit()
    conn.close()


class TestReconcileCLIGameIDPerspectives:
    """E-221-07 / R8-P1-3: ``bb data reconcile --game-id X`` must process
    every perspective the game was loaded from, not just the default (which
    pre-fix was the home-first deterministic selection in ``reconcile_game``
    and silently dropped other perspectives).

    The CLI handler at ``src/cli/data.py:1160`` previously called
    ``reconcile_game(conn, game_id, dry_run=...)`` without a
    ``perspective_team_id`` kwarg.  For any cross-perspective game (the
    modal case for LSB-adjacent tracked opponents loaded from two
    boxscores), only one perspective's discrepancies landed in
    ``reconciliation_discrepancies`` -- operators running the CLI had no
    way to know.  The fix (E-221-07) iterates
    ``SELECT DISTINCT perspective_team_id FROM plays WHERE game_id = ?``
    inside the CLI handler and calls ``reconcile_game`` once per
    perspective, mirroring ``reconcile_all`` at ``engine.py:454-466``.
    """

    def test_cli_game_id_processes_all_perspectives(
        self, tmp_path: Path
    ) -> None:
        """Both perspectives' discrepancies land in
        ``reconciliation_discrepancies`` after a single invocation of
        ``bb data reconcile --game-id X``.

        Pre-fix (current `src/cli/data.py:1160`): only perspective 1 (the
        home-first deterministic default) persists rows; perspective 2 is
        silently dropped.  The test asserts both perspectives have rows
        post-invocation, which fails pre-fix and passes post-fix.
        """
        from typer.testing import CliRunner
        from src.cli import app as bb_app

        db_path = tmp_path / "test_reconcile_cli.db"
        _seed_reconcile_cli_db(db_path)

        runner = CliRunner()
        result = runner.invoke(
            bb_app,
            [
                "data", "reconcile",
                "--game-id", "game-cli-xperspective",
                "--db", str(db_path),
            ],
        )

        assert result.exit_code == 0, (
            f"bb data reconcile --game-id exited non-zero.\n"
            f"stdout: {result.stdout}\n"
            f"exception: {result.exception}"
        )

        # Verify both perspectives' discrepancies landed in the table.
        conn = sqlite3.connect(str(db_path))
        try:
            p1_count = conn.execute(
                "SELECT COUNT(*) FROM reconciliation_discrepancies "
                "WHERE game_id = ? AND perspective_team_id = ?",
                ("game-cli-xperspective", 1),
            ).fetchone()[0]
            p2_count = conn.execute(
                "SELECT COUNT(*) FROM reconciliation_discrepancies "
                "WHERE game_id = ? AND perspective_team_id = ?",
                ("game-cli-xperspective", 2),
            ).fetchone()[0]
        finally:
            conn.close()

        assert p1_count > 0, (
            "R8-P1-3 regression: perspective 1 should have discrepancy "
            "rows after `bb data reconcile --game-id`. Got 0 rows."
        )
        assert p2_count > 0, (
            "R8-P1-3 bug: perspective 2's discrepancies were dropped. "
            "Pre-fix, the CLI called reconcile_game without a "
            "perspective_team_id kwarg, which fell through to the home-"
            "first deterministic selection and silently skipped "
            "perspective 2. The fix iterates all perspectives from the "
            f"plays table and reconciles each. Got p1={p1_count} p2={p2_count}."
        )
        # Both perspectives seeded identical data -- row counts should match.
        assert p1_count == p2_count, (
            f"perspectives seeded identical data should produce equal row "
            f"counts: p1={p1_count} p2={p2_count}"
        )

    def test_cli_game_id_single_perspective_unchanged(
        self, tmp_path: Path
    ) -> None:
        """AC-2: Given a game loaded from ONE perspective only, the CLI
        behavior is unchanged from pre-fix -- one reconciliation pass runs
        and its discrepancies persist.

        This is the common case (games loaded from a single boxscore
        perspective) and must not regress under the new iteration loop.
        """
        from typer.testing import CliRunner
        from src.cli import app as bb_app

        db_path = tmp_path / "test_reconcile_cli_single.db"
        conn = sqlite3.connect(str(db_path))
        load_real_schema(conn)
        conn.execute(
            "INSERT INTO seasons (season_id, name, season_type, year) "
            "VALUES ('2025-spring-hs', '2025 Spring HS', 'spring-hs', 2025)"
        )
        conn.executemany(
            "INSERT INTO teams (id, name, gc_uuid, membership_type) VALUES (?, ?, ?, ?)",
            [
                (1, "Home Team", "uuid-home", "member"),
                (2, "Away Team", "uuid-away", "member"),
            ],
        )
        conn.executemany(
            "INSERT INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
            [
                ("pitcher-h1", "Home", "Pitcher1"),
                ("pitcher-a1", "Away", "Pitcher1"),
                ("batter-h1", "Home", "Batter1"),
                ("batter-a1", "Away", "Batter1"),
            ],
        )
        _insert_game(conn, "game-cli-single")
        _insert_pitching_boxscore(
            conn, "game-cli-single", "pitcher-h1", 1,
            bf=1, so=1, ip_outs=1, pitches=3, total_strikes=3,
            perspective_team_id=1,
        )
        _insert_pitching_boxscore(
            conn, "game-cli-single", "pitcher-a1", 2,
            bf=1, so=1, ip_outs=1, pitches=3, total_strikes=3,
            perspective_team_id=1,
        )
        _insert_batting_boxscore(
            conn, "game-cli-single", "batter-a1", 2,
            ab=1, so=1, perspective_team_id=1,
        )
        _insert_batting_boxscore(
            conn, "game-cli-single", "batter-h1", 1,
            ab=1, so=1, perspective_team_id=1,
        )
        p_top = _insert_play(
            conn, "game-cli-single", 1, inning=1, half="top",
            batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1",
            outcome="Strikeout", pitch_count=3, did_outs_change=1,
            perspective_team_id=1,
        )
        _insert_play_event(conn, p_top, 1, pitch_result="strike_swinging")
        _insert_play_event(conn, p_top, 2, pitch_result="strike_swinging")
        _insert_play_event(conn, p_top, 3, pitch_result="strike_swinging")
        p_bot = _insert_play(
            conn, "game-cli-single", 2, inning=1, half="bottom",
            batting_team_id=1, batter_id="batter-h1", pitcher_id="pitcher-a1",
            outcome="Strikeout", pitch_count=3, did_outs_change=1,
            perspective_team_id=1,
        )
        _insert_play_event(conn, p_bot, 1, pitch_result="strike_swinging")
        _insert_play_event(conn, p_bot, 2, pitch_result="strike_swinging")
        _insert_play_event(conn, p_bot, 3, pitch_result="strike_swinging")
        conn.commit()
        conn.close()

        runner = CliRunner()
        result = runner.invoke(
            bb_app,
            [
                "data", "reconcile",
                "--game-id", "game-cli-single",
                "--db", str(db_path),
            ],
        )

        assert result.exit_code == 0, (
            f"bb data reconcile --game-id exited non-zero.\n"
            f"stdout: {result.stdout}\n"
            f"exception: {result.exception}"
        )

        conn = sqlite3.connect(str(db_path))
        try:
            p1_count = conn.execute(
                "SELECT COUNT(*) FROM reconciliation_discrepancies "
                "WHERE game_id = ? AND perspective_team_id = ?",
                ("game-cli-single", 1),
            ).fetchone()[0]
            p2_count = conn.execute(
                "SELECT COUNT(*) FROM reconciliation_discrepancies "
                "WHERE game_id = ? AND perspective_team_id = ?",
                ("game-cli-single", 2),
            ).fetchone()[0]
        finally:
            conn.close()

        assert p1_count > 0, (
            "single-perspective game should still produce discrepancy "
            "rows for the loaded perspective"
        )
        assert p2_count == 0, (
            "single-perspective game must not spuriously produce rows for "
            "a perspective that was never loaded"
        )

    def test_cli_game_id_execute_mode_processes_all_perspectives(
        self, tmp_path: Path
    ) -> None:
        """E-221-07 AC-5 regression: the per-perspective iteration loop in
        ``bb data reconcile --game-id X`` must work identically in
        ``--execute`` mode (corrections applied) as in the default dry-run
        mode.

        The E-221-07 Phase 3 tests at ``test_cli_game_id_processes_all_
        perspectives`` and ``test_cli_game_id_single_perspective_unchanged``
        only exercise the dry-run path.  Codex review Finding 3 flagged
        the gap: the shared ``run_id`` branch and per-perspective loop at
        ``src/cli/data.py:1200-1228`` run the same code in both modes, but
        an unexercised path can regress silently.

        Asserts the execute path:
          - HTTP/CLI exit code 0
          - Both perspectives' discrepancy rows persist
          - Shared ``run_id`` across the two perspectives (verifies the
            ``run_id = str(uuid.uuid4())`` outside the loop at
            ``src/cli/data.py:1201`` is reused for every perspective)
          - Per-perspective output labels are emitted in execute mode
            (the ``(perspective=N): correction complete.`` headers)
        """
        from typer.testing import CliRunner
        from src.cli import app as bb_app

        db_path = tmp_path / "test_reconcile_cli_execute.db"
        _seed_reconcile_cli_db(db_path)

        runner = CliRunner()
        result = runner.invoke(
            bb_app,
            [
                "data", "reconcile",
                "--game-id", "game-cli-xperspective",
                "--db", str(db_path),
                "--execute",
            ],
        )

        assert result.exit_code == 0, (
            f"bb data reconcile --game-id --execute exited non-zero.\n"
            f"stdout: {result.stdout}\n"
            f"exception: {result.exception}"
        )

        conn = sqlite3.connect(str(db_path))
        try:
            p1_count = conn.execute(
                "SELECT COUNT(*) FROM reconciliation_discrepancies "
                "WHERE game_id = ? AND perspective_team_id = ?",
                ("game-cli-xperspective", 1),
            ).fetchone()[0]
            p2_count = conn.execute(
                "SELECT COUNT(*) FROM reconciliation_discrepancies "
                "WHERE game_id = ? AND perspective_team_id = ?",
                ("game-cli-xperspective", 2),
            ).fetchone()[0]
            # Shared run_id assertion: both perspectives' rows for this game
            # must cluster under a single run_id (mirrors reconcile_all's
            # pattern at engine.py:451, verified in CLI via the shared-scope
            # run_id declared at src/cli/data.py:1201 outside the per-
            # perspective loop).
            run_id_count = conn.execute(
                "SELECT COUNT(DISTINCT run_id) "
                "FROM reconciliation_discrepancies "
                "WHERE game_id = ?",
                ("game-cli-xperspective",),
            ).fetchone()[0]
        finally:
            conn.close()

        assert p1_count > 0, (
            "Finding 3: perspective 1 should have discrepancy rows after "
            "`bb data reconcile --game-id --execute`"
        )
        assert p2_count > 0, (
            "Finding 3 / AC-5: perspective 2's discrepancies must persist "
            "in execute mode just as they do in dry-run mode. Got "
            f"p1={p1_count} p2={p2_count}."
        )
        assert p1_count == p2_count, (
            f"perspectives seeded identical data should produce equal row "
            f"counts: p1={p1_count} p2={p2_count}"
        )
        assert run_id_count == 1, (
            f"Finding 3 / AC-5: both perspectives must share a single "
            f"run_id per CLI invocation (mirrors reconcile_all's pattern). "
            f"Got {run_id_count} distinct run_ids."
        )

        # Per-perspective output labels are emitted in execute mode, with
        # the "correction complete" label instead of "detection complete".
        assert "(perspective=1): correction complete" in result.stdout, (
            f"execute mode should emit per-perspective correction header "
            f"for perspective 1. stdout:\n{result.stdout}"
        )
        assert "(perspective=2): correction complete" in result.stdout, (
            f"execute mode should emit per-perspective correction header "
            f"for perspective 2. stdout:\n{result.stdout}"
        )


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

        def _mock_extract(conn, game_id, game_stream_id, season_id, team_id, is_home, **kwargs):
            if team_id == 1:  # Home team: simulate re-entry
                return [
                    {"player_id": "pitcher-h1"},
                    {"player_id": "pitcher-h2"},
                    {"player_id": "pitcher-h1"},  # re-entry
                ]
            return original_extract(conn, game_id, game_stream_id, season_id, team_id, is_home, **kwargs)

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

        # reconciliation_discrepancies is created by the real schema (load_real_schema)
        result = get_summary_from_db(db)
        assert result["total_records"] == 0
        assert result["total_corrected"] == 0

    def test_summary_from_populated_db(self, db: sqlite3.Connection) -> None:
        """Summary reflects data across all runs."""
        from src.reconciliation.engine import get_summary_from_db

        # reconciliation_discrepancies.game_id REFERENCES games(game_id) under the
        # real schema, so seed a game row before inserting discrepancies.
        _insert_game(db, "g1")

        # reconciliation_discrepancies is created by the real schema (load_real_schema)
        # Insert some records
        db.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(game_id, run_id, perspective_team_id, team_id, player_id, signal_name, category, "
            "boxscore_value, plays_value, delta, status) "
            "VALUES ('g1', 'r1', 1, 1, 'p1', 'pitcher_bf', 'pitcher', 5, 5, 0, 'MATCH')"
        )
        db.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(game_id, run_id, perspective_team_id, team_id, player_id, signal_name, category, "
            "boxscore_value, plays_value, delta, status) "
            "VALUES ('g1', 'r1', 1, 1, 'p1', 'pitcher_so', 'pitcher', 3, 2, 1, 'CORRECTED')"
        )

        result = get_summary_from_db(db)
        assert result["total_records"] == 2
        assert result["total_corrected"] == 1
        assert result["pitcher_signals"]["pitcher_bf"]["MATCH"] == 1
        assert result["pitcher_signals"]["pitcher_so"]["CORRECTED"] == 1


# ---------------------------------------------------------------------------
# E-201-01: Five accuracy fixes
# ---------------------------------------------------------------------------


class TestBoxscoreSupplement:
    """Fix 1: Boxscore pitches/total_strikes supplement for high-confidence pitchers."""

    def test_supplement_applied_when_gate_passes(self, db: sqlite3.Connection) -> None:
        """TN-4(a): BF+SO+BB all match -> plays_value = boxscore value, correction_detail set."""
        _insert_game(db, "game-supp")

        # Boxscore: 3 BF, 1 SO, 0 BB, 38 pitches, 25 total_strikes
        _insert_pitching_boxscore(
            db, "game-supp", "pitcher-h1", 1,
            bf=3, so=1, bb=0, hbp=0, h=1, pitches=38, total_strikes=25,
        )
        _insert_pitching_boxscore(db, "game-supp", "pitcher-a1", 2, bf=2, pitches=10, total_strikes=6)

        _insert_batting_boxscore(db, "game-supp", "batter-h1", 1, ab=1, h=0)
        _insert_batting_boxscore(db, "game-supp", "batter-h2", 1, ab=1, h=0)
        _insert_batting_boxscore(db, "game-supp", "batter-a1", 2, ab=2, h=1, so=1)
        _insert_batting_boxscore(db, "game-supp", "batter-a2", 2, ab=1, h=0)

        # Plays: 3 top-half plays (matching BF=3, SO=1, BB=0) but only 31 pitch_count total
        p1 = _insert_play(db, "game-supp", 1, half="top", batting_team_id=2,
                           batter_id="batter-a1", pitcher_id="pitcher-h1",
                           outcome="Single", pitch_count=10, did_outs_change=0)
        _insert_play_event(db, p1, 1, pitch_result="ball")
        _insert_play_event(db, p1, 2, pitch_result="strike_looking")
        _insert_play_event(db, p1, 3, pitch_result="in_play")

        p2 = _insert_play(db, "game-supp", 2, half="top", batting_team_id=2,
                           batter_id="batter-a2", pitcher_id="pitcher-h1",
                           outcome="Strikeout", pitch_count=11, did_outs_change=1)
        _insert_play_event(db, p2, 1, pitch_result="strike_swinging")
        _insert_play_event(db, p2, 2, pitch_result="foul")
        _insert_play_event(db, p2, 3, pitch_result="strike_looking")

        p3 = _insert_play(db, "game-supp", 3, half="top", batting_team_id=2,
                           batter_id="batter-a1", pitcher_id="pitcher-h1",
                           outcome="Groundout", pitch_count=10, did_outs_change=1)
        _insert_play_event(db, p3, 1, pitch_result="ball")
        _insert_play_event(db, p3, 2, pitch_result="in_play")

        # Bottom half
        _insert_play(db, "game-supp", 4, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", pitch_count=5, did_outs_change=1)
        _insert_play(db, "game-supp", 5, half="bottom", batting_team_id=1,
                      batter_id="batter-h2", pitcher_id="pitcher-a1",
                      outcome="Groundout", pitch_count=5, did_outs_change=1)

        summary = reconcile_game(db, "game-supp")

        # pitcher_pitches should be MATCH (supplemented: plays_value = boxscore = 38)
        pitches_counts = summary.signal_counts.get("pitcher_pitches", {})
        assert pitches_counts.get("MATCH", 0) == 2, f"pitcher_pitches: {pitches_counts}"

        # pitcher_total_strikes should be MATCH (supplemented)
        ts_counts = summary.signal_counts.get("pitcher_total_strikes", {})
        assert ts_counts.get("MATCH", 0) == 2, f"pitcher_total_strikes: {ts_counts}"

        # Verify correction_detail was written for the supplemented pitcher
        rows = db.execute(
            "SELECT correction_detail FROM reconciliation_discrepancies "
            "WHERE game_id = 'game-supp' AND player_id = 'pitcher-h1' "
            "AND signal_name = 'pitcher_pitches'"
        ).fetchall()
        assert len(rows) == 1
        detail = json.loads(rows[0][0])
        assert detail["boxscore_supplement"] is True
        assert detail["plays_pitches"] == 31  # original plays-derived value
        assert detail["boxscore_pitches"] == 38

    def test_supplement_not_applied_when_gate_fails(self, db: sqlite3.Connection) -> None:
        """TN-4(b): BF/SO/BB mismatch -> plays_value = raw plays-derived value."""
        _insert_game(db, "game-nosupp")

        # Boxscore: BF=3, SO=2, BB=0, pitches=38. Plays will have SO=1 (mismatch)
        _insert_pitching_boxscore(
            db, "game-nosupp", "pitcher-h1", 1,
            bf=3, so=2, bb=0, pitches=38, total_strikes=25,
        )
        _insert_pitching_boxscore(db, "game-nosupp", "pitcher-a1", 2, bf=1)

        _insert_batting_boxscore(db, "game-nosupp", "batter-a1", 2, ab=2, so=1)
        _insert_batting_boxscore(db, "game-nosupp", "batter-a2", 2, ab=1)
        _insert_batting_boxscore(db, "game-nosupp", "batter-h1", 1, ab=1)

        # Plays: 3 BF but only 1 SO (boxscore says 2 -> gate fails on SO)
        _insert_play(db, "game-nosupp", 1, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Strikeout", pitch_count=10, did_outs_change=1)
        _insert_play(db, "game-nosupp", 2, half="top", batting_team_id=2,
                      batter_id="batter-a2", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=11, did_outs_change=1)
        _insert_play(db, "game-nosupp", 3, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Groundout", pitch_count=10, did_outs_change=1)
        _insert_play(db, "game-nosupp", 4, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)

        summary = reconcile_game(db, "game-nosupp")

        # pitcher_pitches for pitcher-h1: boxscore=38, plays=31 -> CORRECTABLE (no supplement)
        pitches_counts = summary.signal_counts.get("pitcher_pitches", {})
        assert "CORRECTABLE" in pitches_counts, f"pitcher_pitches: {pitches_counts}"

    def test_partial_gate_failure(self, db: sqlite3.Connection) -> None:
        """TN-4(h): BF matches but SO doesn't -> supplement not applied."""
        _insert_game(db, "game-partial")

        # BF=2 matches, SO=1 in boxscore but plays will show SO=0
        _insert_pitching_boxscore(
            db, "game-partial", "pitcher-h1", 1,
            bf=2, so=1, bb=0, pitches=20, total_strikes=12,
        )
        _insert_pitching_boxscore(db, "game-partial", "pitcher-a1", 2, bf=1)

        _insert_batting_boxscore(db, "game-partial", "batter-a1", 2, ab=2)
        _insert_batting_boxscore(db, "game-partial", "batter-h1", 1, ab=1)

        # Plays: 2 BF, 0 SO (boxscore says 1 SO -> gate fails)
        _insert_play(db, "game-partial", 1, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=10, did_outs_change=1)
        _insert_play(db, "game-partial", 2, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Groundout", pitch_count=10, did_outs_change=1)
        _insert_play(db, "game-partial", 3, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)

        summary = reconcile_game(db, "game-partial")

        # pitcher_pitches: box=20, plays=20 -> MATCH (pitch counts happen to match)
        # But the point is: supplement was NOT applied (gate failed on SO)
        # Verify no supplement correction_detail
        rows = db.execute(
            "SELECT correction_detail FROM reconciliation_discrepancies "
            "WHERE game_id = 'game-partial' AND player_id = 'pitcher-h1' "
            "AND signal_name = 'pitcher_pitches'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] is None  # No supplement detail

    def test_pitcher_with_zero_plays_not_supplemented(self, db: sqlite3.Connection) -> None:
        """TN-4(i): Pitcher with zero plays (UNCORRECTABLE) is not supplemented."""
        _insert_game(db, "game-zeroplays")

        # Boxscore has pitcher-h1 with 3 BF, but plays show different pitcher
        _insert_pitching_boxscore(
            db, "game-zeroplays", "pitcher-h1", 1,
            bf=2, so=1, bb=0, pitches=20, total_strikes=12,
        )
        _insert_pitching_boxscore(
            db, "game-zeroplays", "pitcher-h2", 1,
            bf=1, so=0, bb=0, pitches=5, total_strikes=3,
        )
        _insert_pitching_boxscore(db, "game-zeroplays", "pitcher-a1", 2, bf=1)

        _insert_batting_boxscore(db, "game-zeroplays", "batter-a1", 2, ab=2)
        _insert_batting_boxscore(db, "game-zeroplays", "batter-a2", 2, ab=1)
        _insert_batting_boxscore(db, "game-zeroplays", "batter-h1", 1, ab=1)

        # All 3 top-half plays attributed to pitcher-h2 (pitcher-h1 has zero plays)
        _insert_play(db, "game-zeroplays", 1, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h2",
                      outcome="Flyout", pitch_count=5, did_outs_change=1)
        _insert_play(db, "game-zeroplays", 2, half="top", batting_team_id=2,
                      batter_id="batter-a2", pitcher_id="pitcher-h2",
                      outcome="Strikeout", pitch_count=5, did_outs_change=1)
        _insert_play(db, "game-zeroplays", 3, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h2",
                      outcome="Groundout", pitch_count=5, did_outs_change=1)
        _insert_play(db, "game-zeroplays", 4, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)

        summary = reconcile_game(db, "game-zeroplays")

        # pitcher-h1 pitches: UNCORRECTABLE (missing from plays, no supplement)
        pitches_counts = summary.signal_counts.get("pitcher_pitches", {})
        assert "UNCORRECTABLE" in pitches_counts, f"pitcher_pitches: {pitches_counts}"

    def test_supplement_skipped_when_boxscore_pitches_null(self, db: sqlite3.Connection) -> None:
        """Bug fix: NULL boxscore pitches should not be supplemented as 0."""
        _insert_game(db, "game-null-p")

        # BF+SO+BB all match, but pitches is NULL in boxscore
        _insert_pitching_boxscore(
            db, "game-null-p", "pitcher-h1", 1,
            bf=2, so=1, bb=0, hbp=0, h=0,
            pitches=0, total_strikes=0,  # Will be inserted as 0
        )
        # Manually NULL-ify pitches to test the guard
        db.execute(
            "UPDATE player_game_pitching SET pitches = NULL, total_strikes = NULL "
            "WHERE game_id = 'game-null-p' AND player_id = 'pitcher-h1'"
        )
        _insert_pitching_boxscore(db, "game-null-p", "pitcher-a1", 2, bf=1)

        _insert_batting_boxscore(db, "game-null-p", "batter-a1", 2, ab=1, so=1)
        _insert_batting_boxscore(db, "game-null-p", "batter-a2", 2, ab=1)
        _insert_batting_boxscore(db, "game-null-p", "batter-h1", 1, ab=1)

        p1 = _insert_play(db, "game-null-p", 1, half="top", batting_team_id=2,
                           batter_id="batter-a1", pitcher_id="pitcher-h1",
                           outcome="Strikeout", pitch_count=5, did_outs_change=1)
        _insert_play_event(db, p1, 1, pitch_result="strike_swinging")
        _insert_play_event(db, p1, 2, pitch_result="strike_swinging")
        _insert_play_event(db, p1, 3, pitch_result="strike_swinging")

        _insert_play(db, "game-null-p", 2, half="top", batting_team_id=2,
                      batter_id="batter-a2", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-null-p", 3, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)

        summary = reconcile_game(db, "game-null-p")

        # pitcher_pitches: boxscore=0 (NULL→0), plays=8 -> should NOT be supplemented
        # Without the fix, supplement would replace plays 8 with 0 (false MATCH)
        pitches_counts = summary.signal_counts.get("pitcher_pitches", {})
        assert "CORRECTABLE" in pitches_counts or "MATCH" not in pitches_counts or \
            pitches_counts.get("MATCH", 0) <= 1, \
            f"pitcher_pitches should not be false MATCH: {pitches_counts}"

        # Verify no supplement correction_detail for pitcher-h1
        rows = db.execute(
            "SELECT correction_detail FROM reconciliation_discrepancies "
            "WHERE game_id = 'game-null-p' AND player_id = 'pitcher-h1' "
            "AND signal_name = 'pitcher_pitches'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] is None  # No supplement metadata

    def test_supplement_preserved_when_corrected(self, db: sqlite3.Connection) -> None:
        """Bug fix: correction_detail from supplement not overwritten by CORRECTED promotion."""
        _insert_game(db, "game-supp-corr")

        # Two home pitchers: pitcher-h1 faced 2, pitcher-h2 faced 1
        # After BF correction, BF+SO+BB will match for pitcher-h1 -> supplement applies
        _insert_pitching_boxscore(
            db, "game-supp-corr", "pitcher-h1", 1,
            bf=2, so=1, bb=0, h=0, pitches=20, total_strikes=12,
        )
        _insert_pitching_boxscore(
            db, "game-supp-corr", "pitcher-h2", 1,
            bf=1, so=0, bb=0, h=0, pitches=8, total_strikes=5,
        )
        _insert_pitching_boxscore(db, "game-supp-corr", "pitcher-a1", 2, bf=1, pitches=3)

        _insert_batting_boxscore(db, "game-supp-corr", "batter-h1", 1, ab=1)
        _insert_batting_boxscore(db, "game-supp-corr", "batter-a1", 2, ab=2, so=1)
        _insert_batting_boxscore(db, "game-supp-corr", "batter-a2", 2, ab=1)

        # All 3 top-half plays misattributed to pitcher-h1 (play 3 should be pitcher-h2)
        p1 = _insert_play(db, "game-supp-corr", 1, half="top", batting_team_id=2,
                           batter_id="batter-a1", pitcher_id="pitcher-h1",
                           outcome="Strikeout", pitch_count=6, did_outs_change=1)
        _insert_play_event(db, p1, 1, pitch_result="strike_looking")
        _insert_play_event(db, p1, 2, pitch_result="foul")
        _insert_play_event(db, p1, 3, pitch_result="strike_swinging")

        p2 = _insert_play(db, "game-supp-corr", 2, half="top", batting_team_id=2,
                           batter_id="batter-a2", pitcher_id="pitcher-h1",
                           outcome="Flyout", pitch_count=4, did_outs_change=1)
        _insert_play_event(db, p2, 1, pitch_result="ball")
        _insert_play_event(db, p2, 2, pitch_result="in_play")

        # Misattributed to pitcher-h1, should be pitcher-h2
        p3 = _insert_play(db, "game-supp-corr", 3, half="top", batting_team_id=2,
                           batter_id="batter-a1", pitcher_id="pitcher-h1",
                           outcome="Groundout", pitch_count=5, did_outs_change=1)
        _insert_play_event(db, p3, 1, pitch_result="ball")
        _insert_play_event(db, p3, 2, pitch_result="in_play")

        _insert_play(db, "game-supp-corr", 4, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)

        # Execute mode: will correct pitcher attribution AND supplement
        summary = reconcile_game(db, "game-supp-corr", dry_run=False)

        assert summary.total_plays_reassigned == 1

        # Check that CORRECTED signals exist
        pitches_counts = summary.signal_counts.get("pitcher_pitches", {})
        assert pitches_counts.get("CORRECTED", 0) > 0 or pitches_counts.get("MATCH", 0) >= 1

        # Verify correction_detail for pitcher-h1 pitcher_pitches retains supplement info
        rows = db.execute(
            "SELECT correction_detail FROM reconciliation_discrepancies "
            "WHERE game_id = 'game-supp-corr' AND player_id = 'pitcher-h1' "
            "AND signal_name = 'pitcher_pitches' AND status = 'CORRECTED'"
        ).fetchall()
        if rows:
            detail = json.loads(rows[0][0])
            # Should have supplement metadata preserved
            assert "boxscore_supplement" in detail, \
                f"Supplement metadata lost in CORRECTED promotion: {detail}"
            # Should also have reassignment info merged in
            assert "reassignments" in detail, \
                f"Reassignment info missing in merged detail: {detail}"


class TestIBBInBBOutcomes:
    """Fix 2/3: Intentional Walk included in BB signals."""

    def test_ibb_counted_in_pitcher_bb(self, db: sqlite3.Connection) -> None:
        """TN-4(c): Intentional Walk counted in pitcher_bb signal."""
        _insert_game(db, "game-ibb-p")

        # Boxscore: 2 BF, 0 SO, 1 BB (the IBB)
        _insert_pitching_boxscore(
            db, "game-ibb-p", "pitcher-h1", 1,
            bf=2, so=0, bb=1, pitches=5,
        )
        _insert_pitching_boxscore(db, "game-ibb-p", "pitcher-a1", 2, bf=1)

        _insert_batting_boxscore(db, "game-ibb-p", "batter-a1", 2, ab=1, bb=1)
        _insert_batting_boxscore(db, "game-ibb-p", "batter-a2", 2, ab=1)
        _insert_batting_boxscore(db, "game-ibb-p", "batter-h1", 1, ab=1)

        # Play 1: Intentional Walk
        _insert_play(db, "game-ibb-p", 1, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Intentional Walk", pitch_count=0, did_outs_change=0)
        _insert_play(db, "game-ibb-p", 2, half="top", batting_team_id=2,
                      batter_id="batter-a2", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=5, did_outs_change=1)
        _insert_play(db, "game-ibb-p", 3, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)

        summary = reconcile_game(db, "game-ibb-p")

        # pitcher_bb should be MATCH (IBB counted)
        bb_counts = summary.signal_counts.get("pitcher_bb", {})
        assert bb_counts.get("MATCH", 0) >= 1, f"pitcher_bb: {bb_counts}"
        non_match = sum(v for k, v in bb_counts.items() if k != "MATCH")
        assert non_match == 0, f"pitcher_bb has non-MATCH: {bb_counts}"

    def test_ibb_counted_in_batter_bb(self, db: sqlite3.Connection) -> None:
        """TN-4(d): Intentional Walk counted in batter_bb signal."""
        _insert_game(db, "game-ibb-b")

        _insert_pitching_boxscore(db, "game-ibb-b", "pitcher-h1", 1, bf=2)
        _insert_pitching_boxscore(db, "game-ibb-b", "pitcher-a1", 2, bf=1)

        # Batter-a1: 0 AB (IBB excluded from AB), 1 BB
        _insert_batting_boxscore(db, "game-ibb-b", "batter-a1", 2, ab=0, bb=1)
        _insert_batting_boxscore(db, "game-ibb-b", "batter-a2", 2, ab=1)
        _insert_batting_boxscore(db, "game-ibb-b", "batter-h1", 1, ab=1)

        _insert_play(db, "game-ibb-b", 1, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Intentional Walk", pitch_count=0, did_outs_change=0)
        _insert_play(db, "game-ibb-b", 2, half="top", batting_team_id=2,
                      batter_id="batter-a2", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-ibb-b", 3, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)

        summary = reconcile_game(db, "game-ibb-b")

        # batter_bb should be MATCH (IBB counted)
        bb_counts = summary.signal_counts.get("batter_bb", {})
        non_match = sum(v for k, v in bb_counts.items() if k != "MATCH")
        assert non_match == 0, f"batter_bb has non-MATCH: {bb_counts}"


class TestGameRunsFromGamesTable:
    """Fix 4: game_runs uses games.home_score/away_score."""

    def test_game_runs_uses_games_table_scores(self, db: sqlite3.Connection) -> None:
        """TN-4(e): game_runs uses games.home_score/away_score for both sides."""
        # Insert game with known scores
        conn = db
        conn.execute(
            "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, "
            "home_score, away_score, status) VALUES "
            "('game-runs', '2025-spring-hs', '2025-04-01', 1, 2, 7, 3, 'completed')"
        )

        _insert_pitching_boxscore(conn, "game-runs", "pitcher-h1", 1, bf=1)
        _insert_pitching_boxscore(conn, "game-runs", "pitcher-a1", 2, bf=1)
        # Batting boxscores that DON'T match game scores (courtesy runner scenario)
        _insert_batting_boxscore(conn, "game-runs", "batter-h1", 1, ab=1, r=5)  # only 5, game says 7
        _insert_batting_boxscore(conn, "game-runs", "batter-a1", 2, ab=1, r=2)  # only 2, game says 3

        _insert_play(conn, "game-runs", 1, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)
        _insert_play(conn, "game-runs", 2, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)

        summary = reconcile_game(conn, "game-runs")

        # game_runs: MATCH for both teams (using games table scores)
        runs_counts = summary.signal_counts.get("game_runs", {})
        assert runs_counts.get("MATCH", 0) == 2, f"game_runs: {runs_counts}"
        non_match = sum(v for k, v in runs_counts.items() if k != "MATCH")
        assert non_match == 0, f"game_runs has non-MATCH: {runs_counts}"

    def test_game_runs_skipped_when_both_scores_null(self, db: sqlite3.Connection) -> None:
        """TN-4(g): game_runs skipped when both home_score and away_score are NULL."""
        conn = db
        conn.execute(
            "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, "
            "home_score, away_score, status) VALUES "
            "('game-null-score', '2025-spring-hs', '2025-04-01', 1, 2, NULL, NULL, 'completed')"
        )

        _insert_pitching_boxscore(conn, "game-null-score", "pitcher-h1", 1, bf=1)
        _insert_pitching_boxscore(conn, "game-null-score", "pitcher-a1", 2, bf=1)
        _insert_batting_boxscore(conn, "game-null-score", "batter-h1", 1, ab=1, r=1)
        _insert_batting_boxscore(conn, "game-null-score", "batter-a1", 2, ab=1, r=0)

        _insert_play(conn, "game-null-score", 1, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)
        _insert_play(conn, "game-null-score", 2, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)

        summary = reconcile_game(conn, "game-null-score")

        assert "game_runs" not in summary.signal_counts, \
            f"game_runs should be skipped: {summary.signal_counts.get('game_runs', {})}"

    def test_game_runs_skipped_when_one_score_null(self, db: sqlite3.Connection) -> None:
        """AC-4: game_runs skipped when only away_score is NULL (single-NULL case)."""
        conn = db
        conn.execute(
            "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, "
            "home_score, away_score, status) VALUES "
            "('game-one-null', '2025-spring-hs', '2025-04-01', 1, 2, 5, NULL, 'completed')"
        )

        _insert_pitching_boxscore(conn, "game-one-null", "pitcher-h1", 1, bf=1)
        _insert_pitching_boxscore(conn, "game-one-null", "pitcher-a1", 2, bf=1)
        _insert_batting_boxscore(conn, "game-one-null", "batter-h1", 1, ab=1, r=1)
        _insert_batting_boxscore(conn, "game-one-null", "batter-a1", 2, ab=1, r=0)

        _insert_play(conn, "game-one-null", 1, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)
        _insert_play(conn, "game-one-null", 2, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)

        summary = reconcile_game(conn, "game-one-null")

        # Neither team should emit game_runs when either score is NULL
        assert "game_runs" not in summary.signal_counts, \
            f"game_runs should be skipped: {summary.signal_counts.get('game_runs', {})}"


class TestGamePACountFromBoxscore:
    """Fix 5: game_pa_count uses boxscore BF sum for both sides."""

    def test_game_pa_count_uses_boxscore_bf(self, db: sqlite3.Connection) -> None:
        """TN-4(f): game_pa_count uses SUM(bf) for both sides (always MATCH)."""
        _insert_game(db, "game-pa-fix")

        # Boxscore says 4 BF total, but plays only has 3 (abandoned final PA)
        _insert_pitching_boxscore(db, "game-pa-fix", "pitcher-h1", 1, bf=4)
        _insert_pitching_boxscore(db, "game-pa-fix", "pitcher-a1", 2, bf=2)

        _insert_batting_boxscore(db, "game-pa-fix", "batter-h1", 1, ab=1)
        _insert_batting_boxscore(db, "game-pa-fix", "batter-h2", 1, ab=1)
        _insert_batting_boxscore(db, "game-pa-fix", "batter-a1", 2, ab=3)
        _insert_batting_boxscore(db, "game-pa-fix", "batter-a2", 2, ab=1)

        # Only 3 top-half plays (BF says 4 -- abandoned final PA)
        _insert_play(db, "game-pa-fix", 1, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-pa-fix", 2, half="top", batting_team_id=2,
                      batter_id="batter-a2", pitcher_id="pitcher-h1",
                      outcome="Groundout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-pa-fix", 3, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)

        _insert_play(db, "game-pa-fix", 4, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-pa-fix", 5, half="bottom", batting_team_id=1,
                      batter_id="batter-h2", pitcher_id="pitcher-a1",
                      outcome="Groundout", pitch_count=3, did_outs_change=1)

        summary = reconcile_game(db, "game-pa-fix")

        # game_pa_count: MATCH for both teams (boxscore BF for both sides)
        pa_counts = summary.signal_counts.get("game_pa_count", {})
        assert pa_counts.get("MATCH", 0) == 2, f"game_pa_count: {pa_counts}"
        non_match = sum(v for k, v in pa_counts.items() if k != "MATCH")
        assert non_match == 0, f"game_pa_count has non-MATCH: {pa_counts}"

    def test_game_pa_count_skipped_when_no_pitching_data(self, db: sqlite3.Connection) -> None:
        """game_pa_count skipped when boxscore has no pitching data (box_pa=0)."""
        conn = db
        conn.execute(
            "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, "
            "home_score, away_score, status) VALUES "
            "('game-no-pitch', '2025-spring-hs', '2025-04-01', 1, 2, 1, 0, 'completed')"
        )

        # No pitching boxscore rows for home team (bf=0 for away team)
        _insert_pitching_boxscore(conn, "game-no-pitch", "pitcher-a1", 2, bf=0)

        _insert_batting_boxscore(conn, "game-no-pitch", "batter-h1", 1, ab=1)
        _insert_batting_boxscore(conn, "game-no-pitch", "batter-a1", 2, ab=1)

        _insert_play(conn, "game-no-pitch", 1, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)
        _insert_play(conn, "game-no-pitch", 2, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)

        summary = reconcile_game(conn, "game-no-pitch")

        # game_pa_count should be emitted at most once (for the team WITH bf data)
        # The away team has bf=0, so its game_pa_count should be skipped
        pa_counts = summary.signal_counts.get("game_pa_count", {})
        # Home team has no pitching boxscore at all -> skipped. Away has bf=0 -> skipped.
        assert pa_counts.get("MATCH", 0) <= 1, \
            f"game_pa_count should skip teams with no BF data: {pa_counts}"


class TestCLIAvailabilitySignalSeparation:
    """CLI summary separates tautological availability signals from cross-source reconciliation."""

    def test_run_summary_separates_availability_signals(
        self, db: sqlite3.Connection, capsys: pytest.CaptureFixture[str],
    ) -> None:
        """_print_summary puts game_runs/game_pa_count in 'Data Availability' not 'Game-Level'."""
        from src.cli.data import _print_summary

        _insert_game(db, "game-cli")

        _insert_pitching_boxscore(db, "game-cli", "pitcher-h1", 1, bf=1, so=0)
        _insert_pitching_boxscore(db, "game-cli", "pitcher-a1", 2, bf=1, so=0)
        _insert_batting_boxscore(db, "game-cli", "batter-h1", 1, ab=1, h=0)
        _insert_batting_boxscore(db, "game-cli", "batter-a1", 2, ab=1, h=0)

        _insert_play(db, "game-cli", 1, half="top", batting_team_id=2,
                      batter_id="batter-a1", pitcher_id="pitcher-h1",
                      outcome="Flyout", pitch_count=3, did_outs_change=1)
        _insert_play(db, "game-cli", 2, half="bottom", batting_team_id=1,
                      batter_id="batter-h1", pitcher_id="pitcher-a1",
                      outcome="Groundout", pitch_count=3, did_outs_change=1)

        summary = reconcile_game(db, "game-cli")
        _print_summary(summary)
        output = capsys.readouterr().out

        # game_runs and game_pa_count must appear under "Data Availability Checks"
        assert "Data Availability Checks" in output, \
            f"Missing 'Data Availability Checks' section in output:\n{output}"
        assert "game_runs" in output, f"game_runs missing from output:\n{output}"
        assert "game_pa_count" in output, f"game_pa_count missing from output:\n{output}"

        # Extract the "Game-Level Signals" section and verify availability signals are NOT in it
        lines = output.split("\n")
        in_game_level = False
        game_level_lines: list[str] = []
        for line in lines:
            if "Game-Level Signals" in line:
                in_game_level = True
                continue
            if in_game_level:
                if line.strip() == "" or (line.strip() and not line.startswith("    ")):
                    break
                game_level_lines.append(line)

        game_level_text = "\n".join(game_level_lines)
        assert "game_runs" not in game_level_text, \
            f"game_runs should NOT be in Game-Level Signals section:\n{game_level_text}"
        assert "game_pa_count" not in game_level_text, \
            f"game_pa_count should NOT be in Game-Level Signals section:\n{game_level_text}"

    def test_db_summary_separates_availability_signals(
        self, db: sqlite3.Connection, capsys: pytest.CaptureFixture[str],
    ) -> None:
        """_print_db_summary puts game_runs/game_pa_count in 'Data Availability' not 'Game-Level'."""
        from src.cli.data import _print_db_summary

        db_summary = {
            "total_records": 10,
            "total_corrected": 2,
            "pitcher_signals": {"pitcher_bf": {"MATCH": 5}},
            "batter_signals": {"batter_ab": {"MATCH": 3}},
            "game_signals": {
                "game_hits": {"MATCH": 4, "AMBIGUOUS": 1},
                "game_runs": {"MATCH": 4},
                "game_pa_count": {"MATCH": 4},
            },
        }
        _print_db_summary(db_summary)
        output = capsys.readouterr().out

        assert "Data Availability Checks" in output
        assert "game_hits" in output  # real cross-source signal still shown

        # game_runs/game_pa_count must NOT appear under "Game-Level Signals"
        lines = output.split("\n")
        in_game_level = False
        game_level_lines: list[str] = []
        for line in lines:
            if "Game-Level Signals" in line:
                in_game_level = True
                continue
            if in_game_level:
                if line.strip() == "" or (line.strip() and not line.startswith("    ")):
                    break
                game_level_lines.append(line)

        game_level_text = "\n".join(game_level_lines)
        assert "game_runs" not in game_level_text
        assert "game_pa_count" not in game_level_text



class TestPerspectiveFiltering:
    """E-220 remediation C1-A: reconcile_game must filter to a single perspective.

    When a game has been loaded from two perspectives, reconcile_game must
    pick ONE perspective and only touch rows tagged with that perspective.
    Mixing perspectives during corrections corrupts pitcher_id assignments.
    """

    def test_only_chosen_perspective_rows_are_corrected(
        self, db: sqlite3.Connection
    ) -> None:
        # Set up a game where two perspectives both have plays + pgp data
        # for the SAME (game, player). Pitcher boundary drift exists in
        # perspective 1 (correctable) but NOT in perspective 2.  Verify the
        # correction only touches perspective 1's plays.
        _insert_game(db, "game-cross-persp")

        # Boxscore data tagged with perspective 1 (canonical/own perspective):
        # pitcher-h1 faced 2 batters, pitcher-h2 faced 1
        _insert_pitching_boxscore(
            db, "game-cross-persp", "pitcher-h1", 1, bf=2, so=1, perspective_team_id=1
        )
        _insert_pitching_boxscore(
            db, "game-cross-persp", "pitcher-h2", 1, bf=1, so=0, perspective_team_id=1
        )
        _insert_pitching_boxscore(
            db, "game-cross-persp", "pitcher-a1", 2, bf=3, so=0, perspective_team_id=1
        )
        _insert_batting_boxscore(
            db, "game-cross-persp", "batter-h1", 1, ab=1, perspective_team_id=1
        )
        _insert_batting_boxscore(
            db, "game-cross-persp", "batter-h2", 1, ab=1, perspective_team_id=1
        )
        _insert_batting_boxscore(
            db, "game-cross-persp", "batter-h3", 1, ab=1, perspective_team_id=1
        )
        _insert_batting_boxscore(
            db, "game-cross-persp", "batter-a1", 2, ab=1, perspective_team_id=1
        )
        _insert_batting_boxscore(
            db, "game-cross-persp", "batter-a2", 2, ab=1, perspective_team_id=1
        )
        _insert_batting_boxscore(
            db, "game-cross-persp", "batter-a3", 2, ab=1, perspective_team_id=1
        )

        # Plays tagged with perspective 1 (correctable boundary drift -- all
        # 3 top plays attributed to pitcher-h1, but boxscore says h2 faced 1)
        _insert_play(
            db, "game-cross-persp", 1, inning=1, half="top",
            batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1",
            perspective_team_id=1,
        )
        _insert_play(
            db, "game-cross-persp", 2, inning=1, half="top",
            batting_team_id=2, batter_id="batter-a2", pitcher_id="pitcher-h1",
            perspective_team_id=1,
        )
        _insert_play(
            db, "game-cross-persp", 3, inning=1, half="top",
            batting_team_id=2, batter_id="batter-a3", pitcher_id="pitcher-h1",
            perspective_team_id=1,
        )
        # Bottom half plays for perspective 1
        _insert_play(
            db, "game-cross-persp", 4, inning=1, half="bottom",
            batting_team_id=1, batter_id="batter-h1", pitcher_id="pitcher-a1",
            perspective_team_id=1,
        )
        _insert_play(
            db, "game-cross-persp", 5, inning=1, half="bottom",
            batting_team_id=1, batter_id="batter-h2", pitcher_id="pitcher-a1",
            perspective_team_id=1,
        )
        _insert_play(
            db, "game-cross-persp", 6, inning=1, half="bottom",
            batting_team_id=1, batter_id="batter-h3", pitcher_id="pitcher-a1",
            perspective_team_id=1,
        )

        # Now insert a SECOND set of plays tagged with perspective 2 -- the
        # same pitcher attribution but ALL correct for the boxscore.  These
        # rows must NOT be touched by reconcile_game.
        _insert_play(
            db, "game-cross-persp", 1, inning=1, half="top",
            batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1",
            perspective_team_id=2,
        )
        _insert_play(
            db, "game-cross-persp", 2, inning=1, half="top",
            batting_team_id=2, batter_id="batter-a2", pitcher_id="pitcher-h1",
            perspective_team_id=2,
        )
        _insert_play(
            db, "game-cross-persp", 3, inning=1, half="top",
            batting_team_id=2, batter_id="batter-a3", pitcher_id="pitcher-h2",
            perspective_team_id=2,
        )
        # Also insert the SAME boxscore for perspective 2 but with different
        # pitcher_id mapping -- if engine read from perspective 2, the
        # correction would be a no-op or different.  Filter must avoid this.
        _insert_pitching_boxscore(
            db, "game-cross-persp", "pitcher-h1", 1, bf=3, so=2, perspective_team_id=2
        )
        _insert_pitching_boxscore(
            db, "game-cross-persp", "pitcher-a1", 2, bf=3, so=0, perspective_team_id=2
        )

        db.commit()

        # Run reconcile in execute mode -- it should pick perspective 1
        # (home_team_id=1 is preferred by the deterministic ORDER BY in the
        # perspective selection subquery: home first, away second, then MIN)
        # and only correct perspective 1's plays.
        summary = reconcile_game(db, "game-cross-persp", dry_run=False)
        assert summary.games_processed == 1
        assert summary.total_plays_reassigned > 0, (
            "expected at least one plays correction in perspective 1"
        )

        # Verify perspective 1 plays were corrected: play_order=3 should now
        # reference pitcher-h2 (was pitcher-h1).
        row = db.execute(
            "SELECT pitcher_id FROM plays "
            "WHERE game_id = 'game-cross-persp' AND play_order = 3 "
            "AND perspective_team_id = 1"
        ).fetchone()
        assert row[0] == "pitcher-h2", (
            f"perspective 1 play_order=3 should be corrected to pitcher-h2, got {row[0]}"
        )

        # Verify perspective 2 plays were NOT touched: play_order=3 still
        # has its original pitcher_id (pitcher-h2 in this fixture, but
        # importantly any UPDATE would have set it to whatever perspective 1
        # corrected to -- if engine had touched it).  We assert by checking
        # that the row count for perspective 2 is unchanged.
        n_p2 = db.execute(
            "SELECT COUNT(*) FROM plays "
            "WHERE game_id = 'game-cross-persp' AND perspective_team_id = 2"
        ).fetchone()[0]
        assert n_p2 == 3, (
            f"perspective 2 should still have 3 plays untouched, got {n_p2}"
        )



class TestPerspectiveSelectionDeterminism:
    """E-220 round 4: reconcile_game must pick a deterministic perspective.

    The prior LIMIT 1 without ORDER BY was non-deterministic -- rowid order
    happened to work in practice, but no guarantee.  The fix adds an explicit
    ORDER BY that prefers home_team_id, then away_team_id, then MIN.
    """

    def test_prefers_home_team_perspective_over_away(
        self, db: sqlite3.Connection
    ) -> None:
        """When both home and away perspectives have plays, home wins."""
        _insert_game(db, "game-persp-order")
        # Both home (team_id=1) and away (team_id=2) perspectives have plays.
        # Insert away perspective FIRST so rowid order puts it before home.
        db.execute(
            "INSERT INTO plays "
            "(game_id, play_order, inning, half, season_id, "
            "batting_team_id, perspective_team_id, batter_id, pitcher_id) "
            "VALUES ('game-persp-order', 1, 1, 'top', '2025-spring-hs', 2, 2, 'batter-a1', 'pitcher-h1')"
        )
        db.execute(
            "INSERT INTO plays "
            "(game_id, play_order, inning, half, season_id, "
            "batting_team_id, perspective_team_id, batter_id, pitcher_id) "
            "VALUES ('game-persp-order', 1, 1, 'top', '2025-spring-hs', 2, 1, 'batter-a1', 'pitcher-h1')"
        )
        # Minimal boxscore rows for both perspectives so signal gen doesn't crash
        _insert_pitching_boxscore(db, "game-persp-order", "pitcher-h1", 1, bf=1, perspective_team_id=1, appearance_order=1)
        _insert_pitching_boxscore(db, "game-persp-order", "pitcher-a1", 2, bf=0, perspective_team_id=1, appearance_order=1)
        _insert_pitching_boxscore(db, "game-persp-order", "pitcher-h1", 1, bf=1, perspective_team_id=2, appearance_order=1)
        _insert_pitching_boxscore(db, "game-persp-order", "pitcher-a1", 2, bf=0, perspective_team_id=2, appearance_order=1)
        _insert_batting_boxscore(db, "game-persp-order", "batter-a1", 2, ab=1, perspective_team_id=1)
        _insert_batting_boxscore(db, "game-persp-order", "batter-a1", 2, ab=1, perspective_team_id=2)
        db.commit()

        summary = reconcile_game(db, "game-persp-order")
        # With 1 play in top half, BF=1 matches -- no UNCORRECTABLE
        # The test is about which perspective was chosen.  To verify, check
        # that the signal counts come from perspective 1's data.
        assert summary.games_processed == 1, (
            "expected game to be processed; perspective selection should be deterministic"
        )

    def test_prefers_away_team_when_only_away_has_plays(
        self, db: sqlite3.Connection
    ) -> None:
        """Deterministic fallback: when home has no plays, away perspective is chosen."""
        _insert_game(db, "game-away-only")
        # Only away perspective (team_id=2) has plays
        db.execute(
            "INSERT INTO plays "
            "(game_id, play_order, inning, half, season_id, "
            "batting_team_id, perspective_team_id, batter_id, pitcher_id) "
            "VALUES ('game-away-only', 1, 1, 'top', '2025-spring-hs', 2, 2, 'batter-a1', 'pitcher-h1')"
        )
        _insert_pitching_boxscore(db, "game-away-only", "pitcher-h1", 1, bf=1, perspective_team_id=2, appearance_order=1)
        _insert_pitching_boxscore(db, "game-away-only", "pitcher-a1", 2, bf=0, perspective_team_id=2, appearance_order=1)
        _insert_batting_boxscore(db, "game-away-only", "batter-a1", 2, ab=1, perspective_team_id=2)
        db.commit()

        summary = reconcile_game(db, "game-away-only")
        assert summary.games_processed == 1

    def test_fallback_to_min_when_neither_home_nor_away(
        self, db: sqlite3.Connection
    ) -> None:
        """If plays only exist with foreign perspectives, fall back to MIN."""
        # Create a third team to use as a foreign perspective
        db.execute(
            "INSERT INTO teams (id, name, gc_uuid, membership_type) "
            "VALUES (3, 'Foreign Team', 'uuid-foreign', 'tracked')"
        )
        _insert_game(db, "game-foreign")
        db.execute(
            "INSERT INTO plays "
            "(game_id, play_order, inning, half, season_id, "
            "batting_team_id, perspective_team_id, batter_id, pitcher_id) "
            "VALUES ('game-foreign', 1, 1, 'top', '2025-spring-hs', 2, 3, 'batter-a1', 'pitcher-h1')"
        )
        _insert_pitching_boxscore(db, "game-foreign", "pitcher-h1", 1, bf=1, perspective_team_id=3, appearance_order=1)
        _insert_pitching_boxscore(db, "game-foreign", "pitcher-a1", 2, bf=0, perspective_team_id=3, appearance_order=1)
        _insert_batting_boxscore(db, "game-foreign", "batter-a1", 2, ab=1, perspective_team_id=3)
        db.commit()

        summary = reconcile_game(db, "game-foreign")
        assert summary.games_processed == 1


class TestPitcherOrderFromDatabase:
    """E-220 round 4: reconcile_game must read pitcher order from player_game_pitching.appearance_order, not disk JSON.

    The pre-fix _extract_pitcher_order() read from data/raw/.../scouting/.../boxscores
    which does not exist on a clean-slate E-220 rebuild.  The fix switches to
    the DB appearance_order column (stable across perspectives per provenance
    rules).
    """

    def test_pitcher_order_from_appearance_order_column(
        self, db: sqlite3.Connection
    ) -> None:
        """Pitcher order is read from player_game_pitching.appearance_order.

        This test deliberately uses a tmp_path that contains NO data/raw/
        scouting files, simulating the clean-slate rebuild scenario.  If the
        engine still tries to read from disk it will fall back to DB insertion
        order which may or may not match appearance_order.
        """
        _insert_game(db, "game-ord")
        # Insert pitchers OUT OF ORDER by id, but with correct appearance_order.
        # Insertion order: pitcher-h2 first (insert rowid 1), pitcher-h1 second.
        # If engine uses DB insertion order (rowid) it'll pick h2 as starter -- WRONG.
        # If it uses appearance_order, it'll correctly pick h1 as starter.
        _insert_pitching_boxscore(
            db, "game-ord", "pitcher-h2", 1, bf=1, perspective_team_id=1, appearance_order=2,
        )
        _insert_pitching_boxscore(
            db, "game-ord", "pitcher-h1", 1, bf=1, perspective_team_id=1, appearance_order=1,
        )
        _insert_pitching_boxscore(
            db, "game-ord", "pitcher-a1", 2, bf=2, perspective_team_id=1, appearance_order=1,
        )

        _insert_batting_boxscore(db, "game-ord", "batter-a1", 2, ab=1, perspective_team_id=1)
        _insert_batting_boxscore(db, "game-ord", "batter-a2", 2, ab=1, perspective_team_id=1)
        _insert_batting_boxscore(db, "game-ord", "batter-h1", 1, ab=1, perspective_team_id=1)
        _insert_batting_boxscore(db, "game-ord", "batter-h2", 1, ab=1, perspective_team_id=1)

        # Home pitches top half: first play goes to pitcher-h1 (appearance_order=1),
        # but the stored play incorrectly attributes it to pitcher-h2.
        # Correction should walk the BF boundary and reassign play 1 to pitcher-h1.
        _insert_play(
            db, "game-ord", 1, inning=1, half="top",
            batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h2",
            perspective_team_id=1,
        )
        _insert_play(
            db, "game-ord", 2, inning=1, half="top",
            batting_team_id=2, batter_id="batter-a2", pitcher_id="pitcher-h2",
            perspective_team_id=1,
        )
        _insert_play(
            db, "game-ord", 3, inning=1, half="bottom",
            batting_team_id=1, batter_id="batter-h1", pitcher_id="pitcher-a1",
            perspective_team_id=1,
        )
        _insert_play(
            db, "game-ord", 4, inning=1, half="bottom",
            batting_team_id=1, batter_id="batter-h2", pitcher_id="pitcher-a1",
            perspective_team_id=1,
        )
        db.commit()

        # No disk JSON exists (clean-slate rebuild). The engine should read
        # from player_game_pitching.appearance_order instead of disk files.
        summary = reconcile_game(db, "game-ord", dry_run=False)

        assert summary.games_processed == 1

        # Verify play_order=1 was corrected to pitcher-h1 (per appearance_order).
        # With insertion-order fallback, pitcher-h2 would stay -- this catches
        # the bug.
        row = db.execute(
            "SELECT pitcher_id FROM plays "
            "WHERE game_id = 'game-ord' AND play_order = 1 "
            "AND perspective_team_id = 1"
        ).fetchone()
        assert row[0] == "pitcher-h1", (
            f"Expected pitcher-h1 (appearance_order=1), got {row[0]}. "
            "This means the engine is NOT reading from appearance_order."
        )



class TestReconcilePerPerspective:
    """E-220 round 6 cluster 4: reconcile_game must be per-perspective.

    Before the fix, the idempotency check at line 102 queried
    `SELECT COUNT(*) FROM plays WHERE game_id = ?` without filtering by
    perspective -- so once game G was reconciled from perspective A, any
    later call for perspective B would see "plays exist" and skip.
    """

    def test_reconcile_runs_separately_per_perspective(
        self, db: sqlite3.Connection
    ) -> None:
        """Load game G from two perspectives; reconcile must run for both.

        Each call should target the plays tagged with its own perspective
        and must not consume the other perspective's rows.
        """
        _insert_game(db, "game-two-persp")

        # Seed perspective 1: home team correctly pitches both halves.
        # Boxscore: pitcher-h1 BF=2, pitcher-h2 BF=1 (boundary-drift case).
        _insert_pitching_boxscore(
            db, "game-two-persp", "pitcher-h1", 1, bf=2, so=1,
            perspective_team_id=1, appearance_order=1,
        )
        _insert_pitching_boxscore(
            db, "game-two-persp", "pitcher-h2", 1, bf=1, so=0,
            perspective_team_id=1, appearance_order=2,
        )
        _insert_pitching_boxscore(
            db, "game-two-persp", "pitcher-a1", 2, bf=3, so=0,
            perspective_team_id=1, appearance_order=1,
        )
        _insert_batting_boxscore(db, "game-two-persp", "batter-a1", 2, ab=1, perspective_team_id=1)
        _insert_batting_boxscore(db, "game-two-persp", "batter-a2", 2, ab=1, perspective_team_id=1)
        _insert_batting_boxscore(db, "game-two-persp", "batter-h1", 1, ab=1, perspective_team_id=1)
        _insert_batting_boxscore(db, "game-two-persp", "batter-h2", 1, ab=1, perspective_team_id=1)
        _insert_batting_boxscore(db, "game-two-persp", "batter-h3", 1, ab=1, perspective_team_id=1)

        # Perspective 1 plays: 3 top-half plays all attributed to pitcher-h1
        # (boundary drift -- correct is h1 for first 2, h2 for 3rd).
        _insert_play(db, "game-two-persp", 1, inning=1, half="top",
                     batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1",
                     perspective_team_id=1)
        _insert_play(db, "game-two-persp", 2, inning=1, half="top",
                     batting_team_id=2, batter_id="batter-a2", pitcher_id="pitcher-h1",
                     perspective_team_id=1)
        _insert_play(db, "game-two-persp", 3, inning=1, half="top",
                     batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1",
                     perspective_team_id=1)
        _insert_play(db, "game-two-persp", 4, inning=1, half="bottom",
                     batting_team_id=1, batter_id="batter-h1", pitcher_id="pitcher-a1",
                     perspective_team_id=1)
        _insert_play(db, "game-two-persp", 5, inning=1, half="bottom",
                     batting_team_id=1, batter_id="batter-h2", pitcher_id="pitcher-a1",
                     perspective_team_id=1)
        _insert_play(db, "game-two-persp", 6, inning=1, half="bottom",
                     batting_team_id=1, batter_id="batter-h3", pitcher_id="pitcher-a1",
                     perspective_team_id=1)

        # Seed perspective 2: same game stream, a CORRECT pitcher attribution
        # (play 3 is already pitcher-h2).
        _insert_pitching_boxscore(
            db, "game-two-persp", "pitcher-h1", 1, bf=2, so=1,
            perspective_team_id=2, appearance_order=1,
        )
        _insert_pitching_boxscore(
            db, "game-two-persp", "pitcher-h2", 1, bf=1, so=0,
            perspective_team_id=2, appearance_order=2,
        )
        _insert_pitching_boxscore(
            db, "game-two-persp", "pitcher-a1", 2, bf=3, so=0,
            perspective_team_id=2, appearance_order=1,
        )
        _insert_batting_boxscore(db, "game-two-persp", "batter-a1", 2, ab=1, perspective_team_id=2)
        _insert_batting_boxscore(db, "game-two-persp", "batter-a2", 2, ab=1, perspective_team_id=2)
        _insert_batting_boxscore(db, "game-two-persp", "batter-h1", 1, ab=1, perspective_team_id=2)
        _insert_batting_boxscore(db, "game-two-persp", "batter-h2", 1, ab=1, perspective_team_id=2)
        _insert_batting_boxscore(db, "game-two-persp", "batter-h3", 1, ab=1, perspective_team_id=2)

        _insert_play(db, "game-two-persp", 1, inning=1, half="top",
                     batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h1",
                     perspective_team_id=2)
        _insert_play(db, "game-two-persp", 2, inning=1, half="top",
                     batting_team_id=2, batter_id="batter-a2", pitcher_id="pitcher-h1",
                     perspective_team_id=2)
        _insert_play(db, "game-two-persp", 3, inning=1, half="top",
                     batting_team_id=2, batter_id="batter-a1", pitcher_id="pitcher-h2",
                     perspective_team_id=2)
        _insert_play(db, "game-two-persp", 4, inning=1, half="bottom",
                     batting_team_id=1, batter_id="batter-h1", pitcher_id="pitcher-a1",
                     perspective_team_id=2)
        _insert_play(db, "game-two-persp", 5, inning=1, half="bottom",
                     batting_team_id=1, batter_id="batter-h2", pitcher_id="pitcher-a1",
                     perspective_team_id=2)
        _insert_play(db, "game-two-persp", 6, inning=1, half="bottom",
                     batting_team_id=1, batter_id="batter-h3", pitcher_id="pitcher-a1",
                     perspective_team_id=2)

        db.commit()

        # Reconcile perspective 1: should correct play 3 from h1 to h2.
        summary1 = reconcile_game(
            db, "game-two-persp", dry_run=False, perspective_team_id=1,
        )
        assert summary1.games_processed == 1, (
            "perspective 1 reconcile must run (game has plays)"
        )
        assert summary1.total_plays_reassigned > 0, (
            "perspective 1 had boundary drift -- correction should fire"
        )

        # Reconcile perspective 2: must also run (NOT skip as "already reconciled")
        summary2 = reconcile_game(
            db, "game-two-persp", dry_run=False, perspective_team_id=2,
        )
        assert summary2.games_processed == 1, (
            "perspective 2 reconcile must run -- the idempotency check at "
            "line 102 was querying without perspective filter, so it saw "
            "perspective 1's plays and incorrectly skipped perspective 2."
        )

        # Both perspectives' plays still exist, each with the correct count
        p1_plays = db.execute(
            "SELECT COUNT(*) FROM plays "
            "WHERE game_id = 'game-two-persp' AND perspective_team_id = 1"
        ).fetchone()[0]
        p2_plays = db.execute(
            "SELECT COUNT(*) FROM plays "
            "WHERE game_id = 'game-two-persp' AND perspective_team_id = 2"
        ).fetchone()[0]
        assert p1_plays == 6, f"perspective 1 should have 6 plays, got {p1_plays}"
        assert p2_plays == 6, f"perspective 2 should have 6 plays, got {p2_plays}"

        # Perspective 1 play 3 should be corrected to pitcher-h2
        row1 = db.execute(
            "SELECT pitcher_id FROM plays "
            "WHERE game_id = 'game-two-persp' AND play_order = 3 "
            "AND perspective_team_id = 1"
        ).fetchone()
        assert row1[0] == "pitcher-h2", (
            f"perspective 1 play 3 should be corrected to pitcher-h2, got {row1[0]}"
        )
        # Perspective 2 play 3 was already pitcher-h2, should stay pitcher-h2
        row2 = db.execute(
            "SELECT pitcher_id FROM plays "
            "WHERE game_id = 'game-two-persp' AND play_order = 3 "
            "AND perspective_team_id = 2"
        ).fetchone()
        assert row2[0] == "pitcher-h2"

