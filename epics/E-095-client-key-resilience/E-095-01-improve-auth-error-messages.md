# E-095-01: Improve AuthSigningError Messages to Mention Client Key

## Epic
[E-095: Client Key Credential Resilience](epic.md)

## Status
`TODO`

## Description
After this story is complete, every error path in `token_manager.py` that fires when POST /auth fails will explicitly name "stale client key" and the `GAMECHANGER_CLIENT_KEY_WEB` env var as a likely cause. The `bb creds refresh` command's catch blocks will also surface the client key as a recovery action. This ensures the operator gets actionable guidance instead of the current generic messages when the real problem is a rotated client key.

## Context
When POST /auth fails due to a stale client key, the server returns HTTP 401 -- the same status code as an expired refresh token. The current error messages in `_handle_auth_error()` say "Refresh token rejected by server (HTTP 401)" and in `_check_login_step_status()` say "clock skew or stale signature" (for 400) or "Check email/password" (for non-200). Neither mentions the client key. The `bb creds refresh` catch block says "Signature rejected by server (possible clock skew)" with no mention of the client key.

Since the most common real-world cause of cascading auth failures (refresh fails, then login fallback also fails) is a stale client key, the error messages should mention it prominently. The operator spent significant time chasing expired/consumed refresh tokens before discovering the real issue was the client key.

Key finding: HTTP 400 (mapped to `AuthSigningError`) may indicate clock skew OR a stale key. HTTP 401 (mapped to `CredentialExpiredError`) may indicate an expired token OR a stale key. Neither can be disambiguated from the status code alone. The messages should mention both possibilities.

## Acceptance Criteria
- [ ] **AC-1**: The `AuthSigningError` raised in `_handle_auth_error()` (HTTP 400 branch, ~line 345) includes text mentioning "stale client key" or "GAMECHANGER_CLIENT_KEY" as a possible cause alongside clock skew. The message should suggest running `bb creds check` to validate the key.
- [ ] **AC-2**: The `AuthSigningError` raised in `_check_login_step_status()` (HTTP 400 branch, ~line 401) includes the same client-key mention as AC-1.
- [ ] **AC-3**: The `CredentialExpiredError` raised in `_handle_auth_error()` (HTTP 401 branch, ~line 352) adds a note that the client key may be stale. This message fires when the refresh token is rejected, so the primary message should still mention the refresh token -- but should add "If this persists, the client key (GAMECHANGER_CLIENT_KEY_WEB) may be stale -- run bb creds check --profile web" or similar. Note: avoid phrasing that assumes login fallback has been attempted, since `force_refresh()` does not trigger login fallback.
- [ ] **AC-4**: The `AuthSigningError` catch block in `src/cli/creds.py` `refresh()` command (~line 233-238) includes recovery guidance that leads with diagnosis, then action. Replace "possible clock skew" language with guidance like: "Signature rejected. Run `bb creds check --profile web` to diagnose. If Client Key shows [XX], run `bb creds extract-key` to update it. If clock skew is suspected, check your system clock."
- [ ] **AC-5**: The `CredentialExpiredError` catch block in `src/cli/creds.py` `refresh()` command (~line 227-231) reorders recovery advice to put client key diagnosis FIRST, before proxy recapture. Guidance like: "Run `bb creds check --profile web` -- if Client Key Validation shows [XX], run `bb creds extract-key`. If the key is valid, re-capture credentials via the proxy and run `bb creds import`." The client key check is fast and free; proxy recapture is slow and manual. The ordering must prevent the operator from spending time on proxy recapture when the real fix is a key update.
- [ ] **AC-6**: Existing tests that assert on `AuthSigningError` or `CredentialExpiredError` message text are updated to match the new messages. No test regressions.
- [ ] **AC-7**: Error messages never reveal the actual client key value -- only the env var name.

## Technical Approach
Two files need message-text changes: `src/gamechanger/token_manager.py` (the methods that raise `AuthSigningError` on HTTP 400 and `CredentialExpiredError` on HTTP 401) and `src/cli/creds.py` (the `refresh()` command's catch blocks for both exception types). The changes are message text updates only -- no control flow changes. The key insight to convey in messages: when auth fails, the client key is the most commonly overlooked cause because `bb creds check` (before this epic) couldn't validate it.

Reference files:
- `src/gamechanger/token_manager.py` -- `_handle_auth_error()` at ~line 330, `_check_login_step_status()` at ~line 385
- `src/cli/creds.py` -- `refresh()` command at ~line 213, catch blocks at ~lines 227-238

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/token_manager.py` -- update error messages in `_handle_auth_error()` and `_check_login_step_status()`
- `src/cli/creds.py` -- update `AuthSigningError` and `CredentialExpiredError` catch blocks in `refresh()` command
- `tests/` -- update any tests asserting on error message text from these methods

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
