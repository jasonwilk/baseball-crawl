"""Tests for load_config_from_db() in src/gamechanger/config.py (E-042-06, E-094-03).

Uses in-memory SQLite databases -- no file I/O, no network calls.

Run with:
    pytest tests/test_config.py -v
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MIGRATION_FILE = _PROJECT_ROOT / "migrations" / "001_initial_schema.sql"

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.gamechanger.config import CrawlConfig, TeamEntry, load_config, load_config_from_db  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    """Create a minimal SQLite DB (teams + seasons tables) and return its path.

    Applies the full 001_initial_schema.sql migration to guarantee correct
    schema structure without duplicating DDL in tests.

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Path to the created database file.
    """
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("PRAGMA foreign_keys=ON;")
    sql = _MIGRATION_FILE.read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()
    conn.close()
    return db_file


def _seed(db_file: Path, seasons: list[dict], teams: list[dict]) -> None:
    """Insert rows into the seasons and teams tables.

    Args:
        db_file: Path to the SQLite database.
        seasons: List of dicts with keys: season_id, name, season_type, year.
        teams: List of dicts with keys: team_id, name, level (optional),
            is_owned, is_active.
    """
    conn = sqlite3.connect(str(db_file))
    conn.execute("PRAGMA foreign_keys=ON;")
    for s in seasons:
        conn.execute(
            "INSERT INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
            (s["season_id"], s["name"], s["season_type"], s["year"]),
        )
    for t in teams:
        conn.execute(
            "INSERT INTO teams (team_id, name, level, is_owned, is_active) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                t["team_id"],
                t["name"],
                t.get("level"),
                t["is_owned"],
                t["is_active"],
            ),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SEASON = {"season_id": "2026-spring-hs", "name": "Spring 2026 HS", "season_type": "spring-hs", "year": 2026}

_OWNED_ACTIVE = {"team_id": "team-varsity", "name": "LSB Varsity", "level": "varsity", "is_owned": 1, "is_active": 1}
_OWNED_INACTIVE = {"team_id": "team-jv", "name": "LSB JV", "level": "jv", "is_owned": 1, "is_active": 0}
_TRACKED_ACTIVE = {"team_id": "team-opp", "name": "Opponent FC", "level": None, "is_owned": 0, "is_active": 1}


# ---------------------------------------------------------------------------
# Tests: correct team filtering
# ---------------------------------------------------------------------------


def test_load_config_from_db_returns_owned_active_teams(tmp_path: Path) -> None:
    """load_config_from_db returns owned active teams in CrawlConfig."""
    db_file = _make_db(tmp_path)
    _seed(db_file, [_SEASON], [_OWNED_ACTIVE])

    config = load_config_from_db(db_file)

    assert isinstance(config, CrawlConfig)
    assert config.season == "2026-spring-hs"
    assert len(config.owned_teams) == 1
    team = config.owned_teams[0]
    assert isinstance(team, TeamEntry)
    assert team.id == "team-varsity"
    assert team.name == "LSB Varsity"
    assert team.level == "varsity"


def test_load_config_from_db_excludes_inactive_owned_teams(tmp_path: Path) -> None:
    """load_config_from_db excludes teams with is_active=0."""
    db_file = _make_db(tmp_path)
    _seed(db_file, [_SEASON], [_OWNED_ACTIVE, _OWNED_INACTIVE])

    config = load_config_from_db(db_file)

    team_ids = [t.id for t in config.owned_teams]
    assert "team-varsity" in team_ids
    assert "team-jv" not in team_ids


def test_load_config_from_db_excludes_tracked_only_teams(tmp_path: Path) -> None:
    """load_config_from_db excludes teams with is_owned=0 (opponent-tracked)."""
    db_file = _make_db(tmp_path)
    _seed(db_file, [_SEASON], [_OWNED_ACTIVE, _TRACKED_ACTIVE])

    config = load_config_from_db(db_file)

    team_ids = [t.id for t in config.owned_teams]
    assert "team-varsity" in team_ids
    assert "team-opp" not in team_ids


def test_load_config_from_db_empty_teams_list(tmp_path: Path) -> None:
    """load_config_from_db returns empty owned_teams when no active owned teams exist."""
    db_file = _make_db(tmp_path)
    _seed(db_file, [_SEASON], [])

    config = load_config_from_db(db_file)

    assert config.owned_teams == []
    assert config.season == "2026-spring-hs"


# ---------------------------------------------------------------------------
# Tests: season derivation
# ---------------------------------------------------------------------------


def test_load_config_from_db_derives_latest_season(tmp_path: Path) -> None:
    """load_config_from_db picks the most recent season by year."""
    db_file = _make_db(tmp_path)
    seasons = [
        {"season_id": "2024-spring-hs", "name": "Spring 2024 HS", "season_type": "spring-hs", "year": 2024},
        {"season_id": "2026-spring-hs", "name": "Spring 2026 HS", "season_type": "spring-hs", "year": 2026},
        {"season_id": "2025-spring-hs", "name": "Spring 2025 HS", "season_type": "spring-hs", "year": 2025},
    ]
    _seed(db_file, seasons, [_OWNED_ACTIVE])

    config = load_config_from_db(db_file)

    assert config.season == "2026-spring-hs"


def test_load_config_from_db_raises_when_no_seasons(tmp_path: Path) -> None:
    """load_config_from_db raises ValueError when the seasons table is empty."""
    db_file = _make_db(tmp_path)
    # No seasons seeded.

    with pytest.raises(ValueError, match="No seasons found in database"):
        load_config_from_db(db_file)


# ---------------------------------------------------------------------------
# Tests: null level handling
# ---------------------------------------------------------------------------


def test_load_config_from_db_null_level_becomes_empty_string(tmp_path: Path) -> None:
    """load_config_from_db converts NULL level to empty string in TeamEntry."""
    db_file = _make_db(tmp_path)
    team = {"team_id": "team-no-level", "name": "No Level Team", "level": None, "is_owned": 1, "is_active": 1}
    _seed(db_file, [_SEASON], [team])

    config = load_config_from_db(db_file)

    assert len(config.owned_teams) == 1
    assert config.owned_teams[0].level == ""


# ---------------------------------------------------------------------------
# Tests: is_owned field (E-094-03)
# ---------------------------------------------------------------------------


def test_load_config_from_db_sets_is_owned_true(tmp_path: Path) -> None:
    """load_config_from_db sets is_owned=True on returned TeamEntry rows."""
    db_file = _make_db(tmp_path)
    _seed(db_file, [_SEASON], [_OWNED_ACTIVE])

    config = load_config_from_db(db_file)

    assert len(config.owned_teams) == 1
    assert config.owned_teams[0].is_owned is True


def test_team_entry_is_owned_default_true() -> None:
    """TeamEntry.is_owned defaults to True when not supplied."""
    entry = TeamEntry(id="abc", name="Test", level="jv")
    assert entry.is_owned is True


def test_load_config_yaml_sets_is_owned_true(tmp_path: Path) -> None:
    """load_config (YAML path) sets is_owned=True on all TeamEntry instances."""
    yaml_content = (
        "season: '2026'\n"
        "owned_teams:\n"
        "  - id: team-abc\n"
        "    name: Lincoln Varsity\n"
        "    level: varsity\n"
        "  - id: team-def\n"
        "    name: Lincoln JV\n"
        "    level: jv\n"
    )
    yaml_file = tmp_path / "teams.yaml"
    yaml_file.write_text(yaml_content)

    config = load_config(yaml_file)

    assert len(config.owned_teams) == 2
    for team in config.owned_teams:
        assert team.is_owned is True
