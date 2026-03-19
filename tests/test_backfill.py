"""Tests for src/gamechanger/loaders/backfill.py (E-132-02).

Covers:
- AC-1: UUID-stub rows are updated when a matching name exists on disk.
- AC-2: Rows with non-UUID names are NOT modified.
- AC-3: Rows with no matching name on disk are unchanged (no error).
- AC-4: Running backfill twice produces the same result (idempotent).
- AC-5: CLI command accessible via 'bb data backfill-team-names'.
- AC-6: Command reports how many team names were updated.

All tests use SQLite in-memory databases and tmp_path fixtures.
No real network calls, no production DB writes.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from migrations.apply_migrations import run_migrations
from src.cli import app
from src.gamechanger.loaders.backfill import (
    backfill_team_names,
    build_name_lookup_from_raw_data,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    """Migrated in-file SQLite connection (backfill uses commit)."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UUID_A = "aaaabbbb-cccc-dddd-eeee-000011112222"
_UUID_B = "bbbbcccc-dddd-eeee-ffff-111122223333"
_UUID_C = "ccccdddd-eeee-ffff-aaaa-222233334444"


def _insert_stub(db: sqlite3.Connection, gc_uuid: str) -> int:
    """Insert a UUID-stub team row (name == gc_uuid) and return its PK."""
    pk = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) VALUES (?, 'tracked', ?, 0)",
        (gc_uuid, gc_uuid),
    ).lastrowid
    db.commit()
    return pk


def _insert_named(db: sqlite3.Connection, gc_uuid: str, name: str) -> int:
    """Insert a team row with a real (non-UUID) name and return its PK."""
    pk = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) VALUES (?, 'tracked', ?, 0)",
        (name, gc_uuid),
    ).lastrowid
    db.commit()
    return pk


def _write_opponents_json(path: Path, entries: list[dict]) -> None:
    path.write_text(json.dumps(entries), encoding="utf-8")


def _write_schedule_json(path: Path, events: list[dict]) -> None:
    path.write_text(json.dumps(events), encoding="utf-8")


def _write_games_json(path: Path, games: list[dict]) -> None:
    path.write_text(json.dumps(games), encoding="utf-8")


def _write_boxscore(path: Path, uuid_key: str) -> None:
    path.write_text(
        json.dumps({
            "own-public-slug": {"players": [], "groups": []},
            uuid_key: {"players": [], "groups": []},
        }),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# build_name_lookup_from_raw_data
# ---------------------------------------------------------------------------


def test_lookup_reads_opponents_json_by_progenitor_team_id(tmp_path: Path) -> None:
    """opponents.json is keyed by progenitor_team_id (not root_team_id)."""
    team_dir = tmp_path / "2025" / "teams" / "team-uuid-001"
    team_dir.mkdir(parents=True)
    _write_opponents_json(
        team_dir / "opponents.json",
        [
            {
                "root_team_id": "root-should-not-be-key",
                "progenitor_team_id": _UUID_A,
                "name": "Blackhawks 14U",
                "is_hidden": False,
            }
        ],
    )

    lookup = build_name_lookup_from_raw_data(tmp_path)

    assert lookup.get(_UUID_A) == "Blackhawks 14U"
    assert "root-should-not-be-key" not in lookup


def test_lookup_skips_hidden_opponents(tmp_path: Path) -> None:
    """Hidden opponents.json entries are excluded from the lookup."""
    team_dir = tmp_path / "2025" / "teams" / "team-uuid-001"
    team_dir.mkdir(parents=True)
    _write_opponents_json(
        team_dir / "opponents.json",
        [{"progenitor_team_id": _UUID_A, "name": "Hidden Team", "is_hidden": True}],
    )

    lookup = build_name_lookup_from_raw_data(tmp_path)

    assert _UUID_A not in lookup


def test_lookup_skips_null_progenitor_team_id(tmp_path: Path) -> None:
    """Entries with null progenitor_team_id are skipped (can't key by None)."""
    team_dir = tmp_path / "2025" / "teams" / "team-uuid-001"
    team_dir.mkdir(parents=True)
    _write_opponents_json(
        team_dir / "opponents.json",
        [{"progenitor_team_id": None, "name": "No UUID Team", "is_hidden": False}],
    )

    lookup = build_name_lookup_from_raw_data(tmp_path)

    assert None not in lookup
    assert len(lookup) == 0


def test_lookup_supplements_from_schedule_json(tmp_path: Path) -> None:
    """schedule.json fills gaps not covered by opponents.json."""
    team_dir = tmp_path / "2025" / "teams" / "team-uuid-001"
    team_dir.mkdir(parents=True)
    # opponents.json has UUID_A; schedule.json supplements with UUID_B.
    _write_opponents_json(
        team_dir / "opponents.json",
        [{"progenitor_team_id": _UUID_A, "name": "Team A", "is_hidden": False}],
    )
    _write_schedule_json(
        team_dir / "schedule.json",
        [{"pregame_data": {"opponent_id": _UUID_B, "opponent_name": "Team B"}}],
    )

    lookup = build_name_lookup_from_raw_data(tmp_path)

    assert lookup.get(_UUID_A) == "Team A"
    assert lookup.get(_UUID_B) == "Team B"


def test_lookup_schedule_does_not_override_opponents(tmp_path: Path) -> None:
    """schedule.json does not overwrite entries already in opponents.json."""
    team_dir = tmp_path / "2025" / "teams" / "team-uuid-001"
    team_dir.mkdir(parents=True)
    _write_opponents_json(
        team_dir / "opponents.json",
        [{"progenitor_team_id": _UUID_A, "name": "Opponents Name", "is_hidden": False}],
    )
    _write_schedule_json(
        team_dir / "schedule.json",
        [{"pregame_data": {"opponent_id": _UUID_A, "opponent_name": "Schedule Name"}}],
    )

    lookup = build_name_lookup_from_raw_data(tmp_path)

    assert lookup[_UUID_A] == "Opponents Name"


def test_lookup_reads_scouting_games_via_boxscores(tmp_path: Path) -> None:
    """Scouting path: UUID keys in boxscores are mapped to names from games.json."""
    scouting_dir = tmp_path / "2025" / "scouting" / "pub-slug-abc"
    (scouting_dir / "boxscores").mkdir(parents=True)
    game_stream_id = "stream-id-game-001"
    _write_games_json(
        scouting_dir / "games.json",
        [
            {
                "id": game_stream_id,
                "game_status": "completed",
                "opponent_team": {"name": "Scouted Opponent"},
            }
        ],
    )
    _write_boxscore(scouting_dir / "boxscores" / f"{game_stream_id}.json", _UUID_C)

    lookup = build_name_lookup_from_raw_data(tmp_path)

    assert lookup.get(_UUID_C) == "Scouted Opponent"


def test_lookup_missing_data_root_returns_empty(tmp_path: Path) -> None:
    """AC-3: build_name_lookup_from_raw_data() returns empty dict when data_root absent."""
    lookup = build_name_lookup_from_raw_data(tmp_path / "no_such_dir")
    assert lookup == {}


def test_lookup_empty_data_root_returns_empty(tmp_path: Path) -> None:
    """AC-3: build_name_lookup_from_raw_data() returns empty dict when no source files found."""
    data_root = tmp_path / "raw"
    data_root.mkdir()
    lookup = build_name_lookup_from_raw_data(data_root)
    assert lookup == {}


def test_lookup_aggregates_across_multiple_seasons(tmp_path: Path) -> None:
    """Names from multiple seasons are merged into one lookup."""
    for season, uuid, name in [
        ("2024", _UUID_A, "Team 2024"),
        ("2025", _UUID_B, "Team 2025"),
    ]:
        team_dir = tmp_path / season / "teams" / f"team-{season}"
        team_dir.mkdir(parents=True)
        _write_opponents_json(
            team_dir / "opponents.json",
            [{"progenitor_team_id": uuid, "name": name, "is_hidden": False}],
        )

    lookup = build_name_lookup_from_raw_data(tmp_path)

    assert lookup.get(_UUID_A) == "Team 2024"
    assert lookup.get(_UUID_B) == "Team 2025"


# ---------------------------------------------------------------------------
# backfill_team_names
# ---------------------------------------------------------------------------


def test_backfill_updates_uuid_stub_rows(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-1: UUID-stub rows are updated with real names from on-disk data."""
    _insert_stub(db, _UUID_A)
    team_dir = tmp_path / "2025" / "teams" / "team-001"
    team_dir.mkdir(parents=True)
    _write_opponents_json(
        team_dir / "opponents.json",
        [{"progenitor_team_id": _UUID_A, "name": "Nighthawks Navy", "is_hidden": False}],
    )

    updated = backfill_team_names(db, tmp_path)

    assert updated == 1
    row = db.execute("SELECT name FROM teams WHERE gc_uuid = ?", (_UUID_A,)).fetchone()
    assert row[0] == "Nighthawks Navy"


def test_backfill_preserves_non_uuid_names(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-2: Rows with non-UUID names are NOT modified by the backfill."""
    _insert_named(db, _UUID_A, "Already Real Name")
    team_dir = tmp_path / "2025" / "teams" / "team-001"
    team_dir.mkdir(parents=True)
    _write_opponents_json(
        team_dir / "opponents.json",
        [{"progenitor_team_id": _UUID_A, "name": "Different Name", "is_hidden": False}],
    )

    updated = backfill_team_names(db, tmp_path)

    assert updated == 0
    row = db.execute("SELECT name FROM teams WHERE gc_uuid = ?", (_UUID_A,)).fetchone()
    assert row[0] == "Already Real Name"


def test_backfill_no_change_when_no_name_data_on_disk(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """AC-3: UUID-stub rows with no matching on-disk data are unchanged (no error)."""
    _insert_stub(db, _UUID_A)
    data_root = tmp_path / "raw"
    data_root.mkdir()

    updated = backfill_team_names(db, data_root)

    assert updated == 0
    row = db.execute("SELECT name FROM teams WHERE gc_uuid = ?", (_UUID_A,)).fetchone()
    assert row[0] == _UUID_A  # unchanged


def test_backfill_idempotent(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-4: Running backfill twice produces the same result."""
    _insert_stub(db, _UUID_A)
    team_dir = tmp_path / "2025" / "teams" / "team-001"
    team_dir.mkdir(parents=True)
    _write_opponents_json(
        team_dir / "opponents.json",
        [{"progenitor_team_id": _UUID_A, "name": "Idempotent Team", "is_hidden": False}],
    )

    first_run = backfill_team_names(db, tmp_path)
    second_run = backfill_team_names(db, tmp_path)

    assert first_run == 1
    assert second_run == 0  # already updated; name no longer == gc_uuid
    row = db.execute("SELECT name FROM teams WHERE gc_uuid = ?", (_UUID_A,)).fetchone()
    assert row[0] == "Idempotent Team"


def test_backfill_multiple_stubs(db: sqlite3.Connection, tmp_path: Path) -> None:
    """Backfill updates all matching UUID-stubs in one pass."""
    _insert_stub(db, _UUID_A)
    _insert_stub(db, _UUID_B)
    _insert_stub(db, _UUID_C)  # no match on disk
    team_dir = tmp_path / "2025" / "teams" / "team-001"
    team_dir.mkdir(parents=True)
    _write_opponents_json(
        team_dir / "opponents.json",
        [
            {"progenitor_team_id": _UUID_A, "name": "Team Alpha", "is_hidden": False},
            {"progenitor_team_id": _UUID_B, "name": "Team Beta", "is_hidden": False},
        ],
    )

    updated = backfill_team_names(db, tmp_path)

    assert updated == 2
    assert db.execute("SELECT name FROM teams WHERE gc_uuid = ?", (_UUID_A,)).fetchone()[0] == "Team Alpha"
    assert db.execute("SELECT name FROM teams WHERE gc_uuid = ?", (_UUID_B,)).fetchone()[0] == "Team Beta"
    assert db.execute("SELECT name FROM teams WHERE gc_uuid = ?", (_UUID_C,)).fetchone()[0] == _UUID_C


def test_backfill_via_scouting_path(db: sqlite3.Connection, tmp_path: Path) -> None:
    """AC-1: Backfill updates UUID-stubs discovered via scouting games.json + boxscores."""
    _insert_stub(db, _UUID_C)
    scouting_dir = tmp_path / "2025" / "scouting" / "pub-slug"
    (scouting_dir / "boxscores").mkdir(parents=True)
    game_stream_id = "stream-scout-001"
    _write_games_json(
        scouting_dir / "games.json",
        [{"id": game_stream_id, "opponent_team": {"name": "Scouted Team Name"}}],
    )
    _write_boxscore(scouting_dir / "boxscores" / f"{game_stream_id}.json", _UUID_C)

    updated = backfill_team_names(db, tmp_path)

    assert updated == 1
    row = db.execute("SELECT name FROM teams WHERE gc_uuid = ?", (_UUID_C,)).fetchone()
    assert row[0] == "Scouted Team Name"


# ---------------------------------------------------------------------------
# P1-2 regression: schedule-only team directories (E-132 remediation)
# ---------------------------------------------------------------------------


def test_lookup_reads_schedule_only_team_directory(tmp_path: Path) -> None:
    """P1-2: build_name_lookup discovers team dirs via schedule.json when no opponents.json."""
    team_dir = tmp_path / "2025" / "teams" / "team-schedule-only"
    team_dir.mkdir(parents=True)
    # Only schedule.json present — no opponents.json.
    _write_schedule_json(
        team_dir / "schedule.json",
        [{"pregame_data": {"opponent_id": _UUID_A, "opponent_name": "Schedule Only Team"}}],
    )

    lookup = build_name_lookup_from_raw_data(tmp_path)

    assert lookup.get(_UUID_A) == "Schedule Only Team"


def test_lookup_schedule_only_dir_not_double_counted_when_opponents_also_present(
    tmp_path: Path,
) -> None:
    """P1-2: A dir with both opponents.json and schedule.json is processed exactly once."""
    team_dir = tmp_path / "2025" / "teams" / "team-both"
    team_dir.mkdir(parents=True)
    _write_opponents_json(
        team_dir / "opponents.json",
        [{"progenitor_team_id": _UUID_A, "name": "From Opponents", "is_hidden": False}],
    )
    _write_schedule_json(
        team_dir / "schedule.json",
        [{"pregame_data": {"opponent_id": _UUID_B, "opponent_name": "From Schedule"}}],
    )

    lookup = build_name_lookup_from_raw_data(tmp_path)

    # Both sources should be included.
    assert lookup.get(_UUID_A) == "From Opponents"
    assert lookup.get(_UUID_B) == "From Schedule"


# ---------------------------------------------------------------------------
# P1-1 regression: two-UUID scouting backfill (E-132 remediation)
# ---------------------------------------------------------------------------

_SCOUTED_OWN_UUID = "00000000-1111-2222-3333-444444444444"
_OPP_GAME1_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_OPP_GAME2_UUID = "ffffffff-0000-1111-2222-333333333333"


def test_lookup_scouting_multi_game_excludes_scouted_team_uuid(tmp_path: Path) -> None:
    """P1-1/backfill: scouted team UUID (appears in all games) is excluded from lookup.

    In a scouting directory with 2+ games, the scouted team's UUID appears in
    every boxscore while each opponent UUID appears in only one.  The lookup
    should contain the opponent UUIDs but not the scouted team's own UUID.
    """
    scouting_dir = tmp_path / "2025" / "scouting" / "pub-slug-multi"
    (scouting_dir / "boxscores").mkdir(parents=True)

    _write_games_json(
        scouting_dir / "games.json",
        [
            {"id": "g001", "opponent_team": {"name": "Opponent 1"}},
            {"id": "g002", "opponent_team": {"name": "Opponent 2"}},
        ],
    )
    # Game 1: scouted team UUID + opponent 1 UUID.
    (scouting_dir / "boxscores" / "g001.json").write_text(
        json.dumps({_SCOUTED_OWN_UUID: {}, _OPP_GAME1_UUID: {}}), encoding="utf-8"
    )
    # Game 2: scouted team UUID + opponent 2 UUID.
    (scouting_dir / "boxscores" / "g002.json").write_text(
        json.dumps({_SCOUTED_OWN_UUID: {}, _OPP_GAME2_UUID: {}}), encoding="utf-8"
    )

    lookup = build_name_lookup_from_raw_data(tmp_path)

    assert lookup.get(_OPP_GAME1_UUID) == "Opponent 1", "Opponent 1 UUID should be in lookup"
    assert lookup.get(_OPP_GAME2_UUID) == "Opponent 2", "Opponent 2 UUID should be in lookup"
    assert _SCOUTED_OWN_UUID not in lookup, (
        "Scouted team's own UUID should be excluded (appears in all games)"
    )


def test_backfill_scouting_multi_game_does_not_label_scouted_team_uuid(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """P1-1/backfill: in a multi-game scouting dir, the scouted team's UUID-stub is not updated."""
    # Insert UUID-stubs for all three UUIDs.
    _insert_stub(db, _SCOUTED_OWN_UUID)
    _insert_stub(db, _OPP_GAME1_UUID)
    _insert_stub(db, _OPP_GAME2_UUID)

    scouting_dir = tmp_path / "2025" / "scouting" / "pub-slug-backfill"
    (scouting_dir / "boxscores").mkdir(parents=True)

    _write_games_json(
        scouting_dir / "games.json",
        [
            {"id": "g001", "opponent_team": {"name": "Opponent Alpha"}},
            {"id": "g002", "opponent_team": {"name": "Opponent Beta"}},
        ],
    )
    (scouting_dir / "boxscores" / "g001.json").write_text(
        json.dumps({_SCOUTED_OWN_UUID: {}, _OPP_GAME1_UUID: {}}), encoding="utf-8"
    )
    (scouting_dir / "boxscores" / "g002.json").write_text(
        json.dumps({_SCOUTED_OWN_UUID: {}, _OPP_GAME2_UUID: {}}), encoding="utf-8"
    )

    updated = backfill_team_names(db, tmp_path)

    # The two opponent stubs should be updated; the scouted team stub should not.
    assert updated == 2
    assert db.execute(
        "SELECT name FROM teams WHERE gc_uuid = ?", (_OPP_GAME1_UUID,)
    ).fetchone()[0] == "Opponent Alpha"
    assert db.execute(
        "SELECT name FROM teams WHERE gc_uuid = ?", (_OPP_GAME2_UUID,)
    ).fetchone()[0] == "Opponent Beta"
    assert db.execute(
        "SELECT name FROM teams WHERE gc_uuid = ?", (_SCOUTED_OWN_UUID,)
    ).fetchone()[0] == _SCOUTED_OWN_UUID, (
        "Scouted team's UUID-stub should remain unchanged (not mislabeled as opponent)"
    )


# ---------------------------------------------------------------------------
# CLI: bb data backfill-team-names (AC-5, AC-6)
# ---------------------------------------------------------------------------


def test_cli_backfill_team_names_reports_updated_count(
    db: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-5 + AC-6: CLI command runs and reports how many names were updated."""
    # Patch the backfill function to avoid needing a real DB path.
    monkeypatch.setattr(
        "src.cli.data._resolve_db_path", lambda: tmp_path / "test.db"
    )

    # Set up DB with a UUID-stub and on-disk data.
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) VALUES (?, 'tracked', ?, 0)",
        (_UUID_A, _UUID_A),
    )
    conn.commit()
    conn.close()

    data_root = tmp_path / "data" / "raw"
    team_dir = data_root / "2025" / "teams" / "team-001"
    team_dir.mkdir(parents=True)
    _write_opponents_json(
        team_dir / "opponents.json",
        [{"progenitor_team_id": _UUID_A, "name": "CLI Test Team", "is_hidden": False}],
    )

    # Monkeypatch the data_root used by the CLI command.
    # CLI uses _PROJECT_ROOT / "data" / "raw"; data_root is already tmp_path / "data" / "raw".
    import src.cli.data as cli_data_module
    monkeypatch.setattr(cli_data_module, "_PROJECT_ROOT", tmp_path)

    runner = CliRunner()
    result = runner.invoke(app, ["data", "backfill-team-names"])

    assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
    assert "1" in result.output
    assert "updated" in result.output.lower()


def test_cli_backfill_team_names_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-5: --dry-run prints info without writing to the database."""
    import src.cli.data as cli_data_module
    monkeypatch.setattr(cli_data_module, "_PROJECT_ROOT", tmp_path)

    data_root = tmp_path / "data" / "raw"
    team_dir = data_root / "2025" / "teams" / "team-001"
    team_dir.mkdir(parents=True)
    _write_opponents_json(
        team_dir / "opponents.json",
        [{"progenitor_team_id": _UUID_A, "name": "Dry Run Team", "is_hidden": False}],
    )

    runner = CliRunner()
    result = runner.invoke(app, ["data", "backfill-team-names", "--dry-run"])

    assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
    assert "dry run" in result.output.lower()
    assert "No changes" in result.output


def test_cli_backfill_team_names_no_stubs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-6: Command reports 0 updated when no UUID-stubs exist."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    monkeypatch.setattr("src.cli.data._resolve_db_path", lambda: db_path)

    import src.cli.data as cli_data_module
    monkeypatch.setattr(cli_data_module, "_PROJECT_ROOT", tmp_path)
    (tmp_path / "data" / "raw").mkdir(parents=True, exist_ok=True)

    runner = CliRunner()
    result = runner.invoke(app, ["data", "backfill-team-names"])

    assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
    assert "0" in result.output


def test_cli_backfill_team_names_error_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Error-path: if backfill_team_names raises, CLI exits non-zero and does not print 'Backfill complete.'"""
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    monkeypatch.setattr("src.cli.data._resolve_db_path", lambda: db_path)

    import src.cli.data as cli_data_module
    monkeypatch.setattr(cli_data_module, "_PROJECT_ROOT", tmp_path)
    (tmp_path / "data" / "raw").mkdir(parents=True, exist_ok=True)

    import src.gamechanger.loaders.backfill as backfill_module

    def _raise(conn, data_root):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(backfill_module, "backfill_team_names", _raise)

    runner = CliRunner()
    result = runner.invoke(app, ["data", "backfill-team-names"])

    assert result.exit_code != 0
    assert "Backfill complete." not in result.output
