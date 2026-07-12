"""Opponent scouting crawler for the baseball-crawl ingestion pipeline.

Fetches game schedule, player roster, and per-game boxscores for opponent
teams using public (unauthenticated) and authenticated GameChanger endpoints.

Scouting chain for each opponent::

    Step 1 -- Game schedule (public, no auth):
        GET /public/teams/{public_id}/games
        -> filters to game_status == "completed"
        -> extracts id field as game_stream_id

    Step 2 -- Roster (gc-token required):
        GET /teams/public/{public_id}/players

    Step 3 -- Boxscores (gc-token required):
        GET /game-stream-processing/{game_stream_id}/boxscore
        (one call per completed game)

Crawled data (games, roster, boxscores) is returned in memory as a
``ScoutingCrawlResult`` for the loader to consume directly -- no raw JSON
files are written to disk.

The ``scouting_runs`` table tracks each run's status, counts, and timestamps.

Usage::

    import sqlite3
    from src.gamechanger.client import GameChangerClient
    from src.gamechanger.crawlers.scouting import ScoutingCrawler

    client = GameChangerClient()
    conn = sqlite3.connect("./data/app.db")
    conn.execute("PRAGMA foreign_keys=ON;")
    crawler = ScoutingCrawler(client, conn)
    result = crawler.scout_team("8O8bTolVfb9A")
    print(result)
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.db.teams import ensure_team_row
from src.gamechanger.client import (
    CredentialExpiredError,
    ForbiddenError,
    GameChangerAPIError,
    GameChangerClient,
    RateLimitError,
)
from src.gamechanger.crawlers import CrawlResult
from src.gamechanger.loaders import ensure_season_row
from src.util.timezone import utcnow_iso

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-memory crawl result (E-220-05 / TN-12 / TN-14)
# ---------------------------------------------------------------------------


@dataclass
class ScoutingCrawlResult:
    """In-memory result from a scouting crawl.

    Replaces the disk-oriented ``CrawlResult`` for the scouting pipeline.
    Contains actual data (games, roster, boxscores) that the loader consumes
    directly without filesystem intermediation.

    Attributes:
        team_id: INTEGER PK of the scouted team in the ``teams`` table.
        season_id: The crawl-derived, year-only season_id (e.g. ``"2025"``).
        games: List of game dicts from the public games endpoint.
        roster: List of player dicts from the public roster endpoint.
        boxscores: Dict mapping game_stream_id to boxscore dict.
        games_crawled: Count of boxscores successfully fetched.
        errors: Count of errors encountered during crawl.
        skipped: True if no completed games were found (nothing to do).
    """

    team_id: int
    season_id: str
    public_id: str = ""
    games: list[dict[str, Any]] = field(default_factory=list)
    roster: list[dict[str, Any]] = field(default_factory=list)
    boxscores: dict[str, dict[str, Any]] = field(default_factory=dict)
    games_crawled: int = 0
    errors: int = 0
    skipped: bool = False

# ---------------------------------------------------------------------------
# Accept headers
# ---------------------------------------------------------------------------

_PUBLIC_GAMES_ACCEPT = "application/vnd.gc.com.public_team_schedule_event:list+json; version=0.0.0"
_ROSTER_ACCEPT = "application/vnd.gc.com.public_player:list+json; version=0.0.0"
_BOXSCORE_ACCEPT = "application/vnd.gc.com.event_box_score+json; version=0.0.0"


# run_type value for full scouting runs (roster + boxscores).
_RUN_TYPE = "full"


class ScoutingCrawler:
    """Crawls opponent scouting data via GameChanger public and authenticated endpoints.

    Given an opponent's ``public_id`` slug, fetches their game schedule
    (unauthenticated), player roster, and per-game boxscores, returning the
    crawled data in memory as a ``ScoutingCrawlResult``.  Tracks each run in
    the ``scouting_runs`` table for idempotency.

    Args:
        client: ``GameChangerClient`` used for API requests.  Public endpoints
            use ``client.get_public()``; authenticated endpoints use
            ``client.get()``.
        db: Open ``sqlite3.Connection`` with ``PRAGMA foreign_keys=ON`` set.
            The caller owns the connection lifecycle.
    """

    def __init__(
        self,
        client: GameChangerClient,
        db: sqlite3.Connection,
    ) -> None:
        self._client = client
        self._db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scout_team(self, public_id: str) -> ScoutingCrawlResult:
        """Fetch schedule, roster, and boxscores for one opponent team.

        Returns an in-memory ``ScoutingCrawlResult`` containing all crawled
        data.  No files are written to disk.  DB side effects (teams, seasons,
        scouting_runs) are preserved.
        """
        logger.info("Scouting team public_id=%s", public_id)
        now_str = utcnow_iso()

        games_data = self._fetch_schedule(public_id)
        if games_data is None:
            # Need a team_id for the result -- ensure row exists.
            team_id = self._ensure_team_row(public_id=public_id)
            return ScoutingCrawlResult(team_id=team_id, season_id="", public_id=public_id, errors=1)

        completed_games = [g for g in games_data if g.get("game_status") == "completed"]
        if not completed_games:
            logger.info("No completed games for public_id=%s; skipping.", public_id)
            team_id = self._ensure_team_row(public_id=public_id)
            return ScoutingCrawlResult(team_id=team_id, season_id="", public_id=public_id, skipped=True)

        season_id = _derive_season_id(completed_games)
        logger.info("Derived season_id=%s for public_id=%s", season_id, public_id)

        team_id = self._ensure_team_row(public_id=public_id)
        self._ensure_season_row(season_id)
        self._upsert_run_start(team_id, season_id, now_str, len(completed_games))

        roster_list = self._fetch_roster(public_id)
        if roster_list is None:
            self._upsert_run_end(team_id, season_id, "failed", len(completed_games), 0, None, "Roster fetch failed")
            self._db.commit()
            return ScoutingCrawlResult(team_id=team_id, season_id=season_id, public_id=public_id, errors=1)

        boxscores, games_crawled = self._fetch_boxscores_in_memory(public_id, completed_games)

        result = self._finalize_crawl(
            team_id, season_id, completed_games, games_crawled, len(roster_list)
        )

        return ScoutingCrawlResult(
            team_id=team_id,
            season_id=season_id,
            public_id=public_id,
            games=games_data,
            roster=roster_list,
            boxscores=boxscores,
            games_crawled=games_crawled,
            errors=result.errors,
        )

    def _finalize_crawl(
        self,
        team_id: int,
        season_id: str,
        completed_games: list[dict[str, Any]],
        games_crawled: int,
        roster_size: int,
    ) -> CrawlResult:
        """Write the end-of-crawl scouting_run status and return a CrawlResult."""
        games_found = len(completed_games)
        if games_crawled == 0:
            self._upsert_run_end(team_id, season_id, "failed", games_found, 0, roster_size, "All boxscore fetches failed")
            self._db.commit()
            return CrawlResult(errors=1)
        self._upsert_run_end(team_id, season_id, "completed", games_found, games_crawled, roster_size, None)
        self._db.commit()
        return CrawlResult(files_written=2 + games_crawled)

    # ------------------------------------------------------------------
    # Scouting chain helpers
    # ------------------------------------------------------------------

    def _fetch_schedule(self, public_id: str) -> list[dict[str, Any]] | None:
        """Fetch the game schedule via the public endpoint."""
        try:
            games_data = self._client.get_public(
                f"/public/teams/{public_id}/games",
                accept=_PUBLIC_GAMES_ACCEPT,
            )
        except (CredentialExpiredError, ForbiddenError, GameChangerAPIError) as exc:
            logger.warning("Schedule fetch failed for public_id=%s: %s", public_id, exc)
            return None
        if not isinstance(games_data, list):
            logger.warning(
                "Unexpected schedule type for public_id=%s: %s",
                public_id,
                type(games_data).__name__,
            )
            return None
        return games_data

    def _fetch_roster(
        self, public_id: str
    ) -> list[dict[str, Any]] | None:
        """Fetch the roster in memory (no file write)."""
        try:
            roster_data = self._client.get(
                f"/teams/public/{public_id}/players",
                accept=_ROSTER_ACCEPT,
            )
        except (CredentialExpiredError, ForbiddenError, GameChangerAPIError) as exc:
            logger.warning("Roster fetch failed for public_id=%s: %s", public_id, exc)
            return None
        roster_list: list[dict[str, Any]] = roster_data if isinstance(roster_data, list) else []
        logger.info("Fetched roster for public_id=%s (%d players).", public_id, len(roster_list))
        return roster_list

    def _fetch_boxscores_in_memory(
        self,
        public_id: str,
        completed_games: list[dict[str, Any]],
    ) -> tuple[dict[str, dict[str, Any]], int]:
        """Fetch boxscores and return them in memory (no file write).

        Returns:
            Tuple of ``(boxscores_dict, games_crawled)`` where
            ``boxscores_dict`` maps ``game_stream_id`` to boxscore dict.
        """
        boxscores: dict[str, dict[str, Any]] = {}
        games_crawled = 0
        for game in completed_games:
            game_stream_id = game.get("id")
            if not game_stream_id:
                logger.warning("Game missing 'id' for public_id=%s; skipping.", public_id)
                continue
            try:
                boxscore = self._client.get(
                    f"/game-stream-processing/{game_stream_id}/boxscore",
                    accept=_BOXSCORE_ACCEPT,
                )
            except ForbiddenError as exc:
                logger.warning(
                    "Boxscore fetch failed game=%s public_id=%s: %s",
                    game_stream_id, public_id, exc,
                )
                continue
            except RateLimitError as exc:
                # E-252-04 / TN-6: isolate a PER-GAME boxscore 429 so it skips
                # only this game -- the remaining games of the team still crawl
                # (the 429 no longer aborts the whole team crawl). This is the
                # per-game seam ONLY; team-level 429s (schedule/roster) are left
                # to propagate to morning-run's per-team seam (E-252-02) so the
                # systemic-429 escalation can observe recurring 429s. GC 429
                # behavior is UNOBSERVED (revisit if a real 429 is captured).
                logger.warning(
                    "Boxscore fetch rate-limited (429) game=%s public_id=%s: %s",
                    game_stream_id, public_id, exc,
                )
                continue
            except CredentialExpiredError:
                raise
            except GameChangerAPIError as exc:
                logger.warning(
                    "Boxscore fetch failed game=%s public_id=%s: %s",
                    game_stream_id, public_id, exc,
                )
                continue
            if not isinstance(boxscore, dict):
                logger.warning("Unexpected boxscore type game=%s: %s", game_stream_id, type(boxscore).__name__)
                continue
            boxscores[str(game_stream_id)] = boxscore
            games_crawled += 1
        logger.info(
            "Boxscores for public_id=%s: crawled=%d / found=%d.",
            public_id, games_crawled, len(completed_games),
        )
        return boxscores, games_crawled

    def update_run_load_status(
        self, team_id: int, season_id: str, status: str
    ) -> None:
        """Update scouting_runs.status after the load phase completes.

        Called by the CLI layer to transition from ``'running'`` (post-crawl)
        to ``'completed'`` (full pipeline success) or ``'failed'`` (load failure).

        Args:
            team_id: Team INTEGER primary key (``teams.id``).
            season_id: Season slug.
            status: New status string -- either ``'completed'`` or ``'failed'``.
        """
        self._db.execute(
            """
            UPDATE scouting_runs SET
                status       = ?,
                last_checked = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                completed_at = CASE WHEN ? = 'completed'
                                    THEN strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                                    ELSE NULL END
            WHERE team_id = ? AND season_id = ? AND run_type = ?
            """,
            (status, status, team_id, season_id, _RUN_TYPE),
        )
        self._db.commit()

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _ensure_team_row(
        self,
        public_id: str | None = None,
        gc_uuid: str | None = None,
    ) -> int:
        """Ensure a ``teams`` row exists and return its INTEGER primary key.

        Delegates to the shared ``ensure_team_row()`` dedup cascade.

        Args:
            public_id: The opponent's public_id slug (preferred lookup key).
            gc_uuid: The opponent's GC UUID (fallback lookup key).

        Returns:
            INTEGER ``teams.id`` for the row.

        Raises:
            ValueError: If both ``public_id`` and ``gc_uuid`` are ``None``.
        """
        if public_id is None and gc_uuid is None:
            raise ValueError("_ensure_team_row requires at least one of public_id or gc_uuid")
        return ensure_team_row(
            self._db,
            public_id=public_id,
            gc_uuid=gc_uuid,
            source="scouting",
        )

    def _ensure_season_row(self, season_id: str) -> None:
        """Ensure a ``seasons`` row exists for the year-only ``season_id``.

        Delegates to the canonical ``ensure_season_row``
        (src/gamechanger/loaders/__init__.py) so the crawler holds no private
        season-row INSERT. Both the live report path and the canonical helper
        thus write through one seam, eliminating the two-writer drift that this
        method's own INSERT used to risk. Inherits the canonical helper's
        fail-loud contract: a non-numeric ``season_id`` raises via ``int()``.
        """
        ensure_season_row(self._db, season_id)

    def _upsert_run_start(
        self,
        team_id: int,
        season_id: str,
        started_at: str,
        games_found: int,
    ) -> None:
        """Upsert a scouting_runs row with status='running'."""
        self._db.execute(
            """
            INSERT INTO scouting_runs
                (team_id, season_id, run_type, started_at, status, last_checked, games_found)
            VALUES (?, ?, ?, ?, 'running', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), ?)
            ON CONFLICT(team_id, season_id, run_type) DO UPDATE SET
                last_checked  = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                started_at    = excluded.started_at,
                status        = excluded.status,
                games_found   = excluded.games_found,
                games_crawled = NULL,
                players_found = NULL,
                error_message = NULL
            """,
            (team_id, season_id, _RUN_TYPE, started_at, games_found),
        )
        self._db.commit()

    def _upsert_run_end(
        self,
        team_id: int,
        season_id: str,
        status: str,
        games_found: int | None,
        games_crawled: int,
        players_found: int | None,
        error_message: str | None,
    ) -> None:
        """Update the scouting_run row with final status and counts."""
        now = utcnow_iso()
        completed_at = None if status == "running" else now
        self._db.execute(
            """
            UPDATE scouting_runs SET
                status        = ?,
                completed_at  = ?,
                games_found   = ?,
                games_crawled = ?,
                players_found = ?,
                error_message = ?,
                last_checked  = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE team_id = ? AND season_id = ? AND run_type = ?
            """,
            (
                status, completed_at, games_found, games_crawled,
                players_found, error_message,
                team_id, season_id, _RUN_TYPE,
            ),
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _derive_season_id(games: list[dict[str, Any]]) -> str:
    """Derive a year-only season_id from the earliest game's start timestamp.

    Extracts the year from each game's ``start_ts`` field and returns it as a
    string.  Falls back to the current year if no valid timestamp is found.

    Args:
        games: List of completed game dicts from the public games endpoint.

    Returns:
        Year-only season slug (e.g. ``"2025"``).
    """
    years: list[int] = []
    for game in games:
        ts = game.get("start_ts") or game.get("end_ts") or ""
        if ts and len(ts) >= 4 and ts[:4].isdigit():
            years.append(int(ts[:4]))
    if years:
        return str(min(years))
    fallback_year = datetime.now(timezone.utc).year
    logger.warning("No valid start_ts found in games; falling back to year=%d.", fallback_year)
    return str(fallback_year)
