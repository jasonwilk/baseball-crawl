"""Plays loader for the baseball-crawl ingestion pipeline.

Reads cached plays JSON files written by ``PlaysCrawler`` and inserts
parsed play and event records into the ``plays`` and ``play_events``
database tables.

Expected file layout (written by PlaysCrawler)::

    data/raw/{season}/teams/{gc_uuid}/plays/{event_id}.json

The loader:

- Iterates over all ``*.json`` files in the plays directory
- Validates that each ``game_id`` exists in the ``games`` table (FK guard)
- Checks whole-game idempotency: skips games with existing plays rows
- Parses each game via ``PlaysParser.parse_game()``
- Creates stub player rows for unknown batter/pitcher IDs (FK-safe)
- Inserts all plays + events in a per-game transaction
- Isolates per-game errors: logs and skips, continues loading

Usage::

    import sqlite3
    from pathlib import Path
    from src.gamechanger.loaders.plays_loader import PlaysLoader
    from src.gamechanger.types import TeamRef

    conn = sqlite3.connect("./data/app.db")
    conn.execute("PRAGMA foreign_keys=ON;")
    ref = TeamRef(id=1, gc_uuid="abc-team-uuid")
    loader = PlaysLoader(conn, owned_team_ref=ref)
    result = loader.load_all(Path("data/raw/2025-spring-hs/teams/abc-team-uuid"))
    print(result)
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from src.db.players import ensure_player_row
from src.gamechanger.loaders import LoadResult
from src.gamechanger.parsers.plays_parser import ParsedPlay, PlaysParser
from src.gamechanger.types import TeamRef

logger = logging.getLogger(__name__)


class PlaysLoader:
    """Loads plays JSON files into the SQLite database.

    Reads all ``plays/{event_id}.json`` files in a team directory, parses
    each via ``PlaysParser``, and inserts the resulting records into the
    ``plays`` and ``play_events`` tables.

    Args:
        db: Open ``sqlite3.Connection`` with ``PRAGMA foreign_keys=ON`` set.
            The caller owns the connection lifecycle.
        owned_team_ref: ``TeamRef`` for the team that owns the data directory.
    """

    def __init__(
        self,
        db: sqlite3.Connection,
        owned_team_ref: TeamRef,
    ) -> None:
        self._db = db
        self._team_ref = owned_team_ref

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_all(self, team_dir: Path) -> LoadResult:
        """Load all plays files in a team directory.

        Reads each ``plays/{event_id}.json`` file, validates the game FK,
        checks whole-game idempotency, parses via ``PlaysParser``, and
        writes plays + events to the database.

        Args:
            team_dir: Path to ``data/raw/{season}/teams/{gc_uuid}/``.

        Returns:
            ``LoadResult`` with ``loaded`` = plays inserted,
            ``skipped`` = games skipped (idempotent or missing FK),
            ``errors`` = games with parse/insert errors.
        """
        plays_dir = team_dir / "plays"
        if not plays_dir.is_dir():
            logger.info("No plays directory at %s; nothing to load.", plays_dir)
            return LoadResult()

        total = LoadResult()
        for plays_path in sorted(plays_dir.glob("*.json")):
            game_id = plays_path.stem
            result = self._load_game(game_id, plays_path=plays_path)
            total.loaded += result.loaded
            total.skipped += result.skipped
            total.errors += result.errors

        logger.info(
            "Plays load complete for %s: loaded=%d skipped=%d errors=%d",
            team_dir,
            total.loaded,
            total.skipped,
            total.errors,
        )
        return total

    def load_payload(self, plays_by_game: dict[str, dict]) -> LoadResult:
        """Load a batch of in-memory plays payloads, keyed by game_id.

        Payload-first counterpart to :meth:`load_all`: applies the identical
        per-game logic (FK guard, whole-game idempotency, parse, per-game
        transaction, error isolation) to each already-fetched plays dict
        without any disk round-trip.

        Entries are iterated in sorted ``game_id`` order to mirror the
        deterministic ``sorted(glob)`` iteration of :meth:`load_all`.
        Falsy/empty entries (e.g. ``{}`` markers for games skipped upstream)
        are skipped, mirroring the generator's existing ``if data:`` guard.

        Args:
            plays_by_game: Mapping of ``game_id`` -> raw plays response dict.

        Returns:
            ``LoadResult`` with ``loaded`` = plays inserted,
            ``skipped`` = games skipped (idempotent or missing FK),
            ``errors`` = games with parse/insert errors.
        """
        total = LoadResult()
        for game_id in sorted(plays_by_game):
            raw_json = plays_by_game[game_id]
            if not raw_json:
                # Empty/{} entry -- nothing to load (mirrors load_all having
                # no file written for already-loaded/skipped games).
                continue
            result = self._load_game(game_id, raw_json=raw_json)
            total.loaded += result.loaded
            total.skipped += result.skipped
            total.errors += result.errors

        logger.info(
            "Plays payload load complete: loaded=%d skipped=%d errors=%d",
            total.loaded,
            total.skipped,
            total.errors,
        )
        return total

    # ------------------------------------------------------------------
    # Per-game loading
    # ------------------------------------------------------------------

    def _load_game(
        self,
        game_id: str,
        *,
        raw_json: dict[str, Any] | None = None,
        plays_path: Path | None = None,
    ) -> LoadResult:
        """Load plays for a single game from an in-memory dict or a file.

        Shared per-game core for both :meth:`load_all` (file path -- pass
        ``plays_path``) and :meth:`load_payload` (in-memory -- pass
        ``raw_json``).  Performs FK guard, idempotency check, parsing, and DB
        insertion within a per-game transaction.  Parse or insert errors are
        caught and logged (per-game error isolation).

        Exactly one of ``raw_json`` or ``plays_path`` must be provided.  When
        ``plays_path`` is given, the file is read lazily inside the parse
        try-block (after the FK guard and idempotency checks) so that read
        failures are isolated exactly as before.

        Args:
            game_id: The ``event_id`` (= ``games.game_id``).
            raw_json: Pre-fetched raw plays response dict (payload path).
            plays_path: Path to the plays JSON file (directory path).

        Returns:
            ``LoadResult`` for this game.
        """
        # Game FK guard -- verify game exists in games table.
        game_row = self._db.execute(
            "SELECT season_id, home_team_id, away_team_id FROM games WHERE game_id = ?",
            (game_id,),
        ).fetchone()

        if game_row is None:
            logger.warning(
                "Game %s not in games table; skipping plays load.", game_id,
            )
            return LoadResult(skipped=1)

        season_id, home_team_id, away_team_id = game_row

        # Whole-game idempotency -- skip if plays exist for this perspective.
        perspective_team_id = self._team_ref.id
        existing = self._db.execute(
            "SELECT 1 FROM plays WHERE game_id = ? AND perspective_team_id = ? LIMIT 1",
            (game_id, perspective_team_id),
        ).fetchone()

        if existing is not None:
            logger.debug(
                "Plays already loaded for game %s; skipping.", game_id,
            )
            return LoadResult(skipped=1)

        # Read (file path only) and parse the plays payload.
        try:
            if raw_json is None:
                raw_json = self._read_json(plays_path)
            parsed_plays = PlaysParser.parse_game(
                raw_json=raw_json,
                game_id=game_id,
                season_id=season_id,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
            )
        except Exception as exc:  # noqa: BLE001 -- per-game error isolation
            logger.error(
                "Parse error for game %s (%s): %s",
                game_id,
                plays_path if plays_path is not None else "payload",
                exc,
            )
            return LoadResult(errors=1)

        if not parsed_plays:
            logger.debug(
                "No plays parsed for game %s; nothing to insert.", game_id,
            )
            return LoadResult(skipped=1)

        # Per-game transaction -- all plays + events commit together.
        try:
            plays_inserted = self._insert_game_plays(parsed_plays, perspective_team_id)
            self._db.commit()
            return LoadResult(loaded=plays_inserted)
        except Exception as exc:  # noqa: BLE001 -- per-game error isolation
            logger.error(
                "Insert error for game %s: %s", game_id, exc,
            )
            self._db.rollback()
            return LoadResult(errors=1)

    # ------------------------------------------------------------------
    # DB operations
    # ------------------------------------------------------------------

    def _insert_game_plays(self, plays: list[ParsedPlay], perspective_team_id: int) -> int:
        """Insert all plays and their events for a single game.

        Ensures stub player rows exist for any unknown batter/pitcher IDs
        before inserting the play rows.

        Args:
            plays: List of ``ParsedPlay`` records from the parser.
            perspective_team_id: INTEGER PK of the team whose API call produced
                this play-by-play data.

        Returns:
            Count of plays inserted.
        """
        plays_inserted = 0

        for play in plays:
            # Ensure stub player rows for batter and pitcher.
            ensure_player_row(self._db, play.batter_id, "Unknown", "Unknown")
            if play.pitcher_id is not None:
                ensure_player_row(self._db, play.pitcher_id, "Unknown", "Unknown")

            # Insert the parent plays row.
            cursor = self._db.execute(
                """
                INSERT INTO plays (
                    game_id, play_order, inning, half,
                    season_id, batting_team_id,
                    batter_id, pitcher_id, outcome,
                    pitch_count, is_first_pitch_strike, is_qab,
                    home_score, away_score, did_score_change,
                    outs_after, did_outs_change,
                    perspective_team_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    play.game_id,
                    play.play_order,
                    play.inning,
                    play.half,
                    play.season_id,
                    play.batting_team_id,
                    play.batter_id,
                    play.pitcher_id,
                    play.outcome,
                    play.pitch_count,
                    play.is_first_pitch_strike,
                    play.is_qab,
                    play.home_score,
                    play.away_score,
                    play.did_score_change,
                    play.outs_after,
                    play.did_outs_change,
                    perspective_team_id,
                ),
            )
            play_id = cursor.lastrowid

            # Insert child play_events rows.
            for event in play.events:
                self._db.execute(
                    """
                    INSERT INTO play_events (
                        play_id, event_order, event_type,
                        pitch_result, is_first_pitch, raw_template
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        play_id,
                        event.event_order,
                        event.event_type,
                        event.pitch_result,
                        event.is_first_pitch,
                        event.raw_template,
                    ),
                )

            plays_inserted += 1

        return plays_inserted

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        """Read and parse a JSON file.

        Args:
            path: Path to the JSON file.

        Returns:
            Parsed JSON dict.

        Raises:
            json.JSONDecodeError: If the file contains invalid JSON.
            OSError: If the file cannot be read.
        """
        return json.loads(path.read_text(encoding="utf-8"))
