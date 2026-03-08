"""Tests for ``bb status`` command (src/cli/status.py).

Uses CliRunner for CLI invocation. All external calls (credential checks,
filesystem reads) are mocked so tests never touch the network or real files.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.cli import status as status_module

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _invoke_status(
    *,
    web_result: tuple[int, str] = (0, "valid -- logged in as Jason Smith"),
    mobile_result: tuple[int, str] = (0, "valid -- logged in as Jason Smith"),
    crawled_at: str | None = "2026-03-05T14:30:00Z",
    total_files: int = 47,
    db_exists: bool = True,
    db_display: str = "data/app.db (2.4 MB)",
    sessions: dict | None = None,
):
    """Invoke ``bb status`` with all external dependencies mocked."""
    cred_map = {"web": web_result, "mobile": mobile_result}

    def fake_check_single(profile: str) -> tuple[int, str]:
        return cred_map[profile]

    with (
        patch("src.cli.status.check_single_profile", side_effect=fake_check_single),
        patch(
            "src.cli.status._get_last_crawl", return_value=(crawled_at, total_files)
        ),
        patch(
            "src.cli.status._get_db_info", return_value=(db_exists, db_display)
        ),
        patch(
            "src.cli.status._get_proxy_sessions", return_value=sessions
        ),
    ):
        return runner.invoke(app, ["status"])


# ---------------------------------------------------------------------------
# Credential display
# ---------------------------------------------------------------------------


class TestCredentialDisplay:
    """AC-2: per-profile credential health display."""

    def test_valid_credentials_shown_in_output(self) -> None:
        """Valid creds show 'valid (logged in as NAME)'."""
        result = _invoke_status(
            web_result=(0, "valid -- logged in as Jason Smith"),
            mobile_result=(0, "valid -- logged in as Coach Lee"),
        )
        assert result.exit_code == 0
        assert "valid (logged in as Jason Smith)" in result.output
        assert "valid (logged in as Coach Lee)" in result.output

    def test_expired_credentials_show_remediation_hint(self) -> None:
        """Expired creds show 'expired -> run: bb creds import'."""
        result = _invoke_status(web_result=(1, "Credentials expired"))
        assert "expired -> run: bb creds import" in result.output

    def test_missing_credentials_show_remediation_hint(self) -> None:
        """Missing creds show 'missing -> run: bb creds import'."""
        result = _invoke_status(web_result=(2, "Missing required credential(s)"))
        assert "missing -> run: bb creds import" in result.output

    def test_both_profiles_shown(self) -> None:
        """Both 'web' and 'mobile' profiles appear in output."""
        result = _invoke_status()
        assert "Credentials (web):" in result.output
        assert "Credentials (mobile):" in result.output

    def test_web_expired_mobile_valid_exits_1(self) -> None:
        """Any expired profile causes exit 1."""
        result = _invoke_status(web_result=(1, "expired"))
        assert result.exit_code == 1

    def test_web_missing_exits_1(self) -> None:
        """Missing credential causes exit 1."""
        result = _invoke_status(web_result=(2, "missing"))
        assert result.exit_code == 1

    def test_mobile_expired_exits_1(self) -> None:
        """Expired mobile creds causes exit 1."""
        result = _invoke_status(mobile_result=(1, "expired"))
        assert result.exit_code == 1

    def test_all_valid_exits_0(self) -> None:
        """All valid creds result in exit 0."""
        result = _invoke_status()
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Last crawl display
# ---------------------------------------------------------------------------


class TestLastCrawlDisplay:
    """AC-3: last crawl info display."""

    def test_manifest_present_shows_timestamp_and_files(self) -> None:
        """When manifest present, shows formatted timestamp and file count."""
        result = _invoke_status(crawled_at="2026-03-05T14:30:00Z", total_files=47)
        assert result.exit_code == 0
        assert "2026-03-05 14:30:00" in result.output
        assert "47 files" in result.output

    def test_manifest_absent_shows_never(self) -> None:
        """When no manifest, shows 'never'."""
        result = _invoke_status(crawled_at=None, total_files=0)
        assert result.exit_code == 0
        assert "never" in result.output

    def test_last_crawl_label_present(self) -> None:
        """'Last crawl:' label always appears."""
        result = _invoke_status()
        assert "Last crawl:" in result.output


# ---------------------------------------------------------------------------
# Database display
# ---------------------------------------------------------------------------


class TestDatabaseDisplay:
    """AC-4: database info display."""

    def test_db_present_shows_path_and_size(self) -> None:
        """When DB exists, shows path and human-readable size."""
        result = _invoke_status(db_exists=True, db_display="data/app.db (2.4 MB)")
        assert result.exit_code == 0
        assert "data/app.db (2.4 MB)" in result.output

    def test_db_absent_shows_warning(self) -> None:
        """When DB absent, shows 'not found -> run: bb data sync'."""
        result = _invoke_status(db_exists=False, db_display="")
        assert result.exit_code == 0  # missing DB is NOT an error exit
        assert "not found -> run: bb data sync" in result.output

    def test_db_absent_does_not_cause_exit_1_when_creds_valid(self) -> None:
        """Missing database alone should not cause exit 1 (AC-7)."""
        result = _invoke_status(db_exists=False)
        assert result.exit_code == 0

    def test_db_absent_with_expired_creds_exits_1(self) -> None:
        """Expired creds + missing DB still exits 1 (creds dominate)."""
        result = _invoke_status(db_exists=False, web_result=(1, "expired"))
        assert result.exit_code == 1

    def test_database_label_present(self) -> None:
        """'Database:' label always appears."""
        result = _invoke_status()
        assert "Database:" in result.output


# ---------------------------------------------------------------------------
# Proxy session display
# ---------------------------------------------------------------------------


class TestProxySessionDisplay:
    """AC-5: proxy session info display."""

    def test_sessions_present_shows_total_and_latest(self) -> None:
        """When sessions exist, shows count, latest session ID, and timestamp."""
        sessions = {
            "total": 3,
            "unreviewed": 0,
            "latest_id": "2026-03-06_211209",
            "latest_ts": "2026-03-06T21:12:09Z",
        }
        result = _invoke_status(sessions=sessions)
        assert result.exit_code == 0
        assert "3 total" in result.output
        assert "2026-03-06_211209" in result.output
        assert "2026-03-06 21:12:09" in result.output

    def test_sessions_with_unreviewed_shown(self) -> None:
        """Unreviewed sessions count is shown."""
        sessions = {
            "total": 3,
            "unreviewed": 1,
            "latest_id": "2026-03-06_211209",
            "latest_ts": "2026-03-06T21:12:09Z",
        }
        result = _invoke_status(sessions=sessions)
        assert "1 unreviewed" in result.output

    def test_sessions_absent_shows_none(self) -> None:
        """When no sessions found, shows 'none'."""
        result = _invoke_status(sessions=None)
        assert result.exit_code == 0
        assert "none" in result.output

    def test_proxy_sessions_label_present(self) -> None:
        """'Proxy sessions:' label always appears."""
        result = _invoke_status()
        assert "Proxy sessions:" in result.output


# ---------------------------------------------------------------------------
# Exit code semantics (AC-7)
# ---------------------------------------------------------------------------


class TestExitCodes:
    """AC-7: exit code semantics."""

    def test_all_healthy_exits_0(self) -> None:
        sessions = {"total": 1, "unreviewed": 0, "latest_id": "s1", "latest_ts": None}
        result = _invoke_status(
            db_exists=True,
            crawled_at="2026-03-05T14:30:00Z",
            sessions=sessions,
        )
        assert result.exit_code == 0

    def test_expired_web_exits_1(self) -> None:
        result = _invoke_status(web_result=(1, "expired"))
        assert result.exit_code == 1

    def test_expired_mobile_exits_1(self) -> None:
        result = _invoke_status(mobile_result=(1, "expired"))
        assert result.exit_code == 1

    def test_missing_db_alone_exits_0(self) -> None:
        """Missing database alone does NOT cause exit 1."""
        result = _invoke_status(db_exists=False)
        assert result.exit_code == 0

    def test_no_manifest_alone_exits_0(self) -> None:
        """Missing manifest alone does NOT cause exit 1."""
        result = _invoke_status(crawled_at=None, total_files=0)
        assert result.exit_code == 0

    def test_no_sessions_alone_exits_0(self) -> None:
        """No proxy sessions alone does NOT cause exit 1."""
        result = _invoke_status(sessions=None)
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------


class TestHumanSize:
    """Unit tests for _human_size helper."""

    def test_bytes(self) -> None:
        assert status_module._human_size(512) == "512.0 B"

    def test_kilobytes(self) -> None:
        assert status_module._human_size(2048) == "2.0 KB"

    def test_megabytes(self) -> None:
        assert status_module._human_size(2 * 1024 * 1024) == "2.0 MB"

    def test_gigabytes(self) -> None:
        assert status_module._human_size(3 * 1024 * 1024 * 1024) == "3.0 GB"


class TestFormatCrawledAt:
    """Unit tests for _format_crawled_at helper."""

    def test_converts_iso8601_to_display(self) -> None:
        assert status_module._format_crawled_at("2026-03-05T14:30:00Z") == "2026-03-05 14:30:00"

    def test_no_trailing_z(self) -> None:
        result = status_module._format_crawled_at("2026-03-05T14:30:00Z")
        assert not result.endswith("Z")


class TestGetLastCrawl:
    """Unit tests for _get_last_crawl with real temp files."""

    def test_no_manifests_returns_none(self, tmp_path: Path) -> None:
        """Empty raw data dir returns (None, 0)."""
        with patch.object(status_module, "_RAW_DATA_ROOT", tmp_path):
            ts, total = status_module._get_last_crawl()
        assert ts is None
        assert total == 0

    def test_single_manifest_returns_data(self, tmp_path: Path) -> None:
        """Single manifest returns its crawled_at and file count."""
        season_dir = tmp_path / "2026"
        season_dir.mkdir()
        manifest = {
            "crawled_at": "2026-03-05T14:30:00Z",
            "season": "2026",
            "crawlers": {
                "roster": {"files_written": 20, "files_skipped": 0, "errors": 0},
                "schedule": {"files_written": 27, "files_skipped": 0, "errors": 0},
            },
        }
        (season_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with patch.object(status_module, "_RAW_DATA_ROOT", tmp_path):
            ts, total = status_module._get_last_crawl()
        assert ts == "2026-03-05T14:30:00Z"
        assert total == 47

    def test_multiple_manifests_returns_latest(self, tmp_path: Path) -> None:
        """With multiple manifests, returns the one with the latest crawled_at."""
        for season, ts, files in [
            ("2025", "2025-10-01T10:00:00Z", 10),
            ("2026", "2026-03-05T14:30:00Z", 47),
        ]:
            d = tmp_path / season
            d.mkdir()
            manifest = {
                "crawled_at": ts,
                "season": season,
                "crawlers": {"roster": {"files_written": files, "files_skipped": 0, "errors": 0}},
            }
            (d / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with patch.object(status_module, "_RAW_DATA_ROOT", tmp_path):
            ts, total = status_module._get_last_crawl()
        assert ts == "2026-03-05T14:30:00Z"
        assert total == 47

    def test_malformed_manifest_skipped(self, tmp_path: Path) -> None:
        """Malformed manifest is skipped without crashing."""
        season_dir = tmp_path / "2026"
        season_dir.mkdir()
        (season_dir / "manifest.json").write_text("NOT JSON", encoding="utf-8")
        with patch.object(status_module, "_RAW_DATA_ROOT", tmp_path):
            ts, total = status_module._get_last_crawl()
        assert ts is None
        assert total == 0


class TestGetProxySessions:
    """Unit tests for _get_proxy_sessions with real temp dirs."""

    def test_missing_dir_returns_none(self, tmp_path: Path) -> None:
        """Missing sessions directory returns None."""
        with patch.object(status_module, "_PROXY_SESSIONS_DIR", tmp_path / "nonexistent"):
            result = status_module._get_proxy_sessions()
        assert result is None

    def test_empty_sessions_dir_returns_none(self, tmp_path: Path) -> None:
        """Empty sessions directory returns None."""
        with patch.object(status_module, "_PROXY_SESSIONS_DIR", tmp_path):
            result = status_module._get_proxy_sessions()
        assert result is None

    def test_single_session_returns_summary(self, tmp_path: Path) -> None:
        """Single session returns correct summary."""
        session_dir = tmp_path / "2026-03-06_204244"
        session_dir.mkdir()
        session_data = {
            "session_id": "2026-03-06_204244",
            "profile": "web",
            "started_at": "2026-03-06T20:42:44Z",
            "stopped_at": "2026-03-06T20:59:18Z",
            "status": "closed",
            "endpoint_count": 5872,
            "reviewed": True,
        }
        (session_dir / "session.json").write_text(json.dumps(session_data), encoding="utf-8")
        with patch.object(status_module, "_PROXY_SESSIONS_DIR", tmp_path):
            result = status_module._get_proxy_sessions()
        assert result is not None
        assert result["total"] == 1
        assert result["unreviewed"] == 0
        assert result["latest_id"] == "2026-03-06_204244"

    def test_unreviewed_sessions_counted(self, tmp_path: Path) -> None:
        """Unreviewed sessions are counted correctly."""
        for i, reviewed in enumerate([True, False, False]):
            session_dir = tmp_path / f"2026-03-06_2042{i:02d}"
            session_dir.mkdir()
            session_data = {
                "session_id": f"2026-03-06_2042{i:02d}",
                "started_at": f"2026-03-06T20:42:0{i}Z",
                "reviewed": reviewed,
            }
            (session_dir / "session.json").write_text(json.dumps(session_data), encoding="utf-8")
        with patch.object(status_module, "_PROXY_SESSIONS_DIR", tmp_path):
            result = status_module._get_proxy_sessions()
        assert result is not None
        assert result["total"] == 3
        assert result["unreviewed"] == 2

    def test_session_dir_without_json_skipped(self, tmp_path: Path) -> None:
        """Session directory without session.json is gracefully skipped."""
        (tmp_path / "2026-03-06_204244").mkdir()
        with patch.object(status_module, "_PROXY_SESSIONS_DIR", tmp_path):
            result = status_module._get_proxy_sessions()
        assert result is None

    def test_malformed_session_json_skipped(self, tmp_path: Path) -> None:
        """Malformed session.json is skipped without crashing."""
        session_dir = tmp_path / "2026-03-06_204244"
        session_dir.mkdir()
        (session_dir / "session.json").write_text("NOT JSON", encoding="utf-8")
        with patch.object(status_module, "_PROXY_SESSIONS_DIR", tmp_path):
            result = status_module._get_proxy_sessions()
        assert result is None


class TestGetDbInfo:
    """Unit tests for _get_db_info with temp files."""

    def test_db_not_found_returns_false(self, tmp_path: Path) -> None:
        """Missing DB returns (False, '')."""
        fake_db = tmp_path / "app.db"
        with patch.object(status_module, "_DB_PATH", fake_db):
            exists, display = status_module._get_db_info()
        assert exists is False
        assert display == ""

    def test_db_present_returns_true_with_display(self, tmp_path: Path) -> None:
        """Existing DB returns (True, display_string) with path and size."""
        fake_db = tmp_path / "app.db"
        fake_db.write_bytes(b"x" * 2048)  # 2 KB
        with (
            patch.object(status_module, "_DB_PATH", fake_db),
            patch.object(status_module, "_PROJECT_ROOT", tmp_path),
        ):
            exists, display = status_module._get_db_info()
        assert exists is True
        assert "app.db" in display
        assert "2.0 KB" in display
