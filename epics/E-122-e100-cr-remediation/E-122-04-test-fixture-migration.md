# E-122-04: Migrate Inline _SCHEMA_SQL to run_migrations()

## Epic
[E-122: E-100 Family Code Review Remediation (Wave 2)](epic.md)

## Status
`TODO`

## Description
After this story is complete, all 5 test files that currently define inline `_SCHEMA_SQL` strings will use `run_migrations()` instead, eliminating schema drift risk. The inline constants will be removed entirely.

## Context
CR-7/8-W2 confirmed that 5 test files contain hardcoded `_SCHEMA_SQL` strings while 14 other test files already use `run_migrations()`. When the authoritative migration (`001_initial_schema.sql`) changes, the inline copies can silently drift, causing tests to pass against a stale schema. See `/.project/research/cr-e100-family/verified-findings.md` finding CR-7/CR-8-W2 for the file list.

## Acceptance Criteria
- [ ] **AC-1**: `tests/test_admin.py` uses `run_migrations()` instead of inline `_SCHEMA_SQL`. The `_SCHEMA_SQL` constant is removed.
- [ ] **AC-2**: `tests/test_auth_routes.py` uses `run_migrations()` instead of inline `_SCHEMA_SQL`. The `_SCHEMA_SQL` constant is removed.
- [ ] **AC-3**: `tests/test_passkey.py` uses `run_migrations()` instead of inline `_SCHEMA_SQL`. The `_SCHEMA_SQL` constant is removed.
- [ ] **AC-4**: `tests/test_dashboard.py` uses `run_migrations()` instead of inline `_SCHEMA_SQL`. The `_SCHEMA_SQL` constant is removed.
- [ ] **AC-5**: `tests/test_auth.py` uses `run_migrations()` instead of inline `_SCHEMA_SQL`. The `_SCHEMA_SQL` constant is removed.
- [ ] **AC-6**: No test file in the repository defines a variable named exactly `_SCHEMA_SQL` (grep verification — note: `_SCHEMA_SQL_NO_AUTH` in `test_auth.py` is intentionally retained for missing-auth-tables testing and is not a target of this story).
- [ ] **AC-7**: All tests in the 5 modified files pass with `run_migrations()`.
- [ ] **AC-8**: All existing tests pass (no regressions).

## Technical Approach
Study how the 14 existing test files that use `run_migrations()` set up their database fixtures. Apply the same pattern to the 5 target files. Some test files may need additional seed data beyond the schema — preserve any INSERT statements that set up test fixtures while replacing only the schema DDL with `run_migrations()`. See epic Technical Notes TN-4 for the file list. See `/.project/research/cr-e100-family/verified-findings.md` finding CR-7/CR-8-W2.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `tests/test_admin.py`
- `tests/test_auth_routes.py`
- `tests/test_passkey.py`
- `tests/test_dashboard.py`
- `tests/test_auth.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
