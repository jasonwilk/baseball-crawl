# E-125-02: SQL Injection Fix + Magic Link Token Hashing

## Epic
[E-125: Full-Project Code Review Remediation](epic.md)

## Status
`DONE`

## Description
After this story is complete, the SQL injection surface in `scouting.py:update_run_load_status` will be eliminated (parameterized SQL only), and magic link tokens will be hashed before database storage using the same SHA-256 pattern already used for session tokens. These are the two most urgent security fixes in the codebase.

## Context
**SQL injection** (Review 02 C-3): `update_run_load_status` uses f-string interpolation to embed a value derived from the `status` function parameter directly into SQL. The CHECK constraint limits exploitability but the pattern is a security violation. The fix is a SQL CASE expression with parameterized values.

**Magic link plaintext** (Review 03 #5): Magic link tokens are stored in cleartext in `magic_link_tokens` table. Session tokens are properly hashed via `hash_token()` (SHA-256) before storage, but magic link tokens skip this step. If the database file is compromised, all unexpired magic link tokens are exposed. The `hash_token()` function in `src/api/auth.py` already exists and should be reused.

## Acceptance Criteria
- [ ] **AC-1**: `scouting.py:update_run_load_status` uses only parameterized SQL -- no f-string interpolation of any value derived from function parameters
- [ ] **AC-2**: The `completed_at` conditional logic uses a SQL CASE expression or equivalent parameterized approach
- [ ] **AC-3**: Magic link tokens are hashed (via `hash_token()`) before INSERT into `magic_link_tokens`
- [ ] **AC-4**: Token verification (`/auth/verify?token=X`) hashes the incoming token before database lookup
- [ ] **AC-5**: Existing magic link login flow works end-to-end (test: request magic link, verify token, session created)
- [ ] **AC-6**: Tests verify that the scouting run status update works for both "completed" and "failed" statuses with correct `completed_at` behavior
- [ ] **AC-7**: All existing tests pass

## Technical Approach
**SQL injection fix**: Replace the f-string `completed_at` interpolation with a CASE expression: `completed_at = CASE WHEN ? = 'completed' THEN strftime(...) ELSE NULL END`. This keeps all values parameterized.

**Magic link hashing**: Per Technical Notes TN-2, follow the session token pattern -- `hash_token()` already exists in `src/api/auth.py`. Apply it at INSERT time and at verification lookup time.

## Dependencies
- **Blocked by**: E-125-01 (CSRF changes affect `tests/test_auth_routes.py` fixtures -- see TN-8)
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/crawlers/scouting.py` (update_run_load_status method)
- `src/api/routes/auth.py` (magic link INSERT and verify lookup)
- `tests/test_scouting.py` or `tests/test_scouting_loader.py` (scouting status update test)
- `tests/test_auth_routes.py` (magic link flow with hashing)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The SQL injection is technically limited by the CHECK constraint on `scouting_runs.status` (`IN ('pending', 'running', 'completed', 'failed')`), but the pattern must still be fixed -- defense-in-depth.
- The `hash_token()` function is at `src/api/auth.py:96`. It uses SHA-256.
