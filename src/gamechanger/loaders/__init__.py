"""GameChanger loaders package.

Provides the shared ``LoadResult`` dataclass used as the return type for all
loader entry points, plus canonical season_id derivation and season-row
helpers.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime

_logger = logging.getLogger(__name__)


@dataclass
class LoadResult:
    """Summary of a completed load run.

    Attributes:
        loaded: Number of records successfully upserted into the database.
        skipped: Number of records skipped due to missing required fields.
        errors: Number of records that caused unexpected errors.
        redirect_map: ``{stale_event_id: surviving_game_id}`` entries produced
            by ``GameLoader`` when a dedup collapse leaves an event id with no
            ``games`` row of its own. Empty for non-redirected loads. Carries
            the mapping to the report generator's plays/spray stages so those
            rows are filed under the surviving id rather than skipped under an
            id that no longer resolves.

            ⚠️ IT IS NO LONGER CROSS-PERSPECTIVE-ONLY (2026-08-15). Two distinct
            entry shapes now exist and they point in OPPOSITE directions:

            * REDIRECT (E-244, unchanged): the incoming game is filed under an
              existing canonical row, so the key is the INCOMING source event
              id and no row is deleted.
            * PROMOTION (opponent-identity divergence): the incoming row wins
              and the canonical stub-headed row is MERGED AWAY AND DELETED, so
              the key is the DELETED row's event id -- an id that had a row a
              moment ago. Entries already pointing AT that deleted row are
              rewritten to follow it.

            So a key here means "this id does not resolve to a games row",
            NOT "this id belonged to another perspective". Code reasoning about
            these entries must not assume the key was never persisted.
    """

    loaded: int = field(default=0)
    skipped: int = field(default=0)
    errors: int = field(default=0)
    redirect_map: dict[str, str] = field(default_factory=dict)


def derive_season_id_for_team(
    db: sqlite3.Connection, team_id: int
) -> tuple[str, int | None]:
    """Derive the canonical year-only season_id for a team from its metadata.

    Looks up ``teams.season_year`` and returns the year as a string (or the
    current year when ``season_year`` is absent), paired with the raw
    ``season_year`` value. The single ``season_id`` per team is the
    within-report game filter; it is inherently single-season.

    Returns:
        Tuple of ``(season_id, season_year)``.  ``season_id`` is the year as a
        string (e.g. ``'2026'``); ``season_year`` is the raw
        ``teams.season_year`` value (may be ``None``).

    Raises:
        ValueError: If *team_id* does not exist in the ``teams`` table.
    """
    row = db.execute(
        "SELECT season_year FROM teams WHERE id = ?",
        (team_id,),
    ).fetchone()

    if row is None:
        raise ValueError(f"team_id {team_id} does not exist in the teams table")

    season_year = row[0]
    year = season_year if season_year is not None else datetime.now().year
    return str(year), season_year


def ensure_season_row(db: sqlite3.Connection, season_id: str) -> None:
    """Ensure a ``seasons`` row exists for *season_id* (idempotent).

    ``season_id`` MUST be a pure-year slug (e.g. ``'2026'``). A non-numeric or
    compound value raises ``ValueError`` via ``int()`` -- cross-season season_id
    forms were de-scoped, so a value that is not a bare year is a caller bug,
    not something to silently coerce to year 0.
    """
    year = int(season_id)

    db.execute(
        """
        INSERT INTO seasons (season_id, name, year)
        VALUES (?, ?, ?)
        ON CONFLICT(season_id) DO NOTHING
        """,
        (season_id, season_id, year),
    )


