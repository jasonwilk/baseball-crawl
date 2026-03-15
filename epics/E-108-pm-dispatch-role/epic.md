# E-108: PM as Dispatch Teammate

## Status
`DRAFT`

## Overview
Add the product-manager as a spawned teammate during epic dispatch. Currently, the main session manages all story statuses, epic table updates, and AC verification directly. This concentrates too many responsibilities in the main session and violates the PM's ownership of epics. The fix: PM is spawned as a teammate during dispatch and owns status management + AC verification, while the main session retains spawning, routing, merge-back, and cascade decisions.

## Background & Context
The dispatch pattern was simplified in E-065 (Merge Team Lead and PM Roles) to eliminate the idle team lead problem. That fix went too far: it removed PM from dispatch entirely and gave the main session all coordination responsibilities including status management and AC verification. In practice during E-100 dispatch (2026-03-15), this created six distinct role-boundary violations — each traced to the missing PM role during dispatch.

The fix is surgical: spawn PM as a teammate with a focused role (status management + AC verification), not as a general coordinator. The main session keeps spawning authority, routing decisions, merge-back, and cascade logic. This is a separation of concerns, not a return to the three-role model.

**Expert consultation**: CA consultation recommended before READY — the changes touch 3 context-layer files that define the dispatch pattern. The epic is DRAFT pending CA consultation in the next session.

## Goals
- PM is spawned as a teammate during dispatch with a clearly defined role
- Status management (story status transitions, epic table updates, epic status transitions) owned by PM
- AC verification ("did they build what was specified") owned by PM, separate from code-reviewer's quality gate
- Main session retains: spawning agents, routing work, merge-back protocol, cascade decisions
- Closure sequence status work (epic COMPLETED, history entries) owned by PM

## Non-Goals
- Changing the code-reviewer's role or rubric
- Adding new review gates or process steps
- Changing how implementers report completion (they still report to main session)
- Modifying worktree isolation or merge-back protocols
- Returning to the three-role model from E-056 (this is four roles with clear boundaries, not the old PM-as-general-coordinator pattern)

## Success Criteria
- `dispatch-pattern.md` documents PM as a fourth dispatch team role with clear responsibility boundaries
- `implement/SKILL.md` Phase 2 spawns PM alongside implementers and code-reviewer
- `implement/SKILL.md` Phase 3 routes status updates and AC verification through PM
- `workflow-discipline.md` reflects PM's dispatch role
- Anti-pattern "Do not spawn a PM teammate" is removed and replaced with PM spawning instructions
- Main session explicitly prohibited from writing code, updating statuses, verifying ACs, or absorbing other agents' work
- Implementers explicitly prohibited from modifying story status files or checking ACs
- Code-review findings routed to original implementer, never fixed by main session
- "Never absorb — always respawn" rule documented for missing/crashed agents
- No ambiguity about who owns what during dispatch — each of the 6 E-100 incidents has a corresponding prohibition

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-108-01 | Update dispatch-pattern.md and workflow-discipline.md with PM dispatch role | TODO | None | - |
| E-108-02 | Update implement SKILL.md with PM spawning and routing | TODO | E-108-01 | - |

## Dispatch Team
- claude-architect (E-108-01, E-108-02)

## Technical Notes

### E-100 Dispatch Incident Log

Six role-boundary violations observed during E-100 dispatch (2026-03-15). Each traces to the missing PM role during dispatch.

**Incident 1: PM not spawned at dispatch start.**
The dispatch-pattern.md said "no PM during dispatch" — so the team lead (main session) began E-100 dispatch without PM. The user had to intervene mid-dispatch to demand PM be added. This violated PM's ownership of the epic lifecycle. Without PM present from the start, there was no agent watching for status/AC violations as they happened.

**Incident 2: Team lead updated story/epic statuses directly.**
The main session changed E-100-01 and E-100-02 from TODO → IN_PROGRESS → DONE in both story files and the epic Stories table. Status management is PM's exclusive responsibility — the main session should only orchestrate (spawn, route, merge-back, cascade).

**Incident 3: Team lead verified ACs directly.**
For E-100-01, the main session was about to verify acceptance criteria itself instead of routing to PM. AC verification requires domain knowledge of what was specified — that's PM's job, not a routing coordinator's.

**Incident 4: Team lead applied code fixes from code review.**
The code-reviewer's MUST FIX on E-100-02 (`_compute_wl` type hint `str` → `int`) was fixed directly by the team lead instead of being routed back to the software-engineer who wrote the code. The main session should NEVER write or modify application code — it routes findings to the implementer for resolution.

**Incident 5: Software engineers self-marked stories DONE and checked AC boxes.**
Happened on E-100-02, E-100-03, and E-100-05. Implementing agents modified their own story status files, setting `Status: DONE` and checking `[x]` on AC boxes. This bypasses PM's independent verification — the implementer is grading their own homework.

**Incident 6: dispatch-pattern.md actively encouraged wrong behavior.**
The existing text "main session manages all statuses" was the root cause of incidents 1-3. The roles need explicit boundaries documented as prohibitions, not just responsibilities.

### Role Boundary Principles (Derived from Incidents)

1. **Never absorb a crashed agent's work.** If an agent crashes or is missing, respawn it. The main session must not take over an agent's domain responsibilities. (Incidents 1, 3, 4)
2. **Status files are PM-exclusive.** No other agent may modify story status fields, check AC boxes, or update epic table rows. (Incidents 2, 5)
3. **AC verification is PM-exclusive.** The PM verifies ACs independently after implementation, using the reviewer's findings and its own reading of the story spec. (Incident 3)
4. **The main session never writes code.** Not application code, not test code, not even a one-line type hint fix. All code changes route through implementers. (Incident 4)
5. **Implementers report; PM adjudicates.** Implementers report completion to the main session. The main session forwards to PM for AC verification and to code-reviewer for quality review. Both gates must pass before merge-back. (Incident 5)

### Role Boundaries During Dispatch

**Main session (spawner + router) — orchestrate ONLY:**
- Creates the team, spawns all agents (implementers + code-reviewer + PM)
- Routes implementer completion reports to code-reviewer and PM
- Manages merge-back protocol (git merge, worktree cleanup, branch deletion)
- Makes cascade decisions (which stories are unblocked, which agents to spawn next)
- Routes code-review findings to implementers for resolution (NEVER fixes code itself)
- Runs closure sequence infrastructure (archive move, worktree sweep)
- Escalates to user on circuit breaker, merge conflicts, dispatch failures
- **MUST NOT**: write or modify application code, update story/epic status files, check AC boxes, verify acceptance criteria, or absorb any other agent's domain responsibilities. If an agent is missing, respawn it.

**Product-manager (status owner + AC verifier):**
- Updates story status files (TODO -> IN_PROGRESS -> DONE) and epic Stories table
- Updates epic status (READY -> ACTIVE -> COMPLETED)
- Verifies acceptance criteria when implementers report completion ("did they build what was specified")
- Writes epic History entries during closure
- Updates PM memory during closure
- Reviews ideas backlog and vision signals during closure

**Code-reviewer (quality gate):**
- Reviews code quality, conventions, and correctness (unchanged)
- Returns APPROVED / NOT APPROVED with structured findings (unchanged)

**Implementers (SE, DE, docs-writer, etc.):**
- Execute stories, report completion to main session (unchanged)
- Respond to code-review findings on their OWN work (main session routes findings back to them)
- MUST NOT modify story status files, check AC boxes, or update epic tables — that is PM's exclusive responsibility
- MUST NOT self-assess ACs — PM performs independent AC verification after implementation
- MUST NOT fix other agents' code — each implementer owns only their assigned story's code

### Interaction Flow Change

Current flow:
```
Implementer reports completion -> Main session triages findings -> Main session verifies ACs -> Main session updates status
```

New flow:
```
Implementer reports completion -> Main session routes to code-reviewer AND PM
  - Code-reviewer: quality review -> findings to main session for triage
  - PM: AC verification -> pass/fail to main session
  - Both must pass before main session runs merge-back
  - PM updates status after merge-back succeeds
```

### Key Design Decisions

1. **PM does NOT spawn agents.** The main session retains all spawning authority. This avoids the nested-spawn problem from E-056.
2. **PM does NOT manage merge-back.** Git operations stay with the main session (the entity that has direct access to the main checkout).
3. **PM receives completion reports via the main session.** Implementers report to main session; main session forwards to PM for AC verification. This keeps the main session as the single routing hub.
4. **AC verification and code review happen in parallel.** The main session can route to both PM and code-reviewer simultaneously when an implementer reports completion.
5. **Status updates happen after merge-back.** PM marks DONE only after the main session confirms merge-back succeeded. This preserves the "not DONE until merged" invariant.
6. **Implementers never touch status.** Implementing agents must not modify story status files, check AC boxes, or update the epic Stories table. This was learned from E-100-02, where the SE prematurely marked its own story DONE and checked all ACs — bypassing PM's independent verification role.

### Files to Change

- `/.claude/rules/dispatch-pattern.md` -- Team Composition section (add PM role), Dispatch Flow steps, Closure Sequence (PM owns status steps)
- `/.claude/skills/implement/SKILL.md` -- Phase 2 (spawn PM), Phase 3 (route to PM), Phase 5 (PM owns closure status work), anti-patterns update
- `/.claude/rules/workflow-discipline.md` -- Workflow Routing Rule (reflect PM dispatch role)

## Open Questions
- CA consultation needed: Do the proposed changes to dispatch-pattern.md create any conflicts with the worktree isolation rules, code-reviewer circuit breaker, or agent-team-compliance patterns? Should the "main session never writes code" rule be in dispatch-pattern.md, workflow-discipline.md, or both?

## History
- 2026-03-15: Created during E-100 dispatch. Motivated by the main session's overloaded responsibilities during multi-wave dispatch.
- 2026-03-15: Expanded with full 6-incident log from E-100 dispatch session. Added Role Boundary Principles, strengthened main session prohibitions ("MUST NOT write code, update statuses, verify ACs, or absorb other agents' work"), added implementer "respond to code-review findings on own work" responsibility, added "route findings to implementer" to main session (replacing direct fix pattern). CA consultation flagged as needed before READY. Stories updated with additional ACs covering all 6 incidents.
