# E-108-02: Update implement SKILL.md with PM Spawning and Routing

## Epic
[E-108: PM as Dispatch Teammate](epic.md)

## Status
`DONE`

## Description
After this story is complete, the implement skill spawns PM as a teammate in Phase 2, routes status updates and AC verification through PM in Phase 3, and delegates closure status work to PM in Phase 5. The anti-pattern "Do not spawn a PM teammate" is removed and replaced with PM spawning instructions.

## Context
This story operationalizes the role boundaries defined in E-108-01 within the implement skill -- the primary dispatch procedure reference. The skill must align with the updated `dispatch-pattern.md`.

## Acceptance Criteria
- [ ] **AC-1**: Phase 2 Step 2 spawns PM alongside implementers and code-reviewer. PM spawn context instructs PM to wait for status update and AC verification requests from the main session.
- [ ] **AC-2**: Phase 2 Step 3 (set epic to ACTIVE) routes through PM instead of the main session doing it directly.
- [ ] **AC-3**: Phase 3 Step 3 (update statuses to IN_PROGRESS) routes through PM.
- [ ] **AC-4**: Phase 3 Step 5 (monitor/review/verify) includes PM AC verification as a parallel gate alongside code-reviewer routing. The main session sends the implementer's completion report to both PM and code-reviewer.
- [ ] **AC-5**: Phase 3 Step 5a (merge-back) and Step 6 (cascade/mark DONE) route status updates through PM after merge-back succeeds.
- [ ] **AC-6**: Phase 5 Step 2 (update epic to COMPLETED) is attributed to PM.
- [ ] **AC-7**: Phase 5 Steps 5-7 (PM memory, ideas review, vision signals) are attributed to PM.
- [ ] **AC-8**: Anti-pattern 7 ("Do not spawn a PM teammate") is removed and replaced with: "Do not skip PM spawning -- PM handles all status updates and AC verification during dispatch."
- [ ] **AC-9**: Workflow Summary diagram reflects PM as a spawned teammate with status/AC responsibilities.
- [ ] **AC-10**: Phase 5 Step 9 (shut down teammates) includes PM in the shutdown list.
- [ ] **AC-11**: No contradictions between `implement/SKILL.md` and `dispatch-pattern.md` (as updated by E-108-01).
- [ ] **AC-12**: Implementer context block (Phase 3 Step 4, the instructions sent to each implementing agent) includes an explicit prohibition: "Do not modify story status files, check AC boxes, or update the epic Stories table. Report completion to the main session; PM will verify ACs and update statuses independently."
- [ ] **AC-13**: Phase 3 Step 5 (review loop) explicitly documents: "Route MUST FIX and accepted SHOULD FIX findings to the implementer who wrote the code. The main session NEVER applies code fixes itself." This addresses E-100 incident 4.
- [ ] **AC-14**: Anti-patterns section includes: "Do not absorb agent work. If PM crashes, respawn PM. If an implementer crashes, respawn the implementer. The main session never takes over another agent's domain responsibilities."
- [ ] **AC-15**: Phase 2 includes an explicit PM spawn context template (similar to existing implementer and code-reviewer templates) that tells PM: its role (status management + AC verification), the epic file path, and instructions to wait for routing from the main session.
- [ ] **AC-16**: Phase 2 or Phase 3 includes a PM context window recovery note: if PM's context fills during large epics, the main session respawns PM with a fresh summary of current epic state (which stories are DONE, which are IN_PROGRESS, current wave).
- [ ] **AC-17**: Phase 3 Gate Interaction: when PM rejects ACs, the main session routes PM's feedback to the implementer alongside any code-review findings. After implementer revision, both PM and code-reviewer re-evaluate. The code-reviewer's 2-round circuit breaker governs the overall loop — PM does not have a separate circuit breaker.
- [ ] **AC-18**: implement SKILL.md's context-layer-only skip condition (currently "main session verifies ACs directly and marks DONE") routes to PM for AC verification and status update instead of the main session doing it directly -- both in Phase 3 (live dispatch) and Phase 5 Step 1 (closure validation summary). Code-reviewer remains skipped for context-layer-only stories.

## Technical Approach
Refer to the epic Technical Notes for interaction flow changes. Read the updated `dispatch-pattern.md` (from E-108-01) for the authoritative role boundaries. Thread PM through the implement skill's phases without changing merge-back protocol, worktree isolation, or code-reviewer behavior.

## Dependencies
- **Blocked by**: E-108-01
- **Blocks**: None

## Files to Create or Modify
- `/.claude/skills/implement/SKILL.md`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No contradictions between implement SKILL.md and dispatch-pattern.md
- [ ] Code follows project style (see CLAUDE.md)
