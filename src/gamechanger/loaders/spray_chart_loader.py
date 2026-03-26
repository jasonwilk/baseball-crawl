"""Spray chart loader for the baseball-crawl ingestion pipeline.

Reads player-stats JSON files written by the spray chart crawler and inserts
ball-in-play events into the ``spray_charts`` table.

Expected file layout (written by SprayChartCrawler)::

    data/raw/{season}/teams/{gc_uuid}/spray/{event_id}.json

The ``game_id`` (= ``event_id``) is inferred from the filename. The
``season_id`` and crawling team's ``gc_uuid`` are inferred from the path.

Key data decisions
------------------
- **Idempotency**: ``INSERT OR IGNORE`` keyed on ``event_gc_id`` (TN-6).
  Re-running the same files produces zero new inserts.
- **chart_type**: ``offense`` section → ``'offensive'``;
  ``defense`` section → ``'defensive'`` (TN-2).
- **Primary defender only**: only the first entry in ``defenders[]`` is stored
  for x/y/position/error (TN-2).
- **Empty defenders**: over-the-fence HRs have an empty ``defenders[]`` array.
  These events are stored with NULL x, y, fielder_position, and error (TN-4).
- **Missing x/y with defender present**: skip the event (log debug) rather
  than storing a partial coordinate (TN-2 / AC-5).
- **Null spray_chart_data**: entire game skipped gracefully (TN-12).
- **Stub players**: unknown player UUIDs receive a stub row
  (first_name='Unknown', last_name='Unknown') before the spray row (AC-6).
- **team_id resolution**: roster lookup against both home/away teams (TN-10).
  Players not found in either roster are assigned the opponent team's ID.

Usage::

    import sqlite3
    from pathlib import Path
    from src.gamechanger.loaders.spray_chart_loader import SprayChartLoader

    conn = sqlite3.connect("./data/app.db")
    conn.execute("PRAGMA foreign_keys=ON;")
    loader = SprayChartLoader(conn)
    result = loader.load_dir(Path("data/raw/2026-spring-hs/teams/abc-uuid/spray"))
    print(result)
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from src.gamechanger.loaders import LoadResult

logger = logging.getLogger(__name__)


class SprayChartLoader:
    """Loads spray chart JSON files into the ``spray_charts`` table.

    Iterates all ``*.json`` files in a team's ``spray/`` directory,
    parses the nested event structure, and inserts rows using
    ``INSERT OR IGNORE`` on ``event_gc_id``.

    Args:
        db: Open SQLite connection with foreign keys enabled.
    """

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def load_dir(self, spray_dir: Path) -> LoadResult:
        """Load all spray chart JSON files from a team's spray directory.

        Infers ``gc_uuid`` and ``season_id`` from the directory path::

            data/raw/{season}/teams/{gc_uuid}/spray/

        Args:
            spray_dir: Path to the ``spray/`` directory for one team/season.

        Returns:
            Aggregated ``LoadResult`` across all game files.
        """
        gc_uuid = spray_dir.parent.name
        season_id = spray_dir.parent.parent.parent.name

        combined = LoadResult()
        json_files = sorted(spray_dir.glob("*.json"))
        if not json_files:
            logger.debug("No spray chart files found in %s.", spray_dir)
            return combined

        for json_file in json_files:
            game_id = json_file.stem
            try:
                result = self._load_game_file(json_file, game_id, gc_uuid, season_id)
            except Exception as exc:  # noqa: BLE001 -- log and continue
                logger.error(
                    "Unexpected error loading spray file %s: %s", json_file, exc
                )
                self._db.rollback()
                result = LoadResult(errors=1)
            combined.loaded += result.loaded
            combined.skipped += result.skipped
            combined.errors += result.errors

        logger.info(
            "SprayChartLoader %s: loaded=%d skipped=%d errors=%d",
            spray_dir,
            combined.loaded,
            combined.skipped,
            combined.errors,
        )
        return combined

    def _load_game_file(
        self, path: Path, game_id: str, gc_uuid: str, season_id: str
    ) -> LoadResult:
        """Parse and load one game's spray chart JSON.

        Args:
            path: Path to the spray chart JSON file.
            game_id: Event ID extracted from the filename (``games.game_id`` PK).
            gc_uuid: GC UUID of the crawling team (from path).
            season_id: Season slug from the file path (e.g. ``"2026-spring-hs"``).

        Returns:
            ``LoadResult`` for this game's events.
        """
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

        spray_data = data.get("spray_chart_data")
        if spray_data is None:
            logger.info(
                "spray_chart_data is null for game %s; skipping.", game_id
            )
            return LoadResult()

        # Resolve crawling team's integer PK from gc_uuid (TN-10 step 1).
        crawling_team_id = self._resolve_team_id_by_gc_uuid(gc_uuid)
        if crawling_team_id is None:
            logger.warning(
                "Crawling team gc_uuid=%s not found in teams table; skipping game %s.",
                gc_uuid,
                game_id,
            )
            return LoadResult()

        # Look up game to get home/away teams (TN-10 step 2).
        game_row = self._db.execute(
            "SELECT home_team_id, away_team_id FROM games WHERE game_id = ?",
            (game_id,),
        ).fetchone()
        if game_row is None:
            logger.warning(
                "Game %s not found in games table; skipping spray load.", game_id
            )
            return LoadResult()
        home_team_id, away_team_id = game_row

        # Opponent team = whichever side the crawling team is NOT on (TN-10 step 4).
        if crawling_team_id == home_team_id:
            opponent_team_id = away_team_id
        elif crawling_team_id == away_team_id:
            opponent_team_id = home_team_id
        else:
            logger.warning(
                "Crawling team gc_uuid=%s (id=%d) is not home or away for game %s; "
                "using away_team_id=%d as opponent fallback.",
                gc_uuid,
                crawling_team_id,
                game_id,
                away_team_id,
            )
            opponent_team_id = away_team_id

        result = LoadResult()
        section_map = [
            ("offense", "offensive"),
            ("defense", "defensive"),
        ]
        for section_key, chart_type in section_map:
            section = spray_data.get(section_key)
            if not section:
                continue
            for player_uuid, events in section.items():
                if not isinstance(events, list):
                    logger.warning(
                        "Events for player %s in %s section is not a list; skipping.",
                        player_uuid,
                        section_key,
                    )
                    result.skipped += 1
                    continue
                team_id = self._resolve_player_team_id(
                    player_uuid,
                    home_team_id,
                    away_team_id,
                    season_id,
                    opponent_team_id,
                )
                for event in events:
                    r = self._insert_event(
                        event, game_id, player_uuid, team_id, chart_type, season_id
                    )
                    result.loaded += r.loaded
                    result.skipped += r.skipped
                    result.errors += r.errors

        self._db.commit()
        return result

    # -----------------------------------------------------------------------
    # Resolution helpers
    # -----------------------------------------------------------------------

    def _resolve_team_id_by_gc_uuid(self, gc_uuid: str) -> int | None:
        """Return the integer teams.id for a gc_uuid, or None if not found."""
        row = self._db.execute(
            "SELECT id FROM teams WHERE gc_uuid = ?", (gc_uuid,)
        ).fetchone()
        return row[0] if row else None

    def _resolve_player_team_id(
        self,
        player_uuid: str,
        home_team_id: int,
        away_team_id: int,
        season_id: str,
        fallback_team_id: int,
    ) -> int:
        """Determine which team a player belongs to for this game (TN-10 step 3-4).

        Checks ``team_rosters`` for home and away teams filtered by season.
        Falls back to ``fallback_team_id`` (opponent) when not found in either.

        Args:
            player_uuid: GC player UUID from the API response.
            home_team_id: home_team_id from the games table.
            away_team_id: away_team_id from the games table.
            season_id: Season slug for roster lookup scoping.
            fallback_team_id: Team ID to assign when player is in neither roster.

        Returns:
            Integer teams.id for the player's team.
        """
        row = self._db.execute(
            "SELECT team_id FROM team_rosters "
            "WHERE player_id = ? AND team_id IN (?, ?) AND season_id = ? LIMIT 1",
            (player_uuid, home_team_id, away_team_id, season_id),
        ).fetchone()
        if row is not None:
            return row[0]

        logger.warning(
            "Player %s not found in team_rosters for season %s; "
            "assigning opponent team_id=%d as best-guess.",
            player_uuid,
            season_id,
            fallback_team_id,
        )
        return fallback_team_id

    def _ensure_stub_player(self, player_id: str) -> None:
        """Ensure a player row exists; insert stub if not present (AC-6).

        Logs WARNING when a stub is created (FK-safe orphan handling).

        Args:
            player_id: GameChanger player UUID.
        """
        existing = self._db.execute(
            "SELECT 1 FROM players WHERE player_id = ?", (player_id,)
        ).fetchone()
        if existing is None:
            logger.warning(
                "Unknown player_id=%s; inserting stub row "
                "(first_name='Unknown', last_name='Unknown').",
                player_id,
            )
            self._db.execute(
                "INSERT INTO players (player_id, first_name, last_name) "
                "VALUES (?, 'Unknown', 'Unknown') "
                "ON CONFLICT(player_id) DO NOTHING",
                (player_id,),
            )

    # -----------------------------------------------------------------------
    # Event insertion
    # -----------------------------------------------------------------------

    def _insert_event(
        self,
        event: dict[str, Any],
        game_id: str,
        player_uuid: str,
        team_id: int,
        chart_type: str,
        season_id: str,
    ) -> LoadResult:
        """Insert a single spray chart event.

        Args:
            event: Raw event dict from the API.
            game_id: games.game_id PK (= event_id filename).
            player_uuid: GC player UUID (spray chart key).
            team_id: Resolved integer teams.id.
            chart_type: ``'offensive'`` or ``'defensive'``.
            season_id: Season slug from the file path.

        Returns:
            ``LoadResult(loaded=1)`` on insert, ``LoadResult(skipped=1)`` on
            duplicate, ``LoadResult(skipped=1)`` on missing required fields.
        """
        event_gc_id = event.get("id")
        if not event_gc_id:
            logger.warning(
                "Spray event missing id field for player %s game %s; skipping.",
                player_uuid,
                game_id,
            )
            return LoadResult(skipped=1)

        attrs = event.get("attributes") or {}
        play_result = attrs.get("playResult")
        play_type = attrs.get("playType")
        created_at_ms = event.get("createdAt")

        defenders = attrs.get("defenders") or []
        if defenders:
            primary = defenders[0]
            loc = primary.get("location") or {}
            x = loc.get("x")
            y = loc.get("y")
            if x is None or y is None:
                # Defender present but coordinates missing -- skip (AC-5).
                logger.debug(
                    "Event %s has defender but no location x/y; skipping.",
                    event_gc_id,
                )
                return LoadResult(skipped=1)
            fielder_position = primary.get("position")
            error_raw = primary.get("error")
            error_int: int | None = (1 if error_raw else 0) if error_raw is not None else None
        else:
            # Empty defenders[] -- over-the-fence HR or similar (TN-4).
            # Store with NULL x, y, fielder_position, error.
            x = None
            y = None
            fielder_position = None
            error_int = None

        # FK-safe: ensure player row exists before inserting spray row.
        self._ensure_stub_player(player_uuid)

        cursor = self._db.execute(
            """
            INSERT OR IGNORE INTO spray_charts (
                game_id, player_id, team_id, pitcher_id,
                chart_type, play_type, play_result,
                x, y, fielder_position, error,
                event_gc_id, created_at_ms, season_id
            ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                game_id,
                player_uuid,
                team_id,
                chart_type,
                play_type,
                play_result,
                x,
                y,
                fielder_position,
                error_int,
                event_gc_id,
                created_at_ms,
                season_id,
            ),
        )
        if cursor.rowcount == 1:
            return LoadResult(loaded=1)
        # INSERT OR IGNORE: row already existed -- idempotent skip.
        return LoadResult(skipped=1)
