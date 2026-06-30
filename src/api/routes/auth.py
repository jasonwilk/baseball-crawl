"""Auth routes for the baseball-crawl FastAPI application.

Provides magic link login, verification, logout, and passkey (WebAuthn)
registration and authentication flows.

Routes:
    GET  /auth/login                  -- Render login page (or redirect if already logged in)
    POST /auth/login                  -- Accept email form, issue magic link
    GET  /auth/verify                 -- Verify magic link token, create session
    GET  /auth/logout                 -- Clear session cookie and session DB row
    GET  /auth/passkey/register       -- Render passkey registration page with WebAuthn options
    POST /auth/passkey/register       -- Verify attestation and store passkey credential
    GET  /auth/passkey/login/options  -- Return WebAuthn authentication options as JSON
    POST /auth/passkey/login/verify   -- Verify assertion and create session
    GET  /auth/passkey/prompt         -- Post-login passkey registration CTA (interstitial)

Schema notes (E-100 schema):
    - sessions.session_id is the SHA-256 hash of the raw cookie token (TEXT PRIMARY KEY)
    - users.id is INTEGER PRIMARY KEY (no user_id alias, no display_name, no is_admin)
    - magic_link_tokens.token is TEXT PRIMARY KEY (raw token stored directly; DELETE on use)
    - passkey login AND registration challenges stored in the TTL'd
      ``webauthn_challenges`` table (migration 004) via the
      ``src.api.passkey_challenges`` helper -- NOT in-process dicts. This makes
      passkey login survive multiple uvicorn workers and app restarts (the
      sessions table has no challenge column in the E-100 schema).
"""

from __future__ import annotations

import base64
import json
import logging
import os
import secrets
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AuthenticatorAssertionResponse,
    AuthenticatorAttestationResponse,
    AuthenticatorSelectionCriteria,
    AuthenticationCredential,
    RegistrationCredential,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from src.api import passkey_challenges
from src.api.auth import create_session, hash_token
from src.api.db import get_connection
from src.api.email import send_magic_link_email
from src.api.helpers import get_app_url

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter(prefix="/auth")

_SESSION_COOKIE_NAME = "session"
_SESSION_MAX_AGE = 604800  # 7 days in seconds

# Magic link rate-limit cooldown in seconds.
_MAGIC_LINK_COOLDOWN_SECONDS = 60

# Passkey challenges (login AND registration) live in the TTL'd
# ``webauthn_challenges`` table (migration 004), accessed via the
# ``src.api.passkey_challenges`` helper. This replaces the former in-process
# module-global dicts, which were single-worker-only and lost on restart
# mid-login. All workers share ``data/app.db`` (WAL on), so a challenge stored
# by one worker is visible to whichever worker handles the verify request.


def _is_dev_mode() -> bool:
    """Return True when running in non-production mode.

    Returns:
        True if APP_ENV is not 'production'.
    """
    return os.environ.get("APP_ENV", "development") != "production"


def _get_webauthn_rp_id() -> str:
    """Return the WebAuthn relying party ID from environment.

    Returns:
        WEBAUTHN_RP_ID env var, or 'baseball.localhost' as default.
    """
    return os.environ.get("WEBAUTHN_RP_ID", "baseball.localhost")


def _get_webauthn_origin() -> str:
    """Return the WebAuthn expected origin from environment.

    Returns:
        WEBAUTHN_ORIGIN env var, or 'http://baseball.localhost:8001' as default.
    """
    return os.environ.get("WEBAUTHN_ORIGIN", "http://baseball.localhost:8001")


def _set_session_cookie(response: RedirectResponse, raw_token: str) -> None:
    """Attach the session cookie to the response.

    Args:
        response: Response object to modify in place.
        raw_token: Raw session token value to store in the cookie.
    """
    response.set_cookie(
        key=_SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=_SESSION_MAX_AGE,
        httponly=True,
        secure=not _is_dev_mode(),
        samesite="lax",
        path="/",
    )


def _get_authenticated_user(
    request: Request,
) -> dict[str, Any] | None:
    """Return the authenticated user from the session cookie, or None.

    Auth routes are excluded from session middleware, so passkey registration
    routes must manually validate the session cookie.

    Args:
        request: The incoming HTTP request.

    Returns:
        User dict with ``id`` and ``email`` if authenticated; None if no valid session.
    """
    # Check if middleware already resolved the user (non-auth routes).
    user = getattr(request.state, "user", None)
    if user:
        return user

    # /auth/* routes are excluded from session middleware -- validate manually.
    cookie_value = request.cookies.get(_SESSION_COOKIE_NAME, "")
    if not cookie_value:
        return None

    session_id = hash_token(cookie_value)
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT s.user_id
                FROM sessions s
                WHERE s.session_id = ?
                  AND s.expires_at > datetime('now')
                """,
                (session_id,),
            )
            session_row = cursor.fetchone()
            if not session_row:
                return None

            cursor = conn.execute(
                "SELECT id, email FROM users WHERE id = ?",
                (session_row["user_id"],),
            )
            user_row = cursor.fetchone()
            if not user_row:
                return None

            return dict(user_row)
    except sqlite3.Error:
        logger.exception("DB error in _get_authenticated_user")
        return None


def _user_has_passkeys(conn: sqlite3.Connection, user_id: int) -> bool:
    """Return True if the user has at least one registered passkey.

    Args:
        conn: Open SQLite connection.
        user_id: User database ID.

    Returns:
        True if the user has a passkey credential row.
    """
    cursor = conn.execute(
        "SELECT 1 FROM passkey_credentials WHERE user_id = ? LIMIT 1",
        (user_id,),
    )
    return cursor.fetchone() is not None


def _base64url_decode(value: str) -> bytes:
    """Decode a base64url string to bytes.

    Args:
        value: Base64url-encoded string (no padding required).

    Returns:
        Decoded bytes.
    """
    padding = 4 - len(value) % 4
    if padding != 4:
        value += "=" * padding
    return base64.urlsafe_b64decode(value)


@router.get("/login", response_class=HTMLResponse, response_model=None)
async def get_login(request: Request) -> HTMLResponse | RedirectResponse:
    """Render the login page, or redirect to /admin/reports if already authenticated.

    Args:
        request: The incoming HTTP request.

    Returns:
        HTMLResponse with the login form, or a redirect to /admin/reports.
    """
    # Already authenticated -> redirect to the reports page.
    # _get_authenticated_user owns the cookie -> session -> user resolution
    # (it checks middleware-attached state first, then validates the session
    # cookie directly), so the "already logged in" check lives in one place.
    # This is byte-identical to the former inline session-only check for every
    # reachable input: the only divergence (a valid session whose user row is
    # gone) is FK-prohibited -- sessions.user_id is NOT NULL REFERENCES
    # users(id) with foreign_keys=ON and no CASCADE, and _delete_user removes
    # sessions before users -- and would be fail-safe (login page) regardless.
    if _get_authenticated_user(request):
        return RedirectResponse(url="/admin/reports", status_code=302)

    return templates.TemplateResponse(request, "auth/login.html", {})


@router.post("/login", response_class=HTMLResponse, response_model=None)
async def post_login(
    request: Request,
    email: str = Form(...),
) -> HTMLResponse:
    """Handle email form submission and issue a magic link.

    Looks up the email in ``users``.  For both known and unknown emails,
    renders the same "If this email is registered..." confirmation page to
    prevent user enumeration.

    Rate limit: if the user has an unexpired token issued within the last 60
    seconds (approximated by checking expires_at > now + 14min), suppress
    issuance.  Since tokens expire in 15 minutes, a token with more than 14
    minutes remaining was issued less than 60 seconds ago.

    Args:
        request: The incoming HTTP request.
        email: Email address submitted via form.

    Returns:
        HTMLResponse with the check_email confirmation page.
    """
    email = email.strip().lower()

    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT id FROM users WHERE email = ?",
                (email,),
            )
            user_row = cursor.fetchone()

            if user_row:
                user_id: int = user_row["id"]

                # Rate limit: if there is an unexpired token with > 14 minutes
                # remaining, it was issued within the last 60 seconds.
                cursor = conn.execute(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM magic_link_tokens
                    WHERE user_id = ?
                      AND expires_at > datetime('now', '+14 minutes')
                    """,
                    (user_id,),
                )
                recent = cursor.fetchone()
                if recent and recent["cnt"] > 0:
                    logger.info(
                        "Magic link rate limit hit for user %d", user_id
                    )
                else:
                    raw_token = secrets.token_urlsafe(32)
                    token_hash = hash_token(raw_token)
                    # Invalidate all prior unused tokens for this user by
                    # deleting them before inserting the new one.
                    conn.execute(
                        "DELETE FROM magic_link_tokens WHERE user_id = ?",
                        (user_id,),
                    )
                    conn.execute(
                        """
                        INSERT INTO magic_link_tokens (token, user_id, expires_at)
                        VALUES (?, ?, datetime('now', '+15 minutes'))
                        """,
                        (token_hash, user_id),
                    )
                    conn.commit()

                    app_url = get_app_url()
                    magic_link_url = f"{app_url}/auth/verify?token={raw_token}"
                    await send_magic_link_email(email, magic_link_url)
    except sqlite3.Error:
        logger.exception("DB error during magic link issuance for %s", email)

    return templates.TemplateResponse(request, "auth/check_email.html", {})


@router.get("/verify", response_class=HTMLResponse, response_model=None)
async def verify_token(
    request: Request,
    token: str = "",
) -> HTMLResponse | RedirectResponse:
    """Verify a magic link token and create an authenticated session.

    After successful verification, checks whether the user has registered
    passkeys.  If not, redirects to the passkey prompt interstitial.  If
    they do, redirects directly to /admin/reports.

    The token is stored directly in magic_link_tokens.token (TEXT PRIMARY KEY).
    Verification deletes the row (single-use).

    Args:
        request: The incoming HTTP request.
        token: Raw magic link token from the query string.

    Returns:
        RedirectResponse on success, or error HTMLResponse.
    """
    if not token:
        return templates.TemplateResponse(
            request, "auth/verify_error.html", {}, status_code=400
        )

    token_hash = hash_token(token)

    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT user_id, expires_at
                FROM magic_link_tokens
                WHERE token = ?
                """,
                (token_hash,),
            )
            row = cursor.fetchone()

            if not row:
                logger.warning("Magic link token not found")
                return templates.TemplateResponse(
                    request, "auth/verify_error.html", {}, status_code=400
                )

            # Check expiry via DB comparison for accuracy.
            cursor = conn.execute(
                """
                SELECT (expires_at > datetime('now')) AS valid
                FROM magic_link_tokens
                WHERE token = ?
                """,
                (token_hash,),
            )
            validity = cursor.fetchone()
            if not validity or not validity["valid"]:
                logger.warning("Magic link token expired for user %d", row["user_id"])
                # Clean up expired token.
                conn.execute(
                    "DELETE FROM magic_link_tokens WHERE token = ?",
                    (token_hash,),
                )
                conn.commit()
                return templates.TemplateResponse(
                    request, "auth/verify_error.html", {}, status_code=400
                )

            # Atomically delete the token (single-use enforcement).
            cursor = conn.execute(
                "DELETE FROM magic_link_tokens WHERE token = ?",
                (token_hash,),
            )
            conn.commit()

            if cursor.rowcount == 0:
                # Another request consumed the token between our SELECT and DELETE.
                logger.warning("Magic link token race: already consumed")
                return templates.TemplateResponse(
                    request, "auth/verify_error.html", {}, status_code=400
                )

            user_id = row["user_id"]
            has_passkeys = _user_has_passkeys(conn, user_id)

    except sqlite3.Error:
        logger.exception("DB error during token verification")
        return templates.TemplateResponse(
            request, "auth/verify_error.html", {}, status_code=500
        )

    # Create session (uses its own connection internally).
    raw_session_token = create_session(user_id)

    # Redirect to passkey prompt if no passkeys registered, else the reports page.
    redirect_url = "/admin/reports" if has_passkeys else "/auth/passkey/prompt"
    response = RedirectResponse(url=redirect_url, status_code=302)
    _set_session_cookie(response, raw_session_token)
    return response


@router.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    """Clear the session cookie and delete the session from the DB.

    Args:
        request: The incoming HTTP request.

    Returns:
        RedirectResponse to /auth/login.
    """
    cookie_value = request.cookies.get(_SESSION_COOKIE_NAME, "")
    if cookie_value:
        session_id = hash_token(cookie_value)
        try:
            with closing(get_connection()) as conn:
                conn.execute(
                    "DELETE FROM sessions WHERE session_id = ?",
                    (session_id,),
                )
                conn.commit()
        except sqlite3.Error:
            logger.exception("DB error during logout")

    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie(
        key=_SESSION_COOKIE_NAME,
        path="/",
    )
    return response


# ---------------------------------------------------------------------------
# Passkey interstitial
# ---------------------------------------------------------------------------


@router.get("/passkey/prompt", response_class=HTMLResponse, response_model=None)
async def get_passkey_prompt(request: Request) -> HTMLResponse | RedirectResponse:
    """Render the post-login passkey registration CTA interstitial.

    Requires an active session.  If not authenticated, redirects to login.

    Args:
        request: The incoming HTTP request.

    Returns:
        HTMLResponse with the passkey_prompt page.
    """
    user = _get_authenticated_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    return templates.TemplateResponse(request, "auth/passkey_prompt.html", {})


# ---------------------------------------------------------------------------
# Passkey registration
# ---------------------------------------------------------------------------


@router.get("/passkey/register", response_class=HTMLResponse, response_model=None)
async def get_passkey_register(request: Request) -> HTMLResponse | RedirectResponse:
    """Render the passkey registration page with embedded WebAuthn options.

    Requires an active session.  Generates registration options server-side,
    stores the challenge in the TTL'd webauthn_challenges table (keyed by the
    session-id hash), and embeds the options as JSON in the rendered page.

    The E-100 sessions table has no challenge column; challenges live in the
    webauthn_challenges table (migration 004) instead.

    Args:
        request: The incoming HTTP request.

    Returns:
        HTMLResponse with embedded registration options and inline JS.
    """
    user = _get_authenticated_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    user_id: int = user["id"]
    email: str = user["email"]

    rp_id = _get_webauthn_rp_id()

    # Fetch existing credentials to exclude from registration options.
    existing_creds: list[bytes] = []
    try:
        with closing(get_connection()) as conn:
            cursor = conn.execute(
                "SELECT credential_id FROM passkey_credentials WHERE user_id = ?",
                (user_id,),
            )
            existing_creds = [row[0] for row in cursor.fetchall()]
    except sqlite3.Error:
        logger.exception("DB error fetching existing passkey credentials for user %d", user_id)

    registration_options = generate_registration_options(
        rp_id=rp_id,
        rp_name="Baseball Stats",
        user_name=email,
        user_id=str(user_id).encode(),
        user_display_name=email,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )

    # Store the challenge in the TTL'd webauthn_challenges table, keyed by the
    # session-id hash. A repeat GET overwrites the prior challenge (UPSERT).
    challenge_b64 = base64.b64encode(registration_options.challenge).decode()
    cookie_value = request.cookies.get(_SESSION_COOKIE_NAME, "")
    if cookie_value:
        session_id = hash_token(cookie_value)
        with closing(get_connection()) as conn:
            passkey_challenges.store_challenge(
                conn,
                passkey_challenges.KIND_REGISTRATION,
                session_id,
                challenge_b64,
            )

    options_dict = json.loads(options_to_json(registration_options))
    return templates.TemplateResponse(
        request,
        "auth/passkey_register.html",
        {"options_json": options_dict},
    )


@router.post("/passkey/register", response_model=None)
async def post_passkey_register(
    request: Request,
) -> JSONResponse | RedirectResponse | HTMLResponse:
    """Verify the attestation response and store the new passkey credential.

    Reads (and consumes) the challenge from the webauthn_challenges table
    (keyed by the session-id hash), verifies via py_webauthn, and stores the
    credential in ``passkey_credentials``.

    Args:
        request: The incoming HTTP request.

    Returns:
        RedirectResponse to /admin/reports on success, or error response.
    """
    user = _get_authenticated_user(request)
    if not user:
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    user_id: int = user["id"]

    # Parse JSON body.
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse({"detail": "Invalid JSON body"}, status_code=400)

    # Retrieve and clear challenge from the in-memory dict.
    cookie_value = request.cookies.get(_SESSION_COOKIE_NAME, "")
    if not cookie_value:
        return JSONResponse({"detail": "Session cookie missing"}, status_code=401)

    session_id = hash_token(cookie_value)
    with closing(get_connection()) as conn:
        challenge_b64 = passkey_challenges.get_challenge(
            conn, passkey_challenges.KIND_REGISTRATION, session_id
        )
        if challenge_b64 is not None:
            # Consume immediately (replay-proof) -- mirrors the old dict pop.
            passkey_challenges.consume_challenge(
                conn, passkey_challenges.KIND_REGISTRATION, session_id
            )

    if not challenge_b64:
        logger.warning("No passkey registration challenge found for user %d", user_id)
        return JSONResponse(
            {"detail": "Registration session expired. Please try again."},
            status_code=400,
        )

    challenge_bytes: bytes = base64.b64decode(challenge_b64)

    # Build the RegistrationCredential from the browser response.
    try:
        raw_id_bytes = _base64url_decode(body.get("rawId", ""))
        response_data = body.get("response", {})
        attestation_bytes = _base64url_decode(response_data.get("attestationObject", ""))
        client_data_bytes = _base64url_decode(response_data.get("clientDataJSON", ""))

        credential = RegistrationCredential(
            id=body.get("id", ""),
            raw_id=raw_id_bytes,
            response=AuthenticatorAttestationResponse(
                client_data_json=client_data_bytes,
                attestation_object=attestation_bytes,
            ),
            type=body.get("type", "public-key"),
        )
    except Exception:
        logger.exception("Failed to parse registration credential from browser response")
        return templates.TemplateResponse(
            request,
            "auth/passkey_error.html",
            {"error": "Invalid registration response from browser."},
            status_code=400,
        )

    # Verify the attestation.
    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=challenge_bytes,
            expected_rp_id=_get_webauthn_rp_id(),
            expected_origin=_get_webauthn_origin(),
        )
    except Exception as exc:
        logger.warning("Passkey registration verification failed for user %d: %s", user_id, exc)
        return templates.TemplateResponse(
            request,
            "auth/passkey_error.html",
            {"error": "Registration verification failed. Please try again."},
            status_code=400,
        )

    # Store the credential.
    try:
        with closing(get_connection()) as conn:
            conn.execute(
                """
                INSERT INTO passkey_credentials
                    (user_id, credential_id, public_key, sign_count)
                VALUES (?, ?, ?, ?)
                """,
                (
                    user_id,
                    verified.credential_id,
                    verified.credential_public_key,
                    verified.sign_count,
                ),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        logger.warning("Duplicate passkey credential for user %d", user_id)
        return JSONResponse({"detail": "Credential already registered."}, status_code=409)
    except sqlite3.Error:
        logger.exception("DB error storing passkey credential for user %d", user_id)
        return JSONResponse({"detail": "Server error storing credential."}, status_code=500)

    logger.info("Passkey registered for user %d", user_id)
    return JSONResponse({"redirect": "/admin/reports?msg=Device+registered+for+quick+login"})


# ---------------------------------------------------------------------------
# Passkey login
# ---------------------------------------------------------------------------


@router.get("/passkey/login/options")
async def get_passkey_login_options() -> JSONResponse:
    """Return WebAuthn authentication options as JSON.

    Uses discoverable credentials (allow_credentials=[]) so the browser's
    credential manager can present any registered passkey for this RP.

    Returns:
        JSONResponse with WebAuthn authentication options.
    """
    auth_options = generate_authentication_options(
        rp_id=_get_webauthn_rp_id(),
        allow_credentials=[],
    )

    # Store the challenge in the TTL'd webauthn_challenges table for the verify
    # step. Login challenges are keyed by the challenge_b64 itself (anonymous --
    # no session exists yet). store_challenge sweeps expired rows first.
    challenge_b64 = base64.b64encode(auth_options.challenge).decode()
    with closing(get_connection()) as conn:
        passkey_challenges.store_challenge(
            conn, passkey_challenges.KIND_LOGIN, challenge_b64, challenge_b64
        )

    options_dict = json.loads(options_to_json(auth_options))
    return JSONResponse(options_dict)


@router.post("/passkey/login/verify", response_model=None)
async def post_passkey_login_verify(request: Request) -> JSONResponse | RedirectResponse:
    """Verify a passkey assertion and create a session.

    Looks up the credential in the DB, verifies via py_webauthn, updates
    sign_count, creates a session (same path as magic link), and returns a
    redirect URL to the client.

    Args:
        request: The incoming HTTP request.

    Returns:
        JSONResponse with redirect URL on success, or error on failure.
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse({"detail": "Invalid JSON body"}, status_code=400)

    response_data = body.get("response", {})

    # Parse the credential from the browser assertion.
    try:
        raw_id_bytes = _base64url_decode(body.get("rawId", ""))
        authenticator_data_bytes = _base64url_decode(
            response_data.get("authenticatorData", "")
        )
        client_data_bytes = _base64url_decode(response_data.get("clientDataJSON", ""))
        signature_bytes = _base64url_decode(response_data.get("signature", ""))
        user_handle_raw = response_data.get("userHandle")
        user_handle_bytes = _base64url_decode(user_handle_raw) if user_handle_raw else None

        credential = AuthenticationCredential(
            id=body.get("id", ""),
            raw_id=raw_id_bytes,
            response=AuthenticatorAssertionResponse(
                client_data_json=client_data_bytes,
                authenticator_data=authenticator_data_bytes,
                signature=signature_bytes,
                user_handle=user_handle_bytes,
            ),
            type=body.get("type", "public-key"),
        )
    except Exception:
        logger.exception("Failed to parse authentication credential from browser response")
        return JSONResponse(
            {"detail": "Invalid passkey response. Please try again or use email login."},
            status_code=400,
        )

    # Look up the passkey credential in the DB.
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT user_id, credential_id, public_key, sign_count
                FROM passkey_credentials
                WHERE credential_id = ?
                """,
                (raw_id_bytes,),
            )
            cred_row = cursor.fetchone()
    except sqlite3.Error:
        logger.exception("DB error looking up passkey credential")
        return JSONResponse({"detail": "Server error"}, status_code=500)

    if not cred_row:
        logger.warning("Passkey credential not found: id=%s...", body.get("id", "")[:16])
        return JSONResponse(
            {"detail": "Passkey authentication failed. Please try again or use email login."},
            status_code=401,
        )

    # Retrieve and validate the stored challenge from the webauthn_challenges
    # table. We accept any LIVE, unconsumed challenge in our store -- the
    # WebAuthn library checks the challenge embedded in clientDataJSON against
    # expected_challenge, so the DB only gates live-and-unconsumed.
    verified_challenge: str | None = None

    # Decode clientDataJSON to extract the challenge the browser used.
    # The lookup-key derivation below MUST stay byte-identical to the store-side
    # derivation in GET /passkey/login/options (b64encode of the raw challenge
    # bytes); see E-238-06 AC-6.
    try:
        client_data = json.loads(client_data_bytes.decode())
        browser_challenge_b64 = client_data.get("challenge", "")
        # Normalize to standard base64 for lookup (webauthn may use base64url)
        padding = 4 - len(browser_challenge_b64) % 4
        if padding != 4:
            browser_challenge_b64 += "=" * padding
        browser_challenge_bytes = base64.urlsafe_b64decode(browser_challenge_b64)
        lookup_key = base64.b64encode(browser_challenge_bytes).decode()
        with closing(get_connection()) as conn:
            if (
                passkey_challenges.get_challenge(
                    conn, passkey_challenges.KIND_LOGIN, lookup_key
                )
                is not None
            ):
                verified_challenge = lookup_key
    except Exception:
        pass

    if not verified_challenge:
        logger.warning("No valid challenge found for passkey login attempt")
        return JSONResponse(
            {"detail": "Passkey authentication failed. Please try again or use email login."},
            status_code=401,
        )

    expected_challenge = base64.b64decode(verified_challenge)

    # Verify the assertion.
    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=expected_challenge,
            expected_rp_id=_get_webauthn_rp_id(),
            expected_origin=_get_webauthn_origin(),
            credential_public_key=bytes(cred_row["public_key"]),
            credential_current_sign_count=cred_row["sign_count"],
        )
    except Exception as exc:
        logger.warning("Passkey authentication verification failed: %s", exc)
        return JSONResponse(
            {"detail": "Passkey authentication failed. Please try again or use email login."},
            status_code=401,
        )

    # Consume the challenge as the ATOMIC replay arbiter. The earlier
    # get_challenge read is advisory; this DELETE is the real gate. SQLite
    # serializes writers, so if two workers raced this assertion, exactly one
    # deletes the row (rowcount 1) and wins -- the loser sees rowcount 0 and is
    # rejected here, BEFORE any session is created or sign_count is bumped.
    # This keeps login replay-proof under multiple workers (E-238-06 AC-2).
    with closing(get_connection()) as conn:
        consumed = passkey_challenges.consume_challenge(
            conn, passkey_challenges.KIND_LOGIN, verified_challenge
        )
    if consumed != 1:
        logger.warning(
            "Passkey login challenge already consumed (replay or race); rejecting"
        )
        return JSONResponse(
            {"detail": "Passkey authentication failed. Please try again or use email login."},
            status_code=401,
        )

    # Update sign_count in DB.
    user_id: int = cred_row["user_id"]
    try:
        with closing(get_connection()) as conn:
            conn.execute(
                "UPDATE passkey_credentials SET sign_count = ? WHERE credential_id = ?",
                (verified.new_sign_count, cred_row["credential_id"]),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("DB error updating passkey sign_count")
        # Non-fatal -- session still gets created.

    # Create a session (same path as magic link verify).
    raw_session_token = create_session(user_id)

    logger.info("Passkey login successful for user %d", user_id)

    # Return redirect info as JSON -- the client JS handles the redirect.
    response = JSONResponse({"redirect": "/admin/reports"})
    response.set_cookie(
        key=_SESSION_COOKIE_NAME,
        value=raw_session_token,
        max_age=_SESSION_MAX_AGE,
        httponly=True,
        secure=not _is_dev_mode(),
        samesite="lax",
        path="/",
    )
    return response
