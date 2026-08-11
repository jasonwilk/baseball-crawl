"""Duplicate-game merge.

Merges a duplicate ``games`` row into its canonical twin. A *twin* pair is the
same real-world game persisted under two distinct ``game_id`` values because it
was loaded from two DIFFERENT team perspectives (Defect A: the cross-perspective
game-dedup gap). Every FK child row of the losing ``games`` row is re-pointed (or
unioned) onto the canonical ``game_id``, then the losing ``games`` row itself is
deleted LAST.

This is the single canonical merge primitive shared by the in-pipeline twin
merge (E-261-03b, at the dedup redirect site) and the operator repair pass
(E-261-04, ``bb data merge-duplicate-games``), mirroring the "de-dup the dedup"
precedent where ``plan_player_dedup`` / ``execute_collapse`` are the one shared
home for player-merge logic (:mod:`src.db.player_dedup`). Detecting WHICH pairs
are twins is NOT this module's job -- callers decide and pass a merge decision;
this module only executes it.

Child-table surface (the six FK children of ``games``, verified against
``migrations/001_initial_schema.sql`` + later migrations, 2026-07-12):

* ``game_perspectives``       -- PK(game_id, perspective_team_id); unioned
* ``player_game_batting``     -- UNIQUE(game_id, player_id, perspective_team_id)
* ``player_game_pitching``    -- UNIQUE(game_id, player_id, perspective_team_id)
* ``plays``                   -- UNIQUE(game_id, play_order, perspective_team_id)
* ``spray_charts``            -- UNIQUE(event_gc_id, perspective_team_id, chart_type)
* ``reconciliation_discrepancies`` -- run-scoped UNIQUE incl. game_id + perspective

``play_events`` is NOT a direct child of ``games`` -- it FKs to ``plays(id)``, so
its rows follow their parent ``plays`` rows automatically when those rows have
their ``game_id`` re-pointed (the ``plays.id`` values are untouched). The dropped
``player_season_*`` aggregates (migration 011) are gone and carry no ``game_id``.

Refusal (AC-2): a genuine twin holds DISJOINT perspectives across its child
rows (the same game seen from two different teams). If the source and canonical
rows share ANY ``perspective_team_id``, the "twin" is not cleanly mergeable --
re-pointing the source's rows onto the canonical ``game_id`` would collide on a
perspective-scoped UNIQUE key. Rather than guess (mirroring the player-dedup
fork-refusal principle), the merge REFUSES and reports a structured result. The
refusal is decided by PRE-classification -- intersecting the two perspective
sets BEFORE any write -- NOT by catching a mid-merge ``IntegrityError``, so a
refusal leaves ZERO rows modified.

No-cascade reality: every ``games`` FK child is a PLAIN ``REFERENCES games(...)``
with NO ``ON DELETE CASCADE``. The losing ``games`` row is therefore deleted
LAST, after all children are re-pointed off it -- a premature ``games`` delete
aborts LOUDLY on the FK constraint rather than silently cascading child loss.

Transaction ownership (AC-3): this helper does NOT commit -- the CALLER owns the
transaction boundary, matching the ``merge_player_pair(manage_transaction=False)``
/ ``reload_game_plays`` precedent. Its rollback guarantee has a PRECONDITION: the
caller must hold an OPEN (non-autocommit) transaction. Under
``isolation_level=None`` each statement self-commits, so there is no rollback-able
transaction and a mid-merge failure would leave a partial merge committed. Given
an explicit open transaction (``BEGIN``/caller-managed) with
``PRAGMA foreign_keys=ON``, a mid-merge failure leaves the transaction
rollback-able with no partial merge visible after the caller rolls back.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# The six FK children of ``games`` that carry a re-pointable ``game_id`` and a
# ``perspective_team_id`` used for the disjointness pre-classification. Order is
# irrelevant for the perspective scan but the merge re-points in this order and
# deletes the ``games`` row LAST (no-cascade reality).
_PERSPECTIVE_CHILD_TABLES = (
    "player_game_batting",
    "player_game_pitching",
    "plays",
    "spray_charts",
    "reconciliation_discrepancies",
)


# ---------------------------------------------------------------------------
# Offline same-game predicate (E-261-03a, AC-7)
# ---------------------------------------------------------------------------
# The OFFLINE counterpart to the live schedule-count dedup signal in
# ``GameLoader._find_duplicate_game``. The operator repair pass (E-261-04,
# ``bb data merge-duplicate-games``) works over an ALREADY-PERSISTED DB where the
# incoming crawl's schedule-count is NOT available -- so this predicate EXCLUDES
# the live-only schedule-count gate and instead decides a twin from three inputs,
# ALL required (the merge deletes a ``games`` row, so the safeguards are pinned):
#
#   1. PRIMARY -- disjoint cross-perspective: the two rows carry NON-empty,
#      NON-overlapping ``perspective_team_id`` sets (the same game seen from two
#      different teams). An empty or overlapping set is NOT a clean twin.
#   2. Bounded score-tolerance CORROBORATION: pairwise scores match with at most
#      one side off by <= ``_SCORE_TOLERANCE_RUNS`` and the other side exact (the
#      observed 12-4 vs 12-5 shape). NULL scores cannot corroborate.
#   3. Near/matching play-count CORROBORATION (REQUIRED, not optional -- Codex
#      P1-2): both play counts must be > 0 and the smaller at least
#      ``_PLAY_COUNT_NEAR_RATIO`` of the larger. Missing/zero play data cannot
#      corroborate, so the predicate must NOT merge on disjoint + score alone.
_SCORE_TOLERANCE_RUNS = 1  # one side may differ by <=1 run with the other exact
_PLAY_COUNT_NEAR_RATIO = 0.85  # min(a, b) / max(a, b) must be >= this; both > 0


def _scores_within_tolerance(
    score_a: tuple[int | None, int | None],
    score_b: tuple[int | None, int | None],
) -> bool:
    """Bounded score-tolerance corroboration (one side exact, other <=1 run).

    Returns False if any of the four scores is None (a NULL cannot corroborate),
    else True iff one side matches exactly and the other differs by at most
    ``_SCORE_TOLERANCE_RUNS``. Exact agreement is the trivial pass.
    """
    home_a, away_a = score_a
    home_b, away_b = score_b
    if None in (home_a, away_a, home_b, away_b):
        return False
    if home_a == home_b and abs(away_a - away_b) <= _SCORE_TOLERANCE_RUNS:
        return True
    if away_a == away_b and abs(home_a - home_b) <= _SCORE_TOLERANCE_RUNS:
        return True
    return False


def _play_counts_near(count_a: int, count_b: int) -> bool:
    """Near/matching play-count corroboration (REQUIRED input).

    Both counts must be strictly positive (absent play data cannot corroborate)
    and the smaller must be at least ``_PLAY_COUNT_NEAR_RATIO`` of the larger.
    Two DISTINCT doubleheader games have independent play counts, so this weak
    corroboration is a required guard, never a standalone trigger.
    """
    if count_a <= 0 or count_b <= 0:
        return False
    lo, hi = sorted((count_a, count_b))
    return lo / hi >= _PLAY_COUNT_NEAR_RATIO


def is_offline_same_game(
    *,
    source_perspectives: set[int],
    canonical_perspectives: set[int],
    source_score: tuple[int | None, int | None],
    canonical_score: tuple[int | None, int | None],
    source_play_count: int,
    canonical_play_count: int,
) -> bool:
    """Decide whether two persisted ``games`` rows are the same real game (OFFLINE).

    The reusable predicate behind the E-261-04 operator repair pass. Returns True
    ONLY when ALL THREE conditions hold (see the module section comment above):
    disjoint cross-perspective (PRIMARY) AND bounded score-tolerance AND near
    play-count. It DELIBERATELY excludes the live-only schedule-count gate used
    by ``GameLoader._find_duplicate_game`` -- that context does not exist offline.

    The play-count input is REQUIRED, not optional: a disjoint + score-tolerance
    pair with absent/mismatched play data does NOT merge, because the merge
    deletes a ``games`` row and same-total doubleheaders can fool score-tolerance
    alone.

    Args:
        source_perspectives: ``perspective_team_id`` set of the duplicate row.
        canonical_perspectives: ``perspective_team_id`` set of the kept row.
        source_score: ``(home_score, away_score)`` of the duplicate row.
        canonical_score: ``(home_score, away_score)`` of the kept row.
        source_play_count: Number of ``plays`` rows on the duplicate row.
        canonical_play_count: Number of ``plays`` rows on the kept row.

    Returns:
        True iff the pair is a cleanly mergeable same-game twin under all three
        corroborated conditions; False otherwise (bias to refuse when ambiguous).
    """
    # 1. PRIMARY: disjoint cross-perspective (both non-empty, no overlap).
    if not source_perspectives or not canonical_perspectives:
        return False
    if source_perspectives & canonical_perspectives:
        return False
    # 2. Bounded score-tolerance corroboration.
    if not _scores_within_tolerance(source_score, canonical_score):
        return False
    # 3. REQUIRED near play-count corroboration.
    if not _play_counts_near(source_play_count, canonical_play_count):
        return False
    return True


class GameMergeError(Exception):
    """Raised when a duplicate-game merge is called with invalid arguments.

    This covers programming errors (same source/canonical id, a missing
    ``games`` row) -- NOT the expected AC-2 non-disjoint refusal, which is
    reported as a structured :class:`GameMergeResult` (``refused=True``) rather
    than raised.
    """


@dataclass
class GameMergeResult:
    """The outcome of a :func:`merge_duplicate_game` call.

    Attributes:
        source_game_id: The duplicate ``game_id`` that was merged away.
        canonical_game_id: The ``game_id`` that was kept.
        merged: True when the merge executed (source row deleted); False when
            refused.
        refused: True when the pair was refused as not cleanly mergeable
            (non-disjoint perspectives). Mutually exclusive with ``merged``.
        refusal_reason: Human-readable explanation when ``refused``; else None.
        shared_perspectives: The ``perspective_team_id`` values present on BOTH
            rows that triggered a refusal (empty on a successful merge).
        table_counts: Per-table count of child rows re-pointed onto the
            canonical ``game_id`` (only tables with a non-zero count appear).
    """

    source_game_id: str
    canonical_game_id: str
    merged: bool = False
    refused: bool = False
    refusal_reason: str | None = None
    shared_perspectives: list[int] = field(default_factory=list)
    table_counts: dict[str, int] = field(default_factory=dict)


def _game_perspective_set(conn: sqlite3.Connection, game_id: str) -> set[int]:
    """Return every ``perspective_team_id`` that has data for ``game_id``.

    The union of the authoritative ``game_perspectives`` junction rows AND the
    distinct perspectives present across the five perspective-bearing child
    tables. Using the union (not ``game_perspectives`` alone) is the defensive
    choice: a stat row could in principle exist for a perspective whose
    ``game_perspectives`` row is absent (the games-row/stat-row coupling is
    loose), and it is precisely such a row that would collide on a
    perspective-scoped UNIQUE during the merge -- so it MUST count toward the
    disjointness test. ``spray_charts.game_id`` is nullable, so its NULL-game
    rows are naturally excluded by the ``WHERE game_id = ?`` predicate.
    """
    perspectives: set[int] = set()
    for (persp,) in conn.execute(
        "SELECT perspective_team_id FROM game_perspectives WHERE game_id = ?",
        (game_id,),
    ):
        if persp is not None:
            perspectives.add(persp)
    for table in _PERSPECTIVE_CHILD_TABLES:
        for (persp,) in conn.execute(
            f"SELECT DISTINCT perspective_team_id FROM {table} WHERE game_id = ?",  # noqa: S608
            (game_id,),
        ):
            if persp is not None:
                perspectives.add(persp)
    return perspectives


def merge_duplicate_game(
    conn: sqlite3.Connection,
    source_game_id: str,
    canonical_game_id: str,
) -> GameMergeResult:
    """Merge the duplicate ``source_game_id`` into ``canonical_game_id``.

    Re-points every FK child row of the source ``games`` row onto the canonical
    ``game_id`` (perspectives unioned), then deletes the source ``games`` row
    LAST. Refuses (without modifying any row) when the pair is not a cleanly
    mergeable twin -- see the module docstring for the disjoint-perspective
    contract, the no-cascade delete-last reality, and the transaction-ownership
    precondition.

    This helper does NOT commit; the caller owns the transaction boundary. For
    the rollback guarantee to hold the caller MUST run inside an OPEN
    (non-autocommit) transaction with ``PRAGMA foreign_keys=ON``.

    Args:
        conn: An open sqlite3.Connection. FK enforcement should be ON so the
            delete-last ordering is validated by the engine.
        source_game_id: The duplicate ``game_id`` to merge away and delete.
        canonical_game_id: The ``game_id`` to keep and re-point children onto.

    Returns:
        A :class:`GameMergeResult`. On a clean merge ``merged=True``; on a
        non-disjoint pair ``refused=True`` with ``shared_perspectives`` naming
        the offending perspectives and no rows modified.

    Raises:
        GameMergeError: If ``source_game_id == canonical_game_id`` or either
            ``games`` row is missing.
        sqlite3.Error: If any SQL statement fails mid-merge (the caller's open
            transaction is left rollback-able; see the precondition above).
    """
    if source_game_id == canonical_game_id:
        raise GameMergeError(
            "source_game_id and canonical_game_id must be different "
            f"(both {source_game_id!r})"
        )

    if (
        conn.execute(
            "SELECT 1 FROM games WHERE game_id = ?", (source_game_id,)
        ).fetchone()
        is None
    ):
        raise GameMergeError(f"Source game {source_game_id!r} not found")
    if (
        conn.execute(
            "SELECT 1 FROM games WHERE game_id = ?", (canonical_game_id,)
        ).fetchone()
        is None
    ):
        raise GameMergeError(f"Canonical game {canonical_game_id!r} not found")

    result = GameMergeResult(
        source_game_id=source_game_id,
        canonical_game_id=canonical_game_id,
    )

    # ---------------------------------------------------------------------
    # AC-2 refusal: PRE-classify by intersecting the two perspective sets
    # BEFORE any write. A genuine cross-perspective twin has DISJOINT
    # perspectives; any overlap means the pair is not cleanly mergeable and
    # re-pointing would collide on a perspective-scoped UNIQUE key.
    # ---------------------------------------------------------------------
    source_perspectives = _game_perspective_set(conn, source_game_id)
    canonical_perspectives = _game_perspective_set(conn, canonical_game_id)
    shared = source_perspectives & canonical_perspectives
    if shared:
        result.refused = True
        result.shared_perspectives = sorted(shared)
        result.refusal_reason = (
            "not a cleanly mergeable twin: source and canonical share "
            f"perspective_team_id(s) {result.shared_perspectives} -- refusing "
            "rather than guessing (both rows carry data for the same perspective)"
        )
        logger.warning(
            "merge_duplicate_game refused: source=%s canonical=%s share "
            "perspective(s) %s; leaving both games unmerged",
            source_game_id,
            canonical_game_id,
            result.shared_perspectives,
        )
        return result

    # ---------------------------------------------------------------------
    # Re-point children onto the canonical game_id. Perspectives are disjoint
    # (pre-classified above), so every UPDATE below is collision-free; a
    # collision that somehow occurred would raise loudly (fail-fast) rather
    # than silently drop a row.
    # ---------------------------------------------------------------------

    # game_perspectives: union semantics (TN-3). The pair's perspective rows
    # are combined onto the canonical game via INSERT OR IGNORE, then the
    # source's rows are deleted. Disjointness makes IGNORE a no-op here, but it
    # keeps the "union" contract explicit and robust.
    # ⚠ This column list must name EVERY game_perspectives column. It is a COPY,
    # not a re-point, so a column omitted here is silently DROPPED on merge --
    # the row lands on the canonical game with that column reset to its default
    # while the perspective's plays are re-pointed intact, and it never
    # self-heals (whole-game plays idempotency skips the game forever).
    # `plays_final_*` was added to game_perspectives in migration 013 and had to
    # be added here too; `test_merge_preserves_every_game_perspectives_column`
    # fails if a future column is added to the table but not to this list.
    conn.execute(
        "INSERT OR IGNORE INTO game_perspectives "
        "(game_id, perspective_team_id, loaded_at, "
        " plays_final_home_score, plays_final_away_score) "
        "SELECT ?, perspective_team_id, loaded_at, "
        "       plays_final_home_score, plays_final_away_score "
        "FROM game_perspectives WHERE game_id = ?",
        (canonical_game_id, source_game_id),
    )
    gp_deleted = conn.execute(
        "DELETE FROM game_perspectives WHERE game_id = ?", (source_game_id,)
    ).rowcount
    if gp_deleted:
        result.table_counts["game_perspectives"] = gp_deleted

    # The five perspective-bearing children: plain re-point of game_id.
    # ``plays`` re-point carries ``play_events`` along automatically (they FK on
    # ``plays.id``, which is never touched).
    for table in _PERSPECTIVE_CHILD_TABLES:
        repointed = conn.execute(
            f"UPDATE {table} SET game_id = ? WHERE game_id = ?",  # noqa: S608
            (canonical_game_id, source_game_id),
        ).rowcount
        if repointed:
            result.table_counts[table] = repointed

    # Delete the losing games row LAST (no-cascade reality). By now every child
    # has been re-pointed off it, so the FK constraints are satisfied.
    conn.execute("DELETE FROM games WHERE game_id = ?", (source_game_id,))

    result.merged = True
    logger.info(
        "merge_duplicate_game complete: source %s merged into canonical %s "
        "(re-pointed %s)",
        source_game_id,
        canonical_game_id,
        result.table_counts or "no child rows",
    )
    return result


# ---------------------------------------------------------------------------
# Offline repair-pass detection + planning (E-261-04)
# ---------------------------------------------------------------------------
# The CLI-side detection/plan layer for ``bb data merge-duplicate-games``. It
# groups already-persisted games by the SAME natural key the live loader dedups
# on -- ``(season_id, game_date, unordered {home_team_id, away_team_id})`` (see
# ``GameLoader._find_duplicate_game``) -- and decides, per group, whether it is a
# cleanly mergeable cross-perspective twin (via the OFFLINE predicate
# :func:`is_offline_same_game`) or an ambiguous group to REFUSE. It only PLANS;
# the CLI executes each plan item through :func:`merge_duplicate_game` and owns
# the transaction boundary.

# Tables whose per-game row counts the dry-run preview reports (the six FK
# children; ``play_events`` is counted separately via ``plays``).
_PREVIEW_CHILD_TABLES = ("game_perspectives", *_PERSPECTIVE_CHILD_TABLES)


@dataclass
class GameMergePlan:
    """One planned duplicate-game merge (source -> canonical).

    ``canonical`` is the row kept; ``source`` is merged away and deleted. The
    perspectives are the single disjoint perspectives that identify the two as a
    cross-perspective twin. ``child_counts`` is the per-table row count that
    would be re-pointed off the source (dry-run preview).
    """

    season_id: str
    game_date: str
    team_pair: tuple[int, int]
    canonical_game_id: str
    source_game_id: str
    canonical_perspective: int
    source_perspective: int
    canonical_score: tuple[int | None, int | None]
    source_score: tuple[int | None, int | None]
    canonical_play_count: int
    source_play_count: int
    child_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class RefusedGameGroup:
    """A same-key game group the offline pass will NOT merge (bias to refuse).

    Covers a group of >= 3 rows (a doubleheader that was also cross-perspective
    loaded is 4 rows), a 2-row group whose perspectives are not disjoint
    singletons, and a 2-row group that fails the offline same-game corroboration
    (score-tolerance / near play-count). Left unmerged in both modes; surfaced
    as one WARN per group on ``--execute``.
    """

    season_id: str
    game_date: str
    team_pair: tuple[int, int]
    game_ids: list[str]
    reason: str


@dataclass
class GameDedupPlan:
    """The full offline plan: merges to apply + groups refused."""

    merges: list[GameMergePlan] = field(default_factory=list)
    refusals: list[RefusedGameGroup] = field(default_factory=list)


@dataclass
class StreamIdRestore:
    """A ``games`` row whose poisoned ``game_stream_id`` will be self-keyed.

    ``poisoned_value`` is the current (clobbered) ``game_stream_id`` that
    corroborates as a redirect source (it equals another row's ``game_id`` or a
    merged pair's now-deleted source id). The restore sets
    ``game_stream_id = game_id``.
    """

    game_id: str
    poisoned_value: str


def _play_count(conn: sqlite3.Connection, game_id: str) -> int:
    """Return the number of ``plays`` rows for a game."""
    return conn.execute(
        "SELECT COUNT(*) FROM plays WHERE game_id = ?", (game_id,)
    ).fetchone()[0]


def _child_row_counts(conn: sqlite3.Connection, game_id: str) -> dict[str, int]:
    """Per-child-table row count for a game (dry-run preview of a merge).

    Counts the six FK children plus ``play_events`` (which follow via ``plays``).
    Only tables with a non-zero count appear.
    """
    counts: dict[str, int] = {}
    for table in _PREVIEW_CHILD_TABLES:
        n = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE game_id = ?",  # noqa: S608
            (game_id,),
        ).fetchone()[0]
        if n:
            counts[table] = n
    play_events = conn.execute(
        "SELECT COUNT(*) FROM play_events e JOIN plays p ON p.id = e.play_id "
        "WHERE p.game_id = ?",
        (game_id,),
    ).fetchone()[0]
    if play_events:
        counts["play_events"] = play_events
    return counts


def plan_duplicate_game_merges(conn: sqlite3.Connection) -> GameDedupPlan:
    """Detect historical cross-perspective duplicate game pairs (OFFLINE).

    Groups completed games by ``(season_id, game_date, unordered team pair)`` --
    the natural key the live loader dedups on -- and classifies each multi-row
    group:

    * **Hard cardinality gate** (TN-5 / finding DE-4): merge ONLY a group of
      EXACTLY 2 rows whose perspectives are disjoint SINGLETONS. A group of >= 3
      rows is ambiguous (a doubleheader that was ALSO cross-perspective loaded is
      4 rows) -> REFUSE.
    * **Offline corroboration**: a 2-row candidate must additionally pass
      :func:`is_offline_same_game` (disjoint cross-perspective PRIMARY + bounded
      score-tolerance + near play-count, ALL required) -> else REFUSE.

    Canonical selection (deterministic, idempotent): the earlier-created row is
    kept (``games.created_at`` ascending, tie-broken by lexicographic
    ``game_id``), mirroring the live "first-loaded perspective wins" convention.

    Returns a :class:`GameDedupPlan`; it reads only and mutates nothing.
    """
    rows = conn.execute(
        """
        SELECT game_id, season_id, game_date, home_team_id, away_team_id,
               home_score, away_score, created_at
        FROM games
        WHERE status = 'completed'
        ORDER BY created_at ASC, game_id ASC
        """
    ).fetchall()

    # Group by the live dedup natural key: (season, date, unordered team pair).
    groups: dict[tuple[str, str, tuple[int, int]], list[tuple]] = {}
    for row in rows:
        _gid, season_id, game_date, home, away, _hs, _as, _created = row
        pair = (min(home, away), max(home, away))
        groups.setdefault((season_id, game_date, pair), []).append(row)

    plan = GameDedupPlan()
    for (season_id, game_date, pair), members in groups.items():
        if len(members) < 2:
            continue  # a lone game is not a duplicate

        game_ids = [m[0] for m in members]

        if len(members) > 2:
            # >= 3 rows: ambiguous (possible doubleheader also cross-perspective
            # loaded). Bias to refuse -- never guess which pair to collapse.
            plan.refusals.append(
                RefusedGameGroup(
                    season_id=season_id,
                    game_date=game_date,
                    team_pair=pair,
                    game_ids=game_ids,
                    reason=(
                        f"{len(members)} rows share this date/team-pair -- "
                        "ambiguous (a doubleheader that was also cross-perspective "
                        "loaded is 4 rows); refusing rather than guessing"
                    ),
                )
            )
            continue

        # Exactly 2 rows. members[0] is the earlier-created (ORDER BY above) ->
        # canonical; members[1] -> source.
        canonical_row, source_row = members[0], members[1]
        canonical_id = canonical_row[0]
        source_id = source_row[0]
        canonical_persps = _game_perspective_set(conn, canonical_id)
        source_persps = _game_perspective_set(conn, source_id)

        # Hard cardinality gate: each row must carry EXACTLY ONE perspective and
        # the two must be disjoint. A multi-perspective row is already merged (or
        # otherwise not a clean twin half) -> refuse.
        if (
            len(canonical_persps) != 1
            or len(source_persps) != 1
            or (canonical_persps & source_persps)
        ):
            plan.refusals.append(
                RefusedGameGroup(
                    season_id=season_id,
                    game_date=game_date,
                    team_pair=pair,
                    game_ids=game_ids,
                    reason=(
                        "not a disjoint single-perspective pair "
                        f"(perspectives {sorted(canonical_persps)} vs "
                        f"{sorted(source_persps)}); refusing"
                    ),
                )
            )
            continue

        canonical_score = (canonical_row[5], canonical_row[6])
        source_score = (source_row[5], source_row[6])
        canonical_plays = _play_count(conn, canonical_id)
        source_plays = _play_count(conn, source_id)

        if not is_offline_same_game(
            source_perspectives=source_persps,
            canonical_perspectives=canonical_persps,
            source_score=source_score,
            canonical_score=canonical_score,
            source_play_count=source_plays,
            canonical_play_count=canonical_plays,
        ):
            plan.refusals.append(
                RefusedGameGroup(
                    season_id=season_id,
                    game_date=game_date,
                    team_pair=pair,
                    game_ids=game_ids,
                    reason=(
                        "failed offline same-game corroboration "
                        f"(scores {canonical_score} vs {source_score}, "
                        f"plays {canonical_plays} vs {source_plays}); refusing"
                    ),
                )
            )
            continue

        plan.merges.append(
            GameMergePlan(
                season_id=season_id,
                game_date=game_date,
                team_pair=pair,
                canonical_game_id=canonical_id,
                source_game_id=source_id,
                canonical_perspective=next(iter(canonical_persps)),
                source_perspective=next(iter(source_persps)),
                canonical_score=canonical_score,
                source_score=source_score,
                canonical_play_count=canonical_plays,
                source_play_count=source_plays,
                child_counts=_child_row_counts(conn, source_id),
            )
        )

    return plan


def plan_stream_id_restores(
    conn: sqlite3.Connection,
    extra_redirect_sources: set[str] | None = None,
) -> list[StreamIdRestore]:
    """Detect ``games`` rows whose ``game_stream_id`` was clobbered (TN-5 / DE-4).

    A tracked-perspective game is self-keyed pre-clobber (``game_stream_id ==
    game_id`` -- ScoutingLoader is the sole populator, verified live). The pre-fix
    redirect clobber overwrote it with the redirect SOURCE event id. A row
    qualifies for restore ONLY when ALL hold:

    * ``game_stream_id`` is non-NULL and differs from ``game_id``.
    * **Hard corroboration**: the poisoned value equals another row's ``game_id``
      OR a merged pair's now-deleted source id (``extra_redirect_sources``). A
      bare value-differs check NEVER triggers a restore.
    * **Scope hardening**: the game carries NO member perspective (all of its
      perspectives are tracked). Any game with a member perspective is skipped --
      member-perspective rows are never modified.

    Idempotent: a restored row has ``game_stream_id == game_id`` and so no longer
    matches the differs predicate, making a re-run a no-op.

    Args:
        conn: Open connection.
        extra_redirect_sources: game_ids of pairs merged (and deleted) earlier in
            the SAME run -- their now-absent ids still corroborate a poison.

    Returns:
        The list of :class:`StreamIdRestore` items to apply (read-only).
    """
    extra = extra_redirect_sources or set()

    all_game_ids = {
        row[0] for row in conn.execute("SELECT game_id FROM games")
    }
    corroboration = all_game_ids | extra

    # Candidate rows: poisoned value, and NO member perspective on the game.
    candidates = conn.execute(
        """
        SELECT g.game_id, g.game_stream_id
        FROM games g
        WHERE g.game_stream_id IS NOT NULL
          AND g.game_stream_id != g.game_id
          AND NOT EXISTS (
              SELECT 1 FROM game_perspectives gp
              JOIN teams t ON t.id = gp.perspective_team_id
              WHERE gp.game_id = g.game_id
                AND t.membership_type = 'member'
          )
        """
    ).fetchall()

    restores: list[StreamIdRestore] = []
    for game_id, stream_id in candidates:
        # Hard corroboration: the poisoned value must actually be a redirect
        # source (another row's game_id or a merged-away source id).
        if stream_id in corroboration:
            restores.append(
                StreamIdRestore(game_id=game_id, poisoned_value=stream_id)
            )
    return restores


def restore_stream_id(conn: sqlite3.Connection, game_id: str) -> None:
    """Self-key one game's ``game_stream_id`` (``game_stream_id = game_id``).

    Does NOT commit -- the caller owns the transaction boundary (mirrors
    :func:`merge_duplicate_game`).
    """
    conn.execute(
        "UPDATE games SET game_stream_id = game_id WHERE game_id = ?", (game_id,)
    )
