"""Report and team lifecycle: expiry cleanup, stale-reap, and cascade deletion.

Extracted from ``src/reports/generator.py`` (E-256-04, TN-13).  This module is
deliberately **client-free**: it imports no ``GameChangerClient``, no crawler,
no loader, no ``render_report``, no ``reconcile_game``, no ``parse_team_url``,
and no ``CredentialExpiredError``.  The admin delete path
(``reports_admin.py::_delete_report``) therefore no longer drags httpx and
jinja2 into its import graph just to cascade-delete a team.

The dependency direction is one-way: ``generator.py`` imports from here (for
``cleanup_expired_reports``, ``cleanup_orphan_teams``, and the two path
constants).  This module MUST NOT import ``generator`` -- doing so would pull
the whole generation stack back in and defeat the extraction.

``_REPO_ROOT`` / ``_REPORTS_DIR`` are canonical HERE.  ``generator`` imports
them, so ``patch("src.reports.generator._REPORTS_DIR")`` still rebinds the name
generator's own code reads.  Code in *this* module reads this module's globals,
so tests targeting the reaper or the expiry sweep must patch
``src.reports.lifecycle._REPO_ROOT`` / ``._REPORTS_DIR``.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.api.db import get_connection, list_reports_with_runs
from src.api.helpers import get_app_url
from src.util.timezone import UTC_ISO_FORMAT, utcnow_iso

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPORTS_DIR = _REPO_ROOT / "data" / "reports"

STALE_GENERATING_SECONDS = 3600


@contextmanager
def _conn_scope(conn: sqlite3.Connection | None) -> Iterator[sqlite3.Connection]:
    """Yield ``conn`` if the caller supplied one, else open and own a fresh one.

    The injected-connection seam (E-256-04, CR round 1).  ``get_connection`` is a
    module GLOBAL: a function that resolves it does so in *its own* module's
    namespace.  Before the lifecycle extraction, ``cleanup_expired_reports`` lived
    in ``generator`` and picked up the ``generator.get_connection`` that 43
    generation tests patch to a ``tmp_path`` database.  After the move it would
    have resolved ``lifecycle.get_connection`` -- unpatched, hence the REAL
    ``data/app.db``.  Worse, ``generate_report`` swallows every exception from the
    opportunistic sweep by design, so the detachment could not produce a failure.

    Taking the connection as an argument removes the hidden global from the
    cross-module call path: the caller's sandbox travels with the connection.
    Callers that pass ``None`` (the CLI, the app-startup reaper) keep the old
    open-and-close behaviour.

    A BORROWED connection is restored on exit.  The sweeps below set
    ``row_factory = sqlite3.Row`` for their own reads; when they owned the
    connection that died with it, but a borrowed one outlives the call and its
    ``row_factory`` is caller-owned state.  Restoring it here -- rather than at
    each call site -- keeps the borrow non-destructive at the one place that
    knows whether the connection is borrowed at all (E-256-04, CR round 2).

    **"Non-destructive" refers to ``row_factory`` ONLY.  This helper does NOT
    make a borrow transaction-safe, and nothing here prevents a borrowed
    connection from being COMMITTED.**  Every caller below commits on whatever
    connection it is handed -- the reaper unconditionally, even at zero rows
    reaped; :func:`cleanup_expired_reports` unconditionally after its expiry
    loop; :func:`reclaim_orphan_reference_data` at the end of its own
    ``BEGIN IMMEDIATE`` transaction.  That is why each of those entry points
    calls :func:`_require_clean_connection` before doing anything: a borrowed
    connection carrying uncommitted work would have that work committed and then
    deleted as orphan data.  This scope restores one attribute; it is not a
    transaction boundary (E-277-02).
    """
    if conn is not None:
        previous_row_factory = conn.row_factory
        try:
            yield conn
        finally:
            conn.row_factory = previous_row_factory
    else:
        with closing(get_connection()) as owned:
            yield owned


def _require_clean_connection(
    conn: sqlite3.Connection | None, entry_point: str
) -> None:
    """Refuse a BORROWED connection that already has an open transaction.

    Defined ONCE and called from all three public entry points that accept a
    caller's connection (E-277-02 AC-5a).  Three hand-maintained copies of this
    check is the "second path to something that already has one" shape
    ``.claude/rules/canonical-seams.md`` names as this codebase's recurring
    defect -- the copies drift, and the one nobody updated is the one that runs.

    WHY it raises rather than coping: every one of these entry points COMMITS on
    the connection it is given.  Against a caller with uncommitted DML in flight
    that commit is not merely rude -- it makes the caller's rows visible, the
    reclamation then classifies them as orphans and DELETES them, and the
    caller's later ``rollback()`` succeeds while recovering nothing.
    Unrecoverable data loss with no error raised anywhere.

    ``conn is None`` is NOT a violation and does not raise: that is the
    owned-connection path (``bb report cleanup``, the app-startup reaper), where
    the callee opens and closes its own connection and there is no caller
    transaction to destroy.  ``bb report cleanup`` does not wrap its call in a
    try/except, so a guard that fired on ``None`` would crash it outright.

    A RuntimeError rather than an ``assert``: ``assert`` is stripped under
    ``python -O`` / ``PYTHONOPTIMIZE``, and this guards data loss rather than
    catching a development slip.  It matches the module's established
    refuse-loudly shape -- :func:`reclaim_orphan_reference_data`'s fixed-point
    self-assert raises a bare ``RuntimeError`` for the same reason.

    Args:
        conn: The caller's connection, or ``None`` for the owned path.
        entry_point: Name of the calling public function, for the message.

    Raises:
        RuntimeError: If ``conn`` is not ``None`` and has an open transaction.
    """
    if conn is None or not conn.in_transaction:
        return
    raise RuntimeError(
        f"{entry_point}() requires a connection with no open transaction, but the "
        "connection passed has uncommitted work in flight. This entry point COMMITS "
        "on the connection it is given, which would make that work visible and then "
        "delete it as orphan data -- a subsequent rollback would recover nothing. "
        "Commit or roll back before calling, or pass conn=None to let this call own "
        "its own connection."
    )


@dataclass
class CleanupResult:
    """Result of an expired-report file-cleanup sweep (E-238-07).

    ``files_removed`` counts HTML files actually unlinked from disk;
    ``errors`` counts rows whose cleanup raised (per-file error isolation --
    one unremovable file does not abort the sweep).
    """

    files_removed: int = 0
    errors: int = 0


@dataclass
class ReaperResult:
    """Outcome of one stuck-'generating' reaper sweep (E-252-08).

    ``reaped`` counts rows transitioned generating -> failed; ``files_removed``
    counts orphan partial-HTML files unlinked; ``errors`` counts rows whose ROW
    CLEARING raised (per-row error isolation -- one bad row does not abort the
    sweep); ``files_failed`` counts rows whose row-clearing SUCCEEDED but whose
    orphan-file unlink raised.

    ``reaped`` and ``errors`` are DISJOINT, and the split above is what makes
    that true.  Before 2026-08-17 a failed unlink counted the same row in both:
    the 2026-08-16 reorder put ``reaped += 1`` above the unlink while one
    ``except`` still wrapped the whole per-row body.  The distinction is
    load-bearing outside this module -- ``reports_admin`` gates an operator-facing
    "this row will keep refusing submissions" ERROR on ``errors``, and a failed
    unlink on a row already flipped to ``failed`` refuses nothing.
    """

    reaped: int = 0
    files_removed: int = 0
    errors: int = 0
    files_failed: int = 0


def reap_stale_generating_reports(
    conn: sqlite3.Connection | None = None,
) -> ReaperResult:
    """Reap reports stuck at status='generating' past the staleness threshold.

    Selects ``reports`` rows in ``status='generating'`` whose ``generated_at`` (the
    generation START) is older than :data:`STALE_GENERATING_SECONDS`, and
    transitions each to ``status='failed'`` with an operator-readable reaped
    message -- so the admin page stops meta-refreshing on it and it becomes
    deletable through the normal admin flow (the delete affordance is gated on
    ``status != 'generating'``).

    Orphan HTML: a report's HTML is written to ``reports/{slug}.html`` BEFORE the
    'ready' transition that sets ``report_path``, so a death in that narrow window
    leaves an orphan file while ``report_path`` is still NULL -- which
    :func:`cleanup_expired_reports` (keyed on ``report_path IS NOT NULL``) can
    NEVER reap. The reaper therefore unlinks ``reports/{slug}.html`` by slug
    (canonical ``_REPO_ROOT`` resolution + an ``.is_file()`` guard, mirroring
    :func:`cleanup_expired_reports` / ``_delete_report``) AFTER flipping the row.

    That ORDER is load-bearing and is explained in full at the loop below: with
    the unlink first, a failing unlink skipped the UPDATE and left the row
    ``generating`` forever, which since 2026-08-16 wedges
    ``POST /admin/reports/generate`` permanently with no escape through the UI.
    Flipping first inverts that into a stray file.  (This paragraph said
    "before flipping the row" until 2026-08-17 -- it had not moved with the
    code, and stale prose here authorizes the next reader to restore a
    product-fatal order.)  The unlink has its OWN ``try`` and its own
    ``files_failed`` counter, so it cannot inflate ``errors``.

    Idempotent: only ``generating`` rows older than the threshold are selected, so
    a re-run finds none (they are now ``failed``); ``ready``/``failed``/``no_games``
    rows and fresh in-progress ``generating`` rows are never touched.

    Reachable without operator action via :func:`cleanup_expired_reports` (which
    runs opportunistically at ``generate_report`` start and via ``bb report
    cleanup``) and the FastAPI app lifespan startup.

    PRECONDITION -- a borrowed connection must have NO open transaction.  Passing
    a connection with uncommitted DML in flight RAISES ``RuntimeError`` here,
    before anything is committed: this function commits unconditionally on the
    connection it is given (even when it reaps zero rows), which would make the
    caller's uncommitted work visible and expose it to deletion as orphan data.
    Passing ``conn=None`` does NOT raise -- that is the owned path, where this
    call opens and closes its own connection.

    What the raise means in production, in both directions: it stops the
    destructive path, but no operator is paged.  THIS function's call sites are
    exactly four, enumerated from the code rather than from any shared list:

    * :func:`cleanup_expired_reports` -- wrapped; logs at WARNING and continues.
    * :func:`reclaim_orphan_reference_data`, its Step 1 -- **NOT wrapped**, so
      the raise propagates out of the reclaim to *that* function's callers and
      is demoted by whichever of them catches it.  This is the one call site
      where the raise is not absorbed here.
    * ``src/api/main.py``, the app-lifespan startup reaper -- **EXEMPT, not a
      demoting site.**  It calls this function with no argument, so ``conn`` is
      ``None``, the guard SKIPS, and the raise cannot occur there at all.  Same
      exemption as ``bb report cleanup`` on :func:`cleanup_expired_reports`.
    * ``src/api/routes/reports_admin.py::_a_generation_is_in_flight`` -- the
      admin generate route's cross-path gate (2026-08-16).  It passes a BORROWED
      connection, so this guard is LIVE there, and it is the first call site on a
      SERVING request path: it runs on every valid ``POST /admin/reports/generate``
      submission, including refused ones.  The raise is absorbed at that site by a
      broad ``except`` that fails CLOSED (refuses the submission) rather than
      returning a 500.

    Note this list does NOT include ``generate_report`` or the admin
    report-DELETE path: neither calls this function.  (The admin GENERATE path
    does, as of the fourth bullet -- do not read the two admin paths as one.)
    "Refuses loudly" describes a direct caller, not the deployed behaviour.

    Args:
        conn: An open connection to use, with no transaction in progress.  When
            ``None`` (the CLI and app-startup callers) one is opened and closed
            here.  See :func:`_conn_scope`.

    Returns:
        A :class:`ReaperResult` with ``reaped`` / ``files_removed`` / ``errors``
        / ``files_failed``.  ``errors`` means "the ROW could not be cleared" and
        nothing else; a failed unlink lands in ``files_failed``.

    Raises:
        RuntimeError: If ``conn`` is not ``None`` and has an open transaction.
    """
    _require_clean_connection(conn, "reap_stale_generating_reports")
    result = ReaperResult()
    threshold = (
        datetime.now(timezone.utc) - timedelta(seconds=STALE_GENERATING_SECONDS)
    ).strftime(UTC_ISO_FORMAT)
    reaped_message = (
        f"Reaped: generation did not complete within {STALE_GENERATING_SECONDS}s "
        "(the generation process likely died mid-run); marked failed so the report "
        "can be deleted or regenerated."
    )
    with _conn_scope(conn) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, slug FROM reports "
            "WHERE status = 'generating' AND generated_at < ?",
            (threshold,),
        ).fetchall()

        for row in rows:
            report_id = row["id"]
            slug = row["slug"]
            try:
                # ORDER IS LOAD-BEARING: flip the row FIRST, unlink AFTER.
                #
                # These two used to run the other way round, and a failing
                # unlink (read-only mount, permissions, EBUSY) hit the `except`
                # below and `continue`d BEFORE the UPDATE -- leaving the row
                # 'generating' forever. That was a leaked orphan file's worth of
                # damage until the admin generate route began refusing on ANY
                # 'generating' row (2026-08-16): a stuck row now refuses every
                # submission from that page permanently, and the delete
                # affordance is itself gated on `status != 'generating'`
                # (admin/reports.html), so there is no way out through the UI.
                #
                # Flipping first inverts the failure into the strictly milder
                # one this function was already designed to tolerate: the row
                # always clears, and a failed unlink leaves a stray file (the
                # pre-existing orphan condition) instead of wedging the product.
                cursor = conn.execute(
                    "UPDATE reports SET status = 'failed', error_message = ? "
                    "WHERE id = ? AND status = 'generating'",
                    (reaped_message, report_id),
                )
                claimed = cursor.rowcount == 1
            except Exception as exc:  # noqa: BLE001 -- per-row error isolation
                logger.warning(
                    "Failed to reap stale 'generating' report id=%s: %s", report_id, exc
                )
                result.errors += 1
                continue

            # THE UPDATE'S ROWCOUNT IS THE ARBITER, and skipping this check
            # DELETES LIVE REPORTS.  The `AND status = 'generating'` clause makes
            # the write safe, but its rowcount was discarded until 2026-08-17, so
            # a row that left 'generating' between our SELECT and our UPDATE was
            # still counted as reaped AND still had `reports/{slug}.html`
            # unlinked -- and by then that file is the FINISHED report's served
            # HTML, not an orphan partial.  Reproduced: a generation that ran
            # past the threshold and then committed 'ready' ended as
            # `status='ready'`, `report_path='reports/{slug}.html'`, file GONE,
            # with the reaper returning `reaped=1, files_removed=1, errors=0`.
            # The share link then 404s on a report the admin list calls ready.
            #
            # Losing this race is BENIGN and expected (the report finished, which
            # is the good outcome), so it is logged at INFO and counted nowhere:
            # nothing failed, and the `status='generating'` COUNT that gates the
            # admin route will not see this row either.  Same shape as the
            # DELETE-is-the-arbiter rule in `.claude/rules/data-model.md`: gate
            # the privileged action on the guarded write's rowcount, never on the
            # earlier read.
            if not claimed:
                logger.info(
                    "Skipped stale-'generating' report id=%s: it left 'generating' "
                    "before this reap claimed it (a late-finishing generation). "
                    "Its HTML is not ours to remove.", report_id,
                )
                continue
            result.reaped += 1

            # Unlink any orphan partial HTML (written before the 'ready' update
            # that would have set report_path -- so report_path is still NULL and
            # cleanup_expired_reports can never reap it). Canonical resolution
            # via the named _REPORTS_DIR constant + is_file guard, mirroring
            # cleanup_expired_reports / _delete_report.
            #
            # ITS OWN try, and its own counter. The row above is already
            # 'failed', so this failure is a stray file -- not a row that will
            # keep refusing submissions. Folding it into `errors` made the two
            # indistinguishable and put a false "this will keep refusing
            # submissions" ERROR in front of the operator via reports_admin.
            try:
                file_path = _REPORTS_DIR / f"{slug}.html"
                if file_path.is_file():
                    file_path.unlink()
                    logger.info("Removed orphan HTML for reaped report: %s", file_path)
                    result.files_removed += 1
            except Exception as exc:  # noqa: BLE001 -- per-file error isolation
                logger.warning(
                    "Reaped report id=%s but could not remove its orphan HTML: %s "
                    "(the row is cleared; a stray file remains)", report_id, exc
                )
                result.files_failed += 1
        conn.commit()

    if result.reaped:
        logger.info(
            "Reaped %d stale 'generating' report(s) to failed (%d orphan file(s) "
            "removed, %d file(s) left behind)",
            result.reaped, result.files_removed, result.files_failed,
        )
    return result


def cleanup_expired_reports(
    conn: sqlite3.Connection | None = None,
) -> CleanupResult:
    """Remove on-disk HTML files for expired reports (KEEP the reports rows),
    then run the terminal orphan-reference-data reclamation sweep.

    Selects ``reports`` rows whose ``expires_at`` is strictly in the past
    (``expires_at < now``) and that still have a non-NULL ``report_path``,
    unlinks each HTML file, and NULLs ``report_path`` -- but KEEPS the ``reports``
    row so the report still appears as expired in ``bb report list`` /
    ``/admin/reports`` and serving it keeps the existing 404 behavior.

    **DESTRUCTIVE side effect (E-273-02, TN-14).** After the expiry sweep this
    function calls :func:`reclaim_orphan_reference_data`, which HARD-DELETEs
    ``teams`` / ``players`` / ``team_rosters`` rows no longer reachable from any
    surviving report. So while the *expired-report* rows are kept, this call is
    NOT non-destructive overall: it self-heals the ownership invariant by
    reclaiming orphaned reference data. Because it also fires at ``generate_report``
    start and via ``bb report cleanup``, orphan reference data is swept
    opportunistically, not only on delete. The reclamation is best-effort
    (isolated, never fails this sweep) and DEFERS when a live ``generating``
    report is in flight (reap-then-gate guard), so an in-flight generation's data
    is never deleted.

    PRECONDITION -- a borrowed connection must have NO open transaction.  Passing
    a connection with uncommitted DML in flight RAISES ``RuntimeError`` at this
    function's entry, before anything is committed and before the reaper runs.
    This function commits unconditionally on the connection it is given, so
    proceeding would make the caller's uncommitted work visible and then expose
    it to deletion by the reclamation sweep below.  Passing ``conn=None`` does
    NOT raise -- that is the owned path (``bb report cleanup``), where this call
    opens and closes its own connection.

    What the raise means in production, in both directions: it stops the
    destructive path, but no operator is paged.  THIS function's call sites are
    exactly two, enumerated from the code rather than from any shared list:

    * ``generate_report`` (``src/reports/generator.py``) -- passes a dedicated
      fresh connection; wrapped, logs at ERROR and continues generation.
    * ``bb report cleanup`` (``src/cli/report.py``) -- passes ``conn=None``, so
      the guard SKIPS and cannot fire.  That call has **no try/except at all**,
      which is why the ``None`` skip is load-bearing rather than tidy: a guard
      that fired there would crash the command outright.

    Note this list does NOT include the admin report-delete path in
    ``src/api/routes/reports_admin.py``: it does not call this function (it
    calls :func:`reclaim_orphan_reference_data` directly).  "Refuses loudly"
    describes a direct caller, not the deployed behaviour.

    File removal mirrors the ``_delete_report`` admin path: canonical
    ``_REPO_ROOT`` resolution plus an ``.is_file()`` guard. Each row's cleanup
    is wrapped in per-row error isolation so one unremovable file (e.g. a
    permission error) does not abort the whole sweep; a failing row keeps its
    ``report_path`` so a later sweep can retry.

    Reachable both opportunistically at the start of ``generate_report``
    and via the ``bb report cleanup`` CLI command.

    Args:
        conn: An open connection to use, with no transaction in progress.  When
            ``None`` (the ``bb report cleanup`` caller) one is opened and closed
            here.  ``generate_report`` passes a DEDICATED fresh connection it
            opens for this call and closes immediately, so the sweep runs against
            the caller's database rather than re-resolving one from this module's
            globals.  See :func:`_conn_scope`.

    Returns:
        A :class:`CleanupResult` with ``files_removed`` and ``errors`` counts.

    Raises:
        RuntimeError: If ``conn`` is not ``None`` and has an open transaction.
    """
    # E-277-02 AC-2.1: the clean-connection guard sits HERE -- at the function's
    # entry, ahead of the reap call and DELIBERATELY OUTSIDE the try below.
    # Inside that try it would be swallowed by the `except Exception` and
    # execution would continue into this function's OWN unconditional
    # `conn.commit()`, committing the caller's uncommitted DML and exposing it to
    # deletion by the reclamation at the end -- the exact bypass this guards.
    # Measured: with guards on the reap and the reclaim but not here, and even
    # with the reap neutralized to a no-op entirely, that bypass reproduces in
    # full. This function's own commit is sufficient on its own.
    _require_clean_connection(conn, "cleanup_expired_reports")

    # E-252-08: also reap stuck 'generating' reports here, so the reaper rides the
    # SAME no-operator-action trigger as expired-file cleanup (opportunistic at
    # generate_report start + `bb report cleanup`). Isolated so a reaper failure can
    # never block or fail the expired-file sweep (this function's own contract).
    # The caller's connection is forwarded so the reaper shares the same sandbox.
    try:
        reap_stale_generating_reports(conn)
    except Exception:  # noqa: BLE001 -- the reaper is best-effort housekeeping
        logger.warning(
            "Stale-'generating' reaper failed during cleanup; continuing", exc_info=True
        )

    result = CleanupResult()
    now_iso = utcnow_iso()
    with _conn_scope(conn) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, report_path FROM reports "
            "WHERE report_path IS NOT NULL AND expires_at < ?",
            (now_iso,),
        ).fetchall()

        for row in rows:
            report_id = row["id"]
            report_path = row["report_path"]
            try:
                # Canonical resolution + is_file() guard (the _delete_report model).
                file_path = _REPO_ROOT / "data" / report_path
                if file_path.is_file():
                    file_path.unlink()
                    logger.info("Removed expired report file: %s", file_path)
                    result.files_removed += 1
                # NULL report_path but KEEP the row (so the list still shows the
                # report as expired). Done whether or not the file was present,
                # because either way the on-disk artifact is now gone.
                conn.execute(
                    "UPDATE reports SET report_path = NULL WHERE id = ?",
                    (report_id,),
                )
            except Exception as exc:  # noqa: BLE001 -- per-file error isolation
                logger.warning(
                    "Failed to clean up expired report file for report_id=%s: %s",
                    report_id, exc,
                )
                result.errors += 1
                continue
        conn.commit()

        # E-273-02 / TN-4: terminal ownership-invariant self-heal. Run the
        # reachability reclamation pass so any teams/players/rosters orphaned by
        # a prior deletion (or that never entered a cascade's scope -- RC#2)
        # become unreachable and are swept. This is the opportunistic trigger
        # that ALSO fires at the start of every generate_report (generator.py):
        # that invocation is safe by construction (the run's scouted team is not
        # committed yet -- _ensure_team_row is a later run() step -- and the
        # reap-then-gate covers concurrent generations). The call-site reap above
        # and the pass's OWN internal reap are both intentional and idempotent
        # (SE MINOR-2): leave both. The pass owns its BEGIN IMMEDIATE..COMMIT
        # transaction and the reap-then-gate guard, so a live generation's data
        # is never deleted (it defers). Best-effort isolation so a sweep failure
        # never breaks the expired-file cleanup's own contract.
        try:
            reclaim_orphan_reference_data(conn)
        except Exception:  # noqa: BLE001 -- reclamation is best-effort housekeeping
            logger.warning(
                "Orphan reclamation failed during cleanup_expired_reports; continuing",
                exc_info=True,
            )

    return result


def _delete_game_scoped_data_for_perspectives(
    conn: sqlite3.Connection,
    game_ids: list[str],
    perspective_team_ids: list[int],
) -> None:
    """Delete game-scoped rows owned by the given perspectives only.

    E-220 round 6 cluster 2: scoped replacement for the prior
    ``_delete_game_scoped_data()``.  Preserves rows belonging to OTHER
    perspectives of the same games.  The ``games`` row itself is only
    deleted when no other perspective remains in ``game_perspectives``;
    otherwise the games row is preserved so the other perspective's data
    still has a valid FK target.

    FK-safe order: play_events -> plays -> reconciliation_discrepancies ->
    player_game_batting -> player_game_pitching -> spray_charts ->
    game_perspectives -> games.

    Args:
        conn: Open SQLite connection.
        game_ids: The games whose dependent rows should be considered.
        perspective_team_ids: Delete only rows tagged with these
            perspectives.  Rows belonging to other perspectives are
            preserved.

    Note: ``reconciliation_discrepancies`` uses ``perspective_team_id``
    directly for perspective-scoped deletion (E-220 round 7 P1-2).
    """
    if not game_ids or not perspective_team_ids:
        return
    gp = ",".join("?" for _ in game_ids)
    pp = ",".join("?" for _ in perspective_team_ids)
    params = list(game_ids) + list(perspective_team_ids)

    # play_events inherits perspective via parent plays (FK to plays.id)
    conn.execute(
        f"DELETE FROM play_events WHERE play_id IN ("
        f"  SELECT id FROM plays "
        f"  WHERE game_id IN ({gp}) AND perspective_team_id IN ({pp})"
        f")",
        params,
    )
    conn.execute(
        f"DELETE FROM plays "
        f"WHERE game_id IN ({gp}) AND perspective_team_id IN ({pp})",
        params,
    )
    # reconciliation_discrepancies: scope by perspective_team_id so
    # cross-perspective game-level rows for the opposite participant are
    # not incorrectly preserved (E-220 round 7 P1-2 bonus bugfix).
    conn.execute(
        f"DELETE FROM reconciliation_discrepancies "
        f"WHERE game_id IN ({gp}) AND perspective_team_id IN ({pp})",
        params,
    )
    conn.execute(
        f"DELETE FROM player_game_batting "
        f"WHERE game_id IN ({gp}) AND perspective_team_id IN ({pp})",
        params,
    )
    conn.execute(
        f"DELETE FROM player_game_pitching "
        f"WHERE game_id IN ({gp}) AND perspective_team_id IN ({pp})",
        params,
    )
    conn.execute(
        f"DELETE FROM spray_charts "
        f"WHERE game_id IN ({gp}) AND perspective_team_id IN ({pp})",
        params,
    )
    conn.execute(
        f"DELETE FROM game_perspectives "
        f"WHERE game_id IN ({gp}) AND perspective_team_id IN ({pp})",
        params,
    )
    # Only delete the games row if no other perspective remains for that game.
    conn.execute(
        f"DELETE FROM games "
        f"WHERE game_id IN ({gp}) "
        f"  AND NOT EXISTS ("
        f"    SELECT 1 FROM game_perspectives gp2 "
        f"    WHERE gp2.game_id = games.game_id"
        f"  )",
        list(game_ids),
    )


def _live_report_perspective_ids(
    conn: sqlite3.Connection, exclude_team_id: int
) -> set[int]:
    """Return team_ids that still hold a ``reports`` row (F-H1 guard).

    These are the perspectives whose game-level data must be preserved when a
    DIFFERENT team is being deleted: a live report is regenerated from the DB,
    and whole-game plays idempotency (``.claude/rules/data-model.md``) means any
    destroyed shared-game plays are never re-fetched -- the hole is permanent
    and silent.  ``exclude_team_id`` (the team being deleted) is dropped so the
    guard never protects the deletion target against itself.

    A row's mere existence counts as "live": ``bb report cleanup`` unlinks an
    expired report's HTML but KEEPS the ``reports`` row (nulls ``report_path``),
    and the row still underpins regeneration.  So any ``reports`` row is treated
    as a data dependency, expired or not.
    """
    rows = conn.execute("SELECT DISTINCT team_id FROM reports").fetchall()
    return {r[0] for r in rows if r[0] != exclude_team_id}


def _delete_team_anchor_and_orphan_data(
    conn: sqlite3.Connection, team_id: int
) -> None:
    """Delete game-level stat rows anchored to or perspectived by the given team.

    Two passes, both unbounded by the participant-games set:

      1. Perspective pass: rows where ``perspective_team_id = team_id`` in any
         game.  Mirrors the Phase 1b cleanup from the pre-refactor admin cascade
         (``src/api/routes/admin.py``).  Necessary because
         ``_delete_game_scoped_data_for_perspectives`` scopes its DELETEs to a
         participant-games set, so cross-perspective scouting rows the team
         produced about games it did not play in are missed.

      2. Anchor pass: rows where ``team_id = team_id`` (and ``batting_team_id``
         for ``plays``) in any game, regardless of which perspective owns them.
         Necessary because ``team_id INTEGER NOT NULL REFERENCES teams(id)``
         has no ``ON DELETE`` clause anywhere in the schema.  SQLite's default
         is NO ACTION (RESTRICT on immediate), so deleting a team without first
         removing its anchor rows raises ``IntegrityError`` at the
         ``DELETE FROM teams`` step.

    F-H1 shared-game guard (E-253-01): the anchor pass is EXCLUDED from rows
    owned by a perspective that still holds a live ``reports`` row.  When teams
    X and Y played a shared game and Y holds a report, Y's pitcher FPS%/P-BF are
    computed from the ``plays`` where X was batting (``batting_team_id = X``)
    under Y's perspective (``perspective_team_id = Y``).  Deleting X must NOT
    destroy those rows.  Because the spared rows still FK-reference X (and the
    shared ``games`` row does too), the caller's teams-row survivor check keeps
    X's ``teams`` row -- so sparing here does not cause an ``IntegrityError`` at
    ``DELETE FROM teams`` (the FK-safety survivor path per TN-1).

    Pass order (perspective first, anchor second) matches the historical
    admin.py Phase 1b / Phase 3 ordering and keeps the two WHERE-clause
    families grepable.  Correctness does not depend on the order -- both
    passes are idempotent DELETEs on overlapping tables with different
    filters.  Within the anchor pass, ``play_events`` MUST be deleted before
    its parent ``plays`` rows to respect the ``play_events.play_id -> plays.id``
    FK.
    """
    # --- Pass 1: perspective_team_id = T (any game) --------------------------
    conn.execute(
        "DELETE FROM play_events WHERE play_id IN ("
        "  SELECT id FROM plays WHERE perspective_team_id = ?"
        ")",
        (team_id,),
    )
    conn.execute(
        "DELETE FROM plays WHERE perspective_team_id = ?", (team_id,)
    )
    conn.execute(
        "DELETE FROM player_game_batting WHERE perspective_team_id = ?",
        (team_id,),
    )
    conn.execute(
        "DELETE FROM player_game_pitching WHERE perspective_team_id = ?",
        (team_id,),
    )
    conn.execute(
        "DELETE FROM spray_charts WHERE perspective_team_id = ?",
        (team_id,),
    )
    conn.execute(
        "DELETE FROM reconciliation_discrepancies WHERE perspective_team_id = ?",
        (team_id,),
    )
    conn.execute(
        "DELETE FROM game_perspectives WHERE perspective_team_id = ?",
        (team_id,),
    )

    # --- Pass 2: team_id / batting_team_id = T (any game, any perspective) ---
    # plays.batting_team_id and plays.perspective_team_id are independent FKs;
    # the perspective pass already handled perspective_team_id = T, so we
    # target batting_team_id = T here.  play_events must precede plays.
    #
    # F-H1 guard: SPARE rows whose perspective still holds a live report.  The
    # same NOT-IN filter is applied to the ``play_events`` subquery so a spared
    # play keeps its child events.  When ``protected`` is empty the clause is
    # omitted (SQLite has no empty-tuple ``IN``), preserving the pre-guard
    # behaviour for true orphans.
    protected = _live_report_perspective_ids(conn, team_id)
    if protected:
        pp = ",".join("?" for _ in protected)
        excl = f" AND perspective_team_id NOT IN ({pp})"
        excl_params: tuple[int, ...] = tuple(protected)
    else:
        excl = ""
        excl_params = ()

    conn.execute(
        "DELETE FROM play_events WHERE play_id IN ("
        "  SELECT id FROM plays WHERE batting_team_id = ?" + excl +
        ")",
        (team_id, *excl_params),
    )
    conn.execute(
        "DELETE FROM plays WHERE batting_team_id = ?" + excl,
        (team_id, *excl_params),
    )
    conn.execute(
        "DELETE FROM player_game_batting WHERE team_id = ?" + excl,
        (team_id, *excl_params),
    )
    conn.execute(
        "DELETE FROM player_game_pitching WHERE team_id = ?" + excl,
        (team_id, *excl_params),
    )
    conn.execute(
        "DELETE FROM spray_charts WHERE team_id = ?" + excl,
        (team_id, *excl_params),
    )
    conn.execute(
        "DELETE FROM reconciliation_discrepancies WHERE team_id = ?" + excl,
        (team_id, *excl_params),
    )


def _delete_team_scoped_data(
    conn: sqlite3.Connection, team_ids: list[int], *, delete_team_rows: bool = True
) -> None:
    """Delete team-scoped dependent rows for the given team IDs.

    FK-safe order per TN-6 Phase 2.  Optionally deletes the team rows
    themselves (set ``delete_team_rows=False`` to skip when game FKs
    still reference the team).
    """
    if not team_ids:
        return
    placeholders = ",".join("?" for _ in team_ids)
    conn.execute(f"DELETE FROM team_rosters WHERE team_id IN ({placeholders})", team_ids)
    # player_season_batting / player_season_pitching are gone (E-259-03 dropped
    # the stored season-aggregate tables; the season line is derived at query
    # time), so there are no team-scoped season rows to cascade-delete here.
    conn.execute(f"DELETE FROM scouting_runs WHERE team_id IN ({placeholders})", team_ids)
    conn.execute(f"DELETE FROM crawl_jobs WHERE team_id IN ({placeholders})", team_ids)
    conn.execute(f"DELETE FROM coaching_assignments WHERE team_id IN ({placeholders})", team_ids)
    conn.execute(f"DELETE FROM user_team_access WHERE team_id IN ({placeholders})", team_ids)
    # E-240-03: scheduled_report_runs slots belong to the team whose schedule
    # produced them; remove them when the team is deleted (Cleanup-Detection
    # Mirror Invariant). Distinct from report deletion, which only NULLs
    # report_id (ON DELETE SET NULL) -- the audit row outlives the report.
    conn.execute(
        f"DELETE FROM scheduled_report_runs WHERE own_team_id IN ({placeholders})",
        team_ids,
    )
    conn.execute(
        f"DELETE FROM opponent_links WHERE our_team_id IN ({placeholders})",
        team_ids,
    )
    conn.execute(
        f"UPDATE opponent_links SET resolved_team_id = NULL, resolution_method = NULL, "
        f"resolved_at = NULL WHERE resolved_team_id IN ({placeholders})",
        team_ids,
    )
    if delete_team_rows:
        conn.execute(f"DELETE FROM teams WHERE id IN ({placeholders})", team_ids)


def cascade_delete_team(conn: sqlite3.Connection, team_id: int) -> None:
    """Cascade-delete a single team and its dependent data.

    Used by the report-deletion path where the team is confirmed eligible
    for cleanup (all guard conditions passed).  Deletes only rows owned
    by this team's perspective; cross-perspective rows belonging to other
    teams are preserved, as are games rows when another perspective
    remains.  The team-scoped tables (rosters, season aggregates,
    scouting_runs, etc.) are deleted unconditionally since they are keyed
    on team_id alone.

    FK-safe team-row deletion (round 7 P1-1): after data cleanup, the
    ``teams`` row itself is only deleted when no ``games`` row still
    FK-references the team.  A survivor occurs when another stub
    perspective loaded the same game and its ``game_perspectives`` row
    kept the ``games`` row alive.  In that case, the team-scoped data
    is still cleaned, but the ``teams`` row is retained to preserve the
    cross-perspective ``games`` FK target.  This mirrors the pattern
    ``cleanup_orphan_teams`` uses.
    """
    game_rows = conn.execute(
        "SELECT game_id FROM games WHERE home_team_id = ? OR away_team_id = ?",
        (team_id, team_id),
    ).fetchall()
    # Unbounded cleanup MUST run before _delete_game_scoped_data_for_perspectives,
    # because the latter attempts to delete the games row inside its last DELETE
    # and will FK-violate if anchor rows (team_id = T, any perspective) still
    # reference the game.  The anchor pass clears those; the perspective-scoped
    # helper then cleans remaining perspective-scoped rows and deletes the game
    # row under the NOT EXISTS guard.
    _delete_team_anchor_and_orphan_data(conn, team_id)
    _delete_game_scoped_data_for_perspectives(
        conn, [r[0] for r in game_rows], [team_id],
    )
    _delete_team_scoped_data(conn, [team_id], delete_team_rows=False)

    # Only delete the teams row if no games row still FK-references it.
    game_still_references_team = conn.execute(
        "SELECT 1 FROM games WHERE home_team_id = ? OR away_team_id = ? LIMIT 1",
        (team_id, team_id),
    ).fetchone() is not None

    if game_still_references_team:
        conn.commit()
        logger.info(
            "Cascade-deleted data for team_id=%d; teams row retained "
            "(cross-perspective games still reference it).",
            team_id,
        )
        return

    conn.execute("DELETE FROM teams WHERE id = ?", (team_id,))
    conn.commit()
    logger.info("Cascade-deleted team_id=%d and all dependent data.", team_id)


def cleanup_orphan_teams(
    conn: sqlite3.Connection, orphan_ids: set[int]
) -> int:
    """Delete orphan teams and their dependent rows in FK-safe order.

    Used during report generation to clean up auto-created opponent stubs.
    Only deletes games where BOTH participants are orphans — shared games
    between an orphan and a non-orphan (e.g., the report team) are
    preserved.  An orphan team is RETAINED (team-scoped data is still cleaned)
    when anything still FK-references it after Phase 1 — a surviving ``games``
    row, OR a row in one of the six game-child tables.

    That second half was missing until 2026-08-17 and is why this docstring no
    longer says "game FK references".  Deletability is decided by the SAME test
    :func:`reclaim_orphan_reference_data` uses, composed from
    :data:`_TEAM_STAT_EXISTS` rather than a second hand-written table list: a
    gameless team holding a ``player_game_batting`` row (the shape a divergence
    collapse leaves behind — ``merge_duplicate_game`` re-points ``game_id``
    only) passed the games-only filter and raised ``IntegrityError`` on the
    ``DELETE FROM teams``.

    ⚠ **The raise was never contained to its own team, and THAT is what made the
    leak permanent.** Neither :func:`_delete_game_scoped_data_for_perspectives`
    nor :func:`_delete_team_scoped_data` commits internally, and the raise fired
    before the ``conn.commit()`` below, so phases 1 and 2 rolled back for the
    WHOLE batch.  The rollback RESTORED the orphan-vs-orphan ``games`` rows
    Phase 1 had just deleted — and :data:`_TEAM_BASE_PRED` requires a team to
    have NO ``games`` row, so every rolled-back team became invisible to the
    only pass that could ever sweep it.  Nothing self-healed: across a 71-team
    restore run, reclamation ran 70 times and deleted 0 teams every time.  Each
    team's ``DELETE`` therefore runs under its OWN ``SAVEPOINT`` now (the
    ``scouting_loader`` per-team precedent), so an uncovered FK costs one team,
    not the batch.

    **Which half buys what.** The SAVEPOINT is what buys the CONTAINMENT, and it
    alone would produce the same set of surviving teams -- the six stat FKs would
    simply fail the way ``reports.team_id`` already does.  The widened predicate
    buys RETENTION SEMANTICS and OPERATOR DIAGNOSTICS: a team held by a stat row
    is a known, expected, benign state (the divergence stub), so it is reported
    as *retained* with the referencing table NAMED, not as a caught
    ``IntegrityError`` on a destructive path.  Do not read the predicate as
    load-bearing for correctness, and do not read the savepoint as redundant
    because of it.
    """
    if not orphan_ids:
        return 0

    placeholders = ",".join("?" for _ in orphan_ids)
    id_list = list(orphan_ids)

    # Phase 1: delete games where BOTH participants are orphans.  Scope to
    # orphan perspectives only -- non-orphan perspective rows for the same
    # games (e.g., the report team's perspective) are preserved.
    game_rows = conn.execute(
        f"SELECT game_id FROM games WHERE home_team_id IN ({placeholders}) "
        f"AND away_team_id IN ({placeholders})",
        id_list + id_list,
    ).fetchall()
    _delete_game_scoped_data_for_perspectives(
        conn, [r[0] for r in game_rows], id_list,
    )

    # Determine which orphans still have remaining game FK references.  Run
    # AFTER Phase 1 so the orphan-vs-orphan rows it just deleted are gone.
    game_ref_rows = conn.execute(
        f"SELECT DISTINCT home_team_id FROM games WHERE home_team_id IN ({placeholders}) "
        f"UNION "
        f"SELECT DISTINCT away_team_id FROM games WHERE away_team_id IN ({placeholders})",
        id_list + id_list,
    ).fetchall()
    game_ref_ids = {r[0] for r in game_ref_rows}

    # ...and which still have a game-CHILD reference.  Composed from the shared
    # _TEAM_STAT_EXISTS constant, never a second hand-written table list: that
    # drift is exactly what this fix closes, and a hand-list is how
    # merge_duplicate_game silently dropped two columns.  Also runs after Phase
    # 1, so a team whose only footprint was an orphan-vs-orphan
    # `game_perspectives` row is correctly seen as clean.
    stat_ref_rows = conn.execute(
        f"SELECT t.id FROM teams t WHERE t.id IN ({placeholders}) "
        f"AND {_TEAM_STAT_EXISTS.format(t='t')}",
        id_list,
    ).fetchall()
    stat_ref_ids = {r[0] for r in stat_ref_rows}

    undeletable_ids = game_ref_ids | stat_ref_ids
    deletable_ids = orphan_ids - undeletable_ids

    for team_id in sorted(stat_ref_ids - game_ref_ids):
        # The probe CAN name the table here -- these are precisely the six
        # tables it covers.  Contrast the savepoint WARNING below, which
        # deliberately promises no table name.
        logger.warning(
            "Orphan cleanup retained team_id=%d: still referenced by %s.",
            team_id, _first_stat_reference_table(conn, team_id),
        )

    # Phase 2: clean team-scoped data for all orphans
    _delete_team_scoped_data(
        conn, id_list, delete_team_rows=False,
    )

    # Phase 3: delete each deletable team row under its OWN savepoint, so an FK
    # this predicate does not cover (`reports.team_id` is NOT NULL REFERENCES
    # teams(id) with no ON DELETE, and is not a stat table) skips ONE team
    # instead of rolling the batch back -- see the docstring for why a rollback
    # here is unrecoverable rather than merely wasteful.  The savepoint name
    # interpolates an int, never a string, so it cannot escape the identifier
    # context.
    # Counted where the outcome actually HAPPENS, not derived by subtracting a
    # skip list from a set decided before the loop ran: a future extra skip path
    # that forgot to decrement would silently over-report deletions.
    deleted_count = 0
    skipped_count = 0
    for team_id in sorted(deletable_ids):
        savepoint = f"orphan_team_delete_{int(team_id)}"
        conn.execute(f"SAVEPOINT {savepoint}")
        try:
            conn.execute("DELETE FROM teams WHERE id = ?", (team_id,))
            conn.execute(f"RELEASE {savepoint}")
            deleted_count += 1
        # sqlite3.Error, NOT sqlite3.IntegrityError.  A narrower catch reinstates
        # the exact defect this loop exists to fix: any other DB error escapes
        # with the SAVEPOINT still open, the caller
        # (``generator.py::_cleanup_orphans``) swallows it, and the connection is
        # closed with the transaction live -- rolling Phases 1 and 2 back for the
        # whole batch and restoring the `games` rows that hide these teams from
        # reclamation forever.
        #
        # ⚠ Do NOT justify this by the `database is locked` scenario, which is
        # mostly unreachable HERE, and that was MEASURED: a DELETE matching ZERO
        # rows still takes SQLite's write lock, so Phases 1 and 2 have already
        # acquired it by the time this loop runs.  Cross-process contention
        # surfaces at Phase 1's first DELETE instead -- before any savepoint
        # exists, where nothing in this function can contain it.  That exposure
        # is real and remains OPEN; it is not what this catch closes.  This catch
        # is defense in depth on a destructive path: the outcome it must never
        # allow is a STRANDED SAVEPOINT, whatever raised.
        except sqlite3.Error as exc:
            conn.execute(f"ROLLBACK TO {savepoint}")
            conn.execute(f"RELEASE {savepoint}")
            skipped_count += 1
            # Names the team and the sqlite error text, and NOT a referencing
            # table: after the widening above, the six tables
            # _first_stat_reference_table probes can no longer be the cause, so
            # it would return "unknown" for exactly these cases.  Promise less
            # rather than promise a name the code cannot produce.
            logger.warning(
                "Orphan cleanup could not delete team_id=%d (%s); skipped it and "
                "kept the rest of the batch.",
                team_id, exc,
            )
    conn.commit()

    if undeletable_ids or skipped_count:
        logger.info(
            "Cleaned up %d orphan team(s); %d retained (still FK-referenced), "
            "%d skipped (delete raised).",
            deleted_count, len(undeletable_ids), skipped_count,
        )
    else:
        logger.info(
            "Cleaned up %d orphan team(s) from report generation.", deleted_count
        )
    return deleted_count


def is_team_eligible_for_cleanup(
    conn: sqlite3.Connection, team_id: int, exclude_report_id: int
) -> bool:
    """Check whether a team is eligible for cascade-delete after report removal.

    Guard conditions (all must pass):
    1. ``is_active = 0``
    2. No other ``reports`` rows reference this team_id

    These are the correct guards for the removed opponent-tracking registry
    mechanism (E-250 dropped that table). They are NOT asserted to be complete
    deletion-safety semantics: the shared-game/live-report eligibility guard
    (a cascade could destroy a still-referenced report's plays) is owned
    separately by CE-3/E-253, not by this function.

    Args:
        conn: Open SQLite connection.
        team_id: The team to check.
        exclude_report_id: The report being deleted (excluded from the
            multi-report check).
    """
    # Guard 1: is_active
    row = conn.execute(
        "SELECT is_active FROM teams WHERE id = ?", (team_id,)
    ).fetchone()
    if row is None:
        return False
    if row[0] != 0:
        return False

    # Guard 2: other reports
    row = conn.execute(
        "SELECT 1 FROM reports WHERE team_id = ? AND id != ? LIMIT 1",
        (team_id, exclude_report_id),
    ).fetchone()
    if row is not None:
        return False

    return True


def list_reports(conn: sqlite3.Connection | None = None) -> list[dict]:
    """Return all reports (joined to their run record) sorted by generated_at desc.

    Uses the shared ``list_reports_with_runs`` join (src/api/db.py) so the CLI
    (``bb report list``) and the admin list (``/admin/reports``) read the same
    1:1 LEFT JOIN (E-235-06 / TN-6). Each dict now carries the reports columns
    -- including the report-level ``error_message`` (newly returned here) -- the
    joined ``report_generation_runs`` columns (NULL for legacy rows with no run),
    and the derived ``url`` / ``is_expired``.

    Args:
        conn: An open connection to use.  When ``None`` (``bb report list``, the
            only caller today) one is opened and closed here.  The parameter
            exists so this entry point is symmetric with the other two: a caller
            inside a sandboxed path can hand its connection across the module
            boundary instead of letting this function resolve a global.  See
            :func:`_conn_scope`.

    Returns:
        List of report dicts. Empty list on a DB error (logged).
    """
    base_url = get_app_url()
    now = utcnow_iso()
    try:
        with _conn_scope(conn) as conn:
            result = list_reports_with_runs(conn)
    except sqlite3.Error:
        logger.exception("Failed to list reports")
        return []

    for r in result:
        r["url"] = f"{base_url}/reports/{r['slug']}"
        r["is_expired"] = r["expires_at"] < now
    return result


# ===========================================================================
# Orphan reference-data reclamation (E-273-01)
# ===========================================================================
#
# Report deletion is cascade-correct locally but leaves ORPHANED reference
# data -- ``teams`` / ``players`` / ``team_rosters`` rows no longer reachable
# from any surviving ``reports`` row and that no per-report cascade will ever
# reclaim (three root causes: order-dependent retention leak, opponent stubs
# never in a cascade's scope, players never deleted).  ``cascade_delete_team``
# answers a LOCAL question ("what does this team own?"); "is this team still
# reachable?" is a GLOBAL question only a reachability sweep can answer.
#
# The ownership graph is a strict DAG -- ``reports -> games -> teams ->
# team_rosters -> players`` -- so the sweep is two ordered phases, not an
# iterative fixed point (E-273 TN-1): the orphan-TEAM set is fully determined
# up front; the orphan-PLAYER set is determined AFTER the team pass removes
# orphan rosters (the only transitive edge).
#
# SINGLE-SOURCE (TN-8): the pass's DELETE targeting AND the invariant COUNT
# both derive from the SAME id-set producers below, so the delete-set and the
# count cannot drift.  The orphan-team predicate is defined ONCE (as the SQL
# fragments composed by :func:`_team_orphan_pred`) and reused by the team
# producer, the player producer's "surviving roster" test, and the orphan-held
# roster count -- never re-inlined.

_RECLAIM_CHUNK = 900
"""Max bound-variable count per ``... IN (?, ...)`` delete chunk.

The orphan set can be large (681 teams / 14,326 players in the live backlog),
so materialized-``IN`` deletes are chunked to stay under SQLite's bound-variable
limit (TN-8).  The producers themselves use correlated ``NOT EXISTS`` (never a
materialized ``NOT IN``) for the same reason.

WHY 900, AND WHY A HIGH ``getlimit()`` HERE PROVES NOTHING (E-277-03).  That
limit is BUILD-DEPENDENT, not a constant of SQLite: ``SQLITE_LIMIT_VARIABLE_NUMBER``
defaulted to 999 before SQLite 3.32.0 and to 32,766 from 3.32.0, and a build may
raise it further still -- the container these docstrings were written against
reports 250,000.  900 sits under the lowest of those, so the chunking holds on
any build whose limit is at least 900, which covers every documented SQLite
default.  Stated in both directions, because only one of them is obvious: a
build configured BELOW 900 would still raise, and this constant would have to be
lowered with it.

So do NOT read a generous ``getlimit()`` on the machine in front of you as
evidence that the chunking is dead code -- the deployment target's SQLite is not
necessarily the one you measured.  Pinned against exactly that misreading by
``test_chunked_player_delete_spans_more_than_two_chunks`` in
``tests/test_orphan_reclamation.py``, which lowers the test connection's limit
so that an unchunked variant raises rather than quietly passing.  Its sibling
``test_chunking_is_load_bearing_removing_it_raises`` is deliberate, not
redundant: that one REMOVES the chunking and requires the raise, so it is what
shows the first test's success is attributable to chunking at all.  The first
proves the chunked path deletes the whole set under a lowered limit; only the
second proves an unchunked path would not.
"""

# --- Orphan-team predicate (composed from two reusable SQL fragments) --------
#
# ``{t}`` is the outer ``teams`` alias.  Kept as two fragments so the BASE
# predicate can be evaluated WITH and WITHOUT the belt-and-suspenders stat
# clause (the WARN path needs "base AND has-stat-row"; the orphan set needs
# "base AND NOT has-stat-row").

_TEAM_BASE_PRED = (
    "{t}.membership_type = 'tracked' "
    # The root: no reports row references this team.
    "AND NOT EXISTS (SELECT 1 FROM reports r WHERE r.team_id = {t}.id) "
    # No games row references this team (home or away).
    "AND NOT EXISTS (SELECT 1 FROM games g "
    "                WHERE g.home_team_id = {t}.id OR g.away_team_id = {t}.id) "
    # Reachability ROOT exclusions: the THREE ROOTS from E-273 TN-7
    # (operator/user decisions) plus the ONE ROOT added by E-277-01.  A team
    # referenced by ANY of them is EXCLUDED from the orphan set, never deleted
    # and never NULLed.  They are NOT pins to clear -- see _TEAM_PIN_TABLES.
    #
    # PER-ROOT VERDICT, and deliberately no blanket claim in either direction.
    # The bullets below ARE the enumeration -- there is deliberately no summary
    # count here to drift out of step with them.  Note only that
    # ``opponent_links`` carries two of these roots, so a count of roots and a
    # count of tables are different numbers; where a count is unavoidable
    # elsewhere in this module it names its unit for that reason.  The
    # previous version of this comment said "all three are provable no-ops on
    # real data ... fire only in a bent-invariant case", which was false for the
    # one root that is load-bearing.  It was OUTLIVED, not careless: E-273
    # reasoned that ``our_team_id`` is always a member team because the morning
    # run iterates the operator's own teams -- sound until E-239 removed the
    # member sync.  ``src/db/teams.py`` now holds the ONLY ``INSERT INTO teams``
    # in ``src/`` or ``scripts/`` and hardcodes ``membership_type='tracked'``,
    # so own teams land squarely inside this predicate's base set.
    #
    #   * ``opponent_links.our_team_id`` -- LOAD-BEARING.  Production writer:
    #     ``src/gamechanger/opponent_ladder.py`` (``_upsert_resolved_positive``
    #     and ``_upsert_pending``, both self-committing) on the morning-run
    #     path.  Until E-277-01 this was the ONLY thing keeping a morning-run
    #     own team out of the orphan set, and that is no longer true: the
    #     morning run's slot write is gated only on ``not dry_run and not
    #     slot.suppress_persist``, NOT on the outcome, so an ordinary run
    #     persists an audit row for EVERY slot -- resolved, unresolved and
    #     placeholder alike -- and the audit root below pins the team too.
    #
    #     Neither root subsumes the other, but the overlap is the ordinary case
    #     and the gaps are narrow.  A link with NO slot arises in exactly three
    #     states: a ``--dry-run`` (``resolve_opponent`` self-commits its
    #     ``opponent_links`` row before the dry-run check, and no slot is
    #     written), the ``suppress_persist`` fresh-reservation skip, and a slot
    #     write that RAISED (``sqlite3.Error`` is caught, rolled back and the
    #     run continues, while the ladder's link is already committed).  Only
    #     the audit root covers the converse -- a placeholder-only team with no
    #     link ever, which is rung (b).
    #   * ``scheduled_report_runs.own_team_id`` -- LOAD-BEARING.  Production
    #     writer: ``_upsert_slot`` in ``src/reports/morning_run.py``.  Pins an
    #     own team whose morning run produced ONLY placeholder deferrals -- the
    #     one ladder rung that persists no ``opponent_links`` row, and therefore
    #     the shape the clause above does not already cover.  Its audit rows are
    #     the only non-regenerable data in this sweep's blast radius.
    #   * ``opponent_links.resolved_team_id`` -- CANNOT FIRE.  Mechanism: no
    #     site in ``src/`` or ``scripts/`` writes this column at all.  The only
    #     SQL touching it is this module's own cascade, which NULLs it.  So no
    #     production path can produce a row matching this clause.  (A grep for
    #     the bare name also hits ``scripts/smoke_test.py``; those are a LOCAL
    #     variable holding a GameChanger team id -- that file never mentions
    #     ``opponent_links``.  Noted so the next reader's grep does not read as
    #     counter-evidence.)
    #   * ``user_team_access.team_id`` -- REACHABLE, and NOT provably dead.  An
    #     earlier version of this comment claimed it could not fire because the
    #     grant surface is member-only.  That is FALSE for two of the three
    #     INSERT writers, and the error is recorded here because it is the same
    #     shape as the one this whole comment repairs.  Only
    #     ``src/api/auth.py::_assign_member_teams`` actually filters on
    #     ``membership_type = 'member'``.  The admin form handlers
    #     ``_create_user`` / ``_update_user`` in
    #     ``src/api/routes/reports_admin.py`` insert whatever integer team ids
    #     the POST supplies, with NO membership check --
    #     ``_get_available_teams()`` only populates the checkbox OPTIONS at
    #     render time and gates nothing on submit, and a POST is not restricted
    #     to the options a form offered.  Executed: a grant row on a ``tracked``
    #     team is accepted and removes that team from the orphan set.
    #
    #     BOTH HALVES, because either alone is misleading: this is REACHABLE
    #     THROUGH THE ADMIN WRITE PATH, and NOT EXERCISED BY THE NORMAL UI FLOW.
    #     The form offers only member teams as checkboxes, so routine operation
    #     will not produce such a row; the handler accepts one anyway if the
    #     submitted id names a tracked team.  So it is neither "fires on
    #     ordinary data" nor "cannot fire" -- do not collapse it to either.
    #     (The absent server-side validation is pre-existing and out of scope
    #     here; it is named as the reason the verdict is REACHABLE, not as a
    #     defect fixed.)
    #
    # The one CANNOT-FIRE clause is retained deliberately: it closes a latent
    # footgun for the cost of one ``NOT EXISTS``, and the reason it cannot fire
    # is a property of code in ANOTHER file that a future change could revoke
    # without touching this one.  Do not delete it as dead code -- re-run the
    # writer audit first, and note that the last two attempts to certify a root
    # dead were both wrong (E-273's on ``our_team_id``, E-277-01's on
    # ``user_team_access``).  A grep for writers is not enough on its own: for
    # each writer found, establish what values it can actually supply.
    "AND NOT EXISTS (SELECT 1 FROM opponent_links ol_r WHERE ol_r.resolved_team_id = {t}.id) "
    "AND NOT EXISTS (SELECT 1 FROM opponent_links ol_o WHERE ol_o.our_team_id = {t}.id) "
    "AND NOT EXISTS (SELECT 1 FROM user_team_access uta WHERE uta.team_id = {t}.id) "
    "AND NOT EXISTS (SELECT 1 FROM scheduled_report_runs srr WHERE srr.own_team_id = {t}.id)"
)
# NOTE: ``is_active`` is a DEAD guard (TN-2) -- ``ensure_team_row_with_provenance``
# hardcodes ``is_active=0`` on every INSERT, so a guard predicated on it protects
# zero rows.  It is intentionally NOT consulted here.

# Belt-and-suspenders GAME-CHILD reference clause (TN-2): a team referenced by a
# surviving game's child row via ``team_id``/``perspective_team_id`` (or
# ``batting_team_id``/``perspective_team_id`` on ``plays``, or
# ``perspective_team_id`` on ``game_perspectives``).
#
# ⚠️ NO LONGER VACUOUS (2026-08-15).  This clause was documented as vacuously
# true on real data -- "a gameless team cannot carry such a row, because the row
# belongs to a game the team participates in, so the team would have a ``games``
# row" -- and that contradiction is now BROKEN by the opponent-identity
# divergence collapse in ``GameLoader`` (see ``.claude/rules/data-model.md``,
# Same-listing Dedup).  Both of its branches leave a bare-name opponent stub
# holding stat rows on a game it has no ``games`` row for: the PROMOTE branch
# because ``merge_duplicate_game`` re-points ``game_id`` only, so re-pointed
# child rows keep ``team_id`` = stub while the stub's own ``games`` row is
# DELETED; the PRESERVE branch because the stub is created and its stats filed
# under the canonical id while no ``games`` row is ever written for it.
# So this clause now fires on REAL data, once per divergence collapse, and the
# excluded team accumulates.  That is the intended graceful behaviour -- but do
# NOT read a hit here as evidence of corruption.  It still converts a
# reclamation-halting
# ``IntegrityError`` (a surviving game-child FK at DELETE FROM teams -- which
# would ROLLBACK the ENTIRE sweep) into a graceful correct exclusion, with a WARN
# (see :func:`_warn_stat_referenced_gameless_teams`).
#
# This clause must cover EVERY ``teams(id)`` FK child that (a) is a GAME child
# (so it is not pin-deleted -- deleting its rows for a SURVIVING game would
# corrupt that game) and (b) is not otherwise absent by the base predicate /
# roots.  The full ``teams(id)`` FK-child audit (E-273 Codex-F1 remediation)
# classifies all live children as base-absent (games/reports), root-excluded
# (opponent_links -- via both its root columns -- user_team_access, and, since
# E-277-01, scheduled_report_runs), pin-deleted (team_rosters, scouting_runs,
# crawl_jobs,
# coaching_assignments, scheduled_report_runs), or
# game-child-excluded HERE (player_game_batting x2, player_game_pitching x2,
# spray_charts x2, reconciliation_discrepancies x2, plays x2, and
# ``game_perspectives`` -- the child the original grep-based sweep filtered out).
#
# ``scheduled_report_runs`` deliberately appears in TWO of those classes since
# E-277-01, so the classes are no longer mutually exclusive.  It is
# root-excluded (an audit-bearing team never reaches the team delete at all) AND
# still listed in _TEAM_PIN_TABLES as a retained FK safety net -- see the
# comment on that entry for why removing the pin entry is a hazard.
_TEAM_STAT_EXISTS = (
    "("
    "EXISTS (SELECT 1 FROM player_game_batting s "
    "        WHERE s.team_id = {t}.id OR s.perspective_team_id = {t}.id) "
    "OR EXISTS (SELECT 1 FROM player_game_pitching s "
    "           WHERE s.team_id = {t}.id OR s.perspective_team_id = {t}.id) "
    "OR EXISTS (SELECT 1 FROM spray_charts s "
    "           WHERE s.team_id = {t}.id OR s.perspective_team_id = {t}.id) "
    "OR EXISTS (SELECT 1 FROM reconciliation_discrepancies s "
    "           WHERE s.team_id = {t}.id OR s.perspective_team_id = {t}.id) "
    "OR EXISTS (SELECT 1 FROM plays s "
    "           WHERE s.batting_team_id = {t}.id OR s.perspective_team_id = {t}.id) "
    "OR EXISTS (SELECT 1 FROM game_perspectives s "
    "           WHERE s.perspective_team_id = {t}.id)"
    ")"
)

# Tables (and their team-scoped columns) probed to NAME the referencing table in
# the WARN.  Order fixes which table is reported first.  Each probe is called
# with a 2-tuple (team_id, team_id) by :func:`_first_stat_reference_table`, so
# every WHERE clause uses exactly TWO placeholders -- a single-column child
# (``game_perspectives``) repeats its column to consume both.
_STAT_REFERENCE_PROBES: tuple[tuple[str, str], ...] = (
    ("player_game_batting", "team_id = ? OR perspective_team_id = ?"),
    ("player_game_pitching", "team_id = ? OR perspective_team_id = ?"),
    ("spray_charts", "team_id = ? OR perspective_team_id = ?"),
    ("reconciliation_discrepancies", "team_id = ? OR perspective_team_id = ?"),
    ("plays", "batting_team_id = ? OR perspective_team_id = ?"),
    ("game_perspectives", "perspective_team_id = ? OR perspective_team_id = ?"),
)

# Innocuous team-scoped pins deleted BEFORE the ``teams`` row (FK-safe order).
# Deliberately EXCLUDES ``opponent_links`` and ``user_team_access``, the root
# tables that are not pins.  This is the TAILORED cleanup (E-273 TN-4 preference
# over reusing the monolithic ``_delete_team_scoped_data``): it never issues a
# no-op DELETE against an operator/user-decision table.  Each pin's team column
# is listed so the delete is a plain ``WHERE <col> IN (...)``.  ``teams`` is
# deleted LAST.
#
# NOT a root/pin partition since E-277-01: ``scheduled_report_runs`` is now BOTH
# a reachability root (above) and a retained pin entry (below).  The exclusion
# above names the root tables that are not pins; it is NOT a claim that every
# root is absent from this list.
_TEAM_PIN_TABLES: tuple[tuple[str, str], ...] = (
    ("team_rosters", "team_id"),
    ("scouting_runs", "team_id"),
    ("crawl_jobs", "team_id"),
    ("coaching_assignments", "team_id"),
    # RETAINED DELIBERATELY, and UNREACHABLE while the keep-root above stands
    # (E-277 TN-10).  A team carrying ``scheduled_report_runs`` rows is excluded
    # from the orphan set, so this DELETE can never match a row today.  That is
    # exactly what makes it look like dead code, which is the reasoning this
    # epic exists to correct elsewhere in this file -- so: DO NOT REMOVE THIS
    # ENTRY unless the ``scheduled_report_runs.own_team_id`` keep-root is
    # removed in the SAME commit.  Removing it alone was measured: the team
    # DELETE then hits ``own_team_id INTEGER NOT NULL REFERENCES teams(id)``
    # with no ``ON DELETE``, raising ``IntegrityError`` and ROLLING BACK THE
    # ENTIRE SWEEP.  Retaining it also keeps the sweep compliant with migration
    # 005's CASCADE MIRROR INVARIANT in every future state: if the keep-root is
    # ever weakened or bypassed, this entry is what still carries a deleted
    # team's audit rows away with it.  Same shape as the deliberately-retained
    # vacuous clause in ``_TEAM_STAT_EXISTS`` above.
    ("scheduled_report_runs", "own_team_id"),
    ("teams", "id"),
)


def _team_orphan_pred(alias: str) -> str:
    """Return the ONE orphan-team predicate for the given ``teams`` alias.

    ``base AND NOT stat_exists`` -- the single definition reused by
    :func:`_orphan_team_ids`, the "surviving roster" test in
    :func:`_orphan_player_ids`, and :func:`_orphan_roster_row_count`.  Because
    every consumer composes THIS string, the DELETE and the COUNT cannot drift
    (TN-8).
    """
    return f"({_TEAM_BASE_PRED.format(t=alias)}) AND NOT {_TEAM_STAT_EXISTS.format(t=alias)}"


@dataclass
class OrphanCounts:
    """Snapshot of the ownership-invariant orphan counts (E-273-01, TN-8).

    All three derive from the SAME producers the reclamation pass deletes
    through, so a zero here is exactly "the pass would delete nothing more".

    ``teams``       -- ``len(_orphan_team_ids)``.
    ``players``     -- ``len(_orphan_player_ids)``.
    ``roster_rows`` -- ``team_rosters`` rows held by an orphan team.
    """

    teams: int = 0
    players: int = 0
    roster_rows: int = 0


@dataclass
class ReclaimResult:
    """Outcome of one :func:`reclaim_orphan_reference_data` sweep (E-273-01).

    ``teams_deleted`` / ``players_deleted`` / ``roster_rows_deleted`` count the
    rows removed.  ``deferred`` is the explicit missing-safety-signal (TN-5): it
    is ``True`` when the concurrency gate refused (a live ``generating`` report
    remained after the reap) and NOTHING was deleted.  Consumers (the one-shot's
    exit-code semantics, E-273-05) MUST key on ``deferred`` -- "0 deletions, no
    error" is otherwise indistinguishable from a genuine no-orphan success.
    """

    teams_deleted: int = 0
    players_deleted: int = 0
    roster_rows_deleted: int = 0
    deferred: bool = False


def _first_stat_reference_table(conn: sqlite3.Connection, team_id: int) -> str:
    """Return the first stat table that references ``team_id`` (for the WARN).

    Probes each stat table in :data:`_STAT_REFERENCE_PROBES` order and returns
    the first table name that carries a row for ``team_id`` (via its team or
    perspective column).  Returns ``"unknown"`` if none match (should not happen
    -- the caller only invokes this for a team the stat clause already flagged).
    """
    for table, where in _STAT_REFERENCE_PROBES:
        row = conn.execute(
            f"SELECT 1 FROM {table} WHERE {where} LIMIT 1", (team_id, team_id)
        ).fetchone()
        if row is not None:
            return table
    return "unknown"


def _warn_stat_referenced_gameless_teams(conn: sqlite3.Connection) -> None:
    """WARN for each gameless team the belt-and-suspenders clause excluded.

    A team matching the BASE predicate (tracked, no reports, no games, not a
    root) but carrying a surviving stat row is EXCLUDED from the orphan set
    (graceful skip instead of a reclamation-halting ``IntegrityError``).  That
    exclusion silently swallows exactly the corruption signal the loud abort
    would have surfaced, so we log it -- mirroring the FK-safe-orphan stub+WARN
    convention (``.claude/rules/data-model.md``).

    ⚠️ NO LONGER a no-op on real data (2026-08-15).  The opponent-identity
    divergence collapse leaves a bare-name opponent stub holding stat rows on a
    game it has no ``games`` row for, so this fires once per such collapse.  The
    message therefore names BOTH causes: a benign divergence stub is expected
    and needs no action; an operator backfill is the one worth investigating.
    """
    sql = (
        f"SELECT id FROM teams t "
        f"WHERE {_TEAM_BASE_PRED.format(t='t')} AND {_TEAM_STAT_EXISTS.format(t='t')}"
    )
    for (team_id,) in conn.execute(sql).fetchall():
        table = _first_stat_reference_table(conn, team_id)
        logger.warning(
            "Team id=%s excluded from reclamation despite no games -- "
            "game-child row in %s. EXPECTED for a bare-name opponent stub left "
            "by an opponent-identity divergence collapse (benign, no action). "
            "Investigate only if no such collapse explains it -- e.g. an "
            "operator backfill.",
            team_id,
            table,
        )


def _orphan_team_ids(conn: sqlite3.Connection, *, warn: bool = False) -> set[int]:
    """Return the ids of all orphan ``teams`` rows (E-273 TN-2, E-273 TN-8).

    The ONE team predicate: ``tracked`` AND no ``reports`` AND no ``games`` AND
    none of the reachability roots -- ``opponent_links.resolved_team_id``,
    ``opponent_links.our_team_id`` and ``user_team_access.team_id`` from
    E-273 TN-7, plus ``scheduled_report_runs.own_team_id`` added by E-277-01 --
    AND the belt-and-suspenders stat clause.  The per-root verdicts (which of
    these fire on real data, and why) live on :data:`_TEAM_BASE_PRED`.
    Built as correlated
    ``NOT EXISTS`` (never a materialized ``NOT IN``) so a large orphan set binds
    NO variables here at all and SQLite's build-dependent bound-variable limit
    (see :data:`_RECLAIM_CHUNK`) is never in play on this path.

    Args:
        conn: Open connection (the pass's in-transaction connection, or any
            read connection for the count).
        warn: When ``True`` (the pass's pre-delete read only), also emit a
            WARNING per gameless team the stat clause excluded.  Left ``False``
            for the count / self-assert recompute so a single pass logs each
            offender at most once.
    """
    sql = f"SELECT id FROM teams t WHERE {_team_orphan_pred('t')}"
    orphan_ids = {row[0] for row in conn.execute(sql).fetchall()}
    if warn:
        _warn_stat_referenced_gameless_teams(conn)
    return orphan_ids


def _orphan_player_ids(conn: sqlite3.Connection) -> set[str]:
    """Return the ids of all orphan ``players`` rows (TN-3, TN-8).

    A player is an orphan iff it has NO surviving reference in ANY of: a
    ``team_rosters`` row on a SURVIVING (non-orphan) team, ``player_game_batting``,
    ``player_game_pitching``, ``plays`` (batter OR pitcher -- the load-bearing
    ``plays`` inclusion; a plays-only stub would be falsely deleted without it),
    or ``spray_charts`` (player OR pitcher).  ``player_id`` is TEXT.

    The "surviving roster" test embeds the SAME orphan-team predicate
    (:func:`_team_orphan_pred`) as a correlated ``NOT EXISTS`` rather than a
    materialized orphan-id list, so the answer is state-independent: whether read
    before or after the team tier deletes, a player whose only roster is on an
    orphan team is correctly an orphan.  ``reconciliation_discrepancies.player_id``
    is a bare TEXT column with NO FK to ``players``, so it is intentionally NOT a
    reachability edge (TN-3 knowingly-accepted residual).
    """
    orphan_pred = _team_orphan_pred("ot")
    sql = f"""
        SELECT p.player_id FROM players p
        WHERE NOT EXISTS (
            SELECT 1 FROM team_rosters tr
            WHERE tr.player_id = p.player_id
              AND NOT EXISTS (
                  SELECT 1 FROM teams ot
                  WHERE ot.id = tr.team_id AND {orphan_pred}
              )
        )
        AND NOT EXISTS (SELECT 1 FROM player_game_batting b WHERE b.player_id = p.player_id)
        AND NOT EXISTS (SELECT 1 FROM player_game_pitching pp WHERE pp.player_id = p.player_id)
        AND NOT EXISTS (SELECT 1 FROM plays pl
                        WHERE pl.batter_id = p.player_id OR pl.pitcher_id = p.player_id)
        AND NOT EXISTS (SELECT 1 FROM spray_charts sc
                        WHERE sc.player_id = p.player_id OR sc.pitcher_id = p.player_id)
    """
    return {row[0] for row in conn.execute(sql).fetchall()}


def _orphan_roster_row_count(conn: sqlite3.Connection) -> int:
    """Return the number of ``team_rosters`` rows held by an orphan team (TN-8)."""
    sql = (
        "SELECT COUNT(*) FROM team_rosters tr WHERE EXISTS ("
        f"SELECT 1 FROM teams ot WHERE ot.id = tr.team_id AND {_team_orphan_pred('ot')}"
        ")"
    )
    return conn.execute(sql).fetchone()[0]


def count_orphan_reference_data(conn: sqlite3.Connection) -> OrphanCounts:
    """Return the ownership-invariant orphan counts (E-273 TN-8).

    The single-source assertion helper: teams and players are ``len()`` of the
    SAME sets the pass deletes, plus the orphan-held roster-row count.  Because
    the count derives from :func:`_orphan_team_ids` (which excludes every
    reachability root), a legitimate ``opponent_links`` / ``user_team_access``
    / ``scheduled_report_runs`` survivor is NEVER flagged as a leak
    (E-273 TN-7 F5).  Consumers (E-273-04 batch test, E-273-05 one-shot) MUST call this
    rather than re-inlining the query.
    """
    return OrphanCounts(
        teams=len(_orphan_team_ids(conn)),
        players=len(_orphan_player_ids(conn)),
        roster_rows=_orphan_roster_row_count(conn),
    )


def _delete_where_in(
    conn: sqlite3.Connection, table: str, column: str, ids: list
) -> None:
    """Chunked ``DELETE FROM {table} WHERE {column} IN (...)``.

    Chunks at :data:`_RECLAIM_CHUNK` so no single statement binds more variables
    than SQLite's bound-variable limit allows.  That limit is BUILD-DEPENDENT
    (E-277-03), so a generous ``getlimit()`` on the build in front of you is NOT
    evidence that this chunking is unnecessary -- see :data:`_RECLAIM_CHUNK` for
    the range of documented values and why 900 is the safe choice across them.
    """
    for start in range(0, len(ids), _RECLAIM_CHUNK):
        chunk = ids[start : start + _RECLAIM_CHUNK]
        placeholders = ",".join("?" for _ in chunk)
        conn.execute(
            f"DELETE FROM {table} WHERE {column} IN ({placeholders})", chunk
        )


def reclaim_orphan_reference_data(
    conn: sqlite3.Connection,
) -> ReclaimResult:
    """Reachability-based terminal sweep of orphaned reference data (E-273-01).

    Removes unreachable ``teams`` / ``team_rosters`` / ``players`` in DAG order
    (team tier then player tier), reclaiming all three orphan root causes, and
    holds the ownership invariant.  ADDITIVE -- it does NOT modify
    ``cascade_delete_team`` (the two behavior-pinning cascade tests stay green).

    Concurrency guard (TN-5), reap-then-gate on ``status='generating'``:
      1. :func:`reap_stale_generating_reports` FIRST (its own committed
         transaction) so a crashed generation is reaped, not treated as an
         hour-long block.
      2. The gate check, the orphan-set compute, and the DELETEs then run in ONE
         transaction on ONE connection (``BEGIN IMMEDIATE`` ... ``COMMIT``).  The
         pass OWNS the full transaction internally -- the NAMED EXCEPTION to the
         codebase's caller-owns-the-transaction convention -- because the
         check -> compute -> delete must be atomic.  Split across connections it
         is a TOCTOU hole: a generation committing an opponent stub AFTER a
         gate-read on a different connection would be seen (and deleted) by a
         fresh orphan-read snapshot.  The single write-locked transaction closes
         it: a stub committed after this snapshot is not in the orphan set.
      3. If a live ``generating`` report remains after the reap, the pass
         REFUSES (deletes nothing) and returns ``deferred=True`` -- a liveness
         delay by design (fail toward "don't sweep").

    Ordering within the one transaction (TN-1 -- single transaction, NOT a
    single up-front snapshot): the orphan-TEAM set is read PRE-delete (the same
    point the gate decided); the team tier is deleted; THEN the orphan-PLAYER set
    is read POST-team-delete, so the just-removed orphan rosters are absent and
    the roster-only players correctly fall out.  A final zero-delta self-assert
    confirms the fixed point (no third pass deletes anything).

    PRECONDITION -- the connection must have NO open transaction.  Passing one
    with uncommitted DML in flight RAISES ``RuntimeError`` at this function's
    entry, before the reap and before anything is committed.  There is no
    ``conn=None`` path here: this parameter is REQUIRED, so unlike the other two
    entry points every call reaches the guard.

    What the raise means in production, in both directions: it stops the
    destructive path, but no operator is paged.  THIS function's call sites are
    exactly three, enumerated from the code rather than from any shared list:

    * :func:`cleanup_expired_reports` -- wrapped; logs at WARNING and continues.
    * The admin report-delete path in ``src/api/routes/reports_admin.py`` --
      wrapped; logs at WARNING and the deletion still succeeds.
    * ``scripts/reclaim_orphan_reference_data.py``, the one-shot -- wrapped, but
      it does MORE than log: it logs at ERROR **and returns a non-zero process
      exit code**.  So "demoted to a log line" is not true of every site, and
      this is the one that differs.

    "Refuses loudly" describes a direct caller, not the deployed behaviour.

    Args:
        conn: An open connection, with no transaction in progress, that the pass
            OWNS the transaction on.  The wiring sites (E-273-02) pass a fresh
            ``get_connection()``; tests / the one-shot inject their DB.

    Returns:
        A :class:`ReclaimResult` with the per-tier deletion counts, or
        ``deferred=True`` (and zero counts) when the gate refused.

    Raises:
        RuntimeError: If ``conn`` has an open transaction, or if the two-phase
            sweep fails to reach its fixed point.
    """
    # E-277-02 AC-3: BEFORE the reap.  Below it the reap has already committed
    # and the guard could never observe the dirty state it exists to catch.
    _require_clean_connection(conn, "reclaim_orphan_reference_data")
    result = ReclaimResult()

    # Step 1: reap FIRST, in its own committed transaction (TN-5.2).
    reap_stale_generating_reports(conn)

    # Steps 2-7: gate + compute + delete in ONE write-locked transaction.
    conn.execute("BEGIN IMMEDIATE")
    try:
        # Step 2: gate (TN-5.1/5.3) -- refuse while any live generating report
        # remains.  BEGIN IMMEDIATE holds the write lock, so a generation
        # committing its generating row concurrently is serialized behind us.
        generating = conn.execute(
            "SELECT COUNT(*) FROM reports WHERE status = 'generating'"
        ).fetchone()[0]
        if generating:
            # E-277-02 AC-6b.  UNREACHABLE TODAY, and kept deliberately on a
            # stated basis -- the same treatment as the vacuous clause in
            # ``_TEAM_STAT_EXISTS`` above, and for the same reason: a
            # never-fires clause shipped WITHOUT saying so is what invites a
            # later reader to delete it as dead code.
            #
            # Why it cannot fire: a transaction is NECESSARILY active here, not
            # merely usually.  ``BEGIN IMMEDIATE`` sits OUTSIDE this ``try``, so
            # a failure there never reaches this branch at all; and if the gate
            # ``SELECT`` above fails, control goes to the ``except`` handler
            # rather than here.  There is no path on which this branch runs with
            # the transaction already ended.
            #
            # Why it is kept anyway: the guard costs one attribute read and
            # holds regardless of what the surrounding code does later.  Its
            # absence would be a latent "cannot rollback - no transaction is
            # active" that replaces a clean deferral with a spurious error, and
            # the reachability argument above depends on the placement of a
            # ``BEGIN IMMEDIATE`` three statements away -- exactly the "safe
            # because of what happened two statements ago" reasoning this epic
            # keeps finding wrong.  Guarded, not exempted, for that reason.
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            result.deferred = True
            logger.info(
                "Orphan reclamation deferred: %d live 'generating' report(s) "
                "remain after reap.",
                generating,
            )
            return result

        # Step 3: orphan-TEAM set, PRE-delete read (same point as the gate).
        team_ids = _orphan_team_ids(conn, warn=True)
        # Count orphan-held roster rows BEFORE the team tier deletes them.
        result.roster_rows_deleted = _orphan_roster_row_count(conn)

        # Step 4: delete the team tier (innocuous pins + team rows), FK-safe,
        # ``teams`` last.  This loop never touches ``opponent_links`` or
        # ``user_team_access`` -- they are not in ``_TEAM_PIN_TABLES``.
        # ``scheduled_report_runs`` IS in that list and so is reached, but never
        # for an audit-bearing team: any team referenced by ANY root is excluded
        # from ``team_ids`` by construction, so no root's rows are ever deleted
        # here.  (No count of roots or tables is given -- this comment does not
        # need one to say what the loop touches, and a count kept here is one
        # more thing to keep in step with the root list.)
        if team_ids:
            id_list = list(team_ids)
            for table, column in _TEAM_PIN_TABLES:
                _delete_where_in(conn, table, column, id_list)
        result.teams_deleted = len(team_ids)

        # Step 5: orphan-PLAYER set, POST-team-delete read (TN-1) -- the freed
        # rosters are absent, so roster-only players correctly fall out.
        player_ids = _orphan_player_ids(conn)

        # Step 6: delete players (leaf tier; player_id is TEXT, set can be large).
        _delete_where_in(conn, "players", "player_id", list(player_ids))
        result.players_deleted = len(player_ids)

        # Step 7: zero-delta self-assert (TN-1) -- the DAG guarantees a fixed
        # point after two phases; a non-zero recompute means a logic bug, so
        # fail loudly and roll back rather than commit a half-correct state.
        remaining = count_orphan_reference_data(conn)
        if remaining.teams or remaining.players or remaining.roster_rows:
            raise RuntimeError(
                "orphan reclamation did not reach a fixed point: "
                f"{remaining!r} remain after the two-phase sweep"
            )

        conn.execute("COMMIT")
    except Exception:
        # E-277-02 AC-6: roll back only if a transaction is still open.  On
        # SQLITE_FULL / SQLITE_IOERR SQLite has ALREADY auto-rolled back, and an
        # unconditional ``ROLLBACK`` then raises "cannot rollback - no
        # transaction is active" -- which REPLACES the real failure as the
        # propagated exception, leaving the true cause demoted to ``__context__``
        # and the wrong type/message in front of any caller inspecting it.
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise

    logger.info(
        "Orphan reclamation: deleted %d team(s), %d roster row(s), %d player(s).",
        result.teams_deleted,
        result.roster_rows_deleted,
        result.players_deleted,
    )
    return result
