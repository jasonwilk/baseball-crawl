# E-119: Fix PII Scanner Discoverability

## Status
`COMPLETED`

## Overview
Agents and the main session cannot discover how to manually invoke the PII scanner. During E-116 dispatch, the main session tried `python scripts/pii_scan.py` which does not exist -- the scanner lives at `src/safety/pii_scanner.py`. The pre-commit hooks work correctly (they reference the right path), but there is no documented or discoverable way for agents to invoke the scanner outside of a commit. This epic adds the scanner path and invocation syntax to CLAUDE.md so agents know the correct invocation path.

## Background & Context
The PII scanner was built in E-006/E-019 and hardened in E-022. It is invoked by two hooks:
- **Git pre-commit hook** (`.githooks/pre-commit`): calls `src/safety/pii_scanner.py --stdin`
- **Claude Code PreToolUse hook** (`.claude/hooks/pii-check.sh`): calls `src/safety/pii_scanner.py --staged`

Both hooks work correctly. The bug is that nothing in the always-loaded context layer tells agents where the scanner is or how to invoke it manually. When an agent wants to run a PII scan before committing (a reasonable safety check), it guesses `scripts/pii_scan.py` -- which doesn't exist.

The existing context-layer file `.claude/rules/pii-safety.md` mentions the scanner path but only fires for `src/safety/**`, `.githooks/**`, and `.claude/hooks/pii-check.sh` paths -- it is not loaded during general agent work.

**Expert consultation**: CA recommended CLAUDE.md placement (Security Rules section) as the correct fix. CLAUDE.md is always loaded for all agents, making it the most discoverable location. Broadening `pii-safety.md` paths was rejected because that rule file's purpose is "don't weaken the scanner" -- broadening its scope would dilute its intent without solving the discoverability problem as cleanly.

## Goals
- Agents can discover the correct PII scanner invocation path without grepping the codebase
- The fix is minimal and context-layer only -- no new wrapper scripts or CLI commands

## Non-Goals
- Adding a `bb` subcommand for PII scanning (unnecessary -- hooks handle this automatically)
- Adding a `scripts/pii_scan.py` wrapper (unnecessary -- the scanner is directly invocable)
- Changing the scanner itself or the hooks
- Changing how pre-commit hooks work

## Success Criteria
1. An agent reading CLAUDE.md can find the PII scanner path and manual invocation syntax
2. No changes to `src/`, `scripts/`, `tests/`, or hook files

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-119-01 | Document PII scanner invocation in CLAUDE.md | DONE | None | claude-architect |

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

### Placement Decision
CA recommended adding the scanner path to the **Security Rules** section of `CLAUDE.md`, near the existing bullet about never logging credentials. This is the most discoverable location because CLAUDE.md is always loaded for all agents. The `pii-safety.md` broadening option was rejected -- that file's purpose is guarding scanner integrity, not advertising the scanner's location.

The addition should be a single bullet point with the scanner path and the `--staged` invocation example, keeping CLAUDE.md concise.

## Open Questions
None.

## History
- 2026-03-17: Created. Bug discovered during E-116 dispatch when main session tried non-existent `scripts/pii_scan.py`.
- 2026-03-17: Incorporated CA recommendation (CLAUDE.md placement) and Codex spec review findings (5 items). Set to READY.
- 2026-03-17: All stories DONE. AC verification passed (all 3 ACs confirmed). Epic COMPLETED.
