# E-061: Proactive Agent Handoffs

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Reduce handoff latency and coordination overhead in Agent Teams dispatch by making handoffs proactive rather than reactive. Adds story-level dispatch metadata (Agent Hint, Handoff Context), a lightweight pre-spawn communication pattern, and updates PM's dispatch procedure to use them.

## Background & Context
The current dispatch flow (dispatch-pattern.md, product-manager.md, workflow-discipline.md) works correctly but is reactive at several points:

1. **No story-level routing hint**: Stories declare "Files to Create or Modify" but not which agent type should execute them. PM must cross-reference files against the routing table in dispatch-pattern.md every time.

2. **No handoff anticipation**: When story A (wave 1) produces output needed by story B (wave 2), PM assembles the handoff context ad-hoc after A completes. There is no mechanism for the story author to declare at planning time what a story produces for its downstream consumers.

3. **No multi-wave spawn communication**: The existing Dispatch Team section enables proactive spawning at team creation when all needed agent types are known. However, for multi-wave epics where later waves need different agent types, PM waits until stories are eligible before requesting those agents from the team lead. PM knows the full dependency graph at dispatch start but has no protocol for communicating later-wave needs upfront.

**Expert consultation**: claude-architect review completed 2026-03-07. Seven concerns raised and incorporated. Key changes from review: consolidated from 5 stories to 3 (scope was overbuilt), simplified Pre-Spawn Protocol from a multi-step procedure to a concise communication pattern, added "routing table wins" language for Agent Hint, grouped Agent Hint and Handoff Context as dispatch metadata in the story template. CLAUDE.md Workflow Contract reviewed -- no changes needed (step 5 is abstract enough to cover the pre-spawn refinement).

**Key constraint**: Only the team lead can spawn agents. This epic does NOT attempt to change that -- it works within it by making the team lead's spawning more informed and timely.

## Goals
- Eliminate PM's repeated inference of agent types by adding an optional routing hint to story files
- Enable richer cross-story handoff context by declaring handoff outputs in story files at planning time
- Reduce serial wait time during multi-wave dispatches by communicating spawn needs upfront

## Non-Goals
- Changing the platform constraint (only team lead spawns agents)
- Automating dispatch without PM coordination
- Adding hooks or automated enforcement (this is process/documentation improvement)
- Changing the Agent Teams architecture or SendMessage protocol
- Adding new agent types

## Success Criteria
- Story template includes optional Agent Hint and Handoff Context fields as dispatch metadata
- dispatch-pattern.md documents how PM uses Agent Hint for routing and includes a pre-spawn communication pattern
- PM agent definition's dispatch procedure references Agent Hint, Handoff Context, and the pre-spawn pattern
- Epic template's Dispatch Team section includes derivation guidance from story Agent Hints

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-061-01 | Add Dispatch Metadata to Story and Epic Templates | DONE | None | architect |
| E-061-02 | Add Agent Hint and Pre-Spawn Protocol to Dispatch Pattern | DONE | None | architect |
| E-061-03 | Update PM Dispatch Procedure for Proactive Handoffs | DONE | E-061-01, E-061-02 | architect |

## Dispatch Team
- claude-architect

## Technical Notes

### Consolidation Rationale
The architect review identified that the original 5 stories (totaling ~50-60 lines of changes across 4 files) created more overhead than the work itself. Consolidated to 3 stories with clean file ownership: each story owns its files exclusively, eliminating the file-conflict dependency problem.

### Story Template Changes (E-061-01)
Two new optional fields are added to `/.project/templates/story-template.md`, grouped under a `## Dispatch Metadata` comment block between "Files to Create or Modify" and "Definition of Done":

**Agent Hint**: A single optional line declaring the agent type for the story. Values are agent names as they appear in `.claude/agents/` filenames: `software-engineer`, `data-engineer`, `claude-architect`, `docs-writer`, `ux-designer`, `api-scout`. (The Agent Selection table in dispatch-pattern.md uses `general-purpose` with role annotations -- the hint uses the role name directly since that is what humans and PM understand.) PM retains final routing authority -- the hint is advisory. If the hint disagrees with the routing table, the routing table wins. Context-layer routing precedence still overrides the hint.

**Handoff Context**: An optional bulleted list where the story author declares what artifacts this story's completion produces for downstream stories. Each bullet names a downstream story ID and describes what it needs. This replaces the current ad-hoc pattern where PM assembles cross-story context after a story completes.

### Epic Template Changes (E-061-01)
The Dispatch Team section comment in `/.project/templates/epic-template.md` gets additional guidance: PM should derive the Dispatch Team from the union of Agent Hint values across all stories. When any story lacks a hint, PM uses file-path inference for that story and includes its agent type in the union.

### Dispatch Pattern Changes (E-061-02)
Three additions to `/.claude/rules/dispatch-pattern.md`:

1. **Agent Hint paragraph** in the Agent Selection section: Stories may carry an Agent Hint field; PM should prefer the hint over file-path inference when present, but context-layer routing precedence still overrides.

2. **Pre-spawn communication** added to the Spawning Scenarios section: At dispatch start, PM reviews the full dependency graph and messages the team lead with all agent types needed across all waves, not just the first. This extends the existing "At team creation" batch spawn (which handles single-wave epics) to multi-wave cases. The team lead spawns wave-1 agents immediately; PM signals when to spawn later-wave agents. For single-wave epics, the existing batch-spawn behavior is unchanged. The existing "Mid-dispatch (cascading)" paragraph is updated to position cascading as a fallback for truly unexpected agent needs discovered mid-dispatch, distinct from planned multi-wave spawning.

3. **Context Packaging update**: When assigning a story, PM checks completed upstream stories for Handoff Context declarations and includes the declared artifacts in the context block alongside the full story file and Technical Notes.

### PM Agent Definition Changes (E-061-03)
Updates to `/.claude/agents/product-manager.md`:

- New sub-step after step 5 (identify available teammates): PM sends a spawn plan to the team lead listing all agent types needed across all waves.
- Step 6 update: PM reads the Agent Hint field first, falls back to file-path inference when absent. Context-layer routing precedence still overrides.
- Step 7 update: When assigning a story with upstream Handoff Context declarations, PM includes the declared artifacts in the context block.
- Context Block Format update: Add a "Handoff context from completed dependencies" block.

### Chicken-and-Egg Note
The E-061 story files themselves use Agent Hint and Handoff Context sections ahead of the template update. This is intentional -- the stories demonstrate the pattern they introduce. The sections are non-standard until E-061-01 updates the template.

### CLAUDE.md Assessment
The CLAUDE.md Workflow Contract (step 5) says PM "request[s] additional spawns from the team lead for newly unblocked stories." This phrasing is abstract enough to cover the pre-spawn refinement without modification. No CLAUDE.md changes needed for this epic.

## Open Questions
- None.

## History
- 2026-03-07: Created as DRAFT with 5 stories.
- 2026-03-07: claude-architect review completed. Seven concerns raised: (1) Agent Hint adds a third routing source -- keep minimal with "routing table wins" language, (2) Handoff Context placement -- group as dispatch metadata, (3) Pre-Spawn Protocol over-specified -- simplify to a few sentences, (4) 5 stories too many for ~50-60 lines -- consolidate to 3, (5) chicken-and-egg pattern -- document in Technical Notes, (6) CLAUDE.md impact -- assessed, no changes needed, (7) dependency table bug -- fixed in consolidation. Consolidated from 5 to 3 stories. Set to READY.
- 2026-03-07: Codex spec review completed. 1 P1, 3 P2, 3 P3 findings. All REFINED: (P1) E-061-03 AC-1 step reference corrected to match actual PM dispatch procedure numbering, (P2) Agent Hint values clarified to use agent filenames not `general-purpose`, (P2) pre-spawn protocol reconciled with existing batch-spawn behavior, (P2) epic Background narrowed to accurately describe the baseline, (P3) DoD items made testable across all 3 stories. Epic remains READY.
- 2026-03-07: Dispatch completed. All 3 stories DONE. E-061-01 and E-061-02 executed in parallel (wave 1), E-061-03 cascaded (wave 2). Artifacts modified: story template, epic template, dispatch-pattern.md, product-manager.md. No documentation impact -- all changes are context-layer process/workflow improvements. Epic COMPLETED.
