# E-095-02: Add Client Key Validation to bb creds check

## Epic
[E-095: Client Key Credential Resilience](epic.md)

## Status
`TODO`

## Description
After this story is complete, `bb creds check --profile web` will include a new "Client Key" diagnostic section that actively validates the client key by attempting a step-2 client-auth POST /auth call. A stale key produces a clear `[XX]` indicator with actionable guidance, a valid key shows `[OK]`, and a missing key shows `[--]`. This transforms `bb creds check` from a passive presence check into a comprehensive credential health diagnostic that catches the most insidious failure mode (stale client key returning misleading 401s everywhere).

## Context
The diagnostic gap that prompted this epic: `bb creds check` reported `[OK]` for the client key (present in .env), `[OK]` for refresh token expiry (14 days remaining), then `[XX] Credentials expired` from the API health check. The operator spent significant time chasing expired/consumed refresh tokens before discovering the client key was stale.

The step-2 client-auth call is the ideal validation target: it requires only `client_id` + `client_key` + `device_id`, exercises the full HMAC signing path, and its success/failure directly indicates client key validity -- independent of refresh token state. The step-2 body is `{"type": "client-auth", "client_id": "<client-id>"}`.

Critical: with a stale key, POST /auth returns HTTP 401 (not 400). The validation must handle both 400 and 401 as potential "stale key" signals, with clock skew check as the disambiguator.

## Acceptance Criteria
- [ ] **AC-1**: `check_profile_detailed()` in `src/gamechanger/credentials.py` returns a new field on `ProfileCheckResult` for client key validation status, with five possible outcomes: valid (HTTP 200 from client-auth), invalid (non-200 with clock within tolerance), clock_skew (local timestamp diverges from server `Date` header by >30 seconds), error (network failure or unexpected exception during the validation call), or skipped (key not present in env, or mobile profile).
- [ ] **AC-2**: The client key validation makes a real HTTP POST to `{GAMECHANGER_BASE_URL}/auth` with body `{"type": "client-auth", "client_id": "..."}` and the signed headers from `build_signature_headers()`. It does NOT reuse `TokenManager` -- it makes a standalone call so that a stale key does not cascade into login fallback or token persistence side effects.
- [ ] **AC-3**: Clock skew detection: the validation records the local timestamp used for signing. On non-200 responses, it compares against the server's `Date` response header (standard HTTP header, universally present -- `gc-timestamp` is unconfirmed in POST /auth responses). If the difference exceeds 30 seconds, the result is "clock skew" rather than "stale client key." If the `Date` header is absent or unparseable, treat as "stale key" (fail closed -- clock skew is the less likely cause in practice).
- [ ] **AC-4**: `bb creds check --profile web` output includes a "Client Key Validation" section (named to distinguish from the presence check in the Credentials section) between "Refresh Token" and "API Health" sections, rendered with the standard `[OK]`/`[XX]`/`[!!]`/`[--]` indicators.
- [ ] **AC-5**: When the client key is valid: `[OK]  Client key verified (POST /auth client-auth succeeded)` or similar.
- [ ] **AC-6**: When the client key is stale: `[XX]  Client key rejected -- update via: bb creds extract-key` or similar. Must mention the extraction command.
- [ ] **AC-7**: When clock skew is detected: `[!!]  Possible clock skew ({N} seconds difference) -- check system clock before blaming the client key` or similar.
- [ ] **AC-8**: When the client key env var is missing: `[--]  Client key not configured (GAMECHANGER_CLIENT_KEY_WEB)` -- the section is rendered but skipped, not hidden.
- [ ] **AC-9**: For mobile profile, the client key section shows `[--]  Client key not available for mobile profile` (mobile key has not been extracted).
- [ ] **AC-9a**: When the validation call fails due to a network error or unexpected exception: `[!!]  Client key validation failed (network error)` or similar. The error outcome is distinct from "stale key" (`[XX]`) because we cannot confirm the key is bad -- only that we couldn't reach the server.
- [ ] **AC-10**: The validation call uses `trust_env=False` on the httpx client, consistent with all other auth calls in the codebase.
- [ ] **AC-11**: The validation call respects the Bright Data proxy configuration (uses `get_proxy_config()` and `verify=False` when proxy is enabled), consistent with `GameChangerClient` behavior.
- [ ] **AC-12**: Tests cover: valid key (mock 200), stale key (mock 401 with close timestamps), stale key (mock 400 with close timestamps), clock skew (mock 400 with divergent timestamps), absent/unparseable Date header (treated as stale key), network error, missing key, mobile profile skip. All tests mock HTTP -- no real network calls.
- [ ] **AC-15**: The new `ProfileCheckResult` field has a default value (e.g., `None`) so that all existing tests and call sites constructing `ProfileCheckResult` continue to work without modification. All existing `test_credentials.py` tests that exercise `check_profile_detailed()` must mock the new client-auth HTTP call to prevent unexpected real network calls.
- [ ] **AC-13**: The validation never logs or displays the client key value itself -- only the env var name and the validation outcome.
- [ ] **AC-14**: When required credentials are missing (`client_id`, `device_id`, or `base_url` absent), the validation is skipped with a `[--]` indicator and a message listing which prerequisite is missing.

## Technical Approach
The validation logic belongs in `src/gamechanger/credentials.py` as a new helper (alongside the existing `_check_presence`, `_check_token_health`, `_check_api` helpers). It calls `build_signature_headers()` from `src/gamechanger/signing.py` to construct the signed request, then makes a standalone `httpx.Client.post()` call. The rendering belongs in `src/cli/creds.py` alongside the existing section renderers. A new dataclass for the validation result fits the existing pattern (`CredentialPresence`, `TokenHealth`, `ApiCheckResult`). The `ProfileCheckResult` dataclass gains the new field.

The validation must handle both HTTP 400 and 401 as potential "stale key" indicators, because the server has been observed returning 401 for bad HMAC signatures (not just for expired tokens).

Reference files:
- `src/gamechanger/credentials.py` -- existing check helpers and dataclasses at lines 78-252
- `src/gamechanger/signing.py` -- `build_signature_headers()` for constructing the signed request
- `src/cli/creds.py` -- existing `_render_*` section functions at lines 267-337
- `src/http/session.py` -- `get_proxy_config()` for proxy URL resolution

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/credentials.py` -- new client key validation helper, new dataclass, updated `check_profile_detailed()` and `ProfileCheckResult`
- `src/cli/creds.py` -- new `_render_client_key_section()`, updated `_render_profile_report()`
- `tests/test_credentials.py` (or equivalent) -- new tests for the validation helper
- `tests/test_cli_creds.py` (or equivalent) -- new tests for the rendered output

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
