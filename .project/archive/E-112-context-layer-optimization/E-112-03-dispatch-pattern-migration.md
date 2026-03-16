# E-112-03: dispatch-pattern.md Migration to Dispatch Scope

## Epic
[E-112: Context Layer Optimization](./epic.md)

## Status
`DONE`

## Description
After this story is complete, `dispatch-pattern.md` will be a ~25-line stub containing the Agent Selection routing table and a pointer to the implement skill. The ~195 lines of dispatch procedure content (already present in the implement skill) will be removed from the universal rule, saving ambient context on every non-dispatch interaction.

## Context
`dispatch-pattern.md` is a universal rule (221 lines) that loads on every interaction, but dispatch procedures are only relevant ~10-20% of the time. The implement skill (534 lines) already contains all dispatch procedure content -- `dispatch-pattern.md` is the redundant copy. However, the Agent Selection routing table must remain universally available because the main session uses it during team formation (before the implement skill is loaded). Safety verdict: YELLOW→GREEN with mitigations.

## Acceptance Criteria
- [ ] **AC-1**: A new universal rule `.claude/rules/agent-routing.md` exists containing: (a) the Agent Selection routing table (agent type → story domain mapping), the Dispatch Team metadata guidance, the Agent Hint description, and the Routing Precedence note (context-layer routing check); and (b) a Decision Routing table mapping decision domains to their owning agent and advisory consultants. The decision routing table covers: work definition/priority (PM), context-layer architecture (CA), domain requirements/coaching value (coach), API behavior/endpoint schemas (api-scout), database schema/ETL (DE), Python implementation/testing (SE). This file is self-contained -- an agent reading only this file can determine the correct agent for any story (dispatch routing) and the correct agent to consult for any decision (decision routing).
- [ ] **AC-2**: `dispatch-pattern.md` is reduced to a ~25-line stub that: (a) states the implement skill is the source of truth for dispatch procedures, (b) references `.claude/rules/agent-routing.md` for agent selection, (c) preserves the "Main Session Dispatch Responsibility" one-line summary, and (d) lists the four team roles (main session, PM, implementers, code-reviewer) with one-line descriptions.
- [ ] **AC-3**: The implement skill's trigger list includes "dispatch story E-NNN-SS" (single-story dispatch) in addition to existing epic-level triggers, per Technical Notes mitigation requirement.
- [ ] **AC-4**: The implement skill includes an explicit migration serialization constraint near the overlap prevention guidance in Phase 3 Step 4: migration stories (files under `migrations/`) must never run concurrently, even without explicit file overlap.
- [ ] **AC-5**: All cross-references to `dispatch-pattern.md` in other context-layer files (CLAUDE.md, agent definitions, other rules, skills) are updated to point to the correct location (stub for overview, implement skill for procedure, agent-routing.md for routing table).
- [ ] **AC-6**: No dispatch procedure content is lost -- everything removed from `dispatch-pattern.md` is verifiably present in the implement skill.
- [ ] **AC-7**: All existing tests pass after the changes.

## Technical Approach
The migration has a strict ordering requirement: create `agent-routing.md` FIRST, then update cross-references, then trim `dispatch-pattern.md`. This ensures no moment where the routing table is unavailable. Verify content parity between `dispatch-pattern.md` and the implement skill before removing anything.

Key cross-reference files to check (non-exhaustive -- grep for "dispatch-pattern"):
- `CLAUDE.md`
- `.claude/agents/product-manager.md`
- `.claude/rules/workflow-discipline.md`
- `.claude/skills/implement/SKILL.md`
- `.claude/rules/worktree-isolation.md`

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/agent-routing.md` (create)
- `.claude/rules/dispatch-pattern.md` (modify -- trim to stub)
- `.claude/skills/implement/SKILL.md` (modify -- add single-story trigger)
- `CLAUDE.md` (modify -- update cross-references if any)
- `.claude/agents/product-manager.md` (modify -- update cross-references if any)
- `.claude/rules/workflow-discipline.md` (modify -- update cross-references if any)
- Other files with `dispatch-pattern` references (modify as discovered by grep)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing tests
- [ ] No dangling references to removed `dispatch-pattern.md` content

## Notes
- `workflow-discipline.md` references `dispatch-pattern.md` but is NOT being moved -- its Dispatch Authorization Gate must remain universal (fires before dispatch trigger). Cross-references in `workflow-discipline.md` should point to the stub or to `agent-routing.md` as appropriate.
- The implement skill is dispatch-scoped (loaded only when dispatch is triggered), so moving content there means it's available exactly when needed and absent otherwise.
- Archived files (`.project/archive/`) are frozen historical records -- do NOT update references in archived epics or stories. Only update references in active context-layer files.
- Net savings: ~195 lines removed from ambient context.
- **Migration serialization gap**: The dispatch-pattern has an explicit "Migration Serialization" subsection that the implement skill lacks. AC-4 ensures this constraint is added to the skill before the dispatch-pattern content is removed. The constraint: migration stories must never run concurrently due to sequence number conflicts.
