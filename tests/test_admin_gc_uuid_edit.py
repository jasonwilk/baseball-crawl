# synthetic-test-data
"""Tests for gc_uuid editing on the admin Edit Team page -- E-151-01.

Tests cover AC-9 sub-items:
(a) valid UUID saves successfully.
(b) empty input stores NULL.
(c) malformed new UUID is rejected with error.
(d) duplicate UUID is rejected with error.
(e) existing fields are unaffected when gc_uuid is added/changed.
(f) mixed-case UUID is normalized to lowercase before storage.
(g) unchanged placeholder gc_uuid is preserved without validation error.

Run with:
    pytest tests/test_admin_gc_uuid_edit.py -v
"""

from __future__ import annotations

import secrets
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from migrations.apply_migrations import run_migrations  # noqa: E402
from src.api.auth import hash_token  # noqa: E402
from src.api.main import app  # noqa: E402

_CSRF = "test-csrf-token"

_VALID_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
_VALID_UUID_2 = "11111111-2222-3333-4444-555566667777"
_PLACEHOLDER = "lsb-varsity-uuid-2026"

_SEED_SQL = """
    INSERT OR IGNORE INTO programs (program_id, name, program_type)
        VALUES ('lsb-hs', 'Lincoln Standing Bear HS', 'hs');
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    """Create a migrated test database with seed data."""
    db_path = tmp_path / "test_gc_uuid.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(_SEED_SQL)
    conn.commit()
    conn.close()
    return db_path


def _insert_user(db_path: Path, email: str) -> int:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    cursor = conn.execute(
        "INSERT INTO users (email, hashed_password) VALUES (?, '')", (email,)
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def _insert_session(db_path: Path, user_id: int) -> str:
    raw_token = secrets.token_hex(32)
    token_hash = hash_token(raw_token)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        """
        INSERT INTO sessions (session_id, user_id, expires_at)
        VALUES (?, ?, datetime('now', '+7 days'))
        """,
        (token_hash, user_id),
    )
    conn.commit()
    conn.close()
    return raw_token


def _insert_team(
    db_path: Path,
    name: str,
    gc_uuid: str | None = None,
    membership_type: str = "member",
) -> int:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    cursor = conn.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid) VALUES (?, ?, ?)",
        (name, membership_type, gc_uuid),
    )
    conn.commit()
    team_id = cursor.lastrowid
    conn.close()
    return team_id


def _fetch_gc_uuid(db_path: Path, team_id: int) -> str | None:
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT gc_uuid FROM teams WHERE id = ?", (team_id,)).fetchone()
    conn.close()
    return row[0] if row else None


def _admin_env(db_path: Path, email: str = "admin@example.com") -> dict[str, str]:
    return {"DATABASE_PATH": str(db_path), "ADMIN_EMAIL": email}


def _post_edit(
    client: TestClient,
    team_id: int,
    *,
    name: str = "Team Name",
    gc_uuid: str = "",
    program_id: str = "",
    classification: str = "",
    membership_type: str = "member",
) -> object:
    return client.post(
        f"/admin/teams/{team_id}/edit",
        data={
            "name": name,
            "gc_uuid": gc_uuid,
            "program_id": program_id,
            "classification": classification,
            "membership_type": membership_type,
            "csrf_token": _CSRF,
        },
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def gc_db(tmp_path: Path) -> Path:
    return _make_db(tmp_path)


# ---------------------------------------------------------------------------
# AC-9a: Valid UUID saves successfully
# ---------------------------------------------------------------------------


class TestValidUuidSaves:
    """AC-9a: Valid UUID saves and redirects."""

    def test_valid_uuid_redirects_and_persists(self, gc_db: Path) -> None:
        """New valid UUID is saved to DB and handler redirects to /admin/teams."""
        user_id = _insert_user(gc_db, "admin@example.com")
        token = _insert_session(gc_db, user_id)
        team_id = _insert_team(gc_db, "LSB Varsity")

        with patch.dict("os.environ", _admin_env(gc_db)):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                response = _post_edit(client, team_id, name="LSB Varsity", gc_uuid=_VALID_UUID)

        assert response.status_code == 303
        assert response.headers["location"].startswith("/admin/teams")
        assert _fetch_gc_uuid(gc_db, team_id) == _VALID_UUID

    def test_changed_uuid_replaces_existing(self, gc_db: Path) -> None:
        """Changing from one valid UUID to another saves the new value."""
        user_id = _insert_user(gc_db, "admin@example.com")
        token = _insert_session(gc_db, user_id)
        team_id = _insert_team(gc_db, "LSB Varsity", gc_uuid=_VALID_UUID)

        with patch.dict("os.environ", _admin_env(gc_db)):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                response = _post_edit(client, team_id, name="LSB Varsity", gc_uuid=_VALID_UUID_2)

        assert response.status_code == 303
        assert _fetch_gc_uuid(gc_db, team_id) == _VALID_UUID_2


# ---------------------------------------------------------------------------
# AC-9b: Empty input stores NULL
# ---------------------------------------------------------------------------


class TestEmptyUuidStoresNull:
    """AC-9b: Empty gc_uuid field sets the column to NULL."""

    def test_empty_input_stores_null(self, gc_db: Path) -> None:
        """Submitting empty gc_uuid clears existing value to NULL."""
        user_id = _insert_user(gc_db, "admin@example.com")
        token = _insert_session(gc_db, user_id)
        team_id = _insert_team(gc_db, "LSB Varsity", gc_uuid=_VALID_UUID)

        with patch.dict("os.environ", _admin_env(gc_db)):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                response = _post_edit(client, team_id, name="LSB Varsity", gc_uuid="")

        assert response.status_code == 303
        assert _fetch_gc_uuid(gc_db, team_id) is None

    def test_whitespace_only_stores_null(self, gc_db: Path) -> None:
        """Whitespace-only input is treated as empty and stores NULL."""
        user_id = _insert_user(gc_db, "admin@example.com")
        token = _insert_session(gc_db, user_id)
        team_id = _insert_team(gc_db, "LSB Varsity", gc_uuid=_VALID_UUID)

        with patch.dict("os.environ", _admin_env(gc_db)):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                response = _post_edit(client, team_id, name="LSB Varsity", gc_uuid="   ")

        assert response.status_code == 303
        assert _fetch_gc_uuid(gc_db, team_id) is None


# ---------------------------------------------------------------------------
# AC-9c: Malformed new UUID is rejected with error
# ---------------------------------------------------------------------------


class TestMalformedUuidRejected:
    """AC-9c: Malformed new UUID re-renders form with error, no DB update."""

    def test_malformed_uuid_returns_200_with_error(self, gc_db: Path) -> None:
        """Submitting a malformed UUID re-renders form with error banner."""
        user_id = _insert_user(gc_db, "admin@example.com")
        token = _insert_session(gc_db, user_id)
        team_id = _insert_team(gc_db, "LSB Varsity")

        with patch.dict("os.environ", _admin_env(gc_db)):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                response = _post_edit(
                    client, team_id, name="LSB Varsity", gc_uuid="not-a-uuid"
                )

        assert response.status_code == 200
        assert "Invalid UUID format" in response.text

    def test_malformed_uuid_does_not_update_db(self, gc_db: Path) -> None:
        """Malformed UUID leaves existing gc_uuid unchanged in the database."""
        user_id = _insert_user(gc_db, "admin@example.com")
        token = _insert_session(gc_db, user_id)
        team_id = _insert_team(gc_db, "LSB Varsity", gc_uuid=_VALID_UUID)

        with patch.dict("os.environ", _admin_env(gc_db)):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                _post_edit(client, team_id, name="LSB Varsity", gc_uuid="bad-uuid-value")

        assert _fetch_gc_uuid(gc_db, team_id) == _VALID_UUID

    def test_malformed_uuid_preserves_submitted_name(self, gc_db: Path) -> None:
        """Form re-render preserves other submitted field values."""
        user_id = _insert_user(gc_db, "admin@example.com")
        token = _insert_session(gc_db, user_id)
        team_id = _insert_team(gc_db, "LSB Varsity")

        with patch.dict("os.environ", _admin_env(gc_db)):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                response = _post_edit(
                    client,
                    team_id,
                    name="Updated Name",
                    gc_uuid="bad-uuid",
                )

        assert response.status_code == 200
        assert "Updated Name" in response.text


# ---------------------------------------------------------------------------
# AC-9d: Duplicate UUID is rejected with error
# ---------------------------------------------------------------------------


class TestDuplicateUuidRejected:
    """AC-9d: UUID already assigned to another team re-renders form with error."""

    def test_duplicate_uuid_returns_200_with_error(self, gc_db: Path) -> None:
        """Duplicate UUID re-renders form with uniqueness error banner."""
        user_id = _insert_user(gc_db, "admin@example.com")
        token = _insert_session(gc_db, user_id)
        _insert_team(gc_db, "Other Team", gc_uuid=_VALID_UUID)
        team_id = _insert_team(gc_db, "LSB Varsity")

        with patch.dict("os.environ", _admin_env(gc_db)):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                response = _post_edit(
                    client, team_id, name="LSB Varsity", gc_uuid=_VALID_UUID
                )

        assert response.status_code == 200
        assert "already assigned" in response.text

    def test_duplicate_uuid_does_not_update_db(self, gc_db: Path) -> None:
        """Duplicate UUID leaves the target team's gc_uuid unchanged."""
        user_id = _insert_user(gc_db, "admin@example.com")
        token = _insert_session(gc_db, user_id)
        _insert_team(gc_db, "Other Team", gc_uuid=_VALID_UUID)
        team_id = _insert_team(gc_db, "LSB Varsity", gc_uuid=_VALID_UUID_2)

        with patch.dict("os.environ", _admin_env(gc_db)):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                _post_edit(client, team_id, name="LSB Varsity", gc_uuid=_VALID_UUID)

        assert _fetch_gc_uuid(gc_db, team_id) == _VALID_UUID_2

    def test_uppercase_stored_on_other_team_blocks_lowercase_save(
        self, gc_db: Path
    ) -> None:
        """Lowercase UUID is blocked when the same UUID is stored uppercase on another team."""
        user_id = _insert_user(gc_db, "admin@example.com")
        token = _insert_session(gc_db, user_id)
        # Store the UUID in uppercase on a different team.
        _insert_team(gc_db, "Other Team", gc_uuid=_VALID_UUID.upper())
        team_id = _insert_team(gc_db, "LSB Varsity")

        with patch.dict("os.environ", _admin_env(gc_db)):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                response = _post_edit(
                    client, team_id, name="LSB Varsity", gc_uuid=_VALID_UUID
                )

        assert response.status_code == 200
        assert "already assigned" in response.text
        assert _fetch_gc_uuid(gc_db, team_id) is None


# ---------------------------------------------------------------------------
# AC-9e: Existing fields unaffected
# ---------------------------------------------------------------------------


class TestExistingFieldsUnaffected:
    """AC-9e: Other fields are preserved when gc_uuid is added/changed."""

    def test_name_and_classification_preserved_on_gc_uuid_add(
        self, gc_db: Path
    ) -> None:
        """Adding a new gc_uuid does not alter unrelated team columns."""
        user_id = _insert_user(gc_db, "admin@example.com")
        token = _insert_session(gc_db, user_id)
        conn = sqlite3.connect(str(gc_db))
        conn.execute("PRAGMA foreign_keys=ON;")
        cursor = conn.execute(
            """
            INSERT INTO teams (name, membership_type, classification, program_id)
            VALUES ('LSB Varsity', 'member', 'varsity', 'lsb-hs')
            """
        )
        team_id = cursor.lastrowid
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(gc_db)):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                response = _post_edit(
                    client,
                    team_id,
                    name="LSB Varsity",
                    gc_uuid=_VALID_UUID,
                    program_id="lsb-hs",
                    classification="varsity",
                    membership_type="member",
                )

        assert response.status_code == 303
        conn = sqlite3.connect(str(gc_db))
        row = conn.execute(
            "SELECT name, classification, program_id, membership_type, gc_uuid FROM teams WHERE id = ?",
            (team_id,),
        ).fetchone()
        conn.close()
        assert row[0] == "LSB Varsity"
        assert row[1] == "varsity"
        assert row[2] == "lsb-hs"
        assert row[3] == "member"
        assert row[4] == _VALID_UUID


# ---------------------------------------------------------------------------
# AC-9f: Mixed-case UUID normalized to lowercase
# ---------------------------------------------------------------------------


class TestUuidNormalization:
    """AC-9f: Mixed-case or padded UUID is normalized before storage."""

    def test_uppercase_uuid_stored_lowercase(self, gc_db: Path) -> None:
        """Uppercase UUID is lowercased before being stored."""
        user_id = _insert_user(gc_db, "admin@example.com")
        token = _insert_session(gc_db, user_id)
        team_id = _insert_team(gc_db, "LSB Varsity")

        upper_uuid = _VALID_UUID.upper()

        with patch.dict("os.environ", _admin_env(gc_db)):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                response = _post_edit(
                    client, team_id, name="LSB Varsity", gc_uuid=upper_uuid
                )

        assert response.status_code == 303
        assert _fetch_gc_uuid(gc_db, team_id) == _VALID_UUID

    def test_leading_trailing_whitespace_trimmed(self, gc_db: Path) -> None:
        """UUID with surrounding whitespace is trimmed before validation and storage."""
        user_id = _insert_user(gc_db, "admin@example.com")
        token = _insert_session(gc_db, user_id)
        team_id = _insert_team(gc_db, "LSB Varsity")

        with patch.dict("os.environ", _admin_env(gc_db)):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                response = _post_edit(
                    client, team_id, name="LSB Varsity", gc_uuid=f"  {_VALID_UUID}  "
                )

        assert response.status_code == 303
        assert _fetch_gc_uuid(gc_db, team_id) == _VALID_UUID


# ---------------------------------------------------------------------------
# AC-9g: Unchanged placeholder gc_uuid preserved without validation error
# ---------------------------------------------------------------------------


class TestPlaceholderPreserved:
    """AC-9g: Legacy non-UUID placeholder is preserved when unchanged."""

    def test_unchanged_placeholder_saves_without_error(self, gc_db: Path) -> None:
        """Saving other fields without touching a placeholder gc_uuid succeeds."""
        user_id = _insert_user(gc_db, "admin@example.com")
        token = _insert_session(gc_db, user_id)
        team_id = _insert_team(gc_db, "LSB Varsity", gc_uuid=_PLACEHOLDER)

        with patch.dict("os.environ", _admin_env(gc_db)):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                response = _post_edit(
                    client,
                    team_id,
                    name="LSB Varsity Updated Name",
                    gc_uuid=_PLACEHOLDER,
                )

        assert response.status_code == 303
        assert _fetch_gc_uuid(gc_db, team_id) == _PLACEHOLDER

    def test_unchanged_placeholder_preserves_other_edits(self, gc_db: Path) -> None:
        """Name change is persisted even when placeholder gc_uuid is unchanged."""
        user_id = _insert_user(gc_db, "admin@example.com")
        token = _insert_session(gc_db, user_id)
        team_id = _insert_team(gc_db, "LSB Varsity", gc_uuid=_PLACEHOLDER)

        with patch.dict("os.environ", _admin_env(gc_db)):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                _post_edit(
                    client,
                    team_id,
                    name="New Team Name",
                    gc_uuid=_PLACEHOLDER,
                )

        conn = sqlite3.connect(str(gc_db))
        row = conn.execute(
            "SELECT name, gc_uuid FROM teams WHERE id = ?", (team_id,)
        ).fetchone()
        conn.close()
        assert row[0] == "New Team Name"
        assert row[1] == _PLACEHOLDER
