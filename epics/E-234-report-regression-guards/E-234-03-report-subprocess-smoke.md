# E-234-03: `bb report` subprocess smoke tests

## Epic
[E-234: Report Regression Guards](epic.md)

## Status
`TODO`

## Description
After this story is complete, the suite contains credential-free subprocess smoke tests for `bb report generate` that catch packaging and import-time breaks the in-process CliRunner masks. These run `bb report generate` as the real installed console script without any network call.

## Context
`generate_report()` hits the network immediately, so a smoke test must not trigger real generation. The testing rule mandates subprocess smoke coverage for console entry points; `bb report` has none today. The existing pattern lives in `tests/test_cli.py` (the `_bb_installed` skipif block, ~lines 256-320) covering `bb`/`status`/`creds`/`db`/`data`. See Technical Notes §TN-3 for the two-layer approach.

## Acceptance Criteria
- [ ] **AC-1**: A subprocess test runs `bb report generate --help`, asserts exit code 0, and asserts the output contains a stable substring (e.g., `gc_url` or `Generate`), per Technical Notes §TN-3. It follows the existing `_bb_installed` skipif convention in `tests/test_cli.py`.
- [ ] **AC-2**: A subprocess test runs `bb report generate` with a deliberately invalid URL argument (e.g., `not-a-valid-url-@@@`), asserts a non-zero exit code, and asserts the error output is present — verifying the parse-time failure path is wired through the real entry point before any network call, per Technical Notes §TN-3.
- [ ] **AC-3**: No mocks are injected into the subprocess and no credentials or network access are required for either test to pass.
- [ ] **AC-4**: No `src/` change — additive test functions only.

## Technical Approach
Add two test functions to the existing subprocess block in `tests/test_cli.py`, mirroring the established `subprocess.run([...], capture_output=True, text=True)` + `_bb_installed` skipif pattern. The invalid-URL case relies on `parse_team_url()` raising `ValueError` before any HTTP call (`generator.py:1000-1003`). See Technical Notes §TN-3.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `tests/test_cli.py` (modify — add `bb report` subprocess smoke functions)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Smallest of the guard stories; high value as the packaging/import canary for the reports CLI.
