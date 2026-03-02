# synthetic-test-data
"""Tests for the HTTP session factory."""

from __future__ import annotations

import logging
import time

import httpx
import respx

from src.http.headers import BROWSER_HEADERS
from src.http.session import create_session


class TestBrowserHeaders:
    """Verify the session sends all required browser headers."""

    @respx.mock
    def test_all_browser_headers_present(self) -> None:
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
