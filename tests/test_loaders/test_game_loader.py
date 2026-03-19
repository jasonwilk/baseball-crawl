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


def _insert_own_team(
    db: sqlite3.Connection,
    gc_uuid: str = _OWN_TEAM_ID,
    public_id: str = _OWN_TEAM_SLUG,
) -> int:
    """Insert own team stub into teams table and return its INTEGER PK."""
    cur = db.execute(
        "INSERT OR IGNORE INTO teams (gc_uuid, public_id, name, membership_type, is_active) "
        "VALUES (?, ?, ?, 'member', 1)",
        (gc_uuid, public_id, gc_uuid),
    )
    if cur.rowcount:
        return cur.lastrowid
    return db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (gc_uuid,)).fetchone()[0]


def _make_loader(db: sqlite3.Connection, gc_uuid: str = _OWN_TEAM_ID) -> GameLoader:
    from src.gamechanger.types import TeamRef
    pk = _insert_own_team(db, gc_uuid=gc_uuid)
    return GameLoader(db, season_id=_SEASON_ID, owned_team_ref=TeamRef(id=pk, gc_uuid=gc_uuid, public_id=_OWN_TEAM_SLUG))


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

    from src.gamechanger.types import TeamRef
    pk_a = _insert_own_team(db, gc_uuid="team-aaa", public_id="slug-aaa")
    pk_b = _insert_own_team(db, gc_uuid=_OWN_TEAM_ID)
    loader_a = GameLoader(db, season_id=_SEASON_ID, owned_team_ref=TeamRef(id=pk_a, gc_uuid="team-aaa", public_id="slug-aaa"))
    loader_b = GameLoader(db, season_id=_SEASON_ID, owned_team_ref=TeamRef(id=pk_b, gc_uuid=_OWN_TEAM_ID, public_id=_OWN_TEAM_SLUG))

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
    # Own batting player should have team_id = INTEGER PK of own team
    row = db.execute(
        "SELECT team_id FROM player_game_batting WHERE player_id = ?;", (_PLAYER_OWN_1,)
    ).fetchone()
    assert row is not None
    own_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_ID,)).fetchone()[0]
    assert row[0] == own_pk


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
    opp_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OPP_TEAM_ID,)).fetchone()[0]
    assert row[0] == opp_pk


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
    own_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_ID,)).fetchone()[0]
    opp_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OPP_TEAM_ID,)).fetchone()[0]
    assert row[0] == own_pk         # home
    assert row[1] == opp_pk         # away
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
    own_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_ID,)).fetchone()[0]
    opp_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OPP_TEAM_ID,)).fetchone()[0]
    assert row[0] == opp_pk         # home (opponent)
    assert row[1] == own_pk         # away (own team)
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
    own_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_ID,)).fetchone()[0]
    assert row[0] == own_pk  # fallback: own team as home


# ---------------------------------------------------------------------------
# AC-8: FK prerequisite rows created automatically
# ---------------------------------------------------------------------------


def test_teams_rows_created_before_game_insert(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-8: teams rows for both home and away are created automatically."""
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})

    # No teams rows before loader is created.
    count_before = db.execute("SELECT COUNT(*) FROM teams;").fetchone()[0]
    assert count_before == 0

    loader = _make_loader(db)  # inserts own team as FK prerequisite
    loader.load_all(team_dir)  # inserts opponent team as FK prerequisite

    gc_uuids = {
        row[0]
        for row in db.execute("SELECT gc_uuid FROM teams;").fetchall()
    }
    assert _OWN_TEAM_ID in gc_uuids
    assert _OPP_TEAM_ID in gc_uuids


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


# ---------------------------------------------------------------------------
# AC-3 / AC-3b: gc_uuid=None scouting path -- no phantom team rows
# ---------------------------------------------------------------------------


def _insert_team_no_uuid(
    db: sqlite3.Connection,
    public_id: str = _OWN_TEAM_SLUG,
) -> int:
    """Insert a tracked team row without a gc_uuid (bridge returned 403 scenario)."""
    cur = db.execute(
        "INSERT INTO teams (public_id, name, membership_type, is_active) "
        "VALUES (?, 'Scouted Team', 'tracked', 0)",
        (public_id,),
    )
    db.commit()
    return cur.lastrowid


def test_gc_uuid_none_no_phantom_team_row(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-3: GameLoader with gc_uuid=None (scouting path) does not create phantom team row.

    Verifies:
    (a) No phantom team row with gc_uuid='' is created.
    (b) Stats are written against the correct team ID.
    (c) The opponent team row is created normally via _ensure_team_row.
    """
    from src.gamechanger.types import TeamRef

    pk = _insert_team_no_uuid(db)
    loader = GameLoader(
        db,
        season_id=_SEASON_ID,
        owned_team_ref=TeamRef(id=pk, gc_uuid=None, public_id=_OWN_TEAM_SLUG),
    )

    # Boxscore uses slug key for own team (standard layout for authenticated member teams)
    boxscore = _make_boxscore(own_key=_OWN_TEAM_SLUG, opp_key=_OPP_TEAM_ID)
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})

    result = loader.load_all(team_dir)

    assert result.errors == 0

    # (a) No phantom team row with gc_uuid=''
    phantom = db.execute(
        "SELECT id FROM teams WHERE gc_uuid = ?", ("",)
    ).fetchone()
    assert phantom is None, "Phantom team row with gc_uuid='' should not exist"

    # (b) Own team stats written against the correct team ID
    row = db.execute(
        "SELECT team_id FROM player_game_batting WHERE player_id = ?", (_PLAYER_OWN_1,)
    ).fetchone()
    assert row is not None, "Own team batting row should exist"
    assert row[0] == pk, f"Expected team_id={pk} (own team), got {row[0]}"

    # (c) Opponent team row created normally via _ensure_team_row
    opp_row = db.execute(
        "SELECT id FROM teams WHERE gc_uuid = ?", (_OPP_TEAM_ID,)
    ).fetchone()
    assert opp_row is not None, "Opponent team row should be created via _ensure_team_row"


def test_detect_team_keys_uuid_only_gc_uuid_none(db: sqlite3.Connection) -> None:
    """AC-3b: _detect_team_keys with two-UUID-key boxscore when gc_uuid is None.

    Verifies that when gc_uuid is None, the code does not match on empty string
    and own_key remains None (cannot identify own team from UUID-only boxscore).
    """
    from src.gamechanger.types import TeamRef

    pk = _insert_team_no_uuid(db)
    loader = GameLoader(
        db,
        season_id=_SEASON_ID,
        owned_team_ref=TeamRef(id=pk, gc_uuid=None, public_id=_OWN_TEAM_SLUG),
    )

    # Boxscore with two UUID keys -- no slug key (opponent-vs-opponent scenario)
    uuid_key_1 = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    uuid_key_2 = _OPP_TEAM_ID
    raw = {uuid_key_1: {}, uuid_key_2: {}}

    own_key, opp_key = loader._detect_team_keys(raw)

    # With gc_uuid=None, own team cannot be matched from UUID-only boxscore.
    # own_key must remain None (no empty-string match should occur).
    assert own_key is None, (
        f"own_key should be None when gc_uuid is None in UUID-only boxscore, got {own_key!r}"
    )

    # No phantom team rows should be created by _detect_team_keys (it only reads)
    phantom = db.execute("SELECT id FROM teams WHERE gc_uuid = ''").fetchone()
    assert phantom is None, "No phantom row with gc_uuid='' should exist"


# ---------------------------------------------------------------------------
# E-117-01: Extended stat coverage (AC-8 through AC-11)
# ---------------------------------------------------------------------------


def _make_full_boxscore() -> dict:
    """Boxscore with non-zero values for all 12 new stat columns.

    Batting extras: R (main), TB, HBP, CS in extras; SHF and E present too.
    Pitching extras: R (main), WP, HBP, pitches, total_strikes, BF in extras.
    """
    return {
        _OWN_TEAM_SLUG: {
            "players": [],
            "groups": [
                {
                    "category": "lineup",
                    "stats": [
                        {
                            "player_id": _PLAYER_OWN_1,
                            "player_text": "(CF)",
                            "is_primary": True,
                            "stats": {
                                "AB": 4, "R": 2, "H": 3, "RBI": 2, "BB": 1, "SO": 0
                            },
                        }
                    ],
                    "extra": [
                        {"stat_name": "2B",  "stats": [{"player_id": _PLAYER_OWN_1, "value": 1}]},
                        {"stat_name": "TB",  "stats": [{"player_id": _PLAYER_OWN_1, "value": 5}]},
                        {"stat_name": "HBP", "stats": [{"player_id": _PLAYER_OWN_1, "value": 1}]},
                        {"stat_name": "CS",  "stats": [{"player_id": _PLAYER_OWN_1, "value": 1}]},
                        {"stat_name": "SHF", "stats": [{"player_id": _PLAYER_OWN_1, "value": 2}]},
                        {"stat_name": "E",   "stats": [{"player_id": _PLAYER_OWN_1, "value": 1}]},
                    ],
                },
                {
                    "category": "pitching",
                    "stats": [
                        {
                            "player_id": _PLAYER_OWN_P1,
                            "player_text": "(W)",
                            "stats": {
                                "IP": 6, "H": 4, "R": 2, "ER": 2, "BB": 1, "SO": 8
                            },
                        }
                    ],
                    "extra": [
                        {"stat_name": "WP",  "stats": [{"player_id": _PLAYER_OWN_P1, "value": 1}]},
                        {"stat_name": "HBP", "stats": [{"player_id": _PLAYER_OWN_P1, "value": 1}]},
                        {"stat_name": "#P",  "stats": [{"player_id": _PLAYER_OWN_P1, "value": 87}]},
                        {"stat_name": "TS",  "stats": [{"player_id": _PLAYER_OWN_P1, "value": 57}]},
                        {"stat_name": "BF",  "stats": [{"player_id": _PLAYER_OWN_P1, "value": 24}]},
                    ],
                },
            ],
        },
        _OPP_TEAM_ID: {
            "players": [],
            "groups": [
                {
                    "category": "lineup",
                    "stats": [
                        {
                            "player_id": _PLAYER_OPP_1,
                            "player_text": "(1B)",
                            "stats": {"AB": 3, "R": 0, "H": 1, "RBI": 0, "BB": 0, "SO": 1},
                        }
                    ],
                    "extra": [],
                },
                {
                    "category": "pitching",
                    "stats": [
                        {
                            "player_id": _PLAYER_OPP_P1,
                            "player_text": "(L)",
                            "stats": {"IP": 5, "H": 7, "R": 5, "ER": 5, "BB": 2, "SO": 4},
                        }
                    ],
                    "extra": [],
                },
            ],
        },
    }


def test_batting_r_stored_from_main_stats(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-8/9: Batting R from main stats is stored in player_game_batting.r."""
    boxscore = _make_full_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT r FROM player_game_batting WHERE player_id = ? AND game_id = ?",
        (_PLAYER_OWN_1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 2


def test_batting_tb_hbp_cs_stored_from_extras(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-9: TB, HBP, CS from extras array are stored correctly."""
    boxscore = _make_full_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT tb, hbp, cs FROM player_game_batting WHERE player_id = ? AND game_id = ?",
        (_PLAYER_OWN_1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 5   # tb
    assert row[1] == 1   # hbp
    assert row[2] == 1   # cs


def test_batting_shf_e_stored_when_present(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-9: SHF and E store integer values when present in extras."""
    boxscore = _make_full_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT shf, e FROM player_game_batting WHERE player_id = ? AND game_id = ?",
        (_PLAYER_OWN_1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 2   # shf
    assert row[1] == 1   # e


def test_batting_shf_e_null_when_absent(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-9: SHF and E are NULL when not present in extras (nullable columns)."""
    # Default boxscore has no extras -- SHF and E will be absent.
    boxscore = _make_boxscore(batting_extra=[])
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT shf, e FROM player_game_batting WHERE player_id = ? AND game_id = ?",
        (_PLAYER_OWN_1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] is None, f"shf should be NULL when absent, got {row[0]}"
    assert row[1] is None, f"e should be NULL when absent, got {row[1]}"


def test_batting_hbp_cs_zero_when_absent(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-9: HBP and CS are 0 when not present in extras (sparse but confirmed in API)."""
    boxscore = _make_boxscore(batting_extra=[])
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT hbp, cs FROM player_game_batting WHERE player_id = ? AND game_id = ?",
        (_PLAYER_OWN_1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 0, f"hbp should be 0 when absent, got {row[0]}"
    assert row[1] == 0, f"cs should be 0 when absent, got {row[1]}"


def test_pitching_r_stored_from_main_stats(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-10: Pitching R from main stats is stored in player_game_pitching.r."""
    boxscore = _make_full_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT r FROM player_game_pitching WHERE player_id = ? AND game_id = ?",
        (_PLAYER_OWN_P1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 2


def test_pitching_new_extras_stored(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-10: WP, HBP, pitches, total_strikes, BF from extras are stored correctly."""
    boxscore = _make_full_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT wp, hbp, pitches, total_strikes, bf "
        "FROM player_game_pitching WHERE player_id = ? AND game_id = ?",
        (_PLAYER_OWN_P1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 1    # wp
    assert row[1] == 1    # hbp
    assert row[2] == 87   # pitches
    assert row[3] == 57   # total_strikes
    assert row[4] == 24   # bf


def test_pitching_extras_zero_when_absent(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-10: Pitching sparse extras (WP, HBP, pitches) are 0 when not in extras."""
    # Use default boxscore -- own pitcher has no extras array.
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT wp, hbp, pitches, total_strikes, bf "
        "FROM player_game_pitching WHERE player_id = ? AND game_id = ?",
        (_PLAYER_OWN_P1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 0, f"wp should be 0 when absent, got {row[0]}"
    assert row[1] == 0, f"hbp should be 0 when absent, got {row[1]}"
    assert row[2] == 0, f"pitches should be 0 when absent, got {row[2]}"
    assert row[3] == 0, f"total_strikes should be 0 when absent, got {row[3]}"
    assert row[4] == 0, f"bf should be 0 when absent, got {row[4]}"


def test_game_stream_id_stored(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-11: games.game_stream_id is populated from GameSummaryEntry.game_stream_id."""
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT game_stream_id FROM games WHERE game_id = ?", (_EVENT_ID,)
    ).fetchone()
    assert row is not None
    assert row[0] == _GAME_STREAM_ID, (
        f"Expected game_stream_id={_GAME_STREAM_ID!r}, got {row[0]!r}"
    )


# ---------------------------------------------------------------------------
# AC-8 (E-127-08): Dual-key summaries index -- event_id and game_stream_id
# ---------------------------------------------------------------------------


def test_boxscore_named_by_event_id_matches_summary(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-8: A boxscore file named by event_id is matched via the summaries index."""
    boxscore = _make_boxscore()
    # Write the boxscore file named by event_id (new crawler behaviour).
    team_dir = _write_team_dir(tmp_path, boxscores={_EVENT_ID: boxscore})
    loader = _make_loader(db)

    result = loader.load_all(team_dir)

    assert result.errors == 0
    assert result.skipped == 0
    row = db.execute("SELECT game_id FROM games WHERE game_id = ?", (_EVENT_ID,)).fetchone()
    assert row is not None, f"Expected game row for event_id={_EVENT_ID!r}"


def test_boxscore_named_by_game_stream_id_matches_summary(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-8: A boxscore file named by game_stream_id is also matched (backwards compat)."""
    boxscore = _make_boxscore()
    # Write the boxscore file named by game_stream_id (old crawler behaviour).
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    result = loader.load_all(team_dir)

    assert result.errors == 0
    assert result.skipped == 0
    row = db.execute("SELECT game_id FROM games WHERE game_id = ?", (_EVENT_ID,)).fetchone()
    assert row is not None, f"Expected game row for event_id={_EVENT_ID!r}"


def test_dual_key_index_event_id_and_game_stream_id_both_resolve(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-8: When both event_id and game_stream_id are distinct, either key resolves the summary."""
    # Confirm the test constants are distinct (test assumption).
    assert _EVENT_ID != _GAME_STREAM_ID

    boxscore = _make_boxscore()

    # Load using event_id-named file.
    team_dir_a = _write_team_dir(tmp_path, team_id="team-a", boxscores={_EVENT_ID: boxscore})
    loader_a = _make_loader(db)
    result_a = loader_a.load_all(team_dir_a)
    assert result_a.errors == 0

    # Same game loaded again using game_stream_id-named file -- should upsert, not error.
    from src.gamechanger.types import TeamRef
    pk_b = _insert_own_team(db, gc_uuid="team-b", public_id="slug-b")
    loader_b = GameLoader(
        db, season_id=_SEASON_ID,
        owned_team_ref=TeamRef(id=pk_b, gc_uuid="team-b", public_id="slug-b"),
    )
    summaries_b = [
        {
            "event_id": _EVENT_ID,
            "game_stream": {"id": _GAME_STREAM_ID, "opponent_id": _OPP_TEAM_ID},
            "home_away": "home",
            "owning_team_score": 5,
            "opponent_team_score": 2,
            "last_scoring_update": "2025-05-10T19:39:58.788Z",
        }
    ]
    team_dir_b = _write_team_dir(
        tmp_path, team_id="team-b",
        summaries=summaries_b,
        boxscores={_GAME_STREAM_ID: boxscore},
    )
    result_b = loader_b.load_all(team_dir_b)
    assert result_b.errors == 0

    # Only one game row should exist (idempotent upsert).
    count = db.execute("SELECT COUNT(*) FROM games WHERE game_id = ?", (_EVENT_ID,)).fetchone()[0]
    assert count == 1

# ---------------------------------------------------------------------------
# E-132-01: Opponent name resolution (AC-1, AC-3, AC-4, AC-6)
# ---------------------------------------------------------------------------

_OPP_NAME = "Blackhawks 14U"
_OPP_PROGENITOR_UUID = _OPP_TEAM_ID  # progenitor_team_id matches opponent_id in game_stream


def _write_opponents_json(team_dir: Path, opponents: list[dict] | None = None) -> None:
    """Write an opponents.json file in team_dir."""
    if opponents is None:
        opponents = [
            {
                "root_team_id": "root-uuid-different-from-progenitor",
                "owning_team_id": _OWN_TEAM_ID,
                "name": _OPP_NAME,
                "is_hidden": False,
                "progenitor_team_id": _OPP_PROGENITOR_UUID,
            }
        ]
    (team_dir / "opponents.json").write_text(json.dumps(opponents), encoding="utf-8")


def _write_schedule_json(team_dir: Path, events: list[dict] | None = None) -> None:
    """Write a schedule.json file in team_dir."""
    if events is None:
        events = [
            {
                "id": _EVENT_ID,
                "pregame_data": {
                    "opponent_id": _OPP_PROGENITOR_UUID,
                    "opponent_name": _OPP_NAME,
                },
            }
        ]
    (team_dir / "schedule.json").write_text(json.dumps(events), encoding="utf-8")


def test_ensure_team_row_with_name_creates_named_row(db: sqlite3.Connection) -> None:
    """_ensure_team_row() uses opponent_name as teams.name when provided."""
    loader = _make_loader(db)
    gc_uuid = "aaaabbbb-cccc-dddd-eeee-111122223333"
    pk = loader._ensure_team_row(gc_uuid, opponent_name="Kearney Mavericks 14U")

    row = db.execute("SELECT name FROM teams WHERE id = ?", (pk,)).fetchone()
    assert row is not None
    assert row[0] == "Kearney Mavericks 14U"


def test_ensure_team_row_without_name_falls_back_to_uuid(db: sqlite3.Connection) -> None:
    """_ensure_team_row() without opponent_name uses UUID as teams.name (legacy)."""
    loader = _make_loader(db)
    gc_uuid = "bbbbcccc-dddd-eeee-ffff-222233334444"
    pk = loader._ensure_team_row(gc_uuid)

    row = db.execute("SELECT name FROM teams WHERE id = ?", (pk,)).fetchone()
    assert row is not None
    assert row[0] == gc_uuid


def test_ensure_team_row_updates_uuid_stub_with_name(db: sqlite3.Connection) -> None:
    """AC-4: When existing row has name == gc_uuid, it is updated to the real name."""
    loader = _make_loader(db)
    gc_uuid = "ccccdddd-eeee-ffff-aaaa-333344445555"

    # Create UUID-stub row (name == gc_uuid).
    stub_pk = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) VALUES (?, 'tracked', ?, 0)",
        (gc_uuid, gc_uuid),
    ).lastrowid
    db.commit()

    returned_pk = loader._ensure_team_row(gc_uuid, opponent_name="Real Team Name")

    assert returned_pk == stub_pk
    row = db.execute("SELECT name FROM teams WHERE id = ?", (stub_pk,)).fetchone()
    assert row[0] == "Real Team Name"


def test_ensure_team_row_preserves_existing_non_uuid_name(db: sqlite3.Connection) -> None:
    """AC-4: When existing row has a non-UUID name, it is NOT overwritten."""
    loader = _make_loader(db)
    gc_uuid = "ddddeee-ffff-aaaa-bbbb-444455556666"

    # Pre-existing row with a real name (set by opponent_resolver or admin).
    existing_pk = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) "
        "VALUES (?, 'tracked', ?, 0)",
        ("Existing Real Name", gc_uuid),
    ).lastrowid
    db.commit()

    returned_pk = loader._ensure_team_row(gc_uuid, opponent_name="Different Name")

    assert returned_pk == existing_pk
    row = db.execute("SELECT name FROM teams WHERE id = ?", (existing_pk,)).fetchone()
    assert row[0] == "Existing Real Name", "Non-UUID name must NOT be overwritten"


def test_build_opponent_name_lookup_reads_progenitor_team_id(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """_build_opponent_name_lookup() keys by progenitor_team_id (not root_team_id)."""
    loader = _make_loader(db)
    team_dir = tmp_path / "team"
    team_dir.mkdir()
    opponents = [
        {
            "root_team_id": "root-uuid-000-should-not-be-used",
            "name": "Nighthawks Navy",
            "is_hidden": False,
            "progenitor_team_id": "progenitor-uuid-aaa",
        },
        # Hidden entry: should be excluded.
        {
            "root_team_id": "root-uuid-hidden",
            "name": "Hidden Team",
            "is_hidden": True,
            "progenitor_team_id": "progenitor-uuid-hidden",
        },
        # Null progenitor: should be excluded from primary lookup.
        {
            "root_team_id": "root-uuid-null",
            "name": "No Progenitor Team",
            "is_hidden": False,
            "progenitor_team_id": None,
        },
    ]
    (team_dir / "opponents.json").write_text(json.dumps(opponents), encoding="utf-8")

    lookup = loader._build_opponent_name_lookup(team_dir)

    assert lookup.get("progenitor-uuid-aaa") == "Nighthawks Navy"
    assert "root-uuid-000-should-not-be-used" not in lookup
    assert "progenitor-uuid-hidden" not in lookup
    assert None not in lookup  # null progenitor_team_id must not be stored as a key


def test_build_opponent_name_lookup_supplements_from_schedule(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """_build_opponent_name_lookup() uses schedule.json to fill null-progenitor gaps."""
    loader = _make_loader(db)
    team_dir = tmp_path / "team"
    team_dir.mkdir()
    # opponents.json with one null progenitor (no name from that source).
    opponents = [
        {
            "root_team_id": "root-uuid-001",
            "name": "Primary Team",
            "is_hidden": False,
            "progenitor_team_id": "progenitor-001",
        },
    ]
    (team_dir / "opponents.json").write_text(json.dumps(opponents), encoding="utf-8")
    # schedule.json with an opponent not covered by opponents.json (different UUID).
    schedule = [
        {
            "id": "sched-event-001",
            "pregame_data": {
                "opponent_id": "progenitor-002",
                "opponent_name": "Schedule Supplement Team",
            },
        }
    ]
    (team_dir / "schedule.json").write_text(json.dumps(schedule), encoding="utf-8")

    lookup = loader._build_opponent_name_lookup(team_dir)

    assert lookup.get("progenitor-001") == "Primary Team"
    assert lookup.get("progenitor-002") == "Schedule Supplement Team"


def test_build_opponent_name_lookup_schedule_does_not_override_opponents(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """schedule.json supplement does not overwrite entries from opponents.json."""
    loader = _make_loader(db)
    team_dir = tmp_path / "team"
    team_dir.mkdir()
    shared_uuid = "shared-uuid-001"
    (team_dir / "opponents.json").write_text(
        json.dumps([{"name": "Opponents Name", "is_hidden": False, "progenitor_team_id": shared_uuid}]),
        encoding="utf-8",
    )
    (team_dir / "schedule.json").write_text(
        json.dumps([{"id": "ev", "pregame_data": {"opponent_id": shared_uuid, "opponent_name": "Schedule Name"}}]),
        encoding="utf-8",
    )

    lookup = loader._build_opponent_name_lookup(team_dir)

    assert lookup[shared_uuid] == "Opponents Name"  # opponents.json wins


def test_build_opponent_name_lookup_missing_files_returns_empty(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-3: _build_opponent_name_lookup() returns empty dict when files are absent."""
    loader = _make_loader(db)
    team_dir = tmp_path / "team"
    team_dir.mkdir()

    lookup = loader._build_opponent_name_lookup(team_dir)

    assert lookup == {}


def test_load_all_creates_opponent_row_with_name_from_opponents_json(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-1: load_all() creates opponent team row with name from opponents.json."""
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    _write_opponents_json(team_dir)
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT name FROM teams WHERE gc_uuid = ?", (_OPP_TEAM_ID,)
    ).fetchone()
    assert row is not None
    assert row[0] == _OPP_NAME, f"Expected '{_OPP_NAME}', got {row[0]!r}"


def test_load_all_creates_opponent_row_with_name_from_schedule_fallback(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-1: load_all() uses schedule.json when opponents.json has null progenitor_team_id."""
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    # opponents.json with null progenitor for this opponent.
    _write_opponents_json(team_dir, opponents=[
        {
            "root_team_id": "root-null-progenitor",
            "name": "Null Progenitor Team",
            "is_hidden": False,
            "progenitor_team_id": None,
        }
    ])
    _write_schedule_json(team_dir)
    loader = _make_loader(db)

    loader.load_all(team_dir)

    row = db.execute(
        "SELECT name FROM teams WHERE gc_uuid = ?", (_OPP_TEAM_ID,)
    ).fetchone()
    assert row is not None
    assert row[0] == _OPP_NAME


def test_load_all_falls_back_to_uuid_when_opponents_json_absent(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-3: load_all() falls back to UUID as name when opponents.json is missing."""
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)

    result = loader.load_all(team_dir)

    assert result.errors == 0
    row = db.execute(
        "SELECT name FROM teams WHERE gc_uuid = ?", (_OPP_TEAM_ID,)
    ).fetchone()
    assert row is not None
    assert row[0] == _OPP_TEAM_ID  # UUID used as name (fallback)


def test_load_all_self_heals_uuid_stub_on_reload(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-4: Re-running load_all() with opponents.json updates existing UUID-stub names."""
    # First load: no opponents.json → UUID-stub created.
    boxscore = _make_boxscore()
    team_dir = _write_team_dir(tmp_path, boxscores={_GAME_STREAM_ID: boxscore})
    loader = _make_loader(db)
    loader.load_all(team_dir)

    stub_row = db.execute(
        "SELECT id, name FROM teams WHERE gc_uuid = ?", (_OPP_TEAM_ID,)
    ).fetchone()
    assert stub_row is not None
    assert stub_row[1] == _OPP_TEAM_ID, "First load without opponents.json should create UUID-stub"

    # Second load: with opponents.json → stub should be healed.
    _write_opponents_json(team_dir)
    loader.load_all(team_dir)

    updated = db.execute(
        "SELECT name FROM teams WHERE id = ?", (stub_row[0],)
    ).fetchone()
    assert updated[0] == _OPP_NAME, f"Expected stub name to be updated to '{_OPP_NAME}', got {updated[0]!r}"


def test_load_file_uses_opponent_name(db: sqlite3.Connection, tmp_path: Path) -> None:
    """load_file() accepts opponent_name and uses it for the team row."""
    loader = _make_loader(db)
    boxscore = _make_boxscore()
    bs_path = _write_boxscore(tmp_path, boxscore)
    summary = _make_summary()

    loader.load_file(bs_path, summary, opponent_name="Provided Opponent Name")

    row = db.execute(
        "SELECT name FROM teams WHERE gc_uuid = ?", (_OPP_TEAM_ID,)
    ).fetchone()
    assert row is not None
    assert row[0] == "Provided Opponent Name"
