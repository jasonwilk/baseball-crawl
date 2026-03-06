# E-056: Fix Dispatch Pattern -- Team Lead as Spawner

## Status
`COMPLETED`

## Overview
The dispatch pattern is architecturally broken. It instructs PM to spawn implementing agents via `TeamCreate` and the `Agent` tool, but PM runs as a teammate and **teammates cannot spawn other teammates** -- only the team lead can manage team membership. This epic restructures the dispatch pattern so the team lead spawns all agents and PM coordinates via messaging.

## Background & Context
During E-051 dispatch (2026-03-06), PM was spawned as a teammate and attempted to spawn a software-engineer. This is impossible due to a hard Agent Teams constraint: "No nested teams: teammates cannot spawn their own teams or teammates. Only the lead can manage the team." Instead of reporting the failure, PM implemented the fix itself -- violating the dispatch pattern.

A partial fix was applied after E-051: PM was made read-only (Write/Edit/Bash tools removed) to prevent self-implementation. However, the dispatch pattern documents still describe PM as the agent that creates teams and spawns implementers, which remains impossible. The read-only fix addressed a symptom; this epic fixes the root cause.

**The architectural constraint**: In Claude Code Agent Teams, only the team lead (the agent that created the team via `TeamCreate`) can spawn new teammates via the `Agent` tool. Teammates communicate with each other via `SendMessage` but cannot add new members.

No expert consultation required -- this is pure process/workflow fixing a documented architectural constraint. All files are context-layer, routed to claude-architect.

## Goals
- Dispatch pattern documents accurately reflect Agent Teams architecture (team lead spawns, PM coordinates)
- PM agent definition removes all references to spawning agents or creating teams
- Implement and review-epic skills correctly describe the team lead's expanded spawning role
- CLAUDE.md and workflow-discipline.md align with the new pattern
- Guardrails ensure PM reports failure instead of self-implementing when delegation is impossible

## Non-Goals
- Changing the PM's read-only enforcement (already correct from the E-051 fix)
- Redesigning the epic/story lifecycle or status update protocol
- Adding new agent types or changing the agent ecosystem
- Modifying any non-context-layer files

## Success Criteria
- All five context-layer files describe a consistent dispatch pattern where the team lead spawns agents and PM coordinates via messaging
- No file references PM using `TeamCreate` or the `Agent` tool to spawn teammates
- The implement skill's Phase 2 has the team lead spawning PM + implementers (not just PM)
- The review-epic skill's Phase 2 has the team lead spawning PM + implementers
- PM agent definition's Dispatch Procedure describes coordination via messaging, not spawning

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-056-01 | Rewrite dispatch-pattern.md for team-lead-as-spawner | DONE | None | claude-architect |
| E-056-02 | Update PM agent definition dispatch procedure | DONE | E-056-01 | claude-architect |
| E-056-03 | Update implement skill for team lead spawning | DONE | E-056-01 | claude-architect |
| E-056-04 | Update review-epic skill for team lead spawning | DONE | E-056-01 | claude-architect |
| E-056-05 | Align CLAUDE.md and workflow-discipline.md | DONE | E-056-01 | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

### The New Dispatch Model

**Before (broken):**
```
User -> Team lead creates team, spawns PM -> PM spawns implementers -> PM coordinates
```

**After (correct):**
```
User -> Team lead creates team, spawns PM + all implementers -> PM coordinates via SendMessage
```

Key changes:
1. **Team lead is the spawner.** The team lead reads the epic's Dispatch Team section, creates the team, and spawns PM + all listed implementers. For the implement skill, the team lead already reads the epic -- it just needs to spawn more agents.
2. **PM coordinates via messaging.** PM uses `SendMessage` to assign stories to implementers, request status updates, and verify acceptance criteria. PM never uses `TeamCreate` or `Agent`.
3. **Team lead handles cascading spawns.** If PM identifies newly unblocked stories that need an agent type not already on the team, PM messages the team lead to spawn the additional agent. The team lead is not "stepping back" entirely -- it remains available for spawn requests.
4. **PM remains the coordinator.** PM still decides what to build, verifies ACs, determines status changes, and instructs teammates to apply file edits. The only change is WHO spawns agents (team lead, not PM).

### Status Update Pattern (Unchanged)
PM is read-only. Status updates work the same as before: PM determines the change, instructs an implementer to apply it, verifies by reading. The "status-update teammate" concept is simplified -- any implementer on the team can apply status edits when PM instructs them.

### Agent Teams API Reference
- `TeamCreate`: Creates a new team. Only the agent calling this becomes the team lead.
- `Agent` tool with `team_name`: Spawns a new teammate. Only the team lead can call this.
- `SendMessage`: Any teammate can message any other teammate. This is how PM coordinates.

### Files to Modify (All Context-Layer)
| File | Story |
|------|-------|
| `/.claude/rules/dispatch-pattern.md` | E-056-01 |
| `/.claude/agents/product-manager.md` | E-056-02 |
| `/.claude/skills/implement/SKILL.md` | E-056-03 |
| `/.claude/skills/review-epic/SKILL.md` | E-056-04 |
| `/CLAUDE.md` | E-056-05 |
| `/.claude/rules/workflow-discipline.md` | E-056-05 |

### Consistency Rules
All five stories must use consistent language for the new pattern. Key terminology:
- "Team lead spawns" (not "PM spawns" or "PM creates a team")
- "PM coordinates via messaging" (not "PM dispatches agents")
- "PM requests spawn" when PM needs a new agent mid-dispatch (team lead fulfills)
- The team lead "remains available for spawn requests" (not "steps back")

## Open Questions
None -- the constraint is documented and the fix is straightforward.

## History
- 2026-03-06: Created. Critical fix for broken dispatch pattern discovered during E-051 execution.
- 2026-03-06: COMPLETED. All 5 stories done. Rewrote dispatch-pattern.md, PM agent def, implement skill, review-epic skill, CLAUDE.md, and workflow-discipline.md to reflect team-lead-as-spawner model. No documentation impact (all changes are context-layer files, not user-facing docs).
