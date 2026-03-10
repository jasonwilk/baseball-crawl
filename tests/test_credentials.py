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
    CredentialPresence,
    ProfileCheckResult,
    TokenHealth,
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

    result = check_profile_detailed("web")

    assert result.token_health is not None
    assert result.token_health.exp is None
    assert result.token_health.is_expired is None


def test_check_profile_detailed_no_refresh_token_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """When refresh token key is absent, token_health is None."""
    env = {k: v for k, v in _FAKE_WEB_CREDENTIALS.items() if k != "GAMECHANGER_REFRESH_TOKEN_WEB"}
    _patch_dotenv(monkeypatch, env)
    monkeypatch.setattr("src.gamechanger.credentials.get_direct_ip", lambda: None)
    monkeypatch.setattr(
        "src.gamechanger.credentials.check_proxy_routing",
        lambda profile, direct_ip: _not_configured_proxy(),
    )

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
