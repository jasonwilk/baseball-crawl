"""Tests for the load pipeline orchestrator (src/pipeline/load.py).

Most tests mock loaders and DB interactions. AC-3/AC-4 use real SQLite
to verify the YAML load path TeamRef fix introduced in E-116-01.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from src.gamechanger.config import CrawlConfig, TeamEntry, load_config
from src.gamechanger.loaders import LoadResult
from src.pipeline.load import _run_game_loader, run, _LOADER_NAMES
from migrations.apply_migrations import run_migrations

# ---------------------------------------------------------------------------
# Loader registry
# ---------------------------------------------------------------------------

def test_loader_names_contains_all_loaders() -> None:
    """_LOADER_NAMES must contain all loaders in pipeline order."""
    assert _LOADER_NAMES == ["roster", "schedule", "game", "plays", "season-stats", "spray-chart"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_config(season: str = "2025", team_ids: list[str] | None = None) -> MagicMock:
    config = MagicMock()
    config.season = season
    ids = team_ids or ["team-001"]
    config.member_teams = [MagicMock(id=tid) for tid in ids]
    return config


def _make_result(loaded: int = 1, skipped: int = 0, errors: int = 0) -> LoadResult:
    return LoadResult(loaded=loaded, skipped=skipped, errors=errors)


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------

def test_dry_run_returns_zero(tmp_path: Path) -> None:
    """Dry run exits 0 without connecting to the database."""
    with patch("src.pipeline.load.load_config", return_value=_make_mock_config()):
        with patch("src.pipeline.load.sqlite3") as mock_sqlite:
            exit_code = run(dry_run=True, data_root=tmp_path, db_path=tmp_path / "app.db")

    assert exit_code == 0
    mock_sqlite.connect.assert_not_called()


def test_dry_run_prints_loaders(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Dry run logs all loader names."""
    import logging

    with caplog.at_level(logging.INFO, logger="src.pipeline.load"):
        with patch("src.pipeline.load.load_config", return_value=_make_mock_config()):
            run(dry_run=True, data_root=tmp_path, db_path=tmp_path / "app.db")

    for name in _LOADER_NAMES:
        assert name in caplog.text


# ---------------------------------------------------------------------------
# Loader filter
# ---------------------------------------------------------------------------

def test_loader_filter_runs_only_roster(tmp_path: Path) -> None:
    """--loader roster runs only the roster loader."""
    # Create a fake roster file so the loader has something to find.
    roster_dir = tmp_path / "2025" / "teams" / "team-001"
    roster_dir.mkdir(parents=True)
    (roster_dir / "roster.json").write_text("[]")

    with patch("src.pipeline.load.load_config", return_value=_make_mock_config()):
        with patch("src.pipeline.load.RosterLoader") as mock_loader_cls:
            mock_loader = MagicMock()
            mock_loader.load_file.return_value = _make_result()
            mock_loader_cls.return_value = mock_loader

            exit_code = run(
                loader_filter="roster",
                data_root=tmp_path,
                db_path=tmp_path / "app.db",
            )

    assert exit_code == 0
    mock_loader.load_file.assert_called_once()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_unhandled_exception_continues_to_next_loader(tmp_path: Path) -> None:
    """An unhandled exception in one loader does not abort the session."""

    # Register a second dummy loader by patching _LOADERS directly.
    good_called: list[bool] = []

    def _bad_runner(db: object, config: object, data_root: Path) -> LoadResult:
        raise RuntimeError("Boom")

    def _good_runner(db: object, config: object, data_root: Path) -> LoadResult:
        good_called.append(True)
        return _make_result()

    fake_loaders = [("bad", _bad_runner), ("good", _good_runner)]

    with patch("src.pipeline.load.load_config", return_value=_make_mock_config()):
        with patch("src.pipeline.load._LOADERS", fake_loaders):
            exit_code = run(data_root=tmp_path, db_path=tmp_path / "app.db")

    assert good_called == [True]
    assert exit_code == 1


def test_exit_code_0_when_all_loaders_succeed(tmp_path: Path) -> None:
    """Exit code is 0 when the roster loader completes without exceptions."""
    roster_dir = tmp_path / "2025" / "teams" / "team-001"
    roster_dir.mkdir(parents=True)
    (roster_dir / "roster.json").write_text("[]")

    with patch("src.pipeline.load.load_config", return_value=_make_mock_config()):
        with patch("src.pipeline.load.RosterLoader") as mock_loader_cls:
            mock_loader = MagicMock()
            mock_loader.load_file.return_value = _make_result()
            mock_loader_cls.return_value = mock_loader

            exit_code = run(
                loader_filter="roster",
                data_root=tmp_path,
                db_path=tmp_path / "app.db",
            )

    assert exit_code == 0


def test_exit_code_1_when_loader_raises(tmp_path: Path) -> None:
    """Exit code is 1 when any loader raises an unhandled exception."""

    def _crashing_runner(db: object, config: object, data_root: Path) -> LoadResult:
        raise ValueError("DB exploded")

    with patch("src.pipeline.load.load_config", return_value=_make_mock_config()):
        with patch("src.pipeline.load._LOADERS", [("roster", _crashing_runner)]):
            exit_code = run(data_root=tmp_path, db_path=tmp_path / "app.db")

    assert exit_code == 1


# ---------------------------------------------------------------------------
# Missing roster file is logged and skipped, not crashed
# ---------------------------------------------------------------------------

def test_missing_roster_file_skipped_gracefully(tmp_path: Path) -> None:
    """If roster.json does not exist for a team, it is skipped without error."""
    config = _make_mock_config(team_ids=["team-no-file"])

    with patch("src.pipeline.load.load_config", return_value=config):
        with patch("src.pipeline.load.RosterLoader") as mock_loader_cls:
            mock_loader = MagicMock()
            mock_loader_cls.return_value = mock_loader

            exit_code = run(
                loader_filter="roster",
                data_root=tmp_path,
                db_path=tmp_path / "app.db",
            )

    assert exit_code == 0
    mock_loader.load_file.assert_not_called()


# ---------------------------------------------------------------------------
# Game loader wiring
# ---------------------------------------------------------------------------

def test_loader_filter_runs_only_game(tmp_path: Path) -> None:
    """--loader game invokes GameLoader.load_all for each team."""
    team_dir = tmp_path / "2025" / "teams" / "team-001"
    team_dir.mkdir(parents=True)

    with patch("src.pipeline.load.load_config", return_value=_make_mock_config()):
        with patch("src.pipeline.load.GameLoader") as mock_loader_cls:
            mock_loader = MagicMock()
            mock_loader.load_all.return_value = _make_result()
            mock_loader_cls.return_value = mock_loader

            exit_code = run(
                loader_filter="game",
                data_root=tmp_path,
                db_path=tmp_path / "app.db",
            )

    assert exit_code == 0
    mock_loader_cls.assert_called_once()
    mock_loader.load_all.assert_called_once_with(team_dir)


def test_game_loader_constructs_with_correct_team(tmp_path: Path) -> None:
    """GameLoader is constructed with owned_team_ref from config (no season_id arg)."""
    team_dir = tmp_path / "2025" / "teams" / "team-abc"
    team_dir.mkdir(parents=True)

    config = _make_mock_config(season="2025", team_ids=["team-abc"])

    with patch("src.pipeline.load.load_config", return_value=config):
        with patch("src.pipeline.load.GameLoader") as mock_loader_cls:
            mock_loader = MagicMock()
            mock_loader.load_all.return_value = _make_result()
            mock_loader_cls.return_value = mock_loader

            run(loader_filter="game", data_root=tmp_path, db_path=tmp_path / "app.db")

    mock_loader_cls.assert_called_once()
    _, kwargs = mock_loader_cls.call_args
    assert "season_id" not in kwargs  # season_id is no longer passed
    assert kwargs["owned_team_ref"].gc_uuid == "team-abc"


def test_missing_game_team_dir_skipped_gracefully(tmp_path: Path) -> None:
    """If team directory does not exist, game loader skips without error."""
    config = _make_mock_config(team_ids=["team-no-dir"])

    with patch("src.pipeline.load.load_config", return_value=config):
        with patch("src.pipeline.load.GameLoader") as mock_loader_cls:
            mock_loader = MagicMock()
            mock_loader_cls.return_value = mock_loader

            exit_code = run(
                loader_filter="game",
                data_root=tmp_path,
                db_path=tmp_path / "app.db",
            )

    assert exit_code == 0
    mock_loader.load_all.assert_not_called()


# ---------------------------------------------------------------------------
# Season-stats loader wiring
# ---------------------------------------------------------------------------

def test_loader_filter_runs_only_season_stats(tmp_path: Path) -> None:
    """--loader season-stats invokes SeasonStatsLoader.load_file for each team."""
    stats_dir = tmp_path / "2025" / "teams" / "team-001"
    stats_dir.mkdir(parents=True)
    (stats_dir / "stats.json").write_text("{}")

    with patch("src.pipeline.load.load_config", return_value=_make_mock_config()):
        with patch("src.pipeline.load.SeasonStatsLoader") as mock_loader_cls:
            mock_loader = MagicMock()
            mock_loader.load_file.return_value = _make_result()
            mock_loader_cls.return_value = mock_loader

            exit_code = run(
                loader_filter="season-stats",
                data_root=tmp_path,
                db_path=tmp_path / "app.db",
            )

    assert exit_code == 0
    mock_loader.load_file.assert_called_once_with(stats_dir / "stats.json")


def test_missing_stats_file_skipped_gracefully(tmp_path: Path) -> None:
    """If stats.json does not exist for a team, it is skipped without error."""
    config = _make_mock_config(team_ids=["team-no-stats"])

    with patch("src.pipeline.load.load_config", return_value=config):
        with patch("src.pipeline.load.SeasonStatsLoader") as mock_loader_cls:
            mock_loader = MagicMock()
            mock_loader_cls.return_value = mock_loader

            exit_code = run(
                loader_filter="season-stats",
                data_root=tmp_path,
                db_path=tmp_path / "app.db",
            )

    assert exit_code == 0
    mock_loader.load_file.assert_not_called()


# ---------------------------------------------------------------------------
# DB source mode
# ---------------------------------------------------------------------------

def test_source_db_uses_same_path_for_config_and_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When source='db', both config reads and DB writes target the resolved_db path."""
    resolved_db = tmp_path / "override.db"
    default_db = tmp_path / "app.db"

    monkeypatch.setenv("DATABASE_PATH", str(resolved_db))

    with patch("src.pipeline.load.load_config_from_db", return_value=_make_mock_config()) as mock_cfg:
        with patch("src.pipeline.load.sqlite3") as mock_sqlite:
            mock_sqlite.connect.return_value.__enter__ = lambda s: s
            mock_sqlite.connect.return_value.__exit__ = MagicMock(return_value=False)
            mock_sqlite.connect.return_value.execute = MagicMock()
            # Patch _LOADERS to empty so the loader loop doesn't run
            with patch("src.pipeline.load._LOADERS", []):
                run(source="db", data_root=tmp_path, db_path=default_db)

    # Config was loaded from the resolved DB path
    mock_cfg.assert_called_once_with(resolved_db)
    # sqlite3.connect was called with the same resolved path (not the default)
    mock_sqlite.connect.assert_called_once_with(str(resolved_db))


def test_source_db_dry_run_shows_resolved_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Dry run with source='db' logs the DATABASE_PATH-resolved path."""
    import logging

    resolved_db = tmp_path / "override.db"
    default_db = tmp_path / "app.db"

    monkeypatch.setenv("DATABASE_PATH", str(resolved_db))

    with caplog.at_level(logging.INFO, logger="src.pipeline.load"):
        with patch("src.pipeline.load.load_config_from_db", return_value=_make_mock_config()):
            run(dry_run=True, source="db", data_root=tmp_path, db_path=default_db)

    assert str(resolved_db) in caplog.text
    assert str(default_db) not in caplog.text


def test_all_three_loaders_run_in_order(tmp_path: Path) -> None:
    """When no filter is set, all three loaders run and results are aggregated."""
    call_order: list[str] = []

    def _roster_runner(db: object, config: object, data_root: Path) -> LoadResult:
        call_order.append("roster")
        return _make_result(loaded=1)

    def _game_runner(db: object, config: object, data_root: Path) -> LoadResult:
        call_order.append("game")
        return _make_result(loaded=2)

    def _season_stats_runner(db: object, config: object, data_root: Path) -> LoadResult:
        call_order.append("season-stats")
        return _make_result(loaded=3)

    fake_loaders = [
        ("roster", _roster_runner),
        ("game", _game_runner),
        ("season-stats", _season_stats_runner),
    ]

    with patch("src.pipeline.load.load_config", return_value=_make_mock_config()):
        with patch("src.pipeline.load._LOADERS", fake_loaders):
            exit_code = run(data_root=tmp_path, db_path=tmp_path / "app.db")

    assert exit_code == 0
    assert call_order == ["roster", "game", "season-stats"]


# ---------------------------------------------------------------------------
# E-116-01: YAML load path TeamRef fix (AC-3 and AC-4)
# ---------------------------------------------------------------------------


def _setup_migrated_db(db_path: Path) -> None:
    """Apply migrations to a fresh SQLite database at db_path."""
    run_migrations(db_path=db_path)


def _insert_team(db_path: Path, gc_uuid: str, name: str = "Test Team") -> int:
    """Insert a member team row and return its INTEGER primary key."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys=ON;")
        cursor = conn.execute(
            "INSERT INTO teams (name, membership_type, classification, gc_uuid) "
            "VALUES (?, 'member', 'varsity', ?)",
            (name, gc_uuid),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def _write_yaml_config(yaml_path: Path, gc_uuid: str, season: str = "2025") -> None:
    """Write a minimal teams.yaml config to yaml_path."""
    data = {
        "season": season,
        "member_teams": [
            {"id": gc_uuid, "name": "Test Team", "classification": "varsity"}
        ],
    }
    yaml_path.write_text(yaml.dump(data))


def test_yaml_source_teamref_has_valid_db_id(tmp_path: Path) -> None:
    """AC-3: YAML-sourced config produces TeamRef with a valid (non-zero) id.

    Verifies the E-116-01 fix: run() now passes db_path to load_config() so that
    TeamEntry.internal_id is resolved from the database before _run_game_loader()
    constructs TeamRef.
    """
    gc_uuid = "test-uuid-ac3"
    db_path = tmp_path / "app.db"
    yaml_path = tmp_path / "teams.yaml"
    season = "2025"

    _setup_migrated_db(db_path)
    expected_id = _insert_team(db_path, gc_uuid)
    _write_yaml_config(yaml_path, gc_uuid, season)

    # Create a team directory so the game loader finds it.
    team_dir = tmp_path / season / "teams" / gc_uuid
    team_dir.mkdir(parents=True)

    captured_team_refs: list = []

    real_load_config = load_config

    def patched_load_config(db_path=None):  # type: ignore[override]
        return real_load_config(path=yaml_path, db_path=db_path)

    with patch("src.pipeline.load.load_config", side_effect=patched_load_config):
        with patch("src.pipeline.load.GameLoader") as mock_loader_cls:
            mock_loader = MagicMock()
            mock_loader.load_all.return_value = _make_result()
            mock_loader_cls.side_effect = lambda db, owned_team_ref: (
                captured_team_refs.append(owned_team_ref) or mock_loader
            )

            exit_code = run(
                loader_filter="game",
                source="yaml",
                data_root=tmp_path,
                db_path=db_path,
            )

    assert exit_code == 0, "Loader should succeed when team is in DB"
    assert len(captured_team_refs) == 1
    team_ref = captured_team_refs[0]
    assert team_ref.id == expected_id, (
        f"Expected TeamRef.id={expected_id}, got {team_ref.id}. "
        "TeamRef(id=0) regression would produce id=0."
    )
    assert team_ref.id != 0, "TeamRef.id must not be 0 (FK violation guard)"
    assert team_ref.gc_uuid == gc_uuid


# ---------------------------------------------------------------------------
# AC-2 / AC-3: team_ids filter (source="db")
# ---------------------------------------------------------------------------


def _make_db_config_with_ids(
    season: str = "2025",
    teams: list[tuple[str, int]] | None = None,
) -> MagicMock:
    """Return a mock CrawlConfig with internal_id populated (simulates source='db')."""
    config = MagicMock()
    config.season = season
    team_list = teams or [("team-001", 1)]
    config.member_teams = [MagicMock(id=gc_uuid, internal_id=iid) for gc_uuid, iid in team_list]
    return config


def test_load_team_ids_filter_db_source(tmp_path: Path) -> None:
    """team_ids=[2] with source='db' passes only the matching team to loaders."""
    teams = [("team-a", 1), ("team-b", 2), ("team-c", 3)]
    db_config = _make_db_config_with_ids(teams=teams)

    teams_seen_per_loader: list[list] = []

    def _capturing_runner(db: object, config: object, data_root: object) -> LoadResult:
        teams_seen_per_loader.append(list(config.member_teams))
        return _make_result()

    fake_loaders = [("roster", _capturing_runner), ("game", _capturing_runner)]

    with patch("src.pipeline.load.load_config_from_db", return_value=db_config):
        with patch("src.pipeline.load._LOADERS", fake_loaders):
            exit_code = run(source="db", team_ids=[2], data_root=tmp_path, db_path=tmp_path / "app.db")

    assert exit_code == 0
    assert len(teams_seen_per_loader) == 2
    for teams_seen in teams_seen_per_loader:
        assert len(teams_seen) == 1
        assert teams_seen[0].internal_id == 2


def test_load_team_ids_none_db_source_processes_all_teams(tmp_path: Path) -> None:
    """team_ids=None with source='db' passes all teams to loaders (unfiltered)."""
    teams = [("team-a", 1), ("team-b", 2), ("team-c", 3)]
    db_config = _make_db_config_with_ids(teams=teams)

    teams_seen_per_loader: list[list] = []

    def _capturing_runner(db: object, config: object, data_root: object) -> LoadResult:
        teams_seen_per_loader.append(list(config.member_teams))
        return _make_result()

    with patch("src.pipeline.load.load_config_from_db", return_value=db_config):
        with patch("src.pipeline.load._LOADERS", [("roster", _capturing_runner)]):
            exit_code = run(source="db", team_ids=None, data_root=tmp_path, db_path=tmp_path / "app.db")

    assert exit_code == 0
    assert len(teams_seen_per_loader) == 1
    assert len(teams_seen_per_loader[0]) == 3


def test_load_team_ids_with_loader_filter(tmp_path: Path) -> None:
    """team_ids=[3] + loader_filter='game' processes only game loader for team 3."""
    teams = [("team-a", 1), ("team-b", 2), ("team-c", 3)]
    db_config = _make_db_config_with_ids(teams=teams)

    teams_seen: list[list] = []

    def _capturing_game_runner(db: object, config: object, data_root: object) -> LoadResult:
        teams_seen.append(list(config.member_teams))
        return _make_result()

    with patch("src.pipeline.load.load_config_from_db", return_value=db_config):
        with patch("src.pipeline.load._LOADERS", [
            ("roster", lambda *a: _make_result()),
            ("game", _capturing_game_runner),
            ("season-stats", lambda *a: _make_result()),
        ]):
            exit_code = run(
                source="db",
                team_ids=[3],
                loader_filter="game",
                data_root=tmp_path,
                db_path=tmp_path / "app.db",
            )

    assert exit_code == 0
    assert len(teams_seen) == 1
    assert teams_seen[0][0].internal_id == 3


def test_yaml_source_raises_when_team_not_in_db(tmp_path: Path) -> None:
    """AC-4: YAML-sourced config raises a clear error when team is absent from DB.

    Verifies that the 'or 0' fallback is replaced with an explicit ValueError
    so that missing teams fail loudly instead of producing TeamRef(id=0).
    """
    gc_uuid = "missing-uuid-ac4"

    # Build a config with internal_id=None (team not in any DB).
    config = CrawlConfig(
        season="2025",
        member_teams=[
            TeamEntry(id=gc_uuid, name="Ghost Team", classification="varsity", internal_id=None)
        ],
    )
    team_dir = tmp_path / "2025" / "teams" / gc_uuid
    team_dir.mkdir(parents=True)

    db_conn = sqlite3.connect(":memory:")

    with pytest.raises(ValueError, match=gc_uuid):
        _run_game_loader(db_conn, config, tmp_path)

    db_conn.close()
