# E-090: Auto-Rename tmux Window on Epic Dispatch

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Automatically rename the tmux window to the epic ID (e.g., "E-088") when the implement skill begins dispatch, if the session is running inside tmux. This eliminates a manual step the operator currently performs and makes it easy to identify which epic each tmux window is working on.

## Background & Context
During Heavy mode dispatch (tmux sessions on the Mac host), the operator manually runs `tmux rename-window "E-NNN"` to label the window. This is a small but consistent friction point -- easy to forget, and helpful for orientation when multiple dispatch sessions are running in parallel tmux windows.

The implement skill (`.claude/skills/implement/SKILL.md`) is the single entry point for all epic dispatch. The `TMUX` environment variable is set when a session is running inside tmux (e.g., `TMUX=/tmp/tmux-1000/default,17663,0`). The combination means: check for `$TMUX` at dispatch start, and if present, run `tmux rename-window "E-NNN"`.

**Expert consultation completed**: SE and CA both consulted per user directive (2026-03-10). Consensus: skill-level approach (not hook), direct Bash call (not script), completely silent failure, no CLAUDE.md documentation needed.

## Goals
- When the implement skill starts dispatch of an epic, the tmux window is automatically renamed to the epic ID if running in a tmux session
- No action taken when not in a tmux session (silent skip)
- Operator can still manually rename the window afterward if desired

## Non-Goals
- Restoring the original window name after dispatch completes (tmux windows are ephemeral in Heavy mode)
- Renaming windows for non-dispatch workflows (e.g., ad-hoc agent spawns, PM consultations)
- Supporting terminal multiplexers other than tmux (e.g., screen, zellij)
- Renaming panes within a window (only the window title)

## Success Criteria
- When `implement E-NNN` is invoked inside a tmux session, the tmux window title changes to "E-NNN" without operator intervention
- When `implement E-NNN` is invoked outside a tmux session, no error occurs and dispatch proceeds normally
- The rename happens early in the dispatch flow (before team creation / agent spawning)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-090-01 | Add tmux window rename to implement skill | DONE | None | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

### Approach (SE + CA consensus, 2026-03-10)

**Decided: Skill-level approach with direct Bash call.**

Add a new step to `.claude/skills/implement/SKILL.md` between Prerequisites and Phase 1 (Team Composition). The step instructs the main session to run a single guarded Bash command:

```
{ [ -n "$TMUX" ] && command -v tmux >/dev/null 2>&1 && tmux rename-window "E-NNN" 2>/dev/null; } || true
```

Substitute the actual epic ID parsed in Prerequisites for `E-NNN` (e.g., `"E-090"`). The `|| true` guarantees exit code 0 on all paths (the `&&` chain returns 1 when not in tmux, which is harmless but could confuse future readers).

Three guards (each maps to a distinct AC):
1. `[ -n "$TMUX" ]` -- skip when not in tmux (AC-2: guard short-circuits, no tmux invocation)
2. `command -v tmux >/dev/null 2>&1` -- skip when tmux binary not on PATH (AC-2: same short-circuit behavior)
3. `2>/dev/null` -- suppress stderr from the rename command itself (AC-3: runtime failures like stale socket or permission error)

**Why not a hook?** Hooks fire on tool events (PreToolUse/PostToolUse), not on skill activation. Wrong granularity -- would fire on every Bash call, not just dispatch start.

**Why not a standalone script?** One-liner command. A separate script adds indirection with no benefit.

**Failure handling:** Completely silent. The rename is QoL, not load-bearing. All existing hooks fail open; this follows the same pattern.

**Nested tmux:** `tmux rename-window` without `-t` targets the innermost session, which is the correct behavior.

**CLAUDE.md documentation:** Not needed (CA verdict). The rename is invisible infrastructure, not a setup step or operator action. The implement skill is self-documenting.

### Routing

The story modifies context-layer files only. Routes to claude-architect per routing precedence.

## Open Questions
None. All questions resolved via SE/CA consultation.

## History
- 2026-03-10: Created as DRAFT. Pending SE and CA consultation per user directive.
- 2026-03-10: SE + CA consultation completed. Consensus: skill-level approach, direct Bash call, silent failure, no CLAUDE.md docs needed. Story 02 (docs) removed -- CA confirmed the implement skill is self-documenting. Epic simplified to 1 story. Set to READY.
- 2026-03-10: Refinement pass by PM, CA, SE. Fixed "both stories" leftover, added `|| true` for clean exit codes, clarified epic ID substitution. CA noted Workflow Summary diagram in SKILL.md should also be updated (implementation detail).
- 2026-03-10: Codex spec review (gpt-5.4). Three findings applied: AC-2 reworded for observable behavior (guard short-circuits, no tmux invocation), AC-3 narrowed to runtime failures only (stale socket, permission error -- not binary-missing which is AC-2's guard), DoD simplified to AC verification + concrete smoke test.
- 2026-03-10: Dispatched. CA implemented E-090-01 (added Phase 0 tmux rename step to implement skill + updated Workflow Summary diagram). Context-layer-only story -- main session verified ACs directly. All 4 ACs passed. Documentation assessment: no triggers fired (no documentation impact). Context-layer assessment: (1) New convention: no. (2) Architectural decision: no. (3) Footgun/boundary: no. (4) Agent behavior change: yes -- Phase 0 added to implement skill, but codification IS the implementation (skill file modified directly). (5) Domain knowledge: no. (6) New CLI/workflow: no. Epic COMPLETED.
