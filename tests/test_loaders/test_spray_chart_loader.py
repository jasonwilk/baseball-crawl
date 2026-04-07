"""Tests for src/gamechanger/loaders/spray_chart_loader.py.

Uses an in-memory SQLite database with the real schema applied.
No network calls are made.

Tests cover:
- AC-1: SprayChartLoader constructor takes db connection
- AC-2: offense section → chart_type='offensive'; defense section → 'defensive'
- AC-3: columns stored correctly (game_id, player_id, team_id, chart_type, etc.)
- AC-3a: game_id from filename, NOT stream_id
- AC-3b: team_id resolved via team_rosters; fallback to opponent for unknown player
- AC-3c: season_id from path segment
- AC-4: INSERT OR IGNORE idempotency -- second run = 0 new rows (AC-9)
- AC-5: null spray_chart_data skipped; missing section skipped; no-location skipped;
        empty defenders[] stored with NULL x/y/position/error (TN-4, AC-9)
- AC-6: unknown player gets stub row + WARNING log (AC-9)
- AC-7: accurate LoadResult loaded/skipped/errors counts (AC-9)
- AC-8: _run_spray_chart_loader helper registered in pipeline
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

import pytest

from src.gamechanger.loaders import LoadResult
from src.gamechanger.loaders.spray_chart_loader import SprayChartLoader


# ---------------------------------------------------------------------------
# Schema fixture
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MIGRATION_001 = _PROJECT_ROOT / "migrations" / "001_initial_schema.sql"
_MIGRATION_006 = _PROJECT_ROOT / "migrations" / "006_spray_charts_indexes.sql"


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory SQLite with real schema (001 + 006) and FK enforcement on."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    conn.executescript(_MIGRATION_001.read_text(encoding="utf-8"))
    conn.execute("ALTER TABLE teams ADD COLUMN season_year INTEGER")
    conn.executescript(_MIGRATION_006.read_text(encoding="utf-8"))
    conn.commit()
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

_OWN_GC_UUID = "own-team-uuid-001"
_OPP_GC_UUID = "opp-team-uuid-002"
# DB season_id is derived from team metadata (season_year=2026, no program).
_SEASON_ID = "2026"
_GAME_ID = "event-game-001"
_PLAYER_A = "player-aaa-001"
_PLAYER_B = "player-bbb-002"
_PLAYER_UNKNOWN = "player-unknown-999"
_EVENT_ID_1 = "event-gc-uuid-11111111"
_EVENT_ID_2 = "event-gc-uuid-22222222"


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed_team(
    conn: sqlite3.Connection,
    gc_uuid: str,
    name: str = "Test Team",
    membership_type: str = "member",
    season_year: int = 2026,
) -> int:
    cur = conn.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, season_year) VALUES (?, ?, ?, ?)",
        (name, membership_type, gc_uuid, season_year),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def _seed_season(
    conn: sqlite3.Connection, season_id: str = _SEASON_ID, year: int = 2026
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES (?, ?, 'default', ?)",
        (season_id, f"Season {season_id}", year),
    )
    conn.commit()


def _seed_game(
    conn: sqlite3.Connection,
    game_id: str,
    home_team_id: int,
    away_team_id: int,
    season_id: str = _SEASON_ID,
) -> None:
    conn.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id) "
        "VALUES (?, ?, '2026-04-01', ?, ?)",
        (game_id, season_id, home_team_id, away_team_id),
    )
    conn.commit()


def _seed_player(
    conn: sqlite3.Connection,
    player_id: str,
    first: str = "Jake",
    last: str = "Smith",
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (player_id, first, last),
    )
    conn.commit()


def _seed_roster(
    conn: sqlite3.Connection,
    team_id: int,
    player_id: str,
    season_id: str = _SEASON_ID,
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id) VALUES (?, ?, ?)",
        (team_id, player_id, season_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Spray data helpers
# ---------------------------------------------------------------------------

def _make_event(
    event_id: str,
    play_result: str = "single",
    play_type: str = "ground_ball",
    x: float = 100.0,
    y: float = 80.0,
    position: str = "SS",
    error: bool = False,
    created_at: int = 1_700_000_000_000,
) -> dict:
    return {
        "id": event_id,
        "createdAt": created_at,
        "attributes": {
            "playResult": play_result,
            "playType": play_type,
            "defenders": [
                {
                    "error": error,
                    "position": position,
                    "location": {"x": x, "y": y},
                }
            ],
        },
    }


def _make_event_empty_defenders(
    event_id: str,
    play_result: str = "home_run",
    play_type: str = "fly_ball",
    created_at: int = 1_700_000_001_000,
) -> dict:
    """Spray event with empty defenders[] -- over-the-fence HR (TN-4)."""
    return {
        "id": event_id,
        "createdAt": created_at,
        "attributes": {
            "playResult": play_result,
            "playType": play_type,
            "defenders": [],
        },
    }


def _write_spray_file(
    tmp_path: Path,
    season_id: str,
    gc_uuid: str,
    game_id: str,
    data: dict,
) -> Path:
    """Write spray JSON and return the spray/ directory path."""
    spray_dir = tmp_path / season_id / "teams" / gc_uuid / "spray"
    spray_dir.mkdir(parents=True, exist_ok=True)
    (spray_dir / f"{game_id}.json").write_text(json.dumps(data), encoding="utf-8")
    return spray_dir


# ---------------------------------------------------------------------------
# Standard prerequisite setup
# ---------------------------------------------------------------------------

def _setup_game(
    conn: sqlite3.Connection,
    own_gc_uuid: str = _OWN_GC_UUID,
    opp_gc_uuid: str = _OPP_GC_UUID,
    game_id: str = _GAME_ID,
    season_id: str = _SEASON_ID,
) -> tuple[int, int]:
    """Insert teams, season, and game. Returns (own_team_id, opp_team_id)."""
    own_id = _seed_team(conn, own_gc_uuid, name="Own Team", membership_type="member")
    opp_id = _seed_team(conn, opp_gc_uuid, name="Opp Team", membership_type="tracked")
    _seed_season(conn, season_id)
    _seed_game(conn, game_id, home_team_id=own_id, away_team_id=opp_id, season_id=season_id)
    return own_id, opp_id


# ---------------------------------------------------------------------------
# AC-1: Constructor
# ---------------------------------------------------------------------------

def test_constructor_accepts_db_connection(db: sqlite3.Connection) -> None:
    """SprayChartLoader can be constructed with a db connection."""
    loader = SprayChartLoader(db)
    assert loader is not None


# ---------------------------------------------------------------------------
# AC-3 / AC-3a / AC-3b / AC-3c: columns stored correctly
# ---------------------------------------------------------------------------

def test_load_dir_inserts_correct_columns(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Verify all core columns are stored correctly from a spray event."""
    own_id, opp_id = _setup_game(db)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, own_id, _PLAYER_A)

    event = _make_event(_EVENT_ID_1, play_result="single", play_type="hard_ground_ball",
                        x=129.06, y=79.08, position="CF", error=False, created_at=9999)
    data = {"spray_chart_data": {"offense": {_PLAYER_A: [event]}, "defense": {}}}
    spray_dir = _write_spray_file(tmp_path, _SEASON_ID, _OWN_GC_UUID, _GAME_ID, data)

    SprayChartLoader(db).load_dir(spray_dir)

    row = db.execute("SELECT * FROM spray_charts WHERE event_gc_id = ?", (_EVENT_ID_1,)).fetchone()
    assert row is not None
    cols = [d[0] for d in db.execute("SELECT * FROM spray_charts LIMIT 0").description]
    record = dict(zip(cols, row))

    assert record["game_id"] == _GAME_ID          # AC-3a: event_id from filename
    assert record["player_id"] == _PLAYER_A
    assert record["team_id"] == own_id             # AC-3b: resolved via roster
    assert record["pitcher_id"] is None            # always NULL
    assert record["chart_type"] == "offensive"
    assert record["play_type"] == "hard_ground_ball"
    assert record["play_result"] == "single"
    assert record["x"] == pytest.approx(129.06)
    assert record["y"] == pytest.approx(79.08)
    assert record["fielder_position"] == "CF"
    assert record["error"] == 0
    assert record["event_gc_id"] == _EVENT_ID_1
    assert record["created_at_ms"] == 9999
    assert record["season_id"] == _SEASON_ID       # AC-3c: from team metadata


# ---------------------------------------------------------------------------
# AC-2: chart_type mapping
# ---------------------------------------------------------------------------

def test_offense_section_maps_to_offensive(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Events in 'offense' section get chart_type='offensive'."""
    own_id, _opp_id = _setup_game(db)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, own_id, _PLAYER_A)

    data = {"spray_chart_data": {"offense": {_PLAYER_A: [_make_event(_EVENT_ID_1)]}, "defense": {}}}
    spray_dir = _write_spray_file(tmp_path, _SEASON_ID, _OWN_GC_UUID, _GAME_ID, data)

    SprayChartLoader(db).load_dir(spray_dir)

    row = db.execute(
        "SELECT chart_type FROM spray_charts WHERE event_gc_id = ?", (_EVENT_ID_1,)
    ).fetchone()
    assert row is not None
    assert row[0] == "offensive"


def test_defense_section_maps_to_defensive(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Events in 'defense' section get chart_type='defensive'."""
    own_id, _opp_id = _setup_game(db)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, own_id, _PLAYER_A)

    data = {"spray_chart_data": {"offense": {}, "defense": {_PLAYER_A: [_make_event(_EVENT_ID_1)]}}}
    spray_dir = _write_spray_file(tmp_path, _SEASON_ID, _OWN_GC_UUID, _GAME_ID, data)

    SprayChartLoader(db).load_dir(spray_dir)

    row = db.execute(
        "SELECT chart_type FROM spray_charts WHERE event_gc_id = ?", (_EVENT_ID_1,)
    ).fetchone()
    assert row is not None
    assert row[0] == "defensive"


# ---------------------------------------------------------------------------
# AC-4 / AC-9: Idempotent re-ingestion
# ---------------------------------------------------------------------------

def test_second_run_inserts_zero_new_rows(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Loading same files twice: first run inserts, second run = 0 new rows."""
    own_id, _opp_id = _setup_game(db)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, own_id, _PLAYER_A)

    data = {"spray_chart_data": {"offense": {_PLAYER_A: [_make_event(_EVENT_ID_1)]}, "defense": {}}}
    spray_dir = _write_spray_file(tmp_path, _SEASON_ID, _OWN_GC_UUID, _GAME_ID, data)

    loader = SprayChartLoader(db)
    result1 = loader.load_dir(spray_dir)
    result2 = loader.load_dir(spray_dir)

    assert result1.loaded == 1
    assert result1.skipped == 0
    assert result2.loaded == 0
    assert result2.skipped == 1

    # Only one row in the DB.
    count = db.execute("SELECT COUNT(*) FROM spray_charts").fetchone()[0]
    assert count == 1


# ---------------------------------------------------------------------------
# AC-5 / AC-9: null spray_chart_data skipped
# ---------------------------------------------------------------------------

def test_null_spray_chart_data_is_skipped(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """File where spray_chart_data is null: no rows inserted, LoadResult(0,0,0)."""
    _setup_game(db)
    data = {"spray_chart_data": None, "stream_id": "some-stream"}
    spray_dir = _write_spray_file(tmp_path, _SEASON_ID, _OWN_GC_UUID, _GAME_ID, data)

    result = SprayChartLoader(db).load_dir(spray_dir)

    assert result.loaded == 0
    assert result.skipped == 0
    assert result.errors == 0
    count = db.execute("SELECT COUNT(*) FROM spray_charts").fetchone()[0]
    assert count == 0


def test_missing_offense_section_skipped_gracefully(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """spray_chart_data with no offense/defense keys produces empty result."""
    _setup_game(db)
    data = {"spray_chart_data": {}}
    spray_dir = _write_spray_file(tmp_path, _SEASON_ID, _OWN_GC_UUID, _GAME_ID, data)

    result = SprayChartLoader(db).load_dir(spray_dir)

    assert result.loaded == 0
    assert result.errors == 0


# ---------------------------------------------------------------------------
# AC-5: Events with no location x/y are skipped (not errored)
# ---------------------------------------------------------------------------

def test_event_with_no_location_xy_is_skipped(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Event with defender but no location.x/y is skipped gracefully."""
    own_id, _opp_id = _setup_game(db)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, own_id, _PLAYER_A)

    event = {
        "id": _EVENT_ID_1,
        "createdAt": 1234,
        "attributes": {
            "playResult": "single",
            "playType": "ground_ball",
            "defenders": [{"error": False, "position": "SS", "location": {}}],
        },
    }
    data = {"spray_chart_data": {"offense": {_PLAYER_A: [event]}, "defense": {}}}
    spray_dir = _write_spray_file(tmp_path, _SEASON_ID, _OWN_GC_UUID, _GAME_ID, data)

    result = SprayChartLoader(db).load_dir(spray_dir)

    assert result.loaded == 0
    assert result.skipped == 1
    assert result.errors == 0
    count = db.execute("SELECT COUNT(*) FROM spray_charts").fetchone()[0]
    assert count == 0


# ---------------------------------------------------------------------------
# AC-5 / AC-9: empty defenders[] stored with NULL x, y, position, error
# ---------------------------------------------------------------------------

def test_empty_defenders_stored_with_null_coordinates(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Over-the-fence HR (empty defenders[]) is stored with NULL x, y, position, error."""
    own_id, _opp_id = _setup_game(db)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, own_id, _PLAYER_A)

    event = _make_event_empty_defenders(_EVENT_ID_1, play_result="home_run")
    data = {"spray_chart_data": {"offense": {_PLAYER_A: [event]}, "defense": {}}}
    spray_dir = _write_spray_file(tmp_path, _SEASON_ID, _OWN_GC_UUID, _GAME_ID, data)

    result = SprayChartLoader(db).load_dir(spray_dir)

    assert result.loaded == 1
    assert result.errors == 0

    row = db.execute(
        "SELECT x, y, fielder_position, error, play_result FROM spray_charts WHERE event_gc_id = ?",
        (_EVENT_ID_1,),
    ).fetchone()
    assert row is not None
    x, y, fielder_position, error_val, play_result = row
    assert x is None
    assert y is None
    assert fielder_position is None
    assert error_val is None
    assert play_result == "home_run"


# ---------------------------------------------------------------------------
# AC-6 / AC-9: stub player creation for unknown player
# ---------------------------------------------------------------------------

def test_unknown_player_gets_stub_row(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Player not in players table gets a stub row before spray insert."""
    _setup_game(db)
    # Do NOT seed _PLAYER_UNKNOWN in players.

    event = _make_event(_EVENT_ID_1)
    data = {"spray_chart_data": {"offense": {_PLAYER_UNKNOWN: [event]}, "defense": {}}}
    spray_dir = _write_spray_file(tmp_path, _SEASON_ID, _OWN_GC_UUID, _GAME_ID, data)

    SprayChartLoader(db).load_dir(spray_dir)

    stub = db.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?",
        (_PLAYER_UNKNOWN,),
    ).fetchone()
    assert stub is not None
    assert stub[0] == "Unknown"
    assert stub[1] == "Unknown"


def test_unknown_player_stub_logs_warning(
    db: sqlite3.Connection, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Stub player creation logs a message with the player UUID."""
    _setup_game(db)

    event = _make_event(_EVENT_ID_1)
    data = {"spray_chart_data": {"offense": {_PLAYER_UNKNOWN: [event]}, "defense": {}}}
    spray_dir = _write_spray_file(tmp_path, _SEASON_ID, _OWN_GC_UUID, _GAME_ID, data)

    with caplog.at_level(logging.DEBUG, logger="src.db.players"):
        SprayChartLoader(db).load_dir(spray_dir)

    assert _PLAYER_UNKNOWN in caplog.text


# ---------------------------------------------------------------------------
# AC-3b: team_id resolved via team_rosters; fallback for unknown roster
# ---------------------------------------------------------------------------

def test_player_in_home_team_roster_gets_home_team_id(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Player in home team roster is assigned home team_id."""
    own_id, opp_id = _setup_game(db)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, own_id, _PLAYER_A)  # own team is home

    event = _make_event(_EVENT_ID_1)
    data = {"spray_chart_data": {"offense": {_PLAYER_A: [event]}, "defense": {}}}
    spray_dir = _write_spray_file(tmp_path, _SEASON_ID, _OWN_GC_UUID, _GAME_ID, data)

    SprayChartLoader(db).load_dir(spray_dir)

    row = db.execute(
        "SELECT team_id FROM spray_charts WHERE event_gc_id = ?", (_EVENT_ID_1,)
    ).fetchone()
    assert row is not None
    assert row[0] == own_id


def test_player_in_away_team_roster_gets_away_team_id(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Player in away team roster is assigned away team_id."""
    own_id, opp_id = _setup_game(db)
    _seed_player(db, _PLAYER_B)
    _seed_roster(db, opp_id, _PLAYER_B)  # opp team is away

    event = _make_event(_EVENT_ID_1)
    data = {"spray_chart_data": {"offense": {_PLAYER_B: [event]}, "defense": {}}}
    spray_dir = _write_spray_file(tmp_path, _SEASON_ID, _OWN_GC_UUID, _GAME_ID, data)

    SprayChartLoader(db).load_dir(spray_dir)

    row = db.execute(
        "SELECT team_id FROM spray_charts WHERE event_gc_id = ?", (_EVENT_ID_1,)
    ).fetchone()
    assert row is not None
    assert row[0] == opp_id


def test_player_not_in_roster_assigned_opponent_team(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Player not in either team's roster is assigned opponent team_id (TN-10 step 4)."""
    own_id, opp_id = _setup_game(db)
    # _PLAYER_UNKNOWN not seeded in any roster

    event = _make_event(_EVENT_ID_1)
    data = {"spray_chart_data": {"offense": {_PLAYER_UNKNOWN: [event]}, "defense": {}}}
    spray_dir = _write_spray_file(tmp_path, _SEASON_ID, _OWN_GC_UUID, _GAME_ID, data)

    SprayChartLoader(db).load_dir(spray_dir)

    row = db.execute(
        "SELECT team_id FROM spray_charts WHERE event_gc_id = ?", (_EVENT_ID_1,)
    ).fetchone()
    assert row is not None
    # Fallback: opponent = away team (opp_id)
    assert row[0] == opp_id


# ---------------------------------------------------------------------------
# AC-7: accurate LoadResult counts
# ---------------------------------------------------------------------------

def test_load_result_counts_correctly(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """LoadResult loaded/skipped/errors reflect actual insertions."""
    own_id, _opp_id = _setup_game(db)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, own_id, _PLAYER_A)

    events = [_make_event(f"evt-{i}", x=float(i), y=float(i)) for i in range(3)]
    data = {"spray_chart_data": {"offense": {_PLAYER_A: events}, "defense": {}}}
    spray_dir = _write_spray_file(tmp_path, _SEASON_ID, _OWN_GC_UUID, _GAME_ID, data)

    result = SprayChartLoader(db).load_dir(spray_dir)

    assert isinstance(result, LoadResult)
    assert result.loaded == 3
    assert result.skipped == 0
    assert result.errors == 0


# ---------------------------------------------------------------------------
# Game not in games table -- skipped gracefully
# ---------------------------------------------------------------------------

def test_game_not_in_games_table_is_skipped(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """If the game row doesn't exist, spray events are skipped (not errored)."""
    _seed_team(db, _OWN_GC_UUID)
    _seed_season(db)
    # Do NOT insert the game row.

    event = _make_event(_EVENT_ID_1)
    data = {"spray_chart_data": {"offense": {_PLAYER_A: [event]}, "defense": {}}}
    spray_dir = _write_spray_file(tmp_path, _SEASON_ID, _OWN_GC_UUID, _GAME_ID, data)

    result = SprayChartLoader(db).load_dir(spray_dir)

    assert result.loaded == 0
    assert result.errors == 0
    count = db.execute("SELECT COUNT(*) FROM spray_charts").fetchone()[0]
    assert count == 0


# ---------------------------------------------------------------------------
# No spray files in dir
# ---------------------------------------------------------------------------

def test_empty_spray_dir_returns_zero_result(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Empty spray directory returns LoadResult(0, 0, 0) without error."""
    spray_dir = tmp_path / _SEASON_ID / "teams" / _OWN_GC_UUID / "spray"
    spray_dir.mkdir(parents=True)

    result = SprayChartLoader(db).load_dir(spray_dir)

    assert result.loaded == 0
    assert result.skipped == 0
    assert result.errors == 0


# ---------------------------------------------------------------------------
# Both offense and defense sections loaded
# ---------------------------------------------------------------------------

def test_both_sections_loaded_from_same_file(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Offense and defense events from same file both get inserted."""
    own_id, opp_id = _setup_game(db)
    _seed_player(db, _PLAYER_A)
    _seed_player(db, _PLAYER_B)
    _seed_roster(db, own_id, _PLAYER_A)
    _seed_roster(db, opp_id, _PLAYER_B)

    data = {
        "spray_chart_data": {
            "offense": {_PLAYER_A: [_make_event(_EVENT_ID_1)]},
            "defense": {_PLAYER_B: [_make_event(_EVENT_ID_2)]},
        }
    }
    spray_dir = _write_spray_file(tmp_path, _SEASON_ID, _OWN_GC_UUID, _GAME_ID, data)

    result = SprayChartLoader(db).load_dir(spray_dir)

    assert result.loaded == 2
    offensive = db.execute(
        "SELECT chart_type FROM spray_charts WHERE event_gc_id = ?", (_EVENT_ID_1,)
    ).fetchone()
    defensive = db.execute(
        "SELECT chart_type FROM spray_charts WHERE event_gc_id = ?", (_EVENT_ID_2,)
    ).fetchone()
    assert offensive[0] == "offensive"
    assert defensive[0] == "defensive"


# ---------------------------------------------------------------------------
# AC-8: _run_spray_chart_loader registered in pipeline
# ---------------------------------------------------------------------------

def test_spray_chart_loader_registered_in_pipeline() -> None:
    """'spray-chart' is in _LOADERS and _LOADER_NAMES in load.py."""
    from src.pipeline.load import _LOADERS, _LOADER_NAMES

    names = [name for name, _ in _LOADERS]
    assert "spray-chart" in names
    assert "spray-chart" in _LOADER_NAMES
    # Must come after season-stats.
    assert names.index("spray-chart") > names.index("season-stats")


def test_spray_chart_in_cli_loader_choices() -> None:
    """'spray-chart' is in _LOADER_CHOICES in data.py."""
    from src.cli.data import _LOADER_CHOICES

    assert "spray-chart" in _LOADER_CHOICES


# ---------------------------------------------------------------------------
# Error field bool → integer conversion
# ---------------------------------------------------------------------------

def test_error_true_stored_as_1(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """error=True in API maps to INTEGER 1 in DB."""
    own_id, _opp_id = _setup_game(db)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, own_id, _PLAYER_A)

    event = _make_event(_EVENT_ID_1, error=True)
    data = {"spray_chart_data": {"offense": {_PLAYER_A: [event]}, "defense": {}}}
    spray_dir = _write_spray_file(tmp_path, _SEASON_ID, _OWN_GC_UUID, _GAME_ID, data)

    SprayChartLoader(db).load_dir(spray_dir)

    row = db.execute(
        "SELECT error FROM spray_charts WHERE event_gc_id = ?", (_EVENT_ID_1,)
    ).fetchone()
    assert row is not None
    assert row[0] == 1


def test_error_false_stored_as_0(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """error=False in API maps to INTEGER 0 in DB."""
    own_id, _opp_id = _setup_game(db)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, own_id, _PLAYER_A)

    event = _make_event(_EVENT_ID_1, error=False)
    data = {"spray_chart_data": {"offense": {_PLAYER_A: [event]}, "defense": {}}}
    spray_dir = _write_spray_file(tmp_path, _SEASON_ID, _OWN_GC_UUID, _GAME_ID, data)

    SprayChartLoader(db).load_dir(spray_dir)

    row = db.execute(
        "SELECT error FROM spray_charts WHERE event_gc_id = ?", (_EVENT_ID_1,)
    ).fetchone()
    assert row is not None
    assert row[0] == 0
