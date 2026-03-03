# E-023: Authentication and Team-Level Permissions

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Add real authentication for all users (magic link + optional passkey) and team-scoped authorization to the coaching dashboard, so each coach sees only the teams they are assigned to. Admin routes (`/admin`) are protected at the network layer by Cloudflare Access policies -- the app itself does not perform admin route authentication.

## Background & Context

### What exists today
The dashboard is accessible behind Cloudflare Tunnel + Zero Trust. The current `/dashboard` route is hardcoded to LSB Varsity 2026. There is no concept of per-coach access or team scoping.

### Why the old design was wrong
The original E-023 design assumed coaches would authenticate via Cloudflare Access (WARP or email OTP). This is wrong: coaches cannot install WARP, and asking them to use Cloudflare's email OTP flow is a poor UX. Coaches are just hitting a URL in their browser. The app needs its own lightweight auth for all users.

### The revised architecture
**All users authenticate at the app level.** The magic link + passkey system is the single identity layer for the application. Cloudflare handles only two separate concerns: routing (tunnel) and admin network protection (Access policy).

1. **User visits login page** -- enters their email address.
2. **App sends a magic link** via Mailgun (15-minute TTL, hashed token stored in DB, single-use).
3. **User clicks link** -- app validates the token, creates a session (SQLite `sessions` table), sets an HTTP-only secure session cookie (7-day TTL).
4. **Optional passkey registration** -- after first magic link login, the user can register a passkey (WebAuthn via `py_webauthn`). Future logins: passkey tap OR "email me a link."
5. **Admin routes** (`/admin/*`) are protected at the **network layer** by Cloudflare Access policies (WARP required to reach them). The app does NOT inspect Cloudflare headers or perform any admin-specific auth -- it trusts that anyone who reaches `/admin` has already been cleared by Cloudflare. The app uses the normal session cookie + `is_admin` flag to identify the user.

### Two concerns, two layers
- **Cloudflare Tunnel**: Routes all traffic (coach and admin) from the public internet to the VPS. This is purely a routing mechanism. Coaches access the dashboard via a normal public URL -- no WARP, no special client software.
- **Cloudflare Access policy on `/admin`**: Requires WARP to reach `/admin/*` paths. This is network-level protection. Non-WARP users never reach the app's `/admin` routes at all.
- **Magic link + passkey (app-level)**: The identity layer for ALL users. Coaches and admins alike log in via magic link or passkey. The app's session middleware determines who the user is. The `is_admin` flag in the `users` table controls what they can do (e.g., see the admin link, access admin features).

Admins get two access paths:
1. WARP + magic link/passkey session --> `/admin` routes (manage coaches)
2. Magic link/passkey session (no WARP needed) --> `/dashboard` routes (same view as coaches)

### Expert consultation
- **baseball-coach**: No formal consultation required. Auth UX is an infrastructure concern, not a coaching-domain question. Coaches need a simple login flow that works on a phone browser -- magic link + passkey delivers that.
- **data-engineer**: No formal consultation required. Schema additions are four small tables in one migration file. The existing `apply_migrations.py` tooling handles it.

### Key design decisions
1. **Magic link, not passwords.** Coaches will not remember yet another password. Email magic link is the simplest auth that does not require password management, reset flows, or bcrypt.
2. **Passkeys as optional upgrade.** After magic link login, coaches can register a passkey on their device for faster future access. This is additive, not required.
3. **SQLite sessions table, not signed cookies.** A `sessions` table avoids needing a cookie-signing secret (`itsdangerous`) and makes session revocation trivial (delete the row). The session cookie contains only a random token; the server looks up the session in DB.
4. **Mailgun for email, stdout in dev.** Mailgun API via `httpx` (already in `requirements.txt`; no SDK). When `MAILGUN_API_KEY` is not set, the magic link is logged to stdout so local dev works without email infrastructure.
5. **Admin route protection via Cloudflare, not the app.** Cloudflare Access policy requires WARP to reach `/admin/*`. The app does NOT inspect Cloudflare headers. Once a request reaches `/admin`, the app trusts it and only checks the session cookie + `is_admin` flag (same session system as coaches). This keeps the app's auth model unified -- one session system for all users.
6. **No auth frameworks.** No Flask-Login, no FastAPI-Users, no Authlib. Just middleware + DB queries.
7. **`DEV_USER_EMAIL` bypass.** When `DEV_USER_EMAIL` is set, the auth middleware skips the login page entirely and auto-creates a session for that email. This keeps local dev frictionless.

## Goals
- Coaches can log in via magic link email without installing anything or managing passwords
- Coaches can optionally register a passkey for faster future logins
- Each coach sees only the teams they are assigned to on the dashboard
- Jason can manage coach accounts and team assignments via an admin page (network-protected by Cloudflare Access/WARP; app-level auth via session + is_admin flag)
- Local development works without Mailgun or Cloudflare (dev user bypass)

## Non-Goals
- Password-based authentication (no passwords anywhere in this system)
- Self-service registration (Jason adds coaches manually via admin page)
- Role-based access beyond admin/non-admin (the dashboard is read-only)
- Per-game or per-player permissions (access is at the team level only)
- Audit logging of who viewed what (can be added later)
- Multi-factor authentication beyond passkey (magic link + passkey IS the MFA story)
- OAuth/OIDC integration
- Email verification beyond the magic link itself (the magic link IS email verification)

## Success Criteria
- A coach can enter their email, receive a magic link, click it, and see their team's dashboard
- A coach with a registered passkey can log in with a tap instead of waiting for an email
- A coach assigned to Varsity sees Varsity data and cannot navigate to JV data
- A coach assigned to both JV and Freshman sees a team selector and can switch between them
- An admin (Jason) sees all teams on the dashboard and can access the admin page (admin page requires WARP at the network layer + session + is_admin in the app)
- An unauthenticated request to the dashboard redirects to the login page
- An unrecognized email (not in the users table) sees the same "If this email is registered, you will receive a login link" message as a recognized email (no enumeration)
- Local dev works with `DEV_USER_EMAIL` and no Mailgun/Cloudflare
- Magic link tokens expire after 15 minutes and cannot be reused
- Sessions expire after 7 days

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-023-01 | Auth schema migration | DONE | None | general-dev |
| E-023-02 | Magic link login flow | DONE | E-023-01 | general-dev |
| E-023-03 | Passkey registration and login | DONE | E-023-02 | general-dev |
| E-023-04 | Team-scoped dashboard | DONE | E-023-02 | general-dev |
| E-023-05 | Admin page for managing coaches | DONE | E-023-02, E-023-04 | general-dev |

## Technical Notes

### Schema additions (migration 003)
```sql
-- migrations/003_auth.sql

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_team_access (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    team_id TEXT NOT NULL REFERENCES teams(team_id),
    UNIQUE(user_id, team_id)
);

CREATE INDEX IF NOT EXISTS idx_user_team_access_user ON user_team_access(user_id);

CREATE TABLE IF NOT EXISTS magic_link_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    expires_at TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_magic_link_tokens_hash ON magic_link_tokens(token_hash);

CREATE TABLE IF NOT EXISTS passkey_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    credential_id BLOB NOT NULL UNIQUE,
    public_key BLOB NOT NULL,
    sign_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_passkey_credentials_user ON passkey_credentials(user_id);
CREATE INDEX IF NOT EXISTS idx_passkey_credentials_cred ON passkey_credentials(credential_id);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_token_hash TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(session_token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
```

### Authentication flows

**Magic link flow:**
```
Coach -> GET /auth/login (login page with email form)
Coach -> POST /auth/login (email submitted)
  -> Server looks up email in users table
  -> If not found: render "If this email is registered, you will receive a login link." (same page as found case, to prevent enumeration)
  -> If found: generate 32-byte random token, hash with SHA-256, store in magic_link_tokens
  -> Send email via Mailgun with link: /auth/verify?token=<raw_token>
  -> (Dev mode: log the link to stdout instead)
  -> Render "If this email is registered, you will receive a login link." confirmation page
Coach -> GET /auth/verify?token=<raw_token>
  -> Server hashes the token, looks up in magic_link_tokens
  -> Validates: exists, not expired (< 15 min), not already used
  -> Marks token as used (set used_at)
  -> Creates session: generate 32-byte random token, hash, store in sessions table
  -> Sets HTTP-only secure cookie: session=<raw_session_token>, max-age=7 days
  -> Redirects to /dashboard
```

**Passkey registration flow (after magic link login):**
```
Coach -> GET /auth/passkey/register (registration page, requires active session)
  -> Server generates WebAuthn registration options via py_webauthn
  -> Returns options to browser
Coach's browser -> navigator.credentials.create(options)
  -> Browser prompts for biometric/PIN
  -> Returns attestation response
Coach -> POST /auth/passkey/register (attestation response)
  -> Server verifies via py_webauthn
  -> Stores credential_id, public_key, sign_count in passkey_credentials
  -> Redirects to /dashboard with success message
```

**Passkey login flow:**
```
Coach -> GET /auth/login (login page now shows "Use passkey" button)
Coach -> clicks "Use passkey"
  -> Browser JavaScript calls GET /auth/passkey/login/options
  -> Server generates WebAuthn authentication options via py_webauthn
  -> Returns options to browser
Coach's browser -> navigator.credentials.get(options)
  -> Browser prompts for biometric/PIN
  -> Returns assertion response
Coach -> POST /auth/passkey/login/verify (assertion response)
  -> Server verifies via py_webauthn, updates sign_count
  -> Creates session (same as magic link verify)
  -> Sets session cookie, redirects to /dashboard
```

**Session middleware:**
```
Every request:
  -> Check for session cookie
  -> If present: hash token, look up in sessions table, check not expired
  -> If valid session: attach user + permitted_teams to request.state
  -> If no session or expired: redirect to /auth/login (for dashboard/protected routes)
  -> /auth/* routes, /health, and static assets are excluded from session check
```

**Admin route protection (two layers):**
```
Layer 1 -- Cloudflare Access policy (network layer, NOT the app's job):
  -> Cloudflare Access policy on /admin/* requires WARP
  -> Non-WARP traffic never reaches the app
  -> The app does NOT inspect Cf-Access-Jwt-Assertion or any CF header

Layer 2 -- App-level admin guard (same session system as coaches):
  -> Request to /admin/* passes through the same session middleware as /dashboard
  -> Session middleware attaches request.state.user (from session cookie)
  -> Admin guard checks request.state.user["is_admin"] == 1
  -> If no session: redirect to /auth/login (same as dashboard)
  -> If session exists but is_admin != 1: return 403
  -> If valid admin session: proceed
```

NOTE: In production, Layer 1 means only WARP users can even reach /admin.
In dev mode, there is no Cloudflare, so only Layer 2 applies (the DEV_USER_EMAIL
bypass auto-creates an admin session).

### Dev mode bypass
When `DEV_USER_EMAIL` environment variable is set:
- The session middleware auto-creates a session for that email on every request (no login page needed)
- If the user does not exist in the DB, auto-create with `is_admin=1` and `display_name="Dev Admin"`
- Since the admin guard uses the session (same as coaches), the dev bypass works for admin routes automatically -- no special admin override needed
- This means local dev works immediately after running the migration -- no Mailgun, no WARP, no login page

### Email sending
- **Production**: Mailgun API via `httpx` (already in `requirements.txt`; no SDK). The endpoint is `https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages`. Auth is HTTP Basic with `api:MAILGUN_API_KEY`.
- **Dev mode**: When `MAILGUN_API_KEY` is not set, log the full magic link URL to stdout at INFO level.
- Environment variables: `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`, `MAILGUN_FROM_EMAIL` (defaults to `noreply@{MAILGUN_DOMAIN}`).

### Dependencies (Python packages)
- `py_webauthn` -- WebAuthn/passkey registration and authentication. Well-maintained, wraps the W3C spec.
- No other new dependencies. Mailgun is called via `httpx` (already in `requirements.txt`). Token generation uses `secrets` (stdlib). Hashing uses `hashlib` (stdlib).

### Session cookie details
- Name: `session`
- Value: raw 32-byte token, hex-encoded (64 characters)
- Flags: `HttpOnly`, `Secure` (except in dev), `SameSite=Lax`, `Path=/`
- Max-Age: 604800 (7 days)
- The server stores only the SHA-256 hash of the token, never the raw token

### File layout (new files)
```
migrations/003_auth.sql                          -- Schema migration
src/api/auth.py                                  -- Session middleware + auth helpers
src/api/routes/auth.py                           -- Login/verify/passkey routes
src/api/routes/admin.py                          -- Admin CRUD routes
src/api/email.py                                 -- Mailgun email sending
src/api/templates/auth/login.html                -- Login page (email + passkey)
src/api/templates/auth/check_email.html          -- "Check your email" confirmation
src/api/templates/auth/passkey_prompt.html        -- Post-login interstitial with passkey CTA
src/api/templates/auth/passkey_register.html     -- Passkey registration page
src/api/templates/admin/users.html               -- Admin user list page
src/api/templates/admin/edit_user.html           -- Admin edit user page
src/api/templates/errors/forbidden.html          -- 403 page
tests/test_auth.py                               -- Auth middleware tests
tests/test_auth_routes.py                        -- Login/verify route tests
tests/test_passkey.py                            -- Passkey flow tests
tests/test_admin.py                              -- Admin route tests
```

### Files modified
```
src/api/main.py                                  -- Register auth middleware + auth/admin routers
src/api/routes/dashboard.py                      -- Filter by permitted teams
src/api/templates/dashboard/team_stats.html      -- Add team selector + user display + logout link
.env.example                                     -- Add DEV_USER_EMAIL, MAILGUN_API_KEY, MAILGUN_DOMAIN
requirements.txt                                 -- Add py_webauthn
```

### Parallel execution notes
- E-023-01 (schema) has no file conflicts and can run independently.
- E-023-02 (magic link) depends on E-023-01 (needs tables). Creates `src/api/auth.py`, `src/api/routes/auth.py`, `src/api/email.py`, and modifies `src/api/main.py`.
- E-023-03 (passkeys) depends on E-023-02 (needs session infrastructure). Modifies `src/api/routes/auth.py` and `src/api/templates/auth/login.html`.
- E-023-04 (dashboard) depends on E-023-02 (needs session middleware). Modifies `src/api/routes/dashboard.py` and dashboard templates.
- E-023-03 and E-023-04 CAN run in parallel (no file conflicts -- E-023-03 touches auth routes/templates only, E-023-04 touches dashboard routes/templates). The passkey registration CTA is shown on a dedicated post-verification interstitial page (`src/api/templates/auth/passkey_prompt.html`), NOT on the dashboard template, to avoid file conflicts with E-023-04.
- E-023-05 (admin) depends on E-023-02 and E-023-04. Creates `src/api/routes/admin.py` and admin templates. Also modifies `src/api/main.py` (register admin router) and `src/api/templates/dashboard/team_stats.html` (admin link). The template file conflict with E-023-04 requires sequential execution: E-023-04 first, then E-023-05. Admin routes use the same session middleware as dashboard routes (no separate CF JWT auth in the app).

### RP_ID and origin for WebAuthn
- Production: `RP_ID` is the domain name (e.g., `baseball.example.com`). `ORIGIN` is `https://baseball.example.com`. These come from environment variables `WEBAUTHN_RP_ID` and `WEBAUTHN_ORIGIN`.
- Dev: `RP_ID=localhost`, `ORIGIN=http://localhost:8000`.

## Open Questions
None. The user provided a complete architecture specification.

## History
- 2026-03-02: Created as READY with Cloudflare Access JWT-based auth design.
- 2026-03-03: Full rewrite. Replaced Cloudflare Access JWT auth with magic link + passkey for coaches. Cloudflare WARP retained only for Jason's admin access. Added Mailgun for email, py_webauthn for passkeys, SQLite sessions table. Stories restructured from 4 to 5.
- 2026-03-03: Architecture clarification pass. Removed app-level CF JWT header inspection for admin routes. Admin route protection is now two layers: (1) Cloudflare Access policy at the network level (WARP required), (2) app-level session + is_admin guard. The app has one unified auth system (magic link + passkey + session) for all users. Admins can also access the dashboard via the same magic link/passkey flow without WARP.
- 2026-03-03: **Codex spec review refinement.** Reviewed 11 findings (4 P1, 6 P2, 1 P3). Accepted 9, rejected 2.
  - **Finding 1 (P1, ACCEPTED)**: Fixed login UX contract. AC-3 wins: both known and unknown emails render the same "If this email is registered..." response. Updated epic Success Criteria and magic link flow description. Updated E-023-02 AC-2 to explicitly render the same page as AC-3.
  - **Finding 2 (P1, ACCEPTED)**: Clarified passkey register endpoint. E-023-03 AC-2 now specifies: the route renders an HTML page that embeds registration options as JSON and includes inline JS to call navigator.credentials.create(). Not a separate JSON endpoint.
  - **Finding 3 (P1, ACCEPTED)**: Fixed bootstrap SQL one-liner in E-023-05 AC-11. Changed `user_email` to `email` to match the schema definition in E-023-01 AC-1.
  - **Finding 4 (P1, ACCEPTED)**: Fixed parallel execution claim for E-023-03/E-023-04. Added `src/api/templates/auth/passkey_prompt.html` as a dedicated post-login interstitial to E-023-03. The passkey CTA lives on this new template, not on the dashboard, eliminating the file conflict. Updated E-023-03 AC-1 accordingly.
  - **Finding 5 (P2, ACCEPTED)**: Resolved WebAuthn challenge storage ambiguity in E-023-03. Removed "temporary cookie" option from technical approach. AC-11 now explicitly says server-side storage only. Technical approach clarified: session row for registration challenges, ephemeral DB table or in-memory dict for login challenges.
  - **Finding 6 (P2, ACCEPTED)**: Added `src/api/templates/errors/forbidden.html` to E-023-05 file list and updated technical approach to render it instead of raising bare HTTPException(403).
  - **Finding 7 (P2, ACCEPTED)**: Added `tests/test_dashboard.py` to E-023-02 modified files list. Existing unauthenticated dashboard tests will break when auth middleware is added; E-023-02 must update them to provide valid sessions. Also added to E-023-04 notes.
  - **Finding 8 (P2, REJECTED)**: E-023-02 is large but coherent. Splitting would create artificial dependencies between login, session, and email concerns that are tightly coupled. Acknowledged size in story notes.
  - **Finding 9 (P2, ACCEPTED)**: Fixed HTTP library reference. Changed `requests` to `httpx` throughout epic Technical Notes and E-023-02 AC-11. `httpx` is already in requirements.txt; `requests` is not.
  - **Finding 10 (P2, ACCEPTED)**: Added coordination note to E-023-01 about E-003-01 dependency risk. E-003-01 is rewriting 001_initial_schema.sql (ACTIVE). If E-003-01 changes the `teams` table structure, `user_team_access` FKs may need adjustment.
  - **Finding 11 (P3, REJECTED)**: Boilerplate DoD lines are conventional scaffolding. Story-specific acceptance criteria are the real contract for implementing agents. Not worth the churn to remove.
- 2026-03-03: **Epic COMPLETED.** All 5 stories dispatched and verified. Wave execution: 01 (schema) → 02 (magic link) → 03+04 (passkeys + dashboard, parallel) → 05 (admin). Full test suite: 385 passed, 0 failures. Key artifacts: migrations/003_auth.sql, src/api/auth.py (session middleware), src/api/routes/auth.py (magic link + passkey routes), src/api/routes/admin.py (admin CRUD), src/api/email.py (Mailgun helper), 6 HTML templates, 4 test files. Added python-multipart and webauthn to requirements.txt. No documentation impact (no existing docs affected by auth addition).
