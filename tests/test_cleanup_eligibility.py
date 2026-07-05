# synthetic-test-data
"""Unit tests for is_team_eligible_for_cleanup (E-250-02, TN-5).

E-250 dropped the ``team_opponents`` registry and removed the two eligibility
guards that consulted it (old Guard 2: any ``team_opponents`` row referencing
the team; old Guard 4: shared games with a team that appears in
``team_opponents``). These tests PROVE the surviving two-guard set
(``is_active = 0`` and no OTHER report) behaves identically to before: no team
that was ineligible under a surviving guard becomes eligible, and the only
class that flips eligible is one whose sole gate was a (now-impossible)
``team_opponents`` row.
"""

from __future__ import annotations

import sqlite3

import pytest

from src.reports.generator import is_team_eligible_for_cleanup
from tests.conftest import load_real_schema


@pytest.fixture
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    load_real_schema(conn)
    yield conn
    conn.close()


def _insert_team(conn: sqlite3.Connection, *, is_active: int, name: str = "T") -> int:
    return conn.execute(
        "INSERT INTO teams (name, membership_type, is_active) VALUES (?, 'tracked', ?)",
        (name, is_active),
    ).lastrowid


def _insert_report(conn: sqlite3.Connection, team_id: int, *, slug: str) -> int:
    return conn.execute(
        "INSERT INTO reports (slug, team_id, title, expires_at) "
        "VALUES (?, ?, 'Report', '2099-01-01T00:00:00Z')",
        (slug, team_id),
    ).lastrowid


def test_team_opponents_table_is_gone(db: sqlite3.Connection) -> None:
    """Migration 008 dropped the registry the removed guards consulted."""
    tables = {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert "team_opponents" not in tables


def test_inactive_team_with_no_other_reports_is_eligible(db: sqlite3.Connection) -> None:
    """Both surviving guards pass -> eligible."""
    team_id = _insert_team(db, is_active=0)
    report_id = _insert_report(db, team_id, slug="only")
    assert is_team_eligible_for_cleanup(db, team_id, report_id) is True


def test_active_team_is_ineligible(db: sqlite3.Connection) -> None:
    """Guard 1 (is_active) preserved: an active team is never eligible."""
    team_id = _insert_team(db, is_active=1)
    report_id = _insert_report(db, team_id, slug="active")
    assert is_team_eligible_for_cleanup(db, team_id, report_id) is False


def test_nonexistent_team_is_ineligible(db: sqlite3.Connection) -> None:
    """A team_id with no row returns False (never raises)."""
    assert is_team_eligible_for_cleanup(db, 999999, 1) is False


def test_inactive_team_with_another_report_is_ineligible(db: sqlite3.Connection) -> None:
    """Guard 2 (no OTHER report) preserved: a surviving report gates cleanup."""
    team_id = _insert_team(db, is_active=0)
    deleting = _insert_report(db, team_id, slug="deleting")
    _insert_report(db, team_id, slug="survivor")
    assert is_team_eligible_for_cleanup(db, team_id, deleting) is False


def test_shared_games_alone_do_not_gate(db: sqlite3.Connection) -> None:
    """TN-5: with old Guard 4 removed, sharing a game with another team no
    longer gates cleanup. The team is inactive with no other report, so it is
    eligible regardless of the shared game -- the only thing that USED to gate
    it here was the other team appearing in ``team_opponents``, which no longer
    exists.
    """
    db.execute(
        "INSERT INTO seasons (season_id, name, year) VALUES ('2026', '2026', 2026)"
    )
    team_id = _insert_team(db, is_active=0, name="Under Test")
    other_id = _insert_team(db, is_active=1, name="Opponent")
    db.execute(
        "INSERT INTO games "
        "(game_id, season_id, game_date, home_team_id, away_team_id, status) "
        "VALUES ('g1', '2026', '2026-04-01', ?, ?, 'completed')",
        (team_id, other_id),
    )
    report_id = _insert_report(db, team_id, slug="shared")
    assert is_team_eligible_for_cleanup(db, team_id, report_id) is True
