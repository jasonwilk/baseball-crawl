# E-128-03: `bb creds setup mobile` Wizard

## Epic
[E-128: Credential Workflow Redesign](epic.md)

## Status
`DONE`

## Description
After this story is complete, `bb creds setup mobile` will be a guided step-by-step wizard that walks the operator through the mitmproxy capture process for mobile credentials. It explicitly acknowledges the Mac-host boundary, guides the operator through iPhone proxy configuration, and validates captured credentials. This replaces the confusing split between `bb creds capture` (which scans for already-captured creds) and documentation the operator must find and follow separately.

## Context
Mobile credential capture requires mitmproxy running on the Mac host (not in the devcontainer). The current `bb creds capture` command only checks whether credentials exist in `.env` -- it doesn't guide the operator through the capture process. The operator must separately find and follow `docs/admin/mitmproxy-guide.md`. The UXD design (2026-03-18) proposed absorbing the guidance inline into the wizard, making it self-contained.

## Acceptance Criteria
- [ ] **AC-1**: Given no mobile credentials in `.env`, when `bb creds setup mobile` is run, then the wizard prints all four numbered steps upfront: (1) start proxy on Mac host (explicitly stating the Mac-host boundary), (2) configure iPhone proxy, (3) force-quit and reopen GC app, (4) scan for credentials. After printing all steps, the wizard shows a single prompt: "Press Enter when you've completed steps 1-3."
- [ ] **AC-2**: Given the operator presses Enter after step 3, when the wizard scans `.env`, then it reports which mobile credential keys were found and which are missing (same keys as current `bb creds capture`).
- [ ] **AC-3**: Given all mobile credentials are present in `.env`, when the wizard validates, then it calls GET /me/user with the mobile access token and reports the result with token lifetime ("valid for ~11 hours, no auto-refresh -- recapture when expired").
- [ ] **AC-4**: Given mobile credentials already exist and are valid, when `bb creds setup mobile` is run, then the wizard reports current status and exits cleanly ("Mobile profile authenticated. Access token valid for ~X hours.").
- [ ] **AC-5**: Given the mobile access token is expired but the refresh token is still valid, when the wizard reports status, then it shows the refresh token lifetime and notes that recapture is needed for a fresh access token (same diagnostic as current `bb creds capture`).
- [ ] **AC-6**: Tests cover: no-credentials guided flow (mocked input), already-authenticated skip, expired access token diagnostic.

## Technical Approach
The wizard is a new branch in the `setup` command in `src/cli/creds.py` per Technical Notes TN-2. It reuses `_print_capture_guidance()` logic and `run_api_check()` from `credentials.py`. The step-by-step prompts use `typer.prompt()` or `input()` for the "press Enter" interaction.

Key files to study: `src/cli/creds.py` (existing `capture` command logic, lines 682-707), `docs/admin/mitmproxy-guide.md` (current guidance to inline).

## Dependencies
- **Blocked by**: None (mobile path is independent of web login bootstrap)
- **Blocks**: None

## Files to Create or Modify
- `src/cli/creds.py` -- add mobile subflow to `setup` command
- `tests/test_cli_creds.py` -- wizard tests for mobile flow

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
