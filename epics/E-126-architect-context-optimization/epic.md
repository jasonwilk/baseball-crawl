# E-126: Optimize Claude-Architect Context Footprint

## Status
`READY`

## Overview
Reduce the claude-architect agent's ambient context footprint by ~21% (~172 lines) by deferring reference material to a skill and consolidating MEMORY.md topic files. This keeps the agent effective while freeing context budget for actual work.

## Background & Context
The architect completed a self-review against context-fundamentals principles and identified ~172 lines of deferrable or duplicated content across its agent definition (~96 lines) and MEMORY.md (~76 lines). The agent definition is the second largest at 227 lines, and MEMORY.md is the largest at 174 lines (approaching the 200-line truncation threshold). No external consultation required -- the architect provided the analysis.

## Goals
- Defer ~96 lines of reference material from the agent definition to a load-on-demand skill
- Reduce MEMORY.md by ~76 lines through topic file extraction and duplication removal
- Combined ambient footprint: ~811 lines to ~639 lines

## Non-Goals
- Restructuring the architect's core responsibilities or capabilities
- Modifying other agents' definitions or memory files
- Changing the context-fundamentals skill itself

## Success Criteria
- Agent definition is under 140 lines (down from 227)
- MEMORY.md is under 110 lines (down from 174)
- All deferred content is accessible via skill or topic file reference
- No information is lost -- everything moves, nothing is deleted without a surviving reference

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-126-01 | Create agent-standards skill and refactor agent definition | TODO | None | claude-architect |
| E-126-02 | Consolidate MEMORY.md with topic files | TODO | None | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

### TN-1: Agent-Standards Skill Structure
The new skill at `.claude/skills/agent-standards/SKILL.md` should follow the project's established skill file pattern:
- **Activation Triggers**: When creating, modifying, or auditing agent definitions
- **Key Concepts**: Design Methodology (the 7-step process currently in the agent definition)
- **Standards**: Agent File Format, Required Frontmatter, Canonical Section Skeleton, Quality Standards, Research & Investigation, Output Formats (the full Standards section, ~85 lines)
- **References**: Links to existing agent files as examples

Content should be adapted to the skill format, not raw copy-pasted from the agent definition.

### TN-2: Agent Definition Refactoring
The agent definition (`.claude/agents/claude-architect.md`) changes:
- Remove the Standards section (replaced by skill reference)
- Remove the Design Methodology section (moved to skill)
- Replace the 9-agent roster in the Identity section with a one-line pointer to CLAUDE.md's Agent Ecosystem table
- Add a Skills section entry for `agent-standards` with load trigger

### TN-3: MEMORY.md Cleanup
The MEMORY.md (`.claude/agent-memory/claude-architect/MEMORY.md`) changes:
- Move ingest workflow logs (~50 lines of per-endpoint integration history) to a new topic file `ingest-workflow-log.md`; replace with a 2-line summary linking to the topic file
- Move Codex configuration details (~9 lines) to a new topic file `codex-config.md`; replace with a 1-line reference
- Remove Agent Ecosystem section (~12 lines) -- CLAUDE.md is authoritative
- Remove Agent Frontmatter section (~5 lines) -- covered by the agent-standards skill content

### TN-4: File Ownership
Both stories modify files exclusively in `.claude/`. No `src/`, `tests/`, `scripts/`, or `docs/` files are touched.

## Open Questions
- None

## History
- 2026-03-18: Created from architect self-review findings
- 2026-03-18: Refined after PM + architect adversarial review. 6 findings incorporated: testable AC-5/AC-6 verification methods, skill structure guidance in TN-1, broadened load trigger in AC-2, retained-sections note and summary guidance in E-126-02 Notes.
- 2026-03-18: Refined after context-fundamentals review. 3 notes added to E-126-02: Topic File Index update reminder for new topic files, ingest log header consolidation guidance, "When to Create New Agents" edge case verification.
