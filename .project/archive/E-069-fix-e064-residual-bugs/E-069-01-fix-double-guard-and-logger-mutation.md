# E-069-01: Fix Double Production Guard and Root Logger Mutation

## Epic
[E-069: Fix E-064 Residual Bugs](epic.md)

## Status
`DONE`

## Description
After this story is complete, `bb db reset` will fire the production guard exactly once, and importing `migrations.apply_migrations` will no longer mutate the root logger. The CLI keeps its early `check_production_guard()` call for correct sequencing (guard before confirmation prompt), then passes `_skip_guard=True` to `reset_database()` to prevent a second execution. The `logging.basicConfig()` call in `apply_migrations.py` will only execute when the script is run directly.

## Context
E-064 moved reset logic from `scripts/reset_dev_db.py` into `src/db/reset.py`. The `reset_database()` function includes `check_production_guard()` as a safety net for all callers. But `src/cli/db.py` also calls `check_production_guard()` before the confirmation prompt, creating a double execution. Meanwhile, `migrations/apply_migrations.py` has a module-level `logging.basicConfig()` that fires on import, polluting the root logger for any process that imports `src.db.reset`.

## Acceptance Criteria
- [ ] **AC-1**: Given APP_ENV=production and no --force flag, when `bb db reset` is invoked, then exactly one error message is displayed (the `logger.error` from `check_production_guard()`), no duplicate Rich-formatted message appears, the confirmation prompt does NOT appear before the guard blocks, and the command exits non-zero.
- [ ] **AC-2**: Given APP_ENV=production and --force flag, when `bb db reset` is invoked, then exactly one warning is logged (the `logger.warning` from `check_production_guard()`), no duplicate warning appears, and the reset proceeds.
- [ ] **AC-3**: Given a fresh Python process, when `from src.db.reset import reset_database` is executed, then `logging.root.handlers` is not modified by the import (no handlers added by `basicConfig`). Test via `subprocess.run(["python", "-c", ...])` -- not in-process (see Technical Notes).
- [ ] **AC-4**: Given a fresh Python process, when `from migrations.apply_migrations import run_migrations` is executed, then `logging.root.handlers` is not modified by the import. Test via `subprocess.run(["python", "-c", ...])` -- not in-process (see Technical Notes).
- [ ] **AC-5**: Given `apply_migrations.py` is run directly (`python migrations/apply_migrations.py`), then the `[migrations]` log format is still used for its own output.
- [ ] **AC-6**: All existing tests continue to pass.
- [ ] **AC-7**: `reset_database()` in `src/db/reset.py` accepts a `_skip_guard: bool = False` parameter. When `_skip_guard=True`, the internal `check_production_guard()` call is skipped. The default (`False`) preserves the safety net for direct callers.

## Technical Approach

**Double guard**: The CLI must call `check_production_guard()` before the confirmation prompt (for correct sequencing -- the guard must block before the user is asked to confirm). After the guard passes, the CLI calls `reset_database()` which contains its own internal guard for direct callers. To prevent double execution, `reset_database()` accepts a `_skip_guard: bool = False` parameter. The CLI passes `_skip_guard=True` after calling the guard early. Direct callers (like `scripts/reset_dev_db.py`) do not pass `_skip_guard`, so the internal guard remains their safety net.

The CLI's current Rich-formatted error wrapper (lines 60-66 of `src/cli/db.py`) should be removed. The `SystemExit` from the early `check_production_guard()` call should be caught and converted to a `typer.Exit`. The implementing agent decides whether to add Rich formatting in that handler for CLI consistency.

**Implementation note**: After the refactor, the `SystemExit` catch at `src/cli/db.py` lines 77-79 (which catches errors from `reset_database()`) will no longer receive production-guard `SystemExit`s (since `_skip_guard=True` suppresses the internal call). The production guard path now exits through the CLI's own early `check_production_guard()` call. Verify the catch at line 77 is still needed for unexpected `SystemExit` from deeper in the call stack, or simplify it.

**Logger mutation**: `migrations/apply_migrations.py` line 33 has `logging.basicConfig()` at module scope. This needs to move inside the `if __name__ == "__main__":` block (line 193) so it only runs when the script is executed directly, not when imported. The `logger = logging.getLogger(__name__)` at line 38 stays at module scope -- it does not configure the root logger.

**AC-3/AC-4 testing**: These ACs must be tested via `subprocess.run(["python", "-c", ...])` assertions, not in-process import inspection. Python's module caching (`sys.modules`) causes in-process tests to give false greens when the module has already been imported elsewhere in the test session. A subprocess runs a fresh interpreter with no prior imports.

**Key constraint**: `reset_database()` must remain safe for direct callers who do not pass `_skip_guard`. The `_skip_guard` parameter has a `False` default -- the guard runs unless explicitly skipped.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-069-02

## Files to Create or Modify
- `src/cli/db.py` -- remove Rich error wrapper (lines 60-66), restructure `SystemExit` handling for early guard call, pass `_skip_guard=True` to `reset_database()`
- `migrations/apply_migrations.py` -- move `logging.basicConfig()` inside `if __name__ == "__main__":` block
- `src/db/reset.py` -- add `_skip_guard: bool = False` parameter to `reset_database()`, update docstring
- `tests/test_cli.py` or new test file -- tests for AC-1 through AC-7 (AC-3/AC-4 via subprocess)
- `tests/test_cli_db.py` -- update mocked `reset_database()` call assertions to include `_skip_guard=True` where the CLI passes it (e.g., `assert_called_once_with(db_path=None, force=True)` becomes `assert_called_once_with(db_path=None, force=True, _skip_guard=True)`)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-069-02**: The logging fix (AC-3/AC-4) ensures clean import behavior for all standalone scripts. Note: the E-069-02 dependency is logical ordering, not hard technical -- `--help` subprocess tests would pass even without the logging fix, but the dependency ensures correct sequencing.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- `scripts/reset_dev_db.py` calls `reset_database()` directly without a separate guard call -- it already works correctly. No changes needed there.
- The `check_production_guard` import in `src/cli/db.py` line 12 remains used -- the CLI still calls it directly for the early guard check.
