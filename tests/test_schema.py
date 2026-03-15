"""Schema tests for migrations/001_initial_schema.sql (E-003-01; updated E-100-01).

Applies the migration to an in-memory SQLite database and verifies:
- All expected tables exist
- Foreign key enforcement works (PRAGMA foreign_keys=ON)
- teams table uses INTEGER PK with membership_type/classification columns
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
    "programs",
    "seasons",
    "players",
    "teams",
    "team_opponents",
    "team_rosters",
    "games",
    "player_game_batting",
    "player_game_pitching",
    "player_season_batting",
    "player_season_pitching",
    "spray_charts",
    "opponent_links",
    "scouting_runs",
    "users",
    "user_team_access",
    "magic_link_tokens",
    "passkey_credentials",
    "sessions",
    "coaching_assignments",
}


class TestTableExistence:
    """Verify all expected tables are created by the migration."""

    def test_all_expected_tables_exist(self, schema_db: sqlite3.Connection) -> None:
        """All expected tables are present after migration."""
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
# Tests: teams table -- INTEGER PK and new columns
# ---------------------------------------------------------------------------


class TestTeamsTable:
    """Verify the teams table has the E-100 schema: INTEGER PK, membership_type."""

    def test_teams_integer_pk(self, schema_db: sqlite3.Connection) -> None:
        """teams.id is auto-assigned INTEGER on insert."""
        cursor = schema_db.execute(
            "INSERT INTO teams (name, membership_type) VALUES ('Test Team', 'member');"
        )
        team_id = cursor.lastrowid
        assert isinstance(team_id, int), f"Expected int PK, got {type(team_id)}"
        assert team_id > 0

    def test_teams_no_team_id_text_column(self, schema_db: sqlite3.Connection) -> None:
        """teams table does NOT have a team_id TEXT column (old schema)."""
        cursor = schema_db.execute("PRAGMA table_info(teams);")
        columns = {row[1] for row in cursor.fetchall()}
        assert "team_id" not in columns, "Old team_id TEXT column must not exist"

    def test_teams_no_is_owned_column(self, schema_db: sqlite3.Connection) -> None:
        """teams table does NOT have an is_owned column (old schema)."""
        cursor = schema_db.execute("PRAGMA table_info(teams);")
        columns = {row[1] for row in cursor.fetchall()}
        assert "is_owned" not in columns, "Old is_owned column must not exist"

    def test_teams_no_level_column(self, schema_db: sqlite3.Connection) -> None:
        """teams table does NOT have a level column (old schema)."""
        cursor = schema_db.execute("PRAGMA table_info(teams);")
        columns = {row[1] for row in cursor.fetchall()}
        assert "level" not in columns, "Old level column must not exist"

    def test_teams_membership_type_column_exists(self, schema_db: sqlite3.Connection) -> None:
        """teams.membership_type column exists."""
        cursor = schema_db.execute("PRAGMA table_info(teams);")
        columns = {row[1] for row in cursor.fetchall()}
        assert "membership_type" in columns

    def test_teams_classification_column_exists(self, schema_db: sqlite3.Connection) -> None:
        """teams.classification column exists."""
        cursor = schema_db.execute("PRAGMA table_info(teams);")
        columns = {row[1] for row in cursor.fetchall()}
        assert "classification" in columns

    def test_teams_gc_uuid_column_exists(self, schema_db: sqlite3.Connection) -> None:
        """teams.gc_uuid column exists."""
        cursor = schema_db.execute("PRAGMA table_info(teams);")
        columns = {row[1] for row in cursor.fetchall()}
        assert "gc_uuid" in columns

    def test_teams_public_id_column_exists(self, schema_db: sqlite3.Connection) -> None:
        """teams.public_id column exists."""
        cursor = schema_db.execute("PRAGMA table_info(teams);")
        columns = {row[1] for row in cursor.fetchall()}
        assert "public_id" in columns

    def test_source_defaults_to_gamechanger(self, schema_db: sqlite3.Connection) -> None:
        """source column defaults to 'gamechanger' when not specified."""
        cursor = schema_db.execute(
            "INSERT INTO teams (name, membership_type) VALUES ('Test Team', 'member');"
        )
        team_id = cursor.lastrowid
        row = schema_db.execute(
            "SELECT source FROM teams WHERE id = ?;", (team_id,)
        ).fetchone()
        assert row is not None
        assert row[0] == "gamechanger"

    def test_is_active_defaults_to_1(self, schema_db: sqlite3.Connection) -> None:
        """is_active defaults to 1 (crawl enabled) when not specified."""
        cursor = schema_db.execute(
            "INSERT INTO teams (name, membership_type) VALUES ('Another Team', 'tracked');"
        )
        team_id = cursor.lastrowid
        row = schema_db.execute(
            "SELECT is_active FROM teams WHERE id = ?;", (team_id,)
        ).fetchone()
        assert row is not None
        assert row[0] == 1

    def test_last_synced_is_nullable(self, schema_db: sqlite3.Connection) -> None:
        """last_synced is NULL by default (not yet crawled)."""
        cursor = schema_db.execute(
            "INSERT INTO teams (name, membership_type) VALUES ('Nullable Team', 'tracked');"
        )
        team_id = cursor.lastrowid
        row = schema_db.execute(
            "SELECT last_synced FROM teams WHERE id = ?;", (team_id,)
        ).fetchone()
        assert row is not None
        assert row[0] is None

    def test_public_id_unique_constraint(self, schema_db: sqlite3.Connection) -> None:
        """Two teams with the same non-NULL public_id raises IntegrityError."""
        schema_db.execute(
            "INSERT INTO teams (name, membership_type, public_id) VALUES ('A', 'tracked', 'slug1');"
        )
        schema_db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            schema_db.execute(
                "INSERT INTO teams (name, membership_type, public_id) VALUES ('B', 'tracked', 'slug1');"
            )

    def test_multiple_null_public_ids_allowed(self, schema_db: sqlite3.Connection) -> None:
        """Multiple teams with public_id = NULL is allowed (partial unique index)."""
        schema_db.execute(
            "INSERT INTO teams (name, membership_type, public_id) VALUES ('A', 'tracked', NULL);"
        )
        schema_db.execute(
            "INSERT INTO teams (name, membership_type, public_id) VALUES ('B', 'tracked', NULL);"
        )
        schema_db.execute(
            "INSERT INTO teams (name, membership_type, public_id) VALUES ('C', 'tracked', NULL);"
        )
        schema_db.commit()
        count = schema_db.execute(
            "SELECT COUNT(*) FROM teams WHERE public_id IS NULL;"
        ).fetchone()[0]
        assert count == 3


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
# Tests: FK enforcement
# ---------------------------------------------------------------------------


class TestForeignKeyEnforcement:
    """Verify FK constraints are enforced with PRAGMA foreign_keys=ON."""

    def _insert_season(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "INSERT INTO seasons (season_id, name, season_type, year) "
            "VALUES ('2026-spring-hs', 'Spring 2026 HS', 'spring-hs', 2026);"
        )

    def _insert_team(self, conn: sqlite3.Connection, membership_type: str = "member") -> int:
        cursor = conn.execute(
            "INSERT INTO teams (name, membership_type) VALUES ('Test Team', ?);",
            (membership_type,),
        )
        return cursor.lastrowid

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
        """Inserting team_rosters with a bad season_id raises IntegrityError."""
        team_id = self._insert_team(schema_db)
        self._insert_player(schema_db)
        with pytest.raises(sqlite3.IntegrityError):
            schema_db.execute(
                "INSERT INTO team_rosters (team_id, player_id, season_id) VALUES (?, 'p-001', 'nonexistent-season');",
                (team_id,),
            )

    def test_team_rosters_accepts_valid_season_id(
        self, schema_db: sqlite3.Connection
    ) -> None:
        """team_rosters insert succeeds when season_id exists in seasons."""
        self._insert_season(schema_db)
        team_id = self._insert_team(schema_db)
        self._insert_player(schema_db)
        schema_db.execute(
            "INSERT INTO team_rosters (team_id, player_id, season_id) VALUES (?, 'p-001', '2026-spring-hs');",
            (team_id,),
        )
        count = schema_db.execute("SELECT COUNT(*) FROM team_rosters;").fetchone()[0]
        assert count == 1

    def test_games_rejects_nonexistent_season_id(
        self, schema_db: sqlite3.Connection
    ) -> None:
        """Inserting games with a bad season_id raises IntegrityError."""
        home_id = self._insert_team(schema_db, "member")
        away_id = self._insert_team(schema_db, "tracked")
        with pytest.raises(sqlite3.IntegrityError):
            schema_db.execute(
                "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id) "
                "VALUES ('g-001', 'nonexistent-season', '2026-03-15', ?, ?);",
                (home_id, away_id),
            )

    def test_games_accepts_valid_season_id(
        self, schema_db: sqlite3.Connection
    ) -> None:
        """games insert succeeds when season_id exists in seasons."""
        self._insert_season(schema_db)
        home_id = self._insert_team(schema_db, "member")
        away_id = self._insert_team(schema_db, "tracked")
        schema_db.execute(
            "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id) "
            "VALUES ('g-001', '2026-spring-hs', '2026-03-15', ?, ?);",
            (home_id, away_id),
        )
        count = schema_db.execute("SELECT COUNT(*) FROM games;").fetchone()[0]
        assert count == 1

    def test_player_season_batting_rejects_nonexistent_season_id(
        self, schema_db: sqlite3.Connection
    ) -> None:
        """player_season_batting rejects a season_id not in seasons."""
        team_id = self._insert_team(schema_db)
        self._insert_player(schema_db)
        with pytest.raises(sqlite3.IntegrityError):
            schema_db.execute(
                "INSERT INTO player_season_batting (player_id, team_id, season_id) VALUES ('p-001', ?, 'nonexistent-season');",
                (team_id,),
            )

    def test_player_season_pitching_rejects_nonexistent_season_id(
        self, schema_db: sqlite3.Connection
    ) -> None:
        """player_season_pitching rejects a season_id not in seasons."""
        team_id = self._insert_team(schema_db)
        self._insert_player(schema_db)
        with pytest.raises(sqlite3.IntegrityError):
            schema_db.execute(
                "INSERT INTO player_season_pitching (player_id, team_id, season_id) VALUES ('p-001', ?, 'nonexistent-season');",
                (team_id,),
            )


# ---------------------------------------------------------------------------
# Tests: crawl config query
# ---------------------------------------------------------------------------


class TestCrawlConfigQuery:
    """Verify the crawl config query: SELECT * FROM teams WHERE is_active = 1."""

    def test_active_filter_returns_only_active_teams(
        self, schema_db: sqlite3.Connection
    ) -> None:
        """is_active=1 filter returns only active teams."""
        schema_db.execute(
            "INSERT INTO teams (name, membership_type, gc_uuid, is_active) VALUES ('Active Team', 'member', 'active-uuid', 1);"
        )
        schema_db.execute(
            "INSERT INTO teams (name, membership_type, gc_uuid, is_active) VALUES ('Inactive Team', 'tracked', 'inactive-uuid', 0);"
        )
        rows = schema_db.execute(
            "SELECT gc_uuid FROM teams WHERE is_active = 1;"
        ).fetchall()
        uuids = {row[0] for row in rows}
        assert "active-uuid" in uuids
        assert "inactive-uuid" not in uuids

    def test_active_filter_returns_correct_count(
        self, schema_db: sqlite3.Connection
    ) -> None:
        """is_active=1 filter returns exactly the right number of teams."""
        schema_db.executemany(
            "INSERT INTO teams (name, membership_type, is_active) VALUES (?, ?, ?);",
            [
                ("Team 1", "member", 1),
                ("Team 2", "member", 1),
                ("Team 3", "tracked", 0),
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
            "INSERT INTO teams (name, membership_type, is_active) VALUES ('Skip Me', 'tracked', 0);"
        )
        rows = schema_db.execute(
            "SELECT id FROM teams WHERE is_active = 1;"
        ).fetchall()
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# Tests: indexes exist
# ---------------------------------------------------------------------------

_EXPECTED_INDEXES = {
    "idx_team_rosters_team_season",
    "idx_team_rosters_player",
    "idx_games_season_id",
    "idx_games_home_team_id",
    "idx_games_away_team_id",
    "idx_pgb_game_id",
    "idx_pgb_player_id",
    "idx_pgb_team_id",
    "idx_pgp_game_id",
    "idx_pgp_player_id",
    "idx_pgp_team_id",
    "idx_psb_player_season",
    "idx_psb_team_season",
    "idx_psp_player_season",
    "idx_psp_team_season",
    "idx_teams_gc_uuid",
    "idx_teams_public_id",
    "idx_scouting_runs_team_season",
    "idx_coaching_assignments_user",
    "idx_coaching_assignments_team",
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
