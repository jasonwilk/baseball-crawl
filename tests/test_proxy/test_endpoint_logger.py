"""Unit tests for proxy/addons/endpoint_logger.py.  # synthetic-test-data

All tests use lightweight mock flow objects -- no running mitmproxy instance required.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from proxy.addons.endpoint_logger import (
    EndpointLogger,
    _build_entry,
    _append_entry,
    _redact_auth_body,
    LOG_PATH,
    _DEFAULT_MAX_BODY_BYTES,
)


# ---------------------------------------------------------------------------
# Helpers: build minimal mock flow objects
# ---------------------------------------------------------------------------


def _make_flow(
    *,
    host: str = "api.gc.com",
    method: str = "GET",
    url: str = "https://api.gc.com/teams/123/players",
    request_content_type: str = "",
    response_content_type: str = "application/json",
    status_code: int = 200,
    user_agent: str = "GameChanger/1234 CFNetwork/1410.0.3 Darwin/22.6.0",
    request_body: bytes = b"",
    response_body: bytes = b"",
    request_headers: dict[str, str] | None = None,
    response_headers: dict[str, str] | None = None,
) -> SimpleNamespace:
    """Build a minimal mock mitmproxy flow for testing."""
    req_headers: dict[str, str] = {}
    if request_content_type:
        req_headers["content-type"] = request_content_type
    if user_agent:
        req_headers["user-agent"] = user_agent
    if request_headers:
        req_headers.update(request_headers)

    resp_headers: dict[str, str] = {}
    if response_content_type:
        resp_headers["content-type"] = response_content_type
    if response_headers:
        resp_headers.update(response_headers)

    request = SimpleNamespace(
        pretty_host=host,
        pretty_url=url,
        method=method,
        headers=req_headers,
        content=request_body,
    )
    response = SimpleNamespace(
        status_code=status_code,
        headers=resp_headers,
        content=response_body,
    )
    return SimpleNamespace(request=request, response=response)


# ---------------------------------------------------------------------------
# _build_entry() -- entry formatting tests
# ---------------------------------------------------------------------------


class TestBuildEntry:
    def test_basic_get_request(self) -> None:
        flow = _make_flow()
        entry = _build_entry(flow, "api.gc.com", "ios")

        assert entry["method"] == "GET"
        assert entry["host"] == "api.gc.com"
        assert entry["path"] == "/teams/123/players"
        assert entry["query_keys"] == []
        assert entry["status_code"] == 200
        assert entry["source"] == "ios"

    def test_timestamp_is_iso8601(self) -> None:
        flow = _make_flow()
        entry = _build_entry(flow, "api.gc.com", "ios")
        # Must parse without error and end with UTC offset
        from datetime import datetime
        dt = datetime.fromisoformat(entry["timestamp"])
        assert dt.tzinfo is not None

    def test_query_keys_sorted_alphabetically(self) -> None:
        flow = _make_flow(url="https://api.gc.com/search?z=1&a=2&m=3")
        entry = _build_entry(flow, "api.gc.com", "web")
        assert entry["query_keys"] == ["a", "m", "z"]

    def test_query_keys_empty_when_no_query(self) -> None:
        flow = _make_flow(url="https://api.gc.com/me/user")
        entry = _build_entry(flow, "api.gc.com", "unknown")
        assert entry["query_keys"] == []

    def test_query_params_contains_full_key_value_mapping(self) -> None:
        flow = _make_flow(url="https://api.gc.com/teams?fetch_place_details=true&page=2&token=secret")
        entry = _build_entry(flow, "api.gc.com", "web")
        assert entry["query_params"] == {
            "fetch_place_details": "true",
            "page": "2",
            "token": "secret",
        }
        # query_keys still present for backward compatibility
        assert entry["query_keys"] == ["fetch_place_details", "page", "token"]

    def test_query_params_empty_dict_when_no_query(self) -> None:
        flow = _make_flow(url="https://api.gc.com/me/user")
        entry = _build_entry(flow, "api.gc.com", "web")
        assert entry["query_params"] == {}

    def test_request_content_type_captured(self) -> None:
        flow = _make_flow(request_content_type="application/json")
        entry = _build_entry(flow, "api.gc.com", "web")
        assert entry["request_content_type"] == "application/json"

    def test_response_content_type_captured(self) -> None:
        flow = _make_flow(response_content_type="application/vnd.gc.com.user+json; version=0.3.0")
        entry = _build_entry(flow, "api.gc.com", "ios")
        assert entry["response_content_type"] == "application/vnd.gc.com.user+json; version=0.3.0"

    def test_missing_content_types_default_to_empty_string(self) -> None:
        flow = _make_flow(request_content_type="", response_content_type="")
        entry = _build_entry(flow, "api.gc.com", "unknown")
        assert entry["request_content_type"] == ""
        assert entry["response_content_type"] == ""

    def test_status_code_recorded(self) -> None:
        flow = _make_flow(status_code=401)
        entry = _build_entry(flow, "api.gc.com", "ios")
        assert entry["status_code"] == 401

    def test_post_method(self) -> None:
        flow = _make_flow(method="POST", url="https://api.gc.com/auth")
        entry = _build_entry(flow, "api.gc.com", "web")
        assert entry["method"] == "POST"

    def test_source_ios(self) -> None:
        flow = _make_flow()
        entry = _build_entry(flow, "api.gc.com", "ios")
        assert entry["source"] == "ios"

    def test_source_web(self) -> None:
        flow = _make_flow(user_agent="Chrome/120.0 Safari/537.36")
        entry = _build_entry(flow, "api.gc.com", "web")
        assert entry["source"] == "web"

    def test_source_unknown(self) -> None:
        flow = _make_flow(user_agent="")
        entry = _build_entry(flow, "api.gc.com", "unknown")
        assert entry["source"] == "unknown"

    # --- Key-set tests: two variants (AC-11) ---

    def test_entry_contains_exactly_expected_keys_capture_mode(self) -> None:
        flow = _make_flow()
        entry = _build_entry(flow, "api.gc.com", "ios", capture_bodies=True)
        expected_keys = {
            "timestamp", "method", "host", "path", "query_keys",
            "request_content_type", "response_content_type", "status_code", "source",
            "query_params", "request_headers", "response_headers",
            "request_body", "response_body",
        }
        assert set(entry.keys()) == expected_keys

    def test_entry_contains_exactly_expected_keys_metadata_mode(self) -> None:
        flow = _make_flow()
        entry = _build_entry(flow, "api.gc.com", "ios", capture_bodies=False)
        expected_keys = {
            "timestamp", "method", "host", "path", "query_keys",
            "request_content_type", "response_content_type", "status_code", "source",
        }
        assert set(entry.keys()) == expected_keys

    # --- Body capture tests ---

    def test_body_null_for_get_request(self) -> None:
        """GET requests have no body; request_body must be null."""
        flow = _make_flow(method="GET", request_body=b"")
        entry = _build_entry(flow, "api.gc.com", "ios")
        assert entry["request_body"] is None

    def test_body_captured_for_post_request(self) -> None:
        """POST requests with a JSON body are captured as a string."""
        payload = b'{"username": "test"}'
        flow = _make_flow(
            method="POST",
            url="https://api.gc.com/auth",
            request_content_type="application/json",
            request_body=payload,
        )
        entry = _build_entry(flow, "api.gc.com", "web")
        assert entry["request_body"] == '{"username": "test"}'

    def test_response_body_captured_as_string(self) -> None:
        payload = b'{"id": "abc", "name": "Test Team"}'
        flow = _make_flow(response_body=payload)
        entry = _build_entry(flow, "api.gc.com", "web")
        assert entry["response_body"] == '{"id": "abc", "name": "Test Team"}'

    def test_response_body_null_for_empty_response(self) -> None:
        flow = _make_flow(response_body=b"")
        entry = _build_entry(flow, "api.gc.com", "web")
        assert entry["response_body"] is None

    # --- Truncation tests (AC-7) ---

    def test_truncation_sentinel_for_oversized_response_body(self) -> None:
        large_body = b"x" * 10
        flow = _make_flow(response_body=large_body)
        entry = _build_entry(flow, "api.gc.com", "web", max_body_bytes=5)
        assert entry["response_body"] == "<truncated: 10 bytes>"

    def test_truncation_sentinel_for_oversized_request_body(self) -> None:
        large_body = b"y" * 10
        flow = _make_flow(
            method="POST",
            request_content_type="application/json",
            request_body=large_body,
        )
        entry = _build_entry(flow, "api.gc.com", "web", max_body_bytes=5)
        assert entry["request_body"] == "<truncated: 10 bytes>"

    def test_truncation_sentinel_includes_original_byte_count(self) -> None:
        body = b"a" * 3_000_000
        flow = _make_flow(response_body=body)
        entry = _build_entry(flow, "api.gc.com", "web", max_body_bytes=_DEFAULT_MAX_BODY_BYTES)
        assert entry["response_body"] == "<truncated: 3000000 bytes>"

    def test_body_at_exact_size_limit_is_not_truncated(self) -> None:
        body = b"x" * 5
        flow = _make_flow(response_body=body)
        entry = _build_entry(flow, "api.gc.com", "web", max_body_bytes=5)
        assert entry["response_body"] == "xxxxx"

    # --- Binary content type tests (AC-8) ---

    def test_binary_image_response_body_is_null(self) -> None:
        flow = _make_flow(
            response_content_type="image/png",
            response_body=b"\x89PNG\r\n",
        )
        entry = _build_entry(flow, "api.gc.com", "web")
        assert entry["response_body"] is None

    def test_binary_video_response_body_is_null(self) -> None:
        flow = _make_flow(
            response_content_type="video/mp4",
            response_body=b"\x00\x00\x00\x18",
        )
        entry = _build_entry(flow, "api.gc.com", "web")
        assert entry["response_body"] is None

    def test_octet_stream_body_is_null(self) -> None:
        flow = _make_flow(
            response_content_type="application/octet-stream",
            response_body=b"\xde\xad\xbe\xef",
        )
        entry = _build_entry(flow, "api.gc.com", "web")
        assert entry["response_body"] is None

    def test_binary_request_body_is_null(self) -> None:
        flow = _make_flow(
            method="POST",
            request_content_type="image/jpeg",
            request_body=b"\xff\xd8\xff",
        )
        entry = _build_entry(flow, "api.gc.com", "web")
        assert entry["request_body"] is None

    # --- Header capture tests ---

    def test_headers_captured_in_capture_mode(self) -> None:
        flow = _make_flow(
            request_headers={"gc-token": "tok123", "accept": "application/json"},
        )
        entry = _build_entry(flow, "api.gc.com", "web", strip_auth_headers=False)
        assert "gc-token" in entry["request_headers"]
        assert entry["request_headers"]["gc-token"] == "tok123"

    def test_auth_headers_stripped_when_enabled(self) -> None:
        flow = _make_flow(
            request_headers={
                "gc-token": "tok123",
                "gc-device-id": "dev456",
                "authorization": "REDACTED_TEST_VALUE",
                "gc-signature": "sig",
                "cookie": "session=x",
                "accept": "application/json",
            },
        )
        entry = _build_entry(flow, "api.gc.com", "web", strip_auth_headers=True)
        req_headers = entry["request_headers"]
        for sensitive in ("gc-token", "gc-device-id", "authorization", "gc-signature", "cookie"):
            assert sensitive not in req_headers
        assert "accept" in req_headers

    def test_auth_headers_present_when_stripping_disabled(self) -> None:
        flow = _make_flow(request_headers={"gc-token": "tok123", "accept": "application/json"})
        entry = _build_entry(flow, "api.gc.com", "web", strip_auth_headers=False)
        assert "gc-token" in entry["request_headers"]

    def test_response_headers_stripped_when_enabled(self) -> None:
        flow = _make_flow(response_headers={"set-cookie": "session=x", "content-length": "42"})
        entry = _build_entry(flow, "api.gc.com", "web", strip_auth_headers=True)
        assert "set-cookie" not in entry["response_headers"]
        assert "content-length" in entry["response_headers"]

    # --- capture_bodies=False tests (AC-5, AC-12) ---

    def test_capture_bodies_false_omits_payload_fields(self) -> None:
        flow = _make_flow(response_body=b'{"key": "value"}')
        entry = _build_entry(flow, "api.gc.com", "web", capture_bodies=False)
        for field in ("request_body", "response_body", "request_headers", "response_headers", "query_params"):
            assert field not in entry

    def test_capture_bodies_false_retains_query_keys(self) -> None:
        flow = _make_flow(url="https://api.gc.com/teams?page=2&sort=asc")
        entry = _build_entry(flow, "api.gc.com", "web", capture_bodies=False)
        assert entry["query_keys"] == ["page", "sort"]

    # --- Non-UTF-8 body decode (graceful handling) ---

    def test_non_utf8_body_decoded_with_replacement(self) -> None:
        bad_bytes = b"\xff\xfe some text"
        flow = _make_flow(response_body=bad_bytes)
        entry = _build_entry(flow, "api.gc.com", "web")
        # Must not raise; replacement chars used for invalid bytes
        assert isinstance(entry["response_body"], str)


# ---------------------------------------------------------------------------
# EndpointLogger.__init__() -- env var reading (AC-9, AC-12)
# ---------------------------------------------------------------------------


class TestEndpointLoggerInit:
    def test_capture_bodies_defaults_to_true(self, monkeypatch: object) -> None:
        monkeypatch.delenv("PROXY_CAPTURE_BODIES", raising=False)
        addon = EndpointLogger()
        assert addon.capture_bodies is True

    def test_capture_bodies_false_when_env_set(self, monkeypatch: object) -> None:
        monkeypatch.setenv("PROXY_CAPTURE_BODIES", "false")
        addon = EndpointLogger()
        assert addon.capture_bodies is False

    def test_strip_auth_headers_defaults_to_false(self, monkeypatch: object) -> None:
        monkeypatch.delenv("PROXY_STRIP_AUTH_HEADERS", raising=False)
        addon = EndpointLogger()
        assert addon.strip_auth_headers is False

    def test_strip_auth_headers_true_when_env_set(self, monkeypatch: object) -> None:
        monkeypatch.setenv("PROXY_STRIP_AUTH_HEADERS", "true")
        addon = EndpointLogger()
        assert addon.strip_auth_headers is True

    def test_max_body_bytes_custom_value(self, monkeypatch: object) -> None:
        monkeypatch.setenv("MAX_BODY_BYTES", "1048576")
        addon = EndpointLogger()
        assert addon.max_body_bytes == 1_048_576

    def test_max_body_bytes_invalid_value_falls_back_to_default(self, monkeypatch: object) -> None:
        monkeypatch.setenv("MAX_BODY_BYTES", "not-a-number")
        addon = EndpointLogger()
        assert addon.max_body_bytes == _DEFAULT_MAX_BODY_BYTES

    def test_max_body_bytes_defaults_to_2mb(self, monkeypatch: object) -> None:
        monkeypatch.delenv("MAX_BODY_BYTES", raising=False)
        addon = EndpointLogger()
        assert addon.max_body_bytes == _DEFAULT_MAX_BODY_BYTES


# ---------------------------------------------------------------------------
# EndpointLogger.response() -- hook behaviour
# ---------------------------------------------------------------------------


class TestEndpointLoggerResponse:
    def test_gc_domain_writes_entry(self, tmp_path: Path) -> None:
        flow = _make_flow()
        log_file = tmp_path / "endpoint-log.jsonl"

        addon = EndpointLogger()
        addon.log_path = log_file
        addon.response(flow)

        assert log_file.exists()
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["host"] == "api.gc.com"

    def test_non_gc_domain_ignored(self, tmp_path: Path) -> None:
        flow = _make_flow(host="google.com", url="https://google.com/search?q=test")
        log_file = tmp_path / "endpoint-log.jsonl"

        addon = EndpointLogger()
        addon.log_path = log_file
        addon.response(flow)

        assert not log_file.exists()

    def test_multiple_requests_all_appended(self, tmp_path: Path) -> None:
        log_file = tmp_path / "endpoint-log.jsonl"
        addon = EndpointLogger()
        addon.log_path = log_file

        for _ in range(3):
            addon.response(_make_flow())

        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 3

    def test_same_endpoint_appended_each_time(self, tmp_path: Path) -> None:
        """No deduplication -- each occurrence is logged."""
        log_file = tmp_path / "endpoint-log.jsonl"
        addon = EndpointLogger()
        addon.log_path = log_file

        addon.response(_make_flow())
        addon.response(_make_flow())

        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_file_created_on_first_write(self, tmp_path: Path) -> None:
        """File does not need to exist beforehand."""
        log_file = tmp_path / "subdir" / "endpoint-log.jsonl"
        assert not log_file.exists()

        addon = EndpointLogger()
        addon.log_path = log_file
        addon.response(_make_flow())

        assert log_file.exists()

    def test_each_line_is_valid_json(self, tmp_path: Path) -> None:
        log_file = tmp_path / "endpoint-log.jsonl"
        addon = EndpointLogger()
        addon.log_path = log_file

        addon.response(_make_flow(url="https://api.gc.com/me/user"))
        addon.response(_make_flow(url="https://api.gc.com/me/teams"))

        for line in log_file.read_text().strip().splitlines():
            entry = json.loads(line)  # must not raise
            assert isinstance(entry, dict)

    def test_source_detected_from_user_agent(self, tmp_path: Path) -> None:
        """detect_source() is called and result written to log."""
        ios_ua = "GameChanger/1234 CFNetwork/1410.0.3 Darwin/22.6.0"
        flow = _make_flow(user_agent=ios_ua)
        log_file = tmp_path / "endpoint-log.jsonl"

        addon = EndpointLogger()
        addon.log_path = log_file
        addon.response(flow)

        entry = json.loads(log_file.read_text().strip())
        assert entry["source"] == "ios"

    def test_session_dir_env_var_routes_output(self, tmp_path: Path, monkeypatch: object) -> None:
        """When PROXY_SESSION_DIR is set, output goes to session dir."""
        monkeypatch.setenv("PROXY_SESSION_DIR", str(tmp_path))
        addon = EndpointLogger()
        addon.response(_make_flow())

        expected = tmp_path / "endpoint-log.jsonl"
        assert expected.exists()
        entry = json.loads(expected.read_text().strip())
        assert entry["host"] == "api.gc.com"

    def test_fallback_path_used_when_no_session_dir(self, tmp_path: Path, monkeypatch: object) -> None:
        """Without PROXY_SESSION_DIR, log_path is LOG_PATH."""
        monkeypatch.delenv("PROXY_SESSION_DIR", raising=False)
        addon = EndpointLogger()
        assert addon.log_path == LOG_PATH

    def test_response_writes_bodies_in_capture_mode(self, tmp_path: Path, monkeypatch: object) -> None:
        """In capture mode, response hook writes body fields to log."""
        monkeypatch.setenv("PROXY_CAPTURE_BODIES", "true")
        monkeypatch.delenv("PROXY_STRIP_AUTH_HEADERS", raising=False)

        flow = _make_flow(response_body=b'{"ok": true}')
        log_file = tmp_path / "endpoint-log.jsonl"
        addon = EndpointLogger()
        addon.log_path = log_file
        addon.response(flow)

        entry = json.loads(log_file.read_text().strip())
        assert entry["response_body"] == '{"ok": true}'
        assert "request_headers" in entry

    def test_response_omits_bodies_in_metadata_mode(self, tmp_path: Path, monkeypatch: object) -> None:
        """In metadata-only mode, response hook omits body/header fields."""
        monkeypatch.setenv("PROXY_CAPTURE_BODIES", "false")

        flow = _make_flow(response_body=b'{"ok": true}')
        log_file = tmp_path / "endpoint-log.jsonl"
        addon = EndpointLogger()
        addon.log_path = log_file
        addon.response(flow)

        entry = json.loads(log_file.read_text().strip())
        assert "response_body" not in entry
        assert "request_headers" not in entry

    def test_auth_headers_stripped_via_env(self, tmp_path: Path, monkeypatch: object) -> None:
        """Auth header stripping works end-to-end via env var."""
        monkeypatch.setenv("PROXY_STRIP_AUTH_HEADERS", "true")
        monkeypatch.setenv("PROXY_CAPTURE_BODIES", "true")

        flow = _make_flow(request_headers={"gc-token": "tok123", "accept": "application/json"})
        log_file = tmp_path / "endpoint-log.jsonl"
        addon = EndpointLogger()
        addon.log_path = log_file
        addon.response(flow)

        entry = json.loads(log_file.read_text().strip())
        assert "gc-token" not in entry["request_headers"]
        assert "accept" in entry["request_headers"]


# ---------------------------------------------------------------------------
# _append_entry() -- file write helper
# ---------------------------------------------------------------------------


class TestAppendEntry:
    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        log_file = tmp_path / "nested" / "dir" / "log.jsonl"
        _append_entry({"key": "value"}, log_file)
        assert log_file.exists()

    def test_appends_newline_delimited_json(self, tmp_path: Path) -> None:
        log_file = tmp_path / "log.jsonl"
        _append_entry({"a": 1}, log_file)
        _append_entry({"b": 2}, log_file)

        lines = log_file.read_text().splitlines()
        assert json.loads(lines[0]) == {"a": 1}
        assert json.loads(lines[1]) == {"b": 2}

    def test_defaults_to_LOG_PATH_when_path_not_provided(self, monkeypatch: object) -> None:
        """_append_entry() without explicit path uses LOG_PATH (module constant)."""
        # We just verify the attribute -- don't actually write to /app/proxy/data/
        import proxy.addons.endpoint_logger as mod
        assert mod.LOG_PATH == Path("/app/proxy/data/endpoint-log.jsonl")


# ---------------------------------------------------------------------------
# _redact_auth_body() -- PII redaction unit tests (AC-1 through AC-4)
# ---------------------------------------------------------------------------


class TestRedactAuthBody:
    """Unit tests for _redact_auth_body()."""

    def test_email_field_is_redacted(self) -> None:
        """AC-1: email value is replaced with [REDACTED]."""
        body = json.dumps({"type": "user-auth", "email": "coach@example.com"})
        result = json.loads(_redact_auth_body(body))
        assert result["email"] == "[REDACTED]"

    def test_type_preserved_on_email_redaction(self) -> None:
        """AC-1: type field is preserved after email redaction."""
        body = json.dumps({"type": "user-auth", "email": "coach@example.com"})
        result = json.loads(_redact_auth_body(body))
        assert result["type"] == "user-auth"

    def test_password_field_is_redacted(self) -> None:
        """AC-2: password value is replaced with [REDACTED]."""
        body = json.dumps({"type": "password", "password": "s3cr3t!"})
        result = json.loads(_redact_auth_body(body))
        assert result["password"] == "[REDACTED]"

    def test_type_preserved_on_password_redaction(self) -> None:
        """AC-2: type field is preserved after password redaction."""
        body = json.dumps({"type": "password", "password": "s3cr3t!"})
        result = json.loads(_redact_auth_body(body))
        assert result["type"] == "password"

    def test_refresh_body_passes_through_unchanged(self) -> None:
        """AC-4: {"type": "refresh"} has no PII fields -- body unchanged."""
        body = json.dumps({"type": "refresh"})
        result = json.loads(_redact_auth_body(body))
        assert result == {"type": "refresh"}

    def test_none_body_returns_none(self) -> None:
        """None body (e.g. empty request) passes through unchanged."""
        assert _redact_auth_body(None) is None

    def test_non_json_body_passes_through_unchanged(self) -> None:
        """Non-JSON body (e.g. binary or plain text) passes through unchanged."""
        body = "not-json"
        assert _redact_auth_body(body) == body


# ---------------------------------------------------------------------------
# Integration: POST /auth redaction via _build_entry() (AC-1 through AC-3)
# ---------------------------------------------------------------------------


class TestAuthBodyRedactionIntegration:
    """Verify PII redaction is applied (or not) by _build_entry() via _build_capture_fields()."""

    def _make_auth_flow(self, body: dict, method: str = "POST") -> SimpleNamespace:
        return _make_flow(
            method=method,
            url="https://api.gc.com/auth",
            request_content_type="application/json",
            request_body=json.dumps(body).encode(),
        )

    def test_user_auth_email_redacted_in_log_entry(self) -> None:
        """AC-1: POST /auth with email → email field is [REDACTED] in log."""
        flow = self._make_auth_flow({"type": "user-auth", "email": "coach@example.com"})
        entry = _build_entry(flow, "api.gc.com", "web", capture_bodies=True)
        body = json.loads(entry["request_body"])
        assert body["email"] == "[REDACTED]"
        assert body["type"] == "user-auth"
        assert "coach@example.com" not in entry["request_body"]

    def test_password_auth_redacted_in_log_entry(self) -> None:
        """AC-2: POST /auth with password → password field is [REDACTED] in log."""
        flow = self._make_auth_flow({"type": "password", "password": "s3cr3t!"})
        entry = _build_entry(flow, "api.gc.com", "web", capture_bodies=True)
        body = json.loads(entry["request_body"])
        assert body["password"] == "[REDACTED]"
        assert body["type"] == "password"
        assert "s3cr3t!" not in entry["request_body"]

    def test_non_auth_request_not_redacted(self) -> None:
        """AC-3: POST to a non-/auth path is not redacted."""
        flow = _make_flow(
            method="POST",
            url="https://api.gc.com/teams/123/games",
            request_content_type="application/json",
            request_body=json.dumps({"email": "should-not-redact@example.com"}).encode(),
        )
        entry = _build_entry(flow, "api.gc.com", "web", capture_bodies=True)
        body = json.loads(entry["request_body"])
        assert body["email"] == "should-not-redact@example.com"

    def test_refresh_auth_passes_through_unchanged(self) -> None:
        """AC-4: POST /auth with type=refresh → no redaction."""
        flow = self._make_auth_flow({"type": "refresh"})
        entry = _build_entry(flow, "api.gc.com", "web", capture_bodies=True)
        body = json.loads(entry["request_body"])
        assert body == {"type": "refresh"}
