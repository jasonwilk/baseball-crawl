"""Season stats loader for the baseball-crawl ingestion pipeline.

Reads ``stats.json`` files (written by the season-stats crawler) and upserts
per-player season batting and pitching records into the SQLite database.

Expected file path convention::

    data/raw/{season_id}/teams/{team_id}/stats.json

The ``team_id`` and ``season_id`` are inferred from the path.

Response shape (from ``GET /teams/{team_id}/season-stats``)::

    {
        "id": "<team_uuid>",
        "team_id": "<team_uuid>",
        "stats_data": {
            "players": {
                "<player_uuid>": {
                    "stats": {
                        "offense": { ... },   # batting stats; absent for pitcher-only
                        "defense": { ... },   # pitching + fielding; absent for DH-only
                        "general": { ... }    # GP, shared
                    }
                }
            },
            ...
        }
    }

Usage::

    import sqlite3
    from pathlib import Path
    from src.gamechanger.loaders.season_stats_loader import SeasonStatsLoader

    conn = sqlite3.connect("./data/app.db")
    conn.execute("PRAGMA foreign_keys=ON;")
    loader = SeasonStatsLoader(conn)
    result = loader.load_file(Path("data/raw/2025/teams/abc-123/stats.json"))
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


def _ip_to_ip_outs(ip: float | int | None) -> int | None:
    """Convert API ``IP`` (decimal innings) to ``ip_outs`` (integer outs).

    The API represents innings pitched as a decimal where the fractional part
    is a true decimal fraction of an inning (e.g. 8.333... = 8⅓ innings = 25
    outs).  The schema stores ``ip_outs`` as integer total outs.

    Args:
        ip: Raw ``IP`` value from the API (float or int), or ``None``.

    Returns:
        Total outs as an integer, or ``None`` if input is ``None``.
    """
    if ip is None:
        return None
    return round(ip * 3)


class SeasonStatsLoader:
    """Loads a season stats JSON file into the SQLite database.

    Upserts player season batting stats into ``player_season_batting`` and
    pitching stats into ``player_season_pitching``.  Split columns (home/away,
    vs L/R) are always NULL because the season-stats API does not provide them.

    Before inserting stat rows, ensures FK prerequisite rows exist for
    ``teams`` and ``seasons``.  Orphaned player IDs (not in ``players`` table)
    receive a stub row (``first_name='Unknown'``, ``last_name='Unknown'``).

    Args:
        db: Open ``sqlite3.Connection`` with ``PRAGMA foreign_keys=ON`` set.
            The caller owns the connection lifecycle.
    """

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def load_file(self, path: Path) -> LoadResult:
        """Load a season stats JSON file into the database.

        Infers ``team_id`` and ``season_id`` from the file path using the
        convention ``data/raw/{season_id}/teams/{team_id}/stats.json``.

        Args:
            path: Absolute or relative path to the ``stats.json`` file.

        Returns:
            A ``LoadResult`` summarising records loaded, skipped, and errors.
        """
        team_id, season_id = self._infer_ids_from_path(path)
        logger.info(
            "Loading season stats file: %s (team=%s, season=%s)", path, team_id, season_id
        )

        data = self._read_json(path)
        if data is None:
            return LoadResult(errors=1)

        players_by_uuid: dict[str, Any] = (
            data.get("stats_data", {}).get("players", {})
        )

        if not isinstance(players_by_uuid, dict):
            logger.error(
                "Expected stats_data.players to be a dict in %s, got %s",
                path,
                type(players_by_uuid).__name__,
            )
            return LoadResult(errors=1)

        # Ensure FK prerequisite rows before any stat inserts.
        self._ensure_team_row(team_id)
        self._ensure_season_row(season_id)

        result = LoadResult()
        for player_id, player_data in players_by_uuid.items():
            if not player_id:
                logger.warning("Encountered empty player_id key in %s; skipping.", path)
                result.skipped += 1
                continue
            try:
                loaded = self._load_player(player_id, player_data, team_id, season_id)
                result.loaded += loaded
                if loaded == 0:
                    result.skipped += 1
            except sqlite3.Error as exc:
                logger.error(
                    "Database error loading season stats for player %s team %s: %s",
                    player_id,
                    team_id,
                    exc,
                )
                result.errors += 1

        self._db.commit()
        logger.info(
            "Season stats load complete: loaded=%d skipped=%d errors=%d",
            result.loaded,
            result.skipped,
            result.errors,
        )
        return result

    # ------------------------------------------------------------------
    # Per-player helpers
    # ------------------------------------------------------------------

    def _load_player(
        self,
        player_id: str,
        player_data: Any,
        team_id: str,
        season_id: str,
    ) -> int:
        """Upsert batting and/or pitching season stats for a single player.

        Args:
            player_id: GameChanger player UUID.
            player_data: Dict with ``stats.offense`` and/or ``stats.defense``.
            team_id: GameChanger team UUID.
            season_id: Season slug.

        Returns:
            Number of stat rows upserted (0, 1, or 2 -- one per table).
        """
        if not isinstance(player_data, dict):
            logger.warning(
                "Player data for %s is not a dict; skipping.", player_id
            )
            return 0

        stats = player_data.get("stats", {}) or {}
        offense = stats.get("offense")
        defense = stats.get("defense")

        has_offense = isinstance(offense, dict) and bool(offense)
        has_defense = isinstance(defense, dict) and bool(defense)

        if not has_offense and not has_defense:
            logger.debug(
                "No offense or defense stats for player %s; skipping.", player_id
            )
            return 0

        # AC-4: ensure player stub exists before inserting FK-referencing rows.
        self._ensure_player_row(player_id)

        rows_upserted = 0

        if has_offense:
            self._upsert_batting(player_id, team_id, season_id, offense)  # type: ignore[arg-type]
            rows_upserted += 1

        if has_defense and self._is_pitcher(defense):  # type: ignore[arg-type]
            self._upsert_pitching(player_id, team_id, season_id, defense)  # type: ignore[arg-type]
            rows_upserted += 1

        return rows_upserted

    def _is_pitcher(self, defense: dict[str, Any]) -> bool:
        """Return True if the defense stats object includes pitching data.

        Uses ``GP:P`` (games played as pitcher) as the discriminator.  If it
        is present and > 0, the player pitched.  Fielding-only players have
        ``GP:P`` absent or 0.

        Args:
            defense: Defense stats dict from the API.

        Returns:
            ``True`` if the player has pitching stats to load.
        """
        gp_p = defense.get("GP:P", 0)
        try:
            return int(gp_p) > 0
        except (TypeError, ValueError):
            return False

    # ------------------------------------------------------------------
    # Batting upsert
    # ------------------------------------------------------------------

    def _upsert_batting(
        self,
        player_id: str,
        team_id: str,
        season_id: str,
        offense: dict[str, Any],
    ) -> None:
        """Upsert a player_season_batting row.

        All split columns are NULL -- the season-stats API does not provide
        home/away or left/right pitcher splits.

        Args:
            player_id: GameChanger player UUID.
            team_id: GameChanger team UUID.
            season_id: Season slug.
            offense: Offense stats dict from the API.
        """
        self._db.execute(
            """
            INSERT INTO player_season_batting (
                player_id, team_id, season_id,
                games, ab, h, doubles, triples, hr, rbi, bb, so, sb
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(player_id, team_id, season_id) DO UPDATE SET
                games   = excluded.games,
                ab      = excluded.ab,
                h       = excluded.h,
                doubles = excluded.doubles,
                triples = excluded.triples,
                hr      = excluded.hr,
                rbi     = excluded.rbi,
                bb      = excluded.bb,
                so      = excluded.so,
                sb      = excluded.sb
            """,
            (
                player_id,
                team_id,
                season_id,
                offense.get("GP"),
                offense.get("AB"),
                offense.get("H"),
                offense.get("2B"),
                offense.get("3B"),
                offense.get("HR"),
                offense.get("RBI"),
                offense.get("BB"),
                offense.get("SO"),
                offense.get("SB"),
            ),
        )
        logger.debug(
            "Upserted batting: player=%s team=%s season=%s",
            player_id, team_id, season_id,
        )

    # ------------------------------------------------------------------
    # Pitching upsert
    # ------------------------------------------------------------------

    def _upsert_pitching(
        self,
        player_id: str,
        team_id: str,
        season_id: str,
        defense: dict[str, Any],
    ) -> None:
        """Upsert a player_season_pitching row.

        Converts ``IP`` (float) to ``ip_outs`` (integer outs).  All split
        columns are NULL -- the season-stats API does not provide splits.

        Args:
            player_id: GameChanger player UUID.
            team_id: GameChanger team UUID.
            season_id: Season slug.
            defense: Defense stats dict from the API.
        """
        raw_ip = defense.get("IP")
        ip_outs = _ip_to_ip_outs(raw_ip)

        self._db.execute(
            """
            INSERT INTO player_season_pitching (
                player_id, team_id, season_id,
                games, ip_outs, h, er, bb, so, hr, pitches, strikes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(player_id, team_id, season_id) DO UPDATE SET
                games   = excluded.games,
                ip_outs = excluded.ip_outs,
                h       = excluded.h,
                er      = excluded.er,
                bb      = excluded.bb,
                so      = excluded.so,
                hr      = excluded.hr,
                pitches = excluded.pitches,
                strikes = excluded.strikes
            """,
            (
                player_id,
                team_id,
                season_id,
                defense.get("GP:P"),
                ip_outs,
                defense.get("H"),
                defense.get("ER"),
                defense.get("BB"),
                defense.get("SO"),
                defense.get("HR"),
                defense.get("#P"),
                defense.get("TS"),
            ),
        )
        logger.debug(
            "Upserted pitching: player=%s team=%s season=%s ip_outs=%s",
            player_id, team_id, season_id, ip_outs,
        )

    # ------------------------------------------------------------------
    # FK prerequisite helpers (mirrors RosterLoader pattern)
    # ------------------------------------------------------------------

    def _ensure_player_row(self, player_id: str) -> None:
        """Ensure a ``players`` row exists for ``player_id``.

        Inserts a stub row (``first_name='Unknown'``, ``last_name='Unknown'``)
        if none exists, logging a WARNING.  Does nothing if already present.

        Args:
            player_id: GameChanger player UUID.
        """
        existing = self._db.execute(
            "SELECT 1 FROM players WHERE player_id = ?", (player_id,)
        ).fetchone()

        if existing is None:
            logger.warning(
                "Player %s not found in players table; inserting stub row.", player_id
            )
            self._db.execute(
                """
                INSERT INTO players (player_id, first_name, last_name)
                VALUES (?, 'Unknown', 'Unknown')
                ON CONFLICT(player_id) DO NOTHING
                """,
                (player_id,),
            )

    def _ensure_team_row(self, team_id: str) -> None:
        """Ensure a ``teams`` row exists for ``team_id``.

        Inserts a stub row if none exists.  Does nothing if already present.

        Args:
            team_id: GameChanger team UUID.
        """
        self._db.execute(
            """
            INSERT INTO teams (team_id, name, is_owned, is_active)
            VALUES (?, ?, 0, 0)
            ON CONFLICT(team_id) DO NOTHING
            """,
            (team_id, team_id),
        )
        logger.debug("Ensured teams row for team_id=%s", team_id)

    def _ensure_season_row(self, season_id: str) -> None:
        """Ensure a ``seasons`` row exists for ``season_id``.

        Inserts a stub row if none exists.  Does nothing if already present.

        Args:
            season_id: Season slug (e.g. ``'2025'`` or ``'2026-spring-hs'``).
        """
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
        logger.debug("Ensured seasons row for season_id=%s", season_id)

    # ------------------------------------------------------------------
    # I/O helpers
    # ------------------------------------------------------------------

    def _infer_ids_from_path(self, path: Path) -> tuple[str, str]:
        """Extract ``team_id`` and ``season_id`` from the stats file path.

        Expects the convention ``.../{season_id}/teams/{team_id}/stats.json``.

        Args:
            path: Path to the stats JSON file.

        Returns:
            Tuple of ``(team_id, season_id)``.
        """
        parts = path.parts
        for i, part in enumerate(parts):
            if part == "teams" and i + 1 < len(parts):
                team_id = parts[i + 1]
                season_id = parts[i - 1] if i > 0 else "unknown"
                return team_id, season_id

        team_id = path.parent.name
        season_id = path.parent.parent.parent.name
        logger.warning(
            "Could not infer team_id/season_id from path %s; "
            "falling back to team_id=%s season_id=%s",
            path,
            team_id,
            season_id,
        )
        return team_id, season_id

    def _read_json(self, path: Path) -> dict | None:
        """Read and parse the JSON file at ``path``.

        Args:
            path: Path to the JSON file.

        Returns:
            Parsed dict, or ``None`` on read/parse error.
        """
        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            logger.error("Stats file not found: %s", path)
            return None
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse stats JSON at %s: %s", path, exc)
            return None

        if not isinstance(data, dict):
            logger.error(
                "Expected a JSON object in %s, got %s", path, type(data).__name__
            )
            return None

        return data
