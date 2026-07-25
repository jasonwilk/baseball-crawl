"""Reconcile-at-load: absence classification (E-267-01).

The load pipeline is accumulate-only -- a re-scout INSERTs and UPDATEs, but
nothing that vanished from GameChanger is ever retired, so a deleted game, a
removed boxscore line, or a departed roster player stays live in the DB forever.
This module is the shared primitive that fixes that going FORWARD, at load time
(TN-1): given what is already loaded (``prior_ids``) and what the FRESH crawl
returned (``fresh_ids``), it decides -- per id -- whether an absence is a genuine
REMOVAL (safe to retire) or a TRANSIENT one (keep the live data).

**No snapshot table.** The DB IS the prior-loaded set and the fresh in-memory
crawl is the authority, so there is no "last successful crawl" history to diff
against and no migration (TN-2). Corroboration is therefore a HEALTH gate on the
fresh payload, not a diff against history.

**Bias to refuse.** The load-bearing risk here is deleting live data because a
crawl hiccuped, so this classifier mirrors the refusal posture of
:func:`src.db.game_merge.is_offline_same_game`: an absence is REMOVED only when
the fresh crawl for that grain is *authoritative* -- it (a) fetched OK, (b)
returned a NON-EMPTY payload, and (c) did not shrink catastrophically
(``fresh_count >= prior_count * FLOOR_RATIO``). Any doubt -> TRANSIENT_ABSENT ->
the caller retires nothing. :func:`crawl_is_authoritative` computes that gate
from those three inputs; grains may pass a STRICTER guard of their own (see
below).

Retire convention (TN-4): a retire is a **HARD DELETE**. There is no soft-retire
marker, no ``is_retired`` column and no migration -- a marker would force a
``WHERE is_retired IS NULL`` filter into every reader (``get_season_batting`` /
``get_season_pitching``, ``_query_record``, ``_query_roster``,
``_query_freshness``, ``recon_scoreboard``), and missing one silently
re-inflates the stale row: precisely the failure class this work removes. Hard
delete makes correctness structural, consistent with every existing seam
(``merge_duplicate_game``, ``player_dedup``, ``lifecycle``). Auditability comes
from a WARN log line per retire, not from a reversible marker. A retire is
permitted ONLY for :attr:`AbsenceClass.REMOVED`.

Two contracts, deliberately split (AC-4):

* :func:`classify_absences` is **PURE** -- id sets in, classification out. No
  DB handle, no I/O, no logging. It decides nothing about *how* a retire
  happens.
* The grain RETIRE helpers (E-267-02 game / -03 player-line / -04 roster) own
  the DB side and follow the established seam convention: connection-in,
  **no-commit**, caller-owns-the-transaction (mirroring
  :func:`src.db.game_merge.merge_duplicate_game` and
  ``merge_player_pair(manage_transaction=False)``). They also own the LOGGING --
  one WARN per retire (what/why-REMOVED) and one WARN per refusal. This module
  emits neither.

The three grain result types model refusal DIFFERENTLY, and the divergence is
deliberate -- do not "harmonize" it:

* :class:`GameRetireResult` -- ``refusals: dict[game_id, reason]``
* :class:`PlayerLineRetireResult` -- ``refusals: dict[(table, team_id), reason]``
* :class:`RosterRetireResult` -- ``refused: bool`` + ``refusal_reason``

The first two refuse PER ID: one absent game or player line can be refused while
its neighbours are retired, so the reason has to be attributable to the
individual id (and, for player lines, to the table+team block that gated it).
The roster grain's refusal is a WHOLE-SET decision -- the
:data:`MAX_ROSTER_DEPARTURES` cap either permits this team-season's retire or
refuses all of it -- so a dict there would model a per-id granularity that does
not exist, inventing keys whose values are always identical. A reader moving
between the grains should expect ``.refusals`` in two of them and ``.refused``
in the third; that is the shape of the decisions, not drift. The verb split in
the entry points (``retire_absent_games`` / ``retire_absent_player_lines`` /
``retire_departed_roster_players``) follows the same principle: each names what
actually leaves.

What IS uniform across all three, and must stay so: connection-in / no-commit
(no ``commit()`` or ``rollback()`` anywhere in this module), both WARN classes
owned by the helper rather than the classifier, and the health-gate numerator
``comparable = set(prior_ids) & fresh`` -- the same population on both sides of
the floor ratio in every grain.

Grain-specific delete scoping (AC-5, TN-10 risk 1) -- the retire helpers must
key their set-difference AND their DELETE on:

* **game** grain -- the ``games`` row plus its full child surface, deleted
  atomically with the ``games`` row LAST (no ``ON DELETE CASCADE`` exists);
  DRY against ``game_merge._PERSPECTIVE_CHILD_TABLES`` + ``game_perspectives``
  (+ ``play_events`` via ``plays``).
* **player-line** grain -- ``player_game_batting`` / ``player_game_pitching``
  scoped by ``(game_id, perspective_team_id)``. The ``perspective_team_id``
  predicate is MANDATORY on both the diff and the DELETE: both tables carry it
  and the cross-perspective collision hazard is real. Only the ``player_game_*``
  leaf row is deleted, NEVER the ``players`` parent (TN-10 risk 6). The diff
  runs on RAW boxscore ids BEFORE the ``dedup_team_players`` sweep (risk 2).
* **roster** grain -- ``team_rosters`` scoped by the natural key
  ``(team_id, season_id)``. This table has NO ``perspective_team_id`` (PK is
  ``(team_id, player_id, season_id)``), so the perspective predicate does NOT
  apply here. Its drop cap is an absolute
  :data:`MAX_ROSTER_DEPARTURES`, not the flat floor ratio -- see below.

Per-grain corroboration beyond this classifier (applied by the grain helpers
using their own payload knowledge): a game present-but-scoreless / not-final is
TRANSIENT (postponed or in progress), only a game fully absent from the fresh
schedule is a removal candidate; a scored-but-EMPTY boxscore is the MODAL case
and must NEVER retire prior player lines; the roster grain keeps the existing
empty-payload guard in ``scouting_loader``.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Collection, Hashable
from dataclasses import dataclass, field
from enum import Enum

# DRY against the canonical duplicate-game merge seam (E-267-02 AC-1): the
# retire path must delete the SAME child surface the merge re-points, so both
# read from one list. Importing the private name is deliberate -- a second
# hand-maintained copy here is exactly the drift that produces a silent partial
# retire when a new FK child of ``games`` is added.
from src.db.game_merge import _PERSPECTIVE_CHILD_TABLES

logger = logging.getLogger(__name__)

# Universal catastrophic-shrink floor (TN-2). A fresh payload holding less than
# half of what is already loaded is treated as a broken crawl, not as a mass
# deletion. This is the UNIVERSAL MINIMUM strictness -- a grain may refuse on a
# SMALLER shrink via ``extra_guard``, but never on a larger one.
FLOOR_RATIO = 0.5

# Roster-grain absolute drop cap (TN-12). A 12-15 player roster makes the flat
# 0.5 floor far too loose -- losing 5 of 13 players is catastrophic yet passes a
# ratio gate. The roster retire helper (E-267-04) supplies this as an
# ``extra_guard``: more than two departures in one run REFUSES the whole roster
# retire for that run. Only DELETEs are capped; the ADD path is never gated.
MAX_ROSTER_DEPARTURES = 2

# Game-grain absolute retirement cap (E-270-01, TN-3). The flat 0.5 floor lets an
# alarming ABSOLUTE mass-delete through from underneath: 8 of 30 games is 27% and
# sails past the ratio, yet each of those eight retires destroys a whole game's
# child surface (batting/pitching lines, plays, play_events, spray points,
# reconciliation rows). So the milder-failure roster grain had the stronger guard
# and the harshest-failure grain had none. This cap closes that, composed WITH
# the existing ``boxscores_complete`` signal (both must permit).
#
# Value 2 (operator decision 2026-07-21). api-scout's 1200+-record envelope found
# no mechanism by which ``GET /public/teams/{public_id}/games`` silently drops
# prior-loaded COMPLETED games: it is un-paginated, a truncated body is a JSON
# PARSE error rather than a short valid array, and the only observed
# genuine-removal vector is a scorekeeper voiding ONE game at a time. The cap is
# therefore a backstop against an UNOBSERVED mode, which is exactly why it is set
# tight and matches the :data:`MAX_ROSTER_DEPARTURES` precedent -- a refused
# retire is loud and self-heals on the next clean crawl, a wrong delete is
# irreversible.
#
# It counts RETIRE-ELIGIBLE absences only (``absent - exempt``) -- see the
# deadlock note at the ``exempt`` precompute in :func:`retire_absent_games`.
MAX_GAME_RETIREMENTS = 2


class AbsenceClass(str, Enum):
    """How one prior-loaded id compares against the fresh crawl.

    Attributes:
        PRESENT: The id is in the fresh crawl. Nothing to do.
        REMOVED: The id is absent from an AUTHORITATIVE fresh crawl -- it is
            genuinely gone upstream. This is the ONLY value that permits a
            retire (hard delete, per TN-4).
        TRANSIENT_ABSENT: The id is absent, but the fresh crawl could not be
            trusted to prove it (fetch failure, empty payload, catastrophic
            shrink, or a stricter per-grain guard). Keep the live data; the
            caller retires nothing and logs one WARN per refusal.
    """

    PRESENT = "present"
    REMOVED = "removed"
    TRANSIENT_ABSENT = "transient_absent"


def crawl_is_authoritative(
    *,
    fetch_ok: bool,
    fresh_count: int,
    prior_count: int,
) -> bool:
    """Health gate on the FRESH payload for one grain (TN-2).

    The fresh crawl may be trusted to prove an absence only when ALL THREE
    conditions hold. Any failure means the caller must treat every absence in
    that grain as transient:

    1. ``fetch_ok`` -- the fetch itself succeeded (an exception, a non-2xx, or a
       timeout upstream means the caller passes False).
    2. ``fresh_count > 0`` -- an empty payload proves nothing. Note this is
       checked independently of the ratio: with ``prior_count == 0`` the ratio
       test is vacuously satisfied, so the empty check must stand alone.
    3. ``fresh_count >= prior_count * FLOOR_RATIO`` -- no catastrophic shrink.

    The floor is deliberately NOT a parameter. AC-2 makes
    :data:`FLOOR_RATIO` the UNIVERSAL MINIMUM strictness, and an overridable
    ratio would let a grain pass a LOOSER value (``floor_ratio=0.1``) and
    weaken that minimum through a knob this module advertises. A grain that
    needs to be STRICTER expresses it through :func:`classify_absences`'s
    ``extra_guard``, whose narrowing-only property is structural rather than
    documentary -- one sanctioned strictness mechanism, no asymmetry.

    Args:
        fetch_ok: Whether the fresh fetch for this grain succeeded.
        fresh_count: Size of the fresh payload for this grain.
        prior_count: Size of the prior-loaded set for this grain.

    Returns:
        True iff the fresh crawl is complete enough to prove a removal.
    """
    if not fetch_ok:
        return False
    if fresh_count <= 0:
        return False
    return fresh_count >= prior_count * FLOOR_RATIO


def classify_absences(
    prior_ids: Collection[Hashable],
    fresh_ids: Collection[Hashable],
    *,
    crawl_authoritative: bool,
    extra_guard: Callable[[frozenset[Hashable]], bool] | None = None,
) -> dict[Hashable, AbsenceClass]:
    """Classify each prior-loaded id against the fresh crawl (PURE, AC-1/AC-4).

    A pure function over id sets: no DB handle, no I/O, no logging. Every id in
    ``prior_ids`` gets exactly one classification. Ids present in ``fresh_ids``
    but NOT in ``prior_ids`` are ADDs -- they are not this function's concern and
    do not appear in the result.

    Both id arguments are typed :class:`~collections.abc.Collection`, NOT
    ``Iterable``, and that narrowing is deliberate: this function materializes
    each argument with ``set(...)``, so a one-shot iterator (a generator, a
    ``map``, an open cursor) would be silently EXHAUSTED by the call. Exhausting
    a caller's iterator is a caller-visible side effect and would contradict the
    purity contract, so callers must pass a re-iterable collection.

    Bias to refuse (AC-2): when ``crawl_authoritative`` is False, or when
    ``extra_guard`` rejects the absent set, EVERY absence is classified
    :attr:`AbsenceClass.TRANSIENT_ABSENT` -- never :attr:`AbsenceClass.REMOVED`.
    The classifier only classifies; the caller emits the WARN per refusal and
    performs (or declines) the hard delete.

    Args:
        prior_ids: The ids already loaded in the DB for this grain, scoped by
            that grain's delete key (see the module docstring: player-line by
            ``(game_id, perspective_team_id)``, roster by ``(team_id,
            season_id)``).
        fresh_ids: The ids the fresh crawl returned for the SAME scope.
        crawl_authoritative: The health gate from
            :func:`crawl_is_authoritative`. False -> refuse all absences.
        extra_guard: Optional STRICTER per-grain guard, called with the frozen
            set of absent ids; returning False refuses every absence this run.
            The roster grain supplies the :data:`MAX_ROSTER_DEPARTURES` cap here
            (TN-12), since the flat floor ratio is too loose for a 12-15 roster.

    Returns:
        ``{id: AbsenceClass}`` covering every id in ``prior_ids``.
    """
    prior = set(prior_ids)
    fresh = set(fresh_ids)
    absent = frozenset(prior - fresh)

    # ORDERING IS LOAD-BEARING (the extra_guard cannot-widen invariant): the
    # health gate is applied FIRST and the guard is consulted ONLY when removal
    # is already permitted. ``extra_guard`` can therefore only ever NARROW the
    # decision -- a permissive guard can never resurrect a removal that the
    # health gate refused. Do NOT collapse this into
    # ``extra_guard(absent) if extra_guard else crawl_authoritative``: that
    # inverts the safety posture and would let a partial-payload crawl
    # hard-delete live rows. Pinned by test_permissive_guard_cannot_widen.
    permit_removal = crawl_authoritative
    if permit_removal and extra_guard is not None and absent:
        permit_removal = bool(extra_guard(absent))

    absence_class = (
        AbsenceClass.REMOVED if permit_removal else AbsenceClass.TRANSIENT_ABSENT
    )
    return {
        prior_id: (
            AbsenceClass.PRESENT if prior_id in fresh else absence_class
        )
        for prior_id in prior
    }


def roster_departure_guard(
    absent_ids: frozenset[Hashable],
    *,
    max_departures: int = MAX_ROSTER_DEPARTURES,
) -> bool:
    """Roster-grain ``extra_guard``: absolute departure cap (TN-12).

    Returns False (refuse the whole roster retire for this run) when more than
    ``max_departures`` roster entries are absent. A 12-15 player roster losing
    three or more players in a single crawl is far more likely a partial roster
    payload than three genuine departures, and the flat :data:`FLOOR_RATIO`
    would happily wave that through.

    Intended to be passed as ``extra_guard`` to :func:`classify_absences` by the
    roster retire helper (E-267-04).
    """
    return len(absent_ids) <= max_departures


# ---------------------------------------------------------------------------
# GAME grain retire helper (E-267-02)
# ---------------------------------------------------------------------------
# The first caller of the classifier above. Connection-in, NO-COMMIT, caller
# owns the transaction (the seam convention shared with ``merge_duplicate_game``
# and ``merge_player_pair(manage_transaction=False)``), and it owns the LOGGING:
# one WARN per retire and one WARN per refusal.
#
# Delete surface (AC-1): the full child surface of the ``games`` row, with the
# ``games`` row deleted LAST. No FK child of ``games`` carries
# ``ON DELETE CASCADE``, so delete-last is load-bearing -- a premature ``games``
# delete aborts LOUDLY on the FK constraint instead of silently orphaning rows.
# ``play_events`` is not a direct child (it FKs ``plays.id``), so it is deleted
# through its parent ``plays`` rows FIRST.
_GAME_CHILD_TABLES = ("game_perspectives", *_PERSPECTIVE_CHILD_TABLES)


@dataclass
class GameRetireResult:
    """Outcome of one :func:`retire_absent_games` pass over a team's games.

    Attributes:
        retired_game_ids: The ``game_id`` values hard-deleted this pass.
        refusals: ``{game_id: reason}`` for every prior-loaded game that was a
            candidate but was NOT retired (bias to refuse). One WARN was emitted
            per entry.
        deleted_counts: Per-table count of child rows deleted across all
            retires (only non-zero tables appear).
    """

    retired_game_ids: list[str] = field(default_factory=list)
    refusals: dict[str, str] = field(default_factory=dict)
    deleted_counts: dict[str, int] = field(default_factory=dict)


def _prior_loaded_game_ids(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> list[str]:
    """The games THIS perspective has already loaded for ``season_id``.

    Scoped by ``game_perspectives.perspective_team_id`` rather than by
    home/away membership: the set-difference asks "what did MY crawl load and
    my fresh crawl no longer returns", so a game another team's perspective
    loaded is none of this pass's business.

    Materialized to a ``list`` -- :func:`classify_absences` takes a
    ``Collection``, and a raw cursor would be silently exhausted.
    """
    return [
        row[0]
        for row in conn.execute(
            """
            SELECT DISTINCT g.game_id
            FROM games g
            JOIN game_perspectives gp ON gp.game_id = g.game_id
            WHERE gp.perspective_team_id = ?
              AND g.season_id = ?
            """,
            (team_id, season_id),
        )
    ]


def _other_perspectives(
    conn: sqlite3.Connection, game_id: str, team_id: int
) -> list[int]:
    """Perspectives OTHER than ``team_id`` that also loaded ``game_id``."""
    return sorted(
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT perspective_team_id FROM game_perspectives "
            "WHERE game_id = ? AND perspective_team_id != ?",
            (game_id, team_id),
        )
        if row[0] is not None
    )


def _foreign_perspective_child_rows_exist(
    conn: sqlite3.Connection, game_id: str, team_id: int
) -> bool:
    """Does another perspective still hold CHILD stat rows on ``game_id``?

    The IDEA-159 guard (E-270-01). :func:`_other_perspectives` reads
    ``game_perspectives`` and nothing else, so a game whose FOREIGN junction row
    was stripped -- a partial cleanup, an interrupted merge -- reads as
    single-perspective while the other team's batting lines, pitching lines,
    plays, spray points and reconciliation rows are all still attached to it. A
    whole-game retire would then hard-delete data this grain has no business
    touching, silently, because the only guard looked at the one table that was
    already gone.

    **Guard surface == delete surface (TN-2, binding).** The tables are read from
    the SAME :data:`~src.db.game_merge._PERSPECTIVE_CHILD_TABLES` constant that
    :func:`_delete_game_and_children` loops -- never a hand-written list. A
    hand-list that omitted ``reconciliation_discrepancies`` would wave through
    precisely the game whose only foreign footprint is a reconciliation row: the
    same hole, one table narrower. Reading the constant makes the guard cover
    EXACTLY what the delete removes, so a future sixth child table extends both
    at once with zero drift.

    Existence semantics (``LIMIT 1``, early return): one foreign row anywhere in
    the five tables is the whole answer, and this runs once per prior-loaded game
    in the cap's ``exempt`` precompute.

    Note the ``!= ?`` predicate also excludes a NULL ``perspective_team_id``
    (SQL three-valued logic), which is correct -- a row that names no perspective
    is not evidence of a FOREIGN one. All five tables declare the column
    ``NOT NULL`` anyway.
    """
    for table in _PERSPECTIVE_CHILD_TABLES:
        row = conn.execute(
            f"SELECT 1 FROM {table} "  # noqa: S608
            "WHERE game_id = ? AND perspective_team_id != ? LIMIT 1",
            (game_id, team_id),
        ).fetchone()
        if row is not None:
            return True
    return False


def _game_is_cross_perspective_protected(
    conn: sqlite3.Connection, game_id: str, team_id: int
) -> bool:
    """Would a whole-game retire of ``game_id`` destroy ANOTHER team's data?

    ONE predicate, TWO branches, and there are exactly TWO call sites, both in
    :func:`retire_absent_games` (TN-2): the cap's ``exempt`` precompute, and the
    retire loop's refusal GATE. That sharing is the point: if the cap counted a
    game the loop then refuses, the refused game would recur in ``absent`` on
    every run forever and eventually push the count over
    :data:`MAX_GAME_RETIREMENTS` permanently -- false-refusing every genuine
    removal after it. Exempt and refusal must be the SAME decision, and routing
    both through this one function makes that structural rather than
    test-caught.

    **Adding a third protection branch here is therefore SAFE, and that is the
    whole reason this function exists**: both the exemption and the refusal pick
    it up in the same commit, so the cap can never drop a game from its count
    that the loop still deletes. The only thing a new branch does NOT get for
    free is its own WARN reason string -- see the ``else`` fallback at the loop's
    refusal gate, which names the gap explicitly rather than letting the game
    through.

    The branches:

    * :func:`_other_perspectives` non-empty -- a foreign ``game_perspectives``
      row exists (the E-267 guard). Catches a scored-but-EMPTY foreign
      perspective that carries zero child rows.
    * :func:`_foreign_perspective_child_rows_exist` -- foreign CHILD rows
      survive even though the junction row does not.

    :func:`_other_perspectives` is deliberately NOT widened to fold these
    together (IDEA-159 scope note): a game with ONE legitimate perspective
    must stay retirable, or removed single-perspective games -- the ordinary
    case this grain exists for -- become permanently unretirable.

    The WARN reason strings stay separate at the call site: this returns a bare
    bool, and the loop re-checks the branches individually BELOW its gate --
    purely to name which one fired, never to make the decision.
    """
    if _other_perspectives(conn, game_id, team_id):
        return True
    return _foreign_perspective_child_rows_exist(conn, game_id, team_id)


def _delete_game_and_children(
    conn: sqlite3.Connection, game_id: str
) -> dict[str, int]:
    """Hard-delete one game's FULL child surface, ``games`` row LAST (AC-1).

    Returns the per-table deleted-row counts (non-zero tables only). Does NOT
    commit -- the caller owns the transaction, so a mid-delete failure leaves a
    rollback-able partial state rather than a half-retired game.
    """
    counts: dict[str, int] = {}

    # play_events first: it FKs ``plays.id``, so its rows must go before their
    # parent plays rows are deleted below.
    n = conn.execute(
        "DELETE FROM play_events WHERE play_id IN "
        "(SELECT id FROM plays WHERE game_id = ?)",
        (game_id,),
    ).rowcount
    if n:
        counts["play_events"] = n

    for table in _GAME_CHILD_TABLES:
        n = conn.execute(
            f"DELETE FROM {table} WHERE game_id = ?",  # noqa: S608
            (game_id,),
        ).rowcount
        if n:
            counts[table] = n

    # LAST, after every child is gone (no ON DELETE CASCADE exists).
    n = conn.execute("DELETE FROM games WHERE game_id = ?", (game_id,)).rowcount
    if n:
        counts["games"] = n
    return counts


def retire_absent_games(
    conn: sqlite3.Connection,
    *,
    team_id: int,
    season_id: str,
    fresh_game_ids: Collection[str],
    fetch_ok: bool,
    not_final_game_ids: Collection[str],
    boxscores_complete: bool,
) -> GameRetireResult:
    """Retire prior-loaded games the FRESH schedule no longer contains (AC-1).

    The game-grain retire helper. A prior-loaded game is retired only when it is
    absent from the FULL fresh schedule array AND the fresh crawl passes the
    :func:`crawl_is_authoritative` health gate. Everything else is refused with a
    WARN (bias to refuse).

    **``fresh_game_ids`` MUST be built from the FULL schedule array, NOT from the
    ``game_status == "completed"`` subset** (AC-5). GameChanger KEEPS not-final
    and long-past-unplayed games in the schedule array, so diffing against the
    completed subset would classify every legitimately-present not-final game as
    REMOVED and mass-delete live data. Because GC provably retains those games,
    a game FULLY ABSENT from the full array IS a genuine removal/void rather than
    a postponement (AC-6) -- no extra per-game suspicion clause is needed.

    Refusal cases, each logged as exactly one WARN:

    * The health gate failed (fetch error, empty payload, catastrophic shrink) --
      every absence this pass is refused.
    * More than :data:`MAX_GAME_RETIREMENTS` RETIRE-ELIGIBLE games are absent
      (E-270-01) -- the absolute cap on top of the floor ratio, since 8 of 30
      games is only a 27% shrink and would otherwise sail through. Refuses the
      whole pass. See the TN-1 note at the ``exempt`` precompute for why the
      count excludes cross-perspective-protected games.
    * The prior-loaded game is present in the fresh array but NOT final
      (``not_final_game_ids``) -- postponed, in progress, or an unscored stub.
    * The game also carries ANOTHER perspective's data -- either a foreign
      ``game_perspectives`` row, or (E-270-01) foreign CHILD stat rows that
      outlived a stripped junction row. Hard-deleting the ``games`` row would
      destroy a second team's load, and this grain deletes whole games; the
      narrower per-perspective cleanup is the player-line grain's job
      (E-267-03).

    Does NOT commit -- the caller owns the transaction boundary.

    Args:
        conn: Open connection, ``PRAGMA foreign_keys=ON`` (so delete-last is
            engine-validated).
        team_id: The perspective whose crawl produced ``fresh_game_ids``.
        season_id: Season scope for the prior-loaded set.
        fresh_game_ids: Every game id in the FULL fresh schedule array, plus the
            canonical ids the load pass redirected fresh games onto (a
            cross-perspective redirect stores the game under the canonical id,
            which is NOT the fresh event id -- omitting those would make every
            redirected game look removed). Used for PRESENCE; the floor-ratio
            health gate derives its own narrower population from it (see the
            comment at the ``comparable`` assignment).
        fetch_ok: Whether the fresh schedule fetch succeeded.
        not_final_game_ids: Ids present in the fresh array whose
            ``game_status`` is not ``"completed"`` (absent key, ``null``, or
            ``"new"``).
        boxscores_complete: Whether EVERY completed game in the fresh array was
            actually loaded this run. False refuses every absence (composed with
            the :data:`MAX_GAME_RETIREMENTS` cap into the single
            ``extra_guard``). This is not a nicety: ``fresh_game_ids`` gets its
            redirect-canonical entries from the load pass, so a game whose
            boxscore fetch failed contributes no redirect entry, and its
            canonical row would look absent and be falsely retired.

    Returns:
        A :class:`GameRetireResult` naming what was retired and what was refused.
    """
    result = GameRetireResult()

    prior_ids = _prior_loaded_game_ids(conn, team_id, season_id)
    if not prior_ids:
        return result

    fresh = set(fresh_game_ids)
    not_final = set(not_final_game_ids)
    # HEALTH-GATE population != PRESENCE population. Presence diffs against the
    # FULL fresh array (AC-5), but the floor-ratio backstop counts ONLY the
    # prior-loaded games the fresh array still vouches for -- ``prior & fresh``.
    # Both sides of the ratio are then drawn from the same population, so the
    # gate reduces to the clean invariant "refuse if MORE THAN HALF of what we
    # loaded has vanished", and no id can inflate the numerator without being
    # eligible for the denominator.
    #
    # Two population mismatches were tried and rejected here, both of which
    # silently raise the deletion cap above 0.5 * prior:
    #   * the whole fresh array -- upcoming games are never in prior, so a
    #     truncated-but-200 response padded with future games sails through
    #     (15 prior vs an 8-entry array passes 8 >= 7.5 and deletes 11);
    #   * the fresh COMPLETED set -- newly-completed games are not in prior
    #     either, and they appear in normal operation (that is what re-scouting
    #     is for), lifting a 15-game cap from 7.5 to 10.5 deletions.
    # A prior game that merely reverted to not-final still counts as vouched-for
    # (it is in the array), which is what keeps a single status reversion on a
    # small schedule from reading as a collapsed payload.
    comparable = set(prior_ids) & fresh
    authoritative = crawl_is_authoritative(
        fetch_ok=fetch_ok, fresh_count=len(comparable), prior_count=len(prior_ids)
    )

    # CAP POPULATION (E-270-01, TN-1). The cap counts RETIRE-ELIGIBLE absences
    # -- ``absent - exempt`` -- never raw ``len(absent)``, and that distinction is
    # the difference between a backstop and a permanent deadlock.
    #
    # A cross-perspective-owned game is in THIS team's prior set, can go missing
    # from THIS perspective's fresh schedule (a redirect this run did not
    # record), classifies REMOVED, and is then refused-and-KEPT by the loop
    # below. It never leaves ``prior``, so it recurs in ``absent`` on EVERY
    # subsequent run. Count those toward the cap and a team that accumulates
    # MAX_GAME_RETIREMENTS of them can never retire anything again: the next run
    # carrying one genuine removal has ``len(absent) > cap`` and the WHOLE pass
    # is refused, forever -- restoring the stale-game bug this grain exists to
    # close. That is the roster grain's backfill-churn deadlock reproduced (see
    # ``_cap_on_genuine_departures``), and it is not hypothetical: api-scout's
    # 636-record probe found ~4% of stored game_ids absent from the queried
    # team's own array, and ALL of them were cross-perspective twins -- ~22 false
    # removals on a 583-game corpus, which would trip a cap of 2 constantly.
    #
    # Excluding them does not weaken the mass-delete protection: they are not
    # deletable by this grain in the first place, a genuine truncation still
    # leaves plenty of DELETABLE games absent to trip the cap, and FLOOR_RATIO is
    # untouched as the gross-truncation backstop.
    #
    # Precomputed ONCE here and closed over, so the guard itself stays a pure
    # function of the frozen absent set with no connection -- the same shape as
    # the roster grain's ``previously`` closure. ``absent`` is derived first
    # because it is a pure set difference over two already-materialized sets:
    # computing it here needs no connection and does not touch
    # ``classify_absences``, which recomputes the identical set from the identical
    # inputs.
    #
    # The comprehension is scoped to ``absent`` rather than to all of
    # ``prior_ids``: only ``absent - exempt`` and ``exempt & absent`` are ever
    # consumed, so a PRESENT game's protection status is unobservable, and every
    # entry of it costs up to six single-row queries. On the ordinary run -- a
    # re-scout with nothing missing -- that is ZERO queries instead of ~180 for a
    # 30-game season, on a path morning-run walks once per team. The guard still
    # SUBTRACTS rather than assuming ``exempt`` and its own ``absent_ids`` agree,
    # so this stays correct if the scoping is ever widened back.
    absent = frozenset(prior_ids) - fresh
    exempt = frozenset(
        game_id
        for game_id in absent
        if _game_is_cross_perspective_protected(conn, game_id, team_id)
    )
    retire_eligible_absent = absent - exempt

    def _guard(absent_ids: frozenset[Hashable]) -> bool:
        # Short-circuiting ``and``: BOTH conditions narrow, either alone refuses
        # (TN-3). ``classify_absences`` consults this only AFTER the health gate
        # already permitted removal, so it can only ever tighten.
        return (
            boxscores_complete
            and len(absent_ids - exempt) <= MAX_GAME_RETIREMENTS
        )

    classification = classify_absences(
        prior_ids, fresh, crawl_authoritative=authoritative,
        extra_guard=_guard,
    )

    # WHICH gate refused (TN-4). All three are WHOLE-SET decisions, so the reason
    # is settled once here rather than per game, and the three causes are named
    # apart: an operator seeing "8 games vanished" needs to know whether that was
    # a suspected partial crawl (the floor), an incomplete boxscore load (the
    # redirect map is unreliable), or a legitimate-looking mass removal above the
    # cap -- the remedies differ. Only the cap case names MAX_GAME_RETIREMENTS.
    if not authoritative:
        transient_reason = (
            "absent from the fresh schedule, but the fresh crawl is not "
            f"authoritative (fetch_ok={fetch_ok}, "
            f"fresh_comparable_count={len(comparable)}, "
            f"prior_count={len(prior_ids)}, floor_ratio={FLOOR_RATIO}, "
            f"boxscores_complete={boxscores_complete})"
        )
    elif not boxscores_complete:
        transient_reason = (
            "absent from the fresh schedule, but boxscores_complete=False -- a "
            "completed game in the fresh array was not loaded this run, so the "
            "redirect map is incomplete and a canonical row can look absent "
            "when it is not"
        )
    else:
        transient_reason = (
            f"retire-eligible absent count {len(retire_eligible_absent)} exceeds "
            f"MAX_GAME_RETIREMENTS={MAX_GAME_RETIREMENTS} (raw absent "
            f"{len(absent)}, of which {len(exempt & absent)} are "
            "cross-perspective protected) -- a mass removal this large is far "
            "more likely a truncated schedule than that many genuine voids"
        )

    for game_id in sorted(prior_ids):
        absence = classification[game_id]

        if absence is AbsenceClass.PRESENT:
            if game_id in not_final:
                reason = (
                    "present in the fresh schedule but NOT final "
                    "(postponed, in progress, or an unscored stub)"
                )
                result.refusals[game_id] = reason
                logger.warning(
                    "Game-grain retire REFUSED for game %s (team %s, season %s): "
                    "%s; keeping the prior-loaded data.",
                    game_id, team_id, season_id, reason,
                )
            continue

        if absence is AbsenceClass.TRANSIENT_ABSENT:
            result.refusals[game_id] = transient_reason
            logger.warning(
                "Game-grain retire REFUSED for game %s (team %s, season %s): "
                "%s; keeping the prior-loaded data.",
                game_id, team_id, season_id, transient_reason,
            )
            continue

        # REMOVED -- but never delete a games row another perspective owns. The
        # DECISION is the shared predicate, and it is the SAME call the cap's
        # ``exempt`` set is built from (TN-2), so a game refused here cannot have
        # been counted against MAX_GAME_RETIREMENTS and a protection branch added
        # to the predicate later widens the refusal and the exemption TOGETHER.
        #
        # The individual helpers are re-checked strictly BELOW this gate, and
        # only to name which branch fired in the WARN. Do NOT lift them back into
        # the decision (``others = ...; if others:`` / ``elif foreign...``). That
        # form is behaviourally identical TODAY and no test can tell the two
        # apart -- which is exactly the hazard: it re-opens the drift in the
        # DELETE direction on a destructive path. A third branch would then widen
        # ``exempt`` (dropping the game from the cap count) while the loop still
        # refused on the old two, and the game would be hard-deleted -- losing
        # precisely the data the new branch was added to protect. The ``else``
        # below is what keeps such a branch safe from the moment it is added,
        # before anyone gets round to writing its reason string.
        #
        # The ``else`` is NOT dead code and NOT belt-and-braces, so do not prune
        # it or mark it no-cover. What it protects against is specific to this
        # loop's shape: ``reason`` is a FUNCTION-scope local reused across
        # iterations (the not-final branch above binds it too). Drop the ``else``
        # and a protected game matching no named branch either raises
        # ``UnboundLocalError`` on the first such game, or -- once ``reason`` is
        # already bound from an EARLIER game -- silently records that earlier
        # game's message against this one. The retire is still refused either
        # way (the ``continue`` below is unconditional, so no delete is
        # reachable from inside this gate); the damage is a MISLABELLED WARN on
        # a destructive path, naming the wrong cause in the one record TN-4
        # makes the operator's sole signal for why a retire was refused.
        #
        # It is reachable today, too, but only in a bounded window -- do not
        # over-read it. In the ordinary case this pass is entered with NO open
        # transaction (``load_payload`` commits per boxscore, and
        # ``_load_team_core`` early-returns when there are none), and Python's
        # ``sqlite3`` opens an implicit transaction only before DML -- so the
        # gate and the two re-checks are separate bare SELECTs sharing no
        # snapshot of the WAL file, and a concurrent writer removing the foreign
        # row in between leaves the gate saying protected and both re-checks
        # saying no. That window CLOSES at this pass's first hard delete: the
        # implicit BEGIN before that DELETE is never committed here (no-commit
        # convention -- the caller commits), so every later read runs inside a
        # write transaction that is snapshot-isolated and excludes other WAL
        # writers. Not a vanishing window, though -- a pass whose absent games
        # are ALL protected never deletes, so every gate read stays inside it.
        #
        # Pinned by test_protection_with_no_matching_reason_still_refuses (the
        # first-refusal / UnboundLocalError case) and
        # test_unmatched_protection_does_not_inherit_a_previous_games_reason
        # (the stale-carryover case).
        if _game_is_cross_perspective_protected(conn, game_id, team_id):
            others = _other_perspectives(conn, game_id, team_id)
            if others:
                reason = (
                    f"also loaded by perspective(s) {others}; a whole-game "
                    "delete would destroy another team's data"
                )
            elif _foreign_perspective_child_rows_exist(conn, game_id, team_id):
                reason = (
                    "no foreign game_perspectives row survives, but child stat "
                    "row(s) under another perspective_team_id do; a whole-game "
                    "delete would destroy another team's data"
                )
            else:
                reason = (
                    "cross-perspective protected by a branch this message does "
                    "not name -- a protection branch was added to "
                    "_game_is_cross_perspective_protected without a matching "
                    "reason string; a whole-game delete would destroy another "
                    "team's data"
                )
            result.refusals[game_id] = reason
            logger.warning(
                "Game-grain retire REFUSED for game %s (team %s, season %s): "
                "%s; keeping the prior-loaded data.",
                game_id, team_id, season_id, reason,
            )
            continue

        counts = _delete_game_and_children(conn, game_id)
        result.retired_game_ids.append(game_id)
        for table, n in counts.items():
            result.deleted_counts[table] = result.deleted_counts.get(table, 0) + n
        logger.warning(
            "Game-grain retire: hard-deleted game %s (team %s, season %s) -- "
            "REMOVED from an authoritative fresh schedule (%d comparable fresh "
            "vs %d prior). Rows deleted: %s",
            game_id, team_id, season_id, len(comparable), len(prior_ids),
            counts or "none",
        )

    return result


# ---------------------------------------------------------------------------
# PLAYER-LINE grain retire helper (E-267-03)
# ---------------------------------------------------------------------------
# Same seam convention as the game grain above: connection-in, NO-COMMIT, caller
# owns the transaction, helper owns the WARN logging.
#
# Scope (TN-10 risk 1): BOTH the set-difference AND the DELETE are keyed on
# ``(game_id, perspective_team_id)``. GameChanger issues DIFFERENT ``player_id``
# values per perspective for the same human, so an unscoped delete would reap the
# OTHER perspective's rows and corrupt that team's report. This is
# perspective-provenance applied to deletes.
#
# Leaf-only (TN-10 risk 6): only the ``player_game_*`` row is deleted, NEVER the
# ``players`` parent -- other games, other perspectives, and ``team_rosters`` all
# reference it.

#: ``(label, table)`` for the two per-player stat tables. Batting and pitching
#: are reconciled INDEPENDENTLY: they carry different player populations (a
#: batter who never pitched is legitimately absent from the pitching group), so
#: a single merged diff would retire every position player's... nothing, and
#: every pitcher's batting line. Separate diffs, separate health gates.
_PLAYER_LINE_TABLES: tuple[tuple[str, str], ...] = (
    ("batting", "player_game_batting"),
    ("pitching", "player_game_pitching"),
)


@dataclass(frozen=True)
class PlayerLineBlock:
    """One team's side of a boxscore, as the reconcile sees it.

    A boxscore carries TWO team blocks and BOTH are written under the SAME
    ``perspective_team_id`` (distinguished only by ``team_id``), so the reconcile
    must treat them as two independently-gated candidate sets rather than one
    union. A half-populated payload -- own block with stats, opponent block with
    ``stats: []`` -- is real, and a single global "populated" flag would let the
    populated half authorize retiring the empty half's prior lines.

    Attributes:
        team_id: The participant team this block's rows belong to
            (``player_game_*.team_id``, NOT ``perspective_team_id``).
        batting_player_ids: Player ids in this block's lineup groups.
        pitching_player_ids: Player ids in this block's pitching groups.
        populated: Whether THIS block carried at least one per-player stat row.
            False -> this block's prior lines are never retired.
    """

    team_id: int
    batting_player_ids: frozenset[str]
    pitching_player_ids: frozenset[str]
    populated: bool


@dataclass
class PlayerLineRetireResult:
    """Outcome of one :func:`retire_absent_player_lines` pass.

    Keyed by ``(table, team_id)`` because each team block in the boxscore is
    gated independently -- a single per-table key would collide between the two
    sides and hide one of them.

    Attributes:
        retired: ``{(table, team_id): [player_id, ...]}`` hard-deleted.
        refusals: ``{(table, team_id): reason}`` for a block whose absences were
            all refused (bias to refuse). One WARN was emitted per entry.
        uncovered_team_ids: ``team_id`` values holding prior rows for this
            game+perspective that NO block in this payload covers, so they could
            not be reconciled at all (see the residual note on
            :func:`retire_absent_player_lines`). Reported, never retired.
    """

    retired: dict[tuple[str, int], list[str]] = field(default_factory=dict)
    refusals: dict[tuple[str, int], str] = field(default_factory=dict)
    uncovered_team_ids: list[int] = field(default_factory=list)

    @property
    def total_retired(self) -> int:
        return sum(len(v) for v in self.retired.values())


def _prior_line_player_ids(
    conn: sqlite3.Connection,
    table: str,
    game_id: str,
    perspective_team_id: int,
    team_id: int,
) -> list[str]:
    """Player ids already loaded into ``table`` for this game/perspective/team.

    Scoped by ``team_id`` as well as ``perspective_team_id`` so each boxscore
    block is diffed against only its own side's rows.

    Materialized to a ``list`` -- :func:`classify_absences` takes a
    ``Collection`` and would silently exhaust a raw cursor.
    """
    return [
        row[0]
        for row in conn.execute(
            f"SELECT player_id FROM {table} "  # noqa: S608
            "WHERE game_id = ? AND perspective_team_id = ? AND team_id = ?",
            (game_id, perspective_team_id, team_id),
        )
    ]


def retire_absent_player_lines(
    conn: sqlite3.Connection,
    *,
    game_id: str,
    perspective_team_id: int,
    blocks: Collection[PlayerLineBlock],
) -> PlayerLineRetireResult:
    """Retire per-player stat rows the fresh boxscore no longer lists (AC-1).

    A prior ``player_game_batting`` / ``player_game_pitching`` row is hard-deleted
    only when the fresh boxscore block covering it is POPULATED and that specific
    player is absent from it.

    **A bare HTTP 200 is NOT authority to retire** (TN-11, and the load-bearing
    correctness rule of this grain). The MODAL opponent-scouting boxscore is
    "scored but EMPTY": the envelope and the lineup/pitching categories are all
    present, but every per-player ``stats`` array is ``[]``. Treating that as
    proof that the players are gone would retire live lines on the single most
    common shape in the data. Populated-ness is therefore derived from the
    per-player ``stats`` arrays, never from the status code -- and a 404 or 401
    never reaches this function at all, because no payload is loaded.

    **Populated-ness is PER BLOCK, and that is load-bearing.** A boxscore's two
    team blocks are both written under ONE ``perspective_team_id``, so an earlier
    shape of this function unioned them and gated both with a single global flag.
    A HALF-populated payload (own block with stats, opponent block ``stats: []``)
    then let the populated half authorize retiring the empty half: with 5 own
    players fresh and 3 stale opponent lines, ``comparable`` is 5 against a prior
    of 8, which clears ``5 >= 4`` and hard-deletes all 3. The floor ratio offers
    no protection there -- the condition reduces to
    ``|populated side| >= |empty side's prior|``, a coin flip at real roster
    sizes. Each block is therefore diffed and gated INDEPENDENTLY, scoped by
    ``team_id``.

    Health gate: ``prior & fresh`` is the numerator against ``prior`` as the
    denominator, so both sides of the floor ratio are drawn from the SAME
    population (the E-267-02 lesson). A brand-new player id inflating the
    numerator would raise the deletion cap above half the prior lines, and here
    that matters twice over -- a re-issued ``player_id`` for the same human is
    exactly what ``dedup_team_players`` exists to merge, so an id churn should
    REFUSE rather than delete.

    **Uncovered-row residual (deliberate, and deliberately NOT closed).** Rows
    whose ``team_id`` matches no block are left untouched -- no fresh evidence
    covers them, so bias-to-refuse applies. Two production shapes reach this:
    an absent opponent block (``_detect_team_keys`` finds no opponent key, so
    the payload carries only one side), and opponent ``team_id`` churn (a
    re-scout resolving the opponent to a different ``teams.id``, stranding the
    old rows). Such rows are then permanently unreconcilable by this grain.

    Widening the retire to cover them would REINTRODUCE the false-delete this
    function's per-block design exists to prevent -- an uncovered ``team_id`` is
    precisely a side for which the payload carries no evidence, which is the
    "empty block" case wearing a different hat. So the residual is made
    OBSERVABLE instead of closed: uncovered team ids are reported on
    :attr:`PlayerLineRetireResult.uncovered_team_ids` and logged, turning a
    silent permanent-stale hole into a monitored one.

    Does NOT commit -- the caller owns the transaction boundary.

    Args:
        conn: Open connection.
        game_id: The canonical game id (post-redirect).
        perspective_team_id: The perspective whose crawl produced the payload.
            Scopes both the diff and the DELETE (TN-10 risk 1).
        blocks: One :class:`PlayerLineBlock` per team block present in the
            payload (typically two: own and opponent).

    Returns:
        A :class:`PlayerLineRetireResult`.
    """
    result = PlayerLineRetireResult()

    for block in blocks:
        for label, table in _PLAYER_LINE_TABLES:
            prior_ids = _prior_line_player_ids(
                conn, table, game_id, perspective_team_id, block.team_id
            )
            if not prior_ids:
                continue

            fresh = set(
                block.batting_player_ids
                if label == "batting"
                else block.pitching_player_ids
            )
            comparable = set(prior_ids) & fresh
            authoritative = crawl_is_authoritative(
                fetch_ok=block.populated,
                fresh_count=len(comparable),
                prior_count=len(prior_ids),
            )
            classification = classify_absences(
                prior_ids, fresh, crawl_authoritative=authoritative
            )

            absent = sorted(
                pid
                for pid, cls in classification.items()
                if cls is not AbsenceClass.PRESENT
            )
            if not absent:
                continue

            if not authoritative:
                reason = (
                    "the fresh boxscore block is not authoritative for this "
                    f"grain (payload_populated={block.populated}, "
                    f"fresh_comparable_count={len(comparable)}, "
                    f"prior_count={len(prior_ids)}, floor_ratio={FLOOR_RATIO})"
                )
                result.refusals[(table, block.team_id)] = reason
                logger.warning(
                    "Player-line retire REFUSED for %s on game %s (perspective "
                    "%s, team %s): %d prior line(s) absent (%s) but %s; keeping "
                    "the prior-loaded data.",
                    label, game_id, perspective_team_id, block.team_id,
                    len(absent), ", ".join(absent), reason,
                )
                continue

            for player_id in absent:
                # Leaf row ONLY (risk 6), perspective- AND team-scoped (risk 1).
                conn.execute(
                    f"DELETE FROM {table} WHERE game_id = ? AND player_id = ? "  # noqa: S608
                    "AND perspective_team_id = ? AND team_id = ?",
                    (game_id, player_id, perspective_team_id, block.team_id),
                )
            result.retired[(table, block.team_id)] = absent
            logger.warning(
                "Player-line retire: hard-deleted %d stale %s line(s) on game %s "
                "(perspective %s, team %s) -- absent from a POPULATED fresh "
                "boxscore block (%d comparable fresh vs %d prior). Players: %s",
                len(absent), label, game_id, perspective_team_id, block.team_id,
                len(comparable), len(prior_ids), ", ".join(absent),
            )

    _report_uncovered_team_ids(
        conn, result, game_id, perspective_team_id, blocks
    )
    return result


def _report_uncovered_team_ids(
    conn: sqlite3.Connection,
    result: PlayerLineRetireResult,
    game_id: str,
    perspective_team_id: int,
    blocks: Collection[PlayerLineBlock],
) -> None:
    """Record + log prior rows no payload block covered (the residual).

    Changes NO behavior -- nothing is retired here -- but it is the difference
    between a permanently-stale row someone can notice and one that is invisible
    forever.

    The log line is deliberately detailed rather than minimal, because it is the
    ONLY diagnostic trail for a downstream symptom the reader cannot explain on
    its own. ``_completed_games_with_data`` in ``src/reports/generator.py``
    scopes its ``player_game_*`` EXISTS subqueries by ``perspective_team_id``
    ONLY, with no ``team_id`` predicate (verified against that query) -- so a
    single stale uncovered row keeps its game counted in N, can hold the
    coach-facing "Through {date}" at a game with no live data, and suppresses the
    ``N == 0`` silent-empty-report gate. The stat VALUES stay correct (all four
    aggregates are ``team_id``-scoped); it is the game COUNT and freshness date
    that drift. That downstream query is pre-existing and out of this story's
    scope, so this log is what gives an operator chasing a suspicious
    "Through {date}" a trail back to the cause -- hence game_id, perspective,
    the uncovered team ids, AND the row count each is holding.
    """
    covered = {block.team_id for block in blocks}
    uncovered: set[int] = set()
    row_counts: dict[int, int] = {}
    for _label, table in _PLAYER_LINE_TABLES:
        for team_id, row_count in conn.execute(
            f"SELECT team_id, COUNT(*) FROM {table} "  # noqa: S608
            "WHERE game_id = ? AND perspective_team_id = ? GROUP BY team_id",
            (game_id, perspective_team_id),
        ):
            if team_id is not None and team_id not in covered:
                row_counts[team_id] = row_counts.get(team_id, 0) + row_count
                uncovered.add(team_id)
    if not uncovered:
        return
    result.uncovered_team_ids = sorted(uncovered)
    logger.warning(
        "Player-line reconcile: game %s (perspective %s) holds prior stat rows "
        "for team(s) NO block in this payload covers -- rows per uncovered "
        "team: %s (payload blocks: %s). Those rows cannot be reconciled and may "
        "be permanently STALE; they are deliberately NOT retired, since a "
        "payload carrying no evidence for a side must never authorize deleting "
        "that side's data. Downstream symptom to watch: "
        "_completed_games_with_data counts a game by perspective alone, so a "
        "stale row here can inflate the report's game count N and hold the "
        "'Through {date}' freshness line at a game with no live data.",
        game_id,
        perspective_team_id,
        {team_id: row_counts[team_id] for team_id in result.uncovered_team_ids},
        sorted(covered),
    )


# ---------------------------------------------------------------------------
# ROSTER grain retire helper (E-267-04)
# ---------------------------------------------------------------------------
# Same seam convention as the other two grains: connection-in, NO-COMMIT, caller
# owns the transaction, helper owns the WARN logging.
#
# Scope (TN-10 risk 1): the natural key ``(team_id, season_id)``. ``team_rosters``
# has NO ``perspective_team_id`` -- its PK is ``(team_id, player_id, season_id)``
# and it is populated from a single team-level roster crawl, so there is no
# cross-perspective collision to guard against on this grain. One team-season is
# one roster source is one row set.
#
# Leaf-only (TN-10 risk 6): the ``team_rosters`` row goes, the ``players`` parent
# NEVER does. A roster departure is not a player deletion -- the same human may
# hold stat rows for games already played and may appear on other teams.


@dataclass
class RosterRetireResult:
    """Outcome of one :func:`retire_departed_roster_players` pass.

    The count fields are carried (not just logged) so a caller can surface them
    without re-querying, and so tests can assert the AC-2 WARN payload
    structurally.

    Attributes:
        retired_player_ids: ``player_id`` values whose roster row was deleted.
        refused: True when the drop guard or health gate refused this run.
        refusal_reason: Human-readable explanation when ``refused``, else None.
        roster_db_count: Prior roster rows for this ``(team_id, season_id)``.
        fresh_crawl_count: Distinct player ids in the fresh roster crawl.
        absent_count: Prior players absent from the fresh crawl.
    """

    retired_player_ids: list[str] = field(default_factory=list)
    refused: bool = False
    refusal_reason: str | None = None
    roster_db_count: int = 0
    fresh_crawl_count: int = 0
    absent_count: int = 0


def _prior_roster_player_ids(
    conn: sqlite3.Connection, team_id: int, season_id: str
) -> list[str]:
    """Roster player ids already loaded for this ``(team_id, season_id)``.

    Materialized to a ``list`` -- :func:`classify_absences` takes a
    ``Collection`` and would silently exhaust a raw cursor.
    """
    return [
        row[0]
        for row in conn.execute(
            "SELECT player_id FROM team_rosters "
            "WHERE team_id = ? AND season_id = ?",
            (team_id, season_id),
        )
    ]


def retire_departed_roster_players(
    conn: sqlite3.Connection,
    *,
    team_id: int,
    season_id: str,
    fresh_player_ids: Collection[str],
    previously_rostered_ids: Collection[str],
    exempt_player_ids: Collection[str],
) -> RosterRetireResult:
    """Retire roster rows for players the fresh roster crawl no longer lists.

    Closes H2: without this, a departed player renders on the coach-facing
    roster grid forever, because ``_query_roster`` reads ``team_rosters``
    directly and the upsert paths never remove anything.

    **The drop guard is an ABSOLUTE cap, not a ratio** (TN-12, locked by the
    data-engineer). A roster is small and bounded (12-15) and real churn is about
    one departure per crawl, so :data:`FLOOR_RATIO` is the wrong instrument here:
    a 9-of-14 mid-edit roster clears ``9 >= 7`` and would false-retire five live
    players. :func:`roster_departure_guard` refuses anything above
    :data:`MAX_ROSTER_DEPARTURES` and is passed as ``extra_guard`` -- the
    sanctioned narrowing seam, which can only ever tighten the flat floor, never
    loosen it. This function does NOT define its own cap.

    Accepted benign fallback (TN-12): a preseason tryout cut trimming a 20-player
    pool to 12-15 in one edit legitimately drops more than two, so the cap
    refuses it and stale tryout names linger on the grid until a clean crawl or
    an operator purge. That is accepted deliberately -- the failure mode is grid
    clutter, never a corrupted stat, which is what separates this grain from the
    game and player-line grains. The WARN is the operator's signal.

    Departed-player semantics (AC-5 / TN-13): the roster grid answers "who is on
    this team now", so a departed player there is a false lineup option. Season
    stat lines answer "what happened this season" and MUST survive. The two are
    independent by construction -- ``player_game_*`` rows FK to ``players``, not
    to ``team_rosters`` -- so retiring a roster row cannot break a stat row, and
    the season leaderboards resolve names through ``players`` (verified against
    ``get_season_batting`` / ``get_season_pitching``, which only LEFT JOIN
    ``team_rosters`` for a jersey number).

    Only DELETEs are gated. The ADD path is never capped -- a roster that grows
    is not a signal of anything.

    Does NOT commit -- the caller owns the transaction boundary.

    Args:
        conn: Open connection.
        team_id: Team whose roster is being reconciled.
        season_id: Season scope. With ``team_id`` this is the full natural key.
        fresh_player_ids: Player ids in the fresh roster crawl. EMPTY means the
            payload proved nothing and nothing is retired.
        previously_rostered_ids: Roster player ids as of the START of this load,
            BEFORE the roster upsert and the boxscore jersey backfill ran.
            REQUIRED, and load-bearing in two ways: it scopes the departure CAP
            to genuine departures (a row this run's own backfill re-created is
            not evidence of a truncated crawl), and it picks the retire log
            level. Passing an empty set therefore does NOT mean "no hint" -- it
            means "nothing was rostered before this load", which makes every
            absence read as churn and effectively disables the cap. That is why
            it has no default.

            NOTE this widened during the E-267 closure review. It was originally
            a cosmetic log-level input with an explicit test asserting it could
            never affect a retire; counting backfill churn toward the cap turned
            out to make the cap self-trapping (see the comment at the guard
            below), so the population it defines is now a real health input.
        exempt_player_ids: Ids that are NOT retirement candidates because a
            pending dedup COLLAPSE is about to merge them (see the split-identity
            note below). Removed from the candidate set entirely, so they neither
            get retired nor count toward the departure cap -- they are not
            departures, they are the same human under two ids.

    Returns:
        A :class:`RosterRetireResult`.
    """
    # Split-identity guard. This retire runs BEFORE ``dedup_team_players``, and
    # dedup can only detect a duplicate pair while BOTH ids are co-rostered
    # (``find_duplicate_players`` joins ``team_rosters`` twice). So retiring a
    # roster row that is about to be merged destroys the detection signal, and
    # the human ends up SPLIT: the roster row under the new id, every stat row
    # still under the old one, and no pair left for dedup to find -- verified by
    # reproduction, and it does NOT self-heal, because each later crawl
    # re-backfills the old id and this retire removes it again before dedup runs.
    #
    # Only members of EXECUTABLE collapses are exempt. A refused FORK member must
    # stay retirable: the planner will never merge it, so exempting it would make
    # it permanently unretirable -- trading a split identity for a stale row that
    # nothing can ever remove.
    exempt = set(exempt_player_ids)
    prior_ids = [
        pid
        for pid in _prior_roster_player_ids(conn, team_id, season_id)
        if pid not in exempt
    ]
    fresh = set(fresh_player_ids)
    result = RosterRetireResult(
        roster_db_count=len(prior_ids), fresh_crawl_count=len(fresh)
    )
    if not prior_ids:
        return result

    comparable = set(prior_ids) & fresh
    authoritative = crawl_is_authoritative(
        fetch_ok=bool(fresh),
        fresh_count=len(comparable),
        prior_count=len(prior_ids),
    )
    # The cap counts GENUINE departures only. A row re-created by THIS run's
    # boxscore jersey backfill (absent from the fresh roster, and absent from the
    # pre-load snapshot) is a deterministic artifact of our own load -- not
    # evidence of a truncated crawl, which is the only thing the cap exists to
    # detect. Counting churn made the cap self-trapping: a team that cut THREE
    # players who had already appeared in a completed boxscore hit
    # ``absent_count = 3 > MAX_ROSTER_DEPARTURES`` on every re-scout forever, so
    # the whole-set refusal left them on the grid permanently AND blocked every
    # later genuine departure -- restoring H2, the defect this grain closes.
    previously = set(previously_rostered_ids)

    def _cap_on_genuine_departures(absent_ids: frozenset[Hashable]) -> bool:
        return roster_departure_guard(frozenset(absent_ids & previously))

    classification = classify_absences(
        prior_ids,
        fresh,
        crawl_authoritative=authoritative,
        extra_guard=_cap_on_genuine_departures,
    )

    absent = sorted(
        pid for pid, cls in classification.items() if cls is not AbsenceClass.PRESENT
    )
    result.absent_count = len(absent)
    if not absent:
        return result

    # ``all``, not ``any``: classify_absences assigns ONE class to every absence
    # in a run (the gates are whole-set decisions, never per-id), so a mixed
    # result is not representable. Spelled ``all`` so a future reader is not left
    # wondering whether a partial refusal is possible here -- it is not.
    if all(
        classification[pid] is AbsenceClass.TRANSIENT_ABSENT for pid in absent
    ):
        # Distinguish WHICH gate refused: an operator seeing "5 players vanished"
        # needs to know whether that is a suspected partial crawl (the flat
        # floor) or a legitimate-looking bulk edit above the cap (the tryout-cut
        # case), because the remedies differ.
        if not authoritative:
            reason = (
                "the fresh roster crawl is not authoritative "
                f"(fresh_crawl_count={len(fresh)}, "
                f"fresh_comparable_count={len(comparable)}, "
                f"roster_db_count={len(prior_ids)}, floor_ratio={FLOOR_RATIO})"
            )
        else:
            reason = (
                f"absent_count={len(absent)} exceeds "
                f"MAX_ROSTER_DEPARTURES={MAX_ROSTER_DEPARTURES} -- a drop this "
                "large in a 12-15 player roster is far more likely a truncated "
                "crawl or a bulk edit than real churn"
            )
        result.refused = True
        result.refusal_reason = reason
        logger.warning(
            "Roster retire REFUSED: team_id=%s season_id=%s roster_db_count=%d "
            "fresh_crawl_count=%d absent_count=%d absent_player_ids=%s -- %s; "
            "keeping every roster row.",
            team_id, season_id, len(prior_ids), len(fresh), len(absent),
            absent, reason,
        )
        return result

    for player_id in absent:
        # Leaf row ONLY (risk 6), scoped to the roster natural key (risk 1).
        conn.execute(
            "DELETE FROM team_rosters "
            "WHERE team_id = ? AND season_id = ? AND player_id = ?",
            (team_id, season_id, player_id),
        )
    result.retired_player_ids = absent

    # Log LEVEL only -- every player above is deleted either way.
    #
    # A player cut mid-season who appears in any already-played boxscore is
    # re-added by the jersey backfill on EVERY re-scout and retired again here,
    # forever. Logging that at WARNING each run would emit an identical line in
    # perpetuity and train an operator to ignore the one record TN-4 makes the
    # sole audit trail for a retire. So the NEW departures -- those that were
    # already rostered when this load began -- keep WARNING, while the recurring
    # churn (a row this very run's backfill re-created) drops to INFO. The first
    # crawl after a real cut therefore warns exactly once.
    genuine = [pid for pid in absent if pid in previously]
    churn = [pid for pid in absent if pid not in previously]
    if genuine:
        logger.warning(
            "Roster retire: hard-deleted %d departed roster row(s) -- team_id=%s "
            "season_id=%s roster_db_count=%d fresh_crawl_count=%d "
            "absent_count=%d absent_player_ids=%s. Their season stat lines are "
            "untouched.",
            len(genuine), team_id, season_id, len(prior_ids), len(fresh),
            len(absent), genuine,
        )
    if churn:
        logger.info(
            "Roster retire (recurring): re-removed %d roster row(s) the boxscore "
            "jersey backfill re-created this run -- team_id=%s season_id=%s "
            "player_ids=%s. Expected every crawl for a player cut mid-season who "
            "still appears in an already-played boxscore; not a new departure.",
            len(churn), team_id, season_id, churn,
        )
    return result
