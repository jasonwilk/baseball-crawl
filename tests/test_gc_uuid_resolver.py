"""Tests for src.gamechanger.resolvers.gc_uuid_resolver."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.gamechanger.exceptions import CredentialExpiredError
from src.gamechanger.resolvers.gc_uuid_resolver import (
    _strip_classification_suffix,
    resolve_gc_uuid,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory database with minimal schema for resolver tests."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = OFF;")  # Simplify test setup
    conn.executescript("""
        CREATE TABLE teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            membership_type TEXT NOT NULL DEFAULT 'tracked',
            gc_uuid TEXT,
            public_id TEXT,
            season_year INTEGER,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE games (
            game_id TEXT PRIMARY KEY,
            season_id TEXT NOT NULL DEFAULT 'test-season',
            game_date TEXT NOT NULL DEFAULT '2026-04-01',
            home_team_id INTEGER NOT NULL,
            away_team_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'final'
        );
    """)
    return conn


@pytest.fixture()
def data_root(tmp_path: Path) -> Path:
    """Return a temporary data/raw directory."""
    raw = tmp_path / "raw"
    raw.mkdir()
    return raw


def _seed_member_team(db: sqlite3.Connection, gc_uuid: str = "member-uuid-1234") -> int:
    """Insert a member team and return its id."""
    cur = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid) "
        "VALUES ('Member Team', 'member', ?)",
        (gc_uuid,),
    )
    db.commit()
    return cur.lastrowid  # type: ignore[return-value]


def _seed_tracked_team(
    db: sqlite3.Connection,
    name: str = "Opponent Varsity",
    public_id: str = "opponent-slug",
    gc_uuid: str | None = None,
    season_year: int | None = 2026,
) -> int:
    """Insert a tracked team and return its id."""
    cur = db.execute(
        "INSERT INTO teams (name, membership_type, public_id, gc_uuid, season_year) "
        "VALUES (?, 'tracked', ?, ?, ?)",
        (name, public_id, gc_uuid, season_year),
    )
    db.commit()
    return cur.lastrowid  # type: ignore[return-value]


def _write_boxscore(
    data_root: Path,
    member_gc_uuid: str,
    event_id: str,
    opponent_uuid: str,
    season: str = "2026",
) -> None:
    """Write a boxscore JSON file with two top-level UUID keys."""
    boxscore_dir = data_root / season / "teams" / member_gc_uuid / "boxscores"
    boxscore_dir.mkdir(parents=True, exist_ok=True)
    boxscore_data = {
        member_gc_uuid: {"stats": "member_data"},
        opponent_uuid: {"stats": "opponent_data"},
    }
    (boxscore_dir / f"{event_id}.json").write_text(json.dumps(boxscore_data))


def _write_opponents_json(
    data_root: Path,
    member_gc_uuid: str,
    entries: list[dict],
    season: str = "2026",
) -> None:
    """Write an opponents.json file for a member team."""
    opp_dir = data_root / season / "teams" / member_gc_uuid
    opp_dir.mkdir(parents=True, exist_ok=True)
    (opp_dir / "opponents.json").write_text(json.dumps(entries))


# ---------------------------------------------------------------------------
# Tier 1 tests
# ---------------------------------------------------------------------------

class TestTier1BoxscoreExtraction:
    """AC-8a: Tier 1 success path."""

    def test_resolves_uuid_from_member_boxscore(
        self, db: sqlite3.Connection, data_root: Path
    ) -> None:
        """Tier 1 finds opponent UUID in member boxscore and verifies via games table."""
        member_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        opponent_uuid = "11111111-2222-3333-4444-555555555555"
        event_id = "game-event-001"

        _seed_member_team(db, gc_uuid=member_uuid)
        tracked_id = _seed_tracked_team(db, name="Rival Team", public_id="rival-slug")

        # Create game row linking event to tracked team.
        db.execute(
            "INSERT INTO games (game_id, home_team_id, away_team_id) VALUES (?, ?, ?)",
            (event_id, tracked_id, 999),
        )
        db.commit()

        # Write boxscore file.
        _write_boxscore(data_root, member_uuid, event_id, opponent_uuid)

        result = resolve_gc_uuid(
            team_id=tracked_id,
            public_id="rival-slug",
            team_name="Rival Team",
            season_year=2026,
            conn=db,
            data_root=data_root,
        )

        assert result == opponent_uuid
        # Verify stored on team row.
        stored = db.execute(
            "SELECT gc_uuid FROM teams WHERE id = ?", (tracked_id,)
        ).fetchone()
        assert stored[0] == opponent_uuid

    def test_tier1_skips_when_no_game_match(
        self, db: sqlite3.Connection, data_root: Path
    ) -> None:
        """Tier 1 does not resolve when the game doesn't involve the target team."""
        member_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        opponent_uuid = "11111111-2222-3333-4444-555555555555"
        event_id = "game-event-002"

        _seed_member_team(db, gc_uuid=member_uuid)
        tracked_id = _seed_tracked_team(db)

        # Game does NOT involve tracked_id.
        db.execute(
            "INSERT INTO games (game_id, home_team_id, away_team_id) VALUES (?, ?, ?)",
            (event_id, 888, 999),
        )
        db.commit()

        _write_boxscore(data_root, member_uuid, event_id, opponent_uuid)

        result = resolve_gc_uuid(
            team_id=tracked_id,
            public_id="opponent-slug",
            team_name="Opponent Varsity",
            season_year=2026,
            conn=db,
            data_root=data_root,
        )
        assert result is None


# ---------------------------------------------------------------------------
# Tier 2 tests
# ---------------------------------------------------------------------------

class TestTier2Progenitor:
    """AC-8b: Tier 2 success path."""

    def test_resolves_via_progenitor_team_id(
        self, db: sqlite3.Connection, data_root: Path
    ) -> None:
        """Tier 2 finds progenitor_team_id by name match in opponents.json."""
        member_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        progenitor = "ff00aa00-bb00-cc00-dd00-ee00ff000001"

        _seed_member_team(db, gc_uuid=member_uuid)
        tracked_id = _seed_tracked_team(db, name="Rival Varsity")

        _write_opponents_json(data_root, member_uuid, [
            {
                "name": "Rival Varsity",
                "root_team_id": "some-root-id",
                "owning_team_id": "some-owner",
                "is_hidden": False,
                "progenitor_team_id": progenitor,
            },
        ])

        result = resolve_gc_uuid(
            team_id=tracked_id,
            public_id="rival-slug",
            team_name="Rival Varsity",
            season_year=2026,
            conn=db,
            data_root=data_root,
        )

        assert result == progenitor
        stored = db.execute(
            "SELECT gc_uuid FROM teams WHERE id = ?", (tracked_id,)
        ).fetchone()
        assert stored[0] == progenitor

    def test_tier2_skips_null_progenitor(
        self, db: sqlite3.Connection, data_root: Path
    ) -> None:
        """Tier 2 skips entries with null progenitor_team_id."""
        member_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

        _seed_member_team(db, gc_uuid=member_uuid)
        tracked_id = _seed_tracked_team(db, name="Manual Entry Team")

        _write_opponents_json(data_root, member_uuid, [
            {
                "name": "Manual Entry Team",
                "root_team_id": "some-root",
                "owning_team_id": "some-owner",
                "is_hidden": False,
                "progenitor_team_id": None,
            },
        ])

        result = resolve_gc_uuid(
            team_id=tracked_id,
            public_id="manual-slug",
            team_name="Manual Entry Team",
            season_year=2026,
            conn=db,
            data_root=data_root,
        )
        assert result is None

    def test_tier2_case_insensitive_match(
        self, db: sqlite3.Connection, data_root: Path
    ) -> None:
        """Tier 2 name matching is case-insensitive."""
        member_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        progenitor = "ff00aa00-bb00-cc00-dd00-ee00ff000002"

        _seed_member_team(db, gc_uuid=member_uuid)
        tracked_id = _seed_tracked_team(db, name="RIVAL varsity")

        _write_opponents_json(data_root, member_uuid, [
            {
                "name": "Rival Varsity",
                "root_team_id": "r1",
                "owning_team_id": "o1",
                "is_hidden": False,
                "progenitor_team_id": progenitor,
            },
        ])

        result = resolve_gc_uuid(
            team_id=tracked_id,
            public_id="rival-slug",
            team_name="RIVAL varsity",
            season_year=2026,
            conn=db,
            data_root=data_root,
        )
        assert result == progenitor


# ---------------------------------------------------------------------------
# Tier 3 tests
# ---------------------------------------------------------------------------

class TestTier3Search:
    """AC-8c, AC-8f, AC-8g: Tier 3 paths."""

    def test_resolves_via_search_with_shortened_name(
        self, db: sqlite3.Connection, data_root: Path
    ) -> None:
        """AC-8c: Tier 3 strips suffix, calls search, returns gc_uuid."""
        tracked_id = _seed_tracked_team(
            db, name="Rival Varsity", season_year=2026,
        )

        mock_client = MagicMock()
        mock_client.post_json.return_value = {
            "hits": [
                {
                    "result": {
                        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "name": "Rival",
                        "public_id": "rival-pub",
                        "season": {"year": 2026},
                    }
                }
            ],
        }

        result = resolve_gc_uuid(
            team_id=tracked_id,
            public_id="rival-slug",
            team_name="Rival Varsity",
            season_year=2026,
            conn=db,
            data_root=data_root,
            client=mock_client,
        )

        assert result == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        # Verify the search was called with shortened name.
        call_args = mock_client.post_json.call_args
        assert call_args[1]["body"]["name"] == "Rival"

        stored = db.execute(
            "SELECT gc_uuid FROM teams WHERE id = ?", (tracked_id,)
        ).fetchone()
        assert stored[0] == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    def test_tier3_skipped_when_no_client(
        self, db: sqlite3.Connection, data_root: Path
    ) -> None:
        """AC-8f: Tier 3 is skipped when no client is provided."""
        tracked_id = _seed_tracked_team(db, name="No Client Team", season_year=2026)

        result = resolve_gc_uuid(
            team_id=tracked_id,
            public_id="nc-slug",
            team_name="No Client Team",
            season_year=2026,
            conn=db,
            data_root=data_root,
            client=None,
        )
        assert result is None

    def test_tier3_skipped_when_season_year_is_none(
        self, db: sqlite3.Connection, data_root: Path
    ) -> None:
        """AC-8g: Tier 3 is skipped when season_year is None."""
        tracked_id = _seed_tracked_team(db, name="No Year Team", season_year=None)

        mock_client = MagicMock()

        result = resolve_gc_uuid(
            team_id=tracked_id,
            public_id="ny-slug",
            team_name="No Year Team",
            season_year=None,
            conn=db,
            data_root=data_root,
            client=mock_client,
        )
        assert result is None
        # Verify search was NOT called.
        mock_client.post_json.assert_not_called()

    def test_tier3_rejects_ambiguous_results(
        self, db: sqlite3.Connection, data_root: Path
    ) -> None:
        """Tier 3 returns None when multiple matches exist."""
        tracked_id = _seed_tracked_team(db, name="Common Varsity", season_year=2026)

        mock_client = MagicMock()
        mock_client.post_json.return_value = {
            "hits": [
                {"result": {"id": "uuid-a", "name": "Common", "season": {"year": 2026}}},
                {"result": {"id": "uuid-b", "name": "Common", "season": {"year": 2026}}},
            ],
        }

        result = resolve_gc_uuid(
            team_id=tracked_id,
            public_id="common-slug",
            team_name="Common Varsity",
            season_year=2026,
            conn=db,
            data_root=data_root,
            client=mock_client,
        )
        assert result is None

    def test_tier3_rejects_non_uuid_search_result(
        self, db: sqlite3.Connection, data_root: Path
    ) -> None:
        """Tier 3 returns None when search result id is not a valid UUID."""
        tracked_id = _seed_tracked_team(db, name="Bad ID Team", season_year=2026)

        mock_client = MagicMock()
        mock_client.post_json.return_value = {
            "hits": [
                {"result": {"id": "not-a-uuid", "name": "Bad ID", "season": {"year": 2026}}},
            ],
        }

        result = resolve_gc_uuid(
            team_id=tracked_id,
            public_id="bad-id-slug",
            team_name="Bad ID Team",
            season_year=2026,
            conn=db,
            data_root=data_root,
            client=mock_client,
        )
        assert result is None
        # Verify gc_uuid was NOT stored
        row = db.execute(
            "SELECT gc_uuid FROM teams WHERE id = ?", (tracked_id,)
        ).fetchone()
        assert row[0] is None

    def test_tier3_propagates_credential_expired_error(
        self, db: sqlite3.Connection, data_root: Path
    ) -> None:
        """AC-7: CredentialExpiredError from tier 3 propagates to caller."""
        tracked_id = _seed_tracked_team(db, name="Auth Fail Team", season_year=2026)

        mock_client = MagicMock()
        mock_client.post_json.side_effect = CredentialExpiredError("expired")

        with pytest.raises(CredentialExpiredError):
            resolve_gc_uuid(
                team_id=tracked_id,
                public_id="af-slug",
                team_name="Auth Fail Team",
                season_year=2026,
                conn=db,
                data_root=data_root,
                client=mock_client,
            )


# ---------------------------------------------------------------------------
# Cross-tier tests
# ---------------------------------------------------------------------------

class TestCascadeBehavior:
    """AC-8d, AC-8e: Cross-tier behavior."""

    def test_all_tiers_fail_returns_none(
        self, db: sqlite3.Connection, data_root: Path
    ) -> None:
        """AC-8d: Returns None when all tiers fail."""
        tracked_id = _seed_tracked_team(db, name="Ghost Team", season_year=2026)

        mock_client = MagicMock()
        mock_client.post_json.return_value = {"hits": []}

        result = resolve_gc_uuid(
            team_id=tracked_id,
            public_id="ghost-slug",
            team_name="Ghost Team",
            season_year=2026,
            conn=db,
            data_root=data_root,
            client=mock_client,
        )
        assert result is None

    def test_existing_gc_uuid_never_overwritten(
        self, db: sqlite3.Connection, data_root: Path
    ) -> None:
        """AC-8e: If gc_uuid already exists, UPDATE is a no-op."""
        member_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        existing_uuid = "existing-0000-0000-0000-000000000000"
        new_uuid = "11111111-2222-3333-4444-555555555555"

        _seed_member_team(db, gc_uuid=member_uuid)
        # Create tracked team WITH existing gc_uuid.
        tracked_id = _seed_tracked_team(
            db, name="Already Resolved", gc_uuid=existing_uuid,
        )

        event_id = "game-existing"
        db.execute(
            "INSERT INTO games (game_id, home_team_id, away_team_id) VALUES (?, ?, ?)",
            (event_id, tracked_id, 999),
        )
        db.commit()

        _write_boxscore(data_root, member_uuid, event_id, new_uuid)

        # The resolver will find the UUID via tier 1 and try to store it,
        # but the conditional UPDATE should not overwrite.
        result = resolve_gc_uuid(
            team_id=tracked_id,
            public_id="ar-slug",
            team_name="Already Resolved",
            season_year=2026,
            conn=db,
            data_root=data_root,
        )
        # Tier 1 finds the new UUID...
        assert result == new_uuid
        # ...but the DB still has the original.
        stored = db.execute(
            "SELECT gc_uuid FROM teams WHERE id = ?", (tracked_id,)
        ).fetchone()
        assert stored[0] == existing_uuid

    def test_cascade_stops_at_first_success(
        self, db: sqlite3.Connection, data_root: Path
    ) -> None:
        """AC-6: Tier 2 is not attempted when tier 1 succeeds."""
        member_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        boxscore_uuid = "11111111-2222-3333-4444-555555555555"
        progenitor_uuid = "22222222-3333-4444-5555-666666666666"

        _seed_member_team(db, gc_uuid=member_uuid)
        tracked_id = _seed_tracked_team(db, name="Dual Match")

        event_id = "game-dual"
        db.execute(
            "INSERT INTO games (game_id, home_team_id, away_team_id) VALUES (?, ?, ?)",
            (event_id, 999, tracked_id),
        )
        db.commit()

        _write_boxscore(data_root, member_uuid, event_id, boxscore_uuid)
        _write_opponents_json(data_root, member_uuid, [
            {
                "name": "Dual Match",
                "root_team_id": "r1",
                "owning_team_id": "o1",
                "is_hidden": False,
                "progenitor_team_id": progenitor_uuid,
            },
        ])

        result = resolve_gc_uuid(
            team_id=tracked_id,
            public_id="dual-slug",
            team_name="Dual Match",
            season_year=2026,
            conn=db,
            data_root=data_root,
        )
        # Tier 1 UUID should win (not tier 2).
        assert result == boxscore_uuid


# ---------------------------------------------------------------------------
# Name stripping tests
# ---------------------------------------------------------------------------

class TestStripClassificationSuffix:
    """Classification suffix stripping for tier 3 search."""

    def test_strips_varsity(self) -> None:
        assert _strip_classification_suffix("Lincoln Varsity") == "Lincoln"

    def test_strips_jv(self) -> None:
        assert _strip_classification_suffix("Lincoln JV") == "Lincoln"

    def test_strips_reserve_freshman(self) -> None:
        assert _strip_classification_suffix("Lincoln Reserve/Freshman") == "Lincoln"

    def test_strips_freshman(self) -> None:
        assert _strip_classification_suffix("Lincoln Freshman") == "Lincoln"

    def test_strips_reserve(self) -> None:
        assert _strip_classification_suffix("Lincoln Reserve") == "Lincoln"

    def test_no_suffix_unchanged(self) -> None:
        assert _strip_classification_suffix("Lincoln") == "Lincoln"

    def test_strips_middle_suffix(self) -> None:
        """Handles 'Lincoln Northeast Reserve/Freshman Rockets'."""
        result = _strip_classification_suffix(
            "Lincoln Northeast Reserve/Freshman Rockets"
        )
        assert result == "Lincoln Northeast Rockets"


# ---------------------------------------------------------------------------
# CLI integration test (AC-10)
# ---------------------------------------------------------------------------

class TestScoutLiveResolverIntegration:
    """AC-10: _scout_live calls resolver at the correct pipeline stage."""

    def test_resolver_called_after_crawl_before_spray(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Verify _resolve_missing_gc_uuids is called between main crawl/load
        and spray crawl in _scout_live.
        """
        call_order: list[str] = []

        # Mock _run_scout_pipeline to succeed.
        def fake_run_scout_pipeline(*args, **kwargs):
            call_order.append("scout_pipeline")
            return 0

        # Mock _resolve_missing_gc_uuids to record call.
        def fake_resolve(conn, data_root, client, team_public_id=None):
            call_order.append("resolve_gc_uuids")

        # Mock ScoutingSprayChartCrawler.
        class FakeSprayCrawler:
            def __init__(self, *args, **kwargs):
                pass

            def crawl_all(self, **kwargs):
                call_order.append("spray_crawl")
                return MagicMock(files_written=0, files_skipped=0, errors=0)

            def crawl_team(self, *args, **kwargs):
                call_order.append("spray_crawl")
                return MagicMock(files_written=0, files_skipped=0, errors=0)

        # Mock ScoutingSprayChartLoader.
        class FakeSprayLoader:
            def __init__(self, *args, **kwargs):
                pass

            def load_all(self, *args, **kwargs):
                call_order.append("spray_load")
                return MagicMock(loaded=0, skipped=0, errors=0)

        # Mock GameChangerClient.
        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

        # Apply all mocks.
        import src.cli.data as data_mod

        monkeypatch.setattr(data_mod, "_run_scout_pipeline", fake_run_scout_pipeline)
        monkeypatch.setattr(data_mod, "_resolve_missing_gc_uuids", fake_resolve)
        monkeypatch.setattr(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            FakeSprayCrawler,
        )
        monkeypatch.setattr(
            "src.gamechanger.loaders.scouting_spray_loader.ScoutingSprayChartLoader",
            FakeSprayLoader,
        )
        monkeypatch.setattr(
            "src.gamechanger.client.GameChangerClient", FakeClient,
        )

        # Mock _resolve_db_path to use a temp db.
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.close()
        monkeypatch.setattr(data_mod, "_resolve_db_path", lambda: db_path)

        # Mock _heal_season_year_cli to no-op.
        monkeypatch.setattr(data_mod, "_heal_season_year_cli", lambda *a, **k: None)

        with pytest.raises(SystemExit) as exc_info:
            data_mod._scout_live(
                profile="test",
                team=None,
                season=None,
                force=False,
            )

        assert exc_info.value.code == 0
        # Verify ordering: scout_pipeline -> resolve_gc_uuids -> spray_crawl -> spray_load
        assert call_order == [
            "scout_pipeline",
            "resolve_gc_uuids",
            "spray_crawl",
            "spray_load",
        ]
