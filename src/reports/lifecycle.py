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
    counts orphan partial-HTML files unlinked; ``errors`` counts rows whose reap
    raised (per-row error isolation -- one bad row does not abort the sweep).
    """

    reaped: int = 0
    files_removed: int = 0
    errors: int = 0


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
    :func:`cleanup_expired_reports` / ``_delete_report``) before flipping the row.

    Idempotent: only ``generating`` rows older than the threshold are selected, so
    a re-run finds none (they are now ``failed``); ``ready``/``failed``/``no_games``
    rows and fresh in-progress ``generating`` rows are never touched.

    Reachable without operator action via :func:`cleanup_expired_reports` (which
    runs opportunistically at ``generate_report`` start and via ``bb report
    cleanup``) and the FastAPI app lifespan startup.

    Args:
        conn: An open connection to use.  When ``None`` (the CLI and app-startup
            callers) one is opened and closed here.  See :func:`_conn_scope`.

    Returns:
        A :class:`ReaperResult` with ``reaped`` / ``files_removed`` / ``errors``.
    """
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
                # Unlink any orphan partial HTML (written before the 'ready' update
                # that would have set report_path -- so report_path is still NULL and
                # cleanup_expired_reports can never reap it). Canonical resolution
                # via the named _REPORTS_DIR constant + is_file guard, mirroring
                # cleanup_expired_reports / _delete_report.
                file_path = _REPORTS_DIR / f"{slug}.html"
                if file_path.is_file():
                    file_path.unlink()
                    logger.info("Removed orphan HTML for reaped report: %s", file_path)
                    result.files_removed += 1
                conn.execute(
                    "UPDATE reports SET status = 'failed', error_message = ? "
                    "WHERE id = ? AND status = 'generating'",
                    (reaped_message, report_id),
                )
                result.reaped += 1
            except Exception as exc:  # noqa: BLE001 -- per-row error isolation
                logger.warning(
                    "Failed to reap stale 'generating' report id=%s: %s", report_id, exc
                )
                result.errors += 1
                continue
        conn.commit()

    if result.reaped:
        logger.info(
            "Reaped %d stale 'generating' report(s) to failed (%d orphan file(s) removed)",
            result.reaped, result.files_removed,
        )
    return result


def cleanup_expired_reports(
    conn: sqlite3.Connection | None = None,
) -> CleanupResult:
    """Remove on-disk HTML files for expired reports; KEEP the DB rows.

    Selects ``reports`` rows whose ``expires_at`` is strictly in the past
    (``expires_at < now``) and that still have a non-NULL ``report_path``,
    unlinks each HTML file, and NULLs ``report_path`` -- but KEEPS the row so
    the report still appears as expired in ``bb report list`` / ``/admin/reports``
    and serving it keeps the existing 404 behavior.

    File removal mirrors the ``_delete_report`` admin path: canonical
    ``_REPO_ROOT`` resolution plus an ``.is_file()`` guard. Each row's cleanup
    is wrapped in per-row error isolation so one unremovable file (e.g. a
    permission error) does not abort the whole sweep; a failing row keeps its
    ``report_path`` so a later sweep can retry.

    Reachable both opportunistically at the start of ``generate_report``
    and via the ``bb report cleanup`` CLI command.

    Args:
        conn: An open connection to use.  When ``None`` (the ``bb report cleanup``
            caller) one is opened and closed here.  ``generate_report`` passes the
            connection it opened, so the sweep runs against the caller's database
            rather than re-resolving one from this module's globals.  See
            :func:`_conn_scope`.

    Returns:
        A :class:`CleanupResult` with ``files_removed`` and ``errors`` counts.
    """
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
    conn.execute(f"DELETE FROM player_season_batting WHERE team_id IN ({placeholders})", team_ids)
    conn.execute(f"DELETE FROM player_season_pitching WHERE team_id IN ({placeholders})", team_ids)
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
    preserved.  Orphan teams that still have game FK references after
    Phase 1 are retained (team-scoped data is still cleaned).
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

    # Determine which orphans still have remaining game FK references
    remaining_rows = conn.execute(
        f"SELECT DISTINCT home_team_id FROM games WHERE home_team_id IN ({placeholders}) "
        f"UNION "
        f"SELECT DISTINCT away_team_id FROM games WHERE away_team_id IN ({placeholders})",
        id_list + id_list,
    ).fetchall()
    undeletable_ids = {r[0] for r in remaining_rows}
    deletable_ids = orphan_ids - undeletable_ids

    # Phase 2: clean team-scoped data for all orphans
    _delete_team_scoped_data(
        conn, id_list, delete_team_rows=False,
    )
    # Only delete team rows that have no remaining game references
    if deletable_ids:
        dp = ",".join("?" for _ in deletable_ids)
        conn.execute(f"DELETE FROM teams WHERE id IN ({dp})", list(deletable_ids))
    conn.commit()

    count = len(deletable_ids)
    if undeletable_ids:
        logger.info(
            "Cleaned up %d orphan team(s); %d retained (shared games).",
            count, len(undeletable_ids),
        )
    else:
        logger.info("Cleaned up %d orphan team(s) from report generation.", count)
    return count


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
