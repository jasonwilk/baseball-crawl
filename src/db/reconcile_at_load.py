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
still vouches for at least one prior-loaded id, and (c) did not shrink
catastrophically (``fresh_count >= prior_count * FLOOR_RATIO``). Any doubt ->
TRANSIENT_ABSENT -> the caller retires nothing.

:func:`crawl_is_authoritative` computes that gate from FOUR inputs -- the three
above plus ``permit_empty_prior``, an OPT-IN rule (E-276-01) under which an
EMPTY protected population conditionally bypasses (b) and returns the
``fetch_ok`` value: nothing pre-existing is being protected, so there is no
absence to refuse. It is off by default because the function is SHARED, and a
grain that never asked for the rule should not silently acquire it. Grains may
additionally pass a STRICTER guard of their own (see below).

Stated precisely, because the obvious stronger phrasing is false: the rule
changes the answer on exactly ONE input -- ``fetch_ok`` True with
``prior_count == 0``. It cannot make an EMPTY payload authoritative anywhere,
on any grain: ``fetch_ok`` is checked first and returns False before the rule is
reached (executed, both directions). So default-off guards against a FUTURE
edit reaching that input, not against today's code.

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
  plus ``gate_outcomes: dict[(table, team_id), GateOutcome]``
* :class:`RosterRetireResult` -- ``refused: bool`` + ``refusal_reason``

A prose reason string says *that* a grain refused, never *which* of the several
independent mechanisms did -- the health gate, the block-populated signal and (on
game and roster) an absolute cap all produce "0 retired". :class:`GateOutcome` is
the structural record that names it, so a test asserts on
``refused_by`` + that mechanism's own counts rather than on WARN prose, and the
WARN is rendered FROM the record rather than the record inferred from the WARN.
It keys exactly as that grain's ``.refusals`` keys -- by ``(table, team_id)`` on
the player-line grain, because that grain evaluates a gate per team block per
table (up to four per call) and a scalar would capture only the last one.
E-276-01 carries it on :class:`PlayerLineRetireResult`; the game and roster
grains gain it with their own gate changes (E-276-02 / -03).

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
owned by the helper rather than the classifier, and the CANDIDATE population --
the live prior read, on every grain, never the snapshot below (E-276-01). The
snapshot computes the gate value ONLY; it is never the classification universe.

The health-gate POPULATION is NOT uniform, and the temporal clause is the
load-bearing half. On a grain whose caller supplies a pre-upsert SNAPSHOT
(game and player-line), the numerator ``snapshot & fresh`` and the denominator
``snapshot`` are drawn from that same population, captured BEFORE any of this
run's writes to that grain's delete scope -- supplied by the caller, because only
the caller knows *when*. **Same-population-on-both-sides is NECESSARY but NOT
SUFFICIENT**: a set read AFTER the fresh upsert satisfies it while measuring
``|fresh| >= |stale|``, which is not a health gate at all -- every row the run
writes lands on both sides of the ratio and relaxes it by half a row. That is
precisely the defect E-276 exists to fix, and it is why the same-population
sentence alone would pass it again.

**E-276 IS COMPLETE ACROSS ALL THREE GRAINS, and they did not converge on one
answer.** Game and player-line take a caller-supplied pre-upsert snapshot;
**the roster grain has NO floor gate at all** -- its refusers are an empty fresh
payload and the :data:`MAX_ROSTER_DEPARTURES` cap, which is therefore its SOLE
guard. That asymmetry is the design, not an unfinished migration: see the
discriminator at :func:`retire_departed_roster_players`. *(This paragraph used
to close by saying game and roster "still measure that degenerate form until
E-276-02 / -03 land" -- naming two stories by number and describing a state both
have since left.)*

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
  apply here. **Under V1 (E-276-03) this grain runs NO floor ratio at all**:
  its only refusers are an empty fresh payload and the absolute
  :data:`MAX_ROSTER_DEPARTURES` cap, which is therefore its SOLE guard -- not a
  cap layered beneath a floor. See the block at that constant.

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

# The dedup name fold, imported for the AC-15 matched-victim diagnostic
# (E-276-01). Importing the private name is deliberate and follows the line
# above: the diagnostic's whole claim is that a victim looks like a pair
# ``bb data dedup-players`` would merge, so it must fold names EXACTLY as
# detection does -- a second local fold would silently diverge on the Unicode
# and diacritic cases ``_fold_name`` exists to handle, and the diagnostic would
# name pairs the instrument it recommends cannot see. Top-level rather than
# function-local: ``player_dedup`` imports nothing from ``src``, so there is no
# cycle to dodge.
from src.db.player_dedup import _fold_name

logger = logging.getLogger(__name__)

# Universal catastrophic-shrink floor (TN-2). A fresh payload holding less than
# half of what is already loaded is treated as a broken crawl, not as a mass
# deletion. This is the UNIVERSAL MINIMUM strictness -- a grain may refuse on a
# SMALLER shrink via ``extra_guard``, but never on a larger one.
FLOOR_RATIO = 0.5

# Roster-grain absolute drop cap (TN-12). The roster retire helper supplies this
# as an ``extra_guard``: more than two GENUINE departures in one run REFUSES the
# whole roster retire for that run. Only DELETEs are capped; the ADD path is
# never gated.
#
# ⛔ READ BOTH SENTENCES BEFORE CHANGING THIS VALUE. They are independent and
# neither implies the other (E-276-03):
#
#   This constant sets the per-invocation RATE of pre-existing roster loss, not
#   a total. Cumulative exposure is unbounded in the number of invocations
#   against a progressively degrading crawl. It is also the SOLE guard on the
#   roster grain -- there is no floor ratio beneath it.
#
# A tuner who reads only the first still does not learn there is nothing
# underneath. E-276-03 REMOVED this grain's floor (operator ruling: on roster,
# prefer delete over refuse), so changing this value is a SAFETY change, not a
# policy tweak.
#
# ⚠️ THE OBVIOUS PHRASING IS THE WRONG ONE. "Raise the cap to 5 and
# per-invocation loss becomes <= 5" is technically correct AND READS AS A BOUND.
# It means 5N, unbounded in N -- and morning-run walks several teams per
# process, so N is not one. Executed, 26-row roster, progressively degrading
# crawl, 5 invocations: cap 2 leaves 16 survivors; cap 5 leaves 1.
#
# ⚠️ AND THE PROTECTION RUNS BACKWARDS WITH RESPECT TO SEVERITY. Executed on a
# 13-row roster: a crawl degrading gently (11,9,7,5,3,1) loses 2 per run, 12 of
# 13 total, with the cap PERMITTING every step; a crawl collapsing to 1 and
# staying there loses NOTHING, because the cap refuses. "Bounded at <= 2" reads
# as a bound on damage and is a bound on SPEED.
#
# That is a genuine TRADE and not a defect: the same 2-per-run shape is exactly
# correct for a real roster losing two players a week, and the cap cannot
# distinguish that from slow degradation -- they are byte-identical at every
# step, and no gate could separate them on the evidence a crawl carries. The
# residual is ACCEPTED, not closed.
#
# ⛔ DO NOT CITE THE CONSTANT-PIN AS EVIDENCE THIS VALUE IS ADEQUATE. A pinning
# test (and the behavioural tests that flip at cap >= 3) makes a change
# DELIBERATE; it says nothing about whether the value is CORRECT, and every one
# of them fails for the reason "the cap moved", which is the tuner's own intent.
# The rate residue above requires NO change to this constant, so the pin has
# nothing to trigger on: "the cap is locked" is a true statement about change
# control and carries ZERO adequacy content. The two facts never touch, which is
# exactly why the pin reads as a mitigation.
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
# tight.
#
# ⚠️ SCOPED TO THIS GRAIN (E-276-03). This comment used to add "and matches the
# :data:`MAX_ROSTER_DEPARTURES` precedent -- a refused retire is loud and
# self-heals on the next clean crawl, a wrong delete is irreversible." **That
# reasoning is correct HERE and was always BACKWARDS for roster**, where a
# refused retire does not self-heal: it strands rows that inflate the next run's
# absent set until the cap refuses permanently (executed in both directions,
# confirmed independently by two agents). It is the sentence that made
# bias-to-refuse feel SAFE on the roster grain, which is why the analogy went
# unchallenged by four reviewers -- and under V1 that grain no longer prefers
# refuse AT ALL, so citing it as a precedent is now wrong twice over. The
# self-heals-vs-irreversible argument stands for the GAME grain, on its own
# merits, with no cross-grain precedent needed.
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


@dataclass(frozen=True)
class GateOutcome:
    """One gate evaluation's structural record (E-276-01, TN-11).

    Several independent mechanisms each produce "0 retired" -- the health gate,
    a grain's payload-completeness signal, and (on game and roster) an absolute
    cap -- so a test asserting "refused" proves nothing about WHICH one fired,
    and a suite built on that goes green whether or not the fix works. This
    record is the discriminator, and the operator-facing refusal WARN is
    rendered FROM it (never the reverse: one source of truth, not two that
    drift).

    **Not scalar on every grain.** The record keys exactly as that grain's
    ``.refusals`` keys, because both derive from the same loop structure: scalar
    on game and roster, keyed by ``(table, team_id)`` on the player-line grain,
    which evaluates up to four independent gates per call (2 team blocks x 2
    stat tables). A uniform shape is the defect, not the goal.

    **Admissibility rule for future fields**: a field belongs here only if it is
    computable from the call that produces it. Anything phrased "grew since",
    "changed from" or "unlike last time" is a test assertion wearing a field's
    clothes -- it needs a previous invocation's record, nothing in production
    retains one, and retaining one would be a snapshot table by another name
    (TN-2 rejects that outright). Route those to a test.

    Attributes:
        gate_evaluated: Whether a floor gate was computed at all. **The
            fail-closed field**: a grain that early-returned, or one that runs
            no floor gate, must be distinguishable from one that computed and
            permitted, and MUST NOT read as a permit. Not represented by nulling
            the other fields -- a nulled field is indistinguishable from an
            unset one.
        gate_permitted: The gate's verdict, or None when ``gate_evaluated`` is
            False.
        gate_prior_count: The DENOMINATOR the gate used -- the pre-upsert
            snapshot population on a grain that captures one. This is the
            numeric tell: pre-fix the player-line WARN read a prior count of 18
            (9 stale + 9 just written) where the true pre-run population was 9.
        gate_comparable_count: The NUMERATOR the gate used --
            ``gate_prior & fresh``.
        refused_by: UNIT-level refusal only -- None, ``"gate"``,
            ``"cap"``, ``"boxscores_incomplete"``, ``"empty_payload"``,
            ``"fetch_not_ok"`` or ``"skipped_no_exemption_plan"``. **The
            membership is PER GRAIN** (player-line can emit ``"gate"``,
            ``"empty_payload"`` and ``"fetch_not_ok"``, and has no cap). It MUST
            NOT absorb the PER-ID refusers, which already live in ``.refusals``
            -- folding them in would lose *which* ids were held back. A test
            asserting "0 retired" checks BOTH.
        permitted: The value the code acted on. Derivable, but carried so a test
            asserts the acted-on value instead of recomputing it.
        matched_victim_player_ids: **The one member on the PERMITTED branch**
            (player-line only, E-276-01 AC-15). On a retire this grain
            PERMITTED, the victim ids that name- or jersey-match a SURVIVING
            fresh id -- i.e. the deletions that look like a re-issued
            ``player_id`` for the same human rather than a genuine departure.
            Computable from this one call, so it satisfies the admissibility
            rule above. Surfacing only: the retire decision is unchanged.
    """

    gate_evaluated: bool = False
    gate_permitted: bool | None = None
    gate_prior_count: int = 0
    gate_comparable_count: int = 0
    refused_by: str | None = None
    permitted: bool = False
    matched_victim_player_ids: tuple[str, ...] = ()


def crawl_is_authoritative(
    *,
    fetch_ok: bool,
    fresh_count: int,
    prior_count: int,
    permit_empty_prior: bool = False,
) -> bool:
    """Health gate on the FRESH payload for one grain (TN-2).

    By DEFAULT the fresh crawl may be trusted to prove an absence only when all
    three conditions below hold. Any failure means the caller must treat every
    absence in that grain as transient:

    1. ``fetch_ok`` -- the fetch itself succeeded (an exception, a non-2xx, or a
       timeout upstream means the caller passes False).
    2. ``fresh_count > 0`` -- the fresh payload vouches for at least one
       prior-loaded id. Checked independently of the ratio, because with
       ``prior_count == 0`` the ratio test is vacuously satisfied -- so on the
       DEFAULT path this check is the only thing protecting that case.
       ⚠️ **``prior_count == 0`` is precisely the input ``permit_empty_prior``
       overrides** (its Args entry is ~40 lines below, in this same docstring).
       These two passages describe ONE input under opposite settings; the
       scoping words "on the DEFAULT path" are the only thing keeping them from
       contradicting each other, so do not drop them as hedging.
    3. ``fresh_count >= prior_count * FLOOR_RATIO`` -- no catastrophic shrink.

    ⚠️ **"All three" is the DEFAULT-PATH contract, not an invariant of this
    function.** ``permit_empty_prior=True`` bypasses condition 2 at
    ``prior_count == 0`` and returns the ``fetch_ok`` value, so
    ``crawl_is_authoritative(fetch_ok=True, fresh_count=0, prior_count=0,
    permit_empty_prior=True)`` is ``True`` with condition 2 NOT holding
    (executed). That is the intended behaviour, and condition 2 is protecting an
    empty population there -- but a reader who takes "all three" as
    unconditional will mis-predict the FIRST-EVER-LOAD case, where the
    player-line grain's pre-upsert snapshot is legitimately empty and the rule
    must permit or the grain deadlocks (TN-3).

    **``fresh_count`` is the OVERLAP, not a payload size** (E-276-01, correcting
    a docstring that was false before this epic touched anything). Every caller
    computes ``comparable = set(prior_ids) & fresh`` immediately above its call
    and passes ``len(comparable)``. Both sides of the ratio are therefore drawn
    from the same population, which is what reduces the gate to the intended
    question -- "did more than half of what we had vanish?" -- rather than
    comparing two unrelated counts. Documenting it as a payload size is how the
    parameter came to be fed one thing and described as another.

    The floor is deliberately NOT a parameter. AC-2 makes
    :data:`FLOOR_RATIO` the UNIVERSAL MINIMUM strictness, and an overridable
    ratio would let a grain pass a LOOSER value (``floor_ratio=0.1``) and
    weaken that minimum through a knob this module advertises. A grain that
    needs to be STRICTER expresses it through :func:`classify_absences`'s
    ``extra_guard``, whose narrowing-only property is structural rather than
    documentary -- one sanctioned strictness mechanism, no asymmetry.

    Args:
        fetch_ok: Whether the fresh fetch for this grain succeeded.
        fresh_count: How many PRIOR-loaded ids the fresh payload still vouches
            for -- ``len(prior_ids & fresh_ids)``, NOT the payload's own size.
        prior_count: Size of the protected (prior-loaded) set for this grain.
        permit_empty_prior: OPT-IN vacuous-permit rule (E-276-01, TN-1(c)).
            When True and ``prior_count == 0``, return the ``fetch_ok`` value
            instead of refusing on condition 2: nothing pre-existing is being
            protected, so the ratio question is vacuous and there is no absence
            to refuse. Required by any grain that computes the gate over a
            PRE-UPSERT snapshot, which is legitimately empty on a first-ever
            load -- without it that load refuses, its rows survive into the next
            run's snapshot, and the grain can deadlock (TN-3).

            **Opt-in, not unconditional.** The rule changes the answer on
            exactly one input: ``fetch_ok`` True with ``prior_count == 0``.
            ``fetch_ok`` is checked FIRST, so an empty payload refuses on that
            conjunct with or without this parameter.

            **Calibration, MEASURED rather than reasoned** (E-276-03; the
            previous version of this paragraph was false and is corrected
            below). This function has exactly **TWO** callers --
            :func:`retire_absent_games` and :func:`retire_absent_player_lines`
            -- and **both pass ``permit_empty_prior=True``, and both legitimately
            reach ``prior_count == 0`` on every first-ever load**, because each
            computes it from a PRE-UPSERT SNAPSHOT that is empty there. Pinned by
            a ``gate_prior_count == 0`` assertion in each grain's test file.

            Making the rule unconditional was EXECUTED against the full suite:
            **3 failures, all in this module's own test file** -- the sibling
            that pins the default-off position, plus two that lose their
            disagreement region. **No production behaviour changed.**

            So the honest statement is narrower than "it would widen something":
            default-off is a CONTRACT choice, not a live guard.

            **WHEN THE SETTING CHANGES AN OUTCOME AT ALL, executed both ways.**
            It turns on whether a caller's GATE population and its CANDIDATE
            population are the same set:

            * **Same set** (the obvious live-fed shape): ``prior_count == 0``
              means the candidate set is empty too, so ``absent = prior - fresh``
              is empty and BOTH settings retire nothing. Measured --
              ``classify_absences([], {"x"}, ...)`` returns ``{}`` under either
              verdict. **The default is not protection here**; it forces the next
              caller to CHOOSE explicitly, which is a smaller and different
              thing.
            * **Different sets**: ``prior_count == 0`` says nothing about how
              many candidates exist, so the verdict decides their fate outright.
              Measured on the shipped shape -- an empty snapshot against 9 live
              candidates and a total id churn -- **off retires 0 of 9, on
              retires 9 of 9.**

            ⚠️ **That second case is not hypothetical: it is the configuration
            this epic introduced, and it is what BOTH current callers are.** Each
            passes ``prior_count=len(gate_prior)`` (a pre-upsert snapshot) while
            classifying over the live prior, and each opts in. So no production
            caller relies on the default today -- which is precisely why the
            default's job is to make the next one state its choice rather than
            inherit ours.

            ⚠️ **THREE earlier versions of this paragraph were wrong, and the
            pattern matters more than any of them.** (i) *"An unconditional rule
            would make an empty roster payload read as authoritative"* --
            ``fetch_ok`` short-circuits first, so it never could; and the roster
            grain no longer calls this function at all. (ii) *"The game and
            roster grains early-return on an empty LIVE prior and so never reach
            this function with ``prior_count == 0``"* -- game reaches it on
            every first-ever load, and roster does not reach the function.
            (iii) *"The default protects the next caller that does"* -- for a
            same-population caller it protects nothing, per the measurement
            above. **Each was a confident rewrite by someone close to the code,
            and each read well.** (i) and (ii) were conclusions that outlived
            their own false premises; (iii) overstated a mechanism in the
            closing-generalization position. The corrective that finally worked
            was not a fourth rewrite -- it was executing the two cases instead of
            arguing them.

    Returns:
        True iff the fresh crawl is complete enough to prove a removal.
    """
    if not fetch_ok:
        return False
    if permit_empty_prior and prior_count == 0:
        # Vacuous: an empty protected population has nothing to lose, so return
        # the fetch-ok value rather than refusing on the standalone empty check
        # (which is there to protect a NON-empty population).
        return fetch_ok
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
            (TN-12). On roster that cap is now the SOLE guard rather than a
            narrowing of a floor -- E-276-03 removed this grain's floor -- so
            ``extra_guard``'s narrowing-only property still holds and there is
            simply nothing left beneath it to narrow.

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
    # hard-delete live rows. Pinned by
    # test_permissive_guard_cannot_widen_a_refused_health_gate.
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
        gate_outcome: The structural record of this pass's gate evaluation
            (E-276-02, TN-11). **Scalar on this grain**, because the gate is a
            single whole-pass decision -- it keys exactly as ``refusals`` keys,
            and ``refusals`` is per-``game_id`` only for the PER-ID protections
            (cross-perspective, not-final), which are a different question.
            ``refused_by`` answers *"did this pass refuse as a unit, and why?"*;
            ``refusals`` answers *"which ids were individually held back?"*. **A
            test asserting "0 retired" must check BOTH** -- neither closes the
            wrong-reason trap alone.
    """

    retired_game_ids: list[str] = field(default_factory=list)
    refusals: dict[str, str] = field(default_factory=dict)
    deleted_counts: dict[str, int] = field(default_factory=dict)
    gate_outcome: GateOutcome = field(default_factory=GateOutcome)


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


def snapshot_prior_loaded_game_ids(
    conn: sqlite3.Connection, *, team_id: int, season_id: str
) -> frozenset[str]:
    """PRE-LOAD snapshot of this grain's protected population (E-276-02).

    The caller owns *when* this runs; this seam owns the SQL. Same division as
    the player-line capture: the parameter's whole value is its TIMING, and only
    the caller knows it.

    **This grain's pollution is NOT an artifact of reading inside an open
    transaction, and no isolation change could fix it.** The payload loader
    commits per game, so by the time the reconcile runs, this run's newly-loaded
    games are COMMITTED. Reading the population later returns
    ``old | newly_completed``, and each newly-completed game raises the numerator
    and the denominator together -- relaxing the floor by half a game. Since
    newly-completed games appear in ordinary operation (that is what re-scouting
    is for), stale absences that correctly refuse on their own start retiring
    once enough new games load beside them. The capture has to MOVE.

    Scope key ``(team_id, season_id)``, identical to the live read
    (:func:`_prior_loaded_game_ids`) so the two measure the same population --
    a snapshot keyed more coarsely inflates both sides of the ratio and makes
    the gate look healthier than it is.

    Args:
        conn: Open connection.
        team_id: The perspective whose crawl this pass reconciles.
        season_id: Season scope. Must be the DERIVED season id, which is why the
            capture cannot be hoisted above the season-id derivation.

    Returns:
        The prior-loaded ``game_id`` set as of the capture instant -- empty on a
        first-ever load, which the vacuous-permit rule handles.
    """
    return frozenset(_prior_loaded_game_ids(conn, team_id, season_id))


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
    prior_snapshot: Collection[str],
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
        prior_snapshot: **REQUIRED, no default** -- the games already loaded for
            this ``(team_id, season_id)`` as of the START of the run, captured by
            the caller via :func:`snapshot_prior_loaded_game_ids` ABOVE the
            boxscore load (E-276-02). The health gate computes over THIS
            population; the CANDIDATE population stays the live read below.

            A default would silently restore the exact defect this parameter
            exists to fix, which is why the evidence-parameter rule in
            ``.claude/rules/python-style.md`` forbids one: the payload loader
            commits per game, so a gate reading the live population counts this
            run's own newly-completed games on BOTH sides of the ratio and
            relaxes the floor by half a game each.

    Returns:
        A :class:`GameRetireResult` naming what was retired and what was refused.
    """
    result = GameRetireResult()

    prior_ids = _prior_loaded_game_ids(conn, team_id, season_id)
    if not prior_ids:
        return result

    fresh = set(fresh_game_ids)
    not_final = set(not_final_game_ids)
    # HEALTH-GATE population != PRESENCE population, and != CANDIDATE population.
    # Presence diffs against the FULL fresh array (AC-5). The floor-ratio
    # backstop counts only the games the fresh array still vouches for, over the
    # population loaded AS OF THE START OF THIS RUN (E-276-02): ``snapshot &
    # fresh`` against ``snapshot``. Both sides are drawn from that same
    # pre-load population, so the gate reduces to the intended invariant --
    # "refuse if MORE THAN HALF of what we had has vanished" -- and nothing this
    # run wrote can inflate either side.
    #
    # Three population mismatches were tried and rejected here. The first two
    # silently raise the deletion cap above 0.5 * prior:
    #   * the whole fresh array -- upcoming games are never in prior, so a
    #     truncated-but-200 response padded with future games sails through
    #     (15 prior vs an 8-entry array passes 8 >= 7.5 and deletes 11);
    #   * the fresh COMPLETED set -- newly-completed games appear in normal
    #     operation (that is what re-scouting is for), lifting a 15-game cap
    #     from 7.5 to 10.5 deletions.
    #   * ⛔ the LIVE prior read, which is what this line used to do. Its
    #     rejected-alternatives note claimed newly-completed games "are not in
    #     prior either" -- FALSE, and the correction is the whole point of
    #     E-276-02. The payload loader COMMITS PER GAME, so by the time this
    #     pass runs a newly-completed game IS in the live prior set and IS in
    #     ``fresh``: it joins the numerator and the denominator together and
    #     relaxes the floor by half a game each. Stale absences that correctly
    #     refuse on their own then start retiring once enough new games load
    #     beside them, bounded only by MAX_GAME_RETIREMENTS. No isolation-level
    #     change could have fixed it -- the rows are committed, not merely
    #     visible-uncommitted -- which is why the capture MOVED to the caller.
    # A prior game that merely reverted to not-final still counts as vouched-for
    # (it is in the array), which is what keeps a single status reversion on a
    # small schedule from reading as a collapsed payload.
    gate_prior = frozenset(prior_snapshot)
    gate_comparable = gate_prior & fresh
    authoritative = crawl_is_authoritative(
        fetch_ok=fetch_ok,
        fresh_count=len(gate_comparable),
        prior_count=len(gate_prior),
        # A first-ever load has an EMPTY snapshot with nothing to protect, while
        # the LIVE prior below is already populated by this run's own writes.
        # Opt-in here, never unconditionally in the shared gate (TN-1(c)).
        permit_empty_prior=True,
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

    # WHICH mechanism refused (TN-4, E-276-02). All of these are WHOLE-SET
    # decisions, so the reason is settled once here rather than per game, and
    # each is named apart: an operator seeing "8 games vanished" needs to know
    # whether that was a suspected partial crawl (the floor), an incomplete
    # boxscore load (the redirect map is unreliable), or a legitimate-looking
    # mass removal above the cap -- the remedies differ.
    #
    # ⚠️ THIS ENUMERATION IS NO LONGER THE WHOLE STORY, and the comment that used
    # to sit here said "the three causes" as though it were. It was ACCURATE when
    # written and was falsified by a change elsewhere, not by an error in it --
    # this epic's own subject, in this function. Two things moved:
    #   * ``refused_by`` on the result now names the mechanism STRUCTURALLY, so
    #     this prose is the rendering and not the record (TN-11: the WARN renders
    #     FROM the record, never the reverse);
    #   * the health gate splits three ways of its own -- ``fetch_not_ok``,
    #     ``empty_payload`` and ``gate`` -- so "not authoritative" is a family,
    #     not a cause, and ``boxscores_incomplete`` is a distinct member rather
    #     than a flavour of the cap.
    # These are UNIT-level only. Per-id protections (cross-perspective,
    # not-final) are recorded in ``result.refusals[game_id]`` and MUST NOT be
    # folded in here -- folding them would lose WHICH ids were held back.
    if not authoritative:
        if not fetch_ok:
            refused_by = "fetch_not_ok"
        elif not fresh:
            refused_by = "empty_payload"
        else:
            # The gate proper: a populated, non-empty array that no longer
            # vouches for half of what was loaded before this run began. A
            # zero OVERLAP lands here rather than on ``empty_payload`` -- the
            # array is not empty, it just shares nothing with the snapshot.
            refused_by = "gate"
    elif not boxscores_complete:
        refused_by = "boxscores_incomplete"
    else:
        refused_by = "cap"

    # The wording of each branch is PRESERVED, not rewritten -- "not
    # authoritative" / "boxscores_complete=False" / "MAX_GAME_RETIREMENTS=" are
    # the tokens that already discriminate these three causes for an operator,
    # and existing tests assert both their presence AND their absence from the
    # other branches. ``refused_by=`` is ADDED alongside, which is what makes the
    # health-gate family (fetch / empty / floor) nameable without collapsing the
    # distinction the surrounding comment describes.
    if not authoritative:
        transient_reason = (
            "absent from the fresh schedule, but the fresh crawl is not "
            f"authoritative (refused_by={refused_by}, fetch_ok={fetch_ok}, "
            f"fresh_comparable_count={len(gate_comparable)}, "
            f"prior_count={len(gate_prior)}, floor_ratio={FLOOR_RATIO}, "
            f"boxscores_complete={boxscores_complete}) -- the two counts are "
            "over the population loaded as of the START of this run, so games "
            "loaded THIS run inflate neither"
        )
    elif refused_by == "boxscores_incomplete":
        transient_reason = (
            "absent from the fresh schedule, but refused_by=boxscores_incomplete "
            "(boxscores_complete=False) -- a completed game in the fresh array "
            "was not loaded this run, so the redirect map is incomplete and a "
            "canonical row can look absent when it is not"
        )
    else:
        transient_reason = (
            f"absent from the fresh schedule, but refused_by=cap: "
            f"retire-eligible absent count {len(retire_eligible_absent)} exceeds "
            f"MAX_GAME_RETIREMENTS={MAX_GAME_RETIREMENTS} (raw absent "
            f"{len(absent)}, of which {len(exempt & absent)} are "
            "cross-perspective protected) -- a mass removal this large is far "
            "more likely a truncated schedule than that many genuine voids"
        )

    # The unit-level decision the code ACTED on. With no absences the guard is
    # never consulted, so the acted-on value is the gate's verdict alone.
    unit_refused = any(
        cls is AbsenceClass.TRANSIENT_ABSENT for cls in classification.values()
    )
    result.gate_outcome = GateOutcome(
        gate_evaluated=True,
        gate_permitted=authoritative,
        gate_prior_count=len(gate_prior),
        gate_comparable_count=len(gate_comparable),
        refused_by=refused_by if unit_refused else None,
        permitted=(not unit_refused) if absent else authoritative,
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
            "REMOVED from an authoritative fresh schedule (%d comparable of %d "
            "loaded as of the START of this run). Rows deleted: %s",
            game_id, team_id, season_id,
            len(gate_comparable), len(gate_prior),
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
        gate_outcomes: ``{(table, team_id): GateOutcome}`` -- the structural
            record of each gate evaluation, keyed identically to ``refusals``
            because this grain gates each ``(block, table)`` pair independently
            (E-276-01, TN-11).

            **An entry is written as the LAST act of the pair's branch**, so a
            key that is ABSENT means that pair never completed a decision --
            a crash cannot leave a record reading as a permit. Read a missing
            key as :class:`GateOutcome`'s fail-closed default
            (``gate_evaluated=False``), never as "no gate needed".
        uncovered_team_ids: ``team_id`` values holding prior rows for this
            game+perspective that NO block in this payload covers, so they could
            not be reconciled at all (see the residual note on
            :func:`retire_absent_player_lines`). Reported, never retired.
    """

    retired: dict[tuple[str, int], list[str]] = field(default_factory=dict)
    refusals: dict[tuple[str, int], str] = field(default_factory=dict)
    gate_outcomes: dict[tuple[str, int], GateOutcome] = field(default_factory=dict)
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


def snapshot_prior_line_player_ids(
    conn: sqlite3.Connection,
    *,
    game_id: str,
    perspective_team_id: int,
    team_ids: Collection[int],
) -> dict[tuple[str, int], frozenset[str]]:
    """PRE-UPSERT snapshot of this grain's protected population (E-276-01).

    The caller owns *when* this runs; this seam owns the SQL. The whole point of
    the parameter is its TIMING, and only the caller knows it -- so this is a
    public helper the loader invokes at its capture anchor (the top of
    ``GameLoader._upsert_game_and_stats``, after the canonical-id rebind and
    before any of this game's stat writes), rather than something
    :func:`retire_absent_player_lines` could do for itself. By the time the
    retire runs, ``old & fresh`` is unrecoverable: a fresh id present in the DB
    is indistinguishable between "was already there" and "we just wrote it".

    **FOUR sets per game, not one.** The scope key is
    ``(table, game_id, perspective_team_id, team_id)`` -- ``table`` is NOT
    optional. :func:`retire_absent_player_lines` gates each ``(block, table)``
    pair independently, so a snapshot keyed without ``table`` would union the
    batting and pitching prior sets and inflate every gate's numerator AND
    denominator with rows from the other table. The ratio would still look
    plausible and the gate would still refuse on a catastrophic shrink -- it
    would just stop measuring the block it is gating, which is this epic's
    original defect in a new key. Nothing crashes and no row-count assertion
    notices. The snapshot must be keyed IDENTICALLY to the live read.

    **Cannot be hoisted to the start of the run.** The set must key on the
    CANONICAL game id, and that id does not exist until mid-loop: the loader
    resolves the duplicate, records the redirect, rebinds the summary's event id
    and only then upserts. A whole-run pre-capture would have to guess ids that
    do not yet exist.

    Args:
        conn: Open connection.
        game_id: The CANONICAL game id (post-redirect).
        perspective_team_id: The perspective whose crawl produced the payload.
        team_ids: Every participant ``team_id`` whose block may appear in this
            payload (typically own + opponent). A key for a block that turns out
            to be absent is simply unused.

    Returns:
        ``{(table, team_id): frozenset(player_id)}`` for both stat tables and
        every requested ``team_id`` -- an empty frozenset where nothing is loaded
        yet, which is the ordinary first-ever-load shape.
    """
    return {
        (table, team_id): frozenset(
            _prior_line_player_ids(
                conn, table, game_id, perspective_team_id, team_id
            )
        )
        for _label, table in _PLAYER_LINE_TABLES
        for team_id in team_ids
    }


#: ``refused_by`` members this grain can emit (TN-11's per-grain membership).
#: There is no cap on the player-line grain and no boxscore-completeness signal,
#: so ``"cap"`` and ``"boxscores_incomplete"`` are unreachable here -- a test
#: asserting either would be asserting a state the code cannot produce.
_PLAYER_LINE_REFUSERS = ("fetch_not_ok", "empty_payload", "gate")


def _player_line_refused_by(*, populated: bool, fresh: set[str]) -> str:
    """Which mechanism refused this ``(block, table)`` pair.

    Mapped to the OPERATOR-MEANINGFUL cause -- what about this payload made it
    unable to prove an absence -- **not** to whichever conjunct of
    :func:`crawl_is_authoritative` happened to short-circuit first. The two come
    apart in exactly the case this epic exists to fix, and the third bullet is
    where: on a full id churn the failing conjunct is ``fresh_count <= 0``, yet
    reporting that as ``"empty_payload"`` would be false to the operator, who has
    a populated, non-empty block in front of them. The remedies differ, which is
    what the field is for.

    * ``populated`` False -> ``"fetch_not_ok"``. This grain's authority signal is
      the per-block populated flag, and False means the block carried no
      per-player ``stats`` rows at all -- the MODAL scored-but-empty opponent
      boxscore.
    * an empty ``fresh`` set -> ``"empty_payload"``. Reachable independently of
      the above: a block whose lineup group has rows but whose pitching group is
      empty is ``populated`` yet contributes no fresh PITCHING ids.
    * otherwise -> ``"gate"``, the floor ratio over the pre-upsert snapshot.
      **A full id churn lands here, not on ``"empty_payload"``**: the payload is
      populated and non-empty, and it is the OVERLAP with the protected
      population that is zero. That distinction is the whole point of the
      corrected gate.
    """
    if not populated:
        return "fetch_not_ok"
    if not fresh:
        return "empty_payload"
    return "gate"


def _player_line_refusal_reason(
    label: str, outcome: GateOutcome, *, populated: bool
) -> str:
    """Render the operator-facing refusal message FROM the gate record.

    The record is the source and the WARN renders from it, never the reverse.

    Naming the mechanism is a PRESERVATION, not a new capability: this path
    already emitted a ``fresh_comparable_count`` / ``prior_count`` /
    ``floor_ratio`` triple. What it could not say is WHICH of the several
    mechanisms that each produce "0 retired" was reporting, nor WHICH population
    it measured -- and on the input this epic exists to fix the polluted gate
    read a comfortable **9 of 18** (measured, not recalled: 9 stale lines plus
    the 9 the run had just written, clearing the floor at exact equality) and
    hard-deleted all nine live lines without emitting a refusal at all. The
    corrected gate reads **0 of 9** on that same input and refuses.
    """
    if outcome.refused_by == "fetch_not_ok":
        return (
            "refused_by=fetch_not_ok: this boxscore block carried no per-player "
            f"stat rows (payload_populated={populated}), so it is not evidence "
            "that anything left -- the scored-but-EMPTY boxscore is the modal "
            "opponent-scouting shape"
        )
    if outcome.refused_by == "empty_payload":
        return (
            f"refused_by=empty_payload: the fresh block listed no {label} player "
            "ids at all, so it vouches for none of the "
            f"{outcome.gate_prior_count} line(s) already loaded"
        )
    return (
        "refused_by=gate: the fresh block vouches for only "
        f"{outcome.gate_comparable_count} of the {outcome.gate_prior_count} "
        f"{label} line(s) already loaded as of the START of this load "
        f"(floor_ratio={FLOOR_RATIO}, payload_populated={populated}). The gate's "
        "population is the PRE-UPSERT snapshot, so this run's own writes are "
        "excluded from both sides of the ratio"
    )


def _dedup_candidate_victims(
    conn: sqlite3.Connection,
    *,
    game_id: str,
    team_id: int,
    victim_ids: Collection[str],
    surviving_fresh_ids: Collection[str],
) -> tuple[str, ...]:
    """Victims that look like a RE-ISSUED id for a surviving player (AC-15).

    A single-invocation diagnostic on the PERMITTED branch, computed from this
    call alone: which of the lines we are about to hard-delete name-match or
    jersey-match a player the fresh block still carries. Those are the deletions
    that look routine and are not -- GameChanger re-issuing a ``player_id`` for
    the same human, which is what ``bb data dedup-players`` exists to merge.

    **Surfacing only.** It changes nothing about what is deleted; the operator
    ruled that every mechanism which would CLOSE this window closes it by
    refusing forever, and a permanent refusal on this grain doubles the
    coach-facing season aggregate. Surface it, do not gate it.

    Matching is DELIBERATELY BROADER than ``find_duplicate_players`` and the
    divergences are stated rather than implied, because this is a diagnostic
    that names that instrument:

    * folded last names equal and one folded first name a prefix of the other,
      with BOTH first names non-empty -- that last clause mirrors detection's
      ``LENGTH(_dedup_fold(...)) > 0`` guard, and the fold is detection's own
      (see the module-level import);
    * OR the same non-empty ``team_rosters.jersey_number`` on this team, in this
      game's season.
      Detection has NO jersey rule at all -- this half exists to catch a
      re-issued id whose displayed name also changed, which prefix matching
      provably cannot see.

    ONE further divergence, narrower-in-detection than here, so this can
    over-name relative to what the instrument will merge:

    * **no co-roster requirement** -- detection joins ``team_rosters`` twice and
      only pairs ids rostered together.

    Season scoping is NOT on that list: the jersey read is season-scoped, derived
    by joining ``games`` on the ``game_id`` this call already takes, so it agrees
    with detection's structural scoping rather than diverging from it. See the
    comment on the ``jerseys`` query for why the season is joined rather than
    threaded.

    It does NOT call ``plan_player_dedup`` -- that would be a self-join per gate
    evaluation, i.e. up to four per game.

    Runs ONLY when a permitted retire actually has victims, which is rare, so the
    two small keyed reads below are off the ordinary re-scout path entirely.
    """
    victims = sorted(set(victim_ids))
    survivors = sorted(set(surviving_fresh_ids) - set(victims))
    if not victims or not survivors:
        return ()

    all_ids = [*victims, *survivors]
    placeholders = ",".join("?" for _ in all_ids)
    names: dict[str, tuple[str, str]] = {
        pid: (_fold_name(first or ""), _fold_name(last or ""))
        for pid, first, last in conn.execute(
            "SELECT player_id, first_name, last_name FROM players "  # noqa: S608
            f"WHERE player_id IN ({placeholders})",
            all_ids,
        )
    }
    # SEASON-SCOPED through the anchor table. ``team_rosters``' PK is
    # ``(team_id, player_id, season_id)``, so a read keyed on team+player alone
    # returns one row PER SEASON and the comprehension below keeps whichever
    # SQLite happened to return last. That made the diagnostic decide on row
    # ORDERING, in both directions: a cross-season jersey reuse could
    # FALSE-POSITIVE (two different humans, same number, different years), and a
    # genuine same-season collision could be SUPPRESSED if the other season's row
    # landed last.
    #
    # This function's own scope key carries no ``season_id`` -- but the season is
    # one join away, because ``games.season_id`` is NOT NULL and the caller holds
    # the ``game_id`` the whole grain is scoped by. Deriving it here rather than
    # threading a separate parameter means the diagnostic's season CANNOT drift
    # from the grain's, and NOT NULL means the join cannot silently drop rows.
    #
    # It also matters that this is the dimension the instrument this WARN
    # RECOMMENDS was hardened on: E-250-01 made season scoping structural in
    # ``find_duplicate_players`` (``season_id`` is a required keyword there), so
    # an unscoped diagnostic would name pairs ``bb data dedup-players`` cannot
    # act on -- the same class as the blank-name false positive, one dimension
    # over.
    jerseys: dict[str, str] = {
        pid: number
        for pid, number in conn.execute(
            "SELECT tr.player_id, tr.jersey_number FROM team_rosters tr "  # noqa: S608
            "JOIN games g ON g.season_id = tr.season_id "
            f"WHERE g.game_id = ? AND tr.team_id = ? AND tr.player_id IN ({placeholders}) "
            "AND tr.jersey_number IS NOT NULL AND tr.jersey_number != ''",
            [game_id, team_id, *all_ids],
        )
    }

    matched: list[str] = []
    for victim in victims:
        v_first, v_last = names.get(victim, ("", ""))
        v_jersey = jerseys.get(victim)
        for survivor in survivors:
            s_first, s_last = names.get(survivor, ("", ""))
            # BOTH folded first names must be NON-EMPTY, mirroring
            # ``find_duplicate_players``' own ``LENGTH(_dedup_fold(...)) > 0``
            # guard on both sides. Without it the prefix test is VACUOUS --
            # ``s_first.startswith("")`` is True for every string -- so a blank
            # first name plus a shared surname matches any teammate. Not
            # hypothetical: ``ScoutingLoader`` writes
            # ``first_name=str(player.get("first_name") or "")``, so GC omitting
            # a first name stores ``''``. Executed: two genuinely different
            # humans, shared surname, different jerseys, blank victim first name
            # -> this returned ``('victim',)`` while
            # ``find_duplicate_players`` returned ``[]``. The WARN would have
            # named a re-issued id and pointed the operator at
            # ``bb data dedup-players``, which cannot act on that pair precisely
            # because detection excludes it by the guard being mirrored here.
            #
            # STATED COST, because this guard is not free: it also drops a
            # GENUINE re-issue whose first name is blank in BOTH generations
            # under one surname. Detection excludes that pair too, so the WARN
            # there would again name an instrument that cannot act -- and the
            # jersey half below still catches the blank-named re-issue that
            # keeps its number.
            name_match = (
                bool(v_last)
                and v_last == s_last
                and bool(v_first)
                and bool(s_first)
                and (v_first.startswith(s_first) or s_first.startswith(v_first))
            )
            # The half that survives a DISPLAYED-NAME change -- the ``Mike`` ->
            # ``Michael`` shape name-prefix matching provably cannot see, which
            # is regime B's own premise. Pinned by
            # test_a_jersey_only_match_is_caught_when_the_name_changed_too.
            jersey_match = v_jersey is not None and v_jersey == jerseys.get(survivor)
            if name_match or jersey_match:
                matched.append(victim)
                break
    return tuple(matched)


def retire_absent_player_lines(
    conn: sqlite3.Connection,
    *,
    game_id: str,
    perspective_team_id: int,
    blocks: Collection[PlayerLineBlock],
    prior_snapshots: dict[tuple[str, int], frozenset[str]],
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

    **Health gate: the population is the caller's PRE-UPSERT SNAPSHOT, and the
    timing is the whole point** (E-276-01). ``snapshot & fresh`` is the numerator
    against ``snapshot`` as the denominator. Same-population-on-both-sides is
    NECESSARY but NOT SUFFICIENT, and reading that population here -- after this
    run's own rows are written -- is how the gate came to satisfy it while
    measuring nothing: every line the run writes is in ``prior`` AND in ``fresh``,
    so it lands on both sides and relaxes the floor by half a row. At a full id
    churn the degenerate form reads a comfortable 9-of-18 -- 9 stale lines plus
    the 9 the run just wrote, clearing the floor at exact equality -- and
    hard-deletes all nine live lines; the corrected gate reads 0-of-9 on the
    same input and refuses. A re-issued ``player_id`` for the same human is exactly what
    ``dedup_team_players`` exists to merge, so an id churn must REFUSE rather
    than delete -- **on the run it arrives**.

    The CANDIDATE population is unchanged: the live prior read, diffed against
    ``fresh``. The snapshot computes the gate value ONLY and is never passed as
    the classification universe -- doing so would silently shrink the candidate
    set to ``snapshot - fresh``, which permits strictly FEWER deletions (so no
    neutrality property notices) while leaving this run's own churn rows
    permanently unretirable.

    **Stated residual, so this docstring does not imply the grain now refuses all
    churn** (TN-8): PARTIAL churn still deletes. Prior 9 with 5 survivors plus 4
    brand-new ids gives ``comparable 5 >= 4.5`` and the 4 churned lines go. And a
    refusal still WRITES -- only the retire is refused -- so a churn the dedup
    sweep cannot merge grows the protected population each run until it reaches
    the floor and the prior generation is deleted, uncapped (this grain has no
    ``MAX_*`` beneath the gate). Both are accepted, surfaced residuals: the
    permitted branch emits a matched-victim WARN naming
    ``bb data dedup-players`` (see :func:`_dedup_candidate_victims`), and closing
    the window needs a different instrument -- not a ratio and not a cap.

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
        prior_snapshots: **REQUIRED, no default** -- the pre-upsert protected
            population, ``{(table, team_id): frozenset(player_id)}``, captured by
            the caller via :func:`snapshot_prior_line_player_ids` BEFORE any of
            this game's stat writes. A default here would silently restore the
            exact defect this parameter exists to fix, which is why the
            evidence-parameter rule in ``.claude/rules/python-style.md`` forbids
            one.

            **A MISSING key raises rather than defaulting to empty**, for the
            same reason. "Nothing loaded yet" is a real state and is carried as
            an EMPTY frozenset present at the key, where the vacuous-permit rule
            handles it correctly; an ABSENT key means the caller keyed its
            capture differently from the live read, and defaulting that to empty
            would route a wiring mistake into the vacuous permit and hard-delete
            every prior line with ``gate_prior_count == 0`` and no refusal WARN
            -- fail-OPEN, silently, with the full pre-fix blast radius. The
            ``gate_prior_count`` on each :class:`GateOutcome` still makes a
            wrongly-POPULATED snapshot visible (it reads a count the caller can
            check); the raise closes the absent-key half structurally.

    Returns:
        A :class:`PlayerLineRetireResult`.
    """
    result = PlayerLineRetireResult()

    for block in blocks:
        for label, table in _PLAYER_LINE_TABLES:
            key = (table, block.team_id)
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

            # GATE population != CANDIDATE population (E-276-01, TN-1(b)).
            # ``prior_ids`` (live, post-upsert) stays the candidate universe --
            # that set is already correct, and this is a gate-population fix, not
            # a delete-targeting one. The FLOOR is computed over the caller's
            # pre-upsert snapshot, keyed identically to the live read so the two
            # measure the same block (a coarser key inflates both sides and makes
            # the gate look healthier than it is).
            if key not in prior_snapshots:
                # FAIL CLOSED on a mis-wired capture. An ABSENT key is not the
                # same fact as an EMPTY one: "nothing was loaded yet" is a real
                # state and is carried as an empty frozenset AT the key, where
                # the vacuous-permit rule handles it correctly. A missing key
                # means the caller keyed its snapshot differently from the live
                # read -- and defaulting it to empty would route that mistake
                # straight into the vacuous permit, deleting every prior line
                # with `gate_prior_count == 0` and no refusal WARN. Raising here
                # costs one swallowed `LoadResult.errors` increment and an
                # ERROR-level traceback; the alternative costs live data.
                raise KeyError(
                    f"player-line prior snapshot is missing {key!r} for game "
                    f"{game_id} (perspective {perspective_team_id}); the "
                    "pre-upsert capture must be keyed identically to the live "
                    f"read. Captured keys: {sorted(prior_snapshots)}"
                )
            gate_prior = prior_snapshots[key]
            gate_comparable = gate_prior & fresh
            authoritative = crawl_is_authoritative(
                fetch_ok=block.populated,
                fresh_count=len(gate_comparable),
                prior_count=len(gate_prior),
                # A first-ever load has an EMPTY snapshot with nothing to
                # protect. Without the vacuous permit it refuses, its own rows
                # enter the next run's snapshot, and the grain can deadlock
                # (TN-3). Opt-in here, NOT unconditionally in the shared gate.
                permit_empty_prior=True,
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
                # A gate WAS evaluated -- record it. This is the ordinary
                # first-ever-load shape (empty snapshot, vacuous permit, every
                # live prior id present in ``fresh``), and it must be
                # distinguishable from a pass that never ran.
                result.gate_outcomes[key] = GateOutcome(
                    gate_evaluated=True,
                    gate_permitted=authoritative,
                    gate_prior_count=len(gate_prior),
                    gate_comparable_count=len(gate_comparable),
                    refused_by=None,
                    permitted=authoritative,
                )
                continue

            if not authoritative:
                outcome = GateOutcome(
                    gate_evaluated=True,
                    gate_permitted=False,
                    gate_prior_count=len(gate_prior),
                    gate_comparable_count=len(gate_comparable),
                    refused_by=_player_line_refused_by(
                        populated=block.populated, fresh=fresh
                    ),
                    permitted=False,
                )
                reason = _player_line_refusal_reason(
                    label, outcome, populated=block.populated
                )
                result.refusals[key] = reason
                logger.warning(
                    "Player-line retire REFUSED for %s on game %s (perspective "
                    "%s, team %s): %d prior line(s) absent (%s) but %s; keeping "
                    "the prior-loaded data.",
                    label, game_id, perspective_team_id, block.team_id,
                    len(absent), ", ".join(absent), reason,
                )
                # LAST: a crash above leaves NO entry for this key, so a missing
                # record can never read as a permit.
                result.gate_outcomes[key] = outcome
                continue

            for player_id in absent:
                # Leaf row ONLY (risk 6), perspective- AND team-scoped (risk 1).
                conn.execute(
                    f"DELETE FROM {table} WHERE game_id = ? AND player_id = ? "  # noqa: S608
                    "AND perspective_team_id = ? AND team_id = ?",
                    (game_id, player_id, perspective_team_id, block.team_id),
                )
            result.retired[key] = absent
            logger.warning(
                "Player-line retire: hard-deleted %d stale %s line(s) on game %s "
                "(perspective %s, team %s) -- absent from a POPULATED fresh "
                "boxscore block (%d comparable of %d prior, as of the START of "
                "this load). Players: %s",
                len(absent), label, game_id, perspective_team_id, block.team_id,
                len(gate_comparable), len(gate_prior), ", ".join(absent),
            )

            # AC-15 diagnostic on the PERMITTED branch. Deliberately NOT folded
            # into the refusal message above: that one explains why nothing
            # happened, this one explains a deletion that looked routine.
            matched = _dedup_candidate_victims(
                conn,
                game_id=game_id,
                team_id=block.team_id,
                victim_ids=absent,
                surviving_fresh_ids=fresh,
            )
            if matched:
                logger.warning(
                    "Player-line retire: %d of the %d hard-deleted %s line(s) on "
                    "game %s (perspective %s, team %s) name- or jersey-match a "
                    "player the fresh block still carries -- %s. That is the "
                    "shape of a RE-ISSUED player_id for the same human, not a "
                    "departure, and the stat rows are already gone. Run "
                    "`bb data dedup-players` to merge the surviving pair before "
                    "the next re-scout.",
                    len(matched), len(absent), label, game_id,
                    perspective_team_id, block.team_id, ", ".join(matched),
                )
            result.gate_outcomes[key] = GateOutcome(
                gate_evaluated=True,
                gate_permitted=True,
                gate_prior_count=len(gate_prior),
                gate_comparable_count=len(gate_comparable),
                refused_by=None,
                permitted=True,
                matched_victim_player_ids=matched,
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
        refused: True when the departure cap or the empty-payload check refused
            this run. (There is no health gate on this grain under V1.)
        refusal_reason: Human-readable explanation when ``refused``, else None.
        roster_db_count: Prior roster rows for this ``(team_id, season_id)``,
            exempt-filtered -- the population the candidate set is drawn from.
            **The epic's own numeric tell**: the original audit identified the
            defect from a ``roster_db_count=4`` on a roster that had only ever
            held three rows. Keep it asserted, and keep it this population.
        fresh_crawl_count: Distinct player ids in the fresh roster crawl.
        absent_count: Prior players absent from the fresh crawl.
        genuine_departure_count: ``absent & previously_rostered_ids`` -- **the
            CAP's own count**, and the number that actually decides the refusal.
            Distinct from ``absent_count``, which also includes churn rows this
            run's own jersey backfill re-created; those are absent but are not
            departures and the cap must not see them.
        gate_outcome: The structural record (E-276-01, TN-11). On this grain
            ``gate_evaluated`` is **always False** -- V1 runs no floor gate, so
            there is no verdict to report, and that must be distinguishable from
            a gate that ran and permitted rather than represented by nulled
            counts. ``refused_by`` is therefore this grain's ONLY structural
            discriminator, which is why two of its five values are synthesized
            by the loader wrapper for paths that return before this helper is
            ever called.
    """

    retired_player_ids: list[str] = field(default_factory=list)
    refused: bool = False
    refusal_reason: str | None = None
    roster_db_count: int = 0
    fresh_crawl_count: int = 0
    absent_count: int = 0
    genuine_departure_count: int = 0
    gate_outcome: GateOutcome = field(default_factory=GateOutcome)


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

    **⛔ THERE IS NO FLOOR RATIO ON THIS GRAIN (E-276-03, V1).** The permit
    condition is exactly ``(fresh payload non-empty) AND (cap permits)``.
    :data:`MAX_ROSTER_DEPARTURES` is the **SOLE guard** -- not a cap layered
    *under* a floor, which is what this docstring used to describe and what the
    other two grains still have. Read the block at that constant before changing
    its value: the bound it gives is a per-invocation RATE, not a total.

    :func:`roster_departure_guard` is still passed as ``extra_guard``, so it
    still can only ever NARROW; there is simply nothing left for it to narrow.
    A roster is small and bounded (12-15) and real churn is about one departure
    per crawl, so :data:`FLOOR_RATIO` was the wrong instrument here even when it
    was present: a 9-of-14 mid-edit roster clears ``9 >= 7`` and would
    false-retire five live players. This function does NOT define its own cap.

    Accepted benign fallback (TN-12): a preseason tryout cut trimming a 20-player
    pool to 12-15 in one edit legitimately drops more than two, so the cap
    refuses it and stale tryout names linger on the grid until a clean crawl or
    an operator purge. That is accepted deliberately.

    **⚠️ "grid clutter, never a corrupted stat" -- SCOPED, not deleted.** That
    sentence used to close the paragraph above and to state what separates this
    grain from the game and player-line grains. It is **true outside the band
    régime and FALSE inside it**: a roster delete can collapse a dedup fork the
    planner had REFUSED into a mergeable pair, and the same run's dedup sweep
    then executes the merge -- destroying a stat row on one branch and silently
    reassigning one on the other, with no row count changing. V1 does not
    introduce that chain (today's code fires it identically in the <= 3-row
    region) but it does EXTEND its reach into a two-value churn band, so a
    reader must not be left believing the sentence holds unconditionally. It is
    also the sentence the operator's prefer-delete ruling rests on. See
    [[IDEA-188]]; the permanent-lock régime is [[IDEA-186]].

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
            absence read as churn so the cap counts ZERO departures and permits
            unconditionally at any roster size. That is why it has no default.

            **⛔ STRENGTHENED at E-276-03: that now disables the ONLY guard on
            this grain, with nothing beneath it.** The sentence above used to
            say "effectively disables the cap", which was accurate when a floor
            still stood underneath and would still refuse a catastrophic shrink.
            V1 removed the floor. Pinned in both directions by
            ``test_an_empty_previously_rostered_ids_leaves_the_grain_unguarded``
            and ``test_catastrophic_roster_shrink_refuses_on_the_cap`` -- the
            same fixture with this one input varied, and opposite outcomes.

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

    # ⛔ NO FLOOR RATIO ON THIS GRAIN (E-276-03, V1). The permit condition is
    # exactly:
    #
    #     permit = (fresh roster payload non-empty) AND (cap permits)
    #
    # and :func:`crawl_is_authoritative` is deliberately NOT called here. The
    # other two grains gained a correctly-populated floor; this one LOSES its
    # floor, on the operator's ruling to invert the bias here -- delete rather
    # than refuse. So this grain ends E-276 with LESS gating than it started
    # with, and :data:`MAX_ROSTER_DEPARTURES` becomes its SOLE guard. That is
    # deliberate and settled: do not "restore" the floor, and do not harmonize
    # this grain with the other two.
    #
    # WHY the floor goes rather than being re-populated, since re-adding it is
    # the obvious "fix": a correctly-populated roster floor PERMANENTLY LOCKS
    # this grain on a reachable input where today's code converges to a clean
    # roster. Executed through the real loader -- DB {a,b,c}, cap 2, fresh
    # {a,n1} then {n1,n2,n3}: today retires b,c then a and converges; a
    # floor-bearing fix refuses both runs, strands three rows, and from run 3
    # the cap sees `absent & previously` = 3 > 2 and REFUSES FOREVER. It is fed
    # by two mechanisms -- the cap counting the stranded rows, AND the floor's
    # own denominator being inflated by rows its own refusals stranded -- so a
    # repair addressing only the cap leaves the second intact.
    #
    # The floor's entire contribution here was also exactly the harmful region:
    # churn-free, a floor can only refuse where the cap permits when the stored
    # roster is <= 3 rows, which is precisely where the lock is produced.
    #
    # ⚠️ This removal does NOT fix the post-upsert prior read on this grain --
    # it REMOVES the gate that carried it. The same demonstration behaves
    # identically before and after, because the cap fires first. What it fixes
    # is the CONCEALMENT: a floor that appeared to protect, could not, and would
    # have locked the grain if repaired.
    authoritative = bool(fresh)
    # The cap counts GENUINE departures only. A row re-created by THIS run's
    # boxscore jersey backfill (absent from the fresh roster, and absent from the
    # pre-load snapshot) is a deterministic artifact of our own load -- not
    # evidence of a truncated crawl, which is the only thing the cap exists to
    # detect. Counting churn made the cap self-trapping: a team that cut THREE
    # players who had already appeared in a completed boxscore hit
    # ``absent_count = 3 > MAX_ROSTER_DEPARTURES`` on every re-scout forever, so
    # the whole-set refusal left them on the grid permanently AND blocked every
    # later genuine departure -- restoring H2, the defect this grain closes.
    #
    # ⛔ AND ``previously`` IS NO LONGER JUST A REFINEMENT OF THE CAP'S
    # POPULATION (E-276-03). With the floor removed, this intersection is the
    # ENTIRE safety decision on the grain: ``previously = set()`` makes it empty,
    # the guard sees zero departures, and it permits unconditionally at any
    # roster size -- with nothing underneath. That is unchanged code; what
    # changed is what used to sit beneath it.
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
    # The CAP's own count -- the population it actually decides on. Distinct from
    # ``absent_count``: churn rows this run's own backfill re-created are absent
    # but are not departures, and the cap must not see them.
    result.genuine_departure_count = len(set(absent) & previously)
    if not absent:
        # Sixth state: nothing was absent, so no mechanism refused anything.
        # ``refused_by`` stays None -- "nothing to decide" must not read as a
        # refusal (AC-3).
        return result

    # ``all``, not ``any``: classify_absences assigns ONE class to every absence
    # in a run (the gates are whole-set decisions, never per-id), so a mixed
    # result is not representable. Spelled ``all`` so a future reader is not left
    # wondering whether a partial refusal is possible here -- it is not.
    if all(
        classification[pid] is AbsenceClass.TRANSIENT_ABSENT for pid in absent
    ):
        # Distinguish WHICH mechanism refused. Under V1 there are only TWO
        # refusers left in this function, and the first one's MEANING changed:
        # it is no longer "suspected partial crawl" (that was the floor) but
        # "the fresh roster crawl was empty". ``fresh_comparable_count`` and
        # ``floor_ratio`` are deliberately GONE from it -- neither decided
        # anything any more, and leaving them would ship a message whose numbers
        # do not explain the decision.
        #
        # This matters more under V1 than it did before, not less: the cap is
        # now the ONLY refuser on the grain, so this string is the only signal
        # separating a healthy bias-to-refuse from the permanent lock in
        # IDEA-186 -- where the whole difficulty is that a recurring cap refusal
        # "looks exactly like the guard working".
        if not authoritative:
            refused_by = "fetch_not_ok"
            reason = (
                "the fresh roster crawl carried no player ids at all "
                f"(refused_by=fetch_not_ok, fresh_crawl_count={len(fresh)}, "
                f"roster_db_count={len(prior_ids)}) -- an empty crawl proves no "
                "departures"
            )
        else:
            refused_by = "cap"
            reason = (
                f"refused_by=cap: genuine_departure_count="
                f"{result.genuine_departure_count} (of absent_count={len(absent)}) "
                f"exceeds MAX_ROSTER_DEPARTURES={MAX_ROSTER_DEPARTURES} -- a drop "
                "this large in a 12-15 player roster is far more likely a "
                "truncated crawl or a bulk edit than real churn. NOTE this cap is "
                "the SOLE guard on this grain: there is no floor ratio beneath it"
            )
        result.refused = True
        result.refusal_reason = reason
        result.gate_outcome = GateOutcome(
            # ALWAYS False on this grain: V1 runs no floor gate at all, so there
            # is no verdict to report. This must not read as a permit, which is
            # why it is a distinct field rather than a nulled count.
            gate_evaluated=False,
            gate_permitted=None,
            refused_by=refused_by,
            permitted=False,
        )
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
