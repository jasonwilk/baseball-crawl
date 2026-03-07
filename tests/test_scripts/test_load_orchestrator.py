"""Tests for scripts/load.py orchestrator.

All loaders and DB interactions are mocked -- no real SQLite writes.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.load import run, _LOADER_NAMES
from src.gamechanger.loaders import LoadResult

# ---------------------------------------------------------------------------
# Loader registry
# ---------------------------------------------------------------------------

def test_loader_names_contains_all_three() -> None:
    """_LOADER_NAMES must contain roster, game, and season-stats in order."""
    assert _LOADER_NAMES == ["roster", "game", "season-stats"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_config(season: str = "2025", team_ids: list[str] | None = None) -> MagicMock:
    config = MagicMock()
    config.season = season
    ids = team_ids or ["team-001"]
    config.owned_teams = [MagicMock(id=tid) for tid in ids]
    return config


def _make_result(loaded: int = 1, skipped: int = 0, errors: int = 0) -> LoadResult:
    return LoadResult(loaded=loaded, skipped=skipped, errors=errors)


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------

def test_dry_run_returns_zero(tmp_path: Path) -> None:
    """Dry run exits 0 without connecting to the database."""
    with patch("scripts.load.load_config", return_value=_make_mock_config()):
        with patch("scripts.load.sqlite3") as mock_sqlite:
            exit_code = run(dry_run=True, data_root=tmp_path, db_path=tmp_path / "app.db")

    assert exit_code == 0
    mock_sqlite.connect.assert_not_called()


def test_dry_run_prints_loaders(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Dry run prints all loader names."""
    with patch("scripts.load.load_config", return_value=_make_mock_config()):
        run(dry_run=True, data_root=tmp_path, db_path=tmp_path / "app.db")

    captured = capsys.readouterr()
    for name in _LOADER_NAMES:
        assert name in captured.out


# ---------------------------------------------------------------------------
# Loader filter
# ---------------------------------------------------------------------------

def test_loader_filter_runs_only_roster(tmp_path: Path) -> None:
    """--loader roster runs only the roster loader."""
    # Create a fake roster file so the loader has something to find.
    roster_dir = tmp_path / "2025" / "teams" / "team-001"
    roster_dir.mkdir(parents=True)
    (roster_dir / "roster.json").write_text("[]")

    with patch("scripts.load.load_config", return_value=_make_mock_config()):
        with patch("scripts.load.RosterLoader") as mock_loader_cls:
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

    with patch("scripts.load.load_config", return_value=_make_mock_config()):
        with patch("scripts.load._LOADERS", fake_loaders):
            exit_code = run(data_root=tmp_path, db_path=tmp_path / "app.db")

    assert good_called == [True]
    assert exit_code == 1


def test_exit_code_0_when_all_loaders_succeed(tmp_path: Path) -> None:
    """Exit code is 0 when all loaders complete without exceptions."""
    roster_dir = tmp_path / "2025" / "teams" / "team-001"
    roster_dir.mkdir(parents=True)
    (roster_dir / "roster.json").write_text("[]")

    with patch("scripts.load.load_config", return_value=_make_mock_config()):
        with patch("scripts.load.RosterLoader") as mock_loader_cls:
            mock_loader = MagicMock()
            mock_loader.load_file.return_value = _make_result()
            mock_loader_cls.return_value = mock_loader

            exit_code = run(data_root=tmp_path, db_path=tmp_path / "app.db")

    assert exit_code == 0


def test_exit_code_1_when_loader_raises(tmp_path: Path) -> None:
    """Exit code is 1 when any loader raises an unhandled exception."""

    def _crashing_runner(db: object, config: object, data_root: Path) -> LoadResult:
        raise ValueError("DB exploded")

    with patch("scripts.load.load_config", return_value=_make_mock_config()):
        with patch("scripts.load._LOADERS", [("roster", _crashing_runner)]):
            exit_code = run(data_root=tmp_path, db_path=tmp_path / "app.db")

    assert exit_code == 1


# ---------------------------------------------------------------------------
# Missing roster file is logged and skipped, not crashed
# ---------------------------------------------------------------------------

def test_missing_roster_file_skipped_gracefully(tmp_path: Path) -> None:
    """If roster.json does not exist for a team, it is skipped without error."""
    config = _make_mock_config(team_ids=["team-no-file"])

    with patch("scripts.load.load_config", return_value=config):
        with patch("scripts.load.RosterLoader") as mock_loader_cls:
            mock_loader = MagicMock()
            mock_loader_cls.return_value = mock_loader

            exit_code = run(data_root=tmp_path, db_path=tmp_path / "app.db")

    assert exit_code == 0
    mock_loader.load_file.assert_not_called()


# ---------------------------------------------------------------------------
# Game loader wiring
# ---------------------------------------------------------------------------

def test_loader_filter_runs_only_game(tmp_path: Path) -> None:
    """--loader game invokes GameLoader.load_all for each team."""
    team_dir = tmp_path / "2025" / "teams" / "team-001"
    team_dir.mkdir(parents=True)

    with patch("scripts.load.load_config", return_value=_make_mock_config()):
        with patch("scripts.load.GameLoader") as mock_loader_cls:
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


def test_game_loader_constructs_with_correct_season_and_team(tmp_path: Path) -> None:
    """GameLoader is constructed with season_id and owned_team_id from config."""
    team_dir = tmp_path / "2025" / "teams" / "team-abc"
    team_dir.mkdir(parents=True)

    config = _make_mock_config(season="2025", team_ids=["team-abc"])

    with patch("scripts.load.load_config", return_value=config):
        with patch("scripts.load.GameLoader") as mock_loader_cls:
            mock_loader = MagicMock()
            mock_loader.load_all.return_value = _make_result()
            mock_loader_cls.return_value = mock_loader

            run(loader_filter="game", data_root=tmp_path, db_path=tmp_path / "app.db")

    mock_loader_cls.assert_called_once_with(
        mock_loader_cls.call_args[0][0],  # db positional arg
        season_id="2025",
        owned_team_id="team-abc",
    )


def test_missing_game_team_dir_skipped_gracefully(tmp_path: Path) -> None:
    """If team directory does not exist, game loader skips without error."""
    config = _make_mock_config(team_ids=["team-no-dir"])

    with patch("scripts.load.load_config", return_value=config):
        with patch("scripts.load.GameLoader") as mock_loader_cls:
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

    with patch("scripts.load.load_config", return_value=_make_mock_config()):
        with patch("scripts.load.SeasonStatsLoader") as mock_loader_cls:
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

    with patch("scripts.load.load_config", return_value=config):
        with patch("scripts.load.SeasonStatsLoader") as mock_loader_cls:
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

    with patch("scripts.load.load_config_from_db", return_value=_make_mock_config()) as mock_cfg:
        with patch("scripts.load.sqlite3") as mock_sqlite:
            mock_sqlite.connect.return_value.__enter__ = lambda s: s
            mock_sqlite.connect.return_value.__exit__ = MagicMock(return_value=False)
            mock_sqlite.connect.return_value.execute = MagicMock()
            # Patch _LOADERS to empty so the loader loop doesn't run
            with patch("scripts.load._LOADERS", []):
                run(source="db", data_root=tmp_path, db_path=default_db)

    # Config was loaded from the resolved DB path
    mock_cfg.assert_called_once_with(resolved_db)
    # sqlite3.connect was called with the same resolved path (not the default)
    mock_sqlite.connect.assert_called_once_with(str(resolved_db))


def test_source_db_dry_run_shows_resolved_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Dry run with source='db' prints the DATABASE_PATH-resolved path."""
    resolved_db = tmp_path / "override.db"
    default_db = tmp_path / "app.db"

    monkeypatch.setenv("DATABASE_PATH", str(resolved_db))

    with patch("scripts.load.load_config_from_db", return_value=_make_mock_config()):
        run(dry_run=True, source="db", data_root=tmp_path, db_path=default_db)

    captured = capsys.readouterr()
    assert str(resolved_db) in captured.out
    assert str(default_db) not in captured.out


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

    with patch("scripts.load.load_config", return_value=_make_mock_config()):
        with patch("scripts.load._LOADERS", fake_loaders):
            exit_code = run(data_root=tmp_path, db_path=tmp_path / "app.db")

    assert exit_code == 0
    assert call_order == ["roster", "game", "season-stats"]
