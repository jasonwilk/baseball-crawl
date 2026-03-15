"""Tests for src/gamechanger/loaders/roster.py.

Uses an in-memory SQLite database with the schema applied from
migrations/001_initial_schema.sql.  No real database files are created.
No network calls are made.

Tests cover:
- AC-1: Successful upsert of players and team_rosters
- AC-2: Idempotent -- loading same file twice produces same state
- AC-3: Cross-team player: one players row, two team_rosters rows
- AC-4: Unknown JSON fields are ignored (logged at DEBUG)
- AC-5: Missing required field causes record skip, load continues
- AC-6: FK prerequisite rows (teams, seasons) created automatically
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from src.gamechanger.loaders import LoadResult
from src.gamechanger.loaders.roster import RosterLoader

# ---------------------------------------------------------------------------
# Schema fixture
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MIGRATION_FILE = _PROJECT_ROOT / "migrations" / "001_initial_schema.sql"


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory SQLite connection with the schema applied and FK enforcement on.

    Yields:
        Open sqlite3.Connection ready for loader tests.
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

_TEAM_ID = "team-uuid-jv-001"
_SEASON_ID = "2025"

_SAMPLE_PLAYERS = [
    {
        "id": "player-aaa-001",
        "first_name": "Jake",
        "last_name": "Smith",
        "number": "7",
        "avatar_url": "",
    },
    {
        "id": "player-bbb-002",
        "first_name": "Mike",
        "last_name": "Jones",
        "number": "14",
        "avatar_url": "https://example.com/avatar.png",
    },
]


def _write_roster(tmp_path: Path, players: list[dict], team_id: str = _TEAM_ID, season: str = _SEASON_ID) -> Path:
    """Write a roster.json file at the conventional path and return it.

    Args:
        tmp_path: Pytest temporary directory.
        players: Raw player list to serialise.
        team_id: Team UUID (used in path).
        season: Season label (used in path).

    Returns:
        Path to the written ``roster.json``.
    """
    dest = tmp_path / season / "teams" / team_id / "roster.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(players), encoding="utf-8")
    return dest


def _player_ids(conn: sqlite3.Connection) -> set[str]:
    """Return the set of player_ids in the players table."""
    rows = conn.execute("SELECT player_id FROM players;").fetchall()
    return {row[0] for row in rows}


def _roster_rows(conn: sqlite3.Connection) -> list[tuple]:
    """Return all team_rosters rows as (team_id, player_id, season_id) tuples."""
    rows = conn.execute(
        "SELECT team_id, player_id, season_id FROM team_rosters;"
    ).fetchall()
    return rows


# ---------------------------------------------------------------------------
# AC-1: Successful upsert
# ---------------------------------------------------------------------------


def test_load_file_upserts_all_players(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-1: All players in roster.json are upserted into the players table."""
    path = _write_roster(tmp_path, _SAMPLE_PLAYERS)
    loader = RosterLoader(db)

    result = loader.load_file(path)

    assert result.loaded == 2
    assert result.skipped == 0
    assert result.errors == 0
    assert _player_ids(db) == {"player-aaa-001", "player-bbb-002"}


def test_load_file_upserts_team_roster_rows(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-1: team_rosters rows are created for each player."""
    path = _write_roster(tmp_path, _SAMPLE_PLAYERS)
    loader = RosterLoader(db)

    loader.load_file(path)

    rows = _roster_rows(db)
    assert len(rows) == 2
    team_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_TEAM_ID,)).fetchone()[0]
    team_ids = {r[0] for r in rows}
    player_ids = {r[1] for r in rows}
    season_ids = {r[2] for r in rows}
    assert team_ids == {team_pk}
    assert player_ids == {"player-aaa-001", "player-bbb-002"}
    assert season_ids == {_SEASON_ID}


def test_load_file_stores_jersey_number(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-1: Jersey number is stored in the team_rosters row."""
    path = _write_roster(tmp_path, _SAMPLE_PLAYERS)
    loader = RosterLoader(db)

    loader.load_file(path)

    row = db.execute(
        "SELECT jersey_number FROM team_rosters WHERE player_id = 'player-aaa-001';"
    ).fetchone()
    assert row is not None
    assert row[0] == "7"


def test_load_file_returns_load_result(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-1: load_file returns a LoadResult dataclass."""
    path = _write_roster(tmp_path, _SAMPLE_PLAYERS)
    loader = RosterLoader(db)

    result = loader.load_file(path)

    assert isinstance(result, LoadResult)


# ---------------------------------------------------------------------------
# AC-2: Idempotent -- loading the same file twice
# ---------------------------------------------------------------------------


def test_load_file_twice_does_not_duplicate_players(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-2: Running load_file twice produces the same players table state."""
    path = _write_roster(tmp_path, _SAMPLE_PLAYERS)
    loader = RosterLoader(db)

    loader.load_file(path)
    loader.load_file(path)

    count = db.execute("SELECT COUNT(*) FROM players;").fetchone()[0]
    assert count == 2


def test_load_file_twice_does_not_duplicate_roster_rows(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-2: Running load_file twice produces the same team_rosters table state."""
    path = _write_roster(tmp_path, _SAMPLE_PLAYERS)
    loader = RosterLoader(db)

    loader.load_file(path)
    loader.load_file(path)

    count = db.execute("SELECT COUNT(*) FROM team_rosters;").fetchone()[0]
    assert count == 2


# ---------------------------------------------------------------------------
# AC-3: Cross-team player -- one players row, multiple team_rosters rows
# ---------------------------------------------------------------------------


def test_cross_team_player_has_one_players_row(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-3: A player on two teams has exactly one row in the players table."""
    shared_player = [
        {"id": "player-shared-999", "first_name": "Ace", "last_name": "Pitcher", "number": "1", "avatar_url": ""}
    ]
    path_team_a = _write_roster(tmp_path, shared_player, team_id="team-aaa", season="2025")
    path_team_b = _write_roster(tmp_path, shared_player, team_id="team-bbb", season="2025")

    loader = RosterLoader(db)
    loader.load_file(path_team_a)
    loader.load_file(path_team_b)

    count = db.execute(
        "SELECT COUNT(*) FROM players WHERE player_id = 'player-shared-999';"
    ).fetchone()[0]
    assert count == 1


def test_cross_team_player_has_two_roster_rows(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-3: A player on two teams has two rows in team_rosters."""
    shared_player = [
        {"id": "player-shared-999", "first_name": "Ace", "last_name": "Pitcher", "number": "1", "avatar_url": ""}
    ]
    path_team_a = _write_roster(tmp_path, shared_player, team_id="team-aaa", season="2025")
    path_team_b = _write_roster(tmp_path, shared_player, team_id="team-bbb", season="2025")

    loader = RosterLoader(db)
    loader.load_file(path_team_a)
    loader.load_file(path_team_b)

    count = db.execute(
        "SELECT COUNT(*) FROM team_rosters WHERE player_id = 'player-shared-999';"
    ).fetchone()[0]
    assert count == 2


# ---------------------------------------------------------------------------
# AC-4: Unknown fields are ignored (logged at DEBUG)
# ---------------------------------------------------------------------------


def test_unknown_field_is_ignored_and_load_continues(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-4: Unknown JSON fields do not cause errors; record is loaded normally."""
    players_with_extra = [
        {
            "id": "player-ccc-003",
            "first_name": "Extra",
            "last_name": "Fields",
            "number": "99",
            "avatar_url": "",
            "unknown_future_field": "some_value",
            "another_new_key": 42,
        }
    ]
    path = _write_roster(tmp_path, players_with_extra)
    loader = RosterLoader(db)

    result = loader.load_file(path)

    assert result.loaded == 1
    assert result.skipped == 0
    assert result.errors == 0
    assert "player-ccc-003" in _player_ids(db)


def test_unknown_field_logged_at_debug(
    db: sqlite3.Connection, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-4: Unknown fields are logged at DEBUG level."""
    import logging

    players_with_extra = [
        {
            "id": "player-ddd-004",
            "first_name": "Debug",
            "last_name": "Log",
            "number": "0",
            "avatar_url": "",
            "undocumented_key": "hello",
        }
    ]
    path = _write_roster(tmp_path, players_with_extra)
    loader = RosterLoader(db)

    with caplog.at_level(logging.DEBUG, logger="src.gamechanger.loaders.roster"):
        loader.load_file(path)

    assert "undocumented_key" in caplog.text


# ---------------------------------------------------------------------------
# AC-5: Missing required field causes skip; load continues
# ---------------------------------------------------------------------------


def test_missing_player_id_causes_skip(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-5: A record without 'id' is skipped; good records still load."""
    players = [
        {"first_name": "No", "last_name": "Id", "number": "0", "avatar_url": ""},  # missing id
        {"id": "player-eee-005", "first_name": "Good", "last_name": "Player", "number": "1", "avatar_url": ""},
    ]
    path = _write_roster(tmp_path, players)
    loader = RosterLoader(db)

    result = loader.load_file(path)

    assert result.skipped == 1
    assert result.loaded == 1
    assert result.errors == 0
    assert "player-eee-005" in _player_ids(db)


def test_missing_player_id_error_is_logged(
    db: sqlite3.Connection, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-5: Missing required field is logged at ERROR level with raw data."""
    import logging

    players = [
        {"first_name": "Missing", "last_name": "Id", "number": "0", "avatar_url": ""}
    ]
    path = _write_roster(tmp_path, players)
    loader = RosterLoader(db)

    with caplog.at_level(logging.ERROR, logger="src.gamechanger.loaders.roster"):
        loader.load_file(path)

    assert "id" in caplog.text.lower()


def test_missing_first_name_causes_skip(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-5: A record without 'first_name' is skipped; load continues."""
    players = [
        {"id": "player-fff-006", "last_name": "NoFirstName", "number": "5", "avatar_url": ""},
        {"id": "player-ggg-007", "first_name": "Good", "last_name": "Player", "number": "6", "avatar_url": ""},
    ]
    path = _write_roster(tmp_path, players)
    loader = RosterLoader(db)

    result = loader.load_file(path)

    assert result.skipped == 1
    assert result.loaded == 1


# ---------------------------------------------------------------------------
# AC-6: FK prerequisite rows created automatically
# ---------------------------------------------------------------------------


def test_teams_row_created_automatically(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-6: A teams row is created for the team_id before inserting team_rosters."""
    path = _write_roster(tmp_path, _SAMPLE_PLAYERS)
    loader = RosterLoader(db)

    # No teams row exists yet.
    count_before = db.execute("SELECT COUNT(*) FROM teams;").fetchone()[0]
    assert count_before == 0

    loader.load_file(path)

    row = db.execute(
        "SELECT gc_uuid FROM teams WHERE gc_uuid = ?;", (_TEAM_ID,)
    ).fetchone()
    assert row is not None, f"Expected teams row for {_TEAM_ID}"


def test_seasons_row_created_automatically(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-6: A seasons row is created for the season_id before inserting team_rosters."""
    path = _write_roster(tmp_path, _SAMPLE_PLAYERS)
    loader = RosterLoader(db)

    # No seasons row exists yet.
    count_before = db.execute("SELECT COUNT(*) FROM seasons;").fetchone()[0]
    assert count_before == 0

    loader.load_file(path)

    row = db.execute(
        "SELECT season_id FROM seasons WHERE season_id = ?;", (_SEASON_ID,)
    ).fetchone()
    assert row is not None, f"Expected seasons row for {_SEASON_ID}"


def test_load_succeeds_when_fk_prerequisites_absent(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-6: Loading completes without FK constraint errors even with no pre-existing rows."""
    path = _write_roster(tmp_path, _SAMPLE_PLAYERS)
    loader = RosterLoader(db)

    # FK enforcement is ON; without prerequisite rows this would fail.
    result = loader.load_file(path)

    assert result.errors == 0
    assert result.loaded == len(_SAMPLE_PLAYERS)


def test_existing_team_row_not_overwritten(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-6: If a teams row already exists, _ensure_team_row does not overwrite it."""
    # Pre-insert a teams row with enriched data.
    db.execute(
        "INSERT INTO teams (gc_uuid, name, membership_type, is_active) VALUES (?, ?, 'member', 1);",
        (_TEAM_ID, "Lincoln JV"),
    )
    db.commit()

    path = _write_roster(tmp_path, _SAMPLE_PLAYERS)
    loader = RosterLoader(db)

    loader.load_file(path)

    row = db.execute(
        "SELECT name, membership_type FROM teams WHERE gc_uuid = ?;", (_TEAM_ID,)
    ).fetchone()
    assert row is not None
    # Enriched values should be preserved.
    assert row[0] == "Lincoln JV"
    assert row[1] == "member"  # membership_type stays 'member'


def test_existing_season_row_not_overwritten(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-6: If a seasons row already exists, _ensure_season_row does not overwrite it."""
    db.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, 'Spring 2025 HS', 'spring-hs', 2025);",
        (_SEASON_ID,),
    )
    db.commit()

    path = _write_roster(tmp_path, _SAMPLE_PLAYERS)
    loader = RosterLoader(db)

    loader.load_file(path)

    row = db.execute(
        "SELECT name, season_type FROM seasons WHERE season_id = ?;", (_SEASON_ID,)
    ).fetchone()
    assert row is not None
    assert row[0] == "Spring 2025 HS"
    assert row[1] == "spring-hs"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_roster_file_loads_zero_records(db: sqlite3.Connection, tmp_path: Path) -> None:
    """Empty roster array produces loaded=0 with no errors."""
    path = _write_roster(tmp_path, [])
    loader = RosterLoader(db)

    result = loader.load_file(path)

    assert result.loaded == 0
    assert result.skipped == 0
    assert result.errors == 0


def test_load_result_default_values() -> None:
    """LoadResult initialises all counts to zero by default."""
    result = LoadResult()
    assert result.loaded == 0
    assert result.skipped == 0
    assert result.errors == 0


def test_nonexistent_roster_file_returns_error(db: sqlite3.Connection, tmp_path: Path) -> None:
    """Loading a nonexistent file returns errors=1."""
    path = tmp_path / "2025" / "teams" / "no-team" / "roster.json"
    loader = RosterLoader(db)

    result = loader.load_file(path)

    assert result.errors == 1
    assert result.loaded == 0


def test_avatar_url_empty_string_does_not_cause_error(db: sqlite3.Connection, tmp_path: Path) -> None:
    """avatar_url='' (not null, not absent) does not cause any errors."""
    players = [
        {"id": "player-hhh-008", "first_name": "Avatar", "last_name": "Test", "number": "42", "avatar_url": ""}
    ]
    path = _write_roster(tmp_path, players)
    loader = RosterLoader(db)

    result = loader.load_file(path)

    assert result.loaded == 1
    assert result.errors == 0


def test_path_inference_from_conventional_path(db: sqlite3.Connection, tmp_path: Path) -> None:
    """team_id and season_id are correctly inferred from the path convention."""
    team_id = "specific-team-uuid"
    season = "2026-spring-hs"
    path = _write_roster(tmp_path, _SAMPLE_PLAYERS, team_id=team_id, season=season)
    loader = RosterLoader(db)

    loader.load_file(path)

    # Verify the correct team_id and season_id were used.
    row = db.execute(
        "SELECT team_id, season_id FROM team_rosters WHERE player_id = 'player-aaa-001';"
    ).fetchone()
    assert row is not None
    # team_rosters.team_id is now INTEGER FK -- resolve via gc_uuid lookup
    team_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (team_id,)).fetchone()[0]
    assert row[0] == team_pk
    assert row[1] == season
