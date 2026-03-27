"""Schedule loader -- loads upcoming (not-yet-played) games from schedule.json.

Reads the crawled ``schedule.json`` file for each member team, filters to
actual game events that are not canceled, resolves opponent team IDs via the
``opponent_links`` table (or creates stub teams), and upserts game rows with
``status='scheduled'`` and NULL scores.

When a game completes and the ``GameLoader`` subsequently upserts the same
``game_id`` with ``status='completed'`` and actual scores, the existing
``ON CONFLICT(game_id) DO UPDATE`` naturally upgrades the row.

Expected file layout (written by ScheduleCrawler)::

    data/raw/{season}/teams/{team_id}/schedule.json

Usage::

    import sqlite3
    from pathlib import Path
    from src.gamechanger.loaders.schedule_loader import ScheduleLoader
    from src.gamechanger.types import TeamRef

    conn = sqlite3.connect("./data/app.db")
    conn.execute("PRAGMA foreign_keys=ON;")
    team_ref = TeamRef(id=1, gc_uuid="abc-uuid")
    loader = ScheduleLoader(conn, season_id="2025", owned_team_ref=team_ref)
    result = loader.load_file(Path("data/raw/2025/teams/abc-uuid/schedule.json"))
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from src.db.teams import ensure_team_row
from src.gamechanger.loaders import LoadResult, extract_year_from_season_id
from src.gamechanger.types import TeamRef

logger = logging.getLogger(__name__)


class ScheduleLoader:
    """Loads scheduled (upcoming) games from schedule.json into the games table.

    Args:
        db: Open ``sqlite3.Connection`` with ``PRAGMA foreign_keys=ON`` set.
        season_id: Season slug used as FK in all inserts (e.g. ``'2025'``).
        owned_team_ref: ``TeamRef`` for the team that owns the schedule data.
    """

    def __init__(
        self,
        db: sqlite3.Connection,
        season_id: str,
        owned_team_ref: TeamRef,
    ) -> None:
        self._db = db
        self._season_id = season_id
        self._team_ref = owned_team_ref

    def load_file(self, schedule_path: Path) -> LoadResult:
        """Load scheduled games from a schedule.json file.

        Filters to game events that are not canceled, resolves opponent IDs,
        and upserts game rows with ``status='scheduled'``.

        Args:
            schedule_path: Path to ``schedule.json``.

        Returns:
            ``LoadResult`` with counts of loaded, skipped, and errored records.
        """
        if not schedule_path.exists():
            logger.warning("Schedule file not found at %s; skipping.", schedule_path)
            return LoadResult()

        try:
            with schedule_path.open(encoding="utf-8") as fh:
                raw = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read %s: %s", schedule_path, exc)
            return LoadResult(errors=1)

        if not isinstance(raw, list):
            logger.error(
                "Expected JSON array in %s, got %s",
                schedule_path,
                type(raw).__name__,
            )
            return LoadResult(errors=1)

        self._ensure_season_row()

        result = LoadResult()
        for item in raw:
            event = item.get("event") or {}
            pregame = item.get("pregame_data")

            # Filter: only game events
            if event.get("event_type") != "game":
                continue

            # Filter: skip canceled events
            if event.get("status") == "canceled":
                continue

            # Must have pregame_data for opponent info
            if not pregame:
                logger.warning(
                    "Game event %s has no pregame_data; skipping.",
                    event.get("id"),
                )
                result.skipped += 1
                continue

            try:
                self._load_scheduled_game(event, pregame)
                result.loaded += 1
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Failed to load scheduled game %s: %s",
                    event.get("id"),
                    exc,
                )
                result.errors += 1

        self._db.commit()
        logger.info(
            "Schedule load complete for %s: loaded=%d skipped=%d errors=%d",
            schedule_path,
            result.loaded,
            result.skipped,
            result.errors,
        )
        return result

    def _load_scheduled_game(self, event: dict, pregame: dict) -> None:
        """Parse and upsert a single scheduled game.

        Args:
            event: The ``event`` object from schedule.json.
            pregame: The ``pregame_data`` object from schedule.json.
        """
        game_id = event.get("id")
        if not game_id:
            raise ValueError("Event missing 'id' field")

        # Extract game date from event.start
        game_date = self._extract_game_date(event)

        # Resolve opponent team ID
        opponent_root_team_id = pregame.get("opponent_id")
        opponent_name = pregame.get("opponent_name")
        opp_team_id = self._resolve_opponent(opponent_root_team_id, opponent_name)

        # Determine home/away assignment
        home_away = pregame.get("home_away")
        own_team_id = self._team_ref.id

        if home_away == "away":
            home_team_id = opp_team_id
            away_team_id = own_team_id
        else:
            # "home" or null -- our team is home by convention
            home_team_id = own_team_id
            away_team_id = opp_team_id

        # Upsert game row with scheduled status and NULL scores.
        # Only update if the existing row is also 'scheduled' -- do not
        # downgrade a 'completed' row back to 'scheduled'.
        self._db.execute(
            """
            INSERT INTO games
                (game_id, season_id, game_date, home_team_id, away_team_id,
                 home_score, away_score, status)
            VALUES (?, ?, ?, ?, ?, NULL, NULL, 'scheduled')
            ON CONFLICT(game_id) DO UPDATE SET
                game_date    = excluded.game_date,
                home_team_id = excluded.home_team_id,
                away_team_id = excluded.away_team_id,
                home_score   = CASE WHEN games.status = 'completed'
                                    THEN games.home_score
                                    ELSE excluded.home_score END,
                away_score   = CASE WHEN games.status = 'completed'
                                    THEN games.away_score
                                    ELSE excluded.away_score END,
                status       = CASE WHEN games.status = 'completed'
                                    THEN games.status
                                    ELSE excluded.status END
            """,
            (game_id, self._season_id, game_date, home_team_id, away_team_id),
        )

        # Upsert team_opponents junction row (AC-6)
        if opp_team_id != own_team_id:
            first_seen_year = extract_year_from_season_id(self._season_id) or 0
            self._db.execute(
                """
                INSERT INTO team_opponents (our_team_id, opponent_team_id, first_seen_year)
                VALUES (?, ?, ?)
                ON CONFLICT(our_team_id, opponent_team_id) DO NOTHING
                """,
                (own_team_id, opp_team_id, first_seen_year),
            )

        logger.debug(
            "Upserted scheduled game %s: %s vs %s on %s (home_away=%s)",
            game_id,
            home_team_id,
            away_team_id,
            game_date,
            home_away,
        )

    def _extract_game_date(self, event: dict) -> str:
        """Extract the game date from an event's start field.

        Handles both timed events (``start.datetime``) and full-day events
        (``start.date``).

        Args:
            event: The event object from schedule.json.

        Returns:
            ISO date string (YYYY-MM-DD).
        """
        start = event.get("start") or {}
        # Timed event: {"datetime": "2025-04-26T16:00:00.000Z"}
        dt = start.get("datetime")
        if dt:
            return dt[:10]
        # Full-day event: {"date": "2025-04-26"}
        date_val = start.get("date")
        if date_val:
            return date_val[:10]
        logger.warning(
            "Event %s has no start.datetime or start.date; using fallback date.",
            event.get("id"),
        )
        return "1900-01-01"

    def _resolve_opponent(
        self,
        root_team_id: str | None,
        opponent_name: str | None,
    ) -> int:
        """Resolve an opponent to a teams(id) integer PK.

        Resolution chain (per TN-2):
        1. Look up opponent_links by our_team_id + root_team_id
        2. If resolved_team_id is not NULL -> use it
        3. If resolved_team_id is NULL (name-only) -> find or create stub team

        Args:
            root_team_id: The ``pregame_data.opponent_id`` value (root_team_id
                namespace, NOT gc_uuid).
            opponent_name: Human-readable opponent name.

        Returns:
            INTEGER PK from the ``teams`` table.
        """
        if root_team_id:
            # Step 1: Check opponent_links
            row = self._db.execute(
                """
                SELECT resolved_team_id FROM opponent_links
                WHERE our_team_id = ? AND root_team_id = ?
                """,
                (self._team_ref.id, root_team_id),
            ).fetchone()

            if row and row[0] is not None:
                # Step 2: resolved_team_id exists
                return row[0]

        # Step 3: Find or create stub team by name
        name = opponent_name or root_team_id or "Unknown Opponent"
        return self._find_or_create_stub_team(name)

    def _find_or_create_stub_team(self, name: str) -> int:
        """Find an existing team by name or create a stub team row.

        Delegates to the shared ``ensure_team_row()`` dedup cascade.

        Args:
            name: Team name to search for or create.

        Returns:
            INTEGER PK from the ``teams`` table.
        """
        season_year = extract_year_from_season_id(self._season_id)
        return ensure_team_row(
            self._db,
            name=name,
            season_year=season_year,
            source="schedule",
        )

    def _ensure_season_row(self) -> None:
        """Ensure a seasons row exists for the configured season_id."""
        year = extract_year_from_season_id(self._season_id) or 0
        self._db.execute(
            """
            INSERT INTO seasons (season_id, name, season_type, year)
            VALUES (?, ?, 'unknown', ?)
            ON CONFLICT(season_id) DO NOTHING
            """,
            (self._season_id, self._season_id, year),
        )
