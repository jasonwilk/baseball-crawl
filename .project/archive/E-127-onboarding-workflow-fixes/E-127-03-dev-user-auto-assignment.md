# E-127-03: Dev User Auto-Assignment to Member Teams

## Epic
[E-127: Onboarding Workflow Fixes](epic.md)

## Status
`DONE`

## Description
After this story is complete, the `DEV_USER_EMAIL` bypass will automatically assign the dev user to all teams with `membership_type = 'member'`. This eliminates the "You have no team assignments" dead end that occurs after `bb db reset` when the dev user is auto-created but has no `user_team_access` rows.

## Context
In `src/api/auth.py`, `_create_dev_user()` creates a user row but never inserts into `user_team_access`. The existing `_handle_dev_bypass()` flow calls `_get_permitted_teams()` after user creation/lookup, which returns an empty list. The app then shows no teams on the dashboard. The fix is defined in epic Technical Notes TN-3: auto-assign on user creation (atomic, same transaction), plus a backfill for existing dev users with zero assignments. DE confirmed no schema changes needed.

## Acceptance Criteria
- [ ] **AC-1**: Given `DEV_USER_EMAIL` is set and the dev user does not exist, when the first request hits a protected route, then the user is created AND `user_team_access` rows are inserted for every team where `membership_type = 'member'`, in the same database transaction (atomic per TN-3).
- [ ] **AC-2**: Given `DEV_USER_EMAIL` is set and the dev user exists but has zero `user_team_access` rows, when a request hits a protected route, then member team assignments are auto-inserted using `INSERT OR IGNORE` (backfill case, per TN-3).
- [ ] **AC-3**: Given the dev user already has team assignments, when a request hits a protected route, then no duplicate rows are inserted and existing assignments are preserved (`INSERT OR IGNORE` idempotency).
- [ ] **AC-4**: `request.state.permitted_teams` reflects the auto-assigned teams on the same request that triggered the assignment (no second request needed).
- [ ] **AC-5**: Tests cover creation, backfill, and idempotency scenarios.

## Technical Approach
The changes are confined to `src/api/auth.py` in the dev bypass path. Per DE guidance: user creation + team assignment must be in the same transaction, and `INSERT OR IGNORE` ensures idempotency. The backfill check (AC-2) triggers when `_get_permitted_teams()` returns empty for a dev bypass user.

Known constraint (per DE): teams added after dev user creation won't auto-grant. The backfill path (empty permitted_teams triggers re-assignment) covers the most common post-reset case.

Key files to study: `src/api/auth.py` (lines 205-228 for `_handle_dev_bypass`, lines 243-289 for user creation helpers), `migrations/001_initial_schema.sql` (lines 434-439 for `user_team_access` schema).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/auth.py` -- add auto-assignment logic in `_create_dev_user()` and backfill in `_handle_dev_bypass()`
- `tests/test_auth.py` -- tests for auto-assignment and backfill

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
