"""Player season-stats crawler for the GameChanger data ingestion pipeline.

Fetches season-aggregate batting, pitching, and fielding stats for all players
on each configured team from the GameChanger API and writes the raw JSON
response to::

    data/raw/{season}/teams/{team_id}/stats.json

The crawl is idempotent: if a fresh file already exists (default: younger than
24 hours) it is skipped and logged at INFO level.

Usage::

    from src.gamechanger.client import GameChangerClient
    from src.gamechanger.config import load_config
    from src.gamechanger.crawlers.player_stats import PlayerStatsCrawler

    client = GameChangerClient()
    config = load_config()
    crawler = PlayerStatsCrawler(client, config)
    result = crawler.crawl_all()
    print(result)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from src.gamechanger.client import CredentialExpiredError, GameChangerAPIError, GameChangerClient
from src.gamechanger.config import CrawlConfig
from src.gamechanger.crawlers import CrawlResult

logger = logging.getLogger(__name__)

_SEASON_STATS_ACCEPT = "application/vnd.gc.com.team_season_stats+json; version=0.2.0"
_SEASON_STATS_USER_ACTION = "data_loading:team_stats"
_DATA_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw"


class PlayerStatsCrawler:
    """Crawls and caches season-aggregate player stats for configured LSB teams.

    Makes one request per team to ``GET /teams/{team_id}/season-stats``.
    The response contains all players on the team keyed by UUID.

    Args:
        client: Authenticated ``GameChangerClient`` used for all HTTP requests.
        config: Parsed ``CrawlConfig`` containing the season and owned team list.
        freshness_hours: How many hours a cached ``stats.json`` is considered
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
        """Crawl season stats for all configured owned teams.

        Iterates over every entry in ``config.member_teams``.  API errors for
        individual teams are caught, logged, and counted -- they do not abort
        the overall crawl.

        Returns:
            A ``CrawlResult`` summarising files written, files skipped, and
            errors encountered.
        """
        result = CrawlResult()
        for team in self._config.member_teams:
            try:
                path = self.crawl_team(team.id, self._config.season)
                if path is None:
                    result.files_skipped += 1
                else:
                    result.files_written += 1
            except GameChangerAPIError as exc:
                logger.error(
                    "API error crawling season stats for team %s: %s", team.id, exc
                )
                result.errors += 1
            except CredentialExpiredError:
                raise
            except Exception as exc:  # noqa: BLE001 -- broad catch intentional; log and continue
                logger.error(
                    "Unexpected error crawling season stats for team %s: %s", team.id, exc
                )
                result.errors += 1
        return result

    def crawl_team(self, team_id: str, season: str) -> Path | None:
        """Fetch and write season stats for a single team.

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
                "Season stats for team %s are fresh (< %dh old); skipping fetch.",
                team_id,
                self._freshness_hours,
            )
            return None

        logger.info("Fetching season stats for team %s (season %s).", team_id, season)
        data: Any = self._client.get(
            f"/teams/{team_id}/season-stats",
            accept=_SEASON_STATS_ACCEPT,
        )

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(data, indent=2), encoding="utf-8")
        player_count = len(data.get("stats_data", {}).get("players", {})) if isinstance(data, dict) else "?"
        logger.info("Wrote season stats to %s (%s players).", dest, player_count)
        return dest

    def _dest_path(self, team_id: str, season: str) -> Path:
        """Return the canonical destination path for a team's season-stats file.

        Args:
            team_id: GameChanger team UUID.
            season: Season label string.

        Returns:
            ``data/raw/{season}/teams/{team_id}/stats.json``
        """
        return self._data_root / season / "teams" / team_id / "stats.json"

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
