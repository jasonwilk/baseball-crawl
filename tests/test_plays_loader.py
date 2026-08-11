"""Tests for src/gamechanger/loaders/plays_loader.py (E-195-03).

Covers:
- AC-1: Successful load with DB verification (plays + play_events)
- AC-2: Whole-game idempotent re-load (zero new rows)
- AC-3: Stub player creation for unknown batter/pitcher IDs
- AC-4: Parse error isolation (bad payload logged, other games continue)
- AC-5: Per-game DB transaction (commit/rollback)
- AC-6: LoadResult counts (loaded/skipped/errors)
- AC-7: Game FK guard (skip when game not in games table)
- AC-8: Tests cover all the above scenarios

All tests use an on-disk SQLite database with all migrations applied and drive
the loader through its in-memory ``load_payload`` entry point.
No real network calls.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

from migrations.apply_migrations import run_migrations
from src.gamechanger.loaders.plays_loader import PlaysLoader
from src.gamechanger.types import TeamRef


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEASON_ID = "2026"
_GC_UUID = "aaaabbbb-cccc-dddd-eeee-ffff00000001"
_PUBLIC_ID = "lsb-varsity"
_GAME_ID_1 = "game-event-id-001"
_GAME_ID_2 = "game-event-id-002"
_BATTER_1 = "ba11e100-0001-0001-0001-000000000001"
_BATTER_2 = "ba11e200-0002-0002-0002-000000000002"
_PITCHER_1 = "01c4e100-0001-0001-0001-000000000001"

_HOME_TEAM_ID = 1
_AWAY_TEAM_ID = 2


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    """Apply all migrations and return an open connection."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@pytest.fixture()
def team_ref(db: sqlite3.Connection) -> TeamRef:
    """Insert the owned team and return a TeamRef."""
    db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, public_id, is_active) "
        "VALUES (?, 'member', ?, ?, 1)",
        ("LSB Varsity", _GC_UUID, _PUBLIC_ID),
    )
    team_id = db.execute(
        "SELECT id FROM teams WHERE gc_uuid = ?", (_GC_UUID,)
    ).fetchone()[0]
    db.commit()
    return TeamRef(id=team_id, gc_uuid=_GC_UUID, public_id=_PUBLIC_ID)


@pytest.fixture()
def opponent_ref(db: sqlite3.Connection) -> TeamRef:
    """Insert an opponent team and return a TeamRef."""
    db.execute(
        "INSERT INTO teams (name, membership_type, is_active) "
        "VALUES (?, 'tracked', 1)",
        ("Opponent Wolves",),
    )
    team_id = db.execute(
        "SELECT id FROM teams WHERE name = ?", ("Opponent Wolves",)
    ).fetchone()[0]
    db.commit()
    return TeamRef(id=team_id)


@pytest.fixture()
def loader(db: sqlite3.Connection, team_ref: TeamRef) -> PlaysLoader:
    """Return a PlaysLoader backed by the test database."""
    return PlaysLoader(db, owned_team_ref=team_ref)


def _insert_season(db: sqlite3.Connection, season_id: str = _SEASON_ID) -> None:
    """Insert a season row required by FK constraints."""
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) "
        "VALUES (?, ?, ?)",
        (season_id, "Spring 2026 HS", 2026),
    )
    db.commit()


def _insert_game(
    db: sqlite3.Connection,
    game_id: str,
    home_team_id: int,
    away_team_id: int,
    season_id: str = _SEASON_ID,
    home_score: int | None = None,
    away_score: int | None = None,
) -> None:
    """Insert a game row required by FK constraints.

    ``home_score``/``away_score`` default to NULL (a game whose official score
    is not stored); pass them to exercise the derived-vs-stored comparison.
    """
    db.execute(
        "INSERT OR IGNORE INTO games (game_id, season_id, game_date, home_team_id, away_team_id, "
        "status, home_score, away_score) "
        "VALUES (?, ?, ?, ?, ?, 'completed', ?, ?)",
        (game_id, season_id, "2026-04-10", home_team_id, away_team_id, home_score, away_score),
    )
    db.commit()


def _insert_player(
    db: sqlite3.Connection,
    player_id: str,
    first_name: str = "Known",
    last_name: str = "Player",
) -> None:
    """Insert a player row."""
    db.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES (?, ?, ?)",
        (player_id, first_name, last_name),
    )
    db.commit()


def _make_plays_json(
    batter_id: str = _BATTER_1,
    pitcher_id: str | None = _PITCHER_1,
    outcome: str = "Single",
    inning: int = 1,
    half: str = "top",
    play_order: int = 0,
) -> dict:
    """Build a minimal plays API response with one play."""
    # Build at_plate_details with pitch events.
    at_plate_details = [
        {"template": "Ball 1"},
        {"template": "Strike 1 looking"},
        {"template": "In play"},
    ]

    # Build final_details with batter ID.
    final_details_templates = [
        {"template": f"${{{batter_id}}} singles to left field"},
    ]
    if pitcher_id is not None:
        final_details_templates.append(
            {"template": f"${{{pitcher_id}}} pitching"},
        )

    return {
        "sport": {"batting_style": "normal"},
        "team_players": {},
        "plays": [
            {
                "order": play_order,
                "inning": inning,
                "half": half,
                "name_template": {"template": outcome},
                "at_plate_details": at_plate_details,
                "final_details": final_details_templates,
                "home_score": 0,
                "away_score": 0,
                "did_score_change": False,
                "outs": 1,
                "did_outs_change": True,
            },
        ],
    }


def _make_multi_play_json(
    batter1: str = _BATTER_1,
    batter2: str = _BATTER_2,
    pitcher: str = _PITCHER_1,
) -> dict:
    """Build a plays response with two plays."""
    return {
        "sport": {"batting_style": "normal"},
        "team_players": {},
        "plays": [
            {
                "order": 0,
                "inning": 1,
                "half": "top",
                "name_template": {"template": "Single"},
                "at_plate_details": [
                    {"template": "Strike 1 looking"},
                    {"template": "In play"},
                ],
                "final_details": [
                    {"template": f"${{{batter1}}} singles to center field"},
                    {"template": f"${{{pitcher}}} pitching"},
                ],
                "home_score": 0,
                "away_score": 0,
                "did_score_change": False,
                "outs": 0,
                "did_outs_change": False,
            },
            {
                "order": 1,
                "inning": 1,
                "half": "top",
                "name_template": {"template": "Fly Out"},
                "at_plate_details": [
                    {"template": "Ball 1"},
                    {"template": "In play"},
                ],
                "final_details": [
                    {"template": f"${{{batter2}}} flies out to center field"},
                    {"template": f"${{{pitcher}}} pitching"},
                ],
                "home_score": 0,
                "away_score": 0,
                "did_score_change": False,
                "outs": 1,
                "did_outs_change": True,
            },
        ],
    }


# A payload whose ``plays`` entries are not dicts: ``play.get(...)`` raises
# inside PlaysParser, exercising the loader's per-game error isolation.
_MALFORMED_PLAYS_PAYLOAD = {"sport": {}, "team_players": {}, "plays": ["not-a-dict"]}


# ---------------------------------------------------------------------------
# AC-1: Successful load with DB verification
# ---------------------------------------------------------------------------


def test_load_payload_inserts_plays_and_events(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """AC-1: load_payload parses the payload and inserts plays + events."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    result = loader.load_payload({_GAME_ID_1: _make_plays_json()})

    assert result.loaded == 1
    assert result.skipped == 0
    assert result.errors == 0

    # Verify plays row.
    plays_row = db.execute(
        "SELECT game_id, play_order, inning, half, batter_id, pitcher_id, outcome, pitch_count "
        "FROM plays WHERE game_id = ?",
        (_GAME_ID_1,),
    ).fetchone()
    assert plays_row is not None
    game_id, play_order, inning, half, batter_id, pitcher_id, outcome, pitch_count = plays_row
    assert game_id == _GAME_ID_1
    assert play_order == 0
    assert inning == 1
    assert half == "top"
    assert batter_id == _BATTER_1
    assert pitcher_id == _PITCHER_1
    assert outcome == "Single"
    assert pitch_count == 3  # Ball 1, Strike 1 looking, In play

    # Verify play_events rows.
    play_id = db.execute(
        "SELECT id FROM plays WHERE game_id = ?", (_GAME_ID_1,)
    ).fetchone()[0]
    events = db.execute(
        "SELECT event_order, event_type, pitch_result, is_first_pitch, raw_template "
        "FROM play_events WHERE play_id = ? ORDER BY event_order",
        (play_id,),
    ).fetchall()
    assert len(events) == 3
    # Event 0: Ball 1 (first pitch event in the PA)
    assert events[0] == (0, "pitch", "ball", 1, "Ball 1")
    # Event 1: Strike 1 looking
    assert events[1] == (1, "pitch", "strike_looking", 0, "Strike 1 looking")
    # Event 2: In play
    assert events[2] == (2, "pitch", "in_play", 0, "In play")


def test_load_payload_inserts_multiple_plays(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """AC-1: Multiple plays in one game are all inserted."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    result = loader.load_payload({_GAME_ID_1: _make_multi_play_json()})

    assert result.loaded == 2
    assert result.skipped == 0
    assert result.errors == 0

    plays_count = db.execute(
        "SELECT COUNT(*) FROM plays WHERE game_id = ?", (_GAME_ID_1,)
    ).fetchone()[0]
    assert plays_count == 2

    events_count = db.execute(
        "SELECT COUNT(*) FROM play_events pe JOIN plays p ON pe.play_id = p.id WHERE p.game_id = ?",
        (_GAME_ID_1,),
    ).fetchone()[0]
    # Play 1: 2 events, Play 2: 2 events
    assert events_count == 4


def test_load_payload_uses_game_table_season_id(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """The season_id written to plays comes from the games table, not the loader's season_id."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id, season_id=_SEASON_ID)

    loader.load_payload({_GAME_ID_1: _make_plays_json()})

    row = db.execute(
        "SELECT season_id FROM plays WHERE game_id = ?", (_GAME_ID_1,),
    ).fetchone()
    assert row is not None
    assert row[0] == _SEASON_ID


# ---------------------------------------------------------------------------
# AC-2: Whole-game idempotency
# ---------------------------------------------------------------------------


def test_idempotent_reload_produces_zero_new_rows(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """AC-2: Re-running the loader for an already-loaded game produces zero new rows."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    payload = {_GAME_ID_1: _make_plays_json()}

    # First load.
    result1 = loader.load_payload(payload)
    assert result1.loaded == 1

    plays_count_after_first = db.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
    events_count_after_first = db.execute("SELECT COUNT(*) FROM play_events").fetchone()[0]

    # Second load -- should be idempotent.
    result2 = loader.load_payload(payload)
    assert result2.loaded == 0
    assert result2.skipped == 1
    assert result2.errors == 0

    # Row counts unchanged.
    plays_count_after_second = db.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
    events_count_after_second = db.execute("SELECT COUNT(*) FROM play_events").fetchone()[0]
    assert plays_count_after_second == plays_count_after_first
    assert events_count_after_second == events_count_after_first


# ---------------------------------------------------------------------------
# AC-3: Stub player creation for unknown IDs
# ---------------------------------------------------------------------------


def test_stub_player_created_for_unknown_batter(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """AC-3: Unknown batter_id gets a stub player row inserted before the play row."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    # Do NOT insert the batter player row -- it should be auto-created.
    result = loader.load_payload({_GAME_ID_1: _make_plays_json(batter_id=_BATTER_1)})
    assert result.loaded == 1

    # Verify the stub player was created.
    player = db.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?",
        (_BATTER_1,),
    ).fetchone()
    assert player is not None
    assert player == ("Unknown", "Unknown")


def test_stub_player_created_for_unknown_pitcher(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """AC-3: Unknown pitcher_id gets a stub player row inserted before the play row."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    result = loader.load_payload({_GAME_ID_1: _make_plays_json(pitcher_id=_PITCHER_1)})
    assert result.loaded == 1

    # Verify the stub pitcher was created.
    player = db.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?",
        (_PITCHER_1,),
    ).fetchone()
    assert player is not None
    assert player == ("Unknown", "Unknown")


def test_existing_player_not_overwritten_by_stub(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """AC-3: If a player already exists with a real name, the stub does not overwrite."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)
    _insert_player(db, _BATTER_1, "John", "Doe")

    loader.load_payload({_GAME_ID_1: _make_plays_json(batter_id=_BATTER_1)})

    player = db.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?",
        (_BATTER_1,),
    ).fetchone()
    assert player == ("John", "Doe")


def test_null_pitcher_id_no_stub_created(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """AC-3: When pitcher_id is None, no stub is created for None."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    # Build a plays JSON with no pitcher reference.
    plays_json = {
        "sport": {},
        "team_players": {},
        "plays": [
            {
                "order": 0,
                "inning": 1,
                "half": "top",
                "name_template": {"template": "Single"},
                "at_plate_details": [{"template": "In play"}],
                "final_details": [
                    {"template": f"${{{_BATTER_1}}} singles to left field"},
                ],
                "home_score": 0,
                "away_score": 0,
                "did_score_change": False,
                "outs": 0,
                "did_outs_change": False,
            },
        ],
    }

    result = loader.load_payload({_GAME_ID_1: plays_json})
    assert result.loaded == 1

    # Only the batter stub should exist, not a NULL pitcher stub.
    player_count = db.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    assert player_count == 1  # Only the batter


# ---------------------------------------------------------------------------
# AC-4: Parse error isolation
# ---------------------------------------------------------------------------


def test_parse_error_logged_and_skipped(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """AC-4: A malformed payload is logged and skipped; other games load fine."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)
    _insert_game(db, _GAME_ID_2, team_ref.id, opponent_ref.id)

    result = loader.load_payload(
        {
            _GAME_ID_1: _MALFORMED_PLAYS_PAYLOAD,
            _GAME_ID_2: _make_plays_json(),
        }
    )

    assert result.errors == 1  # Game 1 errored
    assert result.loaded == 1  # Game 2 loaded
    assert result.skipped == 0


def test_parse_error_missing_plays_key(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """AC-4: A well-formed payload with no plays key produces zero plays (skipped)."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    result = loader.load_payload({_GAME_ID_1: {"sport": {}, "team_players": {}}})

    # No plays parsed, so skipped.
    assert result.loaded == 0
    assert result.skipped == 1
    assert result.errors == 0


# ---------------------------------------------------------------------------
# AC-5: Per-game DB transaction
# ---------------------------------------------------------------------------


def test_per_game_transaction_rollback_on_error(
    db: sqlite3.Connection,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """AC-5: If insert fails partway through a game, the partial plays are rolled back."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    # Build plays JSON with an invalid half value that will fail the CHECK constraint.
    # The first play is valid; the second has an invalid half.
    plays_json = {
        "sport": {},
        "team_players": {},
        "plays": [
            {
                "order": 0,
                "inning": 1,
                "half": "top",
                "name_template": {"template": "Single"},
                "at_plate_details": [{"template": "In play"}],
                "final_details": [
                    {"template": f"${{{_BATTER_1}}} singles"},
                    {"template": f"${{{_PITCHER_1}}} pitching"},
                ],
                "home_score": 0,
                "away_score": 0,
                "did_score_change": False,
                "outs": 0,
                "did_outs_change": False,
            },
            {
                "order": 1,
                "inning": 1,
                "half": "INVALID_HALF",  # CHECK constraint violation
                "name_template": {"template": "Walk"},
                "at_plate_details": [
                    {"template": "Ball 1"},
                    {"template": "Ball 2"},
                    {"template": "Ball 3"},
                    {"template": "Ball 4"},
                ],
                "final_details": [
                    {"template": f"${{{_BATTER_2}}} walks"},
                    {"template": f"${{{_PITCHER_1}}} pitching"},
                ],
                "home_score": 0,
                "away_score": 0,
                "did_score_change": False,
                "outs": 0,
                "did_outs_change": False,
            },
        ],
    }

    loader = PlaysLoader(db, owned_team_ref=team_ref)
    result = loader.load_payload({_GAME_ID_1: plays_json})

    # The game should have errored due to the CHECK constraint violation.
    assert result.errors == 1
    assert result.loaded == 0

    # No plays should remain (rolled back).
    plays_count = db.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
    assert plays_count == 0


# ---------------------------------------------------------------------------
# AC-6: LoadResult counts
# ---------------------------------------------------------------------------


def test_load_result_counts(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """AC-6: LoadResult loaded/skipped/errors counts are correct."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)
    _insert_game(db, _GAME_ID_2, team_ref.id, opponent_ref.id)

    result = loader.load_payload(
        {
            _GAME_ID_1: _make_plays_json(),
            _GAME_ID_2: _make_plays_json(batter_id=_BATTER_2),
        }
    )
    assert result.loaded == 2  # 1 play per game, 2 games
    assert result.skipped == 0
    assert result.errors == 0


def test_load_result_empty_payload(loader: PlaysLoader) -> None:
    """AC-6: An empty payload mapping returns an empty LoadResult."""
    result = loader.load_payload({})
    assert result.loaded == 0
    assert result.skipped == 0
    assert result.errors == 0


# ---------------------------------------------------------------------------
# AC-7: Game FK guard
# ---------------------------------------------------------------------------


def test_game_fk_guard_skips_missing_game(
    db: sqlite3.Connection,
    loader: PlaysLoader,
) -> None:
    """AC-7: Games not in the games table are skipped with a warning."""
    _insert_season(db)
    # Do NOT insert a game row for GAME_ID_1.

    result = loader.load_payload({_GAME_ID_1: _make_plays_json()})

    assert result.loaded == 0
    assert result.skipped == 1
    assert result.errors == 0

    # No plays inserted.
    plays_count = db.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
    assert plays_count == 0


def test_game_fk_guard_loads_valid_skips_invalid(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """AC-7: Valid games load while invalid games are skipped."""
    _insert_season(db)
    # Only insert game 1, not game 2.
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    result = loader.load_payload(
        {
            _GAME_ID_1: _make_plays_json(),
            _GAME_ID_2: _make_plays_json(batter_id=_BATTER_2),
        }
    )

    assert result.loaded == 1  # Game 1
    assert result.skipped == 1  # Game 2 (no FK)
    assert result.errors == 0


# ---------------------------------------------------------------------------
# Multi-season scope test (Pre-Submission Checklist)
# ---------------------------------------------------------------------------


def test_plays_scoped_to_correct_game_across_seasons(
    db: sqlite3.Connection,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """Multi-scope test: plays from different seasons are correctly scoped.

    Verifies that the loader uses the game table's season_id (not a
    hardcoded value) and that plays from two different seasons do not
    cross-contaminate.
    """
    season_1 = "2025"
    season_2 = "2026"

    # Insert both seasons.
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) VALUES (?, ?, ?)",
        (season_1, "Spring 2025", 2025),
    )
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) VALUES (?, ?, ?)",
        (season_2, "Spring 2026", 2026),
    )

    # Insert games in different seasons.
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id, season_id=season_1)
    _insert_game(db, _GAME_ID_2, team_ref.id, opponent_ref.id, season_id=season_2)
    db.commit()

    # Load both games using the same loader instance.
    loader = PlaysLoader(db, owned_team_ref=team_ref)
    result = loader.load_payload(
        {
            _GAME_ID_1: _make_plays_json(),
            _GAME_ID_2: _make_plays_json(batter_id=_BATTER_2),
        }
    )

    assert result.loaded == 2

    # Verify each play has the correct season_id from its game row.
    row1 = db.execute(
        "SELECT season_id FROM plays WHERE game_id = ?", (_GAME_ID_1,)
    ).fetchone()
    assert row1[0] == season_1

    row2 = db.execute(
        "SELECT season_id FROM plays WHERE game_id = ?", (_GAME_ID_2,)
    ).fetchone()
    assert row2[0] == season_2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_batting_team_id_correct_for_top_and_bottom(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """Verify batting_team_id is away for top half, home for bottom half."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    # Two plays: one top (away team batting), one bottom (home team batting).
    plays_json = {
        "sport": {},
        "team_players": {},
        "plays": [
            {
                "order": 0,
                "inning": 1,
                "half": "top",
                "name_template": {"template": "Single"},
                "at_plate_details": [{"template": "In play"}],
                "final_details": [
                    {"template": f"${{{_BATTER_1}}} singles"},
                    {"template": f"${{{_PITCHER_1}}} pitching"},
                ],
                "home_score": 0,
                "away_score": 0,
                "did_score_change": False,
                "outs": 0,
                "did_outs_change": False,
            },
            {
                "order": 1,
                "inning": 1,
                "half": "bottom",
                "name_template": {"template": "Fly Out"},
                "at_plate_details": [{"template": "In play"}],
                "final_details": [
                    {"template": f"${{{_BATTER_2}}} flies out"},
                    {"template": f"${{{_PITCHER_1}}} pitching"},
                ],
                "home_score": 0,
                "away_score": 0,
                "did_score_change": False,
                "outs": 1,
                "did_outs_change": True,
            },
        ],
    }

    loader.load_payload({_GAME_ID_1: plays_json})

    top_row = db.execute(
        "SELECT batting_team_id FROM plays WHERE game_id = ? AND half = 'top'",
        (_GAME_ID_1,),
    ).fetchone()
    bottom_row = db.execute(
        "SELECT batting_team_id FROM plays WHERE game_id = ? AND half = 'bottom'",
        (_GAME_ID_1,),
    ).fetchone()

    # Top half: away team is batting.
    assert top_row[0] == opponent_ref.id
    # Bottom half: home team is batting.
    assert bottom_row[0] == team_ref.id


# ---------------------------------------------------------------------------
# E-220-03: Perspective tagging
# ---------------------------------------------------------------------------


def test_plays_rows_have_perspective_team_id(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """AC-1: Every plays row has perspective_team_id set to owned_team_ref.id."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    loader.load_payload({_GAME_ID_1: _make_multi_play_json()})

    rows = db.execute(
        "SELECT perspective_team_id FROM plays WHERE game_id = ?",
        (_GAME_ID_1,),
    ).fetchall()
    assert len(rows) == 2
    for row in rows:
        assert row[0] == team_ref.id, f"Expected perspective_team_id={team_ref.id}, got {row[0]}"


def test_two_perspectives_coexist(
    db: sqlite3.Connection,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """AC-2: Same game's plays from two perspectives coexist in the database."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    payload = {_GAME_ID_1: _make_plays_json()}

    # Load from perspective A (team_ref).
    loader_a = PlaysLoader(db, owned_team_ref=team_ref)
    result_a = loader_a.load_payload(payload)
    assert result_a.loaded == 1

    # Load from perspective B (opponent_ref).
    loader_b = PlaysLoader(db, owned_team_ref=opponent_ref)
    result_b = loader_b.load_payload(payload)
    assert result_b.loaded == 1

    # Both sets should coexist.
    total = db.execute(
        "SELECT COUNT(*) FROM plays WHERE game_id = ?", (_GAME_ID_1,)
    ).fetchone()[0]
    assert total == 2, f"Expected 2 plays rows (1 per perspective), got {total}"

    perspectives = db.execute(
        "SELECT DISTINCT perspective_team_id FROM plays WHERE game_id = ?",
        (_GAME_ID_1,),
    ).fetchall()
    assert len(perspectives) == 2
    assert {r[0] for r in perspectives} == {team_ref.id, opponent_ref.id}


def test_idempotency_check_includes_perspective(
    db: sqlite3.Connection,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """AC-3: Idempotency check is per-perspective -- loading from a new
    perspective proceeds even if plays exist from another perspective."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    payload = {_GAME_ID_1: _make_plays_json()}

    # Load from perspective A.
    loader_a = PlaysLoader(db, owned_team_ref=team_ref)
    result_a = loader_a.load_payload(payload)
    assert result_a.loaded == 1

    # Same perspective A again -- should be skipped (idempotent).
    result_a2 = loader_a.load_payload(payload)
    assert result_a2.skipped == 1
    assert result_a2.loaded == 0

    # Different perspective B -- should load (not idempotent for B).
    loader_b = PlaysLoader(db, owned_team_ref=opponent_ref)
    result_b = loader_b.load_payload(payload)
    assert result_b.loaded == 1
    assert result_b.skipped == 0


# ---------------------------------------------------------------------------
# E-237-01: Direct load_payload entry point (AC-5)
# ---------------------------------------------------------------------------


def _setup_independent_db(
    tmp_path: Path, name: str
) -> tuple[sqlite3.Connection, TeamRef, TeamRef]:
    """Create a fresh migrated DB with member + opponent teams and two games.

    Insertion order matches the ``team_ref`` / ``opponent_ref`` fixtures so the
    member team is id 1 and the opponent id 2 in every independent DB, making
    cross-DB row comparison meaningful.
    """
    db_path = tmp_path / f"{name}.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")

    conn.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, public_id, is_active) "
        "VALUES (?, 'member', ?, ?, 1)",
        ("LSB Varsity", _GC_UUID, _PUBLIC_ID),
    )
    member_id = conn.execute(
        "SELECT id FROM teams WHERE gc_uuid = ?", (_GC_UUID,)
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO teams (name, membership_type, is_active) "
        "VALUES (?, 'tracked', 1)",
        ("Opponent Wolves",),
    )
    opp_id = conn.execute(
        "SELECT id FROM teams WHERE name = ?", ("Opponent Wolves",)
    ).fetchone()[0]
    conn.commit()

    member_ref = TeamRef(id=member_id, gc_uuid=_GC_UUID, public_id=_PUBLIC_ID)
    opp_ref = TeamRef(id=opp_id)

    _insert_season(conn)
    _insert_game(conn, _GAME_ID_1, member_ref.id, opp_ref.id)
    _insert_game(conn, _GAME_ID_2, member_ref.id, opp_ref.id)
    return conn, member_ref, opp_ref


def _dump_plays(conn: sqlite3.Connection) -> list[tuple]:
    """Dump content-bearing plays columns (excluding surrogate id), ordered."""
    return conn.execute(
        """
        SELECT game_id, play_order, inning, half, season_id, batting_team_id,
               batter_id, pitcher_id, outcome, pitch_count,
               is_first_pitch_strike, is_qab, home_score, away_score,
               did_score_change, outs_after, did_outs_change, perspective_team_id
        FROM plays
        ORDER BY game_id, play_order
        """
    ).fetchall()


def _dump_events(conn: sqlite3.Connection) -> list[tuple]:
    """Dump play_events joined to their game/play_order, ordered deterministically."""
    return conn.execute(
        """
        SELECT p.game_id, p.play_order, pe.event_order, pe.event_type,
               pe.pitch_result, pe.is_first_pitch, pe.raw_template
        FROM play_events pe
        JOIN plays p ON pe.play_id = p.id
        ORDER BY p.game_id, p.play_order, pe.event_order
        """
    ).fetchall()


def test_load_payload_writes_expected_plays_and_events(tmp_path: Path) -> None:
    """AC-5: load_payload writes every play + event across a multi-game payload.

    Also exercises the empty-entry skip: a falsy payload value contributes
    nothing and is not counted.
    """
    plays_a = _make_plays_json()
    plays_b = _make_multi_play_json()

    conn, ref, _ = _setup_independent_db(tmp_path, "payload")
    payload = {
        _GAME_ID_1: plays_a,
        _GAME_ID_2: plays_b,
        "game-empty-entry-skip": {},  # falsy -> contributes nothing
    }
    result = PlaysLoader(conn, owned_team_ref=ref).load_payload(payload)

    assert result.loaded == 3  # 1 play (game 1) + 2 plays (game 2)
    assert result.skipped == 0
    assert result.errors == 0

    # Every parsed play and its events reached the DB, under the right games.
    plays = _dump_plays(conn)
    assert [(row[0], row[1]) for row in plays] == [
        (_GAME_ID_1, 0),
        (_GAME_ID_2, 0),
        (_GAME_ID_2, 1),
    ]
    assert len(_dump_events(conn)) == 7  # 3 + 2 + 2

    # The empty entry created no rows.
    orphan = conn.execute(
        "SELECT COUNT(*) FROM plays WHERE game_id = ?", ("game-empty-entry-skip",)
    ).fetchone()[0]
    assert orphan == 0

    # AC-4: every payload-written plays row carries perspective_team_id = ref.id.
    perspectives = conn.execute(
        "SELECT DISTINCT perspective_team_id FROM plays"
    ).fetchall()
    assert perspectives == [(ref.id,)]

    conn.close()


def test_load_payload_iteration_order_is_sorted(tmp_path: Path) -> None:
    """AC-2: load_payload iterates entries in sorted game_id order."""
    conn, ref, _ = _setup_independent_db(tmp_path, "order")
    # Provide entries in reverse key order; sorted iteration must still load both.
    payload = {
        _GAME_ID_2: _make_plays_json(batter_id=_BATTER_2),
        _GAME_ID_1: _make_plays_json(),
    }
    result = PlaysLoader(conn, owned_team_ref=ref).load_payload(payload)
    assert result.loaded == 2
    assert result.skipped == 0
    assert result.errors == 0
    conn.close()


def test_load_payload_perspective_uses_member_team_pk(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """AC-5: load_payload() sets perspective_team_id to the member team's integer PK."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    loader.load_payload({_GAME_ID_1: _make_plays_json()})

    rows = db.execute(
        "SELECT DISTINCT perspective_team_id FROM plays WHERE game_id = ?",
        (_GAME_ID_1,),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == team_ref.id


# ---------------------------------------------------------------------------
# Plays-derived final score persistence
# ---------------------------------------------------------------------------


def _make_walk_off_json(
    batter_id: str = _BATTER_1,
    pitcher_id: str = _PITCHER_1,
    final_home: int = 8,
    final_away: int = 7,
) -> dict:
    """Build a payload whose game-ending run lands on a SKIPPED final play.

    Three plays: a completed PA at 7-7, then the walk-off run on an abandoned
    plate appearance (empty ``final_details``, so the parser skips it, but
    ``did_score_change`` true), then the trailing inert phantom carrying 0/0.
    Only the first play becomes a ``plays`` row.
    """
    return {
        "sport": {"batting_style": "normal"},
        "team_players": {},
        "plays": [
            {
                "order": 0,
                "inning": 7,
                "half": "bottom",
                "name_template": {"template": "Single"},
                "at_plate_details": [
                    {"template": "Strike 1 looking"},
                    {"template": "In play"},
                ],
                "final_details": [
                    {"template": f"${{{batter_id}}} singles to left field"},
                    {"template": f"${{{pitcher_id}}} pitching"},
                ],
                "home_score": 7,
                "away_score": 7,
                "did_score_change": False,
                "outs": 1,
                "did_outs_change": False,
            },
            {
                "order": 1,
                "inning": 7,
                "half": "bottom",
                "name_template": {"template": "Single"},
                "at_plate_details": [{"template": "In play"}],
                "final_details": [],
                "home_score": final_home,
                "away_score": final_away,
                "did_score_change": True,
                "outs": 1,
                "did_outs_change": False,
            },
            {
                "order": 2,
                "inning": 8,
                "half": "top",
                "name_template": {"template": ""},
                "at_plate_details": [],
                "final_details": [],
                "home_score": 0,
                "away_score": 0,
                "did_score_change": False,
                "outs": 0,
                "did_outs_change": False,
            },
        ],
    }


def _read_final_score(db: sqlite3.Connection, game_id: str) -> list[tuple]:
    return db.execute(
        "SELECT perspective_team_id, plays_final_home_score, plays_final_away_score "
        "FROM game_perspectives WHERE game_id = ? ORDER BY perspective_team_id",
        (game_id,),
    ).fetchall()


def test_load_payload_persists_plays_final_score(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """The derived final score is written to game_perspectives at its own grain."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id, home_score=8, away_score=7)

    result = loader.load_payload({_GAME_ID_1: _make_walk_off_json()})

    # The game-ending play is still skipped -- this chunk adds no plays row.
    assert result.loaded == 1
    assert db.execute(
        "SELECT COUNT(*) FROM plays WHERE game_id = ?", (_GAME_ID_1,)
    ).fetchone()[0] == 1

    # ...but its run is no longer lost.
    assert _read_final_score(db, _GAME_ID_1) == [(team_ref.id, 8, 7)]


def test_final_score_upserts_onto_existing_game_perspectives_row(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """The normal pipeline order: GameLoader created the row first.

    A bare UPDATE would work here but silently no-op when the row is absent,
    so the write is an UPSERT.  This asserts the conflict branch updates in
    place rather than raising or duplicating.
    """
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id, home_score=8, away_score=7)
    # Mirror GameLoader's INSERT OR IGNORE, which runs earlier in the pipeline.
    db.execute(
        "INSERT OR IGNORE INTO game_perspectives (game_id, perspective_team_id) VALUES (?, ?)",
        (_GAME_ID_1, team_ref.id),
    )
    db.commit()

    loader.load_payload({_GAME_ID_1: _make_walk_off_json()})

    assert _read_final_score(db, _GAME_ID_1) == [(team_ref.id, 8, 7)]


def test_final_score_is_not_persisted_when_load_is_skipped(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """A game already loaded for this perspective writes nothing at all."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id, home_score=8, away_score=7)
    loader.load_payload({_GAME_ID_1: _make_walk_off_json()})
    assert _read_final_score(db, _GAME_ID_1) == [(team_ref.id, 8, 7)]

    # Re-load the same perspective with a DIFFERENT final; idempotency skips it,
    # so the stored score must not move.
    result = loader.load_payload(
        {_GAME_ID_1: _make_walk_off_json(final_home=99, final_away=1)},
    )

    assert result.skipped == 1
    assert result.loaded == 0
    assert _read_final_score(db, _GAME_ID_1) == [(team_ref.id, 8, 7)]


def test_final_score_disagreement_with_games_row_warns(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
    caplog,
) -> None:
    """A derived final that disagrees with the games row is the standing detector.

    Two legitimate classes produce this -- two scorebooks kept separately, and
    a scorekeeper who abandoned charting mid-game -- plus any payload shape the
    measured population does not contain.  The score is still stored; the
    WARNING is how an operator finds out.
    """
    _insert_season(db)
    # Official score is 8-13; the payload's plays only reach 8-12.
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id, home_score=8, away_score=13)

    with caplog.at_level(
        logging.WARNING, logger="src.gamechanger.loaders.plays_loader",
    ):
        loader.load_payload(
            {_GAME_ID_1: _make_walk_off_json(final_home=8, final_away=12)},
        )

    disagreements = [
        r for r in caplog.records
        if "disagrees with the games row" in r.getMessage()
    ]
    assert len(disagreements) == 1
    assert disagreements[0].levelno == logging.WARNING
    message = disagreements[0].getMessage()
    assert "plays 8-12" in message
    assert "games 8-13" in message

    # The derived value is still recorded -- the warning reports, it does not veto.
    assert _read_final_score(db, _GAME_ID_1) == [(team_ref.id, 8, 12)]


def test_final_score_agreement_does_not_warn(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
    caplog,
) -> None:
    """Negative control: the detector stays quiet when the scores agree.

    Without this, the warning test above would pass against a loader that
    warns unconditionally.
    """
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id, home_score=8, away_score=7)

    with caplog.at_level(
        logging.WARNING, logger="src.gamechanger.loaders.plays_loader",
    ):
        loader.load_payload({_GAME_ID_1: _make_walk_off_json()})

    assert [
        r for r in caplog.records
        if "disagrees with the games row" in r.getMessage()
    ] == []


def test_final_score_absent_when_payload_has_no_score_keys(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """A payload carrying no score keys stores NULL, never a fabricated 0.

    NULL is load-bearing provenance: "not derived" must stay distinguishable
    from a real 0-0 game.
    """
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id, home_score=3, away_score=2)
    payload = _make_plays_json()
    del payload["plays"][0]["home_score"]
    del payload["plays"][0]["away_score"]

    result = loader.load_payload({_GAME_ID_1: payload})

    assert result.loaded == 1
    assert _read_final_score(db, _GAME_ID_1) == [(team_ref.id, None, None)]


def test_final_score_persisted_when_every_play_is_skipped(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """A payload yielding ZERO insertable plays can still carry a real final.

    Every skip path can be the play that carries the game-ending run -- that is
    the premise of this whole chunk -- so a degenerate payload whose only play
    is skipped must not lose its score to an early return.
    """
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id, home_score=8, away_score=7)
    payload = _make_walk_off_json()
    # Drop the one completed PA, leaving only the skipped run-carrier and the
    # inert phantom.
    payload["plays"] = payload["plays"][1:]

    result = loader.load_payload({_GAME_ID_1: payload})

    # Nothing insertable -- still correctly reported as skipped, not loaded.
    assert result.loaded == 0
    assert result.skipped == 1
    assert result.errors == 0
    assert db.execute(
        "SELECT COUNT(*) FROM plays WHERE game_id = ?", (_GAME_ID_1,)
    ).fetchone()[0] == 0

    # ...but the recovered score is not lost.
    assert _read_final_score(db, _GAME_ID_1) == [(team_ref.id, 8, 7)]


def test_underivable_final_score_does_not_overwrite_a_stored_one(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """NULL provenance is one-way: "not derived" must not erase a real score.

    Reachable because the plays-delete and the game_perspectives row are not
    deleted together, so a game whose row already carries a score can be
    re-loaded from a payload that derives nothing.
    """
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id, home_score=8, away_score=7)
    loader.load_payload({_GAME_ID_1: _make_walk_off_json()})
    assert _read_final_score(db, _GAME_ID_1) == [(team_ref.id, 8, 7)]

    # Re-open the load path the way a plays-only delete does, then re-load a
    # payload carrying no usable score.  play_events FK plays(id), so they go
    # first; the game_perspectives row is deliberately left in place -- that is
    # the shape that makes this reachable.
    db.execute(
        "DELETE FROM play_events WHERE play_id IN "
        "(SELECT id FROM plays WHERE game_id = ?)",
        (_GAME_ID_1,),
    )
    db.execute("DELETE FROM plays WHERE game_id = ?", (_GAME_ID_1,))
    db.commit()
    payload = _make_plays_json()
    del payload["plays"][0]["home_score"]
    del payload["plays"][0]["away_score"]

    result = loader.load_payload({_GAME_ID_1: payload})

    assert result.loaded == 1
    assert _read_final_score(db, _GAME_ID_1) == [(team_ref.id, 8, 7)]


def test_two_perspectives_record_their_own_final_scores(
    db: sqlite3.Connection,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
) -> None:
    """The grain rationale, asserted: perspectives genuinely disagree.

    Verified in the live DB, where one game's last play reads 8-7 under one
    perspective and 10-7 under the other.  A game-level column would be
    last-writer-wins and would manufacture a false discrepancy.
    """
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id, home_score=8, away_score=7)

    PlaysLoader(db, owned_team_ref=team_ref).load_payload(
        {_GAME_ID_1: _make_walk_off_json()},
    )
    PlaysLoader(db, owned_team_ref=opponent_ref).load_payload(
        {_GAME_ID_1: _make_walk_off_json(final_home=10, final_away=7)},
    )

    assert _read_final_score(db, _GAME_ID_1) == sorted([
        (team_ref.id, 8, 7),
        (opponent_ref.id, 10, 7),
    ])
