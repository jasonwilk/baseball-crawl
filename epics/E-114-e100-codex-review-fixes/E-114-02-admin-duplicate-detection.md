# E-114-02: Fix Admin Duplicate Detection on Reverify Failure

## Epic
[E-114: E-100 Codex Review Fixes](epic.md)

## Status
`TODO`

## Description
After this story is complete, the admin add-team flow detects duplicate teams even when the TOCTOU bridge reverification fails (403), preventing creation of a second row for a team that already exists with a gc_uuid from prior opponent resolution.

## Context
The GET confirm handler already calls `_check_duplicate_new` with the Phase 1 gc_uuid from query params, so duplicates are caught at render time. The bug is **POST-side only**: when `_toctou_refresh_uuid` returns None (bridge 403 on reverify), `_check_duplicate_new` only checks `public_id` because `gc_uuid_value` is None. If opponent_resolver previously created a row with the team's gc_uuid but no public_id, the POST duplicate check misses it. Result: two rows for the same real-world team with stats accumulating separately. Low probability (requires credential expiry between Phase 1 and Phase 2) but hard to recover from.

## Acceptance Criteria
- [ ] **AC-1**: When `_toctou_refresh_uuid` returns None after a previously successful Phase 1 bridge lookup, the duplicate check still catches an existing row that has the gc_uuid discovered in Phase 1. The Phase 1 gc_uuid must be available to the duplicate check even when reverify fails.
- [ ] **AC-2**: The existing duplicate detection for `public_id` and `gc_uuid` (when non-None) is not weakened or removed.
- [ ] **AC-3**: A test exists that covers the specific scenario: (a) a team row exists with gc_uuid but no public_id (as created by opponent_resolver), (b) the add-team confirm POST arrives with the same team's public_id but gc_uuid=None (reverify failed), (c) the system detects the duplicate and rejects the insert.
- [ ] **AC-4**: A test exists for the `discover-opponents` admin route that verifies it returns discovered opponents correctly (covering the A-P2a gap identified in the codex test review).
- [ ] **AC-5**: Existing admin route tests continue to pass.

## Technical Approach
The core issue is that the original Phase 1 gc_uuid is lost when reverify fails. The Phase 1 bridge lookup discovers a gc_uuid, but when `_toctou_refresh_uuid` returns None (403 on reverify), `gc_uuid_value` becomes None and `_check_duplicate_new` can only check `public_id`. The constraint: the duplicate check at submit time must have access to the gc_uuid that Phase 1 originally discovered, even when reverify fails. How that gc_uuid is preserved across the Phase 1 -> Phase 2 boundary is an implementation decision.

Context files to read:
- `/workspaces/baseball-crawl/src/api/routes/admin.py` (the confirm flow: `confirm_team_submit`, `_toctou_refresh_uuid`, `_check_duplicate_new`, `_insert_team_new`)
- `/workspaces/baseball-crawl/src/api/templates/admin/confirm_team.html` (form fields)
- `/workspaces/baseball-crawl/tests/test_admin_teams.py`
- `/workspaces/baseball-crawl/tests/test_admin_opponents.py` (for discover-opponents route test)

## Dependencies
- **Blocked by**: None
- **Blocks**: E-114-03 (shared test file), E-114-05 (shared test files)

## Files to Create or Modify
- `src/api/routes/admin.py` (modified)
- `src/api/templates/admin/confirm_team.html` (possibly modified -- depends on how Phase 1 gc_uuid is preserved)
- `tests/test_admin_teams.py` (modified -- new test case)
- `tests/test_admin_opponents.py` (modified -- new discover-opponents route test)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
