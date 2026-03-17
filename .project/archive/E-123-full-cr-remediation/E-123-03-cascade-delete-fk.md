# E-123-03: User Cascade Delete FK Fix

## Epic
[E-123: Full Code Review Remediation](epic.md)

## Status
`DONE`

## Description
After this story is complete, deleting a user via the admin UI will correctly cascade through the `coaching_assignments` table, preventing `IntegrityError` when a user has coaching assignments. A test will verify the complete cascade.

## Context
CR1-C2 confirmed that `_delete_user()` in `src/api/routes/admin.py:279-294` deletes from `user_team_access`, `sessions`, `magic_link_tokens`, `passkey_credentials`, then `users` -- but omits `coaching_assignments`, which has a `user_id` FK to `users(id)`. With `PRAGMA foreign_keys=ON`, deleting a user with coaching assignments crashes with `IntegrityError`. CR1-M4 confirmed no test covers this scenario. See `/.project/research/full-code-review/cr1-verified.md` (C2, M4) for evidence.

## Acceptance Criteria
- [ ] **AC-1**: `_delete_user()` includes `DELETE FROM coaching_assignments WHERE user_id = ?` before `DELETE FROM users`
- [ ] **AC-2**: A test creates a user with coaching assignments, deletes the user, and verifies no `IntegrityError` is raised
- [ ] **AC-3**: The test verifies `coaching_assignments` rows are deleted after user deletion
- [ ] **AC-4**: All existing tests pass

## Technical Approach
Read `_delete_user()` at `src/api/routes/admin.py:279-294` and the schema at `migrations/001_initial_schema.sql` to confirm the FK relationship. Add the missing DELETE statement in the correct cascade order. Add a test in `tests/test_admin.py` within the `TestCascadeDelete` class that inserts a user with coaching assignments and verifies deletion succeeds. See TN-3 in the epic for details.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/routes/admin.py`
- `tests/test_admin.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
