# E-127-01: `bb creds import` Multi-Format Input

## Epic
[E-127: Onboarding Workflow Fixes](epic.md)

## Status
`DONE`

## Description
After this story is complete, `bb creds import` will accept three input formats -- curl commands (existing), raw JSON token payloads, and bare JWT strings -- and auto-detect the format without requiring new CLI flags. This eliminates the need for operators to craft curl commands when they only have token values from a proxy capture or browser devtools.

## Context
The current `bb creds import` command (in `src/cli/creds.py`) delegates to `parse_curl()` in `src/gamechanger/credential_parser.py`. It only accepts curl command strings. When an operator has raw tokens (common from mitmproxy captures or browser devtools Application tab), they must either construct a fake curl command or manually edit `.env`. The format detection heuristic is defined in Technical Notes TN-1 of the epic.

## Acceptance Criteria
- [ ] **AC-1**: Given a raw JSON object in GC auth response format (`{"type": "token", "access": {"data": "...", "expires": N}, "refresh": {"data": "...", "expires": N}}`), with or without the `user_id` and `type` top-level fields, when passed to `bb creds import` (via `--curl`, `--file`, or stdin), then the correct `GAMECHANGER_REFRESH_TOKEN_WEB` (and/or access token per profile) are written to `.env`.
- [ ] **AC-1b**: Given a simple token map JSON (`{"access_token": "jwt...", "refresh_token": "jwt..."}`) or a single-token JSON (`{"token": "jwt..."}`), when passed to `bb creds import`, then the tokens are correctly identified and the corresponding env vars are written to `.env`. (These are convenience formats for operator input, not GC API shapes.)
- [ ] **AC-2**: Given a bare JWT string (three dot-separated base64url segments), when passed to `bb creds import`, then the token type is auto-detected (access vs refresh per existing JWT inspection logic) and the correct env var is written to `.env`.
- [ ] **AC-3**: Given a curl command string (existing format), when passed to `bb creds import`, then behavior is unchanged from the current implementation.
- [ ] **AC-4**: Given an unrecognizable input format, when passed to `bb creds import`, then a clear error message is displayed explaining the accepted formats.
- [ ] **AC-5**: The format is auto-detected per Technical Notes TN-1 -- no new CLI flags required for format selection.
- [ ] **AC-6**: Tests cover all input formats (GC auth response JSON including with undocumented `user_id` top-level field, simple token map JSON, single token JSON, bare JWT, curl command), the error case, and `--profile mobile` with JSON input to verify profile routing applies to non-curl formats.

## Technical Approach
The format detection logic and token routing rules are defined in epic Technical Notes TN-1. The existing `credential_parser.py` already has JWT decoding and profile-aware routing logic -- the new code extends input parsing, not token handling. The `merge_env_file()` utility handles `.env` writes.

**Profile routing for non-curl inputs**: For curl commands, the profile comes from the existing `--profile` CLI flag. For JSON and bare JWT inputs, the same `--profile` flag applies -- it defaults to `"web"` (the common case for proxy captures and browser devtools). An operator importing a mobile token would pass `--profile mobile` explicitly. No new flags needed; the existing `--profile` parameter covers all input formats.

Key files to study: `src/gamechanger/credential_parser.py` (existing curl parser, JWT inspection, merge logic), `src/cli/creds.py` (CLI entry point, `import_creds` command).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/credential_parser.py` -- add format detection and JSON/JWT parsing functions
- `src/cli/creds.py` -- wire new input paths into the `import_creds` command
- `tests/test_credential_parser.py` -- tests for new input formats

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
