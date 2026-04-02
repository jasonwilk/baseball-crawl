"""Tests for migration 013: Fix stale season_ids for teams without program_id.

Verifies that the migration:
- Corrects suffixed season_ids to year-only for opponent-only games (both
  teams lack program_id).
- Does NOT corrupt member-team games (where at least one team has program_id).
- Handles composite-PK dedup correctly.
- Is idempotent.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from migrations.apply_migrations import run_migrations

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_MIGRATION_FILE = _PROJECT_ROOT / "migrations" / "013_fix_stale_season_ids.sql"

_OLD_SEASON = "2026-spring-hs"
_CORRECTED_SEASON = "2026"

# Team IDs
_MEMBER_TEAM = 10   # has program_id
_OPP_STUB_A = 20    # no program_id, season_year=2026
_OPP_STUB_B = 30    # no program_id, season_year=2026


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    """Apply all migrations up to 012, then seed test data with OLD season_ids."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")

    # Program for member team
    conn.execute(
        "INSERT OR IGNORE INTO programs (program_id, name, program_type) "
        "VALUES ('lsb-hs', 'Lincoln Standing Bear HS', 'hs')"
    )

    # Member team (WITH program_id)
    conn.execute(
        "INSERT OR IGNORE INTO teams (id, name, membership_type, is_active, "
        "season_year, program_id) "
        "VALUES (?, 'LSB Varsity', 'member', 1, 2026, 'lsb-hs')",
        (_MEMBER_TEAM,),
    )

    # Opponent stubs (WITHOUT program_id)
    conn.execute(
        "INSERT OR IGNORE INTO teams (id, name, membership_type, is_active, "
        "season_year, program_id) "
        "VALUES (?, 'Opponent A', 'tracked', 1, 2026, NULL)",
        (_OPP_STUB_A,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO teams (id, name, membership_type, is_active, "
        "season_year, program_id) "
        "VALUES (?, 'Opponent B', 'tracked', 1, 2026, NULL)",
        (_OPP_STUB_B,),
    )

    # Old season row (FK prerequisite)
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, ?, 'spring-hs', 2026)",
        (_OLD_SEASON, _OLD_SEASON),
    )

    # Player
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES ('p1', 'Test', 'Player')"
    )

    # Game 1: member vs opponent (member has program_id → must NOT change)
    conn.execute(
        "INSERT OR IGNORE INTO games "
        "(game_id, season_id, game_date, home_team_id, away_team_id, status) "
        "VALUES ('member-game', ?, '2026-04-01', ?, ?, 'completed')",
        (_OLD_SEASON, _MEMBER_TEAM, _OPP_STUB_A),
    )
    conn.execute(
        "INSERT OR IGNORE INTO plays "
        "(game_id, play_order, inning, half, season_id, batting_team_id, "
        "batter_id, outcome, pitch_count, is_first_pitch_strike, is_qab, "
        "home_score, away_score, did_score_change, outs_after, did_outs_change) "
        "VALUES ('member-game', 1, 1, 'top', ?, ?, 'p1', 'Single', 3, 1, 0, "
        "0, 0, 0, 0, 0)",
        (_OLD_SEASON, _MEMBER_TEAM),
    )

    # Game 2: opponent vs opponent (both lack program_id → SHOULD change)
    conn.execute(
        "INSERT OR IGNORE INTO games "
        "(game_id, season_id, game_date, home_team_id, away_team_id, status) "
        "VALUES ('opp-game', ?, '2026-04-02', ?, ?, 'completed')",
        (_OLD_SEASON, _OPP_STUB_A, _OPP_STUB_B),
    )
    conn.execute(
        "INSERT OR IGNORE INTO plays "
        "(game_id, play_order, inning, half, season_id, batting_team_id, "
        "batter_id, outcome, pitch_count, is_first_pitch_strike, is_qab, "
        "home_score, away_score, did_score_change, outs_after, did_outs_change) "
        "VALUES ('opp-game', 1, 1, 'top', ?, ?, 'p1', 'Flyout', 2, 0, 0, "
        "0, 0, 0, 1, 1)",
        (_OLD_SEASON, _OPP_STUB_A),
    )

    # Stat rows for opponent stubs
    conn.execute(
        "INSERT OR IGNORE INTO player_season_batting "
        "(player_id, team_id, season_id, stat_completeness) "
        "VALUES ('p1', ?, ?, 'boxscore_only')",
        (_OPP_STUB_A, _OLD_SEASON),
    )
    conn.execute(
        "INSERT OR IGNORE INTO player_season_pitching "
        "(player_id, team_id, season_id, stat_completeness) "
        "VALUES ('p1', ?, ?, 'boxscore_only')",
        (_OPP_STUB_A, _OLD_SEASON),
    )
    conn.execute(
        "INSERT OR IGNORE INTO team_rosters "
        "(team_id, player_id, season_id) VALUES (?, 'p1', ?)",
        (_OPP_STUB_A, _OLD_SEASON),
    )
    conn.execute(
        "INSERT OR IGNORE INTO spray_charts "
        "(game_id, team_id, player_id, season_id, chart_type, x, y) "
        "VALUES ('opp-game', ?, 'p1', ?, 'offensive', 0.5, 0.5)",
        (_OPP_STUB_A, _OLD_SEASON),
    )

    conn.commit()

    # Apply migration 013
    sql = _MIGRATION_FILE.read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()

    yield conn
    conn.close()


@pytest.fixture()
def db_with_dupes(tmp_path: Path) -> sqlite3.Connection:
    """Seed BOTH old-suffixed AND year-only rows for the same (player, team).

    This exercises the composite-key dedup DELETE path (steps 5a, 6a, 7a)
    where the migration must DELETE the old-suffixed row because an UPDATE
    would violate the UNIQUE constraint.
    """
    db_path = tmp_path / "test_dupes.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")

    # Opponent stub team (no program_id)
    conn.execute(
        "INSERT OR IGNORE INTO teams (id, name, membership_type, is_active, "
        "season_year, program_id) "
        "VALUES (?, 'Opponent Dupe', 'tracked', 1, 2026, NULL)",
        (_OPP_STUB_A,),
    )

    # Both season rows as FK prerequisites
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, ?, 'spring-hs', 2026)",
        (_OLD_SEASON, _OLD_SEASON),
    )
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, ?, 'default', 2026)",
        (_CORRECTED_SEASON, _CORRECTED_SEASON),
    )

    # Two players to confirm per-player dedup
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES ('p1', 'Test', 'Player')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES ('p2', 'Other', 'Player')"
    )

    # -- player_season_batting: both old-suffixed AND year-only rows ------
    # p1: has BOTH → old-suffixed should be DELETED
    conn.execute(
        "INSERT INTO player_season_batting "
        "(player_id, team_id, season_id, stat_completeness) "
        "VALUES ('p1', ?, ?, 'boxscore_only')",
        (_OPP_STUB_A, _OLD_SEASON),
    )
    conn.execute(
        "INSERT INTO player_season_batting "
        "(player_id, team_id, season_id, stat_completeness) "
        "VALUES ('p1', ?, ?, 'boxscore_only')",
        (_OPP_STUB_A, _CORRECTED_SEASON),
    )
    # p2: only old-suffixed → should be UPDATED (no conflict)
    conn.execute(
        "INSERT INTO player_season_batting "
        "(player_id, team_id, season_id, stat_completeness) "
        "VALUES ('p2', ?, ?, 'boxscore_only')",
        (_OPP_STUB_A, _OLD_SEASON),
    )

    # -- player_season_pitching: both old-suffixed AND year-only rows -----
    conn.execute(
        "INSERT INTO player_season_pitching "
        "(player_id, team_id, season_id, stat_completeness) "
        "VALUES ('p1', ?, ?, 'boxscore_only')",
        (_OPP_STUB_A, _OLD_SEASON),
    )
    conn.execute(
        "INSERT INTO player_season_pitching "
        "(player_id, team_id, season_id, stat_completeness) "
        "VALUES ('p1', ?, ?, 'boxscore_only')",
        (_OPP_STUB_A, _CORRECTED_SEASON),
    )
    conn.execute(
        "INSERT INTO player_season_pitching "
        "(player_id, team_id, season_id, stat_completeness) "
        "VALUES ('p2', ?, ?, 'boxscore_only')",
        (_OPP_STUB_A, _OLD_SEASON),
    )

    # -- team_rosters: both old-suffixed AND year-only rows ---------------
    conn.execute(
        "INSERT INTO team_rosters (team_id, player_id, season_id) "
        "VALUES (?, 'p1', ?)",
        (_OPP_STUB_A, _OLD_SEASON),
    )
    conn.execute(
        "INSERT INTO team_rosters (team_id, player_id, season_id) "
        "VALUES (?, 'p1', ?)",
        (_OPP_STUB_A, _CORRECTED_SEASON),
    )
    conn.execute(
        "INSERT INTO team_rosters (team_id, player_id, season_id) "
        "VALUES (?, 'p2', ?)",
        (_OPP_STUB_A, _OLD_SEASON),
    )

    conn.commit()

    # Apply migration 013
    sql = _MIGRATION_FILE.read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()

    yield conn
    conn.close()


# ── Member-team games are NOT corrupted ─────────────────────────────


def test_member_game_season_id_unchanged(db: sqlite3.Connection) -> None:
    """Game between member team and opponent keeps its suffixed season_id."""
    row = db.execute(
        "SELECT season_id FROM games WHERE game_id = 'member-game'"
    ).fetchone()
    assert row[0] == _OLD_SEASON


def test_member_game_plays_season_id_unchanged(db: sqlite3.Connection) -> None:
    """Plays for member-team game keep their suffixed season_id."""
    row = db.execute(
        "SELECT season_id FROM plays WHERE game_id = 'member-game'"
    ).fetchone()
    assert row[0] == _OLD_SEASON


# ── Opponent-only games ARE corrected ───────────────────────────────


def test_opp_game_season_id_corrected(db: sqlite3.Connection) -> None:
    """Game between two opponent stubs gets corrected to year-only."""
    row = db.execute(
        "SELECT season_id FROM games WHERE game_id = 'opp-game'"
    ).fetchone()
    assert row[0] == _CORRECTED_SEASON


def test_opp_game_plays_season_id_corrected(db: sqlite3.Connection) -> None:
    """Plays for opponent-only game get corrected to year-only."""
    row = db.execute(
        "SELECT season_id FROM plays WHERE game_id = 'opp-game'"
    ).fetchone()
    assert row[0] == _CORRECTED_SEASON


# ── Stat tables corrected for opponent stubs ────────────────────────


def test_opp_batting_season_id_corrected(db: sqlite3.Connection) -> None:
    row = db.execute(
        "SELECT season_id FROM player_season_batting WHERE team_id = ?",
        (_OPP_STUB_A,),
    ).fetchone()
    assert row[0] == _CORRECTED_SEASON


def test_opp_pitching_season_id_corrected(db: sqlite3.Connection) -> None:
    row = db.execute(
        "SELECT season_id FROM player_season_pitching WHERE team_id = ?",
        (_OPP_STUB_A,),
    ).fetchone()
    assert row[0] == _CORRECTED_SEASON


def test_opp_roster_season_id_corrected(db: sqlite3.Connection) -> None:
    row = db.execute(
        "SELECT season_id FROM team_rosters WHERE team_id = ?",
        (_OPP_STUB_A,),
    ).fetchone()
    assert row[0] == _CORRECTED_SEASON


def test_opp_spray_season_id_corrected(db: sqlite3.Connection) -> None:
    row = db.execute(
        "SELECT season_id FROM spray_charts WHERE team_id = ?",
        (_OPP_STUB_A,),
    ).fetchone()
    assert row[0] == _CORRECTED_SEASON


# ── Season prerequisite row created ─────────────────────────────────


def test_year_only_season_row_created(db: sqlite3.Connection) -> None:
    row = db.execute(
        "SELECT season_type, year FROM seasons WHERE season_id = ?",
        (_CORRECTED_SEASON,),
    ).fetchone()
    assert row is not None
    assert row == ("default", 2026)


# ── Idempotency ─────────────────────────────────────────────────────


def test_idempotent_rerun(db: sqlite3.Connection) -> None:
    """Re-running the migration is a no-op."""
    sql = _MIGRATION_FILE.read_text(encoding="utf-8")
    db.executescript(sql)
    db.commit()

    # Member game still unchanged
    row = db.execute(
        "SELECT season_id FROM games WHERE game_id = 'member-game'"
    ).fetchone()
    assert row[0] == _OLD_SEASON

    # Opponent game still corrected
    row = db.execute(
        "SELECT season_id FROM games WHERE game_id = 'opp-game'"
    ).fetchone()
    assert row[0] == _CORRECTED_SEASON

    # No duplicate season rows
    count = db.execute(
        "SELECT COUNT(*) FROM seasons WHERE season_id = ?",
        (_CORRECTED_SEASON,),
    ).fetchone()[0]
    assert count == 1


# ── Composite-key dedup DELETE path (TN-3) ─────────────────────────


def test_batting_dedup_deletes_old_suffixed_row(
    db_with_dupes: sqlite3.Connection,
) -> None:
    """When both old-suffixed and year-only rows exist, the old one is deleted."""
    rows = db_with_dupes.execute(
        "SELECT season_id FROM player_season_batting "
        "WHERE player_id = 'p1' AND team_id = ?",
        (_OPP_STUB_A,),
    ).fetchall()
    season_ids = [r[0] for r in rows]
    assert season_ids == [_CORRECTED_SEASON], (
        f"Expected only year-only row; got {season_ids}"
    )


def test_batting_dedup_updates_when_no_conflict(
    db_with_dupes: sqlite3.Connection,
) -> None:
    """When only old-suffixed row exists, it is updated to year-only."""
    rows = db_with_dupes.execute(
        "SELECT season_id FROM player_season_batting "
        "WHERE player_id = 'p2' AND team_id = ?",
        (_OPP_STUB_A,),
    ).fetchall()
    season_ids = [r[0] for r in rows]
    assert season_ids == [_CORRECTED_SEASON]


def test_pitching_dedup_deletes_old_suffixed_row(
    db_with_dupes: sqlite3.Connection,
) -> None:
    """When both old-suffixed and year-only rows exist, the old one is deleted."""
    rows = db_with_dupes.execute(
        "SELECT season_id FROM player_season_pitching "
        "WHERE player_id = 'p1' AND team_id = ?",
        (_OPP_STUB_A,),
    ).fetchall()
    season_ids = [r[0] for r in rows]
    assert season_ids == [_CORRECTED_SEASON]


def test_pitching_dedup_updates_when_no_conflict(
    db_with_dupes: sqlite3.Connection,
) -> None:
    """When only old-suffixed row exists, it is updated to year-only."""
    rows = db_with_dupes.execute(
        "SELECT season_id FROM player_season_pitching "
        "WHERE player_id = 'p2' AND team_id = ?",
        (_OPP_STUB_A,),
    ).fetchall()
    season_ids = [r[0] for r in rows]
    assert season_ids == [_CORRECTED_SEASON]


def test_roster_dedup_deletes_old_suffixed_row(
    db_with_dupes: sqlite3.Connection,
) -> None:
    """When both old-suffixed and year-only rows exist, the old one is deleted."""
    rows = db_with_dupes.execute(
        "SELECT season_id FROM team_rosters "
        "WHERE player_id = 'p1' AND team_id = ?",
        (_OPP_STUB_A,),
    ).fetchall()
    season_ids = [r[0] for r in rows]
    assert season_ids == [_CORRECTED_SEASON]


def test_roster_dedup_updates_when_no_conflict(
    db_with_dupes: sqlite3.Connection,
) -> None:
    """When only old-suffixed row exists, it is updated to year-only."""
    rows = db_with_dupes.execute(
        "SELECT season_id FROM team_rosters "
        "WHERE player_id = 'p2' AND team_id = ?",
        (_OPP_STUB_A,),
    ).fetchall()
    season_ids = [r[0] for r in rows]
    assert season_ids == [_CORRECTED_SEASON]


def test_dedup_exactly_one_row_per_player_team(
    db_with_dupes: sqlite3.Connection,
) -> None:
    """After migration, each (player_id, team_id) has exactly one row per table."""
    for table in (
        "player_season_batting",
        "player_season_pitching",
        "team_rosters",
    ):
        for player in ("p1", "p2"):
            count = db_with_dupes.execute(
                f"SELECT COUNT(*) FROM {table} "  # noqa: S608
                "WHERE player_id = ? AND team_id = ?",
                (player, _OPP_STUB_A),
            ).fetchone()[0]
            assert count == 1, (
                f"{table}: expected 1 row for ({player}, {_OPP_STUB_A}), "
                f"got {count}"
            )
