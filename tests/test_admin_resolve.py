"""Tests for E-167-04: Admin opponent resolution workflow.

Covers: suggestion page, confirm flow, skip flow, unhide flow,
duplicate detection, unresolved banner, hidden filter tab.
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
    db_path = tmp_path / "test_resolve.db"
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

    # Unresolved opponent link
    cur = conn.execute(
        "INSERT INTO opponent_links "
        "(our_team_id, root_team_id, opponent_name, resolved_team_id, public_id, "
        "resolution_method, is_hidden) "
        "VALUES (?, 'gc-root-001', 'Rival HS', NULL, NULL, NULL, 0)",
        (varsity_id,),
    )
    unresolved_link_id = cur.lastrowid

    # Resolved opponent link
    cur_opp = conn.execute(
        "INSERT INTO teams (name, membership_type, source, is_active) "
        "VALUES ('Resolved Opp', 'tracked', 'gamechanger', 0)"
    )
    opp_id = cur_opp.lastrowid
    conn.execute(
        "INSERT INTO opponent_links "
        "(our_team_id, root_team_id, opponent_name, resolved_team_id, public_id, "
        "resolution_method, is_hidden) "
        "VALUES (?, 'gc-root-002', 'Resolved Opp', ?, 'resolved-slug', 'auto', 0)",
        (varsity_id, opp_id),
    )

    # Hidden opponent link
    cur = conn.execute(
        "INSERT INTO opponent_links "
        "(our_team_id, root_team_id, opponent_name, resolved_team_id, public_id, "
        "resolution_method, is_hidden) "
        "VALUES (?, 'gc-root-003', 'Hidden Opp', NULL, NULL, NULL, 1)",
        (varsity_id,),
    )
    hidden_link_id = cur.lastrowid

    conn.commit()
    conn.close()

    return db_path, {
        "varsity": varsity_id,
        "opp": opp_id,
        "unresolved_link": unresolved_link_id,
        "hidden_link": hidden_link_id,
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
    """Create user + session, return (client, token). Use inside env patch."""
    uid = _insert_user(db_path, email)
    token = _insert_session(db_path, uid)
    client = TestClient(app, cookies={"session": token, "csrf_token": _CSRF})
    return client, token


def _get_link_row(db_path: Path, link_id: int) -> dict | None:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM opponent_links WHERE id = ?", (link_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

_MOCK_SEARCH_RESULTS = [
    {
        "name": "Rival HS Eagles",
        "gc_uuid": "uuid-rival-001",
        "public_id": "rival-eagles-slug",
        "city": "Lincoln",
        "state": "NE",
        "season_year": 2026,
        "season_name": "spring",
        "sport": "baseball",
        "num_players": 15,
        "staff": ["Coach Smith"],
    },
    {
        "name": "Rival HS Hawks",
        "gc_uuid": "uuid-rival-002",
        "public_id": "rival-hawks-slug",
        "city": "Omaha",
        "state": "NE",
        "season_year": 2026,
        "season_name": "spring",
        "sport": "baseball",
        "num_players": 12,
        "staff": [],
    },
]

from src.gamechanger.team_resolver import TeamProfile  # noqa: E402

_MOCK_PROFILE = TeamProfile(
    public_id="rival-eagles-slug",
    name="Rival HS Eagles",
    sport="baseball",
    city="Lincoln",
    state="NE",
    record_wins=10,
    record_losses=3,
    year=2026,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUnresolvedBanner:
    """AC-1: Unresolved banner and filter."""

    def test_banner_shown(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        with patch.dict("os.environ", _admin_env(db_path, "banner1@example.com")):
            client, _ = _auth_client(db_path, "banner1@example.com")
            resp = client.get("/admin/opponents")
        assert resp.status_code == 200
        assert "linking" in resp.text.lower()
        assert "Start linking" in resp.text

    def test_unresolved_count_in_filter_pill(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        with patch.dict("os.environ", _admin_env(db_path, "banner2@example.com")):
            client, _ = _auth_client(db_path, "banner2@example.com")
            resp = client.get("/admin/opponents")
        assert "Needs linking (1)" in resp.text

    def test_unresolved_filter(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        with patch.dict("os.environ", _admin_env(db_path, "banner3@example.com")):
            client, _ = _auth_client(db_path, "banner3@example.com")
            resp = client.get("/admin/opponents?filter=unresolved")
        assert "Rival HS" in resp.text
        assert "Resolved Opp" not in resp.text


class TestResolveButton:
    """AC-2: Unresolved rows show Resolve button."""

    def test_resolve_button_visible(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        with patch.dict("os.environ", _admin_env(db_path, "btn1@example.com")):
            client, _ = _auth_client(db_path, "btn1@example.com")
            resp = client.get("/admin/opponents?filter=unresolved")
        assert "/resolve" in resp.text
        assert "Find on GameChanger" in resp.text


class TestSuggestionPage:
    """AC-3, AC-4, AC-8, AC-12: Search suggestion page."""

    def test_search_results_displayed(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        with (
            patch.dict("os.environ", _admin_env(db_path, "search1@example.com")),
            patch("src.api.routes.admin._gc_search_teams", return_value=_MOCK_SEARCH_RESULTS),
        ):
            client, _ = _auth_client(db_path, "search1@example.com")
            resp = client.get(f"/admin/opponents/{ids['unresolved_link']}/resolve")
        assert resp.status_code == 200
        assert "Rival HS Eagles" in resp.text
        assert "Rival HS Hawks" in resp.text
        assert "Select" in resp.text

    def test_refine_search_form(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        with (
            patch.dict("os.environ", _admin_env(db_path, "search2@example.com")),
            patch("src.api.routes.admin._gc_search_teams", return_value=[]),
        ):
            client, _ = _auth_client(db_path, "search2@example.com")
            resp = client.get(f"/admin/opponents/{ids['unresolved_link']}/resolve")
        assert 'name="q"' in resp.text
        # State/city filters removed (AC-10: POST /search only supports name)
        assert 'name="state"' not in resp.text
        assert 'name="city"' not in resp.text

    def test_no_results_message(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        with (
            patch.dict("os.environ", _admin_env(db_path, "search3@example.com")),
            patch("src.api.routes.admin._gc_search_teams", return_value=[]),
        ):
            client, _ = _auth_client(db_path, "search3@example.com")
            resp = client.get(f"/admin/opponents/{ids['unresolved_link']}/resolve")
        assert "No teams found" in resp.text
        # Unified page: URL paste section is inline (not a separate link)
        assert "Paste a GameChanger URL" in resp.text

    def test_search_error_shows_fallback(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        with (
            patch.dict("os.environ", _admin_env(db_path, "search4@example.com")),
            patch("src.api.routes.admin._gc_search_teams", side_effect=Exception("API down")),
        ):
            client, _ = _auth_client(db_path, "search4@example.com")
            resp = client.get(f"/admin/opponents/{ids['unresolved_link']}/resolve")
        assert resp.status_code == 200
        assert "Search failed" in resp.text
        # Unified page: URL paste section is inline
        assert "Paste a GameChanger URL" in resp.text

    def test_refine_params_passed(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        with (
            patch.dict("os.environ", _admin_env(db_path, "search5@example.com")),
            patch("src.api.routes.admin._gc_search_teams", return_value=[]) as mock_search,
        ):
            client, _ = _auth_client(db_path, "search5@example.com")
            resp = client.get(
                f"/admin/opponents/{ids['unresolved_link']}/resolve?q=Eagles"
            )
        mock_search.assert_called_once_with("Eagles")


class TestSearchResultRendering:
    """AC-3, AC-4: Search result display and Select link format."""

    def test_select_link_uses_public_id_and_gc_uuid(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        with (
            patch.dict("os.environ", _admin_env(db_path, "render1@example.com")),
            patch("src.api.routes.admin._gc_search_teams", return_value=_MOCK_SEARCH_RESULTS),
        ):
            client, _ = _auth_client(db_path, "render1@example.com")
            resp = client.get(f"/admin/opponents/{ids['unresolved_link']}/resolve")
        assert "confirm=rival-eagles-slug" in resp.text
        assert "gc_uuid=uuid-rival-001" in resp.text

    def test_location_and_season_year_displayed(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        with (
            patch.dict("os.environ", _admin_env(db_path, "render2@example.com")),
            patch("src.api.routes.admin._gc_search_teams", return_value=_MOCK_SEARCH_RESULTS),
        ):
            client, _ = _auth_client(db_path, "render2@example.com")
            resp = client.get(f"/admin/opponents/{ids['unresolved_link']}/resolve")
        assert "Lincoln" in resp.text
        assert "NE" in resp.text
        assert "2026" in resp.text


class TestSearchNormalization:
    """AC-2: _gc_search_teams returns normalized flat dicts."""

    def test_normalize_post_search_response(self) -> None:
        from src.api.routes.admin import _gc_search_teams

        mock_api_response = {
            "total_count": 1,
            "hits": [
                {
                    "type": "team",
                    "result": {
                        "id": "uuid-123",
                        "public_id": "slug-abc",
                        "name": "Test Team",
                        "sport": "baseball",
                        "location": {"city": "Omaha", "state": "NE", "country": "US"},
                        "season": {"name": "spring", "year": 2026},
                        "number_of_players": 15,
                        "staff": ["Coach A"],
                    },
                }
            ],
            "next_page": None,
        }
        with patch("src.gamechanger.client.GameChangerClient") as MockClient:
            MockClient.return_value.post_json.return_value = mock_api_response
            results = _gc_search_teams("Test Team")

        assert len(results) == 1
        r = results[0]
        assert r["name"] == "Test Team"
        assert r["gc_uuid"] == "uuid-123"
        assert r["public_id"] == "slug-abc"
        assert r["city"] == "Omaha"
        assert r["state"] == "NE"
        assert r["season_year"] == 2026
        assert r["season_name"] == "spring"
        assert r["sport"] == "baseball"
        assert r["num_players"] == 15
        assert r["staff"] == ["Coach A"]

    def test_normalize_empty_hits(self) -> None:
        from src.api.routes.admin import _gc_search_teams

        with patch("src.gamechanger.client.GameChangerClient") as MockClient:
            MockClient.return_value.post_json.return_value = {"total_count": 0, "hits": []}
            results = _gc_search_teams("Nothing")

        assert results == []

    def test_normalize_missing_optional_fields(self) -> None:
        from src.api.routes.admin import _gc_search_teams

        mock_response = {
            "hits": [
                {
                    "type": "team",
                    "result": {
                        "id": "uuid-456",
                        "public_id": "slug-def",
                        "name": "Sparse Team",
                    },
                }
            ],
        }
        with patch("src.gamechanger.client.GameChangerClient") as MockClient:
            MockClient.return_value.post_json.return_value = mock_response
            results = _gc_search_teams("Sparse")

        assert len(results) == 1
        r = results[0]
        assert r["name"] == "Sparse Team"
        assert r["city"] is None
        assert r["state"] is None
        assert r["season_year"] is None
        assert r["staff"] == []


class TestSkipFlow:
    """AC-5: Skip (hide) an opponent."""

    def test_skip_sets_is_hidden(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        with patch.dict("os.environ", _admin_env(db_path, "skip1@example.com")):
            client, _ = _auth_client(db_path, "skip1@example.com")
            resp = client.post(
                f"/admin/opponents/{ids['unresolved_link']}/skip",
                data={"csrf_token": _CSRF},
                follow_redirects=False,
            )
        assert resp.status_code == 303
        assert "filter=unresolved" in resp.headers["location"]
        row = _get_link_row(db_path, ids["unresolved_link"])
        assert row["is_hidden"] == 1


class TestPasteURLLink:
    """AC-6: URL paste section on unified resolve page."""

    def test_url_paste_section_present(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        link_id = ids["unresolved_link"]
        with (
            patch.dict("os.environ", _admin_env(db_path, "paste1@example.com")),
            patch("src.api.routes.admin._gc_search_teams", return_value=[]),
        ):
            client, _ = _auth_client(db_path, "paste1@example.com")
            resp = client.get(f"/admin/opponents/{link_id}/resolve")
        assert "Paste a GameChanger URL" in resp.text


class TestConfirmFlow:
    """Confirm page and POST with public_id + gc_uuid."""

    def test_confirm_page_shows_profile(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        with (
            patch.dict("os.environ", _admin_env(db_path, "confirm1@example.com")),
            patch("src.api.routes.admin.resolve_team", return_value=_MOCK_PROFILE),
        ):
            client, _ = _auth_client(db_path, "confirm1@example.com")
            resp = client.get(
                f"/admin/opponents/{ids['unresolved_link']}/resolve"
                "?confirm=rival-eagles-slug&gc_uuid=uuid-rival-001"
            )
        assert resp.status_code == 200
        assert "Rival HS Eagles" in resp.text
        assert "Confirm connection" in resp.text
        # gc_uuid should be in a hidden field
        assert 'name="gc_uuid"' in resp.text
        assert "uuid-rival-001" in resp.text

    def test_confirm_duplicate_warning(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        # Insert existing team with same public_id
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO teams (name, membership_type, public_id, source) "
            "VALUES ('Existing Team', 'tracked', 'rival-eagles-slug', 'test')"
        )
        conn.commit()
        conn.close()

        with (
            patch.dict("os.environ", _admin_env(db_path, "confirm2@example.com")),
            patch("src.api.routes.admin.resolve_team", return_value=_MOCK_PROFILE),
        ):
            client, _ = _auth_client(db_path, "confirm2@example.com")
            resp = client.get(
                f"/admin/opponents/{ids['unresolved_link']}/resolve"
                "?confirm=rival-eagles-slug&gc_uuid=uuid-rival-001"
            )
        assert "Duplicate warning" in resp.text
        assert "merge" in resp.text.lower()

    def test_confirm_post_resolves_with_public_id_and_gc_uuid(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        with (
            patch.dict("os.environ", _admin_env(db_path, "confirm3@example.com")),
            patch("src.api.routes.admin.resolve_team", return_value=_MOCK_PROFILE),
        ):
            client, _ = _auth_client(db_path, "confirm3@example.com")
            resp = client.post(
                f"/admin/opponents/{ids['unresolved_link']}/resolve",
                data={
                    "csrf_token": _CSRF,
                    "confirm_id": "rival-eagles-slug",
                    "gc_uuid": "uuid-rival-001",
                },
                follow_redirects=False,
            )
        assert resp.status_code == 303
        assert "filter=unresolved" in resp.headers["location"]

        row = _get_link_row(db_path, ids["unresolved_link"])
        assert row["resolved_team_id"] is not None
        assert row["resolution_method"] == "search"
        assert row["public_id"] == "rival-eagles-slug"

        # Verify the team row has the gc_uuid
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        team_row = conn.execute(
            "SELECT gc_uuid, public_id FROM teams WHERE id = ?",
            (row["resolved_team_id"],),
        ).fetchone()
        conn.close()
        assert team_row["gc_uuid"] == "uuid-rival-001"
        assert team_row["public_id"] == "rival-eagles-slug"

    def test_confirm_post_without_gc_uuid_still_works(self, tmp_path: Path) -> None:
        """POST without gc_uuid (edge case) should still resolve."""
        db_path, ids = _make_db(tmp_path)
        with (
            patch.dict("os.environ", _admin_env(db_path, "confirm4@example.com")),
            patch("src.api.routes.admin.resolve_team", return_value=_MOCK_PROFILE),
        ):
            client, _ = _auth_client(db_path, "confirm4@example.com")
            resp = client.post(
                f"/admin/opponents/{ids['unresolved_link']}/resolve",
                data={"csrf_token": _CSRF, "confirm_id": "rival-eagles-slug"},
                follow_redirects=False,
            )
        assert resp.status_code == 303
        row = _get_link_row(db_path, ids["unresolved_link"])
        assert row["resolved_team_id"] is not None
        assert row["resolution_method"] == "search"


class TestHiddenFilter:
    """AC-11: Hidden filter tab, unhide button."""

    def test_hidden_filter_shows_hidden_only(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        with patch.dict("os.environ", _admin_env(db_path, "hidden1@example.com")):
            client, _ = _auth_client(db_path, "hidden1@example.com")
            resp = client.get("/admin/opponents?filter=hidden")
        assert "Hidden Opp" in resp.text
        assert "Rival HS" not in resp.text

    def test_unhide_button_visible(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        with patch.dict("os.environ", _admin_env(db_path, "hidden2@example.com")):
            client, _ = _auth_client(db_path, "hidden2@example.com")
            resp = client.get("/admin/opponents?filter=hidden")
        assert "Unhide" in resp.text

    def test_unhide_restores(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        with patch.dict("os.environ", _admin_env(db_path, "hidden3@example.com")):
            client, _ = _auth_client(db_path, "hidden3@example.com")
            resp = client.post(
                f"/admin/opponents/{ids['hidden_link']}/unhide",
                data={"csrf_token": _CSRF},
                follow_redirects=False,
            )
        assert resp.status_code == 303
        row = _get_link_row(db_path, ids["hidden_link"])
        assert row["is_hidden"] == 0

    def test_hidden_count_in_pill(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        with patch.dict("os.environ", _admin_env(db_path, "hidden4@example.com")):
            client, _ = _auth_client(db_path, "hidden4@example.com")
            resp = client.get("/admin/opponents")
        assert "Hidden (1)" in resp.text


# ---------------------------------------------------------------------------
# E-173-02: Auto-scout after search resolve
# ---------------------------------------------------------------------------


class TestAutoScoutAfterSearchResolve:
    """AC-1, AC-4, AC-6: Search resolve triggers scouting sync."""

    def test_scouting_enqueued_after_resolve(self, tmp_path: Path) -> None:
        """AC-1: resolve_opponent_confirm triggers run_scouting_sync when public_id is non-null."""
        db_path, ids = _make_db(tmp_path)
        with (
            patch.dict("os.environ", _admin_env(db_path, "scout1@example.com")),
            patch("src.api.routes.admin.resolve_team", return_value=_MOCK_PROFILE),
            patch("src.api.routes.admin.trigger") as mock_trigger,
        ):
            client, _ = _auth_client(db_path, "scout1@example.com")
            resp = client.post(
                f"/admin/opponents/{ids['unresolved_link']}/resolve",
                data={
                    "csrf_token": _CSRF,
                    "confirm_id": "rival-eagles-slug",
                    "gc_uuid": "uuid-rival-001",
                },
                follow_redirects=False,
            )

        assert resp.status_code == 303
        # TestClient executes BackgroundTasks synchronously, so
        # run_scouting_sync is called directly during the request.
        mock_trigger.run_scouting_sync.assert_called_once()
        call_args = mock_trigger.run_scouting_sync.call_args
        # First positional arg is team_id, second is public_id, third is crawl_job_id
        assert call_args[0][1] == "rival-eagles-slug"  # public_id

        # AC-5: crawl_jobs row uses sync_type='scouting_crawl'
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        job = conn.execute(
            "SELECT * FROM crawl_jobs WHERE sync_type = 'scouting_crawl' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        assert job is not None
        assert job["sync_type"] == "scouting_crawl"

    def test_flash_message_includes_syncing(self, tmp_path: Path) -> None:
        """AC-4: Flash message mentions background sync."""
        db_path, ids = _make_db(tmp_path)
        with (
            patch.dict("os.environ", _admin_env(db_path, "scout2@example.com")),
            patch("src.api.routes.admin.resolve_team", return_value=_MOCK_PROFILE),
            patch("src.api.routes.admin.trigger"),
        ):
            client, _ = _auth_client(db_path, "scout2@example.com")
            resp = client.post(
                f"/admin/opponents/{ids['unresolved_link']}/resolve",
                data={
                    "csrf_token": _CSRF,
                    "confirm_id": "rival-eagles-slug",
                    "gc_uuid": "uuid-rival-001",
                },
                follow_redirects=False,
            )
        assert resp.status_code == 303
        location = resp.headers["location"]
        assert "syncing" in location.lower() or "Stats" in location

    def test_crawl_job_sync_type(self, tmp_path: Path) -> None:
        """AC-5: crawl_jobs row uses sync_type='scouting_crawl'."""
        db_path, ids = _make_db(tmp_path)
        with (
            patch.dict("os.environ", _admin_env(db_path, "scout3@example.com")),
            patch("src.api.routes.admin.resolve_team", return_value=_MOCK_PROFILE),
            patch("src.api.routes.admin.trigger"),
        ):
            client, _ = _auth_client(db_path, "scout3@example.com")
            resp = client.post(
                f"/admin/opponents/{ids['unresolved_link']}/resolve",
                data={
                    "csrf_token": _CSRF,
                    "confirm_id": "rival-eagles-slug",
                    "gc_uuid": "uuid-rival-001",
                },
                follow_redirects=False,
            )
        assert resp.status_code == 303
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        job = conn.execute(
            "SELECT * FROM crawl_jobs WHERE sync_type = 'scouting_crawl'"
        ).fetchone()
        conn.close()
        assert job is not None
        assert job["sync_type"] == "scouting_crawl"
        assert job["status"] == "running"

    def test_no_scout_when_resolved_team_has_null_public_id(self, tmp_path: Path) -> None:
        """AC-3, AC-6: No scouting when resolved team's public_id is NULL.

        Setup: pre-insert a team matched by gc_uuid with public_id=NULL, and
        a *different* team already owning the confirm_id slug.  ensure_team_row
        matches on gc_uuid (step 1) and skips public_id backfill due to the
        collision, so the resolved team retains public_id=NULL.
        """
        db_path, ids = _make_db(tmp_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        # Pre-insert team matched by gc_uuid, with NULL public_id
        conn.execute(
            "INSERT INTO teams (name, membership_type, gc_uuid, public_id, source, is_active) "
            "VALUES ('Rival Pre-Existing', 'tracked', 'uuid-collision-001', NULL, 'test', 0)"
        )
        # Another team already owns the slug that confirm_id will try to assign
        conn.execute(
            "INSERT INTO teams (name, membership_type, public_id, source, is_active) "
            "VALUES ('Slug Owner', 'tracked', 'collision-slug', 'test', 0)"
        )
        conn.commit()
        conn.close()

        collision_profile = TeamProfile(
            public_id="collision-slug",
            name="Rival Pre-Existing",
            sport="baseball",
            city="Lincoln",
            state="NE",
            record_wins=0,
            record_losses=0,
            year=2026,
        )
        with (
            patch.dict("os.environ", _admin_env(db_path, "scout4@example.com")),
            patch("src.api.routes.admin.resolve_team", return_value=collision_profile),
            patch("src.api.routes.admin.trigger") as mock_trigger,
        ):
            client, _ = _auth_client(db_path, "scout4@example.com")
            resp = client.post(
                f"/admin/opponents/{ids['unresolved_link']}/resolve",
                data={
                    "csrf_token": _CSRF,
                    "confirm_id": "collision-slug",
                    "gc_uuid": "uuid-collision-001",
                },
                follow_redirects=False,
            )
        assert resp.status_code == 303

        # run_scouting_sync should NOT have been called
        mock_trigger.run_scouting_sync.assert_not_called()

        # No crawl_jobs row for scouting
        conn = sqlite3.connect(str(db_path))
        job_count = conn.execute(
            "SELECT COUNT(*) FROM crawl_jobs WHERE sync_type = 'scouting_crawl'"
        ).fetchone()[0]
        conn.close()
        assert job_count == 0


# ---------------------------------------------------------------------------
# E-173-03: Unified resolve page
# ---------------------------------------------------------------------------


class TestUnifiedResolvePage:
    """AC-1, AC-2, AC-3, AC-7, AC-9: Unified page structure and enriched cards."""

    def test_page_title_and_sections(self, tmp_path: Path) -> None:
        """AC-1, AC-2: Page has correct title and all three sections."""
        db_path, ids = _make_db(tmp_path)
        with (
            patch.dict("os.environ", _admin_env(db_path, "unified1@example.com")),
            patch("src.api.routes.admin._gc_search_teams", return_value=_MOCK_SEARCH_RESULTS),
        ):
            client, _ = _auth_client(db_path, "unified1@example.com")
            resp = client.get(f"/admin/opponents/{ids['unresolved_link']}/resolve")
        assert resp.status_code == 200
        # AC-1: Title
        assert "Find Rival HS on GameChanger" in resp.text
        # AC-1: Member team shown
        assert "LSB Varsity" in resp.text
        # AC-2: Search section
        assert "Search GameChanger" in resp.text
        # AC-2: Divider
        assert ">or<" in resp.text.replace(" ", "")
        # AC-2: URL paste section
        assert "Paste a GameChanger URL" in resp.text
        # AC-7: Skip section
        assert "No match -- skip" in resp.text

    def test_search_cards_enriched(self, tmp_path: Path) -> None:
        """AC-3: Search result cards display enriched fields."""
        db_path, ids = _make_db(tmp_path)
        with (
            patch.dict("os.environ", _admin_env(db_path, "unified2@example.com")),
            patch("src.api.routes.admin._gc_search_teams", return_value=_MOCK_SEARCH_RESULTS),
        ):
            client, _ = _auth_client(db_path, "unified2@example.com")
            resp = client.get(f"/admin/opponents/{ids['unresolved_link']}/resolve")
        text = resp.text
        # Team name (bold)
        assert "Rival HS Eagles" in text
        # Season year badge (prominent, not gray)
        assert "bg-blue-100" in text
        assert ">2026<" in text
        # Player count
        assert "15 players" in text
        # Staff
        assert "Coach Smith" in text

    def test_url_paste_form_present(self, tmp_path: Path) -> None:
        """AC-5: URL paste form is present with correct action target."""
        db_path, ids = _make_db(tmp_path)
        with (
            patch.dict("os.environ", _admin_env(db_path, "unified3@example.com")),
            patch("src.api.routes.admin._gc_search_teams", return_value=[]),
        ):
            client, _ = _auth_client(db_path, "unified3@example.com")
            resp = client.get(f"/admin/opponents/{ids['unresolved_link']}/resolve")
        assert resp.status_code == 200
        # URL paste form targets the resolve endpoint with url param
        assert 'name="url"' in resp.text
        assert f"/admin/opponents/{ids['unresolved_link']}/resolve" in resp.text

    def test_old_connect_url_redirects(self, tmp_path: Path) -> None:
        """AC-6: Old connect URL redirects to the unified resolve page.

        Note: route-level redirects only work when the worktree code is loaded.
        This test verifies the redirect behavior of connect_opponent_form.
        """
        db_path, ids = _make_db(tmp_path)
        with patch.dict("os.environ", _admin_env(db_path, "unified4@example.com")):
            client, _ = _auth_client(db_path, "unified4@example.com")
            resp = client.get(
                f"/admin/opponents/{ids['unresolved_link']}/connect",
                follow_redirects=False,
            )
        # The handler redirects (303) to the resolve page
        assert resp.status_code == 303
        assert "/resolve" in resp.headers["location"]


# ---------------------------------------------------------------------------
# E-173-05: Terminology cleanup
# ---------------------------------------------------------------------------


class TestTerminologyCleanup:
    """AC-8: Verify terminology changes in templates."""

    def test_discover_button_removed_from_teams(self, tmp_path: Path) -> None:
        """AC-1, AC-8: 'Discover' button no longer renders on the teams page."""
        db_path, ids = _make_db(tmp_path)
        with patch.dict("os.environ", _admin_env(db_path, "term1@example.com")):
            client, _ = _auth_client(db_path, "term1@example.com")
            resp = client.get("/admin/teams")
        assert "Discover" not in resp.text

    def test_filter_pills_use_new_labels(self, tmp_path: Path) -> None:
        """AC-2, AC-8: Filter pills show new labels."""
        db_path, ids = _make_db(tmp_path)
        with patch.dict("os.environ", _admin_env(db_path, "term2@example.com")):
            client, _ = _auth_client(db_path, "term2@example.com")
            resp = client.get("/admin/opponents")
        assert "Stats loaded" in resp.text
        assert "Needs linking" in resp.text
        # Old labels should not appear
        assert "Full stats" not in resp.text
        assert "Scoresheet only" not in resp.text

    def test_unresolved_badge_shows_count(self, tmp_path: Path) -> None:
        """AC-6, AC-8: Unresolved count badge in sub-nav."""
        db_path, ids = _make_db(tmp_path)
        with patch.dict("os.environ", _admin_env(db_path, "term3@example.com")):
            client, _ = _auth_client(db_path, "term3@example.com")
            resp = client.get("/admin/opponents")
        # Sub-nav should show the unresolved count badge
        assert "text-orange-600" in resp.text

    def test_tracked_badge_renamed_to_opponent(self, tmp_path: Path) -> None:
        """AC-4, AC-8: 'Tracked' badge replaced with 'Opponent' on teams page."""
        db_path, ids = _make_db(tmp_path)
        # Add a tracked team
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            "INSERT INTO teams (name, membership_type, source, is_active) "
            "VALUES ('Some Tracked', 'tracked', 'test', 1)"
        )
        conn.commit()
        conn.close()
        with patch.dict("os.environ", _admin_env(db_path, "term4@example.com")):
            client, _ = _auth_client(db_path, "term4@example.com")
            resp = client.get("/admin/teams")
        assert "Opponent" in resp.text
        # "Tracked" badge text should not appear (only the value in form fields)
        assert ">Tracked<" not in resp.text


# ---------------------------------------------------------------------------
# P1-4: Owned-team guard on URL-paste and resolve POST
# ---------------------------------------------------------------------------


class TestOwnedTeamGuard:
    """P1-4: Reject member-team URLs/slugs in resolve flows."""

    def test_resolve_post_rejects_member_team_slug(self, tmp_path: Path) -> None:
        """Resolve POST with a member team's public_id is rejected."""
        db_path, ids = _make_db(tmp_path)
        with (
            patch.dict("os.environ", _admin_env(db_path, "guard1@example.com")),
            patch("src.api.routes.admin.trigger"),
        ):
            client, _ = _auth_client(db_path, "guard1@example.com")
            resp = client.post(
                f"/admin/opponents/{ids['unresolved_link']}/resolve",
                data={
                    "csrf_token": _CSRF,
                    "confirm_id": "ownedPubId",  # member team's public_id
                },
                follow_redirects=False,
            )
        assert resp.status_code == 303
        assert "Lincoln" in resp.headers.get("location", "") or "error" in resp.headers.get("location", "")


# ---------------------------------------------------------------------------
# P1-5: Stats loaded filter uses actual stats existence
# ---------------------------------------------------------------------------


class TestStatsLoadedFilter:
    """P1-5: 'Stats loaded' filter checks actual season stats, not just public_id."""

    def test_resolved_without_stats_not_in_stats_loaded(self, tmp_path: Path) -> None:
        """Resolved opponent with public_id but no season stats excluded from Stats loaded filter."""
        db_path, ids = _make_db(tmp_path)
        # The DB from _make_db has a resolved opponent (opp_id) with public_id='resolved-slug'
        # but no player_season_batting/pitching rows.
        with patch.dict("os.environ", _admin_env(db_path, "filt1@example.com")):
            client, _ = _auth_client(db_path, "filt1@example.com")
            resp = client.get("/admin/opponents?filter=full")
        assert resp.status_code == 200
        # Resolved Opp has public_id but no stats -- should NOT appear
        assert "Resolved Opp" not in resp.text

    def test_stats_loaded_count_reflects_actual_stats(self, tmp_path: Path) -> None:
        """Stats loaded count is 0 when no opponents have season stat rows."""
        db_path, ids = _make_db(tmp_path)
        with patch.dict("os.environ", _admin_env(db_path, "filt2@example.com")):
            client, _ = _auth_client(db_path, "filt2@example.com")
            resp = client.get("/admin/opponents")
        assert resp.status_code == 200
        # No opponents have actual stats, so count should be 0
        assert "Stats loaded (0)" in resp.text
