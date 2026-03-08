# E-070: RTK Token Optimization Integration

## Status
`COMPLETED`

## Overview
Integrate [rtk](https://github.com/rtk-ai/rtk) into the devcontainer so all Claude Code sessions automatically benefit from 60-90% token reduction on common dev commands (git, docker, pip, etc.). RTK is a CLI proxy that rewrites Bash tool calls via a PreToolUse hook, returning compact output instead of verbose defaults.

## Background & Context
RTK ("Rust Token Killer") is a single Rust binary (<10ms overhead) that intercepts Bash commands and returns token-optimized output. It installs to `~/.local/bin/rtk` and configures itself via `rtk init -g --auto-patch`, which creates hook scripts and settings in `~/.claude/`.

SE research confirmed:
- The binary installs cleanly on linux aarch64 (our devcontainer arch).
- `rtk init -g --auto-patch` writes to the GLOBAL `~/.claude/settings.json` (user-level), not project-level. It uses jq to merge, preserving existing content. No conflict with project-level hooks (PII check, epic archive check).
- Because `~/.claude/` is bind-mounted from the host (`devcontainer.json` mounts section), the hook artifacts persist across rebuilds. Only the binary needs reinstallation.
- The binary (`~/.local/bin/rtk`) is NOT in the mounted directory and is lost on rebuild, so it must be installed via `postCreateCommand`.
- `rtk init -g --auto-patch` is idempotent -- safe to run on every rebuild.
- No custom config needed; defaults are fine.

Expert consultation: SE, claude-architect, and claude-code-guide consulted during spec review triage (2026-03-08). SE and CA both confirmed no spec changes needed beyond prior refinements. The guide raised a concern about PreToolUse hook interaction with PII check hooks, but this was dismissed -- PII check is a PreCommit hook (inspects staged files before git commit), while rtk is a PreToolUse hook (intercepts Bash commands). Different hook types, different triggers, no interaction surface. SE consultation was also completed by the user prior to epic formation.

## Goals
- Every new devcontainer session has rtk active with zero manual setup
- Token savings apply automatically to all Bash tool calls in Claude Code sessions
- Integration persists across devcontainer rebuilds

## Non-Goals
- Custom rtk configuration (defaults are sufficient)
- Measuring or reporting token savings (rtk has built-in `rtk gain` for ad-hoc checks)
- Modifying project-level `.claude/settings.json` (rtk uses global/user-level settings)

## Success Criteria
- After a devcontainer rebuild, `which rtk` returns a valid path
- After a devcontainer rebuild, `rtk --version` succeeds
- The global `~/.claude/settings.json` contains an rtk PreToolUse hook entry
- `~/.claude/hooks/rtk-rewrite.sh` exists and is executable
- Running `rtk git status` in the devcontainer produces compact output
- rtk install/init failure does not cascade to break the rest of the postCreateCommand chain
- Project-level `.claude/settings.json` is untouched (PII/archive hooks intact)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-070-01 | Add rtk to devcontainer postCreateCommand | DONE | None | SE |

## Dispatch Team
- software-engineer

## Technical Notes

### Integration approach
The only file modified is `.devcontainer/devcontainer.json`. A single non-blocking subshell is appended at the tail of `postCreateCommand` (after `pip install -e .`), separated by `;` (not `&&`):

```bash
; (curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh && rtk init -g --auto-patch) || echo "rtk install failed -- skipping"
```

**Design decisions:**
1. **Non-blocking**: Uses `;` to separate from the critical pip chain, wrapped in a subshell with `|| echo` fallback. A GitHub outage will not break container setup.
2. **Full init** (not `--hook-only`): Includes RTK.md and CLAUDE.md reference. The hook gracefully degrades in other devcontainers (exits 0 if binary not found).
3. **Placed at tail**: After all critical installs (Claude Code, pip, project setup). rtk is a nice-to-have, not a blocker.
4. **Idempotent**: `rtk init -g --auto-patch` appends to existing settings without overwriting. Running twice produces no duplicate hook entries.

### Runtime artifacts (produced by `rtk init`, not version-controlled)
These files are created/updated at container build time by `rtk init -g --auto-patch`. They live in the user's home `~/.claude/` directory (bind-mounted from host), NOT in the project's `.claude/` directory. No version-controlled files are modified except `.devcontainer/devcontainer.json`.

- `~/.local/bin/rtk` -- binary (ephemeral, reinstalled each rebuild)
- `~/.claude/hooks/rtk-rewrite.sh` -- PreToolUse hook script (persisted via bind mount)
- `~/.claude/RTK.md` -- rtk instructions for Claude Code (persisted via bind mount)
- `~/.claude/CLAUDE.md` -- gets an `@RTK.md` reference line (persisted via bind mount)
- `~/.claude/settings.json` -- global user-level settings with hook entry (persisted via bind mount)

### Devcontainer rules
Per `/.claude/rules/devcontainer.md`: use `postCreateCommand` for CLI tool installs that lack devcontainer features. rtk has no devcontainer feature, so `postCreateCommand` is the correct path.

## Open Questions
None.

## History
- 2026-03-07: Created. SE consultation completed by user (research findings provided directly).
- 2026-03-07: Updated with finalized SE approach -- non-blocking subshell pattern, full init, tail placement.
- 2026-03-07: Codex spec review triage -- refined 4 findings (AC-6 scope, AC-8 testability, DoD clarity, artifact location language), dismissed 2 (agent routing, consultation).
- 2026-03-08: Second codex spec review triage (5 findings). REFINED 2: AC-8 verification split into visual diff + pytest (P1), DoD-3 tightened from subjective style check to valid-JSON + formatting conventions (P3). DISMISSED 3: AC-6 cascade concern (P1, already addressed -- structural property of `;` + `|| echo`), AC-3/AC-4 runtime behavior (P2, epic-level validation not story-level AC), consultation gap (P2, no project `.claude/` files modified).
- 2026-03-08: Expert consultation review (SE, CA, claude-code-guide). SE and CA confirmed all 5 prior triage decisions. Guide raised new concern about PreToolUse/PreCommit hook interaction -- dismissed because rtk (PreToolUse) and PII check (PreCommit) are different hook types with no shared execution path. No spec changes from consultation. All prior refinements stand.
- 2026-03-08: Dispatched and completed. E-070-01 implemented by SE, approved by code-reviewer with no findings. Documentation assessment: no impact. Context-layer assessment: all 6 triggers No -- no codification needed. Epic COMPLETED.
