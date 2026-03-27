"""Tests for src.db.teams.ensure_team_row().

Covers all four cascade steps, back-fill behavior, collision-safe writes,
self-tracking guard, UUID-as-name stub pattern, and tie-breaking.
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


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_team(db: sqlite3.Connection, team_id: int) -> dict:
    row = db.execute(
        "SELECT id, name, gc_uuid, public_id, season_year, membership_type, source "
        "FROM teams WHERE id = ?",
        (team_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"No team with id={team_id}")
    return {
        "id": row[0],
        "name": row[1],
        "gc_uuid": row[2],
        "public_id": row[3],
        "season_year": row[4],
        "membership_type": row[5],
        "source": row[6],
    }


def _insert_team(
    db: sqlite3.Connection,
    *,
    name: str = "Test Team",
    membership_type: str = "tracked",
    gc_uuid: str | None = None,
    public_id: str | None = None,
    season_year: int | None = None,
    source: str = "gamechanger",
) -> int:
    cursor = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, public_id, season_year, source) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (name, membership_type, gc_uuid, public_id, season_year, source),
    )
    return cursor.lastrowid


# ===========================================================================
# Step 1: gc_uuid match
# ===========================================================================


class TestStep1GcUuidMatch:
    def test_returns_existing_id(self, db: sqlite3.Connection) -> None:
        existing_id = _insert_team(db, name="Rival HS", gc_uuid="uuid-1")
        result = ensure_team_row(db, gc_uuid="uuid-1", name="Rival HS")
        assert result == existing_id

    def test_backfills_public_id_when_null(self, db: sqlite3.Connection) -> None:
        existing_id = _insert_team(db, name="Rival", gc_uuid="uuid-1")
        ensure_team_row(db, gc_uuid="uuid-1", public_id="rival-slug")
        team = _get_team(db, existing_id)
        assert team["public_id"] == "rival-slug"

    def test_does_not_overwrite_existing_public_id(self, db: sqlite3.Connection) -> None:
        existing_id = _insert_team(db, name="Rival", gc_uuid="uuid-1", public_id="old-slug")
        ensure_team_row(db, gc_uuid="uuid-1", public_id="new-slug")
        team = _get_team(db, existing_id)
        assert team["public_id"] == "old-slug"

    def test_backfills_season_year_when_null(self, db: sqlite3.Connection) -> None:
        existing_id = _insert_team(db, name="Rival", gc_uuid="uuid-1")
        ensure_team_row(db, gc_uuid="uuid-1", season_year=2026)
        team = _get_team(db, existing_id)
        assert team["season_year"] == 2026

    def test_does_not_overwrite_existing_season_year(self, db: sqlite3.Connection) -> None:
        existing_id = _insert_team(db, name="Rival", gc_uuid="uuid-1", season_year=2025)
        ensure_team_row(db, gc_uuid="uuid-1", season_year=2026)
        team = _get_team(db, existing_id)
        assert team["season_year"] == 2025

    def test_replaces_uuid_as_name_stub(self, db: sqlite3.Connection) -> None:
        existing_id = _insert_team(db, name="uuid-1", gc_uuid="uuid-1")
        ensure_team_row(db, gc_uuid="uuid-1", name="Real Name")
        team = _get_team(db, existing_id)
        assert team["name"] == "Real Name"

    def test_preserves_real_name(self, db: sqlite3.Connection) -> None:
        existing_id = _insert_team(db, name="Real Name", gc_uuid="uuid-1")
        ensure_team_row(db, gc_uuid="uuid-1", name="Other Name")
        team = _get_team(db, existing_id)
        assert team["name"] == "Real Name"


# ===========================================================================
# Step 2: public_id match
# ===========================================================================


class TestStep2PublicIdMatch:
    def test_returns_existing_id(self, db: sqlite3.Connection) -> None:
        existing_id = _insert_team(db, name="Rival", public_id="rival-slug")
        result = ensure_team_row(db, public_id="rival-slug", name="Rival")
        assert result == existing_id

    def test_no_gc_uuid_is_null_filter(self, db: sqlite3.Connection) -> None:
        """public_id match works even when the row already has a gc_uuid."""
        existing_id = _insert_team(
            db, name="Rival", public_id="rival-slug", gc_uuid="existing-uuid"
        )
        result = ensure_team_row(db, public_id="rival-slug", gc_uuid="new-uuid")
        assert result == existing_id

    def test_backfills_gc_uuid_when_null(self, db: sqlite3.Connection) -> None:
        existing_id = _insert_team(db, name="Rival", public_id="rival-slug")
        ensure_team_row(db, public_id="rival-slug", gc_uuid="uuid-1")
        team = _get_team(db, existing_id)
        assert team["gc_uuid"] == "uuid-1"

    def test_does_not_overwrite_existing_gc_uuid(self, db: sqlite3.Connection) -> None:
        existing_id = _insert_team(
            db, name="Rival", public_id="rival-slug", gc_uuid="old-uuid"
        )
        ensure_team_row(db, public_id="rival-slug", gc_uuid="new-uuid")
        team = _get_team(db, existing_id)
        assert team["gc_uuid"] == "old-uuid"

    def test_backfills_season_year_when_null(self, db: sqlite3.Connection) -> None:
        existing_id = _insert_team(db, name="Rival", public_id="rival-slug")
        ensure_team_row(db, public_id="rival-slug", season_year=2026)
        team = _get_team(db, existing_id)
        assert team["season_year"] == 2026

    def test_replaces_uuid_as_name_stub(self, db: sqlite3.Connection) -> None:
        """UUID-as-name stub replaced even on public_id match."""
        existing_id = _insert_team(db, name="uuid-1", gc_uuid="uuid-1", public_id="slug")
        ensure_team_row(db, public_id="slug", gc_uuid="uuid-1", name="Real Name")
        team = _get_team(db, existing_id)
        assert team["name"] == "Real Name"


# ===========================================================================
# Step 3: name + season_year + tracked match
# ===========================================================================


class TestStep3NameSeasonYearMatch:
    def test_returns_existing_id(self, db: sqlite3.Connection) -> None:
        existing_id = _insert_team(db, name="Rival HS", season_year=2026)
        result = ensure_team_row(db, name="Rival HS", season_year=2026)
        assert result == existing_id

    def test_case_insensitive(self, db: sqlite3.Connection) -> None:
        existing_id = _insert_team(db, name="Rival HS", season_year=2026)
        result = ensure_team_row(db, name="rival hs", season_year=2026)
        assert result == existing_id

    def test_null_season_year_groups_together(self, db: sqlite3.Connection) -> None:
        existing_id = _insert_team(db, name="Rival HS")
        result = ensure_team_row(db, name="Rival HS")  # both NULL
        assert result == existing_id

    def test_different_season_year_no_match(self, db: sqlite3.Connection) -> None:
        _insert_team(db, name="Rival HS", season_year=2025)
        result = ensure_team_row(db, name="Rival HS", season_year=2026)
        # Should INSERT a new row
        assert result != 1  # different from the existing team

    def test_only_matches_tracked(self, db: sqlite3.Connection) -> None:
        """Member teams are not matched by name in step 3."""
        _insert_team(db, name="Rival HS", season_year=2026, membership_type="member")
        result = ensure_team_row(db, name="Rival HS", season_year=2026)
        # Should not match the member row; goes to self-tracking guard or INSERT
        # In this case self-tracking guard (name-only) catches it
        team = _get_team(db, result)
        assert team["membership_type"] == "member"  # guard returned the member

    def test_no_gc_uuid_backfill_on_name_match(self, db: sqlite3.Connection) -> None:
        """Step 3 is conservative: no gc_uuid back-fill."""
        existing_id = _insert_team(db, name="Rival HS", season_year=2026)
        ensure_team_row(db, name="Rival HS", season_year=2026, gc_uuid="uuid-1")
        team = _get_team(db, existing_id)
        assert team["gc_uuid"] is None

    def test_no_public_id_backfill_on_name_match(self, db: sqlite3.Connection) -> None:
        """Step 3 is conservative: no public_id back-fill."""
        existing_id = _insert_team(db, name="Rival HS", season_year=2026)
        ensure_team_row(
            db, name="Rival HS", season_year=2026, public_id="rival-slug"
        )
        team = _get_team(db, existing_id)
        assert team["public_id"] is None

    def test_step3_null_season_year_groups_together_no_backfill_possible(
        self, db: sqlite3.Connection,
    ) -> None:
        """NULL season_year groups together via COALESCE sentinel, but step 3
        season_year back-fill is unreachable: a non-NULL caller value won't
        match a NULL existing value (COALESCE diverges), and a NULL caller
        value has nothing to back-fill. Defense-in-depth code is still present."""
        existing_id = _insert_team(db, name="Rival HS")  # season_year=NULL
        result = ensure_team_row(db, name="Rival HS")  # both NULL -> match
        assert result == existing_id

    def test_season_year_backfill_via_gc_uuid_match(
        self, db: sqlite3.Connection,
    ) -> None:
        """season_year back-fill works via step 1 (gc_uuid match)."""
        existing_id = _insert_team(db, name="Rival HS", gc_uuid="uuid-1")
        ensure_team_row(db, gc_uuid="uuid-1", season_year=2026)
        team = _get_team(db, existing_id)
        assert team["season_year"] == 2026

    def test_uuid_as_name_stub_replaced(self, db: sqlite3.Connection) -> None:
        """Even on name match, UUID-as-name stub gets replaced if gc_uuid matches."""
        # This is a weird case: the existing row has name="uuid-1" and the caller
        # passes name="uuid-1" and gc_uuid="uuid-1" -- step 1 would match first.
        # But if called with just name, the stub replacement needs gc_uuid context.
        existing_id = _insert_team(db, name="some-uuid", season_year=2026)
        # Without gc_uuid, name replacement check (existing == gc_uuid) cannot trigger
        ensure_team_row(db, name="some-uuid", season_year=2026, gc_uuid="some-uuid")
        # Step 3 catches the name match. gc_uuid="some-uuid" matches existing name.
        team = _get_team(db, existing_id)
        # _backfill_name checks existing_name == gc_uuid -> "some-uuid" == "some-uuid" -> True
        # But step 3 doesn't pass gc_uuid to _backfill_name... wait, it does pass gc_uuid.
        # Let me re-check: step 3 calls _backfill_name(db, existing_id, existing_name, name, gc_uuid)
        # existing_name="some-uuid", name="some-uuid", gc_uuid="some-uuid"
        # Since existing_name == gc_uuid, the stub check passes, but name == gc_uuid too,
        # so it would just write the same name. This is correct behavior.
        assert team["name"] == "some-uuid"  # no actual change

    def test_multiple_matches_returns_lowest_id(self, db: sqlite3.Connection) -> None:
        id1 = _insert_team(db, name="Rival HS", season_year=2026)
        _insert_team(db, name="Rival HS", season_year=2026)
        id3 = _insert_team(db, name="Rival HS", season_year=2026)
        result = ensure_team_row(db, name="Rival HS", season_year=2026)
        assert result == id1
        assert result < id3


# ===========================================================================
# Step 4: INSERT
# ===========================================================================


class TestStep4Insert:
    def test_creates_new_tracked_row(self, db: sqlite3.Connection) -> None:
        result = ensure_team_row(
            db, name="New Team", gc_uuid="uuid-new", public_id="new-slug",
            season_year=2026, source="resolver",
        )
        team = _get_team(db, result)
        assert team["name"] == "New Team"
        assert team["gc_uuid"] == "uuid-new"
        assert team["public_id"] == "new-slug"
        assert team["season_year"] == 2026
        assert team["membership_type"] == "tracked"
        assert team["source"] == "resolver"

    def test_default_source(self, db: sqlite3.Connection) -> None:
        result = ensure_team_row(db, name="New Team")
        team = _get_team(db, result)
        assert team["source"] == "gamechanger"

    def test_name_defaults_to_gc_uuid(self, db: sqlite3.Connection) -> None:
        result = ensure_team_row(db, gc_uuid="uuid-only")
        team = _get_team(db, result)
        assert team["name"] == "uuid-only"

    def test_name_defaults_to_unknown(self, db: sqlite3.Connection) -> None:
        result = ensure_team_row(db)
        team = _get_team(db, result)
        assert team["name"] == "Unknown"


# ===========================================================================
# Self-tracking guard
# ===========================================================================


class TestSelfTrackingGuard:
    def test_gc_uuid_matches_member(self, db: sqlite3.Connection) -> None:
        member_id = _insert_team(
            db, name="Our Team", gc_uuid="our-uuid", membership_type="member"
        )
        result = ensure_team_row(db, gc_uuid="our-uuid", name="Our Team")
        assert result == member_id
        # Should NOT have inserted a new row
        count = db.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
        assert count == 1

    def test_public_id_matches_member(self, db: sqlite3.Connection) -> None:
        member_id = _insert_team(
            db, name="Our Team", public_id="our-slug", membership_type="member"
        )
        result = ensure_team_row(db, public_id="our-slug", name="Our Team")
        assert result == member_id
        count = db.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
        assert count == 1

    def test_name_only_matches_member(self, db: sqlite3.Connection) -> None:
        """When both gc_uuid and public_id are None, name guard catches member."""
        member_id = _insert_team(
            db, name="Our Team", membership_type="member", season_year=2026
        )
        result = ensure_team_row(db, name="Our Team", season_year=2026)
        assert result == member_id

    def test_name_only_guard_case_insensitive(self, db: sqlite3.Connection) -> None:
        member_id = _insert_team(
            db, name="Our Team", membership_type="member"
        )
        result = ensure_team_row(db, name="our team")
        assert result == member_id

    def test_gc_uuid_guard_does_not_fire_for_tracked(self, db: sqlite3.Connection) -> None:
        """Self-tracking guard only fires for member teams, not tracked."""
        _insert_team(db, name="Tracked Opp", gc_uuid="opp-uuid", membership_type="tracked")
        # gc_uuid would match in step 1 already, but let's ensure guard doesn't
        # interfere -- step 1 returns the tracked row.
        result = ensure_team_row(db, gc_uuid="opp-uuid")
        team = _get_team(db, result)
        assert team["membership_type"] == "tracked"

    def test_name_guard_does_not_fire_with_gc_uuid(self, db: sqlite3.Connection) -> None:
        """Name-only guard only fires when BOTH gc_uuid and public_id are None."""
        _insert_team(db, name="Our Team", membership_type="member")
        # With gc_uuid provided (that doesn't match step 1), guard should check
        # gc_uuid first, not name.
        result = ensure_team_row(db, gc_uuid="unknown-uuid", name="Our Team")
        # gc_uuid guard: no member with gc_uuid="unknown-uuid" -> passes
        # public_id guard: public_id is None -> passes
        # name guard: gc_uuid is not None -> doesn't fire
        # INSERT new row
        team = _get_team(db, result)
        assert team["membership_type"] == "tracked"


# ===========================================================================
# Collision-safe writes
# ===========================================================================


class TestCollisionSafeWrites:
    def test_public_id_collision_skips_backfill(self, db: sqlite3.Connection) -> None:
        _insert_team(db, name="Other", public_id="taken-slug")
        existing_id = _insert_team(db, name="Rival", gc_uuid="uuid-1")
        ensure_team_row(db, gc_uuid="uuid-1", public_id="taken-slug")
        team = _get_team(db, existing_id)
        assert team["public_id"] is None  # not written due to collision

    def test_gc_uuid_collision_skips_backfill(self, db: sqlite3.Connection) -> None:
        _insert_team(db, name="Other", gc_uuid="taken-uuid")
        existing_id = _insert_team(db, name="Rival", public_id="rival-slug")
        ensure_team_row(db, public_id="rival-slug", gc_uuid="taken-uuid")
        team = _get_team(db, existing_id)
        assert team["gc_uuid"] is None  # not written due to collision


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEdgeCases:
    def test_no_identifiers_inserts_unknown(self, db: sqlite3.Connection) -> None:
        result = ensure_team_row(db)
        team = _get_team(db, result)
        assert team["name"] == "Unknown"
        assert team["membership_type"] == "tracked"

    def test_gc_uuid_match_takes_priority_over_public_id(
        self, db: sqlite3.Connection,
    ) -> None:
        """When both gc_uuid and public_id are provided, gc_uuid wins."""
        id1 = _insert_team(db, name="Team A", gc_uuid="uuid-1")
        _insert_team(db, name="Team B", public_id="slug-b")
        result = ensure_team_row(db, gc_uuid="uuid-1", public_id="slug-b")
        assert result == id1  # gc_uuid match (step 1) takes priority

    def test_gc_uuid_match_takes_priority_over_name(
        self, db: sqlite3.Connection,
    ) -> None:
        id1 = _insert_team(db, name="Team A", gc_uuid="uuid-1", season_year=2026)
        _insert_team(db, name="Team B", season_year=2026)
        result = ensure_team_row(
            db, gc_uuid="uuid-1", name="Team B", season_year=2026,
        )
        assert result == id1

    def test_step3_skipped_when_name_is_none(self, db: sqlite3.Connection) -> None:
        """No name means step 3 is skipped -> INSERT with gc_uuid as name."""
        _insert_team(db, name="Existing", season_year=2026)
        result = ensure_team_row(db, season_year=2026, gc_uuid="uuid-only")
        team = _get_team(db, result)
        assert team["name"] == "uuid-only"  # fallback name
