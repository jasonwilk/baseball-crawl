"""Tests for src/gamechanger/loaders/scouting_spray_loader.py.

Uses an in-memory SQLite database with the real schema applied.
No network calls are made.

Tests cover:
- AC-1: BIP events inserted with correct columns
- AC-2: Team resolution uses public_id (not gc_uuid)
- AC-3: Idempotency via INSERT OR IGNORE
- AC-4: Stub player inserted for unknown player_id + WARNING log
- AC-5: Null spray_chart_data games skipped with INFO log
- AC-6: load_all() scans scouting spray dirs and loads each
- AC-7: Games not in DB are skipped at DEBUG level (not an error)
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
_MIGRATION_006 = _PROJECT_ROOT / "migrations" / "006_spray_charts_indexes.sql"


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory SQLite with real schema (001 + 006) and FK enforcement on."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    conn.executescript(_MIGRATION_001.read_text(encoding="utf-8"))
    conn.executescript(_MIGRATION_006.read_text(encoding="utf-8"))
    conn.commit()
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PUBLIC_ID = "opp-public-id-001"
_OPP_GC_UUID = "aaaabbbb-cccc-dddd-eeee-ffffffffffff"
_OWN_GC_UUID = "11112222-3333-4444-5555-666677778888"
_SEASON_ID = "2025-spring-hs"
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
) -> int:
    cur = conn.execute(
        "INSERT INTO teams (name, membership_type, public_id, gc_uuid, is_active) "
        "VALUES (?, ?, ?, ?, 1)",
        (name, membership_type, public_id, gc_uuid),
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
# AC-4: Stub player for unknown player_id
# ---------------------------------------------------------------------------


def test_unknown_player_gets_stub_row(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Unknown player_id causes a stub player row to be inserted."""
    _seed_season(db)
    opp_id = _seed_team(db, public_id=_PUBLIC_ID)
    own_id = _seed_team(db, name="Own")
    _seed_game(db, _GAME_ID, home_team_id=opp_id, away_team_id=own_id)
    # PLAYER_UNKNOWN is not seeded

    payload = _make_spray_json(player_id=_PLAYER_UNKNOWN)
    _write_spray_file(tmp_path, _SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    loader.load_dir(tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    row = db.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?",
        (_PLAYER_UNKNOWN,),
    ).fetchone()
    assert row is not None
    assert row[0] == "Unknown"
    assert row[1] == "Unknown"


def test_unknown_player_logs_warning(
    db: sqlite3.Connection, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Stub player insertion emits a WARNING log."""
    _seed_season(db)
    opp_id = _seed_team(db, public_id=_PUBLIC_ID)
    own_id = _seed_team(db, name="Own")
    _seed_game(db, _GAME_ID, home_team_id=opp_id, away_team_id=own_id)

    payload = _make_spray_json(player_id=_PLAYER_UNKNOWN)
    _write_spray_file(tmp_path, _SEASON_ID, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    with caplog.at_level(logging.WARNING, logger="src.gamechanger.loaders.scouting_spray_loader"):
        loader.load_dir(tmp_path / _SEASON_ID / "scouting" / _PUBLIC_ID / "spray")

    assert _PLAYER_UNKNOWN in caplog.text
    assert "stub" in caplog.text.lower() or "Unknown" in caplog.text


# ---------------------------------------------------------------------------
# AC-5: Null spray_chart_data skipped gracefully
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
# AC-6: load_all scans scouting spray dirs
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
# AC-7: Games not in DB are skipped at DEBUG level
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


def test_season_id_inferred_from_path(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """season_id in spray_charts row comes from the directory path."""
    season = "2024-fall-hs"
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, ?, 'unknown', 2024)",
        (season, season),
    )
    db.commit()
    opp_id = _seed_team(db, public_id=_PUBLIC_ID)
    own_id = _seed_team(db, name="Own")
    _seed_game(db, _GAME_ID, home_team_id=opp_id, away_team_id=own_id, season_id=season)
    _seed_player(db, _PLAYER_A)

    payload = _make_spray_json()
    _write_spray_file(tmp_path, season, _PUBLIC_ID, _GAME_ID, payload)

    loader = ScoutingSprayChartLoader(db)
    loader.load_dir(tmp_path / season / "scouting" / _PUBLIC_ID / "spray")

    row = db.execute("SELECT season_id FROM spray_charts LIMIT 1").fetchone()
    assert row[0] == season
