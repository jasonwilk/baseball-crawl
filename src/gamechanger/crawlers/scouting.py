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

Raw responses are written to::

    data/raw/{season_id}/scouting/{public_id}/games.json
    data/raw/{season_id}/scouting/{public_id}/roster.json
    data/raw/{season_id}/scouting/{public_id}/boxscores/{game_stream_id}.json

The ``scouting_runs`` table tracks each run's status, counts, and timestamps.
Freshness checks in ``scout_all()`` skip opponents scouted within the
configured threshold.

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

import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.gamechanger.client import (
    CredentialExpiredError,
    ForbiddenError,
    GameChangerAPIError,
    GameChangerClient,
)
from src.gamechanger.crawlers import CrawlResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Accept headers
# ---------------------------------------------------------------------------

_PUBLIC_GAMES_ACCEPT = "application/vnd.gc.com.public_team_schedule_event:list+json; version=0.0.0"
_ROSTER_ACCEPT = "application/vnd.gc.com.public_player:list+json; version=0.0.0"
_BOXSCORE_ACCEPT = "application/vnd.gc.com.event_box_score+json; version=0.0.0"

# UUID pattern for detecting UUID keys in boxscore responses.
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Default data root: data/raw/ relative to the project root.
_DATA_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw"

# run_type value for full scouting runs (roster + boxscores).
_RUN_TYPE = "full"


class ScoutingCrawler:
    """Crawls opponent scouting data via GameChanger public and authenticated endpoints.

    Given an opponent's ``public_id`` slug, fetches their game schedule
    (unauthenticated), player roster, and per-game boxscores, writing raw JSON
    files to ``data/raw/{season_id}/scouting/{public_id}/``.  Tracks each run
    in the ``scouting_runs`` table for idempotency and freshness gating.

    Args:
        client: ``GameChangerClient`` used for API requests.  Public endpoints
            use ``client.get_public()``; authenticated endpoints use
            ``client.get()``.
        db: Open ``sqlite3.Connection`` with ``PRAGMA foreign_keys=ON`` set.
            The caller owns the connection lifecycle.
        freshness_hours: How many hours a completed scouting run is considered
            fresh.  Opponents scouted within this threshold are skipped by
            ``scout_all()``.  Defaults to 24.
        data_root: Root directory for raw data output.  Defaults to
            ``data/raw/`` relative to the project root.
        season_suffix: Suffix used when deriving season IDs from game timestamps.
            Defaults to ``"spring-hs"``.
    """

    def __init__(
        self,
        client: GameChangerClient,
        db: sqlite3.Connection,
        freshness_hours: int = 24,
        data_root: Path = _DATA_ROOT,
        season_suffix: str = "spring-hs",
    ) -> None:
        self._client = client
        self._db = db
        self._freshness_hours = freshness_hours
        self._data_root = data_root
        self._season_suffix = season_suffix

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scout_team(self, public_id: str, season_id: str | None = None) -> CrawlResult:
        """Fetch schedule, roster, and boxscores for one opponent team."""
        logger.info("Scouting team public_id=%s", public_id)
        now_str = _utcnow_iso()

        games_data = self._fetch_schedule(public_id)
        if games_data is None:
            return CrawlResult(errors=1)

        completed_games = [g for g in games_data if g.get("game_status") == "completed"]
        if not completed_games:
            logger.info("No completed games for public_id=%s; skipping.", public_id)
            return CrawlResult(files_skipped=1)

        if season_id is None:
            season_id = _derive_season_id(completed_games, self._season_suffix)
            logger.info("Derived season_id=%s for public_id=%s", season_id, public_id)

        team_id = self._ensure_team_row(public_id=public_id)
        self._ensure_season_row(season_id)
        self._upsert_run_start(team_id, season_id, now_str, len(completed_games))

        scouting_dir = self._data_root / season_id / "scouting" / public_id
        scouting_dir.mkdir(parents=True, exist_ok=True)
        (scouting_dir / "games.json").write_text(
            json.dumps(games_data, indent=2), encoding="utf-8"
        )

        roster_list = self._fetch_and_write_roster(public_id, scouting_dir)
        if roster_list is None:
            self._upsert_run_end(team_id, season_id, "failed", len(completed_games), 0, None, "Roster fetch failed")
            self._db.commit()
            return CrawlResult(errors=1)

        boxscores_dir = scouting_dir / "boxscores"
        boxscores_dir.mkdir(parents=True, exist_ok=True)
        games_crawled = self._fetch_boxscores(public_id, completed_games, boxscores_dir)

        return self._finalize_crawl_result(
            team_id, season_id, completed_games, games_crawled, len(roster_list)
        )

    def _finalize_crawl_result(
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

    def _fetch_and_write_roster(
        self, public_id: str, scouting_dir: Path
    ) -> list[dict[str, Any]] | None:
        """Fetch the roster and write ``roster.json``."""
        try:
            roster_data = self._client.get(
                f"/teams/public/{public_id}/players",
                accept=_ROSTER_ACCEPT,
            )
        except (CredentialExpiredError, ForbiddenError, GameChangerAPIError) as exc:
            logger.warning("Roster fetch failed for public_id=%s: %s", public_id, exc)
            return None
        roster_list: list[dict[str, Any]] = roster_data if isinstance(roster_data, list) else []
        (scouting_dir / "roster.json").write_text(
            json.dumps(roster_list, indent=2), encoding="utf-8"
        )
        logger.info("Wrote roster.json for public_id=%s (%d players).", public_id, len(roster_list))
        return roster_list

    def _fetch_boxscores(
        self,
        public_id: str,
        completed_games: list[dict[str, Any]],
        boxscores_dir: Path,
    ) -> int:
        """Fetch and write a boxscore file for each completed game."""
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
            except ForbiddenError as exc:  # ForbiddenError subclasses CredentialExpiredError; catch first
                logger.warning(
                    "Boxscore fetch failed game=%s public_id=%s: %s",
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
            (boxscores_dir / f"{game_stream_id}.json").write_text(
                json.dumps(boxscore, indent=2), encoding="utf-8"
            )
            games_crawled += 1
            self._record_uuid_from_boxscore(boxscore)
        logger.info(
            "Boxscores for public_id=%s: crawled=%d / found=%d.",
            public_id, games_crawled, len(completed_games),
        )
        return games_crawled

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

    def scout_all(self, season_id: str | None = None) -> CrawlResult:
        """Scout all opponents with a ``public_id`` that are not recently scouted.

        Queries ``opponent_links`` for all visible opponents with a ``public_id``
        and calls ``scout_team()`` for each one that has no completed scouting
        run within the freshness threshold.

        Args:
            season_id: Optional season slug override forwarded to
                ``scout_team()``.  When ``None``, each opponent derives its
                own season from its schedule.

        Returns:
            Aggregated ``CrawlResult`` across all opponents.
        """
        rows = self._db.execute(
            "SELECT DISTINCT public_id FROM opponent_links "
            "WHERE public_id IS NOT NULL AND is_hidden = 0"
        ).fetchall()

        total = CrawlResult()
        logger.info("scout_all: found %d opponents with a public_id.", len(rows))

        for (pub_id,) in rows:
            team_id = self._resolve_team_id(pub_id)
            if self._is_scouted_recently(team_id, season_id=season_id):
                logger.info(
                    "Skipping public_id=%s: scouted within %dh.", pub_id, self._freshness_hours
                )
                total.files_skipped += 1
                continue

            try:
                result = self.scout_team(pub_id, season_id)
            except CredentialExpiredError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("Unexpected error scouting public_id=%s: %s", pub_id, exc)
                total.errors += 1
                continue

            total.files_written += result.files_written
            total.files_skipped += result.files_skipped
            total.errors += result.errors

        return total

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _resolve_team_id(self, public_id: str) -> int | None:
        """Return the teams.id (INTEGER) for a given public_id slug, or None.

        SELECT-only; does not create any rows.

        Args:
            public_id: The opponent's public_id slug.

        Returns:
            INTEGER ``teams.id`` if found, else ``None``.
        """
        row = self._db.execute(
            "SELECT id FROM teams WHERE public_id = ? LIMIT 1",
            (public_id,),
        ).fetchone()
        return row[0] if row is not None else None

    def _ensure_team_row(
        self,
        public_id: str | None = None,
        gc_uuid: str | None = None,
    ) -> int:
        """Ensure a ``teams`` row exists and return its INTEGER primary key.

        Inserts a stub tracked row if none exists.  Uses the partial unique
        index on ``public_id`` or ``gc_uuid`` to detect an existing row.

        Args:
            public_id: The opponent's public_id slug (preferred lookup key).
            gc_uuid: The opponent's GC UUID (fallback lookup key).

        Returns:
            INTEGER ``teams.id`` for the row.

        Raises:
            ValueError: If both ``public_id`` and ``gc_uuid`` are ``None``.
        """
        if public_id is not None:
            cursor = self._db.execute(
                "INSERT OR IGNORE INTO teams (name, membership_type, public_id, is_active) "
                "VALUES (?, 'tracked', ?, 0)",
                (public_id, public_id),
            )
            if cursor.rowcount:
                return cursor.lastrowid
            row = self._db.execute(
                "SELECT id FROM teams WHERE public_id = ? LIMIT 1", (public_id,)
            ).fetchone()
            return row[0]

        if gc_uuid is not None:
            cursor = self._db.execute(
                "INSERT OR IGNORE INTO teams (name, membership_type, gc_uuid, is_active) "
                "VALUES (?, 'tracked', ?, 0)",
                (gc_uuid, gc_uuid),
            )
            if cursor.rowcount:
                return cursor.lastrowid
            row = self._db.execute(
                "SELECT id FROM teams WHERE gc_uuid = ? LIMIT 1", (gc_uuid,)
            ).fetchone()
            return row[0]

        raise ValueError("_ensure_team_row requires at least one of public_id or gc_uuid")

    def _ensure_season_row(self, season_id: str) -> None:
        """Ensure a ``seasons`` row exists for ``season_id``."""
        parts = season_id.split("-")
        year = 0
        for part in parts:
            if part.isdigit() and len(part) == 4:
                year = int(part)
                break
        self._db.execute(
            """
            INSERT INTO seasons (season_id, name, season_type, year)
            VALUES (?, ?, 'unknown', ?)
            ON CONFLICT(season_id) DO NOTHING
            """,
            (season_id, season_id, year),
        )

    def _is_scouted_recently(
        self, team_id: int | None, season_id: str | None = None
    ) -> bool:
        """Return True if this team has a completed scouting run within freshness_hours."""
        if team_id is None:
            return False
        if season_id is not None:
            row = self._db.execute(
                "SELECT last_checked FROM scouting_runs "
                "WHERE team_id = ? AND season_id = ? AND status = 'completed' "
                "ORDER BY last_checked DESC LIMIT 1",
                (team_id, season_id),
            ).fetchone()
        else:
            row = self._db.execute(
                "SELECT last_checked FROM scouting_runs "
                "WHERE team_id = ? AND status = 'completed' "
                "ORDER BY last_checked DESC LIMIT 1",
                (team_id,),
            ).fetchone()
        if row is None:
            return False
        try:
            last_checked = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - last_checked).total_seconds() / 3600
            return age_hours < self._freshness_hours
        except (ValueError, AttributeError):
            return False

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
        now = _utcnow_iso()
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

    def _record_uuid_from_boxscore(self, boxscore: dict[str, Any]) -> None:
        """Ensure a stub teams row exists for any UUID key discovered in the boxscore.

        When a boxscore response contains a UUID top-level key, this method
        inserts a stub tracked row for that UUID if one does not already exist.
        This is best-effort; errors are silently ignored.

        Args:
            boxscore: Top-level boxscore dict (keys are team identifiers).
        """
        for key in boxscore:
            if _UUID_RE.match(key):
                self._db.execute(
                    "INSERT OR IGNORE INTO teams (name, membership_type, gc_uuid, is_active) "
                    "VALUES (?, 'tracked', ?, 0)",
                    (key, key),
                )
                logger.debug("UUID opportunism: ensured stub row for gc_uuid=%s", key)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _derive_season_id(
    games: list[dict[str, Any]],
    season_suffix: str = "spring-hs",
) -> str:
    """Derive a season_id from the earliest game's start timestamp.

    Extracts the year from each game's ``start_ts`` field and returns
    ``"{year}-{season_suffix}"``.  Falls back to the current year if no valid
    timestamp is found.

    Args:
        games: List of completed game dicts from the public games endpoint.
        season_suffix: Suffix appended to the year (default ``"spring-hs"``).

    Returns:
        Season slug (e.g. ``"2025-spring-hs"``).
    """
    years: list[int] = []
    for game in games:
        ts = game.get("start_ts") or game.get("end_ts") or ""
        if ts and len(ts) >= 4 and ts[:4].isdigit():
            years.append(int(ts[:4]))
    if years:
        return f"{min(years)}-{season_suffix}"
    fallback_year = datetime.now(timezone.utc).year
    logger.warning("No valid start_ts found in games; falling back to year=%d.", fallback_year)
    return f"{fallback_year}-{season_suffix}"


def _utcnow_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
