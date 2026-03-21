# synthetic-test-data
"""Tests for src/pipeline/trigger.py -- background crawl trigger functions.

Verifies that crawl_jobs rows are updated to the correct terminal status
and that teams.last_synced is updated on success (and NOT updated on failure)
for both run_member_sync and run_scouting_sync.

HTTP and pipeline modules are mocked; a real SQLite database is used to
verify DB state changes.

Run with:
    pytest tests/test_trigger.py -v
"""

from __future__ import annotations

import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from migrations.apply_migrations import run_migrations  # noqa: E402
from src.gamechanger.crawlers import CrawlResult  # noqa: E402
from src.gamechanger.loaders import LoadResult  # noqa: E402
from src.pipeline import trigger  # noqa: E402


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    """Create a migrated test database with a single member team."""
    db_path = tmp_path / "test_trigger.db"
    run_migrations(db_path=db_path)
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute(
            "INSERT INTO teams (id, name, membership_type) VALUES (1, 'LSB Varsity', 'member')"
        )
        conn.commit()
    return db_path


def _insert_crawl_job(db_path: Path, team_id: int, sync_type: str) -> int:
    """Insert a running crawl_job row and return its id."""
    with closing(sqlite3.connect(str(db_path))) as conn:
        cur = conn.execute(
            "INSERT INTO crawl_jobs (team_id, sync_type, status, started_at) "
            "VALUES (?, ?, 'running', datetime('now'))",
            (team_id, sync_type),
        )
        conn.commit()
        return cur.lastrowid


def _get_crawl_job(db_path: Path, job_id: int) -> dict:
    """Return status, completed_at, error_message for a crawl_jobs row."""
    with closing(sqlite3.connect(str(db_path))) as conn:
        row = conn.execute(
            "SELECT status, completed_at, error_message FROM crawl_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    return {"status": row[0], "completed_at": row[1], "error_message": row[2]}


def _get_last_synced(db_path: Path, team_id: int) -> str | None:
    """Return teams.last_synced for the given team, or None if not set."""
    with closing(sqlite3.connect(str(db_path))) as conn:
        row = conn.execute(
            "SELECT last_synced FROM teams WHERE id = ?", (team_id,)
        ).fetchone()
    return row[0] if row else None


def _insert_scouting_run(
    db_path: Path, team_id: int, season_id: str = "2025"
) -> None:
    """Pre-insert a scouting_runs row visible after the mock crawl completes.

    Uses a far-future last_checked so that trigger.py's
    ``last_checked >= started_at`` filter always matches.
    """
    with closing(sqlite3.connect(str(db_path))) as conn:
        # seasons FK required
        conn.execute(
            "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) "
            "VALUES (?, 'Spring 2025', 'spring-hs', 2025)",
            (season_id,),
        )
        conn.execute(
            "INSERT INTO scouting_runs "
            "(team_id, season_id, status, last_checked) "
            "VALUES (?, ?, 'running', '2099-12-31T00:00:00.000Z')",
            (team_id, season_id),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# run_member_sync
# ---------------------------------------------------------------------------


class TestMemberSync:
    def test_auth_failure_marks_job_failed_no_last_synced(self, tmp_path: Path) -> None:
        db_path = _make_db(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "member_crawl")

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch(
                "src.pipeline.trigger._refresh_auth_token",
                side_effect=RuntimeError("no credentials"),
            ),
        ):
            trigger.run_member_sync(1, "LSB Varsity", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "failed"
        assert "Auth refresh failed" in job["error_message"]
        assert "no credentials" in job["error_message"]
        assert _get_last_synced(db_path, 1) is None

    def test_pipeline_raises_marks_job_failed_no_last_synced(self, tmp_path: Path) -> None:
        db_path = _make_db(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "member_crawl")

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch(
                "src.pipeline.trigger.crawl_module.run",
                side_effect=RuntimeError("crawl exploded"),
            ),
        ):
            trigger.run_member_sync(1, "LSB Varsity", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "failed"
        assert "crawl exploded" in job["error_message"]
        assert _get_last_synced(db_path, 1) is None

    def test_nonzero_exit_marks_job_failed_no_last_synced(self, tmp_path: Path) -> None:
        db_path = _make_db(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "member_crawl")

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.crawl_module.run", return_value=1),
            patch("src.pipeline.trigger.load_module.run", return_value=0),
        ):
            trigger.run_member_sync(1, "LSB Varsity", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "failed"
        assert "crawl_exit=1" in job["error_message"]
        assert _get_last_synced(db_path, 1) is None

    def test_success_marks_job_completed_updates_last_synced(self, tmp_path: Path) -> None:
        db_path = _make_db(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "member_crawl")

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.crawl_module.run", return_value=0),
            patch("src.pipeline.trigger.load_module.run", return_value=0),
        ):
            trigger.run_member_sync(1, "LSB Varsity", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "completed"
        assert job["completed_at"] is not None
        assert job["error_message"] is None
        assert _get_last_synced(db_path, 1) is not None


# ---------------------------------------------------------------------------
# run_scouting_sync
# ---------------------------------------------------------------------------


class TestScoutingSync:
    def test_auth_failure_marks_job_failed_no_last_synced(self, tmp_path: Path) -> None:
        db_path = _make_db(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "scouting_crawl")

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch(
                "src.pipeline.trigger._refresh_auth_token",
                side_effect=RuntimeError("no credentials"),
            ),
        ):
            trigger.run_scouting_sync(1, "test-team-slug", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "failed"
        assert "Auth refresh failed" in job["error_message"]
        assert _get_last_synced(db_path, 1) is None

    def test_crawl_errors_marks_job_failed_no_last_synced(self, tmp_path: Path) -> None:
        db_path = _make_db(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "scouting_crawl")

        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = CrawlResult(errors=1, files_written=0)

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.ScoutingCrawler", return_value=mock_crawler),
        ):
            trigger.run_scouting_sync(1, "test-team-slug", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "failed"
        assert _get_last_synced(db_path, 1) is None

    def test_load_failure_marks_job_failed_updates_scouting_run(
        self, tmp_path: Path
    ) -> None:
        db_path = _make_db(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "scouting_crawl")
        _insert_scouting_run(db_path, team_id=1, season_id="2025")

        scouting_dir = tmp_path / "raw" / "2025" / "scouting" / "test-team-slug"
        scouting_dir.mkdir(parents=True)

        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = CrawlResult(files_written=3)
        mock_loader = MagicMock()
        mock_loader.load_team.side_effect = RuntimeError("load crashed")

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.ScoutingCrawler", return_value=mock_crawler),
            patch("src.pipeline.trigger.ScoutingLoader", return_value=mock_loader),
            patch("src.pipeline.trigger._DATA_ROOT", tmp_path / "raw"),
        ):
            trigger.run_scouting_sync(1, "test-team-slug", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "failed"
        mock_crawler.update_run_load_status.assert_called_once_with(1, "2025", "failed")
        assert _get_last_synced(db_path, 1) is None

    def test_success_marks_job_completed_updates_last_synced(
        self, tmp_path: Path
    ) -> None:
        db_path = _make_db(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "scouting_crawl")
        _insert_scouting_run(db_path, team_id=1, season_id="2025")

        scouting_dir = tmp_path / "raw" / "2025" / "scouting" / "test-team-slug"
        scouting_dir.mkdir(parents=True)

        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = CrawlResult(files_written=3)
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5, errors=0)

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.ScoutingCrawler", return_value=mock_crawler),
            patch("src.pipeline.trigger.ScoutingLoader", return_value=mock_loader),
            patch("src.pipeline.trigger._DATA_ROOT", tmp_path / "raw"),
        ):
            trigger.run_scouting_sync(1, "test-team-slug", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "completed"
        assert job["completed_at"] is not None
        assert job["error_message"] is None
        mock_crawler.update_run_load_status.assert_called_once_with(1, "2025", "completed")
        assert _get_last_synced(db_path, 1) is not None
