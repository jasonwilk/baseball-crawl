"""TTL'd SQLite passkey (WebAuthn) challenge store helper.

Holds the SQL for the `webauthn_challenges` table (migration 004), keeping it
out of the route handlers in ``src/api/routes/auth.py``. Replaces the former
in-process module-global dicts (``_PASSKEY_LOGIN_CHALLENGES``,
``_PASSKEY_REG_CHALLENGES``) and the ``_purge_expired_challenges`` helper.

Why SQLite instead of module globals: the dicts were single-worker-only and
lost on restart mid-login -- a real auth bug. Storing challenges in
``data/app.db`` (WAL on, shared by every uvicorn worker) makes passkey login
survive ``--workers N > 1`` and app restarts.

Lifecycle (no background job):
    * :func:`store_challenge` -- sweep expired rows, then UPSERT the challenge.
      Used by GET /passkey/login/options (kind='login') and
      GET /passkey/register (kind='registration', repeat-GET overwrite).
    * :func:`get_challenge`   -- read a LIVE (``expires_at > datetime('now')``),
      unconsumed challenge. Returns ``None`` for missing OR expired rows
      (read-side TTL gate).
    * :func:`consume_challenge` -- DELETE the row (replay-proof; mirrors the old
      dict ``pop``). Called after py_webauthn verifies.
    * :func:`sweep_expired`   -- ``DELETE WHERE expires_at <= datetime('now')``;
      runs inside every store (replaces ``_purge_expired_challenges``).

TTL is SQLite datetime TEXT everywhere (aligns with ``sessions`` /
``magic_link_tokens``) -- never epoch floats. py_webauthn remains the
cryptographic check; this table only gates live-and-unconsumed.

All functions are connection-injected so callers control the connection
lifecycle and tests can prove cross-connection visibility (multi-worker). The
write helpers (:func:`store_challenge`, :func:`consume_challenge`) COMMIT so a
second connection sees the effect.
"""

from __future__ import annotations

import sqlite3

# The two challenge flows. login challenges are keyed by the challenge itself
# (anonymous -- no session exists yet); registration challenges are keyed by
# the session-id hash.
KIND_LOGIN = "login"
KIND_REGISTRATION = "registration"


def sweep_expired(conn: sqlite3.Connection) -> int:
    """Delete all challenges whose TTL has elapsed.

    Replaces the old ``_purge_expired_challenges``. Called inside
    :func:`store_challenge` (sweep-on-write); does not commit on its own (the
    caller's store commits).

    Args:
        conn: Open SQLite connection.

    Returns:
        Number of expired rows deleted.
    """
    cursor = conn.execute(
        "DELETE FROM webauthn_challenges WHERE expires_at <= datetime('now')"
    )
    return cursor.rowcount


def store_challenge(
    conn: sqlite3.Connection,
    kind: str,
    lookup_key: str,
    challenge: str,
) -> None:
    """Sweep expired rows, then store (UPSERT) a challenge with a fresh TTL.

    The ON CONFLICT DO UPDATE makes a repeat store for the same
    (kind, lookup_key) overwrite the prior challenge and reset its TTL --
    matching the old dict-assignment semantics (registration repeat-GET).
    ``expires_at`` is taken from the column default (now + 5 minutes) on both
    the insert and the conflict update, so the TTL is refreshed on overwrite.

    Commits so other connections (workers) see the row.

    Args:
        conn: Open SQLite connection.
        kind: ``'login'`` or ``'registration'``.
        lookup_key: login -> the challenge_b64 itself; registration -> the
            session-id hash.
        challenge: The standard-base64 challenge string to verify against.
    """
    sweep_expired(conn)
    conn.execute(
        """
        INSERT INTO webauthn_challenges (kind, lookup_key, challenge)
        VALUES (?, ?, ?)
        ON CONFLICT(kind, lookup_key) DO UPDATE SET
            challenge  = excluded.challenge,
            expires_at = excluded.expires_at,
            created_at = excluded.created_at
        """,
        (kind, lookup_key, challenge),
    )
    conn.commit()


def get_challenge(
    conn: sqlite3.Connection,
    kind: str,
    lookup_key: str,
) -> str | None:
    """Return a LIVE, unconsumed challenge, or ``None`` if missing/expired.

    The ``expires_at > datetime('now')`` gate is the read-side TTL enforcement:
    an expired row is treated as absent (and will be swept on the next store).

    Args:
        conn: Open SQLite connection.
        kind: ``'login'`` or ``'registration'``.
        lookup_key: The lookup key for this flow (see :func:`store_challenge`).

    Returns:
        The stored challenge string, or ``None`` if no live row exists.
    """
    cursor = conn.execute(
        """
        SELECT challenge
        FROM webauthn_challenges
        WHERE kind = ? AND lookup_key = ? AND expires_at > datetime('now')
        """,
        (kind, lookup_key),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def consume_challenge(
    conn: sqlite3.Connection,
    kind: str,
    lookup_key: str,
) -> int:
    """Delete a challenge after it has been verified, returning rows deleted.

    DELETE-on-consume (not a mark-used flag): a second verify of the same
    challenge finds no row and is rejected. Mirrors the old dict ``pop``.
    Commits so other connections see the deletion.

    The DELETE is the **atomic replay arbiter**: SQLite serializes writers
    (single-writer WAL), so when two workers race to consume the same row,
    exactly one DELETE commits with rowcount 1 and the other -- running after
    the first commits -- matches no row and returns 0. Callers MUST treat a
    return of 0 as "someone else already consumed this challenge" and reject
    the attempt (the login verify path does this to stay replay-proof under
    multiple workers; see E-238-06 AC-2). The earlier non-atomic
    :func:`get_challenge` read is therefore only advisory -- this DELETE is the
    real gate.

    Args:
        conn: Open SQLite connection.
        kind: ``'login'`` or ``'registration'``.
        lookup_key: The lookup key for this flow (see :func:`store_challenge`).

    Returns:
        Number of rows deleted: 1 if this caller won the consume, 0 if the row
        was already gone (lost the race / already consumed / expired-and-swept).
    """
    cursor = conn.execute(
        "DELETE FROM webauthn_challenges WHERE kind = ? AND lookup_key = ?",
        (kind, lookup_key),
    )
    conn.commit()
    return cursor.rowcount
