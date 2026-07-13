"""Scouting spray chart loader for the baseball-crawl ingestion pipeline.

Inserts ball-in-play events into the ``spray_charts`` table for opponent teams
from in-memory player-stats payloads fetched by ``ScoutingSprayChartCrawler``.
The caller supplies an ``event_id`` -> payload mapping and the opponent's
``public_id``.

Key data decisions
------------------
- **Team resolution**: ``public_id`` → ``teams.id`` lookup (not ``gc_uuid``),
  because scouting data is keyed by the opponent's ``public_id``.
- **Idempotency**: a genuine re-run is short-circuited by the whole-game
  perspective gate in ``_load_game_data`` (returns a benign ``skipped=1``
  BEFORE any event is inserted), so re-running the same files produces zero
  new inserts. The row-level ``INSERT OR IGNORE`` is keyed on the migration-009
  UNIQUE(``event_gc_id``, ``perspective_team_id``, ``chart_type``) -- offense
  and defense for one event no longer collide (E-253-02). A collision reaching
  ``_insert_event`` (a distinct event repeated within one load) is therefore a
  real data anomaly, counted as an error and WARNING-logged -- NOT as an
  idempotent skip.
- **chart_type**: ``offense`` section → ``'offensive'``;
  ``defense`` section → ``'defensive'``.
- **Primary defender only**: only the first entry in ``defenders[]`` is stored
  for x/y/position/error.
- **Empty defenders**: over-the-fence HRs have an empty ``defenders[]`` array.
  These events are stored with NULL x, y, fielder_position, and error.
- **Missing x/y with defender present**: skip the event (log debug).
- **Null spray_chart_data**: entire game skipped gracefully with INFO log (AC-5).
- **season_id**: derived from team metadata, never from a path.
- **Unresolvable players**: players not found in ``team_rosters`` for either the
  home or away team are skipped entirely -- all their events are counted in
  ``LoadResult.skipped`` and no rows are inserted (no stub player, no spray row).
- **Per-game DEBUG summary**: when at least one player in a game is unresolvable,
  one DEBUG line is emitted with the count of skipped events and players.
- **Stub players**: players who ARE found in ``team_rosters`` but lack a ``players``
  row receive a stub row (first_name='Unknown', last_name='Unknown') before
  the spray row is inserted.
- **Game not in DB**: spray events for an unknown game_id are skipped at
  DEBUG level rather than causing an error (AC-7).  In a normal scouting
  pipeline run, game rows are loaded by the boxscore loader before this
  loader runs, so missing rows indicate an edge case (independent run or
  failed boxscore fetch).

Operator cleanup procedure (for removing previously misattributed rows)
-----------------------------------------------------------------------
If the database contains rows loaded before this fix was deployed, run::

    DELETE FROM spray_charts
    WHERE id IN (
        SELECT sc.id FROM spray_charts sc
        JOIN games g ON g.game_id = sc.game_id
        WHERE NOT EXISTS (
            SELECT 1 FROM team_rosters tr
            WHERE tr.player_id = sc.player_id
              AND tr.team_id IN (g.home_team_id, g.away_team_id)
              AND tr.season_id = sc.season_id
        )
    );

This query targets exactly the misattributed rows (players not in
``team_rosters`` for either game team) and is idempotent.  No reload is
required -- the loader's ``INSERT OR IGNORE`` will skip correctly-loaded rows
on any subsequent run.  To load rows for players that are now resolvable (e.g.
after roster data improves), delete the relevant rows and regenerate the
affected report (the reports generator re-runs the scouting spray load).

Usage::

    import sqlite3
    from src.db.paths import resolve_db_path
    from src.gamechanger.loaders.scouting_spray_loader import ScoutingSprayChartLoader

    conn = sqlite3.connect(str(resolve_db_path()))
    conn.execute("PRAGMA foreign_keys=ON;")
    loader = ScoutingSprayChartLoader(conn)
    result = loader.load_from_data({"event-id": player_stats_dict}, "opponentSlug")
    print(result)
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from src.db.players import ensure_player_row
from src.gamechanger.loaders import LoadResult, derive_season_id_for_team

logger = logging.getLogger(__name__)


class ScoutingSprayChartLoader:
    """Loads in-memory scouting spray chart payloads into ``spray_charts``.

    Parses the nested event structure of each game's player-stats payload and
    inserts rows using ``INSERT OR IGNORE`` on the migration-009 unique key.

    Unlike ``SprayChartLoader``, team resolution uses ``public_id`` (not
    ``gc_uuid``) because scouting spray data is keyed by the opponent's
    ``public_id``.

    Args:
        db: Open SQLite connection with foreign keys enabled.
    """

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def load_from_data(
        self,
        spray_data: dict[str, dict],
        public_id: str,
    ) -> LoadResult:
        """Load spray chart data from in-memory crawl results (E-220-10).

        Args:
            spray_data: Dict mapping ``event_id`` to player-stats response dict.
            public_id: The opponent's ``public_id`` slug (for team resolution).

        Returns:
            Aggregated ``LoadResult`` across all games.
        """
        team_id = self._resolve_team_id_by_public_id(public_id)
        if team_id is None:
            logger.warning(
                "Team public_id=%s not found in teams table; skipping spray load.",
                public_id,
            )
            return LoadResult()

        season_id, _ = derive_season_id_for_team(self._db, team_id)

        combined = LoadResult()
        for game_id, data in sorted(spray_data.items()):
            try:
                result = self._load_game_data(
                    data, game_id, team_id, public_id, season_id
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Unexpected error loading scouting spray game %s: %s",
                    game_id, exc,
                )
                self._db.rollback()
                result = LoadResult(errors=1)
            combined.loaded += result.loaded
            combined.skipped += result.skipped
            combined.errors += result.errors

        logger.info(
            "ScoutingSprayChartLoader.load_from_data: "
            "loaded=%d skipped=%d errors=%d",
            combined.loaded,
            combined.skipped,
            combined.errors,
        )
        return combined

    def _load_game_data(
        self,
        data: dict,
        game_id: str,
        team_id: int,
        public_id: str,
        season_id: str,
    ) -> LoadResult:
        """Load one game's spray chart data from an in-memory dict."""
        spray_data = data.get("spray_chart_data")
        if spray_data is None:
            logger.info(
                "spray_chart_data is null for game %s public_id=%s; skipping.",
                game_id, public_id,
            )
            return LoadResult()

        # Whole-game perspective gate: skip if spray data already loaded
        # for this game+perspective (mirrors plays_loader pattern, TN-3).
        # Performance optimization -- INSERT OR IGNORE is still correct without
        # this gate.  Limitation: if the first pass was partial (e.g., some
        # events skipped due to unresolvable players), retries will hit this
        # gate and skip the game.  To retry, delete the partial rows first:
        #   DELETE FROM spray_charts WHERE game_id=? AND perspective_team_id=?
        existing = self._db.execute(
            "SELECT 1 FROM spray_charts WHERE game_id = ? AND perspective_team_id = ? LIMIT 1",
            (game_id, team_id),
        ).fetchone()
        if existing is not None:
            logger.debug(
                "Spray data already loaded for game %s perspective %d; skipping.",
                game_id, team_id,
            )
            return LoadResult(skipped=1)

        game_row = self._db.execute(
            "SELECT home_team_id, away_team_id FROM games WHERE game_id = ?",
            (game_id,),
        ).fetchone()
        if game_row is None:
            logger.debug(
                "Game %s not found in games table for public_id=%s; skipping.",
                game_id, public_id,
            )
            return LoadResult()

        home_team_id, away_team_id = game_row

        if team_id not in (home_team_id, away_team_id):
            logger.warning(
                "Scouted team public_id=%s (id=%d) is not home or away for "
                "game %s; player team resolution may be unreliable.",
                public_id, team_id, game_id,
            )

        result = LoadResult()
        unresolvable_players = 0
        unresolvable_events = 0
        section_map = [("offense", "offensive"), ("defense", "defensive")]
        for section_key, chart_type in section_map:
            section = spray_data.get(section_key)
            if not section:
                continue
            for player_uuid, events in section.items():
                if not isinstance(events, list):
                    # A non-list ``events`` value is a malformed API response
                    # worth surfacing for data-quality follow-up, consistent with
                    # this loader's "log unexpected shapes, don't crash"
                    # convention: skip the entry, count it once as skipped.
                    logger.warning(
                        "Events for player %s in %s section is not a list; skipping.",
                        player_uuid, section_key,
                    )
                    result.skipped += 1
                    continue
                player_team_id = self._resolve_player_team_id(
                    player_uuid, home_team_id, away_team_id, season_id,
                )
                if player_team_id is None:
                    unresolvable_players += 1
                    unresolvable_events += len(events)
                    result.skipped += len(events)
                    continue
                for event in events:
                    r = self._insert_event(
                        event, game_id, player_uuid, player_team_id, chart_type,
                        season_id, team_id,
                    )
                    result.loaded += r.loaded
                    result.skipped += r.skipped
                    result.errors += r.errors

        if unresolvable_players > 0:
            logger.debug(
                "Game %s: skipped %d events for %d unresolvable players.",
                game_id, unresolvable_events, unresolvable_players,
            )

        self._db.commit()
        return result

    # -----------------------------------------------------------------------
    # Resolution helpers
    # -----------------------------------------------------------------------

    def _resolve_team_id_by_public_id(self, public_id: str) -> int | None:
        """Return the integer ``teams.id`` for a ``public_id``, or ``None``."""
        row = self._db.execute(
            "SELECT id FROM teams WHERE public_id = ? LIMIT 1",
            (public_id,),
        ).fetchone()
        return row[0] if row else None

    def _resolve_player_team_id(
        self,
        player_uuid: str,
        home_team_id: int,
        away_team_id: int,
        season_id: str,
    ) -> int | None:
        """Determine which team a player belongs to for this game.

        Checks ``team_rosters`` for home and away teams filtered by season.
        Returns ``None`` when the player is not found in either roster --
        the caller skips all events for that player rather than guessing.

        Args:
            player_uuid: GC player UUID from the API response.
            home_team_id: ``home_team_id`` from the games table.
            away_team_id: ``away_team_id`` from the games table.
            season_id: Season slug for roster lookup scoping.

        Returns:
            Integer ``teams.id`` for the player's team, or ``None`` if the
            player is not in ``team_rosters`` for either team.
        """
        row = self._db.execute(
            "SELECT team_id FROM team_rosters "
            "WHERE player_id = ? AND team_id IN (?, ?) AND season_id = ? LIMIT 1",
            (player_uuid, home_team_id, away_team_id, season_id),
        ).fetchone()
        return row[0] if row is not None else None

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
        perspective_team_id: int,
    ) -> LoadResult:
        """Insert a single scouting spray chart event.

        Args:
            event: Raw event dict from the API.
            game_id: ``games.game_id`` PK (= event_id filename stem).
            player_uuid: GC player UUID (spray chart key).
            team_id: Resolved integer ``teams.id``.
            chart_type: ``'offensive'`` or ``'defensive'``.
            season_id: Season slug derived from the team's metadata.
            perspective_team_id: INTEGER PK of the team whose API call produced
                this data.

        Returns:
            ``LoadResult(loaded=1)`` on insert, ``LoadResult(skipped=1)`` on
            duplicate or missing required fields.
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
                # Defender present but coordinates missing -- skip.
                logger.debug(
                    "Event %s has defender but no location x/y; skipping.",
                    event_gc_id,
                )
                return LoadResult(skipped=1)
            fielder_position = primary.get("position")
            error_raw = primary.get("error")
            error_int: int | None = (1 if error_raw else 0) if error_raw is not None else None
        else:
            # Empty defenders[] -- over-the-fence HR or similar.
            x = None
            y = None
            fielder_position = None
            error_int = None

        # FK-safe: ensure player row exists before inserting spray row.
        ensure_player_row(self._db, player_uuid, "Unknown", "Unknown")

        cursor = self._db.execute(
            """
            INSERT OR IGNORE INTO spray_charts (
                game_id, player_id, team_id, pitcher_id,
                chart_type, play_type, play_result,
                x, y, fielder_position, error,
                event_gc_id, created_at_ms, season_id,
                perspective_team_id
            ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                perspective_team_id,
            ),
        )
        if cursor.rowcount == 1:
            return LoadResult(loaded=1)
        # rowcount == 0: the INSERT OR IGNORE was suppressed by a UNIQUE
        # collision on (event_gc_id, perspective_team_id, chart_type) -- the
        # key widened in migration 009 (E-253-02) so offense and defense for
        # one event no longer collide.  This is NOT an idempotent skip: the
        # whole-game perspective gate in _load_game_data already short-circuits
        # a genuine re-run of an already-loaded game (returning a benign
        # skipped=1) BEFORE any event reaches here, so a collision at this point
        # means a DISTINCT event lost a key race against a sibling within THIS
        # load (e.g., the same event id repeated in one section).  Surface it as
        # an error rather than silently miscounting it as an idempotent skip
        # (E-253-02 AC-3).
        logger.warning(
            "Spray event %s (chart_type=%s) collided on "
            "UNIQUE(event_gc_id, perspective_team_id, chart_type) for game %s "
            "perspective %d; a distinct event was dropped -- not an idempotent "
            "skip.",
            event_gc_id,
            chart_type,
            game_id,
            perspective_team_id,
        )
        return LoadResult(errors=1)
