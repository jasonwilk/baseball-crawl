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

from src.api.helpers import (  # noqa: E402
    format_avg,
    format_date,
    get_app_env,
    ip_display,
    is_production,
    validate_app_env,
)


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


class TestIsProduction:
    """Tests for is_production() -- the strict-normalized prod-detection seam (E-254-01)."""

    def test_true_when_app_env_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        assert is_production() is True

    def test_false_when_development(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "development")
        assert is_production() is False

    def test_false_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default (APP_ENV unset) is non-production."""
        monkeypatch.delenv("APP_ENV", raising=False)
        assert is_production() is False

    def test_false_for_other_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A recognized non-production value (staging) is non-production."""
        monkeypatch.setenv("APP_ENV", "staging")
        assert is_production() is False

    @pytest.mark.parametrize(
        "value", ["production", "Production", "PRODUCTION", " production ", "\tproduction\n"]
    )
    def test_true_for_casing_and_whitespace_variants(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        """AC-1: casing/whitespace variants of 'production' select production."""
        monkeypatch.setenv("APP_ENV", value)
        assert is_production() is True

    def test_false_when_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AC-1: set-but-empty APP_ENV is non-production (treated as unset)."""
        monkeypatch.setenv("APP_ENV", "")
        assert is_production() is False


class TestGetAppEnv:
    """Tests for get_app_env() -- the single APP_ENV normalizer (E-254-01)."""

    def test_strips_and_lowercases(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "  Production  ")
        assert get_app_env() == "production"

    def test_unset_is_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("APP_ENV", raising=False)
        assert get_app_env() == ""

    def test_empty_is_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "   ")
        assert get_app_env() == ""


class TestValidateAppEnv:
    """Tests for validate_app_env() -- the refuse-to-start startup guard (E-254-01 AC-2)."""

    @pytest.mark.parametrize(
        "value", ["production", "development", "dev", "test", "staging", "PRODUCTION", " staging "]
    )
    def test_recognized_values_do_not_raise(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        """AC-2: any recognized value (any casing/whitespace) passes."""
        monkeypatch.setenv("APP_ENV", value)
        validate_app_env()  # must not raise

    def test_unset_does_not_raise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AC-2: unset APP_ENV proceeds normally (dev posture, not unrecognized)."""
        monkeypatch.delenv("APP_ENV", raising=False)
        validate_app_env()  # must not raise

    def test_empty_does_not_raise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AC-2: set-but-empty APP_ENV proceeds normally (treated as unset)."""
        monkeypatch.setenv("APP_ENV", "   ")
        validate_app_env()  # must not raise

    @pytest.mark.parametrize("value", ["prod", "prd", "produciton", "live"])
    def test_unrecognized_raises_runtimeerror(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        """AC-2: a non-empty out-of-set value refuses to start (raises)."""
        monkeypatch.setenv("APP_ENV", value)
        with pytest.raises(RuntimeError, match="Unrecognized APP_ENV"):
            validate_app_env()

    def test_unrecognized_logs_critical(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """AC-2: the refuse-to-start path emits a CRITICAL-level log."""
        monkeypatch.setenv("APP_ENV", "prod")
        with caplog.at_level("CRITICAL", logger="src.api.helpers"):
            with pytest.raises(RuntimeError):
                validate_app_env()
        assert any(r.levelname == "CRITICAL" for r in caplog.records)


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
