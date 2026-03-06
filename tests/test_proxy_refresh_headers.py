"""Unit tests for scripts/proxy-refresh-headers.py.

Tests cover dry-run output, apply mode writing, excluded header filtering,
single-source partial update, missing report file error, and round-trip
(generated file is importable and contains correct values).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import textwrap
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Import the script under test
# ---------------------------------------------------------------------------

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "proxy-refresh-headers.py"


def _load_script() -> ModuleType:
    """Load proxy-refresh-headers.py as a module without executing __main__."""
    spec = importlib.util.spec_from_file_location("proxy_refresh_headers", _SCRIPT_PATH)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_mod = _load_script()

extract_headers_by_source = _mod.extract_headers_by_source
generate_headers_file = _mod.generate_headers_file
parse_existing_headers = _mod.parse_existing_headers
run = _mod.run
_EXCLUDED_HEADERS = _mod._EXCLUDED_HEADERS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MINIMAL_BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 Chrome/145",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "DNT": "1",
}

_MINIMAL_MOBILE_HEADERS: dict[str, str] = {
    "User-Agent": "Odyssey/2026.7.0 Alamofire/5.9.0",
    "Accept-Language": "en-US;q=1.0",
    "Accept-Encoding": "br;q=1.0, gzip;q=0.9",
    "gc-app-version": "2026.7.0.0",
}

_MINIMAL_EXISTING_HEADERS_PY = textwrap.dedent(
    """\
    from __future__ import annotations

    BROWSER_HEADERS: dict[str, str] = {
        "DNT": "1",
        "Accept-Language": "en-US,en;q=0.9",
    }

    MOBILE_HEADERS: dict[str, str] = {
        "Accept-Language": "en-US;q=1.0",
    }
    """
)


def _make_report(sources: list[dict]) -> dict:
    """Build a minimal header report dict."""
    return {
        "generated_at": "2026-03-06T00:00:00+00:00",
        "sources": sources,
    }


# ---------------------------------------------------------------------------
# extract_headers_by_source()
# ---------------------------------------------------------------------------


class TestExtractHeadersBySource:
    def test_web_source_extracted(self) -> None:
        report = _make_report(
            [{"source": "web", "captured_headers": {"Accept-Language": "en-US"}}]
        )
        result = extract_headers_by_source(report)
        assert "web" in result
        assert result["web"]["Accept-Language"] == "en-US"

    def test_ios_source_extracted(self) -> None:
        report = _make_report(
            [{"source": "ios", "captured_headers": {"Accept-Language": "en-US;q=1.0"}}]
        )
        result = extract_headers_by_source(report)
        assert "ios" in result

    def test_unknown_source_ignored(self) -> None:
        report = _make_report(
            [{"source": "unknown", "captured_headers": {"Accept-Language": "en-US"}}]
        )
        result = extract_headers_by_source(report)
        assert "unknown" not in result
        assert result == {}

    def test_credential_headers_excluded(self) -> None:
        report = _make_report(
            [
                {
                    "source": "web",
                    "captured_headers": {
                        "gc-token": "secret",
                        "gc-device-id": "dev123",
                        "gc-signature": "sig",
                        "gc-app-name": "app",
                        "cookie": "session=x",
                        "Accept-Language": "en-US",
                    },
                }
            ]
        )
        result = extract_headers_by_source(report)
        web = result["web"]
        for cred in ("gc-token", "gc-device-id", "gc-signature", "gc-app-name", "cookie"):
            assert cred not in {k.lower() for k in web}

    def test_per_request_headers_excluded(self) -> None:
        report = _make_report(
            [
                {
                    "source": "web",
                    "captured_headers": {
                        "content-type": "application/json",
                        "accept": "text/html",
                        "gc-user-action-id": "abc",
                        "gc-user-action": "data_loading:team",
                        "x-pagination": "true",
                        "Accept-Language": "en-US",
                    },
                }
            ]
        )
        result = extract_headers_by_source(report)
        web = result["web"]
        for per_req in ("content-type", "accept", "gc-user-action-id", "gc-user-action", "x-pagination"):
            assert per_req not in {k.lower() for k in web}

    def test_connection_headers_excluded(self) -> None:
        report = _make_report(
            [
                {
                    "source": "web",
                    "captured_headers": {
                        "host": "api.gc.com",
                        "connection": "keep-alive",
                        "content-length": "0",
                        "transfer-encoding": "chunked",
                        "Accept-Language": "en-US",
                    },
                }
            ]
        )
        result = extract_headers_by_source(report)
        web = result["web"]
        for conn in ("host", "connection", "content-length", "transfer-encoding"):
            assert conn not in {k.lower() for k in web}

    def test_empty_sources_returns_empty(self) -> None:
        report = _make_report([])
        assert extract_headers_by_source(report) == {}


# ---------------------------------------------------------------------------
# generate_headers_file() and round-trip
# ---------------------------------------------------------------------------


class TestGenerateHeadersFile:
    def test_output_is_importable(self, tmp_path: Path) -> None:
        """Generated file can be exec'd without errors."""
        content = generate_headers_file(
            _MINIMAL_BROWSER_HEADERS, _MINIMAL_MOBILE_HEADERS, "2026-03-06"
        )
        ns: dict = {}
        exec(compile(content, "<test>", "exec"), ns)  # noqa: S102
        assert "BROWSER_HEADERS" in ns
        assert "MOBILE_HEADERS" in ns

    def test_browser_headers_preserved(self) -> None:
        content = generate_headers_file(
            _MINIMAL_BROWSER_HEADERS, _MINIMAL_MOBILE_HEADERS, "2026-03-06"
        )
        ns: dict = {}
        exec(compile(content, "<test>", "exec"), ns)  # noqa: S102
        assert ns["BROWSER_HEADERS"]["DNT"] == "1"
        assert ns["BROWSER_HEADERS"]["Accept-Language"] == "en-US,en;q=0.9"

    def test_mobile_headers_preserved(self) -> None:
        content = generate_headers_file(
            _MINIMAL_BROWSER_HEADERS, _MINIMAL_MOBILE_HEADERS, "2026-03-06"
        )
        ns: dict = {}
        exec(compile(content, "<test>", "exec"), ns)  # noqa: S102
        assert ns["MOBILE_HEADERS"]["gc-app-version"] == "2026.7.0.0"

    def test_source_date_in_docstring(self) -> None:
        content = generate_headers_file(
            _MINIMAL_BROWSER_HEADERS, _MINIMAL_MOBILE_HEADERS, "2026-03-06"
        )
        assert "2026-03-06" in content

    def test_module_docstring_present(self) -> None:
        content = generate_headers_file(
            _MINIMAL_BROWSER_HEADERS, _MINIMAL_MOBILE_HEADERS, "2026-03-06"
        )
        assert '"""' in content

    def test_future_annotation_import_present(self) -> None:
        content = generate_headers_file(
            _MINIMAL_BROWSER_HEADERS, _MINIMAL_MOBILE_HEADERS, "2026-03-06"
        )
        assert "from __future__ import annotations" in content

    def test_dict_variable_names_preserved(self) -> None:
        content = generate_headers_file(
            _MINIMAL_BROWSER_HEADERS, _MINIMAL_MOBILE_HEADERS, "2026-03-06"
        )
        assert "BROWSER_HEADERS" in content
        assert "MOBILE_HEADERS" in content

    def test_round_trip_correct_values(self) -> None:
        """Values written into the file match those passed in."""
        browser = {"Accept-Language": "en-US,en;q=0.9", "DNT": "1"}
        mobile = {"Accept-Language": "en-US;q=1.0", "gc-app-version": "2026.7.0.0"}
        content = generate_headers_file(browser, mobile, "2026-03-06")
        ns: dict = {}
        exec(compile(content, "<test>", "exec"), ns)  # noqa: S102
        assert ns["BROWSER_HEADERS"] == browser
        assert ns["MOBILE_HEADERS"] == mobile


# ---------------------------------------------------------------------------
# parse_existing_headers()
# ---------------------------------------------------------------------------


class TestParseExistingHeaders:
    def test_parses_browser_headers(self) -> None:
        result = parse_existing_headers(_MINIMAL_EXISTING_HEADERS_PY)
        assert "BROWSER_HEADERS" in result
        assert result["BROWSER_HEADERS"]["DNT"] == "1"

    def test_parses_mobile_headers(self) -> None:
        result = parse_existing_headers(_MINIMAL_EXISTING_HEADERS_PY)
        assert "MOBILE_HEADERS" in result
        assert result["MOBILE_HEADERS"]["Accept-Language"] == "en-US;q=1.0"


# ---------------------------------------------------------------------------
# run() -- integration scenarios
# ---------------------------------------------------------------------------


class TestRunDryRun:
    def test_missing_report_exits_1(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        with (
            patch.object(_mod, "_REPORT_PATH_SESSION", tmp_path / "no-session.json"),
            patch.object(_mod, "_REPORT_PATH_FLAT", tmp_path / "no-flat.json"),
        ):
            exit_code = run(apply=False)
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "No capture data found" in captured.err

    def test_dry_run_prints_diff(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Dry run should print a diff when headers differ."""
        report = _make_report(
            [
                {
                    "source": "web",
                    "captured_headers": {"Accept-Language": "en-GB"},
                }
            ]
        )
        report_file = tmp_path / "header-report.json"
        report_file.write_text(json.dumps(report), encoding="utf-8")

        fake_existing = _MINIMAL_EXISTING_HEADERS_PY
        with (
            patch.object(_mod, "_REPORT_PATH_SESSION", tmp_path / "no-session.json"),
            patch.object(_mod, "_REPORT_PATH_FLAT", report_file),
            patch.object(_mod, "_HEADERS_PATH", tmp_path / "headers.py"),
        ):
            (tmp_path / "headers.py").write_text(fake_existing, encoding="utf-8")
            exit_code = run(apply=False)

        assert exit_code == 0
        captured = capsys.readouterr()
        # Diff output should appear on stdout
        assert "---" in captured.out or "+++" in captured.out or "No changes" in captured.out

    def test_dry_run_does_not_write_file(self, tmp_path: Path) -> None:
        report = _make_report(
            [{"source": "web", "captured_headers": {"Accept-Language": "en-GB"}}]
        )
        report_file = tmp_path / "header-report.json"
        report_file.write_text(json.dumps(report), encoding="utf-8")

        headers_file = tmp_path / "headers.py"
        headers_file.write_text(_MINIMAL_EXISTING_HEADERS_PY, encoding="utf-8")
        original_mtime = headers_file.stat().st_mtime

        with (
            patch.object(_mod, "_REPORT_PATH_SESSION", tmp_path / "no-session.json"),
            patch.object(_mod, "_REPORT_PATH_FLAT", report_file),
            patch.object(_mod, "_HEADERS_PATH", headers_file),
        ):
            run(apply=False)

        # File should be unchanged
        assert headers_file.stat().st_mtime == original_mtime


class TestRunApply:
    def test_apply_writes_file(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        report = _make_report(
            [
                {
                    "source": "web",
                    "captured_headers": {
                        "Accept-Language": "en-GB",
                        "DNT": "1",
                    },
                }
            ]
        )
        report_file = tmp_path / "header-report.json"
        report_file.write_text(json.dumps(report), encoding="utf-8")

        headers_file = tmp_path / "headers.py"
        headers_file.write_text(_MINIMAL_EXISTING_HEADERS_PY, encoding="utf-8")

        with (
            patch.object(_mod, "_REPORT_PATH_SESSION", tmp_path / "no-session.json"),
            patch.object(_mod, "_REPORT_PATH_FLAT", report_file),
            patch.object(_mod, "_HEADERS_PATH", headers_file),
        ):
            exit_code = run(apply=True)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Written" in captured.out

        # File was actually written
        content = headers_file.read_text(encoding="utf-8")
        ns: dict = {}
        exec(compile(content, "<test>", "exec"), ns)  # noqa: S102
        assert ns["BROWSER_HEADERS"]["Accept-Language"] == "en-GB"

    def test_apply_summary_lists_updated_sources(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        report = _make_report(
            [
                {"source": "web", "captured_headers": {"DNT": "1"}},
                {
                    "source": "ios",
                    "captured_headers": {"gc-app-version": "2026.7.0.0"},
                },
            ]
        )
        report_file = tmp_path / "header-report.json"
        report_file.write_text(json.dumps(report), encoding="utf-8")

        headers_file = tmp_path / "headers.py"
        headers_file.write_text(_MINIMAL_EXISTING_HEADERS_PY, encoding="utf-8")

        with (
            patch.object(_mod, "_REPORT_PATH_SESSION", tmp_path / "no-session.json"),
            patch.object(_mod, "_REPORT_PATH_FLAT", report_file),
            patch.object(_mod, "_HEADERS_PATH", headers_file),
        ):
            run(apply=True)

        captured = capsys.readouterr()
        assert "BROWSER_HEADERS" in captured.out
        assert "MOBILE_HEADERS" in captured.out


class TestRunSingleSource:
    def test_web_only_leaves_mobile_unchanged(self, tmp_path: Path) -> None:
        """When only web is in the capture, MOBILE_HEADERS is taken from existing file."""
        original_mobile = {"Accept-Language": "en-AU;q=1.0"}
        existing = textwrap.dedent(
            f"""\
            from __future__ import annotations
            BROWSER_HEADERS: dict[str, str] = {{"DNT": "0"}}
            MOBILE_HEADERS: dict[str, str] = {json.dumps(original_mobile)}
            """
        )
        report = _make_report(
            [{"source": "web", "captured_headers": {"DNT": "1"}}]
        )
        report_file = tmp_path / "header-report.json"
        report_file.write_text(json.dumps(report), encoding="utf-8")

        headers_file = tmp_path / "headers.py"
        headers_file.write_text(existing, encoding="utf-8")

        with (
            patch.object(_mod, "_REPORT_PATH_SESSION", tmp_path / "no-session.json"),
            patch.object(_mod, "_REPORT_PATH_FLAT", report_file),
            patch.object(_mod, "_HEADERS_PATH", headers_file),
        ):
            run(apply=True)

        content = headers_file.read_text(encoding="utf-8")
        ns: dict = {}
        exec(compile(content, "<test>", "exec"), ns)  # noqa: S102
        assert ns["MOBILE_HEADERS"] == original_mobile

    def test_ios_only_leaves_browser_unchanged(self, tmp_path: Path) -> None:
        """When only ios is in the capture, BROWSER_HEADERS is taken from existing file."""
        original_browser = {"DNT": "1", "Accept-Language": "en-US,en;q=0.9"}
        existing = textwrap.dedent(
            f"""\
            from __future__ import annotations
            BROWSER_HEADERS: dict[str, str] = {json.dumps(original_browser)}
            MOBILE_HEADERS: dict[str, str] = {{"Accept-Language": "en-OLD"}}
            """
        )
        report = _make_report(
            [
                {
                    "source": "ios",
                    "captured_headers": {"gc-app-version": "2026.7.0.0"},
                }
            ]
        )
        report_file = tmp_path / "header-report.json"
        report_file.write_text(json.dumps(report), encoding="utf-8")

        headers_file = tmp_path / "headers.py"
        headers_file.write_text(existing, encoding="utf-8")

        with (
            patch.object(_mod, "_REPORT_PATH_SESSION", tmp_path / "no-session.json"),
            patch.object(_mod, "_REPORT_PATH_FLAT", report_file),
            patch.object(_mod, "_HEADERS_PATH", headers_file),
        ):
            run(apply=True)

        content = headers_file.read_text(encoding="utf-8")
        ns: dict = {}
        exec(compile(content, "<test>", "exec"), ns)  # noqa: S102
        assert ns["BROWSER_HEADERS"] == original_browser


class TestRunReportPathFallback:
    def test_session_path_preferred_over_flat(self, tmp_path: Path) -> None:
        """Session-aware path is tried first when both exist."""
        session_report = _make_report(
            [{"source": "web", "captured_headers": {"DNT": "SESSION"}}]
        )
        flat_report = _make_report(
            [{"source": "web", "captured_headers": {"DNT": "FLAT"}}]
        )
        session_file = tmp_path / "session-report.json"
        flat_file = tmp_path / "flat-report.json"
        session_file.write_text(json.dumps(session_report), encoding="utf-8")
        flat_file.write_text(json.dumps(flat_report), encoding="utf-8")

        headers_file = tmp_path / "headers.py"
        headers_file.write_text(_MINIMAL_EXISTING_HEADERS_PY, encoding="utf-8")

        with (
            patch.object(_mod, "_REPORT_PATH_SESSION", session_file),
            patch.object(_mod, "_REPORT_PATH_FLAT", flat_file),
            patch.object(_mod, "_HEADERS_PATH", headers_file),
        ):
            run(apply=True)

        content = headers_file.read_text(encoding="utf-8")
        ns: dict = {}
        exec(compile(content, "<test>", "exec"), ns)  # noqa: S102
        assert ns["BROWSER_HEADERS"]["DNT"] == "SESSION"

    def test_flat_path_used_when_session_missing(self, tmp_path: Path) -> None:
        flat_report = _make_report(
            [{"source": "web", "captured_headers": {"DNT": "FLAT"}}]
        )
        flat_file = tmp_path / "flat-report.json"
        flat_file.write_text(json.dumps(flat_report), encoding="utf-8")

        headers_file = tmp_path / "headers.py"
        headers_file.write_text(_MINIMAL_EXISTING_HEADERS_PY, encoding="utf-8")

        with (
            patch.object(_mod, "_REPORT_PATH_SESSION", tmp_path / "no-session.json"),
            patch.object(_mod, "_REPORT_PATH_FLAT", flat_file),
            patch.object(_mod, "_HEADERS_PATH", headers_file),
        ):
            exit_code = run(apply=True)

        assert exit_code == 0
        content = headers_file.read_text(encoding="utf-8")
        ns: dict = {}
        exec(compile(content, "<test>", "exec"), ns)  # noqa: S102
        assert ns["BROWSER_HEADERS"]["DNT"] == "FLAT"
