"""Shared helper functions for the baseball-crawl dashboard.

These helpers are used both as Jinja2 filters (registered in routes/dashboard.py)
and as importable Python functions for use in DB query functions.
"""

from __future__ import annotations

import datetime


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


def format_season_display(season_id: str) -> str:
    """Convert a season ID to a short human-readable label.

    Strips the classification suffix (e.g. ``-hs``, ``-legion``) and
    capitalizes the season type word.  Output is season-first format:
    ``"Spring 2026"``, not ``"2026 Spring"``.

    Args:
        season_id: Season ID string, e.g. ``"2026-spring-hs"``.

    Returns:
        Human-readable label, e.g. ``"Spring 2026"``.

    Examples:
        >>> format_season_display("2026-spring-hs")
        'Spring 2026'
        >>> format_season_display("2025-summer")
        'Summer 2025'
        >>> format_season_display("2025-spring-legion")
        'Spring 2025'
        >>> format_season_display("2025-fall-reserve")
        'Fall 2025'
    """
    _TYPE_MAP = {
        "spring": "Spring",
        "summer": "Summer",
        "fall": "Fall",
        "legion": "Legion",
    }
    parts = season_id.split("-", 2)  # ["2026", "spring"] or ["2026", "spring", "hs"]
    if len(parts) < 2:
        return season_id
    year = parts[0]
    season_type = _TYPE_MAP.get(parts[1], parts[1].capitalize())
    return f"{season_type} {year}"


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
