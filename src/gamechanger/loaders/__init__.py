"""GameChanger loaders package.

Provides the shared ``LoadResult`` dataclass used as the return type for all
loader ``load_file()`` methods.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field

_logger = logging.getLogger(__name__)


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


def extract_year_from_season_id(season_id: str) -> int | None:
    """Extract the 4-digit year from a season_id slug (e.g. '2025-spring-hs' → 2025)."""
    for part in season_id.split("-"):
        if part.isdigit() and len(part) == 4:
            return int(part)
    return None


def warn_season_year_mismatch(
    db: sqlite3.Connection,
    team_id: int,
    season_id: str,
    loader_name: str,
) -> None:
    """Emit a WARNING if the data's year doesn't match teams.season_year.

    Observability only -- never blocks loading.  Silently returns if the
    season_year column does not exist (pre-migration database).
    """
    data_year = extract_year_from_season_id(season_id)
    if data_year is None:
        return
    try:
        row = db.execute(
            "SELECT season_year FROM teams WHERE id = ?", (team_id,)
        ).fetchone()
    except sqlite3.OperationalError:
        return  # column not yet added
    if row and row[0] is not None and row[0] != data_year:
        _logger.warning(
            "%s: season year mismatch for team_id=%d: teams.season_year=%d but data year=%d (season_id=%s)",
            loader_name, team_id, row[0], data_year, season_id,
        )
