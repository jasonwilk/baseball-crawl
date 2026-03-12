"""Tests for src/gamechanger/loaders/game_loader.py.

Uses an in-memory SQLite database with the full schema applied.  No real
network calls, no production DB writes.

Tests cover all acceptance criteria:
- AC-1: Game record upserted into games table
- AC-2: Batting/pitching lines upserted; idempotent; sparse extras zero-filled
- AC-3: LoadResult returned with correct counts
- AC-4: Unknown player_id gets stub row + WARNING log
- AC-5: Same game across multiple team directories produces same DB state
- AC-6: Asymmetric key handling (slug vs UUID)
- AC-7: home_team_id / away_team_id set via home_away field
- AC-8: FK prerequisite rows (teams, seasons) created automatically
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from src.gamechanger.loaders import LoadResult
from src.gamechanger.loaders.game_loader import GameLoader, GameSummaryEntry as _GameSummaryEntry

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
# Constants and sample data
# ---------------------------------------------------------------------------

_SEASON_ID = "2025"
_OWN_TEAM_ID = "team-uuid-jv-001"          # owned team (UUID)
_OWN_TEAM_SLUG = "y24fFdnr3RAN"            # public_id slug for own team
_OPP_TEAM_ID = "16d38cf9-4f73-438c-83e4-1c28fbb23628"  # UUID

_EVENT_ID = "event-aaa-001"
_GAME_STREAM_ID = "stream-bbb-002"

_PLAYER_OWN_1 = "player-own-aaa-001"
_PLAYER_OWN_P1 = "player-own-pitcher-001"
_PLAYER_OPP_1 = "player-opp-ccc-001"
_PLAYER_OPP_P1 = "player-opp-pitcher-001"


def _make_summary(
    event_id: str = _EVENT_ID,
    game_stream_id: str = _GAME_STREAM_ID,
    home_away: str | None = "home",
    owning_score: int = 5,
    opponent_score: int = 2,
    opponent_id: str = _OPP_TEAM_ID,
) -> _GameSummaryEntry:
    return _GameSummaryEntry(
        event_id=event_id,
        game_stream_id=game_stream_id,
        home_away=home_away,
        owning_team_score=owning_score,
        opponent_team_score=opponent_score,
        opponent_id=opponent_id,
        last_scoring_update="2025-05-10T19:39:58.788Z",
    )


def _make_boxscore(
    own_key: str = _OWN_TEAM_SLUG,
    opp_key: str = _OPP_TEAM_ID,
    own_batting: list[dict] | None = None,
    opp_batting: list[dict] | None = None,
    own_pitching: list[dict] | None = None,
    opp_pitching: list[dict] | None = None,
    batting_extra: list[dict] | None = None,
) -> dict:
    """Build a minimal but valid boxscore dict."""
    if own_batting is None:
        own_batting = [
            {
                "player_id": _PLAYER_OWN_1,
                "player_text": "(CF)",
                "is_primary": True,
                "stats": {"AB": 3, "R": 1, "H": 2, "RBI": 1, "BB": 1, "SO": 0},
            }
        ]
    if own_pitching is None:
        own_pitching = [
            {
                "player_id": _PLAYER_OWN_P1,
                "player_text": "(W)",
                "stats": {"IP": 5, "H": 3, "R": 2, "ER": 2, "BB": 1, "SO": 7},
            }
        ]
    if opp_batting is None:
        opp_batting = [
            {
                "player_id": _PLAYER_OPP_1,
                "player_text": "(1B)",
                "is_primary": True,
                "stats": {"AB": 4, "R": 1, "H": 1, "RBI": 0, "BB": 0, "SO": 2},
            }
        ]
    if opp_pitching is None:
        opp_pitching = [
            {
                "player_id": _PLAYER_OPP_P1,
                "player_text": "(L)",
                "stats": {"IP": 4, "H": 5, "R": 5, "ER": 4, "BB": 2, "SO": 4},
            }
        ]
    if batting_extra is None:
        batting_extra = []

    return {
        own_key: {
            "players": [],
            "groups": [
                {
                    "category": "lineup",
                    "team_stats": {"AB": 3, "R": 1, "H": 2, "RBI": 1, "BB": 1, "SO": 0},
                    "extra": batting_extra,
                    "stats": own_batting,
                },
                {
                    "category": "pitching",
                    "team_stats": {"IP": 5, "H": 3, "R": 2, "ER": 2, "BB": 1, "SO": 7},
                    "extra": [],
                    "stats": own_pitching,
                },
            ],
        },
        opp_key: {
            "players": [],
            "groups": [
                {
                    "category": "lineup",
                    "team_stats": {"AB": 4, "R": 1, "H": 1, "RBI": 0, "BB": 0, "SO": 2},
                    "extra": [],
                    "stats": opp_batting,
                },
                {
                    "category": "pitching",
                    "team_stats": {"IP": 4, "H": 5, "R": 5, "ER": 4, "BB": 2, "SO": 4},
                    "extra": [],
                    "stats": opp_pitching,
                },
            ],
        },
    }


def _write_boxscore(tmp_path: Path, data: dict, game_stream_id: str = _GAME_STREAM_ID) -> Path:
    """Write a boxscore JSON file at the conventional path."""
    dest = tmp_path / f"{game_stream_id}.json"
    dest.write_text(json.dumps(data), encoding="utf-8")
    return dest


def _write_team_dir(
    tmp_path: Path,
    team_id: str = _OWN_TEAM_ID,
    season: str = _SEASON_ID,
    summaries: list[dict] | None = None,
    boxscores: dict[str, dict] | None = None,
) -> Path:
    """Set up a team directory with game_summaries.json and games/ subdir."""
    team_dir = tmp_path / season / "teams" / team_id
    team_dir.mkdir(parents=True, exist_ok=True)

    # Write game_summaries.json
    if summaries is None:
        summaries = [
            {
                "event_id": _EVENT_ID,
                "game_stream": {"id": _GAME_STREAM_ID, "opponent_id": _OPP_TEAM_ID},
                "home_away": "home",
                "owning_team_score": 5,
                "opponent_team_score": 2,
                "last_scoring_update": "2025-05-10T19:39:58.788Z",
            }
        ]
    (team_dir / "game_summaries.json").write_text(json.dumps(summaries), encoding="utf-8")

    # Write boxscore files
    if boxscores is not None:
        games_dir = team_dir / "games"
        games_dir.mkdir(exist_ok=True)
        for gsid, data in boxscores.items():
            (games_dir / f"{gsid}.json").write_text(json.dumps(data), encoding="utf-8")

    return team_dir


def _make_loader(db: sqlite3.Connection, owned_team_id: str = _OWN_TEAM_ID) -> GameLoader:
    return GameLoader(db, season_id=_SEASON_ID, owned_team_id=owned_team_id)


# ---------------------------------------------------------------------------
# AC-1: Game upserted into games table
# ---------------------------------------------------------------------------


def test_game_record_inserted_into_games_table(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-1: load_all inserts a games row with correct event_id."""
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute("SELECT game_id FROM games WHERE game_id = ?;", (_EVENT_ID,)).fetchone()
    assert row is not None, f"Expected games row for event_id={_EVENT_ID}"


def test_game_record_has_correct_season_id(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-1: game row has correct season_id."""
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute("SELECT season_id FROM games WHERE game_id = ?;", (_EVENT_ID,)).fetchone()
    assert row is not None
    assert row[0] == _SEASON_ID


def test_game_record_has_correct_game_date(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-1: game_date is extracted from last_scoring_update (YYYY-MM-DD prefix)."""
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute("SELECT game_date FROM games WHERE game_id = ?;", (_EVENT_ID,)).fetchone()
    assert row is not None
    assert row[0] == "2025-05-10"


def test_game_record_has_correct_scores(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-1: home_score and away_score populated correctly."""
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT home_score, away_score FROM games WHERE game_id = ?;", (_EVENT_ID,)
    ).fetchone()
    assert row is not None
    # own team is home (home_away="home"), owning_score=5, opponent_score=2
    assert row[0] == 5   # home_score
    assert row[1] == 2   # away_score


# ---------------------------------------------------------------------------
# AC-2: Batting and pitching lines upserted; idempotent; extras zero-filled
# ---------------------------------------------------------------------------


def test_batting_line_inserted_for_own_player(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-2: player_game_batting row created for own team player."""
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT ab, h, rbi, bb, so FROM player_game_batting WHERE player_id = ? AND game_id = ?;",
        (_PLAYER_OWN_1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row == (3, 2, 1, 1, 0)


def test_pitching_line_inserted_with_ip_outs_conversion(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-2: IP=5 in boxscore -> ip_outs=15 in DB (1 IP = 3 outs)."""
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT ip_outs, h, er, bb, so FROM player_game_pitching WHERE player_id = ? AND game_id = ?;",
        (_PLAYER_OWN_P1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 15  # 5 IP * 3 = 15 outs
    assert row[1] == 3   # H
    assert row[2] == 2   # ER
    assert row[3] == 1   # BB
    assert row[4] == 7   # SO


def test_load_all_twice_is_idempotent(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-2: Running load_all twice produces same DB state (no duplicates)."""
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)
    loader.load_all(team_dir)

    game_count = db.execute("SELECT COUNT(*) FROM games;").fetchone()[0]
    batting_count = db.execute("SELECT COUNT(*) FROM player_game_batting;").fetchone()[0]
    pitching_count = db.execute("SELECT COUNT(*) FROM player_game_pitching;").fetchone()[0]
    assert game_count == 1
    # 2 teams, 1 batter each
    assert batting_count == 2
    # 2 teams, 1 pitcher each
    assert pitching_count == 2


def test_batting_extras_zero_filled_when_absent(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-2: Extras (2B, 3B, HR, SB) default to 0 when not in extra[] array."""
    boxscore = _make_boxscore(batting_extra=[])  # no extras
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT doubles, triples, hr, sb FROM player_game_batting WHERE player_id = ? AND game_id = ?;",
        (_PLAYER_OWN_1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row == (0, 0, 0, 0)


def test_batting_extras_populated_from_extra_array(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-2: 2B and SB are read from the extra[] array correctly."""
    batting_extra = [
        {"stat_name": "2B", "stats": [{"player_id": _PLAYER_OWN_1, "value": 2}]},
        {"stat_name": "SB", "stats": [{"player_id": _PLAYER_OWN_1, "value": 1}]},
    ]
    boxscore = _make_boxscore(batting_extra=batting_extra)
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT doubles, sb FROM player_game_batting WHERE player_id = ? AND game_id = ?;",
        (_PLAYER_OWN_1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 2  # doubles
    assert row[1] == 1  # sb


# ---------------------------------------------------------------------------
# AC-3: LoadResult counts
# ---------------------------------------------------------------------------


def test_load_all_returns_load_result(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-3: load_all returns a LoadResult instance."""
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    result = loader.load_all(team_dir)

    assert isinstance(result, LoadResult)


def test_load_all_counts_loaded_records(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-3: loaded count = 1 game + 2 batting rows + 2 pitching rows = 5."""
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    result = loader.load_all(team_dir)

    # 1 (game) + 1 (own batter) + 1 (own pitcher) + 1 (opp batter) + 1 (opp pitcher)
    assert result.loaded == 5
    assert result.errors == 0


def test_load_result_skipped_when_no_summary(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-3: Files without a matching game-summaries entry increment skipped."""
    # Write a boxscore file with no matching entry in summaries.
    team_dir = _write_team_dir(tmp_path, summaries=[], boxscores={_GAME_STREAM_ID: _make_boxscore()})
    loader = _make_loader(db)

    result = loader.load_all(team_dir)

    assert result.skipped == 1
    assert result.loaded == 0


# ---------------------------------------------------------------------------
# AC-4: Stub player for unknown player_id
# ---------------------------------------------------------------------------


def test_unknown_player_gets_stub_row(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-4: A player_id not in players table gets a stub row before stat insert."""
    unknown_player = "player-completely-unknown-xxx"
    boxscore = _make_boxscore(
        own_batting=[
            {
                "player_id": unknown_player,
                "player_text": "(DH)",
                "is_primary": True,
                "stats": {"AB": 2, "R": 0, "H": 0, "RBI": 0, "BB": 0, "SO": 1},
            }
        ],
        own_pitching=[],
    )
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?;",
        (unknown_player,),
    ).fetchone()
    assert row is not None
    assert row[0] == "Unknown"
    assert row[1] == "Unknown"


def test_unknown_player_logs_warning(
    db: sqlite3.Connection, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-4: WARNING is logged when a stub player row is created."""
    import logging

    unknown_player = "player-warn-test-yyy"
    boxscore = _make_boxscore(
        own_batting=[
            {
                "player_id": unknown_player,
                "player_text": "(SS)",
                "is_primary": True,
                "stats": {"AB": 3, "R": 0, "H": 1, "RBI": 0, "BB": 0, "SO": 1},
            }
        ],
        own_pitching=[],
    )
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    with caplog.at_level(logging.WARNING, logger="src.gamechanger.loaders.game_loader"):
        loader.load_all(team_dir)

    assert unknown_player in caplog.text


def test_known_player_does_not_get_overwritten(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-4: Pre-existing player row is not overwritten by stub logic."""
    # Pre-insert a real player record.
    db.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, 'Jake', 'Smith');",
        (_PLAYER_OWN_1,),
    )
    db.commit()

    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT first_name FROM players WHERE player_id = ?;", (_PLAYER_OWN_1,)
    ).fetchone()
    assert row is not None
    assert row[0] == "Jake"  # not overwritten with "Unknown"


# ---------------------------------------------------------------------------
# AC-5: Same game under multiple team directories -> same DB state
# ---------------------------------------------------------------------------


def test_same_game_from_two_team_dirs_is_idempotent(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-5: Loading the same game from two team directories upserts correctly."""
    boxscore = _make_boxscore()

    # Team A's directory
    team_dir_a = _write_team_dir(
        tmp_path, team_id="team-aaa", boxscores={_GAME_STREAM_ID: boxscore}
    )
    # Team B's directory (same game, different team_id)
    team_dir_b = _write_team_dir(
        tmp_path, team_id="team-bbb", boxscores={_GAME_STREAM_ID: boxscore}
    )

    loader_a = GameLoader(db, season_id=_SEASON_ID, owned_team_id="team-aaa")
    loader_b = GameLoader(db, season_id=_SEASON_ID, owned_team_id=_OWN_TEAM_ID)

    loader_a.load_all(team_dir_a)
    loader_b.load_all(team_dir_b)

    count = db.execute("SELECT COUNT(*) FROM games WHERE game_id = ?;", (_EVENT_ID,)).fetchone()[0]
    assert count == 1


# ---------------------------------------------------------------------------
# AC-6: Asymmetric key handling (slug vs UUID)
# ---------------------------------------------------------------------------


def test_own_team_slug_key_detected_correctly(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-6: Own team identified by public_id slug (alphanumeric, no dashes)."""
    # Own team uses a slug, opponent uses UUID (default boxscore)
    boxscore = _make_boxscore(own_key="y24fFdnr3RAN", opp_key=_OPP_TEAM_ID)
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    result = loader.load_all(team_dir)

    assert result.errors == 0
    # Own batting player should have team_id = _OWN_TEAM_ID
    row = db.execute(
        "SELECT team_id FROM player_game_batting WHERE player_id = ?;", (_PLAYER_OWN_1,)
    ).fetchone()
    assert row is not None
    assert row[0] == _OWN_TEAM_ID


def test_opponent_uuid_key_detected_correctly(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-6: Opponent identified by UUID key (36 chars with dashes)."""
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT team_id FROM player_game_batting WHERE player_id = ?;", (_PLAYER_OPP_1,)
    ).fetchone()
    assert row is not None
    assert row[0] == _OPP_TEAM_ID


# ---------------------------------------------------------------------------
# AC-7: home_team_id / away_team_id set via home_away field
# ---------------------------------------------------------------------------


def test_home_away_home_sets_own_team_as_home(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-7: home_away='home' -> own team is home_team_id."""
    boxscore = _make_boxscore()
    summaries = [
        {
            "event_id": _EVENT_ID,
            "game_stream": {"id": _GAME_STREAM_ID, "opponent_id": _OPP_TEAM_ID},
            "home_away": "home",
            "owning_team_score": 7,
            "opponent_team_score": 3,
            "last_scoring_update": "2025-05-10T20:00:00Z",
        }
    ]
    team_dir = _write_team_dir(tmp_path, summaries=summaries, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT home_team_id, away_team_id, home_score, away_score FROM games WHERE game_id = ?;",
        (_EVENT_ID,),
    ).fetchone()
    assert row is not None
    assert row[0] == _OWN_TEAM_ID   # home
    assert row[1] == _OPP_TEAM_ID   # away
    assert row[2] == 7              # home score
    assert row[3] == 3              # away score


def test_home_away_away_sets_opponent_as_home(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-7: home_away='away' -> opponent is home_team_id, own team is away."""
    boxscore = _make_boxscore()
    summaries = [
        {
            "event_id": _EVENT_ID,
            "game_stream": {"id": _GAME_STREAM_ID, "opponent_id": _OPP_TEAM_ID},
            "home_away": "away",
            "owning_team_score": 4,
            "opponent_team_score": 9,
            "last_scoring_update": "2025-06-01T20:00:00Z",
        }
    ]
    team_dir = _write_team_dir(tmp_path, summaries=summaries, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT home_team_id, away_team_id, home_score, away_score FROM games WHERE game_id = ?;",
        (_EVENT_ID,),
    ).fetchone()
    assert row is not None
    assert row[0] == _OPP_TEAM_ID   # home (opponent)
    assert row[1] == _OWN_TEAM_ID   # away (own team)
    assert row[2] == 9              # home score (opponent)
    assert row[3] == 4              # away score (own)


def test_home_away_none_defaults_to_own_team_as_home(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-7: home_away=None defaults own team to home (with warning logged)."""
    boxscore = _make_boxscore()
    summaries = [
        {
            "event_id": _EVENT_ID,
            "game_stream": {"id": _GAME_STREAM_ID, "opponent_id": _OPP_TEAM_ID},
            "home_away": None,
            "owning_team_score": 5,
            "opponent_team_score": 2,
            "last_scoring_update": "2025-07-04T20:00:00Z",
        }
    ]
    team_dir = _write_team_dir(tmp_path, summaries=summaries, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT home_team_id FROM games WHERE game_id = ?;", (_EVENT_ID,)
    ).fetchone()
    assert row is not None
    assert row[0] == _OWN_TEAM_ID  # fallback: own team as home


# ---------------------------------------------------------------------------
# AC-8: FK prerequisite rows created automatically
# ---------------------------------------------------------------------------


def test_teams_rows_created_before_game_insert(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-8: teams rows for both home and away are created automatically."""
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    count_before = db.execute("SELECT COUNT(*) FROM teams;").fetchone()[0]
    assert count_before == 0

    loader.load_all(team_dir)

    team_ids = {
        row[0]
        for row in db.execute("SELECT team_id FROM teams;").fetchall()
    }
    assert _OWN_TEAM_ID in team_ids
    assert _OPP_TEAM_ID in team_ids


def test_seasons_row_created_automatically(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-8: seasons row is created for season_id before game insert."""
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    count_before = db.execute("SELECT COUNT(*) FROM seasons;").fetchone()[0]
    assert count_before == 0

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT season_id FROM seasons WHERE season_id = ?;", (_SEASON_ID,)
    ).fetchone()
    assert row is not None


def test_load_succeeds_with_no_pre_existing_fk_rows(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-8: Load completes without FK errors even with empty tables."""
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    result = loader.load_all(team_dir)

    assert result.errors == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_no_games_dir_returns_empty_result(db: sqlite3.Connection, tmp_path: Path) -> None:
    """No games/ subdirectory: load_all returns LoadResult with all zeros."""
    team_dir = _write_team_dir(tmp_path)  # no boxscores
    loader = _make_loader(db)

    result = loader.load_all(team_dir)

    assert result.loaded == 0
    assert result.skipped == 0
    assert result.errors == 0


def test_missing_summaries_file_returns_error(db: sqlite3.Connection, tmp_path: Path) -> None:
    """Missing game_summaries.json returns errors=1."""
    team_dir = tmp_path / _SEASON_ID / "teams" / _OWN_TEAM_ID
    team_dir.mkdir(parents=True)
    # No game_summaries.json written.
    loader = _make_loader(db)

    result = loader.load_all(team_dir)

    assert result.errors == 1


def test_nonexistent_boxscore_file_returns_error(db: sqlite3.Connection, tmp_path: Path) -> None:
    """load_file with nonexistent path returns errors=1."""
    loader = _make_loader(db)
    summary = _make_summary()

    result = loader.load_file(Path("/nonexistent/path/file.json"), summary)

    assert result.errors == 1


def test_batting_row_missing_player_id_is_skipped(db: sqlite3.Connection, tmp_path: Path) -> None:
    """Batting row without player_id is skipped; load continues."""
    boxscore = _make_boxscore(
        own_batting=[
            # Missing player_id
            {"player_text": "(CF)", "stats": {"AB": 2, "R": 0, "H": 1, "RBI": 0, "BB": 0, "SO": 0}},
            # Valid player
            {"player_id": _PLAYER_OWN_1, "player_text": "(1B)", "stats": {"AB": 3, "R": 1, "H": 1, "RBI": 1, "BB": 0, "SO": 1}},
        ],
        own_pitching=[],
    )
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    result = loader.load_all(team_dir)

    assert result.skipped == 1
    # Valid batting row was still loaded.
    count = db.execute("SELECT COUNT(*) FROM player_game_batting WHERE game_id = ?;", (_EVENT_ID,)).fetchone()[0]
    assert count >= 1


def test_ip_zero_converts_to_zero_ip_outs(db: sqlite3.Connection, tmp_path: Path) -> None:
    """IP=0 converts to ip_outs=0."""
    boxscore = _make_boxscore(
        own_pitching=[
            {"player_id": _PLAYER_OWN_P1, "stats": {"IP": 0, "H": 0, "R": 0, "ER": 0, "BB": 0, "SO": 0}}
        ]
    )
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT ip_outs FROM player_game_pitching WHERE player_id = ? AND game_id = ?;",
        (_PLAYER_OWN_P1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 0


def test_ip_one_third_converts_to_one_out(db: sqlite3.Connection, tmp_path: Path) -> None:
    """IP=3.333... (3⅓ innings = 10 outs) converts correctly via round(float*3).

    The old int() truncation would have given 3*3=9 outs (wrong).
    """
    boxscore = _make_boxscore(
        own_pitching=[
            {"player_id": _PLAYER_OWN_P1, "stats": {"IP": 3.3333333333333335, "H": 3, "R": 1, "ER": 1, "BB": 1, "SO": 4}}
        ]
    )
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT ip_outs FROM player_game_pitching WHERE player_id = ? AND game_id = ?;",
        (_PLAYER_OWN_P1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 10, f"3⅓ IP should be 10 outs, got {row[0]}"


def test_ip_two_thirds_converts_to_two_outs(db: sqlite3.Connection, tmp_path: Path) -> None:
    """IP=3.666... (3⅔ innings = 11 outs) converts correctly via round(float*3).

    The old int() truncation would have given 3*3=9 outs (wrong).
    """
    boxscore = _make_boxscore(
        own_pitching=[
            {"player_id": _PLAYER_OWN_P1, "stats": {"IP": 3.6666666666666665, "H": 2, "R": 0, "ER": 0, "BB": 0, "SO": 5}}
        ]
    )
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT ip_outs FROM player_game_pitching WHERE player_id = ? AND game_id = ?;",
        (_PLAYER_OWN_P1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 11, f"3⅔ IP should be 11 outs, got {row[0]}"


def test_multiple_games_in_one_team_dir(db: sqlite3.Connection, tmp_path: Path) -> None:
    """Multiple boxscore files in one team directory are all loaded."""
    stream1 = "stream-001"
    stream2 = "stream-002"
    event1 = "event-001"
    event2 = "event-002"

    summaries = [
        {
            "event_id": event1,
            "game_stream": {"id": stream1, "opponent_id": _OPP_TEAM_ID},
            "home_away": "home",
            "owning_team_score": 5,
            "opponent_team_score": 2,
            "last_scoring_update": "2025-05-10T19:00:00Z",
        },
        {
            "event_id": event2,
            "game_stream": {"id": stream2, "opponent_id": _OPP_TEAM_ID},
            "home_away": "away",
            "owning_team_score": 3,
            "opponent_team_score": 1,
            "last_scoring_update": "2025-05-11T19:00:00Z",
        },
    ]
    team_dir = _write_team_dir(
        tmp_path,
        summaries=summaries,
        boxscores={
            stream1: _make_boxscore(),
            stream2: _make_boxscore(),
        },
    )
    loader = _make_loader(db)

    result = loader.load_all(team_dir)

    count = db.execute("SELECT COUNT(*) FROM games;").fetchone()[0]
    assert count == 2
    assert result.errors == 0
