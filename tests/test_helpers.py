"""Unit tests for src/api/helpers.py (E-004-01).

Tests ip_display filter and format_avg helper per AC-7 and AC-8.

Run with:
    pytest tests/test_helpers.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.api.helpers import format_avg, format_date, ip_display  # noqa: E402


class TestIpDisplay:
    """Tests for ip_display filter (AC-7)."""

    def test_ip_display_zero(self) -> None:
        """0 outs -> '0.0'"""
        assert ip_display(0) == "0.0"

    def test_ip_display_one_out(self) -> None:
        """1 out (0.1 IP) -> '0.1'"""
        assert ip_display(1) == "0.1"

    def test_ip_display_three_outs(self) -> None:
        """3 outs (1.0 IP) -> '1.0'"""
        assert ip_display(3) == "1.0"

    def test_ip_display_nine_outs(self) -> None:
        """9 outs (3.0 IP) -> '3.0'"""
        assert ip_display(9) == "3.0"

    def test_ip_display_twenty_outs(self) -> None:
        """20 outs (6.2 IP) -> '6.2'"""
        assert ip_display(20) == "6.2"

    def test_ip_display_none(self) -> None:
        """None -> '-'"""
        assert ip_display(None) == "-"

    def test_ip_display_returns_string(self) -> None:
        """Return type is always str."""
        assert isinstance(ip_display(6), str)
        assert isinstance(ip_display(None), str)


class TestFormatAvg:
    """Tests for format_avg helper (AC-8)."""

    def test_format_avg_one_third(self) -> None:
        """(1, 3) -> '.333'"""
        assert format_avg(1, 3) == ".333"

    def test_format_avg_zero_denom(self) -> None:
        """(0, 0) -> '-' (zero denominator)"""
        assert format_avg(0, 0) == "-"

    def test_format_avg_perfect(self) -> None:
        """(3, 3) -> '1.000'"""
        assert format_avg(3, 3) == "1.000"

    def test_format_avg_zero_numerator(self) -> None:
        """(0, 4) -> '.000'"""
        assert format_avg(0, 4) == ".000"

    def test_format_avg_none_denom(self) -> None:
        """None denominator -> '-'"""
        assert format_avg(5, None) == "-"

    def test_format_avg_returns_string(self) -> None:
        """Return type is always str."""
        assert isinstance(format_avg(2, 6), str)
        assert isinstance(format_avg(0, 0), str)


class TestFormatDate:
    """Tests for format_date filter."""

    def test_format_date_march(self) -> None:
        """2026-03-04 -> 'Mar 4'"""
        assert format_date("2026-03-04") == "Mar 4"

    def test_format_date_january(self) -> None:
        """2026-01-15 -> 'Jan 15'"""
        assert format_date("2026-01-15") == "Jan 15"

    def test_format_date_single_digit_day(self) -> None:
        """Day without leading zero: 2026-02-01 -> 'Feb 1'"""
        assert format_date("2026-02-01") == "Feb 1"

    def test_format_date_double_digit_day(self) -> None:
        """Day with two digits: 2026-11-28 -> 'Nov 28'"""
        assert format_date("2026-11-28") == "Nov 28"

    def test_format_date_none(self) -> None:
        """None -> '-'"""
        assert format_date(None) == "-"

    def test_format_date_empty_string(self) -> None:
        """Empty string -> '-'"""
        assert format_date("") == "-"

    def test_format_date_invalid_format(self) -> None:
        """Unparseable string -> '-'"""
        assert format_date("not-a-date") == "-"

    def test_format_date_returns_string(self) -> None:
        """Return type is always str."""
        assert isinstance(format_date("2026-03-04"), str)
        assert isinstance(format_date(None), str)
