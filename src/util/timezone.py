"""Operating-timezone seam (E-252-05 / CE-2).

The single reusable source of the venue OPERATING timezone and the operating-tz
"today". Introduced for morning-run's default target date, but deliberately kept
here (a neutral, dependency-light module -- only stdlib) rather than inside
``src.reports.morning_run`` so it can be imported from anywhere without pulling
in the report pipeline.

CE-3 / E-253 REUSES this same seam for ``game_date`` derivation and MUST NOT
introduce a second timezone convention (epic TN-4): import
:func:`get_operating_timezone` / :func:`operating_today` from here.

The operating timezone is read once, from the ``OPERATING_TIMEZONE`` env var,
defaulting to the venue (``America/Chicago``) when unset or invalid. The
invalid-value degradation mirrors :func:`derive_local_date` (also housed here as
of E-253-04): unknown tz -> log a WARNING and fall back, never crash.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

# The env var + default (user-confirmed). CE-3/E-253 reuses this convention.
OPERATING_TIMEZONE_ENV = "OPERATING_TIMEZONE"
DEFAULT_OPERATING_TIMEZONE = "America/Chicago"


def get_operating_timezone() -> ZoneInfo:
    """Return the configured operating :class:`~zoneinfo.ZoneInfo`.

    Reads ``OPERATING_TIMEZONE`` (an IANA name, e.g. ``"America/New_York"``).
    Falls back to :data:`DEFAULT_OPERATING_TIMEZONE` when the env var is unset or
    empty (the normal case, no warning), and falls back WITH a logged WARNING
    when it names an unknown/invalid zone (AC-4). Never raises.
    """
    name = os.environ.get(OPERATING_TIMEZONE_ENV, "").strip() or DEFAULT_OPERATING_TIMEZONE
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning(
            "Unknown %s=%r; falling back to %s",
            OPERATING_TIMEZONE_ENV,
            name,
            DEFAULT_OPERATING_TIMEZONE,
        )
        return ZoneInfo(DEFAULT_OPERATING_TIMEZONE)


def operating_today(now: datetime | None = None) -> date:
    """The current calendar date in the operating timezone.

    Using this instead of the container's UTC ``date.today()`` keeps the default
    "today" venue-local: in production the container clock is UTC, so after
    ~19:00 venue time the UTC date has already rolled to tomorrow and an evening
    run would otherwise default to tomorrow's games (AC-1).

    Args:
        now: The instant to convert. A tz-aware datetime is used as-is; a naive
            datetime is treated as UTC. Defaults to the real current UTC instant.
            Injectable so callers/tests are deterministic with no real-clock
            dependence (TN-8).

    Returns:
        The operating-timezone local date of ``now``.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(get_operating_timezone()).date()


def derive_local_date(start_datetime: str | None, tz_name: str | None) -> str | None:
    """Derive a game's LOCAL calendar date from its UTC start + IANA timezone.

    A UTC-"today" filter (or a UTC-sliced ``game_date``) would miss late-evening
    games that roll past UTC midnight (TN-9 / B3; CE-3 / E-253-04), so the
    calendar date MUST be computed in the local timezone.

    Relocated here from ``src.reports.morning_run`` (E-253-04) so lower-layer
    callers -- notably ``src.gamechanger.loaders.game_loader`` -- can reuse it
    without inverting the layering (loaders importing from reports).

    Args:
        start_datetime: ISO-8601 UTC datetime string (e.g.
            ``"2026-06-20T23:00:00.000Z"``), or ``None`` (full-day events).
        tz_name: IANA timezone string (e.g. ``"America/Chicago"``), or ``None``.
            Pass an IANA NAME, never a :class:`~zoneinfo.ZoneInfo` object -- the
            operating-tz seam callers bridge :func:`get_operating_timezone`'s
            ``ZoneInfo`` to its name via ``.key`` before calling this.

    Returns:
        The local date as ``"YYYY-MM-DD"``, or ``None`` when ``start_datetime``
        is absent (the caller falls back to its own raw date).
    """
    if not start_datetime:
        return None
    iso = start_datetime.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        logger.warning("Unparseable start_datetime %r; cannot derive local date", start_datetime)
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if tz_name:
        try:
            dt = dt.astimezone(ZoneInfo(tz_name))
        except (ZoneInfoNotFoundError, ValueError):
            logger.warning(
                "Unknown timezone %r; using UTC date for the local-date filter",
                tz_name,
            )
    return dt.date().isoformat()


# The canonical wire format for timestamps this project WRITES (E-256-03).
# Second precision, no fractional part. Load-bearing: ``reports.generated_at``
# and ``reports.expires_at`` are compared LEXICALLY (not parsed) -- by
# ``cleanup_expired_reports``' SQL ``expires_at < ?``, by the stale-'generating'
# reaper's ``generated_at < ?``, and by the plain string ``<`` / ``>`` in
# ``reports_admin`` and ``morning_run``. Lexical order equals chronological
# order ONLY while every operand shares one format, so both sides of those
# comparisons must be produced from this constant.
#
# Do NOT confuse this with GameChanger's WIRE format (``...T16:00:00.000Z``,
# seen in ``start_ts`` / ``last_scoring_update``), which we only ever READ.
UTC_ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def utcnow_iso() -> str:
    """Return the current UTC instant as a :data:`UTC_ISO_FORMAT` string.

    The single implementation (E-256-03). It replaces the two divergent private
    ``_utcnow_iso`` copies in ``src.reports.generator`` and
    ``src.gamechanger.crawlers.scouting``, which differed by a constant
    ``".000"`` fractional part -- enough to invert lexical ordering between two
    same-second timestamps, since ``"."`` (0x2E) sorts before ``"Z"`` (0x5A).
    """
    return datetime.now(timezone.utc).strftime(UTC_ISO_FORMAT)
