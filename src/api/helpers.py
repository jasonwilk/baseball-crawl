"""Shared helper functions for the baseball-crawl reports surface.

These helpers are used both as Jinja2 filters (registered in src/reports/renderer.py)
and as importable Python functions for use in DB query functions.
"""

from __future__ import annotations

import datetime
import logging
import os

logger = logging.getLogger(__name__)

_APP_URL_DEFAULT = "http://baseball.localhost:8001"

# Recognized ``APP_ENV`` values (post-normalization).  A non-empty value that
# normalizes to anything OUTSIDE this set is a typo (e.g. ``prod``/``prd``) and
# is caught loudly at startup by :func:`validate_app_env` rather than silently
# selecting the insecure (non-``Secure`` cookie) posture at runtime.
_RECOGNIZED_APP_ENVS = frozenset(
    {"production", "development", "dev", "test", "staging"}
)


def get_app_url() -> str:
    """Return the base application URL from the environment.

    Reads ``APP_URL``; falls back to ``http://baseball.localhost:8001`` (the
    dev host the browser uses, keeping magic-link/report links coherent with
    the WebAuthn origin).  Trailing slashes are stripped.  The single source
    for report-link and magic-link base URLs (E-247-07 AC-4) -- production sets
    ``APP_URL`` explicitly, so this default only affects local-dev links.
    """
    return os.environ.get("APP_URL", _APP_URL_DEFAULT).rstrip("/")


def get_app_env() -> str:
    """Return the normalized ``APP_ENV`` value (``.strip().lower()``).

    Casing and surrounding whitespace are discarded so that ``production``,
    ``Production``, ``PRODUCTION``, and ``" production "`` all normalize to
    ``"production"``.  Unset or empty ``APP_ENV`` normalizes to ``""`` -- callers
    treat that as the local-dev posture (non-production).  This is the single
    normalizer that both :func:`is_production` and :func:`validate_app_env`
    build on (E-254-01).
    """
    return os.environ.get("APP_ENV", "").strip().lower()


def is_production() -> bool:
    """Return True when running in production (``APP_ENV`` normalizes to ``production``).

    The single-source production-detection seam (E-252-03, strict-normalized in
    E-254-01).  Reads :func:`get_app_env`, so casing/whitespace variants of
    ``production`` correctly select the production posture and unset/empty
    resolves to non-production (local dev needs ``Secure``-off cookies over
    HTTP; this default is load-bearing).  A leaf helper (imports only ``os`` /
    ``logging``), so ``email.py``, the morning-run CLI preflight,
    ``routes/auth.py::_is_dev_mode``, ``auth.py::SessionMiddleware``, and
    ``csrf.py`` can all single-source prod detection without an import cycle.
    """
    return get_app_env() == "production"


def validate_app_env() -> None:
    """Refuse to start when ``APP_ENV`` is set to an unrecognized value.

    A non-empty ``APP_ENV`` that normalizes to a value OUTSIDE
    :data:`_RECOGNIZED_APP_ENVS` (an abbreviation typo such as ``prod``/``prd``)
    is caught at startup -- a CRITICAL-level log plus a ``RuntimeError`` -- rather
    than silently downgrading the cookie ``Secure`` flag at runtime (the actual
    fail-open the audit flagged).  Unset OR set-but-empty ``APP_ENV`` is treated
    as unset (local-dev posture) and does NOT raise.

    Called once at app construction, alongside the ``DEV_USER_EMAIL``-in-production
    guard in :meth:`src.api.auth.SessionMiddleware.__init__` (E-254-01).

    Raises:
        RuntimeError: If ``APP_ENV`` is non-empty and normalizes outside the
            recognized set.
    """
    normalized = get_app_env()
    if not normalized:
        return
    if normalized not in _RECOGNIZED_APP_ENVS:
        recognized = ", ".join(sorted(_RECOGNIZED_APP_ENVS))
        raw = os.environ.get("APP_ENV", "")
        logger.critical(
            "APP_ENV=%r is not a recognized environment (expected one of %s, "
            "or unset for local dev); refusing to start to avoid silently "
            "selecting an insecure cookie posture at runtime.",
            raw,
            recognized,
        )
        raise RuntimeError(
            f"Unrecognized APP_ENV={raw!r}; expected one of {recognized}, "
            "or leave it unset for local development."
        )


def ip_display(ip_outs: int | None) -> str:
    """Convert an ip_outs integer to standard innings-pitched display notation.

    Innings pitched are stored as integer outs (1 IP = 3 outs).  This function
    converts to the ``"W.T"`` display format where W is whole innings and T is
    the remainder in thirds (0, 1, or 2).

    Args:
        ip_outs: Total outs recorded.  May be None for players with no pitching data.

    Returns:
        Formatted IP string, e.g. ``"6.2"`` for 20 outs, ``"3.0"`` for 9 outs,
        ``"0.0"`` for 0 outs, or ``"-"`` for None.

    Examples:
        >>> ip_display(20)
        '6.2'
        >>> ip_display(9)
        '3.0'
        >>> ip_display(0)
        '0.0'
        >>> ip_display(None)
        '-'
    """
    if ip_outs is None:
        return "-"
    whole = ip_outs // 3
    thirds = ip_outs % 3
    return f"{whole}.{thirds}"


def format_avg(numerator: int | None, denominator: int | None) -> str:
    """Format a batting average (or similar ratio) as a three-decimal string.

    Returns ``"-"`` when the denominator is zero or None (avoids division by
    zero).  Returns ``".000"`` when numerator is zero and denominator is
    non-zero.

    Args:
        numerator:   Hit count (or similar numerator).
        denominator: At-bat count (or similar denominator).

    Returns:
        Formatted average string, e.g. ``".333"``, ``".000"``, or ``"-"``.

    Examples:
        >>> format_avg(1, 3)
        '.333'
        >>> format_avg(0, 0)
        '-'
        >>> format_avg(3, 3)
        '1.000'
        >>> format_avg(0, 4)
        '.000'
    """
    if not denominator:
        return "-"
    avg = (numerator or 0) / denominator
    # Baseball average convention: ".333" not "0.333" (no leading zero)
    formatted = f"{avg:.3f}"
    return formatted.lstrip("0") or ".000"


def format_date(date_str: str | None) -> str:
    """Convert an ISO date string to a short human-readable format.

    Converts ``"YYYY-MM-DD"`` to ``"Mon D"`` format (e.g. ``"2026-03-04"``
    becomes ``"Mar 4"``).  Returns ``"-"`` for None or unparseable values.

    Args:
        date_str: ISO date string in ``"YYYY-MM-DD"`` format, or None.

    Returns:
        Formatted date string, e.g. ``"Mar 4"``, or ``"-"`` on failure.

    Examples:
        >>> format_date("2026-03-04")
        'Mar 4'
        >>> format_date("2026-01-15")
        'Jan 15'
        >>> format_date(None)
        '-'
    """
    if not date_str:
        return "-"
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%b %-d")
    except (ValueError, AttributeError):
        return "-"
