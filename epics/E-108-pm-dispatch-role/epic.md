# E-108: PM as Dispatch Teammate

## Status
`READY`

## Overview
Add the product-manager as a spawned teammate during epic dispatch. Currently, the main session manages all story statuses, epic table updates, and AC verification directly. This concentrates too many responsibilities in the main session and violates the PM's ownership of epics. The fix: PM is spawned as a teammate during dispatch and owns status management + AC verification, while the main session retains spawning, routing, merge-back, and cascade decisions.

## Background & Context
The dispatch pattern was simplified in E-065 (Merge Team Lead and PM Roles) to eliminate the idle team lead problem. That fix went too far: it removed PM from dispatch entirely and gave the main session all coordination responsibilities including status management and AC verification. In practice during E-100 dispatch (2026-03-15), this created six distinct role-boundary violations — each traced to the missing PM role during dispatch.

The fix is surgical: spawn PM as a teammate with a focused role (status management + AC verification), not as a general coordinator. The main session keeps spawning authority, routing decisions, merge-back, and cascade logic. This is a separation of concerns, not a return to the three-role model.

**Expert consultation**: CA consultation completed 2026-03-15. No conflicts with worktree isolation, code-reviewer circuit breaker, or agent-team-compliance. See CA Consultation Results in Technical Notes.

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
  - Both must pass before merge-back (with PM AC override: if reviewer flags
    an AC as MUST FIX but PM says it passes, PM's verdict is authoritative —
    see PM-Reviewer AC Disagreement in Technical Notes)
  - PM updates status after merge-back succeeds
```

### Key Design Decisions

1. **PM does NOT spawn agents.** The main session retains all spawning authority. This avoids the nested-spawn problem from E-056.
2. **PM does NOT manage merge-back.** Git operations stay with the main session (the entity that has direct access to the main checkout).
3. **PM receives completion reports via the main session.** Implementers report to main session; main session forwards to PM for AC verification. This keeps the main session as the single routing hub.
4. **AC verification and code review happen in parallel.** The main session can route to both PM and code-reviewer simultaneously when an implementer reports completion.
5. **Status updates happen after merge-back.** PM marks DONE only after the main session confirms merge-back succeeded. This preserves the "not DONE until merged" invariant.
6. **Implementers never touch status.** Implementing agents must not modify story status files, check AC boxes, or update the epic Stories table. This was learned from E-100-02, where the SE prematurely marked its own story DONE and checked all ACs — bypassing PM's independent verification role.

### Reviewer AC Relationship

PM owns authoritative AC verification (pass/fail gate for the DONE decision). Code-reviewer continues to check ACs as part of its quality review — no rubric change, preserving the Non-Goals commitment. If code-reviewer flags an unmet AC, it is routed to PM who makes the final determination. This avoids changing `code-reviewer.md` while eliminating ambiguity about who has AC authority. The code-reviewer's AC observations are advisory input to PM's verdict, not a separate blocking gate.

### CA Consultation Results (2026-03-15)

**Conflict check**: No conflicts with worktree isolation, code-reviewer circuit breaker, or agent-team-compliance patterns. The "never absorb — always respawn" principle aligns with Pattern 3 in agent-team-compliance.md. No changes needed to agent-team-compliance.md.

**Placement of "main session never writes code" rule**: Both files, with different scope. `dispatch-pattern.md` gets the full prohibition list in the main session role definition. `workflow-discipline.md` gets a concise version in the Workflow Routing Rule section. Rationale: defense-in-depth — different audiences at different moments, both always loaded.

**PM worktree isolation**: PM is spawned WITHOUT `isolation: "worktree"` — it reads/writes status files in the main checkout and needs direct access.

**Gate Interaction — PM AC rejection**: When PM rejects ACs, route feedback to implementer alongside code-review findings. After revision, both gates re-evaluate. PM AC rejection does NOT have its own circuit breaker — the code-reviewer's 2-round circuit breaker governs the overall loop. If the circuit breaker fires, escalate to user regardless of PM AC status.

**PM-Reviewer AC Disagreement**: The code-reviewer mechanically classifies unmet ACs as MUST FIX, which produces a NOT APPROVED verdict. PM is the authoritative AC gate. When their verdicts conflict on AC satisfaction, the main session resolves as follows:
1. Reviewer APPROVED + PM ACs pass → merge-back (normal path).
2. Reviewer NOT APPROVED due to non-AC MUST FIX only (bugs, conventions, security) → route to implementer; PM's AC verdict is irrelevant to these findings.
3. Reviewer NOT APPROVED, ALL MUST FIX are AC-related, PM says ACs pass → **PM override**: reclassify all AC-based MUST FIX as resolved-by-PM, proceed to merge-back.
4. Reviewer NOT APPROVED with mixed AC + non-AC MUST FIX, PM says ACs pass → remove AC-based items from MUST FIX list, route only non-AC items to implementer. If non-AC items remain, verdict stays NOT APPROVED for those items only.
5. PM says ACs fail → route PM's AC feedback to implementer regardless of reviewer verdict.
Non-AC findings (bugs, security, conventions) are the reviewer's exclusive domain — PM cannot override those. This resolution happens at the main session's routing layer; `code-reviewer.md` is unchanged.

**PM context window edge case**: If PM's context fills during large epics, the main session respawns PM with a fresh summary of epic state. Document this in implement SKILL.md.

**PM spawn context template**: implement SKILL.md Phase 2 needs an explicit spawn context template for PM (like the ones for implementers and code-reviewer).

**Closure assessment ownership**: Main session remains the trigger for doc/context-layer assessments (may need to spawn additional agents, which PM can't do). PM owns status + ACs, not spawning coordination.

### Stale Agent Memory Cleanup

After E-108 ships, PM's own memory files and one skill file will contain contradictory "no PM during dispatch" language. The implementing agent (claude-architect) must update these as part of E-108 implementation -- they are context-layer files within architect's domain.

Files containing stale language:
1. `/.claude/agent-memory/product-manager/lessons-learned.md` -- contains "PM is not spawned as a teammate during dispatch"
2. `/.claude/agent-memory/product-manager/MEMORY.md` -- contains "Main session creates team, spawns implementers directly (no PM teammate)"
3. `/.claude/skills/multi-agent-patterns/SKILL.md` -- contains "no PM intermediary during dispatch" (lower priority, loaded on demand)

If these are not updated, PM will read its own memory at conversation start and see rules contradicting the new dispatch pattern. This is the same class of issue that Codex spec review F1 (Round 0) caught for `CLAUDE.md` and `product-manager.md` -- stale "PM is not spawned" text in active context-layer files.

### Files to Change

- `/.claude/rules/dispatch-pattern.md` -- Team Composition section (add PM role), Dispatch Flow steps, Closure Sequence (PM owns status steps)
- `/.claude/skills/implement/SKILL.md` -- Phase 2 (spawn PM), Phase 3 (route to PM), Phase 5 (PM owns closure status work), anti-patterns update
- `/.claude/rules/workflow-discipline.md` -- Workflow Routing Rule (reflect PM dispatch role)
- `/CLAUDE.md` -- Workflow Contract step 5 (replace "PM is not spawned" with PM dispatch role)
- `/.claude/agents/product-manager.md` -- How Work Flows step 5 (replace "PM's role is limited to READY" with dispatch role)
- `/.claude/agent-memory/product-manager/lessons-learned.md` -- remove/update "PM is not spawned as a teammate during dispatch" language
- `/.claude/agent-memory/product-manager/MEMORY.md` -- remove/update "no PM teammate" language in Key Workflow Contract and Active Epics sections
- `/.claude/skills/multi-agent-patterns/SKILL.md` -- remove/update "no PM intermediary during dispatch" language

## Open Questions
*All resolved — see CA Consultation Results below.*

## History
- 2026-03-15: Created during E-100 dispatch. Motivated by the main session's overloaded responsibilities during multi-wave dispatch.
- 2026-03-15: Expanded with full 6-incident log from E-100 dispatch session. Added Role Boundary Principles, strengthened main session prohibitions ("MUST NOT write code, update statuses, verify ACs, or absorb other agents' work"), added implementer "respond to code-review findings on own work" responsibility, added "route findings to implementer" to main session (replacing direct fix pattern). CA consultation flagged as needed before READY. Stories updated with additional ACs covering all 6 incidents.
- 2026-03-15: CA consultation completed. No conflicts found. Findings incorporated: PM spawned without worktree isolation, gate interaction paragraph (PM AC rejection uses code-reviewer circuit breaker), "never writes code" rule in both files with different scope, PM spawn context template added to E-108-02, PM context window respawn guidance added to E-108-02, closure assessment ownership stays with main session. Open Questions resolved. Stories updated with 3 new ACs (E-108-01) and 3 new ACs (E-108-02). Epic marked READY.
- 2026-03-15: Codex spec review triage. Three findings assessed. F1 (P1, incomplete file set): REFINE — `CLAUDE.md` and `product-manager.md` added to E-108-01 scope with AC-18 and AC-19 to eliminate contradictory "PM is not spawned" statements in active context-layer files. F2 (P1, unclear reviewer/PM AC model): REFINE — "Reviewer AC Relationship" paragraph added to Technical Notes clarifying PM as authoritative AC gate with code-reviewer AC observations as advisory input; AC-20 added to E-108-01. F3 (P3, vague DoD): DISMISSED — template-level boilerplate, not actionable at story level.
- 2026-03-15: Codex spec review Round 1 triage. Two findings assessed. F1 (P1, PM-vs-reviewer AC arbitration gap): DISMISSED — already resolved by Reviewer AC Relationship paragraph in Technical Notes + AC-20; code-reviewer's MUST FIX classification is advisory input to PM's verdict, not a separate blocking gate. F2 (P2, context-layer-only exception unaddressed): REFINE — AC-21 added to E-108-01 (dispatch-pattern.md step 6 routes to PM), AC-18 added to E-108-02 (implement SKILL.md context-layer-only skip routes to PM).
- 2026-03-15: Codex spec review Round 2 triage. Two findings assessed. F1 (P1, PM-vs-reviewer AC arbitration still under-specified): **REVERSED from Round 1 DISMISS → REFINE** — Round 1 dismissal was premature. The Reviewer AC Relationship paragraph was conceptual but lacked a concrete dispatch flow mechanism. The reviewer mechanically classifies unmet ACs as MUST FIX → NOT APPROVED; the spec didn't describe what the main session does when PM disagrees. Added "PM-Reviewer AC Disagreement" paragraph to Technical Notes with 5-case resolution rule. Refined AC-20 to specify the PM-override mechanism (remove AC-based MUST FIX from routing list; if that empties MUST FIX, story passes review gate; non-AC findings remain reviewer's domain). Updated Interaction Flow Change diagram to reference PM AC override. F2 (P1, hidden dependency on code-reviewer.md): DISMISSED — restatement of F1. Arbitration logic lives in dispatch-pattern.md (in scope), not code-reviewer.md. Reviewer behavior unchanged per Non-Goals.
- 2026-03-15: Codex spec review Round 3 triage. Two findings assessed. F1 (P2, E-108-01 not a standalone slice — transient contradiction with implement SKILL.md between stories): DISMISSED — both stories are sequential same-agent dispatch (01 → 02, both claude-architect); transient window is zero in practice; merging would create 39-AC mega-story; E-108-02 AC-11 explicitly checks cross-file consistency. F2 (P2, PM memory routing-precedence exception stale): REFINE — AC-22 added to E-108-01 to update dispatch-pattern.md line 183 exception text (main session no longer updates PM memory; PM owns its own memory during closure).
- 2026-03-15: Codex spec review Round 4 (final) triage. Two P2 findings assessed — same class (stale validation-ownership text in closure sections). F1 (P2, dispatch-pattern.md step 9 still attributes context-layer-only validation to main session): REFINE — AC-7 expanded to include step 9 validation-ownership attribution alongside existing status-update steps. F2 (P2, implement SKILL.md Phase 5 Step 1 still attributes context-layer-only validation to main session): REFINE — AC-18 expanded to cover both Phase 3 (live dispatch) and Phase 5 Step 1 (closure validation summary). No new ACs added; minimal expansions to existing ACs.
- 2026-03-15: E-108 evaluation session identified stale agent memory cleanup requirement. Three files outside original scope contain contradictory "no PM during dispatch" language: `lessons-learned.md`, PM `MEMORY.md`, and `multi-agent-patterns/SKILL.md`. Added "Stale Agent Memory Cleanup" subsection to Technical Notes and added all three files to Files to Change. Same class as Codex spec review F1 (Round 0) -- stale text in active context-layer files that PM reads at conversation start.
- 2026-03-15: Folded two E-107 code review SHOULD FIX findings into E-108-01 as opportunistic fixes (both target `workflow-discipline.md`, already in scope): (1) PM Task Types section says "five modes" but should say "six" (curate added in E-068), (2) Consultation Mode Constraint MUST NOT list blocks `docs/` but is silent about `.claude/` paths -- add clarifying sentence explaining the intentional asymmetry.
- 2026-03-15: Codex spec review Round 5 triage. Two findings assessed. F1 (P1, stale memory cleanup has no story-level AC): REFINE — AC-9 expanded from "either file" to "any file listed in Files to Create or Modify" and three stale memory/skill files added to E-108-01's Files to Create or Modify section (`lessons-learned.md`, PM `MEMORY.md`, `multi-agent-patterns/SKILL.md`). F2 (P2, opportunistic fixes have no AC coverage): **REVERSED from DISMISS → REFINE** — user override: opportunistic fixes are carry-overs that were already missed once during E-107; they are the most in need of an AC, not the least. "The implementer will just do it" is the same reasoning that let them slip originally. AC-23 added to E-108-01 covering both fixes.
