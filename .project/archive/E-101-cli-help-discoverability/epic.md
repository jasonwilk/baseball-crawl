# E-101: BB CLI Help and Discoverability

## Status
`COMPLETED`

## Overview
Make the `bb` CLI behave like a standard CLI tool: sub-groups show help when called bare, `--help` works at every depth, and the help format follows docker/git/kubectl conventions. This is a polish pass to improve operator discoverability, not a rewrite.

## Background & Context
The `bb` CLI (Typer-based, E-055) works well functionally but has three discoverability gaps:

1. **Unhelpful bare sub-groups.** `bb creds`, `bb data`, `bb proxy`, `bb db` show a "Missing command" error (exit 2) when called without a subcommand. The root `bb` already handles this gracefully (has `invoke_without_command=True` + callback), but none of the four sub-groups do.
2. **Non-standard format.** The help output lacks conventional elements like epilog footers ("Run `bb COMMAND --help` for help on a specific command") and usage examples on complex commands.

Root cause: the four sub-group `typer.Typer()` instances have `help=` strings but no `callback` and no `invoke_without_command=True`.

Note: Deep `--help` (e.g., `bb creds extract-key --help`) already works correctly in Typer 0.24.1 -- this was confirmed by SE assessment and is not a bug.

**UX Designer consultation (2026-03-13):** Recommendations incorporated below. Key decisions: bare groups show full `--help` output (matching docker/kubectl pattern), epilog footers on all groups, examples on complex commands only, no Rich markup in help strings.

## Goals
- Every `bb` sub-group shows help when called bare (no subcommand)
- `--help` works correctly at every level, including deep subcommands with options
- Help format follows standard CLI conventions (description, usage, commands/options list, epilog footer)
- Complex commands include usage examples in `--help` output

## Non-Goals
- Rewriting the CLI structure or adding new commands
- Adding color/Rich formatting to help text (Rich is for operational output, not help strings)
- Adding "did you mean...?" typo correction or fuzzy matching
- Adding shell completion (already disabled via `add_completion=False`)

## Success Criteria
- `bb creds`, `bb data`, `bb proxy`, `bb db` each display their subcommand listing when called bare
- `bb creds extract-key --help` shows the `--apply` option
- `bb proxy refresh-headers --help` shows the `--apply` option
- All help output includes a group-specific epilog footer (e.g., "Run 'bb creds COMMAND --help' for more information on a command.")
- All existing tests pass (no regressions)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-101-01 | Add bare-group help and epilog to all CLI sub-groups | DONE | None | se-101 |
| E-101-02 | Tighten docstrings and add examples to complex commands | DONE | E-101-01 | se-101 |

## Dispatch Team
- software-engineer

## Technical Notes

### UX Designer Recommendations (2026-03-13)

1. **Bare-group pattern**: Add `invoke_without_command=True` and a callback to each sub-group Typer. The callback calls `ctx.get_help()` when no subcommand is given, then raises `typer.Exit()`. Same pattern already used by the root app.

2. **Epilog footers**: Group-specific epilog text at each level. Root: `Run 'bb COMMAND --help' for more information on a command.` Sub-groups use their name: `Run 'bb creds COMMAND --help' for more information on a command.` (and analogously for `data`, `proxy`, `db`).

3. **Boolean flag verification**: Confirm `--apply` on `extract-key` and `refresh-headers` registers correctly with `--help`. If not, add explicit `is_flag=True` to the `typer.Option()` call.

4. **Docstring discipline**: Typer uses the first line of each command's docstring as the short description in group listings. Ensure every command has a crisp single-sentence first line.

5. **Examples on complex commands**: Add `Examples:` blocks to `check`, `extract-key`, `refresh-headers`, and `scout` command docstrings. These appear in `--help` output.

6. **No Rich in help text**: Rich markup in help strings renders as literal markup in some terminal environments. Keep all help text as plain strings.

### Files Overview

- `src/cli/__init__.py` -- root app (already has callback; needs epilog)
- `src/cli/creds.py` -- creds group (needs callback, invoke_without_command, epilog, docstring tightening, examples)
- `src/cli/data.py` -- data group (needs callback, invoke_without_command, epilog, docstring tightening, examples)
- `src/cli/proxy.py` -- proxy group (needs callback, invoke_without_command, epilog, docstring tightening)
- `src/cli/db.py` -- db group (needs callback, invoke_without_command, epilog, docstring tightening)
- `src/cli/status.py` -- standalone command (docstring tightening only)

### SE Technical Assessment (2026-03-13)

1. **Deep `--help` already works.** `bb creds extract-key --help` correctly shows `--apply` in Typer 0.24.1. No fix needed -- AC-7/AC-8 in story 01 are verification-only.
2. **Confirmed approach**: `invoke_without_command=True` + `@app.callback()` is the right pattern. ~4 lines per sub-module.
3. **Callback docstring wins**: When a callback is added, the callback's docstring takes precedence over `help=` on the `Typer()` constructor for the group description. Callback docstring must carry the description text.
4. **Current behavior is exit 2 + "Missing command" error**, not silent. The fix changes this to exit 0 + help text.
5. **Available formatting features** (no new deps): `rich_help_panel`, `epilog`, `short_help`, `suggest_commands` (already on by default). Rich markup mode is already `"rich"` by default.
6. **Testing**: Use `typer.testing.CliRunner` in-process. ~4 new test functions for bare-group behavior.

## Open Questions
- None

## History
- 2026-03-13: Created. UX Designer consulted before story writing.
- 2026-03-13: COMPLETED. Both stories implemented and reviewed. E-101-01 added bare-group help callbacks and epilog footers to all CLI sub-groups. E-101-02 tightened docstrings and added usage examples to complex commands. 322 CLI tests passing, 0 regressions. No documentation impact (polish pass on existing CLI, no new features/endpoints/schema). Context-layer assessment: (1) new convention — no, (2) architectural decision — no, (3) footgun/boundary — no, (4) agent behavior — no, (5) domain knowledge — no, (6) new CLI command/workflow — no. No context-layer codification needed.
