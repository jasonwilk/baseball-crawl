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

E-100 schema notes:
    - sessions: session_id TEXT PK (no challenge column, no id)
    - users: id INTEGER PK (no user_id alias)
    - passkey_credentials: credential_id TEXT PK (no id column)
    - Passkey login AND registration challenges are stored in the TTL'd
      ``webauthn_challenges`` table (migration 004) via the
      ``src.api.passkey_challenges`` helper -- login keyed by the challenge_b64
      itself, registration keyed by the SHA-256 of the session cookie token.
      (E-238-06 replaced the former in-process ``_PASSKEY_*`` module dicts.)

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

from migrations.apply_migrations import run_migrations  # noqa: E402
from src.api import passkey_challenges  # noqa: E402
from src.api.auth import hash_token  # noqa: E402
from src.api.csrf import CSRF_COOKIE_NAME, CSRF_HEADER  # noqa: E402
from src.api.main import app  # noqa: E402

_CSRF = "test-csrf-token-passkey"
_CSRF_COOKIES = {CSRF_COOKIE_NAME: _CSRF}

_SEED_SQL = """
    INSERT OR IGNORE INTO programs (program_id, name, program_type) VALUES
        ('lsb-hs', 'Lincoln Standing Bear HS', 'hs');
    INSERT OR IGNORE INTO teams (name, membership_type, classification) VALUES
        ('LSB Varsity 2026', 'member', 'varsity');
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    """Create a fully-schemed E-100 database with one team row.

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Path to the database file.
    """
    db_path = tmp_path / "test_passkey.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SEED_SQL)
    conn.commit()
    conn.close()
    return db_path


def _insert_user(db_path: Path, email: str) -> int:
    """Insert a user and return user id.

    Args:
        db_path: Path to the database.
        email: User email address.

    Returns:
        The new user id integer (INTEGER PK).
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "INSERT INTO users (email) VALUES (?)",
        (email,),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def _insert_session(
    db_path: Path,
    user_id: int,
) -> str:
    """Insert a valid session row and return the raw token.

    In E-100 schema, sessions has no challenge column. Passkey registration
    challenges are stored in the webauthn_challenges table (migration 004),
    keyed by SHA-256 of the cookie token.

    Args:
        db_path: Path to the database.
        user_id: User to associate with this session.

    Returns:
        Raw session token (64 hex chars).
    """
    raw_token = secrets.token_hex(32)
    session_id = hash_token(raw_token)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT INTO sessions (session_id, user_id, expires_at)
        VALUES (?, ?, datetime('now', '+7 days'))
        """,
        (session_id, user_id),
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

    In E-100 schema, passkey_credentials has credential_id TEXT PRIMARY KEY
    (stored as bytes blob via sqlite3 BLOB affinity).

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


def _seed_challenge(
    db_path: Path,
    kind: str,
    lookup_key: str,
    challenge_b64: str,
    *,
    expired: bool = False,
) -> None:
    """Insert a row into the webauthn_challenges table.

    Replaces the former ``patch.dict(auth_routes._PASSKEY_*)`` monkeypatches:
    challenges now live in SQLite (migration 004), keyed by (kind, lookup_key).

    Args:
        db_path: Path to the database.
        kind: ``'login'`` or ``'registration'``.
        lookup_key: login -> the challenge_b64 itself; registration -> the
            session-id hash.
        challenge_b64: Standard-base64 challenge string to store.
        expired: If True, sets ``expires_at`` one minute in the past so the
            read-side TTL gate rejects it.
    """
    expires_clause = (
        "datetime('now', '-1 minute')" if expired else "datetime('now', '+5 minutes')"
    )
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        f"""
        INSERT INTO webauthn_challenges (kind, lookup_key, challenge, expires_at)
        VALUES (?, ?, ?, {expires_clause})
        ON CONFLICT(kind, lookup_key) DO UPDATE SET
            challenge = excluded.challenge,
            expires_at = excluded.expires_at
        """,
        (kind, lookup_key, challenge_b64),
    )
    conn.commit()
    conn.close()


def _challenge_exists(db_path: Path, kind: str, lookup_key: str) -> bool:
    """Return True if a (kind, lookup_key) row exists in webauthn_challenges.

    Used to assert consume (DELETE-on-consume) behavior. Ignores TTL -- this
    checks raw row presence, not liveness.

    Args:
        db_path: Path to the database.
        kind: ``'login'`` or ``'registration'``.
        lookup_key: The lookup key for the row.

    Returns:
        True if a row is present.
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "SELECT 1 FROM webauthn_challenges WHERE kind = ? AND lookup_key = ?",
        (kind, lookup_key),
    )
    found = cursor.fetchone() is not None
    conn.close()
    return found


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    """Database with full E-100 schema and one member team."""
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
                cookies={"session": raw_token, CSRF_COOKIE_NAME: _CSRF},
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
                cookies={"session": raw_token, CSRF_COOKIE_NAME: _CSRF},
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
                cookies={"session": raw_token, CSRF_COOKIE_NAME: _CSRF},
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
            with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                response = client.get("/auth/passkey/register")

        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]

    def test_register_stores_challenge_in_table(self, db: Path) -> None:
        """GET /auth/passkey/register stores the challenge in webauthn_challenges.

        In E-100 schema, there is no sessions.challenge column. The challenge
        is stored in the webauthn_challenges table (migration 004), keyed by
        the session-id hash.
        """
        user_id = _insert_user(db, "challenge-stored@example.com")
        raw_token = _insert_session(db, user_id)
        session_id = hash_token(raw_token)

        env = {"DATABASE_PATH": str(db), "DEV_USER_EMAIL": ""}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token, CSRF_COOKIE_NAME: _CSRF},
            ) as client:
                client.get("/auth/passkey/register")

        # Challenge should be present in the table, keyed by session-id hash.
        assert _challenge_exists(db, "registration", session_id)


# ---------------------------------------------------------------------------
# AC-14c: Registration requires active session
# ---------------------------------------------------------------------------


class TestPasskeyRegisterRequiresSession:
    """POST /auth/passkey/register requires an active session (AC-14c)."""

    def test_post_register_without_session_returns_401(self, db: Path) -> None:
        """POST /auth/passkey/register without session cookie returns 401."""
        env = {"DATABASE_PATH": str(db), "DEV_USER_EMAIL": ""}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
                response = client.post(
                    "/auth/passkey/register",
                    json={"id": "test", "rawId": "dGVzdA", "type": "public-key", "response": {}},
                    headers={CSRF_HEADER: _CSRF},
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
        raw_token = _insert_session(db, user_id)
        session_id = hash_token(raw_token)

        credential_id = secrets.token_bytes(16)
        public_key_bytes = secrets.token_bytes(64)

        # Build a mock VerifiedRegistration result
        mock_verified = MagicMock()
        mock_verified.credential_id = credential_id
        mock_verified.credential_public_key = public_key_bytes
        mock_verified.sign_count = 0

        # Pre-populate the in-memory challenge dict (simulates GET /register having been called).
        challenge_bytes = secrets.token_bytes(32)
        challenge_b64 = base64.b64encode(challenge_bytes).decode()

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

        # Seed the registration challenge in the table (simulates GET /register).
        _seed_challenge(db, "registration", session_id, challenge_b64)

        env = {"DATABASE_PATH": str(db), "DEV_USER_EMAIL": ""}
        with patch.dict("os.environ", env, clear=False):
            with patch(
                "src.api.routes.auth.verify_registration_response",
                return_value=mock_verified,
            ):
                with TestClient(
                    app,
                    cookies={"session": raw_token, CSRF_COOKIE_NAME: _CSRF},
                ) as client:
                    response = client.post("/auth/passkey/register", json=body, headers={CSRF_HEADER: _CSRF})

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

    def test_successful_registration_clears_challenge_from_table(self, db: Path) -> None:
        """After registration, the challenge row is DELETEd from webauthn_challenges (AC-14b)."""
        user_id = _insert_user(db, "clear-challenge@example.com")
        raw_token = _insert_session(db, user_id)
        session_id = hash_token(raw_token)

        credential_id = secrets.token_bytes(16)
        mock_verified = MagicMock()
        mock_verified.credential_id = credential_id
        mock_verified.credential_public_key = secrets.token_bytes(64)
        mock_verified.sign_count = 0

        challenge_bytes = secrets.token_bytes(32)
        challenge_b64 = base64.b64encode(challenge_bytes).decode()

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

        _seed_challenge(db, "registration", session_id, challenge_b64)

        env = {"DATABASE_PATH": str(db), "DEV_USER_EMAIL": ""}
        with patch.dict("os.environ", env, clear=False):
            with patch(
                "src.api.routes.auth.verify_registration_response",
                return_value=mock_verified,
            ):
                with TestClient(
                    app,
                    cookies={"session": raw_token, CSRF_COOKIE_NAME: _CSRF},
                ) as client:
                    client.post("/auth/passkey/register", json=body, headers={CSRF_HEADER: _CSRF})

        # Challenge should be consumed (DELETEd from the table).
        assert not _challenge_exists(db, "registration", session_id)

    def test_registration_without_challenge_returns_400(self, db: Path) -> None:
        """POST /auth/passkey/register with no stored challenge returns 400 (AC-14b)."""
        user_id = _insert_user(db, "no-challenge@example.com")
        raw_token = _insert_session(db, user_id)
        session_id = hash_token(raw_token)

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
        # No challenge seeded for this session -> the table has no row.
        with patch.dict("os.environ", env, clear=False):
            with TestClient(
                app,
                cookies={"session": raw_token, CSRF_COOKIE_NAME: _CSRF},
            ) as client:
                response = client.post("/auth/passkey/register", json=body, headers={CSRF_HEADER: _CSRF})

        assert response.status_code == 400

    def test_registration_failure_shows_error_page(self, db: Path) -> None:
        """Failed attestation verification returns error page with 'try again' (AC-5)."""
        user_id = _insert_user(db, "fail-reg@example.com")
        raw_token = _insert_session(db, user_id)
        session_id = hash_token(raw_token)

        challenge_bytes = secrets.token_bytes(32)
        challenge_b64 = base64.b64encode(challenge_bytes).decode()

        body = {
            "id": _b64url(secrets.token_bytes(16)),
            "rawId": _b64url(secrets.token_bytes(16)),
            "type": "public-key",
            "response": {
                "attestationObject": _b64url(b"bad-attestation"),
                "clientDataJSON": _b64url(b'{"type":"webauthn.create","challenge":"test"}'),
            },
        }

        _seed_challenge(db, "registration", session_id, challenge_b64)

        env = {"DATABASE_PATH": str(db), "DEV_USER_EMAIL": ""}
        with patch.dict("os.environ", env, clear=False):
            with patch(
                "src.api.routes.auth.verify_registration_response",
                side_effect=Exception("Verification failed"),
            ):
                with TestClient(
                    app,
                    cookies={"session": raw_token, CSRF_COOKIE_NAME: _CSRF},
                ) as client:
                    response = client.post("/auth/passkey/register", json=body, headers={CSRF_HEADER: _CSRF})

        assert response.status_code == 400
        assert "try again" in response.text.lower()

    def test_multiple_passkeys_per_user(self, db: Path) -> None:
        """A user can register multiple passkeys (AC-4): separate credential rows."""
        user_id = _insert_user(db, "multi-passkey@example.com")

        cred_id_1 = secrets.token_bytes(16)
        cred_id_2 = secrets.token_bytes(16)

        for cred_id in (cred_id_1, cred_id_2):
            raw_token = _insert_session(db, user_id)
            session_id = hash_token(raw_token)

            challenge_bytes = secrets.token_bytes(32)
            challenge_b64 = base64.b64encode(challenge_bytes).decode()

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

            _seed_challenge(db, "registration", session_id, challenge_b64)

            env = {"DATABASE_PATH": str(db), "DEV_USER_EMAIL": ""}
            with patch.dict("os.environ", env, clear=False):
                with patch(
                    "src.api.routes.auth.verify_registration_response",
                    return_value=mock_verified,
                ):
                    with TestClient(
                        app,
                        cookies={"session": raw_token, CSRF_COOKIE_NAME: _CSRF},
                    ) as client:
                        response = client.post("/auth/passkey/register", json=body, headers={CSRF_HEADER: _CSRF})

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
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
                response = client.get("/auth/passkey/login/options")

        assert response.status_code == 200

    def test_login_options_content_type_json(self, db: Path) -> None:
        """GET /auth/passkey/login/options returns JSON content type (AC-14d)."""
        env = {"DATABASE_PATH": str(db)}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
                response = client.get("/auth/passkey/login/options")

        assert "application/json" in response.headers.get("content-type", "")

    def test_login_options_has_challenge(self, db: Path) -> None:
        """Authentication options JSON contains a 'challenge' field (AC-14d)."""
        env = {"DATABASE_PATH": str(db)}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
                response = client.get("/auth/passkey/login/options")

        data = response.json()
        assert "challenge" in data
        assert len(data["challenge"]) > 0

    def test_login_options_has_rp_id(self, db: Path) -> None:
        """Authentication options JSON contains 'rpId' field (AC-14d)."""
        env = {"DATABASE_PATH": str(db), "WEBAUTHN_RP_ID": "localhost"}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
                response = client.get("/auth/passkey/login/options")

        data = response.json()
        assert "rpId" in data
        assert data["rpId"] == "localhost"

    def test_login_options_allow_credentials_empty(self, db: Path) -> None:
        """Authentication options allowCredentials is empty (discoverable credentials, AC-7)."""
        env = {"DATABASE_PATH": str(db)}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
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

        env = {
            "DATABASE_PATH": str(db),
            "WEBAUTHN_RP_ID": "localhost",
            "WEBAUTHN_ORIGIN": "http://localhost:8000",
            "DEV_USER_EMAIL": "",
        }

        raw_id_b64url = _b64url(credential_id)

        challenge_bytes = secrets.token_bytes(32)
        challenge_b64url = _b64url(challenge_bytes)
        challenge_b64 = base64.b64encode(challenge_bytes).decode()

        client_data_bytes = self._make_fake_client_data(challenge_b64url)
        client_data_b64url = _b64url(client_data_bytes)

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

        mock_verified = MagicMock()
        mock_verified.new_sign_count = 6

        _seed_challenge(db, "login", challenge_b64, challenge_b64)
        with patch.dict("os.environ", env, clear=False):
            with patch(
                "src.api.routes.auth.verify_authentication_response",
                return_value=mock_verified,
            ):
                with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                    response = client.post(
                        "/auth/passkey/login/verify", json=body,
                        headers={CSRF_HEADER: _CSRF},
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

        _seed_challenge(db, "login", challenge_b64, challenge_b64)
        with patch.dict("os.environ", env, clear=False):
            with patch(
                "src.api.routes.auth.verify_authentication_response",
                return_value=mock_verified,
            ):
                with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                    client.post("/auth/passkey/login/verify", json=body, headers={CSRF_HEADER: _CSRF})

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

        _seed_challenge(db, "login", challenge_b64, challenge_b64)
        with patch.dict("os.environ", env, clear=False):
            with patch(
                "src.api.routes.auth.verify_authentication_response",
                return_value=mock_verified,
            ):
                with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                    client.post("/auth/passkey/login/verify", json=body, headers={CSRF_HEADER: _CSRF})

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

        _seed_challenge(db, "login", challenge_b64, challenge_b64)
        with patch.dict("os.environ", env, clear=False):
            with patch(
                "src.api.routes.auth.verify_authentication_response",
                side_effect=Exception("Invalid signature"),
            ):
                with TestClient(app, cookies=_CSRF_COOKIES) as client:
                    response = client.post(
                        "/auth/passkey/login/verify", json=body,
                        headers={CSRF_HEADER: _CSRF},
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

        _seed_challenge(db, "login", challenge_b64, challenge_b64)
        with patch.dict("os.environ", env, clear=False):
            with TestClient(app, cookies=_CSRF_COOKIES) as client:
                response = client.post("/auth/passkey/login/verify", json=body, headers={CSRF_HEADER: _CSRF})

        assert response.status_code == 401

    def test_login_rejected_when_challenge_already_consumed(self, db: Path) -> None:
        """Replay loser: even a cryptographically valid assertion is rejected if
        the challenge row was already consumed by a concurrent worker (AC-2).

        Simulates the multi-worker race deterministically: the challenge is live
        (get_challenge passes) and verify succeeds, but consume_challenge returns
        0 -- another worker won the consume. The login path MUST reject with 401
        and create NO session, because the atomic DELETE is the real arbiter.
        """
        user_id = _insert_user(db, "replay-loser@example.com")
        credential_id = secrets.token_bytes(16)
        public_key_bytes = secrets.token_bytes(64)
        _insert_passkey_credential(
            db, user_id, credential_id=credential_id, public_key=public_key_bytes, sign_count=5
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
        mock_verified.new_sign_count = 6

        env = {
            "DATABASE_PATH": str(db),
            "WEBAUTHN_RP_ID": "localhost",
            "WEBAUTHN_ORIGIN": "http://localhost:8000",
            "DEV_USER_EMAIL": "",
        }

        _seed_challenge(db, "login", challenge_b64, challenge_b64)
        with patch.dict("os.environ", env, clear=False):
            with patch(
                "src.api.routes.auth.verify_authentication_response",
                return_value=mock_verified,
            ):
                # Simulate a concurrent worker having already deleted the row:
                # consume reports 0 rows deleted -> this request is the loser.
                with patch(
                    "src.api.routes.auth.passkey_challenges.consume_challenge",
                    return_value=0,
                ):
                    with TestClient(
                        app, follow_redirects=False, cookies=_CSRF_COOKIES
                    ) as client:
                        response = client.post(
                            "/auth/passkey/login/verify", json=body,
                            headers={CSRF_HEADER: _CSRF},
                        )

        assert response.status_code == 401
        assert "session" not in response.cookies
        # No session row was created for the replay loser.
        conn = sqlite3.connect(str(db))
        count = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        conn.close()
        assert count == 0


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
    ) -> str:
        """Insert a magic link token for testing verify redirects.

        Args:
            db_path: Path to the database.
            user_id: User to associate with this token.
            expired: If True, sets expires_at in the past.

        Returns:
            Raw token string.
        """
        raw_token = secrets.token_urlsafe(32)
        token_hashed = hash_token(raw_token)
        expires_offset = "-1 hour" if expired else "+15 minutes"

        conn = sqlite3.connect(str(db_path))
        conn.execute(
            f"""
            INSERT INTO magic_link_tokens (token, user_id, expires_at)
            VALUES (?, ?, datetime('now', '{expires_offset}'))
            """,
            (token_hashed, user_id),
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
            with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                response = client.get(f"/auth/verify?token={raw_token}")

        assert response.status_code == 302
        assert "/auth/passkey/prompt" in response.headers["location"]

    def test_verify_redirects_to_reports_when_has_passkeys(self, db: Path) -> None:
        """User with passkeys is redirected directly to /admin/reports (AC-1).

        E-238-05 retargeted this redirect off the (quarantined) /dashboard to
        /admin/reports; this assertion tracks that change.
        """
        user_id = _insert_user(db, "haspk@example.com")
        _insert_passkey_credential(db, user_id)
        raw_token = self._insert_magic_token(db, user_id)

        env = {"DATABASE_PATH": str(db), "DEV_USER_EMAIL": ""}
        with patch.dict("os.environ", env, clear=False):
            with TestClient(app, follow_redirects=False, cookies=_CSRF_COOKIES) as client:
                response = client.get(f"/auth/verify?token={raw_token}")

        assert response.status_code == 302
        assert "/admin/reports" in response.headers["location"]


# ---------------------------------------------------------------------------
# E-238-06: webauthn_challenges TTL'd table + passkey_challenges helper
# ---------------------------------------------------------------------------


class TestWebauthnChallengeTable:
    """The webauthn_challenges table exists and matches migration 004 (AC-1, AC-8)."""

    def test_table_exists(self, db: Path) -> None:
        """Migration 004 created the webauthn_challenges table."""
        conn = sqlite3.connect(str(db))
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='webauthn_challenges'"
        ).fetchone()
        conn.close()
        assert row is not None

    def test_expires_at_index_exists(self, db: Path) -> None:
        """Migration 004 created the expires_at index (sweep performance)."""
        conn = sqlite3.connect(str(db))
        row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND name='idx_webauthn_challenges_expires_at'"
        ).fetchone()
        conn.close()
        assert row is not None

    def test_columns_and_pk(self, db: Path) -> None:
        """Columns match the epic schema and (kind, lookup_key) is the PK."""
        conn = sqlite3.connect(str(db))
        cols = {
            row[1]: row  # name -> (cid, name, type, notnull, dflt_value, pk)
            for row in conn.execute("PRAGMA table_info(webauthn_challenges)")
        }
        conn.close()
        assert set(cols) == {"kind", "lookup_key", "challenge", "expires_at", "created_at"}
        # Composite PK on (kind, lookup_key): both carry a non-zero pk index.
        assert cols["kind"][5] > 0
        assert cols["lookup_key"][5] > 0
        assert cols["challenge"][5] == 0
        # expires_at is NOT NULL with a datetime default (no epoch float).
        assert cols["expires_at"][3] == 1
        assert "datetime" in (cols["expires_at"][4] or "")

    def test_kind_check_constraint_rejects_bad_kind(self, db: Path) -> None:
        """The CHECK(kind IN ('login','registration')) constraint is enforced."""
        conn = sqlite3.connect(str(db))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO webauthn_challenges (kind, lookup_key, challenge) "
                "VALUES ('bogus', 'k', 'c')"
            )
        conn.close()

    def test_default_expires_at_is_future_datetime_text(self, db: Path) -> None:
        """The DEFAULT (datetime('now','+5 minutes')) applies when omitted."""
        conn = sqlite3.connect(str(db))
        conn.execute(
            "INSERT INTO webauthn_challenges (kind, lookup_key, challenge) "
            "VALUES ('login', 'k', 'c')"
        )
        conn.commit()
        live = conn.execute(
            "SELECT expires_at > datetime('now') FROM webauthn_challenges WHERE lookup_key='k'"
        ).fetchone()[0]
        conn.close()
        assert live == 1


class TestPasskeyChallengesHelper:
    """The passkey_challenges helper store/get/consume/sweep behavior (AC-2..7)."""

    def test_store_then_get_roundtrip(self, db: Path) -> None:
        """A stored challenge is read back by get_challenge (AC-7)."""
        conn = sqlite3.connect(str(db))
        passkey_challenges.store_challenge(conn, "login", "key-a", "chal-a")
        assert passkey_challenges.get_challenge(conn, "login", "key-a") == "chal-a"
        conn.close()

    def test_get_missing_returns_none(self, db: Path) -> None:
        """get_challenge returns None when no row exists."""
        conn = sqlite3.connect(str(db))
        assert passkey_challenges.get_challenge(conn, "login", "absent") is None
        conn.close()

    def test_consume_deletes_row(self, db: Path) -> None:
        """consume_challenge DELETEs the row (AC-2)."""
        conn = sqlite3.connect(str(db))
        passkey_challenges.store_challenge(conn, "login", "key-b", "chal-b")
        passkey_challenges.consume_challenge(conn, "login", "key-b")
        assert passkey_challenges.get_challenge(conn, "login", "key-b") is None
        assert not _challenge_exists(db, "login", "key-b")
        conn.close()

    def test_replay_rejected_after_consume(self, db: Path) -> None:
        """A second consume/get of a consumed challenge finds nothing (AC-2 replay)."""
        conn = sqlite3.connect(str(db))
        passkey_challenges.store_challenge(conn, "login", "key-c", "chal-c")
        # First use: present.
        assert passkey_challenges.get_challenge(conn, "login", "key-c") == "chal-c"
        passkey_challenges.consume_challenge(conn, "login", "key-c")
        # Replay: the row is gone (DELETE-on-consume), so it is rejected.
        assert passkey_challenges.get_challenge(conn, "login", "key-c") is None
        conn.close()

    def test_consume_returns_rows_deleted(self, db: Path) -> None:
        """consume_challenge returns 1 when it deletes, 0 when the row is gone."""
        conn = sqlite3.connect(str(db))
        passkey_challenges.store_challenge(conn, "login", "key-r", "chal-r")
        assert passkey_challenges.consume_challenge(conn, "login", "key-r") == 1
        # Second consume finds nothing -> 0.
        assert passkey_challenges.consume_challenge(conn, "login", "key-r") == 0
        conn.close()

    def test_consume_is_atomic_arbiter_across_connections(self, db: Path) -> None:
        """Two workers racing the same live row: exactly one consume wins (AC-2).

        Simulates the multi-worker TOCTOU window: both connections read the same
        live challenge, then both attempt to consume it. SQLite serializes
        writers, so the first consume deletes the row (returns 1) and the second
        finds nothing (returns 0). The 0-result is how the login verify path
        detects and rejects the replay loser.
        """
        writer = sqlite3.connect(str(db))
        passkey_challenges.store_challenge(writer, "login", "race-key", "race-chal")
        writer.close()

        conn_a = sqlite3.connect(str(db))
        conn_b = sqlite3.connect(str(db))
        # Both workers see the live challenge before either deletes (the window).
        assert passkey_challenges.get_challenge(conn_a, "login", "race-key") == "race-chal"
        assert passkey_challenges.get_challenge(conn_b, "login", "race-key") == "race-chal"
        # The DELETE is the arbiter: exactly one winner.
        won_a = passkey_challenges.consume_challenge(conn_a, "login", "race-key")
        won_b = passkey_challenges.consume_challenge(conn_b, "login", "race-key")
        conn_a.close()
        conn_b.close()
        assert {won_a, won_b} == {1, 0}, f"Expected one winner, got {won_a=}, {won_b=}"

    def test_expired_challenge_rejected_on_read(self, db: Path) -> None:
        """get_challenge rejects an expired row (read-side TTL gate, AC-4)."""
        _seed_challenge(db, "login", "key-exp", "chal-exp", expired=True)
        conn = sqlite3.connect(str(db))
        assert passkey_challenges.get_challenge(conn, "login", "key-exp") is None
        conn.close()

    def test_sweep_on_write_deletes_expired(self, db: Path) -> None:
        """store_challenge sweeps expired rows on each create (AC-4, no background job)."""
        _seed_challenge(db, "login", "key-old", "chal-old", expired=True)
        assert _challenge_exists(db, "login", "key-old")
        conn = sqlite3.connect(str(db))
        # Storing any challenge triggers the sweep-on-write.
        passkey_challenges.store_challenge(conn, "login", "key-new", "chal-new")
        conn.close()
        assert not _challenge_exists(db, "login", "key-old")
        assert _challenge_exists(db, "login", "key-new")

    def test_sweep_expired_returns_count(self, db: Path) -> None:
        """sweep_expired deletes only expired rows and reports the count."""
        _seed_challenge(db, "login", "exp-1", "c1", expired=True)
        _seed_challenge(db, "login", "exp-2", "c2", expired=True)
        _seed_challenge(db, "login", "live-1", "c3", expired=False)
        conn = sqlite3.connect(str(db))
        deleted = passkey_challenges.sweep_expired(conn)
        conn.commit()
        conn.close()
        assert deleted == 2
        assert _challenge_exists(db, "login", "live-1")

    def test_register_twice_overwrites(self, db: Path) -> None:
        """A repeat registration store overwrites via ON CONFLICT DO UPDATE (AC-3)."""
        session_hash = "sess-hash-xyz"
        conn = sqlite3.connect(str(db))
        passkey_challenges.store_challenge(conn, "registration", session_hash, "chal-1")
        passkey_challenges.store_challenge(conn, "registration", session_hash, "chal-2")
        # Single row, holding the latest challenge.
        assert passkey_challenges.get_challenge(conn, "registration", session_hash) == "chal-2"
        count = conn.execute(
            "SELECT COUNT(*) FROM webauthn_challenges WHERE kind='registration' AND lookup_key=?",
            (session_hash,),
        ).fetchone()[0]
        conn.close()
        assert count == 1

    def test_multi_connection_visibility(self, db: Path) -> None:
        """A challenge stored via one connection is readable via a second (AC-5).

        Uses the FILE-BACKED db fixture (NOT :memory:): store_challenge COMMITs,
        so a separate connection -- standing in for another uvicorn worker --
        sees the row. This is the multi-worker correctness proof.
        """
        writer = sqlite3.connect(str(db))
        passkey_challenges.store_challenge(writer, "login", "shared-key", "shared-chal")
        writer.close()

        reader = sqlite3.connect(str(db))
        assert passkey_challenges.get_challenge(reader, "login", "shared-key") == "shared-chal"
        reader.close()

    def test_login_lookup_key_byte_identical(self, db: Path) -> None:
        """Store-side and lookup-side login key derivations agree byte-for-byte (AC-6).

        STORE side (GET /passkey/login/options): base64.b64encode(challenge).
        LOOKUP side (POST /verify): rebuild from the base64url challenge the
        browser echoes in clientDataJSON (urlsafe_b64decode w/ padding ->
        standard b64encode). The two MUST produce the same key, and a store via
        the options derivation must be found via the verify derivation.
        """
        challenge_bytes = secrets.token_bytes(32)

        # STORE side -- exactly as GET /passkey/login/options derives it.
        store_side_key = base64.b64encode(challenge_bytes).decode()

        # What the browser puts in clientDataJSON.challenge: base64url, no pad.
        browser_challenge_b64 = base64.urlsafe_b64encode(challenge_bytes).rstrip(b"=").decode()

        # LOOKUP side -- exactly as POST /verify rebuilds the key.
        padding = 4 - len(browser_challenge_b64) % 4
        if padding != 4:
            browser_challenge_b64 += "=" * padding
        browser_challenge_bytes = base64.urlsafe_b64decode(browser_challenge_b64)
        lookup_side_key = base64.b64encode(browser_challenge_bytes).decode()

        # Byte-identical derivation (the silent-break risk #1 guard).
        assert lookup_side_key == store_side_key

        # And a round-trip through the table: store via options key, look up via verify key.
        conn = sqlite3.connect(str(db))
        passkey_challenges.store_challenge(conn, "login", store_side_key, store_side_key)
        assert passkey_challenges.get_challenge(conn, "login", lookup_side_key) == store_side_key
        conn.close()
