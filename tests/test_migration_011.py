"""Tests for migration 011: Fix season_id for Lincoln Rebels 14U.

Verifies that the migration corrects season_id from '2026-spring-hs' to
'2025-summer-usssa' for team 126 and its scouted opponents, and that
scouting_runs is NOT updated.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from migrations.apply_migrations import run_migrations

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA_FILE = _PROJECT_ROOT / "migrations" / "001_initial_schema.sql"
_MIGRATION_FILE = _PROJECT_ROOT / "migrations" / "011_fix_season_id_rebels_14u.sql"

_OLD_SEASON = "2026-spring-hs"
_NEW_SEASON = "2025-summer-usssa"
_TEAM_126 = 126
_OPP_TEAM = 200


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    """Apply all migrations up to 009, then seed test data with the OLD season_id."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")

    # Ensure team 126 exists with no program (the migration will assign one)
    conn.execute(
        "INSERT OR IGNORE INTO teams (id, name, membership_type, is_active, season_year) "
        "VALUES (?, 'Rebels 14U', 'member', 1, 2025)",
        (_TEAM_126,),
    )
    # Opponent team scouted via team 126
    conn.execute(
        "INSERT OR IGNORE INTO teams (id, name, membership_type, is_active) "
        "VALUES (?, 'Opponent A', 'tracked', 1)",
        (_OPP_TEAM,),
    )
    # Link opponent to team 126
    conn.execute(
        "INSERT OR IGNORE INTO team_opponents (our_team_id, opponent_team_id, first_seen_year) "
        "VALUES (?, ?, 2025)",
        (_TEAM_126, _OPP_TEAM),
    )

    # Old season row (FK prerequisite for seeding)
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, ?, 'spring-hs', 2026)",
        (_OLD_SEASON, _OLD_SEASON),
    )

    # Seed players
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES ('p1', 'John', 'Doe')"
    )

    # Seed data in each affected table with the OLD season_id
    conn.execute(
        "INSERT OR IGNORE INTO games (game_id, season_id, game_date, home_team_id, away_team_id, status) "
        "VALUES ('game-001', ?, '2025-06-15', ?, ?, 'completed')",
        (_OLD_SEASON, _TEAM_126, _OPP_TEAM),
    )
    conn.execute(
        "INSERT OR IGNORE INTO plays (game_id, play_order, inning, half, season_id, batting_team_id, "
        "batter_id, outcome, pitch_count, is_first_pitch_strike, is_qab, "
        "home_score, away_score, did_score_change, outs_after, did_outs_change) "
        "VALUES ('game-001', 1, 1, 'top', ?, ?, 'p1', 'Single', 3, 1, 0, 0, 0, 0, 0, 0)",
        (_OLD_SEASON, _TEAM_126),
    )
    conn.execute(
        "INSERT OR IGNORE INTO player_season_batting (player_id, team_id, season_id, stat_completeness) "
        "VALUES ('p1', ?, ?, 'full')",
        (_TEAM_126, _OLD_SEASON),
    )
    conn.execute(
        "INSERT OR IGNORE INTO player_season_pitching (player_id, team_id, season_id, stat_completeness) "
        "VALUES ('p1', ?, ?, 'full')",
        (_TEAM_126, _OLD_SEASON),
    )
    conn.execute(
        "INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id) "
        "VALUES (?, 'p1', ?)",
        (_TEAM_126, _OLD_SEASON),
    )
    conn.execute(
        "INSERT OR IGNORE INTO spray_charts (game_id, team_id, player_id, season_id, chart_type, x, y) "
        "VALUES ('game-001', ?, 'p1', ?, 'offensive', 0.5, 0.5)",
        (_TEAM_126, _OLD_SEASON),
    )

    # Opponent data with old season_id
    conn.execute(
        "INSERT OR IGNORE INTO player_season_batting (player_id, team_id, season_id, stat_completeness) "
        "VALUES ('p1', ?, ?, 'full')",
        (_OPP_TEAM, _OLD_SEASON),
    )
    conn.execute(
        "INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id) "
        "VALUES (?, 'p1', ?)",
        (_OPP_TEAM, _OLD_SEASON),
    )

    # Scouting runs row -- should NOT be updated
    conn.execute(
        "INSERT OR IGNORE INTO scouting_runs "
        "(team_id, season_id, run_type, status) "
        "VALUES (?, ?, 'full', 'completed')",
        (_TEAM_126, _OLD_SEASON),
    )

    conn.commit()

    # Now apply migration 011
    sql = _MIGRATION_FILE.read_text(encoding="utf-8")
    conn.executescript("PRAGMA foreign_keys=ON;\n" + sql)
    conn.commit()

    yield conn
    conn.close()


# ── Program and team assignment (AC-3) ──────────────────────────────


def test_usssa_program_created(db: sqlite3.Connection) -> None:
    """AC-3: rebels-usssa program row exists."""
    row = db.execute(
        "SELECT program_type FROM programs WHERE program_id = 'rebels-usssa'"
    ).fetchone()
    assert row is not None
    assert row[0] == "usssa"


def test_team_126_assigned_to_program(db: sqlite3.Connection) -> None:
    """AC-3: Team 126 has program_id='rebels-usssa'."""
    row = db.execute(
        "SELECT program_id FROM teams WHERE id = ?", (_TEAM_126,)
    ).fetchone()
    assert row[0] == "rebels-usssa"


# ── Season row (AC-4) ──────────────────────────────────────────────


def test_new_season_row_exists(db: sqlite3.Connection) -> None:
    """AC-4: seasons row for '2025-summer-usssa' exists."""
    row = db.execute(
        "SELECT season_type, year FROM seasons WHERE season_id = ?", (_NEW_SEASON,)
    ).fetchone()
    assert row is not None
    assert row == ("summer-usssa", 2025)


# ── Games corrected (AC-6) ─────────────────────────────────────────


def test_games_season_id_corrected(db: sqlite3.Connection) -> None:
    """AC-6: games rows have the corrected season_id."""
    row = db.execute(
        "SELECT season_id FROM games WHERE game_id = 'game-001'"
    ).fetchone()
    assert row[0] == _NEW_SEASON


# ── Plays corrected (AC-7) ─────────────────────────────────────────


def test_plays_season_id_corrected(db: sqlite3.Connection) -> None:
    """AC-7: plays rows have the corrected season_id."""
    row = db.execute(
        "SELECT season_id FROM plays WHERE game_id = 'game-001'"
    ).fetchone()
    assert row[0] == _NEW_SEASON


# ── Season stats corrected (AC-8) ──────────────────────────────────


def test_batting_season_id_corrected(db: sqlite3.Connection) -> None:
    """AC-8: player_season_batting for team 126 corrected."""
    row = db.execute(
        "SELECT season_id FROM player_season_batting WHERE team_id = ?", (_TEAM_126,)
    ).fetchone()
    assert row[0] == _NEW_SEASON


def test_pitching_season_id_corrected(db: sqlite3.Connection) -> None:
    """AC-8: player_season_pitching for team 126 corrected."""
    row = db.execute(
        "SELECT season_id FROM player_season_pitching WHERE team_id = ?", (_TEAM_126,)
    ).fetchone()
    assert row[0] == _NEW_SEASON


def test_opponent_batting_season_id_corrected(db: sqlite3.Connection) -> None:
    """AC-5/AC-8: opponent data also corrected via CTE."""
    row = db.execute(
        "SELECT season_id FROM player_season_batting WHERE team_id = ?", (_OPP_TEAM,)
    ).fetchone()
    assert row[0] == _NEW_SEASON


# ── Rosters corrected (AC-9) ──────────────────────────────────────


def test_rosters_season_id_corrected(db: sqlite3.Connection) -> None:
    """AC-9: team_rosters for team 126 corrected."""
    row = db.execute(
        "SELECT season_id FROM team_rosters WHERE team_id = ?", (_TEAM_126,)
    ).fetchone()
    assert row[0] == _NEW_SEASON


def test_opponent_rosters_season_id_corrected(db: sqlite3.Connection) -> None:
    """AC-9: opponent team_rosters also corrected."""
    row = db.execute(
        "SELECT season_id FROM team_rosters WHERE team_id = ?", (_OPP_TEAM,)
    ).fetchone()
    assert row[0] == _NEW_SEASON


# ── Spray charts corrected (AC-10) ────────────────────────────────


def test_spray_charts_season_id_corrected(db: sqlite3.Connection) -> None:
    """AC-10: spray_charts for team 126 corrected."""
    row = db.execute(
        "SELECT season_id FROM spray_charts WHERE team_id = ?", (_TEAM_126,)
    ).fetchone()
    assert row[0] == _NEW_SEASON


# ── scouting_runs NOT updated (AC-11) ─────────────────────────────


def test_scouting_runs_not_updated(db: sqlite3.Connection) -> None:
    """AC-11: scouting_runs.season_id stays as '2026-spring-hs'."""
    row = db.execute(
        "SELECT season_id FROM scouting_runs WHERE team_id = ?", (_TEAM_126,)
    ).fetchone()
    assert row[0] == _OLD_SEASON


# ── Idempotency (AC-12) ───────────────────────────────────────────


def test_idempotent_rerun(db: sqlite3.Connection) -> None:
    """AC-12: Re-running the migration does not fail or produce duplicates."""
    sql = _MIGRATION_FILE.read_text(encoding="utf-8")
    # Run again -- should be a no-op
    db.executescript("PRAGMA foreign_keys=ON;\n" + sql)
    db.commit()

    # Verify no duplicates
    count = db.execute(
        "SELECT COUNT(*) FROM games WHERE game_id = 'game-001'"
    ).fetchone()[0]
    assert count == 1

    count = db.execute(
        "SELECT COUNT(*) FROM seasons WHERE season_id = ?", (_NEW_SEASON,)
    ).fetchone()[0]
    assert count == 1

    # Verify values still correct
    row = db.execute(
        "SELECT season_id FROM games WHERE game_id = 'game-001'"
    ).fetchone()
    assert row[0] == _NEW_SEASON
