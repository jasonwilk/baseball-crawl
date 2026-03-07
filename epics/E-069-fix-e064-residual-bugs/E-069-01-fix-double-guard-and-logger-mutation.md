# E-069-01: Fix Double Production Guard and Root Logger Mutation

## Epic
[E-069: Fix E-064 Residual Bugs](epic.md)

## Status
`TODO`

## Description
After this story is complete, `bb db reset` will fire the production guard exactly once (inside `reset_database()`), and importing `migrations.apply_migrations` will no longer mutate the root logger. The `src/cli/db.py` reset command will rely on `reset_database()`'s internal guard instead of calling `check_production_guard()` separately. The `logging.basicConfig()` call in `apply_migrations.py` will only execute when the script is run directly.

## Context
E-064 moved reset logic from `scripts/reset_dev_db.py` into `src/db/reset.py`. The `reset_database()` function includes `check_production_guard()` as a safety net for all callers. But `src/cli/db.py` also calls `check_production_guard()` before the confirmation prompt, creating a double execution. Meanwhile, `migrations/apply_migrations.py` has a module-level `logging.basicConfig()` that fires on import, polluting the root logger for any process that imports `src.db.reset`.

## Acceptance Criteria
- [ ] **AC-1**: Given APP_ENV=production and no --force flag, when `bb db reset` is invoked, then exactly one error message is displayed (not two) and the command exits non-zero.
- [ ] **AC-2**: Given APP_ENV=production and --force flag, when `bb db reset` is invoked, then exactly one warning is logged (not two) and the reset proceeds.
- [ ] **AC-3**: Given a fresh Python process, when `from src.db.reset import reset_database` is executed, then `logging.root.handlers` is not modified by the import (no handlers added by `basicConfig`).
- [ ] **AC-4**: Given a fresh Python process, when `from migrations.apply_migrations import run_migrations` is executed, then `logging.root.handlers` is not modified by the import.
- [ ] **AC-5**: Given `apply_migrations.py` is run directly (`python migrations/apply_migrations.py`), then the `[migrations]` log format is still used for its own output.
- [ ] **AC-6**: All existing tests continue to pass.

## Technical Approach

**Double guard**: `src/cli/db.py` currently calls `check_production_guard()` at line 58-59, then calls `reset_database()` which calls it again at line 176 of `src/db/reset.py`. The `reset_database()` docstring already says callers do not need to call it separately. The CLI module should stop calling it separately and instead let `reset_database()` handle it. The CLI error handling around the guard call (lines 58-66) should be restructured to catch the `SystemExit` from `reset_database()` instead.

**Logger mutation**: `migrations/apply_migrations.py` line 33 has `logging.basicConfig()` at module scope. This needs to move inside the `if __name__ == "__main__":` block (line 193) so it only runs when the script is executed directly, not when imported. The `logger = logging.getLogger(__name__)` at line 38 stays at module scope -- it does not configure the root logger.

**Key constraint**: `reset_database()` must remain safe for direct callers who do not call `check_production_guard()` separately. Do not remove the guard from `reset_database()`.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-069-02

## Files to Create or Modify
- `src/cli/db.py` -- remove redundant `check_production_guard()` call, restructure error handling
- `migrations/apply_migrations.py` -- move `logging.basicConfig()` inside `if __name__ == "__main__":` block
- `src/db/reset.py` -- no changes expected, but may need docstring clarification
- `tests/test_cli.py` or new test file -- tests for AC-1 through AC-5

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-069-02**: The logging fix (AC-3/AC-4) ensures `scripts/reset_dev_db.py --help` produces clean output when run as a subprocess, which E-069-02's smoke tests depend on.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `check_production_guard` import in `src/cli/db.py` line 12 may become unused after the fix -- remove it if so.
- `scripts/reset_dev_db.py` calls `reset_database()` directly without a separate guard call -- it already works correctly. No changes needed there.
