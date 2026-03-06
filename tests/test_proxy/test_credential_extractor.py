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
        assert credentials["GAMECHANGER_AUTH_TOKEN_WEB"] == "jwt.web.tok"
        assert "GAMECHANGER_AUTH_TOKEN" not in credentials

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

    def test_web_all_four_credentials_use_web_suffix(self) -> None:
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {
                "gc-token": "jwt.tok",
                "gc-device-id": "dev-id",
                "gc-app-name": "appname",
                "gc-signature": "sigvalue",
                "user-agent": "Chrome/120",
            },
        )

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        credentials = mock_merge.call_args[0][1]
        assert credentials["GAMECHANGER_AUTH_TOKEN_WEB"] == "jwt.tok"
        assert credentials["GAMECHANGER_DEVICE_ID_WEB"] == "dev-id"
        assert credentials["GAMECHANGER_APP_NAME_WEB"] == "appname"
        assert credentials["GAMECHANGER_SIGNATURE_WEB"] == "sigvalue"
        # No unsuffixed keys
        assert "GAMECHANGER_AUTH_TOKEN" not in credentials
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
        assert credentials["GAMECHANGER_AUTH_TOKEN_MOBILE"] == "jwt.mobile.tok"
        assert "GAMECHANGER_AUTH_TOKEN" not in credentials

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
        assert credentials["GAMECHANGER_AUTH_TOKEN_MOBILE"] == "jwt.cfnet.tok"
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
            extractor.request(web_flow)   # writes GAMECHANGER_AUTH_TOKEN_WEB=tok
            extractor.request(ios_flow)   # writes GAMECHANGER_AUTH_TOKEN_MOBILE=tok (different key)

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

        assert "GAMECHANGER_AUTH_TOKEN_WEB" in caplog.text
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
