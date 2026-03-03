"""Query validation tests for the E-003 data model (E-003-04).

Applies migrations/001_initial_schema.sql + tests/fixtures/seed.sql to a
fresh in-memory SQLite database and validates that the schema supports the
coaching queries coaches will actually run.

All tests use a single in-memory database per test function (via the
``seeded_db`` fixture).  No persistent test databases, no network calls.

Run with:
    pytest tests/test_schema_queries.py -v
"""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_FIXTURES_DIR = _PROJECT_ROOT / "tests" / "fixtures"

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded_db() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with all migrations and seed applied.

    Applies every NNN_*.sql migration file found in migrations/ (in numeric
    order), then applies tests/fixtures/seed.sql.  Foreign keys are enabled.

    Yields:
        Open sqlite3.Connection ready for queries.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.commit()

    migrations_dir = _PROJECT_ROOT / "migrations"
    for mf in sorted(migrations_dir.glob("[0-9][0-9][0-9]_*.sql")):
        conn.executescript(mf.read_text(encoding="utf-8"))

    seed_sql = (_FIXTURES_DIR / "seed.sql").read_text(encoding="utf-8")
    conn.executescript(seed_sql)
    conn.commit()

    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# AC-4: migration + seed applies cleanly (no FK violations or errors)
# ---------------------------------------------------------------------------


class TestSeedLoadsCleanly:
    """AC-4: applying migration + seed to a fresh DB produces no errors."""

    def test_migration_and_seed_apply_without_error(self) -> None:
        """The full migration + seed script runs without raising any exception."""
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.commit()

            migrations_dir = _PROJECT_ROOT / "migrations"
            for mf in sorted(migrations_dir.glob("[0-9][0-9][0-9]_*.sql")):
                conn.executescript(mf.read_text(encoding="utf-8"))

            seed_sql = (_FIXTURES_DIR / "seed.sql").read_text(encoding="utf-8")
            conn.executescript(seed_sql)
            conn.commit()

            # Verify at least the key tables are populated.
            count = conn.execute("SELECT COUNT(*) FROM seasons;").fetchone()[0]
            assert count == 2, f"Expected 2 seasons, got {count}"
        finally:
            conn.close()

    def test_seed_has_correct_team_count(self, seeded_db: sqlite3.Connection) -> None:
        """Seed inserts exactly 5 teams."""
        count = seeded_db.execute("SELECT COUNT(*) FROM teams;").fetchone()[0]
        assert count == 5

    def test_seed_has_correct_player_count(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        """Seed inserts exactly 30 players (15 Varsity + 15 JV)."""
        count = seeded_db.execute("SELECT COUNT(*) FROM players;").fetchone()[0]
        assert count == 30

    def test_seed_has_correct_game_count(self, seeded_db: sqlite3.Connection) -> None:
        """Seed inserts exactly 10 games."""
        count = seeded_db.execute("SELECT COUNT(*) FROM games;").fetchone()[0]
        assert count == 10

    def test_inactive_team_present(self, seeded_db: sqlite3.Connection) -> None:
        """AC-2: at least one team has is_active=0."""
        count = seeded_db.execute(
            "SELECT COUNT(*) FROM teams WHERE is_active = 0;"
        ).fetchone()[0]
        assert count >= 1, "No inactive team found in seed data"

    def test_last_synced_non_null_present(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        """AC-2: at least one team has a non-null last_synced."""
        count = seeded_db.execute(
            "SELECT COUNT(*) FROM teams WHERE last_synced IS NOT NULL;"
        ).fetchone()[0]
        assert count >= 1, "No team with last_synced found"

    def test_batting_home_away_splits_present(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        """AC-3: at least one player has populated home/away split columns in batting."""
        count = seeded_db.execute(
            "SELECT COUNT(*) FROM player_season_batting "
            "WHERE home_ab IS NOT NULL AND away_ab IS NOT NULL;"
        ).fetchone()[0]
        assert count >= 1, "No batting row with home/away splits found"

    def test_pitching_vs_lhb_rhb_splits_present(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        """AC-3: at least one pitcher has populated vs_lhb/vs_rhb split columns."""
        count = seeded_db.execute(
            "SELECT COUNT(*) FROM player_season_pitching "
            "WHERE vs_lhb_ab IS NOT NULL AND vs_rhb_ab IS NOT NULL;"
        ).fetchone()[0]
        assert count >= 1, "No pitching row with vs_lhb/vs_rhb splits found"


# ---------------------------------------------------------------------------
# AC-5: Player batting stats (BA, OBP, K rate)
# ---------------------------------------------------------------------------


class TestPlayerBattingStats:
    """AC-5: given a player_id, return BA, OBP, and K rate."""

    # PLAYER_VARSITY_01: ab=20, h=7, bb=3, so=4
    # BA = 7/20 = 0.350
    # OBP = (7+3)/(20+3) = 10/23 ≈ 0.43478
    # Krate = 4/20 = 0.200

    _QUERY = """
        SELECT
            CAST(h AS REAL) / ab                        AS batting_avg,
            CAST(h + bb AS REAL) / (ab + bb)            AS obp,
            CAST(so AS REAL) / ab                       AS k_rate
        FROM player_season_batting
        WHERE player_id = 'PLAYER_VARSITY_01'
          AND season_id  = '2026-spring-hs';
    """

    def test_batting_average(self, seeded_db: sqlite3.Connection) -> None:
        """BA = H / AB is numerically correct for PLAYER_VARSITY_01."""
        row = seeded_db.execute(self._QUERY).fetchone()
        assert row is not None, "No row found for PLAYER_VARSITY_01"
        ba = row[0]
        assert abs(ba - 7 / 20) < 1e-6, f"Expected BA=0.350, got {ba}"

    def test_on_base_percentage(self, seeded_db: sqlite3.Connection) -> None:
        """OBP = (H+BB)/(AB+BB) is numerically correct for PLAYER_VARSITY_01."""
        row = seeded_db.execute(self._QUERY).fetchone()
        assert row is not None
        obp = row[1]
        expected = 10 / 23
        assert abs(obp - expected) < 1e-6, f"Expected OBP={expected:.5f}, got {obp}"

    def test_k_rate(self, seeded_db: sqlite3.Connection) -> None:
        """K rate = SO / AB is numerically correct for PLAYER_VARSITY_01."""
        row = seeded_db.execute(self._QUERY).fetchone()
        assert row is not None
        k_rate = row[2]
        assert abs(k_rate - 4 / 20) < 1e-6, f"Expected Krate=0.200, got {k_rate}"

    def test_query_performance(self, seeded_db: sqlite3.Connection) -> None:
        """AC-12: player batting stats query completes in under 100ms."""
        start = time.perf_counter()
        seeded_db.execute(self._QUERY).fetchall()
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 100, f"Query took {elapsed_ms:.1f}ms (limit 100ms)"


# ---------------------------------------------------------------------------
# AC-6: Team roster with season batting sorted by OBP descending
# ---------------------------------------------------------------------------


class TestTeamRosterByOBP:
    """AC-6: given team_id + season_id, return roster sorted by OBP descending."""

    # Expected OBP order for TEAM_VARSITY in 2026-spring-hs:
    #   PLAYER_VARSITY_02: 11/22 = 0.500
    #   PLAYER_VARSITY_01: 10/23 ≈ 0.43478
    #   PLAYER_VARSITY_03:  7/18 ≈ 0.38889
    #   PLAYER_VARSITY_04:  7/20 = 0.350
    #   PLAYER_VARSITY_05..15:  5/16 = 0.3125

    _QUERY = """
        SELECT
            psb.player_id,
            CAST(psb.h + psb.bb AS REAL) / (psb.ab + psb.bb) AS obp
        FROM player_season_batting psb
        JOIN team_rosters tr
          ON tr.player_id = psb.player_id
         AND tr.team_id   = psb.team_id
         AND tr.season_id = psb.season_id
        WHERE psb.team_id  = 'TEAM_VARSITY'
          AND psb.season_id = '2026-spring-hs'
        ORDER BY obp DESC;
    """

    def test_returns_all_roster_players(self, seeded_db: sqlite3.Connection) -> None:
        """All 15 Varsity players appear in the sorted roster query."""
        rows = seeded_db.execute(self._QUERY).fetchall()
        assert len(rows) == 15, f"Expected 15 players, got {len(rows)}"

    def test_top_player_by_obp(self, seeded_db: sqlite3.Connection) -> None:
        """The player with the highest OBP is PLAYER_VARSITY_02."""
        rows = seeded_db.execute(self._QUERY).fetchall()
        assert rows[0][0] == "PLAYER_VARSITY_02", (
            f"Expected PLAYER_VARSITY_02 at rank 1, got {rows[0][0]}"
        )

    def test_second_player_by_obp(self, seeded_db: sqlite3.Connection) -> None:
        """PLAYER_VARSITY_01 is second by OBP."""
        rows = seeded_db.execute(self._QUERY).fetchall()
        assert rows[1][0] == "PLAYER_VARSITY_01", (
            f"Expected PLAYER_VARSITY_01 at rank 2, got {rows[1][0]}"
        )

    def test_third_player_by_obp(self, seeded_db: sqlite3.Connection) -> None:
        """PLAYER_VARSITY_03 is third by OBP."""
        rows = seeded_db.execute(self._QUERY).fetchall()
        assert rows[2][0] == "PLAYER_VARSITY_03", (
            f"Expected PLAYER_VARSITY_03 at rank 3, got {rows[2][0]}"
        )

    def test_fourth_player_by_obp(self, seeded_db: sqlite3.Connection) -> None:
        """PLAYER_VARSITY_04 is fourth by OBP."""
        rows = seeded_db.execute(self._QUERY).fetchall()
        assert rows[3][0] == "PLAYER_VARSITY_04", (
            f"Expected PLAYER_VARSITY_04 at rank 4, got {rows[3][0]}"
        )

    def test_obp_values_are_descending(self, seeded_db: sqlite3.Connection) -> None:
        """OBP values are in non-increasing order."""
        rows = seeded_db.execute(self._QUERY).fetchall()
        obp_values = [r[1] for r in rows]
        for i in range(len(obp_values) - 1):
            assert obp_values[i] >= obp_values[i + 1], (
                f"OBP not descending at index {i}: {obp_values[i]} < {obp_values[i+1]}"
            )

    def test_query_performance(self, seeded_db: sqlite3.Connection) -> None:
        """AC-12: roster-by-OBP query completes in under 100ms."""
        start = time.perf_counter()
        seeded_db.execute(self._QUERY).fetchall()
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 100, f"Query took {elapsed_ms:.1f}ms (limit 100ms)"


# ---------------------------------------------------------------------------
# AC-7: Team W-L record
# ---------------------------------------------------------------------------


class TestTeamWinLossRecord:
    """AC-7: given team_id + season_id, return their W-L record."""

    # TEAM_VARSITY in 2026-spring-hs: 5 wins, 2 losses (see seed.sql header)

    _QUERY = """
        SELECT
            SUM(CASE
                WHEN home_team_id = 'TEAM_VARSITY' AND home_score > away_score THEN 1
                WHEN away_team_id = 'TEAM_VARSITY' AND away_score > home_score THEN 1
                ELSE 0
            END) AS wins,
            SUM(CASE
                WHEN home_team_id = 'TEAM_VARSITY' AND home_score < away_score THEN 1
                WHEN away_team_id = 'TEAM_VARSITY' AND away_score < home_score THEN 1
                ELSE 0
            END) AS losses
        FROM games
        WHERE season_id = '2026-spring-hs'
          AND (home_team_id = 'TEAM_VARSITY' OR away_team_id = 'TEAM_VARSITY');
    """

    def test_win_count(self, seeded_db: sqlite3.Connection) -> None:
        """TEAM_VARSITY has exactly 5 wins in 2026-spring-hs."""
        row = seeded_db.execute(self._QUERY).fetchone()
        assert row is not None
        assert row[0] == 5, f"Expected 5 wins, got {row[0]}"

    def test_loss_count(self, seeded_db: sqlite3.Connection) -> None:
        """TEAM_VARSITY has exactly 2 losses in 2026-spring-hs."""
        row = seeded_db.execute(self._QUERY).fetchone()
        assert row is not None
        assert row[1] == 2, f"Expected 2 losses, got {row[1]}"

    def test_wins_plus_losses_equals_games(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        """Total games played equals wins + losses (no ties in the seed data)."""
        row = seeded_db.execute(self._QUERY).fetchone()
        assert row is not None
        assert row[0] + row[1] == 7, (
            f"Expected 7 total games, got {row[0] + row[1]}"
        )

    def test_query_performance(self, seeded_db: sqlite3.Connection) -> None:
        """AC-12: W-L record query completes in under 100ms."""
        start = time.perf_counter()
        seeded_db.execute(self._QUERY).fetchall()
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 100, f"Query took {elapsed_ms:.1f}ms (limit 100ms)"


# ---------------------------------------------------------------------------
# AC-8: Home/away split batting averages
# ---------------------------------------------------------------------------


class TestHomeAwaySplitBattingAverage:
    """AC-8: given player_id, return home vs. away split batting averages."""

    # PLAYER_VARSITY_01 splits (from seed):
    #   home_ab=10, home_h=4  => home BA = 0.400
    #   away_ab=10, away_h=3  => away BA = 0.300

    _QUERY = """
        SELECT
            CAST(home_h AS REAL) / home_ab AS home_ba,
            CAST(away_h AS REAL) / away_ab AS away_ba
        FROM player_season_batting
        WHERE player_id = 'PLAYER_VARSITY_01'
          AND season_id  = '2026-spring-hs';
    """

    def test_home_batting_average(self, seeded_db: sqlite3.Connection) -> None:
        """Home BA = home_h / home_ab = 4/10 = 0.400."""
        row = seeded_db.execute(self._QUERY).fetchone()
        assert row is not None
        assert abs(row[0] - 0.400) < 1e-6, f"Expected home BA=0.400, got {row[0]}"

    def test_away_batting_average(self, seeded_db: sqlite3.Connection) -> None:
        """Away BA = away_h / away_ab = 3/10 = 0.300."""
        row = seeded_db.execute(self._QUERY).fetchone()
        assert row is not None
        assert abs(row[1] - 0.300) < 1e-6, f"Expected away BA=0.300, got {row[1]}"

    def test_home_ba_greater_than_away_ba(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        """Home BA is higher than away BA for PLAYER_VARSITY_01."""
        row = seeded_db.execute(self._QUERY).fetchone()
        assert row is not None
        assert row[0] > row[1], (
            f"Expected home BA ({row[0]}) > away BA ({row[1]})"
        )

    def test_query_performance(self, seeded_db: sqlite3.Connection) -> None:
        """AC-12: home/away split query completes in under 100ms."""
        start = time.perf_counter()
        seeded_db.execute(self._QUERY).fetchall()
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 100, f"Query took {elapsed_ms:.1f}ms (limit 100ms)"


# ---------------------------------------------------------------------------
# AC-9: Pitchers sorted by K/9 descending
# ---------------------------------------------------------------------------


class TestPitcherLeaderboardByK9:
    """AC-9: given team_id + season_id, return pitchers sorted by K/9 descending."""

    # Expected order for TEAM_VARSITY in 2026-spring-hs:
    #   PLAYER_VARSITY_01: ip_outs=54, so=22  K/9 = 22*27.0/54 = 11.000  (rank 1)
    #   PLAYER_VARSITY_02: ip_outs=36, so=12  K/9 = 12*27.0/36 =  9.000  (rank 2)
    #   PLAYER_VARSITY_03: ip_outs=18, so=5   K/9 =  5*27.0/18 =  7.500  (rank 3)

    _QUERY = """
        SELECT
            player_id,
            so * 27.0 / ip_outs AS k9
        FROM player_season_pitching
        WHERE team_id  = 'TEAM_VARSITY'
          AND season_id = '2026-spring-hs'
          AND ip_outs > 0
        ORDER BY k9 DESC;
    """

    def test_returns_three_pitchers(self, seeded_db: sqlite3.Connection) -> None:
        """Exactly 3 pitchers appear for TEAM_VARSITY in 2026-spring-hs."""
        rows = seeded_db.execute(self._QUERY).fetchall()
        assert len(rows) == 3, f"Expected 3 pitchers, got {len(rows)}"

    def test_first_pitcher_is_varsity_01(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        """PLAYER_VARSITY_01 has the highest K/9 (rank 1)."""
        rows = seeded_db.execute(self._QUERY).fetchall()
        assert rows[0][0] == "PLAYER_VARSITY_01", (
            f"Expected PLAYER_VARSITY_01 at rank 1, got {rows[0][0]}"
        )

    def test_second_pitcher_is_varsity_02(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        """PLAYER_VARSITY_02 has the second-highest K/9 (rank 2)."""
        rows = seeded_db.execute(self._QUERY).fetchall()
        assert rows[1][0] == "PLAYER_VARSITY_02", (
            f"Expected PLAYER_VARSITY_02 at rank 2, got {rows[1][0]}"
        )

    def test_third_pitcher_is_varsity_03(
        self, seeded_db: sqlite3.Connection
    ) -> None:
        """PLAYER_VARSITY_03 has the third-highest K/9 (rank 3)."""
        rows = seeded_db.execute(self._QUERY).fetchall()
        assert rows[2][0] == "PLAYER_VARSITY_03", (
            f"Expected PLAYER_VARSITY_03 at rank 3, got {rows[2][0]}"
        )

    def test_k9_values_are_correct(self, seeded_db: sqlite3.Connection) -> None:
        """K/9 values match the expected computed results."""
        rows = seeded_db.execute(self._QUERY).fetchall()
        expected = [
            ("PLAYER_VARSITY_01", 11.000),
            ("PLAYER_VARSITY_02", 9.000),
            ("PLAYER_VARSITY_03", 7.500),
        ]
        for i, (player_id, k9) in enumerate(expected):
            assert rows[i][0] == player_id
            assert abs(rows[i][1] - k9) < 1e-6, (
                f"{player_id}: expected K/9={k9}, got {rows[i][1]}"
            )

    def test_k9_values_are_descending(self, seeded_db: sqlite3.Connection) -> None:
        """K/9 values are in strictly decreasing order."""
        rows = seeded_db.execute(self._QUERY).fetchall()
        k9_values = [r[1] for r in rows]
        for i in range(len(k9_values) - 1):
            assert k9_values[i] > k9_values[i + 1], (
                f"K/9 not strictly descending at index {i}: "
                f"{k9_values[i]} <= {k9_values[i+1]}"
            )

    def test_query_performance(self, seeded_db: sqlite3.Connection) -> None:
        """AC-12: K/9 leaderboard query completes in under 100ms."""
        start = time.perf_counter()
        seeded_db.execute(self._QUERY).fetchall()
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 100, f"Query took {elapsed_ms:.1f}ms (limit 100ms)"


# ---------------------------------------------------------------------------
# AC-10: Crawl config query (active teams only)
# ---------------------------------------------------------------------------


class TestCrawlConfigQuery:
    """AC-10: SELECT team_id, name FROM teams WHERE is_active = 1."""

    _QUERY = "SELECT team_id FROM teams WHERE is_active = 1 ORDER BY team_id;"

    def test_active_teams_count(self, seeded_db: sqlite3.Connection) -> None:
        """Exactly 4 teams are active in the seed data."""
        rows = seeded_db.execute(self._QUERY).fetchall()
        assert len(rows) == 4, f"Expected 4 active teams, got {len(rows)}"

    def test_inactive_team_excluded(self, seeded_db: sqlite3.Connection) -> None:
        """TEAM_OPP_B (is_active=0) is not in the crawl config results."""
        rows = seeded_db.execute(self._QUERY).fetchall()
        team_ids = {r[0] for r in rows}
        assert "TEAM_OPP_B" not in team_ids, (
            "TEAM_OPP_B (inactive) should not appear in crawl config results"
        )

    def test_active_teams_present(self, seeded_db: sqlite3.Connection) -> None:
        """All four active teams appear in the crawl config results."""
        rows = seeded_db.execute(self._QUERY).fetchall()
        team_ids = {r[0] for r in rows}
        for expected_id in ("TEAM_VARSITY", "TEAM_JV", "TEAM_OPP_A", "TEAM_OPP_C"):
            assert expected_id in team_ids, (
                f"{expected_id} should be in crawl config but is missing"
            )

    def test_query_performance(self, seeded_db: sqlite3.Connection) -> None:
        """AC-12: crawl config query completes in under 100ms."""
        start = time.perf_counter()
        seeded_db.execute(self._QUERY).fetchall()
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 100, f"Query took {elapsed_ms:.1f}ms (limit 100ms)"


# ---------------------------------------------------------------------------
# AC-11: Seasons by type ordered by year
# ---------------------------------------------------------------------------


class TestSeasonsByType:
    """AC-11: given a season_type, return seasons of that type ordered by year."""

    _QUERY_SPRING = """
        SELECT season_id, year
        FROM seasons
        WHERE season_type = 'spring-hs'
        ORDER BY year;
    """

    _QUERY_LEGION = """
        SELECT season_id, year
        FROM seasons
        WHERE season_type = 'summer-legion'
        ORDER BY year;
    """

    _QUERY_ALL_ORDERED = """
        SELECT season_id, season_type, year
        FROM seasons
        ORDER BY year;
    """

    def test_spring_hs_season_found(self, seeded_db: sqlite3.Connection) -> None:
        """The spring-hs season query returns exactly one row."""
        rows = seeded_db.execute(self._QUERY_SPRING).fetchall()
        assert len(rows) == 1, f"Expected 1 spring-hs season, got {len(rows)}"

    def test_spring_hs_season_id(self, seeded_db: sqlite3.Connection) -> None:
        """The spring-hs season has the correct season_id."""
        rows = seeded_db.execute(self._QUERY_SPRING).fetchall()
        assert rows[0][0] == "2026-spring-hs", (
            f"Expected season_id '2026-spring-hs', got {rows[0][0]}"
        )

    def test_summer_legion_season_found(self, seeded_db: sqlite3.Connection) -> None:
        """The summer-legion season query returns exactly one row."""
        rows = seeded_db.execute(self._QUERY_LEGION).fetchall()
        assert len(rows) == 1, f"Expected 1 summer-legion season, got {len(rows)}"

    def test_summer_legion_season_id(self, seeded_db: sqlite3.Connection) -> None:
        """The summer-legion season has the correct season_id."""
        rows = seeded_db.execute(self._QUERY_LEGION).fetchall()
        assert rows[0][0] == "2025-summer-legion", (
            f"Expected season_id '2025-summer-legion', got {rows[0][0]}"
        )

    def test_all_seasons_ordered_by_year(self, seeded_db: sqlite3.Connection) -> None:
        """All seasons returned in year-ascending order: 2025, 2026."""
        rows = seeded_db.execute(self._QUERY_ALL_ORDERED).fetchall()
        assert len(rows) == 2
        years = [r[2] for r in rows]
        assert years == sorted(years), f"Seasons not in year order: {years}"
        assert years[0] == 2025
        assert years[1] == 2026

    def test_query_performance(self, seeded_db: sqlite3.Connection) -> None:
        """AC-12: seasons-by-type query completes in under 100ms."""
        start = time.perf_counter()
        seeded_db.execute(self._QUERY_SPRING).fetchall()
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 100, f"Query took {elapsed_ms:.1f}ms (limit 100ms)"
