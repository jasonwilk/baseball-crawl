"""Tests for finalize_opponent_resolution() write-through logic.

Covers:
- AC-1:  finalize_opponent_resolution() exists, performs five operations atomically
- AC-4:  UNIQUE constraint not violated when resolved team already has team_opponents row
- AC-5:  is_active = 1 set on resolved team
- AC-6:  Stub discovered internally via _find_tracked_stub pattern
- AC-7:  Function runs within caller's transaction (no own commit)
- AC-9:  FK references reassigned from stub to resolved team, with dedup guard
- AC-10: All six test scenarios
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from migrations.apply_migrations import run_migrations
from src.api.db import finalize_opponent_resolution


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    """SQLite connection with full schema applied."""
    db_path = tmp_path / "test_finalize.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    yield conn
    conn.close()


def _insert_team(
    conn: sqlite3.Connection,
    name: str,
    membership_type: str = "tracked",
    public_id: str | None = None,
    gc_uuid: str | None = None,
    is_active: int = 0,
    season_year: int | None = 2026,
) -> int:
    cur = conn.execute(
        "INSERT INTO teams (name, membership_type, public_id, gc_uuid, is_active, source, season_year) "
        "VALUES (?, ?, ?, ?, ?, 'test', ?)",
        (name, membership_type, public_id, gc_uuid, is_active, season_year),
    )
    return cur.lastrowid


def _insert_team_opponents(
    conn: sqlite3.Connection,
    our_team_id: int,
    opponent_team_id: int,
    first_seen_year: int | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO team_opponents (our_team_id, opponent_team_id, first_seen_year) "
        "VALUES (?, ?, ?)",
        (our_team_id, opponent_team_id, first_seen_year),
    )
    return cur.lastrowid


def _insert_season(conn: sqlite3.Connection, season_id: str = "2026-spring-hs") -> None:
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, 'Spring 2026 HS', 'spring-hs', 2026)",
        (season_id,),
    )


def _insert_game(
    conn: sqlite3.Connection,
    game_id: str,
    home_team_id: int,
    away_team_id: int,
    season_id: str = "2026-spring-hs",
    game_stream_id: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, game_stream_id) "
        "VALUES (?, ?, '2026-04-01', ?, ?, ?)",
        (game_id, season_id, home_team_id, away_team_id, game_stream_id),
    )


def _insert_player(conn: sqlite3.Connection, player_id: str, first_name: str = "Test", last_name: str = "Player") -> None:
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (player_id, first_name, last_name),
    )


def _insert_player_game_batting(
    conn: sqlite3.Connection,
    game_id: str,
    player_id: str,
    team_id: int,
) -> int:
    cur = conn.execute(
        "INSERT INTO player_game_batting (game_id, player_id, team_id) VALUES (?, ?, ?)",
        (game_id, player_id, team_id),
    )
    return cur.lastrowid


def _insert_player_season_batting(
    conn: sqlite3.Connection,
    player_id: str,
    team_id: int,
    season_id: str = "2026-spring-hs",
) -> int:
    cur = conn.execute(
        "INSERT INTO player_season_batting (player_id, team_id, season_id) VALUES (?, ?, ?)",
        (player_id, team_id, season_id),
    )
    return cur.lastrowid


def _insert_team_roster(
    conn: sqlite3.Connection,
    team_id: int,
    player_id: str,
    season_id: str = "2026-spring-hs",
) -> None:
    conn.execute(
        "INSERT INTO team_rosters (team_id, player_id, season_id) VALUES (?, ?, ?)",
        (team_id, player_id, season_id),
    )


# ---------------------------------------------------------------------------
# AC-10a: Resolution creates team_opponents row and sets is_active=1
# ---------------------------------------------------------------------------


class TestBasicResolution:
    """AC-10a: Resolution creates team_opponents row and sets is_active=1."""

    def test_creates_team_opponents_and_activates(self, db: sqlite3.Connection) -> None:
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        resolved_id = _insert_team(db, "Rival HS", is_active=0, public_id="rival-slug")
        db.commit()

        result = finalize_opponent_resolution(
            db,
            our_team_id=our_id,
            resolved_team_id=resolved_id,
            opponent_name="Rival HS",
        )

        # team_opponents row created
        row = db.execute(
            "SELECT our_team_id, opponent_team_id, first_seen_year FROM team_opponents "
            "WHERE our_team_id = ? AND opponent_team_id = ?",
            (our_id, resolved_id),
        ).fetchone()
        assert row is not None
        assert row[2] == 2026  # first_seen_year derived from member team's season_year

        # is_active = 1
        active = db.execute(
            "SELECT is_active FROM teams WHERE id = ?", (resolved_id,)
        ).fetchone()
        assert active[0] == 1

        # Result dict
        assert result["resolved_team_id"] == resolved_id
        assert result["public_id"] == "rival-slug"
        assert result["old_stub_team_id"] is None

    def test_first_seen_year_fallback_to_current_year(self, db: sqlite3.Connection) -> None:
        """When member team has no season_year, falls back to current calendar year."""
        our_id = _insert_team(db, "LSB Varsity", membership_type="member", season_year=None)
        resolved_id = _insert_team(db, "Rival HS")
        db.commit()

        finalize_opponent_resolution(
            db,
            our_team_id=our_id,
            resolved_team_id=resolved_id,
            opponent_name="Rival HS",
        )

        row = db.execute(
            "SELECT first_seen_year FROM team_opponents WHERE our_team_id = ? AND opponent_team_id = ?",
            (our_id, resolved_id),
        ).fetchone()
        assert row is not None
        assert row[0] is not None  # Should be current year


# ---------------------------------------------------------------------------
# AC-10b: Resolution with existing stub updates row to point to resolved team
# ---------------------------------------------------------------------------


class TestStubReplacement:
    """AC-10b: Resolution with existing stub updates row to point to resolved team."""

    def test_stub_row_updated_to_resolved_team(self, db: sqlite3.Connection) -> None:
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        stub_id = _insert_team(db, "Rival HS", public_id=None)
        resolved_id = _insert_team(db, "Rival HS", public_id="rival-slug", gc_uuid="rival-uuid")
        _insert_team_opponents(db, our_id, stub_id, first_seen_year=2025)
        db.commit()

        result = finalize_opponent_resolution(
            db,
            our_team_id=our_id,
            resolved_team_id=resolved_id,
            opponent_name="Rival HS",
        )

        assert result["old_stub_team_id"] == stub_id

        # Old stub row should be updated to point to resolved team
        rows = db.execute(
            "SELECT opponent_team_id FROM team_opponents WHERE our_team_id = ?",
            (our_id,),
        ).fetchall()
        team_ids = [r[0] for r in rows]
        assert resolved_id in team_ids
        assert stub_id not in team_ids


# ---------------------------------------------------------------------------
# AC-10c: Resolution with no stub creates a new row
# ---------------------------------------------------------------------------


class TestNoStub:
    """AC-10c: Resolution with no stub creates a new row."""

    def test_new_row_created_when_no_stub(self, db: sqlite3.Connection) -> None:
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        resolved_id = _insert_team(db, "New Team", public_id="new-slug")
        db.commit()

        result = finalize_opponent_resolution(
            db,
            our_team_id=our_id,
            resolved_team_id=resolved_id,
            opponent_name="New Team",
        )

        assert result["old_stub_team_id"] is None

        row = db.execute(
            "SELECT opponent_team_id FROM team_opponents WHERE our_team_id = ?",
            (our_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == resolved_id


# ---------------------------------------------------------------------------
# AC-10d: UNIQUE constraint not violated when resolved team already has row
# ---------------------------------------------------------------------------


class TestUniqueConstraintHandling:
    """AC-10d: UNIQUE constraint not violated when resolved team already has team_opponents row."""

    def test_no_error_when_resolved_team_already_linked(self, db: sqlite3.Connection) -> None:
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        stub_id = _insert_team(db, "Rival HS", public_id=None)
        resolved_id = _insert_team(db, "Rival HS", public_id="rival-slug")
        _insert_team_opponents(db, our_id, stub_id)
        _insert_team_opponents(db, our_id, resolved_id)  # Already linked!
        db.commit()

        # Should not raise
        result = finalize_opponent_resolution(
            db,
            our_team_id=our_id,
            resolved_team_id=resolved_id,
            opponent_name="Rival HS",
        )

        assert result["old_stub_team_id"] == stub_id

        # Stub row should be deleted (resolved already has a row)
        stub_row = db.execute(
            "SELECT 1 FROM team_opponents WHERE our_team_id = ? AND opponent_team_id = ?",
            (our_id, stub_id),
        ).fetchone()
        assert stub_row is None

        # Resolved row still exists
        resolved_row = db.execute(
            "SELECT 1 FROM team_opponents WHERE our_team_id = ? AND opponent_team_id = ?",
            (our_id, resolved_id),
        ).fetchone()
        assert resolved_row is not None

    def test_idempotent_double_call(self, db: sqlite3.Connection) -> None:
        """Calling finalize twice should not fail."""
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        resolved_id = _insert_team(db, "Rival HS", public_id="rival-slug")
        db.commit()

        finalize_opponent_resolution(db, our_id, resolved_id, "Rival HS")
        # Second call -- should not raise
        result = finalize_opponent_resolution(db, our_id, resolved_id, "Rival HS")
        assert result["old_stub_team_id"] is None

        count = db.execute(
            "SELECT COUNT(*) FROM team_opponents WHERE our_team_id = ? AND opponent_team_id = ?",
            (our_id, resolved_id),
        ).fetchone()[0]
        assert count == 1


# ---------------------------------------------------------------------------
# AC-10e: FK references reassigned from stub to resolved team
# ---------------------------------------------------------------------------


class TestFKReassignment:
    """AC-10e: FK references reassigned from stub to resolved team."""

    def test_games_reassigned(self, db: sqlite3.Connection) -> None:
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        stub_id = _insert_team(db, "Rival HS", public_id=None)
        resolved_id = _insert_team(db, "Rival HS", public_id="rival-slug")
        _insert_team_opponents(db, our_id, stub_id)
        _insert_season(db)
        _insert_game(db, "game-001", home_team_id=our_id, away_team_id=stub_id)
        _insert_game(db, "game-002", home_team_id=stub_id, away_team_id=our_id)
        db.commit()

        finalize_opponent_resolution(db, our_id, resolved_id, "Rival HS")

        g1 = db.execute("SELECT away_team_id FROM games WHERE game_id = 'game-001'").fetchone()
        assert g1[0] == resolved_id
        g2 = db.execute("SELECT home_team_id FROM games WHERE game_id = 'game-002'").fetchone()
        assert g2[0] == resolved_id

    def test_player_game_batting_reassigned(self, db: sqlite3.Connection) -> None:
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        stub_id = _insert_team(db, "Rival HS", public_id=None)
        resolved_id = _insert_team(db, "Rival HS", public_id="rival-slug")
        _insert_team_opponents(db, our_id, stub_id)
        _insert_season(db)
        _insert_game(db, "game-001", home_team_id=our_id, away_team_id=stub_id)
        _insert_player(db, "p-001")
        _insert_player_game_batting(db, "game-001", "p-001", stub_id)
        db.commit()

        finalize_opponent_resolution(db, our_id, resolved_id, "Rival HS")

        row = db.execute(
            "SELECT team_id FROM player_game_batting WHERE game_id = 'game-001' AND player_id = 'p-001'"
        ).fetchone()
        assert row[0] == resolved_id

    def test_player_season_batting_reassigned(self, db: sqlite3.Connection) -> None:
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        stub_id = _insert_team(db, "Rival HS", public_id=None)
        resolved_id = _insert_team(db, "Rival HS", public_id="rival-slug")
        _insert_team_opponents(db, our_id, stub_id)
        _insert_season(db)
        _insert_player(db, "p-001")
        _insert_player_season_batting(db, "p-001", stub_id)
        db.commit()

        finalize_opponent_resolution(db, our_id, resolved_id, "Rival HS")

        row = db.execute(
            "SELECT team_id FROM player_season_batting WHERE player_id = 'p-001'"
        ).fetchone()
        assert row[0] == resolved_id

    def test_team_roster_reassigned(self, db: sqlite3.Connection) -> None:
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        stub_id = _insert_team(db, "Rival HS", public_id=None)
        resolved_id = _insert_team(db, "Rival HS", public_id="rival-slug")
        _insert_team_opponents(db, our_id, stub_id)
        _insert_season(db)
        _insert_player(db, "p-001")
        _insert_team_roster(db, stub_id, "p-001")
        db.commit()

        finalize_opponent_resolution(db, our_id, resolved_id, "Rival HS")

        row = db.execute(
            "SELECT team_id FROM team_rosters WHERE player_id = 'p-001'"
        ).fetchone()
        assert row[0] == resolved_id


# ---------------------------------------------------------------------------
# AC-10f: Dedup guard prevents duplicate rows when resolved team has matching data
# ---------------------------------------------------------------------------


class TestDedupGuard:
    """AC-10f: Dedup guard prevents duplicate rows when resolved team already has matching data."""

    def test_game_dedup_by_game_stream_id(self, db: sqlite3.Connection) -> None:
        """Same real-world game loaded under different game_ids: dedup by game_stream_id."""
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        stub_id = _insert_team(db, "Rival HS", public_id=None)
        resolved_id = _insert_team(db, "Rival HS", public_id="rival-slug")
        _insert_team_opponents(db, our_id, stub_id)
        _insert_season(db)
        # Same real-world game loaded twice with same game_stream_id but different game_ids
        _insert_game(db, "game-resolved", home_team_id=our_id, away_team_id=resolved_id,
                     game_stream_id="stream-001")
        _insert_game(db, "game-stub", home_team_id=our_id, away_team_id=stub_id,
                     game_stream_id="stream-001")
        # A different game only on the stub (should be reassigned)
        _insert_game(db, "game-unique", home_team_id=our_id, away_team_id=stub_id,
                     game_stream_id="stream-002")
        db.commit()

        finalize_opponent_resolution(db, our_id, resolved_id, "Rival HS")

        # game-resolved: unchanged (already points to resolved)
        g1 = db.execute("SELECT away_team_id FROM games WHERE game_id = 'game-resolved'").fetchone()
        assert g1[0] == resolved_id
        # game-stub: NOT reassigned (dedup by game_stream_id catches it)
        g2 = db.execute("SELECT away_team_id FROM games WHERE game_id = 'game-stub'").fetchone()
        assert g2[0] == stub_id  # stays on stub because resolved already has stream-001
        # game-unique: reassigned to resolved (different game_stream_id)
        g3 = db.execute("SELECT away_team_id FROM games WHERE game_id = 'game-unique'").fetchone()
        assert g3[0] == resolved_id

    def test_game_null_game_stream_id_always_reassigned(self, db: sqlite3.Connection) -> None:
        """Games with NULL game_stream_id are always reassigned (no dedup check)."""
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        stub_id = _insert_team(db, "Rival HS", public_id=None)
        resolved_id = _insert_team(db, "Rival HS", public_id="rival-slug")
        _insert_team_opponents(db, our_id, stub_id)
        _insert_season(db)
        _insert_game(db, "game-null-stream", home_team_id=our_id, away_team_id=stub_id,
                     game_stream_id=None)
        db.commit()

        finalize_opponent_resolution(db, our_id, resolved_id, "Rival HS")

        g = db.execute("SELECT away_team_id FROM games WHERE game_id = 'game-null-stream'").fetchone()
        assert g[0] == resolved_id

    def test_player_game_batting_reassigned(self, db: sqlite3.Connection) -> None:
        """player_game_batting rows for stub are reassigned to resolved team."""
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        stub_id = _insert_team(db, "Rival HS", public_id=None)
        resolved_id = _insert_team(db, "Rival HS", public_id="rival-slug")
        _insert_team_opponents(db, our_id, stub_id)
        _insert_season(db)
        _insert_game(db, "game-001", home_team_id=our_id, away_team_id=stub_id)
        _insert_player(db, "p-001")
        _insert_player_game_batting(db, "game-001", "p-001", stub_id)
        db.commit()

        finalize_opponent_resolution(db, our_id, resolved_id, "Rival HS")

        row = db.execute(
            "SELECT team_id FROM player_game_batting WHERE game_id = 'game-001' AND player_id = 'p-001'"
        ).fetchone()
        assert row[0] == resolved_id

    def test_player_season_batting_dedup(self, db: sqlite3.Connection) -> None:
        """Dedup guard skips player_season_batting where resolved team has same (player_id, season_id)."""
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        stub_id = _insert_team(db, "Rival HS", public_id=None)
        resolved_id = _insert_team(db, "Rival HS", public_id="rival-slug")
        _insert_team_opponents(db, our_id, stub_id)
        _insert_season(db)
        _insert_player(db, "p-001")

        _insert_player_season_batting(db, "p-001", stub_id)
        _insert_player_season_batting(db, "p-001", resolved_id)
        db.commit()

        # Should not raise
        finalize_opponent_resolution(db, our_id, resolved_id, "Rival HS")

        rows = db.execute(
            "SELECT team_id FROM player_season_batting WHERE player_id = 'p-001'"
        ).fetchall()
        team_ids = [r[0] for r in rows]
        assert resolved_id in team_ids


# ---------------------------------------------------------------------------
# AC-9 extended: pitching and spray chart FK reassignment
# ---------------------------------------------------------------------------


class TestPitchingAndSprayReassignment:
    """Additional FK reassignment tests for player_game_pitching, player_season_pitching, spray_charts."""

    def test_player_game_pitching_reassigned(self, db: sqlite3.Connection) -> None:
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        stub_id = _insert_team(db, "Rival HS", public_id=None)
        resolved_id = _insert_team(db, "Rival HS", public_id="rival-slug")
        _insert_team_opponents(db, our_id, stub_id)
        _insert_season(db)
        _insert_game(db, "game-001", home_team_id=our_id, away_team_id=stub_id)
        _insert_player(db, "p-001")
        db.execute(
            "INSERT INTO player_game_pitching (game_id, player_id, team_id) VALUES (?, ?, ?)",
            ("game-001", "p-001", stub_id),
        )
        db.commit()

        finalize_opponent_resolution(db, our_id, resolved_id, "Rival HS")

        row = db.execute(
            "SELECT team_id FROM player_game_pitching WHERE game_id = 'game-001' AND player_id = 'p-001'"
        ).fetchone()
        assert row[0] == resolved_id

    def test_player_season_pitching_reassigned(self, db: sqlite3.Connection) -> None:
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        stub_id = _insert_team(db, "Rival HS", public_id=None)
        resolved_id = _insert_team(db, "Rival HS", public_id="rival-slug")
        _insert_team_opponents(db, our_id, stub_id)
        _insert_season(db)
        _insert_player(db, "p-001")
        db.execute(
            "INSERT INTO player_season_pitching (player_id, team_id, season_id) VALUES (?, ?, ?)",
            ("p-001", stub_id, "2026-spring-hs"),
        )
        db.commit()

        finalize_opponent_resolution(db, our_id, resolved_id, "Rival HS")

        row = db.execute(
            "SELECT team_id FROM player_season_pitching WHERE player_id = 'p-001'"
        ).fetchone()
        assert row[0] == resolved_id

    def test_spray_charts_reassigned(self, db: sqlite3.Connection) -> None:
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        stub_id = _insert_team(db, "Rival HS", public_id=None)
        resolved_id = _insert_team(db, "Rival HS", public_id="rival-slug")
        _insert_team_opponents(db, our_id, stub_id)
        _insert_season(db)
        _insert_game(db, "game-001", home_team_id=our_id, away_team_id=stub_id)
        _insert_player(db, "p-001")
        db.execute(
            "INSERT INTO spray_charts (game_id, player_id, team_id, chart_type, x, y) "
            "VALUES (?, ?, ?, 'offensive', 0.5, 0.5)",
            ("game-001", "p-001", stub_id),
        )
        db.commit()

        finalize_opponent_resolution(db, our_id, resolved_id, "Rival HS")

        row = db.execute(
            "SELECT team_id FROM spray_charts WHERE game_id = 'game-001' AND player_id = 'p-001'"
        ).fetchone()
        assert row[0] == resolved_id

    def test_player_season_pitching_dedup(self, db: sqlite3.Connection) -> None:
        """Dedup guard: skip when resolved team already has matching (player_id, season_id)."""
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        stub_id = _insert_team(db, "Rival HS", public_id=None)
        resolved_id = _insert_team(db, "Rival HS", public_id="rival-slug")
        _insert_team_opponents(db, our_id, stub_id)
        _insert_season(db)
        _insert_player(db, "p-001")
        # Both stub and resolved have season pitching for same player+season
        db.execute(
            "INSERT INTO player_season_pitching (player_id, team_id, season_id) VALUES (?, ?, ?)",
            ("p-001", stub_id, "2026-spring-hs"),
        )
        db.execute(
            "INSERT INTO player_season_pitching (player_id, team_id, season_id) VALUES (?, ?, ?)",
            ("p-001", resolved_id, "2026-spring-hs"),
        )
        db.commit()

        # Should not raise UNIQUE constraint error
        finalize_opponent_resolution(db, our_id, resolved_id, "Rival HS")

        rows = db.execute(
            "SELECT team_id FROM player_season_pitching WHERE player_id = 'p-001'"
        ).fetchall()
        team_ids = [r[0] for r in rows]
        assert resolved_id in team_ids


# ---------------------------------------------------------------------------
# AC-7: Function does not commit (runs within caller's transaction)
# ---------------------------------------------------------------------------


class TestTransactionBehavior:
    """AC-7: Function runs within caller's transaction, does not commit."""

    def test_no_commit_by_function(self, db: sqlite3.Connection) -> None:
        """If we rollback after finalize, changes should be gone."""
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        resolved_id = _insert_team(db, "Rival HS", public_id="rival-slug", is_active=0)
        db.commit()

        finalize_opponent_resolution(db, our_id, resolved_id, "Rival HS")
        db.rollback()

        # team_opponents row should not exist after rollback
        row = db.execute(
            "SELECT 1 FROM team_opponents WHERE our_team_id = ? AND opponent_team_id = ?",
            (our_id, resolved_id),
        ).fetchone()
        assert row is None

        # is_active should still be 0 after rollback
        active = db.execute(
            "SELECT is_active FROM teams WHERE id = ?", (resolved_id,)
        ).fetchone()
        assert active[0] == 0


# ---------------------------------------------------------------------------
# AC-5: is_active always set to 1
# ---------------------------------------------------------------------------


class TestActivation:
    """AC-5: Resolved team is_active set to 1 regardless of prior state."""

    def test_already_active_stays_active(self, db: sqlite3.Connection) -> None:
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        resolved_id = _insert_team(db, "Rival HS", is_active=1, public_id="rival-slug")
        db.commit()

        finalize_opponent_resolution(db, our_id, resolved_id, "Rival HS")

        active = db.execute("SELECT is_active FROM teams WHERE id = ?", (resolved_id,)).fetchone()
        assert active[0] == 1

    def test_inactive_becomes_active(self, db: sqlite3.Connection) -> None:
        our_id = _insert_team(db, "LSB Varsity", membership_type="member")
        resolved_id = _insert_team(db, "Rival HS", is_active=0, public_id="rival-slug")
        db.commit()

        finalize_opponent_resolution(db, our_id, resolved_id, "Rival HS")

        active = db.execute("SELECT is_active FROM teams WHERE id = ?", (resolved_id,)).fetchone()
        assert active[0] == 1
