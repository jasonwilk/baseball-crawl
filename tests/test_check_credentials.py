# synthetic-test-data
"""Unit tests for scripts/check_credentials.py.

All HTTP calls are mocked -- no real network requests are made.
Credentials are injected via monkeypatching dotenv_values.
TokenManager is mocked so no real POST /auth calls are made.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
import respx

from src.gamechanger.credentials import check_credentials

_FAKE_ACCESS_TOKEN = "fake-access-token"

_FAKE_WEB_CREDENTIALS = {
    "GAMECHANGER_REFRESH_TOKEN_WEB": "fake-jwt-token",
    "GAMECHANGER_CLIENT_ID_WEB": "fake-client-id",
    "GAMECHANGER_CLIENT_KEY_WEB": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    "GAMECHANGER_DEVICE_ID_WEB": "abcdef1234567890abcdef1234567890",
    "GAMECHANGER_BASE_URL": "https://api.team-manager.gc.com",
}

_FAKE_MOBILE_CREDENTIALS = {
    "GAMECHANGER_ACCESS_TOKEN_MOBILE": "fake-mobile-access-token",
    "GAMECHANGER_DEVICE_ID_MOBILE": "mobile1234567890abcdef1234567890",
    "GAMECHANGER_BASE_URL": "https://api.team-manager.gc.com",
}

_FAKE_BOTH_CREDENTIALS = {**_FAKE_WEB_CREDENTIALS, **_FAKE_MOBILE_CREDENTIALS}

_BASE_URL = "https://api.team-manager.gc.com"


def _patch_dotenv(monkeypatch: pytest.MonkeyPatch, values: dict) -> None:
    """Patch dotenv_values in the client module so credentials are injected."""
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda: values)


def _mock_token_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch TokenManager so no real POST /auth calls are made during tests."""
    mock_tm = MagicMock()
    mock_tm.get_access_token.return_value = _FAKE_ACCESS_TOKEN
    mock_tm.force_refresh.return_value = _FAKE_ACCESS_TOKEN
    monkeypatch.setattr("src.gamechanger.client.TokenManager", lambda **_kw: mock_tm)


# ---------------------------------------------------------------------------
# Single profile: missing credentials -- exit 2
# ---------------------------------------------------------------------------


def test_missing_all_credentials_returns_exit_2(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_dotenv(monkeypatch, {})
    exit_code, message = check_credentials(profile="web")
    assert exit_code == 2
    assert "GAMECHANGER_REFRESH_TOKEN_WEB" in message or "Missing" in message


def test_missing_one_credential_returns_exit_2(monkeypatch: pytest.MonkeyPatch) -> None:
    partial = {k: v for k, v in _FAKE_WEB_CREDENTIALS.items() if k != "GAMECHANGER_REFRESH_TOKEN_WEB"}
    _patch_dotenv(monkeypatch, partial)
    exit_code, message = check_credentials(profile="web")
    assert exit_code == 2
    assert "GAMECHANGER_REFRESH_TOKEN_WEB" in message


def test_missing_credentials_message_never_reveals_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Credential values must not appear in output."""
    partial = {
        "GAMECHANGER_REFRESH_TOKEN_WEB": "super-secret-token",
        "GAMECHANGER_CLIENT_ID_WEB": "secret-client-id",
        "GAMECHANGER_DEVICE_ID_WEB": "secret-device",
        # GAMECHANGER_CLIENT_KEY_WEB and GAMECHANGER_BASE_URL absent
    }
    _patch_dotenv(monkeypatch, partial)
    exit_code, message = check_credentials(profile="web")
    assert exit_code == 2
    assert "super-secret-token" not in message
    assert "secret-device" not in message


# ---------------------------------------------------------------------------
# Single profile (web): valid credentials -- exit 0
# ---------------------------------------------------------------------------


@respx.mock
def test_valid_credentials_with_full_name_returns_exit_0(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_dotenv(monkeypatch, _FAKE_WEB_CREDENTIALS)
    _mock_token_manager(monkeypatch)
    respx.get(f"{_BASE_URL}/me/user").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "user-uuid",
                "email": "coach@example.com",
                "first_name": "Jason",
                "last_name": "Smith",
            },
        )
    )
    exit_code, message = check_credentials(profile="web")
    assert exit_code == 0
    assert "Jason Smith" in message
    assert "valid" in message.lower()


@respx.mock
def test_valid_credentials_falls_back_to_email_when_names_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_dotenv(monkeypatch, _FAKE_WEB_CREDENTIALS)
    _mock_token_manager(monkeypatch)
    respx.get(f"{_BASE_URL}/me/user").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "user-uuid",
                "email": "coach@example.com",
                "first_name": "",
                "last_name": "",
            },
        )
    )
    exit_code, message = check_credentials(profile="web")
    assert exit_code == 0
    assert "(authenticated user)" in message


@respx.mock
def test_valid_credentials_message_does_not_reveal_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Token value must not appear in success output."""
    _patch_dotenv(monkeypatch, _FAKE_WEB_CREDENTIALS)
    _mock_token_manager(monkeypatch)
    respx.get(f"{_BASE_URL}/me/user").mock(
        return_value=httpx.Response(
            200,
            json={"email": "coach@example.com", "first_name": "Jason", "last_name": "Smith"},
        )
    )
    exit_code, message = check_credentials(profile="web")
    assert exit_code == 0
    assert "fake-jwt-token" not in message
    assert "abcdef1234567890abcdef1234567890" not in message


# ---------------------------------------------------------------------------
# Single profile (web): expired credentials (401) -- exit 1
# ---------------------------------------------------------------------------


@respx.mock
def test_expired_credentials_401_returns_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_dotenv(monkeypatch, _FAKE_WEB_CREDENTIALS)
    _mock_token_manager(monkeypatch)
    respx.get(f"{_BASE_URL}/me/user").mock(
        return_value=httpx.Response(401, json={"error": "unauthorized"})
    )
    exit_code, message = check_credentials(profile="web")
    assert exit_code == 1
    assert "expired" in message.lower()


# ---------------------------------------------------------------------------
# Single profile (web): forbidden (403) -- exit 1
# ---------------------------------------------------------------------------


@respx.mock
def test_forbidden_403_returns_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_dotenv(monkeypatch, _FAKE_WEB_CREDENTIALS)
    _mock_token_manager(monkeypatch)
    respx.get(f"{_BASE_URL}/me/user").mock(
        return_value=httpx.Response(403, json={"error": "forbidden"})
    )
    exit_code, message = check_credentials(profile="web")
    assert exit_code == 1
    assert "denied" in message.lower()


# ---------------------------------------------------------------------------
# Single profile (web): network errors -- exit 1
# ---------------------------------------------------------------------------


@respx.mock
def test_network_timeout_returns_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_dotenv(monkeypatch, _FAKE_WEB_CREDENTIALS)
    _mock_token_manager(monkeypatch)
    respx.get(f"{_BASE_URL}/me/user").mock(side_effect=httpx.TimeoutException("timed out"))
    exit_code, message = check_credentials(profile="web")
    assert exit_code == 1
    assert "network" in message.lower() or "error" in message.lower()


@respx.mock
def test_connect_error_returns_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_dotenv(monkeypatch, _FAKE_WEB_CREDENTIALS)
    _mock_token_manager(monkeypatch)
    respx.get(f"{_BASE_URL}/me/user").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    exit_code, message = check_credentials(profile="web")
    assert exit_code == 1
    assert "network" in message.lower() or "error" in message.lower()


# ---------------------------------------------------------------------------
# Single profile (mobile): valid -- exit 0
# ---------------------------------------------------------------------------


@respx.mock
def test_mobile_profile_valid_returns_exit_0(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_dotenv(monkeypatch, _FAKE_MOBILE_CREDENTIALS)
    _mock_token_manager(monkeypatch)
    respx.get(f"{_BASE_URL}/me/user").mock(
        return_value=httpx.Response(
            200,
            json={"email": "coach@example.com", "first_name": "Jason", "last_name": "Smith"},
        )
    )
    exit_code, message = check_credentials(profile="mobile")
    assert exit_code == 0
    assert "valid" in message.lower()


def test_mobile_profile_missing_credentials_returns_exit_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_dotenv(monkeypatch, {})
    exit_code, message = check_credentials(profile="mobile")
    assert exit_code == 2
    assert "GAMECHANGER_DEVICE_ID_MOBILE" in message or "Missing" in message


# ---------------------------------------------------------------------------
# Multi-profile summary (no profile arg): AC-3 and AC-4
# ---------------------------------------------------------------------------


@respx.mock
def test_multi_profile_both_valid_returns_exit_0(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_dotenv(monkeypatch, _FAKE_BOTH_CREDENTIALS)
    _mock_token_manager(monkeypatch)
    respx.get(f"{_BASE_URL}/me/user").mock(
        return_value=httpx.Response(
            200,
            json={"email": "coach@example.com", "first_name": "Jason", "last_name": "Smith"},
        )
    )
    exit_code, message = check_credentials()
    assert exit_code == 0
    assert "web" in message
    assert "mobile" in message


@respx.mock
def test_multi_profile_only_web_valid_returns_exit_0(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exit 0 when at least one profile is valid (AC-4)."""
    _patch_dotenv(monkeypatch, _FAKE_WEB_CREDENTIALS)  # no mobile keys
    _mock_token_manager(monkeypatch)
    respx.get(f"{_BASE_URL}/me/user").mock(
        return_value=httpx.Response(
            200,
            json={"email": "coach@example.com", "first_name": "Jason", "last_name": "Smith"},
        )
    )
    exit_code, message = check_credentials()
    assert exit_code == 0
    assert "web" in message
    assert "mobile" in message


def test_multi_profile_both_missing_returns_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exit 1 when all profiles fail (AC-4)."""
    _patch_dotenv(monkeypatch, {})
    exit_code, message = check_credentials()
    assert exit_code == 1
    assert "web" in message
    assert "mobile" in message


def test_multi_profile_summary_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """Summary output shows per-profile status (AC-3)."""
    _patch_dotenv(monkeypatch, {})
    _, message = check_credentials()
    assert "Credential status:" in message
    assert "web" in message
    assert "mobile" in message
