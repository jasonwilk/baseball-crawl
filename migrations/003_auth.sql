-- Migration 003: Auth tables (E-023)
--
-- Creates all tables required for authentication and team-level access control:
--   - users: coaching staff accounts (email + display name)
--   - user_team_access: team-scoped access grants (join table)
--   - magic_link_tokens: one-time email login tokens (hashed)
--   - passkey_credentials: WebAuthn/FIDO2 passkey registrations
--   - sessions: authenticated session tokens (hashed)
--
-- Auth lifecycle supported:
--   - Magic link login: request token -> click link -> verify hash -> create session
--   - Passkey registration: register credential -> sign challenge -> verify -> create session
--   - Session management: check session_token_hash to authorize requests
--   - Team-scoped access: user_team_access restricts which teams a user can view
--
-- Conventions (same as 001_initial_schema.sql):
--   - Primary keys: <table_singular>_id or id (INTEGER AUTOINCREMENT surrogate)
--   - Timestamps:   TEXT in ISO 8601 format, DEFAULT (datetime('now'))
--   - Booleans:     INTEGER 0/1
--   - Sensitive values (tokens, keys): stored hashed or as BLOB, never plaintext
--
-- See E-023 for full auth design rationale and implementation details.

-- ---------------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------------
-- Every coaching staff member who can log in. is_admin=1 grants access to the
-- admin page (E-023-05) for managing users and team access grants.
CREATE TABLE IF NOT EXISTS users (
    user_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    email        TEXT    NOT NULL UNIQUE,
    display_name TEXT    NOT NULL,
    is_admin     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- user_team_access
-- ---------------------------------------------------------------------------
-- Grants a user access to a specific team's data. A user with no rows here
-- sees no team data (unless is_admin=1, which bypasses this check).
-- References teams(team_id) from 001_initial_schema.sql.
CREATE TABLE IF NOT EXISTS user_team_access (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL REFERENCES users(user_id),
    team_id  TEXT    NOT NULL REFERENCES teams(team_id),
    UNIQUE(user_id, team_id)
);

CREATE INDEX IF NOT EXISTS idx_user_team_access_user ON user_team_access(user_id);

-- ---------------------------------------------------------------------------
-- magic_link_tokens
-- ---------------------------------------------------------------------------
-- One-time login tokens sent via email. token_hash is a SHA-256 hash of the
-- raw token; the raw token is never stored. expires_at and used_at enforce
-- single-use and time-bounded validity.
CREATE TABLE IF NOT EXISTS magic_link_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash  TEXT    NOT NULL UNIQUE,
    user_id     INTEGER NOT NULL REFERENCES users(user_id),
    expires_at  TEXT    NOT NULL,
    used_at     TEXT,                                    -- NULL until redeemed
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_magic_link_tokens_hash ON magic_link_tokens(token_hash);

-- ---------------------------------------------------------------------------
-- passkey_credentials
-- ---------------------------------------------------------------------------
-- WebAuthn/FIDO2 passkey registrations. credential_id and public_key are BLOB
-- because py_webauthn works with raw bytes; storing as BLOB avoids
-- base64 encode/decode overhead. sign_count tracks the authenticator's
-- internal counter to detect cloned credentials.
CREATE TABLE IF NOT EXISTS passkey_credentials (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(user_id),
    credential_id BLOB    NOT NULL UNIQUE,
    public_key    BLOB    NOT NULL,
    sign_count    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_passkey_credentials_user          ON passkey_credentials(user_id);
CREATE INDEX IF NOT EXISTS idx_passkey_credentials_credential_id ON passkey_credentials(credential_id);

-- ---------------------------------------------------------------------------
-- sessions
-- ---------------------------------------------------------------------------
-- Authenticated sessions. session_token_hash is a SHA-256 hash of the raw
-- bearer token set in the session cookie; the raw token is never stored.
-- expires_at enforces session lifetime; middleware rejects expired sessions.
CREATE TABLE IF NOT EXISTS sessions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_token_hash  TEXT    NOT NULL UNIQUE,
    user_id             INTEGER NOT NULL REFERENCES users(user_id),
    expires_at          TEXT    NOT NULL,
    challenge           TEXT,                                    -- Ephemeral WebAuthn challenge (NULL when not in a ceremony)
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sessions_token   ON sessions(session_token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
