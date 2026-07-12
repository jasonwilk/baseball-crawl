"""Tests for the UTC-iso half of ``src/util/timezone.py`` (E-256-03).

``get_operating_timezone`` / ``operating_today`` / ``derive_local_date`` are
exercised in ``tests/test_morning_run.py``.  This module pins ``utcnow_iso``
and its ``UTC_ISO_FORMAT`` contract, which E-256-03 made the single source of
the timestamp shape this project WRITES.

The format is load-bearing, not cosmetic: ``reports.generated_at`` and
``reports.expires_at`` are compared LEXICALLY (never parsed), so lexical order
must equal chronological order.  That holds only while every operand shares one
format -- which is exactly what the two pre-consolidation ``_utcnow_iso`` copies
violated.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from src.util.timezone import UTC_ISO_FORMAT, utcnow_iso

_EXACT_SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestUtcnowIsoFormat:
    """The emitted shape is second-precision with a literal trailing ``Z``."""

    def test_matches_exact_shape(self) -> None:
        assert _EXACT_SHAPE.match(utcnow_iso())

    def test_has_no_fractional_seconds(self) -> None:
        """The old ``scouting`` copy emitted a constant ``.000`` -- it must not return."""
        assert "." not in utcnow_iso()

    def test_round_trips_through_the_declared_format(self) -> None:
        """``UTC_ISO_FORMAT`` is the format ``utcnow_iso`` actually uses."""
        parsed = datetime.strptime(utcnow_iso(), UTC_ISO_FORMAT)
        assert parsed.year >= 2026

    def test_is_utc_not_local(self) -> None:
        """The instant is UTC, not the operating timezone (venue-local is a
        separate seam -- ``operating_today`` / ``derive_local_date``)."""
        emitted = datetime.strptime(utcnow_iso(), UTC_ISO_FORMAT).replace(tzinfo=timezone.utc)
        assert abs(emitted - datetime.now(timezone.utc)) < timedelta(seconds=5)


class TestLexicalOrderingInvariant:
    """Lexical string order must equal chronological order.

    This is the property the report-expiry comparisons depend on
    (``expires_at > utcnow_iso()`` in ``morning_run``; ``expires_at < now`` in
    ``reports_admin``; ``expires_at < ?`` / ``generated_at < ?`` in SQL).
    """

    def test_one_second_later_sorts_greater(self) -> None:
        """Lexical order tracks chronological order at the format's finest
        granularity -- one second, the smallest difference it can represent.

        A wider gap (days apart) would pass under any format that renders the
        date, and so would not exercise the ordering property at all.
        """
        base = datetime(2026, 7, 9, 3, 17, 42, tzinfo=timezone.utc)
        earlier = base.strftime(UTC_ISO_FORMAT)
        later = (base + timedelta(seconds=1)).strftime(UTC_ISO_FORMAT)
        assert earlier < later, f"{earlier!r} should sort before {later!r}"

    def test_same_second_renders_one_exact_string(self) -> None:
        """Sub-second differences collapse to a single, exact rendering.

        This is what makes an expiry check at the exact expiry second resolve
        deterministically rather than by format luck: two instants anywhere
        inside second 42 produce the *same* string, and that string is pinned
        here as a literal.  The literal is the load-bearing part -- an equality
        between two renderings of the same value would hold for every possible
        format, including the dotted one this consolidation removed.
        """
        early = datetime(2026, 7, 9, 3, 17, 42, 0, tzinfo=timezone.utc)
        late = datetime(2026, 7, 9, 3, 17, 42, 999_999, tzinfo=timezone.utc)

        assert early.strftime(UTC_ISO_FORMAT) == "2026-07-09T03:17:42Z"
        assert late.strftime(UTC_ISO_FORMAT) == "2026-07-09T03:17:42Z"

    def test_dotted_format_would_invert_same_second_ordering(self) -> None:
        """Regression guard for the bug the consolidation removed.

        The two former implementations differed only by a constant ``".000"``.
        Within the same second that suffix INVERTS lexical order, because ``"."``
        (0x2E) sorts before ``"Z"`` (0x5A) -- so a ``.000Z`` "now" would read as
        strictly earlier than an equal-second ``Z`` ``expires_at``, flipping an
        expired report to non-expired.  Mixing the two formats is what this
        assertion documents as unsafe; the canonical helper emits only one.
        """
        base = datetime(2026, 7, 9, 3, 17, 42, tzinfo=timezone.utc)
        canonical = base.strftime(UTC_ISO_FORMAT)
        dotted = base.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        assert dotted < canonical
        assert not utcnow_iso().endswith(".000Z")
