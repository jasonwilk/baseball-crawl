"""Scouting spray chart crawler for the baseball-crawl ingestion pipeline.

Fetches player-stats (spray chart) data for completed games on each scouted
opponent's schedule, writing one file per game to::

    data/raw/{season_id}/scouting/{public_id}/spray/{event_id}.json

The crawler reads the already-cached ``games.json`` written by
``ScoutingCrawler``, resolves each opponent's ``gc_uuid`` from the database,
and calls::

    GET /teams/{gc_uuid}/schedule/events/{event_id}/player-stats

for each completed game not already cached.  The endpoint returns both teams'
spray data in a single call; the full response is saved and team-separation
happens in the loader (E-163-02).

The ``gc_uuid`` lookup uses ``SELECT gc_uuid FROM teams WHERE public_id = ?``
(``teams.public_id`` is UNIQUE).  When an opponent has no ``gc_uuid``, the
crawler falls back to extracting per-game opponent UUIDs from cached boxscore
files in ``data/raw/{season_id}/scouting/{public_id}/boxscores/``.  Each
boxscore JSON has two top-level keys: the scouted team's ``public_id`` slug
and the other team's ``gc_uuid``.  The spray endpoint returns both teams'
data regardless of which team's UUID is in the path, so using the opponent's
UUID produces complete spray data.  If no boxscores are cached either, the
opponent is skipped with an INFO log.

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
import re
import sqlite3
from pathlib import Path
from typing import Any

from src.gamechanger.client import CredentialExpiredError, GameChangerAPIError, GameChangerClient
from src.gamechanger.crawlers import CrawlResult

logger = logging.getLogger(__name__)

_PLAYER_STATS_ACCEPT = "application/json, text/plain, */*"
_DATA_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw"
_COMPLETED_STATUS = "completed"
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


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

    def crawl_all(self, season_id: str | None = None) -> CrawlResult:
        """Crawl spray data for all opponents that have a public_id.

        Discovers opponents from two sources via UNION:

        1. ``opponent_links`` rows with ``is_hidden = 0`` and a non-NULL
           ``public_id`` (opponents discovered via schedule seeding).
        2. Tracked teams (``membership_type = 'tracked'``) with a non-NULL
           ``public_id`` that have NO ``opponent_links`` row at all (teams
           added directly via the admin "generate report" flow).

        Teams with *only* ``is_hidden = 1`` rows in ``opponent_links`` are
        excluded: branch 1 filters on ``is_hidden = 0``, and branch 2's
        ``NOT EXISTS`` matches *any* ``opponent_links`` row regardless of
        ``is_hidden``.  If a ``public_id`` has both hidden and visible rows
        (possible when multiple member teams share an opponent), branch 1
        still includes it via the visible row -- this is per-link visibility,
        not global suppression.  UNION deduplicates teams that appear in
        both sources.

        ``CredentialExpiredError`` propagates immediately; other exceptions
        per opponent are caught, logged, and counted.

        Args:
            season_id: When provided, only process the games.json file for
                       this specific season.  When ``None``, process all
                       seasons found on disk.

        Returns:
            Aggregated ``CrawlResult`` across all opponents.
        """
        rows = self._db.execute(
            "SELECT DISTINCT public_id FROM opponent_links "
            "WHERE public_id IS NOT NULL AND is_hidden = 0 "
            "UNION "
            "SELECT t.public_id FROM teams t "
            "WHERE t.membership_type = 'tracked' "
            "AND t.public_id IS NOT NULL "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM opponent_links ol "
            "  WHERE ol.public_id = t.public_id"
            ")"
        ).fetchall()

        total = CrawlResult()
        logger.info(
            "ScoutingSprayChartCrawler: found %d opponents with a public_id.",
            len(rows),
        )

        for (public_id,) in rows:
            try:
                result = self.crawl_team(public_id, season_id=season_id)
            except CredentialExpiredError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Unexpected error crawling spray for public_id=%s: %s",
                    public_id,
                    exc,
                )
                total.errors += 1
                continue

            total.files_written += result.files_written
            total.files_skipped += result.files_skipped
            total.errors += result.errors

        logger.info(
            "ScoutingSprayChartCrawler complete: %d fetched, %d cached, %d errored.",
            total.files_written,
            total.files_skipped,
            total.errors,
        )
        return total

    def crawl_team(
        self,
        public_id: str,
        season_id: str | None = None,
        gc_uuid: str | None = None,
    ) -> CrawlResult:
        """Crawl spray data for a single opponent.

        Looks up the opponent's ``gc_uuid`` from the database unless
        ``gc_uuid`` is provided directly (bypasses the lookup).  When
        ``gc_uuid`` is available, fetches player-stats using that UUID for
        all completed games.  When ``gc_uuid`` is NULL, falls back to
        extracting per-game opponent UUIDs from cached boxscore files and
        uses those for the spray endpoint calls.  If neither ``gc_uuid`` nor
        boxscore UUIDs are available, logs an INFO message and returns an
        empty result.

        Args:
            public_id: The opponent's ``public_id`` slug.
            season_id: When provided, only process the games.json file for
                       this specific season.  When ``None``, process all
                       seasons found on disk.
            gc_uuid: When provided, skip the database lookup and use this
                     value directly.  Useful when the caller has already
                     resolved the ``gc_uuid``.

        Returns:
            ``CrawlResult`` for this opponent's games.
        """
        if gc_uuid is None:
            gc_uuid = self._lookup_gc_uuid(public_id)

        if season_id is not None:
            season_globs = [season_id]
        else:
            # Discover all seasons that have scouting data for this opponent.
            season_dirs = sorted(
                p.parent.parent.parent.name
                for p in self._data_root.glob(f"*/scouting/{public_id}/games.json")
            )
            season_globs = season_dirs if season_dirs else []

        if not season_globs:
            logger.warning(
                "No games.json found for public_id=%s in %s; skipping.",
                public_id,
                self._data_root,
            )
            return CrawlResult()

        # If gc_uuid is available, use the direct path for all seasons.
        if gc_uuid is not None:
            result = CrawlResult()
            for sid in season_globs:
                games_file = self._data_root / sid / "scouting" / public_id / "games.json"
                if not games_file.exists():
                    continue
                partial = self._crawl_team_season(public_id, gc_uuid, games_file, sid)
                result.files_written += partial.files_written
                result.files_skipped += partial.files_skipped
                result.errors += partial.errors
            return result

        # Fallback: gc_uuid is NULL. Extract per-game UUIDs from cached
        # boxscore files (the other team's UUID in each boxscore).
        result = CrawlResult()
        any_uuid_found = False
        for sid in season_globs:
            uuid_map = self._build_boxscore_uuid_map(public_id, sid)
            if not uuid_map:
                continue
            any_uuid_found = True
            games_file = self._data_root / sid / "scouting" / public_id / "games.json"
            if not games_file.exists():
                continue
            partial = self._crawl_team_season_with_uuid_map(
                public_id, uuid_map, games_file, sid,
            )
            result.files_written += partial.files_written
            result.files_skipped += partial.files_skipped
            result.errors += partial.errors

        if not any_uuid_found:
            logger.info(
                "No gc_uuid and no boxscore UUIDs for opponent public_id=%s; "
                "skipping spray crawl.",
                public_id,
            )

        return result

    def _crawl_team_season(
        self,
        public_id: str,
        gc_uuid: str,
        games_file: Path,
        season_id: str,
    ) -> CrawlResult:
        """Fetch spray data for one opponent in one season.

        Reads ``games_file``, filters to completed games, and fetches
        player-stats for any game whose spray file does not already exist.
        ``CredentialExpiredError`` propagates immediately.  Other
        ``GameChangerAPIError`` exceptions are caught, logged, and counted.

        Args:
            public_id: The opponent's ``public_id`` slug (used for file paths).
            gc_uuid: The opponent's GameChanger UUID (used for the API call).
            games_file: Path to the cached ``games.json`` file.
            season_id: Season label extracted from the file path.

        Returns:
            ``CrawlResult`` for this season's games.
        """
        result = CrawlResult()

        games_data = self._load_games(games_file)
        completed = [g for g in games_data if g.get("game_status") == _COMPLETED_STATUS]

        if not completed:
            logger.info(
                "No completed games for public_id=%s season=%s; skipping.",
                public_id,
                season_id,
            )
            return result

        spray_dir = self._data_root / season_id / "scouting" / public_id / "spray"

        for game in completed:
            # The public-endpoint 'id' field is the event_id used by the
            # authenticated player-stats endpoint (confirmed by api-scout).
            event_id = game.get("id")
            if not event_id:
                logger.warning(
                    "Game missing 'id' for public_id=%s season=%s; skipping.",
                    public_id,
                    season_id,
                )
                result.errors += 1
                continue

            dest = spray_dir / f"{event_id}.json"

            if dest.exists():
                logger.debug(
                    "Scouting spray file for game %s already cached; skipping.",
                    event_id,
                )
                result.files_skipped += 1
                continue

            try:
                data = self._client.get(
                    f"/teams/{gc_uuid}/schedule/events/{event_id}/player-stats",
                    accept=_PLAYER_STATS_ACCEPT,
                )
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(json.dumps(data, indent=2), encoding="utf-8")
                logger.info(
                    "Wrote scouting spray chart event_id=%s -> %s.",
                    event_id,
                    dest,
                )
                result.files_written += 1
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
            except Exception as exc:  # noqa: BLE001 -- broad catch intentional; log and continue
                logger.error(
                    "Unexpected error fetching player-stats for event_id=%s public_id=%s: %s",
                    event_id,
                    public_id,
                    exc,
                )
                result.errors += 1

        return result

    def _build_boxscore_uuid_map(
        self,
        public_id: str,
        season_id: str,
    ) -> dict[str, str]:
        """Build a mapping of event_id -> opponent gc_uuid from cached boxscore files.

        Each scouting boxscore JSON has two top-level keys: one is the scouted
        team's ``public_id`` slug (not a UUID), the other is the opponent's
        ``gc_uuid`` (matches UUID regex).  This extracts the UUID key for each
        boxscore file.

        Args:
            public_id: The scouted team's ``public_id`` slug.
            season_id: Season label (e.g., ``"2026-spring-hs"``).

        Returns:
            Dict mapping ``event_id`` (boxscore filename stem) to the opponent's
            gc_uuid.  Empty if no boxscore files exist or none contain a UUID key.
        """
        boxscores_dir = self._data_root / season_id / "scouting" / public_id / "boxscores"
        if not boxscores_dir.is_dir():
            return {}

        uuid_map: dict[str, str] = {}
        for bs_path in boxscores_dir.glob("*.json"):
            event_id = bs_path.stem
            try:
                with bs_path.open(encoding="utf-8") as fh:
                    boxscore = json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                logger.debug(
                    "Could not read boxscore %s for UUID extraction: %s",
                    bs_path,
                    exc,
                )
                continue

            if not isinstance(boxscore, dict):
                continue

            for key in boxscore:
                # Defensive: guard against theoretical UUID-formatted public_id
                if _UUID_RE.match(key) and key != public_id:
                    uuid_map[event_id] = key
                    break

        if uuid_map:
            logger.info(
                "Extracted %d opponent UUIDs from boxscores for public_id=%s season=%s.",
                len(uuid_map),
                public_id,
                season_id,
            )
        return uuid_map

    def _crawl_team_season_with_uuid_map(
        self,
        public_id: str,
        uuid_map: dict[str, str],
        games_file: Path,
        season_id: str,
    ) -> CrawlResult:
        """Fetch spray data using per-game UUIDs from boxscore extraction.

        Similar to ``_crawl_team_season`` but instead of using a single
        ``gc_uuid`` for all games, looks up each game's UUID from the
        ``uuid_map``.  Games without a UUID in the map are skipped silently
        (they simply had no boxscore cached).

        Args:
            public_id: The opponent's ``public_id`` slug (used for file paths).
            uuid_map: Mapping of ``event_id`` to the opponent's gc_uuid for
                      that specific game.
            games_file: Path to the cached ``games.json`` file.
            season_id: Season label extracted from the file path.

        Returns:
            ``CrawlResult`` for this season's games.
        """
        result = CrawlResult()

        games_data = self._load_games(games_file)
        completed = [g for g in games_data if g.get("game_status") == _COMPLETED_STATUS]

        if not completed:
            return result

        spray_dir = self._data_root / season_id / "scouting" / public_id / "spray"

        for game in completed:
            event_id = game.get("id")
            if not event_id:
                logger.warning(
                    "Game missing 'id' for public_id=%s season=%s; skipping.",
                    public_id,
                    season_id,
                )
                result.errors += 1
                continue

            game_uuid = uuid_map.get(event_id)
            if game_uuid is None:
                # No boxscore cached for this game -- skip silently.
                continue

            dest = spray_dir / f"{event_id}.json"

            if dest.exists():
                logger.debug(
                    "Scouting spray file for game %s already cached; skipping.",
                    event_id,
                )
                result.files_skipped += 1
                continue

            try:
                data = self._client.get(
                    f"/teams/{game_uuid}/schedule/events/{event_id}/player-stats",
                    accept=_PLAYER_STATS_ACCEPT,
                )
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(json.dumps(data, indent=2), encoding="utf-8")
                logger.info(
                    "Wrote scouting spray chart (fallback) event_id=%s -> %s.",
                    event_id,
                    dest,
                )
                result.files_written += 1
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

    def _load_games(self, path: Path) -> list[dict[str, Any]]:
        """Load and parse a ``games.json`` file.

        Args:
            path: Path to the ``games.json`` file.

        Returns:
            List of game records, or an empty list on parse failure.
        """
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            logger.warning(
                "games.json at %s is not a list (got %s); treating as empty.",
                path,
                type(raw).__name__,
            )
            return []
        return raw

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
