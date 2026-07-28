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

import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from src.gamechanger.loaders import LoadResult, ensure_season_row
from src.gamechanger.loaders.game_loader import GameLoader, GameSummaryEntry as _GameSummaryEntry

# ---------------------------------------------------------------------------
# Schema fixture
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MIGRATION_FILE = _PROJECT_ROOT / "migrations" / "001_initial_schema.sql"
# E-250-02: migration 008 drops seasons.season_type, team_opponents, and
# players.gc_athlete_profile_id. The fixture must apply it so the schema matches
# the season INSERTs (which no longer supply season_type).
_MIGRATION_008 = (
    _PROJECT_ROOT / "migrations" / "008_drop_identity_opponent_season_type.sql"
)
# E-264-01: migration 012 adds teams.innings_per_game, which ensure_team_row's
# INSERT now references. The partial-chain fixture must apply it so the teams
# schema matches the loader's team-row writes.
_MIGRATION_012 = (
    _PROJECT_ROOT / "migrations" / "012_teams_innings_per_game.sql"
)


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory SQLite connection with schema applied and FK enforcement on."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    conn.executescript(_MIGRATION_FILE.read_text(encoding="utf-8"))
    conn.executescript(_MIGRATION_008.read_text(encoding="utf-8"))
    conn.executescript(_MIGRATION_012.read_text(encoding="utf-8"))
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
    owning_score: int | None = 5,
    opponent_score: int | None = 2,
    opponent_id: str = _OPP_TEAM_ID,
) -> _GameSummaryEntry:
    return _GameSummaryEntry(
        event_id=event_id,
        game_stream_id=game_stream_id,
        home_away=home_away,
        owning_team_score=owning_score,
        opponent_team_score=opponent_score,
        opponent_id=opponent_id,
        date_source_instant="2025-05-10T19:39:58.788Z",
    )


def _make_boxscore(
    own_key: str = _OWN_TEAM_SLUG,
    opp_key: str = _OPP_TEAM_ID,
    own_batting: list[dict] | None = None,
    opp_batting: list[dict] | None = None,
    own_pitching: list[dict] | None = None,
    opp_pitching: list[dict] | None = None,
    batting_extra: list[dict] | None = None,
    own_players: list[dict] | None = None,
    opp_players: list[dict] | None = None,
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

    if own_players is None:
        own_players = []
    if opp_players is None:
        opp_players = []

    return {
        own_key: {
            "players": own_players,
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
            "players": opp_players,
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


def _insert_own_team(
    db: sqlite3.Connection,
    gc_uuid: str = _OWN_TEAM_ID,
    public_id: str = _OWN_TEAM_SLUG,
    season_year: int = 2025,
) -> int:
    """Insert own team stub into teams table and return its INTEGER PK."""
    cur = db.execute(
        "INSERT OR IGNORE INTO teams (gc_uuid, public_id, name, membership_type, is_active, season_year) "
        "VALUES (?, ?, ?, 'member', 1, ?)",
        (gc_uuid, public_id, gc_uuid, season_year),
    )
    if cur.rowcount:
        return cur.lastrowid
    return db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (gc_uuid,)).fetchone()[0]


def _make_loader(db: sqlite3.Connection, gc_uuid: str = _OWN_TEAM_ID) -> GameLoader:
    from src.gamechanger.types import TeamRef
    pk = _insert_own_team(db, gc_uuid=gc_uuid)
    loader = GameLoader(db, owned_team_ref=TeamRef(id=pk, gc_uuid=gc_uuid, public_id=_OWN_TEAM_SLUG))
    # ScoutingLoader ensures the season row in production; load_payload does not.
    ensure_season_row(db, loader._season_id)
    return loader


def _load_game(
    loader: GameLoader,
    boxscore: dict,
    summary: _GameSummaryEntry | None = None,
    opponent_name: str | None = None,
) -> LoadResult:
    """Load one in-memory boxscore through the loader's sole entry point."""
    return loader.load_payload(
        boxscore, summary if summary is not None else _make_summary(),
        opponent_name=opponent_name,
    )


# ---------------------------------------------------------------------------
# AC-1: Game upserted into games table
# ---------------------------------------------------------------------------


def test_game_record_inserted_into_games_table(db: sqlite3.Connection) -> None:
    """AC-1: load_payload inserts a games row with correct event_id."""
    boxscore = _make_boxscore()
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    row = db.execute("SELECT game_id FROM games WHERE game_id = ?;", (_EVENT_ID,)).fetchone()
    assert row is not None, f"Expected games row for event_id={_EVENT_ID}"


def test_game_record_has_correct_season_id(db: sqlite3.Connection) -> None:
    """AC-1: game row has correct season_id."""
    boxscore = _make_boxscore()
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    row = db.execute("SELECT season_id FROM games WHERE game_id = ?;", (_EVENT_ID,)).fetchone()
    assert row is not None
    assert row[0] == _SEASON_ID


def test_game_record_has_correct_game_date(db: sqlite3.Connection) -> None:
    """AC-1: game_date is the venue-LOCAL calendar date of date_source_instant.

    Since E-253-04 the loader derives game_date via ``derive_local_date`` (the
    game's timezone, else the operating-tz seam) rather than slicing the raw UTC
    ``date_source_instant[:10]`` prefix. This fixture's afternoon-Chicago instant
    resolves to the same local day (2025-05-10), so the asserted value is
    unchanged.
    """
    boxscore = _make_boxscore()
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    row = db.execute("SELECT game_date FROM games WHERE game_id = ?;", (_EVENT_ID,)).fetchone()
    assert row is not None
    assert row[0] == "2025-05-10"


def test_game_record_has_correct_scores(db: sqlite3.Connection) -> None:
    """AC-1: home_score and away_score populated correctly."""
    boxscore = _make_boxscore()
    loader = _make_loader(db)

    _load_game(loader, boxscore)

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


def test_batting_line_inserted_for_own_player(db: sqlite3.Connection) -> None:
    """AC-2: player_game_batting row created for own team player."""
    boxscore = _make_boxscore()
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    row = db.execute(
        "SELECT ab, h, rbi, bb, so FROM player_game_batting WHERE player_id = ? AND game_id = ?;",
        (_PLAYER_OWN_1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row == (3, 2, 1, 1, 0)


def test_pitching_line_inserted_with_ip_outs_conversion(db: sqlite3.Connection) -> None:
    """AC-2: IP=5 in boxscore -> ip_outs=15 in DB (1 IP = 3 outs)."""
    boxscore = _make_boxscore()
    loader = _make_loader(db)

    _load_game(loader, boxscore)

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


def test_load_payload_twice_is_idempotent(db: sqlite3.Connection) -> None:
    """AC-2: Running load_payload twice produces same DB state (no duplicates)."""
    boxscore = _make_boxscore()
    loader = _make_loader(db)

    _load_game(loader, boxscore)
    _load_game(loader, boxscore)

    game_count = db.execute("SELECT COUNT(*) FROM games;").fetchone()[0]
    batting_count = db.execute("SELECT COUNT(*) FROM player_game_batting;").fetchone()[0]
    pitching_count = db.execute("SELECT COUNT(*) FROM player_game_pitching;").fetchone()[0]
    assert game_count == 1
    # 2 teams, 1 batter each
    assert batting_count == 2
    # 2 teams, 1 pitcher each
    assert pitching_count == 2


def test_batting_extras_zero_filled_when_absent(db: sqlite3.Connection) -> None:
    """AC-2: Extras (2B, 3B, HR, SB) default to 0 when not in extra[] array."""
    boxscore = _make_boxscore(batting_extra=[])  # no extras
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    row = db.execute(
        "SELECT doubles, triples, hr, sb FROM player_game_batting WHERE player_id = ? AND game_id = ?;",
        (_PLAYER_OWN_1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row == (0, 0, 0, 0)


def test_batting_extras_populated_from_extra_array(db: sqlite3.Connection) -> None:
    """AC-2: 2B and SB are read from the extra[] array correctly."""
    batting_extra = [
        {"stat_name": "2B", "stats": [{"player_id": _PLAYER_OWN_1, "value": 2}]},
        {"stat_name": "SB", "stats": [{"player_id": _PLAYER_OWN_1, "value": 1}]},
    ]
    boxscore = _make_boxscore(batting_extra=batting_extra)
    loader = _make_loader(db)

    _load_game(loader, boxscore)

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


def test_load_payload_returns_load_result(db: sqlite3.Connection) -> None:
    """AC-3: load_payload returns a LoadResult instance."""
    boxscore = _make_boxscore()
    loader = _make_loader(db)

    result = _load_game(loader, boxscore)

    assert isinstance(result, LoadResult)


def test_load_payload_counts_loaded_records(db: sqlite3.Connection) -> None:
    """AC-3: loaded count = 1 game + 2 batting rows + 2 pitching rows = 5."""
    boxscore = _make_boxscore()
    loader = _make_loader(db)

    result = _load_game(loader, boxscore)

    # 1 (game) + 1 (own batter) + 1 (own pitcher) + 1 (opp batter) + 1 (opp pitcher)
    assert result.loaded == 5
    assert result.errors == 0


# ---------------------------------------------------------------------------
# AC-4: Stub player for unknown player_id
# ---------------------------------------------------------------------------


def test_unknown_player_gets_stub_row(db: sqlite3.Connection) -> None:
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
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    row = db.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?;",
        (unknown_player,),
    ).fetchone()
    assert row is not None
    assert row[0] == "Unknown"
    assert row[1] == "Unknown"


def test_unknown_player_logs_debug(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-4: DEBUG is logged when a stub player row is created via ensure_player_row."""
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
    loader = _make_loader(db)

    with caplog.at_level(logging.DEBUG, logger="src.db.players"):
        _load_game(loader, boxscore)

    assert unknown_player in caplog.text


def test_known_player_does_not_get_overwritten(db: sqlite3.Connection) -> None:
    """AC-4: Pre-existing player row is not overwritten by stub logic."""
    # Pre-insert a real player record.
    db.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, 'Jake', 'Smith');",
        (_PLAYER_OWN_1,),
    )
    db.commit()

    boxscore = _make_boxscore()
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    row = db.execute(
        "SELECT first_name FROM players WHERE player_id = ?;", (_PLAYER_OWN_1,)
    ).fetchone()
    assert row is not None
    assert row[0] == "Jake"  # not overwritten with "Unknown"


# ---------------------------------------------------------------------------
# AC-5: Same game loaded from two team perspectives -> same DB state
# ---------------------------------------------------------------------------


def test_same_game_from_two_teams_is_idempotent(db: sqlite3.Connection) -> None:
    """AC-5: Loading the same game from two team perspectives upserts correctly."""
    from src.gamechanger.types import TeamRef

    boxscore = _make_boxscore()
    pk_a = _insert_own_team(db, gc_uuid="team-aaa", public_id="slug-aaa")
    pk_b = _insert_own_team(db, gc_uuid=_OWN_TEAM_ID)
    loader_a = GameLoader(db, owned_team_ref=TeamRef(id=pk_a, gc_uuid="team-aaa", public_id="slug-aaa"))
    loader_b = GameLoader(db, owned_team_ref=TeamRef(id=pk_b, gc_uuid=_OWN_TEAM_ID, public_id=_OWN_TEAM_SLUG))
    ensure_season_row(db, loader_a._season_id)

    loader_a.load_payload(boxscore, _make_summary())
    loader_b.load_payload(boxscore, _make_summary())

    count = db.execute("SELECT COUNT(*) FROM games WHERE game_id = ?;", (_EVENT_ID,)).fetchone()[0]
    assert count == 1


# ---------------------------------------------------------------------------
# AC-6: Asymmetric key handling (slug vs UUID)
# ---------------------------------------------------------------------------


def test_own_team_slug_key_detected_correctly(db: sqlite3.Connection) -> None:
    """AC-6: Own team identified by public_id slug (alphanumeric, no dashes)."""
    # Own team uses a slug, opponent uses UUID (default boxscore)
    boxscore = _make_boxscore(own_key="y24fFdnr3RAN", opp_key=_OPP_TEAM_ID)
    loader = _make_loader(db)

    result = _load_game(loader, boxscore)

    assert result.errors == 0
    # Own batting player should have team_id = INTEGER PK of own team
    row = db.execute(
        "SELECT team_id FROM player_game_batting WHERE player_id = ?;", (_PLAYER_OWN_1,)
    ).fetchone()
    assert row is not None
    own_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_ID,)).fetchone()[0]
    assert row[0] == own_pk


def test_opponent_uuid_key_detected_correctly(db: sqlite3.Connection) -> None:
    """AC-6: Opponent identified by UUID key (36 chars with dashes)."""
    boxscore = _make_boxscore()
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    row = db.execute(
        "SELECT team_id FROM player_game_batting WHERE player_id = ?;", (_PLAYER_OPP_1,)
    ).fetchone()
    assert row is not None
    # Opponent team row has gc_uuid=NULL (E-211); query by name (UUID used as fallback name).
    opp_pk = db.execute("SELECT id FROM teams WHERE name = ?", (_OPP_TEAM_ID,)).fetchone()[0]
    assert row[0] == opp_pk


# ---------------------------------------------------------------------------
# AC-7: home_team_id / away_team_id set via home_away field
# ---------------------------------------------------------------------------


def test_home_away_home_sets_own_team_as_home(db: sqlite3.Connection) -> None:
    """AC-7: home_away='home' -> own team is home_team_id."""
    boxscore = _make_boxscore()
    summary = _make_summary(home_away="home", owning_score=7, opponent_score=3)
    loader = _make_loader(db)

    _load_game(loader, boxscore, summary)

    row = db.execute(
        "SELECT home_team_id, away_team_id, home_score, away_score FROM games WHERE game_id = ?;",
        (_EVENT_ID,),
    ).fetchone()
    assert row is not None
    own_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_ID,)).fetchone()[0]
    opp_pk = db.execute("SELECT id FROM teams WHERE name = ?", (_OPP_TEAM_ID,)).fetchone()[0]
    assert row[0] == own_pk         # home
    assert row[1] == opp_pk         # away
    assert row[2] == 7              # home score
    assert row[3] == 3              # away score


def test_home_away_away_sets_opponent_as_home(db: sqlite3.Connection) -> None:
    """AC-7: home_away='away' -> opponent is home_team_id, own team is away."""
    boxscore = _make_boxscore()
    summary = _make_summary(home_away="away", owning_score=4, opponent_score=9)
    loader = _make_loader(db)

    _load_game(loader, boxscore, summary)

    row = db.execute(
        "SELECT home_team_id, away_team_id, home_score, away_score FROM games WHERE game_id = ?;",
        (_EVENT_ID,),
    ).fetchone()
    assert row is not None
    own_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_ID,)).fetchone()[0]
    opp_pk = db.execute("SELECT id FROM teams WHERE name = ?", (_OPP_TEAM_ID,)).fetchone()[0]
    assert row[0] == opp_pk         # home (opponent)
    assert row[1] == own_pk         # away (own team)
    assert row[2] == 9              # home score (opponent)
    assert row[3] == 4              # away score (own)


def test_home_away_none_defaults_to_own_team_as_home(db: sqlite3.Connection) -> None:
    """AC-7: home_away=None defaults own team to home (with warning logged)."""
    boxscore = _make_boxscore()
    summary = _make_summary(home_away=None)
    loader = _make_loader(db)

    _load_game(loader, boxscore, summary)

    row = db.execute(
        "SELECT home_team_id FROM games WHERE game_id = ?;", (_EVENT_ID,)
    ).fetchone()
    assert row is not None
    own_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_ID,)).fetchone()[0]
    assert row[0] == own_pk  # fallback: own team as home


# ---------------------------------------------------------------------------
# AC-8: FK prerequisite rows created automatically
# ---------------------------------------------------------------------------


def test_teams_rows_created_before_game_insert(db: sqlite3.Connection) -> None:
    """AC-8: teams rows for both home and away are created automatically.

    E-211: Opponent team row has gc_uuid=NULL (not the boxscore key).
    """
    boxscore = _make_boxscore()

    # No teams rows before loader is created.
    count_before = db.execute("SELECT COUNT(*) FROM teams;").fetchone()[0]
    assert count_before == 0

    loader = _make_loader(db)  # inserts own team as FK prerequisite
    _load_game(loader, boxscore)  # inserts opponent team as FK prerequisite

    teams = db.execute("SELECT gc_uuid, name FROM teams;").fetchall()
    gc_uuids = {row[0] for row in teams}
    names = {row[1] for row in teams}
    assert _OWN_TEAM_ID in gc_uuids, "Own team gc_uuid must be present"
    # E-211: opponent gc_uuid is now NULL; verify by name instead.
    assert _OPP_TEAM_ID in names, "Opponent row should exist with UUID as name fallback"
    assert len(teams) >= 2, "At least own + opponent team rows expected"


def test_load_succeeds_with_no_pre_existing_fk_rows(db: sqlite3.Connection) -> None:
    """AC-8: Load completes without FK errors even with empty tables."""
    boxscore = _make_boxscore()
    loader = _make_loader(db)

    result = _load_game(loader, boxscore)

    assert result.errors == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_non_dict_payload_returns_error(db: sqlite3.Connection) -> None:
    """A payload that is not a JSON object returns errors=1."""
    loader = _make_loader(db)

    result = loader.load_payload(["not", "a", "dict"], _make_summary())

    assert result.errors == 1


def test_batting_row_missing_player_id_is_skipped(db: sqlite3.Connection) -> None:
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
    loader = _make_loader(db)

    result = _load_game(loader, boxscore)

    assert result.skipped == 1
    # Valid batting row was still loaded.
    count = db.execute("SELECT COUNT(*) FROM player_game_batting WHERE game_id = ?;", (_EVENT_ID,)).fetchone()[0]
    assert count >= 1


def test_ip_zero_converts_to_zero_ip_outs(db: sqlite3.Connection) -> None:
    """IP=0 converts to ip_outs=0."""
    boxscore = _make_boxscore(
        own_pitching=[
            {"player_id": _PLAYER_OWN_P1, "stats": {"IP": 0, "H": 0, "R": 0, "ER": 0, "BB": 0, "SO": 0}}
        ]
    )
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    row = db.execute(
        "SELECT ip_outs FROM player_game_pitching WHERE player_id = ? AND game_id = ?;",
        (_PLAYER_OWN_P1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 0


def test_ip_one_third_converts_to_one_out(db: sqlite3.Connection) -> None:
    """IP=3.333... (3⅓ innings = 10 outs) converts correctly via round(float*3).

    The old int() truncation would have given 3*3=9 outs (wrong).
    """
    boxscore = _make_boxscore(
        own_pitching=[
            {"player_id": _PLAYER_OWN_P1, "stats": {"IP": 3.3333333333333335, "H": 3, "R": 1, "ER": 1, "BB": 1, "SO": 4}}
        ]
    )
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    row = db.execute(
        "SELECT ip_outs FROM player_game_pitching WHERE player_id = ? AND game_id = ?;",
        (_PLAYER_OWN_P1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 10, f"3⅓ IP should be 10 outs, got {row[0]}"


def test_ip_two_thirds_converts_to_two_outs(db: sqlite3.Connection) -> None:
    """IP=3.666... (3⅔ innings = 11 outs) converts correctly via round(float*3).

    The old int() truncation would have given 3*3=9 outs (wrong).
    """
    boxscore = _make_boxscore(
        own_pitching=[
            {"player_id": _PLAYER_OWN_P1, "stats": {"IP": 3.6666666666666665, "H": 2, "R": 0, "ER": 0, "BB": 0, "SO": 5}}
        ]
    )
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    row = db.execute(
        "SELECT ip_outs FROM player_game_pitching WHERE player_id = ? AND game_id = ?;",
        (_PLAYER_OWN_P1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 11, f"3⅔ IP should be 11 outs, got {row[0]}"


def test_multiple_games_for_one_team(db: sqlite3.Connection) -> None:
    """Multiple boxscore payloads for one team are all loaded."""
    loader = _make_loader(db)

    summary1 = _make_summary(
        event_id="event-001", game_stream_id="stream-001",
        home_away="home", owning_score=5, opponent_score=2,
    )
    summary2 = _make_summary(
        event_id="event-002", game_stream_id="stream-002",
        home_away="away", owning_score=3, opponent_score=1,
    )
    summary2 = replace(summary2, date_source_instant="2025-05-11T19:00:00Z")

    result1 = loader.load_payload(_make_boxscore(), summary1)
    result2 = loader.load_payload(_make_boxscore(), summary2)

    count = db.execute("SELECT COUNT(*) FROM games;").fetchone()[0]
    assert count == 2
    assert result1.errors == 0
    assert result2.errors == 0


# ---------------------------------------------------------------------------
# AC-3 / AC-3b: gc_uuid=None scouting path -- no phantom team rows
# ---------------------------------------------------------------------------


def _insert_team_no_uuid(
    db: sqlite3.Connection,
    public_id: str = _OWN_TEAM_SLUG,
) -> int:
    """Insert a tracked team row without a gc_uuid (bridge returned 403 scenario)."""
    cur = db.execute(
        "INSERT INTO teams (public_id, name, membership_type, is_active, season_year) "
        "VALUES (?, 'Scouted Team', 'tracked', 0, 2025)",
        (public_id,),
    )
    db.commit()
    return cur.lastrowid


def test_gc_uuid_none_no_phantom_team_row(db: sqlite3.Connection) -> None:
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
        owned_team_ref=TeamRef(id=pk, gc_uuid=None, public_id=_OWN_TEAM_SLUG),
    )
    ensure_season_row(db, loader._season_id)

    # Boxscore uses slug key for own team (standard layout for authenticated member teams)
    boxscore = _make_boxscore(own_key=_OWN_TEAM_SLUG, opp_key=_OPP_TEAM_ID)

    result = _load_game(loader, boxscore)

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

    # (c) Opponent team row created normally via _ensure_team_row (gc_uuid=NULL, name=UUID fallback)
    opp_row = db.execute(
        "SELECT id FROM teams WHERE name = ?", (_OPP_TEAM_ID,)
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
# E-247-03 AC-4: HARD GATE -- boxscore key classification must stay
# byte-identical after _UUID_RE was swapped for is_gc_uuid. A botched anchor or
# a dropped IGNORECASE flag would flip own-vs-opponent classification and pull
# the wrong team's boxscore. This pins the uuid_keys/slug_keys split (which
# drives own_key/opp_key) over a representative key set, calling the real
# _detect_team_keys so it exercises whichever predicate the source uses.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw_keys, expected_own, expected_opp",
    [
        # Canonical lowercase UUID opponent + public_id slug own key.
        (
            ["y24fFdnr3RAN", "16d38cf9-4f73-438c-83e4-1c28fbb23628"],
            "y24fFdnr3RAN",
            "16d38cf9-4f73-438c-83e4-1c28fbb23628",
        ),
        # Uppercase UUID must still classify as a UUID (re.IGNORECASE): if the
        # flag were dropped, this opponent key would be misread as the slug.
        (
            ["y24fFdnr3RAN", "16D38CF9-4F73-438C-83E4-1C28FBB23628"],
            "y24fFdnr3RAN",
            "16D38CF9-4F73-438C-83E4-1C28FBB23628",
        ),
        # A dashed-but-non-canonical key (wrong group lengths) is NOT a UUID and
        # must be classified as the slug/own key -- full ^...$ anchoring.
        (
            ["team-uuid-jv-001", "16d38cf9-4f73-438c-83e4-1c28fbb23628"],
            "team-uuid-jv-001",
            "16d38cf9-4f73-438c-83e4-1c28fbb23628",
        ),
    ],
)
def test_detect_team_keys_classification_byte_identical(
    db: sqlite3.Connection,
    raw_keys: list[str],
    expected_own: str,
    expected_opp: str,
) -> None:
    """AC-4: own/opponent key split is driven only by the UUID predicate."""
    loader = _make_loader(db)
    raw = {k: {} for k in raw_keys}

    own_key, opp_key = loader._detect_team_keys(raw)

    assert own_key == expected_own
    assert opp_key == expected_opp


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


def test_batting_r_stored_from_main_stats(db: sqlite3.Connection) -> None:
    """AC-8/9: Batting R from main stats is stored in player_game_batting.r."""
    boxscore = _make_full_boxscore()
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    row = db.execute(
        "SELECT r FROM player_game_batting WHERE player_id = ? AND game_id = ?",
        (_PLAYER_OWN_1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 2


def test_batting_tb_hbp_cs_stored_from_extras(db: sqlite3.Connection) -> None:
    """AC-9: TB, HBP, CS from extras array are stored correctly."""
    boxscore = _make_full_boxscore()
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    row = db.execute(
        "SELECT tb, hbp, cs FROM player_game_batting WHERE player_id = ? AND game_id = ?",
        (_PLAYER_OWN_1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 5   # tb
    assert row[1] == 1   # hbp
    assert row[2] == 1   # cs


def test_batting_shf_e_stored_when_present(db: sqlite3.Connection) -> None:
    """AC-9: SHF and E store integer values when present in extras."""
    boxscore = _make_full_boxscore()
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    row = db.execute(
        "SELECT shf, e FROM player_game_batting WHERE player_id = ? AND game_id = ?",
        (_PLAYER_OWN_1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 2   # shf
    assert row[1] == 1   # e


def test_batting_shf_e_null_when_absent(db: sqlite3.Connection) -> None:
    """AC-9: SHF and E are NULL when not present in extras (nullable columns)."""
    # Default boxscore has no extras -- SHF and E will be absent.
    boxscore = _make_boxscore(batting_extra=[])
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    row = db.execute(
        "SELECT shf, e FROM player_game_batting WHERE player_id = ? AND game_id = ?",
        (_PLAYER_OWN_1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] is None, f"shf should be NULL when absent, got {row[0]}"
    assert row[1] is None, f"e should be NULL when absent, got {row[1]}"


def test_batting_hbp_cs_zero_when_absent(db: sqlite3.Connection) -> None:
    """AC-9: HBP and CS are 0 when not present in extras (sparse but confirmed in API)."""
    boxscore = _make_boxscore(batting_extra=[])
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    row = db.execute(
        "SELECT hbp, cs FROM player_game_batting WHERE player_id = ? AND game_id = ?",
        (_PLAYER_OWN_1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 0, f"hbp should be 0 when absent, got {row[0]}"
    assert row[1] == 0, f"cs should be 0 when absent, got {row[1]}"


def test_pitching_r_stored_from_main_stats(db: sqlite3.Connection) -> None:
    """AC-10: Pitching R from main stats is stored in player_game_pitching.r."""
    boxscore = _make_full_boxscore()
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    row = db.execute(
        "SELECT r FROM player_game_pitching WHERE player_id = ? AND game_id = ?",
        (_PLAYER_OWN_P1, _EVENT_ID),
    ).fetchone()
    assert row is not None
    assert row[0] == 2


def test_pitching_new_extras_stored(db: sqlite3.Connection) -> None:
    """AC-10: WP, HBP, pitches, total_strikes, BF from extras are stored correctly."""
    boxscore = _make_full_boxscore()
    loader = _make_loader(db)

    _load_game(loader, boxscore)

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


def test_pitching_extras_zero_when_absent(db: sqlite3.Connection) -> None:
    """AC-10: Pitching sparse extras (WP, HBP, pitches) are 0 when not in extras."""
    # Use default boxscore -- own pitcher has no extras array.
    boxscore = _make_boxscore()
    loader = _make_loader(db)

    _load_game(loader, boxscore)

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


def test_game_stream_id_stored(db: sqlite3.Connection) -> None:
    """AC-11: games.game_stream_id is populated from GameSummaryEntry.game_stream_id."""
    boxscore = _make_boxscore()
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    row = db.execute(
        "SELECT game_stream_id FROM games WHERE game_id = ?", (_EVENT_ID,)
    ).fetchone()
    assert row is not None
    assert row[0] == _GAME_STREAM_ID, (
        f"Expected game_stream_id={_GAME_STREAM_ID!r}, got {row[0]!r}"
    )


# ---------------------------------------------------------------------------
# E-132-01: Opponent name resolution (AC-1, AC-3, AC-4, AC-6)
# ---------------------------------------------------------------------------

_OPP_NAME = "Blackhawks 14U"
_OPP_PROGENITOR_UUID = _OPP_TEAM_ID  # progenitor_team_id matches opponent_id in game_stream


def test_ensure_team_row_with_name_creates_named_row(db: sqlite3.Connection) -> None:
    """_ensure_team_row() uses opponent_name as teams.name when provided.

    E-211: gc_uuid is always None -- the boxscore identifier is never stored.
    """
    loader = _make_loader(db)
    identifier = "aaaabbbb-cccc-dddd-eeee-111122223333"
    pk = loader._ensure_team_row(identifier, opponent_name="Kearney Mavericks 14U")

    row = db.execute("SELECT name, gc_uuid FROM teams WHERE id = ?", (pk,)).fetchone()
    assert row is not None
    assert row[0] == "Kearney Mavericks 14U"
    assert row[1] is None, "gc_uuid must be NULL -- boxscore key must not be stored"


def test_ensure_team_row_without_name_falls_back_to_identifier(db: sqlite3.Connection) -> None:
    """_ensure_team_row() without opponent_name uses identifier as teams.name.

    E-211: The identifier (boxscore key) is used only as a name fallback,
    never stored as gc_uuid.
    """
    loader = _make_loader(db)
    identifier = "bbbbcccc-dddd-eeee-ffff-222233334444"
    pk = loader._ensure_team_row(identifier)

    row = db.execute("SELECT name, gc_uuid FROM teams WHERE id = ?", (pk,)).fetchone()
    assert row is not None
    assert row[0] == identifier, "Name should be the identifier string"
    assert row[1] is None, "gc_uuid must be NULL"


def test_ensure_team_row_deduplicates_by_name_and_season(db: sqlite3.Connection) -> None:
    """E-211: Repeated calls with same name match by name+season_year (step 3)."""
    loader = _make_loader(db)
    identifier = "ccccdddd-eeee-ffff-aaaa-333344445555"

    pk1 = loader._ensure_team_row(identifier, opponent_name="Real Team Name")
    pk2 = loader._ensure_team_row(identifier, opponent_name="Real Team Name")

    assert pk1 == pk2, "Same opponent_name + season_year should reuse the team row"


def test_ensure_team_row_does_not_match_by_gc_uuid(db: sqlite3.Connection) -> None:
    """E-211: A pre-existing row with gc_uuid=X is NOT matched when identifier=X.

    This is the core anti-contamination behavior: _ensure_team_row no longer
    passes gc_uuid to the shared function, so gc_uuid-based matching does not occur.
    """
    loader = _make_loader(db)
    identifier = "ddddeee-ffff-aaaa-bbbb-444455556666"

    # Pre-existing row with gc_uuid set (e.g., by the search resolver).
    existing_pk = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) "
        "VALUES (?, 'tracked', ?, 0)",
        ("Existing Real Name", identifier),
    ).lastrowid
    db.commit()

    # _ensure_team_row with opponent_name creates a new row (name doesn't match).
    returned_pk = loader._ensure_team_row(identifier, opponent_name="Different Name")

    # Should NOT return the existing row (no gc_uuid match path).
    assert returned_pk != existing_pk, (
        "_ensure_team_row must not match by gc_uuid -- it passes gc_uuid=None"
    )


def test_load_payload_falls_back_to_uuid_when_no_opponent_name(
    db: sqlite3.Connection,
) -> None:
    """AC-3: with no opponent_name supplied, the opponent UUID is the name fallback."""
    boxscore = _make_boxscore()
    loader = _make_loader(db)

    result = _load_game(loader, boxscore)

    assert result.errors == 0
    # Opponent row has gc_uuid=NULL (E-211); UUID string is used as name fallback.
    row = db.execute(
        "SELECT name FROM teams WHERE name = ?", (_OPP_TEAM_ID,)
    ).fetchone()
    assert row is not None
    assert row[0] == _OPP_TEAM_ID  # UUID used as name (fallback)


def test_load_payload_with_opponent_name_creates_named_row(
    db: sqlite3.Connection,
) -> None:
    """Re-running with an opponent_name creates a named opponent row.

    E-211: Since gc_uuid=None is passed for opponents, name-based dedup applies.
    The first load without an opponent_name creates a row with the UUID as name.
    The second load with an opponent_name creates a new row with the real name
    (different name = different team row under name-based dedup).
    """
    # First load: no opponent_name → UUID-stub created (gc_uuid=NULL, name=UUID).
    boxscore = _make_boxscore()
    loader = _make_loader(db)
    _load_game(loader, boxscore)

    stub_row = db.execute(
        "SELECT id, name FROM teams WHERE name = ?", (_OPP_TEAM_ID,)
    ).fetchone()
    assert stub_row is not None
    assert stub_row[1] == _OPP_TEAM_ID, "First load without a name should create a UUID-stub"

    # Second load: with opponent_name → creates a new row with real name.
    _load_game(loader, boxscore, opponent_name=_OPP_NAME)

    named_row = db.execute(
        "SELECT id, name FROM teams WHERE name = ?", (_OPP_NAME,)
    ).fetchone()
    assert named_row is not None, f"Expected row with name '{_OPP_NAME}'"
    assert named_row[0] != stub_row[0], "Named row should be distinct from UUID-stub row"


def test_load_payload_uses_opponent_name(db: sqlite3.Connection) -> None:
    """load_payload() accepts opponent_name and uses it for the team row."""
    loader = _make_loader(db)
    boxscore = _make_boxscore()

    loader.load_payload(boxscore, _make_summary(), opponent_name="Provided Opponent Name")

    # Opponent row has gc_uuid=NULL (E-211); find by name.
    row = db.execute(
        "SELECT name FROM teams WHERE name = ?", ("Provided Opponent Name",)
    ).fetchone()
    assert row is not None
    assert row[0] == "Provided Opponent Name"


# ---------------------------------------------------------------------------
# E-169-01: Player name extraction from boxscore players array
# ---------------------------------------------------------------------------


def test_new_player_gets_real_name_from_boxscore(db: sqlite3.Connection) -> None:
    """AC-1: New player row is created with real name from boxscore players array."""
    boxscore = _make_boxscore(
        own_players=[
            {"id": _PLAYER_OWN_1, "first_name": "Caleb", "last_name": "Davis", "number": "23"},
            {"id": _PLAYER_OWN_P1, "first_name": "Marcus", "last_name": "Lee", "number": "11"},
        ],
        opp_players=[
            {"id": _PLAYER_OPP_1, "first_name": "Jake", "last_name": "Miller", "number": "7"},
            {"id": _PLAYER_OPP_P1, "first_name": "Tyler", "last_name": "Brown", "number": "15"},
        ],
    )
    loader = _make_loader(db)

    loader.load_payload(boxscore, _make_summary())

    row = db.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?",
        (_PLAYER_OWN_1,),
    ).fetchone()
    assert row == ("Caleb", "Davis"), f"Expected real name, got {row}"


def test_stub_player_upgraded_to_real_name(db: sqlite3.Connection) -> None:
    """AC-2: Existing stub player (Unknown Unknown) is upgraded to real name."""
    # Pre-insert a stub player row.
    db.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, 'Unknown', 'Unknown')",
        (_PLAYER_OWN_1,),
    )
    db.commit()

    boxscore = _make_boxscore(
        own_players=[
            {"id": _PLAYER_OWN_1, "first_name": "Caleb", "last_name": "Davis", "number": "23"},
            {"id": _PLAYER_OWN_P1, "first_name": "Marcus", "last_name": "Lee"},
        ],
    )
    loader = _make_loader(db)

    loader.load_payload(boxscore, _make_summary())

    row = db.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?",
        (_PLAYER_OWN_1,),
    ).fetchone()
    assert row == ("Caleb", "Davis"), f"Expected stub to be upgraded, got {row}"


def test_existing_real_name_not_overwritten(db: sqlite3.Connection) -> None:
    """AC-3: Existing player with real name is NOT overwritten by boxscore data."""
    # Pre-insert a player with a real name (e.g., from roster loader).
    db.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, 'RealFirst', 'RealLast')",
        (_PLAYER_OWN_1,),
    )
    db.commit()

    boxscore = _make_boxscore(
        own_players=[
            {"id": _PLAYER_OWN_1, "first_name": "Caleb", "last_name": "Davis", "number": "23"},
            {"id": _PLAYER_OWN_P1, "first_name": "Marcus", "last_name": "Lee"},
        ],
    )
    loader = _make_loader(db)

    loader.load_payload(boxscore, _make_summary())

    row = db.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?",
        (_PLAYER_OWN_1,),
    ).fetchone()
    assert row == ("RealFirst", "RealLast"), f"Expected real name preserved, got {row}"


def test_jersey_number_creates_roster_row(db: sqlite3.Connection) -> None:
    """AC-4: Jersey number from boxscore creates a team_rosters row."""
    boxscore = _make_boxscore(
        own_players=[
            {"id": _PLAYER_OWN_1, "first_name": "Caleb", "last_name": "Davis", "number": "23"},
            {"id": _PLAYER_OWN_P1, "first_name": "Marcus", "last_name": "Lee", "number": "11"},
        ],
    )
    loader = _make_loader(db)

    loader.load_payload(boxscore, _make_summary())

    own_team_id = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_ID,)).fetchone()[0]
    row = db.execute(
        "SELECT jersey_number, position FROM team_rosters WHERE team_id = ? AND player_id = ? AND season_id = ?",
        (own_team_id, _PLAYER_OWN_1, _SEASON_ID),
    ).fetchone()
    assert row is not None, "Expected team_rosters row to be created"
    assert row[0] == "23", f"Expected jersey_number='23', got {row[0]!r}"
    assert row[1] is None, "position should be NULL for boxscore-sourced rows"


def test_jersey_number_backfills_null(db: sqlite3.Connection) -> None:
    """AC-4: Existing roster row with NULL jersey_number gets backfilled."""
    # Create the player and roster row first (as if roster loader ran without jersey number).
    db.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, 'Caleb', 'Davis')",
        (_PLAYER_OWN_1,),
    )
    loader = _make_loader(db)
    own_team_id = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_ID,)).fetchone()[0]
    db.execute(
        "INSERT INTO team_rosters (team_id, player_id, season_id, jersey_number, position) VALUES (?, ?, ?, NULL, 'CF')",
        (own_team_id, _PLAYER_OWN_1, _SEASON_ID),
    )
    db.commit()

    boxscore = _make_boxscore(
        own_players=[
            {"id": _PLAYER_OWN_1, "first_name": "Caleb", "last_name": "Davis", "number": "23"},
            {"id": _PLAYER_OWN_P1, "first_name": "Marcus", "last_name": "Lee"},
        ],
    )
    loader.load_payload(boxscore, _make_summary())

    row = db.execute(
        "SELECT jersey_number, position FROM team_rosters WHERE team_id = ? AND player_id = ? AND season_id = ?",
        (own_team_id, _PLAYER_OWN_1, _SEASON_ID),
    ).fetchone()
    assert row[0] == "23", f"Expected jersey_number backfilled to '23', got {row[0]!r}"
    assert row[1] == "CF", "Existing position should NOT be overwritten"


def test_jersey_number_not_overwritten_when_set(db: sqlite3.Connection) -> None:
    """AC-4: Existing roster row with non-NULL jersey_number is NOT overwritten."""
    db.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, 'Caleb', 'Davis')",
        (_PLAYER_OWN_1,),
    )
    loader = _make_loader(db)
    own_team_id = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_ID,)).fetchone()[0]
    db.execute(
        "INSERT INTO team_rosters (team_id, player_id, season_id, jersey_number) VALUES (?, ?, ?, '99')",
        (own_team_id, _PLAYER_OWN_1, _SEASON_ID),
    )
    db.commit()

    boxscore = _make_boxscore(
        own_players=[
            {"id": _PLAYER_OWN_1, "first_name": "Caleb", "last_name": "Davis", "number": "23"},
            {"id": _PLAYER_OWN_P1, "first_name": "Marcus", "last_name": "Lee"},
        ],
    )
    loader.load_payload(boxscore, _make_summary())

    row = db.execute(
        "SELECT jersey_number FROM team_rosters WHERE team_id = ? AND player_id = ? AND season_id = ?",
        (own_team_id, _PLAYER_OWN_1, _SEASON_ID),
    ).fetchone()
    assert row[0] == "99", f"Expected jersey_number to stay '99', got {row[0]!r}"


def test_opponent_player_names_extracted(db: sqlite3.Connection) -> None:
    """AC-5: Player names are extracted from both own and opponent teams."""
    boxscore = _make_boxscore(
        own_players=[
            {"id": _PLAYER_OWN_1, "first_name": "Caleb", "last_name": "Davis"},
            {"id": _PLAYER_OWN_P1, "first_name": "Marcus", "last_name": "Lee"},
        ],
        opp_players=[
            {"id": _PLAYER_OPP_1, "first_name": "Jake", "last_name": "Miller"},
            {"id": _PLAYER_OPP_P1, "first_name": "Tyler", "last_name": "Brown"},
        ],
    )
    loader = _make_loader(db)

    loader.load_payload(boxscore, _make_summary())

    opp_row = db.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?",
        (_PLAYER_OPP_1,),
    ).fetchone()
    assert opp_row == ("Jake", "Miller"), f"Expected opponent player real name, got {opp_row}"

    opp_pitcher = db.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?",
        (_PLAYER_OPP_P1,),
    ).fetchone()
    assert opp_pitcher == ("Tyler", "Brown"), f"Expected opponent pitcher real name, got {opp_pitcher}"


def test_player_without_name_in_players_array_gets_stub(db: sqlite3.Connection) -> None:
    """When a player appears in stats but not in players array, they get a stub."""
    boxscore = _make_boxscore(
        own_players=[],  # No player info provided
        opp_players=[],
    )
    loader = _make_loader(db)

    loader.load_payload(boxscore, _make_summary())

    row = db.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?",
        (_PLAYER_OWN_1,),
    ).fetchone()
    assert row == ("Unknown", "Unknown"), f"Expected stub name, got {row}"


# ---------------------------------------------------------------------------
# E-197-02 AC-9: USSSA team produces correct derived season_id
# ---------------------------------------------------------------------------


def test_usssa_team_produces_correct_season_id(db: sqlite3.Connection) -> None:
    """A team with season_year=2025 produces the year-only season_id='2025' in the DB."""
    # Set up a USSSA program and team
    db.execute(
        "INSERT OR IGNORE INTO programs (program_id, name, program_type) "
        "VALUES ('rebels-usssa', 'Lincoln Rebels', 'usssa')"
    )
    gc_uuid = "usssa-team-uuid-001"
    public_id = "usssaSlug123"
    db.execute(
        "INSERT INTO teams (gc_uuid, public_id, name, membership_type, is_active, program_id, season_year) "
        "VALUES (?, ?, 'Rebels 14U', 'member', 1, 'rebels-usssa', 2025)",
        (gc_uuid, public_id),
    )
    team_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (gc_uuid,)).fetchone()[0]
    db.commit()

    from src.gamechanger.types import TeamRef
    team_ref = TeamRef(id=team_pk, gc_uuid=gc_uuid, public_id=public_id)

    boxscore = _make_boxscore(own_key=public_id, opp_key=_OPP_TEAM_ID)

    loader = GameLoader(db, owned_team_ref=team_ref)
    ensure_season_row(db, loader._season_id)
    result = _load_game(loader, boxscore)

    assert result.errors == 0
    assert result.loaded >= 1

    row = db.execute(
        "SELECT season_id FROM games WHERE game_id = ?", (_EVENT_ID,)
    ).fetchone()
    assert row is not None
    assert row[0] == "2025", (
        f"Expected team to produce year-only season_id='2025', got '{row[0]}'"
    )


# ---------------------------------------------------------------------------
# E-200-01: season_id updated on upsert (regression test)
# ---------------------------------------------------------------------------


def test_upsert_game_updates_season_id(db: sqlite3.Connection) -> None:
    """Regression test: _upsert_game ON CONFLICT must update season_id.

    1. Insert a game with season_id "2024".
    2. Upsert the same game_id with season_id "2025".
    3. Assert the row's season_id is "2025".
    """
    from src.gamechanger.loaders import ensure_season_row
    from src.gamechanger.types import TeamRef

    # Seed prerequisite rows
    pk = _insert_own_team(db)
    opp_pk = db.execute(
        "INSERT INTO teams (gc_uuid, name, membership_type, is_active) "
        "VALUES ('opp-uuid', 'Opponent', 'tracked', 1)",
    ).lastrowid
    ensure_season_row(db, "2024")
    ensure_season_row(db, "2025")
    db.commit()

    game_id = "evt-season-upsert-test"
    game_stream_id = "stream-season-upsert-test"

    # Step 1: Create loader and insert game with "2024"
    loader = GameLoader(db, owned_team_ref=TeamRef(id=pk, gc_uuid=_OWN_TEAM_ID, public_id=_OWN_TEAM_SLUG))
    loader._season_id = "2024"
    loader._upsert_game(
        game_id=game_id,
        game_date="2025-05-01",
        home_team_id=pk,
        away_team_id=opp_pk,
        home_score=3,
        away_score=1,
        game_stream_id=game_stream_id,
    )
    db.commit()

    row = db.execute("SELECT season_id FROM games WHERE game_id = ?", (game_id,)).fetchone()
    assert row[0] == "2024"

    # Step 2: Upsert same game with "2025"
    loader._season_id = "2025"
    loader._upsert_game(
        game_id=game_id,
        game_date="2025-05-01",
        home_team_id=pk,
        away_team_id=opp_pk,
        home_score=3,
        away_score=1,
        game_stream_id=game_stream_id,
    )
    db.commit()

    # Step 3: Verify season_id was updated
    row = db.execute("SELECT season_id FROM games WHERE game_id = ?", (game_id,)).fetchone()
    assert row[0] == "2025", (
        f"Expected season_id='2025' after upsert, got '{row[0]}'"
    )


# ---------------------------------------------------------------------------
# E-204-01: appearance_order tracking
# ---------------------------------------------------------------------------

_PLAYER_OWN_P2 = "player-own-pitcher-002"
_PLAYER_OWN_P3 = "player-own-pitcher-003"


def test_appearance_order_populated_for_multiple_pitchers(
    db: sqlite3.Connection,
) -> None:
    """AC-2: Three pitchers get appearance_order 1, 2, 3 matching stats array order."""
    pitching = [
        {"player_id": _PLAYER_OWN_P1, "player_text": "(W)", "stats": {"IP": 5, "H": 3, "R": 2, "ER": 2, "BB": 1, "SO": 7}},
        {"player_id": _PLAYER_OWN_P2, "player_text": "", "stats": {"IP": 2, "H": 1, "R": 0, "ER": 0, "BB": 0, "SO": 3}},
        {"player_id": _PLAYER_OWN_P3, "player_text": "(SV)", "stats": {"IP": 2, "H": 0, "R": 0, "ER": 0, "BB": 1, "SO": 2}},
    ]
    boxscore = _make_boxscore(own_pitching=pitching)
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    rows = db.execute(
        "SELECT player_id, appearance_order FROM player_game_pitching "
        "WHERE game_id = ? ORDER BY appearance_order",
        (_EVENT_ID,),
    ).fetchall()

    own_rows = [(r[0], r[1]) for r in rows if r[0].startswith("player-own")]
    assert own_rows == [
        (_PLAYER_OWN_P1, 1),
        (_PLAYER_OWN_P2, 2),
        (_PLAYER_OWN_P3, 3),
    ]


def test_appearance_order_updated_on_upsert(
    db: sqlite3.Connection,
) -> None:
    """AC-3: Re-loading same boxscore updates appearance_order via ON CONFLICT."""
    pitching_v1 = [
        {"player_id": _PLAYER_OWN_P1, "player_text": "", "stats": {"IP": 5, "H": 3, "R": 2, "ER": 2, "BB": 1, "SO": 7}},
        {"player_id": _PLAYER_OWN_P2, "player_text": "", "stats": {"IP": 2, "H": 1, "R": 0, "ER": 0, "BB": 0, "SO": 3}},
    ]
    boxscore_v1 = _make_boxscore(own_pitching=pitching_v1)
    loader = _make_loader(db)
    _load_game(loader, boxscore_v1)

    # Verify initial load
    row = db.execute(
        "SELECT appearance_order FROM player_game_pitching WHERE game_id = ? AND player_id = ?",
        (_EVENT_ID, _PLAYER_OWN_P1),
    ).fetchone()
    assert row[0] == 1

    # Re-load same data -- appearance_order should be preserved via upsert
    _load_game(loader, boxscore_v1)

    row = db.execute(
        "SELECT appearance_order FROM player_game_pitching WHERE game_id = ? AND player_id = ?",
        (_EVENT_ID, _PLAYER_OWN_P1),
    ).fetchone()
    assert row[0] == 1


def test_appearance_order_single_pitcher(
    db: sqlite3.Connection,
) -> None:
    """Single pitcher gets appearance_order = 1."""
    boxscore = _make_boxscore()  # default has 1 pitcher per side
    loader = _make_loader(db)

    _load_game(loader, boxscore)

    row = db.execute(
        "SELECT appearance_order FROM player_game_pitching WHERE game_id = ? AND player_id = ?",
        (_EVENT_ID, _PLAYER_OWN_P1),
    ).fetchone()
    assert row[0] == 1

    # Opponent pitcher also gets appearance_order = 1
    opp_row = db.execute(
        "SELECT appearance_order FROM player_game_pitching WHERE game_id = ? AND player_id = ?",
        (_EVENT_ID, _PLAYER_OPP_P1),
    ).fetchone()
    assert opp_row[0] == 1


def test_appearance_order_in_dataclass() -> None:
    """AC-4: _PlayerPitching dataclass includes appearance_order field."""
    from src.gamechanger.loaders.game_loader import _PlayerPitching

    p = _PlayerPitching(player_id="test-player", appearance_order=3)
    assert p.appearance_order == 3

    # Default is None
    p_default = _PlayerPitching(player_id="test-player-2")
    assert p_default.appearance_order is None


# ---------------------------------------------------------------------------
# E-220-02: Perspective tagging
# ---------------------------------------------------------------------------


def test_batting_rows_have_perspective_team_id(db: sqlite3.Connection) -> None:
    """AC-1: Every batting row has perspective_team_id set to owned_team_ref.id."""
    boxscore = _make_boxscore()
    loader = _make_loader(db)
    own_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_ID,)).fetchone()[0]

    _load_game(loader, boxscore)

    rows = db.execute(
        "SELECT perspective_team_id FROM player_game_batting WHERE game_id = ?",
        (_EVENT_ID,),
    ).fetchall()
    assert len(rows) == 2  # own + opp batter
    for row in rows:
        assert row[0] == own_pk, f"Expected perspective_team_id={own_pk}, got {row[0]}"


def test_pitching_rows_have_perspective_team_id(db: sqlite3.Connection) -> None:
    """AC-1: Every pitching row has perspective_team_id set to owned_team_ref.id."""
    boxscore = _make_boxscore()
    loader = _make_loader(db)
    own_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_ID,)).fetchone()[0]

    _load_game(loader, boxscore)

    rows = db.execute(
        "SELECT perspective_team_id FROM player_game_pitching WHERE game_id = ?",
        (_EVENT_ID,),
    ).fetchall()
    assert len(rows) == 2  # own + opp pitcher
    for row in rows:
        assert row[0] == own_pk, f"Expected perspective_team_id={own_pk}, got {row[0]}"


def test_two_perspectives_create_separate_stat_rows(db: sqlite3.Connection) -> None:
    """AC-2: Same game from two perspectives creates separate batting/pitching rows."""
    from src.gamechanger.types import TeamRef

    boxscore = _make_boxscore()

    # Team A loads the game
    pk_a = _insert_own_team(db, gc_uuid="team-perspective-a", public_id="slug-a")
    loader_a = GameLoader(
        db, owned_team_ref=TeamRef(id=pk_a, gc_uuid="team-perspective-a", public_id="slug-a"),
    )
    ensure_season_row(db, loader_a._season_id)
    summary = _make_summary(game_stream_id="game-persp")
    loader_a.load_payload(boxscore, summary)

    # Team B loads the same game
    pk_b = _insert_own_team(db, gc_uuid="team-perspective-b", public_id="slug-b")
    loader_b = GameLoader(
        db, owned_team_ref=TeamRef(id=pk_b, gc_uuid="team-perspective-b", public_id="slug-b"),
    )
    loader_b.load_payload(boxscore, summary)

    # Should have 4 batting rows (2 per perspective) and 4 pitching rows
    batting_count = db.execute(
        "SELECT COUNT(*) FROM player_game_batting WHERE game_id = ?", (_EVENT_ID,)
    ).fetchone()[0]
    pitching_count = db.execute(
        "SELECT COUNT(*) FROM player_game_pitching WHERE game_id = ?", (_EVENT_ID,)
    ).fetchone()[0]
    assert batting_count == 4, f"Expected 4 batting rows (2 perspectives x 2 players), got {batting_count}"
    assert pitching_count == 4, f"Expected 4 pitching rows (2 perspectives x 2 players), got {pitching_count}"

    # Verify different perspective_team_id values
    perspectives = db.execute(
        "SELECT DISTINCT perspective_team_id FROM player_game_batting WHERE game_id = ?",
        (_EVENT_ID,),
    ).fetchall()
    assert len(perspectives) == 2
    assert {r[0] for r in perspectives} == {pk_a, pk_b}


def test_game_perspectives_row_inserted(db: sqlite3.Connection) -> None:
    """AC-3: game_perspectives row exists after loading a game."""
    boxscore = _make_boxscore()
    loader = _make_loader(db)
    own_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_ID,)).fetchone()[0]

    _load_game(loader, boxscore)

    row = db.execute(
        "SELECT game_id, perspective_team_id FROM game_perspectives WHERE game_id = ? AND perspective_team_id = ?",
        (_EVENT_ID, own_pk),
    ).fetchone()
    assert row is not None, "Expected game_perspectives row for this game and perspective"
    assert row[0] == _EVENT_ID
    assert row[1] == own_pk


def test_opp_data_same_perspective_as_own_data(db: sqlite3.Connection) -> None:
    """AC-5: Both own_data and opp_data rows carry the same perspective_team_id."""
    boxscore = _make_boxscore()
    loader = _make_loader(db)
    own_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_ID,)).fetchone()[0]

    _load_game(loader, boxscore)

    own_persp = db.execute(
        "SELECT perspective_team_id FROM player_game_batting WHERE player_id = ?",
        (_PLAYER_OWN_1,),
    ).fetchone()[0]
    opp_persp = db.execute(
        "SELECT perspective_team_id FROM player_game_batting WHERE player_id = ?",
        (_PLAYER_OPP_1,),
    ).fetchone()[0]
    assert own_persp == own_pk
    assert opp_persp == own_pk
    assert own_persp == opp_persp, "Both sides should have the same perspective_team_id"


def test_load_payload_perspective_uses_member_team_pk(db: sqlite3.Connection) -> None:
    """AC-6: load_payload() sets perspective_team_id to the member team's integer PK."""
    boxscore = _make_boxscore()
    loader = _make_loader(db)
    own_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_ID,)).fetchone()[0]

    _load_game(loader, boxscore)

    rows = db.execute(
        "SELECT DISTINCT perspective_team_id FROM player_game_batting WHERE game_id = ?",
        (_EVENT_ID,),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == own_pk


def test_dedup_game_perspective_uses_canonical_id(db: sqlite3.Connection) -> None:
    """AC-7: When _find_duplicate_game redirects to canonical game_id,
    game_perspectives uses the canonical game_id.

    Simulates the same physical game loaded twice with different event_ids
    from the same team perspective (e.g., crawled via schedule and then
    via game-summaries with a different event_id).
    """

    loader = _make_loader(db)
    own_pk = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_ID,)).fetchone()[0]

    # First load: creates game with event_id "event-canonical"
    summary_a = _make_summary(
        event_id="event-canonical",
        game_stream_id="stream-canon-a",
    )
    boxscore = _make_boxscore()
    loader.load_payload(boxscore, summary_a)

    # Verify canonical game exists
    game_row = db.execute(
        "SELECT game_id FROM games WHERE game_id = ?", ("event-canonical",)
    ).fetchone()
    assert game_row is not None

    # Second load: different event_id, same date/teams/score → dedup redirects to canonical
    summary_b = _make_summary(
        event_id="event-duplicate",
        game_stream_id="stream-canon-b",
    )
    loader.load_payload(boxscore, summary_b)

    # game_perspectives should reference the canonical game_id
    persp_rows = db.execute(
        "SELECT game_id, perspective_team_id FROM game_perspectives WHERE perspective_team_id = ?",
        (own_pk,),
    ).fetchall()
    assert len(persp_rows) == 1, f"Expected 1 game_perspectives row (idempotent), got {len(persp_rows)}"
    assert persp_rows[0][0] == "event-canonical", (
        f"Expected canonical game_id in game_perspectives, got {persp_rows[0][0]}"
    )

    # No game row should exist for the duplicate event_id
    dup_game = db.execute(
        "SELECT game_id FROM games WHERE game_id = ?", ("event-duplicate",)
    ).fetchone()
    assert dup_game is None, "Duplicate event_id should not create a separate game row"


def test_on_conflict_uses_three_column_unique(db: sqlite3.Connection) -> None:
    """AC-8: ON CONFLICT clauses use (game_id, player_id, perspective_team_id).

    Loading same data twice with same perspective is idempotent (no duplicates).
    """
    boxscore = _make_boxscore()
    loader = _make_loader(db)

    _load_game(loader, boxscore)
    _load_game(loader, boxscore)

    batting_count = db.execute(
        "SELECT COUNT(*) FROM player_game_batting WHERE game_id = ?", (_EVENT_ID,)
    ).fetchone()[0]
    pitching_count = db.execute(
        "SELECT COUNT(*) FROM player_game_pitching WHERE game_id = ?", (_EVENT_ID,)
    ).fetchone()[0]
    # 2 batting (own + opp) and 2 pitching (own + opp) -- no duplicates
    assert batting_count == 2
    assert pitching_count == 2


# ---------------------------------------------------------------------------
# E-237-02: Direct load_payload entry point (AC-5)
# ---------------------------------------------------------------------------


def _fresh_db() -> sqlite3.Connection:
    """Build an independent in-memory DB with schema + FK enforcement."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    conn.executescript(_MIGRATION_FILE.read_text(encoding="utf-8"))
    conn.executescript(_MIGRATION_008.read_text(encoding="utf-8"))
    conn.executescript(_MIGRATION_012.read_text(encoding="utf-8"))
    conn.commit()
    return conn


def _dump_games(conn: sqlite3.Connection) -> list[tuple]:
    """Dump content-bearing games columns (excludes created_at), ordered."""
    return conn.execute(
        "SELECT game_id, season_id, game_date, home_team_id, away_team_id, "
        "home_score, away_score, status, game_stream_id, start_time, timezone "
        "FROM games ORDER BY game_id"
    ).fetchall()


def _dump_batting(conn: sqlite3.Connection) -> list[tuple]:
    """Dump per-player batting rows (excludes surrogate id), ordered."""
    return conn.execute(
        "SELECT game_id, player_id, team_id, perspective_team_id, batting_order, "
        "positions_played, is_primary, stat_completeness, ab, r, h, rbi, bb, so, "
        "doubles, triples, hr, tb, hbp, shf, sb, cs, e "
        "FROM player_game_batting ORDER BY player_id"
    ).fetchall()


def _dump_pitching(conn: sqlite3.Connection) -> list[tuple]:
    """Dump per-player pitching rows (excludes surrogate id), ordered."""
    return conn.execute(
        "SELECT game_id, player_id, team_id, perspective_team_id, decision, "
        "appearance_order, stat_completeness, ip_outs, h, r, er, bb, so, wp, hbp, "
        "pitches, total_strikes, bf "
        "FROM player_game_pitching ORDER BY player_id"
    ).fetchall()


def test_load_payload_writes_games_and_stat_rows() -> None:
    """AC-5: load_payload writes the game row plus both sides' stat rows.

    Row-content pin over the sole entry point: one game row, one batting and one
    pitching row per side, each carrying the owned team's perspective PK.
    """
    boxscore = _make_boxscore()
    summary = _make_summary()
    opponent_name = "Rival High"

    db_pl = _fresh_db()
    loader_pl = _make_loader(db_pl)
    result_pl = loader_pl.load_payload(boxscore, summary, opponent_name=opponent_name)

    assert result_pl.loaded > 0
    assert result_pl.errors == 0
    assert result_pl.skipped == 0

    assert len(_dump_games(db_pl)) == 1
    assert len(_dump_batting(db_pl)) == 2   # own + opponent batter
    assert len(_dump_pitching(db_pl)) == 2  # own + opponent pitcher

    # AC-4: every stat row carries perspective_team_id = the owned team PK.
    own_pk = db_pl.execute(
        "SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_ID,)
    ).fetchone()[0]
    perspectives = db_pl.execute(
        "SELECT DISTINCT perspective_team_id FROM player_game_batting "
        "UNION "
        "SELECT DISTINCT perspective_team_id FROM player_game_pitching"
    ).fetchall()
    assert perspectives == [(own_pk,)]

    db_pl.close()


def test_load_payload_commits_per_call() -> None:
    """AC-3/TN-10: load_payload commits per call (no open transaction after)."""
    boxscore = _make_boxscore()
    summary = _make_summary()

    db = _fresh_db()
    loader = _make_loader(db)
    ensure_season_row(db, loader._season_id)
    result = loader.load_payload(boxscore, summary, opponent_name="Rival High")
    assert result.loaded > 0

    # After a per-call commit the connection has no pending transaction.
    assert db.in_transaction is False
    db.close()


# ---------------------------------------------------------------------------
# E-253-06: Stat-key drift canary (TN-7)
# ---------------------------------------------------------------------------


class TestStatKeyDriftCanary:
    """The canary ERRORs when a core stat key is absent from ALL rows of a
    non-empty group -- the signature of a GameChanger field rename that would
    silently zero the stat for every player. Group-grain, never per-row."""

    def test_normal_boxscore_does_not_fire(self) -> None:
        """AC-2: a realistic boxscore (all core keys present) -> no canary error."""
        db = _fresh_db()
        loader = _make_loader(db)
        ensure_season_row(db, loader._season_id)
        result = loader.load_payload(_make_boxscore(), _make_summary())
        assert result.errors == 0
        db.close()

    def test_renamed_batting_core_key_in_all_rows_fires(self) -> None:
        """AC-1: 'AB' renamed (here: absent) in ALL batting rows -> one error.

        Simulates GC renaming the at-bats field: the loader-read ``AB`` key is
        gone from every row's ``stats`` dict (the value has moved under a name
        the parser does not read), so AB would silently load 0 for everyone.
        """
        drifted = [
            {
                "player_id": _PLAYER_OWN_1,
                # AB renamed away -> the loader-read key is absent; value now
                # sits under a name the parser ignores.
                "stats": {"AtBats": 3, "R": 1, "H": 2, "RBI": 1, "BB": 1, "SO": 0},
            },
            {
                "player_id": _PLAYER_OWN_P1,
                "stats": {"AtBats": 4, "R": 0, "H": 1, "RBI": 0, "BB": 0, "SO": 1},
            },
        ]
        db = _fresh_db()
        loader = _make_loader(db)
        ensure_season_row(db, loader._season_id)
        result = loader.load_payload(
            _make_boxscore(own_batting=drifted), _make_summary()
        )
        # Group-grain: exactly one error for the own-team batting group.
        assert result.errors == 1
        db.close()

    def test_renamed_pitching_core_key_in_all_rows_fires(self) -> None:
        """AC-1: 'IP' absent from ALL pitching rows -> one error.

        IP is a canary core key (read separately from _PITCHING_MAIN, always
        present per row); its disappearance must fire.
        """
        drifted = [
            {
                "player_id": _PLAYER_OWN_P1,
                # IP renamed away; the remaining _PITCHING_MAIN keys are intact.
                "stats": {"InningsPitched": 5, "H": 3, "R": 2, "ER": 2, "BB": 1, "SO": 7},
            }
        ]
        db = _fresh_db()
        loader = _make_loader(db)
        ensure_season_row(db, loader._season_id)
        result = loader.load_payload(
            _make_boxscore(own_pitching=drifted), _make_summary()
        )
        assert result.errors == 1
        db.close()

    def test_core_key_present_in_one_row_does_not_fire(self) -> None:
        """AC-2: 'AB' present in >=1 row (absent in another) -> no canary error.

        The canary is group-grain absence: a partially-missing key (a single
        odd row) is NOT drift -- only absence from EVERY row is.
        """
        mixed = [
            {
                "player_id": _PLAYER_OWN_1,
                "stats": {"AB": 3, "R": 1, "H": 2, "RBI": 1, "BB": 1, "SO": 0},
            },
            {
                "player_id": _PLAYER_OWN_P1,
                # AB absent here only -> still present in the group.
                "stats": {"R": 0, "H": 1, "RBI": 0, "BB": 0, "SO": 1},
            },
        ]
        db = _fresh_db()
        loader = _make_loader(db)
        ensure_season_row(db, loader._season_id)
        result = loader.load_payload(_make_boxscore(own_batting=mixed), _make_summary())
        assert result.errors == 0
        db.close()

    def test_absent_extra_in_all_rows_does_not_fire(self) -> None:
        """AC-2: an extra ('2B') absent from every row must NOT fire the canary.

        Extras live in the separate sparse ``extra[]`` array, not the per-row
        ``stats`` dict, and are optionally-absent by design (no doubles all game
        -> 2B absent everywhere). The default boxscore has empty batting extras,
        so 2B is absent for all players; the canary must stay silent.
        """
        db = _fresh_db()
        loader = _make_loader(db)
        ensure_season_row(db, loader._season_id)
        box = _make_boxscore()  # batting_extra defaults to []
        # Sanity: no batting row's stats dict contains an extra like 2B.
        own_group = box[_OWN_TEAM_SLUG]["groups"][0]
        assert all("2B" not in r["stats"] for r in own_group["stats"])
        result = loader.load_payload(box, _make_summary())
        assert result.errors == 0
        db.close()

    def test_empty_group_does_not_fire(self) -> None:
        """AC-1 scope: an EMPTY stat group is not drift (no rows to be missing
        a key) -> no canary error."""
        db = _fresh_db()
        loader = _make_loader(db)
        ensure_season_row(db, loader._season_id)
        box = _make_boxscore(own_batting=[], own_pitching=[])
        result = loader.load_payload(box, _make_summary())
        assert result.errors == 0
        db.close()


# ---------------------------------------------------------------------------
# E-253-06: missing scores are NOT coerced to 0-0 (scoreless doubleheader)
# ---------------------------------------------------------------------------


class TestMissingScoreNoCoercion:
    """Missing game-summary scores must not flatten to 0-0 and collapse two
    distinct scoreless games into one row under the natural-key dedup."""

    def test_missing_scores_stored_as_null(self, db: sqlite3.Connection) -> None:
        """A summary omitting scores stores NULL home/away score, not 0."""
        summary = _make_summary(owning_score=None, opponent_score=None)
        _make_loader(db).load_payload(_make_boxscore(), summary)

        row = db.execute(
            "SELECT home_score, away_score FROM games WHERE game_id = ?", (_EVENT_ID,)
        ).fetchone()
        assert row == (None, None), "missing scores must be NULL, not coerced to 0"

    def test_genuine_zero_score_preserved(self, db: sqlite3.Connection) -> None:
        """A real 0 score (present, value 0) stays 0 -- only MISSING becomes NULL."""
        summary = _make_summary(owning_score=0, opponent_score=0)
        _make_loader(db).load_payload(_make_boxscore(), summary)

        row = db.execute(
            "SELECT home_score, away_score FROM games WHERE game_id = ?", (_EVENT_ID,)
        ).fetchone()
        assert row == (0, 0), "a genuine 0-0 must be preserved, not nulled"

    def test_scoreless_doubleheader_stays_two_rows(self, db: sqlite3.Connection) -> None:
        """AC-3: two same-date, same-team games both missing scores (and no
        start_time) do NOT collapse -- they remain two games rows.

        Pre-fix, both coerced to 0-0 with equal score totals, so the natural-key
        dedup treated the second as a duplicate of the first and redirected it.
        """
        loader = _make_loader(db)
        # No scores, no start_time -> the only pre-fix distinguishing signal
        # (score total) was the false 0-0 collapse.
        summary_1 = replace(
            _make_summary(
                event_id="dh-game-1", game_stream_id="dh-stream-1",
                owning_score=None, opponent_score=None,
            ),
            date_source_instant="2025-05-10T13:00:00.000Z",
        )
        summary_2 = replace(
            _make_summary(
                event_id="dh-game-2", game_stream_id="dh-stream-2",
                owning_score=None, opponent_score=None,
            ),
            date_source_instant="2025-05-10T18:00:00.000Z",
        )
        loader.load_payload(_make_boxscore(), summary_1)
        loader.load_payload(_make_boxscore(), summary_2)

        game_ids = {
            r[0] for r in db.execute("SELECT game_id FROM games").fetchall()
        }
        assert game_ids == {"dh-game-1", "dh-game-2"}, (
            "a scoreless doubleheader must remain two rows, not collapse to one"
        )
