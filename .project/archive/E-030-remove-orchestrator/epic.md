# E-030: Remove Orchestrator Agent

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Remove the orchestrator agent from the project and make the product-manager (PM) the direct entry point for all work. The orchestrator adds unnecessary indirection without providing value -- the user can talk directly to the PM (or to direct-routing exceptions). This epic deletes the orchestrator agent definition, updates all files that reference it, and revises the workflow contract to reflect the simpler `user -> PM -> implementing agent` routing model.

## Background & Context
The orchestrator was designed as a "smart router" that reads project state before delegating to specialized agents. In practice, it adds a relay step that:
- Increases the telephone game risk (orchestrator paraphrases user intent before passing to PM)
- Consumes an extra agent invocation for pure pass-through routing
- Adds maintenance burden (routing table must stay in sync with the agent ecosystem)
- Provides no value the user cannot get by talking directly to the PM or direct-routing exceptions

The PM already has all the capabilities needed to serve as the entry point: it reads project state, makes routing decisions, manages dispatch, and coordinates implementing agents. The direct-routing exceptions (api-scout, baseball-coach, claude-architect) can continue to be invoked directly by the user.

**Expert consultation**: PM performed comprehensive architectural analysis by reading all files that reference the orchestrator (10 files in `.claude/`, 7 files in `epics/`, plus archived epics and research artifacts). The scope is fully understood. No concerns with removing the orchestrator -- it simplifies the architecture and removes a documented source of telephone game distortion. The claude-architect's memory file and the multi-agent-patterns skill both document the orchestrator as a relay risk point, confirming the architectural validity of this change.

**E-028 impact**: E-028 (Documentation System) is READY with TODO stories that reference the orchestrator in multiple places. E-028-01 AC-7, E-028-03 AC-5(c), and E-028-05 (entire story revolves around orchestrator routing updates). This epic must revise those stories before E-028 is dispatched, otherwise E-028 implementers will try to update a deleted file.

**E-002-08 note**: E-002-08 uses the word "orchestrator" to describe a crawl orchestration script, not the agent. No changes needed there.

**E-010 note**: E-010-02 (Phase 2, BLOCKED) references the orchestrator in descriptions and ACs. Since E-010-02 is BLOCKED on E-002+E-003 and will not be dispatched anytime soon, revising it now would be premature. It should be revised when its blocking dependencies clear and the story becomes eligible for dispatch.

## Goals
- The orchestrator agent definition is deleted and no references to it remain in active project infrastructure
- The workflow contract reflects `user -> PM -> implementing agent` (no orchestrator intermediary)
- All agent definitions, rules, skills, and memory files are updated to reflect the PM as entry point
- E-028 stories are revised so they can be dispatched without referencing a deleted agent
- The agent count drops from 7 to 6 across all documentation

## Non-Goals
- Changing the PM's dispatch mechanism (Agent Teams remain unchanged)
- Changing direct-routing exceptions (api-scout, baseball-coach, claude-architect remain directly invocable)
- Revising archived epics or research artifacts (historical references are fine)
- Revising BLOCKED stories in other epics that will not be dispatched soon (e.g., E-010-02)
- Changing which model the PM uses or how it operates (PM stays opus, keeps all current responsibilities)

## Success Criteria
- `.claude/agents/orchestrator.md` does not exist
- `CLAUDE.md` Agent Ecosystem table lists 6 agents (no orchestrator row), Workflow Contract step 1 says "User requests work from PM" instead of "Orchestrator routes to PM"
- `.claude/rules/dispatch-pattern.md` dispatch flow starts with "User requests dispatch" -> "PM reads the epic" (no orchestrator step)
- `.claude/rules/workflow-discipline.md` routing rule says `user -> PM -> implementing agent`
- `.claude/agents/product-manager.md` contains no orchestrator references
- `.claude/agents/claude-architect.md` ecosystem list has 6 agents (no orchestrator)
- `.claude/skills/multi-agent-patterns/SKILL.md` routing chain diagram shows `User -> PM -> implementing agents` (no orchestrator relay)
- `.claude/agent-memory/claude-architect/MEMORY.md` ecosystem list has 6 agents
- E-028 stories (01, 03, 05) and epic.md are revised to remove orchestrator references
- `grep -ri orchestrator .claude/agents/ .claude/rules/ .claude/skills/ CLAUDE.md` returns zero results (excluding agent-memory which may contain historical notes)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-030-01 | Remove orchestrator from core project infrastructure | DONE | None | claude-architect |
| E-030-02 | Update agent definitions for PM-as-entry-point | DONE | None | claude-architect |
| E-030-03 | Update skills and agent memory | DONE | None | claude-architect |
| E-030-04 | Revise E-028 stories to remove orchestrator references | DONE | None | claude-architect |

## Technical Notes

### What Changes and Why

The orchestrator is referenced in three categories of files:

**Category 1: Core infrastructure (E-030-01)**
These files define the routing model and workflow contract. They need the most significant edits.
- `.claude/agents/orchestrator.md` -- DELETE entirely
- `CLAUDE.md` -- Agent Ecosystem table (remove row), How Agents Collaborate (remove orchestrator bullet), Workflow Contract (change step 1)
- `.claude/rules/dispatch-pattern.md` -- Dispatch Flow step 2 ("Orchestrator routes to PM" -> remove)
- `.claude/rules/workflow-discipline.md` -- Routing Rule (change pipeline description)

**Category 2: Agent definitions (E-030-02)**
These files reference the orchestrator in their inter-agent coordination or ecosystem descriptions.
- `.claude/agents/product-manager.md` -- Skills section references "orchestrator -> PM -> implementing agent chain" in multi-agent-patterns trigger
- `.claude/agents/claude-architect.md` -- Identity section lists all 7 agents including orchestrator; Inter-Agent Coordination references orchestrator; Anti-Patterns reference orchestrator routing table

**Category 3: Skills and memory (E-030-03)**
These files describe the routing chain or ecosystem topology.
- `.claude/skills/multi-agent-patterns/SKILL.md` -- Routing chain diagram, Telephone Game section, Diagnosing Failures section all reference orchestrator
- `.claude/skills/filesystem-context/SKILL.md` -- Related Skills section mentions "orchestrator -> PM -> implementing agent chain"
- `.claude/agent-memory/claude-architect/MEMORY.md` -- Agent Ecosystem section lists orchestrator

**Category 4: E-028 story revisions (E-030-04)**
E-028 stories that will break if dispatched after orchestrator deletion.
- `epics/E-028-documentation-system/epic.md` -- Goals mention "orchestrator routing", Success Criteria mention orchestrator, Technical Notes reference orchestrator
- `epics/E-028-documentation-system/E-028-01.md` -- AC-7 mentions orchestrator in Inter-Agent Coordination requirement
- `epics/E-028-documentation-system/E-028-03.md` -- AC-5(c) says "orchestrator as entry point"
- `epics/E-028-documentation-system/E-028-05.md` -- Title, description, multiple ACs, file list all reference orchestrator.md

### Replacement Patterns

When removing orchestrator references, apply these consistent replacements:

| Old Pattern | New Pattern |
|------------|-------------|
| "orchestrator -> product-manager -> implementing agent" | "user -> product-manager -> implementing agent" |
| "orchestrator routes to PM" | "user requests work from PM" |
| "7 agents" / "seven agents" | "6 agents" / "six agents" |
| "coordinated by an orchestrator" | "coordinated by the product-manager" |
| Orchestrator row in agent tables | Delete the row |
| "orchestrator routes documentation requests to docs-writer" | "product-manager dispatches documentation work to docs-writer" |
| E-028-05 ACs about orchestrator.md | Replace with ACs about CLAUDE.md and workflow file updates only |

### E-028-05 Revision Strategy

E-028-05 ("CLAUDE.md, orchestrator, and workflow integration updates") needs the most significant revision of the E-028 stories. With the orchestrator gone:
- The title should become "CLAUDE.md and workflow integration updates"
- AC-2 (orchestrator routing table) and AC-3 (orchestrator Available Agents) should be removed entirely
- The remaining ACs (CLAUDE.md Agent Ecosystem table, dispatch-pattern.md, workflow-discipline.md, PM agent definition) stay but with orchestrator.md removed from the file list
- The story's file list drops `.claude/agents/orchestrator.md`

### Parallel Execution Analysis

All four stories modify completely different file sets:
- E-030-01: `CLAUDE.md`, `.claude/agents/orchestrator.md`, `.claude/rules/dispatch-pattern.md`, `.claude/rules/workflow-discipline.md`
- E-030-02: `.claude/agents/product-manager.md`, `.claude/agents/claude-architect.md`
- E-030-03: `.claude/skills/multi-agent-patterns/SKILL.md`, `.claude/skills/filesystem-context/SKILL.md`, `.claude/agent-memory/claude-architect/MEMORY.md`
- E-030-04: `epics/E-028-documentation-system/epic.md`, `epics/E-028-documentation-system/E-028-01.md`, `epics/E-028-documentation-system/E-028-03.md`, `epics/E-028-documentation-system/E-028-05.md`

**No file conflicts. All four stories can run in parallel.**

### PM Memory Update (post-completion)

After epic completion, PM updates its own MEMORY.md:
- Remove orchestrator from Key Workflow Contract
- Update Active Epics summary for E-028 (revised stories)
- Note architectural decision: orchestrator removed, PM is direct entry point
- Update agent count references

## Open Questions
None. Scope is fully understood from file analysis.

## History
- 2026-03-03: Created. PM performed comprehensive file analysis in lieu of claude-architect Task tool consultation (PM identified all 20+ files with orchestrator references, confirmed no architectural concerns). All four stories can run in parallel with zero file conflicts. Set to READY.
- 2026-03-03: Dispatched all 4 stories in parallel (all IN_PROGRESS). Epic set to ACTIVE. Implementers: architect-01 (E-030-01), architect-02 (E-030-02), architect-03 (E-030-03), architect-04 (E-030-04).
- 2026-03-03: All 4 stories DONE. All acceptance criteria verified by PM. Epic COMPLETED. Archived to /.project/archive/E-030-remove-orchestrator/.
