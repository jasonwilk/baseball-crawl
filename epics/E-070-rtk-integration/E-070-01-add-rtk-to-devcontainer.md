# E-070-01: Add rtk to devcontainer postCreateCommand

## Epic
[E-070: RTK Token Optimization Integration](./epic.md)

## Status
`TODO`

## Description
After this story is complete, every devcontainer rebuild will automatically install the rtk binary and configure the Claude Code PreToolUse hook for token-optimized Bash output. No manual setup required.

## Context
RTK is a CLI proxy that reduces LLM token consumption by rewriting common dev commands. The binary must be installed on every rebuild (it lives in `~/.local/bin/` which is ephemeral), and the hook configuration must be initialized (it lives in `~/.claude/` which is bind-mounted and persistent, but `rtk init` is idempotent so running it each time is safe and ensures the config stays current).

## Acceptance Criteria
- [ ] **AC-1**: Given a freshly built devcontainer, when the user runs `which rtk`, then the output shows a valid path (e.g., `/home/vscode/.local/bin/rtk`).
- [ ] **AC-2**: Given a freshly built devcontainer, when the user runs `rtk --version`, then it prints a version string without error.
- [ ] **AC-3**: Given a freshly built devcontainer, when the user inspects `~/.claude/settings.json` (global, user-level), then it contains a PreToolUse hook entry referencing `rtk-rewrite.sh`.
- [ ] **AC-4**: Given a freshly built devcontainer, when the user checks `~/.claude/hooks/rtk-rewrite.sh`, then the file exists and is executable.
- [ ] **AC-5**: Given a freshly built devcontainer, when the user inspects the project-level `.claude/settings.json`, then it is unchanged (PII scan and epic archive hooks intact, no rtk entries added).
- [ ] **AC-6**: Given the rtk install script or `rtk init` fails (e.g., network error, binary not found), when the postCreateCommand continues, then all subsequent steps in the chain still execute -- rtk failure does not cascade.
- [ ] **AC-7**: Given `rtk init -g --auto-patch` has already been run once, when it runs a second time, then no duplicate hook entries appear in `~/.claude/settings.json`.
- [ ] **AC-8**: The `postCreateCommand` string before the rtk append point is character-for-character identical to the current value in the repository. Verification: `pytest` passes with no regressions.

## Technical Approach
A single non-blocking subshell is appended at the tail of the existing `postCreateCommand` chain in `.devcontainer/devcontainer.json`, after the final `pip install -e .`. The subshell is separated by `;` (not `&&`) so that rtk failure cannot cascade to block the critical install chain. Inside the subshell, the install and init are chained with `&&` (init only runs if install succeeds), and the entire subshell has an `|| echo` fallback for graceful degradation.

The existing chain must remain completely intact -- this is a tail append only.

References:
- `/.claude/rules/devcontainer.md` -- devcontainer conventions (postCreateCommand is the correct path for CLI tools without devcontainer features)
- `/.devcontainer/devcontainer.json` -- current postCreateCommand chain

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.devcontainer/devcontainer.json` (modify -- append to postCreateCommand)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Existing pytest suite passes with no regressions (no new test files expected -- ACs are verified by manual container rebuild + code inspection)
- [ ] Code follows project style (see CLAUDE.md)

## Notes
- The rtk install script auto-detects OS and architecture. Confirmed working on linux aarch64.
- `rtk init -g --auto-patch` uses jq to merge into existing settings.json -- it does not overwrite.
- Full init (not `--hook-only`) is intentional: includes RTK.md and CLAUDE.md reference. The hook script gracefully degrades in other devcontainers (exits 0 if binary not found).
- No new test files for this story. ACs 1-5, 7 are verified by manual inspection after container rebuild. AC-6 is a structural property of the `;` separator + `|| echo` fallback, verifiable by reading the resulting postCreateCommand string. AC-8 is verified by diff inspection + pytest.
