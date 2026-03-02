# E-016: Evolve Project Manager to Product Manager

## Status
`COMPLETED`

## Overview
Transform the project-manager from a spec-formatting robot into a strategic Product Manager, and upgrade the orchestrator from a haiku-powered keyword matcher into a smart router that can read project state. The current PM is 523 lines -- 200+ of which are embedded templates that already exist in `/.project/templates/` -- and has no guidance on WHAT to build or WHY. The orchestrator cannot read files and adds hops without adding value. This epic rewrites both agent definitions, simplifies the dispatch pattern, and makes the orchestrator the default agent via settings.json.

## Background & Context

No expert consultation required -- scope defined through a multi-agent team analysis (codebase-analyst + architect agents) that evaluated a 67K-line reference project and produced detailed recommendations. User confirmed 4 key design decisions:

1. **Orchestrator model upgrade**: haiku -> sonnet, with Read/Glob/Grep tools (no Write/Edit/Bash). Smart routing requires reading project state.
2. **PM model upgrade**: sonnet -> opus. Strategic product decisions deserve the best model.
3. **Kill Dispatch Manifest**: Replace Mode 2's verbose manifest format with a simple one-line error. The manifest was never actually useful -- it was a workaround for a design flaw (routing dispatch through the orchestrator).
4. **Default agent**: Set `"agent": "orchestrator"` in `.claude/settings.json` so the orchestrator is the identity-level default, not just a contextual suggestion.

### What Prompted This

The PM currently knows HOW to format stories (templates, numbering, file organization) but has zero guidance on:
- What to build and why (product strategy)
- How to discover requirements (task types)
- When to delegate vs. decide (technical boundaries)
- How to structure responses (response formats)

The orchestrator cannot read files, so it routes purely on keyword matching. It cannot check epic status, read story files, or understand project context before routing. This makes it a dumb relay that adds latency without adding intelligence.

E-015 (Fix Agent Dispatch) is now COMPLETED. It introduced the Dispatch Manifest as a workaround for the nested-subagent constraint. This epic supersedes that tactical fix: instead of accommodating the PM running as a subagent, we simplify the rule to "PM must run in main session for dispatch" and emit a one-line error otherwise.

## Goals
- Reduce the PM agent definition from 523 lines to approximately 200-250 lines by removing embedded templates and redundant process documentation
- Add explicit PM task types (discover, plan, clarify, triage, close) that guide WHAT the PM does, not just HOW it formats output
- Add technical delegation boundaries so the PM knows when to hand off vs. decide
- Add consultation trigger rules so stories arrive pre-informed by domain experts
- Add structured response formats for each task type
- Upgrade the orchestrator to sonnet with Read/Glob/Grep tools and an explicit routing table
- Remove the Dispatch Manifest pattern from all files that reference it
- Make the orchestrator the default agent in settings.json

## Non-Goals
- This epic does NOT change the story/epic template files in `/.project/templates/` -- they are fine
- This epic does NOT change any implementing agent definitions (general-dev, data-engineer, api-scout, baseball-coach) beyond what is needed in their "Orchestrator Expectations" sections
- This epic does NOT add new agents or remove existing agents
- This epic does NOT change the epic/story numbering scheme
- This epic does NOT implement Agent Teams -- that is a separate concern
- This epic does NOT change the PM's memory file format

## Success Criteria
1. The PM agent definition (`/.claude/agents/project-manager.md`) is under 300 lines, contains no embedded templates, and includes explicit task types with structured response formats.
2. The orchestrator agent definition (`/.claude/agents/orchestrator.md`) specifies `model: sonnet` and includes `Read`, `Glob`, `Grep` in its tools list but NOT `Write`, `Edit`, or `Bash`.
3. `/.claude/settings.json` contains `"agent": "orchestrator"`.
4. `/.claude/rules/dispatch-pattern.md` contains no "Dispatch Manifest Format" section and states the one-line error rule for subagent context.
5. `CLAUDE.md` Agent Ecosystem table and Workflow Contract section reflect the new PM identity and orchestrator capabilities.
6. `/.claude/rules/workflow-discipline.md` is updated to reflect PM task types.
7. No file is modified by more than one story (parallel execution safe).

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-016-01 | Rewrite PM agent definition | DONE | None | claude-architect |
| E-016-02 | Rewrite orchestrator agent definition | DONE | None | claude-architect |
| E-016-03 | Update settings.json -- make orchestrator default agent | DONE | E-016-02 | claude-architect |
| E-016-04 | Simplify dispatch-pattern.md rule | DONE | None | claude-architect |
| E-016-05 | Update CLAUDE.md agent ecosystem section | DONE | E-016-01, E-016-02 | claude-architect |
| E-016-06 | Update workflow-discipline.md and multi-agent-patterns skill | DONE | E-016-01 | claude-architect |

## Technical Notes

### Parallel Execution Map

```
Wave 1 (no dependencies):  E-016-01, E-016-02, E-016-04
Wave 2 (after Wave 1):     E-016-03 (needs 02), E-016-06 (needs 01)
Wave 3 (after Wave 1):     E-016-05 (needs 01 + 02)
```

### File Ownership (No Conflicts)

| File | Story | Action |
|------|-------|--------|
| `/.claude/agents/project-manager.md` | E-016-01 | REWRITE |
| `/.claude/agents/orchestrator.md` | E-016-02 | REWRITE |
| `/.claude/settings.json` | E-016-03 | MODIFY |
| `/.claude/rules/dispatch-pattern.md` | E-016-04 | REWRITE |
| `/CLAUDE.md` (Agent Ecosystem + Workflow Contract sections only) | E-016-05 | MODIFY |
| `/.claude/rules/workflow-discipline.md` | E-016-06 | MODIFY |
| `/.claude/skills/multi-agent-patterns/SKILL.md` | E-016-06 | MODIFY |

### PM Task Types (New Concept)

The rewritten PM should have explicit task types that guide its behavior:

- **discover**: Understand the problem space. Ask questions. Research. Consult experts. Output: problem statement, constraints, open questions.
- **plan**: Create epics and stories. Break work into vertical slices. Output: epic.md + story files.
- **clarify**: Refine an existing story or epic based on new information. Output: updated story/epic files.
- **triage**: Review backlog, recommend priorities, assess blocked work. Output: status summary with recommendations.
- **close**: Verify acceptance criteria, mark stories DONE, archive completed epics, review ideas backlog. Output: updated status files.

### PM Technical Delegation Boundaries (New Concept)

The PM should know what it decides and what it delegates:

**PM decides**: What to build, why, priority order, acceptance criteria, story scope, when an epic is READY.
**PM delegates**: How to build it (code approach), whether an API endpoint exists (api-scout), what a coach needs (baseball-coach), agent architecture (claude-architect), schema design (data-engineer).

The PM packages context for implementing agents but does NOT diagnose code bugs, review implementations for correctness, or make technology choices.

### Orchestrator Tool Set

The orchestrator gets Read, Glob, Grep tools to enable:
- Reading epic.md files to check status before routing
- Checking story statuses to know what is TODO vs. IN_PROGRESS
- Understanding project structure to route accurately

It does NOT get Write, Edit, or Bash. This is a structural enforcement: the orchestrator routes, it does not modify. If it could edit files, it would be tempted to "help" rather than delegate.

### Dispatch Simplification

Replace the Dispatch Manifest pattern with a simple rule:

**Current (E-015 pattern)**: PM has Mode 1 (main session, dispatch normally) and Mode 2 (subagent, produce Dispatch Manifest).

**New (E-016 pattern)**: PM has one dispatch mode. If it detects it is in a subagent context (CLAUDECODE=1 already set), it emits: "ERROR: Dispatch requires the PM to run in the main session. Invoke the project-manager agent directly (not through the orchestrator) and retry." That is the entire Mode 2 behavior.

The orchestrator's routing for "start epic X" remains: tell the user to invoke PM directly.

### Current Line Counts (Baseline)

- `project-manager.md`: 523 lines (frontmatter: 3 lines of YAML + ~30 lines of description examples)
- `orchestrator.md`: 171 lines
- `dispatch-pattern.md`: 65 lines (including frontmatter)
- `workflow-discipline.md`: 27 lines (including frontmatter)
- `CLAUDE.md` Agent Ecosystem + Workflow Contract: ~37 lines (lines 186-222)
- `multi-agent-patterns/SKILL.md`: 212 lines

## Open Questions
None. The four design decisions were confirmed by the user. Scope is locked.

## E-011 Absorption
E-011 (PM Workflow Discipline) is partially superseded by this epic:
- **E-011-01** (PM workflow standards doc): ABANDONED -- content folded into E-016-01 (AC-12, atomic status update protocol)
- **E-011-02** (audit script): KEPT -- independently valuable, no conflict with E-016
- **E-011-03** (PM def audit step): ABANDONED -- superseded by E-016-01 (AC-11, audit script reference)
- **E-011-04** (rules updates): ABANDONED -- superseded by E-016-01 + E-016-06
E-011 remains ACTIVE until E-011-02 completes, then archives.

## Skill Integration
Skills in `.claude/skills/` are currently orphaned -- zero agent definitions reference them. This epic inlines the most critical skill content directly into agent definitions:
- **multi-agent-patterns**: Verbatim relay rule inlined into orchestrator anti-patterns (E-016-02 AC-4). "Never summarize" dispatch principle inlined into PM dispatch mode (E-016-01 AC-13). Skill itself updated in E-016-06.
- **context-fundamentals**: "Read minimum for routing" inlined into orchestrator file-based routing (E-016-02 AC-6). Artifact staleness note inlined into PM memory instructions (E-016-01 AC-14).
- **filesystem-context**: "Read minimum for routing" principle inlined into orchestrator (E-016-02 AC-6).
Full skills remain as deep reference. Post-E-016: context-fundamentals and filesystem-context need a terminology pass (project-manager -> product-manager). Capture as IDEA.

## History
- 2026-03-01: Created. Epic set to READY. Scope defined through multi-agent team analysis. User confirmed 4 key design decisions. 6 stories written. No expert consultation required.
- 2026-03-01: Refined. E-011 absorption analysis complete -- stories 01/03/04 abandoned, content folded into E-016-01 ACs 11-15. Skill integration strategy applied -- critical content inlined into E-016-01 and E-016-02 ACs. AC gaps sharpened (E-016-05 DoD, E-016-06 AC-3). Epic remains READY.
