# E-114-05: Fix Test Schema Drift — Missing Unique Indexes

## Epic
[E-114: E-100 Codex Review Fixes](epic.md)

## Status
`DONE`

## Description
After this story is complete, test files that use inline `_SCHEMA_SQL` include the partial unique indexes on `gc_uuid` and `public_id` from production DDL, ensuring uniqueness violations caught in production are also caught in tests. Additionally, two test coverage gaps are closed: scouting report pitching assertions (C-P2a) and bulk_create_opponents default field assertions (C-P2b).

## Context
Eight test files define inline `_SCHEMA_SQL` that reproduces the production schema but omits the `CREATE UNIQUE INDEX` statements for `gc_uuid` and `public_id`. This means tests pass when inserting duplicate `gc_uuid` or `public_id` values, but the same operations would fail in production. The drift was introduced during E-100 when the schema was rewritten but test schemas were not updated to match.

## Acceptance Criteria
- [ ] **AC-1**: The inline `_SCHEMA_SQL` in `test_admin.py`, `test_admin_opponents.py`, `test_admin_teams.py`, `test_auth.py`, `test_auth_routes.py`, `test_passkey.py`, `test_dashboard.py`, and `test_dashboard_auth.py` includes the `CREATE UNIQUE INDEX` statements for `gc_uuid` and `public_id` that match production DDL in `migrations/001_initial_schema.sql`.
- [ ] **AC-2**: All existing tests in the eight files continue to pass after the schema update. If any test was silently relying on the missing uniqueness constraint, fix the test data (not the constraint).
- [ ] **AC-3**: The `get_opponent_scouting_report()` test in `tests/test_db.py` asserts on the pitching data structure (not just batting), verifying that the function returns both batting and pitching stats for an opponent with game data.
- [ ] **AC-4**: The `bulk_create_opponents()` test in `tests/test_db.py` asserts that created opponent rows have `is_active=0` and `source='discovered'`, verifying the correct default field values per the E-100 schema.
- [ ] **AC-5**: Existing tests across all modified files continue to pass.

## Technical Approach
Read the production schema from `migrations/001_initial_schema.sql` to identify the exact `CREATE UNIQUE INDEX` statements. Add them to each test file's inline `_SCHEMA_SQL`. The implementer should also consider whether refactoring to import the schema from the migration file (instead of inline duplication) is a clean win -- but this is optional and should not block the story if it adds complexity.

For AC-3 and AC-4, expand the existing test functions in `tests/test_db.py` with additional assertions on the existing test data.

Context files to read:
- `/workspaces/baseball-crawl/migrations/001_initial_schema.sql` (authoritative schema)
- `/workspaces/baseball-crawl/tests/test_admin.py`
- `/workspaces/baseball-crawl/tests/test_admin_opponents.py`
- `/workspaces/baseball-crawl/tests/test_admin_teams.py`
- `/workspaces/baseball-crawl/tests/test_auth.py`
- `/workspaces/baseball-crawl/tests/test_auth_routes.py`
- `/workspaces/baseball-crawl/tests/test_passkey.py`
- `/workspaces/baseball-crawl/tests/test_dashboard.py`
- `/workspaces/baseball-crawl/tests/test_dashboard_auth.py`
- `/workspaces/baseball-crawl/tests/test_db.py` (for AC-3, AC-4)

## Dependencies
- **Blocked by**: E-114-02 (shared test files: `test_admin_teams.py`, `test_admin_opponents.py`), E-114-04 (shared test file: `test_dashboard.py`)
- **Blocks**: None

## Files to Create or Modify
- `tests/test_admin.py` (modified)
- `tests/test_admin_opponents.py` (modified)
- `tests/test_admin_teams.py` (modified)
- `tests/test_auth.py` (modified)
- `tests/test_auth_routes.py` (modified)
- `tests/test_passkey.py` (modified)
- `tests/test_dashboard.py` (modified)
- `tests/test_dashboard_auth.py` (modified)
- `tests/test_db.py` (modified -- expanded assertions)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
