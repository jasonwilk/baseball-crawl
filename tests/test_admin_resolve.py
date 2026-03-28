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
        assert "unresolved" in resp.text.lower()
        assert "Start resolving" in resp.text

    def test_unresolved_count_in_filter_pill(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        with patch.dict("os.environ", _admin_env(db_path, "banner2@example.com")):
            client, _ = _auth_client(db_path, "banner2@example.com")
            resp = client.get("/admin/opponents")
        assert "Unresolved (1)" in resp.text

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
        assert ">Resolve<" in resp.text


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
        assert "Paste URL manually" in resp.text

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
        assert "Paste URL manually" in resp.text

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
    """AC-6: Manual paste link on resolve page."""

    def test_manual_paste_link(self, tmp_path: Path) -> None:
        db_path, ids = _make_db(tmp_path)
        link_id = ids["unresolved_link"]
        with (
            patch.dict("os.environ", _admin_env(db_path, "paste1@example.com")),
            patch("src.api.routes.admin._gc_search_teams", return_value=[]),
        ):
            client, _ = _auth_client(db_path, "paste1@example.com")
            resp = client.get(f"/admin/opponents/{link_id}/resolve")
        assert f"/admin/opponents/{link_id}/connect" in resp.text


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
