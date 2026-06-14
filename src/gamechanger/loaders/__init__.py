"""GameChanger loaders package.

Provides the shared ``LoadResult`` dataclass used as the return type for all
loader ``load_file()`` methods, plus canonical season_id derivation and
season-row helpers.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime

_logger = logging.getLogger(__name__)

# program_type → season suffix mapping
_PROGRAM_TYPE_SUFFIX: dict[str, str] = {
    "hs": "spring-hs",
    "usssa": "summer-usssa",
    "legion": "summer-legion",
}


@dataclass
class LoadResult:
    """Summary of a completed load run.

    Attributes:
        loaded: Number of records successfully upserted into the database.
        skipped: Number of records skipped due to missing required fields.
        errors: Number of records that caused unexpected errors.
    """

    loaded: int = field(default=0)
    skipped: int = field(default=0)
    errors: int = field(default=0)


@dataclass
class SeasonDerivation:
    """Result of :func:`derive_season_id_for_team_with_fallback`.

    Attributes:
        season_id: The canonical season_id (e.g. ``'2026-spring-hs'`` or
            ``'2026'``).
        season_year: The raw ``teams.season_year`` value (may be ``None``).
        fallback_used: ``True`` when the season was resolved via a fallback
            rather than full team metadata -- either the current-year fallback
            (``season_year IS None``) or the year-only fallback (no mappable
            ``program_type``, so no season suffix). Feeds E-235's
            ``season_fallback`` run-record flag (gate (b)). ``False`` only when
            BOTH a concrete ``season_year`` and a mapped program suffix exist.
    """

    season_id: str
    season_year: int | None
    fallback_used: bool


def derive_season_id_for_team(
    db: sqlite3.Connection, team_id: int
) -> tuple[str, int | None]:
    """Derive the canonical season_id for a team from its metadata.

    Thin wrapper over :func:`derive_season_id_for_team_with_fallback` for the
    many callers that only need ``(season_id, season_year)``; the derivation
    logic lives in the fallback-aware form (single source of truth).

    Returns:
        Tuple of ``(season_id, season_year)``.  ``season_year`` is the raw
        ``teams.season_year`` value (may be ``None``).

    Raises:
        ValueError: If *team_id* does not exist in the ``teams`` table.
    """
    d = derive_season_id_for_team_with_fallback(db, team_id)
    return d.season_id, d.season_year


def derive_season_id_for_team_with_fallback(
    db: sqlite3.Connection, team_id: int
) -> SeasonDerivation:
    """Derive the canonical season_id, reporting whether a fallback fired.

    Algorithm:
        1. Look up ``teams.season_year`` and ``programs.program_type``
           (via ``teams.program_id``).
        2. Map ``program_type`` to a season suffix (e.g. ``hs`` → ``spring-hs``).
        3. Return ``'{year}-{suffix}'`` or ``'{year}'`` (when no program suffix).

    ``fallback_used`` is the single source of truth for E-235 gate (b): it is
    ``True`` when ``season_year`` was absent (current-year fallback) OR no
    season suffix could be derived (year-only fallback). Callers needing the
    flag MUST read it here rather than re-deriving the rule (which would drift).

    Raises:
        ValueError: If *team_id* does not exist in the ``teams`` table.
    """
    row = db.execute(
        """
        SELECT t.season_year, p.program_type
        FROM teams t
        LEFT JOIN programs p ON t.program_id = p.program_id
        WHERE t.id = ?
        """,
        (team_id,),
    ).fetchone()

    if row is None:
        raise ValueError(f"team_id {team_id} does not exist in the teams table")

    season_year, program_type = row
    year = season_year if season_year is not None else datetime.now().year

    suffix = _PROGRAM_TYPE_SUFFIX.get(program_type) if program_type else None
    # Fallback fired when either metadata input was missing: no concrete
    # season_year (→ current-year) or no mappable program suffix (→ year-only).
    fallback_used = season_year is None or suffix is None
    if suffix:
        return SeasonDerivation(f"{year}-{suffix}", season_year, fallback_used)
    return SeasonDerivation(str(year), season_year, fallback_used)


def ensure_season_row(db: sqlite3.Connection, season_id: str) -> None:
    """Ensure a ``seasons`` row exists for *season_id* (idempotent).

    Handles two formats:
    - ``{year}-{suffix}`` (e.g. ``2025-summer-usssa``): uses suffix as
      ``season_type``.
    - Year-only (e.g. ``2026``): uses ``"default"`` as ``season_type``.
    """
    parts = season_id.split("-", 1)
    year_str = parts[0]
    year = int(year_str) if year_str.isdigit() else 0

    if len(parts) == 2:
        season_type = parts[1]
    else:
        season_type = "default"

    db.execute(
        """
        INSERT INTO seasons (season_id, name, season_type, year)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(season_id) DO NOTHING
        """,
        (season_id, season_id, season_type, year),
    )


