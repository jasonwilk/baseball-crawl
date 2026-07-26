"""Tests for src/db/reconcile_at_load.py (E-267-01).

``classify_absences`` is the shared reconcile-at-load primitive: given the
prior-loaded id set and the fresh crawl's id set for one grain, it classifies
every prior id PRESENT / REMOVED / TRANSIENT_ABSENT. It is PURE -- no DB handle,
no I/O -- so these tests need no database.

Covers:
- AC-1/AC-6a: PRESENT vs REMOVED vs TRANSIENT_ABSENT on seeded id sets.
- AC-2/AC-6b: each of the three bias-to-refuse triggers (fetch failure, empty
  payload, sub-floor shrink) classifies ALL absences TRANSIENT_ABSENT. These
  MUST fail if the primitive would retire any of them.
- AC-2: a stricter per-grain guard (the roster TN-12 departure cap) refuses on a
  shrink the universal floor would wave through; and the guard can only ever
  NARROW -- a permissive guard cannot resurrect a removal the health gate
  refused, and is not even consulted in that case (pins the short-circuit
  ordering, so a posture-inverting refactor fails).
- AC-3/AC-4: REMOVED is reachable only under an authoritative crawl; the
  universal floor is not overridable by callers; the classifier is pure and
  emits no log records.

E-276-01 adds the gate's own arithmetic at this level:

- AC-6: the OPT-IN vacuous-permit rule, BOTH positions pinned -- the permit when
  a caller opts in, and the refusal when it does not. The second is the
  load-bearing half: ``crawl_is_authoritative`` is shared, so an unconditional
  rule would widen a grain that never asked for it.
- AC-8: deletion-neutrality, stated structurally and corroborated by an
  exhaustive walk -- the fix never permits a DELETION today's code refuses,
  given the premise ``W subset-of fresh``. Scoped to deletions, never to
  permits: the two computations genuinely disagree in one region, and every
  disagreement there has an empty candidate set.
- AC-10: connection-in / no-commit, asserted over the module source.
"""

from __future__ import annotations

import logging

import pytest

from src.db.reconcile_at_load import (
    FLOOR_RATIO,
    MAX_ROSTER_DEPARTURES,
    AbsenceClass,
    classify_absences,
    crawl_is_authoritative,
    roster_departure_guard,
)


# ---------------------------------------------------------------------------
# AC-1 / AC-6a: the three classifications
# ---------------------------------------------------------------------------


def test_present_and_removed_under_healthy_crawl():
    """A present id -> PRESENT; a genuinely absent id -> REMOVED."""
    result = classify_absences(
        prior_ids={"g1", "g2", "g3"},
        fresh_ids={"g1", "g2"},
        crawl_authoritative=True,
    )
    assert result == {
        "g1": AbsenceClass.PRESENT,
        "g2": AbsenceClass.PRESENT,
        "g3": AbsenceClass.REMOVED,
    }


def test_absent_under_unhealthy_crawl_is_transient():
    """The same absence, with a non-authoritative crawl -> TRANSIENT_ABSENT."""
    result = classify_absences(
        prior_ids={"g1", "g2", "g3"},
        fresh_ids={"g1", "g2"},
        crawl_authoritative=False,
    )
    assert result["g3"] is AbsenceClass.TRANSIENT_ABSENT
    assert result["g1"] is AbsenceClass.PRESENT


def test_fresh_only_ids_are_not_classified():
    """Ids new in the fresh crawl are ADDs -- not this primitive's concern."""
    result = classify_absences(
        prior_ids={"g1"},
        fresh_ids={"g1", "g2"},
        crawl_authoritative=True,
    )
    assert result == {"g1": AbsenceClass.PRESENT}


def test_tuple_ids_are_supported():
    """Grains key on composite ids, e.g. (game_id, perspective_team_id)."""
    result = classify_absences(
        prior_ids={("game-a", 1), ("game-a", 2)},
        fresh_ids={("game-a", 1)},
        crawl_authoritative=True,
    )
    assert result[("game-a", 2)] is AbsenceClass.REMOVED


# ---------------------------------------------------------------------------
# AC-2 / AC-6b: the three bias-to-refuse triggers
# ---------------------------------------------------------------------------

_PRIOR = {"a", "b", "c", "d"}


@pytest.mark.parametrize(
    ("label", "fetch_ok", "fresh_ids"),
    [
        # (a) the fetch failed outright -- the payload proves nothing.
        ("fetch_failure", False, {"a", "b", "c"}),
        # (b) the fetch "succeeded" but returned an empty payload.
        ("empty_payload", True, set()),
        # (c) the payload shrank below the floor (1 of 4 < 4 * 0.5).
        ("sub_floor_shrink", True, {"a"}),
    ],
)
def test_bias_to_refuse_triggers_never_retire(label, fetch_ok, fresh_ids):
    """Each trigger classifies EVERY absence TRANSIENT_ABSENT, never REMOVED.

    This is the load-bearing guard: a false retire hard-deletes live data, so
    this test must fail if the primitive would retire any absence here.
    """
    authoritative = crawl_is_authoritative(
        fetch_ok=fetch_ok,
        fresh_count=len(fresh_ids),
        prior_count=len(_PRIOR),
    )
    assert authoritative is False, f"{label}: health gate should refuse"

    result = classify_absences(
        prior_ids=_PRIOR,
        fresh_ids=fresh_ids,
        crawl_authoritative=authoritative,
    )
    absent = _PRIOR - fresh_ids
    assert absent, f"{label}: the case must actually contain absences"
    assert AbsenceClass.REMOVED not in result.values(), (
        f"{label}: a transient absence was classified REMOVED -- this would "
        "hard-delete live data"
    )
    for prior_id in absent:
        assert result[prior_id] is AbsenceClass.TRANSIENT_ABSENT


def test_shrink_exactly_at_floor_is_authoritative():
    """The floor is inclusive: fresh_count == prior_count * FLOOR_RATIO passes."""
    assert FLOOR_RATIO == 0.5
    assert crawl_is_authoritative(fetch_ok=True, fresh_count=2, prior_count=4) is True
    assert crawl_is_authoritative(fetch_ok=True, fresh_count=1, prior_count=4) is False


def test_empty_prior_is_permitted_vacuously_when_the_caller_opts_in():
    """E-276-01 AC-6 / TN-1(c): an EMPTY protected population permits.

    Repurposed from ``test_empty_payload_refused_even_with_empty_prior``, which
    asserted ``False`` for these three arguments. The standalone empty-payload
    check exists to protect a NON-empty prior set; with ``prior_count == 0``
    there is nothing pre-existing to protect and the ratio question is vacuous,
    so the gate returns the ``fetch_ok`` value instead of refusing.

    Required by any grain computing the gate over a PRE-UPSERT snapshot: that
    snapshot is legitimately empty on a first-ever load. Without this rule the
    first load refuses, its own rows enter the next run's snapshot, and the
    grain can deadlock permanently (TN-3).

    Its sibling below pins the DEFAULT-OFF half. Both positions of a switch have
    to be pinned for the switch to be covered.
    """
    assert (
        crawl_is_authoritative(
            fetch_ok=True, fresh_count=0, prior_count=0, permit_empty_prior=True
        )
        is True
    )


def test_empty_prior_is_still_refused_without_the_opt_in():
    """The SIBLING half, and the load-bearing one -- do NOT delete as redundant.

    ``crawl_is_authoritative`` is SHARED, so the opt-in must stay opt-in: a
    grain that never asked for the rule must not silently acquire it. This
    assertion is the only executable guard on that -- lose it and the next edit
    that "simplifies" the opt-in away flips the default with every other test
    still green.

    ⚠️ **The stronger-sounding justification is FALSE and is deliberately not
    used here.** Story 01 AC-12 says an unconditional rule "would make an empty
    roster payload read as authoritative there". It would not: ``fetch_ok`` is
    checked FIRST and returns False before the rule is reached, and the roster
    grain's ``fetch_ok`` IS ``bool(fresh)`` -- so an empty payload refuses on
    that conjunct either way (executed, both directions). The rule changes the
    answer on exactly one input: ``fetch_ok`` True with ``prior_count == 0``.

    ⚠️ **This paragraph has now been wrong TWICE about who reaches that input,
    in opposite directions, and the current form is MEASURED.** It first said
    "no grain reaches today" (false -- player-line reaches it on every
    first-ever load); it was then narrowed to "no grain that relies on the
    DEFAULT reaches it -- game and roster both early-return on an empty LIVE
    prior", which E-276-02 and -03 falsified in both halves.

    **As measured after E-276-03**: this function has exactly TWO callers, and
    **BOTH opt in and BOTH reach ``prior_count == 0`` on every first-ever
    load**, because each computes it from a pre-upsert snapshot. The roster
    grain no longer calls it at all -- V1 removed that grain's floor.

    **So no live caller depends on the default**, and making the rule
    unconditional was executed against the full suite: 3 failures, ALL in this
    file, no production behaviour changed. This assertion is therefore a
    CONTRACT pin rather than a guard over a live path -- it protects the next
    caller that derives ``prior_count`` from a LIVE read, where 0 means "nothing
    loaded at all" rather than "nothing loaded yet". That is a weaker claim than
    either previous version, and it is the one that survives execution.

    Recorded rather than silently reworded: a sentence written to correct an
    overstatement, overstating in the opposite direction, in the
    closing-generalization position. Same shape, one round later.

    Same reasoning as ``test_floor_is_not_overridable_by_callers`` -- the
    property this protects is the one a future edit restores by accident.
    """
    assert crawl_is_authoritative(fetch_ok=True, fresh_count=0, prior_count=0) is False


def test_vacuous_permit_returns_the_fetch_ok_value_not_an_unconditional_true():
    """TN-1(c) says "return the fetch-ok value", not "return True".

    A failed fetch still proves nothing, empty prior or not.
    """
    assert (
        crawl_is_authoritative(
            fetch_ok=False, fresh_count=0, prior_count=0, permit_empty_prior=True
        )
        is False
    )


def test_vacuous_permit_does_not_widen_a_NON_empty_prior():
    """Narrowest possible scope: it fires only at ``prior_count == 0``.

    With a real population to protect, an empty overlap is still refused with
    the opt-in set -- otherwise the rule would wave through the exact full-churn
    input this epic exists to refuse.
    """
    assert (
        crawl_is_authoritative(
            fetch_ok=True, fresh_count=0, prior_count=9, permit_empty_prior=True
        )
        is False
    )


def test_healthy_crawl_is_authoritative():
    assert crawl_is_authoritative(fetch_ok=True, fresh_count=3, prior_count=4) is True


def test_floor_is_not_overridable_by_callers():
    """AC-2 makes FLOOR_RATIO the universal MINIMUM -- no looser-floor knob.

    An overridable ``floor_ratio`` would let a grain pass 0.1 and weaken the
    universal minimum through a parameter the module advertises. Strictness
    beyond the floor is expressed through ``classify_absences(extra_guard=...)``,
    whose narrowing-only property is structural rather than documentary.
    """
    with pytest.raises(TypeError, match="floor_ratio"):
        crawl_is_authoritative(
            fetch_ok=True, fresh_count=1, prior_count=13, floor_ratio=0.01
        )


# ---------------------------------------------------------------------------
# AC-2: stricter per-grain guard (roster TN-12 cap)
# ---------------------------------------------------------------------------


def test_roster_cap_refuses_a_shrink_the_flat_floor_allows():
    """13 -> 10 passes the 0.5 floor but exceeds the absolute departure cap."""
    prior = {f"p{i}" for i in range(13)}
    fresh = {f"p{i}" for i in range(10)}
    authoritative = crawl_is_authoritative(
        fetch_ok=True, fresh_count=len(fresh), prior_count=len(prior)
    )
    assert authoritative is True, "the universal floor alone would allow this"

    result = classify_absences(
        prior_ids=prior,
        fresh_ids=fresh,
        crawl_authoritative=authoritative,
        extra_guard=roster_departure_guard,
    )
    assert AbsenceClass.REMOVED not in result.values()
    assert result["p12"] is AbsenceClass.TRANSIENT_ABSENT


def test_roster_departures_at_cap_are_removed():
    """Departures within the cap classify REMOVED under a healthy crawl."""
    assert MAX_ROSTER_DEPARTURES == 2
    prior = {f"p{i}" for i in range(13)}
    fresh = {f"p{i}" for i in range(11)}
    result = classify_absences(
        prior_ids=prior,
        fresh_ids=fresh,
        crawl_authoritative=True,
        extra_guard=roster_departure_guard,
    )
    assert result["p11"] is AbsenceClass.REMOVED
    assert result["p12"] is AbsenceClass.REMOVED
    assert result["p0"] is AbsenceClass.PRESENT


def test_extra_guard_not_consulted_when_nothing_is_absent():
    """No absences -> no guard call, and nothing is classified for retire."""
    calls: list[frozenset] = []

    def guard(absent):
        calls.append(absent)
        return True

    result = classify_absences(
        prior_ids={"p1", "p2"},
        fresh_ids={"p1", "p2", "p3"},
        crawl_authoritative=True,
        extra_guard=guard,
    )
    assert calls == []
    assert set(result.values()) == {AbsenceClass.PRESENT}


def test_permissive_guard_cannot_widen_a_refused_health_gate():
    """A permissive ``extra_guard`` can NEVER resurrect a refused removal.

    The guard is a narrowing-only mechanism. This pins the short-circuit
    ORDERING in ``classify_absences``, not merely the outcome: with the health
    gate False the guard must not even be CALLED, so a refactor to
    ``extra_guard(absent) if extra_guard else crawl_authoritative`` -- which
    inverts the safety posture and would let a partial-payload crawl hard-delete
    live roster rows -- fails here.
    """
    calls: list[frozenset] = []

    def permissive_guard(absent):
        calls.append(absent)
        return True  # would permit every removal if ever consulted

    result = classify_absences(
        prior_ids={"a", "b", "c"},
        fresh_ids={"a"},
        crawl_authoritative=False,
        extra_guard=permissive_guard,
    )

    assert calls == [], "the guard must not be consulted once the health gate refused"
    assert AbsenceClass.REMOVED not in result.values()
    assert result["b"] is AbsenceClass.TRANSIENT_ABSENT
    assert result["c"] is AbsenceClass.TRANSIENT_ABSENT


def test_extra_guard_receives_only_the_absent_ids():
    seen: list[frozenset] = []
    classify_absences(
        prior_ids={"p1", "p2", "p3"},
        fresh_ids={"p1"},
        crawl_authoritative=True,
        extra_guard=lambda absent: seen.append(absent) or True,
    )
    assert seen == [frozenset({"p2", "p3"})]


# ---------------------------------------------------------------------------
# AC-3 / AC-4: retire permitted for REMOVED only; classifier is pure + silent
# ---------------------------------------------------------------------------


def test_removed_appears_only_under_an_authoritative_crawl():
    """The retire-permitting class is reachable ONLY via a healthy crawl.

    A behavioral pin of the real AC-3 invariant (retire == hard delete, allowed
    for REMOVED alone): holding the id sets fixed and flipping ONLY the health
    gate must flip the absent id between REMOVED and TRANSIENT_ABSENT. Replaces
    an earlier tautological assertion over the enum members, which was true by
    construction and would have passed with the module's logic deleted.
    """
    prior, fresh = {"a", "b"}, {"a"}

    healthy = classify_absences(
        prior_ids=prior, fresh_ids=fresh, crawl_authoritative=True
    )
    unhealthy = classify_absences(
        prior_ids=prior, fresh_ids=fresh, crawl_authoritative=False
    )

    assert healthy["b"] is AbsenceClass.REMOVED
    assert unhealthy["b"] is AbsenceClass.TRANSIENT_ABSENT
    assert AbsenceClass.REMOVED not in unhealthy.values()
    # The PRESENT id is unaffected by the health gate either way.
    assert healthy["a"] is unhealthy["a"] is AbsenceClass.PRESENT


def test_classifier_emits_no_log_records(caplog):
    """Logging (WARN per retire / per refusal) belongs to the grain helpers."""
    with caplog.at_level(logging.DEBUG):
        classify_absences(
            prior_ids={"a", "b"},
            fresh_ids=set(),
            crawl_authoritative=False,
        )
        classify_absences(
            prior_ids={"a", "b"},
            fresh_ids={"a"},
            crawl_authoritative=True,
        )
    assert caplog.records == []


def test_inputs_are_not_mutated():
    """The classifier is pure -- caller-owned collections come back untouched."""
    prior = {"a", "b"}
    fresh = {"a"}
    classify_absences(prior_ids=prior, fresh_ids=fresh, crawl_authoritative=True)
    assert prior == {"a", "b"}
    assert fresh == {"a"}


# ---------------------------------------------------------------------------
# E-276-01 AC-6 / AC-8: the corrected gate, and deletion-neutrality
# ---------------------------------------------------------------------------
#
# ``_legacy_permits`` and ``_corrected_permits`` are the two computations over
# the SAME real input: the legacy gate reads the population AFTER this run's
# writes (``P_pre | W``), the corrected gate reads the pre-upsert snapshot
# (``P_pre``). They are not two gates in the shipped code -- there is ONE gate
# per grain and the legacy form is REPLACED, not conjoined. They exist here only
# to state the neutrality relation between the old behaviour and the new.


def _legacy_permits(p_pre: set, writes: set, fresh: set) -> bool:
    """Today's gate: the floor over the post-upsert live population."""
    p_post = p_pre | writes
    return crawl_is_authoritative(
        fetch_ok=True,
        fresh_count=len(p_post & fresh),
        prior_count=len(p_post),
    )


def _corrected_permits(p_pre: set, fresh: set) -> bool:
    """The E-276-01 gate: the floor over the PRE-UPSERT snapshot population."""
    return crawl_is_authoritative(
        fetch_ok=True,
        fresh_count=len(p_pre & fresh),
        prior_count=len(p_pre),
        permit_empty_prior=True,
    )


def test_corrected_gate_refuses_the_full_churn_the_polluted_one_waves_through():
    """The audit's numeric tell, at the primitive.

    9 stored lines, 9 brand-new ids, zero overlap. The polluted population is
    18 with an overlap of 9 -- a comfortable ``9 >= 9`` that PERMITS and
    hard-deletes all nine live lines. The corrected gate reads 0 of 9 on the
    same input and refuses. Every row the run writes is in the prior set AND in
    the fresh set, so it lands on both sides of the ratio and relaxes it by half
    a row.
    """
    stored = {f"old-{i}" for i in range(9)}
    fresh = {f"new-{i}" for i in range(9)}

    assert _legacy_permits(stored, fresh, fresh) is True, (
        "the polluted gate is supposed to permit here -- that is the defect"
    )
    assert _corrected_permits(stored, fresh) is False


@pytest.mark.parametrize(
    ("label", "survivors", "new_ids", "honest_verdict"),
    [
        # prior 10, 5 survive, 6 brand-new: honest floor 5 >= 5 -> PERMIT.
        ("at_the_floor", 5, 6, True),
        # prior 10, 4 survive, 6 brand-new: honest floor 4 >= 5 -> REFUSE.
        ("below_the_floor", 4, 6, False),
    ],
)
def test_overlap_bearing_cases_follow_the_HONEST_verdict(
    label, survivors, new_ids, honest_verdict
):
    """AC-4 at the primitive: the ratio arithmetic, not just a floor.

    The zero-overlap sweep refuses uniformly, which pins a floor but not the
    arithmetic. These two cases differ by ONE survivor and must land on opposite
    sides. The polluted computation permits BOTH (post-upsert prior 16, floor 8,
    numerators 11 and 10), so the pair discriminates.
    """
    stored = {f"old-{i}" for i in range(10)}
    kept = {f"old-{i}" for i in range(survivors)}
    fresh = kept | {f"new-{i}" for i in range(new_ids)}
    writes = fresh

    assert _corrected_permits(stored, fresh) is honest_verdict, label
    assert _legacy_permits(stored, writes, fresh) is True, (
        f"{label}: the polluted computation permits both cases -- that is what "
        "makes this pair discriminating"
    )


def _sets_over(universe: int):
    """Every subset of ``range(universe)``, as frozensets."""
    from itertools import combinations

    items = list(range(universe))
    return [
        frozenset(combo)
        for size in range(universe + 1)
        for combo in combinations(items, size)
    ]


@pytest.mark.parametrize("universe", [3, 4])
def test_deletion_neutrality_holds_structurally_when_writes_come_from_fresh(universe):
    """AC-8: the fix never permits a DELETION today's code refuses.

    Structural, from the single premise ``W subset-of fresh``: every row the run
    adds contributes 1 to the legacy numerator AND 1 to its denominator, and
    ``1 >= 0.5 * 1``. The result is scale-free -- it holds at 2 rows and at 200 --
    so this exhaustive walk is CORROBORATION of the algebra, not its support.

    Scoped to DELETIONS deliberately. See the companion below: the two
    computations genuinely disagree in one region, and a test phrased "permits
    whenever today permits" would fail against a design that is correct.
    """
    violations = []
    for p_pre in _sets_over(universe):
        for fresh in _sets_over(universe):
            for writes in _sets_over(universe):
                if not writes <= fresh:
                    continue  # the premise
                p_post = p_pre | writes
                if not (p_post - fresh):
                    continue  # nothing deletable either way
                if _corrected_permits(p_pre, fresh) and not _legacy_permits(
                    p_pre, writes, fresh
                ):
                    violations.append((set(p_pre), set(fresh), set(writes)))
    assert violations == []


def test_the_premise_is_what_carries_it__violations_appear_once_W_leaves_fresh():
    """The named premise is load-bearing, and this is its counterexample.

    ``W subset-of fresh`` holds on the game and player-line grains (everything
    the run writes into the delete scope comes from the fresh payload) and is
    FALSE on roster, where the jersey backfill writes rows the fresh roster
    crawl never listed. Drop the premise and neutrality fails -- so the test
    above is measuring the premise, not a tautology.
    """
    p_pre, fresh, writes = {0}, {0}, {1, 2}
    assert not writes <= fresh
    assert _corrected_permits(p_pre, fresh) is True
    assert _legacy_permits(p_pre, writes, fresh) is False
    assert (p_pre | writes) - fresh == {1, 2}, "and the divergence is deletable"


@pytest.mark.parametrize("universe", [3, 4])
def test_the_two_computations_disagree_ONLY_where_nothing_can_be_deleted(universe):
    """AC-8's scoping, as an executable claim rather than a caveat.

    At ``P_pre`` empty AND ``W`` empty the corrected gate permits vacuously while
    the legacy one refuses on its standalone ``fresh_count > 0`` check. That is a
    real disagreement in a design that is correct -- and in every such case the
    post-upsert population is empty, so there is nothing to delete on either
    side.
    """
    disagreements = 0
    for p_pre in _sets_over(universe):
        for fresh in _sets_over(universe):
            for writes in _sets_over(universe):
                if not writes <= fresh:
                    continue
                if _corrected_permits(p_pre, fresh) and not _legacy_permits(
                    p_pre, writes, fresh
                ):
                    disagreements += 1
                    assert not (p_pre | writes), (
                        "a disagreement outside the doubly-protected corner"
                    )
    assert disagreements > 0, "the region must be non-empty or this pins nothing"


def test_module_never_commits_or_rolls_back():
    """AC-10: connection-in / no-commit / caller-owns-the-transaction.

    Asserted over the module SOURCE rather than by mocking a connection, because
    the property is "nowhere in this module", not "not on this one path".
    """
    import inspect

    import src.db.reconcile_at_load as module

    source = inspect.getsource(module)
    for banned in (".commit(", ".rollback("):
        assert banned not in source, (
            f"{banned} appeared in reconcile_at_load -- the caller owns the "
            "transaction boundary on every grain"
        )
