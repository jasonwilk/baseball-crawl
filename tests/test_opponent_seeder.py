"""Unit tests for src/gamechanger/loaders/opponent_seeder.py.

Tests cover all acceptance criteria for E-152-01:
- AC-1: Unique opponents from schedule → one row each in opponent_links
- AC-2: Opponent in both sources uses opponents.json name; resolution fields NULL
- AC-3: Opponent absent from opponents.json gets name-only row, resolution NULL
- AC-4: Idempotent -- running twice creates no duplicate rows
- AC-5: pregame_data.opponent_id stored as root_team_id
- AC-6: Upsert always refreshes opponent_name; resolution fields are never overwritten
- AC-7: Events without pregame_data or opponent_id are skipped without error
- AC-8: Missing/empty schedule.json returns 0; missing opponents.json is non-fatal

No network calls are made -- all inputs are fixture JSON files and in-memory SQLite.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from src.gamechanger.loaders.opponent_seeder import seed_schedule_opponents


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory SQLite DB with the minimum schema for opponent_links tests."""
    conn = sqlite3.connect(":memory:")
    # Disable FK enforcement so test setup doesn't need a full schema.
    conn.execute("PRAGMA foreign_keys=OFF;")
    conn.execute("""
        CREATE TABLE teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            membership_type TEXT NOT NULL DEFAULT 'member',
            gc_uuid TEXT,
            is_active INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE opponent_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            our_team_id INTEGER NOT NULL,
            root_team_id TEXT NOT NULL,
            opponent_name TEXT NOT NULL,
            resolved_team_id INTEGER,
            public_id TEXT,
            resolution_method TEXT,
            resolved_at TEXT,
            is_hidden INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(our_team_id, root_team_id)
        )
    """)
    conn.execute("INSERT INTO teams (id, name, membership_type) VALUES (1, 'LSB Varsity', 'member')")
    conn.commit()
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_schedule(tmp_path, events: list) -> object:
    """Write events list to tmp_path/schedule.json and return the Path."""
    from pathlib import Path
    p = tmp_path / "schedule.json"
    p.write_text(json.dumps(events), encoding="utf-8")
    return p


def _write_opponents(tmp_path, opponents: list) -> object:
    """Write opponents list to tmp_path/opponents.json and return the Path."""
    from pathlib import Path
    p = tmp_path / "opponents.json"
    p.write_text(json.dumps(opponents), encoding="utf-8")
    return p


def _game_event(opponent_id: str, opponent_name: str) -> dict:
    """Build a minimal schedule event dict with pregame_data."""
    return {
        "event": {"event_type": "game"},
        "pregame_data": {
            "opponent_id": opponent_id,
            "opponent_name": opponent_name,
        },
    }


def _practice_event() -> dict:
    """Build a practice event dict (no pregame_data)."""
    return {"event": {"event_type": "practice"}}


def _game_event_no_opponent_id(opponent_name: str = "Someone") -> dict:
    """Build a game event with pregame_data but no opponent_id."""
    return {
        "event": {"event_type": "game"},
        "pregame_data": {"opponent_name": opponent_name},
    }


def _opponent_entry(root_team_id: str, name: str, progenitor: str | None = None) -> dict:
    """Build a minimal opponents.json entry."""
    return {
        "root_team_id": root_team_id,
        "name": name,
        "progenitor_team_id": progenitor,
        "is_hidden": False,
    }


def _fetch_links(db: sqlite3.Connection) -> list[dict]:
    """Fetch all opponent_links rows as dicts, ordered by root_team_id."""
    cursor = db.execute("""
        SELECT our_team_id, root_team_id, opponent_name,
               resolved_team_id, public_id, resolution_method
        FROM opponent_links
        ORDER BY root_team_id
    """)
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# AC-1: Seeds unique opponents from schedule
# ---------------------------------------------------------------------------


def test_ac1_seeds_unique_opponents(db, tmp_path):
    """N unique opponents in schedule → N rows in opponent_links."""
    schedule = _write_schedule(tmp_path, [
        _game_event("opp-001", "Team A"),
        _game_event("opp-002", "Team B"),
        _game_event("opp-001", "Team A"),  # duplicate -- should collapse
    ])
    opponents = _write_opponents(tmp_path, [])

    count = seed_schedule_opponents(1, schedule, opponents, db)

    assert count == 2
    rows = _fetch_links(db)
    assert len(rows) == 2
    assert rows[0]["root_team_id"] == "opp-001"
    assert rows[1]["root_team_id"] == "opp-002"
    assert rows[0]["our_team_id"] == 1


def test_ac1_single_opponent_multiple_games(db, tmp_path):
    """One opponent appearing in 5 games → exactly one row."""
    schedule = _write_schedule(tmp_path, [
        _game_event("opp-001", "Team A") for _ in range(5)
    ])
    opponents = _write_opponents(tmp_path, [])

    count = seed_schedule_opponents(1, schedule, opponents, db)

    assert count == 1
    assert db.execute("SELECT COUNT(*) FROM opponent_links").fetchone()[0] == 1


# ---------------------------------------------------------------------------
# AC-2: Opponent in both sources uses opponents.json name; resolution NULL
# ---------------------------------------------------------------------------


def test_ac2_uses_opponents_json_name_when_both_present(db, tmp_path):
    """When opponent appears in both sources, opponents.json name wins."""
    schedule = _write_schedule(tmp_path, [
        _game_event("opp-001", "Schedule Name"),
    ])
    opponents = _write_opponents(tmp_path, [
        _opponent_entry("opp-001", "Opponents JSON Name", progenitor="canon-uuid"),
    ])

    seed_schedule_opponents(1, schedule, opponents, db)

    rows = _fetch_links(db)
    assert len(rows) == 1
    assert rows[0]["opponent_name"] == "Opponents JSON Name"


def test_ac2_resolution_fields_null_after_seeder(db, tmp_path):
    """Seeder sets resolved_team_id and resolution_method to NULL."""
    schedule = _write_schedule(tmp_path, [_game_event("opp-001", "Team")])
    opponents = _write_opponents(tmp_path, [
        _opponent_entry("opp-001", "Team", progenitor="canon-uuid"),
    ])

    seed_schedule_opponents(1, schedule, opponents, db)

    rows = _fetch_links(db)
    assert rows[0]["resolved_team_id"] is None
    assert rows[0]["resolution_method"] is None
    assert rows[0]["public_id"] is None


# ---------------------------------------------------------------------------
# AC-3: Opponent absent from opponents.json gets name-only row
# ---------------------------------------------------------------------------


def test_ac3_absent_from_opponents_json_gets_schedule_name(db, tmp_path):
    """Opponent not in opponents.json uses pregame_data.opponent_name."""
    schedule = _write_schedule(tmp_path, [_game_event("opp-999", "Mystery Team")])
    opponents = _write_opponents(tmp_path, [
        _opponent_entry("opp-other", "Different Team"),
    ])

    seed_schedule_opponents(1, schedule, opponents, db)

    rows = _fetch_links(db)
    assert len(rows) == 1
    assert rows[0]["root_team_id"] == "opp-999"
    assert rows[0]["opponent_name"] == "Mystery Team"
    assert rows[0]["resolved_team_id"] is None
    assert rows[0]["resolution_method"] is None


def test_ac3_null_progenitor_in_opponents_json_still_uses_name(db, tmp_path):
    """Opponents with null progenitor_team_id in opponents.json get correct name."""
    schedule = _write_schedule(tmp_path, [_game_event("opp-null", "Unlinked Team")])
    opponents = _write_opponents(tmp_path, [
        _opponent_entry("opp-null", "Opponents Name", progenitor=None),
    ])

    seed_schedule_opponents(1, schedule, opponents, db)

    rows = _fetch_links(db)
    assert rows[0]["opponent_name"] == "Opponents Name"
    assert rows[0]["resolved_team_id"] is None


# ---------------------------------------------------------------------------
# AC-4: Idempotent -- running twice creates no duplicate rows
# ---------------------------------------------------------------------------


def test_ac4_idempotent_no_duplicates(db, tmp_path):
    """Running the seeder twice produces no duplicate rows."""
    schedule = _write_schedule(tmp_path, [_game_event("opp-001", "Team A")])
    opponents = _write_opponents(tmp_path, [])

    seed_schedule_opponents(1, schedule, opponents, db)
    seed_schedule_opponents(1, schedule, opponents, db)

    assert db.execute("SELECT COUNT(*) FROM opponent_links").fetchone()[0] == 1


def test_ac4_idempotent_count_consistent(db, tmp_path):
    """Count returned on second run equals count from first run."""
    schedule = _write_schedule(tmp_path, [
        _game_event("opp-001", "Team A"),
        _game_event("opp-002", "Team B"),
    ])
    opponents = _write_opponents(tmp_path, [])

    first = seed_schedule_opponents(1, schedule, opponents, db)
    second = seed_schedule_opponents(1, schedule, opponents, db)

    assert first == second == 2


# ---------------------------------------------------------------------------
# AC-5: pregame_data.opponent_id stored as root_team_id
# ---------------------------------------------------------------------------


def test_ac5_opponent_id_stored_as_root_team_id(db, tmp_path):
    """pregame_data.opponent_id is used as root_team_id in opponent_links."""
    schedule = _write_schedule(tmp_path, [_game_event("root-uuid-abc123", "Team X")])
    opponents = _write_opponents(tmp_path, [])

    seed_schedule_opponents(1, schedule, opponents, db)

    row = db.execute("SELECT root_team_id FROM opponent_links").fetchone()
    assert row[0] == "root-uuid-abc123"


# ---------------------------------------------------------------------------
# AC-6: Upsert refreshes opponent_name; resolution fields never overwritten
# ---------------------------------------------------------------------------


def test_ac6_updates_name_but_preserves_auto_resolution(db, tmp_path):
    """Second run updates opponent_name but leaves auto-resolved fields intact."""
    # Pre-seed a resolved row (simulating OpponentResolver output)
    db.execute("""
        INSERT INTO opponent_links
            (our_team_id, root_team_id, opponent_name,
             resolved_team_id, public_id, resolution_method, resolved_at)
        VALUES (1, 'opp-001', 'Old Name', 99, 'some-slug', 'auto', datetime('now'))
    """)
    db.commit()

    schedule = _write_schedule(tmp_path, [_game_event("opp-001", "New Schedule Name")])
    opponents = _write_opponents(tmp_path, [
        _opponent_entry("opp-001", "New Opponents Name", progenitor="x"),
    ])

    seed_schedule_opponents(1, schedule, opponents, db)

    row = db.execute("""
        SELECT opponent_name, resolved_team_id, public_id, resolution_method
        FROM opponent_links WHERE root_team_id = 'opp-001'
    """).fetchone()
    assert row[0] == "New Opponents Name"  # name updated
    assert row[1] == 99                    # resolved_team_id preserved
    assert row[2] == "some-slug"           # public_id preserved
    assert row[3] == "auto"               # resolution_method preserved


def test_ac6_manual_resolution_preserved(db, tmp_path):
    """Manual resolution is not overwritten by the seeder."""
    db.execute("""
        INSERT INTO opponent_links
            (our_team_id, root_team_id, opponent_name, resolved_team_id, resolution_method)
        VALUES (1, 'opp-manual', 'Original Name', 42, 'manual')
    """)
    db.commit()

    schedule = _write_schedule(tmp_path, [_game_event("opp-manual", "New Name")])
    opponents = _write_opponents(tmp_path, [])

    seed_schedule_opponents(1, schedule, opponents, db)

    row = db.execute("""
        SELECT opponent_name, resolved_team_id, resolution_method
        FROM opponent_links WHERE root_team_id = 'opp-manual'
    """).fetchone()
    assert row[0] == "New Name"   # name updated
    assert row[1] == 42           # resolved_team_id preserved
    assert row[2] == "manual"     # resolution_method preserved


def test_ac6_follow_bridge_resolution_preserved(db, tmp_path):
    """follow-bridge resolution method is not overwritten."""
    db.execute("""
        INSERT INTO opponent_links
            (our_team_id, root_team_id, opponent_name, public_id, resolution_method)
        VALUES (1, 'opp-bridge', 'Bridge Team', 'bridge-slug', 'follow-bridge')
    """)
    db.commit()

    schedule = _write_schedule(tmp_path, [_game_event("opp-bridge", "Updated Name")])
    opponents = _write_opponents(tmp_path, [])

    seed_schedule_opponents(1, schedule, opponents, db)

    row = db.execute("""
        SELECT opponent_name, public_id, resolution_method
        FROM opponent_links WHERE root_team_id = 'opp-bridge'
    """).fetchone()
    assert row[0] == "Updated Name"     # name updated
    assert row[1] == "bridge-slug"      # public_id preserved
    assert row[2] == "follow-bridge"    # resolution_method preserved


def test_ac6_unresolved_row_name_updated(db, tmp_path):
    """A row with NULL resolution_method still gets opponent_name updated."""
    db.execute("""
        INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name)
        VALUES (1, 'opp-unresolved', 'Old Name')
    """)
    db.commit()

    schedule = _write_schedule(tmp_path, [_game_event("opp-unresolved", "Schedule Name")])
    opponents = _write_opponents(tmp_path, [
        _opponent_entry("opp-unresolved", "New Opponents Name"),
    ])

    seed_schedule_opponents(1, schedule, opponents, db)

    row = db.execute("SELECT opponent_name FROM opponent_links WHERE root_team_id = 'opp-unresolved'").fetchone()
    assert row[0] == "New Opponents Name"


# ---------------------------------------------------------------------------
# AC-7: Events without pregame_data or opponent_id are skipped
# ---------------------------------------------------------------------------


def test_ac7_skips_events_without_pregame_data(db, tmp_path):
    """Practice/non-game events without pregame_data are skipped without error."""
    schedule = _write_schedule(tmp_path, [
        _practice_event(),
        _practice_event(),
        _game_event("opp-001", "Real Team"),
    ])
    opponents = _write_opponents(tmp_path, [])

    count = seed_schedule_opponents(1, schedule, opponents, db)

    assert count == 1
    rows = _fetch_links(db)
    assert len(rows) == 1
    assert rows[0]["root_team_id"] == "opp-001"


def test_ac7_skips_events_without_opponent_id(db, tmp_path):
    """Game events with pregame_data but no opponent_id are skipped without error."""
    schedule = _write_schedule(tmp_path, [
        _game_event_no_opponent_id("Unnamed Opponent"),
        _game_event("opp-001", "Valid Team"),
    ])
    opponents = _write_opponents(tmp_path, [])

    count = seed_schedule_opponents(1, schedule, opponents, db)

    assert count == 1
    assert _fetch_links(db)[0]["root_team_id"] == "opp-001"


def test_ac7_all_non_game_events_returns_zero(db, tmp_path):
    """Schedule with only practice events returns 0 without error."""
    schedule = _write_schedule(tmp_path, [
        _practice_event(),
        _practice_event(),
    ])
    opponents = _write_opponents(tmp_path, [])

    count = seed_schedule_opponents(1, schedule, opponents, db)

    assert count == 0
    assert db.execute("SELECT COUNT(*) FROM opponent_links").fetchone()[0] == 0


# ---------------------------------------------------------------------------
# AC-8: Missing/empty schedule.json returns 0; missing opponents.json is non-fatal
# ---------------------------------------------------------------------------


def test_ac8_missing_schedule_returns_zero(db, tmp_path):
    """Missing schedule.json returns 0 without raising."""
    from pathlib import Path
    schedule_path = tmp_path / "schedule.json"  # does not exist
    opponents_path = tmp_path / "opponents.json"
    opponents_path.write_text("[]", encoding="utf-8")

    count = seed_schedule_opponents(1, schedule_path, opponents_path, db)

    assert count == 0
    assert db.execute("SELECT COUNT(*) FROM opponent_links").fetchone()[0] == 0


def test_ac8_empty_schedule_file_returns_zero(db, tmp_path):
    """schedule.json with empty content returns 0 without raising."""
    from pathlib import Path
    schedule_path = tmp_path / "schedule.json"
    schedule_path.write_text("", encoding="utf-8")
    opponents = _write_opponents(tmp_path, [])

    count = seed_schedule_opponents(1, schedule_path, opponents, db)

    assert count == 0


def test_ac8_empty_schedule_array_returns_zero(db, tmp_path):
    """schedule.json containing empty array [] returns 0 without raising."""
    schedule = _write_schedule(tmp_path, [])
    opponents = _write_opponents(tmp_path, [])

    count = seed_schedule_opponents(1, schedule, opponents, db)

    assert count == 0


def test_ac8_missing_opponents_json_uses_schedule_names(db, tmp_path):
    """Missing opponents.json is non-fatal; schedule pregame_data names are used."""
    from pathlib import Path
    schedule = _write_schedule(tmp_path, [
        _game_event("opp-001", "Schedule Team Name"),
        _game_event("opp-002", "Another Team"),
    ])
    opponents_path = tmp_path / "opponents.json"  # does not exist

    count = seed_schedule_opponents(1, schedule, opponents_path, db)

    assert count == 2
    rows = {r["root_team_id"]: r for r in _fetch_links(db)}
    assert rows["opp-001"]["opponent_name"] == "Schedule Team Name"
    assert rows["opp-002"]["opponent_name"] == "Another Team"


# ---------------------------------------------------------------------------
# Additional edge-case tests
# ---------------------------------------------------------------------------


def test_our_team_id_matches_team_id_argument(db, tmp_path):
    """our_team_id in opponent_links matches the team_id argument."""
    db.execute("INSERT INTO teams (id, name, membership_type) VALUES (7, 'JV', 'member')")
    db.commit()

    schedule = _write_schedule(tmp_path, [_game_event("opp-001", "Opponent")])
    opponents = _write_opponents(tmp_path, [])

    seed_schedule_opponents(7, schedule, opponents, db)

    row = db.execute("SELECT our_team_id FROM opponent_links").fetchone()
    assert row[0] == 7


def test_schedule_fallback_when_not_in_opponents_json(db, tmp_path):
    """Uses pregame_data.opponent_name when that opponent is absent from opponents.json."""
    schedule = _write_schedule(tmp_path, [
        _game_event("opp-new", "New Team Schedule Name"),
    ])
    opponents = _write_opponents(tmp_path, [
        _opponent_entry("opp-other", "Some Other Team"),
    ])

    seed_schedule_opponents(1, schedule, opponents, db)

    row = db.execute("SELECT opponent_name FROM opponent_links WHERE root_team_id = 'opp-new'").fetchone()
    assert row[0] == "New Team Schedule Name"


def test_multiple_opponents_mixed_sources(db, tmp_path):
    """Some opponents in opponents.json, some not -- both handled correctly."""
    schedule = _write_schedule(tmp_path, [
        _game_event("opp-linked", "Schedule Name for Linked"),
        _game_event("opp-unlinked", "Only Schedule Name"),
    ])
    opponents = _write_opponents(tmp_path, [
        _opponent_entry("opp-linked", "Canonical Name from Opponents", progenitor="uuid-x"),
    ])

    count = seed_schedule_opponents(1, schedule, opponents, db)

    assert count == 2
    rows = {r["root_team_id"]: r for r in _fetch_links(db)}
    assert rows["opp-linked"]["opponent_name"] == "Canonical Name from Opponents"
    assert rows["opp-unlinked"]["opponent_name"] == "Only Schedule Name"


def test_returns_count_of_unique_opponents(db, tmp_path):
    """Return value equals the count of unique opponents, not schedule events."""
    schedule = _write_schedule(tmp_path, [
        _game_event("opp-001", "Team A"),
        _game_event("opp-002", "Team B"),
        _game_event("opp-001", "Team A"),  # repeat of opp-001
        _game_event("opp-003", "Team C"),
        _practice_event(),                 # skipped
    ])
    opponents = _write_opponents(tmp_path, [])

    count = seed_schedule_opponents(1, schedule, opponents, db)

    assert count == 3  # 3 unique opponent_ids


def test_malformed_schedule_json_raises(db, tmp_path):
    """Malformed JSON in schedule.json propagates json.JSONDecodeError."""
    import json
    schedule_path = tmp_path / "schedule.json"
    schedule_path.write_text("{not valid json", encoding="utf-8")
    opponents = _write_opponents(tmp_path, [])

    with pytest.raises(json.JSONDecodeError):
        seed_schedule_opponents(1, schedule_path, opponents, db)


def test_malformed_opponents_json_raises(db, tmp_path):
    """Malformed JSON in opponents.json propagates json.JSONDecodeError."""
    import json
    schedule = _write_schedule(tmp_path, [_game_event("opp-001", "Team")])
    opponents_path = tmp_path / "opponents.json"
    opponents_path.write_text("{bad json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        seed_schedule_opponents(1, schedule_path=schedule, opponents_path=opponents_path, db=db)


# ---------------------------------------------------------------------------
# E-167: is_hidden filtering
# ---------------------------------------------------------------------------


def _opponent_entry_hidden(root_team_id: str, name: str) -> dict:
    """Build an opponents.json entry with is_hidden=true."""
    return {
        "root_team_id": root_team_id,
        "name": name,
        "progenitor_team_id": None,
        "is_hidden": True,
    }


def test_is_hidden_opponents_filtered_from_seeding(db, tmp_path):
    """Opponents with is_hidden=true in opponents.json are not seeded."""
    schedule = _write_schedule(tmp_path, [
        _game_event("opp-visible", "Visible Team"),
        _game_event("opp-hidden", "Hidden Team"),
    ])
    opponents = _write_opponents(tmp_path, [
        _opponent_entry("opp-visible", "Visible Team"),
        _opponent_entry_hidden("opp-hidden", "Hidden Team"),
    ])

    count = seed_schedule_opponents(1, schedule, opponents, db)

    assert count == 1
    rows = _fetch_links(db)
    assert len(rows) == 1
    assert rows[0]["root_team_id"] == "opp-visible"


def test_is_hidden_all_opponents_hidden_returns_zero(db, tmp_path):
    """When all opponents are hidden, seeder returns 0."""
    schedule = _write_schedule(tmp_path, [
        _game_event("opp-hidden", "Hidden Team"),
    ])
    opponents = _write_opponents(tmp_path, [
        _opponent_entry_hidden("opp-hidden", "Hidden Team"),
    ])

    count = seed_schedule_opponents(1, schedule, opponents, db)

    assert count == 0
    assert db.execute("SELECT COUNT(*) FROM opponent_links").fetchone()[0] == 0


def test_is_hidden_without_opponents_json_does_not_filter(db, tmp_path):
    """Without opponents.json, no is_hidden info available -- all are seeded."""
    from pathlib import Path
    schedule = _write_schedule(tmp_path, [
        _game_event("opp-001", "Team A"),
    ])
    opponents_path = tmp_path / "opponents.json"  # does not exist

    count = seed_schedule_opponents(1, schedule, opponents_path, db)

    assert count == 1
