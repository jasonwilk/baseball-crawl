"""Unit tests for proxy/addons/credential_extractor.py.

Tests use mock flow objects rather than a live mitmproxy instance.
All .env writes are patched so no real files are created.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from proxy.addons.credential_extractor import CredentialExtractor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_flow(host: str, headers: dict[str, str]) -> MagicMock:
    """Return a minimal mock mitmproxy HTTPFlow."""
    flow = MagicMock()
    flow.request.host = host
    flow.request.headers = headers
    return flow


# ---------------------------------------------------------------------------
# Domain filtering
# ---------------------------------------------------------------------------


class TestDomainFiltering:
    def test_non_gc_domain_is_ignored(self) -> None:
        """Requests to non-GameChanger hosts must not trigger any write."""
        extractor = CredentialExtractor()
        flow = _make_flow("google.com", {"gc-token": "abc123"})

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        mock_merge.assert_not_called()

    def test_gc_com_subdomain_is_processed(self) -> None:
        """Requests to *.gc.com must be processed."""
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {"gc-token": "tok1", "user-agent": "Chrome/120"},
        )

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        mock_merge.assert_called_once()

    def test_gamechanger_com_subdomain_processes_known_source(self) -> None:
        """Requests to *.gamechanger.com with known source are processed."""
        extractor = CredentialExtractor()
        flow = _make_flow(
            "app.gamechanger.com",
            {"gc-token": "tok2", "user-agent": "Chrome/120"},
        )

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        mock_merge.assert_called_once()


# ---------------------------------------------------------------------------
# Source-based profile routing (AC-1, AC-2, AC-3)
# ---------------------------------------------------------------------------


class TestWebSourcePath:
    """AC-1: Web browser traffic writes to _WEB suffixed keys."""

    def test_web_token_writes_to_web_key(self) -> None:
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {"gc-token": "jwt.web.tok", "user-agent": "Mozilla/5.0 Chrome/120.0.0.0"},
        )

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        credentials = mock_merge.call_args[0][1]
        assert credentials["GAMECHANGER_REFRESH_TOKEN_WEB"] == "jwt.web.tok"
        assert "GAMECHANGER_REFRESH_TOKEN" not in credentials

    def test_web_device_id_writes_to_web_key(self) -> None:
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {
                "gc-token": "tok",
                "gc-device-id": "device-web",
                "user-agent": "Chrome/120",
            },
        )

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        credentials = mock_merge.call_args[0][1]
        assert credentials["GAMECHANGER_DEVICE_ID_WEB"] == "device-web"

    def test_web_three_credentials_use_web_suffix(self) -> None:
        """gc-token, gc-device-id, gc-app-name are captured; gc-signature is NOT (computed at runtime)."""
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {
                "gc-token": "jwt.tok",
                "gc-device-id": "dev-id",
                "gc-app-name": "appname",
                "gc-signature": "sigvalue",  # present in traffic but not captured
                "user-agent": "Chrome/120",
            },
        )

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        credentials = mock_merge.call_args[0][1]
        assert credentials["GAMECHANGER_REFRESH_TOKEN_WEB"] == "jwt.tok"
        assert credentials["GAMECHANGER_DEVICE_ID_WEB"] == "dev-id"
        assert credentials["GAMECHANGER_APP_NAME_WEB"] == "appname"
        # gc-signature is no longer captured -- computed at runtime from CLIENT_KEY
        assert "GAMECHANGER_SIGNATURE_WEB" not in credentials
        # No unsuffixed keys
        assert "GAMECHANGER_REFRESH_TOKEN" not in credentials
        assert "GAMECHANGER_DEVICE_ID" not in credentials


class TestIosSourcePath:
    """AC-2: iOS app traffic writes to _MOBILE suffixed keys."""

    def test_ios_token_writes_to_mobile_key(self) -> None:
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {
                "gc-token": "jwt.mobile.tok",
                "user-agent": "Odyssey/2026.7.0 (com.gc.teammanager; build:0; iOS 26.3.0) Alamofire/5.9.0",
            },
        )

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        credentials = mock_merge.call_args[0][1]
        assert credentials["GAMECHANGER_REFRESH_TOKEN_MOBILE"] == "jwt.mobile.tok"
        assert "GAMECHANGER_REFRESH_TOKEN" not in credentials

    def test_ios_cfnetwork_writes_to_mobile_key(self) -> None:
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {
                "gc-token": "jwt.cfnet.tok",
                "gc-device-id": "mobile-device",
                "user-agent": "GameChanger/5.0 CFNetwork/1408.0.4 Darwin/22.5.0",
            },
        )

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        credentials = mock_merge.call_args[0][1]
        assert credentials["GAMECHANGER_REFRESH_TOKEN_MOBILE"] == "jwt.cfnet.tok"
        assert credentials["GAMECHANGER_DEVICE_ID_MOBILE"] == "mobile-device"


class TestUnknownSourcePath:
    """AC-3: Unknown traffic source logs WARNING and does NOT write credentials."""

    def test_unknown_ua_does_not_write(self) -> None:
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {"gc-token": "tok", "user-agent": "curl/7.81.0"},
        )

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        mock_merge.assert_not_called()

    def test_unknown_ua_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {"gc-token": "tok", "user-agent": "python-requests/2.31.0"},
        )

        with patch("proxy.addons.credential_extractor.merge_env_file"):
            with caplog.at_level("WARNING", logger="proxy.addons.credential_extractor"):
                extractor.request(flow)

        assert any(r.levelno >= 30 for r in caplog.records)  # WARNING level

    def test_empty_ua_does_not_write(self) -> None:
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {"gc-token": "tok", "user-agent": ""},
        )

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        mock_merge.assert_not_called()


# ---------------------------------------------------------------------------
# No credential headers present
# ---------------------------------------------------------------------------


class TestNoCredentials:
    def test_no_credential_headers_does_not_write(self) -> None:
        """A GC request with no credential headers triggers no .env write."""
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {"user-agent": "Chrome/120", "accept": "application/json"},
        )

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        mock_merge.assert_not_called()


# ---------------------------------------------------------------------------
# Deduplication (AC-5: cache keyed by suffixed names)
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_duplicate_web_token_does_not_trigger_second_write(self) -> None:
        """If the web token value is unchanged, merge_env_file is only called once."""
        extractor = CredentialExtractor()
        headers = {"gc-token": "same-token", "user-agent": "Chrome/120"}
        flow1 = _make_flow("api.gc.com", headers)
        flow2 = _make_flow("api.gc.com", headers)

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow1)
            extractor.request(flow2)

        assert mock_merge.call_count == 1

    def test_web_and_mobile_tokens_tracked_independently(self) -> None:
        """Web and mobile credentials are cached under different keys."""
        extractor = CredentialExtractor()
        web_flow = _make_flow("api.gc.com", {"gc-token": "tok", "user-agent": "Chrome/120"})
        ios_flow = _make_flow("api.gc.com", {"gc-token": "tok", "user-agent": "CFNetwork/1408"})

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(web_flow)   # writes GAMECHANGER_REFRESH_TOKEN_WEB=tok
            extractor.request(ios_flow)   # writes GAMECHANGER_REFRESH_TOKEN_MOBILE=tok (different key)

        # Both should have triggered a write (different env keys)
        assert mock_merge.call_count == 2

    def test_changed_token_triggers_second_write(self) -> None:
        """A new token value causes a second .env write."""
        extractor = CredentialExtractor()

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(
                _make_flow("api.gc.com", {"gc-token": "token-v1", "user-agent": "Chrome/120"})
            )
            extractor.request(
                _make_flow("api.gc.com", {"gc-token": "token-v2", "user-agent": "Chrome/120"})
            )

        assert mock_merge.call_count == 2

    def test_partial_new_header_triggers_write(self) -> None:
        """Adding a new header key (not just changing a value) triggers a write."""
        extractor = CredentialExtractor()

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            # First request: only gc-token
            extractor.request(
                _make_flow("api.gc.com", {"gc-token": "tok", "user-agent": "Chrome/120"})
            )
            # Second request: gc-token same value, but gc-device-id newly present
            extractor.request(
                _make_flow(
                    "api.gc.com",
                    {"gc-token": "tok", "gc-device-id": "new-device", "user-agent": "Chrome/120"},
                )
            )

        assert mock_merge.call_count == 2


# ---------------------------------------------------------------------------
# Source and key names logged (AC-6)
# ---------------------------------------------------------------------------


class TestSourceLogging:
    def test_ios_source_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """iOS traffic source is included in the log message."""
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {
                "gc-token": "tok",
                "user-agent": "GameChanger/5.0 CFNetwork/1408.0.4 Darwin/22.5.0",
            },
        )

        with patch("proxy.addons.credential_extractor.merge_env_file"):
            with caplog.at_level("INFO", logger="proxy.addons.credential_extractor"):
                extractor.request(flow)

        assert "ios" in caplog.text

    def test_web_source_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """Web traffic source is included in the log message."""
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {
                "gc-token": "tok",
                "user-agent": "Mozilla/5.0 Chrome/120.0.0.0",
            },
        )

        with patch("proxy.addons.credential_extractor.merge_env_file"):
            with caplog.at_level("INFO", logger="proxy.addons.credential_extractor"):
                extractor.request(flow)

        assert "web" in caplog.text

    def test_suffixed_key_names_logged_not_values(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Log output contains suffixed key names but not credential values."""
        token_value = "super-secret-jwt-token-do-not-log"
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {"gc-token": token_value, "user-agent": "Chrome/120"},
        )

        with patch("proxy.addons.credential_extractor.merge_env_file"):
            with caplog.at_level("INFO", logger="proxy.addons.credential_extractor"):
                extractor.request(flow)

        assert "GAMECHANGER_REFRESH_TOKEN_WEB" in caplog.text
        assert token_value not in caplog.text


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_os_error_on_write_does_not_raise(self) -> None:
        """An OSError from merge_env_file is caught and logged without crashing."""
        extractor = CredentialExtractor()
        flow = _make_flow("api.gc.com", {"gc-token": "tok", "user-agent": "Chrome/120"})

        with patch(
            "proxy.addons.credential_extractor.merge_env_file",
            side_effect=OSError("permission denied"),
        ):
            # Should not raise.
            extractor.request(flow)

    def test_cache_not_updated_on_write_failure(self) -> None:
        """If the write fails, the cache is not updated, so next request retries."""
        extractor = CredentialExtractor()
        flow1 = _make_flow("api.gc.com", {"gc-token": "tok", "user-agent": "Chrome/120"})
        flow2 = _make_flow("api.gc.com", {"gc-token": "tok", "user-agent": "Chrome/120"})

        # First call fails.
        with patch(
            "proxy.addons.credential_extractor.merge_env_file",
            side_effect=OSError("disk full"),
        ):
            extractor.request(flow1)

        # Second call should retry (cache not updated after failure).
        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow2)

        mock_merge.assert_called_once()


# ---------------------------------------------------------------------------
# gc-client-id capture (AC-1)
# ---------------------------------------------------------------------------


class TestClientIdCapture:
    def test_ios_client_id_writes_to_mobile_key(self) -> None:
        """gc-client-id from iOS traffic is written to GAMECHANGER_CLIENT_ID_MOBILE."""
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {
                "gc-client-id": "mobile-client-uuid",
                "gc-token": "tok",
                "user-agent": "GameChanger/5.0 CFNetwork/1408 Darwin/22.5.0",
            },
        )

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        credentials = mock_merge.call_args[0][1]
        assert credentials["GAMECHANGER_CLIENT_ID_MOBILE"] == "mobile-client-uuid"

    def test_web_client_id_writes_to_web_key(self) -> None:
        """gc-client-id from web traffic is written to GAMECHANGER_CLIENT_ID_WEB."""
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {
                "gc-client-id": "web-client-uuid",
                "gc-token": "tok",
                "user-agent": "Chrome/120",
            },
        )

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        credentials = mock_merge.call_args[0][1]
        assert credentials["GAMECHANGER_CLIENT_ID_WEB"] == "web-client-uuid"

    def test_client_id_deduplication(self) -> None:
        """Same gc-client-id value does not trigger a second write."""
        extractor = CredentialExtractor()
        headers = {
            "gc-client-id": "client-uuid",
            "gc-token": "tok",
            "user-agent": "Chrome/120",
        }

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(_make_flow("api.gc.com", headers))
            extractor.request(_make_flow("api.gc.com", headers))

        assert mock_merge.call_count == 1


# ---------------------------------------------------------------------------
# Response handler: POST /auth token capture (AC-2, AC-3, AC-4, AC-5, AC-6, AC-7)
# ---------------------------------------------------------------------------


def _make_response_flow(
    host: str,
    method: str,
    path: str,
    user_agent: str,
    response_body: dict | None = None,
    response_content: bytes | None = None,
) -> MagicMock:
    """Return a minimal mock mitmproxy HTTPFlow with request + response."""
    import json as _json

    flow = MagicMock()
    flow.request.host = host
    flow.request.method = method
    flow.request.path = path
    flow.request.headers = {"user-agent": user_agent}

    if response_content is not None:
        flow.response.content = response_content
    elif response_body is not None:
        flow.response.content = _json.dumps(response_body).encode()
    else:
        flow.response.content = b"{}"

    return flow


_TOKEN_RESPONSE = {
    "type": "token",
    "access": {"data": "access.jwt.value", "expires": 9999},
    "refresh": {"data": "refresh.jwt.value", "expires": 99999},
}

_CLIENT_TOKEN_RESPONSE = {
    "type": "client-token",
    "token": {"data": "client.jwt.value", "expires": 9999},
}


class TestResponseHandlerFiltering:
    """AC-4: response() only processes POST /auth on GC domains."""

    def test_non_gc_domain_ignored(self) -> None:
        extractor = CredentialExtractor()
        flow = _make_response_flow(
            "google.com", "POST", "/auth", "GameChanger/5.0 CFNetwork/1408",
            response_body=_TOKEN_RESPONSE,
        )
        with patch("proxy.addons.credential_extractor.merge_env_file") as mock_merge:
            extractor.response(flow)
        mock_merge.assert_not_called()

    def test_get_request_ignored(self) -> None:
        extractor = CredentialExtractor()
        flow = _make_response_flow(
            "api.gc.com", "GET", "/auth", "GameChanger/5.0 CFNetwork/1408",
            response_body=_TOKEN_RESPONSE,
        )
        with patch("proxy.addons.credential_extractor.merge_env_file") as mock_merge:
            extractor.response(flow)
        mock_merge.assert_not_called()

    def test_non_auth_path_ignored(self) -> None:
        extractor = CredentialExtractor()
        flow = _make_response_flow(
            "api.gc.com", "POST", "/me/teams", "GameChanger/5.0 CFNetwork/1408",
            response_body=_TOKEN_RESPONSE,
        )
        with patch("proxy.addons.credential_extractor.merge_env_file") as mock_merge:
            extractor.response(flow)
        mock_merge.assert_not_called()


class TestResponseHandlerTokenType:
    """AC-3: Only type=="token" responses are processed."""

    def test_client_token_response_ignored(self) -> None:
        """type=="client-token" (step 2) is ignored -- no user tokens present."""
        extractor = CredentialExtractor()
        flow = _make_response_flow(
            "api.gc.com", "POST", "/auth",
            "GameChanger/5.0 CFNetwork/1408 Darwin/22.5.0",
            response_body=_CLIENT_TOKEN_RESPONSE,
        )
        with patch("proxy.addons.credential_extractor.merge_env_file") as mock_merge:
            extractor.response(flow)
        mock_merge.assert_not_called()

    def test_token_response_is_processed(self) -> None:
        """type=="token" response writes access + refresh tokens."""
        extractor = CredentialExtractor()
        flow = _make_response_flow(
            "api.gc.com", "POST", "/auth",
            "GameChanger/5.0 CFNetwork/1408 Darwin/22.5.0",
            response_body=_TOKEN_RESPONSE,
        )
        with patch("proxy.addons.credential_extractor.merge_env_file") as mock_merge:
            extractor.response(flow)
        mock_merge.assert_called_once()


class TestResponseHandlerCredentialCapture:
    """AC-2: Access + refresh tokens extracted and written with correct keys."""

    def test_mobile_access_token_written_to_mobile_key(self) -> None:
        """Access token from iOS POST /auth is written to GAMECHANGER_ACCESS_TOKEN_MOBILE."""
        extractor = CredentialExtractor()
        flow = _make_response_flow(
            "api.gc.com", "POST", "/auth",
            "GameChanger/5.0 CFNetwork/1408 Darwin/22.5.0",
            response_body=_TOKEN_RESPONSE,
        )
        with patch("proxy.addons.credential_extractor.merge_env_file") as mock_merge:
            extractor.response(flow)

        credentials = mock_merge.call_args[0][1]
        assert credentials["GAMECHANGER_ACCESS_TOKEN_MOBILE"] == "access.jwt.value"

    def test_mobile_refresh_token_written_to_mobile_key(self) -> None:
        """Refresh token from iOS POST /auth is written to GAMECHANGER_REFRESH_TOKEN_MOBILE."""
        extractor = CredentialExtractor()
        flow = _make_response_flow(
            "api.gc.com", "POST", "/auth",
            "GameChanger/5.0 CFNetwork/1408 Darwin/22.5.0",
            response_body=_TOKEN_RESPONSE,
        )
        with patch("proxy.addons.credential_extractor.merge_env_file") as mock_merge:
            extractor.response(flow)

        credentials = mock_merge.call_args[0][1]
        assert credentials["GAMECHANGER_REFRESH_TOKEN_MOBILE"] == "refresh.jwt.value"

    def test_web_access_token_written_to_web_key(self) -> None:
        """Access token from web POST /auth is written to GAMECHANGER_ACCESS_TOKEN_WEB."""
        extractor = CredentialExtractor()
        flow = _make_response_flow(
            "api.gc.com", "POST", "/auth", "Mozilla/5.0 Chrome/120.0.0.0",
            response_body=_TOKEN_RESPONSE,
        )
        with patch("proxy.addons.credential_extractor.merge_env_file") as mock_merge:
            extractor.response(flow)

        credentials = mock_merge.call_args[0][1]
        assert credentials["GAMECHANGER_ACCESS_TOKEN_WEB"] == "access.jwt.value"
        assert credentials["GAMECHANGER_REFRESH_TOKEN_WEB"] == "refresh.jwt.value"

    def test_access_key_distinct_from_refresh_key(self) -> None:
        """AC-6: Access token uses a different env key than refresh token."""
        extractor = CredentialExtractor()
        flow = _make_response_flow(
            "api.gc.com", "POST", "/auth",
            "GameChanger/5.0 CFNetwork/1408 Darwin/22.5.0",
            response_body=_TOKEN_RESPONSE,
        )
        with patch("proxy.addons.credential_extractor.merge_env_file") as mock_merge:
            extractor.response(flow)

        credentials = mock_merge.call_args[0][1]
        assert "GAMECHANGER_ACCESS_TOKEN_MOBILE" in credentials
        assert "GAMECHANGER_REFRESH_TOKEN_MOBILE" in credentials
        # They should be different keys (and in this test, different values)
        assert (
            credentials["GAMECHANGER_ACCESS_TOKEN_MOBILE"]
            != credentials["GAMECHANGER_REFRESH_TOKEN_MOBILE"]
        )

    def test_env_path_passed_to_merge(self) -> None:
        """/app/.env is the path argument for response-body token writes."""
        extractor = CredentialExtractor()
        flow = _make_response_flow(
            "api.gc.com", "POST", "/auth",
            "GameChanger/5.0 CFNetwork/1408 Darwin/22.5.0",
            response_body=_TOKEN_RESPONSE,
        )
        with patch("proxy.addons.credential_extractor.merge_env_file") as mock_merge:
            extractor.response(flow)

        env_path = mock_merge.call_args[0][0]
        assert env_path == "/app/.env"


class TestResponseHandlerDeduplication:
    """AC-5: Deduplication for response-body tokens."""

    def test_same_tokens_do_not_trigger_second_write(self) -> None:
        extractor = CredentialExtractor()
        flow1 = _make_response_flow(
            "api.gc.com", "POST", "/auth",
            "GameChanger/5.0 CFNetwork/1408 Darwin/22.5.0",
            response_body=_TOKEN_RESPONSE,
        )
        flow2 = _make_response_flow(
            "api.gc.com", "POST", "/auth",
            "GameChanger/5.0 CFNetwork/1408 Darwin/22.5.0",
            response_body=_TOKEN_RESPONSE,
        )
        with patch("proxy.addons.credential_extractor.merge_env_file") as mock_merge:
            extractor.response(flow1)
            extractor.response(flow2)

        assert mock_merge.call_count == 1

    def test_changed_access_token_triggers_second_write(self) -> None:
        extractor = CredentialExtractor()
        body_v1 = {
            "type": "token",
            "access": {"data": "access.v1", "expires": 1},
            "refresh": {"data": "refresh.v1", "expires": 2},
        }
        body_v2 = {
            "type": "token",
            "access": {"data": "access.v2", "expires": 1},
            "refresh": {"data": "refresh.v2", "expires": 2},
        }
        flow1 = _make_response_flow(
            "api.gc.com", "POST", "/auth",
            "GameChanger/5.0 CFNetwork/1408 Darwin/22.5.0",
            response_body=body_v1,
        )
        flow2 = _make_response_flow(
            "api.gc.com", "POST", "/auth",
            "GameChanger/5.0 CFNetwork/1408 Darwin/22.5.0",
            response_body=body_v2,
        )
        with patch("proxy.addons.credential_extractor.merge_env_file") as mock_merge:
            extractor.response(flow1)
            extractor.response(flow2)

        assert mock_merge.call_count == 2


class TestResponseHandlerNoCredentialLogging:
    """AC-7: No credential values appear in log output."""

    def test_token_values_not_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        extractor = CredentialExtractor()
        flow = _make_response_flow(
            "api.gc.com", "POST", "/auth",
            "GameChanger/5.0 CFNetwork/1408 Darwin/22.5.0",
            response_body={
                "type": "token",
                "access": {"data": "super-secret-access-token", "expires": 1},
                "refresh": {"data": "super-secret-refresh-token", "expires": 2},
            },
        )
        with patch("proxy.addons.credential_extractor.merge_env_file"):
            with caplog.at_level("DEBUG", logger="proxy.addons.credential_extractor"):
                extractor.response(flow)

        assert "super-secret-access-token" not in caplog.text
        assert "super-secret-refresh-token" not in caplog.text

    def test_key_names_are_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        extractor = CredentialExtractor()
        flow = _make_response_flow(
            "api.gc.com", "POST", "/auth",
            "GameChanger/5.0 CFNetwork/1408 Darwin/22.5.0",
            response_body=_TOKEN_RESPONSE,
        )
        with patch("proxy.addons.credential_extractor.merge_env_file"):
            with caplog.at_level("INFO", logger="proxy.addons.credential_extractor"):
                extractor.response(flow)

        assert "GAMECHANGER_ACCESS_TOKEN_MOBILE" in caplog.text


class TestResponseHandlerEdgeCases:
    def test_invalid_json_body_does_not_raise(self) -> None:
        """Non-JSON response body is handled gracefully."""
        extractor = CredentialExtractor()
        flow = _make_response_flow(
            "api.gc.com", "POST", "/auth",
            "GameChanger/5.0 CFNetwork/1408 Darwin/22.5.0",
            response_content=b"not-json",
        )
        with patch("proxy.addons.credential_extractor.merge_env_file") as mock_merge:
            extractor.response(flow)  # should not raise
        mock_merge.assert_not_called()

    def test_missing_access_data_field_does_not_raise(self) -> None:
        """Token response with missing nested fields is handled gracefully."""
        extractor = CredentialExtractor()
        flow = _make_response_flow(
            "api.gc.com", "POST", "/auth",
            "GameChanger/5.0 CFNetwork/1408 Darwin/22.5.0",
            response_body={"type": "token", "access": {}, "refresh": {}},
        )
        with patch("proxy.addons.credential_extractor.merge_env_file") as mock_merge:
            extractor.response(flow)  # should not raise
        mock_merge.assert_not_called()

    def test_unknown_ua_logs_warning_and_drops(self, caplog: pytest.LogCaptureFixture) -> None:
        """Unknown User-Agent in POST /auth response logs warning and drops tokens."""
        extractor = CredentialExtractor()
        flow = _make_response_flow(
            "api.gc.com", "POST", "/auth", "curl/7.81.0",
            response_body=_TOKEN_RESPONSE,
        )
        with patch("proxy.addons.credential_extractor.merge_env_file") as mock_merge:
            with caplog.at_level("WARNING", logger="proxy.addons.credential_extractor"):
                extractor.response(flow)

        mock_merge.assert_not_called()
        assert any(r.levelno >= 30 for r in caplog.records)

    def test_os_error_on_write_does_not_raise(self) -> None:
        """An OSError from merge_env_file in response handler is caught."""
        extractor = CredentialExtractor()
        flow = _make_response_flow(
            "api.gc.com", "POST", "/auth",
            "GameChanger/5.0 CFNetwork/1408 Darwin/22.5.0",
            response_body=_TOKEN_RESPONSE,
        )
        with patch(
            "proxy.addons.credential_extractor.merge_env_file",
            side_effect=OSError("disk full"),
        ):
            extractor.response(flow)  # should not raise


# ---------------------------------------------------------------------------
# Env file path
# ---------------------------------------------------------------------------


class TestEnvFilePath:
    def test_env_path_passed_to_merge(self) -> None:
        """merge_env_file receives /app/.env as the path argument."""
        extractor = CredentialExtractor()
        flow = _make_flow("api.gc.com", {"gc-token": "tok", "user-agent": "Chrome/120"})

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        env_path = mock_merge.call_args[0][0]
        assert env_path == "/app/.env"
