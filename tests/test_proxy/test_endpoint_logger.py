"""Unit tests for proxy/addons/endpoint_logger.py.

All tests use lightweight mock flow objects -- no running mitmproxy instance required.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from proxy.addons.endpoint_logger import EndpointLogger, _build_entry, _append_entry, LOG_PATH


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
) -> SimpleNamespace:
    """Build a minimal mock mitmproxy flow for testing."""
    request_headers = {}
    if request_content_type:
        request_headers["content-type"] = request_content_type
    if user_agent:
        request_headers["user-agent"] = user_agent

    response_headers = {}
    if response_content_type:
        response_headers["content-type"] = response_content_type

    request = SimpleNamespace(
        pretty_host=host,
        pretty_url=url,
        method=method,
        headers=request_headers,
    )
    response = SimpleNamespace(
        status_code=status_code,
        headers=response_headers,
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

    def test_query_keys_sorted_and_no_values(self) -> None:
        flow = _make_flow(url="https://api.gc.com/teams?fetch_place_details=true&page=2&token=secret")
        entry = _build_entry(flow, "api.gc.com", "web")
        assert entry["query_keys"] == ["fetch_place_details", "page", "token"]
        # Values must NOT be present in the entry
        assert "secret" not in json.dumps(entry)
        assert "true" not in json.dumps(entry)

    def test_query_keys_empty_when_no_query(self) -> None:
        flow = _make_flow(url="https://api.gc.com/me/user")
        entry = _build_entry(flow, "api.gc.com", "unknown")
        assert entry["query_keys"] == []

    def test_query_keys_sorted_alphabetically(self) -> None:
        flow = _make_flow(url="https://api.gc.com/search?z=1&a=2&m=3")
        entry = _build_entry(flow, "api.gc.com", "web")
        assert entry["query_keys"] == ["a", "m", "z"]

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

    def test_entry_contains_exactly_expected_keys(self) -> None:
        flow = _make_flow()
        entry = _build_entry(flow, "api.gc.com", "ios")
        expected_keys = {
            "timestamp", "method", "host", "path", "query_keys",
            "request_content_type", "response_content_type", "status_code", "source",
        }
        assert set(entry.keys()) == expected_keys

    def test_no_body_data_in_entry(self) -> None:
        """Request and response bodies must NOT appear in the log entry."""
        flow = _make_flow()
        entry = _build_entry(flow, "api.gc.com", "ios")
        assert "body" not in entry
        assert "content" not in entry
        assert "data" not in entry


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
        """AC-4: No deduplication -- each occurrence is logged."""
        log_file = tmp_path / "endpoint-log.jsonl"
        addon = EndpointLogger()
        addon.log_path = log_file

        addon.response(_make_flow())
        addon.response(_make_flow())

        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_file_created_on_first_write(self, tmp_path: Path) -> None:
        """AC-7: File does not need to exist beforehand."""
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
        """AC-6: when PROXY_SESSION_DIR is set, output goes to session dir."""
        monkeypatch.setenv("PROXY_SESSION_DIR", str(tmp_path))
        addon = EndpointLogger()
        addon.response(_make_flow())

        expected = tmp_path / "endpoint-log.jsonl"
        assert expected.exists()
        entry = json.loads(expected.read_text().strip())
        assert entry["host"] == "api.gc.com"

    def test_fallback_path_used_when_no_session_dir(self, tmp_path: Path, monkeypatch: object) -> None:
        """AC-1 fallback: without PROXY_SESSION_DIR, log_path is LOG_PATH."""
        monkeypatch.delenv("PROXY_SESSION_DIR", raising=False)
        addon = EndpointLogger()
        assert addon.log_path == LOG_PATH


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
