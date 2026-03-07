# E-069: Fix E-064 Residual Bugs

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
The E-064 import restructuring (moving reusable logic from `scripts/` to `src/`) introduced three residual issues: a double production guard in `bb db reset`, root logger mutation on import of `src/db/reset`, and no subprocess smoke tests for standalone script entry points. These were found by a codex code review of E-066 changes (which itself passed clean -- the findings are all from E-064's diff).

## Background & Context
E-064 successfully fixed the `bb` CLI import crash by moving business logic from `scripts/` into `src/` packages (`src/db/`, `src/pipeline/`, `src/gamechanger/credentials.py`). The `bb` CLI works correctly now, and 930+ tests pass. However, the restructuring left behind three issues:

1. **Double production guard**: `src/cli/db.py` calls `check_production_guard()` before the confirmation prompt (lines 58-66), then `reset_database()` calls it again internally (line 176 of `src/db/reset.py`). The guard fires twice in production -- operators see a raw logger error AND a Rich-formatted error, or with `--force` see the warning printed twice.

2. **Root logger mutation on import**: `src/db/reset.py` line 15 imports `migrations.apply_migrations`, whose module-level `logging.basicConfig()` (line 33) mutates the root logger for the entire process. Merely importing `bb db` (which happens on any `bb` invocation since Typer loads all subcommands) configures root logging to INFO with the `[migrations]` formatter. This breaks caller-controlled logging and causes non-migration messages to use the migration log format when scripts run directly.

3. **No standalone script subprocess tests**: The subprocess smoke tests in `tests/test_cli.py` only cover the `bb` entry point. The standalone `python scripts/*.py` entry points have no subprocess coverage to verify they still work after the import restructuring. The logging regression in finding #2 is exactly the kind of breakage this gap would catch.

No expert consultation required -- pure Python implementation fixes with clear scope. The SE who consulted on E-064 already identified the relevant patterns.

## Goals
- Eliminate double production guard execution in `bb db reset`
- Prevent `migrations.apply_migrations` from mutating the root logger on import
- Add subprocess smoke tests for standalone script entry points

## Non-Goals
- Redesigning the CLI module structure
- Changing the `bb` command interface
- Refactoring `apply_migrations.py` beyond the logging fix

## Success Criteria
- `bb db reset` in production (without `--force`) shows exactly one error message, not two
- `bb db reset --force` in production shows exactly one warning, not two
- Importing `src.db.reset` or `src.cli.db` does not mutate the root logger
- Running `python scripts/reset_dev_db.py` uses the script's own log format, not the migration format
- All standalone scripts (`scripts/*.py`) have subprocess smoke tests that verify they exit cleanly with `--help`
- All existing tests continue to pass

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-069-01 | Fix double production guard and root logger mutation | TODO | None | software-engineer |
| E-069-02 | Add subprocess smoke tests for standalone script entry points | TODO | E-069-01 | software-engineer |

## Dispatch Team
- software-engineer

## Technical Notes

### Finding 1: Double Production Guard

The call chain for `bb db reset`:
1. `src/cli/db.py` line 58-59 calls `check_production_guard(force=force)` -- fires the guard
2. If the guard passes (not production, or production+force), the confirmation prompt runs
3. `src/cli/db.py` line 76 calls `reset_database(db_path=db_path, force=force)`
4. `src/db/reset.py` line 176 calls `check_production_guard(force=force)` again inside `reset_database()`

The `reset_database()` docstring says "The production guard is handled here; callers do not need to call it separately." But `src/cli/db.py` calls it separately anyway, creating the double execution.

The standalone script `scripts/reset_dev_db.py` calls `reset_database()` directly (line 85) and does NOT call `check_production_guard()` separately -- so it only fires once. The bug is CLI-specific.

**Key constraint**: `reset_database()` must remain safe for direct callers (like `scripts/reset_dev_db.py`) who do not call `check_production_guard()` separately. The guard inside `reset_database()` is the safety net. The fix is to remove the redundant call in `src/cli/db.py`, not the one in `reset_database()`.

### Finding 2: Root Logger Mutation

`migrations/apply_migrations.py` line 33 has a module-level `logging.basicConfig()` call. This runs at import time, not just when the script is run directly. The import chain:

1. `src/db/reset.py` line 15: `from migrations.apply_migrations import run_migrations`
2. This triggers `logging.basicConfig()` at module scope in `apply_migrations.py`
3. `src/cli/db.py` imports from `src/db/reset` at module scope
4. Typer loads all subcommand modules on any `bb` invocation

The fix: move the `logging.basicConfig()` call inside the `if __name__ == "__main__":` block, so it only runs when `apply_migrations.py` is executed directly as a script. The `logger = logging.getLogger(__name__)` line is fine at module scope -- it does not configure the root logger.

### Finding 3: Standalone Script Subprocess Tests

The E-064 subprocess smoke tests cover `bb --help` and subcommand help pages. But the standalone scripts (`python scripts/bootstrap.py --help`, `python scripts/crawl.py --help`, etc.) have no subprocess coverage. These scripts use `sys.path.insert()` to bootstrap imports, and import-time side effects (like finding #2) only manifest when run as real subprocesses.

Target scripts for `--help` subprocess tests:
- `scripts/bootstrap.py`
- `scripts/crawl.py`
- `scripts/load.py`
- `scripts/check_credentials.py`
- `scripts/backup_db.py`
- `scripts/reset_dev_db.py`

These should follow the same pattern as `test_bb_help_subprocess()` in `tests/test_cli.py`: `subprocess.run(["python", script_path, "--help"])`, assert exit code 0.

### File Conflict Analysis

Stories 01 and 02 share `tests/test_cli.py` only if the new tests go in that file. Story 02 depends on story 01 because the logging fix in story 01 affects whether `scripts/reset_dev_db.py --help` produces clean output in a subprocess test.

## Open Questions
- None

## History
- 2026-03-07: Created from codex code review findings on E-064 changes (found during E-066 review).
