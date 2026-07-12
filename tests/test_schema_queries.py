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

    # (home/away + vs_lhb/rhb split-column presence tests removed: E-259-03
    # dropped player_season_* -- the query-time reader derives the basic season
    # line only, no stored splits.)


# (TestPlayerBattingStats + TestTeamRosterByOBP removed: E-259-03 dropped
# player_season_batting -- BA / OBP / roster-by-OBP were queries over the stored
# season table, which the query-time reader does not reproduce as a splits/OBP
# surface.)


# ---------------------------------------------------------------------------
# AC-7: Team W-L record
# ---------------------------------------------------------------------------


class TestTeamWinLossRecord:
    """AC-7: given team_id + season_id, return their W-L record."""

    # TEAM_VARSITY in 2026: 5 wins, 2 losses (see seed.sql header)

    _QUERY = """
        SELECT
            SUM(CASE
                WHEN home_team_id = (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY')
                     AND home_score > away_score THEN 1
                WHEN away_team_id = (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY')
                     AND away_score > home_score THEN 1
                ELSE 0
            END) AS wins,
            SUM(CASE
                WHEN home_team_id = (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY')
                     AND home_score < away_score THEN 1
                WHEN away_team_id = (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY')
                     AND away_score < home_score THEN 1
                ELSE 0
            END) AS losses
        FROM games
        WHERE season_id = '2026'
          AND (
            home_team_id = (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY')
            OR away_team_id = (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY')
          );
    """

    def test_win_count(self, seeded_db: sqlite3.Connection) -> None:
        """TEAM_VARSITY has exactly 5 wins in 2026."""
        row = seeded_db.execute(self._QUERY).fetchone()
        assert row is not None
        assert row[0] == 5, f"Expected 5 wins, got {row[0]}"

    def test_loss_count(self, seeded_db: sqlite3.Connection) -> None:
        """TEAM_VARSITY has exactly 2 losses in 2026."""
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


# (TestHomeAwaySplitBattingAverage + TestPitcherLeaderboardByK9 removed: E-259-03
# dropped player_season_batting / player_season_pitching -- their home/away and
# vs-LHB/RHB splits and stored ip_outs/so are gone; the query-time reader derives
# the basic season line only.)


# ---------------------------------------------------------------------------
# AC-10: Crawl config query (active teams only)
# ---------------------------------------------------------------------------


class TestCrawlConfigQuery:
    """AC-10: SELECT gc_uuid FROM teams WHERE is_active = 1 (teams use INTEGER PK in E-100)."""

    _QUERY = "SELECT gc_uuid FROM teams WHERE is_active = 1 ORDER BY gc_uuid;"

    def test_active_teams_count(self, seeded_db: sqlite3.Connection) -> None:
        """Exactly 4 teams are active in the seed data."""
        rows = seeded_db.execute(self._QUERY).fetchall()
        assert len(rows) == 4, f"Expected 4 active teams, got {len(rows)}"

    def test_inactive_team_excluded(self, seeded_db: sqlite3.Connection) -> None:
        """TEAM_OPP_B (is_active=0) is not in the crawl config results."""
        rows = seeded_db.execute(self._QUERY).fetchall()
        gc_uuids = {r[0] for r in rows}
        assert "TEAM_OPP_B" not in gc_uuids, (
            "TEAM_OPP_B (inactive) should not appear in crawl config results"
        )

    def test_active_teams_present(self, seeded_db: sqlite3.Connection) -> None:
        """All four active teams appear in the crawl config results."""
        rows = seeded_db.execute(self._QUERY).fetchall()
        gc_uuids = {r[0] for r in rows}
        for expected_gc_uuid in ("TEAM_VARSITY", "TEAM_JV", "TEAM_OPP_A", "TEAM_OPP_C"):
            assert expected_gc_uuid in gc_uuids, (
                f"{expected_gc_uuid} should be in crawl config but is missing"
            )

    def test_query_performance(self, seeded_db: sqlite3.Connection) -> None:
        """AC-12: crawl config query completes in under 100ms."""
        start = time.perf_counter()
        seeded_db.execute(self._QUERY).fetchall()
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 100, f"Query took {elapsed_ms:.1f}ms (limit 100ms)"


# ---------------------------------------------------------------------------
# Seasons ordered by year (the two-season fixture structure guard)
# ---------------------------------------------------------------------------


class TestSeasonsOrderedByYear:
    """Given the two-season fixture, return both seasons ordered by year.

    E-250: the ``season_type`` column was dropped (cross-season machinery
    removed at the root); both fixture seasons carry year-only season_ids, so
    the prior season-type-filtering tests are gone.
    """

    _QUERY_ALL_ORDERED = """
        SELECT season_id, year
        FROM seasons
        ORDER BY year;
    """

    def test_all_seasons_ordered_by_year(self, seeded_db: sqlite3.Connection) -> None:
        """All seasons returned in year-ascending order: 2025, 2026."""
        rows = seeded_db.execute(self._QUERY_ALL_ORDERED).fetchall()
        assert len(rows) == 2
        years = [r[1] for r in rows]
        assert years == sorted(years), f"Seasons not in year order: {years}"
        assert years[0] == 2025
        assert years[1] == 2026
        assert rows[0][0] == "2025"
        assert rows[1][0] == "2026"

    def test_query_performance(self, seeded_db: sqlite3.Connection) -> None:
        """AC-12: seasons query completes in under 100ms."""
        start = time.perf_counter()
        seeded_db.execute(self._QUERY_ALL_ORDERED).fetchall()
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 100, f"Query took {elapsed_ms:.1f}ms (limit 100ms)"
