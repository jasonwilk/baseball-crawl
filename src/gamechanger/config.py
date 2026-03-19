"""Configuration loader for the baseball-crawl ingestion pipeline.

Reads ``config/teams.yaml`` and exposes a ``CrawlConfig`` dataclass that
downstream crawlers consume.  The YAML file is committed to version control and
contains no credentials.

A database-driven loader ``load_config_from_db()`` is also provided.  It reads
active member teams from the ``teams`` table and derives the current season from
the most recent row in the ``seasons`` table.

Example YAML::

    season: "2025"
    member_teams:
      - id: "abc123"
        name: "Lincoln Freshman"
        classification: "freshman"
      - id: "def456"
        name: "Lincoln Varsity"
        classification: "varsity"

Usage::

    from src.gamechanger.config import CrawlConfig, load_config, load_config_from_db

    config = load_config()
    for team in config.member_teams:
        print(team.id, team.name)
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "teams.yaml"


@dataclass
class TeamEntry:
    """A single team entry from the YAML config or database.

    Attributes:
        id: GameChanger team UUID (member teams) or public_id slug (tracked teams).
        name: Human-readable team name.
        classification: Program level (e.g. ``"freshman"``, ``"jv"``, ``"varsity"``).
        internal_id: INTEGER primary key from ``teams.id``.  Populated when the
            config is loaded from the database or when a ``db_path`` is supplied
            to ``load_config()``.  ``None`` when loaded from YAML without a DB lookup.
    """

    id: str
    name: str
    classification: str
    internal_id: int | None = None


@dataclass
class CrawlConfig:
    """Top-level configuration parsed from ``config/teams.yaml``.

    Attributes:
        season: Season label used as the top-level directory under ``data/raw/``.
        member_teams: List of LSB member teams to crawl.
    """

    season: str
    member_teams: list[TeamEntry] = field(default_factory=list)


def load_config(
    path: Path = _DEFAULT_CONFIG_PATH,
    db_path: Path | None = None,
) -> CrawlConfig:
    """Load and parse the teams YAML config file.

    Args:
        path: Path to the YAML config file.  Defaults to
            ``config/teams.yaml`` relative to the project root.
        db_path: Optional path to the SQLite database.  When supplied,
            each team entry's ``internal_id`` is populated via a
            ``SELECT id FROM teams WHERE gc_uuid = ?`` lookup.

    Returns:
        A populated ``CrawlConfig`` instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If required top-level keys (``season``, ``member_teams``) are
            missing.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}. "
            "Create config/teams.yaml with at minimum a 'season' key and "
            "a 'member_teams' list."
        )

    with path.open() as fh:
        raw = yaml.safe_load(fh)

    if not isinstance(raw, dict):
        raise ValueError(f"Config file must be a YAML mapping, got: {type(raw).__name__}")

    if "season" not in raw:
        raise ValueError("Config file is missing required key: 'season'")
    if "member_teams" not in raw:
        raise ValueError("Config file is missing required key: 'member_teams'")

    teams = _parse_member_teams(raw["member_teams"])

    # Optionally populate internal_id from the database.
    if db_path is not None:
        _populate_internal_ids(teams, db_path)

    logger.debug(
        "Loaded config: season=%s, %d member teams", raw["season"], len(teams)
    )
    return CrawlConfig(season=str(raw["season"]), member_teams=teams)


def _parse_member_teams(raw_entries: list) -> list[TeamEntry]:
    """Build a list of ``TeamEntry`` objects from raw YAML entries.

    Args:
        raw_entries: List of dicts from the ``member_teams`` YAML key.

    Returns:
        List of ``TeamEntry`` instances.
    """
    return [
        TeamEntry(
            id=str(entry["id"]),
            name=str(entry.get("name", "")),
            classification=str(entry.get("classification", "")),
        )
        for entry in raw_entries
    ]


def _populate_internal_ids(teams: list[TeamEntry], db_path: Path) -> None:
    """Populate ``TeamEntry.internal_id`` from the database for each team.

    Args:
        teams: List of ``TeamEntry`` instances to update in-place.
        db_path: Path to the SQLite database.
    """
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.row_factory = sqlite3.Row
        for team in teams:
            row = conn.execute(
                "SELECT id FROM teams WHERE gc_uuid = ? LIMIT 1",
                (team.id,),
            ).fetchone()
            if row is not None:
                team.internal_id = row["id"]
            else:
                logger.debug(
                    "No teams row found for gc_uuid=%s; internal_id remains None.",
                    team.id,
                )


def load_config_from_db(db_path: Path) -> CrawlConfig:
    """Load crawl configuration from the SQLite database.

    Queries active member teams and derives the current season from the most
    recent entry in the ``seasons`` table.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        A populated ``CrawlConfig`` instance.  If no active member teams are
        found, ``member_teams`` will be an empty list (not an error).

    Raises:
        ValueError: If no seasons exist in the database.
        sqlite3.Error: If the database cannot be opened or queried.
    """
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.row_factory = sqlite3.Row

        season_row = conn.execute(
            "SELECT season_id FROM seasons ORDER BY year DESC LIMIT 1"
        ).fetchone()
        if season_row is None:
            raise ValueError("No seasons found in database")
        season_id: str = season_row["season_id"]

        team_rows = conn.execute(
            "SELECT id, name, classification, gc_uuid "
            "FROM teams WHERE is_active = 1 AND membership_type = 'member' AND gc_uuid IS NOT NULL"
        ).fetchall()

    teams: list[TeamEntry] = []
    for row in team_rows:
        gc_uuid_str: str = row["gc_uuid"]
        try:
            uuid.UUID(gc_uuid_str)
        except ValueError:
            logger.warning(
                "Skipping team '%s' (id=%d): gc_uuid '%s' is not a valid UUID format",
                row["name"],
                row["id"],
                gc_uuid_str,
            )
            continue
        teams.append(
            TeamEntry(
                id=gc_uuid_str,
                name=row["name"],
                classification=row["classification"] or "",
                internal_id=row["id"],
            )
        )

    logger.debug(
        "Loaded DB config: season=%s, %d member teams", season_id, len(teams)
    )
    return CrawlConfig(season=season_id, member_teams=teams)
