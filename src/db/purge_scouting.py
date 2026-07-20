"""Scouting/report data purge -- clean data slate, preserving identity + auth.

Backs ``bb db purge-scouting`` (E-267-06). This is the most destructive command
in the system: it empties every scouting and report table while leaving user
identity and authentication intact, so coaches stay logged in across the wipe.

Why this exists instead of the two obvious alternatives:

* A mass report-delete does NOT clean-slate. ``_delete_report`` purges a team's
  data only when the report is the LAST one for that team AND the team is
  ``is_active = 0``; an ``is_active = 1`` subject team and its children
  (players, seasons, orphan team rows) strand behind that cascade guard.
* ``bb db reset`` clears everything by deleting the DB file -- including
  ``users`` / ``passkey_credentials`` / ``sessions``, i.e. every login.

This module is the targeted middle path. It mirrors the STRUCTURE of
:mod:`src.db.reset` (production guard, ``--force`` escape hatch, programmatic
entry point) but NOT its guard body -- see :func:`check_purge_production_guard`.

Partition (TN-8, data-engineer owned; verified against migrations 001-012 --
012 is ``ALTER TABLE`` only and adds no table). :data:`KEEP_TABLES` (7) and
:data:`PURGE_DELETE_ORDER` (20) are exhaustive and disjoint over the 27
non-internal live tables; ``tests/test_purge_scouting.py`` re-derives that from
``sqlite_master`` so a future migration cannot add a table that falls through
the partition unclassified.

Three properties are load-bearing and each is pinned by a test:

1. **FK enforcement is LIVE.** The delete order below is FK-safe, but a
   mis-order only aborts LOUDLY if foreign keys are actually enforced.
   ``sqlite3.connect()`` defaults ``PRAGMA foreign_keys`` to OFF and
   :mod:`src.db.reset` never turns it on (it deletes the whole file, so it does
   not care) -- a naive mirror of that module would silently ORPHAN rows while
   appearing to succeed. This module routes through
   :func:`src.api.db.get_connection` (which sets the pragma) and then
   RE-VERIFIES it at runtime via :func:`_assert_foreign_keys_on` before touching
   a single row.
2. **One transaction.** Every delete runs inside a single transaction --
   committed at the end, rolled back on any error -- so a mid-purge failure can
   never leave a corrupt half-state.
3. **Report HTML is unlinked for ALL purged reports**, not just expired ones.
   :func:`src.reports.lifecycle.cleanup_expired_reports` filters
   ``expires_at < now`` and is therefore NOT the mechanism here.
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

from src.api.db import get_connection
from src.api.helpers import is_production
from src.db.paths import resolve_db_path

logger = logging.getLogger(__name__)

# Repo root, resolved the canonical way (src/db/purge_scouting.py -> repo root).
# A module-level global specifically so tests can point report-path resolution
# at a tmp_path instead of the real ``data/reports/`` tree.
_REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# The partition (TN-8)
# ---------------------------------------------------------------------------

#: Identity, authentication, and bootstrap tables that SURVIVE the purge.
#: ``programs`` is kept because it holds the ``lsb-hs`` bootstrap row (which
#: ``bb db reset`` also recreates) and is a FK-safe parent of nothing purged.
#: ``_migrations`` is kept so the schema version is not lost.
KEEP_TABLES = frozenset(
    {
        "users",
        "passkey_credentials",
        "magic_link_tokens",
        "sessions",
        "webauthn_challenges",
        "programs",
        "_migrations",
    }
)

#: Every purged table, in FK-SAFE DELETE ORDER (children before parents).
#: Order is load-bearing: with foreign keys enforced, a mis-order raises
#: ``sqlite3.IntegrityError`` and the whole purge rolls back.
#:
#: Two classifications are counter-intuitive and were resolved by the
#: data-engineer, so do not "correct" them:
#:   * ``user_team_access`` is PURGE, not KEEP. It is AUTHORIZATION, not
#:     authentication -- login survives via users/passkey/magic-link/sessions.
#:     It FKs ``teams``, admins see all teams regardless, and non-admin grants
#:     are re-granted as teams regenerate.
#:   * ``seasons`` is PURGE. It self-heals through ``ensure_season_row``.
PURGE_DELETE_ORDER: tuple[str, ...] = (
    # 1. grandchildren (FK to plays)
    "play_events",
    # 2. report children (FK to reports)
    "report_generation_runs",
    "scheduled_report_runs",
    # 3. children of games / teams / players
    "plays",
    "player_game_batting",
    "player_game_pitching",
    "spray_charts",
    "reconciliation_discrepancies",
    "game_perspectives",
    "team_rosters",
    "scouting_runs",
    "opponent_links",
    "crawl_jobs",
    "coaching_assignments",
    "user_team_access",
    "reports",
    # 4. games and players (parents of the above, children of teams/seasons)
    "games",
    "players",
    # 5. teams
    "teams",
    # 6. seasons (parent of games/team_rosters)
    "seasons",
)

PURGE_TABLES = frozenset(PURGE_DELETE_ORDER)


@dataclass
class PurgeResult:
    """Outcome of one :func:`purge_scouting_data` run.

    Attributes:
        rows_deleted: Per-table deleted-row counts (only non-zero tables).
        files_removed: Report HTML files successfully unlinked.
        file_errors: Report HTML rows whose unlink failed (isolated, not fatal).
    """

    rows_deleted: dict[str, int] = field(default_factory=dict)
    files_removed: int = 0
    file_errors: int = 0

    @property
    def total_rows(self) -> int:
        return sum(self.rows_deleted.values())


# ---------------------------------------------------------------------------
# Production guard (AC-4 / TN-9)
# ---------------------------------------------------------------------------


def check_purge_production_guard(force: bool) -> None:
    """Refuse a production purge unless ``--force`` was passed.

    Deliberately does NOT delegate to
    :func:`src.db.reset.check_production_guard`. That function compares
    ``os.environ.get("APP_ENV", "development").lower() == "production"``, which
    is the IDEA-101 bypass class: a stray whitespace variant such as
    ``" production "`` does not match, so the guard silently fails OPEN on the
    single most destructive command in the system. This guard routes through the
    canonical :func:`src.api.helpers.is_production` seam, whose
    ``.strip().lower()`` normalizer makes casing AND whitespace variants all
    select the production posture.

    Args:
        force: True when ``--force`` was passed on the CLI.

    Raises:
        SystemExit: If running in production and ``force`` is False.
    """
    if not is_production():
        return
    if not force:
        logger.error(
            "REFUSING to purge: APP_ENV indicates PRODUCTION. This would delete "
            "all scouting and report data. Pass --force to confirm."
        )
        sys.exit(1)
    logger.warning(
        "Purging scouting/report data on PRODUCTION (--force supplied). "
        "User identity and auth will be preserved; all scouting/report data "
        "will be destroyed. Proceeding."
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _assert_foreign_keys_on(conn: sqlite3.Connection) -> None:
    """Fail loudly unless FK enforcement is actually live on ``conn``.

    Not belt-and-braces. The FK-safe delete order is the ONLY thing standing
    between a future edit and silently orphaned rows, and it is inert when
    ``PRAGMA foreign_keys`` is OFF -- which is sqlite3's DEFAULT. Verifying the
    pragma's live value (rather than trusting that the connection factory set
    it) turns "FK enforcement is intended" into "FK enforcement is proven",
    right before the deletes that depend on it.

    Raises:
        RuntimeError: If foreign key enforcement is not enabled.
    """
    row = conn.execute("PRAGMA foreign_keys").fetchone()
    if not row or not row[0]:
        raise RuntimeError(
            "Refusing to purge: PRAGMA foreign_keys is OFF on this connection. "
            "The FK-safe delete order cannot abort on a mis-order without it, "
            "so a purge would silently orphan rows."
        )


def _collect_report_paths(conn: sqlite3.Connection) -> list[tuple[object, str]]:
    """Enumerate ``(id, report_path)`` for EVERY report with an on-disk file.

    No expiry filter -- deliberately NOT
    :func:`src.reports.lifecycle.cleanup_expired_reports`, which selects only
    ``expires_at < now``. The purge removes every report, so it must remove
    every report's HTML.

    Must run BEFORE the ``reports`` DELETE: once the rows are gone there is
    nothing left to enumerate.
    """
    return [
        (row[0], row[1])
        for row in conn.execute(
            "SELECT id, report_path FROM reports WHERE report_path IS NOT NULL"
        )
    ]


def _unlink_report_files(paths: list[tuple[object, str]]) -> tuple[int, int]:
    """Unlink the enumerated report HTML files with PER-ROW error isolation.

    One unremovable file (permissions, a path that vanished under us) must not
    abort the purge, so every row is wrapped individually. A path that is
    already absent is a no-op, not an error -- the desired end state is "the
    file is gone", which is already true.

    Resolution mirrors the canonical ``_delete_report`` /
    ``cleanup_expired_reports`` model (``_REPO_ROOT / "data" / report_path`` plus
    an ``.is_file()`` guard) and ADDS a containment check those paths lack.
    ``Path.__truediv__`` DISCARDS the base entirely when the right operand is
    absolute (``Path("/repo/data") / "/etc/passwd"`` is ``/etc/passwd``), and a
    ``../..`` prefix escapes on resolution -- either way ``.is_file()`` then
    passes and ``unlink()`` deletes a file outside the reports tree. Today
    ``report_path`` is generated internally so this is not reachable, but this
    is the most destructive command in the system and it enumerates EVERY
    report row, so the containment is asserted rather than assumed. A violation
    is counted as a file error, never raised -- it must not abort a purge whose
    database work has already committed.

    Returns:
        ``(files_removed, file_errors)``.
    """
    removed = 0
    errors = 0
    base = (_REPO_ROOT / "data").resolve()
    for report_id, report_path in paths:
        try:
            file_path = (base / report_path).resolve()
            if not file_path.is_relative_to(base):
                errors += 1
                logger.warning(
                    "Purge REFUSING to remove report file for report id=%s: "
                    "path %r resolves to %s, outside the reports base %s.",
                    report_id,
                    report_path,
                    file_path,
                    base,
                )
                continue
            if file_path.is_file():
                file_path.unlink()
                removed += 1
                logger.info("Purge removed report file: %s", file_path)
        except OSError:
            errors += 1
            logger.warning(
                "Purge could not remove report file for report id=%s (%s); "
                "continuing.",
                report_id,
                report_path,
                exc_info=True,
            )
    return removed, errors


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def purge_scouting_data(
    db_path: Path | None = None,
    force: bool = False,
) -> PurgeResult:
    """Empty every scouting/report table, preserving identity and auth.

    The programmatic entry point behind ``bb db purge-scouting``. Deletes the
    :data:`PURGE_DELETE_ORDER` tables in FK-safe order inside ONE transaction,
    leaving :data:`KEEP_TABLES` untouched.

    The production guard ALWAYS runs here. It is deliberately not skippable:
    the CLI runs its own copy first (so the guard fires BEFORE the confirmation
    prompt, mirroring ``bb db reset``), but a library whose only protection is
    "the caller remembered to check" is one edit deep on the most destructive
    command in the system. The duplicate WARN on the production ``--force`` path
    is the whole cost.

    Transaction scope: an explicit ``BEGIN IMMEDIATE`` opens the write
    transaction BEFORE the report-path enumeration, so the SELECT reads the same
    snapshot the DELETEs act on. Three processes share this WAL file (admin UI,
    interactive CLI, morning-run cron); enumerating outside the transaction
    would let a report row inserted in the gap have its row deleted but its HTML
    orphaned. Enumeration still precedes the ``reports`` DELETE -- it must, since
    the rows are about to vanish.

    Unlink ordering (deliberate): the files are unlinked AFTER the transaction
    COMMITS. Unlinking is not rollback-able, so unlinking mid-transaction would
    mean a rolled-back purge leaves ``reports`` rows pointing at files that no
    longer exist: precisely the corrupt half-state the single transaction exists
    to prevent. Deferring inverts the residual failure into a harmless one -- a
    crash between commit and unlink orphans some HTML on disk with no rows
    referring to it.

    Args:
        db_path: Database path. Defaults to the canonical resolution.
        force: Proceed even in production (the operator's explicit confirmation).

    Returns:
        A :class:`PurgeResult` with per-table row counts and file tallies.

    Raises:
        SystemExit: Production without ``force``.
        RuntimeError: If FK enforcement is not live on the connection.
        sqlite3.Error: On a DB failure -- the transaction is rolled back first,
            so no partial purge is committed.
    """
    check_purge_production_guard(force=force)

    resolved = resolve_db_path(db_path)
    logger.info("Purging scouting/report data from: %s", resolved)

    result = PurgeResult()
    conn = get_connection(resolved)
    try:
        # Proven, not assumed -- and before any row is touched.
        _assert_foreign_keys_on(conn)

        try:
            # Open the write transaction FIRST so the enumeration below reads
            # inside it (see the transaction-scope note above).
            conn.execute("BEGIN IMMEDIATE")
            report_paths = _collect_report_paths(conn)
            for table in PURGE_DELETE_ORDER:
                deleted = conn.execute(f"DELETE FROM {table}").rowcount  # noqa: S608
                if deleted:
                    result.rows_deleted[table] = deleted
            conn.commit()
        except Exception:
            # Single-transaction contract: nothing partial survives a failure.
            conn.rollback()
            logger.error(
                "Purge FAILED and was rolled back; the database is unchanged.",
                exc_info=True,
            )
            raise

        # Post-commit (see the ordering note above).
        result.files_removed, result.file_errors = _unlink_report_files(report_paths)
    finally:
        conn.close()

    logger.info(
        "Purge complete: %d row(s) across %d table(s); %d report file(s) removed "
        "(%d file error(s)). Identity and auth preserved.",
        result.total_rows,
        len(result.rows_deleted),
        result.files_removed,
        result.file_errors,
    )
    return result
