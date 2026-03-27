"""Integration tests for E-167 dedup prevention across pipeline paths.

Verifies that running different pipeline INSERT paths (schedule_loader,
opponent_resolver, game_loader, scouting) for the same opponent through
different paths does not create duplicate rows.

Uses an in-memory SQLite database with the teams table schema.
"""

from __future__ import annotations

import sqlite3

import pytest

from src.db.teams import ensure_team_row


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory database with the teams table and relevant indexes."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("""
        CREATE TABLE teams (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            program_id      TEXT,
            membership_type TEXT NOT NULL CHECK(membership_type IN ('member', 'tracked')),
            classification  TEXT,
            public_id       TEXT,
            gc_uuid         TEXT,
            source          TEXT NOT NULL DEFAULT 'gamechanger',
            is_active       INTEGER NOT NULL DEFAULT 1,
            last_synced     TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            season_year     INTEGER
        )
    """)
    conn.execute(
        "CREATE UNIQUE INDEX idx_teams_gc_uuid ON teams(gc_uuid) WHERE gc_uuid IS NOT NULL"
    )
    conn.execute(
        "CREATE UNIQUE INDEX idx_teams_public_id ON teams(public_id) WHERE public_id IS NOT NULL"
    )
    conn.execute(
        "CREATE INDEX idx_teams_name_season_year ON teams(name COLLATE NOCASE, season_year)"
    )
    return conn


def _team_count(db: sqlite3.Connection) -> int:
    return db.execute("SELECT COUNT(*) FROM teams").fetchone()[0]


# ---------------------------------------------------------------------------
# AC-7(a): Stub created first, then resolver finds by name
# ---------------------------------------------------------------------------


def test_stub_then_resolver_no_duplicate(db: sqlite3.Connection) -> None:
    """Schedule loader creates a stub by name, then resolver finds it by name."""
    # Schedule loader path: name only, no gc_uuid or public_id
    stub_id = ensure_team_row(
        db, name="Rival HS", season_year=2026, source="schedule"
    )

    # Resolver path: has gc_uuid + public_id + name
    resolver_id = ensure_team_row(
        db,
        name="Rival HS",
        gc_uuid="uuid-rival",
        public_id="rival-slug",
        season_year=2026,
        source="resolver",
    )

    # Step 3 (name+season_year) should match the stub; no duplicate created
    assert resolver_id == stub_id
    assert _team_count(db) == 1


# ---------------------------------------------------------------------------
# AC-7(b): Resolver created first, then stub finds by name
# ---------------------------------------------------------------------------


def test_resolver_then_stub_no_duplicate(db: sqlite3.Connection) -> None:
    """Resolver creates a row with gc_uuid, then schedule loader finds it by name."""
    # Resolver path: has gc_uuid + name
    resolver_id = ensure_team_row(
        db,
        name="Rival HS",
        gc_uuid="uuid-rival",
        season_year=2026,
        source="resolver",
    )

    # Schedule loader path: name only
    stub_id = ensure_team_row(
        db, name="Rival HS", season_year=2026, source="schedule"
    )

    # Step 3 (name+season_year match on tracked row) finds the existing row
    assert stub_id == resolver_id
    assert _team_count(db) == 1


# ---------------------------------------------------------------------------
# AC-7(c): Two resolvers with different gc_uuids for the same public_id
# ---------------------------------------------------------------------------


def test_two_gc_uuids_same_public_id_no_duplicate(db: sqlite3.Connection) -> None:
    """Two resolver calls with different gc_uuids but same public_id collapse."""
    # First resolver call creates the row
    id1 = ensure_team_row(
        db,
        gc_uuid="uuid-alpha",
        public_id="shared-slug",
        name="Rival HS",
        season_year=2026,
        source="resolver",
    )

    # Second resolver call with different gc_uuid but same public_id
    id2 = ensure_team_row(
        db,
        gc_uuid="uuid-beta",
        public_id="shared-slug",
        name="Rival HS",
        season_year=2026,
        source="resolver",
    )

    # Step 2 (public_id match) finds the existing row
    assert id2 == id1
    assert _team_count(db) == 1

    # gc_uuid is NOT overwritten (existing is non-null)
    row = db.execute("SELECT gc_uuid FROM teams WHERE id = ?", (id1,)).fetchone()
    assert row[0] == "uuid-alpha"


# ---------------------------------------------------------------------------
# Additional cross-path scenarios
# ---------------------------------------------------------------------------


def test_game_loader_then_resolver_backfills(db: sqlite3.Connection) -> None:
    """Game loader creates with gc_uuid (UUID-as-name), resolver enriches."""
    # Game loader: gc_uuid only, no real name
    game_id = ensure_team_row(db, gc_uuid="uuid-rival", source="game_loader")

    # Verify UUID-as-name stub
    row = db.execute("SELECT name FROM teams WHERE id = ?", (game_id,)).fetchone()
    assert row[0] == "uuid-rival"

    # Resolver: same gc_uuid + real name + public_id
    resolver_id = ensure_team_row(
        db,
        gc_uuid="uuid-rival",
        name="Rival HS",
        public_id="rival-slug",
        season_year=2026,
        source="resolver",
    )

    assert resolver_id == game_id
    assert _team_count(db) == 1

    # Name back-filled (UUID stub replaced)
    row = db.execute(
        "SELECT name, public_id, season_year FROM teams WHERE id = ?", (game_id,)
    ).fetchone()
    assert row[0] == "Rival HS"
    assert row[1] == "rival-slug"
    assert row[2] == 2026


def test_scouting_then_resolver_no_duplicate(db: sqlite3.Connection) -> None:
    """Scouting creates with public_id, resolver finds by public_id."""
    # Scouting path: public_id only (creates row with name defaulting to "Unknown")
    scout_id = ensure_team_row(db, public_id="rival-slug", source="scouting")

    # Resolver path: has gc_uuid + public_id + name
    resolver_id = ensure_team_row(
        db,
        gc_uuid="uuid-rival",
        public_id="rival-slug",
        name="Rival HS",
        season_year=2026,
        source="resolver",
    )

    # Step 2 (public_id match) finds the scouting row
    assert resolver_id == scout_id
    assert _team_count(db) == 1

    # gc_uuid and season_year back-filled; name stays "Unknown" because the
    # UUID-as-name stub check requires existing_name == gc_uuid
    row = db.execute(
        "SELECT name, gc_uuid, season_year FROM teams WHERE id = ?", (scout_id,)
    ).fetchone()
    assert row[1] == "uuid-rival"  # gc_uuid back-filled
    assert row[2] == 2026  # season_year back-filled


def test_multiple_identifier_paths_converge(db: sqlite3.Connection) -> None:
    """Pipeline paths that share identifiers converge to the same row."""
    # Path 1: Game loader creates with gc_uuid (UUID-as-name stub)
    id1 = ensure_team_row(
        db, gc_uuid="uuid-rival", name="Rival HS", source="game_loader"
    )

    # Path 2: Resolver enriches via gc_uuid match (step 1)
    id2 = ensure_team_row(
        db,
        gc_uuid="uuid-rival",
        public_id="rival-slug",
        name="Rival HS",
        season_year=2026,
        source="resolver",
    )

    # Path 3: Scouting finds via public_id match (step 2)
    id3 = ensure_team_row(db, public_id="rival-slug", source="scouting")

    # Path 4: Schedule finds via name+season_year match (step 3)
    id4 = ensure_team_row(
        db, name="Rival HS", season_year=2026, source="schedule"
    )

    # All paths converge to the same team
    assert id1 == id2 == id3 == id4
    assert _team_count(db) == 1
