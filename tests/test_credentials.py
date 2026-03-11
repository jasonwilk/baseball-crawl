# synthetic-test-data
"""Unit tests for the enhanced check_profile_detailed() in src/gamechanger/credentials.py.

All HTTP calls are mocked -- no real network requests are made.
dotenv_values and proxy helpers are monkeypatched so no filesystem or
external-service access occurs.

Coverage:
- Credential presence (present / missing keys)
- Token health (valid, expired, undecodable, absent)
- API health check (ok, expired, network error, missing creds)
- Proxy status (not configured, pass, pass_unverified, fail, error)
- No credential values appear in output structures
- decode_jwt_exp helper
"""

from __future__ import annotations

import base64
import json
import time
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from src.gamechanger.credentials import (
    ClientKeyCheckResult,
    CredentialPresence,
    ProfileCheckResult,
    TokenHealth,
    _check_client_key,
    _extract_display_name,
    check_profile_detailed,
    decode_jwt_exp,
)
from src.http.proxy_check import ProxyCheckOutcome, ProxyCheckResult

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_BASE_URL = "https://api.team-manager.gc.com"

_FAKE_WEB_CREDENTIALS = {
    "GAMECHANGER_REFRESH_TOKEN_WEB": "fake-refresh-token",
    "GAMECHANGER_CLIENT_ID_WEB": "fake-client-id",
    "GAMECHANGER_CLIENT_KEY_WEB": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    "GAMECHANGER_DEVICE_ID_WEB": "abcdef1234567890abcdef1234567890",
    "GAMECHANGER_BASE_URL": _BASE_URL,
}


def _make_jwt(exp_offset: int = 3600) -> str:
    """Build a minimal JWT string with a real ``exp`` claim."""
    payload = {"exp": int(time.time()) + exp_offset}
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    )
    return f"header.{payload_b64}.sig"


def _patch_dotenv(monkeypatch: pytest.MonkeyPatch, values: dict) -> None:
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda *_a, **_kw: values)
    monkeypatch.setattr("src.gamechanger.credentials.dotenv_values", lambda *_a, **_kw: values)


def _mock_token_manager(monkeypatch: pytest.MonkeyPatch, token: str = "fake-access") -> None:
    mock_tm = MagicMock()
    mock_tm.get_access_token.return_value = token
    monkeypatch.setattr("src.gamechanger.client.TokenManager", lambda **_: mock_tm)


def _not_configured_proxy() -> ProxyCheckResult:
    return ProxyCheckResult(profile="web", outcome=ProxyCheckOutcome.NOT_CONFIGURED)


# ---------------------------------------------------------------------------
# decode_jwt_exp
# ---------------------------------------------------------------------------


def test_decode_jwt_exp_returns_exp_from_valid_token() -> None:
    future_exp = int(time.time()) + 7200
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps({"exp": future_exp}).encode())
        .rstrip(b"=")
        .decode()
    )
    token = f"header.{payload_b64}.sig"
    assert decode_jwt_exp(token) == future_exp


def test_decode_jwt_exp_returns_none_for_malformed_token() -> None:
    assert decode_jwt_exp("not-a-jwt") is None


def test_decode_jwt_exp_returns_none_when_exp_missing() -> None:
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps({"sub": "user"}).encode())
        .rstrip(b"=")
        .decode()
    )
    token = f"header.{payload_b64}.sig"
    assert decode_jwt_exp(token) is None


# ---------------------------------------------------------------------------
# _extract_display_name
# ---------------------------------------------------------------------------


def test_extract_display_name_returns_full_name_when_present() -> None:
    """Returns 'First Last' when both fields are non-empty."""
    assert _extract_display_name({"first_name": "Jason", "last_name": "Smith"}) == "Jason Smith"


def test_extract_display_name_missing_last_name_returns_authenticated_user() -> None:
    """Falls back to '(authenticated user)' when last_name is absent -- no PII leaked."""
    result = _extract_display_name({"first_name": "Jason"})
    assert result == "(authenticated user)"
    assert "@" not in result


def test_extract_display_name_missing_first_name_returns_authenticated_user() -> None:
    """Falls back to '(authenticated user)' when first_name is absent."""
    result = _extract_display_name({"last_name": "Smith"})
    assert result == "(authenticated user)"
    assert "@" not in result


def test_extract_display_name_missing_both_names_returns_authenticated_user() -> None:
    """Falls back to '(authenticated user)' when both name fields are absent -- not email."""
    user = {"email": "coach@example.com"}
    result = _extract_display_name(user)
    assert result == "(authenticated user)"
    assert "coach@example.com" not in result


def test_extract_display_name_empty_names_returns_authenticated_user() -> None:
    """Falls back to '(authenticated user)' when name fields are empty strings."""
    result = _extract_display_name({"first_name": "", "last_name": "", "email": "x@y.com"})
    assert result == "(authenticated user)"
    assert "x@y.com" not in result


# ---------------------------------------------------------------------------
# AC-1: All credentials present, valid API response
# ---------------------------------------------------------------------------


@respx.mock
def test_check_profile_detailed_all_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-1: Full happy path -- all sections OK."""
    env = {
        **_FAKE_WEB_CREDENTIALS,
        "GAMECHANGER_REFRESH_TOKEN_WEB": _make_jwt(86400 * 12),  # 12 days
    }
    _patch_dotenv(monkeypatch, env)
    _mock_token_manager(monkeypatch)
    monkeypatch.setattr(
        "src.gamechanger.credentials.get_direct_ip", lambda: "1.2.3.4"
    )
    monkeypatch.setattr(
        "src.gamechanger.credentials.check_proxy_routing",
        lambda profile, direct_ip: _not_configured_proxy(),
    )
    respx.post(f"{_BASE_URL}/auth").mock(return_value=httpx.Response(200, json={}))
    respx.get(f"{_BASE_URL}/me/user").mock(
        return_value=httpx.Response(
            200,
            json={"first_name": "Jason", "last_name": "Smith", "email": "coach@example.com"},
        )
    )

    result = check_profile_detailed("web")

    assert isinstance(result, ProfileCheckResult)
    assert result.exit_code == 0
    assert result.profile == "web"
    # Credential presence
    assert result.presence.keys_missing == []
    assert len(result.presence.keys_present) > 0
    # Token health
    assert result.token_health is not None
    assert result.token_health.is_expired is False
    # API
    assert result.api_result.exit_code == 0
    assert result.api_result.display_name == "Jason Smith"
    assert "Jason Smith" in result.api_result.message
    # Proxy
    assert result.proxy_result.outcome == ProxyCheckOutcome.NOT_CONFIGURED


# ---------------------------------------------------------------------------
# AC-2: Missing credentials
# ---------------------------------------------------------------------------


def test_check_profile_detailed_missing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-2: Missing keys listed, no values revealed."""
    _patch_dotenv(monkeypatch, {})
    monkeypatch.setattr("src.gamechanger.credentials.get_direct_ip", lambda: None)
    monkeypatch.setattr(
        "src.gamechanger.credentials.check_proxy_routing",
        lambda profile, direct_ip: _not_configured_proxy(),
    )

    result = check_profile_detailed("web")

    assert result.exit_code == 2
    assert "GAMECHANGER_REFRESH_TOKEN_WEB" in result.presence.keys_missing
    assert "GAMECHANGER_BASE_URL" in result.presence.keys_missing
    assert result.presence.keys_present == []
    # API check skipped
    assert result.api_result.exit_code == 2
    assert "missing" in result.api_result.message.lower()


def test_check_profile_detailed_missing_keys_no_values_revealed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-9: Credential values must not appear in structured output."""
    secret_token = "super-secret-refresh-token"
    partial = {
        "GAMECHANGER_REFRESH_TOKEN_WEB": secret_token,
        "GAMECHANGER_CLIENT_ID_WEB": "some-client-id",
        # Missing CLIENT_KEY, DEVICE_ID, BASE_URL
    }
    _patch_dotenv(monkeypatch, partial)
    monkeypatch.setattr("src.gamechanger.credentials.get_direct_ip", lambda: None)
    monkeypatch.setattr(
        "src.gamechanger.credentials.check_proxy_routing",
        lambda profile, direct_ip: _not_configured_proxy(),
    )

    result = check_profile_detailed("web")

    # Secret values must not appear anywhere in the dataclass string representation
    result_str = repr(result)
    assert secret_token not in result_str
    assert "some-client-id" not in result_str


# ---------------------------------------------------------------------------
# AC-3: Expired refresh token -- API check still attempted
# ---------------------------------------------------------------------------


@respx.mock
def test_check_profile_detailed_expired_token_still_attempts_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-3: Expired refresh token triggers [!!] but API check is still attempted."""
    expired_token = _make_jwt(exp_offset=-3600)  # expired 1 hour ago
    env = {**_FAKE_WEB_CREDENTIALS, "GAMECHANGER_REFRESH_TOKEN_WEB": expired_token}
    _patch_dotenv(monkeypatch, env)
    _mock_token_manager(monkeypatch)
    monkeypatch.setattr("src.gamechanger.credentials.get_direct_ip", lambda: "1.2.3.4")
    monkeypatch.setattr(
        "src.gamechanger.credentials.check_proxy_routing",
        lambda profile, direct_ip: _not_configured_proxy(),
    )
    respx.post(f"{_BASE_URL}/auth").mock(return_value=httpx.Response(200, json={}))
    respx.get(f"{_BASE_URL}/me/user").mock(
        return_value=httpx.Response(
            200,
            json={"first_name": "Jason", "last_name": "Smith", "email": "coach@example.com"},
        )
    )

    result = check_profile_detailed("web")

    # Token health shows expired
    assert result.token_health is not None
    assert result.token_health.is_expired is True
    # But API check was still attempted and succeeded (access token cached)
    assert result.api_result.exit_code == 0
    assert result.exit_code == 0


@respx.mock
def test_check_profile_detailed_expired_token_no_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-3: If token is expired and API also fails, exit_code reflects API failure."""
    from src.gamechanger.client import CredentialExpiredError

    expired_token = _make_jwt(exp_offset=-86400)  # expired 1 day ago
    env = {**_FAKE_WEB_CREDENTIALS, "GAMECHANGER_REFRESH_TOKEN_WEB": expired_token}
    _patch_dotenv(monkeypatch, env)

    mock_tm = MagicMock()
    mock_tm.get_access_token.side_effect = CredentialExpiredError("expired")
    monkeypatch.setattr("src.gamechanger.client.TokenManager", lambda **_: mock_tm)
    monkeypatch.setattr("src.gamechanger.credentials.get_direct_ip", lambda: None)
    monkeypatch.setattr(
        "src.gamechanger.credentials.check_proxy_routing",
        lambda profile, direct_ip: _not_configured_proxy(),
    )
    respx.post(f"{_BASE_URL}/auth").mock(return_value=httpx.Response(200, json={}))

    result = check_profile_detailed("web")

    assert result.token_health is not None
    assert result.token_health.is_expired is True
    assert result.api_result.exit_code == 1
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# AC-4: Proxy configured and routing correctly
# ---------------------------------------------------------------------------


def test_check_profile_detailed_proxy_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-4: Proxy configured -- routing check result is included."""
    _patch_dotenv(monkeypatch, {})
    monkeypatch.setattr("src.gamechanger.credentials.get_direct_ip", lambda: "1.2.3.4")
    pass_result = ProxyCheckResult(
        profile="web",
        outcome=ProxyCheckOutcome.PASS,
        proxy_ip="5.6.7.8",
        direct_ip="1.2.3.4",
    )
    monkeypatch.setattr(
        "src.gamechanger.credentials.check_proxy_routing",
        lambda profile, direct_ip: pass_result,
    )

    result = check_profile_detailed("web")

    assert result.proxy_result.outcome == ProxyCheckOutcome.PASS


def test_check_profile_detailed_proxy_pass_unverified(monkeypatch: pytest.MonkeyPatch) -> None:
    """PASS_UNVERIFIED: direct baseline unavailable."""
    _patch_dotenv(monkeypatch, {})
    monkeypatch.setattr("src.gamechanger.credentials.get_direct_ip", lambda: None)
    unverified = ProxyCheckResult(
        profile="web", outcome=ProxyCheckOutcome.PASS_UNVERIFIED, proxy_ip="5.6.7.8"
    )
    monkeypatch.setattr(
        "src.gamechanger.credentials.check_proxy_routing",
        lambda profile, direct_ip: unverified,
    )

    result = check_profile_detailed("web")

    assert result.proxy_result.outcome == ProxyCheckOutcome.PASS_UNVERIFIED


# ---------------------------------------------------------------------------
# AC-5: Proxy not configured
# ---------------------------------------------------------------------------


def test_check_profile_detailed_proxy_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-5: No proxy configured -- outcome is NOT_CONFIGURED."""
    _patch_dotenv(monkeypatch, {})
    monkeypatch.setattr("src.gamechanger.credentials.get_direct_ip", lambda: "1.2.3.4")
    monkeypatch.setattr(
        "src.gamechanger.credentials.check_proxy_routing",
        lambda profile, direct_ip: ProxyCheckResult(
            profile="web", outcome=ProxyCheckOutcome.NOT_CONFIGURED
        ),
    )

    result = check_profile_detailed("web")

    assert result.proxy_result.outcome == ProxyCheckOutcome.NOT_CONFIGURED


# ---------------------------------------------------------------------------
# Token health edge cases
# ---------------------------------------------------------------------------


@respx.mock
def test_check_profile_detailed_undecodable_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Undecodable token: exp=None, is_expired=None."""
    env = {**_FAKE_WEB_CREDENTIALS, "GAMECHANGER_REFRESH_TOKEN_WEB": "not.a.jwt"}
    _patch_dotenv(monkeypatch, env)
    _mock_token_manager(monkeypatch)
    monkeypatch.setattr("src.gamechanger.credentials.get_direct_ip", lambda: None)
    monkeypatch.setattr(
        "src.gamechanger.credentials.check_proxy_routing",
        lambda profile, direct_ip: _not_configured_proxy(),
    )
    respx.post(f"{_BASE_URL}/auth").mock(return_value=httpx.Response(200, json={}))
    respx.get(f"{_BASE_URL}/me/user").mock(return_value=httpx.Response(200, json={}))

    result = check_profile_detailed("web")

    assert result.token_health is not None
    assert result.token_health.exp is None
    assert result.token_health.is_expired is None


@respx.mock
def test_check_profile_detailed_no_refresh_token_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """When refresh token key is absent, token_health is None."""
    env = {k: v for k, v in _FAKE_WEB_CREDENTIALS.items() if k != "GAMECHANGER_REFRESH_TOKEN_WEB"}
    _patch_dotenv(monkeypatch, env)
    monkeypatch.setattr("src.gamechanger.credentials.get_direct_ip", lambda: None)
    monkeypatch.setattr(
        "src.gamechanger.credentials.check_proxy_routing",
        lambda profile, direct_ip: _not_configured_proxy(),
    )
    respx.post(f"{_BASE_URL}/auth").mock(return_value=httpx.Response(200, json={}))

    result = check_profile_detailed("web")

    assert result.token_health is None


# ---------------------------------------------------------------------------
# API health check edge cases
# ---------------------------------------------------------------------------


@respx.mock
def test_check_profile_detailed_api_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Network error during API check returns exit_code=1."""
    env = {**_FAKE_WEB_CREDENTIALS, "GAMECHANGER_REFRESH_TOKEN_WEB": _make_jwt()}
    _patch_dotenv(monkeypatch, env)
    _mock_token_manager(monkeypatch)
    monkeypatch.setattr("src.gamechanger.credentials.get_direct_ip", lambda: None)
    monkeypatch.setattr(
        "src.gamechanger.credentials.check_proxy_routing",
        lambda profile, direct_ip: _not_configured_proxy(),
    )
    respx.post(f"{_BASE_URL}/auth").mock(return_value=httpx.Response(200, json={}))
    respx.get(f"{_BASE_URL}/me/user").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    result = check_profile_detailed("web")

    assert result.api_result.exit_code == 1
    assert result.exit_code == 1
    assert "network" in result.api_result.message.lower() or "error" in result.api_result.message.lower()


@respx.mock
def test_check_profile_detailed_api_display_name_not_in_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-9: Credential values (tokens, URLs) do not appear in the display name field."""
    env = {
        **_FAKE_WEB_CREDENTIALS,
        "GAMECHANGER_REFRESH_TOKEN_WEB": _make_jwt(),
    }
    _patch_dotenv(monkeypatch, env)
    _mock_token_manager(monkeypatch)
    monkeypatch.setattr("src.gamechanger.credentials.get_direct_ip", lambda: None)
    monkeypatch.setattr(
        "src.gamechanger.credentials.check_proxy_routing",
        lambda profile, direct_ip: _not_configured_proxy(),
    )
    respx.post(f"{_BASE_URL}/auth").mock(return_value=httpx.Response(200, json={}))
    respx.get(f"{_BASE_URL}/me/user").mock(
        return_value=httpx.Response(
            200,
            json={"first_name": "Coach", "last_name": "User", "email": "coach@example.com"},
        )
    )

    result = check_profile_detailed("web")

    # Token value must not appear anywhere in the result
    assert "fake-access" not in repr(result)
    assert "abcdef1234567890abcdef1234567890" not in repr(result)


# ---------------------------------------------------------------------------
# AC-7: __file__-relative .env path resolution
# ---------------------------------------------------------------------------


def test_credentials_env_path_resolves_to_repo_root() -> None:
    """AC-7: _ENV_PATH in credentials.py resolves to <repo-root>/.env regardless of cwd."""
    from src.gamechanger.credentials import _ENV_PATH

    assert _ENV_PATH.name == ".env"
    repo_root = _ENV_PATH.parent
    assert (repo_root / "pyproject.toml").exists(), (
        f"Expected repo root at {repo_root!r} but pyproject.toml not found there"
    )


def test_credentials_env_path_is_absolute() -> None:
    """AC-7: _ENV_PATH in credentials.py is an absolute path (not cwd-relative)."""
    from src.gamechanger.credentials import _ENV_PATH

    assert _ENV_PATH.is_absolute()


# ---------------------------------------------------------------------------
# _check_client_key tests (AC-1 through AC-14 in E-095-02)
# ---------------------------------------------------------------------------


def _web_env_for_key_check(overrides: dict | None = None) -> dict:
    """Return a minimal web-profile env dict for client key validation tests."""
    base = {
        "GAMECHANGER_CLIENT_ID_WEB": "fake-client-id",
        "GAMECHANGER_CLIENT_KEY_WEB": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        "GAMECHANGER_DEVICE_ID_WEB": "abcdef1234567890abcdef1234567890",
        "GAMECHANGER_BASE_URL": _BASE_URL,
    }
    if overrides:
        base.update(overrides)
    return base


@respx.mock
def test_check_client_key_valid_key_returns_valid() -> None:
    """AC-1 / AC-5: 200 response → status='valid', [OK] indicator."""
    respx.post(f"{_BASE_URL}/auth").mock(return_value=httpx.Response(200, json={}))
    result = _check_client_key("web", _web_env_for_key_check())
    assert result.status == "valid"
    assert "verified" in result.message.lower() or "succeeded" in result.message.lower()


@respx.mock
def test_check_client_key_stale_401_close_timestamps() -> None:
    """AC-1 / AC-6: 401 with close server timestamp → status='invalid'."""
    import time as _time

    now = int(_time.time())
    # Server timestamp matches local (within 30s) → stale key, not clock skew.
    date_header = "Mon, 11 Mar 2026 00:00:00 GMT"  # won't be parsed as "now" but skew check needs divergence
    # Use a mock that returns 401 with a Date header very close to now.
    from email.utils import formatdate
    close_date = formatdate(now, usegmt=True)
    respx.post(f"{_BASE_URL}/auth").mock(
        return_value=httpx.Response(401, headers={"Date": close_date})
    )
    result = _check_client_key("web", _web_env_for_key_check())
    assert result.status == "invalid"
    assert "rejected" in result.message.lower()
    assert "extract-key" in result.message


@respx.mock
def test_check_client_key_stale_400_close_timestamps() -> None:
    """AC-1 / AC-6: 400 with close server timestamp → status='invalid'."""
    import time as _time
    from email.utils import formatdate

    now = int(_time.time())
    close_date = formatdate(now, usegmt=True)
    respx.post(f"{_BASE_URL}/auth").mock(
        return_value=httpx.Response(400, headers={"Date": close_date})
    )
    result = _check_client_key("web", _web_env_for_key_check())
    assert result.status == "invalid"


@respx.mock
def test_check_client_key_clock_skew_detected() -> None:
    """AC-1 / AC-7: Non-200 with server Date header >30s skewed → status='clock_skew'."""
    from email.utils import formatdate

    # Server timestamp is 120 seconds in the past relative to local clock.
    stale_ts = int(time.time()) - 120
    skewed_date = formatdate(stale_ts, usegmt=True)
    respx.post(f"{_BASE_URL}/auth").mock(
        return_value=httpx.Response(400, headers={"Date": skewed_date})
    )
    result = _check_client_key("web", _web_env_for_key_check())
    assert result.status == "clock_skew"
    assert result.skew_seconds is not None
    assert result.skew_seconds > 30
    assert "clock" in result.message.lower() or "skew" in result.message.lower()


@respx.mock
def test_check_client_key_absent_date_header_treated_as_stale() -> None:
    """AC-1 / AC-3: Non-200 with no Date header → status='invalid' (fail closed)."""
    respx.post(f"{_BASE_URL}/auth").mock(
        return_value=httpx.Response(401, headers={})
    )
    result = _check_client_key("web", _web_env_for_key_check())
    assert result.status == "invalid"


@respx.mock
def test_check_client_key_unparseable_date_header_treated_as_stale() -> None:
    """AC-3: Unparseable Date header → status='invalid' (fail closed)."""
    respx.post(f"{_BASE_URL}/auth").mock(
        return_value=httpx.Response(401, headers={"Date": "not-a-real-date"})
    )
    result = _check_client_key("web", _web_env_for_key_check())
    assert result.status == "invalid"


@respx.mock
def test_check_client_key_network_error_returns_error() -> None:
    """AC-1 / AC-9a: Network error → status='error', [!!] indicator."""
    respx.post(f"{_BASE_URL}/auth").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    result = _check_client_key("web", _web_env_for_key_check())
    assert result.status == "error"
    assert "network" in result.message.lower() or "error" in result.message.lower()


def test_check_client_key_missing_key_returns_skipped() -> None:
    """AC-1 / AC-8: Missing client key → status='skipped' with key name in message."""
    env = _web_env_for_key_check({"GAMECHANGER_CLIENT_KEY_WEB": ""})
    result = _check_client_key("web", env)
    assert result.status == "skipped"
    assert "GAMECHANGER_CLIENT_KEY_WEB" in result.message


def test_check_client_key_mobile_profile_returns_skipped() -> None:
    """AC-1 / AC-9: Mobile profile → status='skipped'."""
    result = _check_client_key("mobile", {})
    assert result.status == "skipped"
    assert "mobile" in result.message.lower()


def test_check_client_key_missing_prerequisites_returns_skipped() -> None:
    """AC-14: Missing client_id, device_id, or base_url → skipped, lists which prereqs."""
    env = {"GAMECHANGER_CLIENT_KEY_WEB": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="}
    result = _check_client_key("web", env)
    assert result.status == "skipped"
    assert "GAMECHANGER_CLIENT_ID_WEB" in result.message
    assert "GAMECHANGER_DEVICE_ID_WEB" in result.message
    assert "GAMECHANGER_BASE_URL" in result.message


def test_check_client_key_never_logs_key_value() -> None:
    """AC-13: Key value must not appear in the returned message."""
    key_value = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    # Missing prereqs so no HTTP call is made; still verify message is clean.
    env = {"GAMECHANGER_CLIENT_KEY_WEB": key_value}
    result = _check_client_key("web", env)
    assert key_value not in result.message


def test_check_profile_detailed_includes_client_key_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-15: ProfileCheckResult.client_key_result is populated after check_profile_detailed."""
    _patch_dotenv(monkeypatch, {})
    monkeypatch.setattr("src.gamechanger.credentials.get_direct_ip", lambda: None)
    monkeypatch.setattr(
        "src.gamechanger.credentials.check_proxy_routing",
        lambda profile, direct_ip: _not_configured_proxy(),
    )

    result = check_profile_detailed("web")

    # With empty env, client_key_result should be "skipped" (key absent).
    assert result.client_key_result is not None
    assert result.client_key_result.status == "skipped"


def test_invalid_client_key_sets_exit_code_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exit code reflects invalid client key even when API health check passes.

    When check_profile_detailed() gets a passing API result (exit_code=0) but
    the client key validation returns 'invalid', the overall exit_code should
    be 1 -- not 0.
    """
    env = {**_FAKE_WEB_CREDENTIALS, "GAMECHANGER_REFRESH_TOKEN_WEB": _make_jwt(3600)}
    _patch_dotenv(monkeypatch, env)
    _mock_token_manager(monkeypatch)
    monkeypatch.setattr("src.gamechanger.credentials.get_direct_ip", lambda: None)
    monkeypatch.setattr(
        "src.gamechanger.credentials.check_proxy_routing",
        lambda profile, direct_ip: _not_configured_proxy(),
    )
    # Mock the client key check to return 'invalid'
    monkeypatch.setattr(
        "src.gamechanger.credentials._check_client_key",
        lambda profile, env: ClientKeyCheckResult(
            status="invalid",
            message="Client key rejected -- update via: bb creds extract-key",
        ),
    )

    with respx.mock:
        respx.get(f"{_BASE_URL}/me/user").mock(
            return_value=httpx.Response(200, json={"first_name": "Jason", "last_name": "Smith"})
        )
        result = check_profile_detailed("web")

    assert result.api_result.exit_code == 0, "API check itself should pass"
    assert result.client_key_result is not None
    assert result.client_key_result.status == "invalid"
    assert result.exit_code == 1, "Overall exit code should be 1 due to invalid client key"


def test_profile_check_result_default_client_key_none() -> None:
    """AC-15: ProfileCheckResult can be constructed without client_key_result (default None)."""
    from src.gamechanger.credentials import ApiCheckResult, CredentialPresence, TokenHealth
    from src.http.proxy_check import ProxyCheckOutcome, ProxyCheckResult

    result = ProfileCheckResult(
        profile="web",
        presence=CredentialPresence(keys_present=[], keys_missing=[]),
        token_health=None,
        api_result=ApiCheckResult(exit_code=2, display_name=None, message="skipped"),
        proxy_result=ProxyCheckResult(profile="web", outcome=ProxyCheckOutcome.NOT_CONFIGURED),
        exit_code=2,
        # client_key_result NOT provided -- should default to None
    )
    assert result.client_key_result is None
