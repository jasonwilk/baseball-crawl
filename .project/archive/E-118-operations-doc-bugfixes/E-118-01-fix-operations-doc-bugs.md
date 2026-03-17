# E-118-01: Fix Three Documentation Bugs in Operations Guide

## Epic
[E-118: Fix Documentation Bugs in Operations Guide](epic.md)

## Status
`DONE`

## Description
After this story is complete, `docs/admin/operations.md` will accurately reflect the codebase in three places where it currently contains incorrect information: a wrong API endpoint URL, an invalid input format example, and a wrong admin UI path.

## Context
Codex review of E-115 output identified three factual errors in the operations guide. Each has been confirmed against the source code. All fixes are in a single file and are independent line-level corrections.

## Acceptance Criteria
- [x] **AC-1**: The bridge endpoint reference is corrected from `GET /teams/{team_uuid}/public-team-profile-id` to `GET /teams/public/{public_id}/id`, per Technical Notes Bug 1
- [x] **AC-2**: The bare UUID line (`A bare UUID: 72bb77d8-...` or equivalent) is removed from the "What the URL parser accepts" list, per Technical Notes Bug 2
- [x] **AC-3**: The `/admin/opponents` reference for connecting discovered placeholders is replaced with the correct upgrade path (paste the GameChanger URL via the Add Team form at `/admin/teams`), per Technical Notes Bug 3
- [x] **AC-4**: The "Last updated" footer in `docs/admin/operations.md` reflects the current date

## Technical Approach
Three independent find-and-fix edits in `docs/admin/operations.md`. Each fix replaces an incorrect reference with the correct one per the epic's Technical Notes. The implementing agent should read the source files cited in Technical Notes to confirm the correct values before editing.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `docs/admin/operations.md`

## Agent Hint
docs-writer

## Definition of Done
- [x] All acceptance criteria pass
- [x] No regressions in existing documentation
- [x] Changes match the source code references cited in Technical Notes

## Notes
Source code references for verification:
- Bug 1: `src/gamechanger/bridge.py:34-54`
- Bug 2: `src/api/routes/admin.py:915-918`
- Bug 3: `src/api/db.py:765` (`bulk_create_opponents`)
