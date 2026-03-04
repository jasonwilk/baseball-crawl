"""Roster crawler for the GameChanger data ingestion pipeline.

Fetches the current roster for each configured team from the GameChanger API
and writes the raw JSON response to::

    data/raw/{season}/teams/{team_id}/roster.json

The crawl is idempotent: if a fresh file already exists (default: younger than
24 hours) it is skipped and logged at INFO level.

Usage::

    from src.gamechanger.client import GameChangerClient
    from src.gamechanger.config import load_config
    from src.gamechanger.crawlers.roster import RosterCrawler

    client = GameChangerClient()
    config = load_config()
    crawler = RosterCrawler(client, config)
    result = crawler.crawl_all()
    print(result)
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.gamechanger.client import GameChangerClient, GameChangerAPIError
from src.gamechanger.config import CrawlConfig
from src.gamechanger.crawlers import CrawlResult

logger = logging.getLogger(__name__)

_ROSTER_ACCEPT = "application/vnd.gc.com.player:list+json; version=0.1.0"
_DATA_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw"


class RosterCrawler:
    """Crawls and caches roster data for configured LSB teams.

    Args:
        client: Authenticated ``GameChangerClient`` used for all HTTP requests.
        config: Parsed ``CrawlConfig`` containing the season and owned team list.
        freshness_hours: How many hours a cached ``roster.json`` is considered
            fresh.  Files younger than this threshold are skipped.  Defaults to
            24.
        data_root: Root directory for raw data output.  Defaults to
            ``data/raw/`` relative to the project root.
    """

    def __init__(
        self,
        client: GameChangerClient,
        config: CrawlConfig,
        freshness_hours: int = 24,
        data_root: Path = _DATA_ROOT,
    ) -> None:
        self._client = client
        self._config = config
        self._freshness_hours = freshness_hours
        self._data_root = data_root

    def crawl_all(self) -> CrawlResult:
        """Crawl rosters for all configured owned teams.

        Iterates over every entry in ``config.owned_teams``.  API errors for
        individual teams are caught, logged, and counted -- they do not abort
        the overall crawl.

        Returns:
            A ``CrawlResult`` summarising files written, files skipped, and
            errors encountered.
        """
        result = CrawlResult()
        for team in self._config.owned_teams:
            try:
                path = self.crawl_team(team.id, self._config.season)
                if path is None:
                    result.files_skipped += 1
                else:
                    result.files_written += 1
            except GameChangerAPIError as exc:
                logger.error(
                    "API error crawling roster for team %s: %s", team.id, exc
                )
                result.errors += 1
            except Exception as exc:  # noqa: BLE001 -- broad catch intentional; log and continue
                logger.error(
                    "Unexpected error crawling roster for team %s: %s", team.id, exc
                )
                result.errors += 1
        return result

    def crawl_team(self, team_id: str, season: str) -> Path | None:
        """Fetch and write the roster for a single team.

        Checks freshness first; if the file exists and is fresh the method
        returns ``None`` (caller should count as skipped).

        Args:
            team_id: GameChanger team UUID.
            season: Season label (e.g. ``"2025"``).

        Returns:
            The ``Path`` the file was written to, or ``None`` if the existing
            file was fresh and the fetch was skipped.

        Raises:
            GameChangerAPIError: If the API returns an error response.
        """
        dest = self._dest_path(team_id, season)

        if self._is_fresh(dest, self._freshness_hours):
            logger.info(
                "Roster for team %s is fresh (< %dh old); skipping fetch.",
                team_id,
                self._freshness_hours,
            )
            return None

        logger.info("Fetching roster for team %s (season %s).", team_id, season)
        data: Any = self._client.get(
            f"/teams/{team_id}/players",
            accept=_ROSTER_ACCEPT,
        )

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Wrote roster to %s (%d players).", dest, len(data) if isinstance(data, list) else "?")
        return dest

    def _dest_path(self, team_id: str, season: str) -> Path:
        """Return the canonical destination path for a team's roster file.

        Args:
            team_id: GameChanger team UUID.
            season: Season label string.

        Returns:
            ``data/raw/{season}/teams/{team_id}/roster.json``
        """
        return self._data_root / season / "teams" / team_id / "roster.json"

    def _is_fresh(self, path: Path, freshness_hours: int) -> bool:
        """Return True if *path* exists and is younger than *freshness_hours*.

        Args:
            path: File path to check.
            freshness_hours: Freshness threshold in hours.

        Returns:
            ``True`` if the file exists and was modified within the threshold.
        """
        if not path.exists():
            return False
        age_seconds = time.time() - path.stat().st_mtime
        return age_seconds < freshness_hours * 3600
