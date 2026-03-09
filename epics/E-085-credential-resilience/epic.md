# E-085: Credential Resilience and Diagnostic Improvements

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Make the credential system self-healing and self-diagnosing. When the refresh token expires (14-day inactivity), `TokenManager` should automatically recover by performing the full 4-step login flow instead of failing with `CredentialExpiredError`. Simultaneously, upgrade `bb creds check` and `bb status` to give operators a complete, actionable picture of system health -- credentials, proxy, API reachability -- in a single command.

## Background & Context
The full programmatic login flow (client-auth -> user-auth -> password -> get tokens) was confirmed working on 2026-03-09. Currently, `TokenManager` only implements the refresh path (`POST /auth {type: "refresh"}`). When the refresh token expires after 14 days of inactivity, the system fails hard with `CredentialExpiredError`, requiring manual intervention (proxy capture or curl paste). With email/password and the client key already in `.env`, the system has everything it needs to recover automatically.

Meanwhile, `bb creds check` currently calls `GET /me/user` but provides minimal diagnostic output -- just "valid" or "expired/missing" with no detail about which token failed, whether the proxy is configured, or what endpoint was tested. `bb status` aggregates credential checks but similarly lacks proxy status and actionable recovery guidance.

**Consultation completed (2026-03-09)**: claude-architect, ux-designer, api-scout, and software-engineer all consulted. Key findings incorporated: CA confirmed CLAUDE.md update is sufficient (no new rule file); UXD designed sectioned-panel visual language with `[OK]`/`[!!]`/`[XX]`/`[--]` status indicators; api-scout confirmed `GET /me/user` only accepts access tokens (not refresh) and response shape assertions needed; SE confirmed `_do_login()` on TokenManager, `LoginFailedError(CredentialExpiredError)` subclass pattern, and `force_refresh()` should NOT trigger login fallback. All open questions resolved.

## Goals
- `TokenManager` auto-recovers from expired refresh tokens via the full login flow (no manual intervention required)
- `bb creds check` provides a complete diagnostic: credential presence, token validity, proxy status, test endpoint, and actionable next steps
- `bb status` integrates proxy connectivity status alongside existing sections
- New `.env` variables (`GAMECHANGER_USER_EMAIL`, `GAMECHANGER_USER_PASSWORD`) are documented and the system knows how to use them

## Non-Goals
- Mobile profile login flow (the mobile client key is still unknown; this epic is web-only for the login fallback)
- Automatic credential rotation scheduling (cron-like refresh)
- Step 1 of the login flow (logout/session invalidation) -- the login fallback skips step 1 since the refresh token is already expired
- Changing the existing refresh-first flow (refresh remains the primary path; login is the fallback)

## Success Criteria
- Given expired refresh token + valid email/password in `.env`, when `TokenManager.get_access_token()` is called, it performs the full login flow and returns a valid access token without raising `CredentialExpiredError`
- Given missing email/password in `.env`, when the refresh token is expired, `CredentialExpiredError` is raised with a message explaining that login credentials are needed
- `bb creds check --profile web` output shows: credential presence, token health, proxy status, test endpoint, and clear next-step guidance
- `bb status` shows proxy connectivity status (Bright Data) as a section alongside credentials, crawl, DB, and proxy sessions
- All new code has test coverage; existing tests continue to pass

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-085-01 | TokenManager Login Fallback | TODO | None | - |
| E-085-02 | Enhanced `bb creds check` Output | TODO | None | - |
| E-085-03 | `bb status` Proxy Connectivity Section | TODO | E-085-02 | - |
| E-085-04 | Context-Layer Documentation Update | TODO | E-085-01, E-085-02, E-085-03 | - |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### Login Flow Implementation (Stories 01, 04)

The full login flow is documented in `docs/api/auth.md` under "Complete Login Flow (4 Steps)". For the auto-recovery use case, only steps 2-4 are needed (step 1 is logout, which is unnecessary when the refresh token is already expired):

- **Step 2** (`client-auth`): `POST /auth {type: "client-auth", client_id: CLIENT_ID}` with NO `gc-token` header. `usePreviousSignature: false`. Returns `{type: "client-token", token: "...", expires: N}` -- note different response shape from refresh.
- **Step 3** (`user-auth`): `POST /auth {type: "user-auth", email: EMAIL}` with `gc-token: CLIENT_TOKEN`. Chained signature (previous_signature from step 2 response).
- **Step 4** (`password`): `POST /auth {type: "password", password: PASSWORD}` with `gc-token: CLIENT_TOKEN`. Chained signature (previous_signature from step 3 response). Returns the standard `{type: "token", access: {...}, refresh: {...}}` response.

**Signature chaining**: The server returns a `gc-signature` response header on each step. The client extracts the HMAC part (after the dot) and passes it as `previous_signature_b64` to the next step's `build_signature_headers()` call. `signing.py` already supports the `previous_signature_b64` parameter.

**Required `.env` variables for login fallback**: `GAMECHANGER_USER_EMAIL` and `GAMECHANGER_USER_PASSWORD`. These are already documented in `docs/api/auth.md` but not yet used by `TokenManager`.

**Error type (SE consultation)**: Add `LoginFailedError(CredentialExpiredError)` in `exceptions.py`, following the same subclass pattern as `ForbiddenError(CredentialExpiredError)`. This preserves existing `except CredentialExpiredError` handlers while enabling specific `except LoginFailedError` catches. Recovery message: "check email/password in .env" (vs. CredentialExpiredError's "run bb creds import").

**force_refresh() boundary (SE consultation)**: `force_refresh()` should NOT trigger login fallback -- only `get_access_token()` initial fetch path. This prevents operator-initiated refresh from silently falling through to login. If `force_refresh()` gets a 401, it raises `CredentialExpiredError` as today.

**Response shape validation (api-scout consultation)**: Step 2 response shape (`{type: "client-token", ...}`) is NOT independently confirmed via direct curl -- inferred from proxy observation. Add assertion/log for response shape. SE should read `data/raw/auth-login-flow-findings.json` before implementing.

**gc-signature response header (SE consultation)**: Log WARNING if `gc-signature` response header is absent on any step -- this indicates the chaining contract may have changed.

**Clock skew (SE consultation)**: 400 during login chain should raise `AuthSigningError` (not `LoginFailedError`). Network error mid-chain is safe (server is stateless, retry restarts from scratch).

### Credential Check Enhancements (Stories 02, 03)

Current `bb creds check` flow: `GameChangerClient(profile=X)` -> `client.get("/me/user")` -> success/failure. The output is a single line with minimal context.

The enhanced check should report:
1. **Credential presence**: Which `.env` keys are set vs. missing (without revealing values)
2. **Token health**: Whether the refresh token JWT is expired (decode `exp` claim locally without hitting the API)
3. **API reachability**: Whether `GET /me/user` succeeds (the actual validation). Note: this endpoint only accepts access tokens, not refresh tokens (api-scout confirmation).
4. **Proxy status**: Whether Bright Data proxy is configured and routing correctly (reuse `check_proxy_routing()` from `src/http/proxy_check.py`)
5. **Test endpoint**: Display which endpoint was used for validation (`GET /me/user`)

Current `bb status` flow: Checks credentials (per-profile), last crawl, DB info, proxy sessions. Missing: Bright Data proxy connectivity (the `bb proxy check` logic).

**Visual language (UXD consultation)**: Shared across `bb creds check` and `bb status`:
- Status indicators: `[OK]` green, `[!!]` yellow, `[XX]` red, `[--]` dim (no emoji -- works in all terminals)
- `bb creds check`: expanded per-sub-check view with sectioned panels (credential presence, token health, API reachability, proxy status, test endpoint)
- `bb status`: compact one-line-per-subsystem view with new "Proxy (Bright Data)" section
- Two-level hierarchy: `bb status` for quick daily health check, `bb creds check` for full diagnostic
- Mobile token health should always show `[!!]` yellow -- honest representation that auto-refresh is not available for mobile profile

**API health check nuance (api-scout consultation)**: `GET /me/user` response contains PII fields (email, first_name, last_name) -- display only the user's display name, never log the full response. Accept header: `application/vnd.gc.com.user+json; version=0.3.0`.

### File Ownership Map

| File | Story | Notes |
|------|-------|-------|
| `src/gamechanger/token_manager.py` | 01 | Add login fallback methods |
| `src/gamechanger/exceptions.py` | 01 | Add `LoginFailedError(CredentialExpiredError)` subclass |
| `tests/test_token_manager.py` | 01 | New tests for login flow |
| `src/gamechanger/credentials.py` | 02 | Enhanced check_single_profile |
| `src/cli/creds.py` | 02 | Enhanced check command output |
| `tests/test_credentials.py` | 02 | Tests for enhanced check |
| `tests/test_cli_creds.py` | 02 | CLI output tests |
| `src/cli/status.py` | 03 | Add proxy connectivity section |
| `tests/test_status.py` | 03 | Tests for proxy section |
| `CLAUDE.md` | 04 | Update credential docs, bb commands |
| `docs/api/auth.md` | 04 | Note that login flow is now implemented |

## Open Questions

All open questions resolved via consultation (2026-03-09). See Technical Notes for incorporated findings.

### Resolved Questions (Summary)

| Agent | Question | Resolution |
|-------|----------|------------|
| CA | CLAUDE.md sections to update | Three-token architecture paragraph + .env variables list. No `bb creds refresh` entry change. |
| CA | New rule file needed? | No -- CLAUDE.md update is sufficient. Not a cross-cutting concern. |
| UXD | CLI output layout | Sectioned panels with `[OK]`/`[!!]`/`[XX]`/`[--]` indicators. Two-level hierarchy: `bb status` (compact) vs. `bb creds check` (expanded). |
| UXD | Shared visual language | Yes -- same indicator system, same color coding, same panel style. |
| api-scout | GET /me/user nuances | Only accepts access tokens. Response has PII -- display name only. Accept: `application/vnd.gc.com.user+json; version=0.3.0`. |
| api-scout | client-auth response shape | NOT independently confirmed via direct curl. Add assertion/log. Read `data/raw/auth-login-flow-findings.json`. |
| SE | Login flow structure | Methods on `TokenManager` -- `_do_login()` sibling to `_do_refresh()`. |
| SE | Error type | `LoginFailedError(CredentialExpiredError)` subclass -- same pattern as `ForbiddenError`. |
| SE | Test strategy | respx `side_effect` for multi-step chains. 7 test cases identified. |
| SE | Edge cases | `force_refresh()` should NOT trigger login fallback. Clock skew -> `AuthSigningError`. Log WARNING on missing gc-signature response header. |

## History
- 2026-03-09: Created. Full login flow confirmed working programmatically earlier today.
- 2026-03-09: All four consultations completed (CA, UXD, api-scout, SE). Key findings: `LoginFailedError` subclass pattern, `[OK]`/`[!!]`/`[XX]`/`[--]` visual language, `force_refresh()` should not trigger login fallback, `GET /me/user` only accepts access tokens, client-auth response shape needs assertion. Open Questions resolved. Technical Notes updated. Stories updated with consultation-informed refinements.
- 2026-03-09: Codex spec review triage (5 findings). All refined: (1) P1: E-085-04 deps expanded to include 02+03 (docs must describe implemented reality). (2) P1: E-085-03 now depends on 02 (file conflict via check_single_profile return type change). (3) P2: PASS_UNVERIFIED proxy outcome explicitly mapped to `[!!]` yellow in both 02 and 03 notes. (4) P2: E-085-04 AC-1 narrowed to behavioral change (env vars already in CLAUDE.md). (5) P3: E-085-04 DoD replaced with docs-specific verification. Epic wave updated: 01+02 parallel -> 03 (depends on 02) -> 04 (depends on 01+02+03).
