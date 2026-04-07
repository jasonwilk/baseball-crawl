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
    valid_names = ["roster", "schedule", "opponent", "player-stats", "game-stats", "spray-chart", "plays"]
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
    valid_names = ["roster", "schedule", "game", "plays", "season-stats"]
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
    skipped_hidden: int = 0,
    resolve_errors: int = 0,
    unlinked_resolved: int = 0,
    follow_bridge_failed: int = 0,
    unlinked_errors: int = 0,
) -> MagicMock:
    """Build a mock OpponentResolver with pre-configured resolve() and resolve_unlinked() return values."""
    mock_resolve_result = MagicMock()
    mock_resolve_result.resolved = resolved
    mock_resolve_result.unlinked = unlinked
    mock_resolve_result.skipped_hidden = skipped_hidden
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
            skipped_hidden=1,
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


# ---------------------------------------------------------------------------
# bb data crawl --crawler plays / bb data load --loader plays (E-195-04)
# ---------------------------------------------------------------------------


def test_crawl_help_lists_plays() -> None:
    """bb data crawl --help lists 'plays' as a valid --crawler value (AC-5, AC-7)."""
    result = runner.invoke(app, ["data", "crawl", "--help"])
    assert result.exit_code == 0
    assert "plays" in result.output


def test_load_help_lists_plays() -> None:
    """bb data load --help lists 'plays' as a valid --loader value (AC-5, AC-7)."""
    result = runner.invoke(app, ["data", "load", "--help"])
    assert result.exit_code == 0
    assert "plays" in result.output


def test_crawl_plays_dispatches_to_pipeline(  # noqa: D103
) -> None:
    """bb data crawl --crawler plays dispatches to pipeline crawl.run (AC-1)."""
    with patch("src.pipeline.crawl.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "crawl", "--crawler", "plays"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        dry_run=False,
        crawler_filter="plays",
        profile="web",
        source="yaml",
    )


def test_load_plays_dispatches_to_pipeline(  # noqa: D103
) -> None:
    """bb data load --loader plays dispatches to pipeline load.run (AC-2)."""
    with patch("src.pipeline.load.run", return_value=0) as mock_run:
        result = runner.invoke(app, ["data", "load", "--loader", "plays"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        dry_run=False,
        loader_filter="plays",
        source="yaml",
    )


def test_plays_loader_runs_after_game_loader() -> None:
    """Plays loader must execute after game loader in default ordering (AC-6).

    The plays table has an FK to games; loading plays before games would
    violate the constraint.
    """
    from src.pipeline.load import _LOADER_NAMES

    game_idx = _LOADER_NAMES.index("game")
    plays_idx = _LOADER_NAMES.index("plays")
    assert plays_idx > game_idx, (
        f"plays loader (index {plays_idx}) must come after game loader "
        f"(index {game_idx}) due to FK dependency"
    )


def test_plays_crawler_in_default_crawl_order() -> None:
    """Plays crawler is included in the default all-crawlers list (AC-3)."""
    from src.pipeline.crawl import _CRAWLER_NAMES

    assert "plays" in _CRAWLER_NAMES


def test_plays_loader_in_default_load_order() -> None:
    """Plays loader is included in the default all-loaders list (AC-4)."""
    from src.pipeline.load import _LOADER_NAMES

    assert "plays" in _LOADER_NAMES


# ---------------------------------------------------------------------------
# bb data crawl --crawler scouting-spray (E-163-01)
# ---------------------------------------------------------------------------


def test_crawl_scouting_spray_is_accepted_as_valid_crawler() -> None:
    """'scouting-spray' is a valid --crawler choice (not rejected with exit 1)."""
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_all.return_value = MagicMock(
        files_written=0, files_skipped=0, errors=0
    )

    with (
        patch("src.cli.data._resolve_db_path", return_value=Path("/fake/app.db")),
        patch("src.gamechanger.client.GameChangerClient"),
        patch("src.cli.data.sqlite3.connect"),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
    ):
        result = runner.invoke(app, ["data", "crawl", "--crawler", "scouting-spray"])

    # Should not produce an "Invalid crawler" error.
    assert "Invalid crawler" not in result.output


def test_crawl_scouting_spray_does_not_call_pipeline_factory() -> None:
    """--crawler scouting-spray does not route through pipeline/crawl.py factory."""
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_all.return_value = MagicMock(
        files_written=1, files_skipped=0, errors=0
    )

    with (
        patch("src.pipeline.crawl.run") as mock_factory,
        patch("src.cli.data._resolve_db_path", return_value=Path("/fake/app.db")),
        patch("src.gamechanger.client.GameChangerClient"),
        patch("src.cli.data.sqlite3.connect"),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
    ):
        runner.invoke(app, ["data", "crawl", "--crawler", "scouting-spray"])

    mock_factory.assert_not_called()


def test_crawl_scouting_spray_calls_crawl_all() -> None:
    """--crawler scouting-spray invokes ScoutingSprayChartCrawler.crawl_all()."""
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_all.return_value = MagicMock(
        files_written=3, files_skipped=1, errors=0
    )

    with (
        patch("src.cli.data._resolve_db_path", return_value=Path("/fake/app.db")),
        patch("src.gamechanger.client.GameChangerClient"),
        patch("src.cli.data.sqlite3.connect"),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
    ):
        result = runner.invoke(app, ["data", "crawl", "--crawler", "scouting-spray"])

    mock_spray_crawler.crawl_all.assert_called_once()
    assert result.exit_code == 0


def test_crawl_scouting_spray_errors_exit_code_1() -> None:
    """--crawler scouting-spray exits with code 1 if crawl_all reports errors."""
    mock_spray_crawler = MagicMock()
    mock_spray_crawler.crawl_all.return_value = MagicMock(
        files_written=0, files_skipped=0, errors=2
    )

    with (
        patch("src.cli.data._resolve_db_path", return_value=Path("/fake/app.db")),
        patch("src.gamechanger.client.GameChangerClient"),
        patch("src.cli.data.sqlite3.connect"),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
    ):
        result = runner.invoke(app, ["data", "crawl", "--crawler", "scouting-spray"])

    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# bb data load --loader scouting-spray (E-163-02)
# ---------------------------------------------------------------------------


def test_load_scouting_spray_is_accepted_as_valid_loader() -> None:
    """'scouting-spray' is a valid --loader choice (not rejected with exit 1)."""
    mock_spray_loader = MagicMock()
    mock_spray_loader.load_all.return_value = MagicMock(loaded=0, skipped=0, errors=0)

    with (
        patch("src.cli.data._resolve_db_path", return_value=Path("/fake/app.db")),
        patch("src.cli.data.sqlite3.connect"),
        patch(
            "src.gamechanger.loaders.scouting_spray_loader.ScoutingSprayChartLoader",
            return_value=mock_spray_loader,
        ),
    ):
        result = runner.invoke(app, ["data", "load", "--loader", "scouting-spray"])

    assert "Invalid loader" not in result.output


def test_load_scouting_spray_does_not_call_pipeline_factory() -> None:
    """--loader scouting-spray does not route through pipeline/load.py factory."""
    mock_spray_loader = MagicMock()
    mock_spray_loader.load_all.return_value = MagicMock(loaded=1, skipped=0, errors=0)

    with (
        patch("src.pipeline.load.run") as mock_factory,
        patch("src.cli.data._resolve_db_path", return_value=Path("/fake/app.db")),
        patch("src.cli.data.sqlite3.connect"),
        patch(
            "src.gamechanger.loaders.scouting_spray_loader.ScoutingSprayChartLoader",
            return_value=mock_spray_loader,
        ),
    ):
        runner.invoke(app, ["data", "load", "--loader", "scouting-spray"])

    mock_factory.assert_not_called()


def test_load_scouting_spray_calls_load_all() -> None:
    """--loader scouting-spray invokes ScoutingSprayChartLoader.load_all()."""
    mock_spray_loader = MagicMock()
    mock_spray_loader.load_all.return_value = MagicMock(loaded=3, skipped=1, errors=0)

    with (
        patch("src.cli.data._resolve_db_path", return_value=Path("/fake/app.db")),
        patch("src.cli.data.sqlite3.connect"),
        patch(
            "src.gamechanger.loaders.scouting_spray_loader.ScoutingSprayChartLoader",
            return_value=mock_spray_loader,
        ),
    ):
        result = runner.invoke(app, ["data", "load", "--loader", "scouting-spray"])

    mock_spray_loader.load_all.assert_called_once()
    assert result.exit_code == 0


def test_load_scouting_spray_errors_exit_code_1() -> None:
    """--loader scouting-spray exits with code 1 if load_all reports errors."""
    mock_spray_loader = MagicMock()
    mock_spray_loader.load_all.return_value = MagicMock(loaded=0, skipped=0, errors=2)

    with (
        patch("src.cli.data._resolve_db_path", return_value=Path("/fake/app.db")),
        patch("src.cli.data.sqlite3.connect"),
        patch(
            "src.gamechanger.loaders.scouting_spray_loader.ScoutingSprayChartLoader",
            return_value=mock_spray_loader,
        ),
    ):
        result = runner.invoke(app, ["data", "load", "--loader", "scouting-spray"])

    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Finding 1: dry_run bypass fix
# ---------------------------------------------------------------------------


def test_crawl_scouting_spray_dry_run_skips_crawl() -> None:
    """--dry-run + --crawler scouting-spray prints message and exits 0 without crawling."""
    with patch(
        "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler"
    ) as mock_cls:
        result = runner.invoke(
            app, ["data", "crawl", "--dry-run", "--crawler", "scouting-spray"]
        )

    mock_cls.assert_not_called()
    assert result.exit_code == 0
    assert "Dry run" in result.output


def test_load_scouting_spray_dry_run_skips_load() -> None:
    """--dry-run + --loader scouting-spray prints message and exits 0 without loading."""
    with patch(
        "src.gamechanger.loaders.scouting_spray_loader.ScoutingSprayChartLoader"
    ) as mock_cls:
        result = runner.invoke(
            app, ["data", "load", "--dry-run", "--loader", "scouting-spray"]
        )

    mock_cls.assert_not_called()
    assert result.exit_code == 0
    assert "Dry run" in result.output


# ---------------------------------------------------------------------------
# bb data dedup
# ---------------------------------------------------------------------------


def _make_dup_team(
    id: int,
    name: str = "Rival HS",
    season_year: int | None = 2026,
    gc_uuid: str | None = None,
    public_id: str | None = None,
    game_count: int = 0,
    has_stats: bool = False,
):
    """Build a DuplicateTeam for dedup tests."""
    from src.db.merge import DuplicateTeam
    return DuplicateTeam(
        id=id, name=name, season_year=season_year, gc_uuid=gc_uuid,
        public_id=public_id, game_count=game_count, has_stats=has_stats,
    )


def test_dedup_dry_run_no_duplicates() -> None:
    """dedup with no duplicates prints message and exits 0."""
    with patch("src.db.merge.find_duplicate_teams", return_value=[]):
        with patch("src.cli.data.sqlite3.connect"):
            result = runner.invoke(app, ["data", "dedup", "--db", "/tmp/test.db"])
    assert result.exit_code == 0
    assert "No duplicate teams found" in result.output


def test_dedup_dry_run_shows_preview() -> None:
    """dedup dry-run shows group info, canonical, and 'Would merge'."""
    groups = [[
        _make_dup_team(1, has_stats=True, game_count=5),
        _make_dup_team(2, game_count=0),
    ]]
    mock_preview = MagicMock()
    mock_preview.games_between_teams = 0

    with (
        patch("src.db.merge.find_duplicate_teams", return_value=groups),
        patch("src.db.merge.preview_merge", return_value=mock_preview),
        patch("src.cli.data.sqlite3.connect"),
    ):
        result = runner.invoke(app, ["data", "dedup", "--db", "/tmp/test.db"])

    assert result.exit_code == 0
    assert "DRY RUN" in result.output
    assert "Would merge id=2 -> id=1" in result.output
    assert "canonical" in result.output.lower()


def test_dedup_execute_performs_merge() -> None:
    """dedup --execute calls merge_teams."""
    groups = [[
        _make_dup_team(1, has_stats=True),
        _make_dup_team(2),
    ]]
    mock_preview = MagicMock()
    mock_preview.games_between_teams = 0

    with (
        patch("src.db.merge.find_duplicate_teams", return_value=groups),
        patch("src.db.merge.preview_merge", return_value=mock_preview),
        patch("src.db.merge.merge_teams") as mock_merge,
        patch("src.cli.data.sqlite3.connect"),
    ):
        result = runner.invoke(app, ["data", "dedup", "--execute", "--db", "/tmp/test.db"])

    assert result.exit_code == 0
    assert "EXECUTE" in result.output
    assert "MERGED id=2 -> id=1" in result.output
    mock_merge.assert_called_once()


def test_dedup_skips_games_between() -> None:
    """dedup skips groups where teams played each other."""
    groups = [[
        _make_dup_team(1, game_count=3),
        _make_dup_team(2, game_count=1),
    ]]
    mock_preview = MagicMock()
    mock_preview.games_between_teams = 2

    with (
        patch("src.db.merge.find_duplicate_teams", return_value=groups),
        patch("src.db.merge.preview_merge", return_value=mock_preview),
        patch("src.cli.data.sqlite3.connect"),
    ):
        result = runner.invoke(app, ["data", "dedup", "--execute", "--db", "/tmp/test.db"])

    assert result.exit_code == 0
    assert "SKIP" in result.output
    assert "game(s) between teams" in result.output
    assert "1 group(s) found, 0 merged, 1 skipped" in result.output


def test_dedup_canonical_heuristic_has_stats_wins() -> None:
    """Canonical selection: has_stats beats higher game_count."""
    from src.cli.data import _select_canonical
    group = [
        _make_dup_team(1, game_count=10, has_stats=False),
        _make_dup_team(2, game_count=1, has_stats=True),
    ]
    canonical, dups = _select_canonical(group)
    assert canonical.id == 2


def test_dedup_canonical_heuristic_game_count_wins() -> None:
    """Canonical selection: higher game_count beats lower id."""
    from src.cli.data import _select_canonical
    group = [
        _make_dup_team(1, game_count=0),
        _make_dup_team(2, game_count=5),
    ]
    canonical, dups = _select_canonical(group)
    assert canonical.id == 2


def test_dedup_canonical_heuristic_lowest_id_wins() -> None:
    """Canonical selection: lowest id when all else equal."""
    from src.cli.data import _select_canonical
    group = [
        _make_dup_team(5),
        _make_dup_team(3),
        _make_dup_team(7),
    ]
    canonical, dups = _select_canonical(group)
    assert canonical.id == 3


def test_dedup_3_team_group_merges_pairwise() -> None:
    """dedup --execute merges N-1 times for an N-team group."""
    groups = [[
        _make_dup_team(1, has_stats=True, game_count=5),
        _make_dup_team(2, game_count=1),
        _make_dup_team(3, game_count=0),
    ]]
    mock_preview = MagicMock()
    mock_preview.games_between_teams = 0

    with (
        patch("src.db.merge.find_duplicate_teams", return_value=groups),
        patch("src.db.merge.preview_merge", return_value=mock_preview),
        patch("src.db.merge.merge_teams") as mock_merge,
        patch("src.cli.data.sqlite3.connect"),
    ):
        result = runner.invoke(app, ["data", "dedup", "--execute", "--db", "/tmp/test.db"])

    assert result.exit_code == 0
    # 3-team group -> 2 merges (each duplicate into canonical)
    assert mock_merge.call_count == 2
    assert "MERGED id=3 -> id=1" in result.output
    assert "MERGED id=2 -> id=1" in result.output
    assert "1 group(s) found, 2 merged, 0 skipped" in result.output


def test_dedup_summary_output() -> None:
    """dedup shows a summary line at the end."""
    groups = [
        [_make_dup_team(1), _make_dup_team(2)],
        [_make_dup_team(3), _make_dup_team(4)],
    ]
    mock_preview = MagicMock()
    mock_preview.games_between_teams = 0

    with (
        patch("src.db.merge.find_duplicate_teams", return_value=groups),
        patch("src.db.merge.preview_merge", return_value=mock_preview),
        patch("src.cli.data.sqlite3.connect"),
    ):
        result = runner.invoke(app, ["data", "dedup", "--db", "/tmp/test.db"])

    assert "2 group(s) found, 2 merged, 0 skipped" in result.output


# ---------------------------------------------------------------------------
# bb data dedup-players (E-215-02)
# ---------------------------------------------------------------------------


def test_dedup_players_error_path() -> None:
    """dedup-players prints error and exits 1 when detection raises."""
    mock_conn = MagicMock()
    mock_conn.execute = MagicMock()
    with patch("src.cli.data.sqlite3.connect", return_value=mock_conn):
        with patch(
            "src.db.player_dedup.find_duplicate_players",
            side_effect=RuntimeError("table missing"),
        ):
            result = runner.invoke(app, ["data", "dedup-players"])

    assert result.exit_code != 0
    assert "Error finding duplicate players" in result.output
    assert "table missing" in result.output


# ---------------------------------------------------------------------------
# bb data repair-opponents (E-173-06)
# ---------------------------------------------------------------------------


def _make_repair_db(tmp_path: Path) -> tuple[Path, dict[str, int]]:
    """Create a test DB with resolved opponent_links but missing team_opponents."""
    from migrations.apply_migrations import run_migrations

    db_path = tmp_path / "repair_test.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")

    # Member team
    cur = conn.execute(
        "INSERT INTO teams (name, membership_type, source, is_active, season_year) "
        "VALUES ('LSB Varsity', 'member', 'test', 1, 2026)"
    )
    our_id = cur.lastrowid

    # Resolved opponent team (inactive -- should be activated)
    cur = conn.execute(
        "INSERT INTO teams (name, membership_type, public_id, source, is_active) "
        "VALUES ('Rival HS', 'tracked', 'rival-slug', 'test', 0)"
    )
    resolved_id = cur.lastrowid

    # Resolved opponent_links row -- but NO team_opponents row
    cur = conn.execute(
        "INSERT INTO opponent_links "
        "(our_team_id, root_team_id, opponent_name, resolved_team_id, "
        "public_id, resolution_method) "
        "VALUES (?, 'gc-root-001', 'Rival HS', ?, 'rival-slug', 'auto')",
        (our_id, resolved_id),
    )
    link_id = cur.lastrowid

    conn.commit()
    conn.close()
    return db_path, {"our_id": our_id, "resolved_id": resolved_id, "link_id": link_id}


def test_repair_opponents_dry_run_no_resolved(tmp_path: Path) -> None:
    """Dry run with no resolved links prints nothing-to-do message."""
    from migrations.apply_migrations import run_migrations

    db_path = tmp_path / "empty.db"
    run_migrations(db_path=db_path)

    result = runner.invoke(app, ["data", "repair-opponents", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "Nothing to repair" in result.output


def test_repair_opponents_dry_run_shows_preview(tmp_path: Path) -> None:
    """Dry run shows what would be processed without making changes."""
    db_path, ids = _make_repair_db(tmp_path)

    result = runner.invoke(app, ["data", "repair-opponents", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "DRY RUN" in result.output
    assert "Rival HS" in result.output
    assert "total to process: 1" in result.output

    # Verify no changes were made
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT COUNT(*) FROM team_opponents WHERE our_team_id = ?",
        (ids["our_id"],),
    ).fetchone()
    conn.close()
    assert row[0] == 0


def test_repair_opponents_execute_creates_team_opponents(tmp_path: Path) -> None:
    """Execute mode creates team_opponents row and activates the team."""
    db_path, ids = _make_repair_db(tmp_path)

    result = runner.invoke(
        app, ["data", "repair-opponents", "--execute", "--db", str(db_path)]
    )
    assert result.exit_code == 0
    assert "EXECUTE" in result.output
    assert "team_opponents created: 1" in result.output

    conn = sqlite3.connect(str(db_path))
    # team_opponents row exists
    row = conn.execute(
        "SELECT opponent_team_id FROM team_opponents WHERE our_team_id = ?",
        (ids["our_id"],),
    ).fetchone()
    assert row is not None
    assert row[0] == ids["resolved_id"]

    # Team is now active
    active = conn.execute(
        "SELECT is_active FROM teams WHERE id = ?", (ids["resolved_id"],)
    ).fetchone()
    assert active[0] == 1
    conn.close()


def test_repair_opponents_idempotent(tmp_path: Path) -> None:
    """Running repair twice does not error or create duplicates."""
    db_path, ids = _make_repair_db(tmp_path)

    # First run
    result1 = runner.invoke(
        app, ["data", "repair-opponents", "--execute", "--db", str(db_path)]
    )
    assert result1.exit_code == 0

    # Second run -- should report no-op
    result2 = runner.invoke(
        app, ["data", "repair-opponents", "--execute", "--db", str(db_path)]
    )
    assert result2.exit_code == 0
    assert "no-op" in result2.output

    # Still only one team_opponents row
    conn = sqlite3.connect(str(db_path))
    count = conn.execute(
        "SELECT COUNT(*) FROM team_opponents WHERE our_team_id = ?",
        (ids["our_id"],),
    ).fetchone()[0]
    conn.close()
    assert count == 1


def test_repair_opponents_replaces_stub(tmp_path: Path) -> None:
    """When a stub exists in team_opponents, repair replaces it with resolved team."""
    db_path, ids = _make_repair_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")

    # Create a stub team and link it in team_opponents
    cur = conn.execute(
        "INSERT INTO teams (name, membership_type, source, is_active) "
        "VALUES ('Rival HS', 'tracked', 'test', 0)"
    )
    stub_id = cur.lastrowid
    conn.execute(
        "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
        (ids["our_id"], stub_id),
    )
    conn.commit()
    conn.close()

    result = runner.invoke(
        app, ["data", "repair-opponents", "--execute", "--db", str(db_path)]
    )
    assert result.exit_code == 0
    assert "stub replaced" in result.output

    # team_opponents should now point to resolved_id, not stub_id
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT opponent_team_id FROM team_opponents WHERE our_team_id = ?",
        (ids["our_id"],),
    ).fetchall()
    conn.close()
    team_ids = [r[0] for r in rows]
    assert ids["resolved_id"] in team_ids
    assert stub_id not in team_ids


def test_repair_opponents_fixes_stale_fk_despite_correct_team_opponents(tmp_path: Path) -> None:
    """Repair reassigns stale FK refs even when team_opponents already points to resolved team.

    Scenario: team_opponents correctly links to resolved_id and team is active,
    but game rows still reference an old stub. The old `already_ok` shortcut
    would have skipped this; the fix always calls finalize which cleans up FKs.
    """
    from migrations.apply_migrations import run_migrations

    db_path = tmp_path / "stale_fk.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")

    # Member team
    cur = conn.execute(
        "INSERT INTO teams (name, membership_type, source, is_active, season_year) "
        "VALUES ('LSB Varsity', 'member', 'test', 1, 2026)"
    )
    our_id = cur.lastrowid

    # Old stub team
    cur = conn.execute(
        "INSERT INTO teams (name, membership_type, source, is_active) "
        "VALUES ('Rival HS', 'tracked', 'test', 0)"
    )
    stub_id = cur.lastrowid

    # Resolved team (already active)
    cur = conn.execute(
        "INSERT INTO teams (name, membership_type, public_id, source, is_active) "
        "VALUES ('Rival HS', 'tracked', 'rival-slug', 'test', 1)"
    )
    resolved_id = cur.lastrowid

    # team_opponents correctly points to resolved_id
    conn.execute(
        "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
        (our_id, resolved_id),
    )
    # But the stub also has a team_opponents row (stale)
    conn.execute(
        "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
        (our_id, stub_id),
    )

    # opponent_links points to resolved
    conn.execute(
        "INSERT INTO opponent_links "
        "(our_team_id, root_team_id, opponent_name, resolved_team_id, "
        "public_id, resolution_method) "
        "VALUES (?, 'gc-root-001', 'Rival HS', ?, 'rival-slug', 'auto')",
        (our_id, resolved_id),
    )

    # Game row with FK pointing to old STUB (stale)
    conn.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) "
        "VALUES ('2026-spring-hs', 'Spring 2026', 'spring-hs', 2026)"
    )
    conn.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id) "
        "VALUES ('stale-g1', '2026-spring-hs', '2026-04-01', ?, ?)",
        (our_id, stub_id),
    )
    conn.commit()
    conn.close()

    result = runner.invoke(
        app, ["data", "repair-opponents", "--execute", "--db", str(db_path)]
    )
    assert result.exit_code == 0

    # The game's away_team_id should now point to resolved_id, not stub_id
    conn = sqlite3.connect(str(db_path))
    game = conn.execute(
        "SELECT away_team_id FROM games WHERE game_id = 'stale-g1'"
    ).fetchone()
    conn.close()
    assert game[0] == resolved_id
