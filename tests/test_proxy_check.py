# synthetic-test-data
"""Unit tests for src/http/proxy_check.py.

All HTTP calls are mocked -- no real network requests are made.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from src.http.proxy_check import (
    ProxyCheckOutcome,
    ProxyCheckResult,
    check_proxy_routing,
    get_direct_ip,
)

_REAL_IP = "1.2.3.4"
_PROXY_IP = "5.6.7.8"
_IP_ECHO_URL = "https://api.ipify.org?format=json"

_PROXY_ENV = {
    "PROXY_ENABLED": "true",
    "PROXY_URL_WEB": "http://user:pass@proxy.example.com:1234",
    "PROXY_URL_MOBILE": "http://user:pass@proxy.example.com:5678",
}

_NO_PROXY_ENV: dict[str, str] = {}


# ---------------------------------------------------------------------------
# get_direct_ip()
# ---------------------------------------------------------------------------


class TestGetDirectIp:
    @respx.mock
    def test_returns_ip_on_success(self) -> None:
        """Returns the IP string from the echo service."""
        respx.get(_IP_ECHO_URL).mock(
            return_value=httpx.Response(200, json={"ip": _REAL_IP})
        )
        result = get_direct_ip()
        assert result == _REAL_IP

    @respx.mock
    def test_returns_none_on_network_error(self) -> None:
        """Returns None when the request fails."""
        respx.get(_IP_ECHO_URL).mock(side_effect=httpx.ConnectError("refused"))
        result = get_direct_ip()
        assert result is None

    @respx.mock
    def test_returns_none_on_http_error(self) -> None:
        """Returns None on non-200 HTTP response."""
        respx.get(_IP_ECHO_URL).mock(return_value=httpx.Response(503))
        result = get_direct_ip()
        assert result is None


# ---------------------------------------------------------------------------
# check_proxy_routing() -- NOT_CONFIGURED outcomes
# ---------------------------------------------------------------------------


class TestProxyNotConfigured:
    def test_returns_not_configured_when_proxy_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-3: Returns NOT_CONFIGURED when PROXY_ENABLED is absent."""
        monkeypatch.setattr("src.http.proxy_check.dotenv_values", lambda *_a, **_kw: _NO_PROXY_ENV)
        result = check_proxy_routing("web", _REAL_IP)
        assert result.outcome == ProxyCheckOutcome.NOT_CONFIGURED

    def test_returns_not_configured_when_proxy_enabled_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-3: Returns NOT_CONFIGURED when PROXY_ENABLED=false."""
        monkeypatch.setattr(
            "src.http.proxy_check.dotenv_values",
            lambda *_a, **_kw: {"PROXY_ENABLED": "false", "PROXY_URL_WEB": "http://proxy:1234"},
        )
        result = check_proxy_routing("web", _REAL_IP)
        assert result.outcome == ProxyCheckOutcome.NOT_CONFIGURED

    def test_returns_not_configured_when_url_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-4: Returns NOT_CONFIGURED when PROXY_ENABLED=true but URL is absent."""
        monkeypatch.setattr(
            "src.http.proxy_check.dotenv_values",
            lambda *_a, **_kw: {"PROXY_ENABLED": "true"},
        )
        result = check_proxy_routing("web", _REAL_IP)
        assert result.outcome == ProxyCheckOutcome.NOT_CONFIGURED


# ---------------------------------------------------------------------------
# check_proxy_routing() -- PASS outcome
# ---------------------------------------------------------------------------


class TestProxyPass:
    @respx.mock
    def test_pass_when_proxy_ip_differs_from_direct(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-1, AC-2: PASS when proxy IP differs from direct IP."""
        monkeypatch.setattr("src.http.proxy_check.dotenv_values", lambda *_a, **_kw: _PROXY_ENV)
        respx.get(_IP_ECHO_URL).mock(
            return_value=httpx.Response(200, json={"ip": _PROXY_IP})
        )
        result = check_proxy_routing("web", _REAL_IP)
        assert result.outcome == ProxyCheckOutcome.PASS
        assert result.proxy_ip == _PROXY_IP
        assert result.direct_ip == _REAL_IP

    @respx.mock
    def test_pass_for_mobile_profile(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-1: PASS for mobile profile when proxy IP differs."""
        monkeypatch.setattr("src.http.proxy_check.dotenv_values", lambda *_a, **_kw: _PROXY_ENV)
        respx.get(_IP_ECHO_URL).mock(
            return_value=httpx.Response(200, json={"ip": _PROXY_IP})
        )
        result = check_proxy_routing("mobile", _REAL_IP)
        assert result.outcome == ProxyCheckOutcome.PASS
        assert result.profile == "mobile"


# ---------------------------------------------------------------------------
# check_proxy_routing() -- FAIL outcome
# ---------------------------------------------------------------------------


class TestProxyFail:
    @respx.mock
    def test_fail_when_proxy_ip_matches_direct(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-2: FAIL when proxy IP matches direct IP (not routing through proxy)."""
        monkeypatch.setattr("src.http.proxy_check.dotenv_values", lambda *_a, **_kw: _PROXY_ENV)
        respx.get(_IP_ECHO_URL).mock(
            return_value=httpx.Response(200, json={"ip": _REAL_IP})
        )
        result = check_proxy_routing("web", _REAL_IP)
        assert result.outcome == ProxyCheckOutcome.FAIL
        assert result.proxy_ip == _REAL_IP
        assert result.direct_ip == _REAL_IP


# ---------------------------------------------------------------------------
# check_proxy_routing() -- ERROR outcome
# ---------------------------------------------------------------------------


class TestProxyError:
    @respx.mock
    def test_error_on_connection_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-7: ERROR with descriptive message when proxy connection fails."""
        monkeypatch.setattr("src.http.proxy_check.dotenv_values", lambda *_a, **_kw: _PROXY_ENV)
        respx.get(_IP_ECHO_URL).mock(side_effect=httpx.ConnectError("connection refused"))
        result = check_proxy_routing("web", _REAL_IP)
        assert result.outcome == ProxyCheckOutcome.ERROR
        assert result.error is not None
        assert len(result.error) > 0

    @respx.mock
    def test_error_on_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-7: ERROR when proxy request times out."""
        monkeypatch.setattr("src.http.proxy_check.dotenv_values", lambda *_a, **_kw: _PROXY_ENV)
        respx.get(_IP_ECHO_URL).mock(side_effect=httpx.TimeoutException("timeout"))
        result = check_proxy_routing("web", _REAL_IP)
        assert result.outcome == ProxyCheckOutcome.ERROR

    @respx.mock
    def test_error_when_proxy_returns_empty_ip(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ERROR when proxy request succeeds but returns no IP in the body."""
        monkeypatch.setattr("src.http.proxy_check.dotenv_values", lambda *_a, **_kw: _PROXY_ENV)
        respx.get(_IP_ECHO_URL).mock(
            return_value=httpx.Response(200, json={})
        )
        result = check_proxy_routing("web", _REAL_IP)
        assert result.outcome == ProxyCheckOutcome.ERROR


# ---------------------------------------------------------------------------
# check_proxy_routing() -- PASS_UNVERIFIED outcome
# ---------------------------------------------------------------------------


class TestProxyPassUnverified:
    @respx.mock
    def test_pass_unverified_when_direct_ip_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-2: PASS-UNVERIFIED when proxy succeeds but direct baseline is None."""
        monkeypatch.setattr("src.http.proxy_check.dotenv_values", lambda *_a, **_kw: _PROXY_ENV)
        respx.get(_IP_ECHO_URL).mock(
            return_value=httpx.Response(200, json={"ip": _PROXY_IP})
        )
        result = check_proxy_routing("web", None)
        assert result.outcome == ProxyCheckOutcome.PASS_UNVERIFIED
        assert result.proxy_ip == _PROXY_IP
        assert result.direct_ip is None


# ---------------------------------------------------------------------------
# Log safety -- proxy URL must never appear in logs
# ---------------------------------------------------------------------------


class TestProxyCheckLogSafety:
    @respx.mock
    def test_proxy_url_not_logged_on_pass(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """AC-6: Proxy URL (with credentials) must not appear in any log output."""
        import logging

        monkeypatch.setattr("src.http.proxy_check.dotenv_values", lambda *_a, **_kw: _PROXY_ENV)
        respx.get(_IP_ECHO_URL).mock(
            return_value=httpx.Response(200, json={"ip": _PROXY_IP})
        )
        with caplog.at_level(logging.DEBUG):
            check_proxy_routing("web", _REAL_IP)

        for record in caplog.records:
            msg = record.getMessage()
            assert "user:pass" not in msg, f"Proxy credentials leaked into log: {msg!r}"
            assert "proxy.example.com" not in msg or "PROXY_URL" in msg, (
                f"Proxy URL host leaked into log: {msg!r}"
            )

    @respx.mock
    def test_proxy_url_not_logged_on_error(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """AC-6: Proxy URL must not appear in log output on network error."""
        import logging

        monkeypatch.setattr("src.http.proxy_check.dotenv_values", lambda *_a, **_kw: _PROXY_ENV)
        respx.get(_IP_ECHO_URL).mock(side_effect=httpx.ConnectError("refused"))
        with caplog.at_level(logging.DEBUG):
            check_proxy_routing("web", _REAL_IP)

        for record in caplog.records:
            msg = record.getMessage()
            assert "user:pass" not in msg, f"Proxy credentials leaked into log: {msg!r}"


# ---------------------------------------------------------------------------
# AC-6 (E-083): proxy check does NOT use sticky session IDs
# ---------------------------------------------------------------------------


class TestProxyCheckNoStickySession:
    def test_check_proxy_routing_does_not_pass_session_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-6: check_proxy_routing() calls resolve_proxy_from_dict() without session_id.

        The diagnostic tool uses rotating IPs -- no session ID should be injected.
        """
        from src.http import session as session_module

        captured_kwargs: dict = {}
        original_resolve = session_module.resolve_proxy_from_dict

        def capturing_resolve(
            env_dict: dict, profile: str, session_id: str | None = None
        ) -> str | None:
            captured_kwargs["session_id"] = session_id
            return original_resolve(env_dict, profile, session_id=session_id)

        monkeypatch.setattr(
            "src.http.proxy_check.resolve_proxy_from_dict", capturing_resolve
        )
        monkeypatch.setattr("src.http.proxy_check.dotenv_values", lambda *_a, **_kw: _PROXY_ENV)

        check_proxy_routing("web", _REAL_IP)

        assert captured_kwargs.get("session_id") is None, (
            f"proxy check passed session_id={captured_kwargs.get('session_id')!r} "
            "but should use rotating IPs (no session ID)"
        )


# ---------------------------------------------------------------------------
# AC-7: __file__-relative .env path resolution
# ---------------------------------------------------------------------------


def test_proxy_check_env_path_resolves_to_repo_root() -> None:
    """AC-7: _ENV_PATH in proxy_check.py resolves to <repo-root>/.env regardless of cwd."""
    from src.http.proxy_check import _ENV_PATH

    assert _ENV_PATH.name == ".env"
    repo_root = _ENV_PATH.parent
    assert (repo_root / "pyproject.toml").exists(), (
        f"Expected repo root at {repo_root!r} but pyproject.toml not found there"
    )


def test_proxy_check_env_path_is_absolute() -> None:
    """AC-7: _ENV_PATH in proxy_check.py is an absolute path (not cwd-relative)."""
    from src.http.proxy_check import _ENV_PATH

    assert _ENV_PATH.is_absolute()
