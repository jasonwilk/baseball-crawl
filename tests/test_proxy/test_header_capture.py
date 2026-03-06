"""Unit tests for proxy/addons/header_capture.py.

Tests cover the pure diff logic and the addon's header-filtering behaviour.
No mitmproxy instance is required -- flow objects are mocked with simple
namespace objects.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from proxy.addons.header_capture import (
    HeaderCapture,
    _CREDENTIAL_HEADERS,
    _REPORT_PATH,
    _SKIP_DIFF_HEADERS,
    build_report,
    compute_header_diff,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_flow(host: str, user_agent: str, headers: dict[str, str]) -> SimpleNamespace:
    """Build a minimal mitmproxy-like flow object for testing."""
    return SimpleNamespace(
        request=SimpleNamespace(
            pretty_host=host,
            headers=headers,
        )
    )


# ---------------------------------------------------------------------------
# compute_header_diff()
# ---------------------------------------------------------------------------


class TestComputeHeaderDiff:
    def test_identical_headers_no_diff(self) -> None:
        captured = {"Accept": "application/json", "Accept-Language": "en-US"}
        canonical = {"Accept": "application/json", "Accept-Language": "en-US"}
        diff = compute_header_diff(captured, canonical, skip=frozenset())
        assert diff["missing_in_captured"] == []
        assert diff["extra_in_captured"] == []
        assert diff["value_differences"] == []

    def test_missing_in_captured(self) -> None:
        captured = {"Accept": "application/json"}
        canonical = {"Accept": "application/json", "DNT": "1"}
        diff = compute_header_diff(captured, canonical, skip=frozenset())
        assert diff["missing_in_captured"] == ["dnt"]
        assert diff["extra_in_captured"] == []
        assert diff["value_differences"] == []

    def test_extra_in_captured(self) -> None:
        captured = {"Accept": "application/json", "X-Custom": "yes"}
        canonical = {"Accept": "application/json"}
        diff = compute_header_diff(captured, canonical, skip=frozenset())
        assert diff["missing_in_captured"] == []
        assert diff["extra_in_captured"] == ["x-custom"]
        assert diff["value_differences"] == []

    def test_value_difference(self) -> None:
        captured = {"Accept": "text/html"}
        canonical = {"Accept": "application/json"}
        diff = compute_header_diff(captured, canonical, skip=frozenset())
        assert diff["missing_in_captured"] == []
        assert diff["extra_in_captured"] == []
        assert len(diff["value_differences"]) == 1
        vd = diff["value_differences"][0]
        assert vd["key"] == "accept"
        assert vd["captured"] == "text/html"
        assert vd["canonical"] == "application/json"

    def test_all_three_diff_types_at_once(self) -> None:
        captured = {
            "Accept": "text/html",   # value differs
            "X-Extra": "yes",         # extra
            # "DNT" missing
        }
        canonical = {
            "Accept": "application/json",
            "DNT": "1",
        }
        diff = compute_header_diff(captured, canonical, skip=frozenset())
        assert diff["missing_in_captured"] == ["dnt"]
        assert diff["extra_in_captured"] == ["x-extra"]
        assert len(diff["value_differences"]) == 1

    def test_skip_list_excludes_headers(self) -> None:
        captured = {"Accept": "application/json", "Content-Length": "0"}
        canonical = {"Accept": "application/json"}
        # content-length is in the default skip list
        diff = compute_header_diff(captured, canonical)
        # Content-Length should NOT appear in extra_in_captured
        assert "content-length" not in diff["extra_in_captured"]

    def test_host_excluded_from_diff(self) -> None:
        captured = {"Accept": "application/json", "Host": "api.gc.com"}
        canonical = {"Accept": "application/json"}
        diff = compute_header_diff(captured, canonical)
        assert "host" not in diff["extra_in_captured"]

    def test_key_comparison_is_case_insensitive(self) -> None:
        captured = {"ACCEPT": "application/json"}
        canonical = {"accept": "application/json"}
        diff = compute_header_diff(captured, canonical, skip=frozenset())
        assert diff["missing_in_captured"] == []
        assert diff["extra_in_captured"] == []
        assert diff["value_differences"] == []

    def test_empty_captured(self) -> None:
        canonical = {"Accept": "application/json"}
        diff = compute_header_diff({}, canonical, skip=frozenset())
        assert "accept" in diff["missing_in_captured"]
        assert diff["extra_in_captured"] == []

    def test_empty_canonical(self) -> None:
        captured = {"Accept": "application/json"}
        diff = compute_header_diff(captured, {}, skip=frozenset())
        assert diff["missing_in_captured"] == []
        assert "accept" in diff["extra_in_captured"]

    def test_both_empty(self) -> None:
        diff = compute_header_diff({}, {}, skip=frozenset())
        assert diff["missing_in_captured"] == []
        assert diff["extra_in_captured"] == []
        assert diff["value_differences"] == []

    def test_value_differences_sorted_by_key(self) -> None:
        captured = {"B-Header": "b-cap", "A-Header": "a-cap"}
        canonical = {"B-Header": "b-can", "A-Header": "a-can"}
        diff = compute_header_diff(captured, canonical, skip=frozenset())
        keys = [d["key"] for d in diff["value_differences"]]
        assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# build_report()
# ---------------------------------------------------------------------------


class TestBuildReport:
    def test_report_structure(self) -> None:
        captured_by_source = {
            "web": {"Accept": "text/html", "User-Agent": "Chrome/131"},
        }
        canonical_by_source = {
            "web": {"Accept": "application/json", "User-Agent": "Chrome/131"},
        }
        report = build_report(captured_by_source, canonical_by_source)

        assert "generated_at" in report
        assert "sources" in report
        assert len(report["sources"]) == 1

        source_entry = report["sources"][0]
        assert source_entry["source"] == "web"
        assert "captured_headers" in source_entry
        assert "browser_headers" in source_entry
        assert "missing_in_captured" in source_entry
        assert "extra_in_captured" in source_entry
        assert "value_differences" in source_entry

    def test_multiple_sources_appear(self) -> None:
        captured_by_source = {
            "web": {"Accept": "text/html"},
            "ios": {"Accept": "application/json"},
        }
        canonical_by_source = {
            "web": {"Accept": "application/json"},
            "ios": {"Accept": "application/json"},
        }
        report = build_report(captured_by_source, canonical_by_source)
        sources = {s["source"] for s in report["sources"]}
        assert sources == {"web", "ios"}

    def test_empty_captured_produces_no_sources(self) -> None:
        report = build_report({}, {"web": {"Accept": "application/json"}})
        assert report["sources"] == []

    def test_generated_at_is_iso8601(self) -> None:
        report = build_report({}, {})
        from datetime import datetime
        # Should parse without error
        dt = datetime.fromisoformat(report["generated_at"].replace("Z", "+00:00"))
        assert dt is not None

    def test_web_source_uses_browser_headers(self) -> None:
        """web source diffs against BROWSER_HEADERS (not MOBILE_HEADERS)."""
        browser_canonical = {"Accept-Language": "en-US,en;q=0.9", "DNT": "1"}
        mobile_canonical = {"Accept-Language": "en-US;q=1.0", "gc-app-version": "2026.7.0.0"}
        canonical_by_source = {"web": browser_canonical, "ios": mobile_canonical}
        captured_by_source = {"web": {"Accept-Language": "en-US,en;q=0.9"}}

        report = build_report(captured_by_source, canonical_by_source)
        web_entry = next(s for s in report["sources"] if s["source"] == "web")

        # The canonical dict stored in the report should be browser_canonical
        assert web_entry["browser_headers"] == browser_canonical

    def test_ios_source_uses_mobile_headers(self) -> None:
        """ios source diffs against MOBILE_HEADERS (not BROWSER_HEADERS)."""
        browser_canonical = {"Accept-Language": "en-US,en;q=0.9", "DNT": "1"}
        mobile_canonical = {"Accept-Language": "en-US;q=1.0", "gc-app-version": "2026.7.0.0"}
        canonical_by_source = {"web": browser_canonical, "ios": mobile_canonical}
        captured_by_source = {"ios": {"Accept-Language": "en-US;q=1.0"}}

        report = build_report(captured_by_source, canonical_by_source)
        ios_entry = next(s for s in report["sources"] if s["source"] == "ios")

        # The canonical dict stored in the report should be mobile_canonical
        assert ios_entry["browser_headers"] == mobile_canonical

    def test_ios_diff_uses_mobile_canonical_values(self) -> None:
        """value_differences for ios reflects drift from MOBILE_HEADERS, not BROWSER_HEADERS."""
        browser_canonical = {"Accept-Language": "en-US,en;q=0.9"}
        mobile_canonical = {"Accept-Language": "en-US;q=1.0"}
        canonical_by_source = {"web": browser_canonical, "ios": mobile_canonical}
        # ios capture matches mobile_canonical exactly
        captured_by_source = {"ios": {"Accept-Language": "en-US;q=1.0"}}

        report = build_report(captured_by_source, canonical_by_source)
        ios_entry = next(s for s in report["sources"] if s["source"] == "ios")

        # No drift -- ios capture matches MOBILE_HEADERS
        assert ios_entry["value_differences"] == []
        assert ios_entry["missing_in_captured"] == []

    def test_unknown_source_falls_back_to_web_canonical(self) -> None:
        """unknown source falls back to the web canonical dict."""
        browser_canonical = {"DNT": "1"}
        mobile_canonical = {"gc-app-version": "2026.7.0.0"}
        canonical_by_source = {"web": browser_canonical, "ios": mobile_canonical}
        captured_by_source = {"unknown": {"DNT": "1"}}

        report = build_report(captured_by_source, canonical_by_source)
        unknown_entry = next(s for s in report["sources"] if s["source"] == "unknown")

        # Falls back to web canonical
        assert unknown_entry["browser_headers"] == browser_canonical


# ---------------------------------------------------------------------------
# HeaderCapture addon (request hook and filtering)
# ---------------------------------------------------------------------------


class TestHeaderCaptureAddon:
    def test_non_gc_domain_ignored(self) -> None:
        addon = HeaderCapture()
        flow = _make_flow("google.com", "Chrome/131", {"Accept": "text/html"})
        addon.request(flow)
        assert addon._captured_by_source == {}

    def test_gc_domain_captured(self, tmp_path: Path) -> None:
        addon = HeaderCapture()
        addon.report_path = tmp_path / "report.json"
        headers = {"Accept": "application/json", "user-agent": "Chrome/131 Safari/537.36"}
        flow = _make_flow("api.gc.com", "Chrome/131", headers)
        addon.request(flow)
        assert "web" in addon._captured_by_source

    def test_credential_headers_excluded(self, tmp_path: Path) -> None:
        addon = HeaderCapture()
        addon.report_path = tmp_path / "report.json"
        headers = {
            "Accept": "application/json",
            "gc-token": "super-secret-token",
            "gc-device-id": "device-123",
            "gc-signature": "sig-abc",
            "gc-app-name": "app-name",
            "cookie": "session=abc",
            "user-agent": "Chrome/131 Safari/537.36",
        }
        flow = _make_flow("api.gc.com", "Chrome/131", headers)
        addon.request(flow)

        captured = addon._captured_by_source.get("web", {})
        captured_lower = {k.lower() for k in captured}
        for cred in _CREDENTIAL_HEADERS:
            assert cred not in captured_lower, f"Credential header '{cred}' should be excluded"

    def test_credential_headers_case_insensitive_exclusion(self, tmp_path: Path) -> None:
        addon = HeaderCapture()
        addon.report_path = tmp_path / "report.json"
        headers = {
            "GC-TOKEN": "super-secret-token",
            "Accept": "application/json",
            "user-agent": "Chrome/131 Safari/537.36",
        }
        flow = _make_flow("api.gc.com", "Chrome/131", headers)
        addon.request(flow)

        captured = addon._captured_by_source.get("web", {})
        captured_lower = {k.lower() for k in captured}
        assert "gc-token" not in captured_lower

    def test_first_seen_wins_on_conflicting_values(self, tmp_path: Path) -> None:
        addon = HeaderCapture()
        addon.report_path = tmp_path / "report.json"
        headers1 = {"Accept": "text/html", "user-agent": "Chrome/131 Safari/537.36"}
        headers2 = {"Accept": "application/json", "user-agent": "Chrome/131 Safari/537.36"}
        flow1 = _make_flow("api.gc.com", "Chrome/131", headers1)
        flow2 = _make_flow("api.gc.com", "Chrome/131", headers2)
        addon.request(flow1)
        addon.request(flow2)

        captured = addon._captured_by_source["web"]
        # First-seen wins: flow1's Accept value is retained
        assert captured["Accept"] == "text/html"

    def test_union_aggregation_no_conflicts(self, tmp_path: Path) -> None:
        """Keys from both requests appear in result when there are no conflicting values."""
        addon = HeaderCapture()
        addon.report_path = tmp_path / "report.json"
        ua = "Chrome/131 Safari/537.36"
        headers1 = {"Accept": "application/json", "user-agent": ua}
        headers2 = {"DNT": "1", "user-agent": ua}
        flow1 = _make_flow("api.gc.com", ua, headers1)
        flow2 = _make_flow("api.gc.com", ua, headers2)
        addon.request(flow1)
        addon.request(flow2)

        captured = addon._captured_by_source["web"]
        assert captured["Accept"] == "application/json"
        assert captured["DNT"] == "1"

    def test_conflict_emits_warning_log(self, tmp_path: Path, caplog: object) -> None:
        """A WARNING is logged when the same key has different values across requests."""
        import logging
        addon = HeaderCapture()
        addon.report_path = tmp_path / "report.json"
        ua = "Chrome/131 Safari/537.36"
        headers1 = {"Accept": "text/html", "user-agent": ua}
        headers2 = {"Accept": "application/json", "user-agent": ua}
        flow1 = _make_flow("api.gc.com", ua, headers1)
        flow2 = _make_flow("api.gc.com", ua, headers2)

        with caplog.at_level(logging.WARNING, logger="proxy.addons.header_capture"):
            addon.request(flow1)
            addon.request(flow2)

        assert any(
            "conflict" in record.message and "Accept" in record.message
            for record in caplog.records
            if record.levelno == logging.WARNING
        )

    def test_order_independence_same_key_set(self, tmp_path: Path) -> None:
        """Same two requests in two different orders produce the same set of keys."""
        ua = "Chrome/131 Safari/537.36"
        headers_a = {"Accept": "text/html", "user-agent": ua}
        headers_b = {"Accept": "application/json", "DNT": "1", "user-agent": ua}

        addon_ab = HeaderCapture()
        addon_ab.report_path = tmp_path / "report_ab.json"
        addon_ab.request(_make_flow("api.gc.com", ua, headers_a))
        addon_ab.request(_make_flow("api.gc.com", ua, headers_b))

        addon_ba = HeaderCapture()
        addon_ba.report_path = tmp_path / "report_ba.json"
        addon_ba.request(_make_flow("api.gc.com", ua, headers_b))
        addon_ba.request(_make_flow("api.gc.com", ua, headers_a))

        keys_ab = set(addon_ab._captured_by_source["web"].keys())
        keys_ba = set(addon_ba._captured_by_source["web"].keys())
        assert keys_ab == keys_ba

    def test_ios_source_detected(self, tmp_path: Path) -> None:
        addon = HeaderCapture()
        addon.report_path = tmp_path / "report.json"
        ios_ua = "GameChanger/1234 CFNetwork/1410.0.3 Darwin/22.6.0"
        headers = {"Accept": "application/json", "user-agent": ios_ua}
        flow = _make_flow("api.gc.com", ios_ua, headers)
        addon.request(flow)
        assert "ios" in addon._captured_by_source

    def test_report_file_written(self, tmp_path: Path) -> None:
        addon = HeaderCapture()
        report_path = tmp_path / "report.json"
        addon.report_path = report_path
        headers = {"Accept": "application/json", "user-agent": "Chrome/131 Safari/537.36"}
        flow = _make_flow("api.gc.com", "Chrome/131", headers)
        addon.request(flow)
        assert report_path.exists()
        content = json.loads(report_path.read_text())
        assert "generated_at" in content
        assert "sources" in content

    def test_report_overwritten_not_appended(self, tmp_path: Path) -> None:
        addon = HeaderCapture()
        report_path = tmp_path / "report.json"
        addon.report_path = report_path
        headers = {"Accept": "application/json", "user-agent": "Chrome/131 Safari/537.36"}
        flow = _make_flow("api.gc.com", "Chrome/131", headers)
        addon.request(flow)
        first_size = report_path.stat().st_size
        addon.request(flow)
        second_size = report_path.stat().st_size
        # Overwrite means the file size stays the same (not growing)
        assert second_size == first_size

    def test_unknown_user_agent_source(self, tmp_path: Path) -> None:
        addon = HeaderCapture()
        addon.report_path = tmp_path / "report.json"
        headers = {"Accept": "application/json", "user-agent": "curl/7.81.0"}
        flow = _make_flow("api.gc.com", "curl/7.81.0", headers)
        addon.request(flow)
        assert "unknown" in addon._captured_by_source

    def test_multiple_sources_separate_entries(self, tmp_path: Path) -> None:
        addon = HeaderCapture()
        report_path = tmp_path / "report.json"
        addon.report_path = report_path
        ios_ua = "GameChanger/1234 CFNetwork/1410.0.3 Darwin/22.6.0"
        web_ua = "Mozilla/5.0 Chrome/131.0 Safari/537.36"
        ios_flow = _make_flow("api.gc.com", ios_ua, {"Accept": "app/json", "user-agent": ios_ua})
        web_flow = _make_flow("api.gc.com", web_ua, {"Accept": "text/html", "user-agent": web_ua})
        addon.request(ios_flow)
        addon.request(web_flow)

        assert "ios" in addon._captured_by_source
        assert "web" in addon._captured_by_source

        report = json.loads(report_path.read_text())
        source_names = {s["source"] for s in report["sources"]}
        assert source_names == {"ios", "web"}

    def test_report_dir_created_if_missing(self, tmp_path: Path) -> None:
        addon = HeaderCapture()
        nested_path = tmp_path / "nested" / "dir" / "report.json"
        addon.report_path = nested_path
        headers = {"Accept": "application/json", "user-agent": "Chrome/131 Safari/537.36"}
        flow = _make_flow("api.gc.com", "Chrome/131", headers)
        addon.request(flow)
        assert nested_path.exists()

    def test_session_dir_env_var_routes_output(self, tmp_path: Path, monkeypatch: object) -> None:
        """AC-7: when PROXY_SESSION_DIR is set, report goes to session dir."""
        monkeypatch.setenv("PROXY_SESSION_DIR", str(tmp_path))
        addon = HeaderCapture()
        headers = {"Accept": "application/json", "user-agent": "Chrome/131 Safari/537.36"}
        flow = _make_flow("api.gc.com", "Chrome/131", headers)
        addon.request(flow)

        expected = tmp_path / "header-report.json"
        assert expected.exists()
        content = json.loads(expected.read_text())
        assert "sources" in content

    def test_fallback_path_used_when_no_session_dir(self, monkeypatch: object) -> None:
        """AC-2 fallback: without PROXY_SESSION_DIR, report_path is _REPORT_PATH."""
        monkeypatch.delenv("PROXY_SESSION_DIR", raising=False)
        addon = HeaderCapture()
        assert addon.report_path == _REPORT_PATH
