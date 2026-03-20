# E-128-05: Smarter Error Diagnostics

## Epic
[E-128: Credential Workflow Redesign](epic.md)

## Status
`DONE`

## Description
After this story is complete, credential error messages will auto-diagnose the root cause (stale client key vs expired refresh token vs clock skew) and prescribe exactly one next command. The current pattern of branching error messages ("if X, do A; if Y, do B") is replaced with inline diagnosis that narrows to one remediation path.

## Context
The current error messages for `bb creds refresh` failures present multiple possible causes and remediation paths, requiring the operator to parse the message and choose. Two distinct failure modes exist: HTTP 400 = signature computation error (stale client key or clock skew, addressed by AC-1), HTTP 401 = token rejection (expired refresh token or stale key mimicking token expiry, addressed by AC-2). The stale-client-key trap is especially confusing: a stale key causes HTTP 401 identical to an expired refresh token. The UXD design (2026-03-18) proposed: diagnose further at the point of failure and prescribe one thing.

## Acceptance Criteria
- [ ] **AC-1**: Given `bb creds refresh` fails with HTTP 400 (signature rejected), then the command runs an inline client key check (calls `extract_client_key()` and compares to `.env`). If the key changed: message says "Client key is stale" and prescribes `bb creds extract-key --apply`. If the key is current: message says "Signature rejected but key is current" and suggests checking system clock.
- [ ] **AC-2**: Given `bb creds refresh` fails with HTTP 401 (token rejected), then the command checks the refresh token's JWT `exp` locally. If expired: message says "Refresh token expired" and prescribes `bb creds setup web`. If not expired: message says "Token rejected but not expired locally -- client key may be stale" and prescribes `bb creds extract-key --apply`.
- [ ] **AC-3**: Given the inline client key check fails (network error fetching JS bundle), then the diagnostic falls back to a simplified two-step message: "Refresh failed. Could not run additional diagnostics (network error). Try: `bb creds extract-key --apply` (if key may be stale), or `bb creds setup web` (to re-authenticate from scratch)." This is an ordered suggestion, not a branching diagnostic -- try key fix first, full setup second.
- [ ] **AC-4**: Error messages never expose credential values (tokens, keys, passwords). Only key names, status indicators, and commands are shown.
- [ ] **AC-5**: Tests cover: stale key detection, expired token detection, non-expired token with 401, network error fallback.

## Technical Approach
The diagnostic logic wraps the existing error handling in `bb creds refresh` per Technical Notes TN-4. On `AuthSigningError` (HTTP 400), call `extract_client_key()` in a try/except and compare. On `CredentialExpiredError` (HTTP 401), decode the refresh token JWT locally to check expiry. The inline diagnostics are best-effort -- if the additional check fails, fall back to AC-3's ordered fallback message.

Key files to study: `src/cli/creds.py` (lines 234-268: refresh error handling), `src/gamechanger/token_manager.py` (error classes), `src/gamechanger/key_extractor.py` (`extract_client_key()`).

## Dependencies
- **Blocked by**: E-128-01 (login bootstrap introduces new error states that this story must handle)
- **Blocks**: None

## Files to Create or Modify
- `src/cli/creds.py` -- enhance error handling in `refresh` command with inline diagnostics
- `tests/test_cli_creds.py` -- error diagnostic tests

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
