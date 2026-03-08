# E-078-01: Rename bb creds refresh to bb creds import

## Epic
[E-078: Reorganize bb creds CLI Commands](epic.md)

## Status
`DONE`

## Description
After this story is complete, the curl-parsing credential command will be `bb creds import` instead of `bb creds refresh`. The command behavior is identical -- only the name, help text, and test references change. This clears the `refresh` name for E-078-02 to use for programmatic token refresh.

## Context
The current `bb creds refresh` parses a curl command and writes credentials to `.env`. With E-077's programmatic token refresh, "refresh" now has a more natural meaning. This story renames the existing command so the name slot is available.

## Acceptance Criteria
- [ ] **AC-1**: `bb creds import` (no flags) reads from the default curl file and writes credentials to `.env` -- identical to current `bb creds refresh` behavior.
- [ ] **AC-2**: `bb creds import --curl "..."` and `bb creds import --file PATH` work identically to the current `--curl` and `--file` flags on `bb creds refresh`.
- [ ] **AC-3**: `bb creds refresh` no longer exists as a command. Running `bb creds refresh` produces a Typer "No such command" error (or similar). This is temporary -- E-078-02 will create a new `refresh` command.
- [ ] **AC-4**: `bb creds --help` lists `import` and `check` (not `refresh`).
- [ ] **AC-5**: All tests in `tests/test_cli_creds.py` are updated to reference `creds import` instead of `creds refresh` and pass.
- [ ] **AC-6**: `src/cli/__init__.py` module docstring updated to say "import" instead of "refresh".
- [ ] **AC-7**: All references to "bb creds refresh" in `src/cli/status.py` (lines 162 and 167) updated to "bb creds import".
- [ ] **AC-8**: Tests in `tests/test_cli_status.py` that assert against the "bb creds refresh" remediation hint string are updated to assert "bb creds import" and pass.

## Technical Approach
This is a rename within `src/cli/creds.py`: the function currently named `refresh` becomes `import_creds` (or similar -- `import` is a Python keyword). The `@app.command()` decorator specifies the CLI name explicitly (e.g., `name="import"`). The function signature, body, and all imports remain identical. Update the test class name and all CLI invocations in the test file.

Also update the two in-code references: `src/cli/__init__.py` module docstring and the `src/cli/status.py` error message that tells users to "run: bb creds refresh".

## Dependencies
- **Blocked by**: None
- **Blocks**: E-078-02 (needs `refresh` name slot cleared), E-078-03

## Files to Create or Modify
- `src/cli/creds.py` -- rename command function and decorator
- `tests/test_cli_creds.py` -- update all `["creds", "refresh", ...]` invocations to `["creds", "import", ...]`
- `src/cli/__init__.py` -- update module docstring
- `src/cli/status.py` -- update error message strings (lines 162 and 167)
- `tests/test_cli_status.py` -- update remediation hint assertions (lines 79 and 84)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The underlying `scripts/refresh_credentials.py` is NOT renamed in this story -- it stays as a legacy alias per the epic Non-Goals.
