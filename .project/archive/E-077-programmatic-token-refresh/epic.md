# E-077: Programmatic Token Refresh -- Fix Broken GameChangerClient

## Status
`COMPLETED`

## Overview
The GameChangerClient is sending the refresh token as `gc-token` on all API calls, resulting in 401 on every request. This epic adds a programmatic auth layer that uses the gc-signature signing algorithm to call POST /auth, obtain short-lived access tokens, and transparently manage token lifecycle -- making the client functional again for both web and mobile profiles.

## Background & Context
The client broke when E-075-01 correctly renamed `GAMECHANGER_AUTH_TOKEN_WEB` to `GAMECHANGER_REFRESH_TOKEN_WEB`. The old env var happened to hold a mislabeled access token that worked by accident. Now that an actual refresh token is stored, the client sends it as `gc-token` on GET requests and gets 401.

The gc-signature signing algorithm was fully reverse-engineered on 2026-03-07 and confirmed working from Python. The algorithm is documented in `data/raw/gc-signature-algorithm.md` (JS pseudocode with detailed comments) and was confirmed working from Python via manual testing. All the cryptographic pieces are solved -- this epic productionizes them.

This epic promotes IDEA-015 (Programmatic Auth Module) with a scoped-down focus: token refresh + auto-refresh in the client. The full 4-step login flow and `bb creds refresh` migration are NOT in scope.

Expert consultation completed (2026-03-08): api-scout (auth flow accuracy, header requirements), software-engineer (implementation patterns, test breakage, atomicity), claude-architect (context-layer impact, error message guidance). All core technical claims confirmed accurate. Findings incorporated into stories.

## Goals
- GameChangerClient correctly obtains and uses access tokens instead of sending refresh tokens
- Access tokens are cached in memory and refreshed automatically when expired
- Refresh token rotation is persisted to .env after each refresh call
- Mobile profile works via manual access token fallback when client key is unavailable
- No credentials are logged, committed, or displayed

## Non-Goals
- Full 4-step login flow (client-auth, user-auth, password steps) -- future scope
- Migrating `bb creds refresh` from curl-paste to programmatic refresh -- future scope
- Mobile client key extraction (E-075 scope)
- New API endpoints or crawlers
- Dashboard changes

## Success Criteria
- `GameChangerClient(profile='web').get('/me/user')` returns valid user data (no 401)
- Access token is refreshed transparently when it expires (no caller intervention)
- Updated refresh token is written back to .env after each refresh
- Mobile profile with `GAMECHANGER_ACCESS_TOKEN_MOBILE` set works for API calls
- Mobile profile without client key raises a clear error explaining the limitation
- All existing tests pass; new tests cover signing, token management, and client integration
- No tokens, keys, or signatures appear in logs or error messages

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-077-01 | gc-signature Signing Module | DONE | None | SE |
| E-077-02 | Token Manager | DONE | E-077-01 | SE |
| E-077-03 | GameChangerClient Auth Integration | DONE | E-077-02 | SE |

## Dispatch Team
- software-engineer

## Technical Notes

### Auth Flow Reference
The signing algorithm and token refresh flow are fully documented in:
- `/workspaces/baseball-crawl/data/raw/gc-signature-algorithm.md` -- authoritative algorithm reference (JS pseudocode)
- `/workspaces/baseball-crawl/docs/api/auth.md` -- full auth architecture (three-token system, refresh flow, header assembly)

### Signing Algorithm Summary
- `gc-signature` format: `{nonce}.{hmac}` where nonce = Base64(random 32 bytes)
- HMAC message: `{timestamp}|{nonce_raw_bytes}|{sorted_body_values}[|{prev_sig_raw_bytes}]`
- Body values extracted recursively with sorted keys (see `values_for_signer` in algorithm doc)
- For standalone refresh calls, previousSignature is omitted
- Required POST /auth headers: gc-signature, gc-client-id, gc-timestamp, gc-device-id, gc-app-name, gc-app-version, gc-token (refresh token)
- Content-Type for POST /auth: `application/json; charset=utf-8` (web), `application/vnd.gc.com.post_eden_auth+json; version=1.0.0` (mobile)

### Token Refresh Response Shape
```json
{
  "type": "token",
  "access": {"data": "<access-token-jwt>", "expires": <unix-timestamp>},
  "refresh": {"data": "<refresh-token-jwt>", "expires": <unix-timestamp>}
}
```

### Token Lifetimes
- Web access token: ~60 minutes
- Mobile access token: ~12 hours
- Refresh token (both): 14 days, self-renewing

### Mobile Constraints
- Mobile client key is unknown (embedded in iOS binary, not yet extracted)
- Without the client key, programmatic gc-signature generation is impossible for mobile
- Workaround: support an optional `GAMECHANGER_ACCESS_TOKEN_MOBILE` env var as a manual fallback (user pastes from mitmweb, good for ~12 hours)
- Mobile client ID is known: `0f18f027-c51e-4122-a330-9d537beb83e0`

### .env Credential Keys (Web Profile)
- `GAMECHANGER_REFRESH_TOKEN_WEB` -- refresh token JWT (14 days)
- `GAMECHANGER_CLIENT_ID_WEB` -- client UUID
- `GAMECHANGER_CLIENT_KEY_WEB` -- Base64-encoded HMAC key
- `GAMECHANGER_DEVICE_ID_WEB` -- hex device identifier
- `GAMECHANGER_BASE_URL` -- API base URL

### .env Credential Keys (Mobile Profile)
- `GAMECHANGER_REFRESH_TOKEN_MOBILE` -- refresh token JWT (if available)
- `GAMECHANGER_CLIENT_ID_MOBILE` -- mobile client UUID (known)
- `GAMECHANGER_CLIENT_KEY_MOBILE` -- mobile HMAC key (unknown/unavailable)
- `GAMECHANGER_DEVICE_ID_MOBILE` -- device identifier
- `GAMECHANGER_ACCESS_TOKEN_MOBILE` -- manual fallback access token (new, optional)

### File Layout
- `src/gamechanger/signing.py` -- pure signing functions (new)
- `src/gamechanger/token_manager.py` -- token lifecycle management (new)
- `src/gamechanger/client.py` -- modified to use token manager
- `tests/test_signing.py` -- signing module tests (new)
- `tests/test_token_manager.py` -- token manager tests (new)
- `tests/test_client.py` -- updated client tests
- `tests/test_check_credentials.py` -- updated for new required keys
- `tests/test_cli_creds.py` -- updated for new required keys
- `scripts/smoke_test.py` -- updated error message
- `.env.example` -- add GAMECHANGER_ACCESS_TOKEN_MOBILE

### .env Update Mechanism
The project already has a pattern for writing to .env: `src/gamechanger/credential_parser.py` contains `merge_env_file()` which reads the existing .env, merges new values, and writes it back. The token manager should use this or a similar approach for persisting rotated refresh tokens.

**Atomicity constraint**: The current `merge_env_file()` implementation is not crash-safe -- a failure mid-write could lose the .env file and the rotated refresh token. The token manager's write-back path must use atomic file replacement (write to a temp file, then rename) to prevent data loss. This is critical because the server invalidates the old refresh token on each refresh call.

### POST /auth HTTP Client Constraint
The POST /auth endpoint has different header requirements than standard GET endpoints: it uses `Accept: */*` (not vendor-typed), `Content-Type: application/json; charset=utf-8` (web) or `application/vnd.gc.com.post_eden_auth+json; version=1.0.0` (mobile), and includes signing headers (`gc-signature`, `gc-timestamp`, `gc-client-id`). The TokenManager should NOT use `create_session()` for POST /auth calls -- use a standalone httpx client to avoid session defaults (User-Agent, browser headers) interfering with the auth-specific header set. The token manager's HTTP client is internal to the token manager, not shared with the GameChangerClient's session.

### Error Response Shapes
POST /auth returns plain text (not JSON) on HTTP 400 (e.g., `"Bad Request"` for stale signature). HTTP 401 has no body. The token manager must handle non-JSON error responses gracefully.

## Open Questions
None -- the problem and solution are well-specified.

## History
- 2026-03-08: Created. Promotes IDEA-015 (scoped to token refresh + client integration). Blocking: all GameChangerClient usage is broken.
- 2026-03-08: Post-READY expert consultation completed. api-scout confirmed all signing/auth claims accurate; identified Accept header requirement and POST /auth HTTP client constraint. software-engineer identified test breakage in downstream files, merge_env_file atomicity gap, eager-vs-lazy token fetch decision, and pagination 401-retry scoping. claude-architect confirmed context-layer updates belong in closure sequence, flagged error message wording. Codex spec review also completed. All findings triaged and incorporated into stories.
- 2026-03-08: Codex spec review triage (5 findings). F1-REFINE(P1): Fixed mobile fallback contract -- TokenManager accepts optional access_token param, loaded from .env via dotenv_values() (not os.environ), client_id/refresh_token optional for mobile. F2-REFINE(P2): Dropped JS "undefined" branch from AC-2 -- no Python equivalent. F3-REFINE(P2): Added AC-8 specifying HTTP 400 behavior (distinct AuthSigningError, no retry, log server gc-timestamp) vs 401 (CredentialExpiredError). Renumbered old AC-8 to AC-9. F4-REFINE(P2): Added tests/test_http_discipline.py to E-077-03 Files list. F5-REFINE(P3): Removed tests/test_cli_creds.py from E-077-03 Files list (confirmed safe). Consulted SE (source file analysis), api-scout (auth semantics, 400 vs 401 distinction), CA (no context-layer impact from new exception type).
- 2026-03-08: Implementation completed. All 3 stories dispatched sequentially (01→02→03), all APPROVED by code-reviewer. Key artifacts: `src/gamechanger/signing.py` (gc-signature HMAC-SHA256), `src/gamechanger/token_manager.py` (TokenManager with atomic .env write-back), `src/gamechanger/exceptions.py` (shared exceptions to break circular import), `src/gamechanger/credential_parser.py` (added `atomic_merge_env_file()` with `_build_merged_lines()` helper). 166 new/updated tests passing, no regressions. SHOULD FIX findings (5 total, recorded for future reference): E-077-01 SF-1 dead code branch in values_for_signer; E-077-02 SF-1 force_refresh() AssertionError on mobile-no-key; E-077-02 SF-2 broad except in atomic_merge_env_file cleanup; E-077-03 SF-1 unexpected exceptions.py (justified -- circular import fix); E-077-03 SF-2 broad except in _build_token_manager.
- 2026-03-08: Documentation assessment -- Trigger 5 fires (epic changes how auth system works). CLAUDE.md GameChanger API section needs update to reflect programmatic token refresh is now implemented. docs/api/auth.md may need minor updates noting the Python implementation exists. Dispatching claude-architect for context-layer updates (which covers CLAUDE.md).
- 2026-03-08: Context-layer assessment -- (1) New convention: YES -- shared exceptions module at src/gamechanger/exceptions.py; atomic_merge_env_file() for safe .env writes. (2) Architectural decision: YES -- TokenManager with standalone httpx client for POST /auth; lazy token fetch pattern in GameChangerClient. (3) Footgun/boundary: YES -- dotenv_values() vs os.environ for credential loading; POST /auth requires different headers than GET endpoints (no create_session()). (4) Agent behavior change: NO. (5) Domain knowledge: YES -- gc-signature algorithm productionized; HTTP 400 = signing error (AuthSigningError) vs 401 = token error (CredentialExpiredError). (6) New CLI/workflow: NO. Triggers 1-3, 5 fire -- dispatching claude-architect for codification.
- 2026-03-08: Codex code review (post-implementation). 6 findings triaged: 2 FIXED (Finding 3: mobile force_refresh() AssertionError replaced with clean CredentialExpiredError; Finding 4: 401 retry response now routes through existing 403/429/5xx error handling in both _get_with_retries and get_paginated). 3 DISMISSED (Findings 1,2,6: token-type confusion in curl-paste and proxy capture paths is pre-existing, not introduced by E-077; tests correctly verify E-077's scope). 1 DEFERRED (Finding 5: devcontainer postCreateCommand exit status masking from RTK append -- valid but unrelated to E-077, separate story needed).
