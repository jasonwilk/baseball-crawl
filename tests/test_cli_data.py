"""Tests for src/cli/data.py -- bb data sub-commands."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.cli.data import _find_scouting_run, _load_all_scouted

runner = CliRunner()


# ---------------------------------------------------------------------------
# bb data sync
# ---------------------------------------------------------------------------


def test_sync_default_args() -> None:
    """sync calls bootstrap.run with default arguments."""
    with patch("src.pipeline.bootstrap.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "sync"])
    mock_run.assert_called_once_with(check_only=False, profile="web", dry_run=False)
    assert result.exit_code == 0


def test_sync_check_only() -> None:
    """sync --check-only forwards check_only=True."""
    with patch("src.pipeline.bootstrap.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "sync", "--check-only"])
    mock_run.assert_called_once_with(check_only=True, profile="web", dry_run=False)
    assert result.exit_code == 0


def test_sync_profile_mobile() -> None:
    """sync --profile mobile forwards profile='mobile'."""
    with patch("src.pipeline.bootstrap.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "sync", "--profile", "mobile"])
    mock_run.assert_called_once_with(check_only=False, profile="mobile", dry_run=False)
    assert result.exit_code == 0


def test_sync_dry_run() -> None:
    """sync --dry-run forwards dry_run=True."""
    with patch("src.pipeline.bootstrap.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "sync", "--dry-run"])
    mock_run.assert_called_once_with(check_only=False, profile="web", dry_run=True)
    assert result.exit_code == 0


def test_sync_propagates_nonzero_exit() -> None:
    """sync propagates non-zero exit codes from bootstrap.run."""
    with patch("src.pipeline.bootstrap.run", return_value=1):
        result = runner.invoke(app, ["data", "sync"])
    assert result.exit_code == 1


def test_sync_has_no_source_flag() -> None:
    """sync intentionally has no --source flag."""
    result = runner.invoke(app, ["data", "sync", "--source", "db"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# bb data crawl
# ---------------------------------------------------------------------------


def test_crawl_default_args() -> None:
    """crawl calls crawl.run with default arguments."""
    with patch("src.pipeline.crawl.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "crawl"])
    mock_run.assert_called_once_with(
        dry_run=False,
        crawler_filter=None,
        profile="web",
        source="yaml",
    )
    assert result.exit_code == 0


def test_crawl_dry_run() -> None:
    """crawl --dry-run forwards dry_run=True."""
    with patch("src.pipeline.crawl.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "crawl", "--dry-run"])
    mock_run.assert_called_once_with(
        dry_run=True,
        crawler_filter=None,
        profile="web",
        source="yaml",
    )
    assert result.exit_code == 0


def test_crawl_with_crawler_filter() -> None:
    """crawl --crawler roster forwards crawler_filter='roster'."""
    with patch("src.pipeline.crawl.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "crawl", "--crawler", "roster"])
    mock_run.assert_called_once_with(
        dry_run=False,
        crawler_filter="roster",
        profile="web",
        source="yaml",
    )
    assert result.exit_code == 0


def test_crawl_with_profile() -> None:
    """crawl --profile mobile forwards profile='mobile'."""
    with patch("src.pipeline.crawl.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "crawl", "--profile", "mobile"])
    mock_run.assert_called_once_with(
        dry_run=False,
        crawler_filter=None,
        profile="mobile",
        source="yaml",
    )
    assert result.exit_code == 0


def test_crawl_source_db() -> None:
    """crawl --source db forwards source='db'."""
    with patch("src.pipeline.crawl.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "crawl", "--source", "db"])
    mock_run.assert_called_once_with(
        dry_run=False,
        crawler_filter=None,
        profile="web",
        source="db",
    )
    assert result.exit_code == 0


def test_crawl_source_yaml_explicit() -> None:
    """crawl --source yaml explicitly forwards source='yaml'."""
    with patch("src.pipeline.crawl.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "crawl", "--source", "yaml"])
    mock_run.assert_called_once_with(
        dry_run=False,
        crawler_filter=None,
        profile="web",
        source="yaml",
    )
    assert result.exit_code == 0


def test_crawl_invalid_crawler_name() -> None:
    """crawl rejects unrecognised --crawler names with exit code 1."""
    with patch("src.pipeline.crawl.run", return_value=0):
        result = runner.invoke(app, ["data", "crawl", "--crawler", "nonexistent"])
    assert result.exit_code == 1


def test_crawl_all_valid_crawler_names() -> None:
    """crawl accepts all documented crawler names."""
    valid_names = ["roster", "schedule", "opponent", "player-stats", "game-stats", "spray-chart"]
    for name in valid_names:
        with patch("src.pipeline.crawl.run", return_value=0) as mock_run:
            result = runner.invoke(app, ["data", "crawl", "--crawler", name])
        assert result.exit_code == 0, f"Crawler '{name}' should be valid"
        mock_run.assert_called_once_with(
            dry_run=False,
            crawler_filter=name,
            profile="web",
            source="yaml",
        )


# ---------------------------------------------------------------------------
# bb data load
# ---------------------------------------------------------------------------


def test_load_default_args() -> None:
    """load calls load.run with default arguments."""
    with patch("src.pipeline.load.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "load"])
    mock_run.assert_called_once_with(
        dry_run=False,
        loader_filter=None,
        source="yaml",
    )
    assert result.exit_code == 0


def test_load_dry_run() -> None:
    """load --dry-run forwards dry_run=True."""
    with patch("src.pipeline.load.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "load", "--dry-run"])
    mock_run.assert_called_once_with(
        dry_run=True,
        loader_filter=None,
        source="yaml",
    )
    assert result.exit_code == 0


def test_load_with_loader_filter() -> None:
    """load --loader roster forwards loader_filter='roster'."""
    with patch("src.pipeline.load.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "load", "--loader", "roster"])
    mock_run.assert_called_once_with(
        dry_run=False,
        loader_filter="roster",
        source="yaml",
    )
    assert result.exit_code == 0


def test_load_source_db() -> None:
    """load --source db forwards source='db'."""
    with patch("src.pipeline.load.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "load", "--source", "db"])
    mock_run.assert_called_once_with(
        dry_run=False,
        loader_filter=None,
        source="db",
    )
    assert result.exit_code == 0


def test_load_source_yaml_explicit() -> None:
    """load --source yaml explicitly forwards source='yaml'."""
    with patch("src.pipeline.load.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "load", "--source", "yaml"])
    mock_run.assert_called_once_with(
        dry_run=False,
        loader_filter=None,
        source="yaml",
    )
    assert result.exit_code == 0


def test_load_invalid_loader_name() -> None:
    """load rejects unrecognised --loader names with exit code 1."""
    with patch("src.pipeline.load.run", return_value=0):
        result = runner.invoke(app, ["data", "load", "--loader", "nonexistent"])
    assert result.exit_code == 1


def test_load_all_valid_loader_names() -> None:
    """load accepts all documented loader names."""
    valid_names = ["roster", "schedule", "game", "season-stats"]
    for name in valid_names:
        with patch("src.pipeline.load.run", return_value=0) as mock_run:
            result = runner.invoke(app, ["data", "load", "--loader", name])
        assert result.exit_code == 0, f"Loader '{name}' should be valid"
        mock_run.assert_called_once_with(
            dry_run=False,
            loader_filter=name,
            source="yaml",
        )


# ---------------------------------------------------------------------------
# bb data --help
# ---------------------------------------------------------------------------


def test_data_help_lists_commands() -> None:
    """bb data --help lists sync, crawl, and load commands."""
    result = runner.invoke(app, ["data", "--help"])
    assert result.exit_code == 0
    assert "sync" in result.output
    assert "crawl" in result.output
    assert "load" in result.output


# ---------------------------------------------------------------------------
# bb data resolve-opponents
# ---------------------------------------------------------------------------


def _make_mock_resolver(
    resolved: int = 1,
    unlinked: int = 0,
    stored_hidden: int = 0,
    resolve_errors: int = 0,
    unlinked_resolved: int = 0,
    follow_bridge_failed: int = 0,
    unlinked_errors: int = 0,
) -> MagicMock:
    """Build a mock OpponentResolver with pre-configured resolve() and resolve_unlinked() return values."""
    mock_resolve_result = MagicMock()
    mock_resolve_result.resolved = resolved
    mock_resolve_result.unlinked = unlinked
    mock_resolve_result.stored_hidden = stored_hidden
    mock_resolve_result.errors = resolve_errors

    mock_unlinked_result = MagicMock()
    mock_unlinked_result.resolved = unlinked_resolved
    mock_unlinked_result.follow_bridge_failed = follow_bridge_failed
    mock_unlinked_result.errors = unlinked_errors

    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = mock_resolve_result
    mock_resolver.resolve_unlinked.return_value = mock_unlinked_result
    return mock_resolver


def test_resolve_opponents_passes_db_path_to_load_config() -> None:
    """resolve_opponents() calls load_config with the db_path keyword argument.

    This is a regression test for the bug fixed in E-120-01 where load_config()
    was called without db_path, causing it to always use the default path.
    """
    fake_db_path = Path("/fake/path/app.db")

    with (
        patch("src.cli.data._resolve_db_path", return_value=fake_db_path),
        patch("src.gamechanger.config.load_config") as mock_load_config,
        patch("src.gamechanger.client.GameChangerClient"),
        patch(
            "src.gamechanger.crawlers.opponent_resolver.OpponentResolver"
        ) as mock_resolver_cls,
        patch("src.cli.data.sqlite3.connect"),
    ):
        mock_resolver_cls.return_value = _make_mock_resolver()
        result = runner.invoke(app, ["data", "resolve-opponents"])

    mock_load_config.assert_called_once_with(db_path=fake_db_path)
    assert result.exit_code == 0


def test_resolve_opponents_calls_resolve_unlinked_after_resolve() -> None:
    """resolve_opponents() calls resolve_unlinked() after resolve() succeeds."""
    fake_db_path = Path("/fake/path/app.db")

    with (
        patch("src.cli.data._resolve_db_path", return_value=fake_db_path),
        patch("src.gamechanger.config.load_config"),
        patch("src.gamechanger.client.GameChangerClient"),
        patch(
            "src.gamechanger.crawlers.opponent_resolver.OpponentResolver"
        ) as mock_resolver_cls,
        patch("src.cli.data.sqlite3.connect"),
    ):
        mock_resolver = _make_mock_resolver(resolved=5, unlinked=2, unlinked_resolved=1)
        mock_resolver_cls.return_value = mock_resolver
        result = runner.invoke(app, ["data", "resolve-opponents"])

    mock_resolver.resolve.assert_called_once()
    mock_resolver.resolve_unlinked.assert_called_once()
    assert result.exit_code == 0


def test_resolve_opponents_output_includes_both_phases() -> None:
    """resolve_opponents() output includes progenitor and follow-bridge counts."""
    fake_db_path = Path("/fake/path/app.db")

    with (
        patch("src.cli.data._resolve_db_path", return_value=fake_db_path),
        patch("src.gamechanger.config.load_config"),
        patch("src.gamechanger.client.GameChangerClient"),
        patch(
            "src.gamechanger.crawlers.opponent_resolver.OpponentResolver"
        ) as mock_resolver_cls,
        patch("src.cli.data.sqlite3.connect"),
    ):
        mock_resolver = _make_mock_resolver(
            resolved=5,
            unlinked=2,
            stored_hidden=1,
            unlinked_resolved=1,
            follow_bridge_failed=1,
        )
        mock_resolver_cls.return_value = mock_resolver
        result = runner.invoke(app, ["data", "resolve-opponents"])

    assert "resolved=5" in result.output
    assert "follow_bridge_failed=1" in result.output
    assert result.exit_code == 0


def test_resolve_opponents_credential_expired_skips_resolve_unlinked() -> None:
    """If resolve() raises CredentialExpiredError, resolve_unlinked() is not called."""
    from src.gamechanger.client import CredentialExpiredError

    fake_db_path = Path("/fake/path/app.db")

    with (
        patch("src.cli.data._resolve_db_path", return_value=fake_db_path),
        patch("src.gamechanger.config.load_config"),
        patch("src.gamechanger.client.GameChangerClient"),
        patch(
            "src.gamechanger.crawlers.opponent_resolver.OpponentResolver"
        ) as mock_resolver_cls,
        patch("src.cli.data.sqlite3.connect"),
    ):
        mock_resolver = _make_mock_resolver()
        mock_resolver.resolve.side_effect = CredentialExpiredError("token expired")
        mock_resolver_cls.return_value = mock_resolver
        result = runner.invoke(app, ["data", "resolve-opponents"])

    mock_resolver.resolve_unlinked.assert_not_called()
    assert result.exit_code == 1


def test_resolve_opponents_resolve_unlinked_exception_caught() -> None:
    """If resolve_unlinked() raises an exception, it is caught and CLI exits with 1."""
    fake_db_path = Path("/fake/path/app.db")

    with (
        patch("src.cli.data._resolve_db_path", return_value=fake_db_path),
        patch("src.gamechanger.config.load_config"),
        patch("src.gamechanger.client.GameChangerClient"),
        patch(
            "src.gamechanger.crawlers.opponent_resolver.OpponentResolver"
        ) as mock_resolver_cls,
        patch("src.cli.data.sqlite3.connect"),
    ):
        mock_resolver = _make_mock_resolver(resolved=3)
        mock_resolver.resolve_unlinked.side_effect = RuntimeError("network failure")
        mock_resolver_cls.return_value = mock_resolver
        result = runner.invoke(app, ["data", "resolve-opponents"])

    assert result.exit_code == 1


def test_resolve_opponents_exit_1_if_resolve_has_errors() -> None:
    """Exit code is 1 if resolve() returns errors > 0, even if resolve_unlinked() succeeds."""
    fake_db_path = Path("/fake/path/app.db")

    with (
        patch("src.cli.data._resolve_db_path", return_value=fake_db_path),
        patch("src.gamechanger.config.load_config"),
        patch("src.gamechanger.client.GameChangerClient"),
        patch(
            "src.gamechanger.crawlers.opponent_resolver.OpponentResolver"
        ) as mock_resolver_cls,
        patch("src.cli.data.sqlite3.connect"),
    ):
        mock_resolver = _make_mock_resolver(resolved=3, resolve_errors=2)
        mock_resolver_cls.return_value = mock_resolver
        result = runner.invoke(app, ["data", "resolve-opponents"])

    assert result.exit_code == 1


def test_resolve_opponents_exit_1_if_resolve_unlinked_has_errors() -> None:
    """Exit code is 1 if resolve_unlinked() returns errors > 0."""
    fake_db_path = Path("/fake/path/app.db")

    with (
        patch("src.cli.data._resolve_db_path", return_value=fake_db_path),
        patch("src.gamechanger.config.load_config"),
        patch("src.gamechanger.client.GameChangerClient"),
        patch(
            "src.gamechanger.crawlers.opponent_resolver.OpponentResolver"
        ) as mock_resolver_cls,
        patch("src.cli.data.sqlite3.connect"),
    ):
        mock_resolver = _make_mock_resolver(resolved=3, follow_bridge_failed=1, unlinked_errors=1)
        mock_resolver_cls.return_value = mock_resolver
        result = runner.invoke(app, ["data", "resolve-opponents"])

    assert result.exit_code == 1


def test_resolve_opponents_dry_run_skips_resolve_unlinked() -> None:
    """--dry-run skips resolve_unlinked() (regression guard for AC-5)."""
    fake_db_path = Path("/fake/path/app.db")

    with (
        patch("src.cli.data._resolve_db_path", return_value=fake_db_path),
        patch("src.gamechanger.config.load_config"),
        patch("src.gamechanger.client.GameChangerClient"),
        patch(
            "src.gamechanger.crawlers.opponent_resolver.OpponentResolver"
        ) as mock_resolver_cls,
        patch("src.cli.data.sqlite3.connect"),
    ):
        mock_resolver = _make_mock_resolver()
        mock_resolver_cls.return_value = mock_resolver
        result = runner.invoke(app, ["data", "resolve-opponents", "--dry-run"])

    mock_resolver.resolve_unlinked.assert_not_called()
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# _find_scouting_run / _load_all_scouted -- status query bug (E-127-10)
# ---------------------------------------------------------------------------


def _make_scouting_db() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the minimal schema for scouting tests."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(
        """
        CREATE TABLE seasons (
            season_id   TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            season_type TEXT NOT NULL,
            year        INTEGER NOT NULL
        );
        CREATE TABLE teams (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            membership_type TEXT NOT NULL,
            public_id       TEXT
        );
        CREATE TABLE scouting_runs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id       INTEGER NOT NULL REFERENCES teams(id),
            season_id     TEXT NOT NULL REFERENCES seasons(season_id),
            run_type      TEXT NOT NULL DEFAULT 'full',
            status        TEXT NOT NULL DEFAULT 'pending',
            last_checked  TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(team_id, season_id, run_type)
        );
        INSERT INTO seasons(season_id, name, season_type, year)
            VALUES ('2026-spring-hs', 'Spring 2026 HS', 'spring-hs', 2026);
        """
    )
    return conn


def test_find_scouting_run_returns_completed_run() -> None:
    """_find_scouting_run() finds a run with status='completed'."""
    conn = _make_scouting_db()
    conn.execute(
        "INSERT INTO teams(name, membership_type, public_id) VALUES ('Opponent A', 'tracked', 'opp-a')"
    )
    team_id = conn.execute("SELECT id FROM teams WHERE public_id='opp-a'").fetchone()[0]
    conn.execute(
        "INSERT INTO scouting_runs(team_id, season_id, status, last_checked) "
        "VALUES (?, '2026-spring-hs', 'completed', '2026-01-01T12:00:00.000Z')",
        (team_id,),
    )
    conn.commit()

    result = _find_scouting_run(conn, "opp-a", "2026-01-01T00:00:00.000Z")

    assert result is not None
    assert result == (team_id, "2026-spring-hs")


def test_find_scouting_run_returns_running_run() -> None:
    """_find_scouting_run() still finds a run with status='running'."""
    conn = _make_scouting_db()
    conn.execute(
        "INSERT INTO teams(name, membership_type, public_id) VALUES ('Opponent B', 'tracked', 'opp-b')"
    )
    team_id = conn.execute("SELECT id FROM teams WHERE public_id='opp-b'").fetchone()[0]
    conn.execute(
        "INSERT INTO scouting_runs(team_id, season_id, status, last_checked) "
        "VALUES (?, '2026-spring-hs', 'running', '2026-01-01T12:00:00.000Z')",
        (team_id,),
    )
    conn.commit()

    result = _find_scouting_run(conn, "opp-b", "2026-01-01T00:00:00.000Z")

    assert result is not None
    assert result == (team_id, "2026-spring-hs")


def test_find_scouting_run_skips_pending_run() -> None:
    """_find_scouting_run() does not return runs with status='pending'."""
    conn = _make_scouting_db()
    conn.execute(
        "INSERT INTO teams(name, membership_type, public_id) VALUES ('Opponent C', 'tracked', 'opp-c')"
    )
    team_id = conn.execute("SELECT id FROM teams WHERE public_id='opp-c'").fetchone()[0]
    conn.execute(
        "INSERT INTO scouting_runs(team_id, season_id, status, last_checked) "
        "VALUES (?, '2026-spring-hs', 'pending', '2026-01-01T12:00:00.000Z')",
        (team_id,),
    )
    conn.commit()

    result = _find_scouting_run(conn, "opp-c", "2026-01-01T00:00:00.000Z")

    assert result is None


def test_load_all_scouted_finds_completed_runs(tmp_path: Path) -> None:
    """_load_all_scouted() processes runs with status='completed'."""
    conn = _make_scouting_db()
    conn.execute(
        "INSERT INTO teams(name, membership_type, public_id) VALUES ('Opponent D', 'tracked', 'opp-d')"
    )
    team_id = conn.execute("SELECT id FROM teams WHERE public_id='opp-d'").fetchone()[0]
    conn.execute(
        "INSERT INTO scouting_runs(team_id, season_id, status, last_checked) "
        "VALUES (?, '2026-spring-hs', 'completed', '2026-01-01T12:00:00.000Z')",
        (team_id,),
    )
    conn.commit()

    # Create the scouting dir so the loader call is attempted.
    scouting_dir = tmp_path / "2026-spring-hs" / "scouting" / "opp-d"
    scouting_dir.mkdir(parents=True)

    mock_load_result = MagicMock()
    mock_load_result.errors = 0

    mock_crawler = MagicMock()
    mock_loader = MagicMock()
    mock_loader.load_team.return_value = mock_load_result

    errors = _load_all_scouted(conn, mock_crawler, mock_loader, tmp_path, "2026-01-01T00:00:00.000Z")

    assert errors == 0
    mock_loader.load_team.assert_called_once()


def test_load_all_scouted_skips_pending_runs(tmp_path: Path) -> None:
    """_load_all_scouted() ignores runs with status='pending'."""
    conn = _make_scouting_db()
    conn.execute(
        "INSERT INTO teams(name, membership_type, public_id) VALUES ('Opponent E', 'tracked', 'opp-e')"
    )
    team_id = conn.execute("SELECT id FROM teams WHERE public_id='opp-e'").fetchone()[0]
    conn.execute(
        "INSERT INTO scouting_runs(team_id, season_id, status, last_checked) "
        "VALUES (?, '2026-spring-hs', 'pending', '2026-01-01T12:00:00.000Z')",
        (team_id,),
    )
    conn.commit()

    mock_crawler = MagicMock()
    mock_loader = MagicMock()

    errors = _load_all_scouted(conn, mock_crawler, mock_loader, tmp_path, "2026-01-01T00:00:00.000Z")

    assert errors == 0
    mock_loader.load_team.assert_not_called()
