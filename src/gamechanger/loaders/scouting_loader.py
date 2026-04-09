"""Scouting loader for the baseball-crawl ingestion pipeline.

Consumes in-memory crawl results from ``ScoutingCrawler.scout_team()``
and loads them into the SQLite database.  Delegates per-game boxscore
loading to the existing ``GameLoader.load_file()`` (which handles all
boxscore parsing, player stubs, game records, and batting/pitching stat
upserts).

Additional responsibilities beyond ``GameLoader``:
- Roster loading into ``players`` and ``team_rosters``.
- ``scouting_runs`` metadata tracking (status transitions, timestamps).
- Season aggregate computation: sums per-game stats from
  ``player_game_batting`` and ``player_game_pitching``, then upserts into
  ``player_season_batting`` and ``player_season_pitching``.

Usage::

    import sqlite3
    from src.gamechanger.loaders.scouting_loader import ScoutingLoader
    from src.gamechanger.crawlers.scouting import ScoutingCrawlResult

    conn = sqlite3.connect("./data/app.db")
    conn.execute("PRAGMA foreign_keys=ON;")
    loader = ScoutingLoader(conn)
    result = loader.load_team(crawl_result)
    print(result)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from src.db.players import ensure_player_row
from src.gamechanger.loaders import LoadResult, derive_season_id_for_team, ensure_season_row
from src.gamechanger.loaders.game_loader import GameLoader, GameSummaryEntry
from src.gamechanger.types import TeamRef

logger = logging.getLogger(__name__)

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
        crawl_result: Any,
        team_id: int | None = None,
        season_id: str | None = None,
    ) -> LoadResult:
        """Load all scouting data from an in-memory crawl result.

        Accepts a ``ScoutingCrawlResult`` from the crawler, loads roster
        and boxscores from the in-memory data, and computes season aggregates.

        Args:
            crawl_result: ``ScoutingCrawlResult`` containing games, roster,
                and boxscores data.  For backwards compatibility, also accepts
                a ``Path`` (deprecated disk-based flow).
            team_id: The opponent's INTEGER PK.  When ``None``, uses
                ``crawl_result.team_id``.
            season_id: Unused (kept for backwards compatibility).  DB season_id
                is derived from team metadata.

        Returns:
            Aggregated ``LoadResult`` across roster and boxscore loading.
        """
        # Backwards compatibility: if crawl_result is a Path, use old disk flow.
        if isinstance(crawl_result, Path):
            return self._load_team_from_disk(crawl_result, team_id, season_id)

        # In-memory flow (E-220-05).
        tid = team_id if team_id is not None else crawl_result.team_id

        # Derive the canonical DB season_id from team metadata (not the crawl path).
        db_season_id, db_season_year = derive_season_id_for_team(self._db, tid)
        ensure_season_row(self._db, db_season_id)

        total = self._load_roster_from_data(crawl_result.roster, tid, db_season_id)

        # Post-roster validation.
        expected_count = sum(1 for p in crawl_result.roster if p.get("id"))
        if expected_count:
            self._validate_roster_count(tid, db_season_id, expected_count)

        if not crawl_result.boxscores:
            logger.info("No boxscores in crawl result for team_id=%d; nothing to load.", tid)
            return total

        # Build TeamRef for GameLoader by looking up gc_uuid and public_id.
        team_ref = self._build_team_ref(tid)
        game_loader = GameLoader(db=self._db, owned_team_ref=team_ref)
        games_index = self._build_games_index_from_data(crawl_result.games)
        opponent_name_index = self._build_opponent_name_index_from_data(crawl_result.games)
        bs_result = self._load_boxscores_from_data(
            game_loader, games_index, crawl_result.boxscores,
            opponent_name_index=opponent_name_index,
        )
        total.loaded += bs_result.loaded
        total.skipped += bs_result.skipped
        total.errors += bs_result.errors

        # Post-boxscore validation: check for duplicate game rows.
        self._check_duplicate_games(tid, db_season_id)

        # Hook 1: dedup sweep after boxscore loading, before aggregation.
        try:
            from src.db.player_dedup import dedup_team_players

            dedup_team_players(
                self._db, tid, db_season_id, manage_transaction=False
            )
        except Exception:  # noqa: BLE001
            logger.error(
                "Post-boxscore dedup sweep failed for team_id=%d season=%s; "
                "continuing with aggregation",
                tid,
                db_season_id,
                exc_info=True,
            )

        self._compute_season_aggregates(tid, db_season_id)
        self._db.commit()
        logger.info(
            "Scouting load complete for team_id=%d season=%s: loaded=%d skipped=%d errors=%d",
            tid, db_season_id, total.loaded, total.skipped, total.errors,
        )
        return total

    def _load_team_from_disk(
        self,
        scouting_dir: Path,
        team_id: int | None,
        season_id: str | None,
    ) -> LoadResult:
        """Legacy disk-based load_team path (backwards compatibility).

        Reads games.json, roster.json, and boxscores/*.json files from disk.
        """
        if team_id is None:
            raise ValueError("team_id is required for disk-based load_team")

        db_season_id, db_season_year = derive_season_id_for_team(self._db, team_id)
        ensure_season_row(self._db, db_season_id)

        total = self._load_roster_section(scouting_dir, team_id, db_season_id)

        roster_path = scouting_dir / "roster.json"
        if roster_path.exists():
            expected_count = self._count_roster_entries(roster_path)
            if expected_count is not None:
                self._validate_roster_count(team_id, db_season_id, expected_count)

        boxscores_dir = scouting_dir / "boxscores"
        if not boxscores_dir.is_dir():
            logger.info("No boxscores directory at %s; nothing to load.", boxscores_dir)
            return total

        team_ref = self._build_team_ref(team_id)
        game_loader = GameLoader(db=self._db, owned_team_ref=team_ref)
        games_path = scouting_dir / "games.json"
        games_index = self._build_games_index(games_path)
        opponent_name_index = self._build_opponent_name_index(games_path)
        bs_result = self._load_boxscores(
            game_loader, games_index, boxscores_dir,
            opponent_name_index=opponent_name_index,
        )
        total.loaded += bs_result.loaded
        total.skipped += bs_result.skipped
        total.errors += bs_result.errors

        self._check_duplicate_games(team_id, db_season_id)

        try:
            from src.db.player_dedup import dedup_team_players
            dedup_team_players(self._db, team_id, db_season_id, manage_transaction=False)
        except Exception:  # noqa: BLE001
            logger.error(
                "Post-boxscore dedup sweep failed for team_id=%d season=%s; continuing with aggregation",
                team_id, db_season_id, exc_info=True,
            )

        self._compute_season_aggregates(team_id, db_season_id)
        self._db.commit()
        logger.info(
            "Scouting load complete for team_id=%d season=%s: loaded=%d skipped=%d errors=%d",
            team_id, db_season_id, total.loaded, total.skipped, total.errors,
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
        opponent_name_index: dict[str, str] | None = None,
    ) -> LoadResult:
        """Load all boxscore files in ``boxscores_dir`` via ``game_loader``.

        Args:
            game_loader: Configured ``GameLoader`` for the scouted team.
            games_index: Mapping of ``game_stream_id`` → ``GameSummaryEntry``.
            boxscores_dir: Directory containing ``{game_stream_id}.json`` files.
            opponent_name_index: Optional mapping of ``game_stream_id`` →
                opponent team name.  When provided, real names are used for
                opponent team rows instead of UUID placeholders.

        Returns:
            Aggregated ``LoadResult`` across all boxscore files.
        """
        name_index = opponent_name_index or {}
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
            opponent_name = name_index.get(game_stream_id)
            result = game_loader.load_file(bs_path, summary, opponent_name=opponent_name)
            total.loaded += result.loaded
            total.skipped += result.skipped
            total.errors += result.errors
        return total

    # ------------------------------------------------------------------
    # Games index builder
    # ------------------------------------------------------------------

    def _build_opponent_name_index(self, games_path: Path) -> dict[str, str]:
        """Build a ``game_stream_id → opponent_team.name`` mapping from games.json.

        Used to supply real opponent team names to ``GameLoader`` so team rows
        are created with human-readable names instead of UUID placeholders.

        Args:
            games_path: Path to ``games.json`` (public games response).

        Returns:
            Dict mapping ``game_stream_id`` (= the ``id`` field in games.json)
            to the opponent team display name.  Returns empty dict on error.
        """
        if not games_path.exists():
            return {}
        try:
            with games_path.open(encoding="utf-8") as fh:
                raw = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read %s for opponent name index: %s", games_path, exc)
            return {}
        if not isinstance(raw, list):
            return {}

        index: dict[str, str] = {}
        for game in raw:
            game_id = game.get("id")
            opponent_team = game.get("opponent_team") or {}
            name = opponent_team.get("name")
            if game_id and name:
                index[str(game_id)] = name
        return index

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
                start_time=game.get("start_ts"),
                timezone=game.get("timezone"),
            )
            index[entry.game_stream_id] = entry

        logger.info("Built games index: %d entries from %s", len(index), games_path)
        return index

    # ------------------------------------------------------------------
    # In-memory data methods (E-220-05)
    # ------------------------------------------------------------------

    def _build_games_index_from_data(
        self, games_data: list[dict[str, Any]]
    ) -> dict[str, GameSummaryEntry]:
        """Build a ``game_stream_id -> GameSummaryEntry`` mapping from in-memory games list."""
        index: dict[str, GameSummaryEntry] = {}
        for game in games_data:
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
                start_time=game.get("start_ts"),
                timezone=game.get("timezone"),
            )
            index[entry.game_stream_id] = entry
        logger.info("Built games index from in-memory data: %d entries", len(index))
        return index

    def _build_opponent_name_index_from_data(
        self, games_data: list[dict[str, Any]]
    ) -> dict[str, str]:
        """Build a ``game_stream_id -> opponent name`` mapping from in-memory games list."""
        index: dict[str, str] = {}
        for game in games_data:
            game_id = game.get("id")
            opponent_team = game.get("opponent_team") or {}
            name = opponent_team.get("name")
            if game_id and name:
                index[str(game_id)] = name
        return index

    def _load_roster_from_data(
        self, roster_data: list[dict[str, Any]], team_id: int, season_id: str
    ) -> LoadResult:
        """Load roster from in-memory data into players and team_rosters."""
        if not roster_data:
            logger.warning("Empty roster data for team_id=%d; skipping.", team_id)
            return LoadResult()
        result = LoadResult()
        for player in roster_data:
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

    def _load_boxscores_from_data(
        self,
        game_loader: GameLoader,
        games_index: dict[str, GameSummaryEntry],
        boxscores: dict[str, dict[str, Any]],
        opponent_name_index: dict[str, str] | None = None,
    ) -> LoadResult:
        """Load boxscores from in-memory data via ``game_loader``.

        GameLoader.load_file() requires a filesystem path.  We write each
        boxscore to a temporary file, let GameLoader process it, then clean up.
        """
        name_index = opponent_name_index or {}
        total = LoadResult()
        # Single TemporaryDirectory wraps the loop -- per-iteration temp files
        # are written inside it and cleaned up automatically when the context
        # exits.  Mirrors the pattern in src/reports/generator.py
        # _crawl_and_load_plays.
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            for game_stream_id, boxscore_data in sorted(boxscores.items()):
                summary = games_index.get(game_stream_id)
                if summary is None:
                    logger.warning(
                        "No games entry for game_stream_id=%s; skipping boxscore",
                        game_stream_id,
                    )
                    total.skipped += 1
                    continue
                opponent_name = name_index.get(game_stream_id)
                tmp_path = tmp_root / f"{game_stream_id}.json"
                tmp_path.write_text(json.dumps(boxscore_data), encoding="utf-8")
                result = game_loader.load_file(tmp_path, summary, opponent_name=opponent_name)
                total.loaded += result.loaded
                total.skipped += result.skipped
                total.errors += result.errors
        return total

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
            ensure_player_row(self._db, player_id, first_name, last_name)
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
    # Post-load validation
    # ------------------------------------------------------------------

    def _check_duplicate_games(self, team_id: int, season_id: str) -> None:
        """Check for duplicate game rows involving this team in a season.

        Queries for ``(game_date, unordered team pair)`` groups with
        ``COUNT(*) > 1`` among completed games where this team is home or
        away within the given season.  Logs WARNING if any duplicates found.
        """
        rows = self._db.execute(
            """
            SELECT game_date,
                   MIN(home_team_id, away_team_id) AS t1,
                   MAX(home_team_id, away_team_id) AS t2,
                   COUNT(*) AS cnt
            FROM games
            WHERE (home_team_id = ? OR away_team_id = ?)
              AND status = 'completed'
              AND season_id = ?
            GROUP BY game_date, t1, t2
            HAVING cnt > 1
            """,
            (team_id, team_id, season_id),
        ).fetchall()

        if rows:
            details = "; ".join(
                f"{r[0]} teams=({r[1]},{r[2]}) x{r[3]}" for r in rows
            )
            logger.warning(
                "Post-load validation: %d duplicate game(s) detected for "
                "team_id=%d: %s",
                len(rows), team_id, details,
            )

    def _validate_roster_count(
        self, team_id: int, season_id: str, expected_count: int
    ) -> None:
        """Warn if DB roster count exceeds the expected count from roster.json.

        DB count may be *lower* after player dedup merges -- that is correct
        behavior and not warned.
        """
        actual = self._db.execute(
            "SELECT COUNT(*) FROM team_rosters WHERE team_id = ? AND season_id = ?",
            (team_id, season_id),
        ).fetchone()[0]

        if actual > expected_count:
            logger.warning(
                "Post-load validation: expected %d roster entries for "
                "team_id=%d, found %d in DB",
                expected_count, team_id, actual,
            )

    @staticmethod
    def _count_roster_entries(roster_path: Path) -> int | None:
        """Count valid player entries in a roster.json file.

        Returns the count of entries with an ``id`` field, or ``None`` if the
        file cannot be read.
        """
        try:
            with roster_path.open(encoding="utf-8") as fh:
                raw = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(raw, list):
            return None
        return sum(1 for p in raw if p.get("id"))

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
        """Sum game batting rows into player_season_batting; return player count.

        Filters by ``perspective_team_id = team_id`` to prevent double-counting
        when the same game has been loaded from multiple perspectives.  In the
        scouting context, ``team_id == perspective_team_id`` (scouting loads
        from the scouted team's perspective).

        NOTE: Other query sites that aggregate per-game stat rows (e.g.
        ``src/api/db.py``, ``src/db/player_dedup.py``) may also need
        perspective filtering -- assess when those surfaces are updated.
        """
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
                SUM(pgb.r)       AS r,
                SUM(pgb.bb)      AS bb,
                SUM(pgb.so)      AS so,
                SUM(pgb.sb)      AS sb,
                SUM(pgb.tb)      AS tb,
                SUM(pgb.hbp)     AS hbp,
                SUM(pgb.shf)     AS shf,
                SUM(pgb.cs)      AS cs
            FROM player_game_batting pgb
            JOIN games g ON pgb.game_id = g.game_id
            WHERE pgb.team_id = ? AND g.season_id = ?
              AND pgb.perspective_team_id = ?
            GROUP BY pgb.player_id
            """,
            (team_id, season_id, team_id),
        ).fetchall()
        for (player_id, games_tracked,
             ab, h, doubles, triples, hr, rbi, r, bb, so, sb,
             tb, hbp, shf, cs) in rows:
            self._db.execute(
                """
                INSERT INTO player_season_batting
                    (player_id, team_id, season_id,
                     gp, games_tracked, ab, h, doubles, triples, hr, rbi, r, bb, so, sb,
                     tb, hbp, shf, cs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(player_id, team_id, season_id) DO UPDATE SET
                    gp            = excluded.gp,
                    games_tracked = excluded.games_tracked,
                    ab            = excluded.ab,
                    h             = excluded.h,
                    doubles       = excluded.doubles,
                    triples       = excluded.triples,
                    hr            = excluded.hr,
                    rbi           = excluded.rbi,
                    r             = excluded.r,
                    bb            = excluded.bb,
                    so            = excluded.so,
                    sb            = excluded.sb,
                    tb            = excluded.tb,
                    hbp           = excluded.hbp,
                    shf           = excluded.shf,
                    cs            = excluded.cs
                """,
                (player_id, team_id, season_id, games_tracked, games_tracked,
                 ab, h, doubles, triples, hr, rbi, r, bb, so, sb,
                 tb, hbp, shf, cs),
            )
        return len(rows)

    def _compute_pitching_aggregates(self, team_id: int, season_id: str) -> int:
        """Sum game pitching rows into player_season_pitching; return player count.

        Filters by ``perspective_team_id = team_id`` to prevent double-counting
        when the same game has been loaded from multiple perspectives.

        Note: ``hr`` is excluded -- ``player_game_pitching`` does not store HR
        allowed (not present in the boxscore pitching extras per the schema).
        """
        rows = self._db.execute(
            """
            SELECT
                pgp.player_id,
                COUNT(*)              AS games_tracked,
                SUM(pgp.ip_outs)      AS ip_outs,
                SUM(pgp.h)            AS h,
                SUM(pgp.r)            AS r,
                SUM(pgp.er)           AS er,
                SUM(pgp.bb)           AS bb,
                SUM(pgp.so)           AS so,
                SUM(pgp.wp)           AS wp,
                SUM(pgp.hbp)          AS hbp,
                SUM(pgp.pitches)      AS pitches,
                SUM(pgp.total_strikes) AS total_strikes,
                SUM(pgp.bf)           AS bf,
                CASE WHEN MAX(pgp.appearance_order) IS NULL THEN NULL
                     ELSE SUM(CASE WHEN pgp.appearance_order = 1 THEN 1 ELSE 0 END)
                END AS gs
            FROM player_game_pitching pgp
            JOIN games g ON pgp.game_id = g.game_id
            WHERE pgp.team_id = ? AND g.season_id = ?
              AND pgp.perspective_team_id = ?
            GROUP BY pgp.player_id
            """,
            (team_id, season_id, team_id),
        ).fetchall()
        for (player_id, games_tracked,
             ip_outs, h, r, er, bb, so,
             wp, hbp, pitches, total_strikes, bf, gs) in rows:
            self._db.execute(
                """
                INSERT INTO player_season_pitching
                    (player_id, team_id, season_id,
                     gp_pitcher, games_tracked, ip_outs, h, r, er, bb, so,
                     wp, hbp, pitches, total_strikes, bf, gs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(player_id, team_id, season_id) DO UPDATE SET
                    gp_pitcher    = excluded.gp_pitcher,
                    games_tracked = excluded.games_tracked,
                    ip_outs       = excluded.ip_outs,
                    h             = excluded.h,
                    r             = excluded.r,
                    er            = excluded.er,
                    bb            = excluded.bb,
                    so            = excluded.so,
                    wp            = excluded.wp,
                    hbp           = excluded.hbp,
                    pitches       = excluded.pitches,
                    total_strikes = excluded.total_strikes,
                    bf            = excluded.bf,
                    gs            = excluded.gs
                """,
                (player_id, team_id, season_id, games_tracked, games_tracked,
                 ip_outs, h, r, er, bb, so,
                 wp, hbp, pitches, total_strikes, bf, gs),
            )
        return len(rows)

    # ------------------------------------------------------------------
    # FK prerequisite helpers
    # ------------------------------------------------------------------

