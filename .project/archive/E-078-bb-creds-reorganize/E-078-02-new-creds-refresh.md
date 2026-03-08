# E-078-02: New bb creds refresh for programmatic token refresh

## Epic
[E-078: Reorganize bb creds CLI Commands](epic.md)

## Status
`DONE`

## Description
After this story is complete, `bb creds refresh` will perform a programmatic token refresh via POST /auth for the web profile. It exchanges the refresh token in `.env` for a new access token, persists the rotated refresh token back to `.env`, and prints a human-readable status message. This wraps the existing `TokenManager.force_refresh()` with a CLI interface.

## Context
E-077 delivered `TokenManager` with `force_refresh()`, which performs the full POST /auth refresh cycle and writes the rotated refresh token back to `.env` atomically. There is currently no CLI command exposing this. After E-078-01 clears the `refresh` name, this story creates the new command.

## Acceptance Criteria
- [ ] **AC-1**: `bb creds refresh` (no flags) performs a programmatic token refresh for the web profile using credentials from `.env` and prints a success message including the token expiry time (e.g., "Access token refreshed for web profile, expires in 3547s").
- [ ] **AC-2**: `bb creds refresh --profile web` behaves identically to `bb creds refresh` with no flags (web is the default).
- [ ] **AC-3**: `bb creds refresh --profile mobile` prints a clear error explaining that mobile programmatic refresh is not yet available (mobile client key not extracted) and exits non-zero. Use an early-exit check (`if profile == "mobile"`) before constructing `TokenManager` for a clean UX message.
- [ ] **AC-4**: When required credentials are missing from `.env`, the command prints a helpful error message (naming the missing keys) and exits non-zero.
- [ ] **AC-5**: When the refresh token is expired or invalid (HTTP 401 from POST /auth), the command prints a message directing the user to re-capture credentials via `bb creds import` and exits non-zero.
- [ ] **AC-6**: When the signature is rejected (HTTP 400), the command prints a message about clock skew and exits non-zero.
- [ ] **AC-7**: On success, the CLI delegates `.env` write-back entirely to `TokenManager.force_refresh()` -- the CLI command itself does not call any `.env` writing functions.
- [ ] **AC-8**: `bb creds --help` lists `check`, `import`, and `refresh`. The `import` help string contains "curl" (it parses curl commands). The `refresh` help string contains "token" (it performs programmatic token refresh).
- [ ] **AC-9**: New tests in `tests/test_cli_creds.py` cover the success path and all three error paths (missing creds, expired token, bad signature) using mocked `TokenManager`.

## Technical Approach
Add a new `refresh` command to `src/cli/creds.py`. The command loads credentials from `.env` using `dotenv_values()`, instantiates `TokenManager` with the appropriate profile's keys, calls `force_refresh()`, and reports the result. Error handling catches `ConfigurationError`, `CredentialExpiredError`, and `AuthSigningError` -- each produces a distinct user-facing message and non-zero exit.

The env-loading logic for `TokenManager` credentials should reference `src/gamechanger/client.py` for the key naming pattern (e.g., `GAMECHANGER_REFRESH_TOKEN_WEB`, `GAMECHANGER_CLIENT_ID_WEB`, etc.).

Key files to reference for TokenManager construction:
- `/workspaces/baseball-crawl/src/gamechanger/token_manager.py` -- `TokenManager` class, `AuthSigningError`
- `/workspaces/baseball-crawl/src/gamechanger/client.py` -- env key naming pattern (`_required_keys()`, `_PROFILE_SUFFIXES`)
- `/workspaces/baseball-crawl/src/gamechanger/exceptions.py` -- `ConfigurationError`, `CredentialExpiredError`

## Dependencies
- **Blocked by**: E-078-01 (needs `refresh` name slot cleared)
- **Blocks**: E-078-03

## Files to Create or Modify
- `src/cli/creds.py` -- add new `refresh` command
- `tests/test_cli_creds.py` -- add tests for new `refresh` command

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The `force_refresh()` method handles `.env` write-back internally via `atomic_merge_env_file()`. The CLI command does not need to do any `.env` writing itself -- just call `force_refresh()` and report the result.

**Obtaining expiry for the success message (AC-1):** `force_refresh()` returns only the access token string, not the expiry timestamp. To display "expires in Ns", base64-decode the JWT payload (second segment) and extract the `exp` claim, then compute `exp - int(time.time())`. No external JWT library is needed -- just `base64.urlsafe_b64decode` and `json.loads`. This is safe because we just received the token from the server and only need the claims for display, not verification.
