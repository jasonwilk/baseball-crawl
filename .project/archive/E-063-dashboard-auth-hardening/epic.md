# E-063: Dashboard Auth Hardening

## Status
`COMPLETED`

## Overview
Close authentication and UX gaps in the dashboard so that unauthenticated visitors cannot access protected pages, the dev bypass cannot leak into production, and auth-adjacent pages (login, errors) present a clean, nav-free experience. This is a security and polish epic -- no new features, just making existing auth work correctly.

## Background & Context
The operator (Jason) reported that he could access the dashboard without authentication. An assessment found four primary gaps plus three additional security concerns surfaced by SE consultation:

1. **DEV_USER_EMAIL production risk** -- The dev bypass grants full admin access (`is_admin=1`) with no guard preventing it from running in production. An accidental `.env` misconfiguration silently disables all authentication.
2. **No root route `/`** -- Visitors get a 404 instead of a redirect to the dashboard or login.
3. **No-such-table bypass** -- When migrations are not applied, the auth middleware catches `OperationalError` and lets requests through unauthenticated.
4. **Nav bar visible on login page** -- `base.html` always renders the bottom nav, even on auth pages where those links are meaningless.
5. **No magic link rate limiting** -- `POST /auth/login` issues a magic link on every request with no cooldown.
6. **Stale magic link tokens** -- Old tokens remain valid when new ones are issued for the same user.

Expert consultations:
- **SE** (2026-03-07): Full auth surface audit. Identified 7 findings, 4 high-priority (DEV_USER_EMAIL guard, missing-table fail-closed, magic link rate limiting, stale token invalidation). Confirmed CSRF is acceptable with SameSite=lax + Cloudflare Zero Trust. Confirmed passkey in-memory store is acceptable for single-worker deployment. SE clarified that missing-table bypass allows dashboard to render without auth (empty user dict passes through) -- this is the root cause of the reported bug.
- **UXD** (2026-03-07): Recommended `base_auth.html` template for nav-free auth pages, `/` -> `/dashboard` redirect, and styled error pages (403 rework, new 404/500). All auth templates extend `base_auth.html`.

## Goals
- Prevent DEV_USER_EMAIL from operating in production environments
- Fail closed when auth tables are missing (503 instead of passthrough)
- Ensure `/` routes to a useful destination
- Harden magic link flow against rate abuse and stale token reuse
- Provide a clean, nav-free experience for login and error pages

## Non-Goals
- CSRF token protection (SameSite=lax + Cloudflare Zero Trust is sufficient for current threat model)
- Moving passkey challenge store to SQLite (acceptable for single-worker deployment)
- Adding new auth methods or changing the login flow
- Modifying Cloudflare Zero Trust configuration
## Success Criteria
- App refuses to start when `DEV_USER_EMAIL` is set with `APP_ENV=production`
- Auth middleware returns 503 when auth tables are missing (instead of passing requests through)
- `GET /` redirects to `/dashboard`
- Login page and error pages render without bottom nav
- Magic links for the same user are invalidated when a new one is issued
- Magic link issuance has a per-user cooldown

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-063-01 | DEV_USER_EMAIL production guard | DONE | None | se-1 |
| E-063-02 | Root route redirect | DONE | None | se-2 |
| E-063-03 | Auth page template and error pages | DONE | E-063-02 | se-2 |
| E-063-04 | Invalidate stale magic link tokens | DONE | None | se-3 |
| E-063-05 | Magic link rate limiting | DONE | E-063-04 | se-3 |
| E-063-06 | Fail closed on missing auth tables | DONE | E-063-01 | se-1 |

## Dispatch Team
- software-engineer

## Technical Notes

### Auth Architecture
- Session middleware: `src/api/auth.py` -- `SessionMiddleware` validates cookies on all non-excluded routes. Excluded: `/auth/*`, `/health`, `/static/*`.
- Dev bypass: `DEV_USER_EMAIL` env var triggers auto-creation of admin user + session on every request (lines 264-280).
- Admin guard: `_require_admin()` in `src/api/routes/admin.py` checks `request.state.user.is_admin`.
- Magic link flow: `POST /auth/login` -> `GET /auth/verify?token=...` -> session created -> redirect.
- Passkey flow: `GET /auth/passkey/login/options` -> browser assertion -> `POST /auth/passkey/login/verify` -> session created.

### Template Hierarchy
- `base.html` -- full chrome (top bar + bottom nav). Used by dashboard and admin pages.
- `base_auth.html` (NEW) -- minimal chrome (top bar only, no bottom nav). Used by auth pages and error pages.
- Auth templates (6 files): `auth/login.html`, `auth/check_email.html`, `auth/verify_error.html`, `auth/passkey_prompt.html`, `auth/passkey_register.html`, `auth/passkey_error.html`.
- Error templates: `errors/forbidden.html` (exists, needs rework), `errors/404.html` (new), `errors/500.html` (new).

### Known Limitations (Not Addressed)
- **Passkey challenge store**: In-memory dict (`_PASSKEY_LOGIN_CHALLENGES`). Breaks with `--workers N > 1`. Documented in code comment. Acceptable for single-worker deployment.
- **CSRF**: No token-based CSRF protection. `SameSite=lax` cookies + Cloudflare Zero Trust sufficient for current threat model (all users are trusted coaching staff behind network-level auth).
- **Missing-table fallback**: Addressed in E-063-06 (fail closed with 503).

## Open Questions
- None

## History
- 2026-03-07: Created. SE consultation (auth surface audit, 7 findings). UXD consultation (template hierarchy, error pages, root route). Added E-063-06 (fail closed on missing tables) after SE clarified that missing-table bypass is the root cause of dashboard-without-auth bug.
- 2026-03-07: Codex spec review triage. REFINED: E-063-03 AC-7 removed (redundant with AC-8); E-063-05 AC-1/AC-2 cooldown boundary clarified (strictly <60s); E-063-05 AC-4 updated (`created_at` confirmed existing); E-063-05 migrations removed from Files list; E-063-03 blocked by E-063-02 (main.py conflict); E-063-06 blocked by E-063-01 (auth.py conflict). DISMISSED: test file overlap (additive, not conflicting); migration routing concern (no migration needed); missing DE consultation (moot).
- 2026-03-07: All 6 stories completed. Wave 1 (01, 02, 04) dispatched in parallel; wave 2 (06, 03, 05) cascaded as dependencies cleared. Key artifacts: `src/api/auth.py` (production guard + fail-closed 503), `src/api/main.py` (root redirect + 404/500 exception handlers), `src/api/routes/auth.py` (stale token invalidation + rate limiting), `src/api/templates/base_auth.html` (new minimal template), error pages (403 rework, new 404/500). Notable: se-1 found and fixed a subtle bug where `_handle_dev_bypass` caught `sqlite3.Error` (parent class) before dispatch could see `OperationalError` for the 503 path. No documentation impact -- no new user-facing features, deployment procedures, or API changes.
