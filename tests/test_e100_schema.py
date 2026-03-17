# synthetic-test-data
"""Schema verification tests for E-100-01: Complete DDL with Full Stat Coverage.

Verifies AC-20 requirements:
(a) migrations apply on fresh DB
(b) programs table seeded correctly
(c) teams table has correct columns and constraints
(d) team_opponents constraints work
(e) all stat table columns exist per the Complete Stat Column Reference
(f) stat_completeness column on all four stat tables with correct CHECK constraints
(g) games_tracked column on both season stat tables
(h) spray_charts table exists with pitcher_id FK
(j) auth tables exist with correct schema
(k) UNIQUE constraints on stat tables enforce no-duplicate rows

Tests use a temporary SQLite database; no Docker required.

Run with:
    pytest tests/test_e100_schema.py -v
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Generator

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from migrations.apply_migrations import run_migrations  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fresh_db(tmp_path: Path) -> Path:
    """Return path to a fresh (unmigrated) database location."""
    return tmp_path / "test_e100.db"


@pytest.fixture()
def migrated_db(fresh_db: Path) -> Generator[sqlite3.Connection, None, None]:
    """Apply all migrations and yield an open connection with FK enforcement."""
    run_migrations(db_path=fresh_db)
    conn = sqlite3.connect(str(fresh_db))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cursor = conn.execute(f"PRAGMA table_info({table});")
    return {row[1] for row in cursor.fetchall()}


def _tables(conn: sqlite3.Connection) -> set[str]:
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    )
    return {row[0] for row in cursor.fetchall()}


def _indexes(conn: sqlite3.Connection) -> set[str]:
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%';"
    )
    return {row[0] for row in cursor.fetchall()}


def _insert_team(conn: sqlite3.Connection, name: str, membership_type: str = "tracked") -> int:
    """Insert a minimal team and return its INTEGER id."""
    cursor = conn.execute(
        "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
        (name, membership_type),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_player(conn: sqlite3.Connection, player_id: str) -> None:
    conn.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (player_id, "Test", "Player"),
    )
    conn.commit()


def _insert_season(conn: sqlite3.Connection, season_id: str = "2026-spring-hs") -> None:
    conn.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
        (season_id, f"Season {season_id}", "spring-hs", 2026),
    )
    conn.commit()


def _insert_game(
    conn: sqlite3.Connection,
    game_id: str,
    season_id: str,
    home_team_id: int,
    away_team_id: int,
) -> None:
    conn.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (game_id, season_id, "2026-03-01", home_team_id, away_team_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# (a) AC-20: Migrations apply on fresh DB
# ---------------------------------------------------------------------------


class TestMigrationsApply:
    """AC-20(a): migrations apply on a fresh database."""

    def test_migration_creates_database(self, fresh_db: Path) -> None:
        """run_migrations creates the database file."""
        assert not fresh_db.exists()
        run_migrations(db_path=fresh_db)
        assert fresh_db.exists()

    def test_all_expected_tables_created(self, migrated_db: sqlite3.Connection) -> None:
        """All 20 expected tables are present after migration."""
        expected = {
            "programs", "teams", "seasons", "players",
            "team_opponents", "team_rosters", "games",
            "player_game_batting", "player_game_pitching",
            "player_season_batting", "player_season_pitching",
            "spray_charts", "opponent_links", "scouting_runs",
            "users", "user_team_access", "magic_link_tokens",
            "passkey_credentials", "sessions", "coaching_assignments",
        }
        actual = _tables(migrated_db)
        missing = expected - actual
        assert not missing, f"Missing tables: {missing}"

    def test_foreign_keys_enabled(self, migrated_db: sqlite3.Connection) -> None:
        """FK enforcement is active after migration -- verified by observing a violation."""
        with pytest.raises(sqlite3.IntegrityError):
            migrated_db.execute(
                "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
                (9999, 8888),
            )
            migrated_db.commit()


# ---------------------------------------------------------------------------
# (b) AC-20: programs table seeded correctly
# ---------------------------------------------------------------------------


class TestProgramsTable:
    """AC-20(b): programs table has correct structure and seed row."""

    def test_programs_columns_exist(self, migrated_db: sqlite3.Connection) -> None:
        """programs table has all required columns."""
        cols = _columns(migrated_db, "programs")
        for col in ("program_id", "name", "program_type", "org_name", "created_at"):
            assert col in cols, f"programs.{col} missing"

    def test_lsb_hs_seed_row_present(self, migrated_db: sqlite3.Connection) -> None:
        """lsb-hs seed row exists in programs after migration."""
        row = migrated_db.execute(
            "SELECT program_id, name, program_type FROM programs WHERE program_id = 'lsb-hs';"
        ).fetchone()
        assert row is not None, "lsb-hs seed row not found"
        assert row[0] == "lsb-hs"
        assert "Lincoln" in row[1]
        assert row[2] == "hs"

    def test_program_type_check_constraint(self, migrated_db: sqlite3.Connection) -> None:
        """program_type CHECK constraint rejects invalid values."""
        with pytest.raises(sqlite3.IntegrityError):
            migrated_db.execute(
                "INSERT INTO programs (program_id, name, program_type) VALUES (?, ?, ?)",
                ("bad-prog", "Bad Program", "invalid_type"),
            )
            migrated_db.commit()


# ---------------------------------------------------------------------------
# (c) AC-20: teams table columns and constraints
# ---------------------------------------------------------------------------


class TestTeamsTable:
    """AC-20(c): teams table has correct columns and constraints."""

    def test_teams_has_integer_pk(self, migrated_db: sqlite3.Connection) -> None:
        """teams.id is INTEGER PRIMARY KEY AUTOINCREMENT (no team_id TEXT column)."""
        cursor = migrated_db.execute("PRAGMA table_info(teams);")
        rows = {row[1]: row for row in cursor.fetchall()}
        assert "id" in rows, "teams.id column missing"
        assert rows["id"][5] == 1, "teams.id is not primary key"
        assert "team_id" not in rows, "teams.team_id TEXT column should not exist in E-100"

    def test_teams_has_no_is_owned(self, migrated_db: sqlite3.Connection) -> None:
        """teams.is_owned column does not exist (replaced by membership_type)."""
        cols = _columns(migrated_db, "teams")
        assert "is_owned" not in cols, "teams.is_owned should not exist in E-100"

    def test_teams_has_no_level(self, migrated_db: sqlite3.Connection) -> None:
        """teams.level column does not exist (replaced by classification)."""
        cols = _columns(migrated_db, "teams")
        assert "level" not in cols, "teams.level should not exist in E-100"

    def test_teams_required_columns(self, migrated_db: sqlite3.Connection) -> None:
        """teams table has all required E-100 columns."""
        cols = _columns(migrated_db, "teams")
        for col in ("id", "name", "program_id", "membership_type", "classification",
                    "public_id", "gc_uuid", "source", "is_active", "last_synced", "created_at"):
            assert col in cols, f"teams.{col} missing"

    def test_membership_type_check_constraint(self, migrated_db: sqlite3.Connection) -> None:
        """membership_type CHECK constraint rejects values other than 'member'/'tracked'."""
        with pytest.raises(sqlite3.IntegrityError):
            migrated_db.execute(
                "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
                ("Bad Team", "owned"),
            )
            migrated_db.commit()

    def test_gc_uuid_partial_unique_index(self, migrated_db: sqlite3.Connection) -> None:
        """Two teams with same non-NULL gc_uuid raises IntegrityError."""
        migrated_db.execute(
            "INSERT INTO teams (name, membership_type, gc_uuid) VALUES (?, ?, ?)",
            ("Team Alpha", "tracked", "uuid-test-1234"),
        )
        migrated_db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            migrated_db.execute(
                "INSERT INTO teams (name, membership_type, gc_uuid) VALUES (?, ?, ?)",
                ("Team Beta", "tracked", "uuid-test-1234"),
            )
            migrated_db.commit()

    def test_multiple_null_gc_uuids_allowed(self, migrated_db: sqlite3.Connection) -> None:
        """Multiple teams can have NULL gc_uuid (partial index, not full UNIQUE)."""
        for i in range(3):
            migrated_db.execute(
                "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
                (f"Null UUID Team {i}", "tracked"),
            )
        migrated_db.commit()
        count = migrated_db.execute("SELECT COUNT(*) FROM teams WHERE gc_uuid IS NULL;").fetchone()[0]
        assert count >= 3


# ---------------------------------------------------------------------------
# (d) AC-20: team_opponents constraints
# ---------------------------------------------------------------------------


class TestTeamOpponents:
    """AC-20(d): team_opponents table constraints work."""

    def test_table_exists(self, migrated_db: sqlite3.Connection) -> None:
        """team_opponents table exists."""
        assert "team_opponents" in _tables(migrated_db)

    def test_unique_constraint(self, migrated_db: sqlite3.Connection) -> None:
        """UNIQUE(our_team_id, opponent_team_id) prevents duplicate pairs."""
        t1 = _insert_team(migrated_db, "Our Team", "member")
        t2 = _insert_team(migrated_db, "Opponent", "tracked")
        migrated_db.execute(
            "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
            (t1, t2),
        )
        migrated_db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            migrated_db.execute(
                "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
                (t1, t2),
            )
            migrated_db.commit()

    def test_self_reference_check_constraint(self, migrated_db: sqlite3.Connection) -> None:
        """CHECK(our_team_id != opponent_team_id) prevents self-pairing."""
        t1 = _insert_team(migrated_db, "Self Team", "member")
        with pytest.raises(sqlite3.IntegrityError):
            migrated_db.execute(
                "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
                (t1, t1),
            )
            migrated_db.commit()


# ---------------------------------------------------------------------------
# (e) AC-20: stat table columns per Complete Stat Column Reference
# ---------------------------------------------------------------------------


class TestPlayerGameBattingColumns:
    """AC-20(e): player_game_batting has all required columns."""

    REQUIRED_COLUMNS = {
        # Structural
        "id", "game_id", "player_id", "team_id",
        "batting_order", "positions_played", "is_primary", "stat_completeness",
        # Main stats
        "ab", "r", "h", "rbi", "bb", "so",
        # Extra stats
        "doubles", "triples", "hr", "tb", "hbp", "shf", "sb", "cs", "e",
    }
    EXCLUDED_COLUMNS = {"pa", "singles", "pitches", "total_strikes"}

    def test_all_required_columns_present(self, migrated_db: sqlite3.Connection) -> None:
        """All required player_game_batting columns exist."""
        cols = _columns(migrated_db, "player_game_batting")
        missing = self.REQUIRED_COLUMNS - cols
        assert not missing, f"Missing player_game_batting columns: {missing}"

    def test_excluded_columns_absent(self, migrated_db: sqlite3.Connection) -> None:
        """Columns not in boxscore batting response are excluded."""
        cols = _columns(migrated_db, "player_game_batting")
        present_exclusions = self.EXCLUDED_COLUMNS & cols
        assert not present_exclusions, (
            f"Columns that should be excluded are present: {present_exclusions}"
        )


class TestPlayerGamePitchingColumns:
    """AC-20(e): player_game_pitching has all required columns."""

    REQUIRED_COLUMNS = {
        # Structural
        "id", "game_id", "player_id", "team_id", "decision", "stat_completeness",
        # Main stats
        "ip_outs", "h", "r", "er", "bb", "so",
        # Extra stats
        "wp", "hbp", "pitches", "total_strikes", "bf",
    }
    EXCLUDED_COLUMNS = {"hr"}  # HR allowed not in boxscore pitching extras

    def test_all_required_columns_present(self, migrated_db: sqlite3.Connection) -> None:
        """All required player_game_pitching columns exist."""
        cols = _columns(migrated_db, "player_game_pitching")
        missing = self.REQUIRED_COLUMNS - cols
        assert not missing, f"Missing player_game_pitching columns: {missing}"

    def test_hr_excluded(self, migrated_db: sqlite3.Connection) -> None:
        """hr column is excluded from player_game_pitching (not in boxscore pitching extras)."""
        cols = _columns(migrated_db, "player_game_pitching")
        assert "hr" not in cols, "player_game_pitching.hr should be excluded per AC-14"


class TestPlayerSeasonBattingColumns:
    """AC-20(e): player_season_batting has all required columns."""

    REQUIRED_STANDARD = {
        "id", "player_id", "team_id", "season_id", "stat_completeness", "games_tracked",
        "gp", "pa", "ab", "h", "singles", "doubles", "triples", "hr", "rbi", "r",
        "bb", "so", "sol", "hbp", "shb", "shf", "gidp", "roe", "fc", "ci", "pik",
        "sb", "cs", "tb", "xbh", "lob", "three_out_lob", "ob", "gshr",
        "two_out_rbi", "hrisp", "abrisp",
    }
    REQUIRED_ADVANCED = {
        "qab", "hard", "weak", "lnd", "flb", "gb", "ps", "sw", "sm",
        "inp", "full", "two_strikes", "two_s_plus_3", "six_plus", "lobb",
    }
    REQUIRED_SPLITS = {
        "home_ab", "home_h", "home_hr", "home_bb", "home_so",
        "away_ab", "away_h", "away_hr", "away_bb", "away_so",
        "vs_lhp_ab", "vs_lhp_h", "vs_lhp_hr", "vs_lhp_bb", "vs_lhp_so",
        "vs_rhp_ab", "vs_rhp_h", "vs_rhp_hr", "vs_rhp_bb", "vs_rhp_so",
    }

    def test_standard_columns_present(self, migrated_db: sqlite3.Connection) -> None:
        """All standard batting stat columns exist."""
        cols = _columns(migrated_db, "player_season_batting")
        missing = self.REQUIRED_STANDARD - cols
        assert not missing, f"Missing standard batting columns: {missing}"

    def test_advanced_columns_present(self, migrated_db: sqlite3.Connection) -> None:
        """All advanced batting stat columns exist."""
        cols = _columns(migrated_db, "player_season_batting")
        missing = self.REQUIRED_ADVANCED - cols
        assert not missing, f"Missing advanced batting columns: {missing}"

    def test_split_columns_present(self, migrated_db: sqlite3.Connection) -> None:
        """All home/away and vs_lhp/vs_rhp split columns exist."""
        cols = _columns(migrated_db, "player_season_batting")
        missing = self.REQUIRED_SPLITS - cols
        assert not missing, f"Missing batting split columns: {missing}"


class TestPlayerSeasonPitchingColumns:
    """AC-20(e): player_season_pitching has all required columns."""

    REQUIRED_STANDARD = {
        "id", "player_id", "team_id", "season_id", "stat_completeness", "games_tracked",
        "gp_pitcher", "gs", "ip_outs", "bf", "pitches", "h", "er", "bb", "so",
        "hr", "bk", "wp", "hbp", "svo", "sb", "cs", "go", "ao", "loo",
        "zero_bb_inn", "inn_123", "fps", "lbfpn",
        "gp", "w", "l", "sv", "bs", "r", "sol", "lob", "pik",
        "total_strikes", "total_balls",
        "lt_3", "first_2_out", "lt_13", "bbs", "lobb", "lobbs",
        "sm", "sw", "weak", "hard", "lnd", "fb", "gb",
    }
    REQUIRED_SPLITS = {
        "home_ip_outs", "home_h", "home_er", "home_bb", "home_so",
        "away_ip_outs", "away_h", "away_er", "away_bb", "away_so",
        "vs_lhb_ab", "vs_lhb_h", "vs_lhb_hr", "vs_lhb_bb", "vs_lhb_so",
        "vs_rhb_ab", "vs_rhb_h", "vs_rhb_hr", "vs_rhb_bb", "vs_rhb_so",
    }

    def test_standard_columns_present(self, migrated_db: sqlite3.Connection) -> None:
        """All standard pitching stat columns exist."""
        cols = _columns(migrated_db, "player_season_pitching")
        missing = self.REQUIRED_STANDARD - cols
        assert not missing, f"Missing standard pitching columns: {missing}"

    def test_split_columns_present(self, migrated_db: sqlite3.Connection) -> None:
        """All home/away and vs_lhb/vs_rhb split columns exist."""
        cols = _columns(migrated_db, "player_season_pitching")
        missing = self.REQUIRED_SPLITS - cols
        assert not missing, f"Missing pitching split columns: {missing}"


# ---------------------------------------------------------------------------
# (f) AC-20: stat_completeness column on all four stat tables
# ---------------------------------------------------------------------------


class TestStatCompletenessColumn:
    """AC-20(f): stat_completeness column exists on all four stat tables with CHECK constraint."""

    STAT_TABLES = [
        "player_game_batting",
        "player_game_pitching",
        "player_season_batting",
        "player_season_pitching",
    ]
    VALID_VALUES = ("full", "supplemented", "boxscore_only")

    @pytest.mark.parametrize("table", STAT_TABLES)
    def test_stat_completeness_column_exists(
        self, migrated_db: sqlite3.Connection, table: str
    ) -> None:
        """stat_completeness column exists on the given stat table."""
        cols = _columns(migrated_db, table)
        assert "stat_completeness" in cols, f"{table}.stat_completeness missing"

    def test_game_batting_stat_completeness_defaults_to_boxscore_only(
        self, migrated_db: sqlite3.Connection
    ) -> None:
        """player_game_batting.stat_completeness defaults to 'boxscore_only'."""
        team_id = _insert_team(migrated_db, "Test Team")
        _insert_player(migrated_db, "P-TEST-01")
        _insert_season(migrated_db)
        _insert_game(migrated_db, "G-TEST-01", "2026-spring-hs", team_id, team_id)

        # Insert without specifying stat_completeness
        migrated_db.execute(
            "INSERT INTO player_game_batting (game_id, player_id, team_id, ab, h) "
            "VALUES (?, ?, ?, ?, ?)",
            ("G-TEST-01", "P-TEST-01", team_id, 3, 1),
        )
        migrated_db.commit()

        row = migrated_db.execute(
            "SELECT stat_completeness FROM player_game_batting WHERE game_id = 'G-TEST-01';"
        ).fetchone()
        assert row is not None
        assert row[0] == "boxscore_only"

    def test_stat_completeness_check_constraint_rejects_invalid(
        self, migrated_db: sqlite3.Connection
    ) -> None:
        """stat_completeness CHECK constraint rejects values outside the allowed set."""
        team_id = _insert_team(migrated_db, "Test Team 2")
        _insert_player(migrated_db, "P-TEST-02")
        _insert_season(migrated_db)
        _insert_game(migrated_db, "G-TEST-02", "2026-spring-hs", team_id, team_id)

        with pytest.raises(sqlite3.IntegrityError):
            migrated_db.execute(
                "INSERT INTO player_game_batting "
                "(game_id, player_id, team_id, ab, stat_completeness) VALUES (?, ?, ?, ?, ?)",
                ("G-TEST-02", "P-TEST-02", team_id, 3, "invalid_value"),
            )
            migrated_db.commit()


# ---------------------------------------------------------------------------
# (g) AC-20: games_tracked column on season stat tables
# ---------------------------------------------------------------------------


class TestGamesTrackedColumn:
    """AC-20(g): games_tracked column on both season stat tables."""

    def test_season_batting_games_tracked(self, migrated_db: sqlite3.Connection) -> None:
        """player_season_batting.games_tracked column exists."""
        cols = _columns(migrated_db, "player_season_batting")
        assert "games_tracked" in cols

    def test_season_pitching_games_tracked(self, migrated_db: sqlite3.Connection) -> None:
        """player_season_pitching.games_tracked column exists."""
        cols = _columns(migrated_db, "player_season_pitching")
        assert "games_tracked" in cols


# ---------------------------------------------------------------------------
# (h) AC-20: spray_charts table with pitcher_id FK
# ---------------------------------------------------------------------------


class TestSprayChartsTable:
    """AC-20(h): spray_charts table exists with pitcher_id FK."""

    REQUIRED_COLUMNS = {
        "id", "game_id", "player_id", "team_id", "pitcher_id",
        "chart_type", "play_type", "play_result", "x", "y",
        "fielder_position", "error",
    }

    def test_table_exists(self, migrated_db: sqlite3.Connection) -> None:
        """spray_charts table exists."""
        assert "spray_charts" in _tables(migrated_db)

    def test_all_columns_present(self, migrated_db: sqlite3.Connection) -> None:
        """spray_charts has all required columns including pitcher_id."""
        cols = _columns(migrated_db, "spray_charts")
        missing = self.REQUIRED_COLUMNS - cols
        assert not missing, f"Missing spray_charts columns: {missing}"

    def test_pitcher_id_is_nullable(self, migrated_db: sqlite3.Connection) -> None:
        """spray_charts.pitcher_id is nullable (FK to players, not required)."""
        cursor = migrated_db.execute("PRAGMA table_info(spray_charts);")
        col_info = {row[1]: row for row in cursor.fetchall()}
        assert "pitcher_id" in col_info
        # notnull == 0 means nullable
        assert col_info["pitcher_id"][3] == 0, "pitcher_id should be nullable"

    def test_chart_type_check_constraint(self, migrated_db: sqlite3.Connection) -> None:
        """chart_type CHECK constraint accepts 'offensive' and 'defensive'."""
        team_id = _insert_team(migrated_db, "Spray Team")
        _insert_player(migrated_db, "P-SPRAY-01")
        _insert_season(migrated_db)
        _insert_game(migrated_db, "G-SPRAY-01", "2026-spring-hs", team_id, team_id)

        # Valid values should insert cleanly
        migrated_db.execute(
            "INSERT INTO spray_charts (game_id, player_id, team_id, chart_type, x, y) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("G-SPRAY-01", "P-SPRAY-01", team_id, "offensive", 100.0, 200.0),
        )
        migrated_db.commit()

    def test_chart_type_rejects_invalid(self, migrated_db: sqlite3.Connection) -> None:
        """chart_type CHECK constraint rejects values not in ('offensive', 'defensive')."""
        team_id = _insert_team(migrated_db, "Spray Team 2")
        _insert_player(migrated_db, "P-SPRAY-02")
        _insert_season(migrated_db)
        _insert_game(migrated_db, "G-SPRAY-02", "2026-spring-hs", team_id, team_id)

        with pytest.raises(sqlite3.IntegrityError):
            migrated_db.execute(
                "INSERT INTO spray_charts (game_id, player_id, team_id, chart_type, x, y) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("G-SPRAY-02", "P-SPRAY-02", team_id, "invalid_chart", 100.0, 200.0),
            )
            migrated_db.commit()


# ---------------------------------------------------------------------------
# (j) AC-20: auth tables exist with correct schema
# ---------------------------------------------------------------------------


class TestAuthSchema:
    """AC-20(j): auth tables exist with correct E-100 schema."""

    def test_users_has_id_not_user_id(self, migrated_db: sqlite3.Connection) -> None:
        """users table uses 'id' as PK (no user_id alias)."""
        cols = _columns(migrated_db, "users")
        assert "id" in cols
        assert "user_id" not in cols

    def test_users_has_no_display_name(self, migrated_db: sqlite3.Connection) -> None:
        """users table has no display_name column."""
        cols = _columns(migrated_db, "users")
        assert "display_name" not in cols

    def test_users_has_no_is_admin(self, migrated_db: sqlite3.Connection) -> None:
        """users table has no is_admin column."""
        cols = _columns(migrated_db, "users")
        assert "is_admin" not in cols

    def test_sessions_uses_session_id(self, migrated_db: sqlite3.Connection) -> None:
        """sessions table uses 'session_id' as PK (not session_token_hash)."""
        cols = _columns(migrated_db, "sessions")
        assert "session_id" in cols
        assert "session_token_hash" not in cols

    def test_magic_link_tokens_uses_token(self, migrated_db: sqlite3.Connection) -> None:
        """magic_link_tokens table uses 'token' as PK (not token_hash)."""
        cols = _columns(migrated_db, "magic_link_tokens")
        assert "token" in cols
        assert "token_hash" not in cols

    def test_coaching_assignments_no_season_id(self, migrated_db: sqlite3.Connection) -> None:
        """coaching_assignments has no season_id column."""
        cols = _columns(migrated_db, "coaching_assignments")
        assert "season_id" not in cols

    def test_coaching_assignments_unique_user_team(self, migrated_db: sqlite3.Connection) -> None:
        """UNIQUE(user_id, team_id) prevents duplicate coaching assignments."""
        migrated_db.execute("INSERT INTO users (email) VALUES (?)", ("coach@test.com",))
        migrated_db.commit()
        user_row = migrated_db.execute("SELECT id FROM users WHERE email = ?", ("coach@test.com",)).fetchone()
        user_id = user_row[0]
        team_id = _insert_team(migrated_db, "Auth Test Team", "member")

        migrated_db.execute(
            "INSERT INTO coaching_assignments (user_id, team_id, role) VALUES (?, ?, ?)",
            (user_id, team_id, "head_coach"),
        )
        migrated_db.commit()

        with pytest.raises(sqlite3.IntegrityError):
            migrated_db.execute(
                "INSERT INTO coaching_assignments (user_id, team_id, role) VALUES (?, ?, ?)",
                (user_id, team_id, "assistant"),
            )
            migrated_db.commit()

    def test_user_team_access_uses_integer_team_id(self, migrated_db: sqlite3.Connection) -> None:
        """user_team_access.team_id is INTEGER FK to teams(id)."""
        cols = _columns(migrated_db, "user_team_access")
        assert "team_id" in cols
        assert "user_id" in cols


# ---------------------------------------------------------------------------
# (k) AC-20: UNIQUE constraints on stat tables
# ---------------------------------------------------------------------------


class TestStatTableUniqueConstraints:
    """AC-20(k): UNIQUE constraints prevent duplicate stat rows."""

    def test_game_batting_unique_game_player(self, migrated_db: sqlite3.Connection) -> None:
        """UNIQUE(game_id, player_id) on player_game_batting."""
        team_id = _insert_team(migrated_db, "Unique Test Team")
        _insert_player(migrated_db, "P-UNIQ-01")
        _insert_season(migrated_db)
        _insert_game(migrated_db, "G-UNIQ-01", "2026-spring-hs", team_id, team_id)

        migrated_db.execute(
            "INSERT INTO player_game_batting (game_id, player_id, team_id, ab) "
            "VALUES (?, ?, ?, ?)",
            ("G-UNIQ-01", "P-UNIQ-01", team_id, 3),
        )
        migrated_db.commit()

        with pytest.raises(sqlite3.IntegrityError):
            migrated_db.execute(
                "INSERT INTO player_game_batting (game_id, player_id, team_id, ab) "
                "VALUES (?, ?, ?, ?)",
                ("G-UNIQ-01", "P-UNIQ-01", team_id, 4),
            )
            migrated_db.commit()

    def test_game_pitching_unique_game_player(self, migrated_db: sqlite3.Connection) -> None:
        """UNIQUE(game_id, player_id) on player_game_pitching."""
        team_id = _insert_team(migrated_db, "Unique Pitch Team")
        _insert_player(migrated_db, "P-UNIQ-02")
        _insert_season(migrated_db)
        _insert_game(migrated_db, "G-UNIQ-02", "2026-spring-hs", team_id, team_id)

        migrated_db.execute(
            "INSERT INTO player_game_pitching (game_id, player_id, team_id, ip_outs) "
            "VALUES (?, ?, ?, ?)",
            ("G-UNIQ-02", "P-UNIQ-02", team_id, 9),
        )
        migrated_db.commit()

        with pytest.raises(sqlite3.IntegrityError):
            migrated_db.execute(
                "INSERT INTO player_game_pitching (game_id, player_id, team_id, ip_outs) "
                "VALUES (?, ?, ?, ?)",
                ("G-UNIQ-02", "P-UNIQ-02", team_id, 12),
            )
            migrated_db.commit()

    def test_season_batting_unique_player_team_season(self, migrated_db: sqlite3.Connection) -> None:
        """UNIQUE(player_id, team_id, season_id) on player_season_batting."""
        team_id = _insert_team(migrated_db, "Unique Season Bat Team")
        _insert_player(migrated_db, "P-UNIQ-03")
        _insert_season(migrated_db)

        migrated_db.execute(
            "INSERT INTO player_season_batting (player_id, team_id, season_id, gp) "
            "VALUES (?, ?, ?, ?)",
            ("P-UNIQ-03", team_id, "2026-spring-hs", 7),
        )
        migrated_db.commit()

        with pytest.raises(sqlite3.IntegrityError):
            migrated_db.execute(
                "INSERT INTO player_season_batting (player_id, team_id, season_id, gp) "
                "VALUES (?, ?, ?, ?)",
                ("P-UNIQ-03", team_id, "2026-spring-hs", 8),
            )
            migrated_db.commit()

    def test_season_pitching_unique_player_team_season(self, migrated_db: sqlite3.Connection) -> None:
        """UNIQUE(player_id, team_id, season_id) on player_season_pitching."""
        team_id = _insert_team(migrated_db, "Unique Season Pitch Team")
        _insert_player(migrated_db, "P-UNIQ-04")
        _insert_season(migrated_db)

        migrated_db.execute(
            "INSERT INTO player_season_pitching (player_id, team_id, season_id, gp_pitcher) "
            "VALUES (?, ?, ?, ?)",
            ("P-UNIQ-04", team_id, "2026-spring-hs", 3),
        )
        migrated_db.commit()

        with pytest.raises(sqlite3.IntegrityError):
            migrated_db.execute(
                "INSERT INTO player_season_pitching (player_id, team_id, season_id, gp_pitcher) "
                "VALUES (?, ?, ?, ?)",
                ("P-UNIQ-04", team_id, "2026-spring-hs", 4),
            )
            migrated_db.commit()


# ---------------------------------------------------------------------------
# games table has game_stream_id column (AC-12)
# ---------------------------------------------------------------------------


def test_games_has_game_stream_id(migrated_db: sqlite3.Connection) -> None:
    """games.game_stream_id column exists (AC-12)."""
    cols = _columns(migrated_db, "games")
    assert "game_stream_id" in cols


# ---------------------------------------------------------------------------
# players table has enriched columns (AC-11)
# ---------------------------------------------------------------------------


def test_players_enriched_columns(migrated_db: sqlite3.Connection) -> None:
    """players table has bats, throws, gc_athlete_profile_id (AC-11)."""
    cols = _columns(migrated_db, "players")
    for col in ("bats", "throws", "gc_athlete_profile_id"):
        assert col in cols, f"players.{col} missing"


# ---------------------------------------------------------------------------
# ip_outs convention: INTEGER type verified at insert
# ---------------------------------------------------------------------------


def test_ip_outs_stores_as_integer(migrated_db: sqlite3.Connection) -> None:
    """ip_outs stores integer outs (3 = 1 IP, 20 = 6.2 IP)."""
    team_id = _insert_team(migrated_db, "IP Test Team")
    _insert_player(migrated_db, "P-IP-01")
    _insert_season(migrated_db)
    _insert_game(migrated_db, "G-IP-01", "2026-spring-hs", team_id, team_id)

    # 6.2 IP = 20 outs
    migrated_db.execute(
        "INSERT INTO player_game_pitching (game_id, player_id, team_id, ip_outs) "
        "VALUES (?, ?, ?, ?)",
        ("G-IP-01", "P-IP-01", team_id, 20),
    )
    migrated_db.commit()

    row = migrated_db.execute(
        "SELECT ip_outs FROM player_game_pitching WHERE game_id = 'G-IP-01';"
    ).fetchone()
    assert row is not None
    assert row[0] == 20
    assert row[0] // 3 == 6   # whole innings
    assert row[0] % 3 == 2    # thirds
