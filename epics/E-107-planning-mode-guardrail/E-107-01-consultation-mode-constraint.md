# E-107-01: Add Consultation Mode Constraint to Rules Layer

## Epic
[E-107: Planning-Mode Agent Guardrail](epic.md)

## Status
`TODO`

## Description
After this story is complete, agents whose spawn prompt declares consultation mode will be structurally prevented from implementing code, modifying story/epic files, or running implementation-verification commands. The constraint is activated by a mode declaration in the spawn prompt (not by the absence of a story reference), ensuring agents working in their primary capacity (PM writing epics, api-scout writing endpoint docs) are unaffected. Both the constraint and the spawn convention live in `workflow-discipline.md` (loaded for all agents).

## Context
During an E-100 planning session, the DE agent was spawned for schema consultation but unilaterally implemented the full E-100-01 story -- writing migration DDL, test fixtures, and 47 tests -- and marked the story DONE. The existing Work Authorization Gate covers dispatch agents (requires a story reference) but has no equivalent constraint for consultation-mode agents. This story closes that gap by extending workflow-discipline.md with a mode-declaration-triggered constraint and a spawning convention subsection.

**Why mode-declaration, not story-absence**: The original formulation ("agents without a story assignment") would accidentally block PM from writing epics (`epics/**`), api-scout from writing endpoint docs (`docs/`), and other agents working in their primary capacity without story references. The refined approach: the constraint activates only when the spawn prompt declares consultation mode, matching the actual failure mode (DE was told "planning only" and ignored it).

## Acceptance Criteria
- [ ] **AC-1**: `workflow-discipline.md` contains a new "Consultation Mode Constraint" section (placed after the Work Authorization Gate) that defines consultation mode as: "An agent is in consultation mode when its spawn prompt includes the consultation mode convention phrase" (defined in AC-5's Spawning Convention subsection; not when it lacks a story reference). The section defines what consultation-mode agents MUST NOT do and what they MAY do.
- [ ] **AC-2**: The MUST NOT list includes: creating/modifying/deleting files in `src/`, `tests/`, `migrations/`, `scripts/`, or `docs/`; modifying epic or story files (`epics/**`, `.project/archive/**`); running implementation-verification commands (`pytest`, `docker compose`).
- [ ] **AC-3**: The MAY list includes: reading any file; writing to own agent memory (`.claude/agent-memory/<agent-name>/`); producing recommendations via SendMessage; creating files in `.project/research/` when explicitly asked.
- [ ] **AC-4**: The section states that if a consultation-mode agent identifies implementable work, it MUST report the recommendation to the spawner via SendMessage rather than implementing it.
- [ ] **AC-5**: The Consultation Mode Constraint section includes a "Spawning Convention" subsection that: (a) requires consultation spawn prompts to include the phrase "Consultation mode: do not create or modify implementation files or planning artifacts"; (b) states that this phrase is the sole trigger that activates the constraint (not just defense-in-depth) -- semantically equivalent phrasing does NOT activate it; (c) provides guidance on when to declare consultation mode -- SHOULD declare when spawning implementing-type agents (SE, DE, docs-writer) for advisory input; NOT declared when spawning agents in their primary capacity (PM for planning, api-scout for exploration, baseball-coach for domain consultation, architect for context-layer work -- architect's primary capacity is producing context-layer artifacts, so consultation mode would conflict with legitimate output).
- [ ] **AC-6**: The section includes a brief explanation of how the two authorization gates complement each other: Work Authorization Gate covers dispatch (story-required, opt-out); Consultation Mode Constraint covers advisory spawns (convention-triggered, opt-in by spawner). The section states that the two gates are mutually exclusive: a dispatch spawn includes a story reference without the consultation mode phrase; a consultation spawn includes the consultation mode phrase without a story reference. If both are present in a spawn prompt, the Consultation Mode Constraint takes precedence (more restrictive).
- [ ] **AC-7**: No new rule files are created. No agent definition files are modified. No changes to CLAUDE.md.

## Technical Approach
One existing rule file (`/.claude/rules/workflow-discipline.md`) gets two new sections. The Consultation Mode Constraint adds a mode-declaration-triggered gate that complements the existing Work Authorization Gate. The spawning convention phrase is the activation trigger -- when present in a spawn prompt, the agent is bound by the MUST NOT / MAY lists. When absent, the constraint is inactive (the agent is working in its primary capacity or under the Work Authorization Gate for dispatch). Context-layer files (`.claude/rules/`, `.claude/skills/`, `.claude/agents/`) are intentionally NOT in the blocked path list -- architect consultation frequently produces context-layer artifacts.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/workflow-discipline.md` -- add Consultation Mode Constraint section (includes Spawning Convention subsection)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass

## Notes
- Architect consultation (2026-03-15): Recommended Approach 1 (extend workflow-discipline.md) + light Approach 3 (spawn prompt convention). Rejected new rule file (scatters authorization logic) and `mode: "plan"` parameter (heavyweight, blocks legitimate memory writes).
- Spec review triage (2026-03-15): P1 (root infra files in blocked list) dismissed -- pragmatic list covers actual failure mode, extensible if new patterns emerge. P2 (spawn convention in dispatch-pattern.md) accepted -- moved to workflow-discipline.md because the E-100 incident was a Task-tool consultation spawn, not a dispatch spawn. Scope simplified from two files to one.
- Second refinement pass (2026-03-15): PM identified that story-absence discriminator would block PM/api-scout from primary work. Architect confirmed Option A (spawn-convention-triggered) as cleanest approach. ACs revised: consultation mode defined by spawn prompt declaration, not story absence. AC-5 elevated from defense-in-depth to primary trigger. AC-6 added (gate complementarity explanation). Former AC-6 renumbered to AC-7.
- Second spec review triage (2026-03-15): 4 findings triaged. (1) P1: AC-1/AC-5 trigger inconsistency — refined AC-1 to defer to AC-5's convention phrase as sole trigger (architect recommended exact-phrase model over semantic). (2) P2: AC-2/AC-5 architect conflict — refined AC-5 to explicitly list architect as "never consultation mode" with rationale (architect recommended: context-layer work IS primary capacity). (3) P2: E-106 reference stale — fixed in epic Non-Goals ("evaluated separately" not "resolved via"). (4) P3: vague DoD checks — collapsed to AC completion only.
- The blocked path list is pragmatic, not exhaustive. If new violation patterns emerge, extend the list.
