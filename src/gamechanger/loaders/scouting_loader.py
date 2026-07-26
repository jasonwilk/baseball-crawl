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
    from src.db.paths import resolve_db_path
    from src.gamechanger.loaders.scouting_loader import ScoutingLoader
    from src.gamechanger.crawlers.scouting import ScoutingCrawlResult

    conn = sqlite3.connect(str(resolve_db_path()))
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
from src.db.reconcile_at_load import (
    GateOutcome,
    RosterRetireResult,
    snapshot_prior_loaded_game_ids,
)
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
            # The FULL schedule array -- deliberately NOT the completed subset
            # (E-267-02 AC-5). See ``_reconcile_absent_games``.
            full_games=crawl_result.games,
            # getattr, not attribute access: several tests pass a duck-typed
            # crawl-result stand-in. The default is False -- FAIL CLOSED. A
            # stand-in that omits the flag has made no claim about its fetch, and
            # a full-looking array from a partially-failed fetch would otherwise
            # be treated as healthy enough to retire. Every real
            # ``ScoutingCrawlResult`` carries the field, so production is
            # unaffected.
            schedule_fetch_ok=getattr(crawl_result, "schedule_fetch_ok", False),
        )

    def _load_team_core(
        self,
        team_id: int,
        roster_data: list[dict[str, Any]],
        games_index: dict[str, GameSummaryEntry],
        opponent_name_index: dict[str, str],
        *,
        boxscores: dict[str, dict[str, Any]] | None = None,
        full_games: list[dict[str, Any]] | None = None,
        schedule_fetch_ok: bool = True,
    ) -> LoadResult:
        """Roster + boxscore + season-aggregate orchestration for one team.

        Args:
            team_id: INTEGER PK of the scouted team.
            roster_data: Roster player dicts (empty list if none).
            games_index: ``game_stream_id -> GameSummaryEntry`` mapping.
            opponent_name_index: ``game_stream_id -> opponent name`` mapping.
            boxscores: ``game_stream_id -> boxscore payload`` mapping.
            full_games: The UNFILTERED fresh schedule array (all
                ``game_status`` values) for the game-grain reconcile. ``None``
                disables the reconcile entirely -- a direct caller with no
                schedule context must never trigger a retire.
            schedule_fetch_ok: Whether the schedule fetch succeeded.

        Returns:
            Aggregated ``LoadResult`` across roster and boxscore loading.
        """
        # Derive the canonical DB season_id from team metadata (not the crawl path).
        db_season_id, db_season_year = derive_season_id_for_team(self._db, team_id)
        ensure_season_row(self._db, db_season_id)

        # Roster snapshot taken BEFORE the roster upsert and the boxscore jersey
        # backfill touch team_rosters. That timing is the whole point: it is what
        # lets the roster reconcile tell a GENUINE departure (rostered before
        # this load began) from CHURN (a row this run's own backfill re-created
        # for a player who already appeared in a completed boxscore).
        #
        # LOAD-BEARING -- this decides what is retired, not just how it is
        # logged. It scopes the MAX_ROSTER_DEPARTURES cap
        # (``_cap_on_genuine_departures`` in reconcile_at_load), and passing an
        # empty set does NOT mean "no hint": it means every absence reads as
        # churn, so the cap counts zero departures and never fires. Do not drop
        # this SELECT as an optimization and do not pass ``set()`` at a call site
        # where the snapshot is inconvenient -- either silently disables the
        # SOLE guard that stops a truncated crawl from mass-deleting a roster.
        #
        # ⛔ STRENGTHENED at E-276-03, and the advice is unchanged -- only the
        # stakes are. This said "the guard", which was imprecise while a floor
        # ratio also stood underneath: a truncated crawl would still have been
        # refused by the floor even with an empty snapshot. **V1 removed that
        # floor.** ``MAX_ROSTER_DEPARTURES`` is now the only thing on this
        # grain, and it is computed as ``absent & previously`` -- so an empty
        # set here makes the cap count zero departures and permit
        # unconditionally, at any roster size, with nothing beneath it.
        #
        # ORDERING COUPLING, invisible at both ends (E-270-05): this is a bare
        # local that travels ~85 lines before use -- captured here, passed to
        # ``_reconcile_departed_roster`` near the end of this method, consumed
        # there as ``previously_rostered_ids``, whose only job is to scope the
        # departure cap to GENUINE departures (``absent & previously``, see
        # ``_cap_on_genuine_departures``). Both drift directions are silent and
        # they fail OPPOSITELY:
        #
        # * A team_rosters write placed ABOVE this SELECT (or this SELECT moved
        #   below one) pollutes the snapshot with rows THIS run created, so our
        #   own backfill churn counts as genuine departures and the cap
        #   false-refuses -- the self-trapping mode E-267 had to fix.
        # * A team_rosters write placed BELOW this SELECT creates rows OUTSIDE
        #   the snapshot; when they go absent they read as churn and do NOT count
        #   toward the cap, weakening the one guard that stops a truncated roster
        #   crawl from mass-deleting a roster.
        #
        # Safe edit: keep this SELECT the FIRST thing that touches team_rosters
        # in this method, and add no team_rosters write between it and the
        # ``_reconcile_departed_roster`` call. No signature enforces either.
        pre_load_roster_ids = {
            row[0]
            for row in self._db.execute(
                "SELECT player_id FROM team_rosters "
                "WHERE team_id = ? AND season_id = ?",
                (team_id, db_season_id),
            )
        }

        # GAME-grain capture anchor (E-276-02). The games loaded for this
        # team-season as of the START of this run -- the health gate's protected
        # population.
        #
        # Placement is forced from both sides. It sits BELOW the season-id
        # derivation because it keys on the DERIVED season id, and ABOVE the
        # boxscore load because that load is what writes new games. Reading it
        # later returns ``old | newly_completed``: the payload loader COMMITS PER
        # GAME, so each newly-completed game is already in the population when
        # the reconcile runs, and it raises the numerator and denominator
        # together -- relaxing the floor by half a game each. Newly-completed
        # games appear in ordinary operation (that is what re-scouting is for),
        # so stale absences that correctly refuse on their own start retiring
        # once enough new games load beside them. No isolation-level change
        # fixes that; the rows are committed, not merely visible-uncommitted.
        #
        # SECOND LONG-SPAN ORDERING COUPLING IN THIS METHOD, and like the roster
        # one above it is invisible at both ends and silent in BOTH drift
        # directions:
        #
        # * A ``games`` WRITE moved ABOVE this SELECT (or this SELECT moved below
        #   one) pollutes the snapshot with rows THIS run created -- which is
        #   precisely the defect E-276-02 exists to remove, reintroduced. The
        #   gate then measures ``|fresh| >= |stale|`` and reads healthy while
        #   authorizing the retire of genuinely stale games.
        # * The RECONCILE CALL hoisted ABOVE the boxscore load breaks a
        #   different, pre-existing coupling: ``game_loader.redirect_map`` is
        #   EMPTY until that load runs, so every redirected game's canonical id
        #   is missing from ``fresh_ids`` and reads as absent. Only the CAPTURE
        #   moves up; the CALL must stay below ``_load_boxscores``. See the
        #   ORDERING COUPLING note at the ``_reconcile_absent_games`` call.
        #
        # Safe edit: keep this SELECT above ``_load_boxscores`` and add no
        # ``games`` write between it and that load. Nothing in any signature
        # enforces either position.
        pre_load_game_ids = snapshot_prior_loaded_game_ids(
            self._db, team_id=team_id, season_id=db_season_id
        )

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

        # Game-grain reconcile (E-267-02): retire prior-loaded games the fresh
        # schedule no longer carries. Runs AFTER the boxscore load so the
        # redirect map is populated -- a cross-perspective redirect stores the
        # game under a canonical id that is NOT the fresh event id.
        #
        # ORDERING COUPLING (E-270-05): this call MUST stay below
        # ``_load_boxscores``, and BOTH failure directions are silent.
        # ``game_loader.redirect_map`` is EMPTY until that load runs, so a
        # reconcile hoisted above it finds every redirected game's canonical id
        # missing from ``fresh_ids`` and treats those live games as absent. What
        # happens next depends on a second, independent guard: under the SAME
        # hoist ``processed_event_ids`` is empty too, so ``boxscores_complete``
        # is False and every absence is REFUSED -- the grain silently stops
        # retiring anything at all, restoring the stale-game bug it exists to
        # close. It does not mass-delete today. But the guards are independent:
        # relax ``boxscores_complete`` on top of a hoist and the same absence
        # becomes a hard delete of live games and their full child surface --
        # bounded, though, by a THIRD guard, the ``MAX_GAME_RETIREMENTS`` cap,
        # which limits what survives that relaxation to at most two games and
        # refuses the pass entirely above it (measured, not inferred: with the
        # relaxation in place, 1 absent -> 1 retired, 2 -> 2, 3 -> 0 retired and
        # the whole pass refused). A hoist that makes MANY redirected games look
        # absent therefore trips the cap rather than emptying the season.
        # Nothing in the signature enforces any of these couplings -- an empty
        # ``redirect_map`` is indistinguishable from "no redirects this run".
        if full_games is not None:
            self._reconcile_absent_games(
                team_id, db_season_id, full_games,
                schedule_fetch_ok=schedule_fetch_ok,
                redirect_map=game_loader.redirect_map,
                prior_snapshot=pre_load_game_ids,
                # PARSED ids, not FETCHED ids: a boxscore can 200 and still
                # fail to parse, recording no redirect entry (Fable review).
                loaded_stream_ids=game_loader.processed_event_ids,
            )

        # Roster-grain reconcile (E-267-04): retire players the fresh roster
        # crawl no longer lists.
        #
        # Position is load-bearing in BOTH directions:
        #   * AFTER the boxscore load, because ``_upsert_roster_jersey`` backfills
        #     a team_rosters row for every player in every boxscore. Retiring at
        #     roster-load time would be immediately undone by the backfill
        #     re-adding a departed player who appears in an EARLIER game -- which
        #     is exactly the cut-mid-season case AC-5 is about.
        #   * BEFORE the dedup sweep, on RAW ids, for the same reason the
        #     player-line grain runs there (E-267-03 / TN-10 risk 2): dedup merges
        #     player_ids, so a post-dedup prior set diffed against raw crawl ids
        #     would mark the freshly-merged canonical "absent".
        self._reconcile_departed_roster(
            team_id, db_season_id, roster_data, pre_load_roster_ids,
        )

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

    def _reconcile_absent_games(
        self,
        team_id: int,
        season_id: str,
        full_games: list[dict[str, Any]],
        *,
        schedule_fetch_ok: bool,
        redirect_map: dict[str, str],
        loaded_stream_ids: set[str],
        prior_snapshot: frozenset[str],
    ) -> None:
        """Retire prior-loaded games the fresh schedule dropped (E-267-02).

        Threads the FULL schedule array -- every ``game_status`` value, NOT the
        ``completed`` subset the crawler filters for boxscore fetching (AC-5).
        GameChanger KEEPS not-final and long-past-unplayed games in the array, so
        diffing against the completed subset would classify every present
        not-final game as REMOVED and mass-delete live data.

        Two id sets are built from that array and handed to the shared retire
        helper:

        * ``fresh`` -- the PRESENCE set: every id in the array, UNION the
          canonical ids this run's redirects mapped fresh events onto. Without
          the redirect targets a cross-perspective twin (stored under the
          canonical id, which is not the fresh event id) would look absent and be
          retired.
        * ``not_final`` -- ids whose ``game_status`` is not ``"completed"``.
          Membership uses ``.get(...) == "completed"`` so an ABSENT key (the
          common not-final shape), ``null``, and the ``"new"`` unscored stub all
          land here.

        **The floor-ratio health gate takes its population from HERE** --
        ``prior_snapshot``, a required parameter of this method, captured by the
        caller ABOVE the boxscore load and threaded straight through to
        ``retire_absent_games`` (E-276-02). ⛔ **Do not "simplify" that threading
        away as redundant**: the helper cannot derive this population for itself,
        because by the time it runs this run's newly-loaded games are already
        COMMITTED (``load_payload`` commits per game), so any read it takes
        returns ``old | newly_completed``.

        ⚠️ This paragraph previously said the gate *"derives its own narrower
        population inside the helper (``prior & fresh``) rather than taking one
        from here"*, and justified it on the ground that upcoming and
        newly-completed games *"cannot be in the prior-loaded denominator"*.
        **Both halves are now false, and the second was ALWAYS false of
        newly-completed games** -- they appear in ordinary operation, that is
        what re-scouting is for, and each one joins the numerator AND the
        denominator, relaxing the floor by half a game. It is the same claim
        corrected in ``retire_absent_games``' own comment block, surviving in a
        second file. Upcoming games remain genuinely excluded, which is the true
        half that made the sentence read as sound.

        A boxscore fetch that skipped any completed game (``loaded_stream_ids``
        missing an id) makes the redirect map incomplete, so the pass refuses
        every absence rather than retire a canonical row whose fresh event
        simply failed to load.

        Failures roll back and are swallowed with an ERROR (mirroring the dedup
        sweep hook): the reconcile is a maintenance pass, and a broken one must
        not lose the boxscore load that already succeeded -- nor leave a partial
        retire to ride the caller's commit.
        """
        fresh_ids: set[str] = set()
        not_final_ids: set[str] = set()
        fresh_completed_ids: set[str] = set()
        for game in full_games:
            game_id = game.get("id")
            if not game_id:
                continue
            gid = str(game_id)
            fresh_ids.add(gid)
            if game.get("game_status") == "completed":
                fresh_completed_ids.add(gid)
            else:
                not_final_ids.add(gid)
        # A redirected game lives under the canonical id, not the fresh event id.
        redirect_targets = set(redirect_map.values())
        fresh_ids.update(redirect_targets)
        # INVARIANT: not_final_ids is a SUBSET of fresh_ids by construction --
        # the loop above adds every surviving gid to fresh_ids UNCONDITIONALLY
        # before the completed/not-final branch, and fresh_ids only grows after
        # (the redirect update). A `not_final_ids &= fresh_ids` line used to sit
        # here; it read as a filter but could never remove anything, so E-270-05
        # deleted it. Verified rather than reasoned: 8262 adversarial input
        # combinations (falsy/odd ids, every status shape, absent keys, six
        # redirect-map shapes) executed against this exact block produced zero
        # cases where the intersection differed, and an assertion of the
        # invariant held across all 179 invocations in a full suite run.
        #
        # If a future edit adds an id to not_final_ids on a path that does NOT
        # also add it to fresh_ids, this invariant breaks and a not-final game
        # could be classified REMOVED and hard-deleted. Keep the unconditional
        # `fresh_ids.add(gid)` above the branch.

        try:
            from src.db.reconcile_at_load import retire_absent_games

            retired = retire_absent_games(
                self._db,
                team_id=team_id,
                season_id=season_id,
                fresh_game_ids=fresh_ids,
                fetch_ok=schedule_fetch_ok,
                not_final_game_ids=not_final_ids,
                boxscores_complete=fresh_completed_ids <= loaded_stream_ids,
                prior_snapshot=prior_snapshot,
            )
            if retired.retired_game_ids or retired.refusals:
                logger.info(
                    "Game-grain reconcile for team_id=%d season=%s: retired=%d "
                    "refused=%d rows_deleted=%s",
                    team_id, season_id,
                    len(retired.retired_game_ids), len(retired.refusals),
                    retired.deleted_counts or "none",
                )
        except Exception:  # noqa: BLE001
            # Roll back FIRST so a partial retire cannot ride the commit at the
            # end of _load_team_core. The boxscore load is already committed
            # per-game by load_payload (and the roster load committed before
            # it), so in every ordinary case only this pass's own writes are
            # lost. Doubly-degenerate exception: if EVERY boxscore raised before
            # its own commit, the roster writes would still be pending here and
            # this rollback would discard them too. That needs two simultaneous
            # failures, and losing a roster upsert is strictly preferable to
            # committing a half-retired game, so the ordering stands.
            self._db.rollback()
            logger.error(
                "Game-grain reconcile failed for team_id=%d season=%s; rolled "
                "back the partial retire and continuing",
                team_id,
                season_id,
                exc_info=True,
            )

    def _pending_collapse_player_ids(
        self, team_id: int, season_id: str
    ) -> set[str] | None:
        """Ids a pending dedup COLLAPSE is about to merge -- not departures.

        The roster retire runs before ``dedup_team_players``, and dedup can only
        detect a duplicate while BOTH ids are co-rostered. Retiring one half
        first therefore destroys the detection signal and splits the human
        permanently (roster under the new id, stats under the old, no pair left
        to find). Asking the planner up front is what lets the retire tell "this
        row is a departure" from "this row is the same person under two ids".

        Uses ``plan_player_dedup`` -- the shared planner, NOT raw
        ``find_duplicate_players`` pairs. That distinction is the whole point:
        the planner separates EXECUTABLE collapses from REFUSED forks, and only
        collapse members may be exempt. Exempting a fork member would preserve a
        row the planner will never merge, i.e. a permanently unretirable roster
        entry -- swapping this defect for a worse one.

        This plan is computed for the EXEMPTION only; it is deliberately NOT
        executed here. The existing ``dedup_team_players`` sweep later in
        ``_load_team_core`` re-detects and performs the merges, so the shared
        ``plan_player_dedup`` / ``execute_collapse`` seam stays the single home
        for merge logic (executing here would mean either open-coding that in the
        loader or dropping the sweep that owns the refused-fork WARNs).

        The property that makes re-detection safe is a SUBSET relation, not
        equality::

            P1.collapses  ⊆  P2.collapses

        where ``P1`` is this plan and ``P2`` is the one the later sweep computes.
        A collapse is a connected component whose members are all co-rostered;
        every member is exempt here, so the retire deletes none of them, and
        deletions only ever remove nodes and edges -- never add them -- so each
        P1 component survives intact and is re-detected. That is exactly what the
        exemption needs: no id it protected can be stranded un-merged.

        The sets are NOT equal, and asserting so would be wrong. ``P2`` may
        contain collapses ``P1`` refused: if a fork is a stub plus
        ``{John Smith, Janet Smith}`` and Janet is absent from the fresh roster,
        she is correctly not exempt and is retired -- dropping the fork to a
        single pair, which ``P2`` then sees as an executable collapse. The sets
        differ only in that direction, which is harmless for the exemption's
        purpose.

        FAIL CLOSED (AC-8): a planner failure returns ``None`` -- distinct from
        an empty set, which legitimately means "no pending collapses" -- and the
        caller SKIPS the retire entirely for that run.

        Returning an empty set here would be fail-OPEN, and the error asymmetry
        forbids it. Skipping costs one stale roster row for a cycle, which the
        next successful crawl removes. Proceeding without exemptions is exactly
        the pre-round-3 behavior, which splits the identity PERMANENTLY -- roster
        under the new id, stats under the old, no co-rostered pair left for dedup
        to find, and no self-heal, because every later crawl re-backfills the old
        id and the retire removes it again before dedup runs. A transient failure
        must not be able to cause unrecoverable corruption.

        (An earlier version of this docstring defended fail-open as "restores the
        prior behavior". That is not a safety argument: the prior behavior is the
        defect being repaired.)

        Returns:
            The exempt id set, or ``None`` if the plan could not be computed.
        """
        try:
            from src.db.player_dedup import plan_player_dedup

            plan = plan_player_dedup(self._db, team_id, season_id=season_id)
        except Exception:  # noqa: BLE001 -- fail CLOSED, see above
            # Realistic, not contrived: this SQL runs on a connection sharing a
            # WAL file with the admin UI and the morning-run cron, so a lock
            # outlasting busy_timeout raises sqlite3.OperationalError. Before
            # AC-8 that transient blip deleted a roster row, prevented the merge,
            # and left a permanently split identity.
            logger.error(
                "Dedup pre-plan FAILED for team_id=%d season=%s; the roster "
                "retire cannot tell a departure from a pending merge without it.",
                team_id, season_id, exc_info=True,
            )
            return None

        exempt: set[str] = set()
        for collapse in plan.collapses:
            exempt.add(collapse.canonical_player_id)
            exempt.update(dup.player_id for dup in collapse.duplicates)
        if exempt:
            # LOAD-BEARING for AC-2a: the retire WARN's roster_db_count /
            # absent_count describe the CANDIDATE population (exempt ids are
            # filtered out before it is built), so this line is what lets an
            # operator reconcile those numbers against the visible roster. If it
            # is ever removed, the exempt count must move into the WARN itself.
            logger.info(
                "Roster retire: exempting %d id(s) pending a dedup collapse for "
                "team_id=%d season=%s: %s. (%d refused fork(s) deliberately NOT "
                "exempt -- a fork is never merged, so its members must stay "
                "retirable.)",
                len(exempt), team_id, season_id, sorted(exempt),
                len(plan.refused_forks),
            )
        return exempt

    def _reconcile_departed_roster(
        self,
        team_id: int,
        season_id: str,
        roster_data: list[dict[str, Any]],
        pre_load_roster_ids: set[str],
    ) -> RosterRetireResult:
        """Retire roster rows for players the fresh crawl dropped (E-267-04).

        Reuses the SAME empty-payload guard the roster load itself applies
        (``_load_roster_from_data`` skips an empty payload): an empty or absent
        roster crawl proves nothing and must never retire anyone. The stricter
        absolute drop cap lives in the helper via
        ``roster_departure_guard`` (TN-12).

        Failures are logged and swallowed, WITHOUT a rollback -- the same
        asymmetry the player-line grain documents. Every DELETE here is an
        independent leaf row, so a mid-loop failure is merely less-complete
        cleanup that the next re-scout retries; a rollback would additionally
        discard the game-grain reconcile's committed-pending work sharing this
        transaction, which is strictly worse than a partial roster cleanup.
        """
        fresh_player_ids = {
            player["id"] for player in roster_data if player.get("id")
        }
        if not fresh_player_ids:
            logger.info(
                "Empty roster payload for team_id=%d season=%s; retiring "
                "nothing (an empty crawl proves no departures).",
                team_id, season_id,
            )
            # SYNTHESIZE a result rather than returning None (E-276-03 AC-3).
            # This path returns BEFORE the helper runs, so without this the
            # mechanism that produced "0 retired" sits upstream of the record
            # meant to disambiguate it -- on the one grain that has no gate and
            # where ``refused_by`` is the only structural discriminator there is.
            return RosterRetireResult(
                refused=True,
                refusal_reason=(
                    "refused_by=empty_payload: the fresh roster payload carried "
                    "no player ids, so it proves no departures"
                ),
                gate_outcome=GateOutcome(
                    gate_evaluated=False, refused_by="empty_payload"
                ),
            )

        # FAIL CLOSED (AC-8): without the exemption plan this retire cannot tell
        # a departure from a pending merge, and guessing wrong splits the
        # identity permanently with no self-heal. A skipped run costs one stale
        # roster row until the next successful crawl.
        exempt_player_ids = self._pending_collapse_player_ids(team_id, season_id)
        if exempt_player_ids is None:
            logger.warning(
                "Roster retire SKIPPED for team_id=%d season=%s: the dedup "
                "pre-plan failed (see the preceding ERROR), so pending-merge "
                "ids cannot be distinguished from genuine departures. No roster "
                "row was retired; the next successful crawl will retire any "
                "real departures.",
                team_id, season_id,
            )
            # SYNTHESIZE, for the same reason as the empty-payload path above.
            return RosterRetireResult(
                refused=True,
                refusal_reason=(
                    "refused_by=skipped_no_exemption_plan: the dedup pre-plan "
                    "failed, so pending-merge ids cannot be told from genuine "
                    "departures"
                ),
                gate_outcome=GateOutcome(
                    gate_evaluated=False,
                    refused_by="skipped_no_exemption_plan",
                ),
            )

        try:
            from src.db.reconcile_at_load import retire_departed_roster_players

            result = retire_departed_roster_players(
                self._db,
                team_id=team_id,
                season_id=season_id,
                fresh_player_ids=fresh_player_ids,
                previously_rostered_ids=pre_load_roster_ids,
                exempt_player_ids=exempt_player_ids,
            )
            if result.retired_player_ids or result.refused:
                logger.info(
                    "Roster reconcile for team_id=%d season=%s: retired=%d "
                    "refused=%s (roster_db=%d fresh=%d absent=%d)",
                    team_id, season_id, len(result.retired_player_ids),
                    result.refused, result.roster_db_count,
                    result.fresh_crawl_count, result.absent_count,
                )
            return result
        except Exception:  # noqa: BLE001 -- cleanup must never lose a good load
            logger.error(
                "Roster reconcile failed for team_id=%d season=%s; the loaded "
                "roster and stats are unaffected.",
                team_id, season_id, exc_info=True,
            )
            # A CRASH must not be reportable as a clean pass. The default
            # ``RosterRetireResult`` carries ``gate_evaluated=False`` and
            # ``refused_by=None``, which reads as "nothing to decide" -- so a
            # caller that needs to tell a crash from a no-op must use the
            # returned object together with the ERROR above, not the row count.
            return RosterRetireResult()

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
                # ⚠️ CROSS-MODULE COUPLING, unguarded by any signature
                # (E-276-02 AC-8). ``event_id`` MUST come from ``game["id"]``,
                # the SAME key ``_reconcile_absent_games`` reads to build
                # ``fresh_ids``. That identity is what makes the game grain's
                # ``W subset-of fresh`` premise hold -- every ``games`` row this
                # run writes is keyed on an id the fresh array also carries --
                # and that premise is what makes deletion-neutrality structural
                # here rather than merely swept (epic TN-3 / TN-5).
                #
                # Note ``game_stream_id`` is set from the same field one line
                # below -- the near-miss to watch, since re-sourcing ``event_id``
                # from it (or from any other key) type-checks. Break the identity
                # and ``W - fresh`` becomes non-empty: the candidate set then
                # includes rows this run itself created and that the fresh array
                # does not carry.
                #
                # ⚠️ HOW LOUD that break is depends on the break, and the
                # tempting stronger claim -- "it passes every existing test and
                # fails silently" -- is FALSE as a general statement. MEASURED:
                # re-keying ``event_id`` to a value outside the fresh array
                # failed **91** unrelated tests, because the ``games`` rows land
                # under ids nothing else can find. A subtler break need not be
                # that loud, but this comment must not claim silence it cannot
                # support. What the test below buys is ATTRIBUTION -- it names
                # the coupling as the cause instead of leaving 91 failures, or a
                # quieter variant's mysterious retire, to be diagnosed from
                # scratch.
                #
                # Pinned by test_every_game_this_run_writes_is_in_the_fresh_array.
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

