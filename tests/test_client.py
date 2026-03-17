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

_FAKE_ACCESS_TOKEN = "fake-access-token"
_FAKE_CREDENTIALS = {
    "GAMECHANGER_REFRESH_TOKEN_WEB": "fake-refresh-token",
    "GAMECHANGER_CLIENT_ID_WEB": "07cb985d-ff6c-429d-992c-b8a0d44e6fc3",
    "GAMECHANGER_CLIENT_KEY_WEB": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    "GAMECHANGER_DEVICE_ID_WEB": "abcdef1234567890abcdef1234567890",
    "GAMECHANGER_BASE_URL": "https://api.team-manager.gc.com",
    "GAMECHANGER_APP_NAME_WEB": "web",
}

_BASE_URL = "https://api.team-manager.gc.com"


def _mock_token_manager(monkeypatch: pytest.MonkeyPatch, access_token: str = _FAKE_ACCESS_TOKEN) -> None:
    """Patch TokenManager so tests do not trigger real POST /auth flows."""
    from unittest.mock import MagicMock
    mock_tm = MagicMock()
    mock_tm.get_access_token.return_value = access_token
    mock_tm.force_refresh.return_value = access_token
    monkeypatch.setattr("src.gamechanger.client.TokenManager", lambda **kwargs: mock_tm)


def _make_client(monkeypatch: pytest.MonkeyPatch) -> GameChangerClient:
    """Return a GameChangerClient with fake credentials and zero delays."""
    monkeypatch.setattr(
        "src.gamechanger.client.dotenv_values",
        lambda *_a, **_kw: _FAKE_CREDENTIALS,
    )
    _mock_token_manager(monkeypatch)
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
    assert "bb creds check" in msg or "check .env" in msg


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
def test_non_5xx_unexpected_status_raises_unexpected_status_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-5xx unexpected status (e.g. 418) raises 'Unexpected status' error without retrying."""
    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(return_value=httpx.Response(418))
    client = _make_client(monkeypatch)

    with pytest.raises(GameChangerAPIError, match=r"Unexpected status 418"):
        client.get("/teams/abc/game-summaries")


@respx.mock
def test_server_error_exhausted_retries_raises_retry_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Three consecutive 5xx responses raise an error that includes retry context, not 'Unexpected status'."""
    monkeypatch.setattr("src.gamechanger.client.time.sleep", lambda s: None)

    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(return_value=httpx.Response(503))
    client = _make_client(monkeypatch)

    with pytest.raises(GameChangerAPIError, match=r"attempt"):
        client.get("/teams/abc/game-summaries")


@respx.mock
def test_server_error_exhausted_retries_does_not_raise_unexpected_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """Three consecutive 5xx responses do not produce an 'Unexpected status' error message."""
    monkeypatch.setattr("src.gamechanger.client.time.sleep", lambda s: None)

    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(return_value=httpx.Response(503))
    client = _make_client(monkeypatch)

    with pytest.raises(GameChangerAPIError) as exc_info:
        client.get("/teams/abc/game-summaries")

    assert "Unexpected status" not in str(exc_info.value)


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
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: {})

    with pytest.raises(ConfigurationError) as exc_info:
        GameChangerClient(min_delay_ms=0, jitter_ms=0)

    msg = str(exc_info.value)
    assert "GAMECHANGER_REFRESH_TOKEN_WEB" in msg
    assert "GAMECHANGER_BASE_URL" in msg


def test_missing_single_credential_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One missing required key raises ConfigurationError mentioning that key."""
    partial_creds = {
        "GAMECHANGER_REFRESH_TOKEN_WEB": "fake-token",
        "GAMECHANGER_CLIENT_ID_WEB": "07cb985d-ff6c-429d-992c-b8a0d44e6fc3",
        "GAMECHANGER_CLIENT_KEY_WEB": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        "GAMECHANGER_DEVICE_ID_WEB": "fake-device-id",
        # GAMECHANGER_BASE_URL intentionally absent
    }
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: partial_creds)

    with pytest.raises(ConfigurationError) as exc_info:
        GameChangerClient(min_delay_ms=0, jitter_ms=0)

    assert "GAMECHANGER_BASE_URL" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC-6: min_delay_ms and jitter_ms are forwarded to create_session()
# ---------------------------------------------------------------------------


def test_min_delay_and_jitter_forwarded_to_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """Constructor forwards min_delay_ms and jitter_ms to create_session()."""
    captured_kwargs: dict[str, object] = {}

    original_create_session = __import__(
        "src.http.session", fromlist=["create_session"]
    ).create_session

    def fake_create_session(
        min_delay_ms: int = 1000, jitter_ms: int = 500, profile: str = "web", **kwargs: object
    ) -> object:
        captured_kwargs["min_delay_ms"] = min_delay_ms
        captured_kwargs["jitter_ms"] = jitter_ms
        captured_kwargs["profile"] = profile
        return original_create_session(min_delay_ms=0, jitter_ms=0)

    monkeypatch.setattr("src.gamechanger.client.create_session", fake_create_session)
    monkeypatch.setattr(
        "src.gamechanger.client.dotenv_values",
        lambda *_a, **_kw: _FAKE_CREDENTIALS,
    )
    _mock_token_manager(monkeypatch)

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
    assert request.headers["gc-token"] == _FAKE_ACCESS_TOKEN
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


# ---------------------------------------------------------------------------
# Profile-aware GameChangerClient (E-050-02)
# ---------------------------------------------------------------------------

_FAKE_CREDENTIALS_NO_APP_NAME = {
    "GAMECHANGER_REFRESH_TOKEN_WEB": "fake-refresh-token",
    "GAMECHANGER_CLIENT_ID_WEB": "07cb985d-ff6c-429d-992c-b8a0d44e6fc3",
    "GAMECHANGER_CLIENT_KEY_WEB": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    "GAMECHANGER_DEVICE_ID_WEB": "abcdef1234567890abcdef1234567890",
    "GAMECHANGER_BASE_URL": "https://api.team-manager.gc.com",
    # GAMECHANGER_APP_NAME_WEB intentionally absent
}

_FAKE_CREDENTIALS_MOBILE = {
    "GAMECHANGER_DEVICE_ID_MOBILE": "mobiledeviceid1234567890abcdef",
    "GAMECHANGER_BASE_URL": "https://api.team-manager.gc.com",
    # Mobile manual fallback path -- no client key, access token provided directly
    "GAMECHANGER_ACCESS_TOKEN_MOBILE": "fake-mobile-access-token",
}

_FAKE_CREDENTIALS_MOBILE_NO_APP_NAME = {
    "GAMECHANGER_DEVICE_ID_MOBILE": "mobiledeviceid1234567890abcdef",
    "GAMECHANGER_BASE_URL": "https://api.team-manager.gc.com",
    "GAMECHANGER_ACCESS_TOKEN_MOBILE": "fake-mobile-access-token",
    # GAMECHANGER_APP_NAME_MOBILE intentionally absent
}


def _make_client_with_profile(
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
    credentials: dict | None = None,
) -> GameChangerClient:
    """Return a GameChangerClient with the given profile and zero delays."""
    creds = credentials if credentials is not None else _FAKE_CREDENTIALS
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: creds)
    _mock_token_manager(monkeypatch)
    return GameChangerClient(min_delay_ms=0, jitter_ms=0, profile=profile)


@respx.mock
def test_default_profile_uses_web_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default profile (web) uses Chrome browser User-Agent on outgoing requests."""
    from src.http.headers import BROWSER_HEADERS

    route = respx.get(f"{_BASE_URL}/me/teams").mock(
        return_value=httpx.Response(200, json=[])
    )
    client = _make_client(monkeypatch)
    client.get("/me/teams")

    request = route.calls.last.request
    assert request.headers["user-agent"] == BROWSER_HEADERS["User-Agent"]


@respx.mock
def test_mobile_profile_uses_mobile_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit profile='mobile' uses iOS Odyssey User-Agent on outgoing requests."""
    from src.http.headers import MOBILE_HEADERS

    route = respx.get(f"{_BASE_URL}/me/teams").mock(
        return_value=httpx.Response(200, json=[])
    )
    client = _make_client_with_profile(monkeypatch, "mobile", _FAKE_CREDENTIALS_MOBILE)
    client.get("/me/teams")

    request = route.calls.last.request
    assert request.headers["user-agent"] == MOBILE_HEADERS["User-Agent"]


def test_invalid_profile_raises_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """profile='invalid' raises an error (ConfigurationError for unknown profile credentials)."""
    monkeypatch.setattr(
        "src.gamechanger.client.dotenv_values", lambda *_a, **_kw: _FAKE_CREDENTIALS
    )
    with pytest.raises((ValueError, ConfigurationError)):
        GameChangerClient(min_delay_ms=0, jitter_ms=0, profile="invalid")


def test_profile_parameter_forwarded_to_create_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Constructor forwards the profile argument to create_session()."""
    original_create_session = __import__(
        "src.http.session", fromlist=["create_session"]
    ).create_session

    captured: dict[str, object] = {}

    def fake_create_session(
        min_delay_ms: int = 1000, jitter_ms: int = 500, profile: str = "web", **kwargs: object
    ) -> object:
        captured["profile"] = profile
        return original_create_session(min_delay_ms=0, jitter_ms=0, profile=profile)

    monkeypatch.setattr("src.gamechanger.client.create_session", fake_create_session)
    monkeypatch.setattr(
        "src.gamechanger.client.dotenv_values", lambda *_a, **_kw: _FAKE_CREDENTIALS_MOBILE
    )
    _mock_token_manager(monkeypatch)

    GameChangerClient(min_delay_ms=0, jitter_ms=0, profile="mobile")
    assert captured["profile"] == "mobile"


@respx.mock
def test_gc_app_name_from_env_var_used_for_web_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When GAMECHANGER_APP_NAME_WEB is set in .env, it is used for web profile."""
    creds_with_app_name = {**_FAKE_CREDENTIALS_NO_APP_NAME, "GAMECHANGER_APP_NAME_WEB": "custom-app"}

    route = respx.get(f"{_BASE_URL}/me/teams").mock(
        return_value=httpx.Response(200, json=[])
    )

    client_web = _make_client_with_profile(monkeypatch, "web", creds_with_app_name)
    client_web.get("/me/teams")
    assert route.calls.last.request.headers["gc-app-name"] == "custom-app"


@respx.mock
def test_gc_app_name_from_env_var_used_for_mobile_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When GAMECHANGER_APP_NAME_MOBILE is set in .env, it is used for mobile profile."""
    creds_with_app_name = {**_FAKE_CREDENTIALS_MOBILE_NO_APP_NAME, "GAMECHANGER_APP_NAME_MOBILE": "custom-mobile-app"}

    route = respx.get(f"{_BASE_URL}/me/teams").mock(
        return_value=httpx.Response(200, json=[])
    )

    client_mobile = _make_client_with_profile(monkeypatch, "mobile", creds_with_app_name)
    client_mobile.get("/me/teams")
    assert route.calls.last.request.headers["gc-app-name"] == "custom-mobile-app"


@respx.mock
def test_gc_app_name_defaults_to_web_when_env_absent_and_profile_web(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without GAMECHANGER_APP_NAME_WEB, web profile defaults gc-app-name to 'web'."""
    route = respx.get(f"{_BASE_URL}/me/teams").mock(
        return_value=httpx.Response(200, json=[])
    )
    client = _make_client_with_profile(monkeypatch, "web", _FAKE_CREDENTIALS_NO_APP_NAME)
    client.get("/me/teams")

    assert route.calls.last.request.headers["gc-app-name"] == "web"


@respx.mock
def test_gc_app_name_omitted_when_env_absent_and_profile_mobile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without GAMECHANGER_APP_NAME_MOBILE, mobile profile omits gc-app-name entirely."""
    route = respx.get(f"{_BASE_URL}/me/teams").mock(
        return_value=httpx.Response(200, json=[])
    )
    client = _make_client_with_profile(monkeypatch, "mobile", _FAKE_CREDENTIALS_MOBILE_NO_APP_NAME)
    client.get("/me/teams")

    assert "gc-app-name" not in route.calls.last.request.headers


# ---------------------------------------------------------------------------
# Profile-scoped credential loading (E-053-02)
# ---------------------------------------------------------------------------


def test_web_profile_loads_web_scoped_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-1: GameChangerClient(profile='web') reads _WEB suffixed keys.

    gc-token is set lazily on first API call; device-id is set eagerly.
    """
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: _FAKE_CREDENTIALS)
    _mock_token_manager(monkeypatch)
    client = GameChangerClient(min_delay_ms=0, jitter_ms=0, profile="web")
    # device-id is set eagerly at construction time
    assert client._session.headers["gc-device-id"] == "abcdef1234567890abcdef1234567890"
    # gc-token is NOT set at construction; set lazily on first API call
    assert "gc-token" not in client._session.headers


def test_web_profile_gc_token_set_on_first_api_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """gc-token is set to the access token (not refresh token) on first API call."""
    import respx as _respx
    import httpx as _httpx

    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: _FAKE_CREDENTIALS)
    _mock_token_manager(monkeypatch, access_token=_FAKE_ACCESS_TOKEN)

    with _respx.mock:
        _respx.get(f"{_BASE_URL}/me/teams").mock(return_value=_httpx.Response(200, json=[]))
        client = GameChangerClient(min_delay_ms=0, jitter_ms=0, profile="web")
        client.get("/me/teams")
        assert client._session.headers["gc-token"] == _FAKE_ACCESS_TOKEN


def test_web_profile_missing_web_key_raises_no_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-2: Missing _WEB key raises ConfigurationError even if flat key exists."""
    creds_with_flat_only = {
        "GAMECHANGER_REFRESH_TOKEN": "flat-token",  # flat key -- should NOT be used
        "GAMECHANGER_DEVICE_ID": "flat-device",
        "GAMECHANGER_BASE_URL": "https://api.team-manager.gc.com",
    }
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: creds_with_flat_only)

    with pytest.raises(ConfigurationError) as exc_info:
        GameChangerClient(min_delay_ms=0, jitter_ms=0, profile="web")

    assert "GAMECHANGER_REFRESH_TOKEN_WEB" in str(exc_info.value)


def test_mobile_profile_loads_mobile_scoped_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-3: GameChangerClient(profile='mobile') reads _MOBILE suffixed keys.

    For mobile without client key, the manual access token fallback is used.
    device-id is set eagerly; gc-token is lazy.
    """
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: _FAKE_CREDENTIALS_MOBILE)
    _mock_token_manager(monkeypatch)
    client = GameChangerClient(min_delay_ms=0, jitter_ms=0, profile="mobile")
    assert client._session.headers["gc-device-id"] == "mobiledeviceid1234567890abcdef"
    # gc-token is NOT set at construction; set lazily on first API call
    assert "gc-token" not in client._session.headers


def test_mobile_profile_missing_device_id_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-4: Missing GAMECHANGER_DEVICE_ID_MOBILE raises ConfigurationError."""
    creds_missing_device_id = {
        "GAMECHANGER_BASE_URL": "https://api.team-manager.gc.com",
        # GAMECHANGER_DEVICE_ID_MOBILE intentionally absent
    }
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: creds_missing_device_id)

    with pytest.raises(ConfigurationError) as exc_info:
        GameChangerClient(min_delay_ms=0, jitter_ms=0, profile="mobile")

    assert "GAMECHANGER_DEVICE_ID_MOBILE" in str(exc_info.value)


def test_base_url_remains_unsuffixed(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-5: GAMECHANGER_BASE_URL is not profile-scoped (same for both profiles)."""
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: _FAKE_CREDENTIALS)
    _mock_token_manager(monkeypatch)
    client = GameChangerClient(min_delay_ms=0, jitter_ms=0, profile="web")
    assert client._base_url == "https://api.team-manager.gc.com"


# ---------------------------------------------------------------------------
# AC-8: 401 retry logic, double-401, token expiry between requests,
# and mobile fallback with manual access token.
# ---------------------------------------------------------------------------


@respx.mock
def test_401_triggers_force_refresh_and_retry_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-8a: 401 triggers force_refresh() and a single retry that succeeds."""
    from unittest.mock import MagicMock

    fresh_token = "refreshed-access-token"
    mock_tm = MagicMock()
    mock_tm.get_access_token.return_value = _FAKE_ACCESS_TOKEN
    mock_tm.force_refresh.return_value = fresh_token
    monkeypatch.setattr("src.gamechanger.client.TokenManager", lambda **_kw: mock_tm)
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: _FAKE_CREDENTIALS)

    # First call returns 401; retry (after force_refresh) returns 200.
    route = respx.get(f"{_BASE_URL}/me/teams").mock(
        side_effect=[
            httpx.Response(401),
            httpx.Response(200, json=["team-a"]),
        ]
    )
    client = GameChangerClient(min_delay_ms=0, jitter_ms=0)
    result = client.get("/me/teams")

    assert result == ["team-a"]
    mock_tm.force_refresh.assert_called_once()
    # Session gc-token updated to the fresh token after refresh.
    assert client._session.headers["gc-token"] == fresh_token
    assert route.call_count == 2


@respx.mock
def test_double_401_raises_credential_expired_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-8b: If both the initial request and the retry return 401, raises CredentialExpiredError."""
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: _FAKE_CREDENTIALS)
    _mock_token_manager(monkeypatch)

    respx.get(f"{_BASE_URL}/me/teams").mock(return_value=httpx.Response(401))
    client = GameChangerClient(min_delay_ms=0, jitter_ms=0)

    with pytest.raises(CredentialExpiredError):
        client.get("/me/teams")


@respx.mock
def test_token_refresh_between_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-8c: Access token is refreshed between requests when TokenManager signals expiry."""
    from unittest.mock import MagicMock

    first_token = "first-access-token"
    second_token = "second-access-token"
    mock_tm = MagicMock()
    # First call returns first_token; second call (simulating expiry) returns second_token.
    mock_tm.get_access_token.side_effect = [first_token, second_token]
    mock_tm.force_refresh.return_value = second_token
    monkeypatch.setattr("src.gamechanger.client.TokenManager", lambda **_kw: mock_tm)
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: _FAKE_CREDENTIALS)

    respx.get(f"{_BASE_URL}/me/teams").mock(return_value=httpx.Response(200, json=[]))
    client = GameChangerClient(min_delay_ms=0, jitter_ms=0)

    # First API call uses first_token.
    client.get("/me/teams")
    assert client._session.headers["gc-token"] == first_token

    # Second API call: TokenManager returns second_token (simulates post-expiry refresh).
    client.get("/me/teams")
    assert client._session.headers["gc-token"] == second_token

    assert mock_tm.get_access_token.call_count == 2


@respx.mock
def test_mobile_manual_access_token_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-8d: Mobile profile with manual access token (no client key) works end-to-end."""
    from unittest.mock import MagicMock

    manual_token = "fake-mobile-access-token"
    mock_tm = MagicMock()
    mock_tm.get_access_token.return_value = manual_token
    mock_tm.force_refresh.return_value = manual_token
    monkeypatch.setattr("src.gamechanger.client.TokenManager", lambda **_kw: mock_tm)
    monkeypatch.setattr(
        "src.gamechanger.client.dotenv_values",
        lambda *_a, **_kw: _FAKE_CREDENTIALS_MOBILE,
    )

    respx.get(f"{_BASE_URL}/me/user").mock(
        return_value=httpx.Response(200, json={"email": "coach@example.com"})
    )
    client = GameChangerClient(min_delay_ms=0, jitter_ms=0, profile="mobile")
    result = client.get("/me/user")

    assert result["email"] == "coach@example.com"
    assert client._session.headers["gc-token"] == manual_token


# ---------------------------------------------------------------------------
# Regression: 401 retry -- force_refresh() error propagation (Finding 4)
# ---------------------------------------------------------------------------


@respx.mock
def test_401_force_refresh_auth_signing_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AuthSigningError from force_refresh() propagates -- not swallowed by except: pass."""
    from unittest.mock import MagicMock
    from src.gamechanger.token_manager import AuthSigningError

    mock_tm = MagicMock()
    mock_tm.get_access_token.return_value = _FAKE_ACCESS_TOKEN
    mock_tm.force_refresh.side_effect = AuthSigningError("bad signature")
    monkeypatch.setattr("src.gamechanger.client.TokenManager", lambda **_kw: mock_tm)
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: _FAKE_CREDENTIALS)

    respx.get(f"{_BASE_URL}/me/teams").mock(return_value=httpx.Response(401))
    client = GameChangerClient(min_delay_ms=0, jitter_ms=0)

    with pytest.raises(AuthSigningError):
        client.get("/me/teams")

    mock_tm.force_refresh.assert_called_once()


@respx.mock
def test_401_force_refresh_credential_expired_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CredentialExpiredError from force_refresh() propagates -- not swallowed by except: pass."""
    from unittest.mock import MagicMock

    mock_tm = MagicMock()
    mock_tm.get_access_token.return_value = _FAKE_ACCESS_TOKEN
    mock_tm.force_refresh.side_effect = CredentialExpiredError("refresh token expired")
    monkeypatch.setattr("src.gamechanger.client.TokenManager", lambda **_kw: mock_tm)
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: _FAKE_CREDENTIALS)

    respx.get(f"{_BASE_URL}/me/teams").mock(return_value=httpx.Response(401))
    client = GameChangerClient(min_delay_ms=0, jitter_ms=0)

    with pytest.raises(CredentialExpiredError, match="refresh token expired"):
        client.get("/me/teams")

    mock_tm.force_refresh.assert_called_once()


@respx.mock
def test_401_post_refresh_403_raises_forbidden_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After successful force_refresh(), a 403 on the retry raises ForbiddenError (not CredentialExpiredError)."""
    from unittest.mock import MagicMock

    fresh_token = "refreshed-access-token"
    mock_tm = MagicMock()
    mock_tm.get_access_token.return_value = _FAKE_ACCESS_TOKEN
    mock_tm.force_refresh.return_value = fresh_token
    monkeypatch.setattr("src.gamechanger.client.TokenManager", lambda **_kw: mock_tm)
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: _FAKE_CREDENTIALS)

    # First request 401 -> force_refresh -> retry gets 403
    respx.get(f"{_BASE_URL}/me/teams").mock(
        side_effect=[
            httpx.Response(401),
            httpx.Response(403),
        ]
    )
    client = GameChangerClient(min_delay_ms=0, jitter_ms=0)

    with pytest.raises(ForbiddenError):
        client.get("/me/teams")


# ---------------------------------------------------------------------------
# E-079-01: Proxy forwarding from dotenv dict (AC-1, AC-2, AC-3)
# ---------------------------------------------------------------------------


def test_proxy_forwarded_to_session_when_enabled_web(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-1: PROXY_ENABLED=true + PROXY_URL_WEB in dotenv dict routes web session through proxy."""
    from unittest.mock import patch as _patch

    creds_with_proxy = {
        **_FAKE_CREDENTIALS,
        "PROXY_ENABLED": "true",
        "PROXY_URL_WEB": "http://proxy.example.com:1234",
    }
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: creds_with_proxy)
    _mock_token_manager(monkeypatch)

    with _patch("src.http.session.httpx.Client") as mock_client:
        mock_client.return_value = mock_client  # make it usable as a session
        mock_client.headers = {}
        GameChangerClient(min_delay_ms=0, jitter_ms=0, profile="web")

    _, kwargs = mock_client.call_args
    assert kwargs.get("proxy") == "http://proxy.example.com:1234"


def test_proxy_forwarded_to_session_when_enabled_mobile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-2: PROXY_ENABLED=true + PROXY_URL_MOBILE in dotenv dict routes mobile session through proxy."""
    from unittest.mock import patch as _patch

    creds_with_proxy = {
        **_FAKE_CREDENTIALS_MOBILE,
        "PROXY_ENABLED": "true",
        "PROXY_URL_MOBILE": "http://proxy.example.com:5678",
    }
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: creds_with_proxy)
    _mock_token_manager(monkeypatch)

    with _patch("src.http.session.httpx.Client") as mock_client:
        mock_client.return_value = mock_client
        mock_client.headers = {}
        GameChangerClient(min_delay_ms=0, jitter_ms=0, profile="mobile")

    _, kwargs = mock_client.call_args
    assert kwargs.get("proxy") == "http://proxy.example.com:5678"


def test_no_proxy_when_proxy_disabled_in_dotenv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-3: PROXY_ENABLED absent from dotenv dict -- no proxy configured on session."""
    from unittest.mock import patch as _patch

    # _FAKE_CREDENTIALS has no PROXY_ENABLED key -- proxy must be None
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: _FAKE_CREDENTIALS)
    _mock_token_manager(monkeypatch)

    with _patch("src.http.session.httpx.Client") as mock_client:
        mock_client.return_value = mock_client
        mock_client.headers = {}
        GameChangerClient(min_delay_ms=0, jitter_ms=0, profile="web")

    _, kwargs = mock_client.call_args
    assert kwargs.get("proxy") is None


@respx.mock
def test_paginated_401_force_refresh_auth_signing_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AuthSigningError from force_refresh() propagates in get_paginated() -- not swallowed."""
    from unittest.mock import MagicMock
    from src.gamechanger.token_manager import AuthSigningError

    mock_tm = MagicMock()
    mock_tm.get_access_token.return_value = _FAKE_ACCESS_TOKEN
    mock_tm.force_refresh.side_effect = AuthSigningError("bad signature")
    monkeypatch.setattr("src.gamechanger.client.TokenManager", lambda **_kw: mock_tm)
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: _FAKE_CREDENTIALS)

    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(return_value=httpx.Response(401))
    client = GameChangerClient(min_delay_ms=0, jitter_ms=0)

    with pytest.raises(AuthSigningError):
        client.get_paginated("/teams/abc/game-summaries")

    mock_tm.force_refresh.assert_called_once()


# ---------------------------------------------------------------------------
# AC-4, AC-5: GameChangerClient session ID generation
# ---------------------------------------------------------------------------


class TestClientStickySessionId:
    """AC-4, AC-5: client generates a unique alphanumeric session ID per instance."""

    def test_client_has_session_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AC-4: GameChangerClient instance has a session_id attribute."""
        client = _make_client(monkeypatch)
        assert hasattr(client, "_session_id")
        assert isinstance(client._session_id, str)
        assert len(client._session_id) > 0

    def test_session_id_is_alphanumeric(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AC-4: session ID contains only alphanumeric characters (hex digits)."""
        client = _make_client(monkeypatch)
        assert client._session_id.isalnum(), (
            f"session_id {client._session_id!r} contains non-alphanumeric characters"
        )

    def test_session_id_is_16_chars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AC-4: token_hex(8) produces a 16-character hex string."""
        client = _make_client(monkeypatch)
        assert len(client._session_id) == 16

    def test_two_instances_have_different_session_ids(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-5: Two GameChangerClient instances in the same process have different IDs."""
        client1 = _make_client(monkeypatch)
        client2 = _make_client(monkeypatch)
        assert client1._session_id != client2._session_id

    def test_session_id_logged_at_debug(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """AC-4: session ID is logged at DEBUG level during client construction."""
        import logging
        with caplog.at_level(logging.DEBUG, logger="src.gamechanger.client"):
            client = _make_client(monkeypatch)
        session_id = client._session_id
        messages = " ".join(r.getMessage() for r in caplog.records)
        assert session_id in messages, (
            f"Expected session_id {session_id!r} in DEBUG log, got: {messages!r}"
        )

    def test_session_id_passed_to_resolve_proxy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-4: client passes its session_id to resolve_proxy_from_dict()."""
        from unittest.mock import patch, MagicMock

        captured_kwargs: dict = {}

        original_resolve = __import__(
            "src.http.session", fromlist=["resolve_proxy_from_dict"]
        ).resolve_proxy_from_dict

        def capturing_resolve(env_dict: dict, profile: str, session_id: str | None = None) -> None:
            captured_kwargs["session_id"] = session_id
            return original_resolve(env_dict, profile, session_id=session_id)

        monkeypatch.setattr("src.gamechanger.client.resolve_proxy_from_dict", capturing_resolve)
        monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: _FAKE_CREDENTIALS)
        _mock_token_manager(monkeypatch)
        client = GameChangerClient(min_delay_ms=0, jitter_ms=0)

        assert captured_kwargs.get("session_id") == client._session_id

    def test_client_session_id_not_in_proxy_url_log(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """AC-7: proxy URL with injected session ID must not appear in log output."""
        import logging

        creds_with_proxy = dict(_FAKE_CREDENTIALS)
        creds_with_proxy["PROXY_ENABLED"] = "true"
        creds_with_proxy["PROXY_URL_WEB"] = "http://brd-user:s3cr3t@proxy.example.com:1234"

        monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: creds_with_proxy)
        _mock_token_manager(monkeypatch)

        with caplog.at_level(logging.DEBUG):
            client = GameChangerClient(min_delay_ms=0, jitter_ms=0)

        session_id = client._session_id
        for record in caplog.records:
            msg = record.getMessage()
            # The raw proxy URL or injected URL must never appear
            assert "s3cr3t" not in msg, f"Proxy credentials leaked into log: {msg!r}"
            injected_user = f"brd-user-session-{session_id}"
            assert injected_user not in msg, f"Injected proxy URL leaked into log: {msg!r}"


# ---------------------------------------------------------------------------
# AC-7: __file__-relative .env path resolution
# ---------------------------------------------------------------------------


def test_default_env_path_resolves_to_repo_root() -> None:
    """AC-7: _DEFAULT_ENV_PATH resolves to <repo-root>/.env regardless of cwd."""
    from src.gamechanger.client import _DEFAULT_ENV_PATH

    # The path must end with ".env" and its parent must be the repo root.
    assert _DEFAULT_ENV_PATH.name == ".env"
    # The parent of _DEFAULT_ENV_PATH should be the repo root, which contains pyproject.toml.
    repo_root = _DEFAULT_ENV_PATH.parent
    assert (repo_root / "pyproject.toml").exists(), (
        f"Expected repo root at {repo_root!r} but pyproject.toml not found there"
    )


def test_default_env_path_is_absolute() -> None:
    """AC-7: _DEFAULT_ENV_PATH is an absolute path (not cwd-relative)."""
    from src.gamechanger.client import _DEFAULT_ENV_PATH

    assert _DEFAULT_ENV_PATH.is_absolute()


# ---------------------------------------------------------------------------
# E-125-05: Retry-After non-integer handling (AC-1, AC-2, AC-5)
# ---------------------------------------------------------------------------


def test_parse_retry_after_integer_string() -> None:
    """_parse_retry_after returns the integer value for a valid integer string."""
    from src.gamechanger.client import _parse_retry_after

    assert _parse_retry_after("30") == 30


def test_parse_retry_after_http_date_falls_back_to_default() -> None:
    """_parse_retry_after falls back to default for an HTTP-date string (AC-1)."""
    from src.gamechanger.client import _parse_retry_after, _DEFAULT_RETRY_AFTER_SECONDS

    result = _parse_retry_after("Fri, 31 Dec 1999 23:59:59 GMT")
    assert result == _DEFAULT_RETRY_AFTER_SECONDS


def test_parse_retry_after_empty_string_falls_back_to_default() -> None:
    """_parse_retry_after falls back to default for an empty string."""
    from src.gamechanger.client import _parse_retry_after, _DEFAULT_RETRY_AFTER_SECONDS

    assert _parse_retry_after("") == _DEFAULT_RETRY_AFTER_SECONDS


def test_parse_retry_after_zero_returns_one() -> None:
    """_parse_retry_after clamps to minimum of 1 second."""
    from src.gamechanger.client import _parse_retry_after

    assert _parse_retry_after("0") == 1


@respx.mock
def test_get_429_with_http_date_retry_after_does_not_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-5: HTTP 429 with an HTTP-date Retry-After does not crash with ValueError."""
    from src.gamechanger.client import _DEFAULT_RETRY_AFTER_SECONDS

    sleep_calls: list[float] = []
    monkeypatch.setattr("src.gamechanger.client.time.sleep", lambda s: sleep_calls.append(s))

    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(
        return_value=httpx.Response(
            429, headers={"Retry-After": "Fri, 31 Dec 1999 23:59:59 GMT"}
        )
    )
    client = _make_client(monkeypatch)

    with pytest.raises(RateLimitError):
        client.get("/teams/abc/game-summaries")

    meaningful_sleeps = [s for s in sleep_calls if s > 0]
    assert meaningful_sleeps == [_DEFAULT_RETRY_AFTER_SECONDS]


@respx.mock
def test_get_public_429_with_http_date_retry_after_does_not_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-5: HTTP 429 with an HTTP-date Retry-After on get_public does not crash."""
    from src.gamechanger.client import _DEFAULT_RETRY_AFTER_SECONDS

    sleep_calls: list[float] = []
    monkeypatch.setattr("src.gamechanger.client.time.sleep", lambda s: sleep_calls.append(s))

    respx.get(f"{_BASE_URL}/public/teams/abc/games").mock(
        return_value=httpx.Response(
            429, headers={"Retry-After": "Sat, 01 Jan 2000 00:00:00 GMT"}
        )
    )
    client = _make_client(monkeypatch)

    with pytest.raises(RateLimitError):
        client.get_public("/public/teams/abc/games")

    meaningful_sleeps = [s for s in sleep_calls if s > 0]
    assert meaningful_sleeps == [_DEFAULT_RETRY_AFTER_SECONDS]


@respx.mock
def test_get_paginated_429_with_http_date_retry_after_does_not_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-5: HTTP 429 with an HTTP-date Retry-After on get_paginated does not crash."""
    from src.gamechanger.client import _DEFAULT_RETRY_AFTER_SECONDS

    sleep_calls: list[float] = []
    monkeypatch.setattr("src.gamechanger.client.time.sleep", lambda s: sleep_calls.append(s))

    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(
        return_value=httpx.Response(
            429, headers={"Retry-After": "Sun, 02 Jan 2000 12:00:00 GMT"}
        )
    )
    client = _make_client(monkeypatch)

    with pytest.raises(RateLimitError):
        client.get_paginated("/teams/abc/game-summaries")

    meaningful_sleeps = [s for s in sleep_calls if s > 0]
    assert meaningful_sleeps == [_DEFAULT_RETRY_AFTER_SECONDS]


# ---------------------------------------------------------------------------
# E-125-05: Pagination URL host validation (AC-3, AC-6)
# ---------------------------------------------------------------------------


@respx.mock
def test_paginated_rejects_different_host_next_page(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-6: get_paginated stops pagination when x-next-page host differs from base URL."""
    import logging

    evil_url = "https://evil.example.com/steal-tokens?page=2"
    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(
        return_value=httpx.Response(
            200,
            json=[{"id": "game-1"}],
            headers={"x-next-page": evil_url},
        )
    )
    # The evil URL should NOT be followed.
    respx.get(evil_url).mock(return_value=httpx.Response(200, json=[{"id": "stolen"}]))

    client = _make_client(monkeypatch)
    with caplog.at_level(logging.WARNING, logger="src.gamechanger.client"):
        result = client.get_paginated("/teams/abc/game-summaries")

    # Only page 1 data returned; evil page was not followed.
    assert result == [{"id": "game-1"}]
    assert any("host mismatch" in r.getMessage() for r in caplog.records)


@respx.mock
def test_paginated_allows_same_host_next_page(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-3: get_paginated follows x-next-page when host matches base URL."""
    page2_url = f"{_BASE_URL}/teams/abc/game-summaries-page2"

    respx.get(f"{_BASE_URL}/teams/abc/game-summaries").mock(
        return_value=httpx.Response(
            200,
            json=[{"id": "game-1"}],
            headers={"x-next-page": page2_url},
        )
    )
    respx.get(page2_url).mock(
        return_value=httpx.Response(200, json=[{"id": "game-2"}])
    )

    client = _make_client(monkeypatch)
    result = client.get_paginated("/teams/abc/game-summaries")

    assert result == [{"id": "game-1"}, {"id": "game-2"}]
