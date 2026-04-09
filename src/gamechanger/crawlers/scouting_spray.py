"""Scouting spray chart crawler for the baseball-crawl ingestion pipeline.

Fetches player-stats (spray chart) data for completed games on each scouted
opponent's schedule, writing one file per game to::

    data/raw/{season_id}/scouting/{public_id}/spray/{event_id}.json

The crawler reads the already-cached ``games.json`` written by
``ScoutingCrawler``, resolves each opponent's ``gc_uuid`` from the database,
and calls::

    GET /teams/{gc_uuid}/schedule/events/{event_id}/player-stats

for each completed game not already cached.

**Endpoint behavior is asymmetric** (verified 2026-03-29): the player-stats
endpoint is team-scoped.  The *owning team* (whose schedule contains the
game) receives both teams' spray data; a *participant* (played in the game
but does not own the schedule entry) receives only its own data.  Therefore
the ``gc_uuid`` used in the request path must belong to the scouted team
itself -- using an opponent's UUID would return only the opponent's data.

When an opponent has no ``gc_uuid``, the crawler cannot call the endpoint and
skips that team with an INFO log.

Idempotency is existence-only: if the file already exists it is skipped
regardless of age.  Files are written even when ``spray_chart_data`` is null
(scorekeeper did not record) so the crawler does not re-fetch the same game.

Rate limiting is handled automatically by the ``GameChangerClient`` session
(minimum 1-second delay with jitter).

Usage::

    import sqlite3
    from src.gamechanger.client import GameChangerClient
    from src.gamechanger.crawlers.scouting_spray import ScoutingSprayChartCrawler

    client = GameChangerClient()
    conn = sqlite3.connect("./data/app.db")
    conn.execute("PRAGMA foreign_keys=ON;")
    crawler = ScoutingSprayChartCrawler(client, conn)
    result = crawler.crawl_all()
    print(result)
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.gamechanger.client import CredentialExpiredError, GameChangerAPIError, GameChangerClient
from src.gamechanger.crawlers import CrawlResult

logger = logging.getLogger(__name__)

_PLAYER_STATS_ACCEPT = "application/json, text/plain, */*"


@dataclass
class SprayCrawlResult:
    """In-memory result from a scouting spray crawl.

    Contains the spray chart data (player-stats responses) keyed by event_id,
    plus metadata about what was crawled.

    Attributes:
        spray_data: Dict mapping event_id to player-stats response dict.
        games_crawled: Number of games successfully fetched.
        games_skipped: Number of games skipped (already cached or no data).
        errors: Number of errors encountered.
    """

    spray_data: dict[str, dict[str, Any]] = field(default_factory=dict)
    games_crawled: int = 0
    games_skipped: int = 0
    errors: int = 0
_DATA_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw"
_COMPLETED_STATUS = "completed"


class ScoutingSprayChartCrawler:
    """Crawls player-stats (spray chart) data for completed games of scouted opponents.

    Reads cached ``games.json`` files (written by ``ScoutingCrawler``) from
    disk, identifies completed games, looks up each opponent's ``gc_uuid``
    from the database, and fetches player-stats via the GameChanger
    authenticated API.

    Args:
        client: Authenticated ``GameChangerClient`` used for all HTTP requests.
        db: Open ``sqlite3.Connection`` with ``PRAGMA foreign_keys=ON`` set.
            The caller owns the connection lifecycle.
        data_root: Root directory for raw data output.  Defaults to
            ``data/raw/`` relative to the project root.
    """

    def __init__(
        self,
        client: GameChangerClient,
        db: sqlite3.Connection,
        data_root: Path = _DATA_ROOT,
    ) -> None:
        self._client = client
        self._db = db
        self._data_root = data_root

    def crawl_team(
        self,
        public_id: str,
        games_data: list[dict[str, Any]],
        season_id: str | None = None,
        gc_uuid: str | None = None,
    ) -> SprayCrawlResult:
        """Crawl spray data for a single opponent (in-memory, E-220 C2-B).

        Returns a ``SprayCrawlResult`` with spray data in memory.  No files
        are written to disk and no disk reads occur -- ``games_data`` is the
        sole source of game discovery.

        Args:
            public_id: The opponent's ``public_id`` slug.
            games_data: In-memory games list (REQUIRED).  Pass
                ``ScoutingCrawlResult.games`` from the parent scouting crawl.
            season_id: Season slug (used only for logging).
            gc_uuid: The opponent's ``gc_uuid``.  When ``None``, looked up
                from the database.

        Returns:
            ``SprayCrawlResult`` with spray data keyed by event_id.
        """
        if gc_uuid is None:
            gc_uuid = self._lookup_gc_uuid(public_id)

        if gc_uuid is None:
            logger.info(
                "No gc_uuid for opponent public_id=%s; skipping spray crawl.",
                public_id,
            )
            return SprayCrawlResult()

        completed = [g for g in games_data if g.get("game_status") == _COMPLETED_STATUS]
        if not completed:
            logger.info(
                "No completed games for public_id=%s; skipping spray crawl.",
                public_id,
            )
            return SprayCrawlResult()

        return self._fetch_spray_in_memory(public_id, gc_uuid, completed)

    def _fetch_spray_in_memory(
        self,
        public_id: str,
        gc_uuid: str,
        completed_games: list[dict[str, Any]],
    ) -> SprayCrawlResult:
        """Fetch spray chart data for completed games and return in-memory.

        No files are written to disk.

        Args:
            public_id: The opponent's ``public_id`` slug.
            gc_uuid: The opponent's GameChanger UUID (for the API call).
            completed_games: List of completed game dicts.

        Returns:
            ``SprayCrawlResult`` with spray data and counts.
        """
        result = SprayCrawlResult()

        for game in completed_games:
            event_id = game.get("id")
            if not event_id:
                logger.warning(
                    "Game missing 'id' for public_id=%s; skipping.",
                    public_id,
                )
                result.errors += 1
                continue

            try:
                data = self._client.get(
                    f"/teams/{gc_uuid}/schedule/events/{event_id}/player-stats",
                    accept=_PLAYER_STATS_ACCEPT,
                )
                result.spray_data[str(event_id)] = data
                result.games_crawled += 1
            except CredentialExpiredError:
                raise
            except GameChangerAPIError as exc:
                logger.error(
                    "API error fetching player-stats for event_id=%s public_id=%s: %s",
                    event_id,
                    public_id,
                    exc,
                )
                result.errors += 1
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Unexpected error fetching player-stats for event_id=%s public_id=%s: %s",
                    event_id,
                    public_id,
                    exc,
                )
                result.errors += 1

        return result

    def _lookup_gc_uuid(self, public_id: str) -> str | None:
        """Return the ``gc_uuid`` for an opponent by ``public_id``, or ``None``.

        Uses the ``teams.public_id`` UNIQUE index for the lookup.

        Args:
            public_id: The opponent's ``public_id`` slug.

        Returns:
            The ``gc_uuid`` string if the row exists and ``gc_uuid`` is
            non-NULL, else ``None``.
        """
        row = self._db.execute(
            "SELECT gc_uuid FROM teams WHERE public_id = ? LIMIT 1",
            (public_id,),
        ).fetchone()
        if row is None:
            return None
        return row[0]  # May be NULL if gc_uuid IS NULL
