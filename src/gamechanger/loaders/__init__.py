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


def derive_season_id_for_team(
    db: sqlite3.Connection, team_id: int
) -> tuple[str, int | None]:
    """Derive the canonical season_id for a team from its metadata.

    Algorithm:
        1. Look up ``teams.season_year`` and ``programs.program_type``
           (via ``teams.program_id``).
        2. Map ``program_type`` to a season suffix (e.g. ``hs`` → ``spring-hs``).
        3. Return ``('{year}-{suffix}', season_year)`` or ``('{year}', season_year)``
           when no program.

    Returns:
        Tuple of ``(season_id, season_year)``.  ``season_year`` is the raw
        ``teams.season_year`` value (may be ``None``).

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
    if suffix:
        return f"{year}-{suffix}", season_year
    return str(year), season_year


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


