# synthetic-test-data
"""Tests for E-155-03: Admin Merge UI.

Covers:
- AC-1: Duplicate banner appears on /admin/teams when duplicates detected.
- AC-2: GET /admin/teams/merge renders team comparison and preview.
- AC-3: POST /admin/teams/merge executes merge and redirects with success.
- AC-4: POST without CSRF cookie returns 403.
- AC-5: Confirm button disabled when blocking issues present.
- AC-6: Resolve link in banner carries team_ids query param.
- Error handling: missing/invalid team_ids redirect to /admin/teams.

Run with:
    pytest tests/test_admin_merge.py -v
"""

from __future__ import annotations

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
from src.api.main import app  # noqa: E402

_ADMIN_EMAIL = "admin@test.example"


# ---------------------------------------------------------------------------
# DB setup helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test_merge_admin.db"
    run_migrations(db_path=db_path)
    return db_path


def _insert_team(
    conn: sqlite3.Connection,
    name: str,
    membership_type: str = "tracked",
    gc_uuid: str | None = None,
    public_id: str | None = None,
    season_year: int | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, public_id, season_year)"
        " VALUES (?, ?, ?, ?, ?)",
        (name, membership_type, gc_uuid, public_id, season_year),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def _insert_user(
    conn: sqlite3.Connection, email: str = _ADMIN_EMAIL, role: str = "user"
) -> int:
    cur = conn.execute(
        "INSERT OR IGNORE INTO users (email, role) VALUES (?, ?)", (email, role)
    )
    conn.commit()
    uid: int = cur.lastrowid or conn.execute(  # type: ignore[assignment]
        "SELECT id FROM users WHERE email = ?", (email,)
    ).fetchone()[0]
    return uid


def _insert_season(conn: sqlite3.Connection, season_id: str = "2026-spring") -> str:
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year)"
        " VALUES (?, 'Spring 2026', 'spring-hs', 2026)",
        (season_id,),
    )
    conn.commit()
    return season_id


def _insert_player(conn: sqlite3.Connection, player_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name)"
        " VALUES (?, 'A', 'B')",
        (player_id,),
    )
    conn.commit()


def _insert_batting(
    conn: sqlite3.Connection,
    player_id: str,
    team_id: int,
    season_id: str = "2026-spring",
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO player_season_batting"
        " (player_id, team_id, season_id, gp, ab, h, doubles, triples, hr, rbi,"
        "  bb, so, sb, hbp, shf, tb)"
        " VALUES (?, ?, ?, 1, 3, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1)",
        (player_id, team_id, season_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------


def _make_client(db_path: Path) -> tuple[TestClient, dict[str, str]]:
    """Return (client, env) with admin bypass configured."""
    env = {
        "DATABASE_PATH": str(db_path),
        "DEV_USER_EMAIL": _ADMIN_EMAIL,
        "ADMIN_EMAIL": _ADMIN_EMAIL,
    }
    return TestClient(app, raise_server_exceptions=True), env


def _get_csrf_cookie(client: TestClient, env: dict[str, str], url: str = "/admin/teams") -> str:
    """Do a GET request to obtain a CSRF cookie, return the token value."""
    with patch.dict("os.environ", env):
        resp = client.get(url, follow_redirects=False)
    # The CSRF cookie is set in Set-Cookie; read it from response cookies
    csrf = resp.cookies.get("csrf_token", "")
    if not csrf:
        # Follow redirects to get a page that sets the cookie
        with patch.dict("os.environ", env):
            resp2 = client.get(url, follow_redirects=True)
        csrf = resp2.cookies.get("csrf_token", "")
    return csrf


# ---------------------------------------------------------------------------
# AC-1: Duplicate banner on /admin/teams
# ---------------------------------------------------------------------------


class TestDuplicatesBanner:
    """AC-1: /admin/teams shows Potential Duplicates banner."""

    def test_banner_shown_when_duplicates_exist(self, tmp_path):
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            _insert_team(conn, "Rival High", season_year=2026)
            _insert_team(conn, "Rival High", season_year=2026)

        client, env = _make_client(db_path)
        with patch.dict("os.environ", env):
            with TestClient(app) as c:
                resp = c.get("/admin/teams")

        assert resp.status_code == 200
        assert "Potential Duplicates" in resp.text
        assert "Rival High" in resp.text
        assert "Resolve" in resp.text

    def test_banner_not_shown_when_no_duplicates(self, tmp_path):
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            _insert_team(conn, "Alpha High", season_year=2026)
            _insert_team(conn, "Beta High", season_year=2026)

        _, env = _make_client(db_path)
        with patch.dict("os.environ", env):
            with TestClient(app) as c:
                resp = c.get("/admin/teams")

        assert resp.status_code == 200
        assert "Potential Duplicates" not in resp.text

    def test_banner_shows_2_teams_count(self, tmp_path):
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            _insert_team(conn, "Dup Team", season_year=2026)
            _insert_team(conn, "Dup Team", season_year=2026)

        _, env = _make_client(db_path)
        with patch.dict("os.environ", env):
            with TestClient(app) as c:
                resp = c.get("/admin/teams")

        assert "2 teams" in resp.text

    def test_resolve_link_contains_team_ids(self, tmp_path):
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            id1 = _insert_team(conn, "Same Name", season_year=2026)
            id2 = _insert_team(conn, "Same Name", season_year=2026)

        _, env = _make_client(db_path)
        with patch.dict("os.environ", env):
            with TestClient(app) as c:
                resp = c.get("/admin/teams")

        # AC-6: Resolve link carries team_ids param
        assert f"team_ids={id1},{id2}" in resp.text or f"team_ids={id2},{id1}" in resp.text

    def test_member_teams_not_included_in_duplicates(self, tmp_path):
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            # Same name, but one is member -- should NOT appear as duplicate group
            _insert_team(conn, "LSB Varsity", membership_type="member", season_year=2026)
            _insert_team(conn, "LSB Varsity", membership_type="tracked", season_year=2026)

        _, env = _make_client(db_path)
        with patch.dict("os.environ", env):
            with TestClient(app) as c:
                resp = c.get("/admin/teams")

        assert "Potential Duplicates" not in resp.text


# ---------------------------------------------------------------------------
# AC-2: GET /admin/teams/merge
# ---------------------------------------------------------------------------


class TestMergePageGet:
    """AC-2: GET /admin/teams/merge renders correctly."""

    def test_renders_for_2_teams(self, tmp_path):
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            id1 = _insert_team(conn, "Team Alpha", season_year=2026)
            id2 = _insert_team(conn, "Team Alpha", season_year=2026)

        _, env = _make_client(db_path)
        with patch.dict("os.environ", env):
            with TestClient(app) as c:
                resp = c.get(f"/admin/teams/merge?team_ids={id1},{id2}")

        assert resp.status_code == 200
        assert "Team Alpha" in resp.text
        # Both team IDs should appear in the page
        assert str(id1) in resp.text
        assert str(id2) in resp.text

    def test_shows_team_details(self, tmp_path):
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            id1 = _insert_team(
                conn, "Show Details", gc_uuid="abc-uuid", public_id="pub-slug", season_year=2026
            )
            id2 = _insert_team(conn, "Show Details", season_year=2026)

        _, env = _make_client(db_path)
        with patch.dict("os.environ", env):
            with TestClient(app) as c:
                resp = c.get(f"/admin/teams/merge?team_ids={id1},{id2}")

        assert resp.status_code == 200
        assert "abc-uuid" in resp.text
        assert "pub-slug" in resp.text

    def test_redirects_when_no_team_ids(self, tmp_path):
        db_path = _make_db(tmp_path)
        _, env = _make_client(db_path)
        with patch.dict("os.environ", env):
            with TestClient(app) as c:
                resp = c.get("/admin/teams/merge", follow_redirects=False)

        assert resp.status_code == 302
        assert "/admin/teams" in resp.headers["location"]

    def test_redirects_when_only_one_id(self, tmp_path):
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            id1 = _insert_team(conn, "Solo", season_year=2026)

        _, env = _make_client(db_path)
        with patch.dict("os.environ", env):
            with TestClient(app) as c:
                resp = c.get(f"/admin/teams/merge?team_ids={id1}", follow_redirects=False)

        assert resp.status_code == 302
        assert "/admin/teams" in resp.headers["location"]

    def test_redirects_on_invalid_team_ids(self, tmp_path):
        db_path = _make_db(tmp_path)
        _, env = _make_client(db_path)
        with patch.dict("os.environ", env):
            with TestClient(app) as c:
                resp = c.get("/admin/teams/merge?team_ids=abc,xyz", follow_redirects=False)

        assert resp.status_code == 302

    def test_redirects_when_team_not_found(self, tmp_path):
        db_path = _make_db(tmp_path)
        _, env = _make_client(db_path)
        with patch.dict("os.environ", env):
            with TestClient(app) as c:
                resp = c.get("/admin/teams/merge?team_ids=9999,8888", follow_redirects=False)

        assert resp.status_code == 302
        assert "/admin/teams" in resp.headers["location"]

    def test_shows_preview_when_canonical_id_provided(self, tmp_path):
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            id1 = _insert_team(conn, "Preview Team", season_year=2026)
            id2 = _insert_team(conn, "Preview Team", season_year=2026)

        _, env = _make_client(db_path)
        with patch.dict("os.environ", env):
            with TestClient(app) as c:
                resp = c.get(
                    f"/admin/teams/merge?team_ids={id1},{id2}&canonical_id={id1}"
                )

        assert resp.status_code == 200
        # Preview section should appear -- Confirm Merge button
        assert "Confirm Merge" in resp.text
        assert "Identifier Gap-Fill" in resp.text

    def test_shows_3_plus_teams(self, tmp_path):
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            id1 = _insert_team(conn, "Triple Team", season_year=2026)
            id2 = _insert_team(conn, "Triple Team", season_year=2026)
            id3 = _insert_team(conn, "Triple Team", season_year=2026)

        _, env = _make_client(db_path)
        with patch.dict("os.environ", env):
            with TestClient(app) as c:
                resp = c.get(f"/admin/teams/merge?team_ids={id1},{id2},{id3}")

        assert resp.status_code == 200
        # All 3 teams should appear
        assert str(id1) in resp.text
        assert str(id2) in resp.text
        assert str(id3) in resp.text

    def test_shows_has_stats_badge(self, tmp_path):
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            _insert_season(conn)
            id1 = _insert_team(conn, "Stats Team", season_year=2026)
            id2 = _insert_team(conn, "Stats Team", season_year=2026)
            _insert_player(conn, "p-stat-001")
            _insert_batting(conn, "p-stat-001", id1)

        _, env = _make_client(db_path)
        with patch.dict("os.environ", env):
            with TestClient(app) as c:
                resp = c.get(f"/admin/teams/merge?team_ids={id1},{id2}")

        assert resp.status_code == 200
        assert "Has stats" in resp.text


# ---------------------------------------------------------------------------
# AC-3: POST /admin/teams/merge
# ---------------------------------------------------------------------------


class TestMergePost:
    """AC-3: POST /admin/teams/merge executes merge."""

    def _csrf_post(
        self,
        db_path: Path,
        data: dict,
        env: dict[str, str],
    ) -> "Response":  # type: ignore[name-defined]
        """POST to /admin/teams/merge with CSRF cookie set."""
        with patch.dict("os.environ", env):
            with TestClient(app) as c:
                # Step 1: GET to obtain CSRF token
                get_resp = c.get("/admin/teams/merge?team_ids=1,2", follow_redirects=False)
                csrf = get_resp.cookies.get("csrf_token", "")
                if not csrf:
                    # Try the teams list page for the cookie
                    get_resp2 = c.get("/admin/teams", follow_redirects=True)
                    csrf = get_resp2.cookies.get("csrf_token", "")
                # Step 2: POST with the token
                post_data = {**data, "csrf_token": csrf}
                resp = c.post(
                    "/admin/teams/merge",
                    data=post_data,
                    cookies={"csrf_token": csrf},
                    follow_redirects=False,
                )
        return resp

    def test_successful_merge_redirects_to_teams(self, tmp_path):
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            id1 = _insert_team(conn, "Will Merge", season_year=2026)
            id2 = _insert_team(conn, "Will Merge", season_year=2026)

        _, env = _make_client(db_path)
        resp = self._csrf_post(
            db_path,
            {
                "canonical_id": str(id1),
                "duplicate_id": str(id2),
                "team_ids_str": f"{id1},{id2}",
            },
            env,
        )

        assert resp.status_code == 303
        assert "/admin/teams" in resp.headers["location"]
        assert "merged_canonical_id" in resp.headers["location"]

    def test_success_message_contains_team_names(self, tmp_path):
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            id1 = _insert_team(conn, "Keep Team", season_year=2026)
            id2 = _insert_team(conn, "Delete Team", season_year=2026)

        _, env = _make_client(db_path)
        resp = self._csrf_post(
            db_path,
            {
                "canonical_id": str(id1),
                "duplicate_id": str(id2),
                "team_ids_str": f"{id1},{id2}",
            },
            env,
        )

        location = resp.headers.get("location", "")
        assert "Keep+Team" in location or "Keep%20Team" in location or "Keep" in location

    def test_duplicate_team_deleted_after_merge(self, tmp_path):
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            id1 = _insert_team(conn, "Canonical", season_year=2026)
            id2 = _insert_team(conn, "Duplicate", season_year=2026)

        _, env = _make_client(db_path)
        self._csrf_post(
            db_path,
            {
                "canonical_id": str(id1),
                "duplicate_id": str(id2),
                "team_ids_str": f"{id1},{id2}",
            },
            env,
        )

        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute("SELECT id FROM teams WHERE id = ?", (id2,)).fetchone()
        assert row is None, "Duplicate team should have been deleted"

    def test_blocking_member_team_redirects_with_error(self, tmp_path):
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            id1 = _insert_team(conn, "Canonical", season_year=2026)
            # Duplicate is a member team -- MergeBlockedError expected
            id2 = _insert_team(conn, "Member Dup", membership_type="member", season_year=2026)

        _, env = _make_client(db_path)

        # Follow the redirect to verify error text renders in the merge page HTML
        with patch.dict("os.environ", env):
            with TestClient(app) as c:
                get_resp = c.get("/admin/teams/merge?team_ids=1,2", follow_redirects=False)
                csrf = get_resp.cookies.get("csrf_token", "")
                if not csrf:
                    get_resp2 = c.get("/admin/teams", follow_redirects=True)
                    csrf = get_resp2.cookies.get("csrf_token", "")
                post_data = {
                    "canonical_id": str(id1),
                    "duplicate_id": str(id2),
                    "team_ids_str": f"{id1},{id2}",
                    "csrf_token": csrf,
                }
                # POST returns 303 redirect to merge page with error in URL
                post_resp = c.post(
                    "/admin/teams/merge",
                    data=post_data,
                    cookies={"csrf_token": csrf},
                    follow_redirects=False,
                )
                assert post_resp.status_code == 303
                location = post_resp.headers.get("location", "")
                assert "/admin/teams/merge" in location
                assert "error" in location

                # Follow the redirect -- error text must appear in rendered HTML
                follow_resp = c.get(location, follow_redirects=True)
                assert follow_resp.status_code == 200
                assert "member" in follow_resp.text.lower() or "blocked" in follow_resp.text.lower() or "error" in follow_resp.text.lower()

    def test_missing_team_redirects_to_teams_list(self, tmp_path):
        db_path = _make_db(tmp_path)
        _, env = _make_client(db_path)
        resp = self._csrf_post(
            db_path,
            {
                "canonical_id": "9999",
                "duplicate_id": "8888",
                "team_ids_str": "9999,8888",
            },
            env,
        )

        assert resp.status_code == 303
        assert "/admin/teams" in resp.headers.get("location", "")

    def test_db_error_redirects_to_merge_page_with_error(self, tmp_path):
        """Non-MergeBlockedError exceptions redirect back to merge page with error."""
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            id1 = _insert_team(conn, "Canonical", season_year=2026)
            id2 = _insert_team(conn, "Duplicate", season_year=2026)

        _, env = _make_client(db_path)
        with patch("src.api.routes.admin._run_merge_teams", side_effect=sqlite3.OperationalError("database is locked")):
            resp = self._csrf_post(
                db_path,
                {
                    "canonical_id": str(id1),
                    "duplicate_id": str(id2),
                    "team_ids_str": f"{id1},{id2}",
                },
                env,
            )

        assert resp.status_code == 303
        location = resp.headers.get("location", "")
        assert "/admin/teams/merge" in location
        assert "error" in location
        # Error message must reference database error (URL-encoded)
        assert "Database" in location or "database" in location.lower()


# ---------------------------------------------------------------------------
# AC-4: CSRF protection
# ---------------------------------------------------------------------------


class TestCSRFProtection:
    """AC-4: POST without valid CSRF token returns 403."""

    def test_post_without_csrf_cookie_returns_403(self, tmp_path):
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            id1 = _insert_team(conn, "CSRF Team", season_year=2026)
            id2 = _insert_team(conn, "CSRF Team", season_year=2026)

        _, env = _make_client(db_path)
        with patch.dict("os.environ", env):
            with TestClient(app) as c:
                resp = c.post(
                    "/admin/teams/merge",
                    data={
                        "canonical_id": str(id1),
                        "duplicate_id": str(id2),
                        "team_ids_str": f"{id1},{id2}",
                        "csrf_token": "bad-token",
                        # No csrf_token cookie set
                    },
                    follow_redirects=False,
                )

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# AC-5: Blocking issues disable confirm button
# ---------------------------------------------------------------------------


class TestBlockingIssues:
    """AC-5: Confirm Merge is disabled when preview has blocking issues."""

    def test_confirm_disabled_when_duplicate_is_member(self, tmp_path):
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            id1 = _insert_team(conn, "Canonical", season_year=2026)
            id2 = _insert_team(conn, "Member Dup", membership_type="member", season_year=2026)

        _, env = _make_client(db_path)
        with patch.dict("os.environ", env):
            with TestClient(app) as c:
                resp = c.get(
                    f"/admin/teams/merge?team_ids={id1},{id2}&canonical_id={id1}"
                )

        assert resp.status_code == 200
        # The submit button should have 'disabled' attribute
        assert "disabled" in resp.text
        # Blocking issues section should appear
        assert "Blocking" in resp.text or "Cannot Merge" in resp.text


# ---------------------------------------------------------------------------
# Merge redirect flow -- teams list shows success + Sync Now button (AC-3)
# ---------------------------------------------------------------------------


class TestMergeSuccessFlash:
    """AC-3: After merge redirect, teams list shows success message and Sync Now."""

    def test_teams_page_shows_sync_now_after_merge(self, tmp_path):
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            id1 = _insert_team(conn, "Flash Team", season_year=2026)

        _, env = _make_client(db_path)
        # Simulate the redirect URL that POST /admin/teams/merge produces
        msg = "Merged Dup into Flash Team. Stats will update on next sync."
        from urllib.parse import quote_plus
        url = f"/admin/teams?msg={quote_plus(msg)}&merged_canonical_id={id1}"

        with patch.dict("os.environ", env):
            with TestClient(app) as c:
                resp = c.get(url)

        assert resp.status_code == 200
        assert "Sync Now" in resp.text
        assert str(id1) in resp.text
