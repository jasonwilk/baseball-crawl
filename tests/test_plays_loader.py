"""Tests for src/gamechanger/loaders/plays_loader.py (E-195-03).

Covers:
- AC-1: Successful load with DB verification (plays + play_events)
- AC-2: Whole-game idempotent re-load (zero new rows)
- AC-3: Stub player creation for unknown batter/pitcher IDs
- AC-4: Parse error isolation (bad file logged, other games continue)
- AC-5: Per-game DB transaction (commit/rollback)
- AC-6: LoadResult counts (loaded/skipped/errors)
- AC-7: Game FK guard (skip when game not in games table)
- AC-8: Tests cover all the above scenarios

All tests use an on-disk SQLite database with all migrations applied.
No real network calls.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from migrations.apply_migrations import run_migrations
from src.gamechanger.loaders.plays_loader import PlaysLoader
from src.gamechanger.types import TeamRef


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEASON_ID = "2026-spring-hs"
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
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, ?, ?, ?)",
        (season_id, "Spring 2026 HS", "spring-hs", 2026),
    )
    db.commit()


def _insert_game(
    db: sqlite3.Connection,
    game_id: str,
    home_team_id: int,
    away_team_id: int,
    season_id: str = _SEASON_ID,
) -> None:
    """Insert a game row required by FK constraints."""
    db.execute(
        "INSERT OR IGNORE INTO games (game_id, season_id, game_date, home_team_id, away_team_id, status) "
        "VALUES (?, ?, ?, ?, ?, 'completed')",
        (game_id, season_id, "2026-04-10", home_team_id, away_team_id),
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


def _write_plays_file(
    team_dir: Path,
    game_id: str,
    data: dict,
) -> Path:
    """Write a plays JSON file and return the team_dir."""
    plays_dir = team_dir / "plays"
    plays_dir.mkdir(parents=True, exist_ok=True)
    file_path = plays_dir / f"{game_id}.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")
    return file_path


# ---------------------------------------------------------------------------
# AC-1: Successful load with DB verification
# ---------------------------------------------------------------------------


def test_load_all_inserts_plays_and_events(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
    tmp_path: Path,
) -> None:
    """AC-1: load_all reads cached JSON, parses, and inserts plays + events."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    team_dir = tmp_path / "team"
    _write_plays_file(team_dir, _GAME_ID_1, _make_plays_json())

    result = loader.load_all(team_dir)

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


def test_load_all_inserts_multiple_plays(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
    tmp_path: Path,
) -> None:
    """AC-1: Multiple plays in one game are all inserted."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    team_dir = tmp_path / "team"
    _write_plays_file(team_dir, _GAME_ID_1, _make_multi_play_json())

    result = loader.load_all(team_dir)

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


def test_load_all_uses_game_table_season_id(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
    tmp_path: Path,
) -> None:
    """The season_id written to plays comes from the games table, not the loader's season_id."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id, season_id=_SEASON_ID)

    team_dir = tmp_path / "team"
    _write_plays_file(team_dir, _GAME_ID_1, _make_plays_json())

    loader.load_all(team_dir)

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
    tmp_path: Path,
) -> None:
    """AC-2: Re-running the loader for an already-loaded game produces zero new rows."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    team_dir = tmp_path / "team"
    _write_plays_file(team_dir, _GAME_ID_1, _make_plays_json())

    # First load.
    result1 = loader.load_all(team_dir)
    assert result1.loaded == 1

    plays_count_after_first = db.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
    events_count_after_first = db.execute("SELECT COUNT(*) FROM play_events").fetchone()[0]

    # Second load -- should be idempotent.
    result2 = loader.load_all(team_dir)
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
    tmp_path: Path,
) -> None:
    """AC-3: Unknown batter_id gets a stub player row inserted before the play row."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    # Do NOT insert the batter player row -- it should be auto-created.
    team_dir = tmp_path / "team"
    _write_plays_file(team_dir, _GAME_ID_1, _make_plays_json(batter_id=_BATTER_1))

    result = loader.load_all(team_dir)
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
    tmp_path: Path,
) -> None:
    """AC-3: Unknown pitcher_id gets a stub player row inserted before the play row."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    team_dir = tmp_path / "team"
    _write_plays_file(team_dir, _GAME_ID_1, _make_plays_json(pitcher_id=_PITCHER_1))

    result = loader.load_all(team_dir)
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
    tmp_path: Path,
) -> None:
    """AC-3: If a player already exists with a real name, the stub does not overwrite."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)
    _insert_player(db, _BATTER_1, "John", "Doe")

    team_dir = tmp_path / "team"
    _write_plays_file(team_dir, _GAME_ID_1, _make_plays_json(batter_id=_BATTER_1))

    loader.load_all(team_dir)

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
    tmp_path: Path,
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

    team_dir = tmp_path / "team"
    _write_plays_file(team_dir, _GAME_ID_1, plays_json)

    result = loader.load_all(team_dir)
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
    tmp_path: Path,
) -> None:
    """AC-4: A corrupt JSON file is logged and skipped; other games load fine."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)
    _insert_game(db, _GAME_ID_2, team_ref.id, opponent_ref.id)

    team_dir = tmp_path / "team"
    plays_dir = team_dir / "plays"
    plays_dir.mkdir(parents=True, exist_ok=True)

    # Game 1: corrupt JSON.
    (plays_dir / f"{_GAME_ID_1}.json").write_text("NOT VALID JSON", encoding="utf-8")

    # Game 2: valid plays data.
    _write_plays_file(team_dir, _GAME_ID_2, _make_plays_json())

    result = loader.load_all(team_dir)

    assert result.errors == 1  # Game 1 errored
    assert result.loaded == 1  # Game 2 loaded
    assert result.skipped == 0


def test_parse_error_missing_plays_key(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
    tmp_path: Path,
) -> None:
    """AC-4: A file with valid JSON but no plays key produces zero plays (skipped)."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    team_dir = tmp_path / "team"
    _write_plays_file(team_dir, _GAME_ID_1, {"sport": {}, "team_players": {}})

    result = loader.load_all(team_dir)

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
    tmp_path: Path,
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

    team_dir = tmp_path / "team"
    _write_plays_file(team_dir, _GAME_ID_1, plays_json)

    loader = PlaysLoader(db, owned_team_ref=team_ref)
    result = loader.load_all(team_dir)

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
    tmp_path: Path,
) -> None:
    """AC-6: LoadResult loaded/skipped/errors counts are correct."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)
    _insert_game(db, _GAME_ID_2, team_ref.id, opponent_ref.id)

    team_dir = tmp_path / "team"

    # Game 1: valid.
    _write_plays_file(team_dir, _GAME_ID_1, _make_plays_json())
    # Game 2: valid.
    _write_plays_file(team_dir, _GAME_ID_2, _make_plays_json(batter_id=_BATTER_2))

    result = loader.load_all(team_dir)
    assert result.loaded == 2  # 1 play per game, 2 games
    assert result.skipped == 0
    assert result.errors == 0


def test_load_result_no_plays_dir(
    loader: PlaysLoader,
    tmp_path: Path,
) -> None:
    """AC-6: Missing plays directory returns empty LoadResult."""
    team_dir = tmp_path / "team"
    team_dir.mkdir()

    result = loader.load_all(team_dir)
    assert result.loaded == 0
    assert result.skipped == 0
    assert result.errors == 0


# ---------------------------------------------------------------------------
# AC-7: Game FK guard
# ---------------------------------------------------------------------------


def test_game_fk_guard_skips_missing_game(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    tmp_path: Path,
) -> None:
    """AC-7: Games not in the games table are skipped with a warning."""
    _insert_season(db)
    # Do NOT insert a game row for GAME_ID_1.

    team_dir = tmp_path / "team"
    _write_plays_file(team_dir, _GAME_ID_1, _make_plays_json())

    result = loader.load_all(team_dir)

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
    tmp_path: Path,
) -> None:
    """AC-7: Valid games load while invalid games are skipped."""
    _insert_season(db)
    # Only insert game 1, not game 2.
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    team_dir = tmp_path / "team"
    _write_plays_file(team_dir, _GAME_ID_1, _make_plays_json())
    _write_plays_file(team_dir, _GAME_ID_2, _make_plays_json(batter_id=_BATTER_2))

    result = loader.load_all(team_dir)

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
    tmp_path: Path,
) -> None:
    """Multi-scope test: plays from different seasons are correctly scoped.

    Verifies that the loader uses the game table's season_id (not a
    hardcoded value) and that plays from two different seasons do not
    cross-contaminate.
    """
    season_1 = "2025-spring-hs"
    season_2 = "2026-spring-hs"

    # Insert both seasons.
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
        (season_1, "Spring 2025", "spring-hs", 2025),
    )
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
        (season_2, "Spring 2026", "spring-hs", 2026),
    )

    # Insert games in different seasons.
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id, season_id=season_1)
    _insert_game(db, _GAME_ID_2, team_ref.id, opponent_ref.id, season_id=season_2)
    db.commit()

    team_dir = tmp_path / "team"
    _write_plays_file(team_dir, _GAME_ID_1, _make_plays_json())
    _write_plays_file(team_dir, _GAME_ID_2, _make_plays_json(batter_id=_BATTER_2))

    # Load both games using the same loader instance.
    loader = PlaysLoader(db, owned_team_ref=team_ref)
    result = loader.load_all(team_dir)

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


def test_empty_plays_dir(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    tmp_path: Path,
) -> None:
    """Empty plays directory returns empty LoadResult."""
    team_dir = tmp_path / "team"
    (team_dir / "plays").mkdir(parents=True)

    result = loader.load_all(team_dir)
    assert result.loaded == 0
    assert result.skipped == 0
    assert result.errors == 0


def test_batting_team_id_correct_for_top_and_bottom(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
    tmp_path: Path,
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

    team_dir = tmp_path / "team"
    _write_plays_file(team_dir, _GAME_ID_1, plays_json)

    loader.load_all(team_dir)

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
    tmp_path: Path,
) -> None:
    """AC-1: Every plays row has perspective_team_id set to owned_team_ref.id."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    team_dir = tmp_path / "team"
    _write_plays_file(team_dir, _GAME_ID_1, _make_multi_play_json())

    loader.load_all(team_dir)

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
    tmp_path: Path,
) -> None:
    """AC-2: Same game's plays from two perspectives coexist in the database."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    team_dir = tmp_path / "team"
    _write_plays_file(team_dir, _GAME_ID_1, _make_plays_json())

    # Load from perspective A (team_ref).
    loader_a = PlaysLoader(db, owned_team_ref=team_ref)
    result_a = loader_a.load_all(team_dir)
    assert result_a.loaded == 1

    # Load from perspective B (opponent_ref).
    loader_b = PlaysLoader(db, owned_team_ref=opponent_ref)
    result_b = loader_b.load_all(team_dir)
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
    tmp_path: Path,
) -> None:
    """AC-3: Idempotency check is per-perspective -- loading from a new
    perspective proceeds even if plays exist from another perspective."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    team_dir = tmp_path / "team"
    _write_plays_file(team_dir, _GAME_ID_1, _make_plays_json())

    # Load from perspective A.
    loader_a = PlaysLoader(db, owned_team_ref=team_ref)
    result_a = loader_a.load_all(team_dir)
    assert result_a.loaded == 1

    # Same perspective A again -- should be skipped (idempotent).
    result_a2 = loader_a.load_all(team_dir)
    assert result_a2.skipped == 1
    assert result_a2.loaded == 0

    # Different perspective B -- should load (not idempotent for B).
    loader_b = PlaysLoader(db, owned_team_ref=opponent_ref)
    result_b = loader_b.load_all(team_dir)
    assert result_b.loaded == 1
    assert result_b.skipped == 0


def test_load_all_perspective_uses_member_team_pk(
    db: sqlite3.Connection,
    loader: PlaysLoader,
    team_ref: TeamRef,
    opponent_ref: TeamRef,
    tmp_path: Path,
) -> None:
    """AC-5: load_all() sets perspective_team_id to the member team's integer PK."""
    _insert_season(db)
    _insert_game(db, _GAME_ID_1, team_ref.id, opponent_ref.id)

    team_dir = tmp_path / "team"
    _write_plays_file(team_dir, _GAME_ID_1, _make_plays_json())

    loader.load_all(team_dir)

    rows = db.execute(
        "SELECT DISTINCT perspective_team_id FROM plays WHERE game_id = ?",
        (_GAME_ID_1,),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == team_ref.id
