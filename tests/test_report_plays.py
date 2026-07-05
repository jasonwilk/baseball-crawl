"""Tests for plays-derived stats in the report generator (E-199-01).

Tests cover:
- AC-6: FPS% computation with HBP/IBB exclusion
- AC-7: QAB% scoped by batting_team_id
- AC-8: Team-level aggregates and metadata
- AC-9: Query functions return correct aggregates, pitching vs batting
  scoping asymmetry, and graceful handling of empty results
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from src.reports import generator as _gen
from src.reports.generator import (
    _query_plays_batting_stats,
    _query_plays_pitching_stats,
    _query_plays_team_stats,
)
from tests.conftest import load_real_schema

# ---------------------------------------------------------------------------
# Schema fixture
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_MIGRATIONS = [
    _PROJECT_ROOT / "migrations" / "001_initial_schema.sql",
    # E-245-01: play_events.pitch_type / pitch_speed_mph columns (the plays
    # loader writes these, so the schema fixture must include them).
    _PROJECT_ROOT / "migrations" / "007_play_events_pitch_columns.sql",
    # E-250-02: drops seasons.season_type, team_opponents, and
    # players.gc_athlete_profile_id so the schema matches the season fixtures.
    _PROJECT_ROOT / "migrations" / "008_drop_identity_opponent_season_type.sql",
]


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory SQLite connection with required schema applied."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    for mig in _MIGRATIONS:
        conn.executescript(mig.read_text(encoding="utf-8"))
    conn.commit()
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEASON_ID = "2026"
_TEAM_ID = 1
_OPP_TEAM_ID = 2
_GAME_ID_1 = "game-001"
_GAME_ID_2 = "game-002"
_PITCHER_A = "pitcher-a-001"
_PITCHER_B = "pitcher-b-001"  # opponent pitcher
_BATTER_X = "batter-x-001"
_BATTER_Y = "batter-y-001"


def _seed_base(conn: sqlite3.Connection) -> None:
    """Insert base rows: seasons, teams, players, games, roster."""
    conn.execute(
        "INSERT INTO seasons (season_id, name, year) VALUES (?, ?, ?)",
        (_SEASON_ID, "Spring 2026 HS", 2026),
    )
    conn.execute(
        "INSERT INTO teams (id, name, membership_type, is_active) VALUES (?, ?, 'tracked', 1)",
        (_TEAM_ID, "Test Team"),
    )
    conn.execute(
        "INSERT INTO teams (id, name, membership_type, is_active) VALUES (?, ?, 'tracked', 1)",
        (_OPP_TEAM_ID, "Opponent Team"),
    )
    for pid in [_PITCHER_A, _PITCHER_B, _BATTER_X, _BATTER_Y]:
        conn.execute(
            "INSERT INTO players (player_id, first_name, last_name) VALUES (?, 'Test', 'Player')",
            (pid,),
        )
    # Roster: pitcher A and batters X, Y belong to TEAM_ID
    for pid in [_PITCHER_A, _BATTER_X, _BATTER_Y]:
        conn.execute(
            "INSERT INTO team_rosters (player_id, team_id, season_id) VALUES (?, ?, ?)",
            (pid, _TEAM_ID, _SEASON_ID),
        )
    # Pitcher B belongs to opponent
    conn.execute(
        "INSERT INTO team_rosters (player_id, team_id, season_id) VALUES (?, ?, ?)",
        (_PITCHER_B, _OPP_TEAM_ID, _SEASON_ID),
    )
    # Two games: team is home in game 1, away in game 2
    conn.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, status) "
        "VALUES (?, ?, '2026-03-15', ?, ?, 'completed')",
        (_GAME_ID_1, _SEASON_ID, _TEAM_ID, _OPP_TEAM_ID),
    )
    conn.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, status) "
        "VALUES (?, ?, '2026-03-20', ?, ?, 'completed')",
        (_GAME_ID_2, _SEASON_ID, _OPP_TEAM_ID, _TEAM_ID),
    )
    conn.commit()


def _insert_play(
    conn: sqlite3.Connection,
    game_id: str,
    play_order: int,
    *,
    batting_team_id: int,
    batter_id: str,
    pitcher_id: str,
    outcome: str = "Groundout",
    pitch_count: int = 3,
    is_first_pitch_strike: int = 1,
    is_qab: int = 0,
    perspective_team_id: int = _TEAM_ID,
) -> None:
    """Insert a single plays row.

    The default ``perspective_team_id = _TEAM_ID`` matches the production
    invariant: scouted team's data is loaded from the scouted team's own
    perspective.  Tests for cross-perspective behavior can override.
    """
    conn.execute(
        """
        INSERT INTO plays (
            game_id, play_order, inning, half, season_id,
            batting_team_id, perspective_team_id, batter_id, pitcher_id, outcome,
            pitch_count, is_first_pitch_strike, is_qab
        ) VALUES (?, ?, 1, 'top', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            game_id, play_order, _SEASON_ID,
            batting_team_id, perspective_team_id, batter_id, pitcher_id, outcome,
            pitch_count, is_first_pitch_strike, is_qab,
        ),
    )


# ---------------------------------------------------------------------------
# Tests: _query_plays_pitching_stats
# ---------------------------------------------------------------------------


class TestQueryPlaysPitchingStats:
    """AC-6, AC-9: FPS% with HBP/IBB exclusion, pitching scoping."""

    def test_basic_fps_and_pitches_per_bf(self, db: sqlite3.Connection) -> None:
        """FPS% = fps_hits / eligible_pas, pitches_per_bf = total_pitches / total_bf."""
        _seed_base(db)
        # Pitcher A faces 4 batters: 3 FPS, 1 non-FPS
        for i, fps in enumerate([1, 1, 1, 0]):
            _insert_play(
                db, _GAME_ID_1, i + 1,
                batting_team_id=_OPP_TEAM_ID,
                batter_id=_BATTER_Y,
                pitcher_id=_PITCHER_A,
                pitch_count=4,
                is_first_pitch_strike=fps,
            )
        db.commit()

        result = _query_plays_pitching_stats(db, _TEAM_ID, _SEASON_ID)
        assert _PITCHER_A in result
        assert result[_PITCHER_A]["fps_pct"] == pytest.approx(3.0 / 4.0)
        assert result[_PITCHER_A]["pitches_per_bf"] == pytest.approx(4.0)

    def test_fps_denominator_counts_only_charted_pas(
        self, db: sqlite3.Connection
    ) -> None:
        """FPS%/P-BF denominators count only charted PAs (E-245 TN-5).

        Supersedes the prior all-BF policy: an un-charted PA carries
        pitch_count=0 and is excluded from the denominator. A charted HBP
        (pitch_count>0) still counts; a 0-pitch IBB (no pitch-by-pitch data,
        the same pitch_count=0 signal as an un-charted PA) is excluded.
        """
        _seed_base(db)
        # 2 normal charted PAs (1 FPS each), 1 charted HBP (FPS=0, 2 pitches),
        # 1 IBB with 0 charted pitches (excluded from the charted denominator).
        _insert_play(
            db, _GAME_ID_1, 1,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, outcome="Groundout",
            is_first_pitch_strike=1, pitch_count=3,
        )
        _insert_play(
            db, _GAME_ID_1, 2,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, outcome="Strikeout",
            is_first_pitch_strike=1, pitch_count=5,
        )
        _insert_play(
            db, _GAME_ID_1, 3,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, outcome="Hit By Pitch",
            is_first_pitch_strike=0, pitch_count=2,
        )
        _insert_play(
            db, _GAME_ID_1, 4,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, outcome="Intentional Walk",
            is_first_pitch_strike=0, pitch_count=0,
        )
        db.commit()

        result = _query_plays_pitching_stats(db, _TEAM_ID, _SEASON_ID)
        stats = result[_PITCHER_A]
        # FPS%: 2 FPS / 3 charted BF (IBB with 0 pitches excluded) = 0.667
        assert stats["fps_pct"] == pytest.approx(2.0 / 3.0)
        # Pitches per BF: (3 + 5 + 2) / 3 charted BF = 3.333
        assert stats["pitches_per_bf"] == pytest.approx(10.0 / 3.0)

    def test_pitching_scoping_includes_both_home_and_away(
        self, db: sqlite3.Connection
    ) -> None:
        """Pitching stats include games where team is home AND away."""
        _seed_base(db)
        # Game 1: team is home, pitcher A pitches
        _insert_play(
            db, _GAME_ID_1, 1,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, is_first_pitch_strike=1, pitch_count=3,
        )
        # Game 2: team is away, pitcher A pitches
        _insert_play(
            db, _GAME_ID_2, 1,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, is_first_pitch_strike=1, pitch_count=5,
        )
        db.commit()

        result = _query_plays_pitching_stats(db, _TEAM_ID, _SEASON_ID)
        # Both games should be included (team is home in game 1, away in game 2)
        assert result[_PITCHER_A]["fps_pct"] == pytest.approx(1.0)
        assert result[_PITCHER_A]["pitches_per_bf"] == pytest.approx(4.0)

    def test_pitching_returns_opponent_pitchers_too(
        self, db: sqlite3.Connection
    ) -> None:
        """Pitching query returns ALL pitchers in team's games (merge filters later)."""
        _seed_base(db)
        # Opponent pitcher B pitches against our team
        _insert_play(
            db, _GAME_ID_1, 1,
            batting_team_id=_TEAM_ID, batter_id=_BATTER_X,
            pitcher_id=_PITCHER_B, is_first_pitch_strike=1, pitch_count=4,
        )
        db.commit()

        result = _query_plays_pitching_stats(db, _TEAM_ID, _SEASON_ID)
        # Pitcher B is in the result because the game involves our team
        assert _PITCHER_B in result

    def test_empty_plays_returns_empty_dict(self, db: sqlite3.Connection) -> None:
        """No plays data yields empty dict."""
        _seed_base(db)
        result = _query_plays_pitching_stats(db, _TEAM_ID, _SEASON_ID)
        assert result == {}


# ---------------------------------------------------------------------------
# Tests: _query_plays_batting_stats
# ---------------------------------------------------------------------------


class TestQueryPlaysBattingStats:
    """AC-7, AC-9: QAB% scoped by batting_team_id."""

    def test_basic_qab_and_pitches_per_pa(self, db: sqlite3.Connection) -> None:
        """QAB% = qab_sum / total_pa, pitches_per_pa = total_pitches / total_pa."""
        _seed_base(db)
        # Batter X: 3 PAs, 2 QABs
        _insert_play(
            db, _GAME_ID_1, 1,
            batting_team_id=_TEAM_ID, batter_id=_BATTER_X,
            pitcher_id=_PITCHER_B, is_qab=1, pitch_count=6,
        )
        _insert_play(
            db, _GAME_ID_1, 2,
            batting_team_id=_TEAM_ID, batter_id=_BATTER_X,
            pitcher_id=_PITCHER_B, is_qab=1, pitch_count=8,
        )
        _insert_play(
            db, _GAME_ID_1, 3,
            batting_team_id=_TEAM_ID, batter_id=_BATTER_X,
            pitcher_id=_PITCHER_B, is_qab=0, pitch_count=1,
        )
        db.commit()

        result = _query_plays_batting_stats(db, _TEAM_ID, _SEASON_ID)
        assert _BATTER_X in result
        assert result[_BATTER_X]["qab_pct"] == pytest.approx(2.0 / 3.0)
        assert result[_BATTER_X]["pitches_per_pa"] == pytest.approx(5.0)

    def test_batting_scoped_by_batting_team_id(
        self, db: sqlite3.Connection
    ) -> None:
        """Only includes PAs where batting_team_id matches the queried team."""
        _seed_base(db)
        # Batter X batting for our team
        _insert_play(
            db, _GAME_ID_1, 1,
            batting_team_id=_TEAM_ID, batter_id=_BATTER_X,
            pitcher_id=_PITCHER_B, is_qab=1, pitch_count=5,
        )
        # Batter Y batting for opponent (should NOT be in our results)
        _insert_play(
            db, _GAME_ID_1, 2,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, is_qab=1, pitch_count=3,
        )
        db.commit()

        result = _query_plays_batting_stats(db, _TEAM_ID, _SEASON_ID)
        assert _BATTER_X in result
        assert _BATTER_Y not in result

    def test_empty_plays_returns_empty_dict(self, db: sqlite3.Connection) -> None:
        """No plays data yields empty dict."""
        _seed_base(db)
        result = _query_plays_batting_stats(db, _TEAM_ID, _SEASON_ID)
        assert result == {}


# ---------------------------------------------------------------------------
# Tests: _query_plays_team_stats
# ---------------------------------------------------------------------------


class TestQueryPlaysTeamStats:
    """AC-8: Team-level aggregates and metadata."""

    def test_no_plays_data(self, db: sqlite3.Connection) -> None:
        """When no plays exist, returns has_plays_data=False, all None."""
        _seed_base(db)
        result = _query_plays_team_stats(db, _TEAM_ID, _SEASON_ID)
        assert result["has_plays_data"] is False
        assert result["plays_game_count"] == 0
        assert result["team_fps_pct"] is None
        assert result["team_pitches_per_pa"] is None

    def test_team_stats_with_data(self, db: sqlite3.Connection) -> None:
        """Team FPS% computed from roster pitchers; team P/PA from batting side."""
        _seed_base(db)
        # Our pitcher A: 3 PAs, 2 FPS
        _insert_play(
            db, _GAME_ID_1, 1,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, is_first_pitch_strike=1, pitch_count=4,
        )
        _insert_play(
            db, _GAME_ID_1, 2,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, is_first_pitch_strike=1, pitch_count=3,
        )
        _insert_play(
            db, _GAME_ID_1, 3,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, is_first_pitch_strike=0, pitch_count=5,
        )
        # Our batters: 2 PAs, total 9 pitches
        _insert_play(
            db, _GAME_ID_1, 4,
            batting_team_id=_TEAM_ID, batter_id=_BATTER_X,
            pitcher_id=_PITCHER_B, pitch_count=4,
        )
        _insert_play(
            db, _GAME_ID_1, 5,
            batting_team_id=_TEAM_ID, batter_id=_BATTER_X,
            pitcher_id=_PITCHER_B, pitch_count=5,
        )
        db.commit()

        result = _query_plays_team_stats(db, _TEAM_ID, _SEASON_ID)
        assert result["has_plays_data"] is True
        assert result["plays_game_count"] == 1
        # Team FPS%: 2/3 (pitcher A is on roster)
        assert result["team_fps_pct"] == pytest.approx(2.0 / 3.0)
        # Team P/PA: (4 + 5) / 2 = 4.5
        assert result["team_pitches_per_pa"] == pytest.approx(4.5)

    def test_plays_game_count_across_multiple_games(
        self, db: sqlite3.Connection
    ) -> None:
        """plays_game_count counts distinct games with plays data."""
        _seed_base(db)
        # Plays in both games
        _insert_play(
            db, _GAME_ID_1, 1,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, pitch_count=3,
        )
        _insert_play(
            db, _GAME_ID_2, 1,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, pitch_count=4,
        )
        db.commit()

        result = _query_plays_team_stats(db, _TEAM_ID, _SEASON_ID)
        assert result["plays_game_count"] == 2

    def test_team_fps_excludes_opponent_pitchers(
        self, db: sqlite3.Connection
    ) -> None:
        """Team FPS% only includes pitchers on the team's roster."""
        _seed_base(db)
        # Opponent pitcher B pitches (not on our roster): FPS=1
        _insert_play(
            db, _GAME_ID_1, 1,
            batting_team_id=_TEAM_ID, batter_id=_BATTER_X,
            pitcher_id=_PITCHER_B, is_first_pitch_strike=1, pitch_count=3,
        )
        # Our pitcher A: FPS=0
        _insert_play(
            db, _GAME_ID_1, 2,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, is_first_pitch_strike=0, pitch_count=4,
        )
        db.commit()

        result = _query_plays_team_stats(db, _TEAM_ID, _SEASON_ID)
        # Team FPS% should be 0/1 = 0.0 (only pitcher A, who had 0 FPS)
        assert result["team_fps_pct"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests: Multi-season scoping (AC-9)
# ---------------------------------------------------------------------------


class TestMultiSeasonScoping:
    """Verify queries are correctly scoped by season_id."""

    def test_pitching_stats_scoped_to_season(
        self, db: sqlite3.Connection
    ) -> None:
        """Plays from a different season are not included."""
        _seed_base(db)
        other_season = "2025"
        conn = db
        conn.execute(
            "INSERT INTO seasons (season_id, name, year) VALUES (?, ?, ?)",
            (other_season, "Spring 2025 HS", 2025),
        )
        conn.execute(
            "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, status) "
            "VALUES (?, ?, '2025-04-10', ?, ?, 'completed')",
            ("game-other", other_season, _TEAM_ID, _OPP_TEAM_ID),
        )
        # Play in the OTHER season
        _insert_play(
            conn, "game-other", 1,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, is_first_pitch_strike=1, pitch_count=3,
        )
        # Play in the target season
        _insert_play(
            conn, _GAME_ID_1, 1,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, is_first_pitch_strike=0, pitch_count=5,
        )
        conn.commit()

        result = _query_plays_pitching_stats(conn, _TEAM_ID, _SEASON_ID)
        # Only the target season play: FPS=0
        assert result[_PITCHER_A]["fps_pct"] == pytest.approx(0.0)

    def test_batting_stats_scoped_to_season(
        self, db: sqlite3.Connection
    ) -> None:
        """Batting query only returns plays from the specified season."""
        _seed_base(db)
        other_season = "2025"
        conn = db
        conn.execute(
            "INSERT INTO seasons (season_id, name, year) VALUES (?, ?, ?)",
            (other_season, "Spring 2025 HS", 2025),
        )
        conn.execute(
            "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, status) "
            "VALUES (?, ?, '2025-04-10', ?, ?, 'completed')",
            ("game-other", other_season, _TEAM_ID, _OPP_TEAM_ID),
        )
        # Play in other season with QAB
        _insert_play(
            conn, "game-other", 1,
            batting_team_id=_TEAM_ID, batter_id=_BATTER_X,
            pitcher_id=_PITCHER_B, is_qab=1, pitch_count=6,
        )
        # Play in target season without QAB
        _insert_play(
            conn, _GAME_ID_1, 1,
            batting_team_id=_TEAM_ID, batter_id=_BATTER_X,
            pitcher_id=_PITCHER_B, is_qab=0, pitch_count=2,
        )
        conn.commit()

        result = _query_plays_batting_stats(conn, _TEAM_ID, _SEASON_ID)
        # Only target season: QAB=0/1=0.0
        assert result[_BATTER_X]["qab_pct"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests: Team FPS% includes all BF (matches GameChanger)
# ---------------------------------------------------------------------------


class TestTeamFpsInclusion:
    """Team-level FPS% denominator counts only charted BF (E-245 TN-5)."""

    def test_team_fps_counts_only_charted_bf(self, db: sqlite3.Connection) -> None:
        """A 0-pitch IBB is excluded from the charted team FPS% denominator."""
        _seed_base(db)
        # Pitcher A (on roster): 2 charted FPS, 1 charted HBP (FPS=0), 1 IBB
        # with 0 charted pitches (excluded from the charted denominator).
        _insert_play(
            db, _GAME_ID_1, 1,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, outcome="Groundout",
            is_first_pitch_strike=1, pitch_count=3,
        )
        _insert_play(
            db, _GAME_ID_1, 2,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, outcome="Single",
            is_first_pitch_strike=1, pitch_count=4,
        )
        _insert_play(
            db, _GAME_ID_1, 3,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, outcome="Hit By Pitch",
            is_first_pitch_strike=0, pitch_count=1,
        )
        _insert_play(
            db, _GAME_ID_1, 4,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, outcome="Intentional Walk",
            is_first_pitch_strike=0, pitch_count=0,
        )
        db.commit()

        result = _query_plays_team_stats(db, _TEAM_ID, _SEASON_ID)
        # Team FPS%: 2 FPS / 3 charted BF (0-pitch IBB excluded) = 0.667
        assert result["team_fps_pct"] == pytest.approx(2.0 / 3.0)


# ---------------------------------------------------------------------------
# Tests: E-245-03 data-bearing denominators + two coverage counts (TN-5)
# ---------------------------------------------------------------------------


class TestE245DataBearingDenominators:
    """FPS%/P-PA charted-gated; QAB% all-PA; two distinct coverage counts."""

    def test_two_coverage_counts_differ(self, db: sqlite3.Connection) -> None:
        """AC-4: pitch_charted_game_count (N) < plays_game_count (K) with a mix.

        Game 1 is pitch-charted (pitch_count > 0); game 2 has plays but is
        un-charted (every PA pitch_count = 0).
        """
        _seed_base(db)
        # Game 1: charted.
        _insert_play(
            db, _GAME_ID_1, 1,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, is_first_pitch_strike=1, pitch_count=4,
        )
        # Game 2: un-charted (pitch_count = 0).
        _insert_play(
            db, _GAME_ID_2, 1,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, is_first_pitch_strike=0, pitch_count=0,
        )
        db.commit()

        result = _query_plays_team_stats(db, _TEAM_ID, _SEASON_ID)
        assert result["plays_game_count"] == 2          # K -- games-with-plays
        assert result["pitch_charted_game_count"] == 1  # N -- charted games
        assert result["has_plays_data"] is True

    def test_team_qab_all_pa_fps_ppa_charted(self, db: sqlite3.Connection) -> None:
        """AC-1/2/3: team QAB% over all PA; FPS%/P-PA over charted PA only."""
        _seed_base(db)
        # Batting side (our team bats): 1 charted (5 pitches, QAB), 1 un-charted
        # (0 pitches, QAB via outcome).
        _insert_play(
            db, _GAME_ID_1, 1,
            batting_team_id=_TEAM_ID, batter_id=_BATTER_X,
            pitcher_id=_PITCHER_B, is_qab=1, pitch_count=5,
        )
        _insert_play(
            db, _GAME_ID_1, 2,
            batting_team_id=_TEAM_ID, batter_id=_BATTER_X,
            pitcher_id=_PITCHER_B, is_qab=1, pitch_count=0,
        )
        db.commit()

        result = _query_plays_team_stats(db, _TEAM_ID, _SEASON_ID)
        # QAB%: 2 QAB / 2 all-PA = 1.0 (NOT gated on pitch_count).
        assert result["team_qab_pct"] == pytest.approx(1.0)
        # P/PA: 5 pitches / 1 charted PA = 5.0 (un-charted PA excluded).
        assert result["team_pitches_per_pa"] == pytest.approx(5.0)

    def test_per_batter_qab_all_pa_ppa_charted(self, db: sqlite3.Connection) -> None:
        """AC-2/3 (per-batter): QAB% all-PA; P-PA charted-only."""
        _seed_base(db)
        _insert_play(
            db, _GAME_ID_1, 1,
            batting_team_id=_TEAM_ID, batter_id=_BATTER_X,
            pitcher_id=_PITCHER_B, is_qab=1, pitch_count=4,
        )
        _insert_play(
            db, _GAME_ID_1, 2,
            batting_team_id=_TEAM_ID, batter_id=_BATTER_X,
            pitcher_id=_PITCHER_B, is_qab=1, pitch_count=0,
        )
        db.commit()

        result = _query_plays_batting_stats(db, _TEAM_ID, _SEASON_ID)
        stats = result[_BATTER_X]
        assert stats["qab_pct"] == pytest.approx(1.0)          # 2/2 all-PA
        assert stats["pitches_per_pa"] == pytest.approx(4.0)   # 4 / 1 charted

    def test_zero_charted_but_plays_exist(self, db: sqlite3.Connection) -> None:
        """AC-7 data shape: plays exist, none charted -> N=0, K>0, FPS/P-PA None, QAB set."""
        _seed_base(db)
        # Pitching side, un-charted.
        _insert_play(
            db, _GAME_ID_1, 1,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, is_first_pitch_strike=0, pitch_count=0,
        )
        # Batting side, un-charted but a QAB by outcome.
        _insert_play(
            db, _GAME_ID_1, 2,
            batting_team_id=_TEAM_ID, batter_id=_BATTER_X,
            pitcher_id=_PITCHER_B, is_qab=1, pitch_count=0,
        )
        db.commit()

        result = _query_plays_team_stats(db, _TEAM_ID, _SEASON_ID)
        assert result["has_plays_data"] is True
        assert result["plays_game_count"] == 1
        assert result["pitch_charted_game_count"] == 0
        assert result["team_fps_pct"] is None          # no charted BF
        assert result["team_pitches_per_pa"] is None    # no charted PA
        assert result["team_qab_pct"] == pytest.approx(1.0)  # all-PA QAB still computed


# ---------------------------------------------------------------------------
# Tests: Per-game failure isolation (SHOULD FIX 1 / AC-5)
# ---------------------------------------------------------------------------


class TestCrawlAndLoadPlaysFailureIsolation:
    """Per-game crawl failure should not prevent other games from loading."""

    def test_per_game_crawl_failure_does_not_block_others(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """When client.get() fails for one game, the function still returns without crashing.

        E-220-06 changed _crawl_and_load_plays to an in-memory pipeline.
        Per-game error isolation is tested by verifying the function completes
        and returns a list even when one game's crawl fails.
        """
        from unittest.mock import MagicMock, patch

        _seed_base(db)

        mock_client = MagicMock()
        fake_plays_response = {
            "sport": "baseball",
            "team_players": {},
            "plays": [],
        }

        def mock_get(path: str, **kwargs):
            if _GAME_ID_1 in path:
                raise RuntimeError("Simulated network error")
            return fake_plays_response

        mock_client.get.side_effect = mock_get

        db_path = str(tmp_path / "test.db")
        file_conn = sqlite3.connect(db_path)
        db.backup(file_conn)
        file_conn.close()

        def _fresh_conn():
            c = sqlite3.connect(db_path)
            c.execute("PRAGMA foreign_keys=ON;")
            c.row_factory = sqlite3.Row
            return c

        from src.reports.generator import _crawl_and_load_plays

        with patch("src.reports.generator.get_connection", side_effect=_fresh_conn):
            result = _crawl_and_load_plays(
                mock_client,
                public_id="test-team",
                team_id=_TEAM_ID,
                season_id=_SEASON_ID,
                game_ids=[_GAME_ID_1, _GAME_ID_2],
            )

        # Function should complete without raising despite game 1 failure
        assert isinstance(result, list)

    def test_recon_out_threads_fetch_failure_and_fetched_ok(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """AC-1: per-game fetch failures and successes thread into _ReconCounts.

        game 1's fetch raises (counts as plays_fetch_failures); game 2 fetches a
        valid empty-plays response and loads cleanly (counts as plays_fetched_ok,
        zero load errors). The function's list[str] return type is unchanged.
        """
        from unittest.mock import MagicMock

        _seed_base(db)

        mock_client = MagicMock()
        fake_plays_response = {
            "sport": "baseball",
            "team_players": {},
            "plays": [],
        }

        def mock_get(path: str, **kwargs):
            if _GAME_ID_1 in path:
                raise RuntimeError("Simulated network error")
            return fake_plays_response

        mock_client.get.side_effect = mock_get

        db_path = str(tmp_path / "test.db")
        file_conn = sqlite3.connect(db_path)
        db.backup(file_conn)
        file_conn.close()

        def _fresh_conn():
            c = sqlite3.connect(db_path)
            c.execute("PRAGMA foreign_keys=ON;")
            c.row_factory = sqlite3.Row
            return c

        from src.reports.generator import _ReconCounts, _crawl_and_load_plays

        recon = _ReconCounts()
        with patch("src.reports.generator.get_connection", side_effect=_fresh_conn):
            result = _crawl_and_load_plays(
                mock_client,
                public_id="test-team",
                team_id=_TEAM_ID,
                season_id=_SEASON_ID,
                game_ids=[_GAME_ID_1, _GAME_ID_2],
                recon_out=recon,
            )

        # Pinned return type (E-211) is unchanged.
        assert isinstance(result, list)
        # One fetch raised, one succeeded.
        assert recon.plays_fetch_failures == 1
        assert recon.plays_fetched_ok == 1
        # The empty-plays load produced no loader errors.
        assert recon.plays_load_errors == 0


# ---------------------------------------------------------------------------
# Tests: _plays_stage honesty -- ERROR-driven plays_status (E-236-02)
# ---------------------------------------------------------------------------


class _FakeCrawlResult:
    """Minimal stand-in for ScoutingCrawlResult exposing only ``boxscores``."""

    def __init__(self, game_ids: list[str]) -> None:
        self.boxscores = {gid: {} for gid in game_ids}


def _make_plays_gen(game_ids: list[str]) -> "_gen._ReportGeneration":
    """Build a minimal _ReportGeneration carrying only what _plays_stage reads."""
    gen = _gen._ReportGeneration.__new__(_gen._ReportGeneration)
    gen.report_id = 123
    gen.client = object()
    gen.public_id = "test-team"
    gen.team_id = _TEAM_ID
    gen.season_id = _SEASON_ID
    gen.plays_game_ids = []
    gen.crawl_result = _FakeCrawlResult(game_ids)
    # _plays_stage reads load_result.redirect_map (E-244); load always runs
    # before the plays stage in production, so None mirrors a redirect-free run.
    gen.load_result = None
    return gen


def _run_plays_stage(game_ids, populate, *, return_value=None):
    """Run _plays_stage with a faked _crawl_and_load_plays.

    ``populate(recon)`` sets the _ReconCounts scenario on the out-parameter the
    way the real helper would. Returns the merged dict of fields written to the
    run record via _update_run_record.
    """
    gen = _make_plays_gen(game_ids)
    captured: dict = {}

    def fake_update(report_id, **fields):
        captured.update(fields)

    def fake_crawl(*args, **kwargs):
        recon = kwargs["recon_out"]
        populate(recon)
        return list(game_ids) if return_value is None else return_value

    with patch.object(_gen, "_update_run_record", fake_update), patch.object(
        _gen, "_crawl_and_load_plays", fake_crawl
    ):
        gen._plays_stage()
    return captured


class TestPlaysStageHonesty:
    """_plays_stage derives an ERROR-driven plays_status (AC-2..AC-5)."""

    def test_completed_when_fetched_but_empty_zero_errors(self) -> None:
        """AC-5 (key assertion): games fetched 200 with NO plays and ZERO errors
        (the modal no-scorebook case) stays "completed" -- not partial/failed.
        """

        def populate(recon):
            recon.plays_fetched_ok = 3  # all attempted games fetched, no raise

        captured = _run_plays_stage(["g1", "g2", "g3"], populate)
        assert captured["plays_status"] == "completed"
        assert captured["plays_errors"] == 0

    def test_partial_on_per_game_fetch_failure(self) -> None:
        """AC-3: some games fetch OK, at least one ERRORS -> partial, errors>0."""

        def populate(recon):
            recon.plays_fetched_ok = 2
            recon.plays_fetch_failures = 1

        captured = _run_plays_stage(["g1", "g2", "g3"], populate)
        assert captured["plays_status"] == "partial"
        assert captured["plays_errors"] == 1

    def test_partial_on_load_errors(self) -> None:
        """AC-3: fetches all succeed but PlaysLoader reports errors -> partial."""

        def populate(recon):
            recon.plays_fetched_ok = 3
            recon.plays_load_errors = 2

        captured = _run_plays_stage(["g1", "g2", "g3"], populate)
        assert captured["plays_status"] == "partial"
        assert captured["plays_errors"] == 2

    def test_partial_sums_fetch_and_load_errors(self) -> None:
        """AC-2 / TN-2: plays_errors is fetch failures + load errors summed."""

        def populate(recon):
            recon.plays_fetched_ok = 2
            recon.plays_fetch_failures = 1
            recon.plays_load_errors = 3

        captured = _run_plays_stage(["g1", "g2", "g3"], populate)
        assert captured["plays_status"] == "partial"
        assert captured["plays_errors"] == 4

    def test_failed_when_all_fetches_error(self) -> None:
        """AC-2 classifier: zero fetched_ok of a non-zero attempted set -> failed."""

        def populate(recon):
            recon.plays_fetch_failures = 3  # all attempted games failed

        captured = _run_plays_stage(["g1", "g2", "g3"], populate)
        assert captured["plays_status"] == "failed"
        assert captured["plays_errors"] == 3

    def test_failed_when_recon_failed_total_failure(self) -> None:
        """AC-4: the existing recon.failed total-failure signal maps to "failed"
        BEFORE the classifier (TN-1 precedence) -- behavior preserved.
        """

        def populate(recon):
            recon.failed = True

        captured = _run_plays_stage(["g1", "g2", "g3"], populate, return_value=[])
        assert captured["plays_status"] == "failed"
        assert captured["reconciliation_status"] == "failed"

    def test_completed_when_nothing_attempted(self) -> None:
        """AC-2 / TN-1: expected == 0 (no games attempted) -> completed."""

        def populate(recon):
            pass  # no games attempted -> all counts stay 0

        captured = _run_plays_stage([], populate, return_value=[])
        assert captured["plays_status"] == "completed"
        assert captured["plays_errors"] == 0

    def test_stage_stays_non_fatal_on_cred_expiry(self) -> None:
        """AC-6: CredentialExpiredError is caught locally; report generation
        continues and the stage records plays_status="failed" without raising.
        """
        gen = _make_plays_gen(["g1", "g2"])
        captured: dict = {}

        def fake_update(report_id, **fields):
            captured.update(fields)

        def fake_crawl(*args, **kwargs):
            raise _gen.CredentialExpiredError("expired")

        with patch.object(_gen, "_update_run_record", fake_update), patch.object(
            _gen, "_crawl_and_load_plays", fake_crawl
        ):
            # Must NOT raise -- the stage swallows CredentialExpiredError.
            gen._plays_stage()

        assert captured["plays_status"] == "failed"


class TestPlaysErrorsColumnWrite:
    """The plays_errors write actually lands (allowlist gate, story-01 carry-fwd)."""

    def test_plays_errors_persists_to_run_record_column(
        self, tmp_path: Path
    ) -> None:
        """plays_errors must be in _RUN_RECORD_COLUMNS or _update_run_record
        silently drops it. Round-trip through the real schema to prove it lands.
        """
        # plays_errors is gated by the allowlist frozenset.
        assert "plays_errors" in _gen._RUN_RECORD_COLUMNS

        db_path = str(tmp_path / "rr.db")
        conn = sqlite3.connect(db_path)
        load_real_schema(conn)
        conn.execute(
            "INSERT INTO teams (id, name, membership_type, is_active) "
            "VALUES (1, 'T', 'tracked', 1)"
        )
        conn.execute(
            "INSERT INTO reports (id, slug, team_id, title, status, "
            "generated_at, expires_at) VALUES "
            "(1, 's', 1, 't', 'generating', "
            "'2026-01-01T00:00:00Z', '2026-02-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO report_generation_runs (report_id, started_at, "
            "overall_status) VALUES (1, '2026-01-01T00:00:00Z', 'running')"
        )
        conn.commit()
        conn.close()

        def _fresh():
            c = sqlite3.connect(db_path)
            c.execute("PRAGMA foreign_keys=ON;")
            return c

        with patch.object(_gen, "get_connection", side_effect=_fresh):
            _gen._update_run_record(1, plays_status="partial", plays_errors=4)

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT plays_status, plays_errors FROM report_generation_runs "
            "WHERE report_id = 1"
        ).fetchone()
        conn.close()
        assert row == ("partial", 4)


# ---------------------------------------------------------------------------
# E-244: dedup redirect map threaded to plays + spray stages
#
# These tests are built on a cross-perspective DEDUPED-game fixture: two source
# event ids collapse to one canonical id via GameLoader._find_duplicate_game
# (TN-6). A single-event-id fixture would pass vacuously and hide the bug, so
# the redirect map consumed by the plays/spray stages is the GENUINE map the
# real GameLoader produced this run -- not a hand-built dict.
# ---------------------------------------------------------------------------

# Distinct id space from the module-level constants above (avoid collisions).
_E244_SLUG = "scoutedteamslug"
_E244_OWN_UUID = "scouted-team-uuid-aaa-0001"
_E244_OPP_UUID = "0c1d2e3f-4a5b-6c7d-8e9f-0a1b2c3d4e5f"  # 36-char UUID = opp key
_E244_CANON_ID = "e244-canonical-game-001"
_E244_SOURCE_ID = "e244-source-game-002"
_E244_SPRAY_PLAYER = "e244-spray-player-001"
# Batter/pitcher ids MUST be 36-char hex+dash UUIDs -- the plays parser extracts
# them via the regex ``\$\{([0-9a-f-]{36})\}`` from the final_details templates.
_E244_BATTER = "aaaaaaaa-1111-2222-3333-444444444444"
_E244_PITCHER = "bbbbbbbb-5555-6666-7777-888888888888"
_E244_OWN_BAT = "e244-own-bat-001"
_E244_OWN_PIT = "e244-own-pit-001"
_E244_OPP_BAT = "e244-opp-bat-001"
_E244_OPP_PIT = "e244-opp-pit-001"
_E244_START = "2026-04-01T18:00:00.000Z"


def _e244_boxscore() -> dict:
    """Minimal valid boxscore: own-team slug key + opponent UUID key."""
    return {
        _E244_SLUG: {
            "players": [],
            "groups": [
                {
                    "category": "lineup",
                    "extra": [],
                    "stats": [
                        {
                            "player_id": _E244_OWN_BAT,
                            "stats": {"AB": 3, "R": 1, "H": 2, "RBI": 1, "BB": 1, "SO": 0},
                        }
                    ],
                },
                {
                    "category": "pitching",
                    "extra": [],
                    "stats": [
                        {
                            "player_id": _E244_OWN_PIT,
                            "stats": {"IP": 5, "H": 3, "R": 2, "ER": 2, "BB": 1, "SO": 7},
                        }
                    ],
                },
            ],
        },
        _E244_OPP_UUID: {
            "players": [],
            "groups": [
                {
                    "category": "lineup",
                    "extra": [],
                    "stats": [
                        {
                            "player_id": _E244_OPP_BAT,
                            "stats": {"AB": 4, "R": 1, "H": 1, "RBI": 0, "BB": 0, "SO": 2},
                        }
                    ],
                },
                {
                    "category": "pitching",
                    "extra": [],
                    "stats": [
                        {
                            "player_id": _E244_OPP_PIT,
                            "stats": {"IP": 4, "H": 5, "R": 5, "ER": 4, "BB": 2, "SO": 4},
                        }
                    ],
                },
            ],
        },
    }


def _e244_summary(event_id: str) -> "object":
    from src.gamechanger.loaders.game_loader import GameSummaryEntry

    return GameSummaryEntry(
        event_id=event_id,
        game_stream_id=event_id,
        home_away="home",
        owning_team_score=5,
        opponent_team_score=2,
        opponent_id=_E244_OPP_UUID,
        last_scoring_update="2026-04-01T18:00:00.000Z",
        start_time=_E244_START,
    )


def _e244_plays_payload() -> dict:
    """A plays response that parses into exactly one plays row."""
    return {
        "sport": {"batting_style": "normal"},
        "team_players": {},
        "plays": [
            {
                "order": 0,
                "inning": 1,
                "half": "top",
                "name_template": {"template": "Single"},
                "at_plate_details": [
                    {"template": "Strike 1 looking"},
                    {"template": "In play"},
                ],
                "final_details": [
                    {"template": f"${{{_E244_BATTER}}} singles to left field"},
                    {"template": f"${{{_E244_PITCHER}}} pitching"},
                ],
                "home_score": 0,
                "away_score": 0,
                "did_score_change": False,
                "outs": 1,
                "did_outs_change": True,
            }
        ],
    }


def _e244_spray_payload() -> dict:
    return {
        "spray_chart_data": {
            "offense": {
                _E244_SPRAY_PLAYER: [
                    {
                        "id": "e244-spray-event-1",
                        "createdAt": 1700000000000,
                        "attributes": {
                            "playResult": "single",
                            "playType": "ground_ball",
                            "defenders": [
                                {
                                    "position": "SS",
                                    "location": {"x": 100.0, "y": 80.0},
                                    "error": False,
                                }
                            ],
                        },
                    }
                ]
            },
            "defense": {},
        }
    }


def _e244_fresh_file_db(tmp_path: Path) -> str:
    """Create a file-backed DB with the real schema and return its path."""
    db_path = str(tmp_path / "e244.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON;")
    for mig in _MIGRATIONS:
        conn.executescript(mig.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()
    return db_path


def _e244_conn_factory(db_path: str):
    def _fresh():
        c = sqlite3.connect(db_path)
        c.execute("PRAGMA foreign_keys=ON;")
        c.row_factory = sqlite3.Row
        return c

    return _fresh


def _e244_seed_and_dedup(db_path: str) -> tuple[int, dict[str, str]]:
    """Seed the scouted team and drive a GENUINE cross-event dedup collapse.

    Loads the canonical game (CANON), then the same real game under a second
    source event id (SOURCE): GameLoader._find_duplicate_game collapses SOURCE
    into CANON, so only the canonical games row survives and the loader's
    redirect_map carries {SOURCE: CANON}. Returns (scouted_team_id, redirect_map).
    """
    from src.gamechanger.loaders import ensure_season_row
    from src.gamechanger.loaders.game_loader import GameLoader
    from src.gamechanger.types import TeamRef

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON;")
    cur = conn.execute(
        "INSERT INTO teams (gc_uuid, public_id, name, membership_type, is_active, season_year) "
        "VALUES (?, ?, ?, 'member', 1, 2026)",
        (_E244_OWN_UUID, _E244_SLUG, "Scouted Team"),
    )
    scouted_id = cur.lastrowid
    ensure_season_row(conn, "2026")
    # Spray player on the scouted (home) roster so spray events resolve to it.
    conn.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, 'Spray', 'Player')",
        (_E244_SPRAY_PLAYER,),
    )
    conn.execute(
        "INSERT INTO team_rosters (player_id, team_id, season_id) VALUES (?, ?, '2026')",
        (_E244_SPRAY_PLAYER, scouted_id),
    )
    conn.commit()

    loader = GameLoader(
        conn,
        owned_team_ref=TeamRef(id=scouted_id, gc_uuid=_E244_OWN_UUID, public_id=_E244_SLUG),
    )
    loader.load_payload(_e244_boxscore(), _e244_summary(_E244_CANON_ID))
    loader.load_payload(_e244_boxscore(), _e244_summary(_E244_SOURCE_ID))
    redirect_map = dict(loader.redirect_map)
    conn.commit()
    conn.close()
    return scouted_id, redirect_map


class TestE244RedirectMapSeam:
    """AC-1 / AC-8: GameLoader produces the {source: canonical} redirect map."""

    def test_dedup_collapse_populates_redirect_map(self, tmp_path: Path) -> None:
        db_path = _e244_fresh_file_db(tmp_path)
        scouted_id, redirect_map = _e244_seed_and_dedup(db_path)

        # Exactly the source->canonical entry; the non-redirected first load adds
        # nothing (AC-1: a non-redirected game produces no map entry).
        assert redirect_map == {_E244_SOURCE_ID: _E244_CANON_ID}

        # Only the canonical games row survives the collapse.
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT game_id FROM games").fetchall()
        conn.close()
        assert [r[0] for r in rows] == [_E244_CANON_ID]

    def test_scouting_loader_exposes_map_on_load_result(self, tmp_path: Path) -> None:
        """The map rides out on LoadResult.redirect_map via ScoutingLoader."""
        from types import SimpleNamespace

        from src.gamechanger.loaders.scouting_loader import ScoutingLoader

        db_path = _e244_fresh_file_db(tmp_path)
        # Seed only the scouted team; let the loader create the games itself.
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys=ON;")
        cur = conn.execute(
            "INSERT INTO teams (gc_uuid, public_id, name, membership_type, is_active, season_year) "
            "VALUES (?, ?, ?, 'member', 1, 2026)",
            (_E244_OWN_UUID, _E244_SLUG, "Scouted Team"),
        )
        scouted_id = cur.lastrowid
        conn.commit()

        def _game(gid: str) -> dict:
            return {
                "id": gid,
                "game_status": "completed",
                "score": {"team": 5, "opponent_team": 2},
                "home_away": "home",
                "start_ts": _E244_START,
                "timezone": "America/Chicago",
                "opponent_team": {"name": "Opp"},
            }

        crawl_result = SimpleNamespace(
            team_id=scouted_id,
            roster=[],
            games=[_game(_E244_CANON_ID), _game(_E244_SOURCE_ID)],
            boxscores={
                _E244_CANON_ID: _e244_boxscore(),
                _E244_SOURCE_ID: _e244_boxscore(),
            },
        )

        loader = ScoutingLoader(conn)
        result = loader.load_team(crawl_result)
        conn.close()

        assert result.redirect_map == {_E244_SOURCE_ID: _E244_CANON_ID}


class TestE244PlaysRemap:
    """AC-2/-3/-4/-6/-7: plays stage files + scopes by the canonical id."""

    def test_plays_filed_and_scoped_under_canonical(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        db_path = _e244_fresh_file_db(tmp_path)
        scouted_id, redirect_map = _e244_seed_and_dedup(db_path)
        assert redirect_map == {_E244_SOURCE_ID: _E244_CANON_ID}

        client = MagicMock()
        client.get.return_value = _e244_plays_payload()

        with patch.object(_gen, "get_connection", side_effect=_e244_conn_factory(db_path)):
            result = _gen._crawl_and_load_plays(
                client,
                public_id=_E244_SLUG,
                team_id=scouted_id,
                season_id="2026",
                game_ids=[_E244_SOURCE_ID],
                redirect_map=redirect_map,
            )

        # AC-4: returned list (=> self.plays_game_ids => rate-query scope) is the
        # CANONICAL id, not the source id.
        assert result == [_E244_CANON_ID]

        # The API FETCH used the SOURCE event id (scouted perspective).
        fetched_paths = [c.args[0] for c in client.get.call_args_list]
        assert any(_E244_SOURCE_ID in p for p in fetched_paths)
        assert all(_E244_CANON_ID not in p for p in fetched_paths)

        conn = sqlite3.connect(db_path)
        # AC-2: plays rows under CANONICAL with perspective = scouted team...
        canon_rows = conn.execute(
            "SELECT COUNT(*) FROM plays WHERE game_id = ? AND perspective_team_id = ?",
            (_E244_CANON_ID, scouted_id),
        ).fetchone()[0]
        # ...and NONE under the orphaned source id.
        source_rows = conn.execute(
            "SELECT COUNT(*) FROM plays WHERE game_id = ?", (_E244_SOURCE_ID,)
        ).fetchone()[0]
        conn.close()
        assert canon_rows > 0
        assert source_rows == 0

    def test_reconcile_invoked_with_canonical_id(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        db_path = _e244_fresh_file_db(tmp_path)
        scouted_id, redirect_map = _e244_seed_and_dedup(db_path)

        client = MagicMock()
        client.get.return_value = _e244_plays_payload()

        recon_spy = MagicMock(return_value=MagicMock())
        with patch.object(_gen, "get_connection", side_effect=_e244_conn_factory(db_path)), \
                patch.object(_gen, "reconcile_game", recon_spy):
            _gen._crawl_and_load_plays(
                client,
                public_id=_E244_SLUG,
                team_id=scouted_id,
                season_id="2026",
                game_ids=[_E244_SOURCE_ID],
                redirect_map=redirect_map,
            )

        # AC-3: reconcile_game keyed off the CANONICAL id (positional arg 1),
        # never the orphaned source id.
        assert recon_spy.called
        called_game_ids = [c.args[1] for c in recon_spy.call_args_list]
        assert called_game_ids == [_E244_CANON_ID]

    def test_two_sources_collapse_to_single_canonical_in_return(
        self, tmp_path: Path
    ) -> None:
        """AC-4: two source ids -> one canonical id, deduped in the return list."""
        from unittest.mock import MagicMock

        db_path = _e244_fresh_file_db(tmp_path)
        scouted_id, _ = _e244_seed_and_dedup(db_path)

        client = MagicMock()
        client.get.return_value = _e244_plays_payload()

        # Both source perspectives map to the same canonical id.
        second_source = "e244-source-game-003"
        redirect_map = {_E244_SOURCE_ID: _E244_CANON_ID, second_source: _E244_CANON_ID}

        with patch.object(_gen, "get_connection", side_effect=_e244_conn_factory(db_path)):
            result = _gen._crawl_and_load_plays(
                client,
                public_id=_E244_SLUG,
                team_id=scouted_id,
                season_id="2026",
                game_ids=[_E244_SOURCE_ID, second_source],
                redirect_map=redirect_map,
            )

        assert result == [_E244_CANON_ID]

    def test_run_two_does_not_refetch_plays(self, tmp_path: Path) -> None:
        """AC-6 (plays): the precheck remap finds canonical rows -> no re-fetch."""
        from unittest.mock import MagicMock

        db_path = _e244_fresh_file_db(tmp_path)
        scouted_id, redirect_map = _e244_seed_and_dedup(db_path)

        client = MagicMock()
        client.get.return_value = _e244_plays_payload()

        with patch.object(_gen, "get_connection", side_effect=_e244_conn_factory(db_path)):
            _gen._crawl_and_load_plays(
                client, public_id=_E244_SLUG, team_id=scouted_id,
                season_id="2026", game_ids=[_E244_SOURCE_ID], redirect_map=redirect_map,
            )
            client.reset_mock()
            result2 = _gen._crawl_and_load_plays(
                client, public_id=_E244_SLUG, team_id=scouted_id,
                season_id="2026", game_ids=[_E244_SOURCE_ID], redirect_map=redirect_map,
            )

        # Plays endpoint NOT re-fetched on run 2 (precheck hit the canonical id).
        assert client.get.call_count == 0
        # The game is still reported as processed under the canonical id.
        assert result2 == [_E244_CANON_ID]

    def test_zero_dedup_identity_passthrough(self, tmp_path: Path) -> None:
        """AC-7: with no redirects, plays behave exactly as before (identity)."""
        from unittest.mock import MagicMock

        db_path = _e244_fresh_file_db(tmp_path)
        scouted_id, _ = _e244_seed_and_dedup(db_path)

        client = MagicMock()
        client.get.return_value = _e244_plays_payload()

        with patch.object(_gen, "get_connection", side_effect=_e244_conn_factory(db_path)):
            result = _gen._crawl_and_load_plays(
                client,
                public_id=_E244_SLUG,
                team_id=scouted_id,
                season_id="2026",
                game_ids=[_E244_CANON_ID],
                redirect_map={},
            )

        assert result == [_E244_CANON_ID]
        fetched_paths = [c.args[0] for c in client.get.call_args_list]
        assert any(_E244_CANON_ID in p for p in fetched_paths)

        conn = sqlite3.connect(db_path)
        canon_rows = conn.execute(
            "SELECT COUNT(*) FROM plays WHERE game_id = ?", (_E244_CANON_ID,)
        ).fetchone()[0]
        conn.close()
        assert canon_rows > 0


class TestE244SprayRemap:
    """AC-5/-6: spray stage files rows under the canonical id (dict-key remap)."""

    def _fake_spray_result(self, source_id: str):
        from types import SimpleNamespace

        return SimpleNamespace(
            spray_data={source_id: _e244_spray_payload()},
            errors=0,
            games_crawled=1,
        )

    def test_spray_filed_under_canonical_and_queryable(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        db_path = _e244_fresh_file_db(tmp_path)
        scouted_id, redirect_map = _e244_seed_and_dedup(db_path)
        assert redirect_map == {_E244_SOURCE_ID: _E244_CANON_ID}

        client = MagicMock()
        fake_crawler = MagicMock()
        fake_crawler.crawl_team.return_value = self._fake_spray_result(_E244_SOURCE_ID)

        with patch.object(_gen, "get_connection", side_effect=_e244_conn_factory(db_path)), \
                patch.object(_gen, "ScoutingSprayChartCrawler", return_value=fake_crawler):
            _gen._crawl_and_load_spray(
                client,
                public_id=_E244_SLUG,
                season_id="2026",
                gc_uuid=None,
                games_data=[],
                team_id=scouted_id,
                redirect_map=redirect_map,
            )

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        # AC-5: spray rows under CANONICAL, none under the source id.
        canon_rows = conn.execute(
            "SELECT COUNT(*) FROM spray_charts WHERE game_id = ?", (_E244_CANON_ID,)
        ).fetchone()[0]
        source_rows = conn.execute(
            "SELECT COUNT(*) FROM spray_charts WHERE game_id = ?", (_E244_SOURCE_ID,)
        ).fetchone()[0]
        # AC-5: the game-id-agnostic spray query picks them up automatically.
        charts = _gen._query_spray_charts(conn, scouted_id, "2026")
        conn.close()
        assert canon_rows > 0
        assert source_rows == 0
        assert _E244_SPRAY_PLAYER in charts

    def test_run_two_inserts_no_duplicate_spray_rows(self, tmp_path: Path) -> None:
        """AC-6 (spray): row-level loader idempotency keyed on the canonical id."""
        from unittest.mock import MagicMock

        db_path = _e244_fresh_file_db(tmp_path)
        scouted_id, redirect_map = _e244_seed_and_dedup(db_path)

        client = MagicMock()

        def _run() -> None:
            fake_crawler = MagicMock()
            fake_crawler.crawl_team.return_value = self._fake_spray_result(_E244_SOURCE_ID)
            with patch.object(_gen, "get_connection", side_effect=_e244_conn_factory(db_path)), \
                    patch.object(_gen, "ScoutingSprayChartCrawler", return_value=fake_crawler):
                _gen._crawl_and_load_spray(
                    client, public_id=_E244_SLUG, season_id="2026",
                    gc_uuid=None, games_data=[], team_id=scouted_id,
                    redirect_map=redirect_map,
                )

        _run()
        conn = sqlite3.connect(db_path)
        count_1 = conn.execute(
            "SELECT COUNT(*) FROM spray_charts WHERE game_id = ?", (_E244_CANON_ID,)
        ).fetchone()[0]
        conn.close()

        _run()
        conn = sqlite3.connect(db_path)
        count_2 = conn.execute(
            "SELECT COUNT(*) FROM spray_charts WHERE game_id = ?", (_E244_CANON_ID,)
        ).fetchone()[0]
        conn.close()

        assert count_1 > 0
        assert count_2 == count_1  # no duplicate rows under the canonical id
