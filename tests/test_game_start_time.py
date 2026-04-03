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
from src.gamechanger.loaders.schedule_loader import ScheduleLoader
from src.gamechanger.loaders.scouting_loader import ScoutingLoader
from src.gamechanger.types import TeamRef


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _create_schema(db: sqlite3.Connection) -> None:
    """Create the minimal schema needed for game loader tests."""
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS programs (
            program_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            program_type TEXT
        );
        CREATE TABLE IF NOT EXISTS seasons (
            season_id TEXT PRIMARY KEY,
            name TEXT,
            season_type TEXT,
            year INTEGER
        );
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gc_uuid TEXT UNIQUE,
            public_id TEXT UNIQUE,
            membership_type TEXT DEFAULT 'tracked',
            is_active INTEGER DEFAULT 1,
            season_year INTEGER,
            program_id TEXT REFERENCES programs(program_id),
            classification TEXT
        );
        CREATE TABLE IF NOT EXISTS games (
            game_id TEXT PRIMARY KEY,
            season_id TEXT REFERENCES seasons(season_id),
            game_date TEXT,
            home_team_id INTEGER REFERENCES teams(id),
            away_team_id INTEGER REFERENCES teams(id),
            home_score INTEGER,
            away_score INTEGER,
            status TEXT,
            game_stream_id TEXT,
            start_time TEXT,
            timezone TEXT
        );
        CREATE TABLE IF NOT EXISTS players (
            player_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT
        );
        CREATE TABLE IF NOT EXISTS team_rosters (
            team_id INTEGER REFERENCES teams(id),
            player_id TEXT REFERENCES players(player_id),
            season_id TEXT,
            jersey_number TEXT,
            PRIMARY KEY (team_id, player_id, season_id)
        );
        CREATE TABLE IF NOT EXISTS player_game_batting (
            player_id TEXT,
            game_id TEXT,
            team_id INTEGER,
            ab INTEGER, r INTEGER, h INTEGER, rbi INTEGER, bb INTEGER, so INTEGER,
            doubles INTEGER, triples INTEGER, hr INTEGER, sb INTEGER, tb INTEGER,
            hbp INTEGER, cs INTEGER, shf INTEGER, e INTEGER,
            batting_order INTEGER, positions_played TEXT, is_primary INTEGER,
            PRIMARY KEY (player_id, game_id, team_id)
        );
        CREATE TABLE IF NOT EXISTS player_game_pitching (
            player_id TEXT,
            game_id TEXT,
            team_id INTEGER,
            ip_outs INTEGER, h INTEGER, r INTEGER, er INTEGER, bb INTEGER,
            so INTEGER, wp INTEGER, hbp INTEGER, pitches INTEGER,
            total_strikes INTEGER, bf INTEGER,
            PRIMARY KEY (player_id, game_id, team_id)
        );
        CREATE TABLE IF NOT EXISTS player_season_batting (
            player_id TEXT,
            team_id INTEGER,
            season_id TEXT,
            gp INTEGER, games_tracked INTEGER, ab INTEGER, h INTEGER,
            doubles INTEGER, triples INTEGER, hr INTEGER, rbi INTEGER,
            r INTEGER, bb INTEGER, so INTEGER, sb INTEGER,
            tb INTEGER, hbp INTEGER, shf INTEGER, cs INTEGER,
            PRIMARY KEY (player_id, team_id, season_id)
        );
        CREATE TABLE IF NOT EXISTS player_season_pitching (
            player_id TEXT,
            team_id INTEGER,
            season_id TEXT,
            gp_pitcher INTEGER, games_tracked INTEGER, ip_outs INTEGER,
            h INTEGER, r INTEGER, er INTEGER, bb INTEGER, so INTEGER,
            wp INTEGER, hbp INTEGER, pitches INTEGER, total_strikes INTEGER,
            bf INTEGER,
            PRIMARY KEY (player_id, team_id, season_id)
        );
        CREATE TABLE IF NOT EXISTS team_opponents (
            our_team_id INTEGER REFERENCES teams(id),
            opponent_team_id INTEGER REFERENCES teams(id),
            first_seen_year INTEGER,
            is_hidden INTEGER DEFAULT 0,
            PRIMARY KEY (our_team_id, opponent_team_id)
        );
        CREATE TABLE IF NOT EXISTS opponent_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            our_team_id INTEGER,
            root_team_id TEXT,
            resolved_team_id INTEGER,
            UNIQUE(our_team_id, root_team_id)
        );
        CREATE TABLE IF NOT EXISTS scouting_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season_id TEXT,
            run_type TEXT,
            status TEXT,
            started_at TEXT,
            completed_at TEXT,
            games_loaded INTEGER,
            errors INTEGER
        );

        INSERT INTO seasons (season_id, year) VALUES ('2025-spring-hs', 2025);
        INSERT INTO programs (program_id, name, program_type) VALUES ('lsb-hs', 'LSB HS', 'hs');
        INSERT INTO teams (id, name, gc_uuid, public_id, membership_type, season_year, program_id)
            VALUES (1, 'Own Team', 'own-uuid-1234', 'OwnTeamSlug', 'member', 2025, 'lsb-hs');
        INSERT INTO teams (id, name, gc_uuid, public_id, membership_type, season_year)
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
# AC-2: Schedule loader extracts start_time and timezone
# ---------------------------------------------------------------------------


class TestScheduleLoaderStartTime:
    """Schedule loader writes start_time and timezone from event.start.datetime."""

    def _make_schedule_json(self, tmp_path: Path, events: list[dict]) -> Path:
        path = tmp_path / "schedule.json"
        path.write_text(json.dumps(events), encoding="utf-8")
        return path

    def _make_event(
        self,
        event_id: str = "evt-001",
        datetime_val: str = "2025-04-26T16:00:00.000Z",
        timezone: str = "America/Chicago",
        full_day: bool = False,
        opponent_id: str = "opp-root-1",
        opponent_name: str = "Opponent Team",
        home_away: str = "home",
    ) -> dict:
        start = {}
        if full_day:
            start["date"] = datetime_val[:10]
        else:
            start["datetime"] = datetime_val
        return {
            "event": {
                "id": event_id,
                "event_type": "game",
                "status": "scheduled",
                "start": start,
                "full_day": full_day,
                "timezone": timezone,
            },
            "pregame_data": {
                "opponent_id": opponent_id,
                "opponent_name": opponent_name,
                "home_away": home_away,
            },
        }

    def test_insert_writes_start_time_and_timezone(
        self, db: sqlite3.Connection, own_team_ref: TeamRef, tmp_path: Path
    ) -> None:
        events = [self._make_event()]
        path = self._make_schedule_json(tmp_path, events)

        loader = ScheduleLoader(db, owned_team_ref=own_team_ref)
        result = loader.load_file(path)

        assert result.loaded == 1
        row = db.execute(
            "SELECT start_time, timezone FROM games WHERE game_id = 'evt-001'"
        ).fetchone()
        assert row is not None
        assert row[0] == "2025-04-26T16:00:00.000Z"
        assert row[1] == "America/Chicago"

    def test_update_overwrites_start_time_and_timezone(
        self, db: sqlite3.Connection, own_team_ref: TeamRef, tmp_path: Path
    ) -> None:
        """Updating with new values overwrites existing ones."""
        # Insert initial game
        events = [self._make_event()]
        path = self._make_schedule_json(tmp_path, events)
        loader = ScheduleLoader(db, owned_team_ref=own_team_ref)
        loader.load_file(path)

        # Update with new start time
        events2 = [
            self._make_event(
                datetime_val="2025-04-26T18:00:00.000Z",
                timezone="America/Denver",
            )
        ]
        path2 = self._make_schedule_json(tmp_path, events2)
        loader.load_file(path2)

        row = db.execute(
            "SELECT start_time, timezone FROM games WHERE game_id = 'evt-001'"
        ).fetchone()
        assert row[0] == "2025-04-26T18:00:00.000Z"
        assert row[1] == "America/Denver"

    def test_full_day_event_has_null_start_time(
        self, db: sqlite3.Connection, own_team_ref: TeamRef, tmp_path: Path
    ) -> None:
        """Full-day events have start.date but no start.datetime -- start_time is NULL."""
        events = [
            self._make_event(
                datetime_val="2025-04-26",
                full_day=True,
            )
        ]
        path = self._make_schedule_json(tmp_path, events)

        loader = ScheduleLoader(db, owned_team_ref=own_team_ref)
        result = loader.load_file(path)

        assert result.loaded == 1
        row = db.execute(
            "SELECT start_time, timezone FROM games WHERE game_id = 'evt-001'"
        ).fetchone()
        # full_day events have start.date but not start.datetime
        assert row[0] is None
        # timezone is still set from event.timezone
        assert row[1] == "America/Chicago"

    def test_full_day_event_with_null_timezone(
        self, db: sqlite3.Connection, own_team_ref: TeamRef, tmp_path: Path
    ) -> None:
        """Full-day events in production have timezone=null -- both fields NULL."""
        events = [
            self._make_event(
                event_id="evt-002",
                datetime_val="2025-04-26",
                timezone=None,
                full_day=True,
            )
        ]
        path = self._make_schedule_json(tmp_path, events)

        loader = ScheduleLoader(db, owned_team_ref=own_team_ref)
        result = loader.load_file(path)

        assert result.loaded == 1
        row = db.execute(
            "SELECT start_time, timezone FROM games WHERE game_id = 'evt-002'"
        ).fetchone()
        assert row[0] is None
        assert row[1] is None

    def test_timed_to_full_day_overwrites_start_time(
        self, db: sqlite3.Connection, own_team_ref: TeamRef, tmp_path: Path
    ) -> None:
        """Schedule loader is authoritative: timed→full-day overwrites start_time with NULL."""
        # First load with start_time
        events = [self._make_event()]
        path = self._make_schedule_json(tmp_path, events)
        loader = ScheduleLoader(db, owned_team_ref=own_team_ref)
        loader.load_file(path)

        # Second load as full_day (no start_time) -- should overwrite
        events2 = [self._make_event(datetime_val="2025-04-26", full_day=True)]
        path2 = self._make_schedule_json(tmp_path, events2)
        loader.load_file(path2)

        row = db.execute(
            "SELECT start_time, timezone FROM games WHERE game_id = 'evt-001'"
        ).fetchone()
        # Schedule endpoint is authoritative -- NULL overwrites previous value
        assert row[0] is None
        # timezone is overwritten with the new value (still America/Chicago from event.timezone)
        assert row[1] == "America/Chicago"


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
            VALUES ('game-100', '2025-spring-hs', '2025-04-26', 1, 2,
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
            VALUES ('game-200', '2025-spring-hs', '2025-04-26', 1, 2,
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
    """Migration 014 adds start_time and timezone columns."""

    def test_migration_file_exists(self) -> None:
        migration = Path(__file__).resolve().parents[1] / "migrations" / "014_add_game_start_time.sql"
        assert migration.exists(), f"Migration file not found at {migration}"

    def test_migration_adds_columns(self) -> None:
        migration = Path(__file__).resolve().parents[1] / "migrations" / "014_add_game_start_time.sql"
        content = migration.read_text(encoding="utf-8")
        assert "start_time" in content
        assert "timezone" in content
        assert "ALTER TABLE games" in content
