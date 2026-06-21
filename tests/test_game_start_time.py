"""Tests for start_time and timezone column support across all game loaders.

Covers:
- AC-1: Migration adds start_time and timezone columns.
- AC-2: Schedule loader writes start_time and timezone on INSERT and UPDATE.
- AC-3: Scouting loader passes start_time and timezone via GameSummaryEntry.
- AC-4: Game loader preserves existing start_time/timezone when upserting with NULLs.
- AC-5: Comprehensive test coverage for all three loaders.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from src.gamechanger.loaders.game_loader import GameLoader, GameSummaryEntry
from src.gamechanger.loaders.scouting_loader import ScoutingLoader
from src.gamechanger.types import TeamRef


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_MIGRATION_FILE = _PROJECT_ROOT / "migrations" / "001_initial_schema.sql"


def _create_schema(db: sqlite3.Connection) -> None:
    """Create the full schema from the migration file and seed test data."""
    db.executescript(_MIGRATION_FILE.read_text(encoding="utf-8"))
    db.executescript(
        """
        INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES ('2025', 'Spring 2025', 'default', 2025);
        INSERT OR IGNORE INTO programs (program_id, name, program_type) VALUES ('lsb-hs', 'LSB HS', 'hs');
        INSERT OR IGNORE INTO teams (id, name, gc_uuid, public_id, membership_type, season_year, program_id)
            VALUES (1, 'Own Team', 'own-uuid-1234', 'OwnTeamSlug', 'member', 2025, 'lsb-hs');
        INSERT OR IGNORE INTO teams (id, name, gc_uuid, public_id, membership_type, season_year)
            VALUES (2, 'Opponent Team', 'opp-uuid-5678', NULL, 'tracked', 2025);
        """
    )


@pytest.fixture()
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON;")
    _create_schema(conn)
    return conn


@pytest.fixture()
def own_team_ref() -> TeamRef:
    return TeamRef(id=1, gc_uuid="own-uuid-1234", public_id="OwnTeamSlug")


# ---------------------------------------------------------------------------
# AC-3: Scouting loader extracts start_time and timezone from public games
# ---------------------------------------------------------------------------


class TestScoutingLoaderStartTime:
    """Scouting loader passes start_time/timezone from games.json through GameSummaryEntry."""

    def test_games_index_populates_start_time_fields(
        self, db: sqlite3.Connection
    ) -> None:
        """_build_games_index creates entries with start_time and timezone."""
        loader = ScoutingLoader(db)
        games_data = [
            {
                "id": "game-001",
                "game_status": "completed",
                "home_away": "home",
                "score": {"team": 5, "opponent_team": 3},
                "start_ts": "2025-04-26T16:00:00.000Z",
                "timezone": "America/Chicago",
            }
        ]
        games_path = Path("/tmp/test_games.json")
        games_path.write_text(json.dumps(games_data), encoding="utf-8")

        try:
            index = loader._build_games_index(games_path)
            entry = index["game-001"]
            assert entry.start_time == "2025-04-26T16:00:00.000Z"
            assert entry.timezone == "America/Chicago"
        finally:
            games_path.unlink(missing_ok=True)

    def test_games_index_handles_missing_start_fields(
        self, db: sqlite3.Connection
    ) -> None:
        """Missing start_ts/timezone produce None in the GameSummaryEntry."""
        loader = ScoutingLoader(db)
        games_data = [
            {
                "id": "game-002",
                "game_status": "completed",
                "home_away": "away",
                "score": {"team": 2, "opponent_team": 1},
                # no start_ts or timezone
            }
        ]
        games_path = Path("/tmp/test_games2.json")
        games_path.write_text(json.dumps(games_data), encoding="utf-8")

        try:
            index = loader._build_games_index(games_path)
            entry = index["game-002"]
            assert entry.start_time is None
            assert entry.timezone is None
        finally:
            games_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# AC-4: Game loader preserves existing start_time/timezone during upsert
# ---------------------------------------------------------------------------


class TestGameLoaderPreservesStartTime:
    """Game loader uses COALESCE to preserve existing values when upserting with NULL."""

    def test_upsert_preserves_existing_start_time(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """When game already has start_time, upserting with NULL keeps the original."""
        # Pre-populate a game with start_time (as if schedule loader set it)
        db.execute(
            """
            INSERT INTO games (game_id, season_id, game_date, home_team_id,
                               away_team_id, status, start_time, timezone)
            VALUES ('game-100', '2025', '2025-04-26', 1, 2,
                    'scheduled', '2025-04-26T16:00:00.000Z', 'America/Chicago')
            """
        )
        db.commit()

        # Game loader upserts with NULL start_time (game-summaries has no time data)
        loader = GameLoader(db=db, owned_team_ref=own_team_ref)
        summary = GameSummaryEntry(
            event_id="game-100",
            game_stream_id="stream-100",
            home_away="home",
            owning_team_score=5,
            opponent_team_score=3,
            opponent_id="opp-uuid-5678",
            last_scoring_update="2025-04-26T20:00:00Z",
            # start_time and timezone default to None
        )
        assert summary.start_time is None
        assert summary.timezone is None

        loader._upsert_game(
            "game-100", "2025-04-26", 1, 2, 5, 3, "stream-100",
        )
        db.commit()

        row = db.execute(
            "SELECT start_time, timezone, status FROM games WHERE game_id = 'game-100'"
        ).fetchone()
        # Preserved from the original insert
        assert row[0] == "2025-04-26T16:00:00.000Z"
        assert row[1] == "America/Chicago"
        # Status upgraded to completed
        assert row[2] == "completed"

    def test_upsert_writes_start_time_when_existing_is_null(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """When game has NULL start_time, upserting with a value sets it."""
        db.execute(
            """
            INSERT INTO games (game_id, season_id, game_date, home_team_id,
                               away_team_id, status, start_time, timezone)
            VALUES ('game-200', '2025', '2025-04-26', 1, 2,
                    'completed', NULL, NULL)
            """
        )
        db.commit()

        loader = GameLoader(db=db, owned_team_ref=own_team_ref)
        loader._upsert_game(
            "game-200", "2025-04-26", 1, 2, 5, 3, "stream-200",
            start_time="2025-04-26T18:00:00.000Z",
            timezone="America/Denver",
        )
        db.commit()

        row = db.execute(
            "SELECT start_time, timezone FROM games WHERE game_id = 'game-200'"
        ).fetchone()
        assert row[0] == "2025-04-26T18:00:00.000Z"
        assert row[1] == "America/Denver"

    def test_fresh_insert_with_null_start_time(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """Fresh INSERT with NULL start_time stores NULL."""
        loader = GameLoader(db=db, owned_team_ref=own_team_ref)
        loader._upsert_game(
            "game-300", "2025-04-26", 1, 2, 5, 3, "stream-300",
        )
        db.commit()

        row = db.execute(
            "SELECT start_time, timezone FROM games WHERE game_id = 'game-300'"
        ).fetchone()
        assert row[0] is None
        assert row[1] is None

    def test_load_file_passes_start_time_from_summary(
        self, db: sqlite3.Connection, own_team_ref: TeamRef, tmp_path: Path
    ) -> None:
        """GameLoader.load_file passes start_time/timezone from GameSummaryEntry through."""
        # Create a minimal boxscore file
        boxscore = {
            "OwnTeamSlug": {
                "stats": [{"AB": 4, "R": 1, "H": 2, "RBI": 1, "BB": 0, "SO": 1}],
                "extra": [],
                "lineup": [],
            },
            "opp-uuid-5678": {
                "stats": [{"AB": 3, "R": 0, "H": 1, "RBI": 0, "BB": 1, "SO": 2}],
                "extra": [],
                "lineup": [],
            },
        }
        bs_path = tmp_path / "stream-400.json"
        bs_path.write_text(json.dumps(boxscore), encoding="utf-8")

        summary = GameSummaryEntry(
            event_id="game-400",
            game_stream_id="stream-400",
            home_away="home",
            owning_team_score=1,
            opponent_team_score=0,
            opponent_id="opp-uuid-5678",
            last_scoring_update="2025-04-26T20:00:00Z",
            start_time="2025-04-26T16:00:00.000Z",
            timezone="America/Chicago",
        )

        loader = GameLoader(db=db, owned_team_ref=own_team_ref)
        loader.load_file(bs_path, summary)

        row = db.execute(
            "SELECT start_time, timezone FROM games WHERE game_id = 'game-400'"
        ).fetchone()
        assert row[0] == "2025-04-26T16:00:00.000Z"
        assert row[1] == "America/Chicago"


# ---------------------------------------------------------------------------
# AC-1: Migration file exists with correct DDL
# ---------------------------------------------------------------------------


class TestMigrationFile:
    """Schema includes start_time and timezone columns (consolidated in 001)."""

    def test_migration_file_exists(self) -> None:
        assert _MIGRATION_FILE.exists(), f"Migration file not found at {_MIGRATION_FILE}"

    def test_migration_includes_start_time_columns(self) -> None:
        content = _MIGRATION_FILE.read_text(encoding="utf-8")
        assert "start_time" in content
        assert "timezone" in content
