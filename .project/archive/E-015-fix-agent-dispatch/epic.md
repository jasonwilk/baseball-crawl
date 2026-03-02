# E-015: Fix Agent Dispatch -- Nested Session Error

## Status
`COMPLETED`

## Overview
The project-manager's Dispatch Mode fails with "Claude Code cannot be launched inside another Claude Code session" when the PM itself is running as a subagent. This epic fixes the dispatch pattern so story execution actually works, and documents the correct approach so the failure cannot recur.

## Background & Context

### What Happened

During E-011 dispatch, the project-manager attempted to dispatch E-011-01 (to claude-architect) and E-011-02 (to general-dev) using the Task tool. Both failed immediately with:

```
Claude Code cannot be launched inside another Claude Code session.
Nested sessions share runtime resources and will crash all active sessions.
```

### Root Cause

The Claude Code platform sets `CLAUDECODE=1` in the environment for any active session. Any subprocess that tries to launch `claude` (including the Task tool, which spawns a new `claude` process) inherits this variable and is refused.

**The architectural constraint**: Subagents CANNOT spawn other subagents. The Task tool is only available to the **top-level Claude Code session** (the main session the user is talking to directly). When the PM runs as a subagent -- invoked by the orchestrator via the Task tool -- it cannot use the Task tool to dispatch further subagents. This is documented in the claude-architect memory at `/.claude/agent-memory/claude-architect/agent-design.md`: "Subagents CANNOT spawn other subagents (no nesting)."

### Why the Current Design Is Wrong

The PM's Dispatch Mode procedure says:

> "5. **Dispatch via Task tool.** For each eligible story, invoke the correct implementing agent with the standard context block."

But this step only works when the PM is running in the **top-level session**. When the orchestrator routes a "start epic X" request to the PM via the Task tool, the PM is a subagent, and step 5 fails.

The current orchestrator routing for "start epic X" is:

> Route to **project-manager** with a Task call.

This makes the PM a subagent, which breaks its own Dispatch Mode.

### Consultation Method

Expert consultation was conducted by reading the claude-architect's documented platform knowledge at `/.claude/agent-memory/claude-architect/` directly. Attempting to invoke claude-architect as a subagent to answer this question would have reproduced the exact bug being fixed. The relevant facts were already present in architect's memory.

### Correct Design

There are two valid patterns for PM dispatch:

**Pattern A: PM runs in the main session.** When the user invokes the PM directly (not through the orchestrator via Task), the PM is the top-level session and can use the Task tool freely. This is the correct model for Dispatch Mode.

**Pattern B: PM produces a dispatch manifest.** When the PM runs as a subagent (e.g., for epic creation, backlog review), it CANNOT dispatch. Instead, it produces a structured handoff listing which agents to call with what prompts. The user or top-level session executes those calls.

The fix requires:
1. **Orchestrator change**: "Start epic X" requests must NOT wrap PM in a Task call. The orchestrator must instead instruct the user to invoke the PM directly from the main session.
2. **PM Dispatch Mode update**: Add an explicit check -- if the PM detects it is running as a subagent (i.e., cannot dispatch), it must produce a dispatch manifest instead of attempting Task calls.
3. **Documentation**: The correct dispatch pattern must be documented in a rules file so agents and the user understand the constraint.

## Goals

- Fix the orchestrator's routing logic for "start epic" / "dispatch stories" requests so it does not wrap the PM in a subagent Task call
- Update the PM's Dispatch Mode procedure to handle both cases (main session: dispatch normally; subagent context: produce a manifest)
- Document the subagent nesting constraint and the correct dispatch pattern in a rules file
- Eliminate the "nested session" failure mode permanently

## Non-Goals

- This epic does NOT change the PM's Refinement Mode (creating epics, writing stories). That work is fine in a subagent context.
- This epic does NOT change story content, acceptance criteria formats, or numbering schemes.
- This epic does NOT implement Agent Teams for dispatch (that is a heavier pattern; simple fix first).
- This epic does NOT retroactively fix any stories left in `IN_PROGRESS` status from the failed E-011 dispatch.

## Success Criteria

1. The orchestrator agent definition (`/.claude/agents/orchestrator.md`) no longer routes "start epic X" / "dispatch stories" requests via a Task tool call to PM. Instead it instructs the user to invoke PM directly.
2. The PM agent definition (`/.claude/agents/project-manager.md`) Dispatch Mode procedure explicitly acknowledges the subagent nesting constraint and describes both operating modes (main session dispatch vs. manifest output).
3. A rules file at `/.claude/rules/dispatch-pattern.md` exists documenting the subagent nesting constraint and correct dispatch pattern.
4. When a user says "start epic E-011" to the orchestrator, the orchestrator responds with instructions to invoke PM directly rather than attempting a nested Task call.
5. When the PM is invoked directly (main session), Dispatch Mode works: it marks stories IN_PROGRESS, invokes implementing agents via Task tool, and marks stories DONE.

## Stories

| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-015-01 | Document the dispatch constraint in a rules file | DONE | None | claude-architect |
| E-015-02 | Fix orchestrator routing for dispatch requests | DONE | E-015-01 | claude-architect |
| E-015-03 | Update PM Dispatch Mode for subagent awareness | DONE | E-015-01 | claude-architect |

## Technical Notes

### The Nesting Constraint (Platform Fact)

`CLAUDECODE=1` is set in the environment of any active Claude Code session. The Task tool works by launching a new `claude` subprocess. That subprocess inherits the environment and immediately fails if `CLAUDECODE=1` is present. This is a platform-enforced safety mechanism -- not a configuration option.

Subagent depth limit: **1**. Main session -> subagent is allowed. Subagent -> sub-subagent is not.

### The Two PM Operating Modes

The PM must explicitly handle both contexts in its Dispatch Mode:

**Mode 1: Main session (PM invoked directly by user)**
- The Task tool is available
- Dispatch proceeds normally: mark stories IN_PROGRESS, invoke agents via Task, verify ACs, mark DONE
- This is the CORRECT context for Dispatch Mode

**Mode 2: Subagent context (PM invoked by orchestrator via Task)**
- The Task tool is NOT available for further delegation
- Dispatch Mode CANNOT proceed normally
- PM must recognize this situation and produce a **Dispatch Manifest** instead:
  - A markdown block listing each eligible story, the agent to invoke, and the full context block
  - The PM outputs this to the conversation so the user (or top-level session) can execute each Task call

### Orchestrator Change Required

Current (broken) routing:
```
"Start epic E-001" -> orchestrator routes to PM via Task tool -> PM tries to dispatch via Task -> FAILS
```

Correct routing:
```
"Start epic E-001" -> orchestrator instructs user: "Invoke PM directly from your main session for dispatch"
```

The orchestrator's routing table for dispatch requests must be updated. Instead of a Task call, the orchestrator responds with instructions to the user, including the exact PM invocation path or the dispatch manifest the PM would produce.

### Manifest Format

When PM is in a subagent context and cannot dispatch, it must output a Dispatch Manifest block like:

```markdown
## Dispatch Manifest for E-NNN

The PM is running in a subagent context and cannot dispatch directly.
Execute these Task tool calls from your main session:

### Task 1: E-NNN-01 -- [Story Title]
Agent: claude-architect
Prompt:
  [Full standard context block]

### Task 2: E-NNN-02 -- [Story Title]
Agent: general-dev
Prompt:
  [Full standard context block]
```

### Files Changed by This Epic

| File | Story | Action |
|------|-------|--------|
| `/.claude/rules/dispatch-pattern.md` | E-015-01 | CREATE |
| `/.claude/agents/orchestrator.md` | E-015-02 | MODIFY -- update routing for dispatch requests |
| `/.claude/agents/project-manager.md` | E-015-03 | MODIFY -- update Dispatch Mode section |

### Parallel Execution

E-015-01 can start immediately. E-015-02 and E-015-03 both depend on E-015-01 (the rules file defines the pattern they must implement) but can run in parallel with each other after E-015-01 is DONE.

## Open Questions

1. Should the PM's Dispatch Manifest also update story statuses to IN_PROGRESS before outputting? Or should status updates happen when the main session actually invokes the agents? **Recommendation**: PM sets statuses to IN_PROGRESS in the manifest output step (it has file access as a subagent). This way, the board is accurate before dispatch, and the implementing agents pick up a story that is already IN_PROGRESS.

2. Is there a `background: true` frontmatter option on agent definitions that changes dispatch behavior? **No.** The `background` field in agent frontmatter specifies whether a subagent runs in the background within a Task call -- it does not bypass the nesting constraint.

## History
- 2026-03-01: Created. Consultation conducted by reading claude-architect memory directly (invoking architect as subagent would have reproduced the bug). Root cause confirmed: CLAUDECODE=1 prevents nested subagent spawning. Three stories written with testable ACs. Epic set to READY.
