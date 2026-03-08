# E-075-03: Mobile Credential Validation Script

## Epic
[E-075: Mobile Profile Credential Capture and Validation](epic.md)

## Status
`TODO`

## Description
After this story is complete, `bb creds check --profile mobile` will validate mobile credentials by calling GET /me/user with mobile-profile headers, and will report detailed presence/absence of each mobile credential individually. If the client key is available, the output will note that programmatic token refresh is possible.

## Context
The existing `check_credentials(profile="mobile")` path in `src/gamechanger/credentials.py` already works structurally -- it creates a `GameChangerClient(profile="mobile")` and calls GET /me/user. However, the error output is generic ("Missing required credential(s)") rather than listing which specific credentials are present vs. missing.

After E-075-R-01 determines whether the mobile client key is available, this story improves the mobile credential check to give the operator clear, actionable diagnostic output.

## Acceptance Criteria
- [ ] **AC-1**: `bb creds check --profile mobile` reports the presence/absence of each mobile credential: `GAMECHANGER_REFRESH_TOKEN_MOBILE`, `GAMECHANGER_CLIENT_ID_MOBILE`, `GAMECHANGER_CLIENT_KEY_MOBILE`, `GAMECHANGER_DEVICE_ID_MOBILE`. Missing credentials are listed individually (not just "missing credentials").
- [ ] **AC-2**: When all required mobile credentials are present, the check calls GET /me/user with mobile-profile headers and reports success/failure.
- [ ] **AC-3**: The output clearly distinguishes between "credentials missing" (config issue) and "credentials invalid/expired" (needs recapture).
- [ ] **AC-4**: If `GAMECHANGER_CLIENT_KEY_MOBILE` is absent but `GAMECHANGER_REFRESH_TOKEN_MOBILE` is present, the check still validates the access token (GET /me/user) but reports that programmatic refresh is unavailable without the client key.
- [ ] **AC-5**: Tests cover: all-present-and-valid, missing-refresh-token, missing-client-key-partial-check, expired-token, network-error.

## Technical Approach
The current `check_single_profile` function catches `ConfigurationError` for missing credentials but only reports the exception message. This story improves the diagnostic output to list which specific credentials are present vs. missing, using the known set of mobile credential env var names.

The `GameChangerClient` already supports `profile="mobile"` and routes to `_MOBILE` suffix keys. The validation logic lives in `src/gamechanger/credentials.py` and is called by the `bb creds check` CLI command.

Key constraint: the client key may not be available (depends on R-01 findings). The validation must degrade gracefully -- a partial credential set (token + device ID, no client key) is still useful for direct API calls, just not for programmatic refresh.

Reference files:
- `/workspaces/baseball-crawl/src/gamechanger/credentials.py` (current validation logic)
- `/workspaces/baseball-crawl/src/gamechanger/client.py` (GameChangerClient profile support)
- `/workspaces/baseball-crawl/epics/E-075-mobile-credential-capture/R-01-findings.md` (research findings -- read before implementing)

## Dependencies
- **Blocked by**: E-075-R-01 (determines what credentials are capturable), E-075-01 (env var names must be aligned)
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/credentials.py` -- improve check_single_profile diagnostic output for mobile
- `tests/test_credentials.py` -- new/updated tests for mobile-specific validation paths

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- This story does NOT add programmatic token refresh for mobile -- that is a separate concern. It only validates that the captured credentials work for direct API calls and reports on refresh capability.
- The `_required_keys` function in `client.py` currently requires only `REFRESH_TOKEN` (after E-075-01) and `DEVICE_ID`. The client key and client ID are not in the required set because the client uses pre-captured tokens directly. The validation story adds visibility into these optional-but-important credentials.
- **R-01 outcome (2026-03-08):** Mobile client key is confirmed different from web and unknown (embedded in iOS binary). AC-4 (client key absent, partial check) is now the **expected** mobile path, not an edge case. The mobile refresh token (14-day) and access token (~12 hours) work directly as gc-token for GET endpoints, so GET /me/user validation will succeed even without the client key. Programmatic refresh is blocked until IPA binary analysis extracts the mobile key.
