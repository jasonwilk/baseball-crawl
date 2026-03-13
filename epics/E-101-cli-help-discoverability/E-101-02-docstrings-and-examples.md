# E-101-02: Tighten Docstrings and Add Examples to Complex Commands

## Epic
[E-101: BB CLI Help and Discoverability](epic.md)

## Status
`TODO`

## Description
After this story is complete, every CLI command will have a crisp single-sentence first line in its docstring (used by Typer as the short description in group listings), and the most complex commands will include usage examples visible in `--help` output. The help output will feel polished and standard.

## Context
Typer uses the first line of each command's docstring as the short description in group/subcommand listings. Some current docstrings have multi-sentence first lines or descriptions that are too long for a listing context. Additionally, complex commands with non-obvious flags benefit from inline examples. This story depends on E-101-01 because the bare-group help must be working before the listing descriptions can be validated visually.

## Acceptance Criteria
- [ ] **AC-1**: Every command function in `creds.py`, `data.py`, `proxy.py`, `db.py`, and `status.py` has a single-sentence first line in its docstring (no period-delimited multi-sentence first lines).
- [ ] **AC-2**: The following commands include an `Examples:` block in their docstring body (visible in `--help` output): `bb creds check`, `bb creds extract-key`, `bb proxy refresh-headers`, `bb data scout`.
- [ ] **AC-3**: Each example block contains at least two example invocations with inline comments explaining what each does.
- [ ] **AC-4**: No help text contains Rich markup (no `[bold]`, `[green]`, etc. in docstrings or `help=` parameters).
- [ ] **AC-5**: All existing tests pass (`pytest` exits 0 with no new failures).

## Technical Approach
Review each command function's docstring across all five CLI modules. Restructure docstrings to follow the pattern: single-sentence first line (becomes the listing description), blank line, optional longer description, optional `Examples:` block. The examples block uses standard indented format that Typer/Click renders cleanly in `--help` output.

For the `status` command (registered via `app.command(name="status")(status.run)`), ensure the `run()` function's docstring works as the short description in the root listing.

See epic Technical Notes for the UX designer's recommended docstring patterns and which commands need examples.

## Dependencies
- **Blocked by**: E-101-01
- **Blocks**: None

## Files to Create or Modify
- `src/cli/creds.py`
- `src/cli/data.py`
- `src/cli/proxy.py`
- `src/cli/db.py`
- `src/cli/status.py`
- `tests/test_cli.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- Do not add Rich markup to any docstring or `help=` parameter. Rich is for operational output only.
- The `review` command in `proxy.py` uses `context_settings` for extra args -- its docstring already includes usage examples in its current form; tighten but preserve the existing examples.
