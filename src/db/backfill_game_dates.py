"""Backfill venue-local ``games.game_date`` from the recoverable UTC instant.

Operator-maintenance re-derivation (E-253-11) that corrects the historical
UTC ``game_date`` mis-derivation (pre-E-253-04, the loader sliced the raw UTC
prefix, filing evening games under the next UTC day). E-253-04 fixed the FORWARD
derivation and relocated ``derive_local_date`` to ``src/util/timezone.py``; this
module re-derives EXISTING rows with the same logic.

Three-tier recoverability (TN-5) keyed on what survives in the ``games`` row:

1. ``start_time`` present + ``timezone`` present -> clean re-derivation via
   ``derive_local_date(start_time, timezone)`` (the majority -- the public feed
   and schedule loader supply both). If this runtime cannot RESOLVE that zone,
   the row is left untouched and counted (see below).
2. ``start_time`` present, ``timezone`` NULL -> re-derive with the E-252-05
   operating-tz default as the fallback zone. The seam returns a ``ZoneInfo``
   OBJECT; ``derive_local_date`` takes an IANA tz-NAME, so we bridge via the
   ``ZoneInfo``'s ``.key`` attribute -- never passing the object in (double-wrap
   hazard, per TN-5). ⚠️ NARROWED in E-278-04 -- see the full-day guard below.
3. ``start_time`` NULL -> no recoverable instant (legacy / game-summaries-only
   loads). Leave ``game_date`` untouched, count and report the skip -- never
   fabricate a date.

Two REFUSALS this module owes to E-278-04, both on the same principle: a repair
pass must not re-derive a row whose correct answer it cannot verify. Note this
is the opposite side of that story's LOAD-path rule, which forbids keying
full-day behavior on a null timezone -- at load, ``is_full_day`` is right there
in the payload, so using a proxy would be substituting a worse signal for an
available one. Here the flag is genuinely, structurally absent, and refusing to
touch an unverifiable row is the conservative direction rather than a shortcut.

**Unresolvable timezone (tier 1).** ``derive_local_date`` now fails CLOSED on a
zone this runtime cannot resolve rather than returning the unconverted UTC date.
Such a row is left alone and counted under its OWN key -- not folded into
``skipped_unparseable``, whose name would then be asserting something false
about it.

**The full-day shape (tier 2).** ``games`` persists no full-day marker, and it
is not being added: a column added now is NULL for exactly the rows anyone would
want to count, and backfilling it from the API means you already have the answer.
So a stored all-day event is INDISTINGUISHABLE here from a timed one -- it is
just a midnight-UTC ``start_time`` with a NULL ``timezone``. Re-deriving it
applies the operating zone to what is really a date marker and shifts it back a
day, re-committing the very defect E-278-04 removed from the load path. This
module therefore SKIPS the ``timezone IS NULL`` + exactly-midnight-UTC
intersection and counts it, which is measurably the right cut: over one 928-row
corpus, midnight-UTC alone selected 50 rows for 2 real full-day events (a 25x
over-count) while the intersection with a null timezone selected exactly 2.
Non-midnight NULL-timezone rows are unambiguous instants and tier 2 still
repairs them.

Only rows whose re-derived date DIFFERS from the stored value are UPDATEd, so
the backfill is idempotent and re-runnable (a second run is a no-op) -- mirroring
``bb data reload-annotated-pitches`` (E-245), the surviving operator-maintenance
precedent this command (E-253) followed.  It corrects stored dates ONLY: it does
NOT re-run player/game dedup. A corrected date that shifts 7-day-rolling-window
membership is the intended correction, not a regression (TN-5).
"""

from __future__ import annotations

import logging
import sqlite3

from src.util.timezone import (
    derive_local_date,
    get_operating_timezone,
    resolve_timezone,
)

logger = logging.getLogger(__name__)

# The date-marker signature of a stored all-day event, per the module docstring.
# Matched against the stored ``start_time`` STRING rather than a parsed instant.
# That is safe today because ``games.start_time`` has exactly one writer --
# ``GameLoader._upsert_game``, which writes GameChanger's wire value through
# unchanged. (Its ``ON CONFLICT`` uses ``COALESCE(excluded.start_time,
# games.start_time)``, which either keeps an old GC wire value or writes a new
# one; it never TRANSFORMS either, so string-suffix matching stays sound. That
# COALESCE lets a sentinel ``game_date`` sit over a retained ``start_time`` --
# a real effect, documented at ``_derive_game_date`` -- but it is about which
# VALUE survives, not about the value's format.) So every full-day event
# OBSERVED carries the first rendering,
# ``...T00:00:00.000Z``. The other two are defensive against a future writer
# rendering the same instant differently, NOT against anything present now.
# Over-matching is the safe direction here: it can only widen a REFUSAL to
# re-derive, never cause a wrong date to be written.
_MIDNIGHT_UTC_SUFFIXES = ("T00:00:00.000Z", "T00:00:00Z", "T00:00:00+00:00")


def backfill_game_dates(
    conn: sqlite3.Connection, *, dry_run: bool = True
) -> dict[str, int]:
    """Re-derive ``games.game_date`` from ``start_time`` + ``timezone``.

    Args:
        conn: Open SQLite connection. When ``dry_run`` is False this function
            commits its own UPDATEs (mirroring ``reload_all_games``).
        dry_run: When True (default), compute and count the changes but write
            nothing. When False, apply the UPDATEs and commit.

    Returns:
        A summary dict with counts:
          ``games_processed`` -- total games rows examined
          ``rows_updated`` -- rows whose game_date was (or would be) corrected
          ``rows_unchanged`` -- rows already holding the re-derived date
          ``skipped_no_start_time`` -- tier 3: start_time NULL, un-correctable
          ``skipped_unparseable`` -- start_time present but not parseable
          ``skipped_unresolvable_timezone`` -- the stored timezone does not
            resolve in this runtime, so no venue-local date can be computed
          ``skipped_ambiguous_full_day`` -- a midnight-UTC start_time with a NULL
            timezone: indistinguishable from an all-day event's date marker, so
            re-deriving could shift it back a day
    """
    summary = {
        "games_processed": 0,
        "rows_updated": 0,
        "rows_unchanged": 0,
        "skipped_no_start_time": 0,
        "skipped_unparseable": 0,
        "skipped_unresolvable_timezone": 0,
        "skipped_ambiguous_full_day": 0,
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
        if timezone:
            if resolve_timezone(timezone) is None:
                # The row named a zone and this runtime cannot resolve it, so
                # there is no venue-local date to compute. Substituting the
                # operating zone would discard what the row actually says and
                # write an unverified guess; the UTC slice is the defect this
                # repairs. Leave it, count it, name it.
                logger.warning(
                    "game_id=%s carries unresolvable timezone %r; left untouched.",
                    game_id, timezone,
                )
                summary["skipped_unresolvable_timezone"] += 1
                continue
            tz_name = timezone
        else:
            # NULL timezone + a midnight-UTC instant is the stored shape of an
            # all-day event, whose start_time is a DATE MARKER. `games` keeps no
            # full-day flag, so this row cannot be told apart from a genuine
            # midnight-UTC start -- and re-deriving it would shift a real date
            # marker back a day. Refuse rather than guess.
            if start_time.endswith(_MIDNIGHT_UTC_SUFFIXES):
                summary["skipped_ambiguous_full_day"] += 1
                continue
            tz_name = operating_tz_name

        new_date = derive_local_date(start_time, tz_name)
        if new_date is None:
            # Past the resolvability gate above, the only remaining None cause is
            # a start_time that will not parse -- so this key name is accurate.
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
        "skipped_no_start_time=%d skipped_unparseable=%d "
        "skipped_unresolvable_timezone=%d skipped_ambiguous_full_day=%d",
        "dry-run" if dry_run else "execute",
        summary["games_processed"], summary["rows_updated"],
        summary["rows_unchanged"], summary["skipped_no_start_time"],
        summary["skipped_unparseable"],
        summary["skipped_unresolvable_timezone"],
        summary["skipped_ambiguous_full_day"],
    )
    return summary
