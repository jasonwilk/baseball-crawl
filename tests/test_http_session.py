# synthetic-test-data
"""Tests for the HTTP session factory."""

from __future__ import annotations

import logging
import time

import httpx
import pytest
import respx

from unittest.mock import patch

from src.http.headers import BROWSER_HEADERS, MOBILE_HEADERS
from src.http.session import create_session, get_proxy_config


class TestHeaderProfiles:
    """Verify the session sends the correct headers for each profile."""

    @respx.mock
    def test_default_profile_uses_browser_headers(self) -> None:
        route = respx.get("https://example.com/test").mock(
            return_value=httpx.Response(200, json={})
        )
        session = create_session(min_delay_ms=0, jitter_ms=0)
        session.get("https://example.com/test")
        request = route.calls.last.request
        for key, value in BROWSER_HEADERS.items():
            assert request.headers[key.lower()] == value, (
                f"Header {key} expected {value!r}, got {request.headers.get(key.lower())!r}"
            )

    @respx.mock
    def test_web_profile_uses_browser_headers(self) -> None:
        route = respx.get("https://example.com/test").mock(
            return_value=httpx.Response(200, json={})
        )
        session = create_session(min_delay_ms=0, jitter_ms=0, profile="web")
        session.get("https://example.com/test")
        request = route.calls.last.request
        for key, value in BROWSER_HEADERS.items():
            assert request.headers[key.lower()] == value, (
                f"Header {key} expected {value!r}, got {request.headers.get(key.lower())!r}"
            )

    @respx.mock
    def test_mobile_profile_uses_mobile_headers(self) -> None:
        route = respx.get("https://example.com/test").mock(
            return_value=httpx.Response(200, json={})
        )
        session = create_session(min_delay_ms=0, jitter_ms=0, profile="mobile")
        session.get("https://example.com/test")
        request = route.calls.last.request
        for key, value in MOBILE_HEADERS.items():
            assert request.headers[key.lower()] == value, (
                f"Header {key} expected {value!r}, got {request.headers.get(key.lower())!r}"
            )

    @respx.mock
    def test_web_profile_user_agent_is_chrome_145(self) -> None:
        route = respx.get("https://example.com/test").mock(
            return_value=httpx.Response(200, json={})
        )
        session = create_session(min_delay_ms=0, jitter_ms=0, profile="web")
        session.get("https://example.com/test")
        ua = route.calls.last.request.headers["user-agent"]
        assert "Chrome/145.0.0.0" in ua

    @respx.mock
    def test_mobile_profile_user_agent_is_odyssey(self) -> None:
        route = respx.get("https://example.com/test").mock(
            return_value=httpx.Response(200, json={})
        )
        session = create_session(min_delay_ms=0, jitter_ms=0, profile="mobile")
        session.get("https://example.com/test")
        ua = route.calls.last.request.headers["user-agent"]
        assert "Odyssey/2026.7.0" in ua

    def test_invalid_profile_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown header profile"):
            create_session(min_delay_ms=0, jitter_ms=0, profile="invalid")  # type: ignore[arg-type]


class TestRateLimiting:
    """Verify delay and jitter between sequential requests."""

    @respx.mock
    def test_minimum_delay_enforced(self) -> None:
        respx.get("https://example.com/a").mock(return_value=httpx.Response(200))
        respx.get("https://example.com/b").mock(return_value=httpx.Response(200))
        session = create_session(min_delay_ms=200, jitter_ms=0)
        start = time.perf_counter()
        session.get("https://example.com/a")
        session.get("https://example.com/b")
        elapsed = time.perf_counter() - start
        # Two requests, each followed by a 200ms sleep = ~400ms total minimum
        assert elapsed >= 0.4, f"Expected >= 400ms, got {elapsed*1000:.0f}ms"

    @respx.mock
    def test_jitter_applied(self) -> None:
        """Run multiple request pairs and confirm not all gaps are identical."""
        gaps: list[float] = []
        for _ in range(10):
            respx.get("https://example.com/j").mock(return_value=httpx.Response(200))
            session = create_session(min_delay_ms=50, jitter_ms=50)
            t0 = time.perf_counter()
            session.get("https://example.com/j")
            gap = time.perf_counter() - t0
            gaps.append(gap)
        # Jitter means not all gaps are the same (when rounded to 10ms)
        rounded = [round(g, 2) for g in gaps]
        assert len(set(rounded)) > 1, f"All gaps identical (no jitter): {rounded}"


class TestCookieJar:
    """Verify cookie persistence across requests."""

    @respx.mock
    def test_cookie_persisted(self) -> None:
        respx.get("https://example.com/login").mock(
            return_value=httpx.Response(
                200,
                headers={"Set-Cookie": "gc_session=abc123; Path=/"},
            )
        )
        route2 = respx.get("https://example.com/data").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        session = create_session(min_delay_ms=0, jitter_ms=0)
        session.get("https://example.com/login")
        session.get("https://example.com/data")
        cookie_header = route2.calls.last.request.headers.get("cookie", "")
        assert "gc_session=abc123" in cookie_header


class TestLogSafety:
    """Verify no credentials leak into log output."""

    @respx.mock
    def test_no_auth_in_logs(self, caplog: object) -> None:
        respx.get("https://example.com/secret").mock(
            return_value=httpx.Response(200)
        )
        with caplog.at_level(logging.DEBUG):  # type: ignore[attr-defined]
            session = create_session(min_delay_ms=0, jitter_ms=0)
            session.headers["Authorization"] = "Bearer test-token-xyz"
            session.get("https://example.com/secret")
        for record in caplog.records:  # type: ignore[attr-defined]
            msg = record.getMessage()
            assert "test-token-xyz" not in msg
            assert "Authorization" not in msg
            assert "Bearer" not in msg
            assert "Cookie" not in msg


class TestContextManager:
    """Verify context manager protocol works."""

    @respx.mock
    def test_context_manager(self) -> None:
        respx.get("https://example.com/cm").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        with create_session(min_delay_ms=0, jitter_ms=0) as session:
            response = session.get("https://example.com/cm")
            assert response.status_code == 200


class TestNormalResponse:
    """Verify the session does not interfere with normal response handling."""

    @respx.mock
    def test_returns_200(self) -> None:
        respx.get("https://example.com/ok").mock(
            return_value=httpx.Response(200, json={"data": 42})
        )
        session = create_session(min_delay_ms=0, jitter_ms=0)
        response = session.get("https://example.com/ok")
        assert response.status_code == 200
        assert response.json() == {"data": 42}


class TestProxyExplicitArg:
    """AC-1: explicit proxy_url kwarg is forwarded to httpx.Client."""

    def test_explicit_proxy_web_profile(self) -> None:
        """create_session(profile='web', proxy_url='http://proxy:7777') configures proxy."""
        with patch("src.http.session.httpx.Client") as mock_client:
            create_session(min_delay_ms=0, jitter_ms=0, profile="web", proxy_url="http://proxy:7777")
        _, kwargs = mock_client.call_args
        assert kwargs.get("proxy") == "http://proxy:7777"

    def test_explicit_proxy_mobile_profile(self) -> None:
        """create_session(profile='mobile', proxy_url='http://proxy:7777') configures proxy."""
        with patch("src.http.session.httpx.Client") as mock_client:
            create_session(min_delay_ms=0, jitter_ms=0, profile="mobile", proxy_url="http://proxy:7777")
        _, kwargs = mock_client.call_args
        assert kwargs.get("proxy") == "http://proxy:7777"

    def test_explicit_none_disables_proxy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """proxy_url=None disables proxy even when env vars are set."""
        monkeypatch.setenv("PROXY_ENABLED", "true")
        monkeypatch.setenv("PROXY_URL_WEB", "http://proxy.example.com:9000")
        with patch("src.http.session.httpx.Client") as mock_client:
            create_session(min_delay_ms=0, jitter_ms=0, profile="web", proxy_url=None)
        _, kwargs = mock_client.call_args
        assert kwargs.get("proxy") is None


class TestProxyDisabledByDefault:
    """AC-2: no proxy when PROXY_ENABLED is unset or false."""

    def test_proxy_disabled_when_env_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No proxy configured when PROXY_ENABLED is not set."""
        monkeypatch.delenv("PROXY_ENABLED", raising=False)
        monkeypatch.delenv("PROXY_URL_WEB", raising=False)
        with patch("src.http.session.httpx.Client") as mock_client:
            create_session(min_delay_ms=0, jitter_ms=0, profile="web")
        _, kwargs = mock_client.call_args
        assert kwargs.get("proxy") is None

    def test_proxy_disabled_when_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No proxy configured when PROXY_ENABLED=false."""
        monkeypatch.setenv("PROXY_ENABLED", "false")
        monkeypatch.setenv("PROXY_URL_WEB", "http://proxy.example.com:9000")
        with patch("src.http.session.httpx.Client") as mock_client:
            create_session(min_delay_ms=0, jitter_ms=0, profile="web")
        _, kwargs = mock_client.call_args
        assert kwargs.get("proxy") is None


class TestProxyAutoConfigFromEnv:
    """AC-3: auto-configure proxy from env vars when no explicit proxy_url given."""

    def test_web_profile_reads_proxy_url_web(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Web profile auto-reads PROXY_URL_WEB when PROXY_ENABLED=true."""
        monkeypatch.setenv("PROXY_ENABLED", "true")
        monkeypatch.setenv("PROXY_URL_WEB", "http://web-proxy.example.com:8080")
        monkeypatch.delenv("PROXY_URL_MOBILE", raising=False)
        with patch("src.http.session.httpx.Client") as mock_client:
            create_session(min_delay_ms=0, jitter_ms=0, profile="web")
        _, kwargs = mock_client.call_args
        assert kwargs.get("proxy") == "http://web-proxy.example.com:8080"

    def test_mobile_profile_reads_proxy_url_mobile(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Mobile profile auto-reads PROXY_URL_MOBILE when PROXY_ENABLED=true."""
        monkeypatch.setenv("PROXY_ENABLED", "true")
        monkeypatch.delenv("PROXY_URL_WEB", raising=False)
        monkeypatch.setenv("PROXY_URL_MOBILE", "http://mobile-proxy.example.com:8081")
        with patch("src.http.session.httpx.Client") as mock_client:
            create_session(min_delay_ms=0, jitter_ms=0, profile="mobile")
        _, kwargs = mock_client.call_args
        assert kwargs.get("proxy") == "http://mobile-proxy.example.com:8081"


class TestGetProxyConfig:
    """AC-4: get_proxy_config() reads PROXY_ENABLED and PROXY_URL_{PROFILE}."""

    def test_returns_url_when_enabled_and_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PROXY_ENABLED", "true")
        monkeypatch.setenv("PROXY_URL_WEB", "http://proxy.example.com:9000")
        assert get_proxy_config("web") == "http://proxy.example.com:9000"

    def test_returns_none_when_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PROXY_ENABLED", "false")
        monkeypatch.setenv("PROXY_URL_WEB", "http://proxy.example.com:9000")
        assert get_proxy_config("web") is None

    def test_returns_none_when_proxy_enabled_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PROXY_ENABLED", raising=False)
        monkeypatch.setenv("PROXY_URL_WEB", "http://proxy.example.com:9000")
        assert get_proxy_config("web") is None

    def test_mobile_reads_proxy_url_mobile(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PROXY_ENABLED", "true")
        monkeypatch.setenv("PROXY_URL_MOBILE", "http://mobile-proxy.example.com:9001")
        assert get_proxy_config("mobile") == "http://mobile-proxy.example.com:9001"


class TestProxyGracefulDegradation:
    """AC-5: PROXY_ENABLED=true but URL empty/unset logs WARNING and returns None."""

    def test_warning_logged_when_url_unset(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("PROXY_ENABLED", "true")
        monkeypatch.delenv("PROXY_URL_WEB", raising=False)
        with caplog.at_level(logging.WARNING):
            result = get_proxy_config("web")
        assert result is None
        warning_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("PROXY_URL_WEB" in msg for msg in warning_messages), (
            f"Expected WARNING mentioning PROXY_URL_WEB, got: {warning_messages}"
        )

    def test_warning_logged_when_url_empty(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("PROXY_ENABLED", "true")
        monkeypatch.setenv("PROXY_URL_WEB", "")
        with caplog.at_level(logging.WARNING):
            result = get_proxy_config("web")
        assert result is None
        warning_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("PROXY_URL_WEB" in msg for msg in warning_messages)

    def test_mobile_warning_names_correct_env_var(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("PROXY_ENABLED", "true")
        monkeypatch.delenv("PROXY_URL_MOBILE", raising=False)
        with caplog.at_level(logging.WARNING):
            result = get_proxy_config("mobile")
        assert result is None
        warning_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("PROXY_URL_MOBILE" in msg for msg in warning_messages)


class TestProxyLogSafety:
    """AC-6: Proxy URL values never appear in any log message."""

    def test_proxy_url_not_logged_on_success(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Known proxy URL must not appear in log output."""
        secret_url = "http://user:s3cr3t@brd.superproxy.io:33335"
        monkeypatch.setenv("PROXY_ENABLED", "true")
        monkeypatch.setenv("PROXY_URL_WEB", secret_url)
        with caplog.at_level(logging.DEBUG):
            result = get_proxy_config("web")
        assert result == secret_url
        for record in caplog.records:
            msg = record.getMessage()
            assert secret_url not in msg, f"Proxy URL leaked into log: {msg!r}"
            assert "s3cr3t" not in msg, f"Proxy credentials leaked into log: {msg!r}"

    def test_proxy_url_not_logged_on_invalid_scheme(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Malformed proxy URL must not appear in the warning log message."""
        bad_url = "socks5://user:hunter2@proxy.example.com:1080"
        monkeypatch.setenv("PROXY_ENABLED", "true")
        monkeypatch.setenv("PROXY_URL_WEB", bad_url)
        with caplog.at_level(logging.WARNING):
            result = get_proxy_config("web")
        assert result is None
        for record in caplog.records:
            msg = record.getMessage()
            assert bad_url not in msg, f"Malformed URL leaked into log: {msg!r}"
            assert "hunter2" not in msg, f"Credentials leaked into log: {msg!r}"


class TestTrustEnvDisabled:
    """Verify trust_env=False is passed to httpx.Client to ignore system proxy vars."""

    def test_trust_env_false(self) -> None:
        with patch("src.http.session.httpx.Client") as mock_client:
            create_session(min_delay_ms=0, jitter_ms=0)
        _, kwargs = mock_client.call_args
        assert kwargs.get("trust_env") is False


class TestProxyProfileIsolation:
    """AC-10: Each profile gets only its own proxy URL, never the other's."""

    def test_web_session_uses_web_proxy_not_mobile(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PROXY_ENABLED", "true")
        monkeypatch.setenv("PROXY_URL_WEB", "http://web-proxy.example.com:8080")
        monkeypatch.setenv("PROXY_URL_MOBILE", "http://mobile-proxy.example.com:8081")
        with patch("src.http.session.httpx.Client") as mock_client:
            create_session(min_delay_ms=0, jitter_ms=0, profile="web")
        _, kwargs = mock_client.call_args
        assert kwargs.get("proxy") == "http://web-proxy.example.com:8080"
        assert kwargs.get("proxy") != "http://mobile-proxy.example.com:8081"

    def test_mobile_session_uses_mobile_proxy_not_web(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PROXY_ENABLED", "true")
        monkeypatch.setenv("PROXY_URL_WEB", "http://web-proxy.example.com:8080")
        monkeypatch.setenv("PROXY_URL_MOBILE", "http://mobile-proxy.example.com:8081")
        with patch("src.http.session.httpx.Client") as mock_client:
            create_session(min_delay_ms=0, jitter_ms=0, profile="mobile")
        _, kwargs = mock_client.call_args
        assert kwargs.get("proxy") == "http://mobile-proxy.example.com:8081"
        assert kwargs.get("proxy") != "http://web-proxy.example.com:8080"


class TestProxyMalformedUrl:
    """AC-11: Malformed proxy URL (bad scheme) logs WARNING and returns None."""

    def test_socks_scheme_rejected(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("PROXY_ENABLED", "true")
        monkeypatch.setenv("PROXY_URL_WEB", "socks5://proxy.example.com:1080")
        with caplog.at_level(logging.WARNING):
            result = get_proxy_config("web")
        assert result is None
        warning_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("PROXY_URL_WEB" in msg for msg in warning_messages), (
            f"Expected WARNING mentioning PROXY_URL_WEB, got: {warning_messages}"
        )
        assert any("invalid scheme" in msg.lower() or "scheme" in msg.lower() for msg in warning_messages), (
            f"Expected WARNING mentioning scheme, got: {warning_messages}"
        )

    def test_no_scheme_rejected(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("PROXY_ENABLED", "true")
        monkeypatch.setenv("PROXY_URL_WEB", "proxy.example.com:8080")
        with caplog.at_level(logging.WARNING):
            result = get_proxy_config("web")
        assert result is None

    def test_https_scheme_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PROXY_ENABLED", "true")
        monkeypatch.setenv("PROXY_URL_WEB", "https://proxy.example.com:8443")
        result = get_proxy_config("web")
        assert result == "https://proxy.example.com:8443"

    def test_malformed_url_not_logged(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The invalid URL value itself must not appear in the log message."""
        bad_url = "ftp://user:secret@proxy.example.com:21"
        monkeypatch.setenv("PROXY_ENABLED", "true")
        monkeypatch.setenv("PROXY_URL_WEB", bad_url)
        with caplog.at_level(logging.WARNING):
            get_proxy_config("web")
        for record in caplog.records:
            msg = record.getMessage()
            assert bad_url not in msg
            assert "secret" not in msg
