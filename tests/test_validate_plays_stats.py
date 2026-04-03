"""Tests for scripts/validate_plays_stats.py (E-195-05).

Covers:
- AC-1: FPS comparison per pitcher (derived vs GC).
- AC-2: QAB comparison per batter (derived vs GC).
- AC-3: Summary report: per-player comparison, match rate, tolerance check.
- AC-4: Diagnostic detail for players exceeding 5% tolerance.
- AC-5: Plays data coverage reporting.
- AC-7: Unit tests use synthetic data in in-memory SQLite.

All tests use an on-disk SQLite database (tmp_path) with all migrations
applied.  No real network calls or game data needed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from migrations.apply_migrations import run_migrations

# Import the functions under test.
# sys.path manipulation is in the script itself, but since tests run via
# pytest with the editable install, we can import directly.
from scripts.validate_plays_stats import (
    build_report,
    compare_stats,
    compute_coverage,
    compute_derived_fps,
    compute_derived_qab,
    compute_match_rate,
    format_report,
    get_fps_game_diagnostics,
    get_gc_fps,
    get_gc_qab,
    get_qab_game_diagnostics,
    get_qab_sample_plays,
    main,
    PlayerComparison,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEASON_ID = "2026-spring-hs"
_GAME_ID_1 = "game-001"
_GAME_ID_2 = "game-002"
_GAME_ID_3 = "game-003"

_PITCHER_A = "a0000000-0000-0000-0000-000000000001"
_PITCHER_B = "b0000000-0000-0000-0000-000000000002"
_BATTER_X = "c0000000-0000-0000-0000-000000000003"
_BATTER_Y = "d0000000-0000-0000-0000-000000000004"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    """Apply all migrations and return an open connection."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def _seed_base_data(db: sqlite3.Connection) -> tuple[int, int]:
    """Insert base data (season, teams, players) needed by all tests.

    Returns:
        Tuple of (home_team_id, away_team_id).
    """
    # Season
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, 'Spring 2026 HS', 'spring-hs', 2026)",
        (_SEASON_ID,),
    )

    # Teams
    db.execute(
        "INSERT INTO teams (name, membership_type, is_active) "
        "VALUES ('Home Eagles', 'member', 1)",
    )
    home_id = db.execute(
        "SELECT id FROM teams WHERE name = 'Home Eagles'"
    ).fetchone()[0]

    db.execute(
        "INSERT INTO teams (name, membership_type, is_active) "
        "VALUES ('Away Wolves', 'tracked', 1)",
    )
    away_id = db.execute(
        "SELECT id FROM teams WHERE name = 'Away Wolves'"
    ).fetchone()[0]

    # Players
    for pid, first, last in [
        (_PITCHER_A, "Alice", "Ace"),
        (_PITCHER_B, "Bob", "Bolt"),
        (_BATTER_X, "Xavier", "Cross"),
        (_BATTER_Y, "Yolanda", "Yard"),
    ]:
        db.execute(
            "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
            "VALUES (?, ?, ?)",
            (pid, first, last),
        )

    db.commit()
    return home_id, away_id


def _insert_game(
    db: sqlite3.Connection,
    game_id: str,
    home_id: int,
    away_id: int,
    *,
    status: str = "completed",
    home_score: int | None = 5,
) -> None:
    """Insert a game row."""
    db.execute(
        "INSERT OR IGNORE INTO games "
        "(game_id, season_id, game_date, home_team_id, away_team_id, "
        " home_score, away_score, status) "
        "VALUES (?, ?, '2026-04-01', ?, ?, ?, 3, ?)",
        (game_id, _SEASON_ID, home_id, away_id, home_score, status),
    )
    db.commit()


def _insert_play(
    db: sqlite3.Connection,
    game_id: str,
    play_order: int,
    batter_id: str,
    pitcher_id: str | None,
    batting_team_id: int,
    *,
    outcome: str = "Single",
    pitch_count: int = 3,
    is_fps: int = 0,
    is_qab: int = 0,
    inning: int = 1,
    half: str = "top",
) -> None:
    """Insert a play row into the plays table."""
    db.execute(
        """
        INSERT INTO plays (
            game_id, play_order, inning, half, season_id, batting_team_id,
            batter_id, pitcher_id, outcome, pitch_count,
            is_first_pitch_strike, is_qab,
            home_score, away_score, did_score_change, outs_after, did_outs_change
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0)
        """,
        (
            game_id, play_order, inning, half, _SEASON_ID, batting_team_id,
            batter_id, pitcher_id, outcome, pitch_count,
            is_fps, is_qab,
        ),
    )


def _insert_season_pitching(
    db: sqlite3.Connection,
    player_id: str,
    team_id: int,
    fps: int | None,
) -> None:
    """Insert a row into player_season_pitching with an FPS value."""
    db.execute(
        "INSERT INTO player_season_pitching "
        "(player_id, team_id, season_id, fps) "
        "VALUES (?, ?, ?, ?)",
        (player_id, team_id, _SEASON_ID, fps),
    )
    db.commit()


def _insert_season_batting(
    db: sqlite3.Connection,
    player_id: str,
    team_id: int,
    qab: int | None,
) -> None:
    """Insert a row into player_season_batting with a QAB value."""
    db.execute(
        "INSERT INTO player_season_batting "
        "(player_id, team_id, season_id, qab) "
        "VALUES (?, ?, ?, ?)",
        (player_id, team_id, _SEASON_ID, qab),
    )
    db.commit()


# ---------------------------------------------------------------------------
# AC-1: FPS comparison per pitcher
# ---------------------------------------------------------------------------


class TestFPSComparison:
    """FPS derivation and comparison tests (AC-1)."""

    def test_compute_derived_fps_includes_hbp_and_ibb(
        self, db: sqlite3.Connection,
    ):
        """Derived FPS includes HBP and IBB outcomes (matches GC formula)."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)

        # 4 PAs for pitcher A: 2 with FPS=1, 1 with FPS=0, 1 HBP with FPS=1.
        _insert_play(db, _GAME_ID_1, 0, _BATTER_X, _PITCHER_A, away_id, is_fps=1)
        _insert_play(db, _GAME_ID_1, 1, _BATTER_X, _PITCHER_A, away_id, is_fps=1)
        _insert_play(db, _GAME_ID_1, 2, _BATTER_X, _PITCHER_A, away_id, is_fps=0)
        _insert_play(
            db, _GAME_ID_1, 3, _BATTER_X, _PITCHER_A, away_id,
            is_fps=1, outcome="Hit By Pitch",
        )
        db.commit()

        result = compute_derived_fps(db)
        # All 4 plays count (HBP included), 3 have FPS=1.
        assert result[(_PITCHER_A, _SEASON_ID)] == 3

    def test_compute_derived_fps_includes_intentional_walk(
        self, db: sqlite3.Connection,
    ):
        """Derived FPS includes Intentional Walk outcomes (IBB with FPS=0 adds 0)."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)

        _insert_play(db, _GAME_ID_1, 0, _BATTER_X, _PITCHER_A, away_id, is_fps=1)
        _insert_play(
            db, _GAME_ID_1, 1, _BATTER_X, _PITCHER_A, away_id,
            is_fps=0, outcome="Intentional Walk",
        )
        db.commit()

        result = compute_derived_fps(db)
        assert result[(_PITCHER_A, _SEASON_ID)] == 1

    def test_compare_fps_exact_match(self, db: sqlite3.Connection):
        """Pitcher with exact match should not exceed tolerance."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)

        # Pitcher A: 10 FPS in plays.
        for i in range(10):
            _insert_play(
                db, _GAME_ID_1, i, _BATTER_X, _PITCHER_A, away_id, is_fps=1,
            )
        db.commit()

        _insert_season_pitching(db, _PITCHER_A, home_id, fps=10)

        derived = compute_derived_fps(db)
        gc = get_gc_fps(db)
        comparisons = compare_stats(db, derived, gc, "player_season_pitching")

        assert len(comparisons) == 1
        assert comparisons[0].derived_value == 10
        assert comparisons[0].gc_value == 10
        assert comparisons[0].abs_diff == 0
        assert comparisons[0].pct_diff == 0.0
        assert not comparisons[0].exceeds_tolerance

    def test_compare_fps_within_tolerance(self, db: sqlite3.Connection):
        """Pitcher within 5% tolerance should be OK."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)

        # Pitcher A: 19 FPS in plays, GC says 20 -> 5% diff (at boundary).
        for i in range(19):
            _insert_play(
                db, _GAME_ID_1, i, _BATTER_X, _PITCHER_A, away_id, is_fps=1,
            )
        db.commit()

        _insert_season_pitching(db, _PITCHER_A, home_id, fps=20)

        derived = compute_derived_fps(db)
        gc = get_gc_fps(db)
        comparisons = compare_stats(db, derived, gc, "player_season_pitching")

        assert len(comparisons) == 1
        assert comparisons[0].pct_diff == pytest.approx(5.0)
        assert not comparisons[0].exceeds_tolerance

    def test_compare_fps_exceeds_tolerance(self, db: sqlite3.Connection):
        """Pitcher exceeding 5% tolerance should be flagged."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)

        # Pitcher A: 8 FPS in plays, GC says 10 -> 20% diff.
        for i in range(8):
            _insert_play(
                db, _GAME_ID_1, i, _BATTER_X, _PITCHER_A, away_id, is_fps=1,
            )
        # 2 more plays with FPS=0 to have total plays.
        for i in range(8, 12):
            _insert_play(
                db, _GAME_ID_1, i, _BATTER_X, _PITCHER_A, away_id, is_fps=0,
            )
        db.commit()

        _insert_season_pitching(db, _PITCHER_A, home_id, fps=10)

        derived = compute_derived_fps(db)
        gc = get_gc_fps(db)
        comparisons = compare_stats(db, derived, gc, "player_season_pitching")

        assert len(comparisons) == 1
        assert comparisons[0].derived_value == 8
        assert comparisons[0].gc_value == 10
        assert comparisons[0].exceeds_tolerance

    def test_fps_only_compares_common_players(self, db: sqlite3.Connection):
        """FPS comparison only includes pitchers with data in both sources."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)

        # Pitcher A has plays data but no season stats.
        _insert_play(
            db, _GAME_ID_1, 0, _BATTER_X, _PITCHER_A, away_id, is_fps=1,
        )
        db.commit()

        # Pitcher B has season stats but no plays data.
        _insert_season_pitching(db, _PITCHER_B, home_id, fps=5)

        derived = compute_derived_fps(db)
        gc = get_gc_fps(db)
        comparisons = compare_stats(db, derived, gc, "player_season_pitching")

        assert len(comparisons) == 0

    def test_fps_multiple_pitchers_across_games(self, db: sqlite3.Connection):
        """FPS aggregation works across multiple games and pitchers."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)
        _insert_game(db, _GAME_ID_2, home_id, away_id)

        # Pitcher A: 3 FPS in game 1, 2 FPS in game 2 -> total 5.
        for i in range(3):
            _insert_play(
                db, _GAME_ID_1, i, _BATTER_X, _PITCHER_A, away_id, is_fps=1,
            )
        for i in range(2):
            _insert_play(
                db, _GAME_ID_2, i, _BATTER_X, _PITCHER_A, away_id, is_fps=1,
            )

        # Pitcher B: 4 FPS in game 1.
        for i in range(3, 7):
            _insert_play(
                db, _GAME_ID_1, i, _BATTER_Y, _PITCHER_B, away_id, is_fps=1,
            )
        db.commit()

        _insert_season_pitching(db, _PITCHER_A, home_id, fps=5)
        _insert_season_pitching(db, _PITCHER_B, home_id, fps=4)

        derived = compute_derived_fps(db)
        gc = get_gc_fps(db)
        comparisons = compare_stats(db, derived, gc, "player_season_pitching")

        assert len(comparisons) == 2
        by_name = {c.player_name: c for c in comparisons}
        assert by_name["Alice Ace"].derived_value == 5
        assert by_name["Alice Ace"].gc_value == 5
        assert not by_name["Alice Ace"].exceeds_tolerance
        assert by_name["Bob Bolt"].derived_value == 4
        assert by_name["Bob Bolt"].gc_value == 4
        assert not by_name["Bob Bolt"].exceeds_tolerance


# ---------------------------------------------------------------------------
# AC-2: QAB comparison per batter
# ---------------------------------------------------------------------------


class TestQABComparison:
    """QAB derivation and comparison tests (AC-2)."""

    def test_compute_derived_qab_counts_all_batters(
        self, db: sqlite3.Connection,
    ):
        """Derived QAB counts include all plays regardless of outcome."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)

        # Batter X: 3 PAs, 2 are QABs.
        _insert_play(
            db, _GAME_ID_1, 0, _BATTER_X, _PITCHER_A, away_id, is_qab=1,
        )
        _insert_play(
            db, _GAME_ID_1, 1, _BATTER_X, _PITCHER_A, away_id, is_qab=0,
        )
        _insert_play(
            db, _GAME_ID_1, 2, _BATTER_X, _PITCHER_A, away_id, is_qab=1,
        )
        db.commit()

        result = compute_derived_qab(db)
        assert result[(_BATTER_X, _SEASON_ID)] == 2

    def test_compare_qab_exact_match(self, db: sqlite3.Connection):
        """Batter with exact QAB match should not exceed tolerance."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)

        for i in range(8):
            _insert_play(
                db, _GAME_ID_1, i, _BATTER_X, _PITCHER_A, away_id, is_qab=1,
            )
        db.commit()

        _insert_season_batting(db, _BATTER_X, away_id, qab=8)

        derived = compute_derived_qab(db)
        gc = get_gc_qab(db)
        comparisons = compare_stats(db, derived, gc, "player_season_batting")

        assert len(comparisons) == 1
        assert comparisons[0].derived_value == 8
        assert comparisons[0].gc_value == 8
        assert not comparisons[0].exceeds_tolerance

    def test_compare_qab_exceeds_tolerance(self, db: sqlite3.Connection):
        """Batter exceeding 5% QAB tolerance should be flagged."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)

        # Batter X: 6 QABs in plays, GC says 10 -> 40% diff.
        for i in range(6):
            _insert_play(
                db, _GAME_ID_1, i, _BATTER_X, _PITCHER_A, away_id, is_qab=1,
            )
        for i in range(6, 15):
            _insert_play(
                db, _GAME_ID_1, i, _BATTER_X, _PITCHER_A, away_id, is_qab=0,
            )
        db.commit()

        _insert_season_batting(db, _BATTER_X, away_id, qab=10)

        derived = compute_derived_qab(db)
        gc = get_gc_qab(db)
        comparisons = compare_stats(db, derived, gc, "player_season_batting")

        assert len(comparisons) == 1
        assert comparisons[0].exceeds_tolerance

    def test_qab_multiple_batters_across_games(self, db: sqlite3.Connection):
        """QAB aggregation works across multiple games for multiple batters."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)
        _insert_game(db, _GAME_ID_2, home_id, away_id)

        # Batter X: 2 QABs in game 1, 3 QABs in game 2 -> 5 total.
        for i in range(2):
            _insert_play(
                db, _GAME_ID_1, i, _BATTER_X, _PITCHER_A, away_id, is_qab=1,
            )
        for i in range(3):
            _insert_play(
                db, _GAME_ID_2, i, _BATTER_X, _PITCHER_A, away_id, is_qab=1,
            )

        # Batter Y: 1 QAB in game 1.
        _insert_play(
            db, _GAME_ID_1, 10, _BATTER_Y, _PITCHER_B, away_id, is_qab=1,
        )
        db.commit()

        _insert_season_batting(db, _BATTER_X, away_id, qab=5)
        _insert_season_batting(db, _BATTER_Y, away_id, qab=1)

        derived = compute_derived_qab(db)
        gc = get_gc_qab(db)
        comparisons = compare_stats(db, derived, gc, "player_season_batting")

        assert len(comparisons) == 2
        by_name = {c.player_name: c for c in comparisons}
        assert by_name["Xavier Cross"].derived_value == 5
        assert not by_name["Xavier Cross"].exceeds_tolerance
        assert by_name["Yolanda Yard"].derived_value == 1
        assert not by_name["Yolanda Yard"].exceeds_tolerance


# ---------------------------------------------------------------------------
# AC-3: Summary report, match rate, tolerance
# ---------------------------------------------------------------------------


class TestMatchRate:
    """Match rate computation tests (AC-3)."""

    def test_all_within_tolerance(self):
        """100% match rate when all players are within tolerance."""
        comps = [
            PlayerComparison(
                player_id="p1", season_id="s1", player_name="A", team_name="T",
                derived_value=10, gc_value=10, abs_diff=0,
                pct_diff=0.0, exceeds_tolerance=False,
            ),
            PlayerComparison(
                player_id="p2", season_id="s1", player_name="B", team_name="T",
                derived_value=9, gc_value=10, abs_diff=1,
                pct_diff=10.0, exceeds_tolerance=False,
            ),
        ]
        assert compute_match_rate(comps) == 100.0

    def test_some_exceed_tolerance(self):
        """Match rate reflects only players within tolerance."""
        comps = [
            PlayerComparison(
                player_id="p1", season_id="s1", player_name="A", team_name="T",
                derived_value=10, gc_value=10, abs_diff=0,
                pct_diff=0.0, exceeds_tolerance=False,
            ),
            PlayerComparison(
                player_id="p2", season_id="s1", player_name="B", team_name="T",
                derived_value=5, gc_value=10, abs_diff=5,
                pct_diff=50.0, exceeds_tolerance=True,
            ),
        ]
        assert compute_match_rate(comps) == pytest.approx(50.0)

    def test_no_comparisons_returns_100(self):
        """Empty comparison list gives 100% match rate."""
        assert compute_match_rate([]) == 100.0


class TestFormatReport:
    """Report formatting tests (AC-3)."""

    def test_format_report_contains_key_sections(self, db: sqlite3.Connection):
        """Report markdown contains all required sections."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)
        _insert_play(
            db, _GAME_ID_1, 0, _BATTER_X, _PITCHER_A, away_id,
            is_fps=1, is_qab=1,
        )
        db.commit()
        _insert_season_pitching(db, _PITCHER_A, home_id, fps=1)
        _insert_season_batting(db, _BATTER_X, away_id, qab=1)

        report = build_report(db)
        md = format_report(report)

        assert "# E-195 Plays Pipeline Validation Results" in md
        assert "## Plays Data Coverage" in md
        assert "## FPS (First Pitch Strike) Comparison" in md
        assert "## QAB (Quality At-Bat) Comparison" in md
        assert "## Summary" in md
        assert "Overall match rate" in md

    def test_format_report_shows_mismatch_status(self, db: sqlite3.Connection):
        """Report shows MISMATCH for players exceeding tolerance."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)

        # Create a big discrepancy: 1 FPS derived vs 20 GC.
        _insert_play(
            db, _GAME_ID_1, 0, _BATTER_X, _PITCHER_A, away_id, is_fps=1,
        )
        for i in range(1, 10):
            _insert_play(
                db, _GAME_ID_1, i, _BATTER_X, _PITCHER_A, away_id, is_fps=0,
            )
        db.commit()
        _insert_season_pitching(db, _PITCHER_A, home_id, fps=20)

        report = build_report(db)
        md = format_report(report)

        assert "MISMATCH" in md
        assert "Alice Ace" in md


# ---------------------------------------------------------------------------
# AC-4: Diagnostic detail for tolerance exceedances
# ---------------------------------------------------------------------------


class TestDiagnostics:
    """Diagnostic detail tests for players exceeding tolerance (AC-4)."""

    def test_fps_diagnostics_for_outlier(self, db: sqlite3.Connection):
        """FPS diagnostics show per-game breakdown for outlier pitchers."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)
        _insert_game(db, _GAME_ID_2, home_id, away_id)

        # Pitcher A: 2 FPS in game 1, 1 FPS in game 2 -> 3 total.
        for i in range(2):
            _insert_play(
                db, _GAME_ID_1, i, _BATTER_X, _PITCHER_A, away_id, is_fps=1,
            )
        _insert_play(
            db, _GAME_ID_2, 0, _BATTER_X, _PITCHER_A, away_id, is_fps=1,
        )
        # Add non-FPS plays.
        for i in range(2, 6):
            _insert_play(
                db, _GAME_ID_1, i, _BATTER_X, _PITCHER_A, away_id, is_fps=0,
            )
        db.commit()

        diags = get_fps_game_diagnostics(db, _PITCHER_A)
        assert len(diags) == 2
        # Game 1: 6 PAs (4 non-fps + 2 fps), 2 FPS.
        g1 = next(d for d in diags if d.game_id == _GAME_ID_1)
        assert g1.play_count == 6
        assert g1.flag_count == 2
        # Game 2: 1 PA, 1 FPS.
        g2 = next(d for d in diags if d.game_id == _GAME_ID_2)
        assert g2.play_count == 1
        assert g2.flag_count == 1

    def test_qab_diagnostics_for_outlier(self, db: sqlite3.Connection):
        """QAB diagnostics show per-game breakdown for outlier batters."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)

        _insert_play(
            db, _GAME_ID_1, 0, _BATTER_X, _PITCHER_A, away_id, is_qab=1,
        )
        _insert_play(
            db, _GAME_ID_1, 1, _BATTER_X, _PITCHER_A, away_id, is_qab=0,
        )
        _insert_play(
            db, _GAME_ID_1, 2, _BATTER_X, _PITCHER_A, away_id, is_qab=1,
        )
        db.commit()

        diags = get_qab_game_diagnostics(db, _BATTER_X)
        assert len(diags) == 1
        assert diags[0].play_count == 3
        assert diags[0].flag_count == 2

    def test_sample_plays_for_qab_outlier(self, db: sqlite3.Connection):
        """Sample plays are returned for QAB outlier investigation."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)

        _insert_play(
            db, _GAME_ID_1, 0, _BATTER_X, _PITCHER_A, away_id,
            is_qab=1, outcome="Double", pitch_count=4, inning=2, half="bottom",
        )
        db.commit()

        samples = get_qab_sample_plays(db, _BATTER_X)
        assert len(samples) == 1
        assert samples[0].game_id == _GAME_ID_1
        assert samples[0].outcome == "Double"
        assert samples[0].flag_value == 1
        assert samples[0].inning == 2

    def test_build_report_includes_diagnostics_for_outliers(
        self, db: sqlite3.Connection,
    ):
        """build_report populates diagnostics dicts for tolerance exceedances."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)

        # Create FPS outlier: derived=1, GC=20.
        _insert_play(
            db, _GAME_ID_1, 0, _BATTER_X, _PITCHER_A, away_id, is_fps=1,
        )
        for i in range(1, 5):
            _insert_play(
                db, _GAME_ID_1, i, _BATTER_X, _PITCHER_A, away_id, is_fps=0,
            )
        db.commit()
        _insert_season_pitching(db, _PITCHER_A, home_id, fps=20)

        report = build_report(db)
        assert _PITCHER_A in report.fps_diagnostics
        assert len(report.fps_diagnostics[_PITCHER_A]) > 0
        assert _PITCHER_A in report.fps_sample_plays
        assert len(report.fps_sample_plays[_PITCHER_A]) > 0

    def test_format_report_includes_diagnostic_tables(
        self, db: sqlite3.Connection,
    ):
        """Formatted report includes diagnostic tables for outliers."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)

        # Create FPS outlier.
        _insert_play(
            db, _GAME_ID_1, 0, _BATTER_X, _PITCHER_A, away_id, is_fps=1,
        )
        for i in range(1, 5):
            _insert_play(
                db, _GAME_ID_1, i, _BATTER_X, _PITCHER_A, away_id, is_fps=0,
            )
        db.commit()
        _insert_season_pitching(db, _PITCHER_A, home_id, fps=20)

        report = build_report(db)
        md = format_report(report)

        assert "### FPS Discrepancy Diagnostics" in md
        assert "Per-game breakdown" in md
        assert "Sample plays" in md


# ---------------------------------------------------------------------------
# AC-5: Plays data coverage
# ---------------------------------------------------------------------------


class TestCoverage:
    """Plays data coverage reporting tests (AC-5)."""

    def test_coverage_counts_completed_games(self, db: sqlite3.Connection):
        """Coverage correctly counts completed vs games-with-plays."""
        home_id, away_id = _seed_base_data(db)

        # 3 completed games, 1 scheduled.
        _insert_game(db, _GAME_ID_1, home_id, away_id, status="completed")
        _insert_game(db, _GAME_ID_2, home_id, away_id, status="completed")
        _insert_game(db, _GAME_ID_3, home_id, away_id, status="completed")
        _insert_game(
            db, "game-004", home_id, away_id, status="scheduled", home_score=None,
        )

        # Only games 1 and 2 have plays.
        _insert_play(
            db, _GAME_ID_1, 0, _BATTER_X, _PITCHER_A, away_id,
        )
        _insert_play(
            db, _GAME_ID_2, 0, _BATTER_X, _PITCHER_A, away_id,
        )
        db.commit()

        total, with_plays, without_plays = compute_coverage(db)
        assert total == 3
        assert with_plays == 2
        assert len(without_plays) == 1
        assert without_plays[0][0] == _GAME_ID_3

    def test_coverage_excludes_tracked_vs_tracked_games(
        self, db: sqlite3.Connection,
    ):
        """Games between two tracked teams are excluded from coverage."""
        home_id, away_id = _seed_base_data(db)

        # Create a second tracked team.
        db.execute(
            "INSERT INTO teams (name, membership_type, is_active) "
            "VALUES ('Tracked Rivals', 'tracked', 1)",
        )
        tracked2_id = db.execute(
            "SELECT id FROM teams WHERE name = 'Tracked Rivals'"
        ).fetchone()[0]

        # Game between member (home) and tracked (away) -- should count.
        _insert_game(db, _GAME_ID_1, home_id, away_id, status="completed")

        # Game between two tracked teams -- should NOT count.
        _insert_game(db, _GAME_ID_2, away_id, tracked2_id, status="completed")
        db.commit()

        total, with_plays, without_plays = compute_coverage(db)
        assert total == 1  # Only the member-team game.

    def test_coverage_zero_completed_games(self, db: sqlite3.Connection):
        """Coverage handles no completed games gracefully."""
        _seed_base_data(db)

        total, with_plays, without_plays = compute_coverage(db)
        assert total == 0
        assert with_plays == 0
        assert without_plays == []

    def test_coverage_all_games_have_plays(self, db: sqlite3.Connection):
        """Coverage is 100% when all completed games have plays."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)
        _insert_play(
            db, _GAME_ID_1, 0, _BATTER_X, _PITCHER_A, away_id,
        )
        db.commit()

        total, with_plays, without_plays = compute_coverage(db)
        assert total == 1
        assert with_plays == 1
        assert without_plays == []

    def test_coverage_in_formatted_report(self, db: sqlite3.Connection):
        """Coverage section appears in the formatted report."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)
        _insert_game(db, _GAME_ID_2, home_id, away_id)
        _insert_play(
            db, _GAME_ID_1, 0, _BATTER_X, _PITCHER_A, away_id,
        )
        db.commit()

        report = build_report(db)
        md = format_report(report)

        assert "Completed games" in md
        assert "Games with plays data" in md
        assert "Games without plays data" in md
        assert "Games Missing Plays Data" in md


# ---------------------------------------------------------------------------
# AC-7: Integration / synthetic data test
# ---------------------------------------------------------------------------


class TestBuildReport:
    """Full build_report integration with synthetic data (AC-7)."""

    def test_build_report_empty_db(self, db: sqlite3.Connection):
        """build_report handles empty database gracefully."""
        _seed_base_data(db)

        report = build_report(db)
        assert report.fps_comparisons == []
        assert report.qab_comparisons == []
        assert report.fps_match_rate == 100.0
        assert report.qab_match_rate == 100.0
        assert report.total_completed_games == 0

    def test_build_report_mixed_results(self, db: sqlite3.Connection):
        """build_report produces correct results with mixed match/mismatch."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)
        _insert_game(db, _GAME_ID_2, home_id, away_id)

        # Pitcher A: 5 FPS derived, 5 GC (exact match).
        for i in range(5):
            _insert_play(
                db, _GAME_ID_1, i, _BATTER_X, _PITCHER_A, away_id, is_fps=1,
            )
        # Pitcher B: 1 FPS derived, 10 GC (big mismatch).
        _insert_play(
            db, _GAME_ID_2, 0, _BATTER_Y, _PITCHER_B, away_id, is_fps=1,
        )
        for i in range(1, 5):
            _insert_play(
                db, _GAME_ID_2, i, _BATTER_Y, _PITCHER_B, away_id, is_fps=0,
            )
        db.commit()

        _insert_season_pitching(db, _PITCHER_A, home_id, fps=5)
        _insert_season_pitching(db, _PITCHER_B, home_id, fps=10)

        report = build_report(db)
        assert len(report.fps_comparisons) == 2
        assert report.fps_match_rate == pytest.approx(50.0)

        # Pitcher B should have diagnostics.
        assert _PITCHER_B in report.fps_diagnostics

    def test_build_report_both_fps_and_qab(self, db: sqlite3.Connection):
        """build_report handles both FPS and QAB comparisons together."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)

        # Pitcher A with FPS, Batter X with QAB.
        _insert_play(
            db, _GAME_ID_1, 0, _BATTER_X, _PITCHER_A, away_id,
            is_fps=1, is_qab=1,
        )
        db.commit()

        _insert_season_pitching(db, _PITCHER_A, home_id, fps=1)
        _insert_season_batting(db, _BATTER_X, away_id, qab=1)

        report = build_report(db)
        assert len(report.fps_comparisons) == 1
        assert len(report.qab_comparisons) == 1
        assert report.fps_match_rate == 100.0
        assert report.qab_match_rate == 100.0


# ---------------------------------------------------------------------------
# AC-3/AC-6: Compare pct_diff edge cases
# ---------------------------------------------------------------------------


class TestPctDiffEdgeCases:
    """Edge cases for percentage difference calculation."""

    def test_both_zero_gives_zero_pct(self, db: sqlite3.Connection):
        """When both derived and GC are 0, pct_diff is 0."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)

        # Pitcher A: 0 FPS in plays (all non-strike first pitches).
        _insert_play(
            db, _GAME_ID_1, 0, _BATTER_X, _PITCHER_A, away_id, is_fps=0,
        )
        db.commit()

        _insert_season_pitching(db, _PITCHER_A, home_id, fps=0)

        derived = compute_derived_fps(db)
        gc = get_gc_fps(db)
        comparisons = compare_stats(db, derived, gc, "player_season_pitching")

        assert len(comparisons) == 1
        assert comparisons[0].pct_diff == 0.0
        assert not comparisons[0].exceeds_tolerance

    def test_gc_zero_derived_nonzero_gives_100_pct(
        self, db: sqlite3.Connection,
    ):
        """When GC is 0 but derived is non-zero, pct_diff is 100%."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)

        _insert_play(
            db, _GAME_ID_1, 0, _BATTER_X, _PITCHER_A, away_id, is_fps=1,
        )
        db.commit()

        _insert_season_pitching(db, _PITCHER_A, home_id, fps=0)

        derived = compute_derived_fps(db)
        gc = get_gc_fps(db)
        comparisons = compare_stats(db, derived, gc, "player_season_pitching")

        assert len(comparisons) == 1
        assert comparisons[0].pct_diff == 100.0
        assert comparisons[0].exceeds_tolerance


# ---------------------------------------------------------------------------
# CLI entry point test
# ---------------------------------------------------------------------------


class TestMainCLI:
    """CLI entry point tests."""

    def test_main_missing_db_returns_1(self, tmp_path: Path):
        """main() returns 1 when database file does not exist."""
        db_path = tmp_path / "nonexistent.db"
        result = main(["--db-path", str(db_path)])
        assert result == 1

    def test_main_success_writes_report(self, tmp_path: Path, db):
        """main() succeeds and writes a report file."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)
        _insert_play(
            db, _GAME_ID_1, 0, _BATTER_X, _PITCHER_A, away_id,
            is_fps=1, is_qab=1,
        )
        db.commit()
        _insert_season_pitching(db, _PITCHER_A, home_id, fps=1)
        _insert_season_batting(db, _BATTER_X, away_id, qab=1)
        db.close()

        # Re-extract the db path from the connection that was already closed.
        # Use the tmp_path pattern from the db fixture.
        db_path = tmp_path / "test.db"
        output_path = tmp_path / "results.md"

        result = main([
            "--db-path", str(db_path),
            "--output", str(output_path),
        ])

        assert result == 0
        assert output_path.exists()
        content = output_path.read_text()
        assert "E-195 Plays Pipeline Validation Results" in content
        assert "FPS" in content
        assert "QAB" in content

    def test_main_reports_outliers(self, tmp_path: Path, db):
        """main() prints warning when outliers are found."""
        home_id, away_id = _seed_base_data(db)
        _insert_game(db, _GAME_ID_1, home_id, away_id)

        # Big mismatch: derived 1, GC 20.
        _insert_play(
            db, _GAME_ID_1, 0, _BATTER_X, _PITCHER_A, away_id, is_fps=1,
        )
        for i in range(1, 5):
            _insert_play(
                db, _GAME_ID_1, i, _BATTER_X, _PITCHER_A, away_id, is_fps=0,
            )
        db.commit()
        _insert_season_pitching(db, _PITCHER_A, home_id, fps=20)
        db.close()

        db_path = tmp_path / "test.db"
        output_path = tmp_path / "results.md"

        result = main([
            "--db-path", str(db_path),
            "--output", str(output_path),
        ])

        assert result == 0
        content = output_path.read_text()
        assert "MISMATCH" in content
