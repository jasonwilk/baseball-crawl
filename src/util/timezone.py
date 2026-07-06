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
invalid-value degradation mirrors ``src.reports.morning_run.derive_local_date``
(unknown tz -> log a WARNING and fall back, never crash).
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
