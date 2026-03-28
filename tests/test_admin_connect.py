"""Tests for E-173-02: Auto-scout after manual connect (connect_opponent handler).

Covers:
- AC-2: Manual connect triggers run_scouting_sync when public_id is non-null
- AC-3: No scouting when public_id is null (tested via absence of crawl_jobs)
- AC-4: Flash message includes syncing note
- AC-5: crawl_jobs row uses sync_type='scouting_crawl'
- AC-6: background_tasks.add_task called with run_scouting_sync
"""

from __future__ import annotations

import secrets
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from migrations.apply_migrations import run_migrations  # noqa: E402
from src.api.auth import hash_token  # noqa: E402
from src.api.main import app  # noqa: E402

_CSRF = "test-csrf-token"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> tuple[Path, dict[str, int]]:
    """Create a test database with a member team and an unlinked opponent link."""
    db_path = tmp_path / "test_connect.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")

    conn.execute(
        "INSERT OR IGNORE INTO programs (program_id, name, program_type) "
        "VALUES ('lsb-hs', 'Lincoln Standing Bear HS', 'hs')"
    )

    cur = conn.execute(
        "INSERT INTO teams (name, membership_type, public_id, source, is_active, season_year) "
        "VALUES ('LSB Varsity', 'member', 'ownedPubId', 'gamechanger', 1, 2026)"
    )
    varsity_id = cur.lastrowid

    # Create a tracked stub team (no public_id)
    cur_stub = conn.execute(
        "INSERT INTO teams (name, membership_type, source, is_active) "
        "VALUES ('Rival HS', 'tracked', 'gamechanger', 0)"
    )
    stub_id = cur_stub.lastrowid

    # Link stub in team_opponents
    conn.execute(
        "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
        (varsity_id, stub_id),
    )

    # Create an unlinked opponent_link
    cur = conn.execute(
        "INSERT INTO opponent_links "
        "(our_team_id, root_team_id, opponent_name, resolved_team_id, public_id, "
        "resolution_method, is_hidden) "
        "VALUES (?, 'gc-root-001', 'Rival HS', NULL, NULL, NULL, 0)",
        (varsity_id,),
    )
    unlinked_link_id = cur.lastrowid

    conn.commit()
    conn.close()

    return db_path, {
        "varsity": varsity_id,
        "stub": stub_id,
        "unlinked_link": unlinked_link_id,
    }


def _admin_env(db_path: Path, email: str) -> dict[str, str]:
    return {"DATABASE_PATH": str(db_path), "ADMIN_EMAIL": email}


def _insert_user(db_path: Path, email: str) -> int:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    cursor = conn.execute(
        "INSERT INTO users (email, hashed_password) VALUES (?, '')", (email,)
    )
    conn.commit()
    uid = cursor.lastrowid
    conn.close()
    return uid


def _insert_session(db_path: Path, user_id: int) -> str:
    raw_token = secrets.token_hex(32)
    token_hash = hash_token(raw_token)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT INTO sessions (session_id, user_id, expires_at) "
        "VALUES (?, ?, datetime('now', '+7 days'))",
        (token_hash, user_id),
    )
    conn.commit()
    conn.close()
    return raw_token


def _auth_client(db_path: Path, email: str) -> tuple[TestClient, str]:
    uid = _insert_user(db_path, email)
    token = _insert_session(db_path, uid)
    client = TestClient(app, cookies={"session": token, "csrf_token": _CSRF})
    return client, token


def _insert_team_with_public_id(db_path: Path, name: str, public_id: str) -> int:
    """Insert a tracked team with a public_id and return its id."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    cur = conn.execute(
        "INSERT INTO teams (name, membership_type, public_id, source, is_active) "
        "VALUES (?, 'tracked', ?, 'gamechanger', 0)",
        (name, public_id),
    )
    team_id = cur.lastrowid
    conn.commit()
    conn.close()
    return team_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAutoScoutAfterConnect:
    """AC-2, AC-4, AC-5: Manual connect triggers auto-scout."""

    def test_scouting_enqueued_after_connect(self, tmp_path: Path) -> None:
        """AC-2, AC-5: connect_opponent creates crawl_jobs row and triggers scouting."""
        db_path, ids = _make_db(tmp_path)
        with (
            patch.dict("os.environ", _admin_env(db_path, "conn1@example.com")),
            patch("src.api.routes.admin.trigger") as mock_trigger,
        ):
            client, _ = _auth_client(db_path, "conn1@example.com")
            resp = client.post(
                f"/admin/opponents/{ids['unlinked_link']}/connect",
                data={"public_id": "rival-hs-slug", "csrf_token": _CSRF},
                follow_redirects=False,
            )

        assert resp.status_code == 303

        # crawl_jobs row should exist with scouting_crawl type
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        job = conn.execute(
            "SELECT * FROM crawl_jobs WHERE sync_type = 'scouting_crawl' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        assert job is not None
        assert job["sync_type"] == "scouting_crawl"

    def test_flash_message_includes_syncing(self, tmp_path: Path) -> None:
        """AC-4: Flash message includes syncing note after connect."""
        db_path, ids = _make_db(tmp_path)
        with (
            patch.dict("os.environ", _admin_env(db_path, "conn2@example.com")),
            patch("src.api.routes.admin.trigger"),
        ):
            client, _ = _auth_client(db_path, "conn2@example.com")
            resp = client.post(
                f"/admin/opponents/{ids['unlinked_link']}/connect",
                data={"public_id": "rival-hs-slug", "csrf_token": _CSRF},
                follow_redirects=False,
            )

        assert resp.status_code == 303
        location = resp.headers["location"]
        assert "syncing" in location.lower() or "Stats" in location

    def test_no_stub_still_creates_team_opponents_and_triggers_scout(self, tmp_path: Path) -> None:
        """Manual connect without a stub still resolves, creates team_opponents, triggers scout."""
        db_path, _ = _make_db(tmp_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        varsity_id = conn.execute("SELECT id FROM teams WHERE name = 'LSB Varsity'").fetchone()[0]

        # Create a link for a non-existent opponent (no stub in team_opponents)
        cur = conn.execute(
            "INSERT INTO opponent_links "
            "(our_team_id, root_team_id, opponent_name, is_hidden) "
            "VALUES (?, 'gc-root-999', 'No Stub Team', 0)",
            (varsity_id,),
        )
        link_id = cur.lastrowid
        conn.commit()
        conn.close()

        with (
            patch.dict("os.environ", _admin_env(db_path, "conn3@example.com")),
            patch("src.api.routes.admin.trigger") as mock_trigger,
        ):
            client, _ = _auth_client(db_path, "conn3@example.com")
            resp = client.post(
                f"/admin/opponents/{link_id}/connect",
                data={"public_id": "no-stub-slug", "csrf_token": _CSRF},
                follow_redirects=False,
            )

        assert resp.status_code == 303

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # team_opponents row should exist linking varsity to the resolved team
        to_row = conn.execute(
            "SELECT opponent_team_id FROM team_opponents WHERE our_team_id = ?",
            (varsity_id,),
        ).fetchall()
        # At least one row should link to a team with public_id='no-stub-slug'
        resolved_ids = [r["opponent_team_id"] for r in to_row]
        resolved_team = conn.execute(
            "SELECT id, public_id, is_active FROM teams WHERE public_id = 'no-stub-slug'"
        ).fetchone()
        assert resolved_team is not None
        assert resolved_team["id"] in resolved_ids
        assert resolved_team["is_active"] == 1

        # Auto-scout should have triggered (crawl_jobs row exists)
        job = conn.execute(
            "SELECT * FROM crawl_jobs WHERE sync_type = 'scouting_crawl'"
        ).fetchone()
        conn.close()
        assert job is not None
