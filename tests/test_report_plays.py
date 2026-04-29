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

import pytest

from src.reports.generator import (
    _query_plays_batting_stats,
    _query_plays_pitching_stats,
    _query_plays_team_stats,
)

# ---------------------------------------------------------------------------
# Schema fixture
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_MIGRATIONS = [
    _PROJECT_ROOT / "migrations" / "001_initial_schema.sql",
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

_SEASON_ID = "2026-spring-hs"
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
        "INSERT INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
        (_SEASON_ID, "Spring 2026 HS", "spring-hs", 2026),
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

    def test_fps_includes_hbp_and_ibb(self, db: sqlite3.Connection) -> None:
        """HBP and Intentional Walk outcomes are included in FPS% denominator (matches GC)."""
        _seed_base(db)
        # 2 normal PAs (1 FPS each), 1 HBP (FPS=0), 1 IBB (FPS=0)
        # Old formula (exclude HBP/IBB): 2/2 = 1.0
        # New formula (all BF):          2/4 = 0.5
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
        # FPS%: 2 FPS / 4 total BF = 0.5 (HBP and IBB included in denom)
        assert stats["fps_pct"] == pytest.approx(2.0 / 4.0)
        # Pitches per BF: (3 + 5 + 2 + 0) / 4 total BF = 2.5
        assert stats["pitches_per_bf"] == pytest.approx(2.5)

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
        other_season = "2025-spring-hs"
        conn = db
        conn.execute(
            "INSERT INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
            (other_season, "Spring 2025 HS", "spring-hs", 2025),
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
        other_season = "2025-spring-hs"
        conn = db
        conn.execute(
            "INSERT INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
            (other_season, "Spring 2025 HS", "spring-hs", 2025),
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
    """Team-level FPS% must include all PAs in denominator (matches GC)."""

    def test_team_fps_includes_hbp_and_ibb(self, db: sqlite3.Connection) -> None:
        """HBP and IBB plays are included in team FPS% denominator."""
        _seed_base(db)
        # Pitcher A (on roster): 2 normal FPS, 1 HBP (FPS=0), 1 IBB (FPS=0)
        # Old formula (exclude HBP/IBB): 2/2 = 1.0
        # New formula (all BF):          2/4 = 0.5
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
        # Team FPS%: 2 FPS / 4 total BF (HBP + IBB included) = 0.5
        assert result["team_fps_pct"] == pytest.approx(2.0 / 4.0)


# ---------------------------------------------------------------------------
# Tests: Per-game failure isolation (SHOULD FIX 1 / AC-5)
# ---------------------------------------------------------------------------


# E-229-04: TestCrawlAndLoadPlaysFailureIsolation removed.
# The deleted `_crawl_and_load_plays` was migrated to the shared
# `run_plays_stage` helper.  Per-game crawl-error isolation is now covered by
# `tests/test_plays_stage.py::test_per_game_http_error_does_not_abort_remaining`.


# ---------------------------------------------------------------------------
# Codex round-6 P2 remediation: report-path real-helper integration coverage.
#
# The other report-generator tests for E-229-04 (TestPlaysStageAuthExpiry,
# TestPlaysStageHelperInvocation in tests/test_report_generator.py) stub
# `run_plays_stage` and assert call signatures; they do not exercise the real
# helper through the report call site.  This test mirrors the round-3 web-path
# fix at
# tests/test_pipeline_scouting_sync_plays.py::test_per_game_http_error_isolation_in_web_path
# by running the real helper end-to-end with two seeded games -- one whose
# plays HTTP fetch raises, one whose returns valid JSON -- and asserting that
# the report renders successfully while plays/play_events rows are persisted
# only for the surviving game.  Closes the integration-coverage gap left after
# the behavior-oriented `_crawl_and_load_plays` test was removed at line 551.
# ---------------------------------------------------------------------------


import logging
import sys
from contextlib import closing
from unittest.mock import MagicMock, patch

_PROJECT_ROOT_E2E = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT_E2E) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT_E2E))


_E2E_GAME_ID_1 = "11111111-1111-1111-1111-111111111111"
_E2E_GAME_ID_2 = "22222222-2222-2222-2222-222222222222"
_E2E_PITCHER = "01000001-aaaa-bbbb-cccc-000000000001"
_E2E_BATTER = "ba000001-aaaa-bbbb-cccc-000000000001"


def _seed_disk_db_for_report(db_path: Path) -> tuple[int, int, str]:
    """Apply migrations + seed teams/players/games for a report-path E2E test.

    Returns (team_id, away_team_id, season_id).  Uses ``derive_season_id_for_team``
    semantics: the seeded team has ``season_year=2026`` and no ``program_id``,
    so the report generator will derive ``season_id="2026"``.
    """
    from migrations.apply_migrations import run_migrations

    run_migrations(db_path=db_path)
    season_id = "2026"
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            "INSERT INTO teams (id, name, membership_type, public_id, season_year) "
            "VALUES (1, 'Tracked Opp', 'tracked', 'TrackedOppE229', 2026)"
        )
        conn.execute(
            "INSERT INTO teams (id, name, membership_type) "
            "VALUES (2, 'Other Side', 'tracked')"
        )
        conn.execute(
            "INSERT INTO seasons (season_id, name, season_type, year) "
            "VALUES (?, '2026', 'default', 2026)",
            (season_id,),
        )
        # Pre-seed players + a games row + boxscore stat rows for each game so
        # the plays loader's foreign-key checks (and reconcile_game's joins)
        # have what they need.  Mirrors the web-path
        # `_seed_game_for_reconcile` shape.
        for pid, first, last in [
            (_E2E_PITCHER, "Pitcher", "One"),
            (_E2E_BATTER, "Batter", "One"),
        ]:
            conn.execute(
                "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
                "VALUES (?, ?, ?)",
                (pid, first, last),
            )
        for game_id in (_E2E_GAME_ID_1, _E2E_GAME_ID_2):
            conn.execute(
                "INSERT INTO games "
                "(game_id, season_id, game_date, home_team_id, away_team_id, status) "
                "VALUES (?, ?, '2026-04-10', 1, 2, 'completed')",
                (game_id, season_id),
            )
            # Mirror the upstream GameLoader._maybe_record_game_perspective
            # write -- the E2E test mocks ScoutingLoader so the real GameLoader
            # never runs; without this seed a missing perspective row would
            # break perspective-provenance MUST #5.
            conn.execute(
                "INSERT OR IGNORE INTO game_perspectives "
                "(game_id, perspective_team_id) VALUES (?, 1)",
                (game_id,),
            )
            conn.execute(
                "INSERT INTO player_game_pitching "
                "(game_id, team_id, player_id, perspective_team_id, "
                " appearance_order, ip_outs, h, r, er, bb, so, pitches, total_strikes, bf) "
                "VALUES (?, 2, ?, 1, 1, 6, 0, 0, 0, 0, 0, 6, 4, 2)",
                (game_id, _E2E_PITCHER),
            )
            conn.execute(
                "INSERT INTO player_game_batting "
                "(game_id, team_id, player_id, perspective_team_id, "
                " ab, r, h, bb, so, hbp) "
                "VALUES (?, 2, ?, 1, 2, 0, 2, 0, 0, 0)",
                (game_id, _E2E_BATTER),
            )
        conn.commit()
    return 1, 2, season_id


def test_generate_report_per_game_http_error_isolation(
    tmp_path: Path,
    plays_json_factory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Real-helper integration: per-game HTTP error isolates inside the report path.

    Mirrors
    ``tests/test_pipeline_scouting_sync_plays.py::test_per_game_http_error_isolation_in_web_path``
    but exercises ``generate_report`` instead of ``run_scouting_sync``.  The
    real ``run_plays_stage`` helper runs against a mocked
    ``GameChangerClient.get`` that raises for game 1 and returns valid JSON for
    game 2.  The report must render successfully, and plays/play_events rows
    must be persisted for game 2 only.

    Closes the round-6 integration-coverage gap for E-229-04 AC-4 / AC-5: the
    other report-generator tests stub ``run_plays_stage``, so a regression in
    the helper-to-callsite wiring would leave them green.
    """
    from src.gamechanger.crawlers.scouting import ScoutingCrawlResult
    from src.gamechanger.loaders import LoadResult
    from src.reports.generator import generate_report

    db_path = tmp_path / "test.db"
    team_id, away_id, _season_id = _seed_disk_db_for_report(db_path)

    def _fresh_conn() -> sqlite3.Connection:
        c = sqlite3.connect(str(db_path))
        c.execute("PRAGMA foreign_keys=ON;")
        return c

    # Skip the public-team API fetch -- non-200 short-circuits cleanly and
    # leaves team_name_from_api / season_year_from_api as None.
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_session.get.return_value = mock_resp

    crawl_result = ScoutingCrawlResult(
        team_id=team_id,
        season_id="2026",
        public_id="TrackedOppE229",
        games=[
            {"id": _E2E_GAME_ID_1, "game_status": "completed"},
            {"id": _E2E_GAME_ID_2, "game_status": "completed"},
        ],
        roster=[],
        boxscores={_E2E_GAME_ID_1: {}, _E2E_GAME_ID_2: {}},
        games_crawled=2,
    )
    mock_crawler = MagicMock()
    mock_crawler.scout_team.return_value = crawl_result
    mock_loader = MagicMock()
    mock_loader.load_team.return_value = LoadResult(loaded=5)

    game_2_plays_json = plays_json_factory(
        _E2E_GAME_ID_2, _E2E_PITCHER, _E2E_BATTER, num_plays=2,
    )

    def _fake_get(path: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        if "plays" not in path:
            return {}
        if _E2E_GAME_ID_1 in path:
            raise RuntimeError("simulated HTTP failure for game 1")
        if _E2E_GAME_ID_2 in path:
            return game_2_plays_json
        return {}

    mock_client = MagicMock()
    mock_client.get.side_effect = _fake_get

    caplog.set_level(logging.INFO, logger="src.reports.generator")

    with (
        patch("src.http.session.create_session", return_value=mock_session),
        patch("src.reports.generator.get_connection", side_effect=_fresh_conn),
        patch("src.reports.generator.GameChangerClient", return_value=mock_client),
        patch(
            "src.reports.generator.ensure_team_row", return_value=team_id,
        ),
        patch(
            "src.reports.generator.render_report", return_value="<html>ok</html>",
        ),
        patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
        patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
        # Skip spray + gc_uuid resolution -- both make extra HTTP calls that
        # would otherwise need their own mocked endpoints.  Plays-stage is
        # the focus; spray has its own coverage.
        patch("src.reports.generator._crawl_and_load_spray"),
        patch("src.reports.generator._resolve_gc_uuid", return_value=None),
        patch("src.reports.generator._REPO_ROOT", tmp_path),
        patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
    ):
        result = generate_report("TrackedOppE229")

    # Report rendered successfully despite per-game plays failure.
    assert result.success is True, (
        f"report failed: {result.error_message!r}"
    )
    assert result.url is not None
    assert result.slug is not None
    report_file = tmp_path / "data" / "reports" / f"{result.slug}.html"
    assert report_file.exists()

    # Plays + play_events rows: game 2 only.
    with closing(sqlite3.connect(str(db_path))) as conn:
        g1_plays = conn.execute(
            "SELECT COUNT(*) FROM plays "
            "WHERE game_id = ? AND perspective_team_id = ?",
            (_E2E_GAME_ID_1, team_id),
        ).fetchone()[0]
        assert g1_plays == 0, (
            "game 1 plays HTTP raised; no rows should have been written"
        )
        g1_events = conn.execute(
            "SELECT COUNT(*) FROM play_events pe "
            "JOIN plays p ON pe.play_id = p.id "
            "WHERE p.game_id = ? AND p.perspective_team_id = ?",
            (_E2E_GAME_ID_1, team_id),
        ).fetchone()[0]
        assert g1_events == 0

        g2_plays = conn.execute(
            "SELECT COUNT(*) FROM plays "
            "WHERE game_id = ? AND perspective_team_id = ?",
            (_E2E_GAME_ID_2, team_id),
        ).fetchone()[0]
        assert g2_plays == 2
        g2_events = conn.execute(
            "SELECT COUNT(*) FROM play_events pe "
            "JOIN plays p ON pe.play_id = p.id "
            "WHERE p.game_id = ? AND p.perspective_team_id = ?",
            (_E2E_GAME_ID_2, team_id),
        ).fetchone()[0]
        assert g2_events > 0

    # Plays-stage INFO log emitted by the report generator names the
    # per-counter result -- loaded=1, errored=1.  Greppable token: the
    # generator's structured "Plays stage for public_id=" prefix.
    plays_log_records = [
        r for r in caplog.records
        if r.name == "src.reports.generator"
        and "Plays stage for public_id=" in r.getMessage()
    ]
    assert plays_log_records, [
        (r.name, r.levelname, r.getMessage()) for r in caplog.records
    ]
    msg = plays_log_records[0].getMessage()
    assert "loaded=1" in msg, msg
    assert "errored=1" in msg, msg
