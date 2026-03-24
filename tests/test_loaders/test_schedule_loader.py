"""Tests for src/gamechanger/loaders/schedule_loader.py.

Uses an in-memory SQLite database with the full schema applied. No real
network calls, no production DB writes.

Tests cover all acceptance criteria:
- AC-1: Scheduled games inserted with correct status, game_date, and team IDs
- AC-2: Scheduled game rows have NULL scores
- AC-3: Idempotent -- re-running does not create duplicates
- AC-4: Scheduled-to-completed upgrade path via GameLoader upsert
- AC-5: Opponent resolution via opponent_links and stub team creation
- AC-6: team_opponents junction row created with first_seen_year
- AC-8: Canceled games and non-game events filtered out
- AC-9: Valid season_id set to config.season
- AC-10: Comprehensive verification of all above
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from src.gamechanger.loaders.schedule_loader import ScheduleLoader
from src.gamechanger.types import TeamRef

# ---------------------------------------------------------------------------
# Schema fixture
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MIGRATION_FILE = _PROJECT_ROOT / "migrations" / "001_initial_schema.sql"


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory SQLite connection with schema applied and FK enforcement on."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    conn.executescript(_MIGRATION_FILE.read_text(encoding="utf-8"))
    conn.commit()
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEASON_ID = "2025-spring-hs"
_OWN_TEAM_GC_UUID = "72bb77d8-aaaa-bbbb-cccc-111111111111"
_OWN_TEAM_DB_ID = 1

_OPP_ROOT_TEAM_ID = "bbe7a634-dddd-eeee-ffff-222222222222"
_OPP_NAME = "Kearney Mavericks 14U"

_GAME_ID_1 = "48c79654-1111-2222-3333-444444444444"
_GAME_ID_2 = "59d8a765-5555-6666-7777-888888888888"
_GAME_ID_3 = "6ae9b876-9999-0000-aaaa-bbbbbbbbbbbb"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_own_team(db: sqlite3.Connection) -> int:
    """Insert the owned team row and return its integer PK."""
    db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) "
        "VALUES ('LSB JV', 'member', ?, 1)",
        (_OWN_TEAM_GC_UUID,),
    )
    row = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_GC_UUID,)).fetchone()
    db.commit()
    return row[0]


def _make_schedule_event(
    game_id: str = _GAME_ID_1,
    event_type: str = "game",
    status: str = "scheduled",
    start_datetime: str = "2025-04-26T16:00:00.000Z",
    opponent_id: str = _OPP_ROOT_TEAM_ID,
    opponent_name: str = _OPP_NAME,
    home_away: str | None = "home",
    full_day: bool = False,
) -> dict:
    """Build a schedule.json event item."""
    if full_day:
        start_obj = {"date": start_datetime[:10]}
    else:
        start_obj = {"datetime": start_datetime}

    item: dict = {
        "event": {
            "id": game_id,
            "event_type": event_type,
            "sub_type": [],
            "status": status,
            "full_day": full_day,
            "team_id": _OWN_TEAM_GC_UUID,
            "start": start_obj,
            "end": start_obj,
            "timezone": "America/Chicago",
            "notes": None,
            "title": f"Game vs. {opponent_name}",
            "series_id": None,
        },
    }

    if event_type == "game":
        item["pregame_data"] = {
            "id": game_id,
            "game_id": game_id,
            "opponent_name": opponent_name,
            "opponent_id": opponent_id,
            "home_away": home_away,
            "lineup_id": None,
        }

    return item


def _write_schedule(tmp_path: Path, events: list[dict]) -> Path:
    """Write a schedule.json file and return its path."""
    schedule_path = tmp_path / "schedule.json"
    schedule_path.write_text(json.dumps(events), encoding="utf-8")
    return schedule_path


def _make_loader(
    db: sqlite3.Connection,
    own_team_id: int,
    season_id: str = _SEASON_ID,
) -> ScheduleLoader:
    """Create a ScheduleLoader with standard config."""
    team_ref = TeamRef(id=own_team_id, gc_uuid=_OWN_TEAM_GC_UUID)
    return ScheduleLoader(db, season_id=season_id, owned_team_ref=team_ref)


# ---------------------------------------------------------------------------
# Tests: AC-1, AC-2, AC-9 -- scheduled games inserted correctly
# ---------------------------------------------------------------------------


class TestScheduledGameInsertion:
    """AC-1, AC-2, AC-9: Scheduled games have correct status, NULL scores, valid season_id."""

    def test_insert_scheduled_game_home(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        """Scheduled game with home_away='home' sets our team as home."""
        own_id = _seed_own_team(db)
        events = [_make_schedule_event(home_away="home")]
        path = _write_schedule(tmp_path, events)

        loader = _make_loader(db, own_id)
        result = loader.load_file(path)

        assert result.loaded == 1
        assert result.errors == 0

        row = db.execute(
            "SELECT game_id, season_id, game_date, home_team_id, away_team_id, "
            "home_score, away_score, status FROM games WHERE game_id = ?",
            (_GAME_ID_1,),
        ).fetchone()

        assert row is not None
        game_id, season_id, game_date, home_tid, away_tid, home_score, away_score, status = row
        assert game_id == _GAME_ID_1
        assert season_id == _SEASON_ID  # AC-9
        assert game_date == "2025-04-26"
        assert home_tid == own_id  # AC-1: our team is home
        assert home_score is None  # AC-2
        assert away_score is None  # AC-2
        assert status == "scheduled"

    def test_insert_scheduled_game_away(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        """Scheduled game with home_away='away' sets our team as away."""
        own_id = _seed_own_team(db)
        events = [_make_schedule_event(home_away="away")]
        path = _write_schedule(tmp_path, events)

        loader = _make_loader(db, own_id)
        result = loader.load_file(path)

        assert result.loaded == 1
        row = db.execute(
            "SELECT home_team_id, away_team_id FROM games WHERE game_id = ?",
            (_GAME_ID_1,),
        ).fetchone()

        assert row is not None
        home_tid, away_tid = row
        assert away_tid == own_id  # our team is away
        assert home_tid != own_id  # opponent is home

    def test_insert_scheduled_game_null_home_away(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """AC-10e: When home_away is null, our team is home by convention."""
        own_id = _seed_own_team(db)
        events = [_make_schedule_event(home_away=None)]
        path = _write_schedule(tmp_path, events)

        loader = _make_loader(db, own_id)
        result = loader.load_file(path)

        assert result.loaded == 1
        row = db.execute(
            "SELECT home_team_id, away_team_id FROM games WHERE game_id = ?",
            (_GAME_ID_1,),
        ).fetchone()

        assert row is not None
        home_tid, away_tid = row
        assert home_tid == own_id  # our team defaulted to home

    def test_full_day_event_date_extraction(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Full-day events use start.date instead of start.datetime."""
        own_id = _seed_own_team(db)
        events = [_make_schedule_event(full_day=True, start_datetime="2025-06-15")]
        path = _write_schedule(tmp_path, events)

        loader = _make_loader(db, own_id)
        loader.load_file(path)

        row = db.execute(
            "SELECT game_date FROM games WHERE game_id = ?", (_GAME_ID_1,)
        ).fetchone()
        assert row[0] == "2025-06-15"


# ---------------------------------------------------------------------------
# Tests: AC-3 -- idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    """AC-3: Re-running the schedule loader does not create duplicates."""

    def test_rerun_does_not_duplicate(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        """Loading the same schedule twice produces exactly one game row."""
        own_id = _seed_own_team(db)
        events = [_make_schedule_event()]
        path = _write_schedule(tmp_path, events)

        loader = _make_loader(db, own_id)
        result1 = loader.load_file(path)
        result2 = loader.load_file(path)

        assert result1.loaded == 1
        assert result2.loaded == 1  # upsert counts as loaded

        count = db.execute("SELECT COUNT(*) FROM games WHERE game_id = ?", (_GAME_ID_1,)).fetchone()[0]
        assert count == 1

    def test_rerun_updates_changed_date(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        """Re-running with a changed date updates the existing row."""
        own_id = _seed_own_team(db)

        events_v1 = [_make_schedule_event(start_datetime="2025-04-26T16:00:00.000Z")]
        path = _write_schedule(tmp_path, events_v1)
        loader = _make_loader(db, own_id)
        loader.load_file(path)

        events_v2 = [_make_schedule_event(start_datetime="2025-04-27T14:00:00.000Z")]
        path = _write_schedule(tmp_path, events_v2)
        loader.load_file(path)

        row = db.execute(
            "SELECT game_date FROM games WHERE game_id = ?", (_GAME_ID_1,)
        ).fetchone()
        assert row[0] == "2025-04-27"


# ---------------------------------------------------------------------------
# Tests: AC-4 -- scheduled-to-completed upgrade
# ---------------------------------------------------------------------------


class TestScheduledToCompletedUpgrade:
    """AC-4: GameLoader upsert upgrades scheduled rows to completed."""

    def test_game_loader_upgrades_scheduled_to_completed(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """A scheduled row is upgraded to completed when GameLoader upserts."""
        own_id = _seed_own_team(db)

        # Step 1: Insert scheduled game via ScheduleLoader
        events = [_make_schedule_event()]
        path = _write_schedule(tmp_path, events)
        loader = _make_loader(db, own_id)
        loader.load_file(path)

        # Verify it's scheduled with NULL scores
        row = db.execute(
            "SELECT status, home_score, away_score FROM games WHERE game_id = ?",
            (_GAME_ID_1,),
        ).fetchone()
        assert row[0] == "scheduled"
        assert row[1] is None
        assert row[2] is None

        # Step 2: Simulate GameLoader upsert with completed status and scores.
        # Use the same upsert pattern as GameLoader._upsert_game()
        opp_team_id = db.execute(
            "SELECT away_team_id FROM games WHERE game_id = ?", (_GAME_ID_1,)
        ).fetchone()[0]

        db.execute(
            """
            INSERT INTO games
                (game_id, season_id, game_date, home_team_id, away_team_id,
                 home_score, away_score, status, game_stream_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?)
            ON CONFLICT(game_id) DO UPDATE SET
                game_date      = excluded.game_date,
                home_team_id   = excluded.home_team_id,
                away_team_id   = excluded.away_team_id,
                home_score     = excluded.home_score,
                away_score     = excluded.away_score,
                status         = excluded.status,
                game_stream_id = excluded.game_stream_id
            """,
            (_GAME_ID_1, _SEASON_ID, "2025-04-26", own_id, opp_team_id,
             5, 2, "stream-001"),
        )
        db.commit()

        # Verify upgraded to completed
        row = db.execute(
            "SELECT status, home_score, away_score, game_stream_id FROM games WHERE game_id = ?",
            (_GAME_ID_1,),
        ).fetchone()
        assert row[0] == "completed"
        assert row[1] == 5
        assert row[2] == 2
        assert row[3] == "stream-001"

    def test_schedule_loader_does_not_downgrade_completed(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Re-running schedule loader on a completed game does not downgrade it."""
        own_id = _seed_own_team(db)

        # Step 1: Insert scheduled game
        events = [_make_schedule_event()]
        path = _write_schedule(tmp_path, events)
        loader = _make_loader(db, own_id)
        loader.load_file(path)

        # Step 2: Manually mark as completed with scores
        db.execute(
            "UPDATE games SET status = 'completed', home_score = 7, away_score = 3 "
            "WHERE game_id = ?",
            (_GAME_ID_1,),
        )
        db.commit()

        # Step 3: Re-run schedule loader
        loader.load_file(path)

        # Verify still completed with scores intact
        row = db.execute(
            "SELECT status, home_score, away_score FROM games WHERE game_id = ?",
            (_GAME_ID_1,),
        ).fetchone()
        assert row[0] == "completed"
        assert row[1] == 7
        assert row[2] == 3


# ---------------------------------------------------------------------------
# Tests: AC-5 -- opponent resolution
# ---------------------------------------------------------------------------


class TestOpponentResolution:
    """AC-5: Opponent resolved via opponent_links or stub team creation."""

    def test_resolved_opponent_via_opponent_links(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """When opponent_links has resolved_team_id, use it."""
        own_id = _seed_own_team(db)

        # Create a resolved opponent team
        db.execute(
            "INSERT INTO teams (name, membership_type, gc_uuid, is_active) "
            "VALUES (?, 'tracked', 'opp-gc-uuid', 1)",
            (_OPP_NAME,),
        )
        resolved_opp_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Create opponent_links row with resolved_team_id
        db.execute(
            "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, resolved_team_id) "
            "VALUES (?, ?, ?, ?)",
            (own_id, _OPP_ROOT_TEAM_ID, _OPP_NAME, resolved_opp_id),
        )
        db.commit()

        events = [_make_schedule_event()]
        path = _write_schedule(tmp_path, events)
        loader = _make_loader(db, own_id)
        loader.load_file(path)

        row = db.execute(
            "SELECT away_team_id FROM games WHERE game_id = ?", (_GAME_ID_1,)
        ).fetchone()
        assert row[0] == resolved_opp_id

    def test_unresolved_opponent_creates_stub(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """When opponent_links has no resolved_team_id, a stub team is created."""
        own_id = _seed_own_team(db)

        # opponent_links row with NULL resolved_team_id
        db.execute(
            "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name) "
            "VALUES (?, ?, ?)",
            (own_id, _OPP_ROOT_TEAM_ID, _OPP_NAME),
        )
        db.commit()

        events = [_make_schedule_event()]
        path = _write_schedule(tmp_path, events)
        loader = _make_loader(db, own_id)
        loader.load_file(path)

        # A stub team should exist
        row = db.execute(
            "SELECT id, name, membership_type, source FROM teams WHERE name = ?",
            (_OPP_NAME,),
        ).fetchone()
        assert row is not None
        assert row[2] == "tracked"
        assert row[3] == "schedule"

    def test_no_opponent_links_creates_stub(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """When no opponent_links row exists, a stub team is created by name."""
        own_id = _seed_own_team(db)
        events = [_make_schedule_event()]
        path = _write_schedule(tmp_path, events)

        loader = _make_loader(db, own_id)
        loader.load_file(path)

        row = db.execute(
            "SELECT id, name, source FROM teams WHERE name = ?", (_OPP_NAME,)
        ).fetchone()
        assert row is not None
        assert row[2] == "schedule"

    def test_existing_stub_team_reused(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """When a stub team already exists by name, it is reused (not duplicated)."""
        own_id = _seed_own_team(db)

        # Pre-create stub team
        db.execute(
            "INSERT INTO teams (name, membership_type, source, is_active) "
            "VALUES (?, 'tracked', 'schedule', 0)",
            (_OPP_NAME,),
        )
        existing_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.commit()

        events = [_make_schedule_event()]
        path = _write_schedule(tmp_path, events)
        loader = _make_loader(db, own_id)
        loader.load_file(path)

        # Should use existing team, not create a new one
        count = db.execute(
            "SELECT COUNT(*) FROM teams WHERE name = ?", (_OPP_NAME,)
        ).fetchone()[0]
        assert count == 1

        row = db.execute(
            "SELECT away_team_id FROM games WHERE game_id = ?", (_GAME_ID_1,)
        ).fetchone()
        assert row[0] == existing_id


# ---------------------------------------------------------------------------
# Tests: AC-6 -- team_opponents junction
# ---------------------------------------------------------------------------


class TestTeamOpponentsJunction:
    """AC-6: team_opponents row created with first_seen_year."""

    def test_team_opponents_row_created(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Loading a scheduled game creates a team_opponents junction row."""
        own_id = _seed_own_team(db)
        events = [_make_schedule_event()]
        path = _write_schedule(tmp_path, events)

        loader = _make_loader(db, own_id)
        loader.load_file(path)

        row = db.execute(
            "SELECT our_team_id, opponent_team_id, first_seen_year "
            "FROM team_opponents WHERE our_team_id = ?",
            (own_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == own_id
        assert row[2] == 2025  # derived from season_id "2025-spring-hs"

    def test_team_opponents_idempotent(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Re-running does not duplicate team_opponents rows (ON CONFLICT DO NOTHING)."""
        own_id = _seed_own_team(db)
        events = [_make_schedule_event()]
        path = _write_schedule(tmp_path, events)

        loader = _make_loader(db, own_id)
        loader.load_file(path)
        loader.load_file(path)

        count = db.execute(
            "SELECT COUNT(*) FROM team_opponents WHERE our_team_id = ?",
            (own_id,),
        ).fetchone()[0]
        assert count == 1

    def test_multiple_opponents_create_multiple_junction_rows(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Different opponents each get their own team_opponents row."""
        own_id = _seed_own_team(db)
        opp2_id = "ccabcdef-abcd-abcd-abcd-abcdefabcdef"
        events = [
            _make_schedule_event(game_id=_GAME_ID_1, opponent_id=_OPP_ROOT_TEAM_ID, opponent_name="Team A"),
            _make_schedule_event(game_id=_GAME_ID_2, opponent_id=opp2_id, opponent_name="Team B"),
        ]
        path = _write_schedule(tmp_path, events)

        loader = _make_loader(db, own_id)
        loader.load_file(path)

        count = db.execute(
            "SELECT COUNT(*) FROM team_opponents WHERE our_team_id = ?",
            (own_id,),
        ).fetchone()[0]
        assert count == 2


# ---------------------------------------------------------------------------
# Tests: AC-8 -- filtering canceled/non-game events
# ---------------------------------------------------------------------------


class TestEventFiltering:
    """AC-8: Canceled games and non-game events are excluded."""

    def test_practice_events_filtered(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        """Practice events are not inserted into the games table."""
        own_id = _seed_own_team(db)
        events = [
            _make_schedule_event(game_id=_GAME_ID_1, event_type="practice"),
        ]
        path = _write_schedule(tmp_path, events)

        loader = _make_loader(db, own_id)
        result = loader.load_file(path)

        assert result.loaded == 0
        count = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        assert count == 0

    def test_other_events_filtered(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        """Other events are not inserted into the games table."""
        own_id = _seed_own_team(db)
        events = [
            _make_schedule_event(game_id=_GAME_ID_1, event_type="other"),
        ]
        path = _write_schedule(tmp_path, events)

        loader = _make_loader(db, own_id)
        result = loader.load_file(path)

        assert result.loaded == 0

    def test_canceled_games_filtered(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        """Canceled game events are not inserted."""
        own_id = _seed_own_team(db)
        events = [
            _make_schedule_event(game_id=_GAME_ID_1, status="canceled"),
        ]
        path = _write_schedule(tmp_path, events)

        loader = _make_loader(db, own_id)
        result = loader.load_file(path)

        assert result.loaded == 0
        count = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        assert count == 0

    def test_mixed_events_only_loads_valid_games(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Only scheduled game events are loaded from a mixed event list."""
        own_id = _seed_own_team(db)
        events = [
            _make_schedule_event(game_id=_GAME_ID_1, event_type="game", status="scheduled"),
            _make_schedule_event(game_id=_GAME_ID_2, event_type="practice"),
            _make_schedule_event(game_id=_GAME_ID_3, event_type="game", status="canceled"),
        ]
        path = _write_schedule(tmp_path, events)

        loader = _make_loader(db, own_id)
        result = loader.load_file(path)

        assert result.loaded == 1
        count = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        assert count == 1

        # Only the valid game should be in the DB
        row = db.execute("SELECT game_id FROM games").fetchone()
        assert row[0] == _GAME_ID_1


# ---------------------------------------------------------------------------
# Tests: AC-10 -- multi-scope verification
# ---------------------------------------------------------------------------


class TestMultiScope:
    """AC-10: Multi-scope tests verifying correct behavior across seasons."""

    def test_two_seasons_scoped_correctly(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Games from different seasons get the correct season_id."""
        own_id = _seed_own_team(db)

        # Season 1
        events_s1 = [_make_schedule_event(game_id=_GAME_ID_1)]
        s1_dir = tmp_path / "s1"
        s1_dir.mkdir()
        path_s1 = s1_dir / "schedule.json"
        path_s1.write_text(json.dumps(events_s1), encoding="utf-8")

        loader_s1 = _make_loader(db, own_id, season_id="2025-spring-hs")
        loader_s1.load_file(path_s1)

        # Season 2
        events_s2 = [_make_schedule_event(game_id=_GAME_ID_2)]
        s2_dir = tmp_path / "s2"
        s2_dir.mkdir()
        path_s2 = s2_dir / "schedule.json"
        path_s2.write_text(json.dumps(events_s2), encoding="utf-8")

        loader_s2 = _make_loader(db, own_id, season_id="2026-spring-hs")
        loader_s2.load_file(path_s2)

        row1 = db.execute(
            "SELECT season_id FROM games WHERE game_id = ?", (_GAME_ID_1,)
        ).fetchone()
        row2 = db.execute(
            "SELECT season_id FROM games WHERE game_id = ?", (_GAME_ID_2,)
        ).fetchone()

        assert row1[0] == "2025-spring-hs"
        assert row2[0] == "2026-spring-hs"


# ---------------------------------------------------------------------------
# Tests: Edge cases and error handling
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases: missing files, malformed data, empty schedules."""

    def test_missing_schedule_file(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        """Missing schedule.json returns empty LoadResult."""
        own_id = _seed_own_team(db)
        loader = _make_loader(db, own_id)
        result = loader.load_file(tmp_path / "nonexistent.json")

        assert result.loaded == 0
        assert result.errors == 0
        assert result.skipped == 0

    def test_malformed_json(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        """Malformed JSON returns error LoadResult."""
        own_id = _seed_own_team(db)
        path = tmp_path / "schedule.json"
        path.write_text("not valid json{{{", encoding="utf-8")

        loader = _make_loader(db, own_id)
        result = loader.load_file(path)

        assert result.errors == 1

    def test_empty_schedule(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        """Empty schedule array produces zero loaded."""
        own_id = _seed_own_team(db)
        path = _write_schedule(tmp_path, [])

        loader = _make_loader(db, own_id)
        result = loader.load_file(path)

        assert result.loaded == 0
        assert result.errors == 0

    def test_game_event_without_pregame_data_skipped(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """A game event without pregame_data is skipped with a warning."""
        own_id = _seed_own_team(db)
        events = [{
            "event": {
                "id": _GAME_ID_1,
                "event_type": "game",
                "status": "scheduled",
                "start": {"datetime": "2025-04-26T16:00:00.000Z"},
            },
            # No pregame_data
        }]
        path = _write_schedule(tmp_path, events)

        loader = _make_loader(db, own_id)
        result = loader.load_file(path)

        assert result.loaded == 0
        assert result.skipped == 1
