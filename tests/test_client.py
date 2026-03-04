# synthetic-test-data
"""Unit tests for src/gamechanger/client.py.

All HTTP calls are mocked -- no real network requests are made.
Tests use min_delay_ms=0, jitter_ms=0 to eliminate rate-limiting sleeps.
Credentials are provided via monkeypatch of dotenv_values.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from src.gamechanger.client import (
    ConfigurationError,
    CredentialExpiredError,
    ForbiddenError,
    GameChangerAPIError,
    GameChangerClient,
    RateLimitError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_CREDENTIALS = {
    "GAMECHANGER_AUTH_TOKEN": "fake-jwt-token",
    "GAMECHANGER_DEVICE_ID": "abcdef1234567890abcdef1234567890",
    "GAMECHANGER_BASE_URL": "https://api.team-manager.gc.com",
    "GAMECHANGER_APP_NAME": "web",
}

_BASE_URL = "https://api.team-manager.gc.com"


def _make_client(monkeypatch: pytest.MonkeyPatch) -> GameChangerClient:
    """Return a GameChangerClient with fake credentials and zero delays."""
    monkeypatch.setattr(
        "src.gamechanger.client.dotenv_values",
        lambda: _FAKE_CREDENTIALS,
    )
    return GameChangerClient(min_delay_ms=0, jitter_ms=0)


# ---------------------------------------------------------------------------
# AC-1: Successful GET returns parsed JSON and logs at DEBUG level
# ---------------------------------------------------------------------------


@respx.mock
def test_get_returns_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful GET returns the parsed JSON body."""
    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(
        return_value=httpx.Response(200, json=[{"event_id": "123"}])
    )
    client = _make_client(monkeypatch)
    result = client.get(
        "/teams/abc/game-summaries",
        accept="application/vnd.gc.com.game_summary:list+json; version=0.1.0",
    )
    assert result == [{"event_id": "123"}]


@respx.mock
def test_get_logs_url_and_status_at_debug(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """GET logs request URL and response status at DEBUG level."""
    import logging

    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(
        return_value=httpx.Response(200, json=[])
    )
    client = _make_client(monkeypatch)
    with caplog.at_level(logging.DEBUG, logger="src.gamechanger.client"):
        client.get("/teams/abc/game-summaries")

    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "/teams/abc/game-summaries" in messages or "game-summaries" in messages


# ---------------------------------------------------------------------------
# AC-2: 401 and 403 raise CredentialExpiredError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status_code", [401, 403])
@respx.mock
def test_credential_expired_error_on_401_403(
    monkeypatch: pytest.MonkeyPatch, status_code: int
) -> None:
    """HTTP 401 and 403 raise CredentialExpiredError with required message content."""
    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(
        return_value=httpx.Response(status_code)
    )
    client = _make_client(monkeypatch)

    with pytest.raises(CredentialExpiredError) as exc_info:
        client.get("/teams/abc/game-summaries")

    msg = str(exc_info.value)
    assert "/teams/abc/game-summaries" in msg
    assert str(status_code) in msg
    assert "python scripts/refresh_credentials.py" in msg


# ---------------------------------------------------------------------------
# AC-1 (E-002-11): 401 raises CredentialExpiredError; 403 raises ForbiddenError
# ---------------------------------------------------------------------------


@respx.mock
def test_get_401_raises_credential_expired_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP 401 raises CredentialExpiredError (not ForbiddenError)."""
    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(
        return_value=httpx.Response(401)
    )
    client = _make_client(monkeypatch)
    with pytest.raises(CredentialExpiredError) as exc_info:
        client.get("/teams/abc/game-summaries")
    assert not isinstance(exc_info.value, ForbiddenError)


@respx.mock
def test_get_403_raises_forbidden_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP 403 raises ForbiddenError."""
    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(
        return_value=httpx.Response(403)
    )
    client = _make_client(monkeypatch)
    with pytest.raises(ForbiddenError):
        client.get("/teams/abc/game-summaries")


@respx.mock
def test_forbidden_error_is_subclass_of_credential_expired_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ForbiddenError is a subclass of CredentialExpiredError (backward compat)."""
    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(
        return_value=httpx.Response(403)
    )
    client = _make_client(monkeypatch)
    # An except CredentialExpiredError clause must still catch 403.
    with pytest.raises(CredentialExpiredError):
        client.get("/teams/abc/game-summaries")


@respx.mock
def test_get_paginated_401_raises_credential_expired_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP 401 on get_paginated raises CredentialExpiredError (not ForbiddenError) -- AC-4."""
    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(
        return_value=httpx.Response(401)
    )
    client = _make_client(monkeypatch)
    with pytest.raises(CredentialExpiredError) as exc_info:
        client.get_paginated("/teams/abc/game-summaries")
    assert not isinstance(exc_info.value, ForbiddenError)


@respx.mock
def test_get_paginated_403_raises_forbidden_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP 403 on get_paginated raises ForbiddenError -- AC-4."""
    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(
        return_value=httpx.Response(403)
    )
    client = _make_client(monkeypatch)
    with pytest.raises(ForbiddenError):
        client.get_paginated("/teams/abc/game-summaries")


# ---------------------------------------------------------------------------
# AC-3: 429 logs WARNING and raises RateLimitError after waiting
# ---------------------------------------------------------------------------


@respx.mock
def test_rate_limit_error_on_429_with_retry_after(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """HTTP 429 with Retry-After header raises RateLimitError after waiting."""
    import logging

    # Patch time.sleep so the test doesn't actually wait
    sleep_calls: list[float] = []
    monkeypatch.setattr("src.gamechanger.client.time.sleep", lambda s: sleep_calls.append(s))

    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "30"})
    )
    client = _make_client(monkeypatch)

    with caplog.at_level(logging.WARNING, logger="src.gamechanger.client"):
        with pytest.raises(RateLimitError):
            client.get("/teams/abc/game-summaries")

    # Verified the correct wait time was used.
    # The session rate-limit hook may also call time.sleep(0.0) -- filter those out.
    meaningful_sleeps = [s for s in sleep_calls if s > 0]
    assert meaningful_sleeps == [30]
    # Verified the warning was logged
    warning_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("/teams/abc/game-summaries" in m or "game-summaries" in m for m in warning_messages)


@respx.mock
def test_rate_limit_error_on_429_without_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP 429 without Retry-After header defaults to 60-second wait."""
    sleep_calls: list[float] = []
    monkeypatch.setattr("src.gamechanger.client.time.sleep", lambda s: sleep_calls.append(s))

    respx.get(f"{_BASE_URL}/me/teams").mock(
        return_value=httpx.Response(429)
    )
    client = _make_client(monkeypatch)

    with pytest.raises(RateLimitError):
        client.get("/me/teams")

    meaningful_sleeps = [s for s in sleep_calls if s > 0]
    assert meaningful_sleeps == [60]


@respx.mock
def test_rate_limit_does_not_silently_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP 429 is not silently retried -- it raises immediately after the wait."""
    monkeypatch.setattr("src.gamechanger.client.time.sleep", lambda s: None)

    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(429)

    respx.get(f"{_BASE_URL}/me/teams").mock(side_effect=handler)
    client = _make_client(monkeypatch)

    with pytest.raises(RateLimitError):
        client.get("/me/teams")

    # Should only have been called once (no silent retry)
    assert call_count == 1


# ---------------------------------------------------------------------------
# AC-4: 5xx retries up to 3 times with exponential backoff
# ---------------------------------------------------------------------------


@respx.mock
def test_server_error_retries_3_times_then_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """5xx response causes up to 3 retries, then raises GameChangerAPIError."""
    sleep_calls: list[float] = []
    monkeypatch.setattr("src.gamechanger.client.time.sleep", lambda s: sleep_calls.append(s))

    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(500)

    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(side_effect=handler)
    client = _make_client(monkeypatch)

    with pytest.raises(GameChangerAPIError):
        client.get("/teams/abc/game-summaries")

    assert call_count == 3
    # Backoff delays: 1s, 2s (before attempts 2 and 3; no sleep after the final failure).
    # The session rate-limit hook may also call time.sleep(0.0) -- filter those out.
    meaningful_sleeps = [s for s in sleep_calls if s > 0]
    assert meaningful_sleeps == [1, 2]


@respx.mock
def test_server_error_succeeds_on_second_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """5xx on first attempt, 200 on second attempt returns the response."""
    monkeypatch.setattr("src.gamechanger.client.time.sleep", lambda s: None)

    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500)
        return httpx.Response(200, json={"ok": True})

    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(side_effect=handler)
    client = _make_client(monkeypatch)
    result = client.get("/teams/abc/game-summaries")
    assert result == {"ok": True}
    assert attempts == 2


# ---------------------------------------------------------------------------
# AC-5: Missing credentials raise ConfigurationError at instantiation
# ---------------------------------------------------------------------------


def test_missing_all_credentials_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No .env file (or empty env) raises ConfigurationError listing missing keys."""
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda: {})

    with pytest.raises(ConfigurationError) as exc_info:
        GameChangerClient(min_delay_ms=0, jitter_ms=0)

    msg = str(exc_info.value)
    assert "GAMECHANGER_AUTH_TOKEN" in msg
    assert "GAMECHANGER_DEVICE_ID" in msg
    assert "GAMECHANGER_BASE_URL" in msg


def test_missing_single_credential_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One missing required key raises ConfigurationError mentioning that key."""
    partial_creds = {
        "GAMECHANGER_AUTH_TOKEN": "fake-token",
        "GAMECHANGER_DEVICE_ID": "fake-device-id",
        # GAMECHANGER_BASE_URL intentionally absent
    }
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda: partial_creds)

    with pytest.raises(ConfigurationError) as exc_info:
        GameChangerClient(min_delay_ms=0, jitter_ms=0)

    assert "GAMECHANGER_BASE_URL" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC-6: min_delay_ms and jitter_ms are forwarded to create_session()
# ---------------------------------------------------------------------------


def test_min_delay_and_jitter_forwarded_to_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """Constructor forwards min_delay_ms and jitter_ms to create_session()."""
    captured_kwargs: dict[str, int] = {}

    original_create_session = __import__(
        "src.http.session", fromlist=["create_session"]
    ).create_session

    def fake_create_session(min_delay_ms: int = 1000, jitter_ms: int = 500) -> object:
        captured_kwargs["min_delay_ms"] = min_delay_ms
        captured_kwargs["jitter_ms"] = jitter_ms
        return original_create_session(min_delay_ms=0, jitter_ms=0)

    monkeypatch.setattr("src.gamechanger.client.create_session", fake_create_session)
    monkeypatch.setattr(
        "src.gamechanger.client.dotenv_values",
        lambda: _FAKE_CREDENTIALS,
    )

    GameChangerClient(min_delay_ms=2000, jitter_ms=750)

    assert captured_kwargs["min_delay_ms"] == 2000
    assert captured_kwargs["jitter_ms"] == 750


# ---------------------------------------------------------------------------
# AC-7: timeout parameter is accepted and forwarded
# ---------------------------------------------------------------------------


@respx.mock
def test_get_accepts_timeout_parameter(monkeypatch: pytest.MonkeyPatch) -> None:
    """get() accepts an optional timeout parameter without error."""
    respx.get(f"{_BASE_URL}/me/teams").mock(
        return_value=httpx.Response(200, json=[])
    )
    client = _make_client(monkeypatch)
    result = client.get("/me/teams", timeout=60)
    assert result == []


# ---------------------------------------------------------------------------
# AC-8: accept parameter overrides the default Accept header
# ---------------------------------------------------------------------------


@respx.mock
def test_accept_header_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """When accept is provided, it overrides the session default Accept header."""
    vendor_accept = "application/vnd.gc.com.game_summary:list+json; version=0.1.0"

    route = respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(
        return_value=httpx.Response(200, json=[])
    )
    client = _make_client(monkeypatch)
    client.get("/teams/abc/game-summaries", accept=vendor_accept)

    request = route.calls.last.request
    assert request.headers["accept"] == vendor_accept


@respx.mock
def test_no_accept_parameter_uses_session_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """When accept is not provided, the session's default Accept header is used."""
    from src.http.headers import BROWSER_HEADERS

    route = respx.get(f"{_BASE_URL}/me/teams").mock(
        return_value=httpx.Response(200, json=[])
    )
    client = _make_client(monkeypatch)
    client.get("/me/teams")

    request = route.calls.last.request
    assert request.headers["accept"] == BROWSER_HEADERS["Accept"]


# ---------------------------------------------------------------------------
# Auth headers are injected on every request
# ---------------------------------------------------------------------------


@respx.mock
def test_auth_headers_injected(monkeypatch: pytest.MonkeyPatch) -> None:
    """gc-token, gc-device-id, and gc-app-name are present on every request."""
    route = respx.get(f"{_BASE_URL}/me/teams").mock(
        return_value=httpx.Response(200, json=[])
    )
    client = _make_client(monkeypatch)
    client.get("/me/teams")

    request = route.calls.last.request
    assert request.headers["gc-token"] == "fake-jwt-token"
    assert request.headers["gc-device-id"] == "abcdef1234567890abcdef1234567890"
    assert request.headers["gc-app-name"] == "web"


# ---------------------------------------------------------------------------
# Content-Type header is set on GET requests
# ---------------------------------------------------------------------------


@respx.mock
def test_content_type_header_set_on_get(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET requests include Content-Type: application/vnd.gc.com.none+json; ..."""
    route = respx.get(f"{_BASE_URL}/me/teams").mock(
        return_value=httpx.Response(200, json=[])
    )
    client = _make_client(monkeypatch)
    client.get("/me/teams")

    request = route.calls.last.request
    assert "application/vnd.gc.com.none+json" in request.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# get_paginated() 5xx retry tests (E-002-10)
# ---------------------------------------------------------------------------


@respx.mock
def test_paginated_5xx_retries_and_succeeds_on_second_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """5xx on first paginated attempt, 200 on second attempt -- pagination continues."""
    sleep_calls: list[float] = []
    monkeypatch.setattr("src.gamechanger.client.time.sleep", lambda s: sleep_calls.append(s))

    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500)
        return httpx.Response(200, json=[{"id": "game-1"}])

    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(side_effect=handler)
    client = _make_client(monkeypatch)
    result = client.get_paginated("/teams/abc/game-summaries")
    assert result == [{"id": "game-1"}]
    assert attempts == 2
    meaningful_sleeps = [s for s in sleep_calls if s > 0]
    assert meaningful_sleeps == [1]


@respx.mock
def test_paginated_5xx_exhausts_retries_and_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """5xx on all 3 paginated attempts raises GameChangerAPIError."""
    sleep_calls: list[float] = []
    monkeypatch.setattr("src.gamechanger.client.time.sleep", lambda s: sleep_calls.append(s))

    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(503)

    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(side_effect=handler)
    client = _make_client(monkeypatch)

    with pytest.raises(GameChangerAPIError):
        client.get_paginated("/teams/abc/game-summaries")

    assert call_count == 3
    meaningful_sleeps = [s for s in sleep_calls if s > 0]
    assert meaningful_sleeps == [1, 2]


@respx.mock
def test_paginated_non_5xx_error_raises_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-5xx, non-200, non-401/403, non-429 status (e.g. 418) raises immediately without retrying."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(418)

    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(side_effect=handler)
    client = _make_client(monkeypatch)

    with pytest.raises(GameChangerAPIError):
        client.get_paginated("/teams/abc/game-summaries")

    assert call_count == 1


@respx.mock
def test_paginated_5xx_retry_logs_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """5xx retry attempt is logged at WARNING level with status, URL, attempt, and backoff."""
    import logging

    monkeypatch.setattr("src.gamechanger.client.time.sleep", lambda s: None)

    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(502)
        return httpx.Response(200, json=[])

    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(side_effect=handler)
    client = _make_client(monkeypatch)

    with caplog.at_level(logging.WARNING, logger="src.gamechanger.client"):
        client.get_paginated("/teams/abc/game-summaries")

    warning_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("502" in m for m in warning_messages)
    assert any("game-summaries" in m or "api.team-manager.gc.com" in m for m in warning_messages)


@respx.mock
def test_paginated_5xx_retries_same_page_not_entire_sequence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """5xx on page 2 retries page 2 only -- page 1 data is preserved."""
    monkeypatch.setattr("src.gamechanger.client.time.sleep", lambda s: None)

    page2_url = f"{_BASE_URL}/teams/abc/page2"
    page2_attempts = 0
    page1_calls = 0

    def page1_handler(request: httpx.Request) -> httpx.Response:
        nonlocal page1_calls
        page1_calls += 1
        return httpx.Response(
            200,
            json=[{"id": "game-1"}],
            headers={"x-next-page": page2_url},
        )

    def page2_handler(request: httpx.Request) -> httpx.Response:
        nonlocal page2_attempts
        page2_attempts += 1
        if page2_attempts == 1:
            return httpx.Response(500)
        return httpx.Response(200, json=[{"id": "game-2"}])

    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(side_effect=page1_handler)
    respx.get(page2_url).mock(side_effect=page2_handler)

    client = _make_client(monkeypatch)
    result = client.get_paginated("/teams/abc/game-summaries")

    assert result == [{"id": "game-1"}, {"id": "game-2"}]
    # Page 1 fetched exactly once -- retry was on page 2 only.
    assert page1_calls == 1
    assert page2_attempts == 2
