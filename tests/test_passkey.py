# synthetic-test-data
"""Tests for passkey registration and login flows (E-023-03 AC-14).

Tests cover:
- (AC-14a) Registration options: GET /auth/passkey/register returns a page
  with embedded valid JSON registration options.
- (AC-14b) Successful registration: POST /auth/passkey/register stores
  credential in passkey_credentials table.
- (AC-14c) Registration requires active session: unauthenticated request
  is redirected to /auth/login.
- (AC-14d) Authentication options: GET /auth/passkey/login/options returns
  valid JSON authentication options.
- (AC-14e) Successful passkey login: POST /auth/passkey/login/verify creates
  a session and sets a cookie.
- (AC-14f) sign_count is updated after authentication.

py_webauthn verify functions are mocked so no real WebAuthn hardware is needed.

Run with:
    pytest tests/test_passkey.py -v
"""

from __future__ import annotations

import base64
import json
import secrets
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.api.auth import hash_token  # noqa: E402
from src.api.main import app  # noqa: E402

# ---------------------------------------------------------------------------
# Full schema SQL (base + auth tables with challenge column)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS _migrations (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        filename   TEXT    NOT NULL UNIQUE,
        applied_at TEXT    NOT NULL DEFAULT (datetime('now'))
    );
    INSERT OR IGNORE INTO _migrations (filename) VALUES ('001_initial_schema.sql');

    CREATE TABLE IF NOT EXISTS players (
        player_id  TEXT PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name  TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS teams (
        team_id    TEXT PRIMARY KEY,
        name       TEXT NOT NULL,
        level      TEXT,
        is_owned   INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS team_rosters (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id       TEXT NOT NULL,
        player_id     TEXT NOT NULL,
        season        TEXT NOT NULL,
        jersey_number TEXT,
        position      TEXT,
        UNIQUE(team_id, player_id, season)
    );

    CREATE TABLE IF NOT EXISTS games (
        game_id      TEXT PRIMARY KEY,
        season       TEXT NOT NULL,
        game_date    TEXT NOT NULL,
        home_team_id TEXT NOT NULL,
        away_team_id TEXT NOT NULL,
        home_score   INTEGER,
        away_score   INTEGER,
        status       TEXT NOT NULL DEFAULT 'completed'
    );

    CREATE TABLE IF NOT EXISTS player_game_batting (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id   TEXT NOT NULL,
        player_id TEXT NOT NULL,
        team_id   TEXT NOT NULL,
        ab        INTEGER,
        h         INTEGER,
        doubles   INTEGER,
        triples   INTEGER,
        hr        INTEGER,
        rbi       INTEGER,
        bb        INTEGER,
        so        INTEGER,
        sb        INTEGER,
        UNIQUE(game_id, player_id)
    );

    CREATE TABLE IF NOT EXISTS player_game_pitching (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id   TEXT NOT NULL,
        player_id TEXT NOT NULL,
        team_id   TEXT NOT NULL,
        ip_outs   INTEGER,
        h         INTEGER,
        er        INTEGER,
        bb        INTEGER,
        so        INTEGER,
        hr        INTEGER,
        UNIQUE(game_id, player_id)
    );

    CREATE TABLE IF NOT EXISTS player_season_batting (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id TEXT NOT NULL,
        team_id   TEXT NOT NULL,
        season    TEXT NOT NULL,
        games     INTEGER,
        ab        INTEGER,
        h         INTEGER,
        doubles   INTEGER,
        triples   INTEGER,
        hr        INTEGER,
        rbi       INTEGER,
        bb        INTEGER,
        so        INTEGER,
        sb        INTEGER,
        home_ab   INTEGER,
        home_h    INTEGER,
        away_ab   INTEGER,
        away_h    INTEGER,
        vs_lhp_ab INTEGER,
        vs_lhp_h  INTEGER,
        vs_rhp_ab INTEGER,
        vs_rhp_h  INTEGER,
        UNIQUE(player_id, team_id, season)
    );

    -- Auth tables (003_auth.sql) with challenge column for WebAuthn
    CREATE TABLE IF NOT EXISTS users (
        user_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        email        TEXT    NOT NULL UNIQUE,
        display_name TEXT    NOT NULL,
        is_admin     INTEGER NOT NULL DEFAULT 0,
        created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS user_team_access (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id  INTEGER NOT NULL REFERENCES users(user_id),
        team_id  TEXT    NOT NULL REFERENCES teams(team_id),
        UNIQUE(user_id, team_id)
    );

    CREATE TABLE IF NOT EXISTS magic_link_tokens (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        token_hash TEXT    NOT NULL UNIQUE,
        user_id    INTEGER NOT NULL REFERENCES users(user_id),
        expires_at TEXT    NOT NULL,
        used_at    TEXT,
        created_at TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS passkey_credentials (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id       INTEGER NOT NULL REFERENCES users(user_id),
        credential_id BLOB    NOT NULL UNIQUE,
        public_key    BLOB    NOT NULL,
        sign_count    INTEGER NOT NULL DEFAULT 0,
        created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS sessions (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        session_token_hash  TEXT    NOT NULL UNIQUE,
        user_id             INTEGER NOT NULL REFERENCES users(user_id),
        expires_at          TEXT    NOT NULL,
        challenge           TEXT,
        created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
    );
"""

_SEED_SQL = """
    INSERT OR IGNORE INTO teams (team_id, name, level, is_owned) VALUES
        ('lsb-varsity-2026', 'LSB Varsity 2026', 'varsity', 1);
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    """Create a fully-schemed database with one team row.

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Path to the database file.
    """
    db_path = tmp_path / "test_passkey.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA_SQL)
    conn.executescript(_SEED_SQL)
    conn.commit()
    conn.close()
    return db_path


def _insert_user(db_path: Path, email: str, is_admin: int = 0) -> int:
    """Insert a user and return user_id.

    Args:
        db_path: Path to the database.
        email: User email address.
        is_admin: Admin flag.

    Returns:
        The new user_id integer.
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "INSERT INTO users (email, display_name, is_admin) VALUES (?, ?, ?)",
        (email, "Test Coach", is_admin),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def _insert_session(
    db_path: Path,
    user_id: int,
    challenge: str | None = None,
) -> str:
    """Insert a valid session row and return the raw token.

    Args:
        db_path: Path to the database.
        user_id: User to associate with this session.
        challenge: Optional base64-encoded challenge to store in the session.

    Returns:
        Raw session token (64 hex chars).
    """
    raw_token = secrets.token_hex(32)
    token_hash = hash_token(raw_token)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT INTO sessions (session_token_hash, user_id, expires_at, challenge)
        VALUES (?, ?, datetime('now', '+7 days'), ?)
        """,
        (token_hash, user_id, challenge),
    )
    conn.commit()
    conn.close()
    return raw_token


def _insert_passkey_credential(
    db_path: Path,
    user_id: int,
    credential_id: bytes | None = None,
    public_key: bytes | None = None,
    sign_count: int = 0,
) -> bytes:
    """Insert a passkey credential row and return the credential_id bytes.

    Args:
        db_path: Path to the database.
        user_id: User to associate with this credential.
        credential_id: Raw credential ID bytes (generated if not provided).
        public_key: Raw public key bytes (generated if not provided).
        sign_count: Initial sign count.

    Returns:
        The credential_id bytes used.
    """
    if credential_id is None:
        credential_id = secrets.token_bytes(32)
    if public_key is None:
        public_key = secrets.token_bytes(64)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT INTO passkey_credentials (user_id, credential_id, public_key, sign_count)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, credential_id, public_key, sign_count),
    )
    conn.commit()
    conn.close()
    return credential_id


def _b64url(data: bytes) -> str:
    """Encode bytes as base64url (no padding).

    Args:
        data: Bytes to encode.

    Returns:
        Base64url-encoded string without padding.
    """
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    """Database with full schema and one owned team."""
    return _make_db(tmp_path)


# ---------------------------------------------------------------------------
# AC-14a: Registration options endpoint returns page with valid JSON options
# ---------------------------------------------------------------------------


class TestGetPasskeyRegister:
    """GET /auth/passkey/register returns HTML with embedded WebAuthn options (AC-14a)."""

    def test_register_page_returns_200_with_valid_session(self, db: Path) -> None:
        """GET /auth/passkey/register returns 200 when authenticated (AC-14a)."""
        user_id = _insert_user(db, "register-opts@example.com")
        raw_token = _insert_session(db, user_id)

        env = {"DATABASE_PATH": str(db), "DEV_USER_EMAIL": ""}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token},
            ) as client:
                response = client.get("/auth/passkey/register")

        assert response.status_code == 200

    def test_register_page_contains_json_options(self, db: Path) -> None:
        """GET /auth/passkey/register embeds JSON registration options (AC-14a)."""
        user_id = _insert_user(db, "embed-opts@example.com")
        raw_token = _insert_session(db, user_id)

        env = {"DATABASE_PATH": str(db), "DEV_USER_EMAIL": ""}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token},
            ) as client:
                response = client.get("/auth/passkey/register")

        # The page should embed a JSON blob with a "challenge" field.
        assert "challenge" in response.text
        assert "pubKeyCredParams" in response.text or "rp" in response.text

    def test_register_page_json_has_required_fields(self, db: Path) -> None:
        """Embedded JSON must contain 'challenge', 'rp', and 'user' fields (AC-14a)."""
        user_id = _insert_user(db, "json-fields@example.com")
        raw_token = _insert_session(db, user_id)

        env = {"DATABASE_PATH": str(db), "DEV_USER_EMAIL": ""}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token},
            ) as client:
                response = client.get("/auth/passkey/register")

        # Extract JSON from the script tag.
        html = response.text
        start = html.find('id="webauthn-options"')
        assert start != -1, "webauthn-options script tag not found"
        json_start = html.find(">", start) + 1
        json_end = html.find("</script>", json_start)
        options_json = html[json_start:json_end].strip()
        options = json.loads(options_json)

        assert "challenge" in options
        assert "rp" in options
        assert "user" in options

    def test_register_page_redirects_without_session(self, db: Path) -> None:
        """GET /auth/passkey/register redirects to /auth/login without session (AC-14c)."""
        env = {"DATABASE_PATH": str(db), "DEV_USER_EMAIL": ""}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get("/auth/passkey/register")

        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]


# ---------------------------------------------------------------------------
# AC-14c: Registration requires active session
# ---------------------------------------------------------------------------


class TestPasskeyRegisterRequiresSession:
    """POST /auth/passkey/register requires an active session (AC-14c)."""

    def test_post_register_without_session_returns_401(self, db: Path) -> None:
        """POST /auth/passkey/register without session cookie returns 401."""
        env = {"DATABASE_PATH": str(db), "DEV_USER_EMAIL": ""}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(app) as client:
                response = client.post(
                    "/auth/passkey/register",
                    json={"id": "test", "rawId": "dGVzdA", "type": "public-key", "response": {}},
                )

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# AC-14b: Successful registration stores credential in passkey_credentials
# ---------------------------------------------------------------------------


class TestPostPasskeyRegister:
    """POST /auth/passkey/register stores credential on success (AC-14b)."""

    def test_successful_registration_stores_credential(self, db: Path) -> None:
        """Valid attestation response stores credential_id, public_key, sign_count (AC-14b)."""
        user_id = _insert_user(db, "store-cred@example.com")
        # Pre-store a challenge in the session
        challenge_bytes = secrets.token_bytes(32)
        challenge_b64 = base64.b64encode(challenge_bytes).decode()
        raw_token = _insert_session(db, user_id, challenge=challenge_b64)

        credential_id = secrets.token_bytes(16)
        public_key_bytes = secrets.token_bytes(64)

        # Build a mock VerifiedRegistration result
        mock_verified = MagicMock()
        mock_verified.credential_id = credential_id
        mock_verified.credential_public_key = public_key_bytes
        mock_verified.sign_count = 0

        # Fake attestation response body matching what the browser sends
        raw_id_b64url = _b64url(credential_id)
        body = {
            "id": raw_id_b64url,
            "rawId": raw_id_b64url,
            "type": "public-key",
            "response": {
                "attestationObject": _b64url(b"fake-attestation"),
                "clientDataJSON": _b64url(b'{"type":"webauthn.create","challenge":"test"}'),
            },
        }

        env = {"DATABASE_PATH": str(db), "DEV_USER_EMAIL": ""}
        with patch.dict("os.environ", env, clear=False):
            with patch(
                "src.api.routes.auth.verify_registration_response",
                return_value=mock_verified,
            ):
                with TestClient(
                    app,
                    cookies={"session": raw_token},
                ) as client:
                    response = client.post("/auth/passkey/register", json=body)

        assert response.status_code == 200
        data = response.json()
        assert "redirect" in data

        # Verify credential was stored in DB
        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT user_id, credential_id, sign_count FROM passkey_credentials WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert row[0] == user_id
        assert bytes(row[1]) == credential_id
        assert row[2] == 0

    def test_successful_registration_clears_challenge(self, db: Path) -> None:
        """After registration, the session challenge column is cleared (AC-14b)."""
        user_id = _insert_user(db, "clear-challenge@example.com")
        challenge_bytes = secrets.token_bytes(32)
        challenge_b64 = base64.b64encode(challenge_bytes).decode()
        raw_token = _insert_session(db, user_id, challenge=challenge_b64)
        token_hash = hash_token(raw_token)

        credential_id = secrets.token_bytes(16)
        mock_verified = MagicMock()
        mock_verified.credential_id = credential_id
        mock_verified.credential_public_key = secrets.token_bytes(64)
        mock_verified.sign_count = 0

        raw_id_b64url = _b64url(credential_id)
        body = {
            "id": raw_id_b64url,
            "rawId": raw_id_b64url,
            "type": "public-key",
            "response": {
                "attestationObject": _b64url(b"fake-attestation"),
                "clientDataJSON": _b64url(b'{"type":"webauthn.create","challenge":"test"}'),
            },
        }

        env = {"DATABASE_PATH": str(db), "DEV_USER_EMAIL": ""}
        with patch.dict("os.environ", env, clear=False):
            with patch(
                "src.api.routes.auth.verify_registration_response",
                return_value=mock_verified,
            ):
                with TestClient(
                    app,
                    cookies={"session": raw_token},
                ) as client:
                    client.post("/auth/passkey/register", json=body)

        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT challenge FROM sessions WHERE session_token_hash = ?",
            (token_hash,),
        )
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert row[0] is None  # challenge cleared

    def test_registration_without_challenge_returns_400(self, db: Path) -> None:
        """POST /auth/passkey/register with no stored challenge returns 400 (AC-14b)."""
        user_id = _insert_user(db, "no-challenge@example.com")
        raw_token = _insert_session(db, user_id, challenge=None)

        body = {
            "id": "dGVzdA",
            "rawId": "dGVzdA",
            "type": "public-key",
            "response": {
                "attestationObject": _b64url(b"fake"),
                "clientDataJSON": _b64url(b'{"type":"webauthn.create"}'),
            },
        }

        env = {"DATABASE_PATH": str(db), "DEV_USER_EMAIL": ""}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(
                app,
                cookies={"session": raw_token},
            ) as client:
                response = client.post("/auth/passkey/register", json=body)

        assert response.status_code == 400

    def test_registration_failure_shows_error_page(self, db: Path) -> None:
        """Failed attestation verification returns error page with 'try again' (AC-5)."""
        user_id = _insert_user(db, "fail-reg@example.com")
        challenge_bytes = secrets.token_bytes(32)
        challenge_b64 = base64.b64encode(challenge_bytes).decode()
        raw_token = _insert_session(db, user_id, challenge=challenge_b64)

        body = {
            "id": _b64url(secrets.token_bytes(16)),
            "rawId": _b64url(secrets.token_bytes(16)),
            "type": "public-key",
            "response": {
                "attestationObject": _b64url(b"bad-attestation"),
                "clientDataJSON": _b64url(b'{"type":"webauthn.create","challenge":"test"}'),
            },
        }

        env = {"DATABASE_PATH": str(db), "DEV_USER_EMAIL": ""}
        with patch.dict("os.environ", env, clear=False):
            with patch(
                "src.api.routes.auth.verify_registration_response",
                side_effect=Exception("Verification failed"),
            ):
                with TestClient(
                    app,
                    cookies={"session": raw_token},
                ) as client:
                    response = client.post("/auth/passkey/register", json=body)

        assert response.status_code == 400
        assert "try again" in response.text.lower()

    def test_multiple_passkeys_per_user(self, db: Path) -> None:
        """A user can register multiple passkeys (AC-4): separate credential rows."""
        user_id = _insert_user(db, "multi-passkey@example.com")

        cred_id_1 = secrets.token_bytes(16)
        cred_id_2 = secrets.token_bytes(16)

        for cred_id in (cred_id_1, cred_id_2):
            challenge_bytes = secrets.token_bytes(32)
            challenge_b64 = base64.b64encode(challenge_bytes).decode()
            raw_token = _insert_session(db, user_id, challenge=challenge_b64)

            mock_verified = MagicMock()
            mock_verified.credential_id = cred_id
            mock_verified.credential_public_key = secrets.token_bytes(64)
            mock_verified.sign_count = 0

            raw_id_b64url = _b64url(cred_id)
            body = {
                "id": raw_id_b64url,
                "rawId": raw_id_b64url,
                "type": "public-key",
                "response": {
                    "attestationObject": _b64url(b"fake-attestation"),
                    "clientDataJSON": _b64url(b'{"type":"webauthn.create","challenge":"x"}'),
                },
            }

            env = {"DATABASE_PATH": str(db), "DEV_USER_EMAIL": ""}
            with patch.dict("os.environ", env, clear=False):
                with patch(
                    "src.api.routes.auth.verify_registration_response",
                    return_value=mock_verified,
                ):
                    with TestClient(
                        app,
                        cookies={"session": raw_token},
                    ) as client:
                        response = client.post("/auth/passkey/register", json=body)

            assert response.status_code == 200

        # Verify two separate rows exist
        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM passkey_credentials WHERE user_id = ?",
            (user_id,),
        )
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 2


# ---------------------------------------------------------------------------
# AC-14d: Authentication options endpoint returns valid JSON
# ---------------------------------------------------------------------------


class TestGetPasskeyLoginOptions:
    """GET /auth/passkey/login/options returns valid JSON authentication options (AC-14d)."""

    def test_login_options_returns_200(self, db: Path) -> None:
        """GET /auth/passkey/login/options returns 200 (AC-14d)."""
        env = {"DATABASE_PATH": str(db)}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(app) as client:
                response = client.get("/auth/passkey/login/options")

        assert response.status_code == 200

    def test_login_options_content_type_json(self, db: Path) -> None:
        """GET /auth/passkey/login/options returns JSON content type (AC-14d)."""
        env = {"DATABASE_PATH": str(db)}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(app) as client:
                response = client.get("/auth/passkey/login/options")

        assert "application/json" in response.headers.get("content-type", "")

    def test_login_options_has_challenge(self, db: Path) -> None:
        """Authentication options JSON contains a 'challenge' field (AC-14d)."""
        env = {"DATABASE_PATH": str(db)}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(app) as client:
                response = client.get("/auth/passkey/login/options")

        data = response.json()
        assert "challenge" in data
        assert len(data["challenge"]) > 0

    def test_login_options_has_rp_id(self, db: Path) -> None:
        """Authentication options JSON contains 'rpId' field (AC-14d)."""
        env = {"DATABASE_PATH": str(db), "WEBAUTHN_RP_ID": "localhost"}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(app) as client:
                response = client.get("/auth/passkey/login/options")

        data = response.json()
        assert "rpId" in data
        assert data["rpId"] == "localhost"

    def test_login_options_allow_credentials_empty(self, db: Path) -> None:
        """Authentication options allowCredentials is empty (discoverable credentials, AC-7)."""
        env = {"DATABASE_PATH": str(db)}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(app) as client:
                response = client.get("/auth/passkey/login/options")

        data = response.json()
        assert data.get("allowCredentials", []) == []


# ---------------------------------------------------------------------------
# AC-14e: Successful passkey login creates session
# AC-14f: sign_count is updated after authentication
# ---------------------------------------------------------------------------


class TestPostPasskeyLoginVerify:
    """POST /auth/passkey/login/verify verifies assertion and creates session (AC-14e, AC-14f)."""

    def _make_fake_client_data(self, challenge_b64url: str) -> bytes:
        """Build a fake clientDataJSON matching the given challenge.

        Args:
            challenge_b64url: Base64url-encoded challenge (as returned in options).

        Returns:
            JSON-encoded clientDataJSON bytes.
        """
        client_data = {
            "type": "webauthn.get",
            "challenge": challenge_b64url,
            "origin": "http://localhost:8000",
        }
        return json.dumps(client_data).encode()

    def test_successful_login_creates_session(self, db: Path) -> None:
        """Valid assertion creates a session row and sets session cookie (AC-14e)."""
        user_id = _insert_user(db, "passkey-login@example.com")
        credential_id = secrets.token_bytes(16)
        public_key_bytes = secrets.token_bytes(64)
        _insert_passkey_credential(
            db, user_id, credential_id=credential_id, public_key=public_key_bytes, sign_count=5
        )

        # First call login/options to get a challenge stored server-side
        env = {
            "DATABASE_PATH": str(db),
            "WEBAUTHN_RP_ID": "localhost",
            "WEBAUTHN_ORIGIN": "http://localhost:8000",
            "DEV_USER_EMAIL": "",
        }

        raw_id_b64url = _b64url(credential_id)

        # Mock the authentication options to get a known challenge
        challenge_bytes = secrets.token_bytes(32)
        challenge_b64url = _b64url(challenge_bytes)
        challenge_b64 = base64.b64encode(challenge_bytes).decode()

        client_data_bytes = self._make_fake_client_data(challenge_b64url)
        client_data_b64url = _b64url(client_data_bytes)

        # Build fake assertion body
        body = {
            "id": raw_id_b64url,
            "rawId": raw_id_b64url,
            "type": "public-key",
            "response": {
                "authenticatorData": _b64url(secrets.token_bytes(37)),
                "clientDataJSON": client_data_b64url,
                "signature": _b64url(secrets.token_bytes(64)),
                "userHandle": None,
            },
        }

        # Mock VerifiedAuthentication result
        mock_verified = MagicMock()
        mock_verified.new_sign_count = 6

        with patch.dict("os.environ", env, clear=False):
            # Pre-populate the challenge store
            with patch.dict(
                "src.api.routes.auth._PASSKEY_LOGIN_CHALLENGES",
                {challenge_b64: __import__("time").time() + 300},
                clear=False,
            ):
                with patch(
                    "src.api.routes.auth.verify_authentication_response",
                    return_value=mock_verified,
                ):
                    with TestClient(app, follow_redirects=False) as client:
                        response = client.post(
                            "/auth/passkey/login/verify", json=body
                        )

        assert response.status_code == 200
        data = response.json()
        assert "redirect" in data
        assert "session" in response.cookies

    def test_successful_login_inserts_session_row(self, db: Path) -> None:
        """Successful passkey login inserts a sessions row (AC-14e)."""
        user_id = _insert_user(db, "login-row@example.com")
        credential_id = secrets.token_bytes(16)
        public_key_bytes = secrets.token_bytes(64)
        _insert_passkey_credential(
            db, user_id, credential_id=credential_id, public_key=public_key_bytes, sign_count=0
        )

        challenge_bytes = secrets.token_bytes(32)
        challenge_b64url = _b64url(challenge_bytes)
        challenge_b64 = base64.b64encode(challenge_bytes).decode()
        client_data_bytes = self._make_fake_client_data(challenge_b64url)

        raw_id_b64url = _b64url(credential_id)
        body = {
            "id": raw_id_b64url,
            "rawId": raw_id_b64url,
            "type": "public-key",
            "response": {
                "authenticatorData": _b64url(secrets.token_bytes(37)),
                "clientDataJSON": _b64url(client_data_bytes),
                "signature": _b64url(secrets.token_bytes(64)),
                "userHandle": None,
            },
        }

        mock_verified = MagicMock()
        mock_verified.new_sign_count = 1

        env = {
            "DATABASE_PATH": str(db),
            "WEBAUTHN_RP_ID": "localhost",
            "WEBAUTHN_ORIGIN": "http://localhost:8000",
            "DEV_USER_EMAIL": "",
        }

        with patch.dict("os.environ", env, clear=False):
            with patch.dict(
                "src.api.routes.auth._PASSKEY_LOGIN_CHALLENGES",
                {challenge_b64: __import__("time").time() + 300},
                clear=False,
            ):
                with patch(
                    "src.api.routes.auth.verify_authentication_response",
                    return_value=mock_verified,
                ):
                    with TestClient(app, follow_redirects=False) as client:
                        client.post("/auth/passkey/login/verify", json=body)

        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 1

    def test_successful_login_updates_sign_count(self, db: Path) -> None:
        """sign_count in passkey_credentials is updated after authentication (AC-14f)."""
        user_id = _insert_user(db, "sign-count@example.com")
        credential_id = secrets.token_bytes(16)
        public_key_bytes = secrets.token_bytes(64)
        initial_sign_count = 10
        _insert_passkey_credential(
            db,
            user_id,
            credential_id=credential_id,
            public_key=public_key_bytes,
            sign_count=initial_sign_count,
        )

        challenge_bytes = secrets.token_bytes(32)
        challenge_b64url = _b64url(challenge_bytes)
        challenge_b64 = base64.b64encode(challenge_bytes).decode()
        client_data_bytes = self._make_fake_client_data(challenge_b64url)

        raw_id_b64url = _b64url(credential_id)
        body = {
            "id": raw_id_b64url,
            "rawId": raw_id_b64url,
            "type": "public-key",
            "response": {
                "authenticatorData": _b64url(secrets.token_bytes(37)),
                "clientDataJSON": _b64url(client_data_bytes),
                "signature": _b64url(secrets.token_bytes(64)),
                "userHandle": None,
            },
        }

        new_sign_count = 11
        mock_verified = MagicMock()
        mock_verified.new_sign_count = new_sign_count

        env = {
            "DATABASE_PATH": str(db),
            "WEBAUTHN_RP_ID": "localhost",
            "WEBAUTHN_ORIGIN": "http://localhost:8000",
            "DEV_USER_EMAIL": "",
        }

        with patch.dict("os.environ", env, clear=False):
            with patch.dict(
                "src.api.routes.auth._PASSKEY_LOGIN_CHALLENGES",
                {challenge_b64: __import__("time").time() + 300},
                clear=False,
            ):
                with patch(
                    "src.api.routes.auth.verify_authentication_response",
                    return_value=mock_verified,
                ):
                    with TestClient(app, follow_redirects=False) as client:
                        client.post("/auth/passkey/login/verify", json=body)

        conn = sqlite3.connect(str(db))
        cursor = conn.execute(
            "SELECT sign_count FROM passkey_credentials WHERE credential_id = ?",
            (credential_id,),
        )
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert row[0] == new_sign_count

    def test_failed_login_returns_json_error(self, db: Path) -> None:
        """Failed passkey verification returns JSON error (AC-10)."""
        user_id = _insert_user(db, "fail-login@example.com")
        credential_id = secrets.token_bytes(16)
        _insert_passkey_credential(db, user_id, credential_id=credential_id)

        challenge_bytes = secrets.token_bytes(32)
        challenge_b64url = _b64url(challenge_bytes)
        challenge_b64 = base64.b64encode(challenge_bytes).decode()
        client_data_bytes = self._make_fake_client_data(challenge_b64url)

        raw_id_b64url = _b64url(credential_id)
        body = {
            "id": raw_id_b64url,
            "rawId": raw_id_b64url,
            "type": "public-key",
            "response": {
                "authenticatorData": _b64url(secrets.token_bytes(37)),
                "clientDataJSON": _b64url(client_data_bytes),
                "signature": _b64url(b"bad-sig"),
                "userHandle": None,
            },
        }

        env = {
            "DATABASE_PATH": str(db),
            "WEBAUTHN_RP_ID": "localhost",
            "WEBAUTHN_ORIGIN": "http://localhost:8000",
            "DEV_USER_EMAIL": "",
        }

        with patch.dict("os.environ", env, clear=False):
            with patch.dict(
                "src.api.routes.auth._PASSKEY_LOGIN_CHALLENGES",
                {challenge_b64: __import__("time").time() + 300},
                clear=False,
            ):
                with patch(
                    "src.api.routes.auth.verify_authentication_response",
                    side_effect=Exception("Invalid signature"),
                ):
                    with TestClient(app) as client:
                        response = client.post(
                            "/auth/passkey/login/verify", json=body
                        )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "failed" in data["detail"].lower() or "passkey" in data["detail"].lower()

    def test_login_unknown_credential_returns_error(self, db: Path) -> None:
        """POST /auth/passkey/login/verify with unregistered credential returns 401."""
        unknown_cred_id = secrets.token_bytes(16)
        raw_id_b64url = _b64url(unknown_cred_id)

        challenge_bytes = secrets.token_bytes(32)
        challenge_b64url = _b64url(challenge_bytes)
        challenge_b64 = base64.b64encode(challenge_bytes).decode()
        client_data = json.dumps({
            "type": "webauthn.get",
            "challenge": challenge_b64url,
            "origin": "http://localhost:8000",
        }).encode()

        body = {
            "id": raw_id_b64url,
            "rawId": raw_id_b64url,
            "type": "public-key",
            "response": {
                "authenticatorData": _b64url(secrets.token_bytes(37)),
                "clientDataJSON": _b64url(client_data),
                "signature": _b64url(secrets.token_bytes(64)),
                "userHandle": None,
            },
        }

        env = {
            "DATABASE_PATH": str(db),
            "DEV_USER_EMAIL": "",
        }

        with patch.dict("os.environ", env, clear=False):
            with patch.dict(
                "src.api.routes.auth._PASSKEY_LOGIN_CHALLENGES",
                {challenge_b64: __import__("time").time() + 300},
                clear=False,
            ):
                with TestClient(app) as client:
                    response = client.post("/auth/passkey/login/verify", json=body)

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# AC-1: verify redirect checks for passkey presence
# ---------------------------------------------------------------------------


class TestVerifyRedirectsToPromptWhenNoPasskeys:
    """After magic-link verify, redirect depends on passkey status (AC-1)."""

    def _insert_magic_token(
        self,
        db_path: Path,
        user_id: int,
        expired: bool = False,
        used: bool = False,
    ) -> str:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hash_token(raw_token)
        expires_offset = "-1 hour" if expired else "+15 minutes"
        used_at_expr = "datetime('now')" if used else "NULL"

        conn = sqlite3.connect(str(db_path))
        conn.execute(
            f"""
            INSERT INTO magic_link_tokens (token_hash, user_id, expires_at, used_at)
            VALUES (?, ?, datetime('now', '{expires_offset}'), {used_at_expr})
            """,
            (token_hash, user_id),
        )
        conn.commit()
        conn.close()
        return raw_token

    def test_verify_redirects_to_prompt_when_no_passkeys(self, db: Path) -> None:
        """User with no passkeys is redirected to /auth/passkey/prompt (AC-1)."""
        user_id = _insert_user(db, "nopk@example.com")
        raw_token = self._insert_magic_token(db, user_id)

        env = {"DATABASE_PATH": str(db), "DEV_USER_EMAIL": ""}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get(f"/auth/verify?token={raw_token}")

        assert response.status_code == 302
        assert "/auth/passkey/prompt" in response.headers["location"]

    def test_verify_redirects_to_dashboard_when_has_passkeys(self, db: Path) -> None:
        """User with passkeys is redirected directly to /dashboard (AC-1)."""
        user_id = _insert_user(db, "haspk@example.com")
        _insert_passkey_credential(db, user_id)
        raw_token = self._insert_magic_token(db, user_id)

        env = {"DATABASE_PATH": str(db), "DEV_USER_EMAIL": ""}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get(f"/auth/verify?token={raw_token}")

        assert response.status_code == 302
        assert "/dashboard" in response.headers["location"]
