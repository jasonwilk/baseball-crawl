"""Unit tests for the shared stage-status classifier (E-236-01, TN-1).

Exercises :func:`classify_stage_status` across a table of cases including the
TN-1 boundaries:
- full + zero-errors            -> completed
- some-loaded + errors          -> partial
- some-loaded + loaded<expected -> partial
- zero-loaded of non-zero set   -> failed
- expected == 0 (nothing tried) -> completed

The classifier is a pure function with no DB/IO, so these run in isolation.
"""

from __future__ import annotations

import pytest

from src.reports.run_status import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PARTIAL,
    classify_stage_status,
)


# (loaded, errors, expected, expected_status, description)
_CASES = [
    # completed: full expected set loaded, zero errors.
    (5, 0, 5, STATUS_COMPLETED, "full load, zero errors"),
    (1, 0, 1, STATUS_COMPLETED, "single full load"),
    # partial: some loaded but errors > 0 (even at full coverage).
    (5, 2, 5, STATUS_PARTIAL, "full coverage but errors present"),
    (3, 1, 3, STATUS_PARTIAL, "full coverage, one error"),
    # partial: some loaded AND loaded < expected (with errors -- AC-3 boundary).
    (3, 2, 5, STATUS_PARTIAL, "some loaded with errors and shortfall"),
    # partial: some loaded, loaded < expected, zero errors.
    (3, 0, 5, STATUS_PARTIAL, "coverage shortfall, zero errors"),
    # failed: zero loaded of a non-zero expected set.
    (0, 0, 5, STATUS_FAILED, "zero loaded of non-zero expected"),
    (0, 3, 5, STATUS_FAILED, "zero loaded with errors"),
    (0, 0, 1, STATUS_FAILED, "zero loaded of single expected"),
    # expected == 0: nothing attempted -> completed (no work, no failure).
    (0, 0, 0, STATUS_COMPLETED, "nothing attempted"),
    # expected == 0 with stray loaded count still completed (no expected set).
    (0, 0, 0, STATUS_COMPLETED, "nothing attempted, idempotent"),
]


@pytest.mark.parametrize(
    "loaded,errors,expected,want,desc",
    _CASES,
    ids=[c[4] for c in _CASES],
)
def test_classify_stage_status_table(
    loaded: int, errors: int, expected: int, want: str, desc: str
) -> None:
    """classify_stage_status returns the documented status for each case."""
    got = classify_stage_status(loaded, errors, expected)
    assert got == want, f"{desc}: got {got!r}, want {want!r}"


def test_returns_only_the_three_known_values() -> None:
    """The classifier never returns a value outside the three constants."""
    allowed = {STATUS_COMPLETED, STATUS_PARTIAL, STATUS_FAILED}
    for loaded in range(0, 4):
        for errors in range(0, 4):
            for expected in range(0, 4):
                assert (
                    classify_stage_status(loaded, errors, expected) in allowed
                )


def test_status_constants_have_expected_string_values() -> None:
    """Constants carry the exact vocabulary stages/columns expect."""
    assert STATUS_COMPLETED == "completed"
    assert STATUS_PARTIAL == "partial"
    assert STATUS_FAILED == "failed"
