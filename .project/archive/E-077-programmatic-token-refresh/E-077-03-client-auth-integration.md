# E-077-03: GameChangerClient Auth Integration

## Epic
[E-077: Programmatic Token Refresh -- Fix Broken GameChangerClient](epic.md)

## Status
`DONE`

## Description
After this story is complete, `GameChangerClient` will use the `TokenManager` to obtain and manage access tokens instead of sending the refresh token directly as `gc-token`. The client will transparently refresh the access token on 401 responses (single retry) and support the mobile manual access token fallback. All existing callers continue to work without changes -- the auth layer is internal to the client.

## Context
The current `GameChangerClient.__init__()` sets `self._session.headers["gc-token"]` to the refresh token from `.env`. This is the root cause of the 401 on every API call. This story replaces that pattern: the client instantiates a `TokenManager`, calls `get_access_token()` to obtain a valid access token, and sets that as `gc-token`. On 401 responses, the client calls `force_refresh()` and retries once before raising `CredentialExpiredError`.

The `_required_keys()` function and `_load_credentials()` method need to be updated to load the additional credentials needed by TokenManager (client_id, client_key for web profile).

## Acceptance Criteria
- [x] **AC-1**: `GameChangerClient.__init__()` instantiates a `TokenManager` with the appropriate credentials for the given profile. For web profile, this includes client_id, client_key, refresh_token, device_id, and base_url. For mobile profile, client_key may be None.
- [x] **AC-2**: The client obtains the access token **lazily on the first API call** (not eagerly in `__init__`). This preserves the existing pattern where three tests inspect `client._session.headers["gc-token"]` immediately after construction. The first call to `get()` or `get_paginated()` calls `TokenManager.get_access_token()` and sets the result as the `gc-token` header before making the HTTP request. Subsequent calls reuse the cached token (the TokenManager handles expiry internally). The refresh token is NOT sent as `gc-token` on regular API calls.
- [x] **AC-3**: When a GET request returns 401, the client calls `TokenManager.force_refresh()` to obtain a fresh access token, updates the `gc-token` header, and retries the request exactly once. If the retry also returns 401, it raises `CredentialExpiredError` as before.
- [x] **AC-4**: The 401-retry logic in AC-3 applies to both `get()` and `get_paginated()` methods. For `get_paginated()`, the 401 retry applies to the individual failing page request only -- it does not restart pagination from page 1.
- [x] **AC-5**: `_required_keys()` and `_load_credentials()` are updated to include `GAMECHANGER_CLIENT_ID_{PROFILE}` and `GAMECHANGER_CLIENT_KEY_{PROFILE}`. For web profile, both are required -- missing either raises `ConfigurationError`. For mobile profile, `GAMECHANGER_CLIENT_KEY_MOBILE` is optional (may be absent or empty). When mobile has no client_key AND `GAMECHANGER_ACCESS_TOKEN_MOBILE` is set, `GAMECHANGER_REFRESH_TOKEN_MOBILE` is also optional (the client operates in manual-fallback mode with no refresh capability). The `_required_keys()` and `_load_credentials()` implementation must support this conditional-required pattern.
- [x] **AC-6**: For mobile profile without a client key, the client works if `GAMECHANGER_ACCESS_TOKEN_MOBILE` is present in `.env` (manual fallback). `_load_credentials()` reads it via `dotenv_values()` and passes it to the `TokenManager` constructor as the `access_token` parameter. `GameChangerClient(profile='mobile').get('/me/user')` does not crash when the client key is absent but the manual access token is present.
- [x] **AC-7**: Existing tests in `tests/test_client.py` are updated to work with the new auth flow. The test helper `_make_client()` provides the additional credentials needed by TokenManager (client_id, client_key). Mock the TokenManager (not the raw POST /auth call) so existing GET-focused tests do not need to simulate the full refresh flow.
- [x] **AC-8**: New tests verify: (a) 401 triggers a single refresh retry, (b) double-401 raises CredentialExpiredError, (c) access token is refreshed between requests when expired, (d) mobile fallback with manual token works.
- [x] **AC-9**: No tokens, keys, or signatures are logged. Error messages reference actionable steps (e.g., "check .env credentials" or "refresh token may have expired") without including credential values. The existing error messages in `_get_with_retries()` and `get_paginated()` that say "Refresh by running: python scripts/refresh_credentials.py" must be updated to context-appropriate messages (e.g., "credentials expired -- check .env or run: bb creds check") since the client now handles refresh internally.

## Technical Approach
The main change is in `GameChangerClient.__init__()`: instead of setting `gc-token` to the refresh token, the client creates a `TokenManager` instance and delegates token acquisition to it. The `_get_with_retries()` and paginated GET methods need a 401 interception layer that calls `force_refresh()` and retries.

Key files to reference:
- Current client: `/workspaces/baseball-crawl/src/gamechanger/client.py`
- Token manager (from E-077-02): `/workspaces/baseball-crawl/src/gamechanger/token_manager.py`
- Existing tests: `/workspaces/baseball-crawl/tests/test_client.py`

The `_PROFILE_SCOPED_KEYS` tuple and `_required_keys()` function need to be expanded to include the new credential keys. The `_load_credentials()` method may need to distinguish between required and optional keys (client_key is optional for mobile).

## Dependencies
- **Blocked by**: E-077-02 (token manager)
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/client.py` (modify)
- `tests/test_client.py` (modify)
- `tests/test_check_credentials.py` (modify -- update `_FAKE_WEB_CREDENTIALS` to include `GAMECHANGER_CLIENT_ID_WEB` and `GAMECHANGER_CLIENT_KEY_WEB`, and update `_FAKE_MOBILE_CREDENTIALS` as needed for the new required-keys contract)
- `tests/test_http_discipline.py` (modify -- update `_FAKE_CREDENTIALS` to include new required keys, update gc-token assertion to expect an access token instead of the refresh token, and mock TokenManager so the test does not trigger real auth flows)
- `scripts/smoke_test.py` (modify -- update error message at line 92 that lists old required keys to include CLIENT_ID and CLIENT_KEY)
- `.env.example` (modify -- add `GAMECHANGER_ACCESS_TOKEN_MOBILE` with a comment explaining it is a manual fallback)

## Agent Hint
software-engineer

## Definition of Done
- [x] All acceptance criteria pass
- [x] Tests written and passing
- [x] Code follows project style (see CLAUDE.md)
- [x] No regressions in existing tests

## Notes
- The `.env.example` file at `/workspaces/baseball-crawl/.env.example` already has `GAMECHANGER_CLIENT_ID_WEB`, `GAMECHANGER_CLIENT_KEY_WEB`, and `GAMECHANGER_ACCESS_TOKEN_MOBILE` is a new addition (line needed in .env.example).
- After this story, `bb creds check` (which uses `check_single_profile()` in `src/gamechanger/credentials.py`) should start working again for web profile because the client will actually obtain access tokens. No changes to `credentials.py` are needed -- it already calls `client.get('/me/user')` which will now work.
- Add `GAMECHANGER_ACCESS_TOKEN_MOBILE` to `.env.example` with a comment explaining it is a manual fallback for when the mobile client key is unavailable.
- **Downstream test impact**: The `_required_keys()` change (AC-5) changes what credentials `GameChangerClient.__init__()` demands, which breaks any test that monkeypatches credentials without the new keys. The files list includes all known affected test files. `tests/test_cli_creds.py` was reviewed and confirmed safe -- it only tests CLI argument plumbing and never constructs `GameChangerClient`. `tests/test_http_discipline.py` IS affected (patches credentials and asserts gc-token value). Run the full test suite to catch any missed files.
- **Error message assertion in tests**: `tests/test_client.py` line 106 has an explicit assertion checking for the exact string `"python scripts/refresh_credentials.py"`. When AC-9 updates the error messages in `client.py`, this test assertion must also be updated to match the new wording.
- **scripts/check_credentials.py and scripts/refresh_credentials.py**: No code changes needed to these scripts -- they work at a different layer (calling `client.get()` or `parse_curl()`). But `scripts/smoke_test.py` has a hardcoded error message listing required env vars that must be updated.
