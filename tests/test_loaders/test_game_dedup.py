"""Tests for game dedup logic in GameLoader (E-216-01).

Verifies that GameLoader.load_file() detects when a game already exists
for the same date and team pair (in either home/away order) and reuses
the existing game_id for all stat upserts.

Test coverage:
- (a): Basic dedup detection -- same date, same teams, different game_id
- (b): Order-insensitive team matching (home/away swapped)
- (c): Doubleheader non-collision with different start_time
- (d): Doubleheader non-collision with score tiebreaker (NULL start_time)
- (e): NULL start_time fallback to score matching
- AC-4: INFO log emitted on dedup redirect
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

import pytest

from src.gamechanger.loaders import ensure_season_row
from src.gamechanger.loaders.game_loader import GameLoader, GameSummaryEntry
from src.gamechanger.types import TeamRef

# ---------------------------------------------------------------------------
# Schema fixture
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MIGRATION_FILE = _PROJECT_ROOT / "migrations" / "001_initial_schema.sql"


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory SQLite with schema applied and FK enforcement on."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    conn.executescript(_MIGRATION_FILE.read_text(encoding="utf-8"))
    conn.execute("ALTER TABLE teams ADD COLUMN season_year INTEGER")
    conn.execute("ALTER TABLE player_game_pitching ADD COLUMN appearance_order INTEGER")
    conn.execute("ALTER TABLE games ADD COLUMN start_time TEXT")
    conn.execute("ALTER TABLE games ADD COLUMN timezone TEXT")
    conn.commit()
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OWN_TEAM_SLUG = "y24fFdnr3RAN"
_OWN_TEAM_UUID = "team-uuid-jv-001"
_OPP_TEAM_UUID = "16d38cf9-4f73-438c-83e4-1c28fbb23628"

_GAME_DATE = "2025-05-10"
_EVENT_ID_1 = "event-first-001"
_EVENT_ID_2 = "event-second-002"
_STREAM_ID_1 = "stream-aaa-001"
_STREAM_ID_2 = "stream-bbb-002"

_PLAYER_OWN_1 = "player-own-aaa-001"
_PLAYER_OWN_P1 = "player-own-pitcher-001"
_PLAYER_OPP_1 = "player-opp-ccc-001"
_PLAYER_OPP_P1 = "player-opp-pitcher-001"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_own_team(db: sqlite3.Connection) -> int:
    cur = db.execute(
        "INSERT OR IGNORE INTO teams (gc_uuid, public_id, name, membership_type, is_active, season_year) "
        "VALUES (?, ?, ?, 'member', 1, 2025)",
        (_OWN_TEAM_UUID, _OWN_TEAM_SLUG, _OWN_TEAM_UUID),
    )
    if cur.rowcount:
        return cur.lastrowid
    return db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_UUID,)).fetchone()[0]


def _make_loader(db: sqlite3.Connection) -> GameLoader:
    pk = _insert_own_team(db)
    loader = GameLoader(
        db,
        owned_team_ref=TeamRef(id=pk, gc_uuid=_OWN_TEAM_UUID, public_id=_OWN_TEAM_SLUG),
    )
    # ensure_season_row is normally called by load_all(); load_file() skips it.
    ensure_season_row(db, loader._season_id)
    return loader


def _make_summary(
    event_id: str = _EVENT_ID_1,
    game_stream_id: str = _STREAM_ID_1,
    home_away: str = "home",
    owning_score: int = 5,
    opponent_score: int = 2,
    start_time: str | None = None,
    game_date: str = _GAME_DATE,
) -> GameSummaryEntry:
    return GameSummaryEntry(
        event_id=event_id,
        game_stream_id=game_stream_id,
        home_away=home_away,
        owning_team_score=owning_score,
        opponent_team_score=opponent_score,
        opponent_id=_OPP_TEAM_UUID,
        last_scoring_update=f"{game_date}T19:39:58.788Z",
        start_time=start_time,
    )


def _make_boxscore() -> dict:
    """Minimal valid boxscore dict."""
    return {
        _OWN_TEAM_SLUG: {
            "players": [],
            "groups": [
                {
                    "category": "lineup",
                    "team_stats": {"AB": 3, "R": 1, "H": 2, "RBI": 1, "BB": 1, "SO": 0},
                    "extra": [],
                    "stats": [
                        {
                            "player_id": _PLAYER_OWN_1,
                            "player_text": "(CF)",
                            "is_primary": True,
                            "stats": {"AB": 3, "R": 1, "H": 2, "RBI": 1, "BB": 1, "SO": 0},
                        }
                    ],
                },
                {
                    "category": "pitching",
                    "team_stats": {"IP": 5, "H": 3, "R": 2, "ER": 2, "BB": 1, "SO": 7},
                    "extra": [],
                    "stats": [
                        {
                            "player_id": _PLAYER_OWN_P1,
                            "player_text": "(W)",
                            "stats": {"IP": 5, "H": 3, "R": 2, "ER": 2, "BB": 1, "SO": 7},
                        }
                    ],
                },
            ],
        },
        _OPP_TEAM_UUID: {
            "players": [],
            "groups": [
                {
                    "category": "lineup",
                    "team_stats": {"AB": 4, "R": 1, "H": 1, "RBI": 0, "BB": 0, "SO": 2},
                    "extra": [],
                    "stats": [
                        {
                            "player_id": _PLAYER_OPP_1,
                            "player_text": "(1B)",
                            "is_primary": True,
                            "stats": {"AB": 4, "R": 1, "H": 1, "RBI": 0, "BB": 0, "SO": 2},
                        }
                    ],
                },
                {
                    "category": "pitching",
                    "team_stats": {"IP": 4, "H": 5, "R": 5, "ER": 4, "BB": 2, "SO": 4},
                    "extra": [],
                    "stats": [
                        {
                            "player_id": _PLAYER_OPP_P1,
                            "player_text": "(L)",
                            "stats": {"IP": 4, "H": 5, "R": 5, "ER": 4, "BB": 2, "SO": 4},
                        }
                    ],
                },
            ],
        },
    }


def _write_boxscore(tmp_path: Path, data: dict, stream_id: str = _STREAM_ID_1) -> Path:
    dest = tmp_path / f"{stream_id}.json"
    dest.write_text(json.dumps(data), encoding="utf-8")
    return dest


def _load_first_game(
    db: sqlite3.Connection,
    loader: GameLoader,
    tmp_path: Path,
    *,
    start_time: str | None = None,
    owning_score: int = 5,
    opponent_score: int = 2,
) -> None:
    """Load the 'first' game so a row exists in the DB for dedup testing."""
    summary = _make_summary(
        event_id=_EVENT_ID_1,
        game_stream_id=_STREAM_ID_1,
        start_time=start_time,
        owning_score=owning_score,
        opponent_score=opponent_score,
    )
    path = _write_boxscore(tmp_path, _make_boxscore(), stream_id=_STREAM_ID_1)
    loader.load_file(path, summary)


# ---------------------------------------------------------------------------
# (a): Basic dedup detection
# ---------------------------------------------------------------------------


def test_dedup_reuses_existing_game_id(
    db: sqlite3.Connection, tmp_path: Path,
) -> None:
    """When a game already exists for the same date and team pair, the new
    boxscore reuses the existing game_id -- no duplicate games row created."""
    loader = _make_loader(db)
    _load_first_game(db, loader, tmp_path)

    # Second load: different event_id, same date/teams/score.
    summary2 = _make_summary(event_id=_EVENT_ID_2, game_stream_id=_STREAM_ID_2)
    path2 = _write_boxscore(tmp_path, _make_boxscore(), stream_id=_STREAM_ID_2)
    loader.load_file(path2, summary2)

    game_count = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    assert game_count == 1, f"Expected 1 game row (dedup), got {game_count}"

    row = db.execute("SELECT game_id FROM games").fetchone()
    assert row[0] == _EVENT_ID_1


def test_dedup_stats_use_canonical_game_id(
    db: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Stat rows are keyed to the existing (canonical) game_id, not the new one."""
    loader = _make_loader(db)
    _load_first_game(db, loader, tmp_path)

    summary2 = _make_summary(event_id=_EVENT_ID_2, game_stream_id=_STREAM_ID_2)
    path2 = _write_boxscore(tmp_path, _make_boxscore(), stream_id=_STREAM_ID_2)
    loader.load_file(path2, summary2)

    batting_ids = db.execute(
        "SELECT DISTINCT game_id FROM player_game_batting"
    ).fetchall()
    assert all(r[0] == _EVENT_ID_1 for r in batting_ids)

    pitching_ids = db.execute(
        "SELECT DISTINCT game_id FROM player_game_pitching"
    ).fetchall()
    assert all(r[0] == _EVENT_ID_1 for r in pitching_ids)


# ---------------------------------------------------------------------------
# (b): Order-insensitive team matching
# ---------------------------------------------------------------------------


def test_dedup_order_insensitive_team_matching(
    db: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Dedup detects the match even when home/away are swapped between the
    existing game and the incoming boxscore."""
    loader = _make_loader(db)
    # First game: own team is HOME.
    _load_first_game(db, loader, tmp_path)

    # Second game: own team is AWAY (swapped perspective), same date and teams.
    summary2 = _make_summary(
        event_id=_EVENT_ID_2,
        game_stream_id=_STREAM_ID_2,
        home_away="away",
        owning_score=5,
        opponent_score=2,
    )
    path2 = _write_boxscore(tmp_path, _make_boxscore(), stream_id=_STREAM_ID_2)
    loader.load_file(path2, summary2)

    game_count = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    assert game_count == 1, f"Expected dedup to 1 game, got {game_count}"


# ---------------------------------------------------------------------------
# (c): Doubleheader non-collision with start_time
# ---------------------------------------------------------------------------


def test_doubleheader_different_start_time_no_dedup(
    db: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Two games on the same date between the same teams with different
    start_time values are NOT deduped (doubleheader)."""
    loader = _make_loader(db)
    _load_first_game(db, loader, tmp_path, start_time="2025-05-10T14:00:00.000Z")

    summary2 = _make_summary(
        event_id=_EVENT_ID_2,
        game_stream_id=_STREAM_ID_2,
        start_time="2025-05-10T18:00:00.000Z",
    )
    path2 = _write_boxscore(tmp_path, _make_boxscore(), stream_id=_STREAM_ID_2)
    loader.load_file(path2, summary2)

    game_count = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    assert game_count == 2, f"Expected 2 games (doubleheader), got {game_count}"


# ---------------------------------------------------------------------------
# (d): Doubleheader non-collision with score tiebreaker
# ---------------------------------------------------------------------------


def test_doubleheader_different_score_null_start_time_no_dedup(
    db: sqlite3.Connection, tmp_path: Path,
) -> None:
    """When start_time is NULL on both sides but total scores differ,
    the games are NOT deduped (doubleheader distinguished by score)."""
    loader = _make_loader(db)
    # First: 5-2 (total 7), no start_time.
    _load_first_game(db, loader, tmp_path, owning_score=5, opponent_score=2)

    # Second: 3-1 (total 4), no start_time.
    summary2 = _make_summary(
        event_id=_EVENT_ID_2,
        game_stream_id=_STREAM_ID_2,
        owning_score=3,
        opponent_score=1,
        start_time=None,
    )
    path2 = _write_boxscore(tmp_path, _make_boxscore(), stream_id=_STREAM_ID_2)
    loader.load_file(path2, summary2)

    game_count = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    assert game_count == 2, f"Expected 2 games (doubleheader by score), got {game_count}"


# ---------------------------------------------------------------------------
# (e): NULL start_time fallback to score matching → dedup
# ---------------------------------------------------------------------------


def test_null_start_time_same_score_triggers_dedup(
    db: sqlite3.Connection, tmp_path: Path,
) -> None:
    """When start_time is NULL on both sides and score totals match,
    the game IS deduped."""
    loader = _make_loader(db)
    _load_first_game(db, loader, tmp_path, owning_score=5, opponent_score=2)

    # Second: same 5-2 score, no start_time.
    summary2 = _make_summary(
        event_id=_EVENT_ID_2,
        game_stream_id=_STREAM_ID_2,
        owning_score=5,
        opponent_score=2,
        start_time=None,
    )
    path2 = _write_boxscore(tmp_path, _make_boxscore(), stream_id=_STREAM_ID_2)
    loader.load_file(path2, summary2)

    game_count = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    assert game_count == 1, f"Expected dedup to 1 game, got {game_count}"


# ---------------------------------------------------------------------------
# AC-4: INFO log on dedup redirect
# ---------------------------------------------------------------------------


def test_dedup_logs_info_message(
    db: sqlite3.Connection, tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    """An INFO-level log message identifies both game_ids on dedup redirect."""
    loader = _make_loader(db)
    _load_first_game(db, loader, tmp_path)

    summary2 = _make_summary(event_id=_EVENT_ID_2, game_stream_id=_STREAM_ID_2)
    path2 = _write_boxscore(tmp_path, _make_boxscore(), stream_id=_STREAM_ID_2)

    with caplog.at_level(logging.INFO, logger="src.gamechanger.loaders.game_loader"):
        loader.load_file(path2, summary2)

    dedup_msgs = [r for r in caplog.records if "Dedup" in r.message]
    assert len(dedup_msgs) >= 1, "Expected at least one Dedup INFO log message"
    msg = dedup_msgs[0]
    assert msg.levelno == logging.INFO
    assert _EVENT_ID_1 in msg.message
    assert _EVENT_ID_2 in msg.message


# ---------------------------------------------------------------------------
# No false-positive: different date → no dedup
# ---------------------------------------------------------------------------


def test_different_date_no_dedup(
    db: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Games on different dates between the same teams are NOT deduped."""
    loader = _make_loader(db)
    _load_first_game(db, loader, tmp_path)

    # Second game on a different date.
    summary2 = _make_summary(
        event_id=_EVENT_ID_2,
        game_stream_id=_STREAM_ID_2,
        game_date="2025-05-11",
    )
    path2 = _write_boxscore(tmp_path, _make_boxscore(), stream_id=_STREAM_ID_2)
    loader.load_file(path2, summary2)

    game_count = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    assert game_count == 2


# ---------------------------------------------------------------------------
# Ambiguous candidate skipped, real match found
# ---------------------------------------------------------------------------

_EVENT_ID_3 = "event-third-003"
_STREAM_ID_3 = "stream-ccc-003"


def test_dedup_skips_ambiguous_finds_real_match(
    db: sqlite3.Connection, tmp_path: Path,
) -> None:
    """When multiple same-date/team-pair rows exist and one is ambiguous
    (NULL start_time/scores) while another is a real match, the dedup
    skips the ambiguous candidate and finds the correct duplicate."""
    loader = _make_loader(db)

    # Load game 1: has start_time, score 5-2.
    _load_first_game(
        db, loader, tmp_path,
        start_time="2025-05-10T14:00:00.000Z",
        owning_score=5,
        opponent_score=2,
    )

    # Load game 2: NULL start_time, NULL scores (ambiguous).
    summary2 = _make_summary(
        event_id=_EVENT_ID_2,
        game_stream_id=_STREAM_ID_2,
        start_time=None,
        owning_score=0,
        opponent_score=0,
    )
    path2 = _write_boxscore(tmp_path, _make_boxscore(), stream_id=_STREAM_ID_2)
    loader.load_file(path2, summary2)

    # Should have 2 games now (game 1 and game 2 are distinct -- different
    # start_time and different scores).
    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 2

    # Load game 3: same start_time as game 1 → should dedup to game 1,
    # not be blocked by the ambiguous game 2.
    summary3 = _make_summary(
        event_id=_EVENT_ID_3,
        game_stream_id=_STREAM_ID_3,
        start_time="2025-05-10T14:00:00.000Z",
        owning_score=5,
        opponent_score=2,
    )
    path3 = _write_boxscore(tmp_path, _make_boxscore(), stream_id=_STREAM_ID_3)
    loader.load_file(path3, summary3)

    # Still 2 games -- game 3 deduped into game 1.
    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 2

    # Verify the canonical game_id is game 1 (not game 2).
    game_ids = {r[0] for r in db.execute("SELECT game_id FROM games").fetchall()}
    assert _EVENT_ID_1 in game_ids
    assert _EVENT_ID_2 in game_ids
    assert _EVENT_ID_3 not in game_ids
