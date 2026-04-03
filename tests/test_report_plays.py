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
    _PROJECT_ROOT / "migrations" / "004_add_team_season_year.sql",
    _PROJECT_ROOT / "migrations" / "009_plays_play_events.sql",
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
) -> None:
    """Insert a single plays row."""
    conn.execute(
        """
        INSERT INTO plays (
            game_id, play_order, inning, half, season_id,
            batting_team_id, batter_id, pitcher_id, outcome,
            pitch_count, is_first_pitch_strike, is_qab
        ) VALUES (?, ?, 1, 'top', ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            game_id, play_order, _SEASON_ID,
            batting_team_id, batter_id, pitcher_id, outcome,
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

    def test_fps_excludes_hbp_and_ibb(self, db: sqlite3.Connection) -> None:
        """HBP and Intentional Walk outcomes are excluded from FPS% denominator."""
        _seed_base(db)
        # 2 normal PAs (1 FPS each), 1 HBP, 1 IBB
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
            is_first_pitch_strike=0, pitch_count=5,
        )
        _insert_play(
            db, _GAME_ID_1, 3,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, outcome="Hit By Pitch",
            is_first_pitch_strike=1, pitch_count=2,
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
        # FPS%: 1 FPS / 2 eligible PAs = 0.5 (HBP and IBB excluded from denom)
        assert stats["fps_pct"] == pytest.approx(0.5)
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
# Tests: Team FPS% HBP/IBB exclusion (SHOULD FIX 2)
# ---------------------------------------------------------------------------


class TestTeamFpsExclusion:
    """Team-level FPS% must exclude HBP and Intentional Walk from denominator."""

    def test_team_fps_excludes_hbp_and_ibb(self, db: sqlite3.Connection) -> None:
        """HBP and IBB plays are excluded from team FPS% denominator."""
        _seed_base(db)
        # Pitcher A (on roster): 1 normal FPS, 1 normal non-FPS, 1 HBP, 1 IBB
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
            is_first_pitch_strike=0, pitch_count=4,
        )
        _insert_play(
            db, _GAME_ID_1, 3,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, outcome="Hit By Pitch",
            is_first_pitch_strike=1, pitch_count=1,
        )
        _insert_play(
            db, _GAME_ID_1, 4,
            batting_team_id=_OPP_TEAM_ID, batter_id=_BATTER_Y,
            pitcher_id=_PITCHER_A, outcome="Intentional Walk",
            is_first_pitch_strike=0, pitch_count=0,
        )
        db.commit()

        result = _query_plays_team_stats(db, _TEAM_ID, _SEASON_ID)
        # Team FPS%: 1 FPS / 2 eligible (HBP + IBB excluded) = 0.5
        assert result["team_fps_pct"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Tests: Per-game failure isolation (SHOULD FIX 1 / AC-5)
# ---------------------------------------------------------------------------


class TestCrawlAndLoadPlaysFailureIsolation:
    """Per-game crawl failure should not prevent other games from loading."""

    def test_per_game_crawl_failure_does_not_block_others(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """When client.get() fails for one game, other games still get plays."""
        from unittest.mock import MagicMock, patch

        _seed_base(db)

        # Build a mock client that fails for game 1 but succeeds for game 2
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

        # Patch get_connection to use our test DB and _DATA_ROOT to tmp_path
        db_path = str(tmp_path / "test.db")
        # Copy our in-memory DB to a file DB for _crawl_and_load_plays
        # (it opens its own connections)
        file_conn = sqlite3.connect(db_path)
        db.backup(file_conn)
        file_conn.close()

        def _fresh_conn():
            c = sqlite3.connect(db_path)
            c.execute("PRAGMA foreign_keys=ON;")
            c.row_factory = sqlite3.Row
            return c

        from src.reports.generator import _crawl_and_load_plays

        with (
            patch("src.reports.generator.get_connection", side_effect=_fresh_conn),
            patch("src.reports.generator._DATA_ROOT", tmp_path / "data" / "raw"),
        ):
            _crawl_and_load_plays(
                mock_client,
                public_id="test-team",
                team_id=_TEAM_ID,
                season_id=_SEASON_ID,
                crawl_season_id=_SEASON_ID,
            )

        # Verify: game 1 has no plays file (crawl failed), game 2 has a file
        plays_dir = tmp_path / "data" / "raw" / _SEASON_ID / "scouting" / "test-team" / "plays"
        assert not (plays_dir / f"{_GAME_ID_1}.json").exists()
        assert (plays_dir / f"{_GAME_ID_2}.json").exists()
