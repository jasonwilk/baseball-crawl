# E-101-01: Add Bare-Group Help and Epilog to All CLI Sub-Groups

## Epic
[E-101: BB CLI Help and Discoverability](epic.md)

## Status
`TODO`

## Description
After this story is complete, every `bb` sub-group (`creds`, `data`, `proxy`, `db`) will display its subcommand listing when called bare (no subcommand), matching the pattern already used by the root `bb` app. All Typer instances (root + four groups) will include an epilog footer directing operators to `--help` for more detail.

## Context
The root `bb` app already uses `invoke_without_command=True` plus a callback that calls `ctx.get_help()`. The four sub-groups lack this pattern, producing an exit 2 "Missing command" error instead of showing help. This is the core fix for the primary pain point.

## Acceptance Criteria
- [ ] **AC-1**: `bb creds` (no subcommand) prints the creds group help text (subcommand listing) and exits 0.
- [ ] **AC-2**: `bb data` (no subcommand) prints the data group help text and exits 0.
- [ ] **AC-3**: `bb proxy` (no subcommand) prints the proxy group help text and exits 0.
- [ ] **AC-4**: `bb db` (no subcommand) prints the db group help text and exits 0.
- [ ] **AC-5**: `bb --help` output includes the epilog: `Run 'bb COMMAND --help' for more information on a command.`
- [ ] **AC-6**: Each sub-group's `--help` output includes a group-specific epilog: `Run 'bb creds COMMAND --help' for more information on a command.` (and analogously for `data`, `proxy`, `db`).
- [ ] **AC-7**: Each sub-group callback's docstring matches the current `help=` string on its `Typer()` constructor, so the group description text is preserved after adding the callback.
- [ ] **AC-8**: `bb creds extract-key --help` shows the `--apply` option (verification -- already works in Typer 0.24.1, confirm no regression).
- [ ] **AC-9**: `bb proxy refresh-headers --help` shows the `--apply` option (verification -- already works, confirm no regression).
- [ ] **AC-10**: All existing tests pass (`pytest` exits 0 with no new failures).

## Technical Approach
Each of the four sub-group modules (`creds.py`, `data.py`, `proxy.py`, `db.py`) needs the same structural change: add `invoke_without_command=True` to the `typer.Typer()` constructor, add a callback function that prints help when no subcommand is given, and add an `epilog` parameter. The root `__init__.py` needs only the `epilog` addition.

AC-8/AC-9 are verification-only: deep `--help` already works in Typer 0.24.1. Confirm no regression after adding callbacks.

See epic Technical Notes for the UX designer's recommended patterns.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-101-02

## Files to Create or Modify
- `src/cli/__init__.py`
- `src/cli/creds.py`
- `src/cli/data.py`
- `src/cli/proxy.py`
- `src/cli/db.py`
- `tests/test_cli.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `proxy.py` `review` command uses `context_settings={"allow_extra_args": True}` -- verify the callback does not interfere with this.
- The callback pattern is: check `ctx.invoked_subcommand is None`, print help, raise `typer.Exit()`.
- **SE assessment (2026-03-13)**: Deep `--help` already works in Typer 0.24.1 -- `bb creds extract-key --help` correctly shows `--apply`. AC-7/AC-8 are verification-only (confirm they work, no fix expected).
- **SE assessment (2026-03-13)**: Callback docstring takes precedence over `help=` kwarg on `Typer()` for the group description. When adding a callback, the docstring must carry the description text.
- **SE assessment (2026-03-13)**: Current bare-group behavior is exit code 2 with "Missing command" error, not silent. The fix changes this to exit 0 with help text.
