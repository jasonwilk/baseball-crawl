# E-128-04: `bb creds` Status Dashboard

## Epic
[E-128: Credential Workflow Redesign](epic.md)

## Status
`DONE`

## Description
After this story is complete, running `bb creds` with no subcommand will display a compact credential status dashboard for all profiles instead of the current help text. The dashboard answers "am I authenticated right now?" in one command and provides actionable next steps for each profile.

## Context
`bb creds` currently shows Typer help text (list of subcommands). This wastes the most natural entry point. Experienced operators don't need the help text -- they need the status. The UXD design (2026-03-18) proposed replacing the help text with a status dashboard that reuses existing diagnostic logic but presents a compact summary.

## Acceptance Criteria
- [ ] **AC-1**: Given `bb creds` is run with no subcommand, then a compact status dashboard is displayed showing each profile (web, mobile) with indicators for: client key, refresh token, API health. Indicator semantics: `[OK]` = present and valid, `[!!]` = present but degraded (expiring soon or stale key), `[XX]` = present but invalid/failed (expired token, API rejected), `[--]` = not configured. Note: For mobile profile, the client key indicator shows `[--]` with a note that mobile client key is not yet extracted. Only indicators applicable to the profile are shown with meaningful status.
- [ ] **AC-2**: Given a profile is fully authenticated (all checks pass), then the dashboard shows "Status: READY" for that profile with no next-step guidance.
- [ ] **AC-3**: Given a profile has some credentials but is not fully functional (e.g., client key present but no refresh token, or stale key), then the dashboard shows "Status: INCOMPLETE" with `[!!]` or `[XX]` indicators on the degraded items and a single next-step command (e.g., "-> Run: bb creds setup web").
- [ ] **AC-4**: Given a profile has no credentials at all, then the dashboard shows "Status: NOT CONFIGURED" with `[--]` indicators and suggests `bb creds setup [profile]`.
- [ ] **AC-5**: The help text remains accessible via `bb creds --help`.
- [ ] **AC-6**: Tests cover: fully authenticated dashboard, partially configured, not configured, and `--help` still works.

## Technical Approach
The dashboard reuses `check_profile_detailed()` from `credentials.py` per Technical Notes TN-3, but renders a compact summary instead of the full Rich panel. The Typer callback (`_creds_group`) currently shows help when no subcommand is invoked; this changes to call the dashboard renderer.

Key files to study: `src/cli/creds.py` (lines 45-50: `_creds_group` callback), `src/gamechanger/credentials.py` (`check_profile_detailed()`).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/cli/creds.py` -- replace help-text callback with dashboard renderer
- `tests/test_cli_creds.py` -- dashboard output tests

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
