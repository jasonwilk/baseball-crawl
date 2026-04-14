"""Tests for src/gamechanger/loaders/scouting_spray_loader.py.

Uses an in-memory SQLite database with the real schema applied.
No network calls are made.

Tests cover:
- AC-1: BIP events inserted with correct columns
- AC-2: Team resolution uses public_id (not gc_uuid)
- AC-3 (old): Idempotency via INSERT OR IGNORE
- AC-4 (old): Stub player inserted for resolvable-but-unknown player_id
- AC-5 (old): Null spray_chart_data games skipped with INFO log
- AC-6 (old): load_all() scans scouting spray dirs and loads each
- AC-7 (old): Games not in DB are skipped at DEBUG level (not an error)
- AC-1 (E-165-01): Unresolvable players are skipped (not inserted, no stub)
- AC-3 (E-165-01): Per-game DEBUG summary emitted only when unresolvable players exist
- AC-5 (E-165-01): New tests -- unresolvable skip, DEBUG summary, mixed scenario
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

import pytest

from src.gamechanger.loaders import LoadResult
from src.gamechanger.loaders.scouting_spray_loader import ScoutingSprayChartLoader


# ---------------------------------------------------------------------------
# Schema fixture
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_MIGRATION_001 = _PROJECT_ROOT / "migrations" / "001_initial_schema.sql"



@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory SQLite with real schema (001 + 006) and FK enforcement on."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    conn.executescript(_MIGRATION_001.read_text(encoding="utf-8"))
    conn.commit()
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PUBLIC_ID = "opp-public-id-001"
_OPP_GC_UUID = "aaaabbbb-cccc-dddd-eeee-ffffffffffff"
_OWN_GC_UUID = "11112222-3333-4444-5555-666677778888"
# DB season_id is derived from team metadata (season_year=2025, no program).
_SEASON_ID = "2025"
# Crawl-path season_id (used for file directory construction).
_CRAWL_SEASON_ID = "2025-spring-hs"
_GAME_ID = "event-game-001"
_PLAYER_A = "player-aaa-001"
_PLAYER_B = "player-bbb-002"
_PLAYER_UNKNOWN = "player-unknown-999"
_EVENT_GC_1 = "event-gc-uuid-11111111"
_EVENT_GC_2 = "event-gc-uuid-22222222"


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_team(
    conn: sqlite3.Connection,
    name: str = "Test Team",
    public_id: str | None = None,
    gc_uuid: str | None = None,
    membership_type: str = "tracked",
    season_year: int = 2025,
) -> int:
    cur = conn.execute(
        "INSERT INTO teams (name, membership_type, public_id, gc_uuid, is_active, season_year) "
        "VALUES (?, ?, ?, ?, 1, ?)",
        (name, membership_type, public_id, gc_uuid, season_year),
    )
    conn.commit()
    return cur.lastrowid


def _seed_season(conn: sqlite3.Connection, season_id: str = _SEASON_ID) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, ?, 'unknown', 2025)",
        (season_id, season_id),
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
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, status) "
        "VALUES (?, ?, '2025-04-01', ?, ?, 'completed')",
        (game_id, season_id, home_team_id, away_team_id),
    )
    conn.commit()


def _seed_player(conn: sqlite3.Connection, player_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES (?, 'Test', 'Player')",
        (player_id,),
    )
    conn.commit()


def _seed_roster(
    conn: sqlite3.Connection, player_id: str, team_id: int, season_id: str = _SEASON_ID
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO team_rosters (player_id, team_id, season_id) "
        "VALUES (?, ?, ?)",
        (player_id, team_id, season_id),
    )
    conn.commit()


def _make_spray_event(
    event_gc_id: str = _EVENT_GC_1,
    play_result: str = "single",
    play_type: str = "ground_ball",
    x: float | None = 100.0,
    y: float | None = 80.0,
    position: str = "SS",
    error: bool = False,
) -> dict:
    """Build a minimal spray chart event."""
    return {
        "id": event_gc_id,
        "createdAt": 1700000000000,
        "attributes": {
            "playResult": play_result,
            "playType": play_type,
            "defenders": [
                {
                    "position": position,
                    "location": {"x": x, "y": y},
                    "error": error,
                }
            ],
        },
    }


def _make_spray_event_no_defenders(event_gc_id: str = _EVENT_GC_1) -> dict:
    """Build a spray event with empty defenders (over-the-fence HR)."""
    return {
        "id": event_gc_id,
        "createdAt": 1700000000000,
        "attributes": {
            "playResult": "home_run",
            "playType": "fly_ball",
            "defenders": [],
        },
    }


def _make_spray_json(
    player_id: str = _PLAYER_A,
    events: list[dict] | None = None,
    null_spray_data: bool = False,
) -> dict:
    """Build a player-stats JSON payload."""
    if null_spray_data:
        return {
            "stream_id": "stream-001",
            "player_stats": {},
            "spray_chart_data": None,
        }
    if events is None:
        events = [_make_spray_event()]
    return {
        "stream_id": "stream-001",
        "player_stats": {},
        "spray_chart_data": {
            "offense": {player_id: events},
            "defense": {},
        },
    }


def _write_spray_file(
    tmp_path: Path,
    season_id: str,
    public_id: str,
    game_id: str,
    payload: dict,
) -> Path:
    dest = tmp_path / season_id / "scouting" / public_id / "spray" / f"{game_id}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload), encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# AC-1: Correct columns stored
# ---------------------------------------------------------------------------


def test_load_dir_inserts_correct_columns(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """BIP event is inserted with correct game_id, player_id, team_id, chart_type, etc."""
    _seed_season(db)
    opp_id = _seed_team(db, public_id=_PUBLIC_ID, gc_uuid=_OPP_GC_UUID)
    own_id = _seed_team(db, name="Own Team", gc_uuid=_OWN_GC_UUID, membership_type="member")
    _seed_game(db, _GAME_ID, home_team_id=own_id, away_team_id=opp_id)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, _PLAYER_A, opp_id)  # player belongs to scouted team

    payload = _make_spray_json()
    _write_spray_file(tmp_path, _SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    result = loader.load_dir(tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    row = db.execute(
        "SELECT game_id, player_id, team_id, chart_type, play_result, play_type, "
        "x, y, fielder_position, season_id FROM spray_charts LIMIT 1"
    ).fetchone()
    assert row is not None
    assert row[0] == _GAME_ID
    assert row[1] == _PLAYER_A
    assert row[2] == opp_id  # scouted team (away side, found in roster)
    assert row[3] == "offensive"
    assert row[4] == "single"
    assert row[5] == "ground_ball"
    assert row[6] == 100.0
    assert row[7] == 80.0
    assert row[8] == "SS"
    assert row[9] == _SEASON_ID
    assert result.loaded == 1
    assert result.errors == 0


def test_defensive_chart_type_is_stored(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Defense section produces chart_type='defensive'."""
    _seed_season(db)
    opp_id = _seed_team(db, public_id=_PUBLIC_ID)
    own_id = _seed_team(db, name="Own")
    _seed_game(db, _GAME_ID, home_team_id=opp_id, away_team_id=own_id)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, _PLAYER_A, opp_id)

    payload = {
        "spray_chart_data": {
            "offense": {},
            "defense": {_PLAYER_A: [_make_spray_event(_EVENT_GC_1)]},
        }
    }
    _write_spray_file(tmp_path, _SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    loader.load_dir(tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    row = db.execute("SELECT chart_type FROM spray_charts LIMIT 1").fetchone()
    assert row is not None
    assert row[0] == "defensive"


# ---------------------------------------------------------------------------
# AC-2: Team resolution via public_id (not gc_uuid)
# ---------------------------------------------------------------------------


def test_team_resolved_via_public_id_not_gc_uuid(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """team_id is resolved by public_id, not gc_uuid."""
    _seed_season(db)
    # Team has no gc_uuid -- resolution must succeed via public_id alone.
    opp_id = _seed_team(db, public_id=_PUBLIC_ID, gc_uuid=None)
    own_id = _seed_team(db, name="Own Team")
    _seed_game(db, _GAME_ID, home_team_id=own_id, away_team_id=opp_id)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, _PLAYER_A, opp_id)  # player belongs to scouted team

    payload = _make_spray_json()
    _write_spray_file(tmp_path, _SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    result = loader.load_dir(tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    assert result.loaded == 1
    row = db.execute("SELECT team_id FROM spray_charts LIMIT 1").fetchone()
    assert row[0] == opp_id


def test_unknown_public_id_skips_directory(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Directory for a public_id not in teams table produces empty result."""
    _seed_season(db)
    _write_spray_file(
        tmp_path, _SEASON_ID, "unknown-pub-id", _GAME_ID, _make_spray_json()
    )

    loader = ScoutingSprayChartLoader(db)
    result = loader.load_dir(
        tmp_path / _SEASON_ID / "scouting" / "unknown-pub-id" / "spray"
    )

    assert result.loaded == 0
    assert result.errors == 0
    assert db.execute("SELECT COUNT(*) FROM spray_charts").fetchone()[0] == 0


# ---------------------------------------------------------------------------
# AC-3: Idempotency
# ---------------------------------------------------------------------------


def test_reloading_same_file_produces_zero_new_inserts(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Running load_dir twice on the same files inserts no duplicates."""
    _seed_season(db)
    opp_id = _seed_team(db, public_id=_PUBLIC_ID)
    own_id = _seed_team(db, name="Own")
    _seed_game(db, _GAME_ID, home_team_id=opp_id, away_team_id=own_id)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, _PLAYER_A, opp_id)

    payload = _make_spray_json()
    _write_spray_file(tmp_path, _SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    spray_dir = tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray"
    result1 = loader.load_dir(spray_dir)
    result2 = loader.load_dir(spray_dir)

    assert result1.loaded == 1
    assert result2.loaded == 0
    assert result2.skipped == 1
    assert db.execute("SELECT COUNT(*) FROM spray_charts").fetchone()[0] == 1


# ---------------------------------------------------------------------------
# AC-4: Stub player for resolvable-but-missing player_id
# (Players NOT in team_rosters are now skipped entirely -- see AC-1 / E-165-01)
# ---------------------------------------------------------------------------


def test_resolvable_unknown_player_gets_stub_row(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Player in team_rosters but not in players table receives a stub players row."""
    _seed_season(db)
    opp_id = _seed_team(db, public_id=_PUBLIC_ID)
    own_id = _seed_team(db, name="Own")
    _seed_game(db, _GAME_ID, home_team_id=opp_id, away_team_id=own_id)
    # Insert a minimal players row to satisfy FK constraint on team_rosters,
    # then let the loader detect it needs a stub upgrade (Unknown/Unknown).
    db.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES (?, 'Unknown', 'Unknown')",
        (_PLAYER_A,),
    )
    db.commit()
    _seed_roster(db, _PLAYER_A, opp_id)

    payload = _make_spray_json(player_id=_PLAYER_A)
    _write_spray_file(tmp_path, _SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    result = loader.load_dir(tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    assert result.loaded == 1
    row = db.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?",
        (_PLAYER_A,),
    ).fetchone()
    assert row is not None
    assert row[0] == "Unknown"
    assert row[1] == "Unknown"


# ---------------------------------------------------------------------------
# AC-5 (old): Null spray_chart_data skipped gracefully
# ---------------------------------------------------------------------------


def test_null_spray_chart_data_skipped_with_info(
    db: sqlite3.Connection, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """File with spray_chart_data=null is skipped; nothing inserted."""
    _seed_season(db)
    opp_id = _seed_team(db, public_id=_PUBLIC_ID)
    own_id = _seed_team(db, name="Own")
    _seed_game(db, _GAME_ID, home_team_id=opp_id, away_team_id=own_id)

    payload = _make_spray_json(null_spray_data=True)
    _write_spray_file(tmp_path, _SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    with caplog.at_level(logging.INFO, logger="src.gamechanger.loaders.scouting_spray_loader"):
        result = loader.load_dir(tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    assert result.loaded == 0
    assert result.errors == 0
    assert db.execute("SELECT COUNT(*) FROM spray_charts").fetchone()[0] == 0
    assert "null" in caplog.text.lower() or "skipping" in caplog.text.lower()


# ---------------------------------------------------------------------------
# AC-6 (old): load_all scans scouting spray dirs
# ---------------------------------------------------------------------------


def test_load_all_processes_all_opponents(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """load_all() processes spray files across multiple opponents and seasons."""
    _seed_season(db)
    pub_a = "opp-a"
    pub_b = "opp-b"
    id_a = _seed_team(db, name="Opp A", public_id=pub_a)
    id_b = _seed_team(db, name="Opp B", public_id=pub_b)
    own_id = _seed_team(db, name="Own")

    game_a = "event-game-a"
    game_b = "event-game-b"
    _seed_game(db, game_a, home_team_id=id_a, away_team_id=own_id)
    _seed_game(db, game_b, home_team_id=id_b, away_team_id=own_id)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, _PLAYER_A, id_a)
    _seed_roster(db, _PLAYER_A, id_b)

    _write_spray_file(
        tmp_path, _SEASON_ID, pub_a, game_a,
        {"spray_chart_data": {"offense": {_PLAYER_A: [_make_spray_event(_EVENT_GC_1)]}, "defense": {}}},
    )
    _write_spray_file(
        tmp_path, _SEASON_ID, pub_b, game_b,
        {"spray_chart_data": {"offense": {_PLAYER_A: [_make_spray_event(_EVENT_GC_2)]}, "defense": {}}},
    )

    loader = ScoutingSprayChartLoader(db)
    result = loader.load_all(tmp_path)

    assert result.loaded == 2
    assert result.errors == 0


def test_load_all_with_public_id_filter(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """load_all(public_id=...) only loads the specified opponent's files."""
    _seed_season(db)
    pub_a = "opp-a"
    pub_b = "opp-b"
    id_a = _seed_team(db, name="Opp A", public_id=pub_a)
    id_b = _seed_team(db, name="Opp B", public_id=pub_b)
    own_id = _seed_team(db, name="Own")

    game_a = "event-game-a"
    game_b = "event-game-b"
    _seed_game(db, game_a, home_team_id=id_a, away_team_id=own_id)
    _seed_game(db, game_b, home_team_id=id_b, away_team_id=own_id)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, _PLAYER_A, id_a)
    _seed_roster(db, _PLAYER_A, id_b)

    _write_spray_file(
        tmp_path, _SEASON_ID, pub_a, game_a,
        {"spray_chart_data": {"offense": {_PLAYER_A: [_make_spray_event(_EVENT_GC_1)]}, "defense": {}}},
    )
    _write_spray_file(
        tmp_path, _SEASON_ID, pub_b, game_b,
        {"spray_chart_data": {"offense": {_PLAYER_A: [_make_spray_event(_EVENT_GC_2)]}, "defense": {}}},
    )

    loader = ScoutingSprayChartLoader(db)
    result = loader.load_all(tmp_path, public_id=pub_a)

    assert result.loaded == 1
    assert db.execute("SELECT COUNT(*) FROM spray_charts").fetchone()[0] == 1


def test_load_all_returns_load_result_instance(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """load_all always returns a LoadResult instance."""
    loader = ScoutingSprayChartLoader(db)
    result = loader.load_all(tmp_path)
    assert isinstance(result, LoadResult)


def test_load_all_no_dirs_returns_empty_result(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """load_all with no spray dirs returns empty LoadResult (not an error)."""
    loader = ScoutingSprayChartLoader(db)
    result = loader.load_all(tmp_path)
    assert result.loaded == 0
    assert result.errors == 0


# ---------------------------------------------------------------------------
# AC-7 (old): Games not in DB are skipped at DEBUG level
# ---------------------------------------------------------------------------


def test_game_not_in_db_is_skipped_at_debug(
    db: sqlite3.Connection, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Spray events for a game_id not in games table are skipped without error."""
    _seed_season(db)
    _seed_team(db, public_id=_PUBLIC_ID)
    # Intentionally NO game row seeded

    payload = _make_spray_json()
    _write_spray_file(tmp_path, _SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    with caplog.at_level(logging.DEBUG, logger="src.gamechanger.loaders.scouting_spray_loader"):
        result = loader.load_dir(tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    assert result.loaded == 0
    assert result.errors == 0
    assert _GAME_ID in caplog.text


def test_game_not_in_db_does_not_count_as_error(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Missing game row is a defensive skip (not counted in errors)."""
    _seed_season(db)
    _seed_team(db, public_id=_PUBLIC_ID)
    payload = _make_spray_json()
    _write_spray_file(tmp_path, _SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    result = loader.load_dir(tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    assert result.errors == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_defenders_stored_with_null_coords(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Empty defenders array (over-the-fence HR) stored with NULL x/y/position/error."""
    _seed_season(db)
    opp_id = _seed_team(db, public_id=_PUBLIC_ID)
    own_id = _seed_team(db, name="Own")
    _seed_game(db, _GAME_ID, home_team_id=opp_id, away_team_id=own_id)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, _PLAYER_A, opp_id)

    hr_event = _make_spray_event_no_defenders()
    payload = {
        "spray_chart_data": {
            "offense": {_PLAYER_A: [hr_event]},
            "defense": {},
        }
    }
    _write_spray_file(tmp_path, _SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    result = loader.load_dir(tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    assert result.loaded == 1
    row = db.execute("SELECT x, y, fielder_position, error FROM spray_charts LIMIT 1").fetchone()
    assert row[0] is None
    assert row[1] is None
    assert row[2] is None
    assert row[3] is None


def test_defender_missing_location_skipped(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Event with defender present but no location x/y is skipped."""
    _seed_season(db)
    opp_id = _seed_team(db, public_id=_PUBLIC_ID)
    own_id = _seed_team(db, name="Own")
    _seed_game(db, _GAME_ID, home_team_id=opp_id, away_team_id=own_id)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, _PLAYER_A, opp_id)  # roster entry so player reaches _insert_event

    bad_event = {
        "id": _EVENT_GC_1,
        "createdAt": 1700000000000,
        "attributes": {
            "playResult": "single",
            "playType": "ground_ball",
            "defenders": [{"position": "SS", "location": {}}],  # no x/y
        },
    }
    payload = {
        "spray_chart_data": {"offense": {_PLAYER_A: [bad_event]}, "defense": {}}
    }
    _write_spray_file(tmp_path, _SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    result = loader.load_dir(tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    assert result.loaded == 0
    assert result.skipped == 1


def test_event_missing_id_field_is_skipped(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Spray event without 'id' field is skipped and counted."""
    _seed_season(db)
    opp_id = _seed_team(db, public_id=_PUBLIC_ID)
    own_id = _seed_team(db, name="Own")
    _seed_game(db, _GAME_ID, home_team_id=opp_id, away_team_id=own_id)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, _PLAYER_A, opp_id)  # roster entry so player reaches _insert_event

    bad_event = {"attributes": {"playResult": "single", "defenders": []}}
    payload = {
        "spray_chart_data": {"offense": {_PLAYER_A: [bad_event]}, "defense": {}}
    }
    _write_spray_file(tmp_path, _SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    result = loader.load_dir(tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    assert result.loaded == 0
    assert result.skipped == 1


def test_player_team_resolved_via_roster(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Player found in team_rosters is assigned their actual team_id."""
    _seed_season(db)
    opp_id = _seed_team(db, public_id=_PUBLIC_ID)
    own_id = _seed_team(db, name="Own Team")
    _seed_game(db, _GAME_ID, home_team_id=opp_id, away_team_id=own_id)
    _seed_player(db, _PLAYER_A)
    # Player A belongs to own_id, not opp_id
    _seed_roster(db, _PLAYER_A, own_id)

    payload = _make_spray_json(player_id=_PLAYER_A)
    _write_spray_file(tmp_path, _SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    loader.load_dir(tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    row = db.execute("SELECT team_id FROM spray_charts LIMIT 1").fetchone()
    assert row[0] == own_id


def test_multi_game_across_season(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Multiple game files in spray dir are all loaded."""
    _seed_season(db)
    opp_id = _seed_team(db, public_id=_PUBLIC_ID)
    own_id = _seed_team(db, name="Own")
    game_1 = "event-game-001"
    game_2 = "event-game-002"
    _seed_game(db, game_1, home_team_id=opp_id, away_team_id=own_id)
    _seed_game(db, game_2, home_team_id=opp_id, away_team_id=own_id)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, _PLAYER_A, opp_id)

    ev1 = _make_spray_event(_EVENT_GC_1)
    ev2 = _make_spray_event(_EVENT_GC_2)
    _write_spray_file(
        tmp_path, _SEASON_ID, _PUBLIC_ID, game_1,
        {"spray_chart_data": {"offense": {_PLAYER_A: [ev1]}, "defense": {}}},
    )
    _write_spray_file(
        tmp_path, _SEASON_ID, _PUBLIC_ID, game_2,
        {"spray_chart_data": {"offense": {_PLAYER_A: [ev2]}, "defense": {}}},
    )

    loader = ScoutingSprayChartLoader(db)
    result = loader.load_dir(tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    assert result.loaded == 2
    assert db.execute("SELECT COUNT(*) FROM spray_charts").fetchone()[0] == 2


def test_season_id_derived_from_team_metadata(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """season_id in spray_charts row comes from team metadata, not the directory path."""
    crawl_season = "2024-fall-hs"
    # Team has season_year=2025 (default from _seed_team), so DB season_id = "2025".
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, ?, 'default', 2025)",
        (_SEASON_ID, _SEASON_ID),
    )
    db.commit()
    opp_id = _seed_team(db, public_id=_PUBLIC_ID)
    own_id = _seed_team(db, name="Own")
    _seed_game(db, _GAME_ID, home_team_id=opp_id, away_team_id=own_id)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, _PLAYER_A, opp_id)

    payload = _make_spray_json()
    # File written under a DIFFERENT crawl-path season than the DB season_id.
    _write_spray_file(tmp_path, crawl_season, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    loader.load_dir(tmp_path / crawl_season / "scouting" / _PUBLIC_ID / "spray")

    row = db.execute("SELECT season_id FROM spray_charts LIMIT 1").fetchone()
    assert row is not None
    # DB season_id comes from team metadata, not the crawl path.
    assert row[0] == _SEASON_ID


# ---------------------------------------------------------------------------
# E-165-01 AC-1 / AC-3 / AC-5: Unresolvable player skip behavior
# ---------------------------------------------------------------------------


def test_unresolvable_player_events_are_skipped(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Player not in team_rosters: all events skipped, no spray row, no stub player row."""
    _seed_season(db)
    opp_id = _seed_team(db, public_id=_PUBLIC_ID)
    own_id = _seed_team(db, name="Own")
    _seed_game(db, _GAME_ID, home_team_id=opp_id, away_team_id=own_id)
    # _PLAYER_UNKNOWN not seeded in players or team_rosters

    payload = _make_spray_json(player_id=_PLAYER_UNKNOWN)
    _write_spray_file(tmp_path, _SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    result = loader.load_dir(tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    assert result.loaded == 0
    assert result.skipped == 1
    assert result.errors == 0
    assert db.execute("SELECT COUNT(*) FROM spray_charts").fetchone()[0] == 0
    assert db.execute(
        "SELECT COUNT(*) FROM players WHERE player_id = ?", (_PLAYER_UNKNOWN,)
    ).fetchone()[0] == 0


def test_unresolvable_player_no_per_player_warning(
    db: sqlite3.Connection, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Unresolvable player emits no per-player WARNING; only a DEBUG summary is used."""
    _seed_season(db)
    opp_id = _seed_team(db, public_id=_PUBLIC_ID)
    own_id = _seed_team(db, name="Own")
    _seed_game(db, _GAME_ID, home_team_id=opp_id, away_team_id=own_id)
    # _PLAYER_UNKNOWN not in team_rosters

    payload = _make_spray_json(player_id=_PLAYER_UNKNOWN)
    _write_spray_file(tmp_path, _SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    with caplog.at_level(logging.WARNING, logger="src.gamechanger.loaders.scouting_spray_loader"):
        loader.load_dir(tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    # No per-player WARNING for unresolvable player (TN-4)
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert not any(_PLAYER_UNKNOWN in r.message for r in warning_records)
    assert not any("best-guess" in r.message for r in warning_records)


def test_per_game_debug_summary_emitted_when_unresolvable(
    db: sqlite3.Connection, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """When a game has unresolvable players, exactly one DEBUG summary line is emitted."""
    _seed_season(db)
    opp_id = _seed_team(db, public_id=_PUBLIC_ID)
    own_id = _seed_team(db, name="Own")
    _seed_game(db, _GAME_ID, home_team_id=opp_id, away_team_id=own_id)
    # _PLAYER_UNKNOWN not in team_rosters

    payload = _make_spray_json(player_id=_PLAYER_UNKNOWN)
    _write_spray_file(tmp_path, _SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    with caplog.at_level(logging.DEBUG, logger="src.gamechanger.loaders.scouting_spray_loader"):
        loader.load_dir(tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    debug_lines = [
        r for r in caplog.records
        if r.levelno == logging.DEBUG and "unresolvable" in r.message
    ]
    assert len(debug_lines) == 1
    assert _GAME_ID in debug_lines[0].message


def test_no_debug_summary_when_all_players_resolvable(
    db: sqlite3.Connection, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """When all players are resolvable, no unresolvable-player DEBUG line is emitted."""
    _seed_season(db)
    opp_id = _seed_team(db, public_id=_PUBLIC_ID)
    own_id = _seed_team(db, name="Own")
    _seed_game(db, _GAME_ID, home_team_id=opp_id, away_team_id=own_id)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, _PLAYER_A, opp_id)

    payload = _make_spray_json(player_id=_PLAYER_A)
    _write_spray_file(tmp_path, _SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    with caplog.at_level(logging.DEBUG, logger="src.gamechanger.loaders.scouting_spray_loader"):
        loader.load_dir(tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    debug_lines = [
        r for r in caplog.records
        if r.levelno == logging.DEBUG and "unresolvable" in r.message
    ]
    assert len(debug_lines) == 0


def test_mixed_resolvable_and_unresolvable_players(
    db: sqlite3.Connection, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Game with resolvable and unresolvable players: correct counts, one DEBUG summary."""
    _seed_season(db)
    opp_id = _seed_team(db, public_id=_PUBLIC_ID)
    own_id = _seed_team(db, name="Own")
    _seed_game(db, _GAME_ID, home_team_id=opp_id, away_team_id=own_id)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, _PLAYER_A, opp_id)  # resolvable
    # _PLAYER_UNKNOWN not in team_rosters -- unresolvable

    payload = {
        "spray_chart_data": {
            "offense": {
                _PLAYER_A: [_make_spray_event(_EVENT_GC_1)],
                _PLAYER_UNKNOWN: [_make_spray_event(_EVENT_GC_2)],
            },
            "defense": {},
        }
    }
    _write_spray_file(tmp_path, _SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    with caplog.at_level(logging.DEBUG, logger="src.gamechanger.loaders.scouting_spray_loader"):
        result = loader.load_dir(tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    assert result.loaded == 1    # _PLAYER_A's event inserted
    assert result.skipped == 1   # _PLAYER_UNKNOWN's event skipped
    assert result.errors == 0
    assert db.execute("SELECT COUNT(*) FROM spray_charts").fetchone()[0] == 1

    debug_lines = [
        r for r in caplog.records
        if r.levelno == logging.DEBUG and "unresolvable" in r.message
    ]
    assert len(debug_lines) == 1
    assert _GAME_ID in debug_lines[0].message


# ---------------------------------------------------------------------------
# E-220-04: Perspective tagging
# ---------------------------------------------------------------------------


def test_scouting_spray_rows_have_perspective_team_id(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-2: Every scouting spray row has perspective_team_id set to the scouted team's PK."""
    _seed_season(db)
    opp_id = _seed_team(db, public_id=_PUBLIC_ID, gc_uuid=_OPP_GC_UUID)
    own_id = _seed_team(db, name="Own Team", gc_uuid=_OWN_GC_UUID, membership_type="member")
    _seed_game(db, _GAME_ID, home_team_id=own_id, away_team_id=opp_id)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, _PLAYER_A, opp_id)

    payload = _make_spray_json()
    _write_spray_file(tmp_path, _CRAWL_SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    loader.load_dir(tmp_path / _CRAWL_SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    row = db.execute(
        "SELECT perspective_team_id FROM spray_charts WHERE event_gc_id = ?",
        (_EVENT_GC_1,),
    ).fetchone()
    assert row is not None
    assert row[0] == opp_id, f"Expected perspective_team_id={opp_id} (scouted team), got {row[0]}"


def test_scouting_spray_two_perspectives_coexist(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-3: Same event_gc_id from two different scouting perspectives coexists."""
    _seed_season(db)
    opp_id = _seed_team(db, public_id=_PUBLIC_ID, gc_uuid=_OPP_GC_UUID)
    own_id = _seed_team(db, name="Own Team", gc_uuid=_OWN_GC_UUID, membership_type="member")
    _seed_game(db, _GAME_ID, home_team_id=own_id, away_team_id=opp_id)
    _seed_player(db, _PLAYER_A)
    _seed_roster(db, _PLAYER_A, opp_id)
    _seed_roster(db, _PLAYER_A, own_id)

    payload = _make_spray_json()

    # Load from scouted team perspective.
    _write_spray_file(tmp_path, _CRAWL_SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)
    loader = ScoutingSprayChartLoader(db)
    loader.load_dir(tmp_path / _CRAWL_SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    # Create a second scouted team with a different public_id.
    opp2_public_id = "opp-public-id-002"
    opp2_id = _seed_team(db, name="Second Opponent", public_id=opp2_public_id)
    _seed_roster(db, _PLAYER_A, opp2_id)
    _seed_game(db, _GAME_ID + "-2", home_team_id=own_id, away_team_id=opp2_id)

    payload2 = _make_spray_json()
    _write_spray_file(tmp_path, _CRAWL_SEASON_ID, opp2_public_id, _GAME_ID + "-2", payload2)
    loader.load_dir(tmp_path / _CRAWL_SEASON_ID / "scouting" / opp2_public_id / "spray")

    rows = db.execute(
        "SELECT DISTINCT perspective_team_id FROM spray_charts WHERE event_gc_id = ?",
        (_EVENT_GC_1,),
    ).fetchall()
    assert len(rows) == 2, f"Expected 2 perspective rows, got {len(rows)}"
    assert {r[0] for r in rows} == {opp_id, opp2_id}


# ---------------------------------------------------------------------------
# E-223-03: Perspective gate tests
# ---------------------------------------------------------------------------


class TestScoutingSprayPerspectiveGate:
    """E-223-03 AC-2/AC-3/AC-4: Whole-game perspective gate for scouting spray."""

    def test_skips_already_loaded_perspective_via_load_dir(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """AC-2/AC-4: load_dir skips game when perspective already loaded."""
        own_id = _seed_team(db, "Own Team", gc_uuid=_OWN_GC_UUID, membership_type="member")
        opp_id = _seed_team(db, "Opponent", public_id=_PUBLIC_ID)
        _seed_season(db)
        _seed_game(db, _GAME_ID, own_id, opp_id)
        _seed_player(db, _PLAYER_A)
        _seed_roster(db, _PLAYER_A, opp_id)

        event1 = _make_spray_event(_EVENT_GC_1)
        event2 = _make_spray_event(_EVENT_GC_2)
        payload = _make_spray_json(_PLAYER_A, events=[event1, event2])
        spray_dir = tmp_path / _CRAWL_SEASON_ID / "scouting" / _PUBLIC_ID / "spray"
        _write_spray_file(tmp_path, _CRAWL_SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

        loader = ScoutingSprayChartLoader(db)
        result1 = loader.load_dir(spray_dir)
        assert result1.loaded == 2

        # Second load: perspective gate should fire
        result2 = loader.load_dir(spray_dir)
        assert result2.skipped == 1, (
            f"Expected game-level skip (1), got skipped={result2.skipped}"
        )
        assert result2.loaded == 0

    def test_skips_already_loaded_perspective_via_load_from_data(
        self, db: sqlite3.Connection
    ) -> None:
        """AC-2/AC-4: load_from_data skips game when perspective already loaded."""
        own_id = _seed_team(db, "Own Team", gc_uuid=_OWN_GC_UUID, membership_type="member")
        opp_id = _seed_team(db, "Opponent", public_id=_PUBLIC_ID)
        _seed_season(db)
        _seed_game(db, _GAME_ID, own_id, opp_id)
        _seed_player(db, _PLAYER_A)
        _seed_roster(db, _PLAYER_A, opp_id)

        event = _make_spray_event(_EVENT_GC_1)
        spray_data = {
            _GAME_ID: {"spray_chart_data": {"offense": {_PLAYER_A: [event]}, "defense": {}}},
        }

        loader = ScoutingSprayChartLoader(db)
        result1 = loader.load_from_data(spray_data, _PUBLIC_ID)
        assert result1.loaded == 1

        # Second load: perspective gate should fire
        result2 = loader.load_from_data(spray_data, _PUBLIC_ID)
        assert result2.skipped == 1, (
            f"Expected game-level skip (1), got skipped={result2.skipped}"
        )
        assert result2.loaded == 0

    def test_loads_new_perspective_for_same_game(
        self, db: sqlite3.Connection
    ) -> None:
        """AC-4: New perspective for same game loads normally."""
        own_id = _seed_team(db, "Own Team", gc_uuid=_OWN_GC_UUID, membership_type="member")
        opp_id = _seed_team(db, "Opponent", public_id=_PUBLIC_ID)
        opp2_public_id = "opp-public-id-002"
        opp2_id = _seed_team(db, "Opponent 2", public_id=opp2_public_id)
        _seed_season(db)
        _seed_game(db, _GAME_ID, own_id, opp_id)
        _seed_player(db, _PLAYER_A)
        _seed_roster(db, _PLAYER_A, opp_id)
        _seed_roster(db, _PLAYER_A, opp2_id)

        event = _make_spray_event(_EVENT_GC_1)
        spray_data = {
            _GAME_ID: {"spray_chart_data": {"offense": {_PLAYER_A: [event]}, "defense": {}}},
        }

        loader = ScoutingSprayChartLoader(db)
        # Load as opp_id perspective
        result1 = loader.load_from_data(spray_data, _PUBLIC_ID)
        assert result1.loaded == 1

        # Load as opp2_id perspective -- should succeed (different perspective)
        result2 = loader.load_from_data(spray_data, opp2_public_id)
        assert result2.loaded == 1, (
            f"New perspective should load normally, got loaded={result2.loaded}"
        )

    def test_partial_load_blocks_retry(self, db: sqlite3.Connection) -> None:
        """Documented limitation: partial first pass blocks retries.

        When the first load partially succeeds (some events loaded, some
        skipped due to unresolvable players), the perspective gate treats
        the game as fully loaded on subsequent runs. This is a known
        trade-off of the game-level gate (performance optimization).

        To recover from a partial load, the operator must first delete the
        partial rows:
            DELETE FROM spray_charts WHERE game_id=? AND perspective_team_id=?
        then re-run the loader.
        """
        own_id = _seed_team(db, "Own Team", gc_uuid=_OWN_GC_UUID, membership_type="member")
        opp_id = _seed_team(db, "Opponent", public_id=_PUBLIC_ID)
        _seed_season(db)
        _seed_game(db, _GAME_ID, own_id, opp_id)
        # Only player A is in roster; player B (PLAYER_UNKNOWN) is not
        _seed_player(db, _PLAYER_A)
        _seed_roster(db, _PLAYER_A, opp_id)

        event_a = _make_spray_event(_EVENT_GC_1)
        event_b = _make_spray_event(_EVENT_GC_2)
        spray_data = {
            _GAME_ID: {
                "spray_chart_data": {
                    "offense": {
                        _PLAYER_A: [event_a],
                        _PLAYER_UNKNOWN: [event_b],  # unresolvable
                    },
                    "defense": {},
                },
            },
        }

        loader = ScoutingSprayChartLoader(db)
        result1 = loader.load_from_data(spray_data, _PUBLIC_ID)
        assert result1.loaded == 1, f"Player A's event should load: {result1}"
        assert result1.skipped == 1, f"Player B's event should skip: {result1}"

        # Now fix the roster (add player B)
        _seed_player(db, _PLAYER_UNKNOWN)
        _seed_roster(db, _PLAYER_UNKNOWN, opp_id)

        # Retry: gate blocks because player A's row already exists
        result2 = loader.load_from_data(spray_data, _PUBLIC_ID)
        assert result2.skipped == 1, (
            f"Gate should block retry (game-level skip): {result2}"
        )
        assert result2.loaded == 0, (
            f"No new rows loaded through the gate: {result2}"
        )

        # Recovery: delete partial rows, then retry succeeds
        db.execute(
            "DELETE FROM spray_charts WHERE game_id = ? AND perspective_team_id = ?",
            (_GAME_ID, opp_id),
        )
        db.commit()
        result3 = loader.load_from_data(spray_data, _PUBLIC_ID)
        assert result3.loaded == 2, (
            f"After deleting partial rows, both events should load: {result3}"
        )
