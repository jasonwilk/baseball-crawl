"""Schedule and game-summaries crawler for the GameChanger data ingestion pipeline.

Fetches the full game schedule and all game summaries for each configured team
from the GameChanger API and writes raw JSON to::

    data/raw/{season}/teams/{team_id}/schedule.json
    data/raw/{season}/teams/{team_id}/game_summaries.json

Both crawls are idempotent: if a fresh file already exists (default: younger
than 1 hour) it is skipped and logged at INFO level.

Usage::

    from src.gamechanger.client import GameChangerClient
    from src.gamechanger.config import load_config
    from src.gamechanger.crawlers.schedule import ScheduleCrawler

    client = GameChangerClient()
    config = load_config()
    crawler = ScheduleCrawler(client, config)
    result = crawler.crawl_all()
    print(result)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from src.gamechanger.client import GameChangerClient, GameChangerAPIError
from src.gamechanger.config import CrawlConfig
from src.gamechanger.crawlers import CrawlResult

logger = logging.getLogger(__name__)

_SCHEDULE_ACCEPT = "application/vnd.gc.com.event:list+json; version=0.2.0"
_GAME_SUMMARIES_ACCEPT = "application/vnd.gc.com.game_summary:list+json; version=0.1.0"
_DATA_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw"


class ScheduleCrawler:
    """Crawls and caches schedule and game-summaries data for configured LSB teams.

    For each team, fetches two endpoints:

    - ``GET /teams/{team_id}/schedule?fetch_place_details=true`` (no pagination)
    - ``GET /teams/{team_id}/game-summaries`` (paginated via ``x-next-page``)

    Args:
        client: Authenticated ``GameChangerClient`` used for all HTTP requests.
        config: Parsed ``CrawlConfig`` containing the season and owned team list.
        freshness_hours: How many hours a cached file is considered fresh.
            Files younger than this threshold are skipped.  Defaults to 1.
        data_root: Root directory for raw data output.  Defaults to
            ``data/raw/`` relative to the project root.
    """

    def __init__(
        self,
        client: GameChangerClient,
        config: CrawlConfig,
        freshness_hours: int = 1,
        data_root: Path = _DATA_ROOT,
    ) -> None:
        self._client = client
        self._config = config
        self._freshness_hours = freshness_hours
        self._data_root = data_root

    def crawl_all(self) -> CrawlResult:
        """Crawl schedule and game-summaries for all configured owned teams.

        Iterates over every entry in ``config.member_teams``.  For each team,
        both endpoints are attempted.  API errors for individual teams are
        caught, logged, and counted -- they do not abort the overall crawl.

        Returns:
            A ``CrawlResult`` summarising files written, files skipped, and
            errors encountered.
        """
        result = CrawlResult()
        for team in self._config.member_teams:
            for crawl_fn in (self._crawl_schedule, self._crawl_game_summaries):
                try:
                    path = crawl_fn(team.id, self._config.season)
                    if path is None:
                        result.files_skipped += 1
                    else:
                        result.files_written += 1
                except GameChangerAPIError as exc:
                    logger.error(
                        "API error crawling %s for team %s: %s",
                        crawl_fn.__name__,
                        team.id,
                        exc,
                    )
                    result.errors += 1
                except Exception as exc:  # noqa: BLE001 -- broad catch intentional; log and continue
                    logger.error(
                        "Unexpected error in %s for team %s: %s",
                        crawl_fn.__name__,
                        team.id,
                        exc,
                    )
                    result.errors += 1
        return result

    def _crawl_schedule(self, team_id: str, season: str) -> Path | None:
        """Fetch and write the schedule for a single team.

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
        dest = self._schedule_path(team_id, season)

        if self._is_fresh(dest, self._freshness_hours):
            logger.info(
                "Schedule for team %s is fresh (< %dh old); skipping fetch.",
                team_id,
                self._freshness_hours,
            )
            return None

        logger.info("Fetching schedule for team %s (season %s).", team_id, season)
        data: Any = self._client.get(
            f"/teams/{team_id}/schedule",
            params={"fetch_place_details": "true"},
            accept=_SCHEDULE_ACCEPT,
        )

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(
            "Wrote schedule to %s (%s events).",
            dest,
            len(data) if isinstance(data, list) else "?",
        )
        return dest

    def _crawl_game_summaries(self, team_id: str, season: str) -> Path | None:
        """Fetch and write all game summaries for a single team.

        Uses paginated fetching (``x-pagination: true`` + ``x-next-page``).
        All pages are fetched and the combined list is written as a single JSON
        file.  Checks freshness first.

        Args:
            team_id: GameChanger team UUID.
            season: Season label (e.g. ``"2025"``).

        Returns:
            The ``Path`` the file was written to, or ``None`` if the existing
            file was fresh and the fetch was skipped.

        Raises:
            GameChangerAPIError: If the API returns an error response.
        """
        dest = self._game_summaries_path(team_id, season)

        if self._is_fresh(dest, self._freshness_hours):
            logger.info(
                "Game summaries for team %s are fresh (< %dh old); skipping fetch.",
                team_id,
                self._freshness_hours,
            )
            return None

        logger.info("Fetching game summaries for team %s (season %s).", team_id, season)
        records: list[Any] = self._client.get_paginated(
            f"/teams/{team_id}/game-summaries",
            accept=_GAME_SUMMARIES_ACCEPT,
        )

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(records, indent=2), encoding="utf-8")
        logger.info(
            "Wrote game summaries to %s (%d records).",
            dest,
            len(records),
        )
        return dest

    def _schedule_path(self, team_id: str, season: str) -> Path:
        """Return the canonical destination path for a team's schedule file.

        Args:
            team_id: GameChanger team UUID.
            season: Season label string.

        Returns:
            ``data/raw/{season}/teams/{team_id}/schedule.json``
        """
        return self._data_root / season / "teams" / team_id / "schedule.json"

    def _game_summaries_path(self, team_id: str, season: str) -> Path:
        """Return the canonical destination path for a team's game-summaries file.

        Args:
            team_id: GameChanger team UUID.
            season: Season label string.

        Returns:
            ``data/raw/{season}/teams/{team_id}/game_summaries.json``
        """
        return self._data_root / season / "teams" / team_id / "game_summaries.json"

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
