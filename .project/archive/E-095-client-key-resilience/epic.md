# E-095: Client Key Credential Resilience

## Status
`COMPLETED`

## Overview
When GameChanger rotates the client key embedded in their JavaScript bundle, all authentication silently fails -- refresh, login fallback, and every POST /auth call return bare HTTP 401 with no indication that the HMAC signing key is wrong. This epic adds active client key validation to diagnostics, improves error guidance to mention the client key as a likely cause, documents the extraction process with the exact JS bundle variable name (`EDEN_AUTH_CLIENT_KEY`), and adds an automated extraction command (`bb creds extract-key`) that fetches the current key from the publicly accessible GC JS bundle.

## Background & Context
The operator lost crawl capability because `GAMECHANGER_CLIENT_KEY_WEB` in `.env` became stale after a GC bundle deployment. The failure mode was extremely misleading:

1. Every POST /auth call (refresh, login fallback steps 2-4) returned HTTP 401 -- the SAME status code as an expired refresh token.
2. The `AuthSigningError` message said "clock skew or stale signature" -- no mention of the client key. But in practice, the 400 path was never hit; the server returned 401 for bad HMAC signatures.
3. `bb creds check` only validates credential *presence* and tests `GET /me/user` (which uses the access token, not the signing path). It reported `[OK]` for the client key (present!) and `[OK]` for refresh token expiry (valid!), then `[XX] Credentials expired` -- completely misleading.
4. The login fallback (steps 2-4) also uses `build_signature_headers()` with the same stale key, so it failed identically.
5. The credential extractor proxy addon captures `gc-token`, `gc-device-id`, `gc-client-id` -- but NOT the client key (which is embedded in the JS bundle, never sent as a header).
6. Manually replaying captured curls failed because client tokens and sessions are single-use.
7. Extracting refresh tokens from proxy sessions failed because the browser consumes them before we can use them.

The actual fix was simple: download the GC JS bundle (publicly accessible, no auth needed), grep for `EDEN_AUTH_CLIENT_KEY`, extract the new key, and update `.env`. After that, `bb creds refresh` succeeded immediately.

**SE consultation note**: The user provided comprehensive technical findings from the manual diagnosis, including exact code paths, HTTP status codes, the `EDEN_AUTH_CLIENT_KEY` variable name and format, the JS bundle URL pattern, and confirmed the step-2 client-auth call as the ideal validation target. PM could not spawn SE (platform constraint -- no Task tool available in this session). The user's findings serve as the technical feasibility assessment: the JS bundle is publicly accessible (no auth), the key format is stable (`clientId:clientKey` composite), and the extraction is a simple HTTP GET + regex grep. All signing module details are confirmed from the existing codebase (`src/gamechanger/signing.py`, `src/gamechanger/token_manager.py`).

## Goals
- `bb creds check --profile web` actively validates the client key by attempting a step-2 client-auth call, producing a clear `[XX]` indicator when the key is stale -- not a misleading "credentials expired" message
- Error messages from `AuthSigningError` and the `bb creds refresh` CLI explicitly name the client key as a likely cause when POST /auth fails
- `bb creds extract-key` automatically fetches the current client key from the GC JS bundle and updates `.env` -- making key rotation a non-event
- A documented, repeatable process for extracting a fresh client key exists in `docs/api/auth.md`, with the exact JS variable name (`EDEN_AUTH_CLIENT_KEY`) and bundle URL pattern

## Non-Goals
- Proactive key rotation monitoring or alerting (check on demand is sufficient)
- Mobile client key extraction (blocked on iOS binary analysis -- separate concern)
- Proxy-based client key detection (the key is never in HTTP traffic)
- Changing the HTTP status code handling in `_handle_auth_error()` or `_check_login_step_status()` -- we cannot control what the server returns

## Success Criteria
- Running `bb creds check --profile web` when the client key is stale produces a clear `[XX]` indicator with a message mentioning the client key, not a generic "credentials expired" message.
- The `AuthSigningError` catch block in `bb creds refresh` and the error messages in `token_manager.py` mention "stale client key" and `GAMECHANGER_CLIENT_KEY_WEB` as explicit possible causes.
- `bb creds extract-key` fetches the GC JS bundle, extracts `EDEN_AUTH_CLIENT_KEY`, and updates `.env` with the current client key and client ID -- with a dry-run mode and clear diff output.
- `docs/api/auth.md` contains a "Client Key Extraction" section documenting both the manual (DevTools) and automated (`bb creds extract-key`) processes.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-095-01 | Improve AuthSigningError messages to mention client key | DONE | None | SE-01 |
| E-095-02 | Add client key validation to bb creds check | DONE | None | SE-02 |
| E-095-03 | Document client key extraction process | DONE | E-095-02, E-095-04 | api-scout |
| E-095-04 | Automated client key extraction command | DONE | None | SE-04 |

## Dispatch Team
- software-engineer
- api-scout

## Technical Notes

### Root Cause Analysis (Confirmed 2026-03-11)
The `GAMECHANGER_CLIENT_KEY_WEB` in `.env` was stale. GC rotated the key in their JavaScript bundle. Every auth call failed at the HMAC signature level with HTTP 401 -- indistinguishable from an expired refresh token at the HTTP level.

### The EDEN_AUTH_CLIENT_KEY Variable
The client key is embedded in the GC JavaScript bundle as `EDEN_AUTH_CLIENT_KEY`. It is a composite value in the format `clientId:clientKey`. The client key portion is a 44-character base64 string (decodes to 32 bytes) -- an HMAC-SHA256 secret. Example structure from the bundle:

```
ba={PUBLIC_PREFIX:"",VERSION_NUMBER:"...",EDEN_AUTH_CLIENT_KEY:"<client-id-uuid>:<base64-client-key>",RUM_CLIENT_TOKEN:...}
```

The JS bundle URL pattern is: `https://web.gc.com/static/js/index.{hash}.js` -- the hash changes with each deployment. The bundle is linked from the HTML page via a `<script>` tag.

### HTTP Status Code Behavior with Stale Client Key
Critical finding: a stale client key causes POST /auth to return HTTP **401** (not 400). This is the same status code returned for an expired refresh token. The current code maps 400 to `AuthSigningError` and 401 to `CredentialExpiredError` -- but in the stale-key scenario, the 401 path is hit, producing the misleading "Refresh token rejected" / "Credentials expired" message. The step-2 client-auth call is the ONLY reliable way to disambiguate, because it requires no refresh token -- if it returns a non-200 status, the client key is the problem (assuming clock is correct).

### Client Key Validation via Step-2 Client-Auth Call
The step-2 client-auth call (`POST /auth {"type": "client-auth", "client_id": "..."}`) is the ideal validation target because:
- It requires only `client_id` + `client_key` + `device_id` (no refresh token)
- It exercises the full HMAC signing path (`build_signature_headers()`)
- It does NOT trigger login fallback or token persistence side effects
- It is the ONLY POST /auth step that sends NO `gc-token` header
- It requires no `previousSignature` (it is always the first call in any login sequence)
- A 200 response confirms the client key is valid
- A non-200 response (with clock skew ruled out) means the client key is stale
- The returned client token (~10 min lifetime) can be discarded

### Clock Skew Detection
For clock skew disambiguation on non-200 responses, use the standard HTTP `Date` response header (universally present) rather than `gc-timestamp` (confirmed in requests but unconfirmed in POST /auth responses). Compare the signing timestamp against the server's `Date` header; if the difference exceeds 30 seconds, classify as clock skew. If the `Date` header is absent or unparseable, treat as "stale key" (fail closed -- clock skew is the less likely cause).

### JS Bundle Extraction Strategy
The GC JS bundle is publicly accessible (no auth needed). Extraction steps:
1. Fetch `https://web.gc.com` (HTML page)
2. Parse `<script>` tags to find the bundle URL matching `static/js/index.*.js`
3. Fetch the bundle
4. Regex for `EDEN_AUTH_CLIENT_KEY:"([^"]+)"` to extract the composite value
5. Split on `:` (first occurrence) -- left side is `client_id` (UUID), right side is `client_key` (base64)
6. Compare against current `.env` values; update if changed

### Command Naming Decision
UXD recommended `update-key` over `extract-key` as more goal-oriented (operator wants to "fix their broken key," not "extract" something). PM decision: keep `extract-key` -- it accurately describes the mechanism (fetching from JS bundle), is already established throughout the stories, and the recovery flow (guided by `bb creds check` output and error messages) carries the operator through regardless of the subcommand name.

### Device ID Note
The device_id also changed between sessions during the diagnosis. This didn't cause the auth failure (client key did), but device IDs are not permanent. This is informational only -- no story action needed.

### Files Shared Across Stories
- `src/gamechanger/token_manager.py` -- modified by E-095-01 (error messages in `_handle_auth_error()` and `_check_login_step_status()`)
- `src/cli/creds.py` -- modified by E-095-01 (AuthSigningError catch in `refresh()`) and E-095-02 (new rendering section in `_render_profile_report()`) and E-095-04 (new `extract_key` command)
- `src/gamechanger/credentials.py` -- modified by E-095-02 (new validation helper and dataclass)
- `docs/api/auth.md` -- modified by E-095-03 (new extraction section)

**Overlap analysis (SE-confirmed)**: E-095-01 modifies `src/cli/creds.py` in the `refresh()` command's error handler (~line 233-238). E-095-02 modifies `src/cli/creds.py` by adding new rendering functions and updating `_render_profile_report()` (~lines 267+). E-095-04 adds a new command function to `src/cli/creds.py`. These touch non-overlapping regions and can run in parallel worktrees. E-095-03 depends on E-095-04 so it can document the automated extraction command.

**Implementation note for E-095-02**: The new `ProfileCheckResult` field must have a default value (e.g., `None`) so that all existing tests constructing `ProfileCheckResult` continue to work without modification. Additionally, the new client-auth HTTP call must be mocked in ALL existing `test_credentials.py` tests that exercise `check_profile_detailed()` to prevent unexpected real network calls.

## Open Questions
None.

## History
- 2026-03-11: Created. Prompted by operator losing crawl capability due to stale client key with no diagnostic path to identify the root cause.
- 2026-03-11: Refined with complete root cause findings. Expanded scope to include automated client key extraction (E-095-04). Updated HTTP status code understanding: stale key returns 401 (not 400). Added EDEN_AUTH_CLIENT_KEY details and JS bundle extraction strategy. Reordered stories: E-095-03 now depends on E-095-04.
- 2026-03-11: Specialist refinement (api-scout, SE, UXD). Key changes: (1) Clock skew detection uses HTTP `Date` header, not `gc-timestamp` (unconfirmed in responses). (2) E-095-01 error message ordering revised -- client key check before proxy recapture advice. (3) E-095-04 gains dry-run banner, post-apply confirmation, and next-step prompt ACs. (4) E-095-02 section renamed "Client Key Validation"; ProfileCheckResult field needs default value; absent Date header treated as stale key. (5) E-095-03 adds notes about no previousSignature and fresh HTML fetch requirement.
- 2026-03-11: COMPLETED. All 4 stories implemented and reviewed. Key artifacts: improved error messages in token_manager.py and cli/creds.py (E-095-01), client key validation via step-2 client-auth call in credentials.py (E-095-02), automated key extraction command `bb creds extract-key` with key_extractor.py module (E-095-04), and Client Key Extraction documentation in docs/api/auth.md (E-095-03). Code review findings: E-095-02 and E-095-04 both required function length refactoring (resolved in round 2). SHOULD FIX from E-095-04 review: untested OSError path in `--apply` write-failure handler.
- 2026-03-11: Documentation assessment: Trigger fired (new feature). Primary docs handled by E-095-03 (docs/api/auth.md). CLAUDE.md updated with `bb creds extract-key` command. Minor follow-up: admin docs (docs/admin/operations.md) could mention extract-key in troubleshooting.
- 2026-03-11: Context-layer assessment: (1) New convention? No. (2) Architectural decision? No. (3) Footgun discovered? Yes -- stale client key returns HTTP 401 indistinguishable from expired refresh token; documented in docs/api/auth.md. (4) Agent behavior change? No. (5) Domain knowledge? Yes -- EDEN_AUTH_CLIENT_KEY variable, composite format, JS bundle extraction; documented in docs/api/auth.md. (6) New CLI command? Yes -- `bb creds extract-key`; added to CLAUDE.md. All codification already complete via E-095-03 and CLAUDE.md update; no additional claude-architect dispatch needed.
