"""Scouting loader for the baseball-crawl ingestion pipeline.

Consumes in-memory crawl results from ``ScoutingCrawler.scout_team()``
and loads them into the SQLite database.  Delegates per-game boxscore
loading to ``GameLoader.load_payload()`` (which handles all boxscore
parsing, player stubs, game records, and batting/pitching stat upserts).

Additional responsibilities beyond ``GameLoader``:
- Roster loading into ``players`` and ``team_rosters``.
- ``scouting_runs`` metadata tracking (status transitions, timestamps).
- A post-boxscore dedup sweep over same-team duplicate player entries.

Season lines are NOT computed here: since the E-259 cutover they are derived at
query time from the per-game tables (``src.api.db.get_season_*``), and the
stored ``player_season_*`` tables are dropped in E-259-03.

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

import logging
import sqlite3
from typing import TYPE_CHECKING, Any

from src.db.players import ensure_player_row
from src.gamechanger.loaders import LoadResult, derive_season_id_for_team, ensure_season_row
from src.gamechanger.loaders.game_loader import (
    GameLoader,
    GameSummaryEntry,
    _derive_game_date,
    _opt_int,
)
from src.gamechanger.types import TeamRef

if TYPE_CHECKING:
    # Import-time cycle: ``crawlers.scouting`` imports ``ensure_season_row`` from
    # the ``loaders`` package, so this annotation-only import must stay deferred.
    from src.gamechanger.crawlers.scouting import ScoutingCrawlResult

logger = logging.getLogger(__name__)

# run_type used by the scouting crawler for scouting_runs.
_RUN_TYPE = "full"


class ScoutingLoader:
    """Loads an in-memory scouting crawl result into the SQLite database.

    Delegates boxscore loading to ``GameLoader.load_payload()`` and adds
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
        crawl_result: ScoutingCrawlResult,
        team_id: int | None = None,
    ) -> LoadResult:
        """Load all scouting data from an in-memory crawl result.

        Accepts a ``ScoutingCrawlResult`` from the crawler, loads roster
        and boxscores from the in-memory data, and computes season aggregates.
        The DB ``season_id`` is always derived from team metadata.

        Args:
            crawl_result: ``ScoutingCrawlResult`` containing games, roster,
                and boxscores data.
            team_id: The opponent's INTEGER PK.  When ``None``, uses
                ``crawl_result.team_id``.

        Returns:
            Aggregated ``LoadResult`` across roster and boxscore loading.
        """
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

    def _load_team_core(
        self,
        team_id: int,
        roster_data: list[dict[str, Any]],
        games_index: dict[str, GameSummaryEntry],
        opponent_name_index: dict[str, str],
        *,
        boxscores: dict[str, dict[str, Any]] | None = None,
    ) -> LoadResult:
        """Roster + boxscore + season-aggregate orchestration for one team.

        Args:
            team_id: INTEGER PK of the scouted team.
            roster_data: Roster player dicts (empty list if none).
            games_index: ``game_stream_id -> GameSummaryEntry`` mapping.
            opponent_name_index: ``game_stream_id -> opponent name`` mapping.
            boxscores: ``game_stream_id -> boxscore payload`` mapping.

        Returns:
            Aggregated ``LoadResult`` across roster and boxscore loading.
        """
        # Derive the canonical DB season_id from team metadata (not the crawl path).
        db_season_id, db_season_year = derive_season_id_for_team(self._db, team_id)
        ensure_season_row(self._db, db_season_id)

        total = self._load_roster_from_data(roster_data, team_id, db_season_id)

        # Post-roster validation.
        expected_count = sum(1 for p in roster_data if p.get("id"))
        if expected_count:
            self._validate_roster_count(team_id, db_season_id, expected_count)

        # Empty-boxscore-source guard (E-247-01 F1): skip the whole post-boxscore
        # tail (dedup / commit) when there is no boxscore source to process THIS
        # invocation.  This is NOT an optimization -- the dedup sweep can MERGE
        # players, so on a populated DB a boxscoreless invocation would mutate
        # rows the pre-refactor early-returns left untouched.
        if not boxscores:
            logger.info(
                "No boxscores in crawl result for team_id=%d; nothing to load.",
                team_id,
            )
            return total

        # Build TeamRef for GameLoader by looking up gc_uuid and public_id.
        team_ref = self._build_team_ref(team_id)
        # Precompute the per-(local-date, opponent-name) schedule count so
        # GameLoader's tolerant same-game signal can tell a single game (score
        # disagreement across perspectives) from a real doubleheader (E-261-03a /
        # TN-4). ScoutingLoader holds the whole games_index; GameLoader sees one
        # summary at a time, so the count MUST be built here.
        schedule_counts = self._build_schedule_counts(games_index, opponent_name_index)
        game_loader = GameLoader(
            db=self._db,
            owned_team_ref=team_ref,
            created_team_ids=self._created_team_ids,
            schedule_counts=schedule_counts,
        )
        bs_result = self._load_boxscores(
            game_loader, games_index,
            boxscores=boxscores,
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

        # Hook 1: dedup sweep after boxscore loading. Collapses same-team
        # duplicate player entries; season aggregates are derived at query time
        # (E-259) so there is no post-dedup recompute.
        try:
            from src.db.player_dedup import dedup_team_players

            dedup_team_players(
                self._db, team_id, db_season_id,
                manage_transaction=False,
            )
        except Exception:  # noqa: BLE001
            logger.error(
                "Post-boxscore dedup sweep failed for team_id=%d season=%s; "
                "continuing",
                team_id,
                db_season_id,
                exc_info=True,
            )

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
            # Absent instant: leave last_scoring_update EMPTY so GameLoader routes
            # it through its absent-instant path and preserves the "1900-01-01"
            # sentinel. Do NOT fabricate a "1900-01-01T00:00:00Z" string -- since
            # E-253-04, GameLoader localizes any present instant via
            # derive_local_date, and that UTC-midnight sentinel would shift back a
            # day (America/Chicago -> "1899-12-31"). (E-253-11 Round-1 remediation.)
            start_ts = game.get("start_ts") or game.get("end_ts") or ""
            entry = GameSummaryEntry(
                event_id=str(game_id),
                game_stream_id=str(game_id),
                home_away=game.get("home_away"),
                # Missing public scores preserve NULL (not coerced to 0) via
                # _opt_int, so a scoreless doubleheader does not collapse under
                # _find_duplicate_game's natural-key dedup (E-253-06 AC-3).
                owning_team_score=_opt_int(score.get("team")),
                opponent_team_score=_opt_int(score.get("opponent_team")),
                opponent_id="",
                last_scoring_update=str(start_ts),
                start_time=game.get("start_ts"),
                timezone=game.get("timezone"),
            )
            index[entry.game_stream_id] = entry
        logger.info("Built games index from in-memory data: %d entries", len(index))
        return index

    def _build_schedule_counts(
        self,
        games_index: dict[str, GameSummaryEntry],
        opponent_name_index: dict[str, str],
    ) -> dict[tuple[str, str], int]:
        """Count OWN-schedule games per ``(local game_date, opponent name)``.

        Feeds ``GameLoader``'s tolerant same-game signal (E-261-03a / TN-4): a
        count of 1 vs a single DB candidate means "same real game, one book off
        by a run"; a count of 2 means a real doubleheader that must NOT collapse.

        The date is derived via the SHARED ``_derive_game_date`` seam so this key
        is byte-identical to the one ``_load_boxscore_data`` builds -- a mismatch
        would silently key-miss and disable the signal (finding E(b)).

        FAIL-CLOSED on an ambiguous date (Codex P1): a summary with NO resolvable
        opponent name could belong to ANY pair -- including a doubleheader partner
        of a resolved sibling on the same date. Merely dropping it (the old
        behavior) would UNDERCOUNT that pair to 1 and let the tolerant guard
        silently collapse a real doubleheader (the asymmetric hazard TN-4 names:
        deleted game data + masked pitcher-rest violation). So ANY date carrying
        an unresolved-opponent summary is treated as AMBIGUOUS and emits NO count
        at all -- every pair on that date then key-misses to a None count, and the
        loader declines the tolerant signal (falls back to exact-score match)
        rather than merging on a possibly-wrong count. A None-opponent summary
        only poisons its OWN date; unrelated resolved dates are unaffected.
        """
        # First pass: any date with an unresolved-opponent summary is ambiguous.
        ambiguous_dates: set[str] = set()
        for stream_id, summary in games_index.items():
            if opponent_name_index.get(stream_id) is None:
                ambiguous_dates.add(_derive_game_date(summary))

        # Second pass: count resolved games, skipping every summary on an
        # ambiguous date so the whole date fails closed (no count -> loader
        # declines) rather than failing open on an undercount.
        counts: dict[tuple[str, str], int] = {}
        for stream_id, summary in games_index.items():
            opponent_name = opponent_name_index.get(stream_id)
            if opponent_name is None:
                continue
            game_date = _derive_game_date(summary)
            if game_date in ambiguous_dates:
                continue
            key = (game_date, opponent_name)
            counts[key] = counts.get(key, 0) + 1
        return counts

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
        opponent_name_index: dict[str, str] | None = None,
    ) -> LoadResult:
        """Load each in-memory boxscore payload via ``GameLoader.load_payload``.

        Payloads are iterated in sorted ``game_stream_id`` order for determinism.
        A payload with no matching games entry is counted as ``skipped``.
        ``load_payload`` commits per game.
        """
        name_index = opponent_name_index or {}
        total = LoadResult()

        for game_stream_id, payload in sorted((boxscores or {}).items()):
            summary = games_index.get(game_stream_id)
            if summary is None:
                logger.warning(
                    "No games entry for game_stream_id=%s; skipping boxscore",
                    game_stream_id,
                )
                total.skipped += 1
                continue
            opponent_name = name_index.get(game_stream_id)
            result = game_loader.load_payload(payload, summary, opponent_name=opponent_name)
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
        """Warn if DB roster count exceeds the expected count from the crawl roster.

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
    # FK prerequisite helpers
    # ------------------------------------------------------------------

