"""Tests for post-load validation in ScoutingLoader (E-216-02).

Covers:
- (a) No duplicates → no warning logged
- (b) Duplicate game detected → WARNING logged
- (c) Roster count exceeding expected → WARNING logged
- (d) Roster count lower than expected (post-dedup) → no warning
- (e) Validation doesn't block the pipeline on warnings
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from migrations.apply_migrations import run_migrations
from src.gamechanger.loaders.scouting_loader import ScoutingLoader


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
    return ScoutingLoader(db)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PUBLIC_ID = "opp-slug-abc123"
_GC_UUID = "aaaabbbb-cccc-dddd-eeee-ffff00000001"
_SEASON_ID = "2025"
_PLAYER_1 = "player-uuid-001"
_PLAYER_2 = "player-uuid-002"
_PLAYER_3 = "player-uuid-003"
_OPP_UUID = "11112222-3333-4444-5555-aaaabbbbcccc"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_team(db: sqlite3.Connection) -> int:
    cursor = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, public_id, is_active, season_year) "
        "VALUES (?, 'tracked', ?, ?, 0, 2025)",
        ("Opp Team", _GC_UUID, _PUBLIC_ID),
    )
    db.commit()
    return cursor.lastrowid


def _crawl_result(
    team_id: int,
    roster: list[dict] | None = None,
    games: list[dict] | None = None,
    boxscores: dict[str, dict] | None = None,
) -> SimpleNamespace:
    """Build a ``ScoutingCrawlResult``-shaped payload for ``load_team``."""
    if roster is None:
        roster = [
            {"id": _PLAYER_1, "first_name": "John", "last_name": "Doe", "number": "14"},
            {"id": _PLAYER_2, "first_name": "Jane", "last_name": "Smith", "number": "7"},
        ]
    return SimpleNamespace(
        team_id=team_id,
        roster=roster,
        games=games if games is not None else [],
        boxscores=boxscores if boxscores is not None else {},
    )


def _make_game_entry(
    game_id: str,
    start_ts: str = "2025-04-10T18:00:00Z",
    team_score: int = 5,
    opp_score: int = 3,
) -> dict:
    return {
        "id": game_id,
        "game_status": "completed",
        "home_away": "home",
        "start_ts": start_ts,
        "score": {"team": team_score, "opponent_team": opp_score},
    }


def _make_minimal_boxscore(own_key: str = _PUBLIC_ID) -> dict:
    return {
        own_key: {
            "players": [
                {"id": _PLAYER_1, "first_name": "John", "last_name": "Doe", "number": "14"}
            ],
            "groups": [
                {
                    "category": "lineup",
                    "stats": [
                        {
                            "player_id": _PLAYER_1,
                            "stats": {"AB": 3, "R": 1, "H": 1, "RBI": 1, "BB": 0, "SO": 1},
                        }
                    ],
                    "extra": [],
                }
            ],
        },
        _OPP_UUID: {"players": [], "groups": []},
    }


# ---------------------------------------------------------------------------
# (a): No duplicates → no warning
# ---------------------------------------------------------------------------


def test_no_duplicate_games_no_warning(
    loader: ScoutingLoader, db: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When no duplicate games exist, no validation warning is logged."""
    team_pk = _insert_team(db)
    game_id = "game-stream-001"
    crawl_result = _crawl_result(
        team_pk,
        games=[_make_game_entry(game_id)],
        boxscores={game_id: _make_minimal_boxscore()},
    )

    with caplog.at_level(logging.WARNING, logger="src.gamechanger.loaders.scouting_loader"):
        loader.load_team(crawl_result)

    dedup_msgs = [r for r in caplog.records if "duplicate game" in r.message]
    assert len(dedup_msgs) == 0


# ---------------------------------------------------------------------------
# (b): Duplicate game detected → WARNING
# ---------------------------------------------------------------------------


def test_duplicate_game_detected_produces_warning(
    loader: ScoutingLoader, db: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When duplicate game rows exist for the same date and team pair,
    a WARNING is logged."""
    team_pk = _insert_team(db)

    # Seed a pre-existing completed game for the same date and team.
    # First ensure season exists.
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) "
        "VALUES (?, ?, ?)",
        (_SEASON_ID, "2025", 2025),
    )
    # Insert an opponent team for the pre-existing game.
    opp_cursor = db.execute(
        "INSERT INTO teams (name, membership_type, is_active, season_year) "
        "VALUES ('Other Opp', 'tracked', 0, 2025)",
    )
    opp_pk = opp_cursor.lastrowid
    # Insert two game rows for the same date and team pair (simulating a dup).
    db.execute(
        """
        INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id,
                           home_score, away_score, status)
        VALUES ('pre-existing-game', ?, '2025-04-10', ?, ?, 5, 3, 'completed')
        """,
        (_SEASON_ID, team_pk, opp_pk),
    )
    db.execute(
        """
        INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id,
                           home_score, away_score, status)
        VALUES ('duplicate-game', ?, '2025-04-10', ?, ?, 6, 2, 'completed')
        """,
        (_SEASON_ID, opp_pk, team_pk),  # reversed order -- same unordered pair
    )
    db.commit()

    # A non-empty boxscores payload is required to reach the post-boxscore
    # validation tail (an empty one short-circuits it, E-247-01 F1).  This
    # boxscore has no matching games entry, so it is skipped and adds no rows --
    # only the pre-seeded duplicates remain for _check_duplicate_games to find.
    crawl_result = _crawl_result(
        team_pk, games=[], boxscores={"orphan-game": _make_minimal_boxscore()},
    )

    with caplog.at_level(logging.WARNING, logger="src.gamechanger.loaders.scouting_loader"):
        loader.load_team(crawl_result)

    dedup_msgs = [r for r in caplog.records if "duplicate game" in r.message]
    assert len(dedup_msgs) >= 1, "Expected WARNING about duplicate games"
    assert str(team_pk) in dedup_msgs[0].message


# ---------------------------------------------------------------------------
# (c): Roster count exceeding expected → WARNING
# ---------------------------------------------------------------------------


def test_roster_count_exceeding_expected_produces_warning(
    loader: ScoutingLoader, db: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When DB roster count exceeds the crawled roster count, a WARNING is logged."""
    team_pk = _insert_team(db)

    # Ensure season exists for FK.
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) "
        "VALUES (?, ?, ?)",
        (_SEASON_ID, "2025", 2025),
    )
    # Pre-insert an extra player in team_rosters that isn't in the crawl roster.
    db.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, 'Extra', 'Player')",
        (_PLAYER_3,),
    )
    db.execute(
        "INSERT INTO team_rosters (team_id, player_id, season_id) VALUES (?, ?, ?)",
        (team_pk, _PLAYER_3, _SEASON_ID),
    )
    db.commit()

    # The crawl roster has 2 players, but the DB will have 3 (2 from the load +
    # 1 pre-existing).
    with caplog.at_level(logging.WARNING, logger="src.gamechanger.loaders.scouting_loader"):
        loader.load_team(_crawl_result(team_pk))

    roster_msgs = [r for r in caplog.records if "roster entries" in r.message]
    assert len(roster_msgs) >= 1, "Expected WARNING about roster count"
    assert "expected 2" in roster_msgs[0].message
    assert "found 3" in roster_msgs[0].message


# ---------------------------------------------------------------------------
# (d): Roster count lower than expected (post-dedup) → no warning
# ---------------------------------------------------------------------------


def test_roster_count_lower_than_expected_no_warning(
    loader: ScoutingLoader, db: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When DB roster count is lower than expected (post-dedup merges reduced
    it), no warning is logged."""
    team_pk = _insert_team(db)

    # Load roster with 2 players to set up DB state.
    loader.load_team(_crawl_result(team_pk))

    # Derive the DB season_id the loader uses (same logic as load_team).
    from src.gamechanger.loaders import derive_season_id_for_team
    db_season_id, _ = derive_season_id_for_team(db, team_pk)

    # Confirm DB has 2 roster entries.
    actual = db.execute(
        "SELECT COUNT(*) FROM team_rosters WHERE team_id = ? AND season_id = ?",
        (team_pk, db_season_id),
    ).fetchone()[0]
    assert actual == 2

    # Call validation directly with expected_count=5 (DB=2 < expected=5).
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="src.gamechanger.loaders.scouting_loader"):
        loader._validate_roster_count(team_pk, db_season_id, expected_count=5)

    roster_msgs = [r for r in caplog.records if "roster entries" in r.message]
    assert len(roster_msgs) == 0, "Should NOT warn when DB count < expected"


# ---------------------------------------------------------------------------
# (e): Validation doesn't block the pipeline
# ---------------------------------------------------------------------------


def test_validation_does_not_block_pipeline(
    loader: ScoutingLoader, db: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Even when validation logs warnings, the pipeline completes and
    returns a valid LoadResult."""
    team_pk = _insert_team(db)

    # Ensure season exists for FK.
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) "
        "VALUES (?, ?, ?)",
        (_SEASON_ID, "2025", 2025),
    )
    # Pre-insert extra roster entry to trigger roster warning.
    db.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, 'Extra', 'Player')",
        (_PLAYER_3,),
    )
    db.execute(
        "INSERT INTO team_rosters (team_id, player_id, season_id) VALUES (?, ?, ?)",
        (team_pk, _PLAYER_3, _SEASON_ID),
    )
    db.commit()

    with caplog.at_level(logging.WARNING, logger="src.gamechanger.loaders.scouting_loader"):
        result = loader.load_team(_crawl_result(team_pk))

    # Pipeline completed (returned a result, didn't raise).
    assert result is not None
    assert result.loaded >= 0


# ---------------------------------------------------------------------------
# Cross-season: same date/team pair in different seasons → no false positive
# ---------------------------------------------------------------------------


def test_same_date_team_pair_different_seasons_no_warning(
    loader: ScoutingLoader, db: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Games on the same date between the same teams but in different seasons
    should NOT produce a duplicate warning."""
    team_pk = _insert_team(db)

    # Create two seasons.
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) "
        "VALUES (?, ?, ?)",
        (_SEASON_ID, "2025", 2025),
    )
    other_season = "2024"
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) "
        "VALUES (?, ?, ?)",
        (other_season, "2024", 2024),
    )

    # Insert an opponent team.
    opp_cursor = db.execute(
        "INSERT INTO teams (name, membership_type, is_active, season_year) "
        "VALUES ('Other Opp', 'tracked', 0, 2025)",
    )
    opp_pk = opp_cursor.lastrowid

    # Insert games on the same date with the same team pair, but different seasons.
    db.execute(
        """
        INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id,
                           home_score, away_score, status)
        VALUES ('game-season-2025', ?, '2025-04-10', ?, ?, 5, 3, 'completed')
        """,
        (_SEASON_ID, team_pk, opp_pk),
    )
    db.execute(
        """
        INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id,
                           home_score, away_score, status)
        VALUES ('game-season-2024', ?, '2025-04-10', ?, ?, 6, 2, 'completed')
        """,
        (other_season, opp_pk, team_pk),
    )
    db.commit()

    # Non-empty boxscores so the post-boxscore validation tail runs; the payload
    # has no matching games entry and is skipped, adding no rows.
    crawl_result = _crawl_result(
        team_pk, games=[], boxscores={"orphan-game": _make_minimal_boxscore()},
    )

    with caplog.at_level(logging.WARNING, logger="src.gamechanger.loaders.scouting_loader"):
        loader.load_team(crawl_result)

    dedup_msgs = [r for r in caplog.records if "duplicate game" in r.message]
    assert len(dedup_msgs) == 0, "Should NOT warn about games in different seasons"
