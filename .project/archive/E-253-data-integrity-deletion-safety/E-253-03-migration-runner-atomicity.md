# E-253-03: Migration-Runner Atomicity + Docstring Correction

## Epic
[E-253: Data-Integrity & Deletion Safety](epic.md)

## Status
`DONE`

## Description
After this story is complete, applying a migration is atomic: a mid-file failure in a multi-statement migration leaves ZERO of that file's statements applied and no `_migrations` row, so the database never wedges into a permanent duplicate-column crash-loop. The false "in a transaction" docstring is corrected to match the real behavior.

## Context
See epic Technical Notes **TN-4**. `migrations/apply_migrations.py:114-141` uses `conn.executescript()`, which COMMITs any pending transaction on entry and runs bare DDL in autocommit mode. A failing 2nd `ALTER` in a multi-ALTER migration (003/007/009 have that shape) leaves the earlier statements committed, and the existing `rollback` has nothing to undo — the DB is stuck re-attempting the already-applied statement forever. The docstring at `:118` claims the SQL runs "in a transaction," which is false.

This story lands BEFORE the two new migrations (009/010) so they run under the fixed runner.

## Acceptance Criteria
- [ ] **AC-1**: Given a multi-statement migration whose Nth statement fails (N > 1), when the runner applies it, then NONE of that file's statements are applied (the database schema is unchanged from before the attempt) AND no row for that file exists in `_migrations` — proven by a failing-input test.
- [ ] **AC-2**: Given the same failed migration, when the runner is re-invoked after the underlying cause is fixed, then the migration applies cleanly (no "duplicate column" / already-applied crash-loop) — the failure is recoverable, not permanent.
- [ ] **AC-3**: A normal (passing) migration still applies and records its `_migrations` row exactly once; existing migrations 001-008 continue to apply on a fresh DB with no behavior change.
- [ ] **AC-4**: Foreign-key enforcement is active for the migration body per the FK-pragma ordering constraint in TN-4 (pragma set before the transaction opens).
- [ ] **AC-5**: The docstring at `apply_migrations.py:118` is corrected to accurately describe the atomic behavior (no longer claims "in a transaction" while running autocommit DDL).

## Technical Approach
See epic Technical Notes **TN-4** for the recommended single-`executescript` shape (`PRAGMA foreign_keys=ON;\nBEGIN;\n{body}\nINSERT _migrations;\nCOMMIT;`) and the two footguns (FK pragma is a no-op inside a transaction; `executescript` cannot nest in a manual `BEGIN`). Escape the filename interpolated into the `_migrations` INSERT defensively. The implementing agent owns the final mechanism.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-253-02 (migration 009), E-253-05 (migration 010) — both new migrations should run under the fixed runner

## Files to Create or Modify
- `migrations/apply_migrations.py`
- `tests/` — migration-runner atomicity test (failing-input: mid-file failure ⇒ zero applied, no `_migrations` row; plus recoverability)

## Agent Hint
data-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Cross-reference: `.claude/rules/migrations.md` ("executescript() and PRAGMAs" — the pragma-reset behavior).
