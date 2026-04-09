"""Tests for scripts/backfill_appearance_order.py.

Uses an in-memory SQLite database with the full schema applied.
No real network calls, no production DB writes.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from src.gamechanger.loaders.backfill import (
    backfill_appearance_order,
    parse_pitcher_order_for_team,
    resolve_boxscore_path,
)

# ---------------------------------------------------------------------------
# Schema fixture
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_MIGRATION_FILE = _PROJECT_ROOT / "migrations" / "001_initial_schema.sql"


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory SQLite with schema + appearance_order column."""
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

_SEASON_ID = "2025"
_GAME_ID = "event-aaa-001"
_GAME_STREAM_ID = "stream-bbb-002"
_TEAM_GC_UUID = "team-uuid-jv-001"
_TEAM_PUBLIC_ID = "y24fFdnr3RAN"
_PITCHER_1 = "pitcher-001"
_PITCHER_2 = "pitcher-002"
_PITCHER_3 = "pitcher-003"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_team(db: sqlite3.Connection, gc_uuid: str = _TEAM_GC_UUID, public_id: str = _TEAM_PUBLIC_ID) -> int:
    cur = db.execute(
        "INSERT INTO teams (gc_uuid, public_id, name, membership_type, is_active) "
        "VALUES (?, ?, ?, 'member', 1)",
        (gc_uuid, public_id, gc_uuid),
    )
    return cur.lastrowid


def _insert_game(
    db: sqlite3.Connection,
    game_id: str = _GAME_ID,
    season_id: str = _SEASON_ID,
    game_stream_id: str | None = _GAME_STREAM_ID,
    home_team_id: int = 1,
    away_team_id: int = 1,
) -> None:
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
        (season_id, season_id, "spring-hs", 2025),
    )
    db.execute(
        "INSERT INTO games (game_id, season_id, game_date, status, game_stream_id, home_team_id, away_team_id) "
        "VALUES (?, ?, '2025-05-10', 'completed', ?, ?, ?)",
        (game_id, season_id, game_stream_id, home_team_id, away_team_id),
    )


def _insert_player(db: sqlite3.Connection, player_id: str) -> None:
    db.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, 'Test', 'Player')",
        (player_id,),
    )


def _insert_pitching_row(db: sqlite3.Connection, game_id: str, player_id: str, team_id: int, appearance_order: int | None = None) -> None:
    _insert_player(db, player_id)
    db.execute(
        "INSERT INTO player_game_pitching (game_id, player_id, team_id, perspective_team_id, ip_outs, appearance_order) "
        "VALUES (?, ?, ?, ?, 9, ?)",
        (game_id, player_id, team_id, team_id, appearance_order),
    )


def _make_boxscore(team_key: str, pitcher_ids: list[str]) -> dict:
    """Build a minimal boxscore dict with pitching stats in order."""
    return {
        team_key: {
            "players": [],
            "groups": [
                {
                    "category": "pitching",
                    "team_stats": {},
                    "extra": [],
                    "stats": [
                        {"player_id": pid, "stats": {"IP": 3}}
                        for pid in pitcher_ids
                    ],
                },
            ],
        },
    }


# ---------------------------------------------------------------------------
# parse_pitcher_order_for_team tests
# ---------------------------------------------------------------------------


def test_parse_pitcher_order_by_public_id() -> None:
    boxscore = _make_boxscore("y24fFdnr3RAN", [_PITCHER_1, _PITCHER_2])
    result = parse_pitcher_order_for_team(boxscore, gc_uuid=None, public_id="y24fFdnr3RAN")
    assert result == [_PITCHER_1, _PITCHER_2]


def test_parse_pitcher_order_by_gc_uuid() -> None:
    boxscore = _make_boxscore("abc-def-123", [_PITCHER_1, _PITCHER_3])
    result = parse_pitcher_order_for_team(boxscore, gc_uuid="abc-def-123", public_id=None)
    assert result == [_PITCHER_1, _PITCHER_3]


def test_parse_pitcher_order_team_not_found() -> None:
    boxscore = _make_boxscore("other-key", [_PITCHER_1])
    result = parse_pitcher_order_for_team(boxscore, gc_uuid="no-match", public_id="no-match")
    assert result is None


def test_parse_pitcher_order_no_pitching_group() -> None:
    boxscore = {
        "team-key": {
            "players": [],
            "groups": [{"category": "lineup", "stats": []}],
        },
    }
    result = parse_pitcher_order_for_team(boxscore, gc_uuid="team-key", public_id=None)
    assert result is None


# ---------------------------------------------------------------------------
# resolve_boxscore_path tests
# ---------------------------------------------------------------------------


def test_resolve_member_path(tmp_path: Path) -> None:
    game_file = tmp_path / _SEASON_ID / "teams" / _TEAM_GC_UUID / "games" / f"{_GAME_ID}.json"
    game_file.parent.mkdir(parents=True, exist_ok=True)
    game_file.write_text("{}")

    result = resolve_boxscore_path(_SEASON_ID, _GAME_ID, _GAME_STREAM_ID, _TEAM_GC_UUID, _TEAM_PUBLIC_ID, data_root=tmp_path)
    assert result == game_file


def test_resolve_member_path_by_stream_id(tmp_path: Path) -> None:
    game_file = tmp_path / _SEASON_ID / "teams" / _TEAM_GC_UUID / "games" / f"{_GAME_STREAM_ID}.json"
    game_file.parent.mkdir(parents=True, exist_ok=True)
    game_file.write_text("{}")

    result = resolve_boxscore_path(_SEASON_ID, _GAME_ID, _GAME_STREAM_ID, _TEAM_GC_UUID, _TEAM_PUBLIC_ID, data_root=tmp_path)
    assert result == game_file


def test_resolve_scouting_path(tmp_path: Path) -> None:
    scout_file = tmp_path / _SEASON_ID / "scouting" / _TEAM_PUBLIC_ID / "boxscores" / f"{_GAME_STREAM_ID}.json"
    scout_file.parent.mkdir(parents=True, exist_ok=True)
    scout_file.write_text("{}")

    result = resolve_boxscore_path(_SEASON_ID, _GAME_ID, _GAME_STREAM_ID, None, _TEAM_PUBLIC_ID, data_root=tmp_path)
    assert result == scout_file


def test_resolve_no_path_found(tmp_path: Path) -> None:
    result = resolve_boxscore_path(_SEASON_ID, _GAME_ID, _GAME_STREAM_ID, _TEAM_GC_UUID, _TEAM_PUBLIC_ID, data_root=tmp_path)
    assert result is None


# ---------------------------------------------------------------------------
# backfill_appearance_order integration tests
# ---------------------------------------------------------------------------


def test_backfill_updates_null_rows(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-2: Backfill parses pitcher order and updates rows."""
    team_id = _insert_team(db)
    _insert_game(db, home_team_id=team_id, away_team_id=team_id)
    _insert_pitching_row(db, _GAME_ID, _PITCHER_1, team_id, appearance_order=None)
    _insert_pitching_row(db, _GAME_ID, _PITCHER_2, team_id, appearance_order=None)
    _insert_pitching_row(db, _GAME_ID, _PITCHER_3, team_id, appearance_order=None)
    db.commit()

    # Write boxscore file
    boxscore = _make_boxscore(_TEAM_PUBLIC_ID, [_PITCHER_1, _PITCHER_2, _PITCHER_3])
    game_file = tmp_path / _SEASON_ID / "teams" / _TEAM_GC_UUID / "games" / f"{_GAME_ID}.json"
    game_file.parent.mkdir(parents=True, exist_ok=True)
    game_file.write_text(json.dumps(boxscore))

    summary = backfill_appearance_order(db, data_root=tmp_path)

    assert summary["games_processed"] == 1
    assert summary["rows_updated"] == 3

    rows = db.execute(
        "SELECT player_id, appearance_order FROM player_game_pitching "
        "WHERE game_id = ? AND team_id = ? ORDER BY appearance_order",
        (_GAME_ID, team_id),
    ).fetchall()
    assert rows == [
        (_PITCHER_1, 1),
        (_PITCHER_2, 2),
        (_PITCHER_3, 3),
    ]


def test_backfill_idempotent(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-3: Re-running after successful run produces no changes."""
    team_id = _insert_team(db)
    _insert_game(db, home_team_id=team_id, away_team_id=team_id)
    _insert_pitching_row(db, _GAME_ID, _PITCHER_1, team_id, appearance_order=None)
    db.commit()

    boxscore = _make_boxscore(_TEAM_PUBLIC_ID, [_PITCHER_1])
    game_file = tmp_path / _SEASON_ID / "teams" / _TEAM_GC_UUID / "games" / f"{_GAME_ID}.json"
    game_file.parent.mkdir(parents=True, exist_ok=True)
    game_file.write_text(json.dumps(boxscore))

    summary1 = backfill_appearance_order(db, data_root=tmp_path)

    assert summary1["rows_updated"] == 1

    # Second run -- no NULL rows left
    summary2 = backfill_appearance_order(db, data_root=tmp_path)

    assert summary2["games_processed"] == 0
    assert summary2["rows_updated"] == 0


def test_backfill_skips_already_populated(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-3: Rows with existing appearance_order are not touched."""
    team_id = _insert_team(db)
    _insert_game(db, home_team_id=team_id, away_team_id=team_id)
    _insert_pitching_row(db, _GAME_ID, _PITCHER_1, team_id, appearance_order=1)
    _insert_pitching_row(db, _GAME_ID, _PITCHER_2, team_id, appearance_order=None)
    db.commit()

    boxscore = _make_boxscore(_TEAM_PUBLIC_ID, [_PITCHER_1, _PITCHER_2])
    game_file = tmp_path / _SEASON_ID / "teams" / _TEAM_GC_UUID / "games" / f"{_GAME_ID}.json"
    game_file.parent.mkdir(parents=True, exist_ok=True)
    game_file.write_text(json.dumps(boxscore))

    summary = backfill_appearance_order(db, data_root=tmp_path)

    # Only pitcher_2 was NULL, so only 1 row updated
    assert summary["rows_updated"] == 1

    rows = db.execute(
        "SELECT player_id, appearance_order FROM player_game_pitching "
        "WHERE game_id = ? ORDER BY appearance_order",
        (_GAME_ID,),
    ).fetchall()
    assert rows == [(_PITCHER_1, 1), (_PITCHER_2, 2)]


def test_backfill_skips_missing_boxscore(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-4: Games without cached JSON are logged and skipped."""
    team_id = _insert_team(db)
    _insert_game(db, home_team_id=team_id, away_team_id=team_id)
    _insert_pitching_row(db, _GAME_ID, _PITCHER_1, team_id, appearance_order=None)
    db.commit()

    # No boxscore file on disk
    summary = backfill_appearance_order(db, data_root=tmp_path)

    assert summary["games_skipped"] == 1
    assert summary["games_processed"] == 0
    assert summary["rows_updated"] == 0


def test_backfill_continues_after_skip(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-4: Script continues processing remaining games after a skip."""
    team_id = _insert_team(db)

    # Game 1: no boxscore file
    _insert_game(db, game_id="game-no-file", game_stream_id="stream-no-file", home_team_id=team_id, away_team_id=team_id)
    _insert_pitching_row(db, "game-no-file", _PITCHER_1, team_id, appearance_order=None)

    # Game 2: has boxscore file
    _insert_game(db, game_id="game-with-file", game_stream_id="stream-with-file", home_team_id=team_id, away_team_id=team_id)
    _insert_pitching_row(db, "game-with-file", _PITCHER_2, team_id, appearance_order=None)
    db.commit()

    boxscore = _make_boxscore(_TEAM_PUBLIC_ID, [_PITCHER_2])
    game_file = tmp_path / _SEASON_ID / "teams" / _TEAM_GC_UUID / "games" / "game-with-file.json"
    game_file.parent.mkdir(parents=True, exist_ok=True)
    game_file.write_text(json.dumps(boxscore))

    summary = backfill_appearance_order(db, data_root=tmp_path)

    assert summary["games_skipped"] == 1
    assert summary["games_processed"] == 1
    assert summary["rows_updated"] == 1


def test_backfill_summary_keys(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-5: Summary contains all required keys."""
    summary = backfill_appearance_order(db, data_root=tmp_path)

    assert "games_processed" in summary
    assert "rows_updated" in summary
    assert "games_skipped" in summary
    assert "games_with_errors" in summary


def test_backfill_handles_corrupt_json(db: sqlite3.Connection, tmp_path: Path) -> None:
    """Games with corrupt JSON are counted as errors."""
    team_id = _insert_team(db)
    _insert_game(db, home_team_id=team_id, away_team_id=team_id)
    _insert_pitching_row(db, _GAME_ID, _PITCHER_1, team_id, appearance_order=None)
    db.commit()

    game_file = tmp_path / _SEASON_ID / "teams" / _TEAM_GC_UUID / "games" / f"{_GAME_ID}.json"
    game_file.parent.mkdir(parents=True, exist_ok=True)
    game_file.write_text("NOT VALID JSON")

    summary = backfill_appearance_order(db, data_root=tmp_path)

    assert summary["games_with_errors"] == 1
    assert summary["games_processed"] == 0


_OPP_GC_UUID = "opp-uuid-001"
_OPP_PUBLIC_ID = "oppSlug123"
_OPP_PITCHER_1 = "opp-pitcher-001"


def test_backfill_opponent_rows_from_member_cached_boxscore(
    db: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Opponent pitching rows are backfilled from the member team's cached boxscore.

    The boxscore file lives under data/raw/{season}/teams/{member_gc_uuid}/games/
    but contains both teams' data. The opponent team's rows should be backfilled
    from this file even though the opponent's own path has no cached file.
    """
    member_id = _insert_team(db, gc_uuid=_TEAM_GC_UUID, public_id=_TEAM_PUBLIC_ID)
    opp_id = _insert_team(db, gc_uuid=_OPP_GC_UUID, public_id=_OPP_PUBLIC_ID)
    _insert_game(db, home_team_id=member_id, away_team_id=opp_id)

    # Member team pitcher
    _insert_pitching_row(db, _GAME_ID, _PITCHER_1, member_id, appearance_order=None)
    # Opponent team pitcher
    _insert_player(db, _OPP_PITCHER_1)
    db.execute(
        "INSERT INTO player_game_pitching (game_id, player_id, team_id, perspective_team_id, ip_outs, appearance_order) "
        "VALUES (?, ?, ?, ?, 12, NULL)",
        (_GAME_ID, _OPP_PITCHER_1, opp_id, opp_id),
    )
    db.commit()

    # Boxscore cached under member team path, contains BOTH teams' data
    boxscore = {
        _TEAM_PUBLIC_ID: {
            "players": [],
            "groups": [
                {
                    "category": "pitching",
                    "team_stats": {},
                    "extra": [],
                    "stats": [{"player_id": _PITCHER_1, "stats": {"IP": 7}}],
                },
            ],
        },
        _OPP_GC_UUID: {
            "players": [],
            "groups": [
                {
                    "category": "pitching",
                    "team_stats": {},
                    "extra": [],
                    "stats": [{"player_id": _OPP_PITCHER_1, "stats": {"IP": 4}}],
                },
            ],
        },
    }
    game_file = tmp_path / _SEASON_ID / "teams" / _TEAM_GC_UUID / "games" / f"{_GAME_ID}.json"
    game_file.parent.mkdir(parents=True, exist_ok=True)
    game_file.write_text(json.dumps(boxscore))

    summary = backfill_appearance_order(db, data_root=tmp_path)

    assert summary["games_processed"] == 1
    assert summary["rows_updated"] == 2

    # Member pitcher backfilled
    row = db.execute(
        "SELECT appearance_order FROM player_game_pitching WHERE game_id = ? AND player_id = ?",
        (_GAME_ID, _PITCHER_1),
    ).fetchone()
    assert row[0] == 1

    # Opponent pitcher also backfilled from the same file
    opp_row = db.execute(
        "SELECT appearance_order FROM player_game_pitching WHERE game_id = ? AND player_id = ?",
        (_GAME_ID, _OPP_PITCHER_1),
    ).fetchone()
    assert opp_row[0] == 1
