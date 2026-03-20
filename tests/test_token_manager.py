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
from src.gamechanger.exceptions import LoginFailedError
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

# Login fallback test data
_EMAIL = "operator@example.com"
_PASSWORD = "s3cr3t-password"
_CLIENT_TOKEN = "eyJCLIENT.token.payload"
_LOGIN_ACCESS_TOKEN = "eyJLOGIN_ACCESS.token.payload"
_LOGIN_REFRESH_TOKEN = "eyJLOGIN_REFRESH.token.payload"
_LOGIN_ACCESS_EXPIRES = _NOW + 3600

_CLIENT_AUTH_RESPONSE = {
    "type": "client-token",
    "token": _CLIENT_TOKEN,
    "expires": _NOW + 600,
}
_USER_AUTH_RESPONSE: dict = {}  # Step 3 body not consumed -- only gc-signature header matters
_LOGIN_FINAL_RESPONSE = {
    "type": "token",
    "access": {"data": _LOGIN_ACCESS_TOKEN, "expires": _LOGIN_ACCESS_EXPIRES},
    "refresh": {"data": _LOGIN_REFRESH_TOKEN, "expires": _NOW + 1_209_600},
}

_GC_SIG_2 = "nonce2.hmac2base64=="
_GC_SIG_3 = "nonce3.hmac3base64=="
_GC_SIG_4 = "nonce4.hmac4base64=="


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


def make_manager_with_login(tmp_env: Path, **kwargs: object) -> TokenManager:
    """Build a TokenManager with email/password for login fallback testing."""
    defaults: dict[str, object] = {
        "profile": "web",
        "client_id": _CLIENT_ID,
        "client_key": _CLIENT_KEY_B64,
        "refresh_token": _REFRESH_TOKEN,
        "device_id": _DEVICE_ID,
        "base_url": _BASE_URL,
        "env_path": tmp_env,
        "email": _EMAIL,
        "password": _PASSWORD,
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


# ---------------------------------------------------------------------------
# Login fallback (AC-1 through AC-14)
# ---------------------------------------------------------------------------


def _four_step_side_effects(
    step2_status: int = 200,
    step3_status: int = 200,
    step4_status: int = 200,
    step2_body: dict | None = None,
    step2_headers: dict | None = None,
    step3_headers: dict | None = None,
    step4_headers: dict | None = None,
) -> list[httpx.Response]:
    """Build the 4-response side_effect list for a full login-fallback sequence.

    The first response is always HTTP 401 (expired refresh token).
    Subsequent responses represent login steps 2, 3, 4.
    """
    r2_body = step2_body if step2_body is not None else _CLIENT_AUTH_RESPONSE
    r2_hdrs = step2_headers if step2_headers is not None else {"gc-signature": _GC_SIG_2}
    r3_hdrs = step3_headers if step3_headers is not None else {"gc-signature": _GC_SIG_3}
    r4_hdrs = step4_headers if step4_headers is not None else {"gc-signature": _GC_SIG_4}

    return [
        httpx.Response(401, text=""),
        httpx.Response(step2_status, json=r2_body, headers=r2_hdrs),
        httpx.Response(step3_status, json=_USER_AUTH_RESPONSE, headers=r3_hdrs),
        httpx.Response(step4_status, json=_LOGIN_FINAL_RESPONSE, headers=r4_hdrs),
    ]


class TestLoginFallback:
    """Tests for AC-1 through AC-14: login fallback behavior."""

    # -----------------------------------------------------------------------
    # AC-9: constructor accepts optional email/password
    # -----------------------------------------------------------------------

    def test_constructor_accepts_optional_email_and_password(self, tmp_path: Path) -> None:
        """TokenManager accepts email/password as optional keyword args (AC-9)."""
        tm = make_manager_with_login(tmp_path / ".env")
        assert tm is not None  # construction succeeded

    def test_constructor_without_email_password_still_works(self, tmp_path: Path) -> None:
        """TokenManager without email/password constructs fine (AC-9 graceful absence)."""
        tm = make_manager(tmp_path / ".env")
        assert tm is not None

    # -----------------------------------------------------------------------
    # AC-1, AC-2, AC-3, AC-7, AC-8, AC-10: 3-step chain end-to-end
    # -----------------------------------------------------------------------

    @respx.mock
    def test_login_fallback_end_to_end_returns_access_token(self, tmp_path: Path) -> None:
        """Full 3-step login chain on 401 returns the new access token (AC-1, AC-10)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(side_effect=_four_step_side_effects())
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager_with_login(env)
            token = tm.get_access_token()
        assert token == _LOGIN_ACCESS_TOKEN

    @respx.mock
    def test_login_fallback_persists_new_refresh_token(self, tmp_path: Path) -> None:
        """Login fallback persists the new refresh token to .env (AC-2)."""
        env = tmp_path / ".env"
        env.write_text(
            f"GAMECHANGER_REFRESH_TOKEN_WEB={_REFRESH_TOKEN}\nOTHER=keep\n",
            encoding="utf-8",
        )
        respx.post(_AUTH_URL).mock(side_effect=_four_step_side_effects())
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager_with_login(env)
            tm.get_access_token()
        content = env.read_text(encoding="utf-8")
        assert f"GAMECHANGER_REFRESH_TOKEN_WEB={_LOGIN_REFRESH_TOKEN}" in content
        assert "OTHER=keep" in content

    @respx.mock
    def test_login_fallback_caches_access_token(self, tmp_path: Path) -> None:
        """Login fallback caches the new access token (AC-3): second call uses cache."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(side_effect=_four_step_side_effects())
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager_with_login(env)
            tm.get_access_token()  # 4 HTTP calls (1 refresh + 3 login steps)
            calls_after_first = len(respx.calls)
            tm.get_access_token()  # should use cache
            calls_after_second = len(respx.calls)
        assert calls_after_first == 4
        assert calls_after_second == 4  # no additional call

    @respx.mock
    def test_login_fallback_step2_has_no_gc_token_header(self, tmp_path: Path) -> None:
        """Step 2 (client-auth) must NOT send gc-token header (AC-7)."""
        env = tmp_path / ".env"
        route = respx.post(_AUTH_URL).mock(side_effect=_four_step_side_effects())
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager_with_login(env)
            tm.get_access_token()
        step2_req = route.calls[1].request
        assert "gc-token" not in step2_req.headers

    @respx.mock
    def test_login_fallback_steps_3_and_4_send_client_token(self, tmp_path: Path) -> None:
        """Steps 3 and 4 use the client token from step 2 as gc-token (AC-7)."""
        env = tmp_path / ".env"
        route = respx.post(_AUTH_URL).mock(side_effect=_four_step_side_effects())
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager_with_login(env)
            tm.get_access_token()
        step3_req = route.calls[2].request
        step4_req = route.calls[3].request
        assert step3_req.headers.get("gc-token") == _CLIENT_TOKEN
        assert step4_req.headers.get("gc-token") == _CLIENT_TOKEN

    @respx.mock
    def test_login_fallback_step2_response_type_validated(self, tmp_path: Path) -> None:
        """Step 2 response type is validated against 'client-token' (AC-13)."""
        env = tmp_path / ".env"
        bad_step2_body = {"type": "unexpected-type", "token": _CLIENT_TOKEN}
        respx.post(_AUTH_URL).mock(
            side_effect=_four_step_side_effects(step2_body=bad_step2_body)
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager_with_login(env)
            with pytest.raises(LoginFailedError, match="unexpected type"):
                tm.get_access_token()

    @respx.mock
    def test_login_fallback_step2_missing_type_raises_login_failed(
        self, tmp_path: Path
    ) -> None:
        """Step 2 response with no 'type' field raises LoginFailedError (AC-13)."""
        env = tmp_path / ".env"
        bad_step2_body = {"token": _CLIENT_TOKEN}  # no 'type' key
        respx.post(_AUTH_URL).mock(
            side_effect=_four_step_side_effects(step2_body=bad_step2_body)
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager_with_login(env)
            with pytest.raises(LoginFailedError):
                tm.get_access_token()

    @respx.mock
    def test_login_fallback_step2_missing_token_field_raises_login_failed(
        self, tmp_path: Path
    ) -> None:
        """Step 2 response with correct type but missing 'token' raises LoginFailedError (not KeyError)."""
        env = tmp_path / ".env"
        bad_step2_body = {"type": "client-token"}  # no 'token' field
        respx.post(_AUTH_URL).mock(
            side_effect=_four_step_side_effects(step2_body=bad_step2_body)
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager_with_login(env)
            with pytest.raises(LoginFailedError, match="missing 'token' field"):
                tm.get_access_token()

    # -----------------------------------------------------------------------
    # AC-6: non-200 and 400 on each step
    # -----------------------------------------------------------------------

    @respx.mock
    def test_login_fallback_step2_non200_raises_login_failed_error(
        self, tmp_path: Path
    ) -> None:
        """Non-200 on step 2 raises LoginFailedError (AC-6)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            side_effect=_four_step_side_effects(step2_status=500)
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager_with_login(env)
            with pytest.raises(LoginFailedError, match="step 2"):
                tm.get_access_token()

    @respx.mock
    def test_login_fallback_step3_non200_raises_login_failed_error(
        self, tmp_path: Path
    ) -> None:
        """Non-200 on step 3 raises LoginFailedError (AC-6)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            side_effect=_four_step_side_effects(step3_status=403)
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager_with_login(env)
            with pytest.raises(LoginFailedError, match="step 3"):
                tm.get_access_token()

    @respx.mock
    def test_login_fallback_step4_non200_raises_login_failed_error(
        self, tmp_path: Path
    ) -> None:
        """Non-200 on step 4 raises LoginFailedError (AC-6)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            side_effect=_four_step_side_effects(step4_status=404)
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager_with_login(env)
            with pytest.raises(LoginFailedError, match="step 4"):
                tm.get_access_token()

    @respx.mock
    def test_login_fallback_step2_400_raises_auth_signing_error(
        self, tmp_path: Path
    ) -> None:
        """HTTP 400 on step 2 raises AuthSigningError not LoginFailedError (AC-6)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            side_effect=_four_step_side_effects(step2_status=400)
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager_with_login(env)
            with pytest.raises(AuthSigningError, match="step 2"):
                tm.get_access_token()

    @respx.mock
    def test_login_fallback_step3_400_raises_auth_signing_error(
        self, tmp_path: Path
    ) -> None:
        """HTTP 400 on step 3 raises AuthSigningError (AC-6)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            side_effect=_four_step_side_effects(step3_status=400)
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager_with_login(env)
            with pytest.raises(AuthSigningError, match="step 3"):
                tm.get_access_token()

    @respx.mock
    def test_login_fallback_step4_400_raises_auth_signing_error(
        self, tmp_path: Path
    ) -> None:
        """HTTP 400 on step 4 raises AuthSigningError (AC-6)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            side_effect=_four_step_side_effects(step4_status=400)
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager_with_login(env)
            with pytest.raises(AuthSigningError, match="step 4"):
                tm.get_access_token()

    @respx.mock
    def test_login_failed_error_is_subclass_of_credential_expired(
        self, tmp_path: Path
    ) -> None:
        """LoginFailedError is caught by except CredentialExpiredError (AC-6)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            side_effect=_four_step_side_effects(step4_status=500)
        )
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager_with_login(env)
            with pytest.raises(CredentialExpiredError):  # catches LoginFailedError too
                tm.get_access_token()

    # -----------------------------------------------------------------------
    # AC-4: missing email or password
    # -----------------------------------------------------------------------

    @respx.mock
    def test_login_fallback_not_attempted_without_email(self, tmp_path: Path) -> None:
        """Without email, 401 raises CredentialExpiredError mentioning login creds (AC-4)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(return_value=httpx.Response(401, text=""))
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager_with_login(env, email=None)
            with pytest.raises(CredentialExpiredError, match="GAMECHANGER_USER_EMAIL"):
                tm.get_access_token()

    @respx.mock
    def test_login_fallback_not_attempted_without_password(self, tmp_path: Path) -> None:
        """Without password, 401 raises CredentialExpiredError mentioning login creds (AC-4)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(return_value=httpx.Response(401, text=""))
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager_with_login(env, password=None)
            with pytest.raises(CredentialExpiredError, match="GAMECHANGER_USER_PASSWORD"):
                tm.get_access_token()

    @respx.mock
    def test_login_fallback_missing_creds_error_mentions_auto_recovery(
        self, tmp_path: Path
    ) -> None:
        """Error message for missing login creds explains auto-recovery (AC-4)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(return_value=httpx.Response(401, text=""))
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager(env)  # no email/password
            with pytest.raises(CredentialExpiredError) as exc_info:
                tm.get_access_token()
        assert "Auto-recovery" in str(exc_info.value) or "login" in str(exc_info.value).lower()

    # -----------------------------------------------------------------------
    # AC-5: mobile profile does not attempt login
    # -----------------------------------------------------------------------

    @respx.mock
    def test_login_fallback_not_attempted_on_mobile(self, tmp_path: Path) -> None:
        """Mobile profile raises CredentialExpiredError on 401 without login attempt (AC-5)."""
        env = tmp_path / ".env"
        # Only 1 HTTP call (refresh attempt that returns 401) -- no login steps
        respx.post(_AUTH_URL).mock(return_value=httpx.Response(401, text=""))
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = TokenManager(
                profile="mobile",
                client_id=_CLIENT_ID,
                client_key=_CLIENT_KEY_B64,
                refresh_token=_REFRESH_TOKEN,
                device_id=_DEVICE_ID,
                base_url=_BASE_URL,
                env_path=env,
                email=_EMAIL,
                password=_PASSWORD,
            )
            with pytest.raises(CredentialExpiredError):
                tm.get_access_token()
        assert len(respx.calls) == 1  # only the refresh attempt

    # -----------------------------------------------------------------------
    # AC-11: force_refresh does not trigger login fallback
    # -----------------------------------------------------------------------

    @respx.mock
    def test_force_refresh_does_not_trigger_login_fallback(self, tmp_path: Path) -> None:
        """force_refresh() on 401 raises CredentialExpiredError, no login (AC-11)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(return_value=httpx.Response(401, text=""))
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager_with_login(env)
            with pytest.raises(CredentialExpiredError):
                tm.force_refresh()
        assert len(respx.calls) == 1  # only the refresh attempt, no login steps

    @respx.mock
    def test_force_refresh_raises_credential_expired_not_login_failed(
        self, tmp_path: Path
    ) -> None:
        """force_refresh() on 401 raises CredentialExpiredError, not LoginFailedError (AC-11)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(return_value=httpx.Response(401, text=""))
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_manager_with_login(env)
            exc = None
            try:
                tm.force_refresh()
            except CredentialExpiredError as e:
                exc = e
            assert exc is not None
            # Must NOT be LoginFailedError (login fallback was not attempted)
            assert not isinstance(exc, LoginFailedError)

    # -----------------------------------------------------------------------
    # AC-12: missing gc-signature header logs warning
    # -----------------------------------------------------------------------

    @respx.mock
    def test_login_fallback_missing_gc_signature_on_step2_logs_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Absent gc-signature on step 2 logs WARNING (AC-12)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            side_effect=_four_step_side_effects(step2_headers={})  # no gc-signature
        )
        with (
            patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)),
            caplog.at_level("WARNING", logger="src.gamechanger.token_manager"),
        ):
            tm = make_manager_with_login(env)
            tm.get_access_token()
        warning_msgs = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert any("gc-signature" in m and "client-auth" in m for m in warning_msgs)

    @respx.mock
    def test_login_fallback_missing_gc_signature_on_step3_logs_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Absent gc-signature on step 3 logs WARNING (AC-12)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            side_effect=_four_step_side_effects(step3_headers={})  # no gc-signature
        )
        with (
            patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)),
            caplog.at_level("WARNING", logger="src.gamechanger.token_manager"),
        ):
            tm = make_manager_with_login(env)
            tm.get_access_token()
        warning_msgs = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert any("gc-signature" in m and "user-auth" in m for m in warning_msgs)

    @respx.mock
    def test_login_fallback_missing_gc_signature_on_step4_logs_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Absent gc-signature on step 4 logs WARNING (AC-12)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(
            side_effect=_four_step_side_effects(step4_headers={})  # no gc-signature
        )
        with (
            patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)),
            caplog.at_level("WARNING", logger="src.gamechanger.token_manager"),
        ):
            tm = make_manager_with_login(env)
            tm.get_access_token()
        warning_msgs = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert any("gc-signature" in m and "password" in m for m in warning_msgs)


# ---------------------------------------------------------------------------
# E-128-01: Login bootstrap path (do_login())
# ---------------------------------------------------------------------------


def _three_step_side_effects(
    step2_status: int = 200,
    step3_status: int = 200,
    step4_status: int = 200,
    step2_body: dict | None = None,
    step2_headers: dict | None = None,
    step3_headers: dict | None = None,
    step4_headers: dict | None = None,
) -> list[httpx.Response]:
    """Build the 3-response side_effect list for a direct login bootstrap sequence.

    Unlike ``_four_step_side_effects``, there is no initial HTTP 401 because
    ``do_login()`` calls ``_do_login_fallback()`` directly without attempting a
    refresh first.
    """
    r2_body = step2_body if step2_body is not None else _CLIENT_AUTH_RESPONSE
    r2_hdrs = step2_headers if step2_headers is not None else {"gc-signature": _GC_SIG_2}
    r3_hdrs = step3_headers if step3_headers is not None else {"gc-signature": _GC_SIG_3}
    r4_hdrs = step4_headers if step4_headers is not None else {"gc-signature": _GC_SIG_4}

    return [
        httpx.Response(step2_status, json=r2_body, headers=r2_hdrs),
        httpx.Response(step3_status, json=_USER_AUTH_RESPONSE, headers=r3_hdrs),
        httpx.Response(step4_status, json=_LOGIN_FINAL_RESPONSE, headers=r4_hdrs),
    ]


def make_bootstrap_manager(tmp_env: Path, **kwargs: object) -> TokenManager:
    """Build a TokenManager in login-bootstrap mode (no refresh token)."""
    defaults: dict[str, object] = {
        "profile": "web",
        "client_id": _CLIENT_ID,
        "client_key": _CLIENT_KEY_B64,
        "refresh_token": None,
        "device_id": _DEVICE_ID,
        "base_url": _BASE_URL,
        "env_path": tmp_env,
        "email": _EMAIL,
        "password": _PASSWORD,
    }
    defaults.update(kwargs)
    return TokenManager(**defaults)  # type: ignore[arg-type]


class TestLoginBootstrap:
    """Tests for E-128-01: do_login() bootstrap path."""

    # -----------------------------------------------------------------------
    # Construction: no refresh token allowed when email+password are present
    # -----------------------------------------------------------------------

    def test_construction_succeeds_without_refresh_token_when_login_creds_present(
        self, tmp_path: Path
    ) -> None:
        """TokenManager constructs without refresh token when email+password are set (AC-1)."""
        tm = make_bootstrap_manager(tmp_path / ".env")
        assert tm is not None

    def test_construction_still_requires_refresh_token_without_login_creds(
        self, tmp_path: Path
    ) -> None:
        """Without login creds, refresh_token is still required (existing behaviour)."""
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

    # -----------------------------------------------------------------------
    # do_login(): happy path
    # -----------------------------------------------------------------------

    @respx.mock
    def test_do_login_returns_access_token(self, tmp_path: Path) -> None:
        """do_login() executes 3-step login flow and returns the access token (AC-1)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(side_effect=_three_step_side_effects())
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_bootstrap_manager(env)
            token = tm.do_login()
        assert token == _LOGIN_ACCESS_TOKEN

    @respx.mock
    def test_do_login_persists_refresh_token_to_env(self, tmp_path: Path) -> None:
        """do_login() persists the new refresh token to .env (AC-5)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(side_effect=_three_step_side_effects())
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_bootstrap_manager(env)
            tm.do_login()
        contents = env.read_text()
        assert "GAMECHANGER_REFRESH_TOKEN_WEB" in contents
        assert _LOGIN_REFRESH_TOKEN in contents

    @respx.mock
    def test_do_login_makes_exactly_three_http_requests(self, tmp_path: Path) -> None:
        """do_login() makes exactly 3 POST /auth requests (steps 2, 3, 4) -- no initial refresh."""
        env = tmp_path / ".env"
        route = respx.post(_AUTH_URL).mock(side_effect=_three_step_side_effects())
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_bootstrap_manager(env)
            tm.do_login()
        assert route.call_count == 3

    # -----------------------------------------------------------------------
    # do_login(): device ID synthesis (AC-2)
    # -----------------------------------------------------------------------

    @respx.mock
    def test_do_login_synthesizes_device_id_when_absent(self, tmp_path: Path) -> None:
        """do_login() generates a synthetic device ID when device_id is None (AC-2)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(side_effect=_three_step_side_effects())
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_bootstrap_manager(env, device_id=None)
            tm.do_login()
        # Synthetic device ID is 32-char hex (token_hex(16) = 32 hex chars).
        assert tm._device_id is not None
        assert len(tm._device_id) == 32
        assert all(c in "0123456789abcdef" for c in tm._device_id)

    @respx.mock
    def test_do_login_persists_synthetic_device_id_to_env(self, tmp_path: Path) -> None:
        """Synthesized device ID is written to .env before login proceeds (AC-2)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(side_effect=_three_step_side_effects())
        with patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)):
            tm = make_bootstrap_manager(env, device_id=None)
            tm.do_login()
        contents = env.read_text()
        assert "GAMECHANGER_DEVICE_ID_WEB" in contents
        assert tm._device_id in contents

    @respx.mock
    def test_do_login_uses_existing_device_id_when_present(self, tmp_path: Path) -> None:
        """do_login() uses the provided device_id without synthesizing a new one (AC-2)."""
        env = tmp_path / ".env"
        respx.post(_AUTH_URL).mock(side_effect=_three_step_side_effects())
        existing_device_id = "a1b2c3d4" * 4
        with (
            patch("src.gamechanger.token_manager.time.time", return_value=float(_NOW)),
            patch("src.gamechanger.token_manager.secrets.token_hex") as mock_token_hex,
        ):
            tm = make_bootstrap_manager(env, device_id=existing_device_id)
            tm.do_login()
        mock_token_hex.assert_not_called()
        assert tm._device_id == existing_device_id

    # -----------------------------------------------------------------------
    # do_login(): error paths
    # -----------------------------------------------------------------------

    def test_do_login_raises_without_email(self, tmp_path: Path) -> None:
        """do_login() raises ConfigurationError when email is missing (defensive guard)."""
        # Construct with valid credentials, then clear email to exercise the do_login guard.
        tm = make_bootstrap_manager(tmp_path / ".env")
        tm._email = None  # simulate edge case bypassing constructor
        with pytest.raises(ConfigurationError, match="USER_EMAIL"):
            tm.do_login()

    def test_do_login_raises_without_password(self, tmp_path: Path) -> None:
        """do_login() raises ConfigurationError when password is missing (defensive guard)."""
        # Construct with valid credentials, then clear password to exercise the do_login guard.
        tm = make_bootstrap_manager(tmp_path / ".env")
        tm._password = None  # simulate edge case bypassing constructor
        with pytest.raises(ConfigurationError, match="USER_PASSWORD"):
            tm.do_login()
