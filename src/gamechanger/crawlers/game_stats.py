"""Box score crawler for the GameChanger data ingestion pipeline.

Reads game-summaries files written by the schedule crawler (E-002-02), filters
to completed games, fetches per-game box score data for each game via::

    GET /game-stream-processing/{game_stream_id}/boxscore

and writes raw JSON to::

    data/raw/{season}/teams/{team_id}/games/{game_stream_id}.json

Completed game stats never change, so the idempotency check is existence-only:
if the file already exists it is skipped regardless of age.

CRITICAL ID MAPPING
-------------------
The boxscore endpoint path parameter is ``game_stream.id`` from game-summaries.
This is NOT ``event_id`` and NOT ``game_stream.game_id``.  In game-summaries:

    event_id == game_stream.game_id  (always)
    game_stream.id != game_stream.game_id  (always)

Usage::

    from src.gamechanger.client import GameChangerClient
    from src.gamechanger.config import load_config
    from src.gamechanger.crawlers.game_stats import GameStatsCrawler

    client = GameChangerClient()
    config = load_config()
    crawler = GameStatsCrawler(client, config)
    result = crawler.crawl_all()
    print(result)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.gamechanger.client import GameChangerClient, GameChangerAPIError
from src.gamechanger.config import CrawlConfig
from src.gamechanger.crawlers import CrawlResult

logger = logging.getLogger(__name__)

_BOXSCORE_ACCEPT = "application/vnd.gc.com.event_box_score+json; version=0.0.0"
_DATA_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw"
_COMPLETED_STATUS = "completed"


class GameStatsCrawler:
    """Crawls and caches box score data for all completed games.

    Reads game-summaries JSON files (written by ``ScheduleCrawler``) from disk,
    identifies completed games, and fetches their box scores from the
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
        """Crawl box scores for all completed games across all configured teams.

        For each owned team, reads the game-summaries file, filters to
        completed games, and fetches box scores for any not already cached.

        API errors on individual games are caught, logged, and counted -- they
        do not abort the overall crawl.  Missing game-summaries files are also
        logged and skipped gracefully.

        Returns:
            A ``CrawlResult`` summarising files written, files skipped, and
            errors encountered.
        """
        result = CrawlResult()
        for team in self._config.owned_teams:
            team_result = self._crawl_team(team.id, self._config.season)
            result.files_written += team_result.files_written
            result.files_skipped += team_result.files_skipped
            result.errors += team_result.errors

        logger.info(
            "GameStatsCrawler complete: %d fetched, %d cached, %d errored.",
            result.files_written,
            result.files_skipped,
            result.errors,
        )
        return result

    def _crawl_team(self, team_id: str, season: str) -> CrawlResult:
        """Crawl box scores for all completed games for a single team.

        Args:
            team_id: GameChanger team UUID.
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
            game_stream_id = self._extract_game_stream_id(record)
            event_id = record.get("event_id", "<unknown>")

            if game_stream_id is None:
                logger.warning(
                    "Missing game_stream.id for event %s (team %s); skipping.",
                    event_id,
                    team_id,
                )
                result.errors += 1
                continue

            dest = self._game_path(team_id, season, game_stream_id)

            if dest.exists():
                logger.debug(
                    "Boxscore for game %s already cached; skipping.", game_stream_id
                )
                result.files_skipped += 1
                continue

            try:
                data = self._fetch_boxscore(game_stream_id)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(json.dumps(data, indent=2), encoding="utf-8")
                logger.info("Wrote boxscore %s -> %s.", game_stream_id, dest)
                result.files_written += 1
            except GameChangerAPIError as exc:
                logger.error(
                    "API error fetching boxscore for game_stream_id=%s event_id=%s: %s",
                    game_stream_id,
                    event_id,
                    exc,
                )
                result.errors += 1
            except Exception as exc:  # noqa: BLE001 -- broad catch intentional; log and continue
                logger.error(
                    "Unexpected error fetching boxscore for game_stream_id=%s event_id=%s: %s",
                    game_stream_id,
                    event_id,
                    exc,
                )
                result.errors += 1

        return result

    def _fetch_boxscore(self, game_stream_id: str) -> Any:
        """Fetch the raw boxscore response for a single game.

        Args:
            game_stream_id: The ``game_stream.id`` value from game-summaries.

        Returns:
            Parsed JSON response (dict with team-keyed entries).

        Raises:
            GameChangerAPIError: If the API returns an error response.
        """
        return self._client.get(
            f"/game-stream-processing/{game_stream_id}/boxscore",
            accept=_BOXSCORE_ACCEPT,
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

    def _extract_game_stream_id(self, record: dict[str, Any]) -> str | None:
        """Extract the ``game_stream.id`` from a game-summaries record.

        This is the path parameter for the boxscore endpoint.  It is distinct
        from ``event_id`` and ``game_stream.game_id``.

        Args:
            record: A single game-summaries record dict.

        Returns:
            The ``game_stream.id`` string, or ``None`` if absent.
        """
        game_stream = record.get("game_stream")
        if not isinstance(game_stream, dict):
            return None
        return game_stream.get("id")

    def _game_summaries_path(self, team_id: str, season: str) -> Path:
        """Return the path to the game-summaries file for a team.

        Args:
            team_id: GameChanger team UUID.
            season: Season label string.

        Returns:
            ``data/raw/{season}/teams/{team_id}/game_summaries.json``
        """
        return self._data_root / season / "teams" / team_id / "game_summaries.json"

    def _game_path(self, team_id: str, season: str, game_stream_id: str) -> Path:
        """Return the destination path for a single game's boxscore file.

        Args:
            team_id: GameChanger team UUID.
            season: Season label string.
            game_stream_id: The ``game_stream.id`` UUID.

        Returns:
            ``data/raw/{season}/teams/{team_id}/games/{game_stream_id}.json``
        """
        return self._data_root / season / "teams" / team_id / "games" / f"{game_stream_id}.json"
