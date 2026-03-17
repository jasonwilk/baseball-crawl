# E-119: Fix PII Scanner Discoverability

## Status
`DRAFT`

## Overview
Agents and the main session cannot discover how to manually invoke the PII scanner. During E-116 dispatch, the main session tried `python scripts/pii_scan.py` which does not exist -- the scanner lives at `src/safety/pii_scanner.py`. The pre-commit hooks work correctly (they reference the right path), but there is no documented or discoverable way for agents to invoke the scanner outside of a commit. This epic adds context-layer documentation so agents know the correct invocation path.

## Background & Context
The PII scanner was built in E-006/E-019 and hardened in E-022. It is invoked by two hooks:
- **Git pre-commit hook** (`.githooks/pre-commit`): calls `src/safety/pii_scanner.py --stdin`
- **Claude Code PreToolUse hook** (`.claude/hooks/pii-check.sh`): calls `src/safety/pii_scanner.py --staged`

Both hooks work correctly. The bug is that nothing in the context layer tells agents where the scanner is or how to invoke it manually. When an agent wants to run a PII scan before committing (a reasonable safety check), it guesses `scripts/pii_scan.py` -- which doesn't exist.

The existing context-layer file `.claude/rules/pii-safety.md` mentions the scanner path but only fires for `src/safety/**` and `.githooks/**` paths -- it is not loaded during general agent work.

No expert consultation required -- this is a context-layer documentation bug with a clear fix.

## Goals
- Agents can discover the correct PII scanner invocation path without grepping the codebase
- The fix is minimal and context-layer only -- no new wrapper scripts or CLI commands

## Non-Goals
- Adding a `bb` subcommand for PII scanning (unnecessary -- hooks handle this automatically)
- Adding a `scripts/pii_scan.py` wrapper (unnecessary -- the scanner is directly invocable)
- Changing the scanner itself or the hooks
- Changing how pre-commit hooks work

## Success Criteria
1. An agent reading the context layer (CLAUDE.md or always-loaded rules) can find the PII scanner path and manual invocation syntax
2. No changes to `src/`, `scripts/`, `tests/`, or hook files

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-119-01 | Document PII scanner invocation in context layer | TODO | None | - |

## Dispatch Team
- claude-architect

## Technical Notes

### Scanner Invocation
The scanner supports three invocation modes (from the scanner's own docstring):
```
python3 src/safety/pii_scanner.py --staged       # scan git staged files
python3 src/safety/pii_scanner.py --stdin         # read file paths from stdin
python3 src/safety/pii_scanner.py file1 file2     # scan specific files
```

### Context-Layer Fix Options
Two viable approaches (CA to decide the best fit):

1. **Expand `pii-safety.md` paths** to fire on all files (`paths: "**"`) or a broader set, so agents always see the scanner path. Risk: the rule file is focused on "don't weaken the scanner" -- broadening its scope may dilute its purpose.

2. **Add scanner path to CLAUDE.md** in the Security Rules section or as a note in the Git Conventions section where `[pii-scan]` confirmation is already mentioned. This is the most discoverable location since CLAUDE.md is always loaded.

Either approach works. The key requirement is that the scanner path and invocation syntax are visible during normal agent work, not only when editing safety files.

## Open Questions
- None -- awaiting CA input on which approach they prefer.

## History
- 2026-03-17: Created. Bug discovered during E-116 dispatch when main session tried non-existent `scripts/pii_scan.py`.
