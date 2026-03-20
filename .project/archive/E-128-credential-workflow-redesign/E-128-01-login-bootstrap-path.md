# E-128-01: Login Bootstrap Path

## Epic
[E-128: Credential Workflow Redesign](epic.md)

## Status
`DONE`

## Description
After this story is complete, `bb creds refresh --profile web` will detect when no refresh token exists but email + password are configured in `.env`, and execute the 3-step login flow directly to obtain tokens. This eliminates the catch-22 where the operator needs a refresh token to get a refresh token. The login flow (`_do_login_fallback()`) is already fully implemented -- this story wires it as a primary bootstrap path.

## Context
`TokenManager._validate_credentials()` currently requires `GAMECHANGER_REFRESH_TOKEN_WEB` when `client_key` is present. If no refresh token exists (fresh machine, post-reset), the constructor raises `ConfigurationError` before any network call is attempted. The login fallback code (`_do_login_fallback()` -- steps 2-4 of POST /auth) is only reachable via HTTP 401 during an in-flight refresh attempt. There is no way to invoke it from the CLI when starting from zero tokens.

The operator confirmed (2026-03-18) they are manually executing these exact login steps via browser DevTools curls. This story automates that.

## Acceptance Criteria
- [ ] **AC-1**: Given `GAMECHANGER_CLIENT_KEY_WEB` and `GAMECHANGER_CLIENT_ID_WEB` are set in `.env`, and `GAMECHANGER_REFRESH_TOKEN_WEB` is absent, and `GAMECHANGER_USER_EMAIL` + `GAMECHANGER_USER_PASSWORD` are set, when `bb creds refresh --profile web` is run, then the 3-step login flow executes successfully (HTTP 200 on all steps), `GAMECHANGER_REFRESH_TOKEN_WEB` is written to `.env`, and the access token is returned.
- [ ] **AC-2**: Given `GAMECHANGER_DEVICE_ID_WEB` is absent and email+password are present, when `bb creds refresh --profile web` is run, then a synthetic device ID is generated (32-char hex via `secrets.token_hex(16)`), written to `.env`, and used for the login flow. (Confirmed viable: E-128-R-01 probe verified GC accepts synthetic device IDs.)
- [ ] **AC-3**: Given both `GAMECHANGER_REFRESH_TOKEN_WEB` and email+password are present, when `bb creds refresh` is run, then existing behavior is unchanged (refresh flow attempted first, login fallback only on 401).
- [ ] **AC-4**: Given email or password is missing and refresh token is also missing, when `bb creds refresh` is run, then a clear error message explains that either a refresh token or email+password credentials are needed.
- [ ] **AC-5**: After a successful login bootstrap, the rotated refresh token is persisted to `.env` atomically (same write-back mechanism as the existing refresh flow).
- [ ] **AC-6**: Tests cover: login bootstrap (no refresh token + email/password), normal refresh (refresh token present), missing credentials error, and device ID synthesis per TN-1.

## Technical Approach
The changes are in two files per Technical Notes TN-1 and TN-8. The core change is relaxing the validation gate in `TokenManager` to allow construction without a refresh token when email+password are present, and adding a `do_login()` entry point that calls the existing `_do_login_fallback()` directly. The CLI command detects the no-refresh-token condition and routes accordingly.

**CLI pre-validation gap**: The `refresh` command's pre-check loop (lines 215-232 of `src/cli/creds.py`) unconditionally requires `GAMECHANGER_REFRESH_TOKEN_{suffix}` and `GAMECHANGER_DEVICE_ID_{suffix}` -- it exits before TokenManager is constructed if either is missing. This loop must be restructured: when email+password are both present, skip refresh_token and device_id from the missing-check (device_id will be synthesized per AC-2; refresh_token will be obtained via login).

**Device ID instance state**: The `do_login()` method must ensure `self._device_id` is set on the TokenManager instance (not just written to `.env`) before calling `_do_login_fallback()`, because `_do_login_fallback()` uses `self._device_id` in request headers. If `_device_id` is `None`, the header value becomes `None` which would cause an HTTP error.

Key files to study: `src/gamechanger/token_manager.py` (lines 134-163: `_validate_credentials()`, lines 582-622: `_do_login_fallback()`), `src/cli/creds.py` (lines 186-279: `refresh` command).

## Dependencies
- **Blocked by**: None
- **Blocks**: E-128-02 (setup wizard uses login bootstrap as its primary path), E-128-05 (new error states)

## Files to Create or Modify
- `src/gamechanger/token_manager.py` -- relax `_validate_credentials()`, add `do_login()` method
- `src/cli/creds.py` -- update `refresh` command to detect login-bootstrap condition and restructure pre-validation loop
- `tests/test_token_manager.py` -- tests for login bootstrap path
- `tests/test_cli_creds.py` -- CLI integration tests for bootstrap scenario
- `.env.example` -- update comments: `DEVICE_ID_WEB` is now auto-generated (not "capture from Chrome"), `REFRESH_TOKEN_WEB` is optional when email+password are present

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-128-02**: The `do_login()` method on TokenManager, which the setup wizard calls as its primary web authentication path.
- **Produces for E-128-05**: New error paths (missing email/password, device ID synthesis failure) that the error diagnostics story refines.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
