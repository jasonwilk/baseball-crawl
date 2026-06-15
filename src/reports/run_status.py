"""Shared stage-status classifier for report generation (E-236, TN-1).

This module is the ONE place that maps a stage's outcome to an honest status
string. Every pipeline stage calls :func:`classify_stage_status` rather than
hardcoding ``"completed"`` / ``"partial"`` / ``"failed"`` literals or inventing
its own partial logic, so the unattended morning-of-game monitor sees a single
consistent vocabulary.

Status vocabulary (module-level constants -- import these, do not write the
bare strings at call sites)::

    from src.reports.run_status import (
        STATUS_COMPLETED, STATUS_PARTIAL, STATUS_FAILED, classify_stage_status,
    )

The per-stage ``*_status`` columns are free-text TEXT with NO CHECK constraint
(migration 002), so ``"partial"`` -- a NEW status value introduced by E-236 --
needs no migration.
"""

from __future__ import annotations

# Module-level status constants. Call sites import these instead of writing
# bare string literals (E-236 TN-1: no stage hardcodes status literals).
STATUS_COMPLETED = "completed"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"


def classify_stage_status(loaded: int, errors: int, expected: int) -> str:
    """Map a stage's ``(loaded, errors, expected)`` to an honest status string.

    Returns exactly one of :data:`STATUS_COMPLETED`, :data:`STATUS_PARTIAL`,
    or :data:`STATUS_FAILED` per the E-236 TN-1 semantics:

    - ``completed`` = the full expected set loaded AND zero errors.
    - ``partial``   = some loaded but ``errors > 0`` OR ``loaded < expected``.
    - ``failed``    = zero loaded of a non-zero expected set.
    - ``expected == 0`` (nothing attempted) = ``completed`` -- no work, no
      failure.

    GUARDRAIL (TN-1 F3) -- ``expected`` and ``loaded`` are "units ATTEMPTED
    where a shortfall implies failure," NOT raw data coverage. Concretely:
    ``expected`` = items the stage tried to process; ``loaded`` = items that
    did NOT error; ``errors`` = the stage's error count. Pure data-coverage
    numbers (e.g. plays_games_covered, spray_games_with_data) are INFORMATIONAL
    columns and must NEVER be passed as ``loaded`` / ``expected`` here -- doing
    so would mark the MODAL scouting case (a legitimate coverage shortfall with
    zero errors, routine for plays/spray) as ``partial``, the exact false-alarm
    class this classifier exists to avoid. The ``loaded < expected -> partial``
    rule is only honest for stages where a coverage shortfall NECESSARILY
    implies a failure (e.g. the boxscore crawl).

    PRECEDENCE -- a stage carrying its OWN explicit failure signal (e.g. a
    spray ``status == "failed"`` or a plays ``recon.failed`` flag) MUST map
    that to :data:`STATUS_FAILED` BEFORE calling this helper; the
    ``expected == 0 -> completed`` branch must never mask a real failure that
    happened to produce zero units. A "hard error" is the caller's
    responsibility, not an input to this function.

    Args:
        loaded: Count of attempted units that did NOT error.
        errors: The stage's error count.
        expected: Count of units the stage attempted to process.

    Returns:
        One of ``"completed"``, ``"partial"``, ``"failed"``.
    """
    if expected == 0:
        # Nothing attempted -> no work, no failure.
        return STATUS_COMPLETED
    if loaded == 0:
        # Zero loaded of a non-zero expected set -> total failure.
        return STATUS_FAILED
    if errors > 0 or loaded < expected:
        # Some loaded, but errors occurred or the expected set is incomplete.
        return STATUS_PARTIAL
    return STATUS_COMPLETED
