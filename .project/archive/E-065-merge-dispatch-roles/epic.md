# E-065: Merge Team Lead and PM Roles During Dispatch

## Status
`COMPLETED`

## Overview
Merge the team lead and PM roles during epic dispatch so the main session acts as both spawner and coordinator. This eliminates the idle-middleman pattern where the team lead sits idle for hours (observed: $31.68 for 70+ minutes during E-062) while PM coordinates via SendMessage, and removes the spawn-relay latency when PM needs new agents for later waves.

## Background & Context
The current dispatch architecture has three roles: team lead (spawner), PM (coordinator), and implementers. In practice, the team lead's only job after initial spawning is to spawn more agents when PM requests it -- otherwise it sits idle consuming budget. All coordination (story assignment, AC verification, status updates) goes through PM via SendMessage, adding relay latency without adding value.

This epic was reviewed and approved by claude-architect. CA confirmed:
- Architecturally sound, eliminates pure waste
- Removes an idle $30+ agent per dispatch
- Eliminates messaging latency for all coordination
- Reduces relay chain from 3 hops (user -> team lead -> PM -> implementer) to 2 (user/main session -> implementer)
- Matches the project's "simple first" principle
- Risks (context window pressure, single point of failure, role confusion) all have existing mitigations

No expert consultation required beyond the CA review already completed -- this is a pure process/workflow improvement affecting only context-layer files.

## Goals
- Eliminate the idle team lead agent during dispatch (saving $30+ per dispatch)
- Remove spawn-relay latency (main session spawns implementers directly)
- Reduce the coordination relay chain from 3 hops to 2
- Preserve PM's planning/discovery/refinement/triage/close roles unchanged
- Preserve all dispatch quality controls (READY gate, AC verification, status updates, closure sequence)

## Non-Goals
- Changing how PM handles planning, discovery, refinement, triage, or close modes
- Modifying the epic/story template structure
- Changing the agent selection routing table (which agent type handles which domain)
- Altering how implementing agents work (they still receive a story, satisfy ACs, report back)
- Modifying any non-context-layer files

## Success Criteria
- All 7 context-layer files consistently describe the merged model: the main session reads the epic, spawns implementers directly, assigns stories, verifies ACs, and runs the closure sequence
- No references to the old three-role dispatch model remain in any of the 7 files
- The implement skill provides a complete, self-contained dispatch workflow for the main session
- PM agent definition retains full planning/discovery/refinement capability but removes dispatch coordination responsibilities
- Workflow discipline rules reflect the simplified routing chain

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-065-01 | Rewrite Dispatch Pattern for Merged Roles | DONE | None | ca-01 |
| E-065-02 | Rewrite Implement Skill for Direct Coordination | DONE | E-065-01 | ca-02 |
| E-065-03 | Simplify PM Agent Definition -- Remove Dispatch Mode | DONE | E-065-01 | ca-03 |
| E-065-04 | Update CLAUDE.md, Workflow Discipline, and Multi-Agent Patterns | DONE | E-065-01 | ca-04 |

## Dispatch Team
- claude-architect

## Technical Notes

### The New Dispatch Model

**Before (3 roles):**
```
User -> Team lead (spawner, idle) -> PM (coordinator, messaging) -> Implementers
```

**After (2 roles):**
```
User/Main session (spawner + coordinator) -> Implementers
```

The main session during dispatch:
1. Reads the epic (status check, team composition, eligible stories)
2. Creates the team and spawns implementers directly (no PM teammate)
3. Marks stories IN_PROGRESS, assigns to implementers with full context blocks
4. Monitors completion, verifies ACs, sends back if unmet
5. Marks verified stories DONE, cascades to newly unblocked stories
6. Runs the full closure sequence (validate, update epic, docs assessment, archive, memory update, ideas review, summary, commit offer)

### What Stays the Same
- Epic/story status lifecycle (DRAFT -> READY -> ACTIVE -> COMPLETED)
- READY gate enforcement
- Agent selection routing table
- Context block format (full story file + full Technical Notes)
- Implementing agent responsibilities (satisfy ACs, report back, don't update statuses)
- Closure sequence steps (validate, update, docs assessment, archive, summary, commit offer)
- PM's five task types for non-dispatch work (discover, plan, clarify, triage, close)
- Direct-routing exceptions (api-scout, baseball-coach, claude-architect)

### What Changes
- Team lead no longer sits idle -- it IS the coordinator
- PM is not spawned as a teammate during dispatch
- No SendMessage relay for story assignment -- main session uses Agent tool directly
- Main session owns all status updates, AC verification, and cascade logic during dispatch
- Spawn requests are instant (main session has Agent tool, no relay needed)
- PM agent definition loses Dispatch Mode section but keeps all other modes
- Implement skill becomes the primary dispatch procedure (not a thin wrapper)

### Cross-Story Consistency Contract
Story E-065-01 defines the canonical new model in dispatch-pattern.md. Stories 02-04 must align with the model defined there. Key terms that must be consistent across all files:
- The main session role name and description
- The dispatch flow steps and numbering
- The closure sequence steps
- Context block format
- Agent selection routing table references

## Open Questions
None -- CA review resolved all architectural questions.

## History
- 2026-03-07: Created. CA consultation completed prior to epic creation. Epic set to READY.
- 2026-03-07: Codex spec review triage (3 P1, 2 P2). All 5 findings ACCEPTED and applied:
  - P1-1 (E-065-02 AC-10): Removed stale "do not modify epic files" anti-pattern requirement. Main session now owns epic file updates during dispatch.
  - P1-2 (E-065-03 AC-5): Rewrote AC-5 to clarify Pre-dispatch is revised for close-mode use only (dispatch steps removed, moved to implement skill).
  - P1-3 (E-065-04 AC-9): Expanded AC-9 and Context to include CLAUDE.md Workflows section (line ~176) which also contains old-model language.
  - P2-1 (E-065-01 AC-4): Added epic template to E-065-01 file list. Rewrote AC-4 to require removing "PM is always included automatically" from template comment.
  - P2-2 (E-065-03 AC-8): Expanded AC-8 to require updating YAML frontmatter description field (remove "dispatches implementation work").
- 2026-03-07: All 4 stories DONE. Epic COMPLETED. Rewrote dispatch model from 3 roles (team lead / PM / implementers) to 2 roles (main session / implementers). 7 context-layer files updated: dispatch-pattern.md (full rewrite), implement SKILL.md (full rewrite absorbing PM dispatch logic), product-manager.md (removed ~80 lines of Dispatch Mode), CLAUDE.md (Workflow Contract + Workflows section), workflow-discipline.md (routing rule + gates), multi-agent-patterns SKILL.md (routing diagram + checklist), epic-template.md (Dispatch Team comment). No documentation impact -- all changes are context-layer only.
