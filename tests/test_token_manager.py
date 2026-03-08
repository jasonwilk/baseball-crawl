"""Tests for src/gamechanger/token_manager.py -- TokenManager class.  # synthetic-test-data"""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from src.gamechanger.client import ConfigurationError, CredentialExpiredError
from src.gamechanger.token_manager import AuthSigningError, TokenManager


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_CLIENT_KEY_B64 = base64.b64encode(b"K" * 32).decode()
_CLIENT_ID = "07cb985d-ff6c-429d-992c-b8a0d44e6fc3"
_REFRESH_TOKEN = "eyJREFRESH.token.payload"
_DEVICE_ID = "deadbeef" * 4
_BASE_URL = "https://api.team-manager.gc.com"
_AUTH_URL = f"{_BASE_URL}/auth"

_NOW = 1_700_000_000

# A token that expires 3600 seconds from _NOW.
_ACCESS_TOKEN = "eyJACCESS.token.payload"
_ACCESS_EXPIRES = _NOW + 3600
_NEW_REFRESH_TOKEN = "eyJNEW_REFRESH.token.payload"

_REFRESH_RESPONSE = {
    "type": "token",
    "access": {"data": _ACCESS_TOKEN, "expires": _ACCESS_EXPIRES},
    "refresh": {"data": _NEW_REFRESH_TOKEN, "expires": _NOW + 1_209_600},
}


def make_manager(tmp_env: Path, **kwargs: object) -> TokenManager:
    """Build a TokenManager with sensible defaults for web profile."""
    defaults: dict[str, object] = {
        "profile": "web",
        "client_id": _CLIENT_ID,
        "client_key": _CLIENT_KEY_B64,
        "refresh_token": _REFRESH_TOKEN,
        "device_id": _DEVICE_ID,
        "base_url": _BASE_URL,
        "env_path": tmp_env,
    }
    defaults.update(kwargs)
    return TokenManager(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AC-1: Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    def test_web_profile_requires_client_key(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="CLIENT_KEY"):
            TokenManager(
                profile="web",
                client_id=_CLIENT_ID,
                client_key=None,
                refresh_token=_REFRESH_TOKEN,
                device_id=_DEVICE_ID,
                base_url=_BASE_URL,
                env_path=tmp_path / ".env",
            )

    def test_web_profile_requires_client_id(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="CLIENT_ID"):
            TokenManager(
                profile="web",
                client_id=None,
                client_key=_CLIENT_KEY_B64,
                refresh_token=_REFRESH_TOKEN,
                device_id=_DEVICE_ID,
                base_url=_BASE_URL,
                env_path=tmp_path / ".env",
            )

    def test_web_profile_requires_refresh_token(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="REFRESH_TOKEN"):
            TokenManager(
                profile="web",
                client_id=_CLIENT_ID,
                client_key=_CLIENT_KEY_B64,
                refresh_token=None,
                device_id=_DEVICE_ID,
                base_url=_BASE_URL,
                env_path=tmp_path / ".env",
            )

    def test_mobile_no_key_no_manual_token_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="GAMECHANGER_ACCESS_TOKEN_MOBILE"):
            TokenManager(
                profile="mobile",
                client_id=_CLIENT_ID,
                client_key=None,
                refresh_token=_REFRESH_TOKEN,
                device_id=_DEVICE_ID,
                base_url=_BASE_URL,
                env_path=tmp_path / ".env",
            )

    def test_mobile_no_key_with_manual_token_succeeds(self, tmp_path: Path) -> None:
        tm = TokenManager(
            profile="mobile",
            client_id=_CLIENT_ID,
            client_key=None,
            refresh_token=None,
            device_id=_DEVICE_ID,
            base_url=_BASE_URL,
            access_token="manual-access-token",
            env_path=tmp_path / ".env",
        )
        assert tm.get_access_token() == "manual-access-token"


# ---------------------------------------------------------------------------
# AC-2: get_access_token -- refresh on first call, cache on subsequent
# ---------------------------------------------------------------------------


class TestGetAccessToken:
    @respx.mock
    def test_first_call_triggers_refresh(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, json=_REFRESH_RESPONSE)
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager(env)
            token = tm.get_access_token()

        assert token == _ACCESS_TOKEN

    @respx.mock
    def test_second_call_uses_cache(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, json=_REFRESH_RESPONSE)
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager(env)
            tm.get_access_token()  # triggers real refresh
            # Only one HTTP call should have been made
            call_count_after_first = len(respx.calls)
            tm.get_access_token()  # should use cache
            call_count_after_second = len(respx.calls)

        assert call_count_after_first == 1
        assert call_count_after_second == 1  # no new call

    @respx.mock
    def test_expired_token_triggers_re_refresh(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, json=_REFRESH_RESPONSE)
        )
        # First call at _NOW sets expiry to _NOW + 3600.
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager(env)
            tm.get_access_token()

        assert len(respx.calls) == 1

        # Second call well past expiry (and safety margin) should re-refresh.
        future = float(_ACCESS_EXPIRES + 1000)
        with patch("src.gamechanger.token_manager.time.time", return_value=future):
            tm.get_access_token()

        assert len(respx.calls) == 2

    @respx.mock
    def test_token_within_safety_margin_triggers_re_refresh(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, json=_REFRESH_RESPONSE)
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager(env)
            tm.get_access_token()

        # Call at 4 minutes before expiry (within the 5-minute safety margin).
        within_margin = float(_ACCESS_EXPIRES - 240)
        with patch("src.gamechanger.token_manager.time.time", return_value=within_margin):
            tm.get_access_token()

        assert len(respx.calls) == 2


# ---------------------------------------------------------------------------
# AC-3: .env write-back
# ---------------------------------------------------------------------------


class TestEnvWriteBack:
    @respx.mock
    def test_new_refresh_token_written_to_env(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_text(
            f"GAMECHANGER_REFRESH_TOKEN_WEB={_REFRESH_TOKEN}\nOTHER=keep\n",
            encoding="utf-8",
        )
        respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, json=_REFRESH_RESPONSE)
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager(env)
            tm.get_access_token()

        content = env.read_text(encoding="utf-8")
        assert f"GAMECHANGER_REFRESH_TOKEN_WEB={_NEW_REFRESH_TOKEN}" in content
        assert "OTHER=keep" in content

    @respx.mock
    def test_env_write_is_atomic(self, tmp_path: Path) -> None:
        """Verify the new refresh token appears via atomic replace (no partial write)."""
        env = tmp_path / ".env"
        env.write_text(f"GAMECHANGER_REFRESH_TOKEN_WEB={_REFRESH_TOKEN}\n", encoding="utf-8")
        respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, json=_REFRESH_RESPONSE)
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager(env)
            tm.get_access_token()

        # File must exist and be complete (atomic_merge_env_file uses os.replace).
        assert env.exists()
        content = env.read_text(encoding="utf-8")
        assert _NEW_REFRESH_TOKEN in content

    @respx.mock
    def test_env_write_failure_logs_warning_and_returns_token(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, json=_REFRESH_RESPONSE)
        )
        with (
            patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)),
            patch(
                "src.gamechanger.token_manager.atomic_merge_env_file",
                side_effect=OSError(13, "Permission denied"),
            ),
            caplog.at_level("WARNING", logger="src.gamechanger.token_manager"),
        ):
            tm = make_manager(env)
            token = tm.get_access_token()

        assert token == _ACCESS_TOKEN
        warning_msgs = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert any("Failed to persist" in m for m in warning_msgs), (
            f"Expected warning about persistence failure; got: {warning_msgs}"
        )

    @respx.mock
    def test_env_write_failure_does_not_log_token_value(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, json=_REFRESH_RESPONSE)
        )
        with (
            patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)),
            patch(
                "src.gamechanger.token_manager.atomic_merge_env_file",
                side_effect=OSError(13, "Permission denied"),
            ),
            caplog.at_level("WARNING", logger="src.gamechanger.token_manager"),
        ):
            tm = make_manager(env)
            tm.get_access_token()

        for record in caplog.records:
            msg = record.getMessage()
            assert _NEW_REFRESH_TOKEN not in msg, f"Credential leaked into log: {msg}"
            assert _REFRESH_TOKEN not in msg, f"Credential leaked into log: {msg}"


# ---------------------------------------------------------------------------
# AC-4: Mobile fallback
# ---------------------------------------------------------------------------


class TestMobileFallback:
    def test_force_refresh_without_client_key_raises_auth_signing_error(
        self, tmp_path: Path
    ) -> None:
        """force_refresh() on mobile no-key profile raises AuthSigningError immediately."""
        manual_token = "eyJMANUAL.access.token"
        tm = TokenManager(
            profile="mobile",
            client_id=None,
            client_key=None,
            refresh_token=None,
            device_id=_DEVICE_ID,
            base_url=_BASE_URL,
            access_token=manual_token,
            env_path=tmp_path / ".env",
        )
        with pytest.raises(AuthSigningError, match="client key"):
            tm.force_refresh()

    def test_force_refresh_without_client_key_not_assertion_error(
        self, tmp_path: Path
    ) -> None:
        """force_refresh() on mobile no-key profile raises AuthSigningError, not AssertionError."""
        manual_token = "eyJMANUAL.access.token"
        tm = TokenManager(
            profile="mobile",
            client_id=None,
            client_key=None,
            refresh_token=None,
            device_id=_DEVICE_ID,
            base_url=_BASE_URL,
            access_token=manual_token,
            env_path=tmp_path / ".env",
        )
        try:
            tm.force_refresh()
            pytest.fail("Expected AuthSigningError to be raised")
        except AuthSigningError:
            pass  # expected
        except AssertionError:
            pytest.fail("force_refresh() raised AssertionError -- no-key guard missing")

    def test_manual_access_token_returned_directly(self, tmp_path: Path) -> None:
        manual_token = "eyJMANUAL.access.token"
        tm = TokenManager(
            profile="mobile",
            client_id=None,
            client_key=None,
            refresh_token=None,
            device_id=_DEVICE_ID,
            base_url=_BASE_URL,
            access_token=manual_token,
            env_path=tmp_path / ".env",
        )
        assert tm.get_access_token() == manual_token

    def test_mobile_no_key_no_manual_raises_with_helpful_message(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ConfigurationError) as exc_info:
            TokenManager(
                profile="mobile",
                client_id=None,
                client_key=None,
                refresh_token=None,
                device_id=_DEVICE_ID,
                base_url=_BASE_URL,
                access_token=None,
                env_path=tmp_path / ".env",
            )
        msg = str(exc_info.value)
        assert "GAMECHANGER_ACCESS_TOKEN_MOBILE" in msg


# ---------------------------------------------------------------------------
# AC-5: force_refresh
# ---------------------------------------------------------------------------


class TestForceRefresh:
    @respx.mock
    def test_force_refresh_calls_auth_even_if_token_valid(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, json=_REFRESH_RESPONSE)
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager(env)
            tm.get_access_token()  # populates cache (1 call)
            tm.force_refresh()      # should force a second call even with valid token

        assert len(respx.calls) == 2

    @respx.mock
    def test_force_refresh_returns_new_token(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        second_access = "eyJSECOND.access.token"
        second_response = {
            "type": "token",
            "access": {"data": second_access, "expires": _ACCESS_EXPIRES + 3600},
            "refresh": {"data": "eyJSECOND.refresh.token", "expires": _NOW + 1_209_600},
        }
        respx.post(_AUTH_URL).mock(
            side_effect=[
                httpx.Response(200, json=_REFRESH_RESPONSE),
                httpx.Response(200, json=second_response),
            ]
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager(env)
            tm.get_access_token()
            new_token = tm.force_refresh()

        assert new_token == second_access


# ---------------------------------------------------------------------------
# AC-6: POST /auth headers
# ---------------------------------------------------------------------------


class TestPostAuthHeaders:
    @respx.mock
    def test_web_profile_headers_present(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        route = respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, json=_REFRESH_RESPONSE)
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager(env)
            tm.get_access_token()

        req = route.calls[0].request
        assert req.headers.get("gc-device-id") == _DEVICE_ID
        assert req.headers.get("gc-app-name") == "web"
        assert req.headers.get("gc-app-version") == "0.0.0"
        assert req.headers.get("accept") == "*/*"
        assert req.headers.get("content-type", "").startswith("application/json")
        assert "gc-signature" in req.headers
        assert "gc-timestamp" in req.headers
        assert "gc-client-id" in req.headers
        assert req.headers.get("gc-client-id") == _CLIENT_ID
        assert req.headers.get("gc-token") == _REFRESH_TOKEN

    @respx.mock
    def test_mobile_profile_headers_use_vendor_content_type(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        route = respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, json=_REFRESH_RESPONSE)
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = TokenManager(
                profile="mobile",
                client_id=_CLIENT_ID,
                client_key=_CLIENT_KEY_B64,
                refresh_token=_REFRESH_TOKEN,
                device_id=_DEVICE_ID,
                base_url=_BASE_URL,
                env_path=env,
            )
            tm.get_access_token()

        req = route.calls[0].request
        assert "vnd.gc.com.post_eden_auth" in req.headers.get("content-type", "")
        assert req.headers.get("gc-app-version") == "2026.7.0.0"

    @respx.mock
    def test_gc_timestamp_not_cached_between_calls(self, tmp_path: Path) -> None:
        """Each refresh call must generate a fresh timestamp."""
        env = tmp_path / ".env"
        route = respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, json=_REFRESH_RESPONSE)
        )
        ts1, ts2 = _NOW, _NOW + 120

        with patch("src.gamechanger.token_manager.time.time", return_value=float(ts1)):
            tm = make_manager(env)
            tm.get_access_token()

        with patch("src.gamechanger.token_manager.time.time", return_value=float(ts2)):
            tm.force_refresh()

        req1 = route.calls[0].request
        req2 = route.calls[1].request
        # Timestamps in the signing headers come from the signing module (time.time at signing).
        # They must differ between the two calls.
        ts_header_1 = req1.headers.get("gc-timestamp")
        ts_header_2 = req2.headers.get("gc-timestamp")
        assert ts_header_1 != ts_header_2


# ---------------------------------------------------------------------------
# AC-7: No credential logging
# ---------------------------------------------------------------------------


class TestNoCredentialLogging:
    @respx.mock
    def test_access_token_not_logged(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(200, json=_REFRESH_RESPONSE)
        )
        with (
            patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)),
            caplog.at_level("DEBUG", logger="src.gamechanger.token_manager"),
        ):
            tm = make_manager(env)
            tm.get_access_token()

        for record in caplog.records:
            msg = record.getMessage()
            assert _ACCESS_TOKEN not in msg, f"Access token leaked into log: {msg}"
            assert _CLIENT_KEY_B64 not in msg, f"Client key leaked into log: {msg}"
            assert _REFRESH_TOKEN not in msg, f"Refresh token leaked into log: {msg}"
            assert _NEW_REFRESH_TOKEN not in msg, f"New refresh token leaked into log: {msg}"


# ---------------------------------------------------------------------------
# AC-8: Error handling (HTTP 400 and 401)
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @respx.mock
    def test_http_400_raises_auth_signing_error(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(400, text="Bad Request")
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager(env)
            with pytest.raises(AuthSigningError):
                tm.get_access_token()

    @respx.mock
    def test_http_400_does_not_raise_credential_expired_error(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(400, text="Bad Request")
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager(env)
            with pytest.raises(AuthSigningError):
                tm.get_access_token()
            # Verify it is NOT a CredentialExpiredError
            try:
                tm.force_refresh()
            except AuthSigningError:
                pass
            except CredentialExpiredError:
                pytest.fail("HTTP 400 should not raise CredentialExpiredError")

    @respx.mock
    def test_http_400_error_includes_server_timestamp_in_message(
        self, tmp_path: Path
    ) -> None:
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(
                400,
                text="Bad Request",
                headers={"gc-timestamp": "1700000999"},
            )
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager(env)
            with pytest.raises(AuthSigningError, match="1700000999"):
                tm.get_access_token()

    @respx.mock
    def test_http_401_raises_credential_expired_error(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(401, text="")
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager(env)
            with pytest.raises(CredentialExpiredError):
                tm.get_access_token()

    @respx.mock
    def test_http_401_does_not_raise_auth_signing_error(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(401, text="")
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager(env)
            with pytest.raises(CredentialExpiredError):
                tm.get_access_token()

    @respx.mock
    def test_http_400_non_json_body_handled_gracefully(self, tmp_path: Path) -> None:
        """Plain-text 400 body does not cause a JSON parse error."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(400, text="Bad Request")
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager(env)
            with pytest.raises(AuthSigningError):
                tm.get_access_token()
            # No JSON parse exception should be raised -- only AuthSigningError

    @respx.mock
    def test_http_401_empty_body_handled_gracefully(self, tmp_path: Path) -> None:
        """Empty 401 body does not cause a JSON parse error."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            return_value=httpx.Response(401, text="")
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager(env)
            with pytest.raises(CredentialExpiredError):
                tm.get_access_token()
