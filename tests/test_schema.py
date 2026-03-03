"""Schema tests for migrations/001_initial_schema.sql (E-003-01).

Applies the migration to an in-memory SQLite database and verifies:
- All expected tables exist
- Foreign key enforcement works (PRAGMA foreign_keys=ON)
- Crawl config query returns correct results

Tests use an in-memory SQLite database; no file I/O required, no network calls.

Run with:
    pytest tests/test_schema.py -v
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup -- allow running from project root without install
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MIGRATION_FILE = _PROJECT_ROOT / "migrations" / "001_initial_schema.sql"

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def schema_db() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the schema applied.

    Enables foreign key enforcement and WAL mode, then applies the migration.

    Yields:
        Open sqlite3.Connection with the schema applied and FKs enabled.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()

    sql = _MIGRATION_FILE.read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()

    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _table_names(conn: sqlite3.Connection) -> set[str]:
    """Return the set of user-defined table names in the connection.

    Args:
        conn: Open SQLite connection.

    Returns:
        Set of table name strings.
    """
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name != '_migrations';"
    )
    return {row[0] for row in cursor.fetchall()}


def _index_names(conn: sqlite3.Connection) -> set[str]:
    """Return the set of index names in the connection.

    Args:
        conn: Open SQLite connection.

    Returns:
        Set of index name strings.
    """
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index';")
    return {row[0] for row in cursor.fetchall()}


# ---------------------------------------------------------------------------
# Tests: table existence
# ---------------------------------------------------------------------------

_EXPECTED_TABLES = {
    "seasons",
    "players",
    "teams",
    "team_rosters",
    "games",
    "player_game_batting",
    "player_game_pitching",
    "player_season_batting",
    "player_season_pitching",
}


class TestTableExistence:
    """Verify all expected tables are created by the migration."""

    def test_all_expected_tables_exist(self, schema_db: sqlite3.Connection) -> None:
        """All nine core tables are present after migration."""
        actual = _table_names(schema_db)
        missing = _EXPECTED_TABLES - actual
        assert not missing, f"Missing tables: {missing}"

    @pytest.mark.parametrize("table", sorted(_EXPECTED_TABLES))
    def test_table_exists(
        self, schema_db: sqlite3.Connection, table: str
    ) -> None:
        """Each expected table exists individually.

        Args:
            schema_db: Seeded in-memory connection fixture.
            table: Table name to verify.
        """
        actual = _table_names(schema_db)
        assert table in actual, f"Table '{table}' not found in schema"


# ---------------------------------------------------------------------------
# Tests: seasons table structure
# ---------------------------------------------------------------------------


class TestSeasonsTable:
    """Verify the seasons table has the correct columns and constraints."""

    def test_seasons_insert_and_select(self, schema_db: sqlite3.Connection) -> None:
        """Can insert a seasons row and retrieve it."""
        schema_db.execute(
            """
            INSERT INTO seasons (season_id, name, season_type, year)
            VALUES ('2026-spring-hs', 'Spring 2026 High School', 'spring-hs', 2026);
            """
        )
        row = schema_db.execute(
            "SELECT season_id, name, season_type, year FROM seasons WHERE season_id = '2026-spring-hs';"
        ).fetchone()
        assert row is not None
        assert row[0] == "2026-spring-hs"
        assert row[1] == "Spring 2026 High School"
        assert row[2] == "spring-hs"
        assert row[3] == 2026

    def test_seasons_created_at_defaults(self, schema_db: sqlite3.Connection) -> None:
        """created_at is populated automatically when not specified."""
        schema_db.execute(
            "INSERT INTO seasons (season_id, name, season_type, year) "
            "VALUES ('2025-spring-hs', 'Spring 2025 High School', 'spring-hs', 2025);"
        )
        row = schema_db.execute(
            "SELECT created_at FROM seasons WHERE season_id = '2025-spring-hs';"
        ).fetchone()
        assert row is not None
        assert row[0] is not None


# ---------------------------------------------------------------------------
# Tests: teams crawl config columns
# ---------------------------------------------------------------------------


class TestTeamsCrawlConfig:
    """Verify teams table has source, is_active, and last_synced columns."""

    def _insert_team(
        self,
        conn: sqlite3.Connection,
        team_id: str,
        name: str,
        is_active: int = 1,
    ) -> None:
        conn.execute(
            "INSERT INTO teams (team_id, name, is_active) VALUES (?, ?, ?);",
            (team_id, name, is_active),
        )

    def test_source_defaults_to_gamechanger(
        self, schema_db: sqlite3.Connection
    ) -> None:
        """source column defaults to 'gamechanger' when not specified."""
        self._insert_team(schema_db, "t-001", "Test Team")
        row = schema_db.execute(
            "SELECT source FROM teams WHERE team_id = 't-001';"
        ).fetchone()
        assert row is not None
        assert row[0] == "gamechanger"

    def test_is_active_defaults_to_1(self, schema_db: sqlite3.Connection) -> None:
        """is_active defaults to 1 (crawl enabled) when not specified."""
        schema_db.execute(
            "INSERT INTO teams (team_id, name) VALUES ('t-002', 'Another Team');"
        )
        row = schema_db.execute(
            "SELECT is_active FROM teams WHERE team_id = 't-002';"
        ).fetchone()
        assert row is not None
        assert row[0] == 1

    def test_last_synced_is_nullable(self, schema_db: sqlite3.Connection) -> None:
        """last_synced is NULL by default (not yet crawled)."""
        self._insert_team(schema_db, "t-003", "Nullable Team")
        row = schema_db.execute(
            "SELECT last_synced FROM teams WHERE team_id = 't-003';"
        ).fetchone()
        assert row is not None
        assert row[0] is None


# ---------------------------------------------------------------------------
# Tests: FK enforcement -- AC-10 (team_rosters) and AC-11 (games)
# ---------------------------------------------------------------------------


class TestForeignKeyEnforcement:
    """Verify FK constraints are enforced with PRAGMA foreign_keys=ON."""

    def _insert_season(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "INSERT INTO seasons (season_id, name, season_type, year) "
            "VALUES ('2026-spring-hs', 'Spring 2026 HS', 'spring-hs', 2026);"
        )

    def _insert_team(self, conn: sqlite3.Connection, team_id: str = "team-001") -> None:
        conn.execute(
            "INSERT INTO teams (team_id, name) VALUES (?, 'Test Team');",
            (team_id,),
        )

    def _insert_player(
        self, conn: sqlite3.Connection, player_id: str = "p-001"
    ) -> None:
        conn.execute(
            "INSERT INTO players (player_id, first_name, last_name) VALUES (?, 'First', 'Last');",
            (player_id,),
        )

    def test_team_rosters_rejects_nonexistent_season_id(
        self, schema_db: sqlite3.Connection
    ) -> None:
        """AC-10: inserting team_rosters with a bad season_id raises IntegrityError."""
        self._insert_team(schema_db)
        self._insert_player(schema_db)
        with pytest.raises(sqlite3.IntegrityError):
            schema_db.execute(
                "INSERT INTO team_rosters (team_id, player_id, season_id) "
                "VALUES ('team-001', 'p-001', 'nonexistent-season');"
            )

    def test_team_rosters_accepts_valid_season_id(
        self, schema_db: sqlite3.Connection
    ) -> None:
        """team_rosters insert succeeds when season_id exists in seasons."""
        self._insert_season(schema_db)
        self._insert_team(schema_db)
        self._insert_player(schema_db)
        schema_db.execute(
            "INSERT INTO team_rosters (team_id, player_id, season_id) "
            "VALUES ('team-001', 'p-001', '2026-spring-hs');"
        )
        count = schema_db.execute("SELECT COUNT(*) FROM team_rosters;").fetchone()[0]
        assert count == 1

    def test_games_rejects_nonexistent_season_id(
        self, schema_db: sqlite3.Connection
    ) -> None:
        """AC-11: inserting games with a bad season_id raises IntegrityError."""
        self._insert_team(schema_db, "home-team")
        self._insert_team(schema_db, "away-team")
        with pytest.raises(sqlite3.IntegrityError):
            schema_db.execute(
                "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id) "
                "VALUES ('g-001', 'nonexistent-season', '2026-03-15', 'home-team', 'away-team');"
            )

    def test_games_accepts_valid_season_id(
        self, schema_db: sqlite3.Connection
    ) -> None:
        """games insert succeeds when season_id exists in seasons."""
        self._insert_season(schema_db)
        self._insert_team(schema_db, "home-team")
        self._insert_team(schema_db, "away-team")
        schema_db.execute(
            "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id) "
            "VALUES ('g-001', '2026-spring-hs', '2026-03-15', 'home-team', 'away-team');"
        )
        count = schema_db.execute("SELECT COUNT(*) FROM games;").fetchone()[0]
        assert count == 1

    def test_player_season_batting_rejects_nonexistent_season_id(
        self, schema_db: sqlite3.Connection
    ) -> None:
        """player_season_batting rejects a season_id not in seasons."""
        self._insert_team(schema_db)
        self._insert_player(schema_db)
        with pytest.raises(sqlite3.IntegrityError):
            schema_db.execute(
                "INSERT INTO player_season_batting (player_id, team_id, season_id) "
                "VALUES ('p-001', 'team-001', 'nonexistent-season');"
            )

    def test_player_season_pitching_rejects_nonexistent_season_id(
        self, schema_db: sqlite3.Connection
    ) -> None:
        """player_season_pitching rejects a season_id not in seasons."""
        self._insert_team(schema_db)
        self._insert_player(schema_db)
        with pytest.raises(sqlite3.IntegrityError):
            schema_db.execute(
                "INSERT INTO player_season_pitching (player_id, team_id, season_id) "
                "VALUES ('p-001', 'team-001', 'nonexistent-season');"
            )


# ---------------------------------------------------------------------------
# Tests: crawl config query -- AC-12
# ---------------------------------------------------------------------------


class TestCrawlConfigQuery:
    """Verify the crawl config query: SELECT * FROM teams WHERE is_active = 1."""

    def test_active_filter_returns_only_active_teams(
        self, schema_db: sqlite3.Connection
    ) -> None:
        """AC-12: is_active=1 filter returns only active teams."""
        schema_db.execute(
            "INSERT INTO teams (team_id, name, is_active) VALUES ('t-active', 'Active Team', 1);"
        )
        schema_db.execute(
            "INSERT INTO teams (team_id, name, is_active) VALUES ('t-inactive', 'Inactive Team', 0);"
        )
        rows = schema_db.execute(
            "SELECT team_id FROM teams WHERE is_active = 1;"
        ).fetchall()
        team_ids = {row[0] for row in rows}
        assert "t-active" in team_ids
        assert "t-inactive" not in team_ids

    def test_active_filter_returns_correct_count(
        self, schema_db: sqlite3.Connection
    ) -> None:
        """is_active=1 filter returns exactly the right number of teams."""
        schema_db.executemany(
            "INSERT INTO teams (team_id, name, is_active) VALUES (?, ?, ?);",
            [
                ("t-001", "Team 1", 1),
                ("t-002", "Team 2", 1),
                ("t-003", "Team 3", 0),
            ],
        )
        count = schema_db.execute(
            "SELECT COUNT(*) FROM teams WHERE is_active = 1;"
        ).fetchone()[0]
        assert count == 2

    def test_inactive_teams_excluded_by_default_query(
        self, schema_db: sqlite3.Connection
    ) -> None:
        """Teams with is_active=0 do not appear in the crawler query."""
        schema_db.execute(
            "INSERT INTO teams (team_id, name, is_active) VALUES ('t-skip', 'Skip Me', 0);"
        )
        rows = schema_db.execute(
            "SELECT team_id FROM teams WHERE is_active = 1;"
        ).fetchall()
        team_ids = {row[0] for row in rows}
        assert "t-skip" not in team_ids


# ---------------------------------------------------------------------------
# Tests: indexes exist
# ---------------------------------------------------------------------------

_EXPECTED_INDEXES = {
    "idx_team_rosters_team_season",
    "idx_team_rosters_player",
    "idx_games_season",
    "idx_games_home_team",
    "idx_games_away_team",
    "idx_player_game_batting_game",
    "idx_player_game_batting_player",
    "idx_player_game_pitching_game",
    "idx_player_season_batting_ps",
    "idx_player_season_pitching_ps",
    "idx_teams_is_active",
}


class TestIndexes:
    """Verify all required indexes are present."""

    @pytest.mark.parametrize("index_name", sorted(_EXPECTED_INDEXES))
    def test_index_exists(
        self, schema_db: sqlite3.Connection, index_name: str
    ) -> None:
        """Each required index is present in the schema.

        Args:
            schema_db: In-memory connection fixture.
            index_name: Index name to verify.
        """
        actual = _index_names(schema_db)
        assert index_name in actual, f"Index '{index_name}' not found in schema"
