"""Configuration loader for the baseball-crawl ingestion pipeline.

Reads ``config/teams.yaml`` and exposes a ``CrawlConfig`` dataclass that
downstream crawlers consume.  The YAML file is committed to version control and
contains no credentials.

Example YAML::

    season: "2025"
    owned_teams:
      - id: "abc123"
        name: "Lincoln Freshman"
        level: "freshman"
      - id: "def456"
        name: "Lincoln Varsity"
        level: "varsity"

Usage::

    from src.gamechanger.config import CrawlConfig, load_config

    config = load_config()
    for team in config.owned_teams:
        print(team.id, team.name)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "teams.yaml"


@dataclass
class TeamEntry:
    """A single team entry from the YAML config.

    Attributes:
        id: GameChanger team UUID.
        name: Human-readable team name.
        level: Program level (e.g. ``"freshman"``, ``"jv"``, ``"varsity"``).
    """

    id: str
    name: str
    level: str


@dataclass
class CrawlConfig:
    """Top-level configuration parsed from ``config/teams.yaml``.

    Attributes:
        season: Season label used as the top-level directory under ``data/raw/``.
        owned_teams: List of LSB teams to crawl.
    """

    season: str
    owned_teams: list[TeamEntry] = field(default_factory=list)


def load_config(path: Path = _DEFAULT_CONFIG_PATH) -> CrawlConfig:
    """Load and parse the teams YAML config file.

    Args:
        path: Path to the YAML config file.  Defaults to
            ``config/teams.yaml`` relative to the project root.

    Returns:
        A populated ``CrawlConfig`` instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If required top-level keys (``season``, ``owned_teams``) are
            missing.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}. "
            "Create config/teams.yaml with at minimum a 'season' key and "
            "an 'owned_teams' list."
        )

    with path.open() as fh:
        raw = yaml.safe_load(fh)

    if not isinstance(raw, dict):
        raise ValueError(f"Config file must be a YAML mapping, got: {type(raw).__name__}")

    if "season" not in raw:
        raise ValueError("Config file is missing required key: 'season'")
    if "owned_teams" not in raw:
        raise ValueError("Config file is missing required key: 'owned_teams'")

    teams = [
        TeamEntry(
            id=str(entry["id"]),
            name=str(entry.get("name", "")),
            level=str(entry.get("level", "")),
        )
        for entry in raw["owned_teams"]
    ]

    logger.debug(
        "Loaded config: season=%s, %d owned teams", raw["season"], len(teams)
    )
    return CrawlConfig(season=str(raw["season"]), owned_teams=teams)
