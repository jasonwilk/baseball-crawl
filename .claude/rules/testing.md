---
paths:
  - "tests/**"
  - "src/**"  # Test Scope Discovery must fire when agents edit source files
---

# Testing Rules

- Use pytest as the test runner
- IMPORTANT: Never make real HTTP requests in tests -- use mocks or fixtures
- Use pytest fixtures for test data setup
- Test data parsing and transformation logic thoroughly
- Use parametrize for testing multiple input variations
- Name test files as `test_<module>.py`
- Name test functions as `test_<behavior_being_tested>`
- Prefer specific assertions (`assert result == expected`) over generic (`assert result`)
- Include edge cases: empty data, malformed input, missing fields
- **Subprocess smoke tests for console script entry points**: Entry points like `bb` must have at least one test that invokes the command via `subprocess.run()` (e.g., `subprocess.run(["bb", "--help"], ...)`). In-process test runners (`typer.testing.CliRunner`, pytest) add the project root to `sys.path`, which masks packaging and import errors that only surface when the entry point runs as an installed console script. Subprocess tests catch these real-world failures.

## Test Scope Discovery

When you modify a function in an existing source module, you MUST discover and run all test files that import from that module -- not just the tests named in the story's "Files to Create or Modify."

### Why

Story-scoped test lists are written during planning, before the implementation details are known. They cover the obvious test files but can miss cross-file dependencies. During E-085, a change to `check_single_profile()` in `src/gamechanger/credentials.py` broke `tests/test_check_credentials.py`, but the implementer only ran `tests/test_credentials.py` and `tests/test_cli_creds.py` (the story-scoped tests). The broken test was in a different file that also imports from the same module.

### The Discovery Pattern

For each source module you modified, find all test files that import from it:

1. Determine the importable module path. For `src/gamechanger/credentials.py`, this is `gamechanger.credentials`.
2. Search for test files that import from that module:
   ```
   grep -rl "gamechanger.credentials" tests/
   ```
   This catches `from gamechanger.credentials import ...`, `import gamechanger.credentials`, and variant forms. False positives are harmless (extra tests run); false negatives are the real risk, and grep avoids them.
3. Run the discovered test files in addition to any story-scoped tests:
   ```
   pytest tests/test_credentials.py tests/test_cli_creds.py tests/test_check_credentials.py
   ```

### Scope

The default is **targeted discovery**: find and run test files that import from modules you changed. If targeted discovery reveals 10+ test files, run `pytest` (full suite) instead of listing them individually.

### Subprocess Edge Case

Subprocess-based tests (e.g., `test_script_entry_points.py` invokes scripts via `subprocess.run()` that internally import from modified modules) are not discovered by grep because the import happens in a child process. These tests check invocation and help-text, not internal logic -- they will still pass when you change a function's behavior. Subprocess-based tests are discovered by convention, not grep.

## Error-Path Testing

When code calls a function that can fail -- returns an error, raises an exception, or returns a status object indicating failure -- write at least one test where that function fails. Verify the caller handles the failure correctly: propagates the error, sets an appropriate status, returns a non-zero exit code, or surfaces the failure to the operator. The caller must NOT print a misleading success message or exit 0 when a dependency failed.

### Primary Scope: Orchestration Code

This requirement is most critical for orchestration code -- CLI commands, pipeline runners, and any function that chains multiple steps together where a failure in one step must be visible to the operator. These are the paths where silent failure causes the most damage: the operator believes the pipeline succeeded when it did not.

### Example Pattern

```python
def test_scout_command_surfaces_loader_failure(tmp_path, monkeypatch):
    """When the loader fails, the CLI must exit non-zero and report the error."""
    monkeypatch.setattr(
        "gamechanger.loaders.scouting_loader.load_team",
        Mock(side_effect=Exception("DB write failed")),
    )
    result = runner.invoke(app, ["data", "scout", "--team", "test-team"])
    assert result.exit_code != 0
    assert "DB write failed" in result.output
```

Mock the fallible dependency to raise or return a failure indicator. Assert the caller's exit code and output reflect the failure.
