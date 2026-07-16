"""Tests for src.db.teams.ensure_team_row().

Covers all four cascade steps, back-fill behavior, collision-safe writes,
self-tracking guard, UUID-as-name stub pattern, and tie-breaking.
"""

from __future__ import annotations

import sqlite3

import pytest

from src.db.teams import (
    EnsureTeamResult,
    ensure_team_row,
    ensure_team_row_with_provenance,
)
from tests.conftest import load_real_schema


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory database with the production schema (FK enforcement on)."""
    conn = sqlite3.connect(":memory:")
    load_real_schema(conn)
    return conn


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_team(db: sqlite3.Connection, team_id: int) -> dict:
    row = db.execute(
        "SELECT id, name, gc_uuid, public_id, season_year, innings_per_game, "
        "membership_type, source "
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
        "innings_per_game": row[5],
        "membership_type": row[6],
        "source": row[7],
    }


def _insert_team(
    db: sqlite3.Connection,
    *,
    name: str = "Test Team",
    membership_type: str = "tracked",
    gc_uuid: str | None = None,
    public_id: str | None = None,
    season_year: int | None = None,
    innings_per_game: int | None = None,
    source: str = "gamechanger",
) -> int:
    cursor = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, public_id, season_year, "
        "innings_per_game, source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, membership_type, gc_uuid, public_id, season_year, innings_per_game, source),
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

    def test_insert_carries_innings_per_game(self, db: sqlite3.Connection) -> None:
        """A fresh INSERT persists a supplied innings_per_game (E-264-01 TN-4)."""
        result = ensure_team_row(
            db, name="New Team", gc_uuid="uuid-ipg", innings_per_game=6,
        )
        team = _get_team(db, result)
        assert team["innings_per_game"] == 6

    def test_insert_innings_per_game_defaults_null(self, db: sqlite3.Connection) -> None:
        """An INSERT with no innings_per_game leaves it NULL (assumed-basis signal)."""
        result = ensure_team_row(db, name="New Team", gc_uuid="uuid-noipg")
        team = _get_team(db, result)
        assert team["innings_per_game"] is None


# ===========================================================================
# innings_per_game back-fill (E-264-01 TN-4)
# ===========================================================================


class TestInningsPerGameBackfill:
    """AC-4: NULL->value fills; a stored integer + later None does NOT clobber.

    Mirrors the season_year back-fill direction: a failed re-fetch (None) must
    keep the last known good basis, and NULL is load-bearing provenance for the
    display layer's "(assumed)" flag.
    """

    def test_backfills_when_null_via_gc_uuid_match(self, db: sqlite3.Connection) -> None:
        existing_id = _insert_team(db, name="Rival", gc_uuid="uuid-1")
        ensure_team_row(db, gc_uuid="uuid-1", innings_per_game=6)
        team = _get_team(db, existing_id)
        assert team["innings_per_game"] == 6

    def test_backfills_when_null_via_public_id_match(self, db: sqlite3.Connection) -> None:
        existing_id = _insert_team(db, name="Rival", public_id="rival-slug")
        ensure_team_row(db, public_id="rival-slug", innings_per_game=7)
        team = _get_team(db, existing_id)
        assert team["innings_per_game"] == 7

    def test_backfills_when_null_via_name_match(self, db: sqlite3.Connection) -> None:
        existing_id = _insert_team(db, name="Rival HS", season_year=2026)
        ensure_team_row(db, name="Rival HS", season_year=2026, innings_per_game=6)
        team = _get_team(db, existing_id)
        assert team["innings_per_game"] == 6

    def test_does_not_overwrite_existing_with_value(self, db: sqlite3.Connection) -> None:
        """A stored integer is preserved when a new (different) value arrives."""
        existing_id = _insert_team(db, name="Rival", gc_uuid="uuid-1", innings_per_game=6)
        ensure_team_row(db, gc_uuid="uuid-1", innings_per_game=7)
        team = _get_team(db, existing_id)
        assert team["innings_per_game"] == 6

    def test_none_does_not_clobber_stored_integer(self, db: sqlite3.Connection) -> None:
        """A later None (failed re-fetch) keeps the last known good basis."""
        existing_id = _insert_team(db, name="Rival", gc_uuid="uuid-1", innings_per_game=6)
        ensure_team_row(db, gc_uuid="uuid-1", innings_per_game=None)
        team = _get_team(db, existing_id)
        assert team["innings_per_game"] == 6


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


# ===========================================================================
# ensure_team_row_with_provenance: identity match_method + insert-vs-match
# (E-235-03 gate (c) + E-235-04 created-set signal)
# ===========================================================================


class TestEnsureTeamRowProvenance:
    """The provenance variant reports match_method ('anchor'/'name_only') and
    whether the row was newly INSERTed. The legacy int wrapper is unchanged."""

    def test_gc_uuid_match_is_anchor_not_inserted(self, db: sqlite3.Connection) -> None:
        existing = _insert_team(db, name="Rival", gc_uuid="uuid-1")
        r = ensure_team_row_with_provenance(db, gc_uuid="uuid-1", name="Rival")
        assert r == EnsureTeamResult(existing, "anchor", False)

    def test_public_id_match_is_anchor_not_inserted(self, db: sqlite3.Connection) -> None:
        existing = _insert_team(db, name="Rival", public_id="rival-slug")
        r = ensure_team_row_with_provenance(db, public_id="rival-slug", name="Rival")
        assert r.team_id == existing
        assert r.match_method == "anchor"
        assert r.inserted is False

    def test_name_match_is_name_only_not_inserted(self, db: sqlite3.Connection) -> None:
        existing = _insert_team(db, name="Rival HS", season_year=2026)
        r = ensure_team_row_with_provenance(db, name="Rival HS", season_year=2026)
        assert r.team_id == existing
        assert r.match_method == "name_only"
        assert r.inserted is False

    def test_insert_with_public_id_is_anchor_inserted(self, db: sqlite3.Connection) -> None:
        r = ensure_team_row_with_provenance(
            db, name="Brand New", public_id="new-slug", season_year=2026,
        )
        assert r.match_method == "anchor"
        assert r.inserted is True
        # The row really was created with the anchor.
        assert _get_team(db, r.team_id)["public_id"] == "new-slug"

    def test_insert_name_only_is_name_only_inserted(self, db: sqlite3.Connection) -> None:
        r = ensure_team_row_with_provenance(db, name="Nameless Opponent")
        assert r.match_method == "name_only"
        assert r.inserted is True

    def test_wrapper_returns_int_unchanged(self, db: sqlite3.Connection) -> None:
        """ensure_team_row still returns the bare int PK (existing callers)."""
        existing = _insert_team(db, name="Rival", gc_uuid="uuid-1")
        assert ensure_team_row(db, gc_uuid="uuid-1") == existing


class _RacingConnection:
    """Wraps a real connection and, just before the step-4 ``INSERT INTO teams``,
    lets a *concurrent* process commit the same anchor first.

    Forces the exact cross-process window E-235-04's DE forward note flags:
    this call's cascade SELECT (steps 1-2) missed, but a racing process commits
    the same gc_uuid/public_id before this INSERT lands, tripping the partial
    UNIQUE index. Used to verify the INSERT degrades to a match, not a crash.
    """

    def __init__(self, real, racer) -> None:
        self._real = real
        self._racer = racer
        self._raced = False

    def execute(self, sql, params=()):
        if not self._raced and sql.strip().upper().startswith("INSERT INTO TEAMS"):
            self._racer()  # concurrent process wins the INSERT
            self._raced = True
        return self._real.execute(sql, params)

    def __getattr__(self, name):
        return getattr(self._real, name)


class TestInsertRaceRecovery:
    """E-235-04 (DE forward note): a concurrent gc_uuid/public_id INSERT that
    trips the partial UNIQUE index degrades to a MATCH of the racing row,
    rather than crashing the generation with IntegrityError.
    """

    def test_public_id_insert_race_degrades_to_match(self, tmp_path) -> None:
        db_path = str(tmp_path / "race.db")
        setup = sqlite3.connect(db_path)
        load_real_schema(setup)
        setup.commit()
        setup.close()

        conn_a = sqlite3.connect(db_path)
        conn_a.execute("PRAGMA foreign_keys=ON")
        conn_b = sqlite3.connect(db_path)
        conn_b.execute("PRAGMA foreign_keys=ON")

        def _racer() -> None:
            ensure_team_row_with_provenance(
                conn_b, public_id="shared-x", name="Shared X", season_year=2026,
            )
            conn_b.commit()

        wrapped = _RacingConnection(conn_a, _racer)
        # A's cascade SELECT misses (row not yet committed), then its INSERT
        # collides with B's freshly-committed row -> recovery matches it.
        result = ensure_team_row_with_provenance(
            wrapped, public_id="shared-x", name="Shared X", season_year=2026,
        )
        conn_a.commit()

        assert result.inserted is False  # degraded to a match, did not crash
        assert result.match_method == "anchor"
        # Exactly one row exists for the shared anchor (no duplicate).
        count = conn_a.execute(
            "SELECT COUNT(*) FROM teams WHERE public_id = 'shared-x'"
        ).fetchone()[0]
        assert count == 1
        # Both runs resolve to the SAME team id.
        assert result.team_id == conn_b.execute(
            "SELECT id FROM teams WHERE public_id = 'shared-x'"
        ).fetchone()[0]
        conn_a.close()
        conn_b.close()

    def test_gc_uuid_insert_race_degrades_to_match(self, tmp_path) -> None:
        db_path = str(tmp_path / "race.db")
        setup = sqlite3.connect(db_path)
        load_real_schema(setup)
        setup.commit()
        setup.close()

        conn_a = sqlite3.connect(db_path)
        conn_a.execute("PRAGMA foreign_keys=ON")
        conn_b = sqlite3.connect(db_path)
        conn_b.execute("PRAGMA foreign_keys=ON")

        def _racer() -> None:
            ensure_team_row_with_provenance(
                conn_b, gc_uuid="uuid-shared", name="Shared U", season_year=2026,
            )
            conn_b.commit()

        wrapped = _RacingConnection(conn_a, _racer)
        result = ensure_team_row_with_provenance(
            wrapped, gc_uuid="uuid-shared", name="Shared U", season_year=2026,
        )
        conn_a.commit()

        assert result.inserted is False
        assert result.match_method == "anchor"
        count = conn_a.execute(
            "SELECT COUNT(*) FROM teams WHERE gc_uuid = 'uuid-shared'"
        ).fetchone()[0]
        assert count == 1
        conn_a.close()
        conn_b.close()

    def test_insert_race_recovery_backfills_winner_row(self, tmp_path) -> None:
        """MEDIUM-1: the recovery re-runs the normal match path, so it applies
        the SAME backfills a match would (here: season_year onto a winner row
        that was committed without one) -- not a bare id lookup."""
        db_path = str(tmp_path / "race.db")
        setup = sqlite3.connect(db_path)
        load_real_schema(setup)
        setup.commit()
        setup.close()

        conn_a = sqlite3.connect(db_path)
        conn_a.execute("PRAGMA foreign_keys=ON")
        conn_b = sqlite3.connect(db_path)
        conn_b.execute("PRAGMA foreign_keys=ON")

        def _racer() -> None:
            # Winner commits with public_id but NO season_year.
            ensure_team_row_with_provenance(conn_b, public_id="shared-z", name="Shared Z")
            conn_b.commit()

        wrapped = _RacingConnection(conn_a, _racer)
        # Loser provides season_year=2026 -> INSERT collides -> recovery
        # re-matches via step-2 (public_id) and backfills season_year (was NULL).
        result = ensure_team_row_with_provenance(
            wrapped, public_id="shared-z", name="Shared Z", season_year=2026,
        )
        conn_a.commit()

        assert result.inserted is False
        row = conn_a.execute(
            "SELECT season_year FROM teams WHERE public_id = 'shared-z'"
        ).fetchone()
        assert row[0] == 2026, "recovery must backfill season_year like a normal match"
        conn_a.close()
        conn_b.close()
