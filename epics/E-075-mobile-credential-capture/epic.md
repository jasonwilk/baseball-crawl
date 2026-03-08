# E-075: Mobile Profile Credential Capture and Validation

## Status
`ACTIVE`

## Overview
Establish a complete mobile credential pipeline -- from proxy capture through programmatic token refresh -- so the project can make authenticated API calls as the iOS GameChanger app. This epic starts with research to resolve key unknowns (client key parity, auth flow differences) before modifying any code.

## Background & Context
The web profile has a fully working credential chain: client ID + client key (from JS bundle), refresh token (from browser capture, self-renewing via programmatic refresh), and device ID. The mobile profile has only a device ID (`GAMECHANGER_DEVICE_ID_MOBILE`) and app name (`GAMECHANGER_APP_NAME_MOBILE=iOS`).

Three critical credentials are missing for mobile:
1. **Refresh token** -- returned in POST /auth response body, but the proxy addon only has a `request()` handler (no response body parsing).
2. **Client ID** -- sent as `gc-client-id` header in mobile traffic, but the addon does not capture this header.
3. **Client key** -- embedded in the iOS app binary. May or may not be the same as the web key.

The proxy credential extractor addon (`proxy/addons/credential_extractor.py`) also has stale env var names: it writes `GAMECHANGER_AUTH_TOKEN_*` and `GAMECHANGER_SIGNATURE_*`, but the documented names are `GAMECHANGER_REFRESH_TOKEN_*` and signatures are now computed (not stored). The `GameChangerClient` (`src/gamechanger/client.py`) also still reads `GAMECHANGER_AUTH_TOKEN_*` internally, creating a naming mismatch with `.env.example` which uses `GAMECHANGER_REFRESH_TOKEN_*`.

This epic is deliberately separate from E-073 (API doc validation sweep) because mobile reverse-engineering has a different risk profile: we are discovering unknowns about the iOS app's auth implementation, not just validating documented endpoints.

No expert consultation required -- this is operator tooling and credential infrastructure. The research stories serve as the discovery mechanism.

## Goals
- Determine whether the mobile client key is the same as the web client key
- Capture all mobile credentials (client ID, refresh token) via the proxy addon
- Align env var naming across addon, client, and .env.example (resolve AUTH_TOKEN vs. REFRESH_TOKEN inconsistency)
- Validate mobile programmatic token refresh end-to-end (if client key is obtainable)

## Non-Goals
- iOS binary reverse engineering (if the client key differs from web, that becomes a separate effort)
- Mobile-specific crawlers or data pipelines (that is downstream work)
- Changes to the `GameChangerClient` API surface (only credential loading internals)
- E-073 API doc validation work (separate epic, separate risk profile)

## Success Criteria
- Mobile proxy session can capture client ID and refresh token automatically
- Env var naming is consistent across addon, client code, and .env.example
- If mobile client key == web client key: programmatic mobile token refresh is confirmed working
- If mobile client key != web client key: a clear finding document explains what was discovered and what is needed next

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-075-R-01 | Mobile Auth Flow Reconnaissance | DONE | None | api-scout |
| E-075-01 | Align Credential Env Var Names | DONE | None | software-engineer |
| E-075-02 | Add gc-client-id and Response Body Capture to Proxy Addon | TODO | E-075-R-01, E-075-01 | - |
| E-075-03 | Mobile Credential Validation Script | TODO | E-075-R-01, E-075-01 | - |

## Dispatch Team
- software-engineer
- api-scout

## Technical Notes

### Credential Naming Inconsistency (Pre-existing)
The project has a naming split that predates this epic:
- `.env.example` and `docs/api/auth.md` use `GAMECHANGER_REFRESH_TOKEN_WEB`
- `src/gamechanger/client.py` reads `GAMECHANGER_AUTH_TOKEN_WEB` (line 44, 63, 128)
- `proxy/addons/credential_extractor.py` writes `GAMECHANGER_AUTH_TOKEN_*` (line 33)
- `src/gamechanger/credential_parser.py` uses `GAMECHANGER_AUTH_TOKEN_WEB` (line 31, 176)

Story E-075-01 resolves this by aligning everything to `GAMECHANGER_REFRESH_TOKEN_*`, which is the correct semantic name (the stored token IS the refresh token, per `docs/api/auth.md`).

### Proxy Addon Architecture
The credential extractor (`proxy/addons/credential_extractor.py`) currently:
- Has only a `request()` handler -- no response body parsing
- Captures: `gc-token`, `gc-device-id`, `gc-app-name`, `gc-signature`
- Does NOT capture: `gc-client-id` (needed for mobile)
- Writes stale key names: `GAMECHANGER_AUTH_TOKEN_*`, `GAMECHANGER_SIGNATURE_*`

Story E-075-02 adds a `response()` handler and `gc-client-id` capture. This depends on E-075-01 (name alignment) to avoid writing stale names.

### Wave Structure
- **Wave 1** (parallel): E-075-R-01 (research) + E-075-01 (naming cleanup)
- **Wave 2** (after wave 1): E-075-02 (addon upgrade) + E-075-03 (validation script) -- parallel with each other, both depend on R-01 findings and 01 naming

### Key Files
| File | Stories |
|------|---------|
| `proxy/addons/credential_extractor.py` | E-075-01, E-075-02 |
| `src/gamechanger/client.py` | E-075-01 |
| `src/gamechanger/credential_parser.py` | E-075-01 |
| `.env.example` | E-075-01 |
| `tests/test_credential_extractor.py` | E-075-01, E-075-02 |
| `tests/test_credential_parser.py` | E-075-01 |
| `tests/test_client.py` | E-075-01 |
| `scripts/check_credentials.py` | E-075-03 |
| `src/gamechanger/credentials.py` | E-075-03 |

### Decision Point After Research -- RESOLVED (2026-03-08)
**Outcome: Mobile client key is CONFIRMED DIFFERENT from web.** Direct test: signing a POST /auth refresh with the web client key returned 401 Unauthorized. The iOS app is purely native (no JS bundles in mobile traffic). The mobile client key is embedded in the iOS binary -- extraction requires IPA binary analysis (out of scope for E-075).

**What this means for remaining stories:**
- **E-075-02 (addon upgrade)**: Proceeds as written. Capturing gc-client-id and response bodies is still valuable for future proxy sessions. No scope change needed.
- **E-075-03 (validation)**: Proceeds as written. AC-4 (client key absent, partial check) is now the expected mobile path, not the edge case. The script validates tokens we CAN capture (presence, JWT decode, GET /me/user) and reports that programmatic refresh is unavailable without the client key.
- **Programmatic mobile token refresh**: Blocked until the mobile client key is extracted. Manual recapture every 14 days via proxy is the workaround.

**Workaround**: The mobile refresh token (14-day lifetime) works directly as `gc-token` for regular GET endpoints without needing the signing key. Only POST /auth refresh calls require gc-signature (and thus the client key).

## Open Questions
- None remaining -- all open questions are addressed by E-075-R-01 research spike

## History
- 2026-03-08: Created
- 2026-03-08: R-01 and 01 completed. Key finding: mobile client key is CONFIRMED DIFFERENT from web (401 on direct test). iOS app is purely native (no JS bundles). Workaround: mobile tokens work directly as gc-token for GET endpoints. Wave 2 (02 + 03) unblocked.
