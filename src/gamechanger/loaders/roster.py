"""Roster loader for the baseball-crawl ingestion pipeline.

Reads a ``roster.json`` file (written by the roster crawler) and upserts
player and team-membership records into the SQLite database.

The loader is idempotent: loading the same file twice produces the same
database state as loading it once.  Upserts are performed via
``INSERT OR REPLACE`` (players) and ``INSERT OR IGNORE`` (team_rosters).

Expected file path convention::

    data/raw/{season_id}/teams/{team_id}/roster.json

The ``team_id`` and ``season_id`` are inferred from the path.

Usage::

    import sqlite3
    from pathlib import Path
    from src.gamechanger.loaders.roster import RosterLoader

    conn = sqlite3.connect("./data/app.db")
    conn.execute("PRAGMA foreign_keys=ON;")
    loader = RosterLoader(conn)
    result = loader.load_file(Path("data/raw/2025/teams/abc-123/roster.json"))
    print(result)
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from src.db.teams import ensure_team_row
from src.gamechanger.loaders import LoadResult, derive_season_id_for_team, ensure_season_row

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field mapping: GameChanger API field name -> (players column, required)
# ---------------------------------------------------------------------------

# Required fields: if missing, the record is skipped.
_REQUIRED_PLAYER_FIELDS: tuple[str, ...] = ("id",)

# Mapping of GC API field name to DB column name.
_PLAYER_FIELD_MAP: dict[str, str] = {
    "id": "player_id",
    "first_name": "first_name",
    "last_name": "last_name",
}

# Team_rosters roster field -> DB column name.
_ROSTER_FIELD_MAP: dict[str, str] = {
    "number": "jersey_number",
    "position": "position",
}

# All known top-level fields in the roster JSON.
_KNOWN_FIELDS: frozenset[str] = frozenset(_PLAYER_FIELD_MAP) | frozenset(_ROSTER_FIELD_MAP) | {"avatar_url"}


@dataclass
class _Player:
    """Parsed player record ready for database insertion.

    Attributes:
        player_id: GameChanger UUID for this player.
        first_name: Player first name (may be initials).
        last_name: Player last name.
        jersey_number: Jersey number string (may be shared; not unique).
        position: Position string if present in raw data.
    """

    player_id: str
    first_name: str
    last_name: str
    jersey_number: str | None = None
    position: str | None = None


class RosterLoader:
    """Loads a roster JSON file into the SQLite database.

    Upserts player records into ``players`` and team-membership records into
    ``team_rosters``.  Before inserting ``team_rosters`` rows, ensures that
    prerequisite ``teams`` and ``seasons`` rows exist.

    Args:
        db: Open ``sqlite3.Connection`` with ``PRAGMA foreign_keys=ON`` set.
            The caller owns the connection lifecycle.
    """

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def load_file(self, path: Path) -> LoadResult:
        """Load a roster JSON file into the database.

        Infers ``team_id`` (gc_uuid) from the file path using the convention
        ``data/raw/{season_id}/teams/{team_id}/roster.json``.  The DB
        ``season_id`` is derived from team metadata, not the filesystem path.

        Args:
            path: Absolute or relative path to the ``roster.json`` file.

        Returns:
            A ``LoadResult`` summarising records loaded, skipped, and errors.
        """
        gc_uuid, path_year = self._infer_team_id_from_path(path)
        logger.info("Loading roster file: %s (team=%s)", path, gc_uuid)

        raw_records = self._read_json(path)
        if raw_records is None:
            return LoadResult(errors=1)

        # Ensure FK prerequisite rows exist before inserting team_rosters.
        # Pass path_year so auto-created stub teams get a reasonable season_year.
        team_int = self._ensure_team_row(gc_uuid, season_year=path_year)
        season_id, _ = derive_season_id_for_team(self._db, team_int)
        ensure_season_row(self._db, season_id)

        result = LoadResult()
        for raw in raw_records:
            player = self._map_player(raw)
            if player is None:
                result.skipped += 1
                continue
            try:
                self._upsert_player(player)
                self._upsert_roster_membership(player, team_int, season_id)
                result.loaded += 1
            except sqlite3.Error as exc:
                logger.error(
                    "Database error loading player %s: %s | raw=%r",
                    raw.get("id", "<unknown>"),
                    exc,
                    raw,
                )
                result.errors += 1

        self._db.commit()
        logger.info(
            "Roster load complete: loaded=%d skipped=%d errors=%d",
            result.loaded,
            result.skipped,
            result.errors,
        )
        return result

    def _infer_team_id_from_path(self, path: Path) -> tuple[str, int | None]:
        """Extract the team's ``gc_uuid`` and path year from the roster file path.

        Expects the convention ``.../{season_id}/teams/{team_id}/roster.json``.

        Args:
            path: Path to the roster JSON file.

        Returns:
            Tuple of ``(gc_uuid, path_year)``.  ``path_year`` is the 4-digit
            year extracted from the season_id path segment, or ``None`` if
            not parseable.
        """
        parts = path.parts
        for i, part in enumerate(parts):
            if part == "teams" and i + 1 < len(parts):
                gc_uuid = parts[i + 1]
                path_year = self._extract_year(parts[i - 1]) if i > 0 else None
                return gc_uuid, path_year
        # Fallback: use immediate parent directory name.
        team_id = path.parent.name
        logger.warning(
            "Could not infer team_id from conventional path; "
            "falling back to team_id=%s",
            team_id,
        )
        return team_id, None

    @staticmethod
    def _extract_year(segment: str) -> int | None:
        """Extract a 4-digit year from a path segment like '2025-spring-hs'."""
        for part in segment.split("-"):
            if part.isdigit() and len(part) == 4:
                return int(part)
        return None

    def _read_json(self, path: Path) -> list[dict] | None:
        """Read and parse the JSON file at ``path``.

        Args:
            path: Path to the JSON file.

        Returns:
            Parsed list of dicts, or ``None`` on read/parse error.
        """
        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            logger.error("Roster file not found: %s", path)
            return None
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse roster JSON at %s: %s", path, exc)
            return None

        if not isinstance(data, list):
            logger.error(
                "Expected a JSON array in %s, got %s", path, type(data).__name__
            )
            return None

        return data

    def _map_player(self, raw: dict) -> _Player | None:
        """Map a raw API dict to a ``_Player`` dataclass.

        Logs unknown fields at DEBUG level.  Returns ``None`` if any required
        field is missing, logging the offending record at ERROR level.

        Args:
            raw: Single player record from the roster JSON array.

        Returns:
            A ``_Player`` instance, or ``None`` if the record should be skipped.
        """
        # Warn about unknown fields.
        for key in raw:
            if key not in _KNOWN_FIELDS:
                logger.debug(
                    "Unknown field %r in roster record; ignoring. raw=%r", key, raw
                )

        # Validate required fields.
        for required in _REQUIRED_PLAYER_FIELDS:
            if not raw.get(required):
                logger.error(
                    "Missing required field %r in roster record; skipping. raw=%r",
                    required,
                    raw,
                )
                return None

        player_id = str(raw["id"])
        first_name = str(raw.get("first_name") or "")
        last_name = str(raw.get("last_name") or "")

        if not first_name:
            logger.error(
                "Missing required field 'first_name' in roster record; skipping. raw=%r",
                raw,
            )
            return None
        if not last_name:
            logger.error(
                "Missing required field 'last_name' in roster record; skipping. raw=%r",
                raw,
            )
            return None

        jersey_number = raw.get("number") or None
        position = raw.get("position") or None

        return _Player(
            player_id=player_id,
            first_name=first_name,
            last_name=last_name,
            jersey_number=jersey_number,
            position=position,
        )

    def _upsert_player(self, player: _Player) -> None:
        """Upsert a player record into the ``players`` table.

        Uses ``INSERT OR REPLACE`` so re-running the same data is idempotent.

        Args:
            player: Parsed player record.
        """
        self._db.execute(
            """
            INSERT INTO players (player_id, first_name, last_name)
            VALUES (?, ?, ?)
            ON CONFLICT(player_id) DO UPDATE SET
                first_name = excluded.first_name,
                last_name  = excluded.last_name
            """,
            (player.player_id, player.first_name, player.last_name),
        )
        logger.debug("Upserted player %s (%s %s)", player.player_id, player.first_name, player.last_name)

    def _upsert_roster_membership(
        self, player: _Player, team_id: int, season_id: str
    ) -> None:
        """Upsert a team_rosters membership row.

        The unique constraint ``(team_id, player_id, season_id)`` prevents
        duplicates.  Uses ``INSERT OR IGNORE`` so re-running is idempotent.

        Args:
            player: Parsed player record.
            team_id: INTEGER PK from the ``teams`` table.
            season_id: Season slug (e.g. ``'2025'``).
        """
        self._db.execute(
            """
            INSERT INTO team_rosters (team_id, player_id, season_id, jersey_number, position)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(team_id, player_id, season_id) DO UPDATE SET
                jersey_number = excluded.jersey_number,
                position      = excluded.position
            """,
            (team_id, player.player_id, season_id, player.jersey_number, player.position),
        )
        logger.debug(
            "Upserted roster membership: player=%s team=%s season=%s",
            player.player_id,
            team_id,
            season_id,
        )

    def _ensure_team_row(
        self, gc_uuid: str, *, season_year: int | None = None
    ) -> int:
        """Ensure a ``teams`` row exists for ``gc_uuid`` and return its INTEGER PK.

        Delegates to the shared ``ensure_team_row()`` dedup cascade.

        Args:
            gc_uuid: GameChanger team UUID.
            season_year: Year from the file path, passed to stub team creation
                so ``derive_season_id_for_team()`` has a reasonable value.

        Returns:
            The ``teams.id`` INTEGER PK for the row.
        """
        return ensure_team_row(
            self._db, gc_uuid=gc_uuid, season_year=season_year, source="roster"
        )

