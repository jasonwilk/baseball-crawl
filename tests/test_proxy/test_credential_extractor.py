"""Unit tests for proxy/addons/credential_extractor.py.

Tests use mock flow objects rather than a live mitmproxy instance.
All .env writes are patched so no real files are created.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

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

    def test_gamechanger_com_subdomain_is_processed(self) -> None:
        """Requests to *.gamechanger.com must be processed."""
        extractor = CredentialExtractor()
        flow = _make_flow(
            "app.gamechanger.com",
            {"gc-token": "tok2", "user-agent": ""},
        )

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        mock_merge.assert_called_once()


# ---------------------------------------------------------------------------
# Header-to-env-key mapping
# ---------------------------------------------------------------------------


class TestHeaderMapping:
    def test_gc_token_maps_to_auth_token(self) -> None:
        """gc-token header maps to GAMECHANGER_AUTH_TOKEN."""
        extractor = CredentialExtractor()
        flow = _make_flow("api.gc.com", {"gc-token": "jwt.abc.def", "user-agent": ""})

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        _, kwargs = mock_merge.call_args if mock_merge.call_args else (None, {})
        args = mock_merge.call_args[0]
        credentials = args[1]
        assert credentials["GAMECHANGER_AUTH_TOKEN"] == "jwt.abc.def"

    def test_gc_device_id_maps_correctly(self) -> None:
        """gc-device-id header maps to GAMECHANGER_DEVICE_ID."""
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {"gc-token": "tok", "gc-device-id": "device-uuid", "user-agent": ""},
        )

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        credentials = mock_merge.call_args[0][1]
        assert credentials["GAMECHANGER_DEVICE_ID"] == "device-uuid"

    def test_gc_app_name_maps_correctly(self) -> None:
        """gc-app-name header maps to GAMECHANGER_APP_NAME."""
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {"gc-token": "tok", "gc-app-name": "myapp", "user-agent": ""},
        )

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        credentials = mock_merge.call_args[0][1]
        assert credentials["GAMECHANGER_APP_NAME"] == "myapp"

    def test_gc_signature_maps_correctly(self) -> None:
        """gc-signature header maps to GAMECHANGER_SIGNATURE."""
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {"gc-token": "tok", "gc-signature": "sig123", "user-agent": ""},
        )

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        credentials = mock_merge.call_args[0][1]
        assert credentials["GAMECHANGER_SIGNATURE"] == "sig123"

    def test_all_four_credentials_written_together(self) -> None:
        """All four credential headers are written in a single call."""
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

        assert mock_merge.call_count == 1
        credentials = mock_merge.call_args[0][1]
        assert credentials["GAMECHANGER_AUTH_TOKEN"] == "jwt.tok"
        assert credentials["GAMECHANGER_DEVICE_ID"] == "dev-id"
        assert credentials["GAMECHANGER_APP_NAME"] == "appname"
        assert credentials["GAMECHANGER_SIGNATURE"] == "sigvalue"

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
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_duplicate_token_does_not_trigger_second_write(self) -> None:
        """If the token value is unchanged, merge_env_file is only called once."""
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

    def test_changed_token_triggers_second_write(self) -> None:
        """A new token value causes a second .env write."""
        extractor = CredentialExtractor()

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(
                _make_flow("api.gc.com", {"gc-token": "token-v1", "user-agent": ""})
            )
            extractor.request(
                _make_flow("api.gc.com", {"gc-token": "token-v2", "user-agent": ""})
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
                _make_flow("api.gc.com", {"gc-token": "tok", "user-agent": ""})
            )
            # Second request: gc-token same value, but gc-device-id newly present
            extractor.request(
                _make_flow(
                    "api.gc.com",
                    {"gc-token": "tok", "gc-device-id": "new-device", "user-agent": ""},
                )
            )

        assert mock_merge.call_count == 2


# ---------------------------------------------------------------------------
# Traffic source logging (source logged, values never logged)
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

    def test_key_names_logged_not_values(self, caplog: pytest.LogCaptureFixture) -> None:
        """Log output contains key names but not credential values."""
        token_value = "super-secret-jwt-token-do-not-log"
        extractor = CredentialExtractor()
        flow = _make_flow(
            "api.gc.com",
            {"gc-token": token_value, "user-agent": "Chrome/120"},
        )

        with patch("proxy.addons.credential_extractor.merge_env_file"):
            with caplog.at_level("INFO", logger="proxy.addons.credential_extractor"):
                extractor.request(flow)

        assert "GAMECHANGER_AUTH_TOKEN" in caplog.text
        assert token_value not in caplog.text


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_os_error_on_write_does_not_raise(self) -> None:
        """An OSError from merge_env_file is caught and logged without crashing."""
        extractor = CredentialExtractor()
        flow = _make_flow("api.gc.com", {"gc-token": "tok", "user-agent": ""})

        with patch(
            "proxy.addons.credential_extractor.merge_env_file",
            side_effect=OSError("permission denied"),
        ):
            # Should not raise.
            extractor.request(flow)

    def test_cache_not_updated_on_write_failure(self) -> None:
        """If the write fails, the cache is not updated, so next request retries."""
        extractor = CredentialExtractor()
        flow1 = _make_flow("api.gc.com", {"gc-token": "tok", "user-agent": ""})
        flow2 = _make_flow("api.gc.com", {"gc-token": "tok", "user-agent": ""})

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
        flow = _make_flow("api.gc.com", {"gc-token": "tok", "user-agent": ""})

        with patch(
            "proxy.addons.credential_extractor.merge_env_file"
        ) as mock_merge:
            extractor.request(flow)

        env_path = mock_merge.call_args[0][0]
        assert env_path == "/app/.env"
