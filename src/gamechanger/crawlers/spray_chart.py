"""Spray chart crawler for the GameChanger data ingestion pipeline.

Reads game-summaries files written by the schedule crawler, filters to
completed games, fetches per-game player-stats data for each game via::

    GET /teams/{team_id}/schedule/events/{event_id}/player-stats

and writes raw JSON to::

    data/raw/{season}/teams/{gc_uuid}/spray/{event_id}.json

Completed game data never changes, so the idempotency check is existence-only:
if the file already exists it is skipped regardless of age.

The endpoint returns both teams' spray chart data in a single call.  The full
response is saved; team separation happens in the loader.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.gamechanger.client import CredentialExpiredError, GameChangerAPIError, GameChangerClient
from src.gamechanger.config import CrawlConfig
from src.gamechanger.crawlers import CrawlResult

logger = logging.getLogger(__name__)

_PLAYER_STATS_ACCEPT = "application/json, text/plain, */*"
_DATA_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw"
_COMPLETED_STATUS = "completed"


class SprayChartCrawler:
    """Crawls and caches player-stats (spray chart) data for all completed games.

    Reads game-summaries JSON files (written by ``ScheduleCrawler``) from disk,
    identifies completed games, and fetches their player-stats from the
    GameChanger API.

    Args:
        client: Authenticated ``GameChangerClient`` used for all HTTP requests.
        config: Parsed ``CrawlConfig`` containing the season and owned team list.
        data_root: Root directory for raw data output.  Defaults to
            ``data/raw/`` relative to the project root.
    """

    def __init__(
        self,
        client: GameChangerClient,
        config: CrawlConfig,
        data_root: Path = _DATA_ROOT,
    ) -> None:
        self._client = client
        self._config = config
        self._data_root = data_root

    def crawl_all(self) -> CrawlResult:
        """Crawl player-stats for all completed games across all configured teams.

        For each owned team, reads the game-summaries file, filters to
        completed games, and fetches player-stats for any not already cached.

        API errors on individual games are caught, logged, and counted -- they
        do not abort the overall crawl.  Missing game-summaries files are also
        logged and skipped gracefully.

        Returns:
            A ``CrawlResult`` summarising files written, files skipped, and
            errors encountered.
        """
        result = CrawlResult()
        for team in self._config.member_teams:
            team_result = self._crawl_team(team.id, self._config.season)
            result.files_written += team_result.files_written
            result.files_skipped += team_result.files_skipped
            result.errors += team_result.errors

        logger.info(
            "SprayChartCrawler complete: %d fetched, %d cached, %d errored.",
            result.files_written,
            result.files_skipped,
            result.errors,
        )
        return result

    def _crawl_team(self, team_id: str, season: str) -> CrawlResult:
        """Crawl player-stats for all completed games for a single team.

        Args:
            team_id: GameChanger team UUID (gc_uuid).
            season: Season label (e.g. ``"2025"``).

        Returns:
            A ``CrawlResult`` for this team's games.
        """
        result = CrawlResult()
        summaries_path = self._game_summaries_path(team_id, season)

        if not summaries_path.exists():
            logger.warning(
                "Game summaries file not found for team %s at %s; skipping.",
                team_id,
                summaries_path,
            )
            return result

        summaries = self._load_summaries(summaries_path)
        total = len(summaries)
        completed = [r for r in summaries if r.get("game_status") == _COMPLETED_STATUS]
        skipped_status = total - len(completed)

        if skipped_status > 0:
            logger.info(
                "Team %s: %d of %d games are not completed -- skipping.",
                team_id,
                skipped_status,
                total,
            )

        for record in completed:
            event_id = record.get("event_id")

            if event_id is None:
                logger.warning(
                    "Missing event_id in record for team %s; skipping.",
                    team_id,
                )
                result.errors += 1
                continue

            dest = self._spray_path(team_id, season, event_id)

            if dest.exists():
                logger.debug(
                    "Spray chart for game %s already cached; skipping.", event_id
                )
                result.files_skipped += 1
                continue

            try:
                data = self._fetch_player_stats(team_id, event_id)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(json.dumps(data, indent=2), encoding="utf-8")
                logger.info("Wrote spray chart %s -> %s.", event_id, dest)
                result.files_written += 1
            except CredentialExpiredError:
                raise
            except GameChangerAPIError as exc:
                logger.error(
                    "API error fetching player-stats for event_id=%s: %s",
                    event_id,
                    exc,
                )
                result.errors += 1
            except Exception as exc:  # noqa: BLE001 -- broad catch intentional; log and continue
                logger.error(
                    "Unexpected error fetching player-stats for event_id=%s: %s",
                    event_id,
                    exc,
                )
                result.errors += 1

        return result

    def _fetch_player_stats(self, team_id: str, event_id: str) -> Any:
        """Fetch the raw player-stats response for a single game.

        Args:
            team_id: GameChanger team UUID used as the endpoint path parameter.
            event_id: The ``event_id`` from game-summaries.

        Returns:
            Parsed JSON response containing player_stats, cumulative_player_stats,
            and spray_chart_data sections.

        Raises:
            GameChangerAPIError: If the API returns an error response.
            CredentialExpiredError: If the session token has expired.
        """
        return self._client.get(
            f"/teams/{team_id}/schedule/events/{event_id}/player-stats",
            accept=_PLAYER_STATS_ACCEPT,
        )

    def _load_summaries(self, path: Path) -> list[dict[str, Any]]:
        """Load and parse a game-summaries JSON file.

        Args:
            path: Path to the game_summaries.json file.

        Returns:
            List of game summary records.
        """
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            logger.warning(
                "game_summaries.json at %s is not a list (got %s); treating as empty.",
                path,
                type(raw).__name__,
            )
            return []
        return raw

    def _game_summaries_path(self, team_id: str, season: str) -> Path:
        """Return the path to the game-summaries file for a team.

        Args:
            team_id: GameChanger team UUID.
            season: Season label string.

        Returns:
            ``data/raw/{season}/teams/{team_id}/game_summaries.json``
        """
        return self._data_root / season / "teams" / team_id / "game_summaries.json"

    def _spray_path(self, team_id: str, season: str, event_id: str) -> Path:
        """Return the destination path for a single game's spray chart file.

        Args:
            team_id: GameChanger team UUID.
            season: Season label string.
            event_id: The ``event_id`` from game-summaries -- used as the filename.

        Returns:
            ``data/raw/{season}/teams/{team_id}/spray/{event_id}.json``
        """
        return self._data_root / season / "teams" / team_id / "spray" / f"{event_id}.json"
