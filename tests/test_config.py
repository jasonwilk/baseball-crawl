"""Tests for load_config_from_db() in src/gamechanger/config.py (E-042-06, E-094-03, E-100-03).

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
        teams: List of dicts with keys: gc_uuid, name, classification (optional),
            membership_type, is_active.
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
            "INSERT INTO teams (gc_uuid, name, classification, membership_type, is_active) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                t["gc_uuid"],
                t["name"],
                t.get("classification"),
                t["membership_type"],
                t["is_active"],
            ),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SEASON = {"season_id": "2026-spring-hs", "name": "Spring 2026 HS", "season_type": "spring-hs", "year": 2026}

_UUID_VARSITY = "aaaaaaaa-0000-4000-8000-000000000001"
_UUID_JV = "aaaaaaaa-0000-4000-8000-000000000002"
_UUID_OPP = "aaaaaaaa-0000-4000-8000-000000000003"

_MEMBER_ACTIVE = {"gc_uuid": _UUID_VARSITY, "name": "LSB Varsity", "classification": "varsity", "membership_type": "member", "is_active": 1}
_MEMBER_INACTIVE = {"gc_uuid": _UUID_JV, "name": "LSB JV", "classification": "jv", "membership_type": "member", "is_active": 0}
_TRACKED_ACTIVE = {"gc_uuid": _UUID_OPP, "name": "Opponent FC", "classification": None, "membership_type": "tracked", "is_active": 1}


# ---------------------------------------------------------------------------
# Tests: correct team filtering
# ---------------------------------------------------------------------------


def test_load_config_from_db_returns_member_active_teams(tmp_path: Path) -> None:
    """load_config_from_db returns active member teams in CrawlConfig."""
    db_file = _make_db(tmp_path)
    _seed(db_file, [_SEASON], [_MEMBER_ACTIVE])

    config = load_config_from_db(db_file)

    assert isinstance(config, CrawlConfig)
    assert config.season == "2026-spring-hs"
    assert len(config.member_teams) == 1
    team = config.member_teams[0]
    assert isinstance(team, TeamEntry)
    assert team.id == _UUID_VARSITY
    assert team.name == "LSB Varsity"
    assert team.classification == "varsity"


def test_load_config_from_db_excludes_inactive_member_teams(tmp_path: Path) -> None:
    """load_config_from_db excludes teams with is_active=0."""
    db_file = _make_db(tmp_path)
    _seed(db_file, [_SEASON], [_MEMBER_ACTIVE, _MEMBER_INACTIVE])

    config = load_config_from_db(db_file)

    team_ids = [t.id for t in config.member_teams]
    assert _UUID_VARSITY in team_ids
    assert _UUID_JV not in team_ids


def test_load_config_from_db_excludes_tracked_teams(tmp_path: Path) -> None:
    """load_config_from_db excludes teams with membership_type='tracked'."""
    db_file = _make_db(tmp_path)
    _seed(db_file, [_SEASON], [_MEMBER_ACTIVE, _TRACKED_ACTIVE])

    config = load_config_from_db(db_file)

    team_ids = [t.id for t in config.member_teams]
    assert _UUID_VARSITY in team_ids
    assert _UUID_OPP not in team_ids


def test_load_config_from_db_empty_teams_list(tmp_path: Path) -> None:
    """load_config_from_db returns empty member_teams when no active member teams exist."""
    db_file = _make_db(tmp_path)
    _seed(db_file, [_SEASON], [])

    config = load_config_from_db(db_file)

    assert config.member_teams == []
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
    _seed(db_file, seasons, [_MEMBER_ACTIVE])

    config = load_config_from_db(db_file)

    assert config.season == "2026-spring-hs"


def test_load_config_from_db_raises_when_no_seasons(tmp_path: Path) -> None:
    """load_config_from_db raises ValueError when the seasons table is empty."""
    db_file = _make_db(tmp_path)
    # No seasons seeded.

    with pytest.raises(ValueError, match="No seasons found in database"):
        load_config_from_db(db_file)


# ---------------------------------------------------------------------------
# Tests: null classification handling
# ---------------------------------------------------------------------------


def test_load_config_from_db_null_classification_becomes_empty_string(tmp_path: Path) -> None:
    """load_config_from_db converts NULL classification to empty string in TeamEntry."""
    db_file = _make_db(tmp_path)
    team = {"gc_uuid": "aaaaaaaa-0000-4000-8000-000000000004", "name": "No Class Team", "classification": None, "membership_type": "member", "is_active": 1}
    _seed(db_file, [_SEASON], [team])

    config = load_config_from_db(db_file)

    assert len(config.member_teams) == 1
    assert config.member_teams[0].classification == ""


# ---------------------------------------------------------------------------
# Tests: internal_id population (E-100-03)
# ---------------------------------------------------------------------------


def test_load_config_from_db_populates_internal_id(tmp_path: Path) -> None:
    """load_config_from_db populates internal_id from teams.id INTEGER PK."""
    db_file = _make_db(tmp_path)
    _seed(db_file, [_SEASON], [_MEMBER_ACTIVE])

    config = load_config_from_db(db_file)

    assert len(config.member_teams) == 1
    team = config.member_teams[0]
    assert team.internal_id is not None
    assert isinstance(team.internal_id, int)
    assert team.internal_id > 0


def test_load_config_yaml_populates_internal_id_when_db_path_given(tmp_path: Path) -> None:
    """load_config with db_path= populates internal_id via DB lookup."""
    db_file = _make_db(tmp_path)
    _seed(db_file, [_SEASON], [_MEMBER_ACTIVE])

    yaml_content = (
        f"season: '2026-spring-hs'\n"
        f"member_teams:\n"
        f"  - id: {_UUID_VARSITY}\n"
        f"    name: LSB Varsity\n"
        f"    classification: varsity\n"
    )
    yaml_file = tmp_path / "teams.yaml"
    yaml_file.write_text(yaml_content)

    config = load_config(yaml_file, db_path=db_file)

    assert len(config.member_teams) == 1
    team = config.member_teams[0]
    assert team.internal_id is not None
    assert isinstance(team.internal_id, int)
    assert team.internal_id > 0


def test_load_config_yaml_internal_id_none_when_no_db(tmp_path: Path) -> None:
    """load_config without db_path leaves internal_id as None."""
    yaml_content = (
        "season: '2026'\n"
        "member_teams:\n"
        "  - id: team-abc\n"
        "    name: Lincoln Varsity\n"
        "    classification: varsity\n"
    )
    yaml_file = tmp_path / "teams.yaml"
    yaml_file.write_text(yaml_content)

    config = load_config(yaml_file)

    assert len(config.member_teams) == 1
    assert config.member_teams[0].internal_id is None


# ---------------------------------------------------------------------------
# Tests: YAML loading with new field names (AC-11)
# ---------------------------------------------------------------------------


def test_load_config_yaml_reads_member_teams_key(tmp_path: Path) -> None:
    """load_config reads member_teams: YAML key."""
    yaml_content = (
        "season: '2026'\n"
        "member_teams:\n"
        "  - id: team-abc\n"
        "    name: Lincoln Varsity\n"
        "    classification: varsity\n"
        "  - id: team-def\n"
        "    name: Lincoln JV\n"
        "    classification: jv\n"
    )
    yaml_file = tmp_path / "teams.yaml"
    yaml_file.write_text(yaml_content)

    config = load_config(yaml_file)

    assert len(config.member_teams) == 2
    assert config.member_teams[0].id == "team-abc"
    assert config.member_teams[0].classification == "varsity"
    assert config.member_teams[1].classification == "jv"


def test_team_entry_has_classification_field() -> None:
    """TeamEntry uses classification, not level."""
    entry = TeamEntry(id="abc", name="Test", classification="jv")
    assert entry.classification == "jv"
    assert not hasattr(entry, "level")


# ---------------------------------------------------------------------------
# Tests: placeholder gc_uuid filtering (E-127-06)
# ---------------------------------------------------------------------------

_VALID_UUID = "ffffffff-0000-4000-a000-000000000099"
_PLACEHOLDER_UUID = "lsb-varsity-uuid-2026"


def test_load_config_from_db_skips_null_gc_uuid(tmp_path: Path) -> None:
    """load_config_from_db skips teams with NULL gc_uuid (AC-1)."""
    db_file = _make_db(tmp_path)
    team_null = {"gc_uuid": None, "name": "Null UUID Team", "classification": "varsity", "membership_type": "member", "is_active": 1}
    _seed(db_file, [_SEASON], [team_null])

    config = load_config_from_db(db_file)

    assert config.member_teams == []


def test_load_config_from_db_skips_null_gc_uuid_logs_nothing(tmp_path: Path, caplog) -> None:
    """NULL gc_uuid teams are excluded via SQL -- no Python-level warning needed."""
    import logging
    db_file = _make_db(tmp_path)
    team_null = {"gc_uuid": None, "name": "Null UUID Team", "classification": "varsity", "membership_type": "member", "is_active": 1}
    _seed(db_file, [_SEASON], [team_null])

    with caplog.at_level(logging.WARNING, logger="src.gamechanger.config"):
        config = load_config_from_db(db_file)

    assert config.member_teams == []


def test_load_config_from_db_skips_placeholder_gc_uuid(tmp_path: Path) -> None:
    """load_config_from_db skips teams with non-UUID gc_uuid values (AC-2)."""
    db_file = _make_db(tmp_path)
    team_placeholder = {"gc_uuid": _PLACEHOLDER_UUID, "name": "LSB Varsity", "classification": "varsity", "membership_type": "member", "is_active": 1}
    _seed(db_file, [_SEASON], [team_placeholder])

    config = load_config_from_db(db_file)

    assert config.member_teams == []


def test_load_config_from_db_placeholder_logs_warning(tmp_path: Path, caplog) -> None:
    """load_config_from_db logs a warning with team name and reason for placeholder gc_uuid (AC-4)."""
    import logging
    db_file = _make_db(tmp_path)
    team_placeholder = {"gc_uuid": _PLACEHOLDER_UUID, "name": "LSB Varsity", "classification": "varsity", "membership_type": "member", "is_active": 1}
    _seed(db_file, [_SEASON], [team_placeholder])

    with caplog.at_level(logging.WARNING, logger="src.gamechanger.config"):
        load_config_from_db(db_file)

    assert any("LSB Varsity" in r.message and _PLACEHOLDER_UUID in r.message for r in caplog.records)


def test_load_config_from_db_includes_valid_uuid_team(tmp_path: Path) -> None:
    """load_config_from_db includes teams with valid UUID-format gc_uuid (AC-3)."""
    db_file = _make_db(tmp_path)
    team_valid = {"gc_uuid": _VALID_UUID, "name": "LSB JV", "classification": "jv", "membership_type": "member", "is_active": 1}
    _seed(db_file, [_SEASON], [team_valid])

    config = load_config_from_db(db_file)

    assert len(config.member_teams) == 1
    assert config.member_teams[0].id == _VALID_UUID
    assert config.member_teams[0].name == "LSB JV"


def test_load_config_from_db_mixed_gc_uuid_validity(tmp_path: Path) -> None:
    """load_config_from_db includes valid UUID teams and skips placeholder teams (AC-3, AC-5)."""
    db_file = _make_db(tmp_path)
    team_valid = {"gc_uuid": _VALID_UUID, "name": "LSB Varsity", "classification": "varsity", "membership_type": "member", "is_active": 1}
    team_placeholder = {"gc_uuid": _PLACEHOLDER_UUID, "name": "LSB JV", "classification": "jv", "membership_type": "member", "is_active": 1}
    team_null = {"gc_uuid": None, "name": "LSB Freshman", "classification": "freshman", "membership_type": "member", "is_active": 1}
    _seed(db_file, [_SEASON], [team_valid, team_placeholder, team_null])

    config = load_config_from_db(db_file)

    assert len(config.member_teams) == 1
    assert config.member_teams[0].id == _VALID_UUID
