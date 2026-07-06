"""Backfill venue-local ``games.game_date`` from the recoverable UTC instant.

Operator-maintenance re-derivation (E-253-11) that corrects the historical
UTC ``game_date`` mis-derivation (pre-E-253-04, the loader sliced the raw UTC
prefix, filing evening games under the next UTC day). E-253-04 fixed the FORWARD
derivation and relocated ``derive_local_date`` to ``src/util/timezone.py``; this
module re-derives EXISTING rows with the same logic.

Three-tier recoverability (TN-5) keyed on what survives in the ``games`` row:

1. ``start_time`` present + ``timezone`` present -> clean re-derivation via
   ``derive_local_date(start_time, timezone)`` (the majority -- the public feed
   and schedule loader supply both).
2. ``start_time`` present, ``timezone`` NULL -> re-derive with the E-252-05
   operating-tz default as the fallback zone. The seam returns a ``ZoneInfo``
   OBJECT; ``derive_local_date`` takes an IANA tz-NAME, so we bridge via the
   ``ZoneInfo``'s ``.key`` attribute -- never passing the object in (double-wrap
   hazard, per TN-5).
3. ``start_time`` NULL -> no recoverable instant (legacy / game-summaries-only
   loads). Leave ``game_date`` untouched, count and report the skip -- never
   fabricate a date.

Only rows whose re-derived date DIFFERS from the stored value are UPDATEd, so
the backfill is idempotent and re-runnable (a second run is a no-op) -- mirroring
``bb data backfill-appearance-order``. It corrects stored dates ONLY: it does
NOT re-run player/game dedup. A corrected date that shifts 7-day-rolling-window
membership is the intended correction, not a regression (TN-5).
"""

from __future__ import annotations

import logging
import sqlite3

from src.util.timezone import derive_local_date, get_operating_timezone

logger = logging.getLogger(__name__)


def backfill_game_dates(
    conn: sqlite3.Connection, *, dry_run: bool = True
) -> dict[str, int]:
    """Re-derive ``games.game_date`` from ``start_time`` + ``timezone``.

    Args:
        conn: Open SQLite connection. When ``dry_run`` is False this function
            commits its own UPDATEs (mirroring ``backfill_appearance_order``).
        dry_run: When True (default), compute and count the changes but write
            nothing. When False, apply the UPDATEs and commit.

    Returns:
        A summary dict with counts:
          ``games_processed`` -- total games rows examined
          ``rows_updated`` -- rows whose game_date was (or would be) corrected
          ``rows_unchanged`` -- rows already holding the re-derived date
          ``skipped_no_start_time`` -- tier 3: start_time NULL, un-correctable
          ``skipped_unparseable`` -- start_time present but not parseable
    """
    summary = {
        "games_processed": 0,
        "rows_updated": 0,
        "rows_unchanged": 0,
        "skipped_no_start_time": 0,
        "skipped_unparseable": 0,
    }

    # Operating-tz NAME (tier-2 fallback). Read once; bridge ZoneInfo -> IANA
    # name via .key so it can be passed to derive_local_date (never the object).
    operating_tz_name = get_operating_timezone().key

    rows = conn.execute(
        "SELECT game_id, game_date, start_time, timezone FROM games"
    ).fetchall()

    updates: list[tuple[str, str]] = []  # (new_game_date, game_id)
    for game_id, game_date, start_time, timezone in rows:
        summary["games_processed"] += 1

        # Tier 3: no recoverable instant -- leave untouched, count the skip.
        if not start_time:
            summary["skipped_no_start_time"] += 1
            continue

        # Tier 1 (timezone present) / Tier 2 (timezone NULL -> operating default).
        tz_name = timezone or operating_tz_name
        new_date = derive_local_date(start_time, tz_name)
        if new_date is None:
            # start_time present but unparseable -- cannot correct; do not touch.
            summary["skipped_unparseable"] += 1
            continue

        if new_date == game_date:
            summary["rows_unchanged"] += 1
            continue

        summary["rows_updated"] += 1
        updates.append((new_date, game_id))

    if updates and not dry_run:
        conn.executemany(
            "UPDATE games SET game_date = ? WHERE game_id = ?", updates
        )
        conn.commit()

    logger.info(
        "game_date backfill (%s): processed=%d updated=%d unchanged=%d "
        "skipped_no_start_time=%d skipped_unparseable=%d",
        "dry-run" if dry_run else "execute",
        summary["games_processed"], summary["rows_updated"],
        summary["rows_unchanged"], summary["skipped_no_start_time"],
        summary["skipped_unparseable"],
    )
    return summary
