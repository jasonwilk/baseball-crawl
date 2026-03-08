# E-078: Reorganize bb creds CLI Commands

## Status
`COMPLETED`

## Overview
Reorganize the `bb creds` subcommands so their names match what they actually do. The current `bb creds refresh` parses a curl command -- it does not do a programmatic token refresh. E-077 added programmatic refresh via `TokenManager`, but there is no CLI command exposing it. This epic renames the curl-parsing command to `bb creds import` and creates a new `bb creds refresh` that performs the programmatic token refresh cycle.

## Background & Context
E-077 delivered `TokenManager.get_access_token()` and `force_refresh()` -- programmatic exchange of a refresh token for an access token via POST /auth. This works for the web profile (mobile lacks the client key). Before E-077, the only credential operation was parsing a curl command from browser dev tools, which was named `bb creds refresh`. Now that real programmatic refresh exists, the naming is confusing:

- `bb creds refresh` = parses a curl command (should be "import")
- No CLI command = programmatic token refresh (should be "refresh")

The underlying `scripts/refresh_credentials.py` retains its name as a legacy alias. The `bb` CLI is the primary interface; fixing it is sufficient.

Expert consultation completed with claude-architect, software-engineer, and docs-writer. All three approved with notes; findings applied to story files.

## Goals
- `bb creds refresh` performs a programmatic token refresh (web profile) and reports success/failure
- `bb creds import` parses a curl command and writes credentials to `.env` (the current `bb creds refresh` behavior)
- Help text, CLAUDE.md, and admin docs reflect the new command names
- Existing tests updated to match renamed commands

## Non-Goals
- Changing the underlying `scripts/refresh_credentials.py` name or behavior (it stays as a legacy alias)
- Adding mobile profile support to `bb creds refresh` (blocked on client key extraction -- E-075 scope)
- Changing `TokenManager` or `credential_parser` internals

## Success Criteria
- `bb creds refresh` exchanges the web refresh token for an access token and prints a human-readable success/failure message
- `bb creds import` (with `--curl` or `--file` flags) parses a curl command and writes credentials to `.env`, identical to current `bb creds refresh` behavior
- `bb creds --help` lists `check`, `import`, and `refresh` with accurate descriptions
- All existing credential-related tests pass (updated for renamed commands)
- CLAUDE.md Commands section reflects the new names
- Admin docs (`bootstrap-guide.md`, `operations.md`, `getting-started.md`, `error-handling.md`) reference `bb creds import` where they currently say `bb creds refresh`

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-078-01 | Rename bb creds refresh to bb creds import | DONE | None | SE |
| E-078-02 | New bb creds refresh for programmatic token refresh | DONE | E-078-01 | SE |
| E-078-03 | Update docs for creds command reorganization | DONE | E-078-01, E-078-02 | architect |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### Command Layout (After)
```
bb creds check     -- validate credentials in .env (unchanged)
bb creds import    -- parse curl command, write credentials to .env (renamed from refresh)
bb creds refresh   -- programmatic token refresh via POST /auth (new)
```

### Key Files
- `src/cli/creds.py` -- CLI command definitions (primary target)
- `src/gamechanger/token_manager.py` -- `TokenManager` class with `get_access_token()` and `force_refresh()`
- `src/gamechanger/credential_parser.py` -- `parse_curl()` and `merge_env_file()` (unchanged)
- `src/gamechanger/credentials.py` -- `check_credentials()` (unchanged)
- `src/gamechanger/client.py` -- `GameChangerClient` (used to construct TokenManager with correct env vars)
- `tests/test_cli_creds.py` -- CLI tests
- `src/cli/__init__.py` -- module docstring mentions "refresh"
- `src/cli/status.py` -- line 162 references `bb creds refresh` in error output

### TokenManager Integration Notes
`TokenManager` requires `profile`, `client_id`, `client_key`, `refresh_token`, `device_id`, and `base_url`. These are loaded from `.env` via `dotenv_values()`. The `GameChangerClient.__init__()` already has the env-loading logic for these keys (see `_required_keys()` and the constructor). The new `bb creds refresh` command needs to replicate that env-loading pattern (or extract it) to instantiate `TokenManager` directly. The web profile requires all six keys; mobile will raise `ConfigurationError` (no client key).

The `force_refresh()` method unconditionally performs a refresh (bypasses cache). It also persists the rotated refresh token back to `.env` via `atomic_merge_env_file()`. This means `bb creds refresh` is a one-call operation: call `force_refresh()`, and the `.env` is updated automatically.

### Error Cases for bb creds refresh
- Missing credentials in `.env` -> `ConfigurationError` (exit 1, helpful message)
- Refresh token expired/invalid -> `CredentialExpiredError` (exit 1, message to re-capture)
- Signature rejected -> `AuthSigningError` (exit 1, check clock)
- Mobile profile without client key -> `ConfigurationError` (exit 1, explain limitation)
- Success -> print profile, token expiry time remaining, confirmation that `.env` was updated

### References for `bb creds refresh` in docs/code that need updating
- `src/cli/status.py:162,167` -- "run: bb creds refresh" error messages -> "run: bb creds import"
- `tests/test_cli_status.py:79,84` -- test assertions on the remediation hint string
- `src/cli/__init__.py:7` -- module docstring
- `docs/api/error-handling.md:65`
- `docs/admin/bootstrap-guide.md:14,107`
- `docs/admin/operations.md:125,226`
- `docs/admin/getting-started.md:154`
- `docs/admin/architecture.md:47` -- credential capture step description

## Open Questions
None.

## History
- 2026-03-08: Created
- 2026-03-08: Expert consultation (claude-architect, software-engineer, docs-writer). All three APPROVE WITH NOTES. Applied fixes: added `tests/test_cli_status.py` to E-078-01 scope (AC-8), clarified status.py has two references (lines 162+167), added JWT decode technical note for expiry display in E-078-02, reworded E-078-02 AC-7 for testability, added mobile early-exit recommendation to E-078-02 AC-3, fixed E-078-03 AC-7 (Script Aliases entry was missing, not just outdated), added `docs/admin/architecture.md` to E-078-03 scope (AC-8).
- 2026-03-08: Codex spec review triage (4 findings). REFINE: E-078-02 AC-8 tightened ("accurate descriptions" -> concrete assertions about help string content). REFINE: E-078-03 re-routed from docs-writer to claude-architect (CLAUDE.md is a context-layer file per routing precedence rule); Dispatch Team updated accordingly. DISMISS: Finding 3 (api-scout consultation) -- E-078-02 is a thin CLI wrapper around TokenManager.force_refresh(); all POST /auth behavior was discovered and documented during E-077; no new API calls or auth behavior changes; consultation would be redundant. DISMISS: Finding 1 partial ("or similar" in AC-3 is appropriate -- Typer controls exact error wording; "or equivalent" in E-078-03 AC-1/AC-2 provides reasonable flexibility for docs phrasing). DISMISS: Finding 4 (generic DoD) -- standard project boilerplate, ACs are the real contract.
- 2026-03-08: Epic COMPLETED. All 3 stories DONE. E-078-01 renamed `bb creds refresh` to `bb creds import` (code-reviewer APPROVED, 0 MUST FIX). E-078-02 added new `bb creds refresh` for programmatic token refresh via TokenManager.force_refresh() (code-reviewer APPROVED, 0 MUST FIX, 1 SHOULD FIX: vacuous fallback condition in test_mobile_profile_exits_nonzero). E-078-03 updated CLAUDE.md and all admin docs to reflect new command names (context-layer-only, verified by main session). Documentation assessment: No documentation impact beyond E-078-03 scope (docs were updated as part of the epic). Context-layer assessment below.
