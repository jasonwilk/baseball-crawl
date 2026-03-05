# E-043: Dev Environment Auth and Networking Fix

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Fix the dev environment so the magic link auth flow works end-to-end when accessing the app at `http://baseball.localhost:8001`. The APP_URL, WEBAUTHN_ORIGIN, and WEBAUTHN_RP_ID defaults currently assume `localhost:8000` (Traefik), but the user accesses the app directly at `baseball.localhost:8001` (bypassing Traefik). Magic links generated with the wrong base URL silently break the login flow, and WebAuthn origin/RP ID mismatches break passkey registration.

## Background & Context
The user confirmed they access the app at `http://baseball.localhost:8001/auth/login`. This is the direct-to-container path (docker-compose maps `127.0.0.1:8001:8000`), using the `baseball.localhost` hostname.

The current defaults in `src/api/routes/auth.py`:
- `APP_URL` defaults to `http://localhost:8000`
- `WEBAUTHN_ORIGIN` defaults to `http://localhost:8000`
- `WEBAUTHN_RP_ID` defaults to `localhost`

All three are wrong for the actual access pattern:
- Magic links use `http://localhost:8000/auth/verify?token=...` -- wrong host and port.
- WebAuthn origin check expects `http://localhost:8000` but the browser sends `http://baseball.localhost:8001`.
- WebAuthn RP ID is `localhost` but the browser hostname is `baseball.localhost`.

No expert consultation required -- this is a dev-environment configuration issue.

## Goals
- Magic link auth flow works end-to-end when accessing the app at `http://baseball.localhost:8001`
- APP_URL, WEBAUTHN_ORIGIN, and WEBAUTHN_RP_ID defaults match the actual dev access pattern
- `.env.example` comments reflect the correct dev defaults and explain when to override

## Non-Goals
- Production auth flow changes (production uses Cloudflare Tunnel, not Traefik)
- Changing the docker-compose port mappings
- Adding new auth features

## Success Criteria
- A developer can run `docker compose up`, visit `http://baseball.localhost:8001/auth/login`, submit their email, and click the magic link from the app logs to complete login -- without setting any env vars.
- `.env.example` documents the correct defaults and explains when to override.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-043-01 | Fix dev auth defaults and verify Traefik routing | DONE | None | software-engineer |

## Technical Notes

### The Problem
Three defaults in `src/api/routes/auth.py` are wrong for the actual dev access pattern (`http://baseball.localhost:8001`):
- `_APP_URL_DEFAULT = "http://localhost:8000"` -- wrong host and port
- `_get_webauthn_origin()` returns `"http://localhost:8000"` -- wrong host and port
- `_get_webauthn_rp_id()` returns `"localhost"` -- wrong; browser sends `baseball.localhost`

### The Fix
1. Change `_APP_URL_DEFAULT` from `http://localhost:8000` to `http://baseball.localhost:8001`.
2. Change `_get_webauthn_origin()` default from `http://localhost:8000` to `http://baseball.localhost:8001`.
3. Change `_get_webauthn_rp_id()` default from `localhost` to `baseball.localhost`.
4. Update `.env.example` comments to reflect the correct dev defaults and explain when to override.
5. Verify Traefik routing status and document it.

### Key Files
- `src/api/routes/auth.py` -- APP_URL default, WEBAUTHN_ORIGIN default, WEBAUTHN_RP_ID default
- `.env.example` -- documentation of env vars and their defaults

## Open Questions
None.

## History
- 2026-03-05: Created. No expert consultation required -- dev-environment config issue.
- 2026-03-05: E-043-01 DONE. Changed three defaults in auth.py and updated .env.example. All existing tests unaffected (they set env vars explicitly). No documentation impact -- changes are self-documenting via .env.example comments. Epic COMPLETED.
