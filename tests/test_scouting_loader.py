"""Tests for src/gamechanger/loaders/scouting_loader.py (E-097-03, E-100-03).

Covers:
- AC-13: Roster upsert into players / team_rosters
- AC-13: Delegation to GameLoader.load_file() for boxscore loading
- AC-13: Season aggregate computation (counting stat sums, rate stats NOT stored)
- AC-13: Idempotency (double-load produces no duplicates)
- AC-13: scouting_runs metadata (status, first_fetched / last_checked)
- AC-13: UUID opportunism (gc_uuid stub creation when discovered)
- AC-8: FK-safe stub player pattern

All tests use SQLite in-memory databases via tmp_path. No real network calls.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from migrations.apply_migrations import run_migrations
from src.gamechanger.loaders.game_loader import GameSummaryEntry
from src.gamechanger.loaders.scouting_loader import ScoutingLoader
from src.gamechanger.types import TeamRef


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
def loader(db: sqlite3.Connection) -> ScoutingLoader:
    """Return a ScoutingLoader backed by the test database."""
    return ScoutingLoader(db)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Public ID slug used as the own_key in test boxscores (non-UUID alphanumeric).
_PUBLIC_ID = "opp-slug-abc123"
# GC UUID used as gc_uuid for the team row so GameLoader._ensure_team_row
# resolves back to the same INTEGER PK.
_GC_UUID = "aaaabbbb-cccc-dddd-eeee-ffff00000001"
_SEASON_ID = "2025-spring-hs"
_PLAYER_1 = "player-uuid-001"
_PLAYER_2 = "player-uuid-002"


def _insert_team(
    db: sqlite3.Connection,
    public_id: str = _PUBLIC_ID,
    gc_uuid: str = _GC_UUID,
    name: str = "Opp Team",
) -> int:
    """Insert a tracked team row and return its INTEGER PK."""
    cursor = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, public_id, is_active) "
        "VALUES (?, 'tracked', ?, ?, 0)",
        (name, gc_uuid, public_id),
    )
    db.commit()
    return cursor.lastrowid


def _make_roster(tmp_path: Path, public_id: str, season_id: str) -> Path:
    """Write a minimal roster.json and return the scouting dir."""
    scouting_dir = tmp_path / "raw" / season_id / "scouting" / public_id
    scouting_dir.mkdir(parents=True, exist_ok=True)
    roster = [
        {"id": _PLAYER_1, "first_name": "John", "last_name": "Doe", "number": "14"},
        {"id": _PLAYER_2, "first_name": "Jane", "last_name": "Smith", "number": "7"},
    ]
    (scouting_dir / "roster.json").write_text(json.dumps(roster), encoding="utf-8")
    return scouting_dir


def _make_games_json(scouting_dir: Path, game_id: str) -> None:
    """Write games.json with one completed game."""
    games = [
        {
            "id": game_id,
            "game_status": "completed",
            "home_away": "home",
            "start_ts": "2025-04-10T18:00:00Z",
            "score": {"team": 5, "opponent_team": 3},
        }
    ]
    (scouting_dir / "games.json").write_text(json.dumps(games), encoding="utf-8")


_OPP_UUID = "11112222-3333-4444-5555-aaaabbbbcccc"


def _make_boxscore(
    scouting_dir: Path,
    game_id: str,
    own_key: str,
    opp_key: str = _OPP_UUID,
    player_id: str = _PLAYER_1,
) -> None:
    """Write a minimal boxscore JSON with one batting player."""
    bs_dir = scouting_dir / "boxscores"
    bs_dir.mkdir(parents=True, exist_ok=True)
    boxscore = {
        own_key: {
            "players": [
                {"id": player_id, "first_name": "John", "last_name": "Doe", "number": "14"}
            ],
            "groups": [
                {
                    "category": "lineup",
                    "stats": [
                        {
                            "player_id": player_id,
                            "stats": {"AB": 3, "H": 1, "RBI": 1, "BB": 0, "SO": 1},
                        }
                    ],
                    "extra": [
                        {"stat_name": "2B", "stats": [{"player_id": player_id, "value": 1}]},
                    ],
                }
            ],
        },
        opp_key: {
            "players": [],
            "groups": [],
        },
    }
    (bs_dir / f"{game_id}.json").write_text(json.dumps(boxscore), encoding="utf-8")


# ---------------------------------------------------------------------------
# AC-13: Roster upsert
# ---------------------------------------------------------------------------


def test_roster_upserted_into_players(
    loader: ScoutingLoader, db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Roster players are upserted into the players table."""
    team_pk = _insert_team(db)
    scouting_dir = _make_roster(tmp_path, _PUBLIC_ID, _SEASON_ID)
    (scouting_dir / "games.json").write_text("[]", encoding="utf-8")

    loader.load_team(scouting_dir, team_pk, _SEASON_ID)

    rows = db.execute("SELECT player_id FROM players").fetchall()
    player_ids = {r[0] for r in rows}
    assert _PLAYER_1 in player_ids
    assert _PLAYER_2 in player_ids


def test_roster_upserted_into_team_rosters(
    loader: ScoutingLoader, db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Roster players are linked in team_rosters with correct season and jersey."""
    team_pk = _insert_team(db)
    scouting_dir = _make_roster(tmp_path, _PUBLIC_ID, _SEASON_ID)
    (scouting_dir / "games.json").write_text("[]", encoding="utf-8")

    loader.load_team(scouting_dir, team_pk, _SEASON_ID)

    rows = db.execute(
        "SELECT player_id, jersey_number FROM team_rosters WHERE team_id = ? AND season_id = ?",
        (team_pk, _SEASON_ID),
    ).fetchall()
    assert len(rows) == 2
    jerseys = {r[0]: r[1] for r in rows}
    assert jerseys.get(_PLAYER_1) == "14"
    assert jerseys.get(_PLAYER_2) == "7"


# ---------------------------------------------------------------------------
# AC-13: Delegation to GameLoader.load_file()
# ---------------------------------------------------------------------------


def test_boxscore_loading_delegates_to_game_loader(
    loader: ScoutingLoader, db: sqlite3.Connection, tmp_path: Path
) -> None:
    """ScoutingLoader delegates boxscore loading to GameLoader.load_file()."""
    team_pk = _insert_team(db)
    game_id = "game-stream-001"
    scouting_dir = _make_roster(tmp_path, _PUBLIC_ID, _SEASON_ID)
    _make_games_json(scouting_dir, game_id)
    _make_boxscore(scouting_dir, game_id, own_key=_PUBLIC_ID, opp_key="11112222-3333-4444-5555-aaaabbbbcccc")

    with patch("src.gamechanger.loaders.scouting_loader.GameLoader") as MockGameLoader:
        mock_gl = MagicMock()
        from src.gamechanger.loaders import LoadResult
        mock_gl.load_file.return_value = LoadResult(loaded=2)
        MockGameLoader.return_value = mock_gl

        loader.load_team(scouting_dir, team_pk, _SEASON_ID)

        expected_team_ref = TeamRef(id=team_pk, gc_uuid=_GC_UUID, public_id=_PUBLIC_ID)
        MockGameLoader.assert_called_once_with(
            db=loader._db, season_id=_SEASON_ID, owned_team_ref=expected_team_ref
        )
        mock_gl.load_file.assert_called_once()
        # First arg should be the boxscore path.
        call_args = mock_gl.load_file.call_args
        bs_path = call_args.args[0]
        assert bs_path.name == f"{game_id}.json"
        # Second arg should be a GameSummaryEntry.
        summary = call_args.args[1]
        assert isinstance(summary, GameSummaryEntry)
        assert summary.event_id == game_id


# ---------------------------------------------------------------------------
# AC-13: Season aggregate computation
# ---------------------------------------------------------------------------


def test_season_aggregates_computed_from_game_rows(
    loader: ScoutingLoader, db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Season batting aggregates are computed from player_game_batting rows."""
    team_pk = _insert_team(db)
    game_id = "game-stream-agg-001"
    opp_uuid = "11112222-3333-4444-5555-aaaabbbbcccc"
    scouting_dir = _make_roster(tmp_path, _PUBLIC_ID, _SEASON_ID)
    _make_games_json(scouting_dir, game_id)
    _make_boxscore(scouting_dir, game_id, own_key=_PUBLIC_ID, opp_key=opp_uuid, player_id=_PLAYER_1)

    loader.load_team(scouting_dir, team_pk, _SEASON_ID)

    # Verify player_game_batting row exists.
    game_row = db.execute(
        "SELECT ab, h, doubles FROM player_game_batting WHERE player_id = ? AND game_id = ?",
        (_PLAYER_1, game_id),
    ).fetchone()
    assert game_row is not None, "Expected a player_game_batting row"
    assert game_row[0] == 3  # ab
    assert game_row[1] == 1  # h
    assert game_row[2] == 1  # doubles

    # Verify season aggregate.
    season_row = db.execute(
        "SELECT ab, h, doubles FROM player_season_batting "
        "WHERE player_id = ? AND team_id = ? AND season_id = ?",
        (_PLAYER_1, team_pk, _SEASON_ID),
    ).fetchone()
    assert season_row is not None, "Expected a player_season_batting row"
    assert season_row[0] == 3  # ab
    assert season_row[1] == 1  # h
    assert season_row[2] == 1  # doubles


def test_rate_stats_not_stored_in_season_batting(
    loader: ScoutingLoader, db: sqlite3.Connection, tmp_path: Path
) -> None:
    """player_season_batting does not have an avg or obp column (rate stats computed at display time)."""
    team_pk = _insert_team(db)
    game_id = "game-stream-rate-001"
    opp_uuid = "22223333-4444-5555-6666-aaaabbbbcccc"
    scouting_dir = _make_roster(tmp_path, _PUBLIC_ID, _SEASON_ID)
    _make_games_json(scouting_dir, game_id)
    _make_boxscore(scouting_dir, game_id, own_key=_PUBLIC_ID, opp_key=opp_uuid, player_id=_PLAYER_1)

    loader.load_team(scouting_dir, team_pk, _SEASON_ID)

    cursor = db.execute("PRAGMA table_info(player_season_batting);")
    columns = {row[1] for row in cursor.fetchall()}
    # Rate stats should NOT be stored.
    assert "avg" not in columns
    assert "obp" not in columns


# ---------------------------------------------------------------------------
# AC-13: Idempotency
# ---------------------------------------------------------------------------


def test_double_load_no_duplicates(
    loader: ScoutingLoader, db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Loading the same data twice produces no duplicate rows in any table."""
    team_pk = _insert_team(db)
    game_id = "game-stream-dup-001"
    opp_uuid = "33334444-5555-6666-7777-aaaabbbbcccc"
    scouting_dir = _make_roster(tmp_path, _PUBLIC_ID, _SEASON_ID)
    _make_games_json(scouting_dir, game_id)
    _make_boxscore(scouting_dir, game_id, own_key=_PUBLIC_ID, opp_key=opp_uuid, player_id=_PLAYER_1)

    loader.load_team(scouting_dir, team_pk, _SEASON_ID)
    loader.load_team(scouting_dir, team_pk, _SEASON_ID)

    player_count = db.execute("SELECT COUNT(*) FROM players WHERE player_id = ?", (_PLAYER_1,)).fetchone()[0]
    assert player_count == 1

    roster_count = db.execute(
        "SELECT COUNT(*) FROM team_rosters WHERE player_id = ? AND team_id = ? AND season_id = ?",
        (_PLAYER_1, team_pk, _SEASON_ID),
    ).fetchone()[0]
    assert roster_count == 1

    game_batting_count = db.execute(
        "SELECT COUNT(*) FROM player_game_batting WHERE player_id = ? AND game_id = ?",
        (_PLAYER_1, game_id),
    ).fetchone()[0]
    assert game_batting_count == 1

    season_batting_count = db.execute(
        "SELECT COUNT(*) FROM player_season_batting "
        "WHERE player_id = ? AND team_id = ? AND season_id = ?",
        (_PLAYER_1, team_pk, _SEASON_ID),
    ).fetchone()[0]
    assert season_batting_count == 1


# ---------------------------------------------------------------------------
# AC-8: FK-safe stub player pattern
# ---------------------------------------------------------------------------


def test_stub_player_created_for_unknown_player_in_boxscore(
    loader: ScoutingLoader, db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Unknown player IDs in boxscores get stub rows (first_name='Unknown')."""
    team_pk = _insert_team(db)
    game_id = "game-stream-stub-001"
    opp_uuid = "44445555-6666-7777-8888-aaaabbbbcccc"
    unknown_player = "unknown-player-uuid-xyz"
    scouting_dir = tmp_path / "raw" / _SEASON_ID / "scouting" / _PUBLIC_ID
    scouting_dir.mkdir(parents=True, exist_ok=True)

    # Minimal roster (no roster.json -- test stub creation from boxscore only).
    (scouting_dir / "roster.json").write_text("[]", encoding="utf-8")

    games = [
        {
            "id": game_id,
            "game_status": "completed",
            "start_ts": "2025-04-10T18:00:00Z",
            "score": {"team": 3, "opponent_team": 1},
        }
    ]
    (scouting_dir / "games.json").write_text(json.dumps(games), encoding="utf-8")

    bs_dir = scouting_dir / "boxscores"
    bs_dir.mkdir(parents=True, exist_ok=True)
    boxscore = {
        _PUBLIC_ID: {
            "players": [],
            "groups": [
                {
                    "category": "lineup",
                    "stats": [
                        {
                            "player_id": unknown_player,
                            "stats": {"AB": 4, "H": 2, "RBI": 0, "BB": 1, "SO": 0},
                        }
                    ],
                    "extra": [],
                }
            ],
        },
        opp_uuid: {"players": [], "groups": []},
    }
    (bs_dir / f"{game_id}.json").write_text(json.dumps(boxscore), encoding="utf-8")

    loader.load_team(scouting_dir, team_pk, _SEASON_ID)

    row = db.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?", (unknown_player,)
    ).fetchone()
    assert row is not None, "Stub player row should have been created"
    assert row[0] == "Unknown"
    assert row[1] == "Unknown"


# ---------------------------------------------------------------------------
# AC-13: UUID opportunism
# ---------------------------------------------------------------------------


def test_loader_uuid_opportunism(
    loader: ScoutingLoader, db: sqlite3.Connection, tmp_path: Path
) -> None:
    """When a UUID key appears in a boxscore, a stub teams row is created for it."""
    team_pk = _insert_team(db)
    game_id = "game-stream-uuid-opp-001"
    uuid_key = "55556666-7777-8888-aaaa-bbbbcccc0005"

    scouting_dir = _make_roster(tmp_path, _PUBLIC_ID, _SEASON_ID)
    _make_games_json(scouting_dir, game_id)
    _make_boxscore(scouting_dir, game_id, own_key=_PUBLIC_ID, opp_key=uuid_key, player_id=_PLAYER_1)

    loader.load_team(scouting_dir, team_pk, _SEASON_ID)

    row = db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (uuid_key,)).fetchone()
    assert row is not None, f"Expected a teams stub row for gc_uuid={uuid_key}"


def test_loader_uuid_opportunism_does_not_create_duplicate(
    loader: ScoutingLoader, db: sqlite3.Connection, tmp_path: Path
) -> None:
    """If a teams row already has gc_uuid set, no duplicate is created."""
    team_pk = _insert_team(db)
    game_id = "game-stream-uuid-opp-002"
    uuid_key = "66667777-8888-9999-aaaa-bbbbcccc0006"

    # Pre-insert a stub row with gc_uuid = uuid_key.
    db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) VALUES (?, 'tracked', ?, 0)",
        ("PreExistingOpp", uuid_key),
    )
    db.commit()

    scouting_dir = _make_roster(tmp_path, _PUBLIC_ID, _SEASON_ID)
    _make_games_json(scouting_dir, game_id)
    _make_boxscore(scouting_dir, game_id, own_key=_PUBLIC_ID, opp_key=uuid_key, player_id=_PLAYER_1)

    loader.load_team(scouting_dir, team_pk, _SEASON_ID)

    # Only one row with that gc_uuid should exist.
    count = db.execute(
        "SELECT COUNT(*) FROM teams WHERE gc_uuid = ?", (uuid_key,)
    ).fetchone()[0]
    assert count == 1, f"Expected exactly 1 row for gc_uuid={uuid_key}, got {count}"


# ---------------------------------------------------------------------------
# E-098-01: Multi-season aggregate isolation (regression test)
# ---------------------------------------------------------------------------


def test_aggregate_isolated_per_season(
    loader: ScoutingLoader, db: sqlite3.Connection
) -> None:
    """Aggregates for one season do not include game rows from another season.

    Sets up two seasons ("2025-spring" and "2026-spring") with different stats
    for the same player, then verifies that running aggregation for "2026-spring"
    produces only "2026-spring" data in player_season_batting and
    player_season_pitching.
    """
    season_a = "2025-spring"
    season_b = "2026-spring"
    game_a = "game-season-a-001"
    game_b = "game-season-b-001"

    # -- Seed required FK rows --------------------------------------------------
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
        (season_a, "Spring 2025", "spring-hs", 2025),
    )
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
        (season_b, "Spring 2026", "spring-hs", 2026),
    )
    # Own team (member) and opponent team (tracked).
    own_pk = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) VALUES (?, 'member', ?, 1)",
        ("Own Team", "ownteam-gc-uuid-0001"),
    ).lastrowid
    opp_pk = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) VALUES (?, 'tracked', ?, 0)",
        ("Opp Team", "oppteam-gc-uuid-0002"),
    ).lastrowid
    db.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (_PLAYER_1, "John", "Doe"),
    )
    db.execute(
        "INSERT OR IGNORE INTO games (game_id, season_id, game_date, home_team_id, away_team_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (game_a, season_a, "2025-04-10", own_pk, opp_pk),
    )
    db.execute(
        "INSERT OR IGNORE INTO games (game_id, season_id, game_date, home_team_id, away_team_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (game_b, season_b, "2026-04-10", own_pk, opp_pk),
    )

    # -- 2025 batting: 5 AB, 2 H; pitching: 9 ip_outs, 3 er ------------------
    db.execute(
        "INSERT INTO player_game_batting "
        "(game_id, player_id, team_id, ab, h, doubles, triples, hr, rbi, bb, so, sb) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_a, _PLAYER_1, own_pk, 5, 2, 0, 0, 0, 0, 0, 1, 0),
    )
    db.execute(
        "INSERT INTO player_game_pitching "
        "(game_id, player_id, team_id, ip_outs, h, er, bb, so) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (game_a, _PLAYER_1, own_pk, 9, 3, 3, 1, 4),
    )

    # -- 2026 batting: 4 AB, 3 H; pitching: 6 ip_outs, 1 er ------------------
    db.execute(
        "INSERT INTO player_game_batting "
        "(game_id, player_id, team_id, ab, h, doubles, triples, hr, rbi, bb, so, sb) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_b, _PLAYER_1, own_pk, 4, 3, 1, 0, 0, 0, 0, 0, 0),
    )
    db.execute(
        "INSERT INTO player_game_pitching "
        "(game_id, player_id, team_id, ip_outs, h, er, bb, so) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (game_b, _PLAYER_1, own_pk, 6, 2, 1, 0, 3),
    )
    db.commit()

    # -- Run aggregation for 2026-spring only (INTEGER PK) --------------------
    loader._compute_batting_aggregates(own_pk, season_b)
    loader._compute_pitching_aggregates(own_pk, season_b)
    db.commit()

    # -- AC-1: batting aggregate for 2026-spring contains only 2026 game data --
    bat_row = db.execute(
        "SELECT ab, h, doubles FROM player_season_batting "
        "WHERE player_id = ? AND team_id = ? AND season_id = ?",
        (_PLAYER_1, own_pk, season_b),
    ).fetchone()
    assert bat_row is not None, "Expected player_season_batting row for 2026-spring"
    assert bat_row[0] == 4, f"Expected ab=4 (2026 only), got {bat_row[0]}"
    assert bat_row[1] == 3, f"Expected h=3 (2026 only), got {bat_row[1]}"
    assert bat_row[2] == 1, f"Expected doubles=1 (2026 only), got {bat_row[2]}"

    # -- AC-2: pitching aggregate for 2026-spring contains only 2026 game data -
    pitch_row = db.execute(
        "SELECT ip_outs, er FROM player_season_pitching "
        "WHERE player_id = ? AND team_id = ? AND season_id = ?",
        (_PLAYER_1, own_pk, season_b),
    ).fetchone()
    assert pitch_row is not None, "Expected player_season_pitching row for 2026-spring"
    assert pitch_row[0] == 6, f"Expected ip_outs=6 (2026 only), got {pitch_row[0]}"
    assert pitch_row[1] == 1, f"Expected er=1 (2026 only), got {pitch_row[1]}"

    # No 2025-spring rows should have been inserted.
    bat_2025 = db.execute(
        "SELECT COUNT(*) FROM player_season_batting WHERE season_id = ?", (season_a,)
    ).fetchone()[0]
    assert bat_2025 == 0, f"Expected 0 rows for 2025-spring, got {bat_2025}"

    pitch_2025 = db.execute(
        "SELECT COUNT(*) FROM player_season_pitching WHERE season_id = ?", (season_a,)
    ).fetchone()[0]
    assert pitch_2025 == 0, f"Expected 0 rows for 2025-spring, got {pitch_2025}"
