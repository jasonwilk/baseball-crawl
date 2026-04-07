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
- AC-5/AC-6 (E-117-02): Full batting fixture covers all 37 new columns
- AC-6 (E-117-02): Exact stored values asserted for every new column
- AC-7 (E-117-02): stat_completeness = 'full' for season_stats_loader rows
- AC-1/AC-5 (E-117-03): Full pitching fixture covers all 38 new pitching columns
- AC-6/AC-7 (E-117-03): Exact stored values for confirmed and optimistic columns
- AC-8 (E-117-03): TB → total_balls mapping verified (pitching context disambiguation)
- AC-9 (E-117-03): stat_completeness = 'full' for pitching rows
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
    """In-memory SQLite connection with the schema applied and FK enforcement on.

    Pre-seeds a team row with ``season_year=2025`` so that
    ``derive_season_id_for_team`` produces the deterministic ``_SEASON_ID``
    value across all tests.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    sql = _MIGRATION_FILE.read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.execute("ALTER TABLE teams ADD COLUMN season_year INTEGER")
    conn.commit()

    # Pre-seed the default team so derive_season_id_for_team returns "2025"
    conn.execute(
        "INSERT INTO teams (gc_uuid, name, membership_type, is_active, season_year) "
        "VALUES (?, ?, 'member', 1, 2025)",
        (_TEAM_ID, _TEAM_ID),
    )
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

# Full offense fixture covering all 47 batting stat columns.
# Values are realistic (non-zero) for the sample required by AC-5.
_OFFENSE_FULL = {
    # Standard (existing 10)
    "GP": 28, "AB": 85, "H": 27, "2B": 6, "3B": 2, "HR": 4,
    "RBI": 18, "BB": 12, "SO": 20, "SB": 7,
    # Standard (22 new)
    "PA": 102,
    "1B": 15,    # singles
    "R": 19,
    "SOL": 8,    # strikeouts looking
    "HBP": 3,
    "SHB": 2,    # sacrifice bunts
    "SHF": 1,    # sacrifice flies
    "GIDP": 2,
    "ROE": 3,
    "FC": 1,
    "CI": 0,
    "PIK": 1,
    "CS": 2,
    "TB": 49,    # total bases
    "XBH": 12,   # extra base hits
    "LOB": 24,
    "3OUTLOB": 6,
    "OB": 42,    # times on base
    "GSHR": 1,   # grand slams
    "2OUTRBI": 7,
    "HRISP": 9,  # hits with RISP
    "ABRISP": 30,
    # Advanced (15 new)
    "QAB": 55,
    "HARD": 11,
    "WEAK": 8,
    "LND": 9,
    "FLB": 14,
    "GB": 22,
    "PS": 310,
    "SW": 60,
    "SM": 15,
    "INP": 45,
    "FULL": 18,
    "2STRIKES": 52,
    "2S+3": 28,
    "6+": 12,
    "LOBB": 4,
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

# Full pitching defense fixture covering all 47 pitching stat columns.
# Values are realistic (non-zero) for the sample required by AC-5.
# Optimistic columns that may not be in the defense section are also included
# to verify correct mapping when they ARE present.
_DEFENSE_PITCHER_FULL = {
    # Existing 9 columns
    "GP:P": 14,
    "IP": 40.0,   # 40 innings = 120 outs
    "H": 32,
    "ER": 14,
    "BB": 18,
    "SO": 55,
    "HR": 3,
    "#P": 620,
    "TS": 390,
    # Confirmed-in-endpoint (15 new)
    "GS": 10,
    "BF": 168,
    "BK": 1,
    "WP": 4,
    "HBP": 5,
    "SVO": 3,
    "SB": 8,
    "CS": 2,
    "GO": 35,
    "AO": 28,
    "LOO": 22,
    "0BBINN": 25,
    "123INN": 12,
    "FPS": 88,
    "LBFPN": 7,
    # Optimistic (23 -- expected in API, may return None in practice for some)
    "GP": None,   # Typically None (lives in general section, not defense)
    "W": 7,
    "L": 4,
    "SV": 2,
    "BS": 1,
    "R": 17,
    "SOL": 18,
    "LOB": 30,
    "PIK": 3,
    "TB": 95,     # CRITICAL: TB in pitching = Total Balls (NOT Total Bases)
    "<3": 42,
    "1ST2OUT": 18,
    "<13": 30,
    "BBS": 6,
    "LOBB": 4,
    "LOBBS": 2,
    "SM": 48,
    "SW": 110,
    "WEAK": 19,
    "HARD": 12,
    "LND": 10,
    "FB": 25,
    "GB": 38,
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

    row = db.execute("SELECT gc_uuid FROM teams WHERE gc_uuid = ?", (_TEAM_ID,)).fetchone()
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
    # Update fixture-seeded team with enriched name
    db.execute("UPDATE teams SET name = 'Lincoln JV' WHERE gc_uuid = ?", (_TEAM_ID,))
    db.commit()
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload({_PLAYER_A: {"stats": {"offense": _OFFENSE_A}}})
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    rows = db.execute("SELECT name FROM teams WHERE gc_uuid = ?", (_TEAM_ID,)).fetchall()
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
    team_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_TEAM_ID,)).fetchone()[0]
    row = db.execute(
        "SELECT ab, h, doubles, triples, hr, rbi, bb, so, sb, gp "
        "FROM player_season_batting WHERE player_id = ? AND team_id = ? AND season_id = ?",
        (_PLAYER_A, team_pk, _SEASON_ID),
    ).fetchone()
    assert row is not None
    ab, h, doubles, triples, hr, rbi, bb, so, sb, gp = row
    assert ab == 60
    assert h == 18
    assert doubles == 4
    assert triples == 1
    assert hr == 2
    assert rbi == 10
    assert bb == 8
    assert so == 12
    assert sb == 3
    assert gp == 20


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
    team_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_TEAM_ID,)).fetchone()[0]
    row = db.execute(
        "SELECT gp_pitcher, ip_outs, h, er, bb, so, hr, pitches, total_strikes "
        "FROM player_season_pitching WHERE player_id = ? AND team_id = ? AND season_id = ?",
        (_PLAYER_A, team_pk, _SEASON_ID),
    ).fetchone()
    assert row is not None
    gp_pitcher, ip_outs, h, er, bb, so, hr, pitches, total_strikes = row
    assert gp_pitcher == 8
    assert ip_outs == 60   # 20.0 * 3
    assert h == 15
    assert er == 7
    assert bb == 6
    assert so == 22
    assert hr == 1
    assert pitches == 300
    assert total_strikes == 200


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

    team_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_TEAM_ID,)).fetchone()[0]
    count = db.execute(
        "SELECT COUNT(*) FROM player_season_batting WHERE player_id = ? AND team_id = ? AND season_id = ?",
        (_PLAYER_A, team_pk, _SEASON_ID),
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
    """A log message is emitted when a player_id is not in the players table."""
    unknown_player = "player-unknown-999"
    payload = _make_stats_payload(
        {unknown_player: {"stats": {"offense": _OFFENSE_A}}}
    )
    path = _write_stats(tmp_path, payload)

    with caplog.at_level(logging.DEBUG, logger="src.db.players"):
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


def test_load_file_infers_team_and_derives_season(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """team_id inferred from path; season_id derived from team metadata."""
    custom_team = "team-varsity-999"
    # Pre-insert a team with HS program and season_year=2026
    db.execute(
        "INSERT OR IGNORE INTO programs (program_id, name, program_type) "
        "VALUES ('lsb-hs', 'Lincoln Standing Bear HS', 'hs')"
    )
    db.execute(
        "INSERT INTO teams (gc_uuid, name, membership_type, is_active, program_id, season_year) "
        "VALUES (?, ?, 'member', 1, 'lsb-hs', 2026)",
        (custom_team, custom_team),
    )
    db.commit()

    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload(
        {_PLAYER_A: {"stats": {"offense": _OFFENSE_A}}},
        team_id=custom_team,
    )
    path = _write_stats(tmp_path, payload, team_id=custom_team, season="2026-spring-hs")

    SeasonStatsLoader(db).load_file(path)

    custom_team_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (custom_team,)).fetchone()[0]
    row = db.execute(
        "SELECT player_id FROM player_season_batting WHERE team_id = ? AND season_id = ?",
        (custom_team_pk, "2026-spring-hs"),
    ).fetchone()
    assert row is not None
    assert row[0] == _PLAYER_A


# ---------------------------------------------------------------------------
# E-117-02: Expanded batting column tests (AC-5, AC-6, AC-7)
# ---------------------------------------------------------------------------

def test_batting_expansion_all_standard_new_columns_stored(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-6: Every newly added standard batting column stores the exact expected value."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload({_PLAYER_A: {"stats": {"offense": _OFFENSE_FULL}}})
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    row = db.execute(
        """
        SELECT
            pa, singles, r, sol, hbp, shb, shf, gidp, roe, fc, ci, pik, cs,
            tb, xbh, lob, three_out_lob, ob, gshr, two_out_rbi, hrisp, abrisp
        FROM player_season_batting WHERE player_id = ?
        """,
        (_PLAYER_A,),
    ).fetchone()
    assert row is not None
    (
        pa, singles, r, sol, hbp, shb, shf, gidp, roe, fc, ci, pik, cs,
        tb, xbh, lob, three_out_lob, ob, gshr, two_out_rbi, hrisp, abrisp,
    ) = row
    assert pa == 102
    assert singles == 15
    assert r == 19
    assert sol == 8
    assert hbp == 3
    assert shb == 2
    assert shf == 1
    assert gidp == 2
    assert roe == 3
    assert fc == 1
    assert ci == 0
    assert pik == 1
    assert cs == 2
    assert tb == 49
    assert xbh == 12
    assert lob == 24
    assert three_out_lob == 6
    assert ob == 42
    assert gshr == 1
    assert two_out_rbi == 7
    assert hrisp == 9
    assert abrisp == 30


def test_batting_expansion_all_advanced_columns_stored(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-6: Every newly added advanced batting column stores the exact expected value."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload({_PLAYER_A: {"stats": {"offense": _OFFENSE_FULL}}})
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    row = db.execute(
        """
        SELECT qab, hard, weak, lnd, flb, gb, ps, sw, sm, inp, full,
               two_strikes, two_s_plus_3, six_plus, lobb
        FROM player_season_batting WHERE player_id = ?
        """,
        (_PLAYER_A,),
    ).fetchone()
    assert row is not None
    qab, hard, weak, lnd, flb, gb, ps, sw, sm, inp, full, two_strikes, two_s_plus_3, six_plus, lobb = row
    assert qab == 55
    assert hard == 11
    assert weak == 8
    assert lnd == 9
    assert flb == 14
    assert gb == 22
    assert ps == 310
    assert sw == 60
    assert sm == 15
    assert inp == 45
    assert full == 18
    assert two_strikes == 52
    assert two_s_plus_3 == 28
    assert six_plus == 12
    assert lobb == 4


def test_batting_expansion_stat_completeness_is_full(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-7: Rows upserted by season_stats_loader have stat_completeness = 'full'."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload({_PLAYER_A: {"stats": {"offense": _OFFENSE_FULL}}})
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    row = db.execute(
        "SELECT stat_completeness FROM player_season_batting WHERE player_id = ?",
        (_PLAYER_A,),
    ).fetchone()
    assert row is not None
    assert row[0] == "full"


def test_batting_expansion_stat_completeness_full_on_minimal_offense(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-7: stat_completeness = 'full' even when only a few fields are present."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload({_PLAYER_A: {"stats": {"offense": _OFFENSE_A}}})
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    row = db.execute(
        "SELECT stat_completeness FROM player_season_batting WHERE player_id = ?",
        (_PLAYER_A,),
    ).fetchone()
    assert row is not None
    assert row[0] == "full"


def test_batting_expansion_upsert_overwrites_completeness(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-7: ON CONFLICT UPDATE also sets stat_completeness = 'full'."""
    _seed_player(db, _PLAYER_A)
    # Manually insert a row with boxscore_only completeness.
    team_pk = db.execute(
        "SELECT id FROM teams WHERE gc_uuid = ?", (_TEAM_ID,)
    ).fetchone()[0]
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES (?, ?, 'unknown', 2025)",
        (_SEASON_ID, _SEASON_ID),
    )
    db.execute(
        "INSERT INTO player_season_batting (player_id, team_id, season_id, stat_completeness, ab) "
        "VALUES (?, ?, ?, 'boxscore_only', 40)",
        (_PLAYER_A, team_pk, _SEASON_ID),
    )
    db.commit()

    payload = _make_stats_payload({_PLAYER_A: {"stats": {"offense": _OFFENSE_FULL}}})
    path = _write_stats(tmp_path, payload)
    SeasonStatsLoader(db).load_file(path)

    row = db.execute(
        "SELECT stat_completeness FROM player_season_batting WHERE player_id = ?",
        (_PLAYER_A,),
    ).fetchone()
    assert row[0] == "full"


def test_batting_expansion_absent_fields_stored_as_null(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-5 edge case: New columns absent from offense dict are stored as NULL."""
    _seed_player(db, _PLAYER_A)
    # Minimal offense with only existing fields -- all new columns absent.
    payload = _make_stats_payload({_PLAYER_A: {"stats": {"offense": _OFFENSE_A}}})
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    row = db.execute(
        "SELECT pa, singles, r, sol, qab, hard, lnd, flb, two_strikes FROM player_season_batting WHERE player_id = ?",
        (_PLAYER_A,),
    ).fetchone()
    assert row is not None
    # All new columns should be NULL because _OFFENSE_A doesn't include them.
    assert all(v is None for v in row), f"Expected all NULL but got: {row}"


# ---------------------------------------------------------------------------
# E-117-03: Expanded pitching column tests (AC-1 through AC-10)
# ---------------------------------------------------------------------------

def test_pitching_expansion_confirmed_columns_stored(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-6: Every newly added confirmed-in-endpoint pitching column stores the exact expected value."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload(
        {_PLAYER_A: {"stats": {"defense": _DEFENSE_PITCHER_FULL}}}
    )
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    row = db.execute(
        """
        SELECT gs, bf, bk, wp, hbp, svo, sb, cs, go, ao,
               loo, zero_bb_inn, inn_123, fps, lbfpn
        FROM player_season_pitching WHERE player_id = ?
        """,
        (_PLAYER_A,),
    ).fetchone()
    assert row is not None
    gs, bf, bk, wp, hbp, svo, sb, cs, go, ao, loo, zero_bb_inn, inn_123, fps, lbfpn = row
    assert gs == 10
    assert bf == 168
    assert bk == 1
    assert wp == 4
    assert hbp == 5
    assert svo == 3
    assert sb == 8
    assert cs == 2
    assert go == 35
    assert ao == 28
    assert loo == 22
    assert zero_bb_inn == 25
    assert inn_123 == 12
    assert fps == 88
    assert lbfpn == 7


def test_pitching_expansion_optimistic_columns_stored(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-7: Every newly added optimistic pitching column stores the exact expected value."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload(
        {_PLAYER_A: {"stats": {"defense": _DEFENSE_PITCHER_FULL}}}
    )
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    row = db.execute(
        """
        SELECT w, l, sv, bs, r, sol, lob, pik,
               lt_3, first_2_out, lt_13, bbs, lobb, lobbs,
               sm, sw, weak, hard, lnd, fb, gb
        FROM player_season_pitching WHERE player_id = ?
        """,
        (_PLAYER_A,),
    ).fetchone()
    assert row is not None
    (
        w, l, sv, bs, r, sol, lob, pik,
        lt_3, first_2_out, lt_13, bbs, lobb, lobbs,
        sm, sw, weak, hard, lnd, fb, gb,
    ) = row
    assert w == 7
    assert l == 4
    assert sv == 2
    assert bs == 1
    assert r == 17
    assert sol == 18
    assert lob == 30
    assert pik == 3
    assert lt_3 == 42
    assert first_2_out == 18
    assert lt_13 == 30
    assert bbs == 6
    assert lobb == 4
    assert lobbs == 2
    assert sm == 48
    assert sw == 110
    assert weak == 19
    assert hard == 12
    assert lnd == 10
    assert fb == 25
    assert gb == 38


def test_pitching_expansion_tb_maps_to_total_balls(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-8: TB in pitching defense maps to total_balls, NOT tb (Total Balls, not Total Bases)."""
    _seed_player(db, _PLAYER_A)
    defense = dict(_DEFENSE_PITCHER_FULL)
    defense["TB"] = 95  # total balls thrown

    payload = _make_stats_payload(
        {_PLAYER_A: {"stats": {"defense": defense}}}
    )
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    row = db.execute(
        "SELECT total_balls FROM player_season_pitching WHERE player_id = ?",
        (_PLAYER_A,),
    ).fetchone()
    assert row is not None
    assert row[0] == 95


def test_pitching_expansion_gp_is_null_when_absent_from_defense(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-7 null case: gp column is NULL when GP is absent from the defense dict (lives in general section)."""
    _seed_player(db, _PLAYER_A)
    # Use a defense fixture that has GP=None (simulating real API behavior).
    defense = dict(_DEFENSE_PITCHER_FULL)
    assert defense.get("GP") is None  # fixture sets GP=None

    payload = _make_stats_payload(
        {_PLAYER_A: {"stats": {"defense": defense}}}
    )
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    row = db.execute(
        "SELECT gp FROM player_season_pitching WHERE player_id = ?",
        (_PLAYER_A,),
    ).fetchone()
    assert row is not None
    assert row[0] is None


def test_pitching_expansion_stat_completeness_is_full(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-9: Pitching rows upserted by season_stats_loader have stat_completeness = 'full'."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload(
        {_PLAYER_A: {"stats": {"defense": _DEFENSE_PITCHER_FULL}}}
    )
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    row = db.execute(
        "SELECT stat_completeness FROM player_season_pitching WHERE player_id = ?",
        (_PLAYER_A,),
    ).fetchone()
    assert row is not None
    assert row[0] == "full"


def test_pitching_expansion_stat_completeness_full_on_minimal_defense(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-9: stat_completeness = 'full' even with the minimal defense fixture."""
    _seed_player(db, _PLAYER_A)
    payload = _make_stats_payload(
        {_PLAYER_A: {"stats": {"defense": _DEFENSE_PITCHER}}}
    )
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    row = db.execute(
        "SELECT stat_completeness FROM player_season_pitching WHERE player_id = ?",
        (_PLAYER_A,),
    ).fetchone()
    assert row is not None
    assert row[0] == "full"


def test_pitching_expansion_absent_optimistic_fields_are_null(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-7 null case: Optimistic columns absent from defense dict are stored as NULL."""
    _seed_player(db, _PLAYER_A)
    # Use the minimal defense fixture -- no optimistic fields present.
    payload = _make_stats_payload(
        {_PLAYER_A: {"stats": {"defense": _DEFENSE_PITCHER}}}
    )
    path = _write_stats(tmp_path, payload)

    SeasonStatsLoader(db).load_file(path)

    row = db.execute(
        "SELECT w, l, sv, r, sol, sm, sw, weak, hard, lnd, fb, gb, total_balls "
        "FROM player_season_pitching WHERE player_id = ?",
        (_PLAYER_A,),
    ).fetchone()
    assert row is not None
    assert all(v is None for v in row), f"Expected all NULL but got: {row}"
