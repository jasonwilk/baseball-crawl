# E-069-02: Add Subprocess Smoke Tests for Standalone Script Entry Points

## Epic
[E-069: Fix E-064 Residual Bugs](epic.md)

## Status
`TODO`

## Description
After this story is complete, all standalone operator scripts in `scripts/` will have subprocess smoke tests that verify they can be invoked directly without import errors or side effects. This closes the testing gap that allowed the E-064 logging regression to ship undetected.

## Context
E-064 added subprocess smoke tests for the `bb` console script entry point (e.g., `test_bb_help_subprocess` in `tests/test_cli.py`). But the standalone scripts (`python scripts/*.py`) have no equivalent coverage. These scripts use `sys.path.insert()` to bootstrap imports, and import-time side effects (like the root logger mutation fixed in E-069-01) only manifest when run as real subprocesses -- not under pytest's in-process runner.

## Acceptance Criteria
- [ ] **AC-1**: `scripts/bootstrap.py --help` exits with code 0 in a subprocess test.
- [ ] **AC-2**: `scripts/crawl.py --help` exits with code 0 in a subprocess test.
- [ ] **AC-3**: `scripts/load.py --help` exits with code 0 in a subprocess test.
- [ ] **AC-4**: `scripts/check_credentials.py --help` exits with code 0 in a subprocess test.
- [ ] **AC-5**: `scripts/backup_db.py --help` exits with code 0 in a subprocess test.
- [ ] **AC-6**: `scripts/reset_dev_db.py --help` exits with code 0 in a subprocess test.
- [ ] **AC-7**: Each test uses `subprocess.run()` with `capture_output=True` and asserts on `returncode`, following the pattern established in `tests/test_cli.py` for `bb` subprocess tests.
- [ ] **AC-8**: All existing tests continue to pass.

## Technical Approach

Follow the pattern from `tests/test_cli.py` lines 92-158 (the `bb` subprocess smoke tests). Each test invokes `subprocess.run(["python", script_path, "--help"])` and asserts exit code 0. Use absolute paths derived from the repo root to locate scripts, so tests work regardless of working directory.

The tests should go in a new test file or a new section of an existing test file -- the implementing agent decides the appropriate location. The key requirement is subprocess isolation: each script runs in its own process, so import-time side effects are exercised.

**Reference**: `/workspaces/baseball-crawl/tests/test_cli.py` lines 92-158 for the existing `bb` subprocess smoke test pattern.

## Dependencies
- **Blocked by**: E-069-01 (the logging fix ensures `reset_dev_db.py --help` produces clean output)
- **Blocks**: None

## Files to Create or Modify
- `tests/test_cli.py` (extend) or new test file (e.g., `tests/test_script_entry_points.py`)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- Scripts that require credentials or database access should still exit 0 on `--help` since help display does not trigger business logic.
- `scripts/proxy-refresh-headers.py` and the bash scripts (`proxy-report.sh`, etc.) are out of scope -- this story covers only the Python scripts that import from `src/`.
