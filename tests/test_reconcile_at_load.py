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


def test_empty_payload_refused_even_with_empty_prior():
    """An empty payload is refused independently of the (vacuous) ratio test."""
    assert crawl_is_authoritative(fetch_ok=True, fresh_count=0, prior_count=0) is False


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
