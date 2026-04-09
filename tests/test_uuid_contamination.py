"""Tests for E-211-01: UUID contamination prevention.

Verifies that none of the three pipeline paths store boxscore-derived
opponent-perspective identifiers as gc_uuid in the teams table.

AC-4: New tests verify no UUID contamination in any of the three paths.
AC-5: Own-team handling in _resolve_team_ids unchanged.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from src.gamechanger.loaders.game_loader import GameLoader, GameSummaryEntry
from src.gamechanger.types import TeamRef

# ---------------------------------------------------------------------------
# Schema fixture
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_MIGRATION_FILE = _PROJECT_ROOT / "migrations" / "001_initial_schema.sql"


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory SQLite connection with full schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    conn.executescript(_MIGRATION_FILE.read_text(encoding="utf-8"))
    conn.commit()
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OWN_GC_UUID = "aaaa1111-2222-3333-4444-555566667777"
_OWN_PUBLIC_ID = "myTeamSlug123"
_OPP_BOXSCORE_KEY = "bbbb2222-3333-4444-5555-666677778888"


def _insert_own_team(db: sqlite3.Connection) -> int:
    """Insert an own-team row and return its PK."""
    cur = db.execute(
        "INSERT INTO teams (gc_uuid, public_id, name, membership_type, is_active, season_year) "
        "VALUES (?, ?, 'Own Team', 'member', 1, 2025)",
        (_OWN_GC_UUID, _OWN_PUBLIC_ID),
    )
    db.commit()
    return cur.lastrowid


def _make_loader(db: sqlite3.Connection) -> GameLoader:
    pk = _insert_own_team(db)
    return GameLoader(
        db,
        owned_team_ref=TeamRef(id=pk, gc_uuid=_OWN_GC_UUID, public_id=_OWN_PUBLIC_ID),
    )


def _make_summary(opponent_id: str = _OPP_BOXSCORE_KEY) -> GameSummaryEntry:
    return GameSummaryEntry(
        event_id="evt-001",
        game_stream_id="stream-001",
        home_away="home",
        owning_team_score=5,
        opponent_team_score=3,
        opponent_id=opponent_id,
        last_scoring_update="2025-05-10T19:39:58.788Z",
    )


# ---------------------------------------------------------------------------
# AC-1: game_loader._ensure_team_row passes gc_uuid=None
# ---------------------------------------------------------------------------


def test_ensure_team_row_passes_gc_uuid_none(db: sqlite3.Connection) -> None:
    """_ensure_team_row calls shared ensure_team_row with gc_uuid=None."""
    loader = _make_loader(db)
    with patch("src.gamechanger.loaders.game_loader.ensure_team_row", wraps=None) as mock_etr:
        mock_etr.return_value = 99
        loader._ensure_team_row(_OPP_BOXSCORE_KEY, opponent_name="Opponent Team")
        mock_etr.assert_called_once()
        call_kwargs = mock_etr.call_args
        assert call_kwargs.kwargs.get("gc_uuid") is None or call_kwargs[1].get("gc_uuid") is None, (
            "gc_uuid must be None -- boxscore keys must not contaminate the gc_uuid column"
        )


def test_ensure_team_row_uses_identifier_as_name_fallback(db: sqlite3.Connection) -> None:
    """When opponent_name is None, the boxscore identifier is used as name (not gc_uuid)."""
    loader = _make_loader(db)
    pk = loader._ensure_team_row(_OPP_BOXSCORE_KEY)
    row = db.execute("SELECT name, gc_uuid FROM teams WHERE id = ?", (pk,)).fetchone()
    assert row is not None
    assert row[0] == _OPP_BOXSCORE_KEY, "Name should be the identifier string"
    assert row[1] is None, "gc_uuid must be NULL -- identifier should not be stored as gc_uuid"


def test_ensure_team_row_with_name_creates_named_row_no_gc_uuid(db: sqlite3.Connection) -> None:
    """When opponent_name is provided, it is used as name; gc_uuid stays NULL."""
    loader = _make_loader(db)
    pk = loader._ensure_team_row(_OPP_BOXSCORE_KEY, opponent_name="East High Tigers")
    row = db.execute("SELECT name, gc_uuid FROM teams WHERE id = ?", (pk,)).fetchone()
    assert row is not None
    assert row[0] == "East High Tigers"
    assert row[1] is None, "gc_uuid must be NULL for opponent rows created via boxscore"


# ---------------------------------------------------------------------------
# AC-1 via _resolve_team_ids: opponent identifier not stored as gc_uuid
# ---------------------------------------------------------------------------


def test_resolve_team_ids_does_not_store_opp_id_as_gc_uuid(db: sqlite3.Connection) -> None:
    """_resolve_team_ids creates an opponent row without storing the boxscore key as gc_uuid."""
    loader = _make_loader(db)
    summary = _make_summary(opponent_id=_OPP_BOXSCORE_KEY)
    own_id, opp_id = loader._resolve_team_ids(summary, opp_key=None, opponent_name="West Lincoln")
    assert opp_id is not None
    row = db.execute("SELECT gc_uuid FROM teams WHERE id = ?", (opp_id,)).fetchone()
    assert row[0] is None, "Opponent gc_uuid must be NULL (not the boxscore key)"


def test_resolve_team_ids_fallback_opp_key_not_stored_as_gc_uuid(db: sqlite3.Connection) -> None:
    """When summary.opponent_id is None, opp_key is used as identifier but NOT as gc_uuid."""
    loader = _make_loader(db)
    summary = _make_summary(opponent_id=None)
    opp_key = "cccc3333-4444-5555-6666-777788889999"
    own_id, opp_id = loader._resolve_team_ids(summary, opp_key=opp_key)
    assert opp_id is not None
    row = db.execute("SELECT gc_uuid, name FROM teams WHERE id = ?", (opp_id,)).fetchone()
    assert row[0] is None, "gc_uuid must be NULL when created from fallback opp_key"
    assert row[1] == opp_key, "Name should fall back to opp_key identifier"


# ---------------------------------------------------------------------------
# AC-5: Own-team handling unchanged
# ---------------------------------------------------------------------------


def test_resolve_team_ids_returns_own_team_id(db: sqlite3.Connection) -> None:
    """_resolve_team_ids returns the own team's PK as the first element."""
    loader = _make_loader(db)
    summary = _make_summary()
    own_id, opp_id = loader._resolve_team_ids(summary, opp_key=None, opponent_name="Opponent")
    expected_own = db.execute(
        "SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_GC_UUID,)
    ).fetchone()[0]
    assert own_id == expected_own


def test_resolve_team_ids_returns_none_when_no_opp_identifier(db: sqlite3.Connection) -> None:
    """When neither opponent_id nor opp_key is available, opp_team_id is None."""
    loader = _make_loader(db)
    summary = _make_summary(opponent_id=None)
    own_id, opp_id = loader._resolve_team_ids(summary, opp_key=None)
    assert opp_id is None


# ---------------------------------------------------------------------------
# AC-2 / AC-3: _record_uuid_from_boxscore removed
# ---------------------------------------------------------------------------


def test_scouting_loader_has_no_record_uuid_method() -> None:
    """AC-2: ScoutingLoader no longer has _record_uuid_from_boxscore."""
    from src.gamechanger.loaders.scouting_loader import ScoutingLoader
    assert not hasattr(ScoutingLoader, "_record_uuid_from_boxscore"), (
        "_record_uuid_from_boxscore must be removed from ScoutingLoader"
    )


def test_scouting_crawler_has_no_record_uuid_method() -> None:
    """AC-3: ScoutingCrawler no longer has _record_uuid_from_boxscore."""
    from src.gamechanger.crawlers.scouting import ScoutingCrawler
    assert not hasattr(ScoutingCrawler, "_record_uuid_from_boxscore"), (
        "_record_uuid_from_boxscore must be removed from ScoutingCrawler"
    )


def test_scouting_loader_no_uuid_re_constant() -> None:
    """AC-2: scouting_loader module no longer has _UUID_RE."""
    import src.gamechanger.loaders.scouting_loader as mod
    assert not hasattr(mod, "_UUID_RE"), (
        "_UUID_RE must be removed from scouting_loader"
    )


def test_scouting_crawler_no_uuid_re_constant() -> None:
    """AC-3: scouting crawler module no longer has _UUID_RE."""
    import src.gamechanger.crawlers.scouting as mod
    assert not hasattr(mod, "_UUID_RE"), (
        "_UUID_RE must be removed from scouting crawler"
    )
