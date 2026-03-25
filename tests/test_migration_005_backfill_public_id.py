# synthetic-test-data
"""Tests for 005_backfill_teams_public_id.sql (E-154-03).

Verifies the idempotent backfill migration that copies public_id from
opponent_links to teams for resolved opponents where teams.public_id IS NULL.

Strategy: Each test seeds data into a DB that has schema 001-004 applied
(but NOT 005), then applies migration 005, then asserts.  This ensures the
UPDATE runs against real pre-existing data, matching the production scenario
the migration was written to heal.

Tests use a temporary SQLite database; no Docker required.

Run with:
    pytest tests/test_migration_005_backfill_public_id.py -v
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from migrations.apply_migrations import (  # noqa: E402
    _CREATE_MIGRATIONS_TABLE,
    apply_migration,
)

_MIGRATIONS_DIR = _PROJECT_ROOT / "migrations"
_MIGRATION_005 = _MIGRATIONS_DIR / "005_backfill_teams_public_id.sql"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def pre_backfill_db(tmp_path: Path) -> sqlite3.Connection:
    """Apply migrations 001-004 to a fresh temp DB.

    Returns an open connection ready for test data to be inserted before
    migration 005 is applied.  Foreign keys are enabled.
    """
    db_path = tmp_path / "test_backfill.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()

    # Bootstrap the migrations tracking table.
    conn.executescript("PRAGMA foreign_keys=ON;\n" + _CREATE_MIGRATIONS_TABLE)
    conn.commit()

    # Apply all migrations strictly before 005.
    for f in sorted(_MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql")):
        if int(f.name[:3]) < 5:
            apply_migration(conn, f)

    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apply_005(conn: sqlite3.Connection) -> None:
    """Apply migration 005 to the given connection."""
    apply_migration(conn, _MIGRATION_005)


def _insert_team(
    conn: sqlite3.Connection,
    name: str,
    public_id: str | None = None,
    membership_type: str = "tracked",
) -> int:
    """Insert a team and return its INTEGER id."""
    cur = conn.execute(
        "INSERT INTO teams (name, public_id, membership_type) VALUES (?, ?, ?)",
        (name, public_id, membership_type),
    )
    conn.commit()
    return cur.lastrowid


def _insert_opponent_link(
    conn: sqlite3.Connection,
    our_team_id: int,
    resolved_team_id: int,
    public_id: str | None,
    root_team_id: str,
    resolved_at: str | None = "2026-01-01T00:00:00",
) -> int:
    """Insert an opponent_links row and return its id."""
    cur = conn.execute(
        """
        INSERT INTO opponent_links
            (our_team_id, root_team_id, opponent_name, resolved_team_id,
             public_id, resolution_method, resolved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            our_team_id,
            root_team_id,
            "Opponent Team",
            resolved_team_id,
            public_id,
            "schedule",
            resolved_at,
        ),
    )
    conn.commit()
    return cur.lastrowid


def _get_public_id(conn: sqlite3.Connection, team_id: int) -> str | None:
    row = conn.execute(
        "SELECT public_id FROM teams WHERE id = ?", (team_id,)
    ).fetchone()
    assert row is not None
    return row[0]


# ---------------------------------------------------------------------------
# AC-2 / AC-6: Basic backfill -- missing public_id gets populated
# ---------------------------------------------------------------------------


def test_backfill_populates_missing_public_id(
    pre_backfill_db: sqlite3.Connection,
) -> None:
    """AC-2 / AC-6: teams.public_id is backfilled from opponent_links."""
    conn = pre_backfill_db
    member = _insert_team(conn, "LSB Varsity", membership_type="member")
    opponent = _insert_team(conn, "Rival HS", public_id=None)

    _insert_opponent_link(conn, member, opponent, "rival-hs-slug", root_team_id="rt-1")

    # Pre-condition: opponent has no public_id
    assert _get_public_id(conn, opponent) is None

    _apply_005(conn)

    assert _get_public_id(conn, opponent) == "rival-hs-slug"


# ---------------------------------------------------------------------------
# AC-3: Existing public_id is not overwritten
# ---------------------------------------------------------------------------


def test_backfill_does_not_overwrite_existing_public_id(
    pre_backfill_db: sqlite3.Connection,
) -> None:
    """AC-3: teams rows that already have public_id are not modified."""
    conn = pre_backfill_db
    member = _insert_team(conn, "LSB Varsity", membership_type="member")
    opponent = _insert_team(conn, "Already Resolved", public_id="already-slug")

    _insert_opponent_link(
        conn, member, opponent, "different-slug", root_team_id="rt-2"
    )

    _apply_005(conn)

    # Must remain the original value, not overwritten
    assert _get_public_id(conn, opponent) == "already-slug"


# ---------------------------------------------------------------------------
# AC-4: Deterministic selection when multiple opponent_links rows exist
# ---------------------------------------------------------------------------


def test_backfill_uses_most_recent_opponent_link(
    pre_backfill_db: sqlite3.Connection,
) -> None:
    """AC-4: Most recent opponent_links row (by resolved_at DESC, id DESC) wins."""
    conn = pre_backfill_db
    member = _insert_team(conn, "LSB JV", membership_type="member")
    opponent = _insert_team(conn, "Multi-Link Opponent", public_id=None)

    # Older link with slug-v1
    _insert_opponent_link(
        conn,
        member,
        opponent,
        "slug-v1",
        root_team_id="rt-3a",
        resolved_at="2025-06-01T00:00:00",
    )
    # Newer link with slug-v2 (different root_team_id to satisfy UNIQUE constraint)
    _insert_opponent_link(
        conn,
        member,
        opponent,
        "slug-v2",
        root_team_id="rt-3b",
        resolved_at="2026-01-01T00:00:00",
    )

    _apply_005(conn)

    assert _get_public_id(conn, opponent) == "slug-v2"


def test_backfill_tiebreaks_by_id_when_resolved_at_is_null(
    pre_backfill_db: sqlite3.Connection,
) -> None:
    """AC-4: When resolved_at is NULL on both rows, higher id wins as tiebreaker."""
    conn = pre_backfill_db
    member = _insert_team(conn, "LSB Freshman", membership_type="member")
    opponent = _insert_team(conn, "Null-Date Opponent", public_id=None)

    # Both links have NULL resolved_at; second insert gets higher id
    _insert_opponent_link(
        conn, member, opponent, "slug-first", root_team_id="rt-4a", resolved_at=None
    )
    _insert_opponent_link(
        conn, member, opponent, "slug-second", root_team_id="rt-4b", resolved_at=None
    )

    _apply_005(conn)

    assert _get_public_id(conn, opponent) == "slug-second"


# ---------------------------------------------------------------------------
# AC-5: UNIQUE collision guard -- skip if target public_id exists on another row
# ---------------------------------------------------------------------------


def test_backfill_skips_row_when_public_id_already_used_elsewhere(
    pre_backfill_db: sqlite3.Connection,
) -> None:
    """AC-5: Migration skips backfill when target public_id is already on another teams row."""
    conn = pre_backfill_db
    member = _insert_team(conn, "LSB Varsity", membership_type="member")

    # another_team already owns the slug that would be backfilled
    another_team = _insert_team(conn, "Owner of Slug", public_id="contested-slug")
    target_team = _insert_team(conn, "Would-Be Backfill Target", public_id=None)

    _insert_opponent_link(
        conn, member, target_team, "contested-slug", root_team_id="rt-5"
    )

    _apply_005(conn)

    # target_team must remain NULL because "contested-slug" is already taken
    assert _get_public_id(conn, target_team) is None

    # another_team must be unchanged
    assert _get_public_id(conn, another_team) == "contested-slug"


# ---------------------------------------------------------------------------
# Batch-duplicate guard: two NULL rows targeting the same slug -- only one wins
# ---------------------------------------------------------------------------


def test_backfill_batch_duplicate_skips_all_ambiguous(
    pre_backfill_db: sqlite3.Connection,
) -> None:
    """Batch-duplicate guard: when two teams rows both map to the same target
    public_id slug, BOTH rows are skipped -- neither gets backfilled.  This
    matches how _write_public_id handles collisions in the resolver (skip +
    log) and avoids routing scouting data to the wrong team row.
    """
    conn = pre_backfill_db
    member = _insert_team(conn, "LSB Varsity", membership_type="member")

    # Two distinct teams rows, both NULL, both pointing at the same slug.
    team_low = _insert_team(conn, "Duplicate Target A", public_id=None)
    team_high = _insert_team(conn, "Duplicate Target B", public_id=None)

    # Both opponent_links rows carry the same public_id slug.
    _insert_opponent_link(
        conn, member, team_low, "shared-slug", root_team_id="rt-dup-a"
    )
    _insert_opponent_link(
        conn, member, team_high, "shared-slug", root_team_id="rt-dup-b"
    )

    # Should not raise IntegrityError.
    _apply_005(conn)

    low_pid = _get_public_id(conn, team_low)
    high_pid = _get_public_id(conn, team_high)

    # Both rows must remain NULL -- neither wins when the slug is ambiguous.
    assert low_pid is None
    assert high_pid is None


# ---------------------------------------------------------------------------
# Idempotency: re-running migration SQL does not change already-populated rows
# ---------------------------------------------------------------------------


def test_backfill_is_idempotent(pre_backfill_db: sqlite3.Connection) -> None:
    """Migration UPDATE is safe to re-run -- no double writes or collisions."""
    conn = pre_backfill_db
    member = _insert_team(conn, "LSB Reserve", membership_type="member")
    opponent = _insert_team(conn, "Idempotent Opponent", public_id=None)

    _insert_opponent_link(conn, member, opponent, "idem-slug", root_team_id="rt-6")

    _apply_005(conn)

    assert _get_public_id(conn, opponent) == "idem-slug"

    # Re-run the SQL directly to simulate a second migration pass
    migration_sql = _MIGRATION_005.read_text()
    conn.executescript(migration_sql)

    # Value must be unchanged
    assert _get_public_id(conn, opponent) == "idem-slug"
