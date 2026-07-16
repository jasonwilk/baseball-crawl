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
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Identity match-method vocabulary (E-235-03 gate (c), TN-1/TN-3).
MATCH_ANCHOR = "anchor"  # matched/created with a gc_uuid or public_id anchor
MATCH_NAME_ONLY = "name_only"  # matched/created by name only (lower trust)


@dataclass
class EnsureTeamResult:
    """Provenance of an :func:`ensure_team_row_with_provenance` resolution.

    Attributes:
        team_id: The ``teams.id`` (integer PK) of the matched or created row.
        match_method: ``'anchor'`` when matched/created via a gc_uuid or
            public_id anchor (reliable); ``'name_only'`` when matched/created by
            name+season with no external-id anchor (the silent-wrong-team risk).
            Feeds E-235's ``identity_match_method`` run-record flag (gate (c)).
        inserted: ``True`` when this call INSERTed a brand-new row; ``False``
            when it matched an existing row (including the dedup/self-tracking
            guards). Consumed by E-235-04's in-memory created-set (insert-vs-
            match), which must record only teams a run truly inserted.
    """

    team_id: int
    match_method: str
    inserted: bool


def ensure_team_row(
    db: sqlite3.Connection,
    *,
    name: str | None = None,
    gc_uuid: str | None = None,
    public_id: str | None = None,
    season_year: int | None = None,
    innings_per_game: int | None = None,
    source: str | None = None,
) -> int:
    """Find or create a team row using a deterministic dedup cascade.

    All identifier parameters are optional -- callers pass what they have.
    Thin wrapper over :func:`ensure_team_row_with_provenance` for the many
    callers that only need the integer PK; the cascade logic lives in the
    provenance form (single source of truth).

    Args:
        db: An open sqlite3.Connection.
        name: Team display name.
        gc_uuid: GC UUID from authenticated API.
        public_id: GC public URL slug.
        season_year: Season year integer.
        innings_per_game: GC's per-team-season regulation innings/game (the ERA
            basis, E-264). NULL-safe backfill only -- fills an existing NULL,
            never clobbers a stored integer.
        source: Pipeline source label (for logging/debugging).

    Returns:
        The ``teams.id`` (integer PK) of the matched or newly created row.
    """
    return ensure_team_row_with_provenance(
        db,
        name=name,
        gc_uuid=gc_uuid,
        public_id=public_id,
        season_year=season_year,
        innings_per_game=innings_per_game,
        source=source,
    ).team_id


def ensure_team_row_with_provenance(
    db: sqlite3.Connection,
    *,
    name: str | None = None,
    gc_uuid: str | None = None,
    public_id: str | None = None,
    season_year: int | None = None,
    innings_per_game: int | None = None,
    source: str | None = None,
    _insert_retry: bool = False,
) -> EnsureTeamResult:
    """Find or create a team row, returning resolution provenance.

    Same deterministic dedup cascade as :func:`ensure_team_row` (which delegates
    here) but additionally reports HOW the row was resolved -- the identity
    ``match_method`` (E-235-03 gate (c)) and whether the row was newly INSERTed
    (``inserted``, consumed by E-235-04). The cascade order is unchanged:
    gc_uuid match → public_id match → name+season match → self-tracking guards
    → INSERT.

    ``_insert_retry`` is internal: on a cross-process INSERT race (a concurrent
    process commits the same gc_uuid/public_id between this call's cascade SELECT
    and its INSERT, tripping a partial UNIQUE index), the function re-enters ONCE
    with this flag set so the now-committed racing row is resolved through the
    normal match path (steps 1-2) -- applying the SAME backfills a match would,
    not a bare id lookup (E-235 Phase 4b MEDIUM-1). The flag bounds the retry to
    a single re-entry (no infinite recursion if the row vanishes again).

    Returns:
        An :class:`EnsureTeamResult`.
    """
    # Step 1: gc_uuid match
    if gc_uuid is not None:
        row = db.execute(
            "SELECT id, name, public_id, season_year, innings_per_game "
            "FROM teams WHERE gc_uuid = ?",
            (gc_uuid,),
        ).fetchone()
        if row:
            existing_id, existing_name, existing_public_id, existing_sy, existing_ipg = row
            logger.debug(
                "ensure_team_row: gc_uuid match id=%d gc_uuid=%r",
                existing_id, gc_uuid,
            )
            _backfill_identifier(
                db, existing_id, "public_id", existing_public_id, public_id, gc_uuid,
            )
            _backfill_name(db, existing_id, existing_name, name, gc_uuid)
            _backfill_season_year(db, existing_id, existing_sy, season_year)
            _backfill_innings_per_game(db, existing_id, existing_ipg, innings_per_game)
            return EnsureTeamResult(existing_id, MATCH_ANCHOR, False)

    # Step 2: public_id match (no gc_uuid IS NULL filter)
    if public_id is not None:
        row = db.execute(
            "SELECT id, name, gc_uuid, season_year, innings_per_game "
            "FROM teams WHERE public_id = ?",
            (public_id,),
        ).fetchone()
        if row:
            existing_id, existing_name, existing_gc_uuid, existing_sy, existing_ipg = row
            logger.debug(
                "ensure_team_row: public_id match id=%d public_id=%r",
                existing_id, public_id,
            )
            _backfill_identifier(
                db, existing_id, "gc_uuid", existing_gc_uuid, gc_uuid, public_id,
            )
            _backfill_name(db, existing_id, existing_name, name, gc_uuid)
            _backfill_season_year(db, existing_id, existing_sy, season_year)
            _backfill_innings_per_game(db, existing_id, existing_ipg, innings_per_game)
            return EnsureTeamResult(existing_id, MATCH_ANCHOR, False)

    # Step 3: name + season_year + tracked match
    if name is not None:
        row = db.execute(
            "SELECT id, name, season_year, innings_per_game FROM teams "
            "WHERE name = ? COLLATE NOCASE "
            "AND COALESCE(season_year, -1) = COALESCE(?, -1) "
            "AND membership_type = 'tracked' "
            "ORDER BY id ASC LIMIT 1",
            (name, season_year),
        ).fetchone()
        if row:
            existing_id, existing_name, existing_sy, existing_ipg = row
            logger.debug(
                "ensure_team_row: name+season_year match id=%d name=%r",
                existing_id, name,
            )
            # Conservative back-fill: NO gc_uuid/public_id on name matches
            _backfill_name(db, existing_id, existing_name, name, gc_uuid)
            _backfill_season_year(db, existing_id, existing_sy, season_year)
            _backfill_innings_per_game(db, existing_id, existing_ipg, innings_per_game)
            return EnsureTeamResult(existing_id, MATCH_NAME_ONLY, False)

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
            return EnsureTeamResult(member[0], MATCH_ANCHOR, False)

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
            return EnsureTeamResult(member[0], MATCH_ANCHOR, False)

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
            return EnsureTeamResult(member[0], MATCH_NAME_ONLY, False)

    # Step 4: INSERT new tracked row
    insert_name = name if name is not None else (gc_uuid or "Unknown")
    insert_source = source if source is not None else "gamechanger"
    try:
        cursor = db.execute(
            "INSERT INTO teams (name, gc_uuid, public_id, season_year, "
            "innings_per_game, membership_type, source, is_active) "
            "VALUES (?, ?, ?, ?, ?, 'tracked', ?, 0)",
            (insert_name, gc_uuid, public_id, season_year, innings_per_game, insert_source),
        )
    except sqlite3.IntegrityError:
        # Cross-process INSERT race (E-235-04): a concurrent process committed a
        # row with the same gc_uuid/public_id between this call's cascade SELECT
        # (steps 1-2) and this INSERT, tripping a partial UNIQUE index. Re-run the
        # cascade ONCE: the racing row now exists, so steps 1-2 MATCH it AND apply
        # the same gc_uuid/public_id/name/season backfills the normal match path
        # does -- not a bare id lookup (E-235 Phase 4b MEDIUM-1). Degrades to a
        # match (inserted=False) without crashing the generation. Name-only
        # inserts have no UNIQUE index on name and never reach here.
        if not _insert_retry:
            logger.info(
                "ensure_team_row: lost INSERT race on gc_uuid=%r/public_id=%r; "
                "re-matching the concurrently-created row with backfill",
                gc_uuid, public_id,
            )
            return ensure_team_row_with_provenance(
                db, name=name, gc_uuid=gc_uuid, public_id=public_id,
                season_year=season_year, innings_per_game=innings_per_game,
                source=source, _insert_retry=True,
            )
        # Already retried once and STILL colliding without a match (the racing
        # row vanished then reappeared -- pathological). Re-raise rather than
        # loop; nothing is masked.
        raise
    new_id = cursor.lastrowid
    logger.info(
        "ensure_team_row: INSERT new tracked team id=%d name=%r gc_uuid=%r "
        "public_id=%r season_year=%r source=%r",
        new_id, insert_name, gc_uuid, public_id, season_year, insert_source,
    )
    # A fresh insert carrying any external id (gc_uuid/public_id) is anchored;
    # an insert from name alone is name_only (lower trust).
    insert_method = MATCH_ANCHOR if (gc_uuid or public_id) else MATCH_NAME_ONLY
    return EnsureTeamResult(new_id, insert_method, True)


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


def _backfill_innings_per_game(
    db: sqlite3.Connection,
    team_id: int,
    existing_ipg: int | None,
    new_ipg: int | None,
) -> None:
    """Write innings_per_game only when the existing row has NULL (E-264 TN-4).

    Mirrors :func:`_backfill_season_year`: a fetched non-NULL value fills an
    existing NULL, but a later None (a failed re-fetch) MUST NOT clobber a
    stored integer -- the last known good basis is kept. NULL is load-bearing
    provenance for the display layer's "(assumed)" flag, so the fill is
    strictly NULL->value.
    """
    if new_ipg is None or existing_ipg is not None:
        return
    db.execute(
        "UPDATE teams SET innings_per_game = ? WHERE id = ?",
        (new_ipg, team_id),
    )
    logger.debug(
        "ensure_team_row: back-filled innings_per_game=%d on team id=%d",
        new_ipg, team_id,
    )
