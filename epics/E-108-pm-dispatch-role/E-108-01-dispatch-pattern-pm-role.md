# E-108-01: Update dispatch-pattern.md and workflow-discipline.md with PM Dispatch Role

## Epic
[E-108: PM as Dispatch Teammate](epic.md)

## Status
`TODO`

## Description
After this story is complete, `dispatch-pattern.md` documents the PM as a spawned teammate during dispatch with clear responsibility boundaries: PM owns status management (story and epic status transitions, epic table updates) and AC verification. The main session retains spawning, routing, merge-back, and cascade. `workflow-discipline.md` reflects the PM's dispatch role.

## Context
The current dispatch pattern (established by E-065) gives the main session all coordination responsibilities. This story adds PM as a fourth role in the Team Composition section and threads PM responsibilities through the Dispatch Flow and Closure Sequence.

## Acceptance Criteria
- [ ] **AC-1**: Team Composition section has four roles: main session (spawner + router), PM (status owner + AC verifier), specialist agents (implementers), code-reviewer (quality gate).
- [ ] **AC-2**: PM role description specifies: story status file updates (TODO -> IN_PROGRESS -> DONE), epic Stories table updates, epic status transitions (READY -> ACTIVE -> COMPLETED), AC verification ("did they build what was specified"), epic History entries, PM memory updates, ideas/vision signal review during closure.
- [ ] **AC-3**: Main session role description is narrowed: spawning agents, routing work (implementer -> code-reviewer + PM), merge-back protocol, cascade decisions, user escalation. Explicitly does NOT manage status updates or verify ACs.
- [ ] **AC-4**: Dispatch Flow step 4 (currently "marks them IN_PROGRESS") routes to PM for status update instead of main session doing it directly.
- [ ] **AC-5**: Dispatch Flow steps 6-8 (completion/review loop) include PM AC verification as a parallel gate alongside code-reviewer. Both must pass before merge-back.
- [ ] **AC-6**: Dispatch Flow step 8 (mark DONE after merge-back) routes to PM for status update.
- [ ] **AC-7**: Closure Sequence steps that involve status updates (step 10: update epic, step 14: update PM memory, step 15: review ideas, step 16: review vision signals) are attributed to PM, not main session.
- [ ] **AC-8**: `workflow-discipline.md` Workflow Routing Rule section reflects PM's dispatch role (PM is spawned during dispatch for status management and AC verification).
- [ ] **AC-9**: No references to "No PM teammate during dispatch" or "PM is not spawned as a teammate during dispatch" remain in either file.
- [ ] **AC-10**: Implementer role description explicitly states: implementing agents MUST NOT modify story status files, check AC boxes, or update the epic Stories table. Only PM performs these actions after independent verification.
- [ ] **AC-11**: Main session role description explicitly prohibits: writing or modifying application/test code, updating story/epic status files, checking AC boxes, verifying acceptance criteria. If a code fix is needed (e.g., from code review), the main session routes the finding to the implementer — never fixes it directly. (Addresses E-100 incident 4: team lead applied code fix instead of routing to SE.)
- [ ] **AC-12**: Main session role includes a "never absorb" rule: if an agent is missing or crashed, respawn it rather than taking over its responsibilities. The main session must not perform PM, code-reviewer, or implementer work in their absence. (Addresses E-100 incident 1: PM not spawned, main session absorbed PM duties.)
- [ ] **AC-13**: Implementer role includes: "Respond to code-review findings on their own work (main session routes findings back to the implementer who wrote the code)." This clarifies that code fixes from review go to the original implementer, not to the main session or a different agent.
- [ ] **AC-14**: The Dispatch Flow documents that code-review findings (MUST FIX, accepted SHOULD FIX) are routed by the main session back to the implementer who wrote the code. The main session triages SHOULD FIX findings (accept/dismiss) but NEVER applies fixes itself.

## Technical Approach
Refer to the epic Technical Notes for role boundaries and interaction flow. The changes are additive to `dispatch-pattern.md` (expand Team Composition, thread PM through Dispatch Flow and Closure Sequence) and a focused update to `workflow-discipline.md` (Workflow Routing Rule section). Do not change merge-back protocol, worktree isolation, or code-reviewer behavior.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-108-02

## Files to Create or Modify
- `/.claude/rules/dispatch-pattern.md`
- `/.claude/rules/workflow-discipline.md`

## Agent Hint
claude-architect

## Handoff Context
- **Produces for E-108-02**: Updated `dispatch-pattern.md` with PM role definitions. `implement/SKILL.md` must align with the new role boundaries.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No contradictions between dispatch-pattern.md and workflow-discipline.md
- [ ] Code follows project style (see CLAUDE.md)
