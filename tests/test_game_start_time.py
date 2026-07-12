"""Tests for start_time and timezone column support across all game loaders.

Covers:
- AC-1: Migration adds start_time and timezone columns.
- AC-2: Schedule loader writes start_time and timezone on INSERT and UPDATE.
- AC-3: Scouting loader passes start_time and timezone via GameSummaryEntry.
- AC-4: Game loader preserves existing start_time/timezone when upserting with NULLs.
- AC-5: Comprehensive test coverage for all three loaders.
"""

from __future__ import annotations

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
# E-250-02: migration 008 drops seasons.season_type, team_opponents, and
# players.gc_athlete_profile_id -- apply it so the schema matches the fixtures.
_MIGRATION_008 = (
    _PROJECT_ROOT / "migrations" / "008_drop_identity_opponent_season_type.sql"
)


def _create_schema(db: sqlite3.Connection) -> None:
    """Create the full schema from the migration file and seed test data."""
    db.executescript(_MIGRATION_FILE.read_text(encoding="utf-8"))
    db.executescript(_MIGRATION_008.read_text(encoding="utf-8"))
    db.executescript(
        """
        INSERT OR IGNORE INTO seasons (season_id, name, year) VALUES ('2025', 'Spring 2025', 2025);
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
    """Scouting loader passes start_time/timezone from the crawled games list
    through GameSummaryEntry."""

    def test_games_index_populates_start_time_fields(
        self, db: sqlite3.Connection
    ) -> None:
        """_build_games_index_from_data creates entries with start_time and timezone."""
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

        index = loader._build_games_index_from_data(games_data)
        entry = index["game-001"]
        assert entry.start_time == "2025-04-26T16:00:00.000Z"
        assert entry.timezone == "America/Chicago"

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

        index = loader._build_games_index_from_data(games_data)
        entry = index["game-002"]
        assert entry.start_time is None
        assert entry.timezone is None


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

    def test_load_payload_passes_start_time_from_summary(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """GameLoader.load_payload passes start_time/timezone from GameSummaryEntry through."""
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
        loader.load_payload(boxscore, summary)

        row = db.execute(
            "SELECT start_time, timezone FROM games WHERE game_id = 'game-400'"
        ).fetchone()
        assert row[0] == "2025-04-26T16:00:00.000Z"
        assert row[1] == "America/Chicago"


# ---------------------------------------------------------------------------
# E-253-04: game_date is the venue-LOCAL calendar date of the scoring instant
# ---------------------------------------------------------------------------


def _load_summary(
    db: sqlite3.Connection,
    own_team_ref: TeamRef,
    *,
    game_id: str,
    stream_id: str,
    last_scoring_update: str,
    timezone: str | None,
) -> str:
    """Load a minimal boxscore for one summary and return the stored game_date."""
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
    summary = GameSummaryEntry(
        event_id=game_id,
        game_stream_id=stream_id,
        home_away="home",
        owning_team_score=1,
        opponent_team_score=0,
        opponent_id="opp-uuid-5678",
        last_scoring_update=last_scoring_update,
        start_time=last_scoring_update,
        timezone=timezone,
    )
    GameLoader(db=db, owned_team_ref=own_team_ref).load_payload(boxscore, summary)
    db.commit()
    row = db.execute(
        "SELECT game_date FROM games WHERE game_id = ?", (game_id,)
    ).fetchone()
    return row[0]


class TestGameDateLocalDerivation:
    """E-253-04: an evening game must file under the venue-local date, not the
    next UTC day (the old ``last_scoring_update[:10]`` slice)."""

    def test_evening_game_uses_local_date_not_next_utc_day(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """AC-2: 2026-06-21T03:00Z == 2026-06-20 22:00 America/Chicago (CDT).

        The UTC prefix is ``2026-06-21``; the correct local date is
        ``2026-06-20``.
        """
        game_date = _load_summary(
            db, own_team_ref,
            game_id="game-eve", stream_id="stream-eve",
            last_scoring_update="2026-06-21T03:00:00.000Z",
            timezone="America/Chicago",
        )
        assert game_date == "2026-06-20", (
            "evening game must file under the local calendar date, not the "
            "next UTC day"
        )

    def test_missing_timezone_falls_back_to_operating_seam(
        self, db: sqlite3.Connection, own_team_ref: TeamRef,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-3: no game timezone -> operating-tz seam (default America/Chicago).

        The seam returns a ZoneInfo; the loader bridges it to the IANA name via
        ``.key`` before calling ``derive_local_date`` (never passes the object).
        With no OPERATING_TIMEZONE set the default (America/Chicago) applies, so
        the same evening instant still resolves to the prior local day.
        """
        monkeypatch.delenv("OPERATING_TIMEZONE", raising=False)
        game_date = _load_summary(
            db, own_team_ref,
            game_id="game-noz", stream_id="stream-noz",
            last_scoring_update="2026-06-21T03:00:00.000Z",
            timezone=None,
        )
        assert game_date == "2026-06-20"

    def test_operating_timezone_env_override_applies_on_fallback(
        self, db: sqlite3.Connection, own_team_ref: TeamRef,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-3: the fallback honors an OPERATING_TIMEZONE override (proves the
        seam is consulted, not a hard-coded default). 2026-06-21T04:30Z falls
        between NY midnight (04:00Z, EDT UTC-4) and Chicago midnight (05:00Z,
        CDT UTC-5): NY has already rolled to 2026-06-21 while Chicago is still
        2026-06-20. Under the NY override the date must be 2026-06-21.
        """
        monkeypatch.setenv("OPERATING_TIMEZONE", "America/New_York")
        game_date = _load_summary(
            db, own_team_ref,
            game_id="game-ny", stream_id="stream-ny",
            last_scoring_update="2026-06-21T04:30:00.000Z",
            timezone=None,
        )
        assert game_date == "2026-06-21"

    def test_absent_instant_falls_back_to_sentinel(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """An empty last_scoring_update preserves the '1900-01-01' sentinel."""
        game_date = _load_summary(
            db, own_team_ref,
            game_id="game-none", stream_id="stream-none",
            last_scoring_update="",
            timezone="America/Chicago",
        )
        assert game_date == "1900-01-01"


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
