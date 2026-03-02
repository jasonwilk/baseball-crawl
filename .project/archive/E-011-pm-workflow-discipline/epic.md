# E-011: PM Workflow Discipline and Status Update Standards

## Status
`ABANDONED`

**Reason**: Fully absorbed by E-016 (Evolve PM to Product Manager). E-011-01/03/04 were abandoned during E-016 planning (content folded into the rewritten PM agent definition). E-011-02 (audit script) was never built and is now abandoned as well -- the PM operates successfully without it. If board consistency auditing becomes a real need, it can be re-captured as a standalone idea.

## Overview
This epic establishes and enforces a complete status update discipline for the project-manager agent. A recurring failure mode was discovered during E-009: story and epic statuses were not updated at the end of PM actions, leaving the board in an inconsistent state and making it unreliable as a coordination mechanism. This epic ensures that gap cannot recur.

## Background & Context

### What Went Wrong in E-009

During E-009 (Tech Stack Redesign), several status updates were missed or delayed:

1. **Research spike files left stale**: E-009-R-01 through E-009-R-04 were completed, but the status fields in each file were not updated from `IN_PROGRESS` to `DONE` at the moment of completion. The epic's Stories table was updated, but the individual file statuses lagged.

2. **E-009-08 missing from Stories table**: Story E-009-08 was written and added as a file to the epic directory, but was not immediately added as a row to the Stories table in `epic.md`.

3. **E-002 and E-003 left in DRAFT**: After research clarified that these epics were viable, their statuses were not promoted to `ACTIVE` in the epic files even though Memory.md was updated to treat them as ACTIVE.

4. **Stories written without immediate epic update**: When E-009-02 through E-009-07 were written in a batch, the epic's Stories table was not updated immediately after each file was created.

### Why This Matters

The Stories table in `epic.md` is the canonical board view. If it does not match individual story file statuses, any agent reading the epic gets an inconsistent picture of the work state. This is not a minor hygiene issue -- it causes real coordination failures:
- An agent dispatched to execute a story may encounter a status mismatch that implies the story is already in progress
- A PM reviewing the board may miss unblocked work because blocked statuses were not cleared
- Memory.md may diverge from file-system truth, making memory unreliable

### What Already Exists

Status update rules are hinted at in multiple places but never consolidated into a single, enforceable standard:

- `/.claude/rules/project-management.md`: "Keep the story table in `epic.md` in sync with individual story file statuses" -- stated but no checklist provided
- `/.claude/rules/workflow-discipline.md`: Covers the READY gate and work authorization but says nothing about when status updates must happen
- `CLAUDE.md` Workflow Contract: Describes the flow but does not specify exactly what the PM must update at the end of each action
- `/.claude/agent-memory/project-manager/MEMORY.md`: The PM's own memory carries epic status notes, but these may drift from file-system reality

The gap is a missing **atomic status update protocol**: a specific, ordered checklist of what to update, when, every time an action completes.

### Prior Art

E-007 (Orchestrator Workflow Discipline) established the READY gate and work authorization gate as rules. E-009 then demonstrated that even with those rules in place, PM can produce inconsistent state between file-level statuses and epic-level summaries. E-011 is the natural continuation: tighten the atomic action protocol, put the checklist somewhere enforced, and add a verification mechanism.

No expert consultation required -- this epic is entirely within the PM/workflow domain. All design decisions were made by the PM directly in E-011-R-01, drawing on established project conventions (E-006, E-007, rules file patterns). No agent infrastructure changes, no schema changes, no code architecture questions.

## Goals

- Define the **atomic status update protocol**: a specific ordered checklist the PM executes at the end of every action (create story, complete story, write spike, dispatch work, etc.)
- Consolidate PM workflow rules into a single authoritative location so there is no ambiguity about where "the rule" lives
- Implement a **verification script** that audits epic board consistency: catches mismatches between Stories table entries and individual story file statuses
- Add a pre-dispatch check to the PM's Dispatch Mode procedure that runs the verification script before dispatching any stories
- Eliminate the current scatter of partial rules across `project-management.md`, `workflow-discipline.md`, and MEMORY.md by pointing all fragments at the canonical document

## Non-Goals

- This epic does NOT address workflow issues for implementing agents (general-dev, data-engineer) -- those are covered by E-007's work authorization gate
- This epic does NOT change the epic lifecycle (`DRAFT -> READY -> ACTIVE -> COMPLETED`) -- that remains as defined
- This epic does NOT create automated story status updates via hooks or background processes -- the goal is discipline, not automation that could silently fail
- This epic does NOT audit past epics retroactively -- fixing historical inconsistencies is out of scope; we start clean from the point E-011 is completed

## Success Criteria

1. A single canonical PM workflow standards document exists at `/.claude/rules/pm-workflow-standards.md`, containing the complete atomic status update protocol
2. The existing partial rules in `project-management.md` and `workflow-discipline.md` are updated to reference the canonical document rather than restating rules inconsistently
3. A verification script exists at `scripts/audit_epic_board.py` that reads all story files and the Stories tables in epic files and reports any status mismatches, missing rows, or orphaned files
4. The PM's Dispatch Mode procedure (in the agent definition at `.claude/agents/project-manager.md`) explicitly includes a board audit step before dispatching stories
5. The PM Memory file is updated to record the canonical document location and the atomic protocol summary
6. When the verification script is run against the current project state, it produces a report that is accurate (not necessarily clean -- the point is to surface real inconsistencies, not to manufacture a pass)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-011-R-01 | PM workflow standards design decisions | DONE | None | PM |
| E-011-01 | PM Workflow Standards document | ABANDONED | E-011-R-01 | claude-architect |
| E-011-02 | Epic board consistency audit script | ABANDONED | E-011-R-01 | general-dev |
| E-011-03 | Update PM agent definition with audit step | ABANDONED | E-011-01 | claude-architect |
| E-011-04 | Update project-management.md and workflow-discipline.md rules | ABANDONED | E-011-01 | claude-architect |

## Technical Notes

### Design Decisions (from E-011-R-01)

All four architectural questions posed in the original epic draft were resolved in E-011-R-01 by the PM directly (pure workflow/process domain, no external consultation needed).

**Canonical document location**: `/.claude/rules/pm-workflow-standards.md` -- a new rules file with `paths: ["**"]` frontmatter so it auto-loads in all agent contexts. Follows the precedent of `workflow-discipline.md` (created in E-007).

**Atomic status update protocol**: Adopted as proposed. Four action types each have a numbered checklist:
- Creating a new story file (4 steps)
- Completing a story (5 steps, includes running audit script)
- Completing a research spike (4 steps)
- Dispatch Mode pre-dispatch (6 steps, includes running audit script as step 3)

**Audit script scope**: `scripts/audit_epic_board.py` -- stdlib-only Python. Detects mismatches, orphaned files, dangling rows, and epics where all stories are DONE but epic is not COMPLETED. The `scripts/` directory does not yet exist; E-011-02 creates it. Exit code 0 if clean, 1 if issues found.

**Enforcement mechanism**: Manual with mandatory inclusion in PM agent definition Dispatch Mode (step 3). Not a pre-commit hook (too noisy, conflicts with E-006's hook) and not a Claude Code hook (unnecessary complexity). Two enforcement points: before dispatch (Dispatch Mode step 3) and after completing a story (completing-a-story protocol step 4).

### Files Changed by This Epic

| File | Story | Action |
|------|-------|--------|
| `/.claude/rules/pm-workflow-standards.md` | E-011-01 | CREATE -- canonical PM workflow standards document |
| `scripts/audit_epic_board.py` | E-011-02 | CREATE -- board consistency audit script |
| `scripts/` (directory) | E-011-02 | CREATE if not exists |
| `/.claude/agents/project-manager.md` | E-011-03 | MODIFY -- add audit step to Dispatch Mode |
| `/.claude/rules/project-management.md` | E-011-04 | MODIFY -- add reference to canonical document |
| `/.claude/rules/workflow-discipline.md` | E-011-04 | MODIFY -- append reference section |

### Parallel Execution

E-011-01 and E-011-02 can run in parallel (different files, no shared state). E-011-03 and E-011-04 both depend on E-011-01 (they reference the canonical document) but can run in parallel with each other after E-011-01 is DONE.

## Open Questions

1. Should the audit script also check MEMORY.md consistency (e.g., that epic statuses in memory match file-system statuses)? This would be useful but significantly increases script complexity. Deferred -- potential follow-on epic after E-011 delivers the baseline.

## History
- 2026-02-28: Created -- DRAFT. Consultation with claude-architect required before stories can be written with testable ACs. Unblock condition: E-011-R-01 (architect consultation) completed and written artifact delivered.
- 2026-03-01: Refinement complete. E-011-R-01 executed by PM directly (pure PM/workflow domain, no external consultation needed). All four design questions resolved. Story files E-011-01 through E-011-04 written with testable ACs. Epic promoted to READY.
- 2026-03-01: ABANDONED. E-016 fully absorbed this epic's concerns. E-011-01/03/04 were already ABANDONED during E-016 planning. E-011-02 (audit script) was never built and is now abandoned -- the PM has been operating successfully without it through multiple epic dispatches. Archived to /.project/archive/.
