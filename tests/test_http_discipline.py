# synthetic-test-data
"""Integration tests for the HTTP discipline contract.

These tests verify the complete HTTP discipline contract end-to-end:
correct headers on every request, auth tokens never appearing in logs,
rate limiting enforcement with jitter variance across a realistic
multi-request session, and cookie persistence.

Unlike the unit tests in test_http_session.py (which test features in
isolation), these tests exercise the session factory in realistic
multi-request workflows on a single session instance.
"""

from __future__ import annotations

import logging
import time

import httpx
import pytest
import respx

from src.http.headers import BROWSER_HEADERS
from src.http.session import create_session


class TestHeaderDiscipline:
    """AC-1: All ten required browser headers sent with correct values."""

    @respx.mock
    def test_all_ten_headers_present_with_correct_values(self) -> None:
        """Every request from create_session() carries all 10 BROWSER_HEADERS."""
        route = respx.get("https://gc.example.com/api/teams").mock(
            return_value=httpx.Response(200, json={"teams": []})
        )
        session = create_session(min_delay_ms=0, jitter_ms=0)
        session.get("https://gc.example.com/api/teams")

        request = route.calls.last.request
        for key, value in BROWSER_HEADERS.items():
            actual = request.headers.get(key.lower())
            assert actual is not None, f"Missing required header: {key}"
            assert actual == value, (
                f"Header {key}: expected {value!r}, got {actual!r}"
            )

    @respx.mock
    def test_headers_survive_auth_injection(self) -> None:
        """Adding an Authorization header does not clobber browser headers."""
        route = respx.get("https://gc.example.com/api/stats").mock(
            return_value=httpx.Response(200, json={})
        )
        session = create_session(min_delay_ms=0, jitter_ms=0)
        session.headers["Authorization"] = "Bearer my-secret-token"
        session.get("https://gc.example.com/api/stats")

        request = route.calls.last.request
        # All 10 browser headers still present after auth injection
        for key, value in BROWSER_HEADERS.items():
            actual = request.headers.get(key.lower())
            assert actual == value, (
                f"Header {key} corrupted after auth injection: {actual!r}"
            )
        # Auth header also present
        assert request.headers["authorization"] == "Bearer my-secret-token"

    @respx.mock
    def test_headers_persist_across_multiple_requests(self) -> None:
        """Headers remain correct on the 5th request, not just the 1st."""
        routes = [
            respx.get(f"https://gc.example.com/api/r{i}").mock(
                return_value=httpx.Response(200)
            )
            for i in range(5)
        ]
        session = create_session(min_delay_ms=0, jitter_ms=0)
        for i in range(5):
            session.get(f"https://gc.example.com/api/r{i}")

        last_request = routes[-1].calls.last.request
        for key, value in BROWSER_HEADERS.items():
            assert last_request.headers.get(key.lower()) == value


class TestLogSafety:
    """AC-2: Auth token never appears in any log record at any level."""

    @respx.mock
    def test_bearer_token_never_in_log_messages(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No log message contains the token, 'Bearer', or 'Cookie'."""
        respx.get("https://gc.example.com/api/secret").mock(
            return_value=httpx.Response(200, json={"private": True})
        )
        with caplog.at_level(logging.DEBUG):
            session = create_session(min_delay_ms=0, jitter_ms=0)
            session.headers["Authorization"] = "Bearer test-token-abc"
            session.get("https://gc.example.com/api/secret")

        for record in caplog.records:
            full_message = record.getMessage()
            assert "test-token-abc" not in full_message, (
                f"Token leaked in log: {full_message!r}"
            )
            assert "Bearer" not in full_message, (
                f"'Bearer' found in log: {full_message!r}"
            )
            assert "Cookie" not in full_message, (
                f"'Cookie' found in log: {full_message!r}"
            )

    @respx.mock
    def test_token_not_in_log_record_attributes(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Token does not leak via record attributes (args, exc_text, etc.)."""
        respx.get("https://gc.example.com/api/data").mock(
            return_value=httpx.Response(200)
        )
        with caplog.at_level(logging.DEBUG):
            session = create_session(min_delay_ms=0, jitter_ms=0)
            session.headers["Authorization"] = "Bearer test-token-abc"
            session.get("https://gc.example.com/api/data")

        for record in caplog.records:
            record_str = str(vars(record))
            assert "test-token-abc" not in record_str, (
                f"Token leaked in log record attributes: {record_str!r}"
            )


class TestRateLimitingIntegration:
    """AC-3: Ten sequential requests on one session enforce delay and show jitter."""

    @respx.mock
    def test_no_gap_shorter_than_minimum_delay(self) -> None:
        """Every inter-request gap >= min_delay_ms (200ms)."""
        for i in range(10):
            respx.get(f"https://gc.example.com/api/item/{i}").mock(
                return_value=httpx.Response(200, json={"id": i})
            )

        session = create_session(min_delay_ms=200, jitter_ms=100)
        timestamps: list[float] = []
        for i in range(10):
            session.get(f"https://gc.example.com/api/item/{i}")
            timestamps.append(time.perf_counter())

        gaps = [
            timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)
        ]
        for idx, gap in enumerate(gaps):
            assert gap >= 0.195, (
                f"Gap {idx} was {gap * 1000:.0f}ms, below 200ms minimum"
            )

    @respx.mock
    def test_not_all_gaps_identical(self) -> None:
        """Jitter produces variance -- not all gaps are the same."""
        for i in range(10):
            respx.get(f"https://gc.example.com/api/jitter/{i}").mock(
                return_value=httpx.Response(200, json={"id": i})
            )

        session = create_session(min_delay_ms=200, jitter_ms=100)
        timestamps: list[float] = []
        for i in range(10):
            session.get(f"https://gc.example.com/api/jitter/{i}")
            timestamps.append(time.perf_counter())

        gaps = [
            timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)
        ]
        rounded = [round(g, 2) for g in gaps]
        assert len(set(rounded)) > 1, (
            f"All gaps identical (no jitter): {rounded}"
        )


class TestCookiePersistence:
    """AC-4: Set-Cookie from request 1 persists as Cookie on request 2."""

    @respx.mock
    def test_gc_auth_cookie_persisted(self) -> None:
        """gc_auth cookie set by server on request 1 is sent on request 2."""
        respx.get("https://gc.example.com/api/auth").mock(
            return_value=httpx.Response(
                200,
                headers={"Set-Cookie": "gc_auth=xyz; Path=/"},
            )
        )
        route2 = respx.get("https://gc.example.com/api/teams").mock(
            return_value=httpx.Response(200, json={"teams": []})
        )

        session = create_session(min_delay_ms=0, jitter_ms=0)
        session.get("https://gc.example.com/api/auth")
        session.get("https://gc.example.com/api/teams")

        cookie_header = route2.calls.last.request.headers.get("cookie", "")
        assert "gc_auth=xyz" in cookie_header, (
            f"Expected gc_auth=xyz in Cookie header, got: {cookie_header!r}"
        )


class TestNormalResponseHandling:
    """AC-5: Session does not interfere with normal 200 response handling."""

    @respx.mock
    def test_200_response_passes_through(self) -> None:
        """A 200 response with JSON body is returned unmodified."""
        respx.get("https://gc.example.com/api/stats").mock(
            return_value=httpx.Response(200, json={"batting_avg": 0.312})
        )

        session = create_session(min_delay_ms=0, jitter_ms=0)
        response = session.get("https://gc.example.com/api/stats")

        assert response.status_code == 200
        assert response.json() == {"batting_avg": 0.312}


# AC-6: SKIP -- E-005-03 (GameChanger client retrofit) is not yet complete.
# When E-005-03 is DONE, add a test here that verifies GameChangerClient
# sends both the Authorization header AND all required browser headers
# on a single request. See E-005-04.md AC-6 for the full specification.
