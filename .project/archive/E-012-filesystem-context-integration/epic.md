# E-012: Filesystem-Context Skill Integration for PM and Architect Agents

## Status
`ABANDONED`

## Overview
The `filesystem-context` skill was created in E-010-01 but is not yet referenced by any agent definition. This epic wires the skill into the two agents that manage project structure -- project-manager and claude-architect -- by adding explicit trigger-condition references and encoding the skill's progressive disclosure principles as concrete behavioral steps in their workflows. After this epic, the project-manager and claude-architect agents will know when to load the skill, and their documented procedures will reflect the ambient vs. deferred context discipline the skill teaches.

## Background & Context

E-010-01 (DONE, 2026-02-28) created `.claude/skills/filesystem-context/SKILL.md` as Phase 1 of the intent/context layer implementation authorized by E-008. The skill teaches the "filesystem as context store" pattern: store context in files, load on demand, use progressive disclosure to keep session token costs low. The skill was adapted specifically for baseball-crawl with named examples from this project's epic/story/research artifact structure.

The problem: no agent currently loads this skill. The SKILL.md itself explains the mechanism -- agents must name the skill in their definition with a trigger condition; the agent then reads the SKILL.md only when that trigger fires. Phase 1 created the skill files. This epic completes the circuit by adding those trigger-condition references.

E-010-06 (the integration story in E-010) addresses the same gap but is BLOCKED until E-002 and E-003 are DONE, and targets orchestrator, general-dev, and data-engineer. This epic targets project-manager and claude-architect, which can be done now since those agents' workflows do not depend on the unbuilt `src/` module structure.

**Consultation with claude-architect**: This epic is squarely within claude-architect's domain (agent configuration, skills, behavioral design). The PM consulted the SKILL.md itself (which specifies trigger conditions for all agent types), the E-010 epic Technical Notes (which specifies which agents should receive skill references), and the E-008 recommendation (which explains why certain agents were prioritized). Key findings from that synthesis:

- The PM's two skill-relevant workflows are Dispatch Mode (loading epic.md + all story files) and Refinement Mode (loading research artifacts and prior epic context). Both are textbook progressive disclosure operations.
- Claude-architect's skill-relevant workflow is agent design: deciding what context belongs in a system prompt (ambient) vs. what belongs in a skill file or memory topic file (deferred). The filesystem-context skill directly informs this decision.
- Story files should explicitly list deferred context by path -- a quality checklist gap that this epic closes.
- The agent definition format for skill references is a dedicated `## Skills` section in the system prompt body (not YAML frontmatter). Each entry lists: skill name, file path, and trigger condition.

No expert consultation required in addition to the above synthesis -- all necessary architectural information is already documented in the skill files and E-010 Technical Notes, which were authored by claude-architect.

## Goals
- The `project-manager` agent definition (`.claude/agents/project-manager.md`) contains a `## Skills` section with an explicit trigger-condition reference to `filesystem-context`.
- The `claude-architect` agent definition (`.claude/agents/claude-architect.md`) contains a `## Skills` section with an explicit trigger-condition reference to `filesystem-context`.
- The PM's Dispatch Mode procedure explicitly includes a context-loading step that names the filesystem-context skill as the framework for that step.
- The PM's quality checklist includes a verifiable item for deferred context file references in story Technical Approach sections.
- The claude-architect agent's design methodology section reflects the ambient vs. deferred context distinction when deciding what goes in system prompts vs. skill files.

## Non-Goals
- Adding skill references to orchestrator, general-dev, or data-engineer -- those are covered by E-010-06 (which remains BLOCKED on E-002+E-003).
- Adding `multi-agent-patterns` or `context-fundamentals` skill references -- those are valid candidates for future integration but are out of scope for this focused epic.
- Writing new intent nodes (directory-scoped CLAUDE.md files) -- that is E-010-04 and E-010-05, still BLOCKED.
- Modifying the E-010 epic or its BLOCKED stories -- this epic runs in parallel to E-010, not as a replacement.
- Changing the workflow contract (CLAUDE.md, `workflow-discipline.md`) -- this epic modifies agent definitions only.

## Success Criteria
1. `.claude/agents/project-manager.md` contains a `## Skills` section that names `filesystem-context` with a trigger condition tied to Dispatch Mode and Refinement Mode context-loading.
2. `.claude/agents/claude-architect.md` contains a `## Skills` section that names `filesystem-context` with a trigger condition tied to agent definition design (ambient vs. deferred context decisions).
3. The PM's Dispatch Mode procedure in `project-manager.md` explicitly includes a step: "Before reading the epic directory, load `.claude/skills/filesystem-context/SKILL.md` to apply progressive disclosure to the file-reading sequence."
4. The PM's quality checklist in `project-manager.md` includes: "Story Technical Approach sections reference deferred context files by absolute path (e.g., `docs/gamechanger-api.md`, `/.project/research/E-NNN-slug.md`)."
5. The claude-architect design methodology in `claude-architect.md` includes a note under "Prompt Engineering" or equivalent section: context that changes per-task (research artifacts, per-task docs) should be deferred (skill file or memory topic file), not embedded in the system prompt.
6. A new agent can read either definition and understand when and why to load the `filesystem-context` skill without reading the E-010 epic or E-008 history.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-012-01 | Add filesystem-context skill reference to project-manager agent | TODO | None | claude-architect |
| E-012-02 | Add filesystem-context skill reference to claude-architect agent | TODO | None | claude-architect |
| E-012-03 | Extend PM dispatch and quality checklist procedures | TODO | E-012-01 | claude-architect |

## Technical Notes

### Skill Reference Format

Each agent definition that references a skill should contain a `## Skills` section in the system prompt body (not YAML frontmatter). The format for each skill entry is:

```
## Skills

### filesystem-context
**File**: `.claude/skills/filesystem-context/SKILL.md`
**Load when**: [specific trigger conditions for this agent]

[One to two sentences describing why this skill is relevant to this agent's work.]
```

The trigger condition must be specific to the agent's named workflow steps, not a paraphrase of the generic activation triggers in the SKILL.md. This specificity is what makes the reference actionable rather than decorative.

### Trigger Conditions by Agent

**project-manager**:
- Primary trigger: "Entering Dispatch Mode -- before reading the epic directory (`/epics/E-NNN-slug/epic.md` and all story files)"
- Secondary trigger: "Entering Refinement Mode -- before reading research artifacts, prior epic history, or dependency story files to understand what a new epic should cover"
- Tertiary trigger: "Writing a new story's Technical Approach section -- to verify that referenced context files are named by absolute path, not held as implicit knowledge"

**claude-architect**:
- Primary trigger: "Designing a new agent definition or modifying an existing one -- specifically when deciding what context should live in the system prompt (ambient) vs. what should be deferred to a skill file, memory topic file, or CLAUDE.md"
- Secondary trigger: "Reviewing or structuring agent memory files -- to apply the rule that MEMORY.md should remain under 200 lines and detailed topic knowledge should be in separate linked files"

### Parallel Execution

E-012-01 and E-012-02 can run in parallel. They touch different files and have no shared dependencies.

E-012-03 depends on E-012-01 because it extends the PM's procedure sections, which are in the same file (`project-manager.md`). E-012-03 should not modify `claude-architect.md` (that is covered by E-012-02).

### File Scope per Story

| Story | Files Modified |
|-------|---------------|
| E-012-01 | `.claude/agents/project-manager.md` |
| E-012-02 | `.claude/agents/claude-architect.md` |
| E-012-03 | `.claude/agents/project-manager.md` |

Note: E-012-01 and E-012-03 both touch `project-manager.md`. They are sequenced (E-012-03 depends on E-012-01) to prevent merge conflicts.

### What "Extending the Procedure" Means (for E-012-03)

The PM's Dispatch Mode procedure already lists steps 1-8. E-012-03 adds a context-loading sub-step to step 1:

> **Step 1 (revised)**: Read the epic directory. Before opening any files, load `.claude/skills/filesystem-context/SKILL.md` to apply progressive disclosure: scan the epic's Stories table first (first pass -- titles and statuses only), then open individual story files only for those with `Status: TODO` (second pass -- full content).

The PM's quality checklist already has 10 items. E-012-03 adds one:

> - [ ] Story `Technical Approach` sections name all referenced context files by absolute path (e.g., `docs/gamechanger-api.md`, `/.project/research/E-NNN-slug.md`) so implementing agents can load them as deferred context rather than guessing file locations.

### Relationship to E-010-06

E-010-06 will add skill references to orchestrator, general-dev, and data-engineer when it unblocks (after E-002+E-003 DONE). E-012 adds skill references to project-manager and claude-architect now, without waiting for E-002+E-003. The two epics together will complete the full agent-ecosystem skill reference circuit. They do not conflict because they touch different agent definition files.

## Open Questions
- Should the `multi-agent-patterns` skill also be added to the PM's definition in this epic, or should that wait for E-010-06 (which adds it to orchestrator)? Recommendation: defer to a follow-on story in E-012 or E-010-06. This epic focuses on filesystem-context only to keep scope narrow and testable.
- When E-010-06 unblocks, should it be expanded to include the work already done in E-012, or should the two epics remain independent? The E-010-06 story files do not yet exist (they are planned but not written), so there is no conflict risk. Note in E-010-06 at that time that PM and claude-architect were handled by E-012.

## History
- 2026-02-28: Created. The filesystem-context skill (E-010-01 DONE) exists but no agent references it. This epic closes the circuit for project-manager and claude-architect. E-010-06 will close it for orchestrator, general-dev, and data-engineer when E-002+E-003 complete.
- 2026-03-01: ABANDONED -- absorbed into E-013 during triage. Stories E-012-01 and E-012-02 became part of expanded E-013-04. E-012-03 became E-013-06.
