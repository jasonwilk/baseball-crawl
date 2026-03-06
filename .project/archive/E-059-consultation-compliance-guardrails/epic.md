# E-059: Consultation Compliance Guardrails

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Add enforceable guardrails to prevent two classes of PM failure exposed during E-058 formation: (1) skipping a user-requested expert consultation because the PM could not spawn the expert and failed to escalate, and (2) prescribing specific implementation details (code patterns, variable names) that belong to the implementing agent. This epic adds procedural checkpoints, stronger rule language, anti-pattern documentation, and an explicit escalation path for the spawning constraint.

## Background & Context
**The incident**: The user asked the PM to "work with SE to propose a fix" for a bug. The PM's agent definition already contains a "User-directed override" rule under Consultation Triggers that says to honor explicit collaboration requests. The PM ignored this rule and wrote the epic without consulting SE at all. The team lead had to manually spawn SE for the consultation afterward.

**Root cause -- the spawning constraint**: A spawned agent cannot spawn another agent. This is an architectural constraint of the platform, not a bug. There are two ways to spawn agents:
1. **Direct spawn** -- the team lead (or top-level Claude) spawns a subagent via Task/Agent tool. Only one level deep.
2. **Agent Teams** -- the team lead creates a team and spawns members. Teammates communicate via messaging but cannot spawn new members. If a teammate needs a peer, it must REQUEST the team lead to spawn one.

Either way, spawning is only one level deep. PM cannot spawn SE. When PM needs an expert consultation, PM must either:
- **Outside a team**: Message back to the team lead/user saying "I need SE consultation before I can finalize this -- please spawn SE with these questions."
- **Inside a team**: Message the team lead to spawn the needed agent.

The E-058 failure happened because PM was spawned as a subagent (one level deep), could not spawn SE, and **instead of escalating the constraint, just skipped the consultation entirely**. The fix must make the escalation path explicit and mandatory.

**Why the existing rule failed**: The user-directed override rule (added in E-047) is present but insufficient:
1. It is a paragraph of guidance buried under a table header -- not a procedural gate that the PM must pass through.
2. There is no mandatory step in the PM's planning workflow that forces scanning the user's request for collaboration directives before writing stories.
3. The anti-patterns section does not call out "skipping user-requested consultation" as a named failure mode.
4. The language is soft ("honor that request") rather than mandatory ("MUST consult the named agent before writing stories").
5. `workflow-discipline.md` has no rule about consultation compliance -- the enforcement is entirely within the PM agent definition, which proved insufficient.
6. The rule says nothing about what to do when the PM **cannot** spawn the requested expert -- no escalation path is defined.

**A second failure mode**: During E-058 formation, the PM also prescribed specific implementation details in story Technical Approach sections (e.g., specific bash patterns like `${BASH_SOURCE[0]}` vs `$0`). This crosses the Technical Delegation Boundary -- the PM decides what to build and why; the implementing agent decides how. Story Technical Approach sections should describe the problem and constraints, not dictate code.

**Precedent**: This follows the pattern established by E-019/E-027 (context-layer routing errors) and E-029 (the fix). In those cases, a memory note and domain description were insufficient to prevent routing errors -- only a procedural checklist step (the context-layer routing check in Dispatch Procedure step 6) stopped the recurrence. The same principle applies here: prose guidance is not enforceable; procedural checkpoints are.

**Expert consultation**: Claude Architect reviewed this DRAFT epic and provided findings that have been incorporated. CA confirmed: no conflicts with existing rules detected, defense-in-depth redundancy (PM agent def + workflow-discipline.md) is intentional and valuable, no additional files needed beyond what the epic identifies. CA recommended adding E-059-04 for the implementation-prescriptiveness guardrail.

## Goals
- Add a mandatory procedural checkpoint to the PM's planning workflow that catches user-directed consultation requests before stories are written, with an explicit escalation path when PM cannot spawn the requested expert
- Strengthen the user-directed override rule with MUST language and a concrete failure example
- Add "skipping user-requested consultation" as a named anti-pattern in the PM agent definition
- Add a consultation compliance rule to `workflow-discipline.md` so the enforcement is not solely within one agent's definition
- Add "prescribing implementation details" as a named anti-pattern and strengthen the Technical Delegation Boundaries section

## Non-Goals
- Changing how domain-triggered consultations work (the existing table-based triggers are fine)
- Adding automated enforcement (hooks, scripts) -- this is a context-layer rule change
- Modifying the dispatch pattern or team composition rules
- Adding consultation requirements beyond what the user explicitly requests
- Changing the platform's spawning architecture (the one-level-deep constraint is a fact, not a bug)

## Success Criteria
- The PM agent definition contains anti-patterns that name both "skipping user-requested consultation" and "prescribing implementation details" with real-incident context
- The PM's "How Work Flows" step 3 (Refinement) includes a mandatory pre-step to scan for collaboration directives, with an explicit escalation path when PM cannot spawn
- `workflow-discipline.md` contains a "Consultation Compliance Gate" rule
- The user-directed override paragraph uses MUST language and includes a concrete example of the failure it prevents
- The Technical Delegation Boundaries section and Quality Checklist are strengthened to prevent implementation prescriptiveness
- All changes are consistent across files (no contradictions between PM agent def and workflow-discipline.md)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-059-01 | Add consultation compliance anti-pattern and strengthen override rule in PM agent definition | DONE | None | claude-architect |
| E-059-02 | Add consultation compliance gate to workflow-discipline.md | DONE | None | claude-architect |
| E-059-03 | Add PM lessons-learned entries for consultation-skip and implementation-prescriptiveness incidents | DONE | E-059-01, E-059-04 | claude-architect |
| E-059-04 | Add implementation-prescriptiveness guardrail to PM agent definition | DONE | None | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

### Files in scope
The following files need modification:

1. **`.claude/agents/product-manager.md`** (stories 01 and 04) -- Five changes across two stories:
   - **(01) Anti-Patterns section**: Add a new numbered item naming "skipping user-requested consultation" as a failure mode. Reference the real incident (PM wrote an epic solo after user said "work with SE"). Include the spawning constraint and escalation path. Follow the pattern of anti-pattern 4, which references E-019/E-027.
   - **(01) Consultation Triggers > User-directed override paragraph**: Strengthen from "honor that request" to "MUST consult the named agent via Task tool before writing any stories -- or if unable to spawn, escalate to the team lead/user with specific questions for the named agent." Add a concrete negative example.
   - **(01) How Work Flows > step 3 (Refinement)**: Expand to include a consultation pre-step: "Before writing stories, scan the user's request for explicit collaboration directives (imperative verb + agent name). If found, consult the named agent via Task tool first -- or if unable to spawn, escalate to the team lead/user with specific questions for the named agent. Then consult domain experts per the Consultation Triggers table..." The pre-step goes here (in the procedural workflow), NOT in the Task Types table (which is for classification, not procedure).
   - **(04) Anti-Patterns section**: Add a new numbered item naming "prescribing implementation details" as a failure mode. Technical Approach sections describe the problem and constraints, not the code solution (no specific function names, variable names, or code patterns).
   - **(04) Technical Delegation Boundaries section**: Strengthen with explicit guidance that story Technical Approach sections describe what needs to change and why, not how to code it. Add: "Story Technical Approach sections describe the problem and constraints, not the code solution."
   - **(04) Quality Checklist**: Add item: "Technical Approach sections describe the problem and constraints, not the code solution (no specific function names, variable names, or code patterns)."

2. **`.claude/rules/workflow-discipline.md`** (story 02) -- Add a new section "Consultation Compliance Gate" between "Dispatch Authorization Gate" and "Work Authorization Gate". Content must include the escalation path for when PM cannot spawn. Defense-in-depth rationale: the PM agent def is loaded only for PM; workflow-discipline.md is loaded for all agents including the team lead, who can flag violations.

3. **`.claude/agent-memory/product-manager/lessons-learned.md`** (story 03) -- Add two new sections:
   - "Consultation Compliance" documenting: (a) the incident (user said "work with SE," PM wrote the epic solo), (b) root cause (spawning constraint + no escalation path + guidance-style rule without procedural enforcement), (c) the fix (E-059), (d) the pattern: "prose guidance is not enforceable; procedural checkpoints are" (echoing the E-029 lesson).
   - "Implementation Prescriptiveness" documenting: (a) the incident (PM prescribed specific bash patterns in story Technical Approach), (b) the principle (PM decides what/why, implementing agent decides how), (c) the fix (E-059-04).

### Design principles
- Follow the E-029 pattern: when a rule fails because it is descriptive rather than procedural, add a mandatory checkpoint step to the workflow.
- Keep changes minimal and targeted. Do not reorganize sections or rewrite unrelated content.
- Use MUST/MUST NOT language for enforceable rules. Use descriptive language only for explanations.
- Reference the real incident honestly -- do not minimize the failure.
- The consultation pre-step belongs in "How Work Flows" step 3 (Refinement), NOT in the Task Types table. The table classifies PM interactions; the workflow steps are the procedural checkpoints.
- Defense-in-depth redundancy between PM agent def and workflow-discipline.md is intentional. PM agent def is loaded only for PM sessions. workflow-discipline.md is loaded for all agents, so the team lead can catch violations too.

### Spawning constraint -- the escalation path
The key behavioral fix is: when PM cannot spawn the requested expert (because spawning is one-level-deep), PM MUST escalate rather than skip. The escalation path depends on context:
- **Outside a team**: Message back to the team lead/user: "I need [agent] consultation before I can finalize this -- please spawn [agent] with these questions: [specific questions]."
- **Inside a team**: Message the team lead: "Please spawn [agent] for consultation on [specific topic]."

This escalation path must appear in: the anti-pattern text (story 01), the Refinement pre-step (story 01), the Consultation Compliance Gate (story 02), and the lessons-learned entry (story 03).

### Parallel execution analysis
- E-059-01, E-059-02, and E-059-04 modify different files (01 and 04 both modify product-manager.md but in different sections -- however, per Parallel Execution Rules, since they touch the same file, one must depend on the other or they must run sequentially).
- **Execution order**: E-059-01 first (main consultation fix to product-manager.md), then E-059-02 and E-059-04 in parallel (02 touches workflow-discipline.md; 04 touches product-manager.md but 01 will be done), then E-059-03 last (depends on both 01 and 04 for anti-pattern numbers).
- Alternatively: E-059-01 and E-059-02 in parallel (different files), then E-059-04 (same file as 01), then E-059-03 (depends on 01 and 04).

## Open Questions
None -- all resolved during CA consultation:
- **Pre-step placement**: Goes in "How Work Flows" step 3 (Refinement), NOT in the Task Types table. The table is for classification, not procedure. (CA finding #2)
- **Defense-in-depth redundancy**: Intentional and valuable. PM agent def is loaded only for PM; workflow-discipline.md is loaded for all agents including team lead who can flag violations. (CA finding #4)

## History
- 2026-03-06: Created as DRAFT. PM acknowledged the consultation-skip failure and scoped this epic to add structural guardrails. All stories assigned to claude-architect (context-layer work).
- 2026-03-06: CA review completed. Incorporated all findings: (1) added E-059-04 for implementation-prescriptiveness guardrail, (2) moved consultation pre-step from Task Types table to How Work Flows step 3, (3) made AC-1 say "new numbered item" not "number 5", (4) resolved both open questions, (5) expanded E-059-03 to cover both failure modes, (6) added spawning constraint root cause and escalation path throughout. Epic set to READY.
- 2026-03-06: Epic dispatched. All 4 stories executed sequentially by claude-architect (01 -> 02 -> 04 -> 03). All acceptance criteria verified by PM. Epic COMPLETED. No documentation impact (context-layer only, no user-facing docs affected).
