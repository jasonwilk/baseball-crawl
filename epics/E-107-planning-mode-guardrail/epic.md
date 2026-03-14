# E-107: Planning-Mode Agent Guardrail

## Status
`DRAFT`

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
- Punishing agents for past violations (the E-100 incident is resolved via E-106)
- Changing how dispatch works (dispatch-pattern.md is fine)
- Adding hard technical enforcement (we're working with LLM agents — the guardrail is a rule, not a sandbox)

## Stories
To be written during refinement.

## Technical Notes

### Possible Approaches (to be evaluated during refinement)
1. **Add consultation-mode clause to Work Authorization Gate**: Extend the existing rule to cover non-dispatch agents. Something like: "Agents spawned for consultation MUST NOT create, modify, or delete files outside of their agent memory. If a consultation agent identifies work that should be done, it MUST report the recommendation to the team lead, not implement it."
2. **New rule file**: `planning-mode-constraints.md` — loaded for all agents, explicitly constraining what agents can do when spawned without a story reference.
3. **Spawn prompt standardization**: Codify a standard consultation spawn template that includes the constraint, rather than relying on ad-hoc "do not write code" instructions.

### Related Rules
- `workflow-discipline.md` — Work Authorization Gate (dispatch scope)
- `agent-team-compliance.md` — team formation and consultation compliance
- `dispatch-pattern.md` — implementing agent responsibilities
- `worktree-isolation.md` — constrains what worktree agents can do (but doesn't apply to non-worktree consultation agents)

## Open Questions
- Is a rules-layer constraint sufficient, or do we need a convention in the Agent tool itself (e.g., a `mode: "consultation"` parameter)?
- Should consultation agents be spawned with `mode: "plan"` to require plan approval before any file writes?
- How do we handle edge cases where a consultation agent legitimately needs to read files to give good advice? (Reading is fine — writing is the problem.)

## History
- 2026-03-14: Created. Motivated by DE agent implementing E-100-01 during a planning consultation session. PM identified this as a new failure mode not covered by existing workflow rules.
