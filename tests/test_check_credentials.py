# synthetic-test-data
"""Unit tests for scripts/check_credentials.py.

All HTTP calls are mocked -- no real network requests are made.
Credentials are injected via monkeypatching dotenv_values.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from scripts.check_credentials import check_credentials

_FAKE_CREDENTIALS = {
    "GAMECHANGER_AUTH_TOKEN": "fake-jwt-token",
    "GAMECHANGER_DEVICE_ID": "abcdef1234567890abcdef1234567890",
    "GAMECHANGER_BASE_URL": "https://api.team-manager.gc.com",
}

_BASE_URL = "https://api.team-manager.gc.com"


def _patch_dotenv(monkeypatch: pytest.MonkeyPatch, values: dict) -> None:
    """Patch dotenv_values in both the client module and the check_credentials module."""
    monkeypatch.setattr("src.gamechanger.client.dotenv_values", lambda: values)
    monkeypatch.setattr("scripts.check_credentials.dotenv_values", lambda: values)


# ---------------------------------------------------------------------------
# AC-2: Missing credentials -- exit 2
# ---------------------------------------------------------------------------


def test_missing_all_credentials_returns_exit_2(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_dotenv(monkeypatch, {})
    exit_code, message = check_credentials()
    assert exit_code == 2
    assert "GAMECHANGER_AUTH_TOKEN" in message
    assert "GAMECHANGER_DEVICE_ID" in message
    assert "GAMECHANGER_BASE_URL" in message


def test_missing_one_credential_returns_exit_2(monkeypatch: pytest.MonkeyPatch) -> None:
    partial = {k: v for k, v in _FAKE_CREDENTIALS.items() if k != "GAMECHANGER_AUTH_TOKEN"}
    _patch_dotenv(monkeypatch, partial)
    exit_code, message = check_credentials()
    assert exit_code == 2
    assert "GAMECHANGER_AUTH_TOKEN" in message


def test_missing_credentials_message_never_reveals_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-8: credential values must not appear in output."""
    partial = {
        "GAMECHANGER_AUTH_TOKEN": "super-secret-token",
        "GAMECHANGER_DEVICE_ID": "secret-device",
        # GAMECHANGER_BASE_URL is absent
    }
    _patch_dotenv(monkeypatch, partial)
    exit_code, message = check_credentials()
    assert exit_code == 2
    assert "super-secret-token" not in message
    assert "secret-device" not in message


# ---------------------------------------------------------------------------
# AC-4: Valid credentials -- exit 0
# ---------------------------------------------------------------------------


@respx.mock
def test_valid_credentials_with_full_name_returns_exit_0(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_dotenv(monkeypatch, _FAKE_CREDENTIALS)
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
    exit_code, message = check_credentials()
    assert exit_code == 0
    assert "Jason Smith" in message
    assert "valid" in message.lower()


@respx.mock
def test_valid_credentials_falls_back_to_email_when_names_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_dotenv(monkeypatch, _FAKE_CREDENTIALS)
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
    exit_code, message = check_credentials()
    assert exit_code == 0
    assert "coach@example.com" in message


@respx.mock
def test_valid_credentials_message_does_not_reveal_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-8: token value must not appear in success output."""
    _patch_dotenv(monkeypatch, _FAKE_CREDENTIALS)
    respx.get(f"{_BASE_URL}/me/user").mock(
        return_value=httpx.Response(
            200,
            json={"email": "coach@example.com", "first_name": "Jason", "last_name": "Smith"},
        )
    )
    exit_code, message = check_credentials()
    assert exit_code == 0
    assert "fake-jwt-token" not in message
    assert "abcdef1234567890abcdef1234567890" not in message


# ---------------------------------------------------------------------------
# AC-5: Expired credentials (401) -- exit 1
# ---------------------------------------------------------------------------


@respx.mock
def test_expired_credentials_401_returns_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_dotenv(monkeypatch, _FAKE_CREDENTIALS)
    respx.get(f"{_BASE_URL}/me/user").mock(
        return_value=httpx.Response(401, json={"error": "unauthorized"})
    )
    exit_code, message = check_credentials()
    assert exit_code == 1
    assert "expired" in message.lower()


# ---------------------------------------------------------------------------
# AC-6: Forbidden (403) -- exit 1
# ---------------------------------------------------------------------------


@respx.mock
def test_forbidden_403_returns_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_dotenv(monkeypatch, _FAKE_CREDENTIALS)
    respx.get(f"{_BASE_URL}/me/user").mock(
        return_value=httpx.Response(403, json={"error": "forbidden"})
    )
    exit_code, message = check_credentials()
    assert exit_code == 1
    assert "denied" in message.lower() or "expired" in message.lower()


# ---------------------------------------------------------------------------
# AC-7: Network errors -- exit 1
# ---------------------------------------------------------------------------


@respx.mock
def test_network_timeout_returns_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_dotenv(monkeypatch, _FAKE_CREDENTIALS)
    respx.get(f"{_BASE_URL}/me/user").mock(side_effect=httpx.TimeoutException("timed out"))
    exit_code, message = check_credentials()
    assert exit_code == 1
    assert "network" in message.lower() or "error" in message.lower()


@respx.mock
def test_connect_error_returns_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_dotenv(monkeypatch, _FAKE_CREDENTIALS)
    respx.get(f"{_BASE_URL}/me/user").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    exit_code, message = check_credentials()
    assert exit_code == 1
    assert "network" in message.lower() or "error" in message.lower()
