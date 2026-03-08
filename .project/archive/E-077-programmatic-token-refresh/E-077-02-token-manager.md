# E-077-02: Token Manager

## Epic
[E-077: Programmatic Token Refresh -- Fix Broken GameChangerClient](epic.md)

## Status
`DONE`

## Description
After this story is complete, the project will have a `TokenManager` class in `src/gamechanger/token_manager.py` that handles the full token lifecycle: calling POST /auth with a signed refresh request, caching the returned access token in memory, detecting expiry, and persisting the rotated refresh token back to `.env`. This is the layer between the signing module (Story 01) and the GameChangerClient (Story 03).

## Context
The GameChangerClient currently sends the refresh token directly as `gc-token` on every API call, which results in 401. The token manager sits between credential loading and API usage: it uses the signing module to construct a valid POST /auth request, exchanges the refresh token for a short-lived access token, and manages the access token lifecycle. The refresh token is self-renewing -- each POST /auth returns a new refresh token that replaces the old one.

For mobile profile, programmatic refresh is blocked because the client key is unknown. The token manager must support a manual access token fallback for mobile.

## Acceptance Criteria
- [ ] **AC-1**: `src/gamechanger/token_manager.py` exists with a `TokenManager` class that accepts profile, client_id, client_key (optional), refresh_token (optional), device_id, base_url, access_token (optional -- for mobile manual fallback), and env_path (path to the `.env` file for write-back; defaults to the repo-root `.env`). For web profile, client_id, client_key, and refresh_token are required -- missing any raises `ConfigurationError`. For mobile profile without client_key, only access_token is required (see AC-4). The class creates its own httpx client internally for POST /auth calls -- it does NOT accept or use a `create_session()` session (POST /auth has different header requirements than GET endpoints; see epic Technical Notes "POST /auth HTTP Client Constraint").
- [ ] **AC-2**: `TokenManager.get_access_token()` returns a valid access token string. On first call, it performs a POST /auth refresh to obtain one. On subsequent calls, it returns the cached token if not expired (with a safety margin before actual expiry). If expired, it transparently refreshes and returns the new token.
- [ ] **AC-3**: After a successful refresh, the new refresh token is written back to `.env` using a new `atomic_merge_env_file()` function added to `src/gamechanger/credential_parser.py`. This function shares read/merge logic with the existing `merge_env_file()` (extracted to a private helper like `_build_merged_lines()`) but uses a temp file + `os.replace()` for the write step, so that a crash mid-write does not destroy the `.env` file. The existing `merge_env_file()` remains unchanged for backward compatibility. The env key written matches the profile suffix convention (e.g., `GAMECHANGER_REFRESH_TOKEN_WEB`). If the write-back fails (permission error, disk full, etc.), the token manager logs a WARNING with the failure reason (no credential values in the log), and still returns the access token to the caller. The rationale: the access token is valid for ~60 minutes, giving the operator time to notice and fix the persistence issue. The next refresh call will fail if the old refresh token was already invalidated server-side, at which point the operator must re-capture credentials manually.
- [ ] **AC-4**: When client_key is None (mobile profile without key), `get_access_token()` returns the `access_token` constructor parameter if it was provided (no refresh capability, no expiry tracking). If `access_token` was not provided either, raises `ConfigurationError` with a message explaining that mobile programmatic refresh requires the client key, and suggesting the manual access token fallback (`GAMECHANGER_ACCESS_TOKEN_MOBILE` in `.env`). The access token follows the same credential loading path as all other credentials: loaded from `.env` via `dotenv_values()` by `GameChangerClient._load_credentials()` (Story 03) and passed into the TokenManager constructor. When using the mobile fallback, `GAMECHANGER_REFRESH_TOKEN_MOBILE` and `GAMECHANGER_CLIENT_ID_MOBILE` are NOT required -- only `GAMECHANGER_ACCESS_TOKEN_MOBILE`, `GAMECHANGER_DEVICE_ID_MOBILE`, and `GAMECHANGER_BASE_URL` are needed.
- [ ] **AC-5**: `TokenManager.force_refresh()` unconditionally performs a new POST /auth refresh, replacing the cached access token even if the current one has not expired. Returns the new access token. This is used by the client for 401 retry logic.
- [ ] **AC-6**: The POST /auth request includes all required headers: gc-signature (from the signing module), gc-client-id, gc-timestamp (generated fresh at signing time, never cached), gc-device-id, gc-app-name, gc-app-version, gc-token (the refresh token), `Accept: */*`, and the correct Content-Type for the profile. Header values are profile-scoped: web uses `gc-app-version: 0.0.0`, `gc-app-name: web`, `Content-Type: application/json; charset=utf-8`; mobile uses `gc-app-version: 2026.7.0.0`, `Content-Type: application/vnd.gc.com.post_eden_auth+json; version=1.0.0` (mobile `gc-app-name` value is unresolved -- use the value from `GAMECHANGER_APP_NAME_MOBILE` env var if set, otherwise omit the header). Note: `gc-device-id` is a request header only -- it is NOT an input to the gc-signature HMAC computation.
- [ ] **AC-7**: No tokens, keys, or signatures are logged at any level. The module logs operational events (e.g., "refreshing access token for web profile", "access token cached, expires in N seconds") without including credential values.
- [ ] **AC-8**: POST /auth error handling distinguishes two failure modes: (a) HTTP 400 (signing failure -- stale timestamp, bad HMAC, malformed signature) raises a distinct exception (e.g., `AuthSigningError`, NOT `CredentialExpiredError`) with a message indicating the signature was rejected. The error message should include the server-returned `gc-timestamp` header value (if present in the response) for clock skew diagnosis, but MUST NOT include any credential values. No retry on 400 -- signing errors are not transient. (b) HTTP 401 (token problem -- expired or wrong-type refresh token) raises `CredentialExpiredError`. No retry at the TokenManager level -- the caller (GameChangerClient) handles retry via `force_refresh()`. Both error paths handle the non-JSON response body gracefully (400 returns plain text, 401 has no body).
- [ ] **AC-9**: `tests/test_token_manager.py` exists with tests covering: successful refresh (mock POST /auth 200 response), cached token reuse, expired token re-refresh, .env write-back of new refresh token (including atomic write verification), .env write-back failure (simulated permission error -- verify WARNING logged and access token still returned), mobile fallback with manual access token, mobile error when no key and no manual token, force_refresh behavior, HTTP 400 signing error (verify distinct exception type raised, not CredentialExpiredError), and HTTP 401 token error. All tests use mocked HTTP. No real API calls.

## Technical Approach
The token manager orchestrates signing (from `src/gamechanger/signing.py`) and HTTP. The POST /auth refresh flow is documented in `/workspaces/baseball-crawl/docs/api/auth.md` under "Token Refresh Flow." The response shape is in the epic Technical Notes. See also the epic Technical Notes sections "POST /auth HTTP Client Constraint" and "Error Response Shapes" for HTTP client and error handling constraints.

For .env write-back, a new `atomic_merge_env_file()` function is added to `/workspaces/baseball-crawl/src/gamechanger/credential_parser.py`. It shares read/merge logic with the existing `merge_env_file()` via a private helper, but writes atomically (temp file + `os.replace()`). The existing `merge_env_file()` is unchanged. See AC-3 for failure handling behavior.

The access token expiry can be determined from the `access.expires` field in the refresh response (Unix timestamp). A safety margin (e.g., refresh when less than 5 minutes remain) prevents edge-case failures from clock skew or slow requests.

## Dependencies
- **Blocked by**: E-077-01 (signing module)
- **Blocks**: E-077-03

## Files to Create or Modify
- `src/gamechanger/token_manager.py` (create)
- `tests/test_token_manager.py` (create)
- `src/gamechanger/credential_parser.py` (modify -- extract shared merge logic to `_build_merged_lines()` private helper, add `atomic_merge_env_file()` that uses temp file + `os.replace()`)
- `tests/test_credential_parser.py` (modify -- add tests for `atomic_merge_env_file()` and verify `merge_env_file()` still works unchanged)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-077-03**: `src/gamechanger/token_manager.py` with the `TokenManager` class that GameChangerClient will instantiate and call `get_access_token()` / `force_refresh()` on.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- Auth flow reference: `/workspaces/baseball-crawl/docs/api/auth.md`
- Credential parser with merge_env_file: `/workspaces/baseball-crawl/src/gamechanger/credential_parser.py`
- The refresh token is self-renewing: each refresh call invalidates the old refresh token and returns a new one. Write-back failure behavior is specified in AC-3 (log WARNING, return access token, operator has ~60 min to fix).
- File locking on `.env` is a known limitation -- not required for this story. Single-operator usage makes concurrent writes unlikely.
