# E-128: Credential Workflow Redesign

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Redesign the GameChanger credential workflow so the operator provides only email + password and the system self-authenticates for the web profile. The current CLI is a disconnected toolkit (`import`, `capture`, `extract-key`, `refresh`, `check`) with no coherent happy path. The operator is manually executing login flow curls that the system already automates internally -- but can't reach from the CLI. This epic wires the existing login flow as the primary bootstrap path, adds a guided setup wizard, and surfaces credential status at a glance.

## Background & Context
During a real credential reset session (2026-03-18), the operator had to:
1. Manually copy login flow curls from browser DevTools (steps 3-4 of the POST /auth sequence)
2. Paste them into the system, which couldn't parse them because `bb creds import` expects a different curl format
3. Manually decode JWTs to determine token type (access vs refresh)
4. Hand-edit `.env` with the correct variable names

**The irony**: `TokenManager._do_login_fallback()` already implements the complete 3-step login flow (client-auth → user-auth → password) programmatically. The signing algorithm is cracked (`signing.py`), client key extraction works (`key_extractor.py`), token refresh works. The operator was manually doing what the system can already do -- but the CLI doesn't expose the login flow as a primary bootstrap path.

**The gate**: `TokenManager._validate_credentials()` requires `GAMECHANGER_REFRESH_TOKEN_WEB` when a client key is present. If no refresh token exists (fresh machine, post-reset), the constructor raises `ConfigurationError` before any network call. The login fallback is only reachable via an in-flight HTTP 401 during a refresh attempt. There is no "bootstrap from email+password" entry point.

**Expert consultation findings** (2026-03-18):
- **api-scout**: Confirmed web minimum input = email + password. Everything else derivable (client key from JS bundle, device ID potentially synthetic, tokens from login flow). Mobile blocked by unknown iOS client key. Studied 24 proxy sessions -- no single header contains "password and refresh token"; the user was describing the manual login flow curls.
- **SE**: Login flow fully implemented in `_do_login_fallback()` (steps 2-4). Gap is one code path: `_validate_credentials()` rejects construction without refresh token even when email+password present. `bb creds import` easy to extend for raw JWT/JSON (E-127-01 covers this).
- **UXD**: Proposed three changes: (1) `bb creds` → status dashboard, (2) `bb creds setup [web|mobile]` wizard with email+password as primary web path, (3) smarter error messages that diagnose first and prescribe one next step.
- **CA**: Auth reference docs (`docs/api/auth.md`) are excellent. Gap: no auth-module rule file scoped to auth source files. Recommends `.claude/rules/auth-module.md`.
- **DE**: No schema changes needed. `.env` is correct for credential storage. Flagged silent refresh token write-back failure as observability gap.
- **docs-writer**: `docs/admin/credential-refresh.md` and `bootstrap-guide.md` are solid. Gap: `docs/production-deployment.md` has no GameChanger credential step and references deprecated variable names.

**Web client ID rotation**: Three distinct web client IDs observed across sessions (2026-03-07 through 2026-03-18), confirming that client IDs rotate with GC deploys. `bb creds extract-key` must handle this reliably (E-127-02).

## Goals
- Operator provides ONLY email + password in `.env`, runs one command, and the web profile is fully authenticated
- `bb creds` (no subcommand) shows credential status at a glance with actionable next steps
- `bb creds setup [web|mobile]` guides the operator through the minimum steps for each profile
- Error messages diagnose the root cause (stale key vs expired token) and prescribe exactly one next command
- Auth-module implementation constraints are surfaced automatically when agents edit auth code
- Production deployment runbook includes GameChanger credential setup

## Non-Goals
- Mobile programmatic token refresh (blocked by unknown iOS client key -- separate initiative)
- Extracting the iOS client key from the binary (out of scope)
- Moving credentials from `.env` to SQLite (unnecessary complexity)
- Persisting access tokens to `.env` (by design: access tokens are short-lived, memory-only)
- Full `bb creds` command group API breakage (existing commands like `check`, `refresh`, `extract-key` stay; `import` and `capture` remain as power-user fallbacks)

## Success Criteria
- `bb creds setup web` with only `GAMECHANGER_USER_EMAIL` and `GAMECHANGER_USER_PASSWORD` in `.env` produces a fully authenticated web profile (all tokens, client key, device ID auto-provisioned)
- `bb creds` (no subcommand) shows a compact status dashboard for all profiles with [OK]/[!!]/[XX] indicators and next-step guidance
- `bb creds setup mobile` walks the operator through mitmproxy capture with step-by-step prompts
- When `bb creds refresh` fails, the error message identifies whether the cause is a stale client key or an expired refresh token and prescribes exactly one remediation command
- `.claude/rules/auth-module.md` fires when agents read or edit `src/gamechanger/{signing,token_manager,client,exceptions}.py`
- `docs/production-deployment.md` includes a GameChanger credential setup step with current variable names
- POST /auth request bodies containing email/password are redacted at proxy capture time

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-128-R-01 | Device ID synthesis probe | DONE | None | - |
| E-128-01 | Login bootstrap path | TODO | None | - |
| E-128-02 | `bb creds setup web` wizard | TODO | E-128-01, E-128-R-01, E-127-01, E-127-02 | - |
| E-128-03 | `bb creds setup mobile` wizard | TODO | None | - |
| E-128-04 | `bb creds` status dashboard | TODO | None | - |
| E-128-05 | Smarter error diagnostics | TODO | E-128-01 | - |
| E-128-06 | Auth-module rule file | TODO | None | - |
| E-128-07 | Production runbook credential step | TODO | E-128-02 | - |
| E-128-08 | Proxy session PII redaction | TODO | None | - |
| E-128-09 | Admin docs credential update | TODO | E-128-02 | - |

## Dispatch Team
- software-engineer
- claude-architect
- docs-writer
- api-scout (advisory only -- no assigned story; available for auth flow questions during dispatch)

### Dispatch Sequencing
- E-128-01 (login bootstrap) must be **merged before** E-128-02 (setup wizard) begins, because the wizard calls the login flow as its primary path.
- E-128-R-01 (device ID probe) must complete before E-128-02, because the probe result determines whether the wizard generates a synthetic device ID or prompts for browser capture.
- E-128-02 depends on E-127-01 (multi-format import, used as curl fallback in wizard) and E-127-02 (extract-key fix, used in wizard key extraction step). These E-127 stories must be merged first.
- E-128-05 (error diagnostics) depends on E-128-01 (new login path introduces new error states).
- E-128-07 (production runbook) should be dispatched after E-128-02 merges, since it documents the new setup flow.
- E-128-03 (mobile wizard), E-128-04 (status dashboard), E-128-06 (auth rule), E-128-08 (PII redaction) are independent and can run in parallel with each other and with E-128-01.
- E-128-03 and E-128-04 both add new code to `src/cli/creds.py` but in non-overlapping regions (new commands vs callback change). Safe to dispatch in parallel.
- E-128-09 (admin docs update) depends on E-128-02 and can be dispatched alongside E-128-07.
- **Test file merge note**: Stories 01, 02, 03, 04, and 05 all add tests to `tests/test_cli_creds.py`. If dispatched in parallel worktrees, expect merge conflicts in the test file. The router should merge these stories sequentially -- E-128-01 first (it's a dependency for 02 and 05), then the remaining stories one at a time, resolving test file conflicts at each merge.

## Technical Notes

### TN-1: Login Bootstrap -- The Core Change

`TokenManager._validate_credentials()` (line 134-148 in `token_manager.py`) currently requires `GAMECHANGER_REFRESH_TOKEN_WEB` when `client_key` is present. The fix:

1. **Relax validation**: When `client_key` is present but `refresh_token` is absent, check for `email` + `password`. If both present, allow construction without raising (the TokenManager is in "login-only" mode).
2. **New method** `do_login()`: Public method that calls `_do_login_fallback()` directly, bypassing the refresh attempt. Returns the access token and persists the refresh token to `.env`.
3. **Wire from CLI**: `bb creds refresh` detects "no refresh token + email+password present" and calls `do_login()` instead of `force_refresh()`.
4. **Device ID handling**: If `GAMECHANGER_DEVICE_ID_WEB` is absent, generate a synthetic 32-char hex via `secrets.token_hex(16)` and persist it to `.env` before proceeding. (Contingent on E-128-R-01 confirming GC accepts synthetic device IDs. If not, the CLI must prompt for manual device ID entry.)

### TN-2: Setup Wizard Design

The `bb creds setup` wizard is a guided flow that reads current credential state, skips steps that are already complete, and walks through only what's missing.

**Web flow** (`bb creds setup web`):
1. Check for `CLIENT_KEY_WEB` in `.env`. If missing or stale, run `extract_client_key()` and write to `.env`.
2. Check for `DEVICE_ID_WEB`. If missing, generate synthetic hex (per TN-1 / R-01 findings) or prompt.
3. Check for `USER_EMAIL` + `USER_PASSWORD`. If missing, prompt the operator to add them to `.env` and re-run.
4. Call `TokenManager.do_login()` → full login flow → tokens written to `.env`.
5. Verify: call `GET /me/user` with the new access token. Print success/failure.

**Fallback path**: If the operator doesn't want to store their password, the wizard offers `bb creds import` as a fallback (curl capture or raw token paste). E-127-01's multi-format import enables this path.

**Mobile flow** (`bb creds setup mobile`):
1. Check for mobile credentials in `.env`. If present and valid, report status and exit.
2. Guide through mitmproxy setup (explicitly noting Mac-host boundary).
3. Prompt: "Force-quit GC on iPhone, reopen, press Enter when done."
4. Scan `.env` for proxy-captured credentials (same logic as current `bb creds capture`).
5. Validate via API. Report token lifetime.

### TN-3: Status Dashboard

`bb creds` (no subcommand) currently shows help text. Replace with a compact status view:

```
GameChanger Credentials

Web Profile
  [OK] Client key      current
  [OK] Refresh token   valid (12 days)
  [OK] API             authenticated
  Status: READY

Mobile Profile
  [--] No credentials captured
  Status: NOT CONFIGURED
  -> Run: bb creds setup mobile
```

Example partial-config state:

```
Web Profile
  [OK] Client key      current
  [XX] Refresh token   expired
  [XX] API             not authenticated
  Status: INCOMPLETE
  -> Run: bb creds setup web
```

The dashboard reuses existing diagnostic logic from `credentials.py` (`check_profile_detailed()`) but presents a compact summary instead of the full panel. The full panel remains accessible via `bb creds check`.

### TN-4: Error Diagnostic Strategy

Current error messages branch: "if X, do A; if Y, do B." The redesign follows the UXD principle: **diagnose first, prescribe one thing.**

When `bb creds refresh` fails:
1. If HTTP 400 (signature rejected): run `extract_client_key()` inline to check if the key changed. If changed: "Client key is stale. Fix: `bb creds extract-key --apply`". If current: "Signature rejected but key is current. Check system clock."
2. If HTTP 401 (token rejected): check refresh token JWT expiry locally. If expired: "Refresh token expired. Fix: `bb creds setup web`". If not expired: "Token rejected but not expired locally. The client key may be stale. Fix: `bb creds extract-key --apply`".

### TN-5: Auth-Module Rule File

Create `.claude/rules/auth-module.md` with paths scoped to `src/gamechanger/{signing,token_manager,client,exceptions}.py`. Content:
- Exception hierarchy: `AuthSigningError` (HTTP 400), `CredentialExpiredError` (HTTP 401), `LoginFailedError` (login flow failure)
- TokenManager uses standalone `httpx.Client` -- NOT `create_session()` from `src/http/session.py`
- Env var access: `dotenv_values()` throughout; does NOT populate `os.environ`
- `.env` write-back: `atomic_merge_env_file()` for safe concurrent updates
- Client pattern: lazy token fetch on first API call, automatic 401 retry
- Security: never log tokens, client key is a shared secret, PII in JWT payloads

### TN-6: Production Runbook Gap

`docs/production-deployment.md` step 2.3 creates `.env` from `.env.example` and lists required variables, but only covers infrastructure vars. It references deprecated variable names (`GC_TOKEN`, `GC_COOKIE`) and never mentions `GAMECHANGER_*` credential variables. The fix:
1. Add a "GameChanger Credentials" step between `.env` creation and `docker compose up`
2. List the minimum required variables (`GAMECHANGER_USER_EMAIL`, `GAMECHANGER_USER_PASSWORD`)
3. Reference `bb creds setup web` as the credential bootstrap command
4. Remove deprecated variable references

### TN-7: Proxy PII Redaction

The mitmproxy addon (`proxy/addons/`) captures POST /auth request bodies to session logs. These contain plaintext email and password values. The addon should redact the `email` and `password` fields in POST /auth request bodies before writing to the endpoint log. The `type` field should be preserved (it identifies the auth step). Session data is gitignored but exists on disk -- defense in depth.

### TN-8: Device ID Synthesis (Confirmed -- R-01 Complete)

The device ID (`gc-device-id`) is a 32-character hex string. **GC does NOT enforce device ID binding.** A randomly generated `secrets.token_hex(16)` is accepted without complaint. Confirmed via live probe (2026-03-18):
- POST /auth refresh with synthetic device ID: HTTP 200
- GET /me/user with synthetic device ID + resulting access token: HTTP 200
- Full user profile returned; no behavioral difference from a real browser device ID

**Scope note**: The probe tested synthetic device IDs for POST /auth refresh and GET /me/user. The full login flow (steps 2-4) was not directly probed with a synthetic device ID, but this is a reasonable inference -- the device ID is a stateless request header with no observed session binding.

**Implication**: `bb creds setup web` can be fully automated. The system generates a stable device ID on first run and persists it to `.env`. No browser capture needed at any point for web profile.

**Bonus finding from the probe**: The client key had rotated AGAIN during the session (bundle hash changed, key changed, client ID unchanged). This is the stale-key-mimics-expired-token trap documented in `docs/api/auth.md`. Reinforces the need for E-128-05's auto-diagnostic on refresh failure.

## Open Questions
- None remaining.

## History
- 2026-03-18: Created from auth redesign discovery session. Full-team consultation (api-scout, SE, UXD, CA, DE, docs-writer). User confirmed manual login flow curls are the exact pain point the system should automate.
- 2026-03-18: E-128-R-01 device ID probe complete. **Synthetic device IDs accepted by GC.** Full web bootstrap from email+password confirmed viable. TN-8 updated. Also discovered client key had rotated again during session -- reinforces E-128-05 auto-diagnostic need. Epic set to READY.
- 2026-03-18: Full-team refinement pass (SE, DE, UXD, CA, api-scout, docs-writer). Key changes: (1) E-128-01 Technical Approach expanded with CLI pre-validation gap and device ID instance-state requirement; (2) E-128-02 AC-1 specifies CLIENT_ID+CLIENT_KEY extraction and .env reload; (3) E-128-03 AC-1 clarifies upfront step display with single Enter prompt; (4) E-128-04 adds indicator semantics and INCOMPLETE state; (5) E-128-05 AC-3 improves fallback message; (6) E-128-06 notes http-discipline overlap, AC-4 tightened; (7) E-128-07 AC-4 made self-contained (no stale bootstrap-guide link); (8) E-128-08 Technical Approach corrected (addon does NOT parse auth types), file paths specified; (9) New story E-128-09 added for admin docs updates; (10) TN-8 clarified R-01 probe scope; (11) Dispatch notes expanded with test file merge guidance and api-scout advisory role.
- 2026-03-19: Codex spec review remediation -- 5 findings applied. (F2) E-128-06 AC-4 and Context: corrected CLAUDE.md section reference from "Key Architectural Decisions" to "GameChanger API" section's Auth bullet. (F3) E-128-04 AC-1: added mobile profile client key indicator clarification. (F4) epic.md test file merge note: expanded to list all 5 stories (01-05) touching test_cli_creds.py, changed guidance to sequential merging. (F5) E-128-05: fixed Technical Approach fallback reference to point to AC-3's ordered message; clarified Context with HTTP 400 vs 401 distinction. (F6) E-128-08 AC-1: corrected "address" to "email" in both body description and field name.
