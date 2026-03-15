"""Scouting loader for the baseball-crawl ingestion pipeline.

Reads raw scouting files written by ``ScoutingCrawler`` and loads them into
the SQLite database.  Delegates per-game boxscore loading to the existing
``GameLoader.load_file()`` (which handles all boxscore parsing, player stubs,
game records, and batting/pitching stat upserts).

Additional responsibilities beyond ``GameLoader``:
- Roster loading into ``players`` and ``team_rosters``.
- ``scouting_runs`` metadata tracking (status transitions, timestamps).
- Season aggregate computation: sums per-game stats from
  ``player_game_batting`` and ``player_game_pitching``, then upserts into
  ``player_season_batting`` and ``player_season_pitching``.
- UUID opportunism: ensures a ``teams`` row exists for any UUID discovered
  as a boxscore key.

Expected raw file layout (written by ``ScoutingCrawler``)::

    data/raw/{season_id}/scouting/{public_id}/games.json
    data/raw/{season_id}/scouting/{public_id}/roster.json
    data/raw/{season_id}/scouting/{public_id}/boxscores/{game_stream_id}.json

Usage::

    import sqlite3
    from pathlib import Path
    from src.gamechanger.loaders.scouting_loader import ScoutingLoader

    conn = sqlite3.connect("./data/app.db")
    conn.execute("PRAGMA foreign_keys=ON;")
    loader = ScoutingLoader(conn)
    result = loader.load_team(
        Path("data/raw/2025-spring-hs/scouting/8O8bTolVfb9A"),
        team_id=42,
        season_id="2025-spring-hs",
    )
    print(result)
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

from src.gamechanger.loaders import LoadResult
from src.gamechanger.loaders.game_loader import GameLoader, GameSummaryEntry
from src.gamechanger.types import TeamRef

logger = logging.getLogger(__name__)

# UUID pattern: 8-4-4-4-12 hex digits with dashes.
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# run_type used by the scouting crawler for scouting_runs.
_RUN_TYPE = "full"


class ScoutingLoader:
    """Loads raw scouting files into the SQLite database.

    Delegates boxscore loading to ``GameLoader.load_file()`` and adds
    roster loading, season aggregate computation, and scouting_runs tracking.

    Args:
        db: Open ``sqlite3.Connection`` with ``PRAGMA foreign_keys=ON`` set.
            The caller owns the connection lifecycle.
    """

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_team(
        self,
        scouting_dir: Path,
        team_id: int,
        season_id: str,
    ) -> LoadResult:
        """Load all scouting data for one opponent from a raw directory.

        Reads ``games.json``, ``roster.json``, and all ``boxscores/*.json``
        files.  Delegates boxscore loading to ``GameLoader.load_file()`` and
        computes season aggregates from the loaded per-game rows.

        Args:
            scouting_dir: Path to ``data/raw/{season_id}/scouting/{public_id}/``.
            team_id: The opponent's INTEGER PK in the ``teams`` table.
            season_id: Season slug (e.g. ``"2025-spring-hs"``).

        Returns:
            Aggregated ``LoadResult`` across roster and boxscore loading.
        """
        self._ensure_season_row(season_id)

        total = self._load_roster_section(scouting_dir, team_id, season_id)

        boxscores_dir = scouting_dir / "boxscores"
        if not boxscores_dir.is_dir():
            logger.info("No boxscores directory at %s; nothing to load.", boxscores_dir)
            return total

        # Build TeamRef for GameLoader by looking up gc_uuid and public_id.
        team_ref = self._build_team_ref(team_id)
        game_loader = GameLoader(db=self._db, season_id=season_id, owned_team_ref=team_ref)
        games_index = self._build_games_index(scouting_dir / "games.json")
        bs_result = self._load_boxscores(game_loader, games_index, boxscores_dir)
        total.loaded += bs_result.loaded
        total.skipped += bs_result.skipped
        total.errors += bs_result.errors

        self._compute_season_aggregates(team_id, season_id)
        self._db.commit()
        logger.info(
            "Scouting load complete for team_id=%d season=%s: loaded=%d skipped=%d errors=%d",
            team_id, season_id, total.loaded, total.skipped, total.errors,
        )
        return total

    def _build_team_ref(self, team_id: int) -> TeamRef:
        """Build a ``TeamRef`` by looking up the teams row for ``team_id``.

        Args:
            team_id: INTEGER PK in the ``teams`` table.

        Returns:
            ``TeamRef`` populated with gc_uuid and public_id from the DB row.
        """
        row = self._db.execute(
            "SELECT gc_uuid, public_id FROM teams WHERE id = ?", (team_id,)
        ).fetchone()
        if row:
            return TeamRef(id=team_id, gc_uuid=row[0], public_id=row[1])
        logger.warning("No teams row found for team_id=%d; TeamRef will have null identifiers.", team_id)
        return TeamRef(id=team_id)

    def _load_roster_section(
        self, scouting_dir: Path, team_id: int, season_id: str
    ) -> LoadResult:
        """Load the roster.json file if present; return a LoadResult.

        Args:
            scouting_dir: Base scouting directory.
            team_id: INTEGER PK of the opponent team.
            season_id: Season slug.

        Returns:
            ``LoadResult`` from roster loading, or an empty result if the file
            is absent.
        """
        roster_path = scouting_dir / "roster.json"
        if roster_path.exists():
            return self._load_roster(roster_path, team_id, season_id)
        logger.warning("roster.json not found at %s; skipping.", roster_path)
        return LoadResult()

    def _load_boxscores(
        self,
        game_loader: GameLoader,
        games_index: dict,
        boxscores_dir: Path,
    ) -> LoadResult:
        """Load all boxscore files in ``boxscores_dir`` via ``game_loader``.

        Args:
            game_loader: Configured ``GameLoader`` for the scouted team.
            games_index: Mapping of ``game_stream_id`` → ``GameSummaryEntry``.
            boxscores_dir: Directory containing ``{game_stream_id}.json`` files.

        Returns:
            Aggregated ``LoadResult`` across all boxscore files.
        """
        total = LoadResult()
        for bs_path in sorted(boxscores_dir.glob("*.json")):
            game_stream_id = bs_path.stem
            summary = games_index.get(game_stream_id)
            if summary is None:
                logger.warning(
                    "No games.json entry for game_stream_id=%s; skipping %s",
                    game_stream_id, bs_path,
                )
                total.skipped += 1
                continue
            result = game_loader.load_file(bs_path, summary)
            total.loaded += result.loaded
            total.skipped += result.skipped
            total.errors += result.errors
            self._record_uuid_from_boxscore_path(bs_path)
        return total

    # ------------------------------------------------------------------
    # Games index builder
    # ------------------------------------------------------------------

    def _build_games_index(self, games_path: Path) -> dict[str, GameSummaryEntry]:
        """Build a ``game_stream_id -> GameSummaryEntry`` mapping from games.json."""
        if not games_path.exists():
            logger.warning("games.json not found at %s; no game index built.", games_path)
            return {}
        try:
            with games_path.open(encoding="utf-8") as fh:
                raw = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read %s: %s", games_path, exc)
            return {}
        if not isinstance(raw, list):
            logger.error("Expected JSON array in %s, got %s", games_path, type(raw).__name__)
            return {}

        index: dict[str, GameSummaryEntry] = {}
        for game in raw:
            if game.get("game_status") != "completed":
                continue
            game_id = game.get("id")
            if not game_id:
                continue
            score = game.get("score") or {}
            start_ts = game.get("start_ts") or game.get("end_ts") or "1900-01-01T00:00:00Z"
            entry = GameSummaryEntry(
                event_id=str(game_id),
                game_stream_id=str(game_id),
                home_away=game.get("home_away"),
                owning_team_score=int(score.get("team") or 0),
                opponent_team_score=int(score.get("opponent_team") or 0),
                opponent_id="",
                last_scoring_update=str(start_ts),
            )
            index[entry.game_stream_id] = entry

        logger.info("Built games index: %d entries from %s", len(index), games_path)
        return index

    # ------------------------------------------------------------------
    # Roster loading
    # ------------------------------------------------------------------

    def _load_roster(
        self, roster_path: Path, team_id: int, season_id: str
    ) -> LoadResult:
        """Load players from a roster.json file into players and team_rosters."""
        try:
            with roster_path.open(encoding="utf-8") as fh:
                raw = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read %s: %s", roster_path, exc)
            return LoadResult(errors=1)
        if not isinstance(raw, list):
            logger.error("Expected JSON array in %s, got %s", roster_path, type(raw).__name__)
            return LoadResult(errors=1)

        result = LoadResult()
        for player in raw:
            player_id = player.get("id")
            if not player_id:
                logger.warning("Roster entry missing 'id'; skipping. entry=%r", player)
                result.skipped += 1
                continue
            ok = self._upsert_roster_player(
                player_id=player_id,
                first_name=str(player.get("first_name") or ""),
                last_name=str(player.get("last_name") or ""),
                team_id=team_id,
                season_id=season_id,
                jersey_number=player.get("number") or None,
            )
            if ok:
                result.loaded += 1
            else:
                result.errors += 1

        self._db.commit()
        logger.info("Roster loaded for team_id=%d: %d players, %d errors.", team_id, result.loaded, result.errors)
        return result

    def _upsert_roster_player(
        self,
        player_id: str,
        first_name: str,
        last_name: str,
        team_id: int,
        season_id: str,
        jersey_number: str | None,
    ) -> bool:
        """Upsert one player into players and team_rosters; return True on success."""
        try:
            self._db.execute(
                """
                INSERT INTO players (player_id, first_name, last_name)
                VALUES (?, ?, ?)
                ON CONFLICT(player_id) DO UPDATE SET
                    first_name = excluded.first_name,
                    last_name  = excluded.last_name
                """,
                (player_id, first_name, last_name),
            )
            self._db.execute(
                """
                INSERT INTO team_rosters (team_id, player_id, season_id, jersey_number)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(team_id, player_id, season_id) DO UPDATE SET
                    jersey_number = excluded.jersey_number
                """,
                (team_id, player_id, season_id, jersey_number),
            )
            return True
        except sqlite3.Error as exc:
            logger.error("DB error loading roster player %s for team %d: %s", player_id, team_id, exc)
            return False

    # ------------------------------------------------------------------
    # Season aggregate computation
    # ------------------------------------------------------------------

    def _compute_season_aggregates(self, team_id: int, season_id: str) -> None:
        """Compute and upsert season aggregate stats from per-game rows.

        Delegates to batting and pitching sub-methods.  Rate stats (AVG, OBP,
        ERA, WHIP) are NOT stored -- they are computed at display time.

        Args:
            team_id: INTEGER PK of the scouted team.
            season_id: Season slug.
        """
        n_batting = self._compute_batting_aggregates(team_id, season_id)
        n_pitching = self._compute_pitching_aggregates(team_id, season_id)
        logger.info(
            "Season aggregates computed: %d batting, %d pitching rows for team=%d season=%s.",
            n_batting, n_pitching, team_id, season_id,
        )

    def _compute_batting_aggregates(self, team_id: int, season_id: str) -> int:
        """Sum game batting rows into player_season_batting; return player count."""
        rows = self._db.execute(
            """
            SELECT
                pgb.player_id,
                COUNT(*)         AS games_tracked,
                SUM(pgb.ab)      AS ab,
                SUM(pgb.h)       AS h,
                SUM(pgb.doubles) AS doubles,
                SUM(pgb.triples) AS triples,
                SUM(pgb.hr)      AS hr,
                SUM(pgb.rbi)     AS rbi,
                SUM(pgb.bb)      AS bb,
                SUM(pgb.so)      AS so,
                SUM(pgb.sb)      AS sb
            FROM player_game_batting pgb
            JOIN games g ON pgb.game_id = g.game_id
            WHERE pgb.team_id = ? AND g.season_id = ?
            GROUP BY pgb.player_id
            """,
            (team_id, season_id),
        ).fetchall()
        for player_id, games_tracked, ab, h, doubles, triples, hr, rbi, bb, so, sb in rows:
            self._db.execute(
                """
                INSERT INTO player_season_batting
                    (player_id, team_id, season_id,
                     gp, games_tracked, ab, h, doubles, triples, hr, rbi, bb, so, sb)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(player_id, team_id, season_id) DO UPDATE SET
                    gp            = excluded.gp,
                    games_tracked = excluded.games_tracked,
                    ab            = excluded.ab,
                    h             = excluded.h,
                    doubles       = excluded.doubles,
                    triples       = excluded.triples,
                    hr            = excluded.hr,
                    rbi           = excluded.rbi,
                    bb            = excluded.bb,
                    so            = excluded.so,
                    sb            = excluded.sb
                """,
                (player_id, team_id, season_id, games_tracked, games_tracked,
                 ab, h, doubles, triples, hr, rbi, bb, so, sb),
            )
        return len(rows)

    def _compute_pitching_aggregates(self, team_id: int, season_id: str) -> int:
        """Sum game pitching rows into player_season_pitching; return player count.

        Note: ``hr`` is excluded -- ``player_game_pitching`` does not store HR
        allowed (not present in the boxscore pitching extras per the schema).
        """
        rows = self._db.execute(
            """
            SELECT
                pgp.player_id,
                COUNT(*)         AS games_tracked,
                SUM(pgp.ip_outs) AS ip_outs,
                SUM(pgp.h)       AS h,
                SUM(pgp.er)      AS er,
                SUM(pgp.bb)      AS bb,
                SUM(pgp.so)      AS so
            FROM player_game_pitching pgp
            JOIN games g ON pgp.game_id = g.game_id
            WHERE pgp.team_id = ? AND g.season_id = ?
            GROUP BY pgp.player_id
            """,
            (team_id, season_id),
        ).fetchall()
        for player_id, games_tracked, ip_outs, h, er, bb, so in rows:
            self._db.execute(
                """
                INSERT INTO player_season_pitching
                    (player_id, team_id, season_id,
                     gp_pitcher, games_tracked, ip_outs, h, er, bb, so)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(player_id, team_id, season_id) DO UPDATE SET
                    gp_pitcher    = excluded.gp_pitcher,
                    games_tracked = excluded.games_tracked,
                    ip_outs       = excluded.ip_outs,
                    h             = excluded.h,
                    er            = excluded.er,
                    bb            = excluded.bb,
                    so            = excluded.so
                """,
                (player_id, team_id, season_id, games_tracked, games_tracked,
                 ip_outs, h, er, bb, so),
            )
        return len(rows)

    # ------------------------------------------------------------------
    # UUID opportunism
    # ------------------------------------------------------------------

    def _record_uuid_from_boxscore_path(self, bs_path: Path) -> None:
        """Ensure a ``teams`` stub row exists for any UUID key found in a boxscore.

        The GameLoader already creates stubs during load_file(), so this is a
        safety net for UUID keys not covered by normal team detection.

        Args:
            bs_path: Path to a boxscore JSON file.
        """
        try:
            with bs_path.open(encoding="utf-8") as fh:
                boxscore = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("Could not read boxscore for UUID opportunism: %s", exc)
            return

        if not isinstance(boxscore, dict):
            return

        for key in boxscore:
            if _UUID_RE.match(key):
                self._db.execute(
                    "INSERT OR IGNORE INTO teams (name, membership_type, gc_uuid, is_active) "
                    "VALUES (?, 'tracked', ?, 0)",
                    (key, key),
                )
                logger.debug("UUID opportunism (loader): ensured stub row for gc_uuid=%s", key)

    # ------------------------------------------------------------------
    # FK prerequisite helpers
    # ------------------------------------------------------------------

    def _ensure_season_row(self, season_id: str) -> None:
        """Ensure a ``seasons`` row exists for ``season_id``.

        Args:
            season_id: Season slug.
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
