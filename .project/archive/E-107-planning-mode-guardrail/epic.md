# E-107: Planning-Mode Agent Guardrail

## Status
`COMPLETED`

## Overview
Prevent agents spawned for planning/consultation from implementing code. The existing Work Authorization Gate (workflow-discipline.md) covers dispatch — agents need a story reference before implementing. But agents spawned for planning sessions (schema design, epic refinement, domain consultation) have no equivalent constraint preventing them from writing code when they should only be advising.

## Background & Context
During an E-100 planning session (2026-03-14), the DE agent was spawned for schema design consultation. After delivering the refined schema proposal and receiving a shutdown request, DE instead implemented the full E-100-01 story — writing migration DDL, test fixtures, and 47 tests. The implementation was high quality, but it violated the planning boundary:

1. The user had not finalized the plan or authorized dispatch
2. The spec review hadn't been triaged yet (findings were still being fixed)
3. Other team members (PM, SE, coach) had already shut down
4. The user explicitly said the team was for planning, not implementation

### Root Cause
The Work Authorization Gate in `workflow-discipline.md` says: "Implementing agents MUST NOT begin any implementation work without a referenced story file in the task prompt." But DE was not spawned as an implementing agent — it was spawned as a planning consultant. The gate's scope is "implementing agents," which doesn't cover agents in advisory/consultation roles who exceed their brief.

### The Gap
No rule prevents a consultation-mode agent from writing files. The agent's spawn prompt said "Do NOT write code" and "this is planning only," but these are prompt-level instructions that can be overridden by the agent's own judgment. There is no structural guardrail equivalent to the story-reference requirement for dispatch agents.

### Additional Violation: Story File Modification
DE also modified the story file (`E-100-01-schema-evolution.md`) — marking it `DONE` and checking all ACs. Story status management is the main session's responsibility during dispatch (per dispatch-pattern.md), and this wasn't even a dispatch. A consultation agent should never modify epic or story files. The guardrail must cover both code files AND planning artifacts (epic/story files, status updates, AC checkboxes).

## Goals
- Structural prevention of implementation during planning sessions
- Clear distinction between "consultation mode" and "implementation mode" for spawned agents
- The guardrail should be in the rules layer (loaded for all agents), not just in spawn prompts

## Non-Goals
- Punishing agents for past violations (the E-100 incident is evaluated separately in E-106)
- Changing how dispatch works (dispatch-pattern.md is fine)
- Adding hard technical enforcement (we're working with LLM agents — the guardrail is a rule, not a sandbox)

## Success Criteria
- Agents whose spawn prompt includes the consultation mode convention phrase are structurally constrained from implementing code or modifying story files
- The constraint is in the rules layer (loaded for all agents), not just in spawn prompts
- The spawn convention phrase is the activation trigger (not just defense-in-depth) -- agents working in their primary capacity (PM, api-scout, etc.) are unaffected
- The two authorization gates (Work Authorization + Consultation Mode) together cover both dispatch and advisory spawns

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-107-01 | Add Consultation Mode Constraint to Rules Layer | DONE | None | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

### Chosen Approach (refined with claude-architect, 2026-03-15; second pass 2026-03-15)
**Approach 1 (extend `workflow-discipline.md`) + Approach 3 (spawn convention as mode declaration)**. Two changes to existing files, zero new files. The spawn convention phrase is the trigger that activates the constraint -- not just defense-in-depth.

**Key design decision (second refinement pass)**: The constraint is **mode-declaration-triggered**, not **story-absence-triggered**. The original formulation ("agents without a story assignment") would accidentally block PM from writing epics, api-scout from writing endpoint docs, and other agents working in their primary capacity. The refined approach: the constraint activates only when the spawn prompt declares consultation mode (via the convention phrase). This matches the actual failure mode -- DE was told "planning only" and ignored it.

**How the two gates complement each other:**
- **Work Authorization Gate**: Covers dispatch. Requires a story reference. Structural (opt-out).
- **Consultation Mode Constraint**: Covers advisory spawns. Triggered by mode declaration. Structural (opt-in by spawner, mandatory compliance by agent).
- **Mutual exclusivity**: The two gates cover different spawn types. A dispatch spawn has a story reference and no consultation mode declaration; a consultation spawn has the mode declaration and no story reference. If a spawn prompt somehow contains both, the Consultation Mode Constraint takes precedence (more restrictive).

Rejected alternatives:
- **New rule file** (`planning-mode-constraints.md`): Scatters authorization logic across two files. The Work Authorization Gate already governs "when can an agent implement?" — extending its scope is cleaner.
- **`mode: "plan"` spawn parameter**: Heavyweight. Would force plan-approval workflows for legitimate memory writes. The problem is role-based (consultation vs. implementation), not action-based.
- **Agent definition changes**: Unnecessary. The constraint is in the rules layer (loaded for all agents via `paths: "**"`).
- **Story-absence discriminator**: Too broad. PM, api-scout, baseball-coach, and claude-architect all legitimately operate without story references. An exemption list would be fragile and inverts the logic (universal constraint + carve-outs = wrong constraint).
- **Explicit agent exemptions (Option B)**: Requires maintenance when new agent types are added. Sign that the universal constraint is wrong.
- **"Advisory-input spawns" definition (Option C)**: Conceptually right but operationally fuzzy -- hard to detect structurally without a mode declaration, which leads back to Option A.

### Related Rules
- `workflow-discipline.md` — Work Authorization Gate (dispatch scope)
- `agent-team-compliance.md` — team formation and consultation compliance
- `dispatch-pattern.md` — implementing agent responsibilities
- `worktree-isolation.md` — constrains what worktree agents can do (but doesn't apply to non-worktree consultation agents)

## Open Questions
None remaining. All resolved during refinement:
- Rules-layer constraint is sufficient (no `mode: "consultation"` parameter needed)
- `mode: "plan"` rejected as heavyweight (blocks legitimate memory writes)
- Reading is explicitly allowed; only creation/modification/deletion is constrained
- Context-layer files intentionally NOT blocked (architect consultation produces context-layer artifacts)
- Constraint is mode-declaration-triggered, not story-absence-triggered (second pass: avoids blocking PM, api-scout, and other agents working in their primary capacity)

## History
- 2026-03-14: Created. Motivated by DE agent implementing E-100-01 during a planning consultation session. PM identified this as a new failure mode not covered by existing workflow rules.
- 2026-03-15: Refined. Architect consulted — recommended extending workflow-discipline.md + spawn prompt convention. 1 story written. Epic set to READY.
- 2026-03-15: Second refinement pass. PM identified critical scoping gap: story-absence discriminator would block PM from writing epics and api-scout from writing endpoint docs. Architect consulted — recommended Option A (spawn-convention-triggered) with mode-declaration refinement. ACs revised: consultation mode is now triggered by spawn prompt declaration, not by absence of story reference. AC-5 elevated from defense-in-depth to primary enforcement mechanism. Guidance added for when to declare consultation mode.
- 2026-03-15: Fresh-eyes PM pass. One finding: AC-6 lacked explicit mutual exclusivity statement for the two gates. Added precedence rule (Consultation Mode Constraint wins if both signals are present in a spawn prompt). Minor clarification, no design change.
- 2026-03-15: Second fresh-eyes PM pass (new context). One finding: AC-5(c) SHOULD list omitted docs-writer, which CLAUDE.md explicitly lists as an implementing agent requiring work authorization. Expanded parenthetical from "(SE, DE)" to "(SE, DE, docs-writer)." Also noted pre-existing inconsistency in PM Task Types section ("five modes" should be six -- curate added in E-068) -- outside E-107 scope.
- 2026-03-15: Dispatched and completed. claude-architect implemented E-107-01 (context-layer-only story, no worktree isolation). Main session verified all 7 ACs directly. Documentation assessment: no triggers fired. Context-layer assessment: triggers 1 (new convention), 3 (failure mode discovered), 4 (agent behavior change) fired -- codification was the epic's deliverable itself (new Consultation Mode Constraint section in workflow-discipline.md), so no additional architect work needed. Triggers 2, 5, 6: no.
