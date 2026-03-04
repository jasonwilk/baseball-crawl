"""Tests for src/gamechanger/loaders/season_stats_loader.py.

Uses an in-memory SQLite database with the real schema applied.
No network calls are made.

Tests cover:
- AC-1: Batting stats upserted into player_season_batting
- AC-1: Pitching stats upserted into player_season_pitching
- AC-2: Idempotent -- loading same file twice produces same state
- AC-3: Returns a LoadResult
- AC-4: Missing player gets stub row (Unknown/Unknown) + WARNING log
- AC-5: Position player (no defense) -> only batting row; pitcher-only -> only pitching row
- AC-6: FK prerequisites (teams, seasons rows) created automatically
- IP float -> ip_outs integer conversion
- Empty players dict loads cleanly (zero records)
- Malformed file returns LoadResult(errors=1)
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

import pytest

from src.gamechanger.loaders import LoadResult
from src.gamechanger.loaders.season_stats_loader import SeasonStatsLoader, _ip_to_ip_outs


# ---------------------------------------------------------------------------
# Schema fixture
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MIGRATION_FILE = _PROJECT_ROOT / "migrations" / "001_initial_schema.sql"


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory SQLite connection with the schema applied and FK enforcement on."""
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
_PLAYER_A = "player-aaa-uuid-001"
_PLAYER_B = "player-bbb-uuid-002"

_OFFENSE_A = {
    "GP": 20, "AB": 60, "H": 18, "2B": 4, "3B": 1, "HR": 2,
    "RBI": 10, "BB": 8, "SO": 12, "SB": 3,
}

_DEFENSE_PITCHER = {
    "GP:P": 8,
    "IP": 20.0,   # 20 whole innings = 60 outs
    "H": 15,
    "ER": 7,
    "BB": 6,
    "SO": 22,
    "HR": 1,
    "#P": 300,
    "TS": 200,
}

_DEFENSE_FIELDER = {
    "GP:P": 0,    # not a pitcher
    "GP:F": 18,
    "PO": 30,
    "A": 5,
    "E": 1,
}


def _make_stats_payload(
    players: dict,
    team_id: str = _TEAM_ID,
) -> dict:
    """Build a stats.json payload matching the season-stats API shape."""
    return {
        "id": team_id,
        "team_id": team_id,
        "stats_data": {
            "players": players,
            "streaks": {},
            "stats": {},
        },
    }


def _write_stats(
    tmp_path: Path,
    payload: dict,
    team_id: str = _TEAM_ID,
    season: str = _SEASON_ID,
) -> Path:
    """Write stats.json at the conventional path."""
    dest = tmp_path / season / "teams" / team_id / "stats.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload), encoding="utf-8")
    return dest


def _seed_player(conn: sqlite3.Connection, player_id: str, first: str = "Jake", last: str = "Smith") -> None:
    """Insert a player row to satisfy FK before inserting stats."""
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (player_id, first, last),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# _ip_to_ip_outs unit tests
# ---------------------------------------------------------------------------

def test_ip_to_ip_outs_whole_innings() -> None:
    """Whole innings convert cleanly: 6 IP = 18 outs."""
    assert _ip_to_ip_outs(6.0) == 18


def test_ip_to_ip_outs_fractional_innings() -> None:
    """Fractional innings: 6.333... IP = 19 outs (6 and 1 third)."""
    assert _ip_to_ip_outs(6 + 1 / 3) == 19


def test_ip_to_ip_outs_two_thirds() -> None:
    """6.666... IP = 20 outs (6 and 2 thirds)."""
    assert _ip_to_ip_outs(6 + 2 / 3) == 20


def test_ip_to_ip_outs_zero() -> None:
    """Zero IP = 0 outs."""
    assert _ip_to_ip_outs(0) == 0


def test_ip_to_ip_outs_none_returns_none() -> None:
    """None input returns None."""
    assert _ip_to_ip_outs(None) is None


# ---------------------------------------------------------------------------
# AC-6: FK prerequisite rows created
# ---------------------------------------------------------------------------

def test_load_file_creates_teams_row(db: sqlite3.Connection, tmp_path: Path) -> None:
    """teams row is created for team_id if not already present."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload({_PLAYER_A: {"stats": {"offense": _OFFENSE_A}}})
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    row = db.execute("SELECT team_id FROM teams WHERE team_id = ?", (_TEAM_ID,)).fetchone()
    assert row is not None


def test_load_file_creates_seasons_row(db: sqlite3.Connection, tmp_path: Path) -> None:
    """seasons row is created for season_id if not already present."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload({_PLAYER_A: {"stats": {"offense": _OFFENSE_A}}})
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    row = db.execute("SELECT season_id FROM seasons WHERE season_id = ?", (_SEASON_ID,)).fetchone()
    assert row is not None


def test_load_file_does_not_duplicate_existing_teams_row(db: sqlite3.Connection, tmp_path: Path) -> None:
    """Existing teams row is not modified or duplicated."""
    db.execute(
        "INSERT INTO teams (team_id, name, is_owned) VALUES (?, 'Lincoln JV', 1)",
        (_TEAM_ID,),
    )
    db.commit()
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload({_PLAYER_A: {"stats": {"offense": _OFFENSE_A}}})
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    rows = db.execute("SELECT name FROM teams WHERE team_id = ?", (_TEAM_ID,)).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "Lincoln JV"  # original name preserved


# ---------------------------------------------------------------------------
# AC-1: Batting stats upserted
# ---------------------------------------------------------------------------

def test_load_file_upserts_batting_row(db: sqlite3.Connection, tmp_path: Path) -> None:
    """A player with offense stats gets a row in player_season_batting."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload({_PLAYER_A: {"stats": {"offense": _OFFENSE_A}}})
    path = _write_stats(tmp_path, payload)

    result = SeasonStatsLoader(db).load_file(path)

    assert result.loaded == 1
    row = db.execute(
        "SELECT ab, h, doubles, triples, hr, rbi, bb, so, sb, games "
        "FROM player_season_batting WHERE player_id = ? AND team_id = ? AND season_id = ?",
        (_PLAYER_A, _TEAM_ID, _SEASON_ID),
    ).fetchone()
    assert row is not None
    ab, h, doubles, triples, hr, rbi, bb, so, sb, games = row
    assert ab == 60
    assert h == 18
    assert doubles == 4
    assert triples == 1
    assert hr == 2
    assert rbi == 10
    assert bb == 8
    assert so == 12
    assert sb == 3
    assert games == 20


def test_load_file_batting_split_columns_are_null(db: sqlite3.Connection, tmp_path: Path) -> None:
    """All split columns (home/away, vs LHP/RHP) remain NULL."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload({_PLAYER_A: {"stats": {"offense": _OFFENSE_A}}})
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    row = db.execute(
        "SELECT home_ab, home_h, away_ab, vs_lhp_ab, vs_rhp_ab "
        "FROM player_season_batting WHERE player_id = ?",
        (_PLAYER_A,),
    ).fetchone()
    assert row == (None, None, None, None, None)


# ---------------------------------------------------------------------------
# AC-1: Pitching stats upserted
# ---------------------------------------------------------------------------

def test_load_file_upserts_pitching_row(db: sqlite3.Connection, tmp_path: Path) -> None:
    """A player with pitching defense stats gets a row in player_season_pitching."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload(
        {_PLAYER_A: {"stats": {"offense": _OFFENSE_A, "defense": _DEFENSE_PITCHER}}}
    )
    path = _write_stats(tmp_path, payload)

    result = SeasonStatsLoader(db).load_file(path)

    assert result.loaded == 2  # 1 batting + 1 pitching
    row = db.execute(
        "SELECT games, ip_outs, h, er, bb, so, hr, pitches, strikes "
        "FROM player_season_pitching WHERE player_id = ? AND team_id = ? AND season_id = ?",
        (_PLAYER_A, _TEAM_ID, _SEASON_ID),
    ).fetchone()
    assert row is not None
    games, ip_outs, h, er, bb, so, hr, pitches, strikes = row
    assert games == 8
    assert ip_outs == 60   # 20.0 * 3
    assert h == 15
    assert er == 7
    assert bb == 6
    assert so == 22
    assert hr == 1
    assert pitches == 300
    assert strikes == 200


def test_load_file_ip_fractional_conversion(db: sqlite3.Connection, tmp_path: Path) -> None:
    """IP = 6.333... is stored as 19 ip_outs."""
    _seed_player(db, _PLAYER_A)
    defense = dict(_DEFENSE_PITCHER)
    defense["IP"] = 6 + 1 / 3  # 6.333... = 19 outs
    payload = _make_stats_payload(
        {_PLAYER_A: {"stats": {"defense": defense}}}
    )
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    row = db.execute(
        "SELECT ip_outs FROM player_season_pitching WHERE player_id = ?",
        (_PLAYER_A,),
    ).fetchone()
    assert row is not None
    assert row[0] == 19


def test_load_file_pitching_split_columns_are_null(db: sqlite3.Connection, tmp_path: Path) -> None:
    """All pitching split columns (home/away, vs LHB/RHB) remain NULL."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload(
        {_PLAYER_A: {"stats": {"defense": _DEFENSE_PITCHER}}}
    )
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    row = db.execute(
        "SELECT home_ip_outs, away_ip_outs, vs_lhb_ab, vs_rhb_ab "
        "FROM player_season_pitching WHERE player_id = ?",
        (_PLAYER_A,),
    ).fetchone()
    assert row == (None, None, None, None)


# ---------------------------------------------------------------------------
# AC-2: Idempotency
# ---------------------------------------------------------------------------

def test_load_file_is_idempotent_batting(db: sqlite3.Connection, tmp_path: Path) -> None:
    """Loading same stats.json twice produces exactly one batting row."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload({_PLAYER_A: {"stats": {"offense": _OFFENSE_A}}})
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)
    SeasonStatsLoader(db).load_file(path)

    count = db.execute(
        "SELECT COUNT(*) FROM player_season_batting WHERE player_id = ? AND team_id = ? AND season_id = ?",
        (_PLAYER_A, _TEAM_ID, _SEASON_ID),
    ).fetchone()[0]
    assert count == 1


def test_load_file_is_idempotent_pitching(db: sqlite3.Connection, tmp_path: Path) -> None:
    """Loading same stats.json twice produces exactly one pitching row."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload(
        {_PLAYER_A: {"stats": {"defense": _DEFENSE_PITCHER}}}
    )
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)
    SeasonStatsLoader(db).load_file(path)

    count = db.execute(
        "SELECT COUNT(*) FROM player_season_pitching WHERE player_id = ?",
        (_PLAYER_A,),
    ).fetchone()[0]
    assert count == 1


def test_load_file_upsert_updates_values_on_reload(db: sqlite3.Connection, tmp_path: Path) -> None:
    """Second load with updated stats overwrites the first."""
    _seed_player(db, _PLAYER_A)
    payload1 = _make_stats_payload(
        {_PLAYER_A: {"stats": {"offense": {**_OFFENSE_A, "AB": 60}}}}
    )
    payload2 = _make_stats_payload(
        {_PLAYER_A: {"stats": {"offense": {**_OFFENSE_A, "AB": 75}}}}
    )
    path = _write_stats(tmp_path, payload1)
    SeasonStatsLoader(db).load_file(path)

    path.write_text(json.dumps(payload2), encoding="utf-8")
    SeasonStatsLoader(db).load_file(path)

    ab = db.execute(
        "SELECT ab FROM player_season_batting WHERE player_id = ?", (_PLAYER_A,)
    ).fetchone()[0]
    assert ab == 75


# ---------------------------------------------------------------------------
# AC-3: Returns LoadResult
# ---------------------------------------------------------------------------

def test_load_file_returns_load_result(db: sqlite3.Connection, tmp_path: Path) -> None:
    """load_file returns a LoadResult instance."""
    payload = _make_stats_payload({})
    path = _write_stats(tmp_path, payload)

    result = SeasonStatsLoader(db).load_file(path)

    assert isinstance(result, LoadResult)


def test_load_file_result_counts_multiple_players(db: sqlite3.Connection, tmp_path: Path) -> None:
    """LoadResult.loaded sums across all players."""
    _seed_player(db, _PLAYER_A)
    _seed_player(db, _PLAYER_B)
    payload = _make_stats_payload({
        _PLAYER_A: {"stats": {"offense": _OFFENSE_A}},
        _PLAYER_B: {"stats": {"offense": _OFFENSE_A}},
    })
    path = _write_stats(tmp_path, payload)

    result = SeasonStatsLoader(db).load_file(path)

    assert result.loaded == 2
    assert result.errors == 0


# ---------------------------------------------------------------------------
# AC-4: Missing player -> stub row + WARNING log
# ---------------------------------------------------------------------------

def test_load_file_inserts_stub_for_unknown_player(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """A player_id not in players table gets a stub row (Unknown/Unknown)."""
    unknown_player = "player-unknown-999"
    # Do NOT seed the player -- loader must create the stub.
    payload = _make_stats_payload(
        {unknown_player: {"stats": {"offense": _OFFENSE_A}}}
    )
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    row = db.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?",
        (unknown_player,),
    ).fetchone()
    assert row is not None
    assert row[0] == "Unknown"
    assert row[1] == "Unknown"


def test_load_file_logs_warning_for_unknown_player(
    db: sqlite3.Connection, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A WARNING is logged when a player_id is not in the players table."""
    unknown_player = "player-unknown-999"
    payload = _make_stats_payload(
        {unknown_player: {"stats": {"offense": _OFFENSE_A}}}
    )
    path = _write_stats(tmp_path, payload)

    with caplog.at_level(logging.WARNING, logger="src.gamechanger.loaders.season_stats_loader"):
        SeasonStatsLoader(db).load_file(path)

    assert unknown_player in caplog.text


def test_load_file_stub_row_not_created_for_known_player(
    db: sqlite3.Connection, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """No stub is inserted and no WARNING logged for a known player."""
    _seed_player(db, _PLAYER_A, "Jake", "Smith")
    payload = _make_stats_payload({_PLAYER_A: {"stats": {"offense": _OFFENSE_A}}})
    path = _write_stats(tmp_path, payload)

    with caplog.at_level(logging.WARNING, logger="src.gamechanger.loaders.season_stats_loader"):
        SeasonStatsLoader(db).load_file(path)

    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 0

    row = db.execute(
        "SELECT first_name FROM players WHERE player_id = ?", (_PLAYER_A,)
    ).fetchone()
    assert row[0] == "Jake"  # original name preserved, not overwritten by stub


# ---------------------------------------------------------------------------
# AC-5: Position player / pitcher-only
# ---------------------------------------------------------------------------

def test_load_file_position_player_only_batting_row(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """A position player (defense present but GP:P=0) gets only a batting row."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload(
        {_PLAYER_A: {"stats": {"offense": _OFFENSE_A, "defense": _DEFENSE_FIELDER}}}
    )
    path = _write_stats(tmp_path, payload)

    result = SeasonStatsLoader(db).load_file(path)

    # Only 1 row (batting only, no pitching)
    assert result.loaded == 1
    batting = db.execute(
        "SELECT 1 FROM player_season_batting WHERE player_id = ?", (_PLAYER_A,)
    ).fetchone()
    pitching = db.execute(
        "SELECT 1 FROM player_season_pitching WHERE player_id = ?", (_PLAYER_A,)
    ).fetchone()
    assert batting is not None
    assert pitching is None


def test_load_file_pitcher_only_only_pitching_row(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """A pitcher with no offense stats gets only a pitching row."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload(
        {_PLAYER_A: {"stats": {"defense": _DEFENSE_PITCHER}}}
    )
    path = _write_stats(tmp_path, payload)

    result = SeasonStatsLoader(db).load_file(path)

    assert result.loaded == 1
    batting = db.execute(
        "SELECT 1 FROM player_season_batting WHERE player_id = ?", (_PLAYER_A,)
    ).fetchone()
    pitching = db.execute(
        "SELECT 1 FROM player_season_pitching WHERE player_id = ?", (_PLAYER_A,)
    ).fetchone()
    assert batting is None
    assert pitching is not None


def test_load_file_two_way_player_both_rows(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """A two-way player (offense + pitching defense) gets both rows."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload(
        {_PLAYER_A: {"stats": {"offense": _OFFENSE_A, "defense": _DEFENSE_PITCHER}}}
    )
    path = _write_stats(tmp_path, payload)

    result = SeasonStatsLoader(db).load_file(path)

    assert result.loaded == 2
    batting = db.execute(
        "SELECT 1 FROM player_season_batting WHERE player_id = ?", (_PLAYER_A,)
    ).fetchone()
    pitching = db.execute(
        "SELECT 1 FROM player_season_pitching WHERE player_id = ?", (_PLAYER_A,)
    ).fetchone()
    assert batting is not None
    assert pitching is not None


def test_load_file_player_with_no_offense_or_pitching_skipped(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """A player entry with no offense or pitching defense is skipped."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload(
        {_PLAYER_A: {"stats": {"defense": _DEFENSE_FIELDER}}}
    )
    path = _write_stats(tmp_path, payload)

    result = SeasonStatsLoader(db).load_file(path)

    # No rows in either table; counts as skipped
    assert result.loaded == 0
    assert result.skipped == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_load_file_empty_players_dict(db: sqlite3.Connection, tmp_path: Path) -> None:
    """An empty stats_data.players dict loads without error."""
    payload = _make_stats_payload({})
    path = _write_stats(tmp_path, payload)

    result = SeasonStatsLoader(db).load_file(path)

    assert result.loaded == 0
    assert result.errors == 0


def test_load_file_missing_file_returns_error(db: sqlite3.Connection, tmp_path: Path) -> None:
    """A missing stats.json returns LoadResult(errors=1)."""
    missing = tmp_path / "nonexistent" / "stats.json"

    result = SeasonStatsLoader(db).load_file(missing)

    assert result.errors == 1
    assert result.loaded == 0


def test_load_file_malformed_json_returns_error(db: sqlite3.Connection, tmp_path: Path) -> None:
    """Malformed JSON returns LoadResult(errors=1)."""
    path = tmp_path / _SEASON_ID / "teams" / _TEAM_ID / "stats.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not valid json", encoding="utf-8")

    result = SeasonStatsLoader(db).load_file(path)

    assert result.errors == 1


def test_load_file_wrong_type_json_returns_error(db: sqlite3.Connection, tmp_path: Path) -> None:
    """A JSON array (not object) at top level returns LoadResult(errors=1)."""
    path = tmp_path / _SEASON_ID / "teams" / _TEAM_ID / "stats.json"
    path.parent.mkdir(parents=True)
    path.write_text("[]", encoding="utf-8")

    result = SeasonStatsLoader(db).load_file(path)

    assert result.errors == 1


def test_load_file_missing_optional_batting_fields(db: sqlite3.Connection, tmp_path: Path) -> None:
    """Batting rows load even when optional fields (2B, 3B, etc.) are absent."""
    _seed_player(db, _PLAYER_A)
    minimal_offense = {"GP": 5, "AB": 10, "H": 3}  # missing 2B, 3B, HR, etc.
    payload = _make_stats_payload(
        {_PLAYER_A: {"stats": {"offense": minimal_offense}}}
    )
    path = _write_stats(tmp_path, payload)

    result = SeasonStatsLoader(db).load_file(path)

    assert result.loaded == 1
    row = db.execute(
        "SELECT ab, doubles, hr FROM player_season_batting WHERE player_id = ?",
        (_PLAYER_A,),
    ).fetchone()
    assert row[0] == 10
    assert row[1] is None  # 2B absent -> NULL
    assert row[2] is None  # HR absent -> NULL


def test_load_file_infers_team_and_season_from_path(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """team_id and season_id are correctly inferred from the file path."""
    custom_team = "team-varsity-999"
    custom_season = "2026-spring-hs"
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload(
        {_PLAYER_A: {"stats": {"offense": _OFFENSE_A}}},
        team_id=custom_team,
    )
    path = _write_stats(tmp_path, payload, team_id=custom_team, season=custom_season)

    SeasonStatsLoader(db).load_file(path)

    row = db.execute(
        "SELECT player_id FROM player_season_batting WHERE team_id = ? AND season_id = ?",
        (custom_team, custom_season),
    ).fetchone()
    assert row is not None
    assert row[0] == _PLAYER_A
