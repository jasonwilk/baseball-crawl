"""Opponent crawler for the GameChanger data ingestion pipeline.

Fetches opponent registry data for each configured owned team and then
fetches rosters for each unique opponent with a canonical team UUID.

Phase 1 -- Opponent registry:
    For each owned team, calls ``GET /teams/{team_id}/opponents`` (with
    cursor-based pagination) and writes the full paginated response to::

        data/raw/{season}/teams/{team_id}/opponents.json

Phase 2 -- Opponent rosters:
    Extracts unique ``progenitor_team_id`` values from all opponents.json
    files (filtering out ``is_hidden: true`` and entries without
    ``progenitor_team_id``).  For each unique opponent UUID (excluding
    owned-team UUIDs), calls ``GET /teams/{progenitor_team_id}/players``
    and writes the result to::

        data/raw/{season}/teams/{opponent_team_id}/roster.json

The crawl is idempotent: files younger than ``freshness_hours`` (default 24)
are skipped.

Usage::

    from src.gamechanger.client import GameChangerClient
    from src.gamechanger.config import load_config
    from src.gamechanger.crawlers.opponent import OpponentCrawler

    client = GameChangerClient()
    config = load_config()
    crawler = OpponentCrawler(client, config)
    result = crawler.crawl_all()
    print(result)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from src.gamechanger.client import CredentialExpiredError, ForbiddenError, GameChangerAPIError, GameChangerClient
from src.gamechanger.config import CrawlConfig
from src.gamechanger.crawlers import CrawlResult
from src.gamechanger.crawlers.roster import RosterCrawler

logger = logging.getLogger(__name__)

_OPPONENTS_ACCEPT = "application/vnd.gc.com.opponent_team:list+json; version=0.0.0"
_DATA_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw"


class OpponentCrawler:
    """Crawls opponent registry and roster data for all configured owned teams.

    Args:
        client: Authenticated ``GameChangerClient`` used for all HTTP requests.
        config: Parsed ``CrawlConfig`` containing the season and owned team list.
        freshness_hours: How many hours a cached file is considered fresh.
            Files younger than this threshold are skipped.  Defaults to 24.
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
        self._roster_crawler = RosterCrawler(
            client, config, freshness_hours=freshness_hours, data_root=data_root
        )

    def crawl_all(self) -> CrawlResult:
        """Run the two-phase opponent crawl.

        Phase 1 fetches and writes the opponents.json registry for each owned
        team.  Phase 2 extracts unique progenitor_team_id values and fetches a
        roster for each.

        Returns:
            A ``CrawlResult`` summarising files written, files skipped, and
            errors encountered (across both phases).
        """
        result = CrawlResult()

        # Phase 1: fetch opponent registry for each owned team.
        all_opponents: list[dict[str, Any]] = []
        for team in self._config.member_teams:
            try:
                opponents, wrote = self._crawl_registry(team.id)
                if wrote:
                    result.files_written += 1
                else:
                    result.files_skipped += 1
                all_opponents.extend(opponents)
            except GameChangerAPIError as exc:
                logger.error(
                    "API error fetching opponent registry for team %s: %s", team.id, exc
                )
                result.errors += 1
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Unexpected error fetching opponent registry for team %s: %s",
                    team.id,
                    exc,
                )
                result.errors += 1

        # Phase 2: deduplicate and fetch rosters.
        owned_ids = {t.id for t in self._config.member_teams}
        phase2_result = self._crawl_opponent_rosters(all_opponents, owned_ids)

        result.files_written += phase2_result.files_written
        result.files_skipped += phase2_result.files_skipped
        result.errors += phase2_result.errors

        return result

    # ------------------------------------------------------------------
    # Phase 1 helpers
    # ------------------------------------------------------------------

    def _crawl_registry(self, team_id: str) -> tuple[list[dict[str, Any]], bool]:
        """Fetch (or load from cache) the opponent registry for one owned team.

        Paginates through all pages of ``GET /teams/{team_id}/opponents`` and
        writes the combined list to ``opponents.json``.

        Args:
            team_id: Owned team UUID.

        Returns:
            A tuple of (opponents list, was_written) where was_written is True
            if a new file was fetched and written, False if the cached file was
            fresh and returned directly.

        Raises:
            GameChangerAPIError: If the API returns an error.
        """
        dest = self._opponents_path(team_id)

        if self._is_fresh(dest):
            logger.info(
                "Opponents registry for team %s is fresh (< %dh old); loading from cache.",
                team_id,
                self._freshness_hours,
            )
            data = json.loads(dest.read_text(encoding="utf-8"))
            return data, False

        logger.info(
            "Fetching opponents registry for team %s (season %s).",
            team_id,
            self._config.season,
        )

        opponents: list[Any] = self._client.get_paginated(
            f"/teams/{team_id}/opponents",
            accept=_OPPONENTS_ACCEPT,
        )

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(opponents, indent=2), encoding="utf-8")
        logger.info(
            "Wrote opponents registry to %s (%d records).", dest, len(opponents)
        )
        return opponents, True

    # ------------------------------------------------------------------
    # Phase 2 helpers
    # ------------------------------------------------------------------

    def _crawl_opponent_rosters(
        self,
        all_opponents: list[dict[str, Any]],
        owned_ids: set[str],
    ) -> CrawlResult:
        """Fetch rosters for all unique opponent teams.

        Deduplicates on ``progenitor_team_id``, skips hidden opponents and
        opponents without a canonical UUID, and excludes owned teams.

        Args:
            all_opponents: Combined list of all opponent records from all registry files.
            owned_ids: Set of owned team UUIDs to exclude.

        Returns:
            A ``CrawlResult`` for the roster-fetching phase only.
        """
        result = CrawlResult()

        # Stats counters for summary log (AC-7).
        total = len(all_opponents)
        with_progenitor = 0
        without_progenitor = 0
        hidden = 0
        successfully_crawled = 0
        access_denied = 0
        unexpected_errors = 0

        seen_ids: set[str] = set()

        for opponent in all_opponents:
            if opponent.get("is_hidden", False):
                hidden += 1
                continue

            progenitor_id: str | None = opponent.get("progenitor_team_id")
            name: str = opponent.get("name", "<unnamed>")

            if not progenitor_id:
                without_progenitor += 1
                logger.info(
                    "Skipping opponent '%s' -- no canonical team UUID (progenitor_team_id absent).",
                    name,
                )
                continue

            with_progenitor += 1

            if progenitor_id in owned_ids:
                logger.debug(
                    "Skipping opponent '%s' (%s) -- is an owned team.", name, progenitor_id
                )
                seen_ids.add(progenitor_id)
                continue

            if progenitor_id in seen_ids:
                logger.debug(
                    "Skipping opponent '%s' (%s) -- already processed.", name, progenitor_id
                )
                continue

            seen_ids.add(progenitor_id)

            try:
                path = self._roster_crawler.crawl_team(progenitor_id, self._config.season)
                if path is None:
                    result.files_skipped += 1
                else:
                    result.files_written += 1
                successfully_crawled += 1
            except ForbiddenError as exc:
                # 403 -- per-opponent access denial, expected for some opponents.
                logger.warning(
                    "Access denied fetching roster for opponent '%s' (%s): %s",
                    name,
                    progenitor_id,
                    exc,
                )
                access_denied += 1
                result.errors += 1
            except CredentialExpiredError as exc:
                # 401 -- token has expired, abort the entire crawl immediately.
                logger.error(
                    "Token expired during opponent roster crawl for '%s' (%s): %s",
                    name,
                    progenitor_id,
                    exc,
                )
                raise
            except GameChangerAPIError as exc:
                logger.warning(
                    "API error fetching roster for opponent '%s' (%s): %s",
                    name,
                    progenitor_id,
                    exc,
                )
                unexpected_errors += 1
                result.errors += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Unexpected error fetching roster for opponent '%s' (%s): %s",
                    name,
                    progenitor_id,
                    exc,
                )
                unexpected_errors += 1
                result.errors += 1

        # AC-7: summary log.
        logger.info(
            "Opponent crawl summary -- "
            "total_unique_opponents=%d, "
            "with_progenitor_id=%d, "
            "without_progenitor_id=%d, "
            "hidden=%d, "
            "successfully_crawled=%d, "
            "access_denied=%d, "
            "unexpected_errors=%d",
            total,
            with_progenitor,
            without_progenitor,
            hidden,
            successfully_crawled,
            access_denied,
            unexpected_errors,
        )

        return result

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def _opponents_path(self, team_id: str) -> Path:
        """Return the destination path for a team's opponents.json registry.

        Args:
            team_id: Owned team UUID.

        Returns:
            ``data/raw/{season}/teams/{team_id}/opponents.json``
        """
        return self._data_root / self._config.season / "teams" / team_id / "opponents.json"

    def _is_fresh(self, path: Path) -> bool:
        """Return True if *path* exists and is younger than freshness_hours.

        Args:
            path: File path to check.

        Returns:
            ``True`` if the file exists and was modified within the threshold.
        """
        if not path.exists():
            return False
        age_seconds = time.time() - path.stat().st_mtime
        return age_seconds < self._freshness_hours * 3600
