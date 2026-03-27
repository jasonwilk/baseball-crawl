"""Shared team-row lookup and creation with deterministic dedup cascade.

Provides ``ensure_team_row()`` -- a single function that all pipeline paths
use to find or create a team row.  The cascade lookup order is:

1. gc_uuid match (strongest signal)
2. public_id match
3. name + season_year + tracked match (weakest / heuristic)
4. INSERT new row

A self-tracking guard runs before step 4 to prevent creating a tracked
duplicate of an existing member team.

Back-fill rules are conservative: gc_uuid and public_id are only written on
identifier matches (steps 1-2), never on name-only matches (step 3).
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)


def ensure_team_row(
    db: sqlite3.Connection,
    *,
    name: str | None = None,
    gc_uuid: str | None = None,
    public_id: str | None = None,
    season_year: int | None = None,
    source: str | None = None,
) -> int:
    """Find or create a team row using a deterministic dedup cascade.

    All identifier parameters are optional -- callers pass what they have.

    Args:
        db: An open sqlite3.Connection.
        name: Team display name.
        gc_uuid: GC UUID from authenticated API.
        public_id: GC public URL slug.
        season_year: Season year integer.
        source: Pipeline source label (for logging/debugging).

    Returns:
        The ``teams.id`` (integer PK) of the matched or newly created row.
    """
    # Step 1: gc_uuid match
    if gc_uuid is not None:
        row = db.execute(
            "SELECT id, name, public_id, season_year FROM teams WHERE gc_uuid = ?",
            (gc_uuid,),
        ).fetchone()
        if row:
            existing_id, existing_name, existing_public_id, existing_sy = row
            logger.debug(
                "ensure_team_row: gc_uuid match id=%d gc_uuid=%r",
                existing_id, gc_uuid,
            )
            _backfill_identifier(
                db, existing_id, "public_id", existing_public_id, public_id, gc_uuid,
            )
            _backfill_name(db, existing_id, existing_name, name, gc_uuid)
            _backfill_season_year(db, existing_id, existing_sy, season_year)
            return existing_id

    # Step 2: public_id match (no gc_uuid IS NULL filter)
    if public_id is not None:
        row = db.execute(
            "SELECT id, name, gc_uuid, season_year FROM teams WHERE public_id = ?",
            (public_id,),
        ).fetchone()
        if row:
            existing_id, existing_name, existing_gc_uuid, existing_sy = row
            logger.debug(
                "ensure_team_row: public_id match id=%d public_id=%r",
                existing_id, public_id,
            )
            _backfill_identifier(
                db, existing_id, "gc_uuid", existing_gc_uuid, gc_uuid, public_id,
            )
            _backfill_name(db, existing_id, existing_name, name, gc_uuid)
            _backfill_season_year(db, existing_id, existing_sy, season_year)
            return existing_id

    # Step 3: name + season_year + tracked match
    if name is not None:
        row = db.execute(
            "SELECT id, name, season_year FROM teams "
            "WHERE name = ? COLLATE NOCASE "
            "AND COALESCE(season_year, -1) = COALESCE(?, -1) "
            "AND membership_type = 'tracked' "
            "ORDER BY id ASC LIMIT 1",
            (name, season_year),
        ).fetchone()
        if row:
            existing_id, existing_name, existing_sy = row
            logger.debug(
                "ensure_team_row: name+season_year match id=%d name=%r",
                existing_id, name,
            )
            # Conservative back-fill: NO gc_uuid/public_id on name matches
            _backfill_name(db, existing_id, existing_name, name, gc_uuid)
            _backfill_season_year(db, existing_id, existing_sy, season_year)
            return existing_id

    # Self-tracking guard: don't create a tracked duplicate of a member team
    if gc_uuid is not None:
        member = db.execute(
            "SELECT id FROM teams WHERE gc_uuid = ? AND membership_type = 'member'",
            (gc_uuid,),
        ).fetchone()
        if member:
            logger.info(
                "ensure_team_row: self-tracking guard (gc_uuid) -> member id=%d",
                member[0],
            )
            return member[0]

    if public_id is not None:
        member = db.execute(
            "SELECT id FROM teams WHERE public_id = ? AND membership_type = 'member'",
            (public_id,),
        ).fetchone()
        if member:
            logger.info(
                "ensure_team_row: self-tracking guard (public_id) -> member id=%d",
                member[0],
            )
            return member[0]

    # Name-only self-tracking guard (for callers with no gc_uuid/public_id)
    if gc_uuid is None and public_id is None and name is not None:
        member = db.execute(
            "SELECT id FROM teams "
            "WHERE name = ? COLLATE NOCASE AND membership_type = 'member' "
            "ORDER BY id ASC LIMIT 1",
            (name,),
        ).fetchone()
        if member:
            logger.info(
                "ensure_team_row: self-tracking guard (name) -> member id=%d",
                member[0],
            )
            return member[0]

    # Step 4: INSERT new tracked row
    insert_name = name if name is not None else (gc_uuid or "Unknown")
    insert_source = source if source is not None else "gamechanger"
    cursor = db.execute(
        "INSERT INTO teams (name, gc_uuid, public_id, season_year, "
        "membership_type, source, is_active) VALUES (?, ?, ?, ?, 'tracked', ?, 0)",
        (insert_name, gc_uuid, public_id, season_year, insert_source),
    )
    new_id = cursor.lastrowid
    logger.info(
        "ensure_team_row: INSERT new tracked team id=%d name=%r gc_uuid=%r "
        "public_id=%r season_year=%r source=%r",
        new_id, insert_name, gc_uuid, public_id, season_year, insert_source,
    )
    return new_id


def _backfill_identifier(
    db: sqlite3.Connection,
    team_id: int,
    column: str,
    existing_value: str | None,
    new_value: str | None,
    context_id: str | None,
) -> None:
    """Back-fill gc_uuid or public_id when the existing row has NULL.

    Collision-safe: checks for another row holding the same value before
    writing. Skips silently when new_value is None or existing is non-NULL.
    """
    if new_value is None or existing_value is not None:
        return

    collision = db.execute(
        f"SELECT id FROM teams WHERE {column} = ? AND id != ?",  # noqa: S608
        (new_value, team_id),
    ).fetchone()
    if collision:
        logger.warning(
            "ensure_team_row: UNIQUE collision on %s=%r -- already assigned to "
            "team id=%d; skipping back-fill for team id=%d (context=%r)",
            column, new_value, collision[0], team_id, context_id,
        )
        return

    db.execute(
        f"UPDATE teams SET {column} = ? WHERE id = ?",  # noqa: S608
        (new_value, team_id),
    )
    logger.debug(
        "ensure_team_row: back-filled %s=%r on team id=%d",
        column, new_value, team_id,
    )


def _backfill_name(
    db: sqlite3.Connection,
    team_id: int,
    existing_name: str,
    new_name: str | None,
    gc_uuid: str | None,
) -> None:
    """Update name only when existing name is a UUID-as-name stub.

    A UUID-as-name stub is when the existing name equals the gc_uuid string
    (the team was created with only a UUID, no real name).
    """
    if new_name is None or gc_uuid is None:
        return
    if existing_name == gc_uuid:
        db.execute(
            "UPDATE teams SET name = ? WHERE id = ?",
            (new_name, team_id),
        )
        logger.debug(
            "ensure_team_row: replaced UUID-as-name stub with %r on team id=%d",
            new_name, team_id,
        )


def _backfill_season_year(
    db: sqlite3.Connection,
    team_id: int,
    existing_sy: int | None,
    new_sy: int | None,
) -> None:
    """Write season_year only when the existing row has NULL."""
    if new_sy is None or existing_sy is not None:
        return
    db.execute(
        "UPDATE teams SET season_year = ? WHERE id = ?",
        (new_sy, team_id),
    )
    logger.debug(
        "ensure_team_row: back-filled season_year=%d on team id=%d",
        new_sy, team_id,
    )
