# E-128-02: `bb creds setup web` Wizard

## Epic
[E-128: Credential Workflow Redesign](epic.md)

## Status
`TODO`

## Description
After this story is complete, `bb creds setup web` will be a guided wizard that reads current credential state, skips steps that are already complete, and walks the operator through the minimum steps to achieve a fully authenticated web profile. The primary path is email+password (fully automated). The fallback path is curl/token import (for operators who don't want to store their password).

## Context
The current CLI has no "happy path" entry point. A new operator faces five commands (`import`, `capture`, `extract-key`, `refresh`, `check`) with no guidance on where to start. The UXD design (2026-03-18 consultation) proposed `bb creds setup` as the single guided entry point. The wizard leverages the login bootstrap path (E-128-01) and multi-format import (E-127-01) as its two authentication strategies.

## Acceptance Criteria
- [ ] **AC-1**: Given no credentials in `.env` and `GAMECHANGER_USER_EMAIL` + `GAMECHANGER_USER_PASSWORD` configured, when `bb creds setup web` is run, then the wizard: (a) extracts and updates both CLIENT_ID and CLIENT_KEY from the JS bundle to `.env`, (b) generates or uses a device ID per TN-2, (c) reloads `.env` values after extraction before constructing TokenManager, (d) executes the login flow via `TokenManager.do_login()`, (e) verifies via GET /me/user, and (f) prints success with token lifetime.
- [ ] **AC-2**: Given credentials already exist and are valid (client key current, refresh token valid, API responds 200), when `bb creds setup web` is run, then the wizard reports "Web profile is already authenticated" with current status and exits cleanly.
- [ ] **AC-3**: Given email+password are NOT in `.env`, when `bb creds setup web` is run, then the wizard names the specific missing variable(s) (e.g., "Missing: GAMECHANGER_USER_EMAIL") and instructs the operator to add them to `.env` and re-run. Below the primary instruction, the wizard offers the fallback path: "Alternatively, capture a curl from browser DevTools and run `bb creds import`."
- [ ] **AC-4**: Given the client key in `.env` is stale (extract-key finds a different key in the JS bundle), when `bb creds setup web` is run, then the wizard auto-updates the client key before proceeding with login.
- [ ] **AC-5**: Given the JS bundle fetch fails (network error, GC down), when `bb creds setup web` is run, then the wizard prints a clear error and suggests retrying or using `bb creds import` as fallback.
- [ ] **AC-6**: Tests cover: full happy path (email+password → authenticated), already-authenticated skip, no-password fallback guidance, stale key auto-update, and network error handling.

## Technical Approach
The wizard is a new Typer command in `src/cli/creds.py` per Technical Notes TN-2. It orchestrates existing building blocks: `extract_client_key()` from `key_extractor.py`, `TokenManager.do_login()` from E-128-01, `run_api_check()` from `credentials.py`. The wizard does not duplicate any logic -- it composes existing functions into a guided flow.

Key files to study: `src/cli/creds.py` (command structure), `src/gamechanger/key_extractor.py` (client key extraction), `src/gamechanger/token_manager.py` (`do_login()` from E-128-01), `src/gamechanger/credentials.py` (diagnostic checks).

## Dependencies
- **Blocked by**: E-128-01 (login bootstrap path -- provides `do_login()`), E-128-R-01 (device ID probe -- determines synthetic vs captured ID), E-127-01 (multi-format import -- provides fallback path), E-127-02 (extract-key fix -- reliable key extraction)
- **Blocks**: E-128-07 (production runbook documents the setup flow)

## Files to Create or Modify
- `src/cli/creds.py` -- add `setup` command with `web` subflow
- `tests/test_cli_creds.py` -- wizard integration tests

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
