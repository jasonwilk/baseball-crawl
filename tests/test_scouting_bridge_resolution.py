# synthetic-test-data
"""Tests for bridge resolution pre-step in ScoutingCrawler -- E-150-02 AC-6.

AC-6 requires tests for:
  (a) Successful resolution updates both teams.public_id and
      opponent_links.public_id (plus resolved_at and resolution_method).
  (b) BridgeForbiddenError (403) is handled gracefully -- opponent skipped,
      scouting continues.
  (c) CredentialExpiredError aborts bridge step but not scouting.
  (d) No-op case produces no API calls when no candidates exist.
  (e) UNIQUE constraint collision skips the update with a WARNING log
      that includes gc_uuid, resolved public_id, and conflicting teams.id,
      and does not modify either table for that opponent.

Run with:
    pytest tests/test_scouting_bridge_resolution.py -v
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from migrations.apply_migrations import run_migrations
from src.gamechanger.bridge import BridgeForbiddenError
from src.gamechanger.client import ConfigurationError, CredentialExpiredError
from src.gamechanger.crawlers.scouting import ScoutingCrawler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    """Apply all migrations and return an open connection."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@pytest.fixture()
def mock_client() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def crawler(mock_client: MagicMock, db: sqlite3.Connection, tmp_path: Path) -> ScoutingCrawler:
    return ScoutingCrawler(mock_client, db, freshness_hours=24, data_root=tmp_path / "raw")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _insert_member_team(db: sqlite3.Connection, name: str = "LSB Varsity") -> int:
    cursor = db.execute(
        "INSERT INTO teams (name, membership_type) VALUES (?, 'member')", (name,)
    )
    db.commit()
    return cursor.lastrowid


def _insert_tracked_team(
    db: sqlite3.Connection,
    name: str,
    gc_uuid: str | None = None,
    public_id: str | None = None,
) -> int:
    cursor = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, public_id) VALUES (?, 'tracked', ?, ?)",
        (name, gc_uuid, public_id),
    )
    db.commit()
    return cursor.lastrowid


def _insert_opponent_link(
    db: sqlite3.Connection,
    our_team_id: int,
    resolved_team_id: int,
    root_team_id: str = "root-001",
    opponent_name: str = "Opponent",
    public_id: str | None = None,
) -> int:
    cursor = db.execute(
        """
        INSERT INTO opponent_links
            (our_team_id, root_team_id, opponent_name, resolved_team_id, public_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (our_team_id, root_team_id, opponent_name, resolved_team_id, public_id),
    )
    db.commit()
    return cursor.lastrowid


def _get_team(db: sqlite3.Connection, team_id: int) -> dict:
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
    db.row_factory = None
    return dict(row) if row else {}


def _get_opponent_link(db: sqlite3.Connection, link_id: int) -> dict:
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT * FROM opponent_links WHERE id = ?", (link_id,)).fetchone()
    db.row_factory = None
    return dict(row) if row else {}


# ---------------------------------------------------------------------------
# AC-6(a): Successful resolution updates both tables
# ---------------------------------------------------------------------------


class TestSuccessfulResolution:
    """AC-6(a): Bridge success updates teams.public_id and opponent_links."""

    def test_updates_teams_public_id(
        self, crawler: ScoutingCrawler, db: sqlite3.Connection
    ) -> None:
        """teams.public_id is set after successful bridge resolution."""
        member_id = _insert_member_team(db)
        tracked_id = _insert_tracked_team(db, "River Hawks", gc_uuid="uuid-river-001")
        link_id = _insert_opponent_link(
            db, member_id, tracked_id, root_team_id="root-r1", opponent_name="River Hawks"
        )

        with patch(
            "src.gamechanger.crawlers.scouting.resolve_uuid_to_public_id",
            return_value="river-hawks-pub",
        ):
            crawler.resolve_missing_public_ids()

        team = _get_team(db, tracked_id)
        assert team["public_id"] == "river-hawks-pub"

    def test_updates_opponent_links_public_id(
        self, crawler: ScoutingCrawler, db: sqlite3.Connection
    ) -> None:
        """opponent_links.public_id is set after successful bridge resolution."""
        member_id = _insert_member_team(db)
        tracked_id = _insert_tracked_team(db, "River Hawks", gc_uuid="uuid-river-001")
        link_id = _insert_opponent_link(
            db, member_id, tracked_id, root_team_id="root-r1", opponent_name="River Hawks"
        )

        with patch(
            "src.gamechanger.crawlers.scouting.resolve_uuid_to_public_id",
            return_value="river-hawks-pub",
        ):
            crawler.resolve_missing_public_ids()

        link = _get_opponent_link(db, link_id)
        assert link["public_id"] == "river-hawks-pub"

    def test_updates_resolved_at_and_resolution_method(
        self, crawler: ScoutingCrawler, db: sqlite3.Connection
    ) -> None:
        """resolved_at and resolution_method='bridge' are set on opponent_links."""
        member_id = _insert_member_team(db)
        tracked_id = _insert_tracked_team(db, "Summit Wolves", gc_uuid="uuid-summit-001")
        link_id = _insert_opponent_link(
            db, member_id, tracked_id, root_team_id="root-s1", opponent_name="Summit"
        )

        with patch(
            "src.gamechanger.crawlers.scouting.resolve_uuid_to_public_id",
            return_value="summit-wolves-pub",
        ):
            crawler.resolve_missing_public_ids()

        link = _get_opponent_link(db, link_id)
        assert link["resolution_method"] == "bridge"
        assert link["resolved_at"] is not None

    def test_updates_all_links_for_same_resolved_team(
        self, crawler: ScoutingCrawler, db: sqlite3.Connection
    ) -> None:
        """All opponent_links rows for the same resolved_team_id are updated."""
        member1_id = _insert_member_team(db, "LSB Varsity")
        member2_id = _insert_member_team(db, "LSB JV")
        tracked_id = _insert_tracked_team(db, "Eagles", gc_uuid="uuid-eagles-001")
        link1_id = _insert_opponent_link(
            db, member1_id, tracked_id, root_team_id="root-e1", opponent_name="Eagles"
        )
        link2_id = _insert_opponent_link(
            db, member2_id, tracked_id, root_team_id="root-e2", opponent_name="Eagles"
        )

        with patch(
            "src.gamechanger.crawlers.scouting.resolve_uuid_to_public_id",
            return_value="eagles-pub",
        ) as mock_bridge:
            crawler.resolve_missing_public_ids()

        # Bridge called only once for distinct resolved_team_id
        mock_bridge.assert_called_once_with("uuid-eagles-001")

        link1 = _get_opponent_link(db, link1_id)
        link2 = _get_opponent_link(db, link2_id)
        assert link1["public_id"] == "eagles-pub"
        assert link2["public_id"] == "eagles-pub"


# ---------------------------------------------------------------------------
# AC-6(b): 403 / BridgeForbiddenError handled gracefully
# ---------------------------------------------------------------------------


class TestBridgeForbiddenError:
    """AC-6(b): 403 is handled per-opponent; scouting continues."""

    def test_forbidden_skips_opponent_no_db_update(
        self, crawler: ScoutingCrawler, db: sqlite3.Connection
    ) -> None:
        """BridgeForbiddenError leaves both tables unchanged."""
        member_id = _insert_member_team(db)
        tracked_id = _insert_tracked_team(db, "Forbidden Team", gc_uuid="uuid-forbidden-001")
        link_id = _insert_opponent_link(
            db, member_id, tracked_id, root_team_id="root-f1", opponent_name="Forbidden"
        )

        with patch(
            "src.gamechanger.crawlers.scouting.resolve_uuid_to_public_id",
            side_effect=BridgeForbiddenError("403"),
        ):
            crawler.resolve_missing_public_ids()

        team = _get_team(db, tracked_id)
        link = _get_opponent_link(db, link_id)
        assert team["public_id"] is None
        assert link["public_id"] is None

    def test_forbidden_logs_warning_with_gc_uuid_and_name(
        self, crawler: ScoutingCrawler, db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
    ) -> None:
        """WARNING is logged with gc_uuid and team name on BridgeForbiddenError."""
        member_id = _insert_member_team(db)
        tracked_id = _insert_tracked_team(db, "Forbidden FC", gc_uuid="uuid-forbidden-fc")
        _insert_opponent_link(
            db, member_id, tracked_id, root_team_id="root-fc", opponent_name="Forbidden FC"
        )

        with patch(
            "src.gamechanger.crawlers.scouting.resolve_uuid_to_public_id",
            side_effect=BridgeForbiddenError("403"),
        ):
            with caplog.at_level(logging.WARNING, logger="src.gamechanger.crawlers.scouting"):
                crawler.resolve_missing_public_ids()

        assert any(
            "uuid-forbidden-fc" in r.message and "Forbidden FC" in r.message
            for r in caplog.records
            if r.levelno == logging.WARNING
        )

    def test_forbidden_continues_to_next_opponent(
        self, crawler: ScoutingCrawler, db: sqlite3.Connection
    ) -> None:
        """After a 403 on one opponent, the next opponent is still attempted."""
        member_id = _insert_member_team(db)
        forbidden_id = _insert_tracked_team(db, "Forbidden", gc_uuid="uuid-forbidden")
        ok_id = _insert_tracked_team(db, "OK Team", gc_uuid="uuid-ok")
        _insert_opponent_link(
            db, member_id, forbidden_id, root_team_id="root-f", opponent_name="Forbidden"
        )
        ok_link_id = _insert_opponent_link(
            db, member_id, ok_id, root_team_id="root-ok", opponent_name="OK Team"
        )

        def side_effect(gc_uuid: str) -> str:
            if gc_uuid == "uuid-forbidden":
                raise BridgeForbiddenError("403")
            return "ok-team-pub"

        with patch(
            "src.gamechanger.crawlers.scouting.resolve_uuid_to_public_id",
            side_effect=side_effect,
        ):
            crawler.resolve_missing_public_ids()

        ok_link = _get_opponent_link(db, ok_link_id)
        assert ok_link["public_id"] == "ok-team-pub"


# ---------------------------------------------------------------------------
# AC-6(c): CredentialExpiredError aborts bridge step
# ---------------------------------------------------------------------------


class TestCredentialError:
    """AC-6(c): CredentialExpiredError/ConfigurationError aborts bridge step."""

    def test_credential_expired_aborts_bridge_step(
        self, crawler: ScoutingCrawler, db: sqlite3.Connection
    ) -> None:
        """CredentialExpiredError stops bridge resolution but leaves DB unchanged."""
        member_id = _insert_member_team(db)
        team_id = _insert_tracked_team(db, "Cred Team", gc_uuid="uuid-cred")
        link_id = _insert_opponent_link(
            db, member_id, team_id, root_team_id="root-cred", opponent_name="Cred Team"
        )

        with patch(
            "src.gamechanger.crawlers.scouting.resolve_uuid_to_public_id",
            side_effect=CredentialExpiredError("expired"),
        ):
            crawler.resolve_missing_public_ids()

        team = _get_team(db, team_id)
        link = _get_opponent_link(db, link_id)
        assert team["public_id"] is None
        assert link["public_id"] is None

    def test_configuration_error_aborts_bridge_step(
        self, crawler: ScoutingCrawler, db: sqlite3.Connection
    ) -> None:
        """ConfigurationError stops bridge resolution but leaves DB unchanged."""
        member_id = _insert_member_team(db)
        team_id = _insert_tracked_team(db, "Cfg Team", gc_uuid="uuid-cfg")
        link_id = _insert_opponent_link(
            db, member_id, team_id, root_team_id="root-cfg", opponent_name="Cfg Team"
        )

        with patch(
            "src.gamechanger.crawlers.scouting.resolve_uuid_to_public_id",
            side_effect=ConfigurationError("no creds"),
        ):
            crawler.resolve_missing_public_ids()

        link = _get_opponent_link(db, link_id)
        assert link["public_id"] is None

    def test_credential_error_does_not_abort_scouting(
        self, crawler: ScoutingCrawler, db: sqlite3.Connection
    ) -> None:
        """CredentialExpiredError from bridge does NOT propagate -- resolve_missing_public_ids returns normally."""
        member_id = _insert_member_team(db)
        team_id = _insert_tracked_team(db, "Cred Team 2", gc_uuid="uuid-cred2")
        _insert_opponent_link(
            db, member_id, team_id, root_team_id="root-cred2", opponent_name="Cred Team 2"
        )

        with patch(
            "src.gamechanger.crawlers.scouting.resolve_uuid_to_public_id",
            side_effect=CredentialExpiredError("expired"),
        ):
            # Should not raise -- bridge step is aborted, not re-raised
            crawler.resolve_missing_public_ids()

    def test_credential_error_stops_remaining_candidates(
        self, crawler: ScoutingCrawler, db: sqlite3.Connection
    ) -> None:
        """After CredentialExpiredError, remaining candidates are not attempted."""
        member_id = _insert_member_team(db)
        team1_id = _insert_tracked_team(db, "Team 1", gc_uuid="uuid-t1")
        team2_id = _insert_tracked_team(db, "Team 2", gc_uuid="uuid-t2")
        _insert_opponent_link(
            db, member_id, team1_id, root_team_id="root-t1", opponent_name="Team 1"
        )
        _insert_opponent_link(
            db, member_id, team2_id, root_team_id="root-t2", opponent_name="Team 2"
        )

        call_count = 0

        def side_effect(gc_uuid: str) -> str:
            nonlocal call_count
            call_count += 1
            raise CredentialExpiredError("expired")

        with patch(
            "src.gamechanger.crawlers.scouting.resolve_uuid_to_public_id",
            side_effect=side_effect,
        ):
            crawler.resolve_missing_public_ids()

        # Only one call was made before abort
        assert call_count == 1


# ---------------------------------------------------------------------------
# AC-6(d): No-op case produces no API calls
# ---------------------------------------------------------------------------


class TestNoOpCase:
    """AC-6(d): No API calls when no candidates exist."""

    def test_no_candidates_no_bridge_call(
        self, crawler: ScoutingCrawler, db: sqlite3.Connection
    ) -> None:
        """When no opponents need resolution, resolve_uuid_to_public_id is never called."""
        # DB has no opponent_links rows at all
        with patch(
            "src.gamechanger.crawlers.scouting.resolve_uuid_to_public_id"
        ) as mock_bridge:
            crawler.resolve_missing_public_ids()

        mock_bridge.assert_not_called()

    def test_opponent_with_public_id_already_set_is_skipped(
        self, crawler: ScoutingCrawler, db: sqlite3.Connection
    ) -> None:
        """Opponents that already have public_id in opponent_links are not re-resolved."""
        member_id = _insert_member_team(db)
        tracked_id = _insert_tracked_team(db, "Already Done", gc_uuid="uuid-done")
        _insert_opponent_link(
            db,
            member_id,
            tracked_id,
            root_team_id="root-done",
            opponent_name="Already Done",
            public_id="already-pub",  # already populated
        )

        with patch(
            "src.gamechanger.crawlers.scouting.resolve_uuid_to_public_id"
        ) as mock_bridge:
            crawler.resolve_missing_public_ids()

        mock_bridge.assert_not_called()

    def test_opponent_without_gc_uuid_is_skipped(
        self, crawler: ScoutingCrawler, db: sqlite3.Connection
    ) -> None:
        """Opponents with no gc_uuid (gc_uuid IS NULL) are not candidates."""
        member_id = _insert_member_team(db)
        tracked_id = _insert_tracked_team(db, "No UUID Team", gc_uuid=None)
        _insert_opponent_link(
            db, member_id, tracked_id, root_team_id="root-nouuid", opponent_name="No UUID"
        )

        with patch(
            "src.gamechanger.crawlers.scouting.resolve_uuid_to_public_id"
        ) as mock_bridge:
            crawler.resolve_missing_public_ids()

        mock_bridge.assert_not_called()


# ---------------------------------------------------------------------------
# AC-6(e): UNIQUE constraint collision
# ---------------------------------------------------------------------------


class TestUniqueConstraintCollision:
    """AC-6(e): Collision on teams.public_id skips both table updates."""

    def test_collision_skips_both_table_updates(
        self, crawler: ScoutingCrawler, db: sqlite3.Connection
    ) -> None:
        """If resolved public_id is already on a different teams row, nothing is updated."""
        member_id = _insert_member_team(db)
        # Existing team that already owns the public_id
        existing_id = _insert_tracked_team(
            db, "Existing Owner", gc_uuid=None, public_id="disputed-pub"
        )
        # Candidate team with gc_uuid but no public_id
        candidate_id = _insert_tracked_team(db, "Candidate", gc_uuid="uuid-candidate")
        link_id = _insert_opponent_link(
            db, member_id, candidate_id, root_team_id="root-cand", opponent_name="Candidate"
        )

        with patch(
            "src.gamechanger.crawlers.scouting.resolve_uuid_to_public_id",
            return_value="disputed-pub",
        ):
            crawler.resolve_missing_public_ids()

        # teams row for candidate is unchanged
        candidate = _get_team(db, candidate_id)
        assert candidate["public_id"] is None
        # opponent_link is unchanged
        link = _get_opponent_link(db, link_id)
        assert link["public_id"] is None

    def test_collision_logs_warning_with_required_context(
        self,
        crawler: ScoutingCrawler,
        db: sqlite3.Connection,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """WARNING log includes gc_uuid, resolved public_id, and conflicting teams.id."""
        member_id = _insert_member_team(db)
        existing_id = _insert_tracked_team(
            db, "Existing Owner", gc_uuid=None, public_id="disputed-pub"
        )
        candidate_id = _insert_tracked_team(db, "Candidate", gc_uuid="uuid-collision-test")
        _insert_opponent_link(
            db, member_id, candidate_id, root_team_id="root-col", opponent_name="Candidate"
        )

        with patch(
            "src.gamechanger.crawlers.scouting.resolve_uuid_to_public_id",
            return_value="disputed-pub",
        ):
            with caplog.at_level(logging.WARNING, logger="src.gamechanger.crawlers.scouting"):
                crawler.resolve_missing_public_ids()

        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            "uuid-collision-test" in msg
            and "disputed-pub" in msg
            and str(existing_id) in msg
            for msg in warning_messages
        )

    def test_collision_continues_to_next_candidate(
        self, crawler: ScoutingCrawler, db: sqlite3.Connection
    ) -> None:
        """After a collision on one candidate, the next candidate is still processed."""
        member_id = _insert_member_team(db)
        existing_id = _insert_tracked_team(
            db, "Existing Owner", gc_uuid=None, public_id="disputed-pub"
        )
        collision_id = _insert_tracked_team(db, "Collision Cand", gc_uuid="uuid-collision")
        ok_id = _insert_tracked_team(db, "OK Candidate", gc_uuid="uuid-ok-cand")
        _insert_opponent_link(
            db, member_id, collision_id, root_team_id="root-col2", opponent_name="Collision"
        )
        ok_link_id = _insert_opponent_link(
            db, member_id, ok_id, root_team_id="root-ok2", opponent_name="OK"
        )

        def side_effect(gc_uuid: str) -> str:
            if gc_uuid == "uuid-collision":
                return "disputed-pub"
            return "ok-pub"

        with patch(
            "src.gamechanger.crawlers.scouting.resolve_uuid_to_public_id",
            side_effect=side_effect,
        ):
            crawler.resolve_missing_public_ids()

        ok_link = _get_opponent_link(db, ok_link_id)
        assert ok_link["public_id"] == "ok-pub"
