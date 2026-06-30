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
        created_team_ids: Optional in-memory set recording opponent team ids
            this loader INSERTs (threaded into ``GameLoader``). The report
            generator passes its per-run created-set here so orphan cleanup
            deletes only teams THIS run created, closing the cross-process
            team-deletion race (E-235-04). ``None`` (the default) disables
            recording.
    """

    def __init__(
        self,
        db: sqlite3.Connection,
        created_team_ids: set[int] | None = None,
    ) -> None:
        self._db = db
        self._created_team_ids = created_team_ids

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
        games_index = self._build_games_index_from_data(crawl_result.games)
        opponent_name_index = self._build_opponent_name_index_from_data(crawl_result.games)
        return self._load_team_core(
            tid,
            crawl_result.roster,
            games_index,
            opponent_name_index,
            boxscores=crawl_result.boxscores,
        )

    def _load_team_from_disk(
        self,
        scouting_dir: Path,
        team_id: int | None,
        season_id: str | None,
    ) -> LoadResult:
        """Legacy disk-based load_team path (backwards compatibility).

        Thin reader: reads roster.json and games.json into the same in-memory
        structures the crawler produces, then delegates to the shared
        :meth:`_load_team_core`, passing the on-disk ``boxscores/`` directory so
        boxscores are read lazily per file (preserving the prior per-file
        ``GameLoader.load_file`` error isolation).  This mirrors the established
        ``plays_loader._load_game`` dual-input pattern, where the disk path is a
        thin wrapper over a single in-memory payload core (E-247-01).
        """
        if team_id is None:
            raise ValueError("team_id is required for disk-based load_team")

        roster_data, roster_read_errors = self._read_roster_json(
            scouting_dir / "roster.json"
        )
        games_path = scouting_dir / "games.json"
        games_index = self._build_games_index(games_path)
        opponent_name_index = self._build_opponent_name_index(games_path)
        return self._load_team_core(
            team_id,
            roster_data,
            games_index,
            opponent_name_index,
            boxscores_dir=scouting_dir / "boxscores",
            extra_errors=roster_read_errors,
        )

    def _load_team_core(
        self,
        team_id: int,
        roster_data: list[dict[str, Any]],
        games_index: dict[str, GameSummaryEntry],
        opponent_name_index: dict[str, str],
        *,
        boxscores: dict[str, dict[str, Any]] | None = None,
        boxscores_dir: Path | None = None,
        extra_errors: int = 0,
    ) -> LoadResult:
        """Shared orchestration core for the in-memory and disk load_team paths.

        Both public entry points resolve their roster and game/opponent-name
        indexes to plain in-memory structures and delegate here, so the ~80
        lines of roster + boxscore + aggregate orchestration exist exactly once
        (E-247-01).  Boxscores follow the ``plays_loader._load_game`` dual-input
        pattern: the in-memory path passes a ``boxscores`` dict (loaded via
        ``GameLoader.load_payload``); the disk path passes a ``boxscores_dir``
        whose files are read lazily per game (loaded via ``GameLoader.load_file``,
        preserving per-file read-error isolation).

        Args:
            team_id: INTEGER PK of the scouted team.
            roster_data: Roster player dicts (empty list if none).
            games_index: ``game_stream_id -> GameSummaryEntry`` mapping.
            opponent_name_index: ``game_stream_id -> opponent name`` mapping.
            boxscores: In-memory ``game_stream_id -> boxscore payload`` mapping.
            boxscores_dir: Directory of ``{game_stream_id}.json`` boxscore files
                (disk path).  Exactly one of ``boxscores`` / ``boxscores_dir``
                is supplied.
            extra_errors: Errors accrued before this core ran (e.g. a present-
                but-malformed ``roster.json`` on the disk path).  Added to the
                result so disk-path read failures stay counted exactly as the
                pre-refactor ``_load_roster`` did.

        Returns:
            Aggregated ``LoadResult`` across roster and boxscore loading.
        """
        # Derive the canonical DB season_id from team metadata (not the crawl path).
        db_season_id, db_season_year = derive_season_id_for_team(self._db, team_id)
        ensure_season_row(self._db, db_season_id)

        total = self._load_roster_from_data(roster_data, team_id, db_season_id)
        total.errors += extra_errors

        # Post-roster validation.
        expected_count = sum(1 for p in roster_data if p.get("id"))
        if expected_count:
            self._validate_roster_count(team_id, db_season_id, expected_count)

        # Empty-boxscore-source guard (E-247-01 F1): skip the whole post-boxscore
        # tail (dedup / season-aggregate recompute / commit) when there is no
        # boxscore source to process THIS invocation.  This is NOT an
        # optimization -- ``canonical_recompute`` DELETEs+rebuilds the season
        # aggregates and the dedup sweep can MERGE players, so on a populated DB
        # a boxscoreless invocation would rewrite rows the pre-refactor early-
        # returns left untouched.  Each path's prior guard is reproduced exactly:
        #   - in-memory: skip when the boxscores dict is empty/falsy.
        #   - disk: skip only when the boxscores DIRECTORY is absent (a present-
        #     but-empty dir still ran the tail pre-refactor).
        if boxscores_dir is not None:
            has_boxscore_source = boxscores_dir.is_dir()
        else:
            has_boxscore_source = bool(boxscores)
        if not has_boxscore_source:
            if boxscores_dir is not None:
                logger.info(
                    "No boxscores directory at %s; nothing to load.", boxscores_dir
                )
            else:
                logger.info(
                    "No boxscores in crawl result for team_id=%d; nothing to load.",
                    team_id,
                )
            return total

        # Build TeamRef for GameLoader by looking up gc_uuid and public_id.
        team_ref = self._build_team_ref(team_id)
        game_loader = GameLoader(
            db=self._db,
            owned_team_ref=team_ref,
            created_team_ids=self._created_team_ids,
        )
        bs_result = self._load_boxscores(
            game_loader, games_index,
            boxscores=boxscores,
            boxscores_dir=boxscores_dir,
            opponent_name_index=opponent_name_index,
        )
        total.loaded += bs_result.loaded
        total.skipped += bs_result.skipped
        total.errors += bs_result.errors

        # Expose the dedup redirect map produced by GameLoader THIS run so the
        # generator's plays/spray stages file rows under the canonical id rather
        # than skipping deduped games under the orphaned source ids (E-244 TN-2).
        # Single whole-map assignment (NOT summed per-game like the int counts).
        total.redirect_map = game_loader.redirect_map

        # Post-boxscore validation: check for duplicate game rows.
        self._check_duplicate_games(team_id, db_season_id)

        # Hook 1: dedup sweep after boxscore loading, before aggregation.
        try:
            from src.db.player_dedup import dedup_team_players

            dedup_team_players(
                self._db, team_id, db_season_id,
                manage_transaction=False, recompute_aggregates=False,
            )
        except Exception:  # noqa: BLE001
            logger.error(
                "Post-boxscore dedup sweep failed for team_id=%d season=%s; "
                "continuing with aggregation",
                team_id,
                db_season_id,
                exc_info=True,
            )

        # Canonical recompute runs exactly once per load (the embedded dedup
        # above suppresses its own recompute via recompute_aggregates=False),
        # committed atomically with the dedup sweep below.
        self._compute_season_aggregates(team_id, db_season_id)
        self._db.commit()
        logger.info(
            "Scouting load complete for team_id=%d season=%s: loaded=%d skipped=%d errors=%d",
            team_id, db_season_id, total.loaded, total.skipped, total.errors,
        )
        return total

    # ------------------------------------------------------------------
    # Disk readers (thin JSON-read wrappers feeding _load_team_core)
    # ------------------------------------------------------------------

    def _read_json_list(self, path: Path) -> list[dict[str, Any]]:
        """Read a JSON-array file into a list; return [] on missing/error/non-list.

        Used for the games.json reads behind the index builders, which carry no
        error count (the pre-refactor ``_build_games_index`` returned ``{}`` on a
        malformed/missing file without an ``errors`` signal).  Roster reads, which
        DID count a malformed file as ``errors=1``, go through
        :meth:`_read_roster_json` instead -- do NOT route roster reads here.
        """
        if not path.exists():
            logger.warning("%s not found; treating as empty.", path)
            return []
        try:
            with path.open(encoding="utf-8") as fh:
                raw = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read %s: %s", path, exc)
            return []
        if not isinstance(raw, list):
            logger.error("Expected JSON array in %s, got %s", path, type(raw).__name__)
            return []
        return raw

    def _read_roster_json(self, roster_path: Path) -> tuple[list[dict[str, Any]], int]:
        """Read the disk ``roster.json``, returning ``(roster_data, read_errors)``.

        Reproduces the pre-refactor disk roster semantics exactly (E-247-01 F2):
        - **missing** file -> ``([], 0)`` (the old ``_load_roster_section``
          "not found" branch returned an empty, error-free ``LoadResult``).
        - **present but malformed / non-array** -> ``([], 1)`` (the old
          ``_load_roster`` returned ``LoadResult(errors=1)`` for a read failure or
          a non-list payload).
        - **valid array** -> ``(raw, 0)`` for the core to load.

        ``read_errors`` is threaded into :meth:`_load_team_core` as
        ``extra_errors`` so a malformed roster keeps its ``errors=1`` signal.
        """
        if not roster_path.exists():
            logger.warning("roster.json not found at %s; skipping.", roster_path)
            return [], 0
        try:
            with roster_path.open(encoding="utf-8") as fh:
                raw = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read %s: %s", roster_path, exc)
            return [], 1
        if not isinstance(raw, list):
            logger.error(
                "Expected JSON array in %s, got %s", roster_path, type(raw).__name__
            )
            return [], 1
        return raw, 0

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

    # ------------------------------------------------------------------
    # Games index builders (disk wrappers over the in-memory core)
    # ------------------------------------------------------------------

    def _build_opponent_name_index(self, games_path: Path) -> dict[str, str]:
        """Build a ``game_stream_id → opponent_team.name`` mapping from games.json.

        Thin JSON-read+validate wrapper delegating to the in-memory
        :meth:`_build_opponent_name_index_from_data` (E-247-01).  Used to supply
        real opponent team names to ``GameLoader`` so team rows are created with
        human-readable names instead of UUID placeholders.

        Args:
            games_path: Path to ``games.json`` (public games response).

        Returns:
            Dict mapping ``game_stream_id`` (= the ``id`` field in games.json)
            to the opponent team display name.  Returns empty dict on error.
        """
        return self._build_opponent_name_index_from_data(self._read_json_list(games_path))

    def _build_games_index(self, games_path: Path) -> dict[str, GameSummaryEntry]:
        """Build a ``game_stream_id -> GameSummaryEntry`` mapping from games.json.

        Thin JSON-read+validate wrapper delegating to the in-memory
        :meth:`_build_games_index_from_data` (E-247-01).
        """
        return self._build_games_index_from_data(self._read_json_list(games_path))

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

    def _load_boxscores(
        self,
        game_loader: GameLoader,
        games_index: dict[str, GameSummaryEntry],
        *,
        boxscores: dict[str, dict[str, Any]] | None = None,
        boxscores_dir: Path | None = None,
        opponent_name_index: dict[str, str] | None = None,
    ) -> LoadResult:
        """Load boxscores via ``game_loader`` from in-memory dicts or disk files.

        Dual-input shared core (E-247-01) mirroring ``plays_loader._load_game``:

        - In-memory path (``boxscores`` dict): each payload is passed directly to
          ``GameLoader.load_payload`` -- no temp files.
        - Disk path (``boxscores_dir``): each ``{game_stream_id}.json`` file is
          read lazily by ``GameLoader.load_file``, so a single unreadable file is
          isolated as one ``errors`` and does not abort the run.

        Both entry points commit per game (``load_payload``/``load_file`` each
        commit), so the only difference is dict-vs-file sourcing.  Exactly one of
        ``boxscores`` / ``boxscores_dir`` is supplied; if neither yields entries
        (empty dict, missing/empty directory) the loop is a no-op.
        """
        name_index = opponent_name_index or {}
        total = LoadResult()

        # Normalize both sources to a sorted ``(game_stream_id, source)`` stream
        # so the orchestration below is identical; ``source`` is a payload dict
        # (in-memory) or a Path (disk).
        if boxscores_dir is not None:
            items: list[tuple[str, Any]] = [
                (p.stem, p) for p in sorted(boxscores_dir.glob("*.json"))
            ]
        else:
            items = sorted((boxscores or {}).items())

        for game_stream_id, source in items:
            summary = games_index.get(game_stream_id)
            if summary is None:
                logger.warning(
                    "No games entry for game_stream_id=%s; skipping boxscore",
                    game_stream_id,
                )
                total.skipped += 1
                continue
            opponent_name = name_index.get(game_stream_id)
            if boxscores_dir is not None:
                result = game_loader.load_file(source, summary, opponent_name=opponent_name)
            else:
                result = game_loader.load_payload(source, summary, opponent_name=opponent_name)
            total.loaded += result.loaded
            total.skipped += result.skipped
            total.errors += result.errors
        return total

    # ------------------------------------------------------------------
    # Roster loading
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Season aggregate computation
    # ------------------------------------------------------------------

    def _compute_season_aggregates(self, team_id: int, season_id: str) -> None:
        """Recompute season aggregate stats from per-game rows.

        Thin signature-preserving delegate (E-237-03, TN-11) to the module-level
        canonical recompute in ``src.db.season_aggregates``.  Rate stats (AVG,
        OBP, ERA, WHIP) are NOT stored -- they are computed at display time.

        Args:
            team_id: INTEGER PK of the scouted team.
            season_id: Season slug.
        """
        from src.db.season_aggregates import canonical_recompute

        canonical_recompute(self._db, team_id, season_id)

    # ------------------------------------------------------------------
    # FK prerequisite helpers
    # ------------------------------------------------------------------

